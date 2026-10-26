#!/usr/bin/env python3
"""Вернулись ли в снимок поставщика пропавшие записи.

26.10.2026 из каталога пропали «Чужая жизнь» (227 из 264 входов Яндекса
zonafilm12.site за неделю) и «Изгнанный реинкарнированный тяжёлый рыцарь…».
Исход PAGE_ABSENT держит адрес 7 суток, но отдельного наблюдения за возвратом
записи не было: вернись она, этого бы никто не заметил. Скрипт читает список
`config/provider-defect-watch.json` и каждый снимок из него (только чтение)
и печатает по каждой записи: есть ли слаг в снимке, ревизию и время сборки.

    python3 automation/local/provider-defect-watch.py [--watch путь]

Код выхода 0 всегда, кроме нечитаемого списка: возврат записи — сигнал SEO
к действию, а не ошибка.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

СПИСОК = Path(__file__).resolve().parents[2] / "config" / "provider-defect-watch.json"


def состояние_снимка(путь: str, слаг: str) -> dict:
    try:
        снимок = json.loads(Path(путь).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return {"catalog": путь, "readable": False, "reason": type(e).__name__}
    записи = снимок.get("details") if isinstance(снимок, dict) else None
    if isinstance(записи, dict):
        есть = слаг in записи
    elif isinstance(записи, list):
        есть = any(isinstance(r, dict) and r.get("slug") == слаг for r in записи)
    else:
        return {"catalog": путь, "readable": False, "reason": "нет поля details"}
    return {"catalog": путь, "readable": True, "present": есть,
            "revision": снимок.get("catalog_revision"), "built_at": снимок.get("catalog_built_at")}


def проверить(список: dict) -> list[dict]:
    итог = []
    for запись in список.get("watch", []):
        снимки = [состояние_снимка(п, запись["slug"]) for п in запись.get("catalogs", [])]
        итог.append({"slug": запись["slug"], "title": запись.get("title"),
                     "returned": any(s.get("present") for s in снимки), "catalogs": снимки})
    return итог


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch", default=str(СПИСОК))
    a = ap.parse_args(argv)
    try:
        список = json.loads(Path(a.watch).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"список не прочитан: {e}")
        return 2
    for r in проверить(список):
        print(f"{'ВЕРНУЛАСЬ' if r['returned'] else 'нет'}: {r['slug']} — {r['title']}")
        for s in r["catalogs"]:
            if s["readable"]:
                print(f"  {s['catalog']}: {'есть' if s['present'] else 'нет'} (ревизия {s['revision']}, сборка {s['built_at']})")
            else:
                print(f"  {s['catalog']}: не прочитан ({s['reason']})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
