#!/usr/bin/env python3
"""H1 страницы выдачи N>1 несёт номер страницы — в общем SEO-слое. Перенос по якорям.

REQ-SEO-PAGINATION п.7 (knowledge/SEO_KNOWLEDGE_PACK.md §2): для page 2+ —
утверждённый шаблон title/H1/description с номером страницы. Замер Архитектора
11.10: title и description номер несут у всех двенадцати витрин, H1 — ни у одной
(«Каталог» на первой и второй странице). H1 рисуют десятки мест вида в пяти
семействах; общий слой `seo_layer.обогатить` видит каждый ответ, поэтому правило
ставится в нём одно: на ответе 200, чей <title> уже несёт «страница N» (то есть
страница сама объявила себя N-й по утверждённому шаблону), к первому <h1>
добавляется « — страница N», если номера там ещё нет. Других страниц правка не
касается: нет номера в title — нет изменения.

Нет якоря или он не единственный — отказ ДО записи. Повтор ничего не меняет.
`--check` — «приведён ли файл».

    python3 automation/host/apply-h1-page-number.py [--check] <seo_layer.py> […]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

МЕТКА = "def номер_в_h1("
ЯКОРЬ = '''    if not вставка:
        return тело
    return тело.replace(b"</head>", вставка.encode("utf-8") + b"</head>", 1)
'''
ЗАМЕНА = '''    if код == 200:
        тело = номер_в_h1(тело, путь)
    if not вставка:
        return тело
    return тело.replace(b"</head>", вставка.encode("utf-8") + b"</head>", 1)


def номер_в_h1(тело: bytes, путь: str) -> bytes:
    """Номер страницы N>1 в первом <h1> (REQ-SEO-PAGINATION п.7).

    Ставится только там, где страница уже объявила себя N-й в <title> по
    утверждённому шаблону «— страница N»: так H1 следует решению вида, а не
    угадывает его по адресу. Номер уже есть в H1 — ничего не меняется.
    """
    import re as _re
    from urllib.parse import parse_qs as _разобрать, urlsplit as _адрес

    сырой = (_разобрать(_адрес(путь or "/").query).get("page") or [""])[0].strip()
    if not сырой.isdigit() or int(сырой) < 2:
        return тело
    try:
        текст = тело.decode("utf-8")
    except UnicodeDecodeError:
        return тело
    метка = f"страница {int(сырой)}"
    титул = _re.search(r"<title[^>]*>(.*?)</title>", текст, _re.S | _re.I)
    if not титул or метка not in титул.group(1):
        return тело
    заголовок = _re.search(r"(<h1\\b[^>]*>)(.*?)(</h1>)", текст, _re.S | _re.I)
    if not заголовок or "страница" in _re.sub(r"<[^>]+>", " ", заголовок.group(2)):
        return тело
    return (текст[:заголовок.end(2)] + f" — {метка}" + текст[заголовок.end(2):]).encode("utf-8")
'''


def привести(текст: str) -> tuple[str, int]:
    if МЕТКА in текст:
        return текст, 0
    if текст.count(ЯКОРЬ) != 1:
        raise ValueError("якорь конца обогатить() найден не ровно один раз")
    return текст.replace(ЯКОРЬ, ЗАМЕНА), 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
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
        print(f"{имя}: мест приведено {n}")
    return код


if __name__ == "__main__":
    sys.exit(main())
