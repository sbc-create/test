#!/usr/bin/env python3
"""Проверить ПОРЯДОК сокращения заголовка, не собирая приложение.

B031: `<title>` страниц тайтла обрезает НАЗВАНИЕ по границе слова и молча,
сохраняя шаблонный хвост и бренд. Измерено на живых страницах
`yummyani.site`: «Меня выгнали из гильдии героев, потому что я был плохим |
YummyAnime» при полном названии «…был плохим компаньоном, поэтому я…».

Решение владельца (из очереди, B031): порядок сокращения «шаблонный хвост →
бренд», название не обрезается. Здесь это ПРОВЕРЯЕТСЯ до всякой сборки:
логика `joinTitle` переписана на JavaScript один в один (прежняя и
предлагаемая) и прогоняется в node на настоящих названиях.

Зачем так, а не сборкой: сборка трёх образов — 15 минут и больше гигабайта на
разделе, где после исчерпания памяти осталось мало. Поведение чистой функции
от этого не зависит.

    python3 automation/local/check-title-order.py
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

BRAND = "YummyAnime"
LIMIT = 70

#: Настоящие названия: первое и второе — с живых страниц yummyani.site,
#: третье — из описания задачи B031, четвёртое — короткое для обратной
#: стороны (оно не должно измениться ни на знак).
СЛУЧАИ = [
    ("Меня выгнали из гильдии героев, потому что я был плохим компаньоном, "
     "поэтому я решил неспешно жить в глуши", " — 1 сезон, 3 серия",
     "смотреть онлайн"),
    ("Некий научный Рейлган S: Все важнейшие открытия делаются во время "
     "купания", " — 2 сезон", "смотреть онлайн"),
    ("Невероятное приключение ДжоДжо: Гонка «Стальной шар»", " — 7 сезон", ""),
    ("Ветер крепчает", "", "смотреть онлайн"),
]

ОБЩЕЕ = """
const BRAND = %(brand)s, LIMIT = %(limit)d;
function lastWordBoundary(value, max) {
  if (value.length <= max) return value;
  const slice = value.slice(0, max);
  const space = slice.lastIndexOf(" ");
  if (space <= 0) return value;
  return slice.slice(0, space).replace(/[\\u2014\\u2013,.:;]+$/u, "").trimEnd();
}
function joinTitleOld(titleRu, middle, boilerplate) {
  const brand = ` | ${BRAND}`;
  const withBoilerplate = `${titleRu}${middle}${boilerplate ? ` ${boilerplate}` : ""}${brand}`;
  if (withBoilerplate.length <= LIMIT) return withBoilerplate;
  const separatorOnly = middle.trim() === "\\u2014";
  const keptMiddle = separatorOnly ? "" : middle;
  const withoutBoilerplate = `${titleRu}${keptMiddle}${brand}`;
  if (withoutBoilerplate.length <= LIMIT) return withoutBoilerplate;
  const reserved = `${keptMiddle}${brand}`.length;
  const budget = Math.max(LIMIT - reserved, 1);
  const shortened = lastWordBoundary(titleRu, budget);
  return `${shortened}${keptMiddle}${brand}`;
}
function joinTitleNew(titleRu, middle, boilerplate) {
  const brand = ` | ${BRAND}`;
  const withBoilerplate = `${titleRu}${middle}${boilerplate ? ` ${boilerplate}` : ""}${brand}`;
  if (withBoilerplate.length <= LIMIT) return withBoilerplate;
  const separatorOnly = middle.trim() === "\\u2014";
  const keptMiddle = separatorOnly ? "" : middle;
  const withoutBoilerplate = `${titleRu}${keptMiddle}${brand}`;
  if (withoutBoilerplate.length <= LIMIT) return withoutBoilerplate;
  /* Следующий на снятие — БРЕНД, а не название: лимит не критерий, а
     обрезанная сущность запрещена. Номера сезона и серии остаются. */
  return `${titleRu}${keptMiddle}`;
}
function joinTitleFit(titleRu, middle, boilerplate) {
  /* Вариант В: бренд снимается ТОЛЬКО если без него полное название влезает
     в лимит. Иначе поведение прежнее. Лимит соблюдается всегда, а самый
     посещаемый случай (короткое название + номер сезона) перестаёт обрезаться. */
  const brand = ` | ${BRAND}`;
  const withBoilerplate = `${titleRu}${middle}${boilerplate ? ` ${boilerplate}` : ""}${brand}`;
  if (withBoilerplate.length <= LIMIT) return withBoilerplate;
  const separatorOnly = middle.trim() === "\u2014";
  const keptMiddle = separatorOnly ? "" : middle;
  const withoutBoilerplate = `${titleRu}${keptMiddle}${brand}`;
  if (withoutBoilerplate.length <= LIMIT) return withoutBoilerplate;
  const withoutBrand = `${titleRu}${keptMiddle}`;
  if (withoutBrand.length <= LIMIT) return withoutBrand;
  return joinTitleOld(titleRu, middle, boilerplate);
}
const случаи = %(случаи)s;
const итог = случаи.map(([titleRu, middle, boiler]) => ({
  название: titleRu,
  прежний: joinTitleOld(titleRu, middle, boiler),
  новый: joinTitleNew(titleRu, middle, boiler),
  влезающий: joinTitleFit(titleRu, middle, boiler),
}));
console.log(JSON.stringify(итог));
"""


def главное() -> int:
    if shutil.which("node") is None:
        print("node на машине нет — порядок проверить нечем", file=sys.stderr)
        return 2
    тело = ОБЩЕЕ % {
        "brand": json.dumps(BRAND, ensure_ascii=False),
        "limit": LIMIT,
        "случаи": json.dumps(СЛУЧАИ, ensure_ascii=False),
    }
    ф = pathlib.Path(tempfile.mkdtemp()) / "порядок.mjs"
    ф.write_text(тело, encoding="utf-8")
    г = subprocess.run(["node", str(ф)], capture_output=True, text=True,
                       timeout=120)
    if г.returncode != 0:
        print((г.stderr or "")[:600], file=sys.stderr)
        return 1
    строки = json.loads(г.stdout.strip().splitlines()[-1])

    плохо = 0
    for з in строки:
        имя = з["название"]
        прежний_полон = имя in з["прежний"]
        новый_полон = имя in з["новый"]
        print(f"\n{имя[:66]}")
        print(f"   прежний: {з['прежний']}")
        print(f"            название целиком: {'да' if прежний_полон else 'НЕТ'}, "
              f"{len(з['прежний'])} знаков")
        print(f"   новый (Б): {з['новый']}")
        print(f"            название целиком: {'да' if новый_полон else 'НЕТ'}, "
              f"{len(з['новый'])} знаков")
        влез = з.get('влезающий','')
        print(f"   бренд только при запасе (В): {влез}")
        print(f"            название целиком: {'да' if имя in влез else 'НЕТ'}, "
              f"{len(влез)} знаков")
        if not новый_полон:
            плохо += 1
            print("   [x] предлагаемый порядок всё равно обрезает название")
    коротких = [з for з in строки if з["прежний"] == з["новый"]]
    print(f"\nслучаев {len(строки)}; название целиком в новом порядке: "
          f"{len(строки) - плохо}; не изменилось ничего: {len(коротких)}")
    print("лимит 70 знаков в новом порядке соблюдается не всегда — это и есть "
          "предмет решения владельца: лимит против обрезанной сущности")
    return 1 if плохо else 0


if __name__ == "__main__":
    raise SystemExit(главное())
