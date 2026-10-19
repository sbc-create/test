#!/usr/bin/env python3
"""Почему шлюз редактора отказывает: сводка по журналу. Только чтение.

Шлюз решает на каждом такте таймера, запускать ли партию редактора. Отказ —
нормальное решение, но отказы разного рода означают разное: удержание доли это
расписание, нехватка памяти — ёмкость хоста, пауза после партии — ритм. Если не
считать их раздельно, «редактор работает» и «редактор почти не запускается»
выглядят одинаково.

    python3 automation/local/editor-gate-stats.py --hours 24
    python3 automation/local/editor-gate-stats.py --hours 6 --json

Коды: 0 — журнал прочитан; 2 — журнала нет или записей за период нет.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import pathlib
import re
import sys

ЖУРНАЛ = pathlib.Path(
    "/home/claude/wt-portable-site-cell-01/var/editor-runs/gate.jsonl")


def разобрать(часов: int, журнал: pathlib.Path = ЖУРНАЛ,
              сейчас: dt.datetime | None = None) -> dict:
    сейчас = сейчас or dt.datetime.now(dt.timezone.utc)
    порог = сейчас - dt.timedelta(hours=часов)
    состояния = collections.Counter()
    запуски = 0
    память = []
    первая = последняя = ""
    try:
        строки = журнал.read_text(encoding="utf-8").splitlines()
    except OSError as сбой:
        return {"измерено": False, "почему": f"журнал не прочитан: {сбой}"}
    for строка in строки:
        try:
            з = json.loads(строка)
        except ValueError:
            continue
        когда = str(з.get("at") or "")
        try:
            м = dt.datetime.strptime(когда, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=dt.timezone.utc)
        except ValueError:
            continue
        if м < порог:
            continue
        первая = первая or когда
        последняя = когда
        шлюз = з.get("gate") or {}
        if шлюз.get("run"):
            запуски += 1
            состояния["ЗАПУСК"] += 1
            continue
        состояния[str(шлюз.get("state") or "без состояния")] += 1
        ресурсы = шлюз.get("resources") or {}
        if "mem_available_mib" in ресурсы:
            память.append(float(ресурсы["mem_available_mib"]))
        else:
            м2 = re.search(r"памяти доступно (\d+) МиБ < (\d+)",
                           str(шлюз.get("reason") or ""))
            if м2:
                память.append(float(м2.group(1)))
    всего = sum(состояния.values())
    if not всего:
        return {"измерено": False, "почему": f"записей за {часов} ч нет"}
    return {"измерено": True, "тактов": всего, "запусков": запуски,
            "состояния": состояния, "период": f"{первая}..{последняя}",
            "память_мин": min(память) if память else None,
            "память_макс": max(память) if память else None}


def main(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description="сводка отказов шлюза редактора")
    р.add_argument("--hours", type=int, default=24)
    р.add_argument("--json", action="store_true")
    дов = р.parse_args(аргв)
    и = разобрать(дов.hours)
    if дов.json:
        печать = dict(и)
        if и["измерено"]:
            печать["состояния"] = dict(и["состояния"])
        print(json.dumps(печать, ensure_ascii=False, indent=2))
        return 0 if и["измерено"] else 2
    if not и["измерено"]:
        print(f"НЕ ИЗМЕРЕНО: {и['почему']}")
        return 2
    print(f"период {и['период']}; тактов {и['тактов']}, из них запусков "
          f"{и['запусков']} ({100 * и['запусков'] / и['тактов']:.1f} %)")
    for состояние, сколько in и["состояния"].most_common():
        print(f"   {состояние:18} {сколько:4}  ({100 * сколько / и['тактов']:.1f} %)")
    if и["память_мин"] is not None:
        print(f"   доступная память в отказах: {и['память_мин']:.0f}–"
              f"{и['память_макс']:.0f} МиБ")
    return 0


if __name__ == "__main__":
    sys.exit(main())
