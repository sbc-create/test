#!/usr/bin/env python3
"""Шапка `zonafilm12.site`: логотип не режется, слово «Поиск» не вылезает.

ПОВОД — приёмка линии SEO 27.10 на живой витрине, телефон 390, тёмная тема:
логотип показан как «Zona Cinen», надпись «Поиск» выходит за рамку своей
кнопки. Видно и на главной, и на страницах подборок.

ПРИЧИНА, измеренная сравнением рантаймов парка, а не предположенная.

* `.zhd__logo` у этой витрины несёт `width:110px` (и `width:130px` с 768px)
  вместе с `overflow:hidden`. «Zona Cinema» при 18px занимает около 129px —
  поэтому обрезается на любой ширине. `text-overflow:ellipsis` при этом
  многоточия не показывает: элемент — inline-flex.
* `.zhd__searchbtn,.zhd__menu` несут `width:44px` при `font-size:18px`.
  44 пикселя — это размер пальца, а не ширина слова «Поиск»: текст в них не
  помещается и выходит за рамку.

ЭТО ПРАВКА ОДНОГО ДОМЕНА, и причина исключения названа числом: из 15 рантаймов
парка сломанные правила несёт РОВНО ОДИН — `zonafilm12-site`. Остальные 14, в
том числе соседняя витрина той же линии `zonafilm-space`, уже несут верные.
То есть чинить общий слой нечего: он здоров, отстала одна копия.

ПОЧЕМУ ОТСТАЛА. Ровно этот дефект был найден и исправлен 2026-10-10, и тогда
же была написана проверка `checks/header_fit.py`. Её поставили на ОДНУ
витрину из 21. Поэтому исправление не унаследовалось, и полгода этого никто
не видел. Защита от повторения — не в CSS, а в том, что проверка ставится
вместе с правкой (MOD-213).

    python3 automation/host/apply-header-fit-patch.py [--check] <файл>…
"""
from __future__ import annotations

import argparse
from pathlib import Path

ЛОГО_БЫЛО = """.zhd__logo{font-size:18px;font-weight:700;letter-spacing:-.3px;color:#fff;
white-space:nowrap;flex:0 0 auto;width:110px;max-width:150px;min-height:44px;
display:inline-flex;align-items:center;overflow:hidden;text-overflow:ellipsis}"""
ЛОГО_СТАЛО = """.zhd__logo{font-size:18px;font-weight:700;letter-spacing:-.3px;color:#fff;
white-space:nowrap;flex:0 0 auto;min-height:44px;
display:inline-flex;align-items:center}"""

ЛОГО768_БЫЛО = "@media(min-width:768px){.zhd__logo{font-size:19px;width:130px}}"
ЛОГО768_СТАЛО = "@media(min-width:768px){.zhd__logo{font-size:19px}}"

КНОПКИ_БЫЛО = """.zhd__searchbtn,.zhd__menu{display:inline-flex;align-items:center;justify-content:center;
width:44px;height:44px;min-width:44px;min-height:44px;
border:1px solid rgba(255,255,255,.28);border-radius:6px;
background:transparent;color:#fff;font-size:18px;cursor:pointer;flex:0 0 auto}"""
КНОПКИ_СТАЛО = """.zhd__searchbtn,.zhd__menu{display:inline-flex;align-items:center;justify-content:center;
height:44px;min-width:44px;min-height:44px;
border:1px solid rgba(255,255,255,.28);border-radius:6px;
background:transparent;color:#fff;font-size:18px;cursor:pointer;flex:0 0 auto}"""

ПОИСК_БЫЛО = ".zhd__searchbtn{margin-left:auto}"
ПОИСК_СТАЛО = ".zhd__searchbtn{min-width:44px;padding:0 10px;font-size:14px;font-weight:600;margin-left:auto}"

#: имя, было, стало, признак применённости
ПАРЫ = (
    # Признак обязан быть УНИКАЛЬНЫМ куском нового правила, а не любой
    # знакомой строкой: первая версия этой правки брала признаком
    # «display:inline-flex;align-items:center}», и он находился в другом
    # правиле файла — пара молча считалась применённой, а логотип оставался
    # обрезанным. Поэтому признак здесь — хвост именно нового правила.
    ("логотип без жёсткой ширины", ЛОГО_БЫЛО, ЛОГО_СТАЛО,
     "flex:0 0 auto;min-height:44px;\ndisplay:inline-flex;align-items:center}"),
    ("логотип с 768px без ширины", ЛОГО768_БЫЛО, ЛОГО768_СТАЛО,
     "@media(min-width:768px){.zhd__logo{font-size:19px}}"),
    ("кнопки шапки растут по содержимому", КНОПКИ_БЫЛО, КНОПКИ_СТАЛО,
     ".zhd__searchbtn,.zhd__menu{display:inline-flex;align-items:center;"
     "justify-content:center;\nheight:44px;min-width:44px"),
    ("слово «Поиск» получает поля", ПОИСК_БЫЛО, ПОИСК_СТАЛО,
     ".zhd__searchbtn{min-width:44px;padding:0 10px"),
)
#: Файл без этого — не шапка Zona, а другая линия.
ТРЕБОВАНИЕ = ".zhd__logo{"


def уместна(пара: tuple, текст: str) -> bool:
    """Относится ли пара к этому файлу.

    У соседней витрины той же линии правило кнопок написано ИНАЧЕ и при этом
    верно: там селектор `.zhd__searchbtn,.zhd__menu,.zhd__theme` и ширина не
    задана вовсе. Ни сломанного правила, ни нашего нового признака в ней нет —
    значит пара к ней не относится, и объявлять её «не приведённой» было бы
    ложной тревогой. Разошедшийся рантайм — другой случай: там требование
    файла выполнено, а якорь пропал, и тогда нужен отказ.
    """
    _, было, _, признак = пара
    return было in текст or признак in текст


def остатки(текст: str) -> list:
    return [f"нет: {п[0]}" for п in ПАРЫ
            if уместна(п, текст) and п[3] not in текст]


def применить(текст: str) -> tuple[str, list]:
    if ТРЕБОВАНИЕ not in текст:
        raise SystemExit("ОТКАЗ: в файле нет шапки Zona — передан не тот файл")
    журнал = []
    for пара in ПАРЫ:
        имя, было, стало, признак = пара
        if признак in текст:
            журнал.append(f"пропущено (уже стоит): {имя}")
            continue
        if было not in текст:
            журнал.append(f"не относится к этой линии: {имя}")
            continue
        текст = текст.replace(было, стало, 1)
        журнал.append(f"применено: {имя}")
    return текст, журнал


def main(аргв=None) -> int:
    р = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    р.add_argument("файлы", nargs="+")
    р.add_argument("--check", action="store_true")
    а = р.parse_args(аргв)
    плохих = 0
    for имя in а.файлы:
        путь = Path(имя)
        исходный = путь.read_text(encoding="utf-8")
        if а.check:
            if ТРЕБОВАНИЕ not in исходный:
                print(f"не этой линии {путь}")
                continue
            п = остатки(исходный)
            print(("ок     " if not п else "НЕ ПРИВЕДЁН ") + str(путь)
                  + ("" if not п else f"  остатки: {п}"))
            плохих += bool(п)
            continue
        новый, журнал = применить(исходный)
        print(f"== {путь}")
        for строка in журнал:
            print(f"   {строка}")
        if новый != исходный:
            путь.write_text(новый, encoding="utf-8")
    return 1 if плохих else 0


if __name__ == "__main__":
    raise SystemExit(main())
