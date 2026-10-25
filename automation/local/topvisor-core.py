"""Ядро запросов Топвизора по измеренным поисковым входам сайта (бесплатная подготовка).

Только чтение. Источники:

* домены — канонический реестр ячеек (`config/site-cells.json`) без тестовых
  имён и без исключённых (`factory.cell.withdrawn`); отдельного перечня
  доменов здесь нет;
* стратегия — запись манифеста Топвизора (`factory.topvisor.manifest`:
  `focus`, группы раздела);
* поисковые входы — выгрузка штатного сборщика Метрики
  (`var/analytics/cabinet-latest.json`, `daily_search_landing_pages`,
  визиты по дням × поисковая система × адрес), Яндекс и Google раздельно;
* название страницы — запись каталога (`factory.qwen.editorial.факты`), то
  есть то же имя, что видит посетитель. Название не придумывается: страница
  без записи каталога в ядро не попадает и названа в `skipped`.

Запрос строится из названия, целевой URL — сама страница входа. Для страниц
серий добавляется «<название> <N> сезон <M> серия» — номера берутся из адреса.
Визиты Метрики — это не клики и не позиции: они только выбирают, что
отслеживать. Позиция появится после съёма Топвизором.

    python3 automation/local/topvisor-core.py [--per-engine 8] [--out путь.json]
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import re
import sys
import time
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(КОРЕНЬ))

from factory.cell import withdrawn  # noqa: E402
from factory.topvisor import manifest  # noqa: E402

ВЫГРУЗКА = КОРЕНЬ / "var" / "analytics" / "cabinet-latest.json"
РЕЕСТР = КОРЕНЬ / "config" / "site-cells.json"
ТАЙТЛ = re.compile(r"^/(?:title|anime)/([^/?#]+)/?(?:season[-/](\d+)/episode[-/](\d+)/?)?$")


def _движок(имя: str) -> str:
    н = (имя or "").lower()
    return "google" if "google" in н else "yandex" if "yandex" in н else "other"


ДАТЫ: set[str] = set()


def входы(выгрузка: dict) -> dict[str, dict[str, collections.Counter]]:
    """домен → движок → путь → визиты за период показателя (даты — в ДАТЫ)."""
    итог: dict[str, dict[str, collections.Counter]] = {}
    for запись in выгрузка.get("domains") or []:
        по = collections.defaultdict(collections.Counter)
        for м in запись.get("measurements") or []:
            if м.get("key") != "daily_search_landing_pages" or not м.get("measured"):
                continue
            for строка in м.get("value") or []:
                изм = строка.get("dimensions") or []
                if len(изм) < 3:
                    continue
                ДАТЫ.add(str(изм[0].get("name") or ""))
                движок = _движок(изм[1].get("id") or изм[1].get("name"))
                адрес = str(изм[2].get("name") or "")
                путь = "/" + адрес.split("://", 1)[-1].split("/", 1)[-1] if "://" in адрес else адрес
                путь = путь.split("?", 1)[0].split("#", 1)[0] or "/"
                по[движок][путь] += float((строка.get("metrics") or [0])[0] or 0)
        итог[запись["domain"]] = по
    return итог


def домены_реестра() -> list[dict]:
    ячейки = json.loads(РЕЕСТР.read_text(encoding="utf-8")).get("cells") or []
    выведено = withdrawn.выведенные()
    return [я for я in ячейки
            if я.get("domain") and not я["domain"].endswith((".localhost", ".test"))
            and not withdrawn.выведен(я["domain"], набор=выведено)
            and я.get("status") in ("live", "not_extracted")]


def название(домен: str, слаг: str, кэш: dict) -> str:
    from factory.qwen import editorial

    ключ = (домен, слаг)
    if ключ not in кэш:
        try:
            кэш[ключ] = str((editorial.факты(домен, слаг).get("facts") or {}).get("name") or "").strip()
        except Exception:  # noqa: BLE001 — отказ каталога = «нет названия», не авария
            кэш[ключ] = ""
        if домен.startswith("yummyani"):
            time.sleep(0.5)  # у Yummy факты читаются со страницы витрины
    return кэш[ключ]


НА_ТАЙТЛ = 2
ДЛИННОЕ = 60


def запрос(имя: str, сезон: str | None, серия: str | None) -> str:
    """Запрос из названия каталога: длинное имя — до двоеточия, без года в
    скобках; номер сезона в конце названия не повторяется перед «N сезон»."""
    текст = re.sub(r"\s*\((?:19|20)\d{2}\)", "", имя).strip()
    if len(текст) > ДЛИННОЕ and ":" in текст:
        текст = текст.split(":", 1)[0].strip()
    if серия:
        текст = re.sub(rf"\s+{re.escape(сезон)}$", "", текст)
        текст = f"{текст} {сезон} сезон {серия} серия"
    return re.sub(r"\s+", " ", текст)


def ядро(домен: str, по: dict[str, collections.Counter], *, на_движок: int, кэш: dict) -> dict:
    spec = manifest.by_domain(домен)
    группы, пропущено = [], []
    for движок in ("yandex", "google"):
        запросы, взято, на_слаг = [], set(), collections.Counter()
        for путь, визиты in по.get(движок, collections.Counter()).most_common():
            if len(запросы) >= на_движок:
                break
            м = ТАЙТЛ.match(путь)
            if not м:
                continue
            слаг, сезон, серия = м.groups()
            if на_слаг[слаг] >= НА_ТАЙТЛ:
                continue
            имя = название(домен, слаг, кэш)
            if not имя:
                пропущено.append({"path": путь, "engine": движок, "reason": "нет записи каталога"})
                continue
            текст = запрос(имя, сезон, серия)
            if текст.lower() in взято:
                continue
            взято.add(текст.lower())
            на_слаг[слаг] += 1
            запросы.append({"query": текст, "target_url": f"https://{домен}{путь}",
                            "basis": {"metric": "ym:s:visits", "engine": движок,
                                      "visits": int(визиты)}})
        if запросы:
            группы.append({"name": f"Входы из поиска — {'Яндекс' if движок == 'yandex' else 'Google'}",
                           "keywords": запросы})
    if spec:
        for г in spec.groups:
            группы.append({"name": г.name, "keywords": [
                {"query": к, "target_url": None,
                 "basis": {"strategy": spec.focus}} for к in г.keywords]})
    визиты = {д: int(sum(по.get(д, {}).values())) for д in ("yandex", "google", "other")}
    return {"domain": домен, "strategy": spec.focus if spec else None,
            "in_manifest": bool(spec), "search_visits": визиты,
            "groups": группы, "skipped": пропущено}


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--per-engine", type=int, default=8)
    р.add_argument("--out", default=str(КОРЕНЬ / "var" / "seo-audit" / "topvisor-core.json"))
    a = р.parse_args()
    выгрузка = json.loads(ВЫГРУЗКА.read_text(encoding="utf-8"))
    по_домену = входы(выгрузка)
    кэш: dict = {}
    сайты = [ядро(я["domain"], по_домену.get(я["domain"], {}), на_движок=a.per_engine, кэш=кэш)
             for я in домены_реестра()]
    сейчас = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    прежний = {}
    if Path(a.out).is_file():
        try:
            прежний = json.loads(Path(a.out).read_text(encoding="utf-8"))
        except ValueError:
            прежний = {}
    def состав(док: dict) -> list:
        return sorted((с["domain"], г["name"], к["query"], к["target_url"])
                      for с in док.get("sites") or [] for г in с["groups"] for к in г["keywords"])
    версия = int(прежний.get("version") or 0)
    изменения = list(прежний.get("changes") or [])
    итог = {"built_at": сейчас,
            "source": {"metrika": str(ВЫГРУЗКА.relative_to(КОРЕНЬ)),
                       "collected_at": выгрузка.get("collected_at"),
                       "measure": "daily_search_landing_pages",
                       "dates": [min(ДАТЫ), max(ДАТЫ)] if ДАТЫ else None},
            "note": ("визиты Метрики выбирают, что отслеживать; это не клики и не позиции. "
                     "Запросы групп стратегии — из манифеста, целевой URL не назначен."),
            "measurement": прежний.get("measurement") or {
                "region": manifest.REGION_MOSCOW,
                "searchers": ["yandex", "google"],
                "device": "решение владельца вместе с бюджетом (U8)",
                "depth": 100,
                "schedule": ("нет: съём платный, лимит автоматических трат 0 ₽; после решения "
                             "владельца — не чаще одного съёма в сутки, повторов за день нет"),
                "status": "awaiting_owner_budget",
                "note": "параметры не меняются без новой версии: иначе замеры несопоставимы"},
            "sites": сайты}
    if состав(итог) != состав(прежний):
        версия += 1
        изменения.append({"version": версия, "at": сейчас,
                          "what": ("первая сборка ядра" if версия == 1 else
                                   "изменён состав запросов или целевых адресов")})
    итог["version"] = версия or 1
    итог["changes"] = изменения
    Path(a.out).write_text(json.dumps(итог, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for с in сайты:
        вх = sum(len(г["keywords"]) for г in с["groups"] if г["name"].startswith("Входы"))
        print(f"{с['domain']:22} визиты Я {с['search_visits']['yandex']:6} G {с['search_visits']['google']:5}"
              f" | запросов по входам {вх:3} | групп всего {len(с['groups'])} | пропущено {len(с['skipped'])}"
              + ("" if с["in_manifest"] else " | НЕТ В МАНИФЕСТЕ"))
    print("итог:", a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
