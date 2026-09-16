#!/usr/bin/env python3
"""Дополняет каталог витрины оригинальными названиями из поискового индекса.

Поиск обязан находить тайтл и по оригинальному названию, а не только по
русскому. Оригинальные названия есть в `search-index.json` релиза — там поле
`original_name`. В каталоге, собранном из разметки карточек, его нет.

Здесь два источника сводятся по `url`. Ничего не выдумывается: у записи, где
`original_name` пуст, он остаётся пустым, и это видно в сводке.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--catalog", required=True)
    р.add_argument("--search-index", required=True)
    р.add_argument("--aliases", default=None,
                   help="JSON с переданными владельцем синонимами: url -> [названия]")
    args = р.parse_args()

    каталог = json.loads(Path(args.catalog).read_text(encoding="utf-8"))
    индекс = json.loads(Path(args.search_index).read_text(encoding="utf-8"))
    по_url = {з.get("url"): з for з in индекс.get("items", [])}

    синонимы = {}
    if args.aliases and Path(args.aliases).is_file():
        синонимы = json.loads(Path(args.aliases).read_text(encoding="utf-8"))

    с_оригиналом = 0
    с_синонимами = 0
    for з in каталог["items"]:
        из_индекса = по_url.get(з["url"]) or {}
        ориг = (из_индекса.get("original_name") or "").strip()
        з["original_title"] = ориг or None
        if ориг:
            с_оригиналом += 1
        доп = синонимы.get(з["url"])
        if доп:
            з["aliases"] = доп
            с_синонимами += 1

    каталог["enriched"] = {
        "with_original_title": с_оригиналом,
        "with_owner_aliases": с_синонимами,
        "total": len(каталог["items"]),
        "note": ("original_title взят из search-index.json релиза; пустое значение "
                 "оставлено пустым. aliases приходят ТОЛЬКО из переданного владельцем "
                 "файла — синонимы не выводятся и не угадываются."),
    }
    Path(args.catalog).write_text(json.dumps(каталог, ensure_ascii=False), encoding="utf-8")
    print(f"[обогащение] {args.catalog}: оригинальных названий {с_оригиналом} "
          f"из {len(каталог['items'])}, синонимов владельца {с_синонимами}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
