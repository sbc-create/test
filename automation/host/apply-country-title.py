#!/usr/bin/env python3
"""Zona: выборка со страной называет страну в title, H1 и description. Перенос по якорям.

Аудит страниц 12.10: /country/<код>/ и /catalog/?country=<код> у трёх Zona —
индексируемые страницы с self-canonical (/catalog/?country=<код>) и своим
составом — носили title «Каталог — Zona», H1 «Каталог» и description «Каталог на
Zona.» одинаково для КАЖДОЙ страны: дубль заголовков на разных выдачах, H1 не
отражает содержимое. Страна бралась в отбор, но не в заголовок.

Правка: после вычисления заголовка раздела (год/жанр/вид) к нему добавляется
название страны из индекса витрины (country_names) — «Каталог: США», «Драма:
Япония», «Сериалы 2024 года: Корея». Описание и title строятся из того же
заголовка и меняются вместе. Других выборок правка не касается.

Нет якоря или он не единственный — отказ ДО записи. Повтор ничего не меняет.

    python3 automation/host/apply-country-title.py [--check] <lords-frontend.py> […]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

МЕТКА = "# Страна выборки — в заголовке (apply-country-title)."
ЯКОРЬ = '''        elif жанр_имя:
            титул = жанр_имя.capitalize() if жанр_имя[:1].islower() else жанр_имя

        kind_route = разд in ВИД_ПО_МАРШРУТУ or разд in КАТЕГОРИЯ_ПО_МАРШРУТУ
'''
ЗАМЕНА = '''        elif жанр_имя:
            титул = жанр_имя.capitalize() if жанр_имя[:1].islower() else жанр_имя
        ''' + МЕТКА + '''
        # Прежде у каждой страны были title «Каталог — …» и H1 «Каталог»: дубль
        # заголовков на разных выдачах (аудит страниц 12.10).
        страна_код = выбрано.get("country")
        if страна_код:
            страна_имя = dict(self.индекс.get("country_names") or []).get(страна_код)
            if страна_имя:
                титул = f"{титул}: {страна_имя}"

        kind_route = разд in ВИД_ПО_МАРШРУТУ or разд in КАТЕГОРИЯ_ПО_МАРШРУТУ
'''


def привести(текст: str) -> tuple[str, int]:
    if МЕТКА in текст:
        return текст, 0
    if текст.count(ЯКОРЬ) != 1:
        raise ValueError("якорь заголовка раздела найден не ровно один раз")
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
        print(f"{имя}: приведён")
    return код


if __name__ == "__main__":
    sys.exit(main())
