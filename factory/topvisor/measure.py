"""Измерения Топвизора: что настроено, что снято и сколько стоит съём.

Только бесплатные чтения (`get/projects_2/projects` с регионами,
`get/positions_2/history`, `get/positions_2/checker/price`). Съём здесь не
запускается никогда — это `factory.topvisor.collect`.

Зачем отдельный сборщик. Ежедневный инвентарь seo-engine работает в «лёгком»
режиме: чтение поисковых систем, регионов и истории в нём заглушено
(`daily_inventory_sync._lean_transport` возвращает пустые списки и
`NOT_READ_SAFETY`). Пустые `engines`/`regions` и `last_position_at: null` в его
выгрузке — свойство сборщика, а не аккаунта; по ним нельзя было заключать,
что поисковые системы не назначены и позиций нет. Здесь эти поля читаются.

Состояние проекта различается явно, ноль и «не измерено» не смешиваются:

* ``ARCHIVED``      — проект архивный (`on = -1`): не проверяется, история не читается;
* ``NO_KEYWORDS``   — запросов нет;
* ``NO_REGIONS``    — нет ни одного включённого региона поисковой системы;
* ``NEVER_CHECKED`` — настроен, но дат съёма в истории нет;
* ``HAS_DATA``      — есть съём; дата последнего — `last_check`;
* ``READ_ERROR``    — чтение не удалось (причина в `error`); остальные проекты
  обрабатываются дальше.

Позиция — число из истории. «Не найден в пределах проверенной глубины»
(`'--'`) остаётся `found: false, position: null` и в полосах идёт отдельной
строкой; в число он не превращается и отсутствием в индексе не считается.
"""
from __future__ import annotations

import datetime as dt
import json
from collections import Counter
from pathlib import Path

from factory.errors import FactoryError

КОРЕНЬ = Path(__file__).resolve().parents[2]
ВЫХОД = КОРЕНЬ / "var" / "topvisor"
ЯДРО = КОРЕНЬ / "config" / "topvisor-cores.json"
ДНЕЙ_ИСТОРИИ = 35

#: Полосы позиций, общие для отчётов и выбора задач.
ПОЛОСЫ = (("1-3", 1, 3), ("4-10", 4, 10), ("11-30", 11, 30), ("31-50", 31, 50))
ВНЕ = "51+"
НЕ_НАЙДЕН = "not_found_within_depth"

ПОИСКОВИКИ = {0: "yandex", 1: "google"}
УСТРОЙСТВА = {0: "desktop", 1: "tablet", 2: "smartphone"}


def полоса(позиция: int | None) -> str:
    if позиция is None:
        return НЕ_НАЙДЕН
    for имя, низ, верх in ПОЛОСЫ:
        if низ <= позиция <= верх:
            return имя
    return ВНЕ


def _int(значение, по_умолчанию=None):
    try:
        return int(str(значение).strip())
    except (TypeError, ValueError):
        return по_умолчанию


def регионы(проект: dict) -> list[dict]:
    """Регионы проекта плоским списком: индекс, поисковик, устройство, глубина.

    Форма ответа `show_searchers_and_regions`: у проекта `searchers[]`, у
    поисковика `key`/`searcher_key`, `name`, `enabled` и `regions[]`, у
    региона `index`, `key`, `name`, `lang`, `device`, `depth`, `enabled`.
    Поля читаются с запасными именами: ответ живого API сохраняется сырым в
    отчёте, и по нему форма уточняется, а не угадывается дальше."""
    итог = []
    for п in проект.get("searchers") or []:
        if not isinstance(п, dict):
            continue
        ключ_пс = _int(п.get("key", п.get("searcher_key")))
        for р in п.get("regions") or []:
            if not isinstance(р, dict):
                continue
            итог.append({
                "index": _int(р.get("index")),
                "searcher_key": ключ_пс,
                "searcher": ПОИСКОВИКИ.get(ключ_пс, str(п.get("name") or ключ_пс)),
                "searcher_enabled": _int(п.get("enabled"), 1) != 0,
                "region_key": _int(р.get("key", р.get("region_key"))),
                "region_name": р.get("name", р.get("region_name")),
                "lang": р.get("lang", р.get("region_lang")),
                "device": УСТРОЙСТВА.get(_int(р.get("device", р.get("region_device")), 0)),
                "depth": _int(р.get("depth", р.get("region_depth"))),
                "enabled": _int(р.get("enabled"), 1) != 0,
            })
    return итог


