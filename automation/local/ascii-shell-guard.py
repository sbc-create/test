#!/usr/bin/env python3
"""Сторож: в shell-скрипте не бывает кириллических имён переменных.

    python3 automation/local/ascii-shell-guard.py <файл.sh> [<файл.sh> …]
    python3 automation/local/ascii-shell-guard.py --dir <каталог>

Повод измеренный, 28.10: ЧЕТЫРЕ раза за одну смену я написал в bash
присваивание вида `РЕПО=…`, `ВРЕМ=…`, `база=…`, `список=…`. Для оболочки это не
присваивание, а КОМАНДА с таким именем: она отвечает «No such file or
directory» либо кодом 127, а дальше скрипт идёт с пустой переменной и делает
не то. У витрины на этот класс есть проверка (`checks/ascii_shell_identifiers.py`),
но мои черновые скрипты ею не покрыты — и правило, записанное без механизма,
четыре раза не сработало.

Сторож ищет строки вида `ИМЯ=значение` и `local ИМЯ=…`, где в имени есть
не-ASCII знак, и отказывает кодом 1 с номером строки. Кириллица в ЗНАЧЕНИЯХ и в
тексте сообщений не трогается: проблема только в именах.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

ПРИСВАИВАНИЕ = re.compile(
    r"^\s*(?:local\s+|export\s+|declare\s+-?\w*\s+)?([A-Za-z_\u0080-￿]"
    r"[A-Za-z0-9_\u0080-￿]*)=")


def беды(путь: pathlib.Path) -> list[str]:
    найдено = []
    for номер, строка in enumerate(путь.read_text(encoding="utf-8",
                                                  errors="replace").splitlines(), 1):
        if строка.lstrip().startswith("#"):
            continue
        м = ПРИСВАИВАНИЕ.match(строка)
        if not м:
            continue
        имя = м.group(1)
        if any(ord(ч) > 127 for ч in имя):
            найдено.append(f"{путь}:{номер}: имя переменной «{имя}» не ASCII — "
                           "оболочка прочтёт строку как команду")
    return найдено


def main() -> int:
    р = argparse.ArgumentParser()
    р.add_argument("files", nargs="*")
    р.add_argument("--dir")
    а = р.parse_args()
    пути: list[pathlib.Path] = [pathlib.Path(ф) for ф in а.files]
    if а.dir:
        пути += sorted(pathlib.Path(а.dir).rglob("*.sh"))
    пути = [п for п in пути if п.is_file()]
    if not пути:
        print("НЕ ИЗМЕРЕНО: ни одного файла не передано")
        return 2
    все_беды: list[str] = []
    for п in пути:
        все_беды += беды(п)
    print(f"проверено файлов: {len(пути)}, найдено не-ASCII имён: {len(все_беды)}")
    for б in все_беды:
        print("  ", б)
    return 1 if все_беды else 0


if __name__ == "__main__":
    sys.exit(main())
