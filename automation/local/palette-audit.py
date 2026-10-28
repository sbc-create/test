#!/usr/bin/env python3
"""MOD-216, пробел 2: сколько у витрины ролей цвета и сколько почти-дубликатов.

    python3 automation/local/palette-audit.py --storefront var/site-repos/lordserial33-biz
    python3 automation/local/palette-audit.py --storefront <путь> --json

Зачем замер, а не правка
------------------------

Пробел 2 MOD-216 назывался «именованная палитра»: у `lordserials22.info` и
`lordserial33.biz` цвета записаны литералами. Правка «заменить литералы на
имена» — это ~300 замен на витрину в `src/lords-frontend.py`, то есть в самом
артефакте рантайма, у которого один ответственный
(`docs/COMMON_FIX_INHERITANCE.md`). Решение о такой правке принимается по
числам, и числа даёт этот инструмент.

Что он считает
--------------

1. Упоминания цвета и различные значения.
2. РОЛИ: близкие значения склеиваются в одну роль. Порог 12 в евклидовой
   метрике RGB — это расстояние, на котором два цвета на экране неразличимы
   («#5b6470» и «#5f6874»).
3. ПОЧТИ-ДУБЛИКАТЫ: различные значения минус роли. Это и есть цена отсутствия
   палитры: один и тот же задуманный цвет записан несколькими значениями, и
   правка одного места оставляет остальные.

Чего инструмент НЕ делает: не правит файлы, не предлагает имён роли (имя — это
решение о смысле, а не о значении) и не считает цвета в данных сайта.
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import sys

ЦВЕТ = re.compile(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b")

#: Расстояние в RGB, ниже которого цвета считаются одной ролью.
ПОРОГ_РОЛИ = 12


def в_rgb(значение: str) -> tuple:
    з = значение.lower()
    if len(з) == 3:
        з = "".join(ч * 2 for ч in з)
    return tuple(int(з[i:i + 2], 16) for i in (0, 2, 4))


def расстояние(a: tuple, b: tuple) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def собрать(корень: pathlib.Path) -> collections.Counter:
    счёт: collections.Counter = collections.Counter()
    for путь in sorted(корень.rglob("*.py")):
        if "__pycache__" in str(путь):
            continue
        текст = путь.read_text(encoding="utf-8", errors="replace")
        счёт.update(м.group(1).lower() for м in ЦВЕТ.finditer(текст))
    return счёт


def роли(счёт: collections.Counter) -> list:
    итог: list = []
    for значение in sorted(счёт, key=lambda з: (-счёт[з], з)):
        rgb = в_rgb(значение)
        к = next((р for р in итог
                  if расстояние(в_rgb(р["значение"]), rgb) < ПОРОГ_РОЛИ), None)
        if к is None:
            итог.append({"значение": значение, "вес": счёт[значение],
                         "слитые": []})
        else:
            к["слитые"].append(значение)
            к["вес"] += счёт[значение]
    return sorted(итог, key=lambda р: -р["вес"])


def по_файлам(корень: pathlib.Path) -> collections.Counter:
    счёт: collections.Counter = collections.Counter()
    for путь in sorted(корень.rglob("*.py")):
        if "__pycache__" in str(путь):
            continue
        н = ЦВЕТ.findall(путь.read_text(encoding="utf-8", errors="replace"))
        if н:
            счёт[str(путь.relative_to(корень))] = len(н)
    return счёт


def main() -> int:
    р = argparse.ArgumentParser()
    р.add_argument("--storefront", required=True)
    р.add_argument("--json", action="store_true")
    а = р.parse_args()
    корень = pathlib.Path(а.storefront).resolve()
    if not корень.is_dir():
        print(f"НЕ ИЗМЕРЕНО: нет {корень}")
        return 2
    счёт = собрать(корень)
    if not счёт:
        print(f"{корень.name}: упоминаний цвета нет — считать нечего")
        return 0
    р_роли = роли(счёт)
    почти = len(счёт) - len(р_роли)
    итог = {"витрина": корень.name, "упоминаний": sum(счёт.values()),
            "различных": len(счёт), "ролей": len(р_роли),
            "почти_дубликатов": почти,
            "файлы": dict(по_файлам(корень).most_common(5)),
            "крупные_роли": [
                {"значение": f"#{р['значение']}", "вес": р["вес"],
                 "почти_те_же": [f"#{с}" for с in р["слитые"]]}
                for р in р_роли[:8]]}
    if а.json:
        print(json.dumps(итог, ensure_ascii=False, indent=1))
        return 0
    print(f"{итог['витрина']}: упоминаний {итог['упоминаний']}, различных "
          f"{итог['различных']}, ролей {итог['ролей']}, почти-дубликатов "
          f"{итог['почти_дубликатов']}")
    for файл, н in итог["файлы"].items():
        print(f"    {файл}: {н}")
    for р_ in итог["крупные_роли"]:
        доп = (", почти те же: " + ", ".join(р_["почти_те_же"][:3])
               if р_["почти_те_же"] else "")
        print(f"    {р_['значение']}: упоминаний {р_['вес']}{доп}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
