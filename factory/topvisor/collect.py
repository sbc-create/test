"""Платный съём позиций — только в пределах лимита владельца.

Без файла `config/topvisor-budget.json` с месячным лимитом съём не
запускается вовсе (BLOCKED_INPUT): «лимит не задан» не означает «ноль» и тем
более «без ограничений». Допуск выдаётся на один вызов `checker/go` одного
проекта и набора регионов после проверок:

1. месячный лимит владельца прочитан;
2. цена этого съёма названа сервисом (`get/positions_2/checker/price`,
   бесплатно) — своя оценка цены вместо ответа сервиса не подставляется;
3. расход за календарный месяц (журнал `var/topvisor/spend.jsonl`) плюс цена
   не превышают ни лимита, ни дневной доли остатка
   (остаток / оставшиеся дни месяца) — бюджет не съедается в первые дни;
4. тот же проект с теми же регионами сегодня (по UTC) ещё не снимался —
   повторных платных проверок одной конфигурации за сутки нет;
5. регионы Яндекса снимаются в окне 20:00–05:59 МСК: в это время Топвизор
   проверяет через Яндекс Search API (документация, 26.10.2026).

Очерёдность: регионы Яндекса раньше Google; сайты — по поисковым визитам
Метрики за последнюю неделю, по убыванию (визиты только упорядочивают
очередь и в оценку позиций не входят).
"""
from __future__ import annotations

import datetime as dt
import json
import calendar
from dataclasses import dataclass
from pathlib import Path

from factory.errors import BlockedInput

КОРЕНЬ = Path(__file__).resolve().parents[2]
БЮДЖЕТ = КОРЕНЬ / "config" / "topvisor-budget.json"
ЖУРНАЛ = КОРЕНЬ / "var" / "topvisor" / "spend.jsonl"
МСК = dt.timezone(dt.timedelta(hours=3))
ЯНДЕКС = 0


@dataclass(frozen=True)
class Допуск:
    project_id: int
    regions_indexes: tuple[int, ...]
    сумма: float
    метод: str = "edit/positions_2/checker/go"

    def покрывает(self, метод: str, payload: dict) -> bool:
        if метод != self.метод:
            return False
        фильтры = payload.get("filters") or []
        ид = [v for f in фильтры if isinstance(f, dict) and f.get("name") == "id"
              for v in (f.get("values") or [])]
        return (ид == [self.project_id]
                and tuple(sorted(int(i) for i in payload.get("regions_indexes") or ()))
                == tuple(sorted(self.regions_indexes)))

    def payload(self) -> dict:
        return {"filters": [{"name": "id", "operator": "EQUALS", "values": [self.project_id]}],
                "regions_indexes": list(self.regions_indexes)}


def лимит(путь: Path = БЮДЖЕТ) -> float:
    try:
        данные = json.loads(путь.read_text(encoding="utf-8"))
        значение = float(данные["monthly_limit_rub"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise BlockedInput(
            "лимит расходов на съём позиций не задан владельцем",
            field="topvisor.budget",
            required_input="месячный лимит в рублях (config/topvisor-budget.json, monthly_limit_rub)",
            blocks_stage="topvisor",
        ) from exc
    if значение <= 0:
        raise BlockedInput("лимит владельца равен нулю: съём не запускается",
                           field="topvisor.budget", blocks_stage="topvisor")
    return значение


def расходы(журнал: Path = ЖУРНАЛ) -> list[dict]:
    if not журнал.is_file():
        return []
    итог = []
    for строка in журнал.read_text(encoding="utf-8").splitlines():
        try:
            итог.append(json.loads(строка))
        except ValueError:
            continue
    return итог


def в_окне_яндекса(момент: dt.datetime) -> bool:
    час = момент.astimezone(МСК).hour
    return час >= 20 or час < 6


def допуск_съёма(*, project_id: int, regions: list[dict], цена: float | None,
                 сейчас: dt.datetime, лимит_руб: float, журнал: list[dict]) -> tuple[Допуск | None, str]:
    """Решение по одному съёму. Возвращает (допуск, причина) — причина
    пишется в отчёт и при отказе, и при допуске."""
    if цена is None:
        return None, "сервис не назвал цену съёма — без цены не запускаем"
    индексы = tuple(sorted(р["index"] for р in regions))
    if any(р["searcher_key"] == ЯНДЕКС for р in regions) and not в_окне_яндекса(сейчас):
        return None, "вне окна Яндекса 20:00–05:59 МСК"
    сегодня = сейчас.date().isoformat()
    for з in журнал:
        if (з.get("project_id") == project_id and str(з.get("at", ""))[:10] == сегодня
                and tuple(sorted(з.get("regions_indexes") or ())) == индексы):
            return None, "эта конфигурация сегодня уже снималась — повтор не нужен"
    месяц = сегодня[:7]
    потрачено = round(sum(float(з.get("price_rub") or 0) for з in журнал
                          if str(з.get("at", ""))[:7] == месяц), 2)
    дней = calendar.monthrange(сейчас.year, сейчас.month)[1]
    осталось_дней = дней - сейчас.day + 1
    доля = (лимит_руб - потрачено) / осталось_дней
    сегодня_потрачено = sum(float(з.get("price_rub") or 0) for з in журнал
                            if str(з.get("at", ""))[:10] == сегодня)
    if потрачено + цена > лимит_руб:
        return None, f"месячный лимит {лимит_руб} ₽: потрачено {потрачено}, съём {цена}"
    if сегодня_потрачено + цена > доля + 1e-9:
        return None, (f"дневная доля остатка {round(доля, 2)} ₽ исчерпана: "
                      f"сегодня {round(сегодня_потрачено, 2)}, съём {цена}")
    return Допуск(project_id, индексы, цена), f"допущен: {цена} ₽, потрачено за месяц {потрачено}"


def очередь(измерение: dict, визиты: dict[str, float]) -> list[tuple[dict, list[dict]]]:
    """(сайт, регионы) в порядке съёма: сначала все регионы Яндекса по
    сайтам с наибольшими поисковыми визитами, затем Google."""
    готовые = [с for с in измерение.get("sites") or []
               if с.get("state") in ("NEVER_CHECKED", "HAS_DATA") and с.get("keywords_total")]
    готовые.sort(key=lambda с: -float(визиты.get(с["domain"], 0)))
    итог = []
    for ключ in (ЯНДЕКС, 1):
        for с in готовые:
            регионы = [р for р in с.get("regions") or []
                       if р["searcher_key"] == ключ and р["enabled"] and р["searcher_enabled"]
                       and р["index"] is not None]
            if регионы:
                итог.append((с, регионы))
    return итог


def записать_расход(project_id: int, domain: str, regions: tuple[int, ...], цена: float,
                    момент: dt.datetime, журнал: Path = ЖУРНАЛ) -> None:
    журнал.parent.mkdir(parents=True, exist_ok=True)
    with журнал.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"at": момент.strftime("%Y-%m-%dT%H:%M:%SZ"), "project_id": project_id,
                            "domain": domain, "regions_indexes": list(regions),
                            "price_rub": цена}, ensure_ascii=False) + "\n")
