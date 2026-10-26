#!/usr/bin/env python3
"""Отметки времени из будущего в незакоммиченных правках.

26.10.2026 сессия пять раз за вечер вписала в журнал, отчёт или реестр время
позже текущего (16:18–16:30Z при 16:17Z, «~16:45Z» при 16:43Z, «17:12» при
17:11Z, «18:00Z» при 17:53Z, «~21:12Z» при 21:10Z). Правило «время только из
date -u» было известно — не хватало механической проверки.

Скрипт смотрит добавленные строки `git diff` (и проиндексированные, и нет),
находит отметки HH:MM или HH:MM:SS с суффиксом Z и сравнивает с текущим UTC.
Отметка позже текущего времени более чем на минуту — ошибка, код выхода 1.
Даты другого дня в строке не разбираются: проверка рассчитана на записи
текущей смены, где день подразумевается.

    python3 automation/local/future-time-check.py [путь …]
"""
from __future__ import annotations

import datetime as dt
import re
import subprocess
import sys

ОТМЕТКА = re.compile(r"(?<![\d:])(?:~)?([01]\d|2[0-3]):([0-5]\d)(?::([0-5]\d))?Z")


def добавленные_строки(пути: list[str]) -> list[str]:
    строки = []
    for аргументы in (["git", "diff", "-U0"], ["git", "diff", "--cached", "-U0"]):
        вывод = subprocess.run(аргументы + ["--", *пути], capture_output=True, text=True).stdout
        строки += [s[1:] for s in вывод.splitlines() if s.startswith("+") and not s.startswith("+++")]
    return строки


def из_будущего(строки: list[str], сейчас: dt.datetime) -> list[tuple[str, str]]:
    предел = сейчас + dt.timedelta(minutes=1)
    найдено = []
    for строка in строки:
        for m in ОТМЕТКА.finditer(строка):
            ч, мин, с = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
            момент = сейчас.replace(hour=ч, minute=мин, second=с, microsecond=0)
            if момент > предел:
                найдено.append((m.group(0), строка.strip()[:160]))
    return найдено


def main(argv: list[str]) -> int:
    сейчас = dt.datetime.now(dt.timezone.utc)
    найдено = из_будущего(добавленные_строки(argv), сейчас)
    print(f"сейчас {сейчас:%H:%M:%S}Z; отметок позже: {len(найдено)}")
    for отметка, строка in найдено:
        print(f"  {отметка}: {строка}")
    return 1 if найдено else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
