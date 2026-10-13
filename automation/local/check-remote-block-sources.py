#!/usr/bin/env python3
"""Пути блока, помеченного `# host: <ref>`, проверяются НА ТОМ УЗЛЕ.

Проверка пакета (`owner-package-check.py`) такие блоки пропускает осознанно:
их файлы лежат на другой машине. Но «пропущено» не должно означать «не
проверено»: иначе опечатка в пути дойдёт до root-консоли владельца.

Этот инструмент достаёт из блока источники `install` и шаблоны вроде
`stage/units/nova-*.service`, и спрашивает их существование у самого узла —
через тот же разрешённый слой (ansible, инвентарь из реестра, пиннинг ключа
сервера). Ничего не меняет: только `test -e` и подсчёт по шаблону.

Код возврата 1 — на узле чего-то нет; 0 — все источники на месте.
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import shlex
import subprocess
import sys
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
ПРОВЕРКА_ПАКЕТА = КОРЕНЬ / "automation" / "local" / "owner-package-check.py"
ИНВЕНТАРЬ = КОРЕНЬ / "var" / "ansible" / "hosts.yml"


def _пакет():
    spec = importlib.util.spec_from_file_location("owner_package_check",
                                                  ПРОВЕРКА_ПАКЕТА)
    м = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(м)
    return м


def источники_блока(команды: list[str]) -> list[str]:
    """Абсолютные пути-источники: аргументы `install` и `cp` до назначения."""
    итог: list[str] = []
    for команда in команды:
        try:
            части = shlex.split(команда)
        except ValueError:
            части = команда.split()
        if not части or части[0] not in ("install", "cp", "sudo"):
            continue
        if части[0] == "sudo":
            части = части[1:]
            if not части or части[0] not in ("install", "cp"):
                continue
        if "-d" in части:
            # `install -d` создаёт КАТАЛОГИ: источников у него нет вовсе, и
            # первая версия принимала назначение за источник.
            continue
        кандидаты = [ч for ч in части[1:] if ч.startswith("/")]
        # Последний абсолютный путь — назначение, остальные источники.
        for путь in кандидаты[:-1]:
            if путь not in итог:
                итог.append(путь)
    return итог


def спросить_узел(узел: str, пути: list[str]) -> tuple[int, str]:
    """Один вызов на все пути: `ls -d` по шаблону и счёт найденного."""
    строки = []
    for путь in пути:
        строки.append(f'n=$(ls -d {путь} 2>/dev/null | wc -l); '
                      f'echo "$n {путь}"')
    команда = "; ".join(строки)
    готово = subprocess.run(
        ["ansible", "-i", str(ИНВЕНТАРЬ), узел, "-m", "raw", "-a", команда],
        capture_output=True, text=True, timeout=300, cwd=КОРЕНЬ)
    return готово.returncode, готово.stdout + готово.stderr


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("документ")
    а = р.parse_args()
    док = Path(а.документ)
    if not док.is_file():
        print(f"ОТКАЗ: нет {док}", file=sys.stderr)
        return 2
    м = _пакет()
    блоки = [б for б in м._строки_блоков(док.read_text(encoding="utf-8"))
             if б.узел is not None]
    if not блоки:
        print("в документе нет блоков с меткой `# host:` — проверять нечего")
        return 0
    беды = 0
    for блок in блоки:
        пути = источники_блока([к for _, к in блок.команды])
        if not пути:
            print(f"{блок.узел}: источников install/cp в блоке нет")
            continue
        код, вывод = спросить_узел(блок.узел, пути)
        print(f"=== {блок.узел}: путей к проверке {len(пути)}")
        for строка in вывод.splitlines():
            м_ = re.match(r"^(\d+)\s+(/\S+)", строка.strip())
            if not м_:
                continue
            сколько, путь = int(м_.group(1)), м_.group(2)
            if сколько:
                print(f"   есть ({сколько}) {путь}")
            else:
                print(f"   НЕТ        {путь}")
                беды += 1
        if код != 0 and беды == 0:
            print(f"   предупреждение: ansible вернул {код}")
    print(f"\nотсутствующих источников на узле: {беды}")
    return 1 if беды else 0


if __name__ == "__main__":
    raise SystemExit(main())
