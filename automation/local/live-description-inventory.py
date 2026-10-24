#!/usr/bin/env python3
"""Сколько описаний стоит на живых витринах и чьи они.

Повод. Опись редакционной очереди (`editorial-inventory.py`) считает тексты,
которые НАПИСАНЫ. На странице стоит не то же самое: измерено 24.10 — у 7 из 16
проверенных страниц yummyani.site текст страницы не совпал с сохранённым в
очереди, а оказался другим описанием того же произведения. Значит у витрин
есть своё хранилище описаний, и его надо считать отдельно.

Хранилище: `/srv/lords/.frontend/<ячейка>-details.json`, запись
`details[<слаг>]`, поля `description` и `description_source`. Это постоянные
данные витрины — инструмент только ЧИТАЕТ их (docs/RUNTIME_DATA_OWNERSHIP.md).

`description_source` и есть ответ на «чьё описание»: `detail` — текст
поставщика каталога, остальные значения названы как есть, без догадок. Если
поле отсутствует, это печатается отдельной строкой: «источник не указан» —
не «поставщик».

Файлы по 95–128 МиБ и совпадают по размеру, но НЕ по содержимому (проверено
хешами 24.10): каждая ячейка считается отдельно.
"""
from __future__ import annotations

import argparse
import collections
import pathlib
import re
import sys

КАТАЛОГ = pathlib.Path("/srv/lords/.frontend")
ОБРАЗЕЦ = re.compile(r'"description_source"\s*:\s*"([^"]*)"')
ПУСТОЕ = re.compile(r'"description"\s*:\s*""')
ЕСТЬ = re.compile(r'"description"\s*:\s*"')
ВСЕГО = re.compile(r'"details_total"\s*:\s*(\d+)')


def посчитать(путь: pathlib.Path) -> dict:
    """Счёт по тексту файла, без разбора JSON: 128 МиБ в память не кладём."""
    текст = путь.read_text(encoding="utf-8", errors="replace")
    источники = collections.Counter(ОБРАЗЕЦ.findall(текст))
    м = ВСЕГО.search(текст)
    есть = len(ЕСТЬ.findall(текст))
    пусто = len(ПУСТОЕ.findall(текст))
    return {
        "файл": путь.name,
        "записей": int(м.group(1)) if м else None,
        "с_описанием": есть - пусто,
        "пустых_описаний": пусто,
        "источники": dict(источники),
        "байт": путь.stat().st_size,
    }


def главное(argv: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--dir", type=pathlib.Path, default=КАТАЛОГ)
    р.add_argument("--only", help="подстрока имени файла")
    а = р.parse_args(argv)

    if not а.dir.exists():
        print(f"НЕ ИЗМЕРЕНО: каталога витрин нет — {а.dir}")
        return 2
    файлы = sorted(п for п in а.dir.glob("*-details.json")
                   if not п.is_symlink() and (not а.only or а.only in п.name))
    if not файлы:
        print(f"НЕ ИЗМЕРЕНО: в {а.dir} нет файлов описаний")
        return 2

    print(f"{'ячейка':26} {'записей':>8} {'с описанием':>12} {'доля':>6}"
          f"  источники описаний")
    итог = collections.Counter()
    всего_зап = всего_оп = 0
    строки = []
    for п in файлы:
        d = посчитать(п)
        if d["записей"] is None:
            print(f"{п.name:26} НЕ ИЗМЕРЕНО: в файле нет details_total")
            continue
        доля = d["с_описанием"] / d["записей"] if d["записей"] else 0
        ист = ", ".join(f"{k or '(пусто)'}={v}" for k, v in
                        sorted(d["источники"].items(), key=lambda x: -x[1]))
        без_поля = d["с_описанием"] - sum(d["источники"].values())
        if без_поля > 0:
            ист += f", источник не указан={без_поля}"
        print(f"{d['файл'].replace('-details.json',''):26} {d['записей']:8}"
              f" {d['с_описанием']:12} {доля:5.1%}  {ист}")
        итог.update(d["источники"])
        всего_зап += d["записей"]
        всего_оп += d["с_описанием"]
        строки.append(d)

    print()
    print(f"ячеек измерено {len(строки)} из {len(файлы)};"
          f" записей {всего_зап}, с описанием {всего_оп}"
          f" ({всего_оп / всего_зап:.1%})" if всего_зап else "записей 0")
    print("источники описаний на всех витринах:")
    for к, в in итог.most_common():
        print(f"  {к or '(пусто)':28} {в}")
    не_поставщик = sum(в for к, в in итог.items() if к != "detail")
    print()
    if не_поставщик == 0:
        print("ВЫВОД: все описания на витринах помечены как текст поставщика"
              " (description_source=detail);"
              " редакционных описаний среди них НЕТ")
        return 1
    print(f"ВЫВОД: описаний не от поставщика {не_поставщик}"
          f" из {всего_оп} — они и есть редакционные на витринах")
    return 0


if __name__ == "__main__":
    sys.exit(главное())
