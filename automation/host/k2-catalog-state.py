#!/usr/bin/env python3
"""Состояние каталогов витрин НА УЗЛЕ: что установлено и что ждёт установки.

Зачем файлом, а не строкой в `ansible -m shell`. Вложенный python с кавычками
внутри f-строки трижды развалился по дороге через оболочку (измерено: то
`unexpected character after line continuation`, то `NameError`). Файл читается
и правится как код, а не как строка в строке.

Что печатает по каждой витрине: ревизия и число позиций УСТАНОВЛЕННОГО
каталога, время его изменения, и есть ли непринятый входящий комплект. Этого
достаточно, чтобы отличить «данные свежие» от «комплект доставлен, но ещё не
установлен» — два состояния, которые снаружи выглядят одинаково.

Запуск на узле:  k2-catalog-state.py [site_id ...]
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

ОПИСЬ = Path("/home/k2deploy/stage/MANIFEST.json")
ВХОДЯЩИЕ = Path("/home/k2deploy/stage/incoming")


def витрины() -> dict[str, str]:
    """site_id → учётная запись, из описи узла."""
    опись = json.loads(ОПИСЬ.read_text(encoding="utf-8"))
    return {с: з["account"] for с, з in (опись.get("cells") or {}).items()}


def когда(путь: Path) -> str:
    т = dt.datetime.fromtimestamp(путь.stat().st_mtime, dt.timezone.utc)
    return т.strftime("%Y-%m-%dT%H:%MZ")


def главное(нужные: list[str]) -> int:
    пары = витрины()
    цели = нужные or sorted(пары)
    плохо = 0
    for site_id in цели:
        учётка = пары.get(site_id)
        if not учётка:
            print(f"{site_id}: нет в описи узла")
            плохо += 1
            continue
        каталог = Path(f"/srv/{учётка}/data/{site_id}-catalog.json")
        подробности = Path(f"/srv/{учётка}/data/{site_id}-details.json")
        входящий = ВХОДЯЩИЕ / site_id
        строка = [f"{site_id}"]
        if каталог.is_file():
            try:
                данные = json.loads(каталог.read_text(encoding="utf-8"))
                строка.append(f"revision={данные.get('revision')}")
                строка.append(f"items={len(данные.get('items') or [])}")
                строка.append(f"installed_at={когда(каталог)}")
            except (OSError, ValueError) as ош:
                строка.append(f"catalog_unreadable={type(ош).__name__}")
                плохо += 1
        else:
            строка.append("catalog_missing")
            плохо += 1
        if подробности.is_file():
            строка.append(f"details_mib={подробности.stat().st_size // (1024 * 1024)}")
        ожидает = (входящий.is_dir()
                   and any(входящий.glob("*.json")))
        строка.append(f"incoming_pending={'да' if ожидает else 'нет'}")
        print(" ".join(строка))
    print(f"итог: витрин {len(цели)}, с проблемами {плохо}")
    return 0 if плохо == 0 else 3


if __name__ == "__main__":
    raise SystemExit(главное(sys.argv[1:]))
