#!/usr/bin/env python3
"""Пересекаются ли мои изменения с незакоммиченными правками чужого дерева.

    python3 automation/local/branch-overlap-check.py [<чужое дерево>] [<его коммит>]


Способ выбран намеренно: НЕ запуск git в чужом рабочем дереве (его правила
сессии запрещают, и правильно), а сравнение содержимого файлов этого дерева с
теми же файлами в коммите, на котором дерево стоит. Коммит читается из своего
же хранилища объектов, файлы — обычным чтением.

Вывод один из трёх по каждому файлу:
  «не менялся»   — байт в байт как в коммите: быстрая передача его не затронет;
  «ИЗМЕНЁН»      — в чужом дереве лежит своя версия: передача затронула бы её;
  «добавляемый»  — мой коммит создаёт файл; важно, нет ли там такого же пути.
"""
from __future__ import annotations

import hashlib
import pathlib
import subprocess
import sys

МОЁ = pathlib.Path(__file__).resolve().parents[2]
ЧУЖОЕ = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path(
    "/home/claude/wt-portable-site-cell-01")
#: Коммит, на котором стоит чужое дерево; он же точка ветвления.
БАЗА = sys.argv[2] if len(sys.argv) > 2 else "claude/nova-publish-memory-01"


def из_коммита(путь: str) -> bytes | None:
    r = subprocess.run(["git", "show", f"{БАЗА}:{путь}"], cwd=str(МОЁ),
                       capture_output=True)
    return r.stdout if r.returncode == 0 else None


def главное() -> int:
    r = subprocess.run(["git", "diff", "--name-status", f"{БАЗА}..HEAD"],
                       cwd=str(МОЁ), capture_output=True, text=True, check=True)
    пересечения, добавляемые_заняты = [], []
    print(f"{'файл':52} {'вид':10} состояние в чужом дереве")
    for строка in r.stdout.strip().splitlines():
        вид, путь = строка.split("\t", 1)
        их = ЧУЖОЕ / путь
        if вид == "A":
            если = "занят их файлом" if их.exists() else "свободен"
            if их.exists():
                добавляемые_заняты.append(путь)
            print(f"{путь:52} {'добавляю':10} {если}")
            continue
        эталон = из_коммита(путь)
        if эталон is None:
            print(f"{путь:52} {'правлю':10} в коммите нет — разбирать отдельно")
            пересечения.append(путь)
            continue
        try:
            сейчас = их.read_bytes()
        except OSError as ош:
            print(f"{путь:52} {'правлю':10} не читается: {type(ош).__name__}")
            пересечения.append(путь)
            continue
        одинаково = hashlib.sha256(сейчас).digest() == hashlib.sha256(эталон).digest()
        print(f"{путь:52} {'правлю':10} "
              + ("не менялся" if одинаково else "ИЗМЕНЁН ИМИ"))
        if not одинаково:
            пересечения.append(путь)
    print()
    print("пересечений с их правками:", len(пересечения), пересечения)
    print("добавляемых путей, уже занятых:", len(добавляемые_заняты), добавляемые_заняты)
    return 1 if (пересечения or добавляемые_заняты) else 0


if __name__ == "__main__":
    raise SystemExit(главное())
