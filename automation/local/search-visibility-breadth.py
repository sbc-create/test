#!/usr/bin/env python3
"""Ширина видимости в поиске: сколько РАЗНЫХ произведений получает входы.

Только чтение артефактов кабинета Метрики.

Зачем отдельная единица. «Путей, получающих входы из поиска» — плохая мера:
один сериал с десятью сериями даёт десять путей, и «хвост из 133 путей» может
оказаться тремя сериалами. Поэтому здесь считаются произведения, а рядом —
доля крупнейшего: именно она показывает, на чём держится аудитория витрины.

Измерено 19.10 этим инструментом (окна 05–11.10 и 12–18.10):

    yummyani.site       84 → 32 произведения, доля крупнейшего 71.7 % → 58.6 %
    animedia.icu        14 → 44
    lordserials22.info  65 → 84
    zonafilm.cc          1 → 111

Выгрузка отдаёт ТОП строк, поэтому «стало меньше» может быть свойством
экспорта. Инструмент печатает число строк по каждому домену в файле: если в
одно и то же число упираются несколько домéнов сразу, это предел, и вывод о
витрине делать нельзя. Отдельного признака «обрезано» в выгрузке нет, поэтому
проверка остаётся за читателем — но данные для неё даются всегда.

Коды возврата: 0 — измерено, 1 — измерено частично (часть домéнов без данных),
2 — не измерено ничего.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
СРЕЗ = "search_landing_pages"
РАЗДЕЛЫ_ПРОИЗВЕДЕНИЙ = ("anime", "title")


def тайтл(путь: str) -> str:
    """Slug произведения из адреса входа или пустая строка.

    Пустая строка — это «адрес не ведёт на произведение» (главная, каталог,
    подборка), а не «произведение неизвестно»: такие адреса в ширину не
    входят, но в визиты входят.
    """
    части = (путь or "").strip("/").split("/")
    if len(части) > 1 and части[0] in РАЗДЕЛЫ_ПРОИЗВЕДЕНИЙ and части[1]:
        return части[1]
    return ""


def срез(файл: pathlib.Path, домен: str) -> dict | None:
    """Входы из поиска по адресам. `None` — не измерено, и это не ноль."""
    try:
        д = json.loads(pathlib.Path(файл).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    спис = д.get("domains")
    if isinstance(спис, dict):
        x = спис.get(домен)
    else:
        x = next((э for э in (спис or []) if э.get("domain") == домен), None)
    if not x:
        return None
    по = {м.get("key"): м for м in (x.get("measurements") or [])}
    м = по.get(СРЕЗ) or {}
    if not м.get("measured"):
        return None
    зн = м.get("value")
    if not isinstance(зн, list):
        return None
    итог: dict[str, float] = {}
    for р in зн:
        путь = next((d.get("name") for d in (р.get("dimensions") or [])
                     if str(d.get("name") or "").startswith("/")), "")
        if not путь:
            continue
        изм = р.get("metrics") or [0]
        итог[путь] = итог.get(путь, 0) + (изм[0] or 0)
    return итог


def ширина(вход: dict) -> dict:
    """Ширина видимости и концентрация по одному срезу."""
    визиты = sum(вход.values())
    по_тайтлам: dict[str, float] = {}
    for п, в in вход.items():
        т = тайтл(п)
        if т:
            по_тайтлам[т] = по_тайтлам.get(т, 0) + в
    крупнейший = max(по_тайтлам.values()) if по_тайтлам else 0
    return {
        "путей": len(вход),
        "визитов": визиты,
        "произведений": len(по_тайтлам),
        "доля_крупнейшего": (крупнейший / визиты * 100) if визиты else 0.0,
        "с_десятью": sum(1 for в in по_тайтлам.values() if в >= 10),
        "по_тайтлам": по_тайтлам,
    }


def сравнить(было: dict, стало: dict) -> dict:
    """Что ушло и что пришло, в произведениях и в визитах."""
    ш1, ш2 = ширина(было), ширина(стало)
    т1, т2 = ш1["по_тайтлам"], ш2["по_тайтлам"]
    ушли = {т: в for т, в in т1.items() if т not in т2}
    пришли = {т: в for т, в in т2.items() if т not in т1}
    return {
        "было": ш1, "стало": ш2,
        "ушли": ушли, "пришли": пришли,
        "цена_ушедших_%": (sum(ушли.values()) / ш1["визитов"] * 100
                           if ш1["визитов"] else 0.0),
    }


def строки_по_доменам(файл: pathlib.Path) -> dict:
    """Число строк среза у КАЖДОГО домена файла — чтобы увидеть общий предел."""
    try:
        д = json.loads(pathlib.Path(файл).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    спис = д.get("domains")
    перебор = (спис.items() if isinstance(спис, dict)
               else ((э.get("domain"), э) for э in (спис or [])))
    итог = {}
    for имя, x in перебор:
        по = {м.get("key"): м for м in ((x or {}).get("measurements") or [])}
        зн = (по.get(СРЕЗ) or {}).get("value")
        if isinstance(зн, list):
            итог[имя] = len(зн)
    return итог


ВИТРИНЫ = ["yummyani.site", "yummyani7.site", "yummyani.org", "yummyani7.info",
           "yummyani.biz", "animedia.icu", "animedia.space",
           "lordserials22.info", "zonafilm.cc", "zonafilm12.site"]


def main(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description="ширина видимости в поиске")
    р.add_argument("--before", default=str(
        pathlib.Path("/home/claude/wt-portable-site-cell-01/artifacts/analytics"
                     "/analytics-2026-10-12.json")))
    р.add_argument("--after", default=str(
        pathlib.Path("/home/claude/wt-portable-site-cell-01/var/analytics"
                     "/cabinet-latest.json")))
    р.add_argument("--domain", action="append", default=[])
    р.add_argument("--json", action="store_true")
    дов = р.parse_args(аргв)
    домены = дов.domain or ВИТРИНЫ

    пределы = {"before": строки_по_доменам(pathlib.Path(дов.before)),
               "after": строки_по_доменам(pathlib.Path(дов.after))}
    итог = {}
    for домен in домены:
        б = срез(pathlib.Path(дов.before), домен)
        с = срез(pathlib.Path(дов.after), домен)
        итог[домен] = сравнить(б, с) if (б is not None and с is not None) else None

    измерено = sum(1 for з in итог.values() if з)
    if дов.json:
        print(json.dumps({"домены": {д: (з and {к: v for к, v in з.items()
                                                if к not in ("было", "стало")}
                                         | {"было": {к: v for к, v in з["было"].items()
                                                     if к != "по_тайтлам"},
                                            "стало": {к: v for к, v in з["стало"].items()
                                                      if к != "по_тайтлам"}})
                                     for д, з in итог.items()},
                          "строк_по_доменам": пределы},
                         ensure_ascii=False, indent=2))
    else:
        print(f"{'витрина':20} {'произв.':>8} {'→':^3} {'произв.':>8}"
              f" {'визиты':>9} {'→':^3} {'визиты':>9} {'доля крупн.':>12}"
              f" {'цена ушедших':>13}")
        for домен, з in итог.items():
            if not з:
                print(f"{домен:20} НЕ ИЗМЕРЕНО (домена или среза в выгрузке нет)")
                continue
            б, с = з["было"], з["стало"]
            print(f"{домен:20} {б['произведений']:8} {'→':^3} {с['произведений']:8}"
                  f" {б['визитов']:9.0f} {'→':^3} {с['визитов']:9.0f}"
                  f" {с['доля_крупнейшего']:11.1f} % {з['цена_ушедших_%']:12.2f} %")
        for имя, п in пределы.items():
            if not п:
                continue
            самое = max(п.values())
            сколько = sum(1 for в in п.values() if в == самое)
            print(f"\n{имя}: строк по домéнам {min(п.values())}..{самое};"
                  f" домéнов с максимумом {сколько}"
                  + ("  — проверь предел выгрузки" if сколько > 1 else ""))
    if not измерено:
        return 2
    return 0 if измерено == len(домены) else 1


if __name__ == "__main__":
    sys.exit(main())
