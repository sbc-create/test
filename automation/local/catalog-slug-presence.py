#!/usr/bin/env python3
"""Есть ли слаг или название в ЛЮБОМ читаемом снимке поставщика на этом хосте.

Повод: страница `zonafilm12.site/title/chuzhaya-zhizn/` отдала 404, и надо было
отличить четыре разные причины — данные поставщика, фильтрацию на нашей
стороне, сопоставление ID (переименование) и обоснованное снятие. Разницу
решает один вопрос: держит ли слаг или это название ХОТЬ ОДИН снимок. Поиск по
одному снимку витрины на него не отвечает: у поставщика одна база на все
семейства, и запись могла остаться у соседей.

Только чтение: ни один снимок не правится. Снимок каталога — постоянные данные
поставщика (docs/RUNTIME_DATA_OWNERSHIP.md).

    python3 automation/local/catalog-slug-presence.py --slug chuzhaya-zhizn
    python3 automation/local/catalog-slug-presence.py --title "Чужая жизнь"
"""
import argparse
import json
import pathlib
import sys


def снимки_хоста() -> list:
    """Все читаемые снимки каталога на машине, а не один."""
    найдено = set()
    for корень in (pathlib.Path("/srv"), pathlib.Path("/srv/lords/.frontend")):
        if корень.is_dir():
            найдено |= set(корень.glob("*/data/*-catalog.json"))
            найдено |= set(корень.glob("*-catalog*.json"))
    return sorted(найдено)


def искать(слаг: str = "", название: str = "") -> tuple:
    """(сколько снимков прочитано, список находок)."""
    осмотрено = 0
    находки = []
    for п in снимки_хоста():
        try:
            д = json.loads(п.read_text(encoding="utf-8"))
        except (OSError, ValueError, PermissionError):
            continue
        осмотрено += 1
        for з in д.get("items") or []:
            имя = str(з.get("title") or з.get("name") or "")
            свой = (слаг and str(з.get("slug") or "") == слаг) or \
                   (название and имя.strip().lower() == название.strip().lower())
            if свой:
                находки.append({"снимок": str(п), "slug": з.get("slug"),
                                "title": имя, "year": з.get("year"),
                                "kind": з.get("kind") or з.get("type")})
    return осмотрено, находки


def главная(аргв=None) -> int:
    р = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    р.add_argument("--slug", default="")
    р.add_argument("--title", default="")
    а = р.parse_args(аргв)
    if not а.slug and not а.title:
        print("BLOCKED_INPUT: нужен --slug или --title", file=sys.stderr)
        return 2
    осмотрено, находки = искать(а.slug, а.title)
    print(f"снимков прочитано: {осмотрено}")
    for н in находки:
        print(f"  НАЙДЕНО: {н['снимок']} | "
              f"{н['slug']} | {н['title']} | {н['year']} | {н['kind']}")
    if not находки:
        искали = а.slug or а.title
        print(f"  «{искали}» нет ни в одном прочитанном снимке — это данные "
              f"поставщика, а не фильтрация на нашей стороне")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(главная())
