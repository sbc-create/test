#!/usr/bin/env python3
"""Список маршрутов приёмки Yummy: структура — из карты страниц, слаги — из данных.

Почему генератор, а не записанный руками список
-----------------------------------------------

Маршрут `/anime/<слаг>` нельзя записать в файл навсегда: слаг принадлежит
данным, и записанный однажды он через неделю ведёт в 404 — проверка начинает
измерять не страницу, а устаревание собственного файла. Структура маршрутов
берётся из `docs/templates/PAGE-MAP-yummy.md`, а конкретные слаги — из того
же снимка, на котором поднят предпросмотр.

Если для маршрута в данных нет подходящей записи, маршрут не выдумывается и
не подменяется соседним: он выводится со статусом `NO_DATA`, и приёмка честно
покажет, что проверить его нечем.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


def _одно(соед, запрос: str):
    try:
        строка = соед.execute(запрос).fetchone()
    except sqlite3.Error:
        return None
    return строка[0] if строка else None


def маршруты(база: Path) -> tuple[list[dict], list[dict]]:
    соед = sqlite3.connect(f"file:{база}?mode=ro", uri=True)
    try:
        # Тайтл для проверки карточки: берётся продолжающийся, у него есть и
        # статус показа, и шанс на серии.
        тайтл = (_одно(соед, "select slug from entity where airing_status='DERIVED_ONGOING'"
                             " and slug is not null order by slug limit 1")
                 or _одно(соед, "select slug from entity where slug is not null"
                                " order by slug limit 1"))
        серия = None
        try:
            серия = соед.execute(
                "select e.slug, v.season, v.episode from episode_event v"
                " join entity e on e.entity_id = v.entity_id"
                " where e.slug is not null order by e.slug, v.season, v.episode limit 1").fetchone()
        except sqlite3.Error:
            серия = None
        # Запрос поиска берётся из настоящего названия: искать заведомо
        # отсутствующее слово и радоваться нулю — проверка ни о чём.
        #
        # Название отбирается простое — буквы и пробелы. Первое попавшееся
        # по алфавиту оказывается вроде «.хак//Знак»: такой запрос проверяет
        # экранирование адреса, а не поиск, и дефект поиска за ним не виден.
        название = None
        try:
            for (имя,) in соед.execute(
                    "select title_ru from entity where title_ru is not null"
                    " order by title_ru limit 4000"):
                if 5 <= len(имя) <= 24 and all(с.isalpha() or с == " " for с in имя):
                    название = имя
                    break
        except sqlite3.Error:
            название = None
    finally:
        соед.close()

    нет: list[dict] = []
    список: list[dict] = [
        {"name": "home", "path": "/", "kind": "app"},
        {"name": "catalog", "path": "/catalog", "kind": "app"},
        {"name": "catalog-page2", "path": "/catalog?page=2", "kind": "app"},
        {"name": "catalog-ongoing", "path": "/catalog/ongoing", "kind": "app"},
        {"name": "catalog-announcement", "path": "/catalog/announcement", "kind": "app"},
        {"name": "catalog-schedule", "path": "/catalog/schedule", "kind": "app"},
        {"name": "catalog-updates", "path": "/catalog/anime-updates", "kind": "app"},
        {"name": "catalog-top", "path": "/catalog/top", "kind": "app"},
        {"name": "posts", "path": "/posts", "kind": "app"},
        {"name": "reviews", "path": "/reviews", "kind": "app"},
        {"name": "search-empty", "path": "/search?q=", "kind": "app"},
        {"name": "search-none", "path": "/search?q=zzqqxxyy", "kind": "app"},
        {"name": "not-found", "path": "/net-takogo-adresa-proverka", "kind": "app"},
        # Собственные страницы витрины — то, что она рисует сама.
        {"name": "own-new", "path": "/new/", "kind": "own"},
        {"name": "own-collections", "path": "/collections/", "kind": "own"},
        {"name": "own-schedule", "path": "/schedule/", "kind": "own"},
        {"name": "own-top", "path": "/top/", "kind": "own"},
    ]
    if название:
        список.insert(10, {"name": "search-title", "path": f"/search?q={название}", "kind": "app",
                           "note": f"название из данных: {название}"})
    else:
        нет.append({"name": "search-title", "reason": "NO_DATA: в снимке нет названия"})
    if тайтл:
        список.append({"name": "title", "path": f"/anime/{тайтл}", "kind": "app"})
    else:
        нет.append({"name": "title", "reason": "NO_DATA: в снимке нет ни одного слага"})
    if серия:
        слаг, сезон, эпизод = серия
        список.append({"name": "season", "path": f"/anime/{слаг}/season/{сезон}", "kind": "app"})
        список.append({"name": "episode",
                       "path": f"/anime/{слаг}/season/{сезон}/episode/{эпизод}", "kind": "app"})
    else:
        нет.append({"name": "season/episode", "reason": "NO_DATA: в снимке нет событий серий"})
    return список, нет


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--readmodel", required=True)
    р.add_argument("--out", required=True)
    а = р.parse_args()
    список, нет = маршруты(Path(а.readmodel))
    Path(а.out).write_text(json.dumps(список, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"маршрутов: {len(список)} → {а.out}")
    for п in нет:
        print(f"  NO_DATA {п['name']}: {п['reason']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