def _цели() -> dict[tuple[str, str], str | None]:
    """(домен, запрос) → целевой URL из ядра. Нет ядра — пусто, не ошибка."""
    try:
        ядро = json.loads(ЯДРО.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {(с["domain"], к["query"].strip().lower()): к.get("target_url")
            for с in ядро.get("sites") or [] for г in с.get("groups") or []
            for к in г.get("keywords") or []}


def разобрать_историю(ответ: dict, регион: dict) -> dict:
    """Последний съём региона: дата, позиции по запросам, полосы, сравнение
    с предыдущим съёмом. Только то, что в ответе; пустое — пустое."""
    даты = sorted(str(д) for д in (ответ.get("existsDates") or []))
    строки = []
    for к in ответ.get("keywords") or []:
        if not isinstance(к, dict):
            continue
        данные = к.get("positionsData") or {}
        по_дате = {}
        for ключ, ячейка in данные.items():
            if isinstance(ячейка, dict):
                по_дате[str(ключ).split(":", 1)[0]] = ячейка
        строки.append((к, по_дате))
    if not даты:
        return {"exists_dates": [], "last_check": None, "keywords": []}
    последняя = даты[-1]
    прошлая = даты[-2] if len(даты) > 1 else None
    запросы = []
    for к, по_дате in строки:
        ячейка = по_дате.get(последняя) or {}
        сырое = str(ячейка.get("position", "")).strip()
        позиция = _int(сырое) if сырое.isdigit() else None
        было = (по_дате.get(прошлая) or {}).get("position") if прошлая else None
        было = _int(было) if str(было or "").strip().isdigit() else None
        запросы.append({
            "keyword_id": к.get("id"),
            "query": к.get("name"),
            "group": к.get("group_name"),
            "position": позиция,
            "found": позиция is not None,
            # Пустая ячейка за дату съёма — «не измерено», а не «не найден».
            "measured": сырое != "",
            "band": полоса(позиция) if сырое != "" else None,
            "previous_position": было,
            "relevant_url": ячейка.get("relevant_url") or None,
        })
    return {"exists_dates": даты, "last_check": последняя,
            "previous_check": прошлая, "keywords": запросы,
            "region_index": регион.get("index")}


def измерить_проект(client, проект: dict, домен: str, *, сегодня: dt.date,
                    цели: dict) -> dict:
    ид = _int(проект.get("id"))
    запись = {"domain": домен, "project_id": ид, "on_raw": проект.get("on"),
              "regions": регионы(проект), "state": None, "error": None,
              "keywords_total": None, "checks": [], "price_one_check_rub": None}
    try:
        if _int(проект.get("on")) == -1:
            запись["state"] = "ARCHIVED"
            return запись
        запись["keywords_total"] = len(client.keywords(ид))
        включённые = [р for р in запись["regions"]
                      if р["enabled"] and р["searcher_enabled"] and р["index"] is not None]
        if not запись["keywords_total"]:
            запись["state"] = "NO_KEYWORDS"
        if not включённые:
            запись["state"] = запись["state"] or "NO_REGIONS"
            return запись
        date1 = (сегодня - dt.timedelta(days=ДНЕЙ_ИСТОРИИ)).isoformat()
        for р in включённые:
            разбор = разобрать_историю(
                client.history(ид, [р["index"]], date1, сегодня.isoformat()), р)
            for к in разбор["keywords"]:
                к["target_url"] = цели.get((домен, str(к["query"] or "").strip().lower()))
            разбор.update({"searcher": р["searcher"], "device": р["device"],
                           "region_name": р["region_name"], "depth": р["depth"],
                           "bands": dict(Counter(к["band"] for к in разбор["keywords"]
                                                 if к["band"]))})
            запись["checks"].append(разбор)
        if запись["keywords_total"]:
            запись["price_one_check_rub"] = client.checker_price(
                [ид], [р["index"] for р in включённые])
        последние = [ч["last_check"] for ч in запись["checks"] if ч["last_check"]]
        запись["last_check"] = max(последние) if последние else None
        if not запись["state"]:
            запись["state"] = "HAS_DATA" if последние else "NEVER_CHECKED"
    except FactoryError as exc:
        запись["state"] = "READ_ERROR"
        запись["error"] = exc.reason
    return запись


def измерить(client, *, домены: set[str] | None = None,
             сегодня: dt.date | None = None) -> dict:
    """Все проекты аккаунта (или только `домены`). Ошибка проекта не
    останавливает остальные."""
    from factory.cell import withdrawn  # noqa: PLC0415
    from factory.topvisor.plan import normalize_domain  # noqa: PLC0415

    сегодня = сегодня or dt.datetime.now(dt.timezone.utc).date()
    сейчас = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    выведено = withdrawn.выведенные()
    цели = _цели()
    проекты = client.projects_with_regions()
    сайты = []
    for п in проекты:
        домен = normalize_domain(str(п.get("url") or п.get("site") or ""))
        if домены is not None and домен not in домены:
            continue
        if withdrawn.выведен(домен, набор=выведено):
            # История и доступ сохраняются, регулярных чтений и съёмов нет.
            сайты.append({"domain": домен, "project_id": _int(п.get("id")),
                          "on_raw": п.get("on"), "state": "WITHDRAWN",
                          "regions": регионы(п)})
            continue
        сайты.append(измерить_проект(client, п, домен, сегодня=сегодня, цели=цели))
    return {"measured_at": сейчас, "source": "topvisor api (read-only)",
            "projects_total": len(проекты), "sites": сайты,
            "raw_project_sample": проекты[0] if проекты else None}


def записать(итог: dict, каталог: Path = ВЫХОД) -> Path:
    """`measure-latest.json` и строки позиций в `positions.jsonl` без
    повторов (дата съёма × проект × регион × запрос)."""
    каталог.mkdir(parents=True, exist_ok=True)
    путь = каталог / "measure-latest.json"
    путь.write_text(json.dumps(итог, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    журнал = каталог / "positions.jsonl"
    было = set()
    if журнал.is_file():
        for строка in журнал.read_text(encoding="utf-8").splitlines():
            try:
                з = json.loads(строка)
            except ValueError:
                continue
            было.add((з.get("date"), з.get("project_id"), з.get("region_index"), з.get("query")))
    новые = []
    for с in итог.get("sites") or []:
        for ч in с.get("checks") or []:
            for к in ч.get("keywords") or []:
                ключ = (ч.get("last_check"), с.get("project_id"), ч.get("region_index"), к.get("query"))
                if not ч.get("last_check") or ключ in было:
                    continue
                было.add(ключ)
                новые.append({"date": ч["last_check"], "domain": с["domain"],
                              "project_id": с["project_id"], "region_index": ч.get("region_index"),
                              "searcher": ч.get("searcher"), "device": ч.get("device"),
                              "region_name": ч.get("region_name"), "depth": ч.get("depth"),
                              **{k: к.get(k) for k in ("query", "group", "position", "found",
                                                       "band", "relevant_url", "target_url")}})
    if новые:
        with журнал.open("a", encoding="utf-8") as f:
            for з in новые:
                f.write(json.dumps(з, ensure_ascii=False) + "\n")
    return путь
