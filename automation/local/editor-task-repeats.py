#!/usr/bin/env python3
"""Сколько заданий редактор получает повторно с тем же исходом. Только чтение.

Повод. Исход `SOURCES_MISSING` за ночь 18→19.10 — 45 из 83 заданий, и собственная
записка прогона 07:40Z говорит прямо: «6 заданий очереди закрыты без текста: 4
повтора PAGE_ABSENT/SOURCES_MISSING». Повторная выдача задания, у которого
условия не изменились, тратит не строку в журнале, а ПРОГОН модели — то есть
текст, который в это время не написан.

Считается по `outcomes` прогонов: один `task_id` с одним и тем же исходом в
разных прогонах — это повтор. Инструмент не решает, плохо это или нет: у
очереди есть срок повторной проверки, и повтор после смены условий законен.
Он называет число и показывает, на сколько прогонов растянулась серия.

    python3 automation/local/editor-task-repeats.py --since 2026-10-18T20:00Z
    python3 automation/local/editor-task-repeats.py --min-repeats 3 --json

Коды: 0 — повторов нет; 1 — есть; 2 — прогонов в периоде нет.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import pathlib
import sys

ПРОГОНЫ = pathlib.Path("/home/claude/wt-portable-site-cell-01/var/editor-runs")


def _время(метка: str) -> dt.datetime | None:
    for формат in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%MZ", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(метка, формат).replace(tzinfo=dt.timezone.utc)
        except ValueError:
            continue
    return None


def собрать(каталог: pathlib.Path, с: dt.datetime | None,
            по: dt.datetime | None) -> list[tuple[str, str, str]]:
    """[(прогон, task_id, исход)] по порядку прогонов."""
    итог = []
    for п in sorted(каталог.glob("*.run.json")):
        метка = п.name.split(".")[0]
        try:
            когда = dt.datetime.strptime(метка, "%Y%m%dT%H%M%SZ").replace(
                tzinfo=dt.timezone.utc)
        except ValueError:
            continue
        if (с and когда < с) or (по and когда > по):
            continue
        try:
            д = json.loads(п.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for и in д.get("outcomes") or []:
            задача = str(и.get("task_id") or "")
            исход = str(и.get("outcome") or "")
            if задача and исход:
                итог.append((метка, задача, исход))
    return итог


def разобрать(записи: list[tuple[str, str, str]], минимум: int = 2) -> dict:
    по_задаче: dict[tuple[str, str], list[str]] = collections.defaultdict(list)
    for прогон, задача, исход in записи:
        по_задаче[(задача, исход)].append(прогон)
    повторы = {к: v for к, v in по_задаче.items() if len(v) >= минимум}
    всего_выдач = len(записи)
    лишних = sum(len(v) - 1 for v in повторы.values())
    исходы = collections.Counter(исход for (_, исход), v in повторы.items()
                                 for _ in range(len(v) - 1))
    верх = sorted(повторы.items(), key=lambda п: -len(п[1]))[:10]
    return {
        "выдач": всего_выдач,
        "задач_с_повторами": len(повторы),
        "лишних_выдач": лишних,
        "доля_лишних": round(100 * лишних / всего_выдач, 1) if всего_выдач else 0.0,
        "по_исходу": dict(исходы),
        "верх": [{"task_id": к[0], "исход": к[1], "выдач": len(v),
                  "прогоны": v[:6]} for к, v in верх],
    }


def main(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description="повторные выдачи заданий редактору")
    р.add_argument("--dir", default=str(ПРОГОНЫ))
    р.add_argument("--since", default="")
    р.add_argument("--until", default="")
    р.add_argument("--min-repeats", type=int, default=2)
    р.add_argument("--json", action="store_true")
    дов = р.parse_args(аргв)

    с = _время(дов.since) if дов.since else None
    по = _время(дов.until) if дов.until else None
    if дов.since and с is None:
        print(f"НЕ ИЗМЕРЕНО: время --since {дов.since!r} не разобрано")
        return 2
    записи = собрать(pathlib.Path(дов.dir), с, по)
    if not записи:
        print("НЕ ИЗМЕРЕНО: прогонов с исходами в периоде нет")
        return 2
    и = разобрать(записи, дов.min_repeats)

    if дов.json:
        print(json.dumps(и, ensure_ascii=False, indent=2))
    else:
        print(f"выдач заданий {и['выдач']}; задач с повторами "
              f"{и['задач_с_повторами']}; лишних выдач {и['лишних_выдач']}"
              f" ({и['доля_лишних']} %)")
        for исход, сколько in sorted(и["по_исходу"].items(), key=lambda п: -п[1]):
            print(f"   {исход:20} лишних выдач {сколько}")
        for з in и["верх"]:
            print(f"   {з['task_id'][:16]} {з['исход']:18} выдач {з['выдач']}"
                  f"  прогоны {', '.join(т[9:15] for т in з['прогоны'])}")
        print()
        print("Повтор сам по себе не дефект: у очереди есть срок повторной "
              "проверки, и повтор после смены условий законен. Здесь названо "
              "только число.")
    return 1 if и["лишних_выдач"] else 0


if __name__ == "__main__":
    sys.exit(main())
