#!/usr/bin/env python3
"""Сегменты трафика по суткам: весь, без роботов Метрики, без автоматизации.

Зачем. Дашборд показывает один набор чисел на весь трафик, и при наплыве
автоматических заходов «отказы 83 %» говорят о составе трафика, а не о сайте.
Разделять обязательно, и разделять по тому, что измерено, а не по догадке.

Источник — показатель `daily_traffic_profile` выгрузки кабинета Метрики:
`ym:s:visits, ym:s:bounceRate, ym:s:pageDepth, ym:s:avgVisitDurationSeconds`
по измерениям `ym:s:date × lastsignTrafficSource × ym:s:deviceCategory ×
ym:s:browser × ym:s:isRobot`. Средние по строке сводятся во взвешенные по
визитам — иначе среднее от средних врёт тем сильнее, чем неравнее строки.

Три сегмента:

* **весь трафик** — как на дашборде;
* **без роботов Метрики** — строки, где `ym:s:isRobot` = Robots, исключены;
  основание — собственная классификация Метрики, видно в данных;
* **без автоматизации** — дополнительно исключены браузеры из
  `АВТОМАТИЗАЦИЯ` (headless-сборки и известные обходчики). Основание печатается
  по каждому исключению: сколько визитов и какой браузер.

Исходная статистика сохраняется: сегмент «весь трафик» печатается всегда и
первым, а исключённое показывается строкой с числом визитов.

    python3 automation/local/traffic-segments.py --domain yummyani.site \\
        --file artifacts/analytics/analytics-2026-10-19.json
    python3 automation/local/traffic-segments.py --domain yummyani.site --json

Коды: 0 — сегменты посчитаны; 2 — показателя нет или домен не найден.
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys

#: Браузеры, которые НЕ являются человеческим просмотром. Список закрытый и
#: называется в отчёте: «автоматизация» без перечня — это догадка, а не замер.
АВТОМАТИЗАЦИЯ = {
    "headlesschrome", "headless chrome", "phantomjs", "puppeteer", "playwright",
    "selenium", "chrome-lighthouse", "headlessfirefox", "curl", "wget",
    "python-requests", "go-http-client", "java", "scrapy",
}
АРХИВ = pathlib.Path(
    "/home/claude/wt-portable-site-cell-01/artifacts/analytics")


def _мера(домен: dict, ключ: str) -> dict | None:
    for м in домен.get("measurements") or []:
        if м.get("key") == ключ:
            return м
    return None


def строки(значение) -> list[dict]:
    """Строки профиля в разобранном виде."""
    итог = []
    for стр in значение or []:
        изм = [str((и or {}).get("name") or "") for и in стр.get("dimensions") or []]
        мет = стр.get("metrics") or []
        if len(изм) < 5 or len(мет) < 4:
            continue
        итог.append({
            "дата": изм[0], "источник": изм[1], "устройство": изм[2],
            "браузер": изм[3], "робот": изм[4],
            "визиты": float(мет[0] or 0), "отказы": float(мет[1] or 0),
            "глубина": float(мет[2] or 0), "время": float(мет[3] or 0),
        })
    return итог


def автоматизация(браузер: str) -> bool:
    """Браузер ли это человека.

    Слово «headless» проверяется отдельно и первым: Метрика пишет
    «HeadlessChrome», но порядок слов у браузеров разнится («Chrome Headless»),
    и перечень с одним написанием пропустил бы вариант. Остальные обходчики —
    по закрытому списку, чтобы случайно не исключить людей.
    """
    б = браузер.strip().lower()
    if "headless" in б:
        return True
    return any(з in б for з in АВТОМАТИЗАЦИЯ)


def свод(стр: list[dict]) -> dict:
    """Взвешенные по визитам отказы, глубина и время."""
    визиты = sum(с["визиты"] for с in стр)
    if not визиты:
        return {"визиты": 0.0, "отказы": None, "глубина": None, "время": None}
    return {
        "визиты": визиты,
        "отказы": sum(с["отказы"] * с["визиты"] for с in стр) / визиты,
        "глубина": sum(с["глубина"] * с["визиты"] for с in стр) / визиты,
        "время": sum(с["время"] * с["визиты"] for с in стр) / визиты,
    }


def сегменты(стр: list[dict]) -> dict:
    без_роботов = [с for с in стр if с["робот"] != "Robots"]
    без_авто = [с for с in без_роботов if not автоматизация(с["браузер"])]
    return {
        "весь трафик": свод(стр),
        "без роботов Метрики": свод(без_роботов),
        "без роботов и автоматизации": свод(без_авто),
    }


def по_источнику(стр: list[dict], ключ: str) -> dict:
    группы = collections.defaultdict(list)
    for с in стр:
        группы[с[ключ]].append(с)
    return {к: свод(v) for к, v in группы.items()}


def основания(стр: list[dict]) -> list[dict]:
    """Чем обосновано каждое исключение: визиты по браузеру и флагу робота."""
    счёт = collections.Counter()
    for с in стр:
        if с["робот"] == "Robots":
            счёт[("робот Метрики", с["браузер"])] += с["визиты"]
        elif автоматизация(с["браузер"]):
            счёт[("автоматизация по браузеру", с["браузер"])] += с["визиты"]
    return [{"основание": о, "браузер": б, "визиты": в}
            for (о, б), в in счёт.most_common()]


def разобрать(путь: pathlib.Path, домен: str, с_даты: str = "", по_дату: str = "") -> dict:
    try:
        д = json.loads(путь.read_text(encoding="utf-8"))
    except (OSError, ValueError) as сбой:
        return {"измерено": False, "почему": f"{путь}: {сбой}"}
    цели = [x for x in д.get("domains") or [] if x.get("domain") == домен]
    if not цели:
        return {"измерено": False, "почему": f"домена {домен} в выгрузке нет"}
    мера = _мера(цели[0], "daily_traffic_profile")
    if мера is None or not мера.get("measured"):
        причина = (мера or {}).get("state") or "показателя нет в выгрузке"
        return {"измерено": False, "почему": f"daily_traffic_profile: {причина}"}
    стр = строки(мера.get("value"))
    если_окно = с_даты or по_дату
    if если_окно:
        стр = [с for с in стр
               if (not с_даты or с["дата"] >= с_даты)
               and (not по_дату or с["дата"] <= по_дату)]
    if not стр:
        причина = ("профиль пуст" if not если_окно
                   else f"в профиле нет суток в окне {с_даты or '…'}..{по_дату or '…'}")
        return {"измерено": False, "почему": причина}
    дни = sorted({с["дата"] for с in стр})
    период_мера = _мера(цели[0], "visits")
    return {
        "измерено": True,
        "собрано": д.get("collected_at"),
        "дней": len(дни),
        "период": f"{дни[0]}..{дни[-1]}",
        "строк": len(стр),
        "визитов_в_профиле": sum(с["визиты"] for с in стр),
        "визитов_в_показателе": (период_мера or {}).get("value"),
        "сегменты": сегменты(стр),
        "по_источнику": по_источнику(стр, "источник"),
        "по_устройству": по_устройству(стр),
        "по_браузеру": по_источнику(стр, "браузер"),
        "по_дням": {д: сегменты([с for с in стр if с["дата"] == д]) for д in дни},
        "основания": основания(стр),
    }


def по_устройству(стр: list[dict]) -> dict:
    return по_источнику(стр, "устройство")


def _строка(имя: str, с: dict) -> str:
    если = lambda з, ф: ("—" if з is None else format(з, ф))  # noqa: E731
    return (f"{имя:34} визиты {с['визиты']:9.0f}  отказы {если(с['отказы'], '6.2f')} %"
            f"  глубина {если(с['глубина'], '5.3f')}  время {если(с['время'], '7.1f')} с")


def main(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description="сегменты трафика по выгрузке кабинета")
    р.add_argument("--domain", required=True)
    р.add_argument("--file", action="append", default=[],
                   help="файл выгрузки; можно несколько — сравнение периодов")
    р.add_argument("--json", action="store_true")
    р.add_argument("--days", action="store_true", help="печатать разбивку по суткам")
    р.add_argument("--since", default="", help="первая дата окна, ГГГГ-ММ-ДД")
    р.add_argument("--until", default="", help="последняя дата окна, ГГГГ-ММ-ДД")
    дов = р.parse_args(аргв)

    файлы = [pathlib.Path(ф) for ф in дов.file] or [
        pathlib.Path("/home/claude/wt-portable-site-cell-01/var/analytics/cabinet-latest.json")]
    итоги = {str(ф): разобрать(ф, дов.domain, дов.since, дов.until) for ф in файлы}

    if дов.json:
        print(json.dumps(итоги, ensure_ascii=False, indent=2))
        return 0 if any(и["измерено"] for и in итоги.values()) else 2

    for имя, и in итоги.items():
        print(f"=== {имя}")
        if not и["измерено"]:
            print(f"    НЕ ИЗМЕРЕНО — {и['почему']}")
            continue
        print(f"    собрано {и['собрано']}; сутки {и['период']} ({и['дней']});"
              f" строк профиля {и['строк']}")
        print(f"    визитов в профиле {и['визитов_в_профиле']:.0f},"
              f" в показателе visits {и['визитов_в_показателе']}")
        for имя_с, с in и["сегменты"].items():
            print("    " + _строка(имя_с, с))
        print("    по источнику:")
        for к, с in sorted(и["по_источнику"].items(), key=lambda п: -п[1]["визиты"]):
            print("      " + _строка(к, с))
        print("    по устройству:")
        for к, с in sorted(и["по_устройству"].items(), key=lambda п: -п[1]["визиты"]):
            print("      " + _строка(к, с))
        print("    по браузеру (верх):")
        for к, с in sorted(и["по_браузеру"].items(),
                           key=lambda п: -п[1]["визиты"])[:6]:
            print("      " + _строка(к, с))
        print("    основания исключений:")
        for о in и["основания"][:8]:
            print(f"      {о['основание']:28} {о['браузер']:20} визиты {о['визиты']:9.0f}")
        if дов.days:
            print("    по суткам (весь / без роботов / без автоматизации):")
            for д, с in и["по_дням"].items():
                в = с["весь трафик"]["визиты"]
                бр = с["без роботов Метрики"]["визиты"]
                ба = с["без роботов и автоматизации"]["визиты"]
                от = с["без роботов и автоматизации"]["отказы"]
                вр = с["без роботов и автоматизации"]["время"]
                print(f"      {д}  {в:8.0f} / {бр:8.0f} / {ба:8.0f}"
                      f"   чистый сегмент: отказы "
                      f"{'—' if от is None else format(от, '5.1f')} %, время "
                      f"{'—' if вр is None else format(вр, '6.1f')} с")
        print()
    return 0 if any(и["измерено"] for и in итоги.values()) else 2


if __name__ == "__main__":
    sys.exit(main())
