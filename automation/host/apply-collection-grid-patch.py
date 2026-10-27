#!/usr/bin/env python3
"""Оформление страницы редакционной подборки приезжает вместе с её разметкой.

ПОВОД — отказ визуальной приёмки 27.10:
`https://animedia.icu/collection/letniy-sezon-2026-celikom/` показывала
«огромный одиночный постер слева, пустое пространство справа и название
произведения далеко внизу». Измерено браузером ДО правки: в ряду 1 карточка
на 390, 1440 и 1920; рамка постера 1340×565 при отношении 2.37; на 1920
содержимое занимает 0.70 окна.

ПРИЧИНА, А НЕ СИМПТОМ. Разметку страницы даёт ОБЩИЙ построитель
`ручная_подборка` в базовом классе: `grid col__grid`, `col__i`, `col__why`,
`claim` и карточка `c`/`c__p`/`c__b`/`c__t`. Правила для этих классов лежали
ТОЛЬКО в `ЛОРДС_СТИЛЬ` (`.col__i`, `.col__why`, `.claim`) и в устаревшем
`СТИЛЬ` (`.grid`, `.c__p`). Zona отдаёт `_тема_зона() + _общее() +
ЗОНА_СТИЛЬ`, Animedia — `_общее() + АНИМЕДИА_СТИЛЬ`; ни один из этих наборов
лист Lords не включает. То есть общий построитель отдавал разметку, оформления
для которой у семейства нет, и страница разворачивалась в одну колонку.

ПОЧЕМУ ПРЕЖНЕЕ ИСПРАВЛЕНИЕ НЕ ЗАЩИТИЛО. Оно чинило ДРУГОЙ метод — `коллекция`
(подборка, собранная фильтром): там разметка переписана на классы семейства, и
в его описании прямо сказано «База собирает её классами grid/sec/card — это
оформление Lords. У Zona и Animedia таких правил нет». Ручная редакционная
подборка рисуется методом `ручная_подборка`, которого та правка не касалась, и
унаследовала ровно ту же болезнь.

ЧТО ДЕЛАЕТ ЭТА ПРАВКА. Переносит оформление подборки в `_общее()` — лист,
который включают ВСЕ семейства без исключения. Дальше семейство не может
отдать эту страницу без оформления: лист приезжает из того же места, что и
построитель разметки. Семейный лист конкатенируется ПОСЛЕ общего, поэтому
собственные правила семейства (у Lords они есть) по-прежнему перекрывают эти —
правка ничего не отнимает у того, у кого уже работало.

Сетка: 2 колонки на телефоне, 3 от 600, 4 от 900, 5 от 1360; ширина сетки
ограничена 1340. Постер — в рамке 2:3 с `object-fit:cover`: пропорции не
искажаются никогда, а кадр нестандартного отношения обрезается, а не
растягивается. Название и пояснение обрезаются по числу строк, чтобы ряд не
разъезжался по высоте.

    python3 automation/host/apply-collection-grid-patch.py [--check] <файл>…
"""
from __future__ import annotations

import argparse
from pathlib import Path

СТИЛЬ = '''#: Оформление страницы редакционной подборки. Лежит ЗДЕСЬ, рядом с общим
#: листом, а не в листе семейства: разметку даёт общий построитель
#: `ручная_подборка`, и правила обязаны приезжать вместе с ним. До 27.10 они
#: лежали только в `ЛОРДС_СТИЛЬ`, и Zona с Animedia отдавали страницу без
#: оформления: одна карточка в ряду, постер во всю ширину содержимого
#: (измерено 1340×565 на ширинах 1440 и 1920).
#:
#: Общий лист конкатенируется ПЕРЕД листом семейства, поэтому эти правила
#: ничего не отнимают у семейства, где своё оформление уже есть.
СТИЛЬ_ПОДБОРКИ = """
.col__grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));
  gap:20px 14px;max-width:1340px;margin:0 auto 28px;padding:0}
@media (min-width:600px){.col__grid{
  grid-template-columns:repeat(3,minmax(0,1fr));gap:22px 16px}}
@media (min-width:900px){.col__grid{
  grid-template-columns:repeat(4,minmax(0,1fr))}}
@media (min-width:1360px){.col__grid{
  grid-template-columns:repeat(5,minmax(0,1fr))}}
.col__i{display:flex;flex-direction:column;min-width:0}
.col__i .c{display:block;text-decoration:none;color:inherit;min-width:0}
/* Рамка постера одна на все карточки: отношение 2:3 задано рамкой, а картинка
   заполняет её `cover`. Пропорции не искажаются ни при каком исходном кадре —
   нестандартный кадр обрезается, а не растягивается. */
.col__i .c__p{display:block;position:relative;width:100%;aspect-ratio:2/3;
  overflow:hidden;border-radius:10px;background:rgba(128,128,128,.16)}
.col__i .c__p img{display:block;width:100%;height:100%;
  object-fit:cover;object-position:center}
.col__i .c__b{padding:8px 2px 0;min-width:0}
/* Длинные названия аниме обрезаются по двум строкам: иначе одна карточка
   растягивает весь ряд, и сетка разъезжается по высоте. */
.col__i .c__t{font-weight:600;font-size:15px;line-height:1.25;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;
  overflow:hidden;overflow-wrap:anywhere}
.col__i .c__m{margin-top:3px;font-size:12px;opacity:.7}
.col__i .c__m span+span{margin-left:6px}
.col__i .col__why{margin:6px 2px 0;font-size:13px;line-height:1.4;opacity:.85;
  display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;
  overflow:hidden;overflow-wrap:anywhere}
/* Вступление и служебные строки — по ширине чтения, а не во всю рамку. */
.claim{max-width:74ch;line-height:1.5}
.col__upd,.col__gone,.col__src{max-width:74ch}
.col__src{margin:0 0 14px;font-size:12px;opacity:.65;line-height:1.45}
"""


'''

БЫЛО = '''def _общее(токены: dict) -> str:
    return ОБЩЕЕ_1_1.replace("@ACC@", токены["acc"])'''
СТАЛО = СТИЛЬ + '''def _общее(токены: dict) -> str:
    return ОБЩЕЕ_1_1.replace("@ACC@", токены["acc"]) + СТИЛЬ_ПОДБОРКИ'''

ПАРЫ = (
    ("оформление подборки в общем листе", БЫЛО, СТАЛО, "СТИЛЬ_ПОДБОРКИ = "),
)


def остатки(текст: str) -> list:
    return [f"нет: {имя}" for имя, _, _, признак in ПАРЫ if признак not in текст]


def применить(текст: str) -> tuple[str, list]:
    if "def _общее(токены: dict)" not in текст:
        raise SystemExit("ОТКАЗ: в файле нет общего листа `_общее` — "
                         "это не рантайм витрины")
    журнал = []
    for имя, было, стало, признак in ПАРЫ:
        if признак in текст:
            журнал.append(f"пропущено (уже стоит): {имя}")
            continue
        if было not in текст:
            raise SystemExit(f"ОТКАЗ: якорь «{имя}» не найден — рантайм "
                             "разошёлся с разобранным образцом")
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
            if "def _общее(токены: dict)" not in исходный:
                print(f"не этой линии (нет общего листа) {путь}")
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
