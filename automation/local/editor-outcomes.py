#!/usr/bin/env python3
"""Чем кончаются задания редактора: доли исходов по периодам. Только чтение.

Зачем. «Редактор работает» и «редактор пишет тексты» — разные утверждения. За
ночь 18→19.10 из 83 исходов 45 были `SOURCES_MISSING`: прогон шёл, модель
работала, текста не появлялось. Чтобы судить о правках источников (MOD-85), доли
исходов нужно сравнивать до и после, а не смотреть на один прогон.

Считается по `*.run.json` самих прогонов: поле `outcomes`. Журнал `runs.jsonl`
исходов заданий не несёт — считать по нему ошибка, она уже делалась.

    python3 automation/local/editor-outcomes.py --since 2026-10-18T20:00Z
    python3 automation/local/editor-outcomes.py --split 2026-10-19T06:30Z
    python3 automation/local/editor-outcomes.py --split 2026-10-19T06:30Z --json

`--split` делит прогоны на «до» и «после» указанного времени и печатает доли
рядом: именно так видно, изменилось ли что-то после правки.

Коды: 0 — посчитано; 2 — прогонов в периоде нет.
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


def прогоны(каталог: pathlib.Path, с: dt.datetime | None,
            по: dt.datetime | None) -> list[tuple[dt.datetime, dict]]:
    итог = []
    for п in sorted(каталог.glob("*.run.json")):
        try:
            когда = dt.datetime.strptime(п.name.split(".")[0], "%Y%m%dT%H%M%SZ").replace(
                tzinfo=dt.timezone.utc)
        except ValueError:
            continue
        if (с and когда < с) or (по and когда > по):
            continue
        try:
            итог.append((когда, json.loads(п.read_text(encoding="utf-8"))))
        except (OSError, ValueError):
            continue
    return итог


def свод(записи: list[tuple[dt.datetime, dict]]) -> dict:
    исходы = collections.Counter()
    публикаций = 0
    for _, д in записи:
        for и in д.get("outcomes") or []:
            исходы[str(и.get("outcome") or "?")] += 1
        публикаций += len((д.get("self_report") or {}).get("urls") or [])
    всего = sum(исходы.values())
    return {
        "прогонов": len(записи),
        "заданий": всего,
        "публикаций": публикаций,
        "исходы": dict(исходы),
        "доли": {к: round(100 * v / всего, 1) for к, v in исходы.items()} if всего else {},
        "период": (f"{записи[0][0]:%Y-%m-%dT%H:%MZ}..{записи[-1][0]:%Y-%m-%dT%H:%MZ}"
                   if записи else ""),
    }


def _печать(имя: str, с: dict) -> None:
    print(f"=== {имя}: прогонов {с['прогонов']}, заданий {с['заданий']},"
          f" публикаций {с['публикаций']} ({с['период']})")
    for исход, сколько in sorted(с["исходы"].items(), key=lambda п: -п[1]):
        print(f"      {исход:20} {сколько:4}  {с['доли'].get(исход, 0):5.1f} %")


def main(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description="доли исходов заданий редактора")
    р.add_argument("--dir", default=str(ПРОГОНЫ))
    р.add_argument("--since", default="")
    р.add_argument("--until", default="")
    р.add_argument("--split", default="", help="разделить период этим временем")
    р.add_argument("--json", action="store_true")
    дов = р.parse_args(аргв)

    каталог = pathlib.Path(дов.dir)
    с, по = _время(дов.since) if дов.since else None, _время(дов.until) if дов.until else None
    if дов.since and с is None:
        print(f"НЕ ИЗМЕРЕНО: время --since {дов.since!r} не разобрано")
        return 2
    if дов.until and по is None:
        print(f"НЕ ИЗМЕРЕНО: время --until {дов.until!r} не разобрано")
        return 2
    записи = прогоны(каталог, с, по)
    if not записи:
        print("НЕ ИЗМЕРЕНО: прогонов в периоде нет")
        return 2

    if дов.split:
        рубеж = _время(дов.split)
        if рубеж is None:
            print(f"НЕ ИЗМЕРЕНО: время --split {дов.split!r} не разобрано")
            return 2
        до = [з for з in записи if з[0] < рубеж]
        после = [з for з in записи if з[0] >= рубеж]
        итог = {"до": свод(до), "после": свод(после), "рубеж": дов.split}
        if дов.json:
            print(json.dumps(итог, ensure_ascii=False, indent=2))
            return 0
        _печать(f"до {дов.split}", итог["до"])
        _печать(f"после {дов.split}", итог["после"])
        мало = min(итог["до"]["заданий"], итог["после"]["заданий"])
        print()
        if мало < 30:
            print(f"ВЫВОДА НЕТ: в меньшей части {мало} заданий. Доли на таком числе "
                  "шумят сильнее любой правки — нужен ещё материал.")
        return 0

    свод_ = свод(записи)
    if дов.json:
        print(json.dumps(свод_, ensure_ascii=False, indent=2))
    else:
        _печать("период", свод_)
    return 0


if __name__ == "__main__":
    sys.exit(main())
