#!/usr/bin/env python3
"""Неизвестный или повторённый ключ запроса — noindex, follow. Перенос по якорям.

knowledge/SEO_KNOWLEDGE_PACK.md §3 п.3: «порядок параметров нормализуется;
повторяющиеся и неизвестные ключи запрещены — это предотвращает комбинаторный
взрыв URL»; п.2: tracking-параметры не индексируются. Замер Архитектора 12.10:
?nosuchkey=1 и ?genre=a&genre=b у всех двенадцати витрин — 200, index, полный
каталог; любое имя ключа давало новый индексируемый адрес.

Почему noindex, а не 308: перечень ключей семейства собран из кода поиском
(зпр.get(...)); пропусти он функциональный ключ (плеер, сообщество), перенаправление
сломало бы функцию, а noindex — нет. Метки трафика (utm_*, yclid, gclid…) тоже
получают noindex, но остаются 200 без перенаправления — атрибуция не теряется.

Правка: в `_отдать` до отправки — если в запросе есть ключ вне перечня семейства
или ключ повторён, а ответ 200 и HTML: meta robots в теле ужесточается до noindex
(или добавляется), заголовок X-Robots-Tag ужесточается переопределённым
send_header. Ослабить нельзя: значение с noindex не трогается.

    python3 automation/host/apply-unknown-keys-noindex.py --family lords|zona|animego|animedia [--check] <файл> […]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

КЛЮЧИ = {
    "lords": ("country", "genre", "kind", "page", "q", "sort", "year", "community", "from", "why"),
    "zona": ("country", "genre", "kind", "page", "q", "sort", "year", "mode", "community", "from", "why"),
    "animego": ("by", "community", "country", "eps", "exclude", "genre", "kind", "mine", "ongoing",
                "page", "q", "rating", "sort", "type", "view", "why", "year", "from"),
    "animedia": ("as", "by", "community", "country", "eps", "exclude", "genre", "kind", "mine", "ongoing",
                 "page", "q", "rating", "sort", "type", "why", "year", "from"),
}
МЕТКА = "def _лишние_ключи_запроса("
ЯКОРЬ_ОТДАЧИ = '''        self.send_response(код)
        self.send_header("Content-Type", тип)
        self.send_header("Content-Length", str(len(тело)))
'''
ВСТАВКА_ОТДАЧИ = '''        # Неизвестный или повторённый ключ запроса — noindex (SEO_KNOWLEDGE_PACK
        # §3 п.2–3; apply-unknown-keys-noindex). Только ужесточение.
        self._закрыть_индекс = bool(
            код == 200 and "text/html" in тип and _лишние_ключи_запроса(self.path or "/"))
        if self._закрыть_индекс:
            тело = _закрыть_индекс_в_теле(тело)
''' + ЯКОРЬ_ОТДАЧИ
ЯКОРЬ_КЛАССА = "    def _отдать(self, тело: bytes, тип=\"text/html; charset=utf-8\", код=200):\n"
МЕТОД = '''    def send_header(self, keyword, value):
        # Ужесточение X-Robots-Tag для адресов с лишними ключами (см. _отдать).
        if (str(keyword).lower() == "x-robots-tag" and getattr(self, "_закрыть_индекс", False)
                and "noindex" not in str(value).lower()):
            value = _закрытые_роботы(str(value))
        return super().send_header(keyword, value)

''' + ЯКОРЬ_КЛАССА


def функции(ключи: tuple[str, ...]) -> str:
    return f'''

#: Ключи запроса, которые витрина читает (собрано из кода; apply-unknown-keys-noindex).
_ИЗВЕСТНЫЕ_КЛЮЧИ_ЗАПРОСА = frozenset({sorted(ключи)!r})


{МЕТКА}путь: str) -> list[str]:
    """Ключи вне перечня витрины и повторённые ключи — причина noindex."""
    from urllib.parse import parse_qsl as _пары, urlsplit as _адрес
    ключи = [к for к, _ in _пары(_адрес(путь).query, keep_blank_values=True)]
    лишние = sorted({{к for к in ключи if к not in _ИЗВЕСТНЫЕ_КЛЮЧИ_ЗАПРОСА}})
    повторы = sorted({{к for к in ключи if ключи.count(к) > 1}})
    return лишние + [f"{{к}} (повтор)" for к in повторы]


def _закрытые_роботы(значение: str) -> str:
    return "noindex, nofollow" if "nofollow" in значение.lower() else "noindex, follow"


def _закрыть_индекс_в_теле(тело: bytes) -> bytes:
    import re as _re
    try:
        текст = тело.decode("utf-8")
    except UnicodeDecodeError:
        return тело
    найдено = _re.search(r'<meta name="robots" content="([^"]*)"\\s*/?>', текст)
    if найдено:
        if "noindex" in найдено.group(1).lower():
            return тело
        новое = f'<meta name="robots" content="{{_закрытые_роботы(найдено.group(1))}}">'
        return (текст[:найдено.start()] + новое + текст[найдено.end():]).encode("utf-8")
    if "</head>" in текст:
        return текст.replace("</head>", '<meta name="robots" content="noindex, follow"></head>', 1).encode("utf-8")
    return тело
'''


def привести(текст: str, семья: str) -> tuple[str, int]:
    if МЕТКА in текст:
        return текст, 0
    for якорь in (ЯКОРЬ_ОТДАЧИ, ЯКОРЬ_КЛАССА):
        if текст.count(якорь) != 1:
            raise ValueError(f"якорь найден не ровно один раз: {якорь.strip()[:60]}")
    if "class Обработчик(BaseHTTPRequestHandler)" not in текст:
        raise ValueError("обработчик не наследует BaseHTTPRequestHandler — super().send_header не годится")
    текст = текст.replace(ЯКОРЬ_ОТДАЧИ, ВСТАВКА_ОТДАЧИ).replace(ЯКОРЬ_КЛАССА, МЕТОД)
    позиция = текст.index("\nclass Обработчик(BaseHTTPRequestHandler)")
    текст = текст[:позиция] + функции(КЛЮЧИ[семья]) + текст[позиция:]
    return текст, 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--family", required=True, choices=sorted(КЛЮЧИ))
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
