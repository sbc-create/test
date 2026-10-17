#!/usr/bin/env python3
"""Самые свежие записи УСТАНОВЛЕННОГО каталога витрины — для доказательства.

Зачем файлом, а не строкой в `ansible -m shell`. Вложенный python с кавычками
внутри оболочки здесь уже разваливался (в том числе на разборе прав: кусок
кода принимался за имя хоста). Файл читается и правится как код.

Печатает ревизию, число позиций и верхние записи по `published_at` — дате
появления записи в каталоге. По ним потом проверяется публичная страница:
адрес, отданный 200, доказывает, что доставленные данные доехали до
посетителя, а не только до диска.

Запуск на узле:  k2-catalog-newest.py <site_id> [сколько]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def главная(аргв: list[str]) -> int:
    if not аргв:
        print("нужен site_id", file=sys.stderr)
        return 2
    site = аргв[0]
    сколько = int(аргв[1]) if len(аргв) > 1 else 6
    # Путь — через опись узла, как у `k2-catalog-state.py`: данные лежат в
    # домашнем каталоге УЧЁТНОЙ ЗАПИСИ витрины (/srv/<account>/data), а не в
    # каталоге доставки. Угаданный путь дал «каталога нет» при живых данных.
    опись = json.loads(Path("/home/k2deploy/stage/MANIFEST.json")
                       .read_text(encoding="utf-8"))
    учётка = ((опись.get("cells") or {}).get(site) or {}).get("account")
    if not учётка:
        print(f"{site}: нет в описи узла")
        return 1
    путь = Path(f"/srv/{учётка}/data/{site}-catalog.json")
    if not путь.is_file():
        print(f"{site}: каталога нет по пути {путь}")
        return 1
    данные = json.loads(путь.read_text(encoding="utf-8"))
    записи = [з for з in (данные.get("items") or []) if з.get("published_at")]
    записи.sort(key=lambda з: з["published_at"], reverse=True)
    print(f"{site} revision={данные.get('revision')} "
          f"items={len(данные.get('items') or [])} "
          f"с_датой={len(записи)}")
    for з in записи[:сколько]:
        print(f"  {з['published_at']}  /title/{з.get('slug')}/  "
              f"{(з.get('title') or '')[:48]}  [{з.get('kind')} {з.get('year')}]")
    return 0


if __name__ == "__main__":
    sys.exit(главная(sys.argv[1:]))
