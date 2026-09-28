#!/usr/bin/env python3
"""Собирает каталог Yummy из его собственного публичного API поиска.

Зачем так
---------

У Yummy есть `/api/search`, отдающий готовые поля: slug, href, name,
posterUrl, year, typeLabel. Это точнее, чем разбирать разметку: приложение
само называет свои данные, и парсер не ломается от смены вёрстки.

Каталог набирается перебором коротких запросов — по буквам алфавита и цифрам.
Дубликаты снимаются по href. Это не полный обход базы, и результат честно
называет себя частичным: `coverage: partial`.

Ничего не выдумывается: поля, которых API не отдаёт (жанры, страны, возраст,
КП, IMDb, сезоны), в каталог не попадают и не заполняются наугад.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

АЛФАВИТ = ("а б в г д е ж з и к л м н о п р с т у ф х ц ч ш э ю я "
           "a b c d e f g h i j k l m n o p q r s t u v w x y z "
           "0 1 2 3 4 5 6 7 8 9").split()
# Пары букв заметно расширяют охват при том же числе запросов.
ПАРЫ = [a + b for a in "абвгдкмнпрсто" for b in "аеиоу"]


def запрос(домен: str, q: str) -> list[dict]:
    try:
        готово = subprocess.run(
            ["curl", "-sS", "--max-time", "20", f"https://{домен}/api/search?q={q}"],
            capture_output=True, text=True, timeout=30)
        d = json.loads(готово.stdout)
    except (subprocess.SubprocessError, ValueError, OSError):
        return []
    return d.get("items") or []


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--domain", required=True)
    р.add_argument("--out", required=True)
    args = р.parse_args()

    каталог: dict[str, dict] = {}
    запросов = 0
    for q in АЛФАВИТ + ПАРЫ:
        запросов += 1
        for з in запрос(args.domain, q):
            href = з.get("href")
            if not href or href in каталог:
                continue
            каталог[href] = {
                "slug": з.get("slug"),
                "title": з.get("name"),
                "poster": з.get("posterUrl"),
                "year": з.get("year"),
                "kind": з.get("typeLabel"),
                "url": href,
            }
        if запросов % 20 == 0:
            print(f"[yummy] запросов {запросов}, собрано {len(каталог)}", file=sys.stderr)

    if not каталог:
        print("каталог пуст: API не ответил", file=sys.stderr)
        return 1
    без_постера = sum(1 for з in каталог.values() if not з["poster"])
    Path(args.out).write_text(json.dumps({
        "version": 1,
        "source": f"https://{args.domain}/api/search",
        "coverage": "partial",
        "coverage_note": ("каталог набран перебором коротких запросов, а не полным "
                          "обходом базы: это не весь каталог, и выдавать его за "
                          "полный нельзя"),
        "queries": запросов,
        "count": len(каталог),
        "without_poster": без_постера,
        "fields_present": ["slug", "title", "poster", "kind", "year", "url"],
        "fields_absent": ["genres", "countries", "age_rating", "kp", "imdb", "seasons"],
        "absent_reason": "API поиска этих полей не отдаёт; выдумывать их запрещено",
        "items": sorted(каталог.values(),
                        key=lambda з: (-(з["year"] or 0), з["title"] or "")),
    }, ensure_ascii=False), encoding="utf-8")
    print(f"[yummy] {args.out}: {len(каталог)} тайтлов за {запросов} запросов, "
          f"без постера {без_постера}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
