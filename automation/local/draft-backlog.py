#!/usr/bin/env python3
"""Черновики, ждущие публикации: сколько, где и названа ли причина.

Только чтение хранилищ доставки. Разделение намеренное: «ждёт под паузой»,
«ждёт с названной причиной» и «ждёт БЕЗ причины» — три разных состояния, и
сводить их в одно число значило бы прятать третье, единственное требующее
работы. Ждущий черновик без причины в отчёте неотличим от того, по которому
просто не дошли руки.

Измерено 20.10 после разбора: в паузе Lords/Zona 31, вне паузы с названной
причиной 5, вне паузы без причины 0.

Коды возврата: 0 — черновиков без названной причины нет, 3 — есть.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import pathlib
import sys

#: Витрины под паузой публикации описаний (блок владельца по site-factory-mcp).
ПАУЗА = frozenset({"zonafilm.space", "zonafilm.cc", "zonafilm12.site",
                   "lordfilm47.space", "1lordserials1.online",
                   "lordserial33.biz", "lordserials22.info"})
ЖУРНАЛЫ = "/srv/sites/*/runtime/overlays/*/history.jsonl"
ЧЕРНОВИКИ = "/srv/sites/*/runtime/overlays/*/drafts.json"


def _записи(путь: pathlib.Path):
    for строка in путь.read_text(encoding="utf-8").splitlines():
        строка = строка.strip()
        if not строка:
            continue
        try:
            yield json.loads(строка)
        except ValueError:
            continue


def собрать() -> dict:
    опубликовано: set[tuple[str, str]] = set()
    отзывы: dict[tuple[str, str], dict] = {}
    for путь in sorted(glob.glob(ЖУРНАЛЫ)):
        домен = pathlib.Path(путь).parent.name
        for з in _записи(pathlib.Path(путь)):
            ключ = (домен, з.get("slug"))
            if з.get("op") == "publish":
                опубликовано.add(ключ)
            elif з.get("op") == "review":
                отзывы[ключ] = з
    ждут = []
    for путь in sorted(glob.glob(ЧЕРНОВИКИ)):
        домен = pathlib.Path(путь).parent.name
        try:
            д = json.loads(pathlib.Path(путь).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for слаг, з in (д.get("items") or {}).items():
            ключ = (домен, слаг)
            if ключ in опубликовано:
                continue
            о = отзывы.get(ключ)
            ждут.append({
                "домен": домен, "слаг": слаг,
                "подготовлен": з.get("prepared_at") or "",
                "состояние": з.get("state"),
                "бед": len(з.get("quality_problems") or []),
                "в_паузе": домен in ПАУЗА,
                "вердикт": (о or {}).get("verdict"),
                "замечаний": len((о or {}).get("notes") or []),
            })
    return {"ждут": ждут}


def main(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    р.add_argument("--hours", type=float, default=24.0,
                   help="порог «ждёт дольше» в часах")
    дов = р.parse_args(аргв)

    сейчас = dt.datetime.now(dt.timezone.utc)
    итог = собрать()
    группы = {"в паузе": [], "с названной причиной": [], "БЕЗ причины": []}
    for з in итог["ждут"]:
        где = ("в паузе" if з["в_паузе"]
               else "с названной причиной" if з["вердикт"]
               else "БЕЗ причины")
        группы[где].append(з)

    print(f"черновиков ждёт публикации: {len(итог['ждут'])}")
    for имя, набор in группы.items():
        print(f"   {имя:24} {len(набор)}")

    долго = []
    for з in группы["БЕЗ причины"]:
        try:
            часов = (сейчас - dt.datetime.fromisoformat(
                з["подготовлен"].replace("Z", "+00:00"))).total_seconds() / 3600
        except ValueError:
            часов = None
        if часов is None or часов >= дов.hours:
            долго.append((часов, з))
    if долго:
        print(f"\nбез названной причины и дольше {дов.hours:.0f} ч:")
        for часов, з in sorted(долго, key=lambda п: -(п[0] or 0)):
            отм = f"{часов:7.1f} ч" if часов is not None else "  время?"
            print(f"   {отм}  {з['домен']:18} {з['слаг'][:34]:36}"
                  f" {з['состояние']}/{з['бед']}")
        return 3
    print("\nчерновиков без названной причины нет:"
          " каждый ждущий либо под паузой, либо с отзывом")
    return 0


if __name__ == "__main__":
    sys.exit(main())
