#!/usr/bin/env python3
"""Какие страницы жанров ГОДЯТСЯ для карты сайта: по измерению, а не по списку.

Повод — задача T262: «в карте индексируемые страницы жанров
`/catalog/?genre=<код>` (ровно те, что отдают index и canonical на себя; пустые
и noindex — нет)». Задача верна по смыслу, но её нельзя выполнить списком жанров
из разметки: 21.10 измерено, что `?genre=anime` на витринах Animedia объявляет
ТЕ ЖЕ 8 228 записей, что каталог без условий, то есть это дубль каталога
(MOD-120). Адрес-дубль в карте — приглашение обходчику потратить бюджет на
копию.

Поэтому каждая страница жанра проверяется по четырём признакам, и в карту
годится только та, у которой все четыре в порядке:

* отвечает 200;
* `robots` начинается с `index`;
* `canonical` указывает НА СЕБЯ (с тем же запросом);
* объявленный размер выборки МЕНЬШЕ каталога — иначе это дубль каталога.

Размер берётся у самой витрины («Найдено N»), а если она его не печатает — из
номера последней страницы листалки. Где нет ни того, ни другого, страница
помечается «не измерено» и в перечень для карты НЕ попадает: карта не место для
догадок.

    python3 automation/local/genre-pages-for-sitemap.py animedia.icu
    python3 automation/local/genre-pages-for-sitemap.py animedia.icu --json
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.parse

АГЕНТ = "factory-genre-pages-for-sitemap"


def достать(адрес: str, таймаут: int = 40) -> str | None:
    try:
        г = subprocess.run(["curl", "-A", АГЕНТ, "-sSL", "-w", "\n@@КОД@@%{http_code}",
                            "--max-time", str(таймаут), адрес],
                           capture_output=True, text=True, timeout=таймаут + 20)
    except subprocess.TimeoutExpired:
        return None
    тело, _, код = г.stdout.rpartition("@@КОД@@")
    return тело if код.strip() == "200" else None


def число_найденного(тело: str) -> int | None:
    for шаблон in (r"Найдено[^\d]{0,20}([\d\s ]{1,12})",
                   r"записей[^\d]{0,12}([\d\s ]{1,12})"):
        м = re.search(шаблон, тело)
        if м:
            цифры = re.sub(r"[^\d]", "", м.group(1))
            if цифры:
                return int(цифры)
    return None


def последняя_страница(тело: str) -> int | None:
    номера = [int(н) for н in re.findall(r"[?&]page=(\d+)", тело)]
    return max(номера) if номера else None


def размер(тело: str) -> tuple[int | None, str]:
    """Размер выборки и способ, которым он получен."""
    н = число_найденного(тело)
    if н is not None:
        return н, "объявлено витриной"
    стр = последняя_страница(тело)
    if стр:
        return стр, "страниц листалки"
    return None, "не измерено"


def канон_на_себя(тело: str, адрес: str) -> bool:
    м = re.search(r'rel="canonical" href="([^"]*)"', тело)
    if not м:
        return False
    а = urllib.parse.urlsplit(м.group(1))
    б = urllib.parse.urlsplit(адрес)
    return (а.path.rstrip("/") == б.path.rstrip("/")
            and urllib.parse.parse_qs(а.query) == urllib.parse.parse_qs(б.query))


def роботы(тело: str) -> str:
    м = re.search(r'name="robots" content="([^"]*)"', тело)
    return м.group(1) if м else ""


def жанры(тело: str) -> list[str]:
    """Коды жанров из ссылок САМОЙ витрины, а не из моего представления."""
    найдено = []
    for ссылка in re.findall(r'href="(/catalog/\?genre=[^"&]+)"', тело):
        код = urllib.parse.unquote(ссылка.split("genre=", 1)[1])
        if код not in найдено:
            найдено.append(код)
    return найдено


def проверить(домен: str, предел: int | None) -> dict:
    корень = f"https://{домен}"
    итог: dict = {"домен": домен, "страницы": [], "замечания": []}
    каталог = достать(f"{корень}/catalog/")
    if каталог is None:
        итог["замечания"].append("каталог не прочитан — НЕ ИЗМЕРЕНО")
        return итог
    весь, способ = размер(каталог)
    итог["каталог"] = весь
    итог["способ_размера"] = способ
    коды = жанры(каталог)
    хаб = достать(f"{корень}/genres/")
    if хаб:
        for код in жанры(хаб):
            if код not in коды:
                коды.append(код)
    итог["жанров_найдено"] = len(коды)
    if предел:
        коды = коды[:предел]
    for код in коды:
        путь = f"/catalog/?genre={urllib.parse.quote(код)}"
        тело = достать(корень + путь)
        if тело is None:
            итог["страницы"].append({"жанр": код, "итог": "не 200"})
            continue
        р = роботы(тело)
        свой = канон_на_себя(тело, путь)
        н, как = размер(тело)
        карточек = len(set(re.findall(r'href="(/title/[^"#?]+/)"', тело)))
        if not р.startswith("index"):
            состояние = "noindex — в карту не идёт"
        elif not свой:
            состояние = "canonical не на себя — в карту не идёт"
        elif карточек == 0:
            состояние = "пустая — в карту не идёт"
        elif н is None or весь is None:
            состояние = "размер не измерен — в карту не идёт"
        elif н >= весь:
            состояние = "ДУБЛЬ КАТАЛОГА — в карту не идёт"
        else:
            состояние = "годится"
        итог["страницы"].append({"жанр": код, "robots": р, "карточек": карточек,
                                 "размер": н, "как": как, "итог": состояние})
    годных = [с["жанр"] for с in итог["страницы"] if с["итог"] == "годится"]
    итог["годных"] = годных
    дублей = [с["жанр"] for с in итог["страницы"] if "ДУБЛЬ" in с["итог"]]
    if дублей:
        итог["замечания"].append(
            f"дубли каталога среди жанров: {', '.join(дублей)} —"
            f" именно их нельзя класть в карту")
    return итог


def main(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("домен")
    р.add_argument("--limit", type=int, default=None,
                   help="проверить только первые N жанров")
    р.add_argument("--json", action="store_true")
    а = р.parse_args(аргв)
    итог = проверить(а.домен, а.limit)
    if а.json:
        print(json.dumps(итог, ensure_ascii=False, indent=1))
        return 0
    print(f"{а.домен}: каталог {итог.get('каталог')} ({итог.get('способ_размера')}),"
          f" жанров найдено {итог.get('жанров_найдено')},"
          f" проверено {len(итог['страницы'])}")
    for с in итог["страницы"]:
        if "robots" in с:
            print(f"   {с['жанр'][:28]:<28} {с['robots'][:14]:<14}"
                  f" карточек {с['карточек']:>3} размер {str(с['размер']):>6}"
                  f" ({с['как']}) | {с['итог']}")
        else:
            print(f"   {с['жанр'][:28]:<28} {с['итог']}")
    print(f"\nгодных для карты: {len(итог.get('годных', []))}")
    for з in итог["замечания"]:
        print(f"   → {з}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
