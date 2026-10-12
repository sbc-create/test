#!/usr/bin/env python3
"""Внутренний поиск — noindex, follow. Перенос по якорям.

knowledge/SEO_KNOWLEDGE_PACK.md §3 п.2: «Комбинаторные фильтры, сортировки, вид
отображения, tracking-параметры и ВНУТРЕННИЙ ПОИСК по умолчанию не индексируются
и не попадают в sitemap». Аудит страниц 12.10: /search/?q=… у всех 12 витрин —
200, index, follow; у Zona и Animedia ещё и self-canonical с q — любой запрос
становился индексируемым адресом. Страница поиска работает как прежде.

Правило дописывается к условию apply-unknown-keys-noindex в _отдать (meta robots
и X-Robots-Tag вместе, только ужесточение).

    python3 automation/host/apply-search-noindex.py [--check] <файл> […]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

МЕТКА = "def _поиск_по_сайту("
ВЫЗОВ = '_лишние_ключи_запроса(self.path or "/")'
НОВЫЙ_ВЫЗОВ = '(_лишние_ключи_запроса(self.path or "/") or _поиск_по_сайту(self.path or "/"))'
ЯКОРЬ_БЛОКА = "\ndef _закрытые_роботы(значение: str) -> str:\n"
ФУНКЦИЯ = '''

def _поиск_по_сайту(путь: str) -> bool:
    """Внутренний поиск не индексируется (§3 п.2; apply-search-noindex)."""
    from urllib.parse import urlsplit as _адрес
    return _адрес(путь).path.rstrip("/") == "/search"
'''


def привести(текст: str) -> tuple[str, int]:
    if МЕТКА in текст:
        return текст, 0
    if текст.count(ВЫЗОВ) != 1 or текст.count(ЯКОРЬ_БЛОКА) != 1:
        raise ValueError("нет правила лишних ключей (apply-unknown-keys-noindex) — ставить не к чему")
    текст = текст.replace(ВЫЗОВ, НОВЫЙ_ВЫЗОВ)
    return текст.replace(ЯКОРЬ_БЛОКА, ФУНКЦИЯ + ЯКОРЬ_БЛОКА), 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--family", help="не используется; для единообразия с соседними инструментами")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("files", nargs="+")
    a = ap.parse_args(argv)
    код = 0
    for имя in a.files:
        путь = Path(имя)
        текст = путь.read_text(encoding="utf-8")
        try:
            новый, n = привести(текст)
        except ValueError as exc:
            print(f"{имя}: ОТКАЗ — {exc}")
            код = 2
            continue
        if a.check:
            print(f"{имя}: {'приведён' if новый == текст else 'не приведён'}")
            код = код or (0 if новый == текст else 1)
            continue
        if новый != текст:
            путь.write_text(новый, encoding="utf-8")
        print(f"{имя}: приведён")
    return код


if __name__ == "__main__":
    sys.exit(main())
