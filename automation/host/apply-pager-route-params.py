#!/usr/bin/env python3
"""Листалка раздела Lords не пишет параметры, подставленные путём раздела. Перенос по якорям.

T028 (замер 13.10 ~01:15Z): ссылки листалки /movies/ и /series/ —
/movies/?kind=Фильм&page=N (lordfilm47.space, 1lordserials1.online) и
…?kind=Фильм&section=movies&page=N (lordserials22.info). Целевые страницы —
canonical на /movies/?page=N либо noindex, follow; каноническая страница
листалки раздела прямых ссылок не получала. /movies/?page=2 и т. п. — 200,
index, follow, canonical на себя.

Путь раздела уже задаёт тип (/movies → Фильм, /series → Сериал, /animation →
Мультфильм) и выведенный из него раздел (`_РАЗДЕЛ_ПО_ВИДУ`); в ссылке они
лишние. Тип, выбранный читателем и отличный от подразумеваемого, остаётся.
Решение Архитектора 13.10 (§72 его отчёта): правка — в общем источнике
automation/host/lords-frontend.py и переносом по якорям в ядра ячеек, не в
адаптер.

Якорь — начало листалки вида Lords (`<em>…</em>` на месте пропуска; у вида
Zona — `zpg__gap`). Нет якоря и нет правки — отказ ДО записи. Повторный
запуск ничего не меняет. `--check` — «приведён ли файл».

    python3 automation/host/apply-pager-route-params.py [--check] <файл> [<файл>…]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

МЕТКА = "# Листалка без параметров, подставленных путём раздела (apply-pager-route-params)"
ЯКОРЬ = re.compile(
    r"^(?P<о>[ \t]+)def листалка\(self, разд: str, выбрано: dict, стр: int, всего: int\) -> str:\n"
    r"(?P<т>[ \t]+)пункты = страницы\(стр, всего\)\n"
    r"(?P=т)if not пункты:\n"
    r"(?P=т)    return \"\"\n"
    r"(?P=т)куски = \[\]\n"
    r"(?P=т)for н in пункты:\n"
    r"(?P=т)    if н is None:\n"
    r"(?P=т)        куски\.append\(\"<em>…</em>\"\)\n",
    re.M)


def вставка(т: str) -> str:
    return (
        f"{т}{МЕТКА}\n"
        f'{т}вид_пути = {{"/movies": "Фильм", "/series": "Сериал",\n'
        f'{т}            "/animation": "Мультфильм"}}.get(str(разд).rstrip("/"))\n'
        f'{т}if вид_пути and выбрано.get("kind") == вид_пути:\n'
        f'{т}    раздел_пути = (globals().get("_РАЗДЕЛ_ПО_ВИДУ") or {{}}).get(вид_пути)\n'
        f'{т}    выбрано = {{к: в for к, в in выбрано.items()\n'
        f'{т}               if к != "kind" and not (к == "section" and в == раздел_пути)}}\n')


def привести(текст: str) -> tuple[str, int]:
    if МЕТКА in текст:
        return текст, 0
    # В ядре Lords две листалки с этим началом (вид Lords и наследованный вид
    # Zona); правка верна для обеих — приводятся все, но хотя бы одна обязана быть.
    найдено = list(ЯКОРЬ.finditer(текст))
    if not найдено:
        raise SystemExit("якорь листалки Lords не найден — файл не тронут")

    def замена(m: re.Match) -> str:
        шапка = (f'{m["о"]}def листалка(self, разд: str, выбрано: dict, стр: int, всего: int) -> str:\n')
        return шапка + вставка(m["т"]) + m.group(0)[len(шапка):]

    return ЯКОРЬ.sub(замена, текст), len(найдено)


def main() -> int:
    п = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    п.add_argument("--check", action="store_true")
    п.add_argument("файлы", nargs="+")
    а = п.parse_args()
    плохо = 0
    for имя in а.файлы:
        путь = Path(имя)
        текст = путь.read_text(encoding="utf-8")
        if а.check:
            ок = МЕТКА in текст
            print(f"{имя}: {'приведён' if ок else 'НЕ приведён'}")
            плохо += 0 if ок else 1
            continue
        новый, n = привести(текст)
        if n:
            путь.write_text(новый, encoding="utf-8")
        print(f"{имя}: {'приведён' if n else 'уже приведён'}")
    return 1 if плохо else 0


if __name__ == "__main__":
    sys.exit(main())
