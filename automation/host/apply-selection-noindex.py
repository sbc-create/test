#!/usr/bin/env python3
"""Выборка каталога без собственной страницы — noindex, follow. Перенос по якорям.

knowledge/SEO_KNOWLEDGE_PACK.md §3 п.1–2: фильтр индексируется лишь при
подтверждённом назначении, стабильном URL, уникальном контенте, SELF-CANONICAL и
внутренних ссылках; комбинаторные фильтры, сортировки и вид отображения по
умолчанию не индексируются. Замер Архитектора 12.10: AnimeGo ?yf=2026, ?eps=1,
?ongoing=1, ?type=movie — 200 index, canonical /catalog/ (общих карточек 0–9 из
24); Animedia ?sort=title — 200 index, canonical /catalog/ (общих 10 из 58).
Индексируемая страница объявляла канонической страницу с другим составом.

Правило дописывается к уже стоящему условию apply-unknown-keys-noindex в _отдать
(meta robots и X-Robots-Tag меняются вместе, только ужесточение, без 308):
* animego — индексируемы только каталог без условий и одиночный жанр/год/страна
  (то, что вид канонизирует на себя), с любым ?page; всё прочее на /catalog/ — noindex;
* animedia — запрос с sort — noindex (единичные фильтры там self-canonical).

    python3 automation/host/apply-selection-noindex.py --family animego|animedia [--check] <файл> […]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

МЕТКА = "def _выборка_без_страницы("
ЯКОРЬ_УСЛОВИЯ = '''            код == 200 and "text/html" in тип and _лишние_ключи_запроса(self.path or "/"))
'''
НОВОЕ_УСЛОВИЕ = '''            код == 200 and "text/html" in тип and (
                _лишние_ключи_запроса(self.path or "/") or _выборка_без_страницы(self.path or "/")))
'''
ЯКОРЬ_БЛОКА = "\ndef _закрытые_роботы(значение: str) -> str:\n"
ПРАВИЛА = {
    "animego": '''

def _выборка_без_страницы(путь: str) -> bool:
    """Выборка /catalog/, которую вид канонизирует не на себя, — noindex (§3 п.1–2).

    Своя страница — только каталог без условий и одиночный жанр, год или страна
    (ровно одно значение), с любым номером страницы. Диапазоны лет, серии, тип,
    статус, сортировка, вид отображения и сочетания — выборки каталога.
    """
    from urllib.parse import parse_qsl as _пары, urlsplit as _адрес
    адрес = _адрес(путь)
    if адрес.path.rstrip("/") != "/catalog":
        return False
    ключи = [к for к, _ in _пары(адрес.query, keep_blank_values=True) if к != "page"]
    if not ключи:
        return False
    return not (len(ключи) == 1 and ключи[0] in ("genre", "year", "country"))
''',
    "animedia": '''

def _выборка_без_страницы(путь: str) -> bool:
    """Сортировка — порядок той же выборки, не своя страница: noindex (§3 п.2)."""
    from urllib.parse import parse_qsl as _пары, urlsplit as _адрес
    return any(к == "sort" for к, _ in _пары(_адрес(путь).query, keep_blank_values=True))
''',
}


def привести(текст: str, семья: str) -> tuple[str, int]:
    if МЕТКА in текст:
        return текст, 0
    for якорь in (ЯКОРЬ_УСЛОВИЯ, ЯКОРЬ_БЛОКА):
        if текст.count(якорь) != 1:
            raise ValueError("нет правила лишних ключей (apply-unknown-keys-noindex) — ставить не к чему")
    текст = текст.replace(ЯКОРЬ_УСЛОВИЯ, НОВОЕ_УСЛОВИЕ)
    return текст.replace(ЯКОРЬ_БЛОКА, ПРАВИЛА[семья] + ЯКОРЬ_БЛОКА), 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--family", required=True, choices=sorted(ПРАВИЛА))
    ap.add_argument("--check", action="store_true")
    ap.add_argument("files", nargs="+")
    a = ap.parse_args(argv)
    код = 0
    for имя in a.files:
        путь = Path(имя)
        текст = путь.read_text(encoding="utf-8")
        try:
            новый, n = привести(текст, a.family)
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
        print(f"{имя}: приведён ({a.family})")
    return код


if __name__ == "__main__":
    sys.exit(main())
