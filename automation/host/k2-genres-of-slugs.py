#!/usr/bin/env python3
"""Жанры конкретных записей по УСТАНОВЛЕННОМУ боковому файлу витрины.

Зачем. Проверить жанровую страницу можно только по тем данным, на которых она
собрана. Сверка по названию из снимка поставщика для этого не годится:
одноимённые записи существуют (слуги вида `…-2` именно о них), и сопоставление
по имени молча берёт не ту запись — измерено 2026-10-17, из-за этого проверка
объявила «жанр не подтверждён» там, где подтверждать было нечем.

Вывод компактный: по строке на слуг, поэтому его можно получить через обычный
вызов на узле, не выкачивая 85 МиБ бокового файла.

Запуск на узле:  k2-genres-of-slugs.py <site_id> <slug> [slug ...]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ОПИСЬ = Path("/home/k2deploy/stage/MANIFEST.json")


def главная(аргв: list[str]) -> int:
    if len(аргв) < 2:
        print("нужен site_id и хотя бы один слуг", file=sys.stderr)
        return 2
    site, слуги = аргв[0], аргв[1:]
    опись = json.loads(ОПИСЬ.read_text(encoding="utf-8"))
    учётка = ((опись.get("cells") or {}).get(site) or {}).get("account")
    if not учётка:
        print(f"{site}: нет в описи узла")
        return 1
    путь = Path(f"/srv/{учётка}/data/{site}-details.json")
    if not путь.is_file():
        print(f"{site}: бокового файла нет по пути {путь}")
        return 1
    данные = json.loads(путь.read_text(encoding="utf-8"))
    подробности = данные.get("details") or {}
    print(f"{site} revision={данные.get('catalog_revision')} "
          f"записей={len(подробности)}")
    for s in слуги:
        д = подробности.get(s)
        if д is None:
            print(f"  {s}: записи нет")
            continue
        print(f"  {s}: type={д.get('type')} genres={д.get('genres')}")
    return 0


if __name__ == "__main__":
    sys.exit(главная(sys.argv[1:]))
