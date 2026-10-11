#!/usr/bin/env python3
"""Путевые фасеты /year/ и /country/ разбирают номер страницы через _page_gate. Перенос по якорям.

REQ-SEO-PAGINATION п.8: недопустимый номер страницы — 400/404, а не первая
страница или пустой шаблон с 200. В репозиториях с исходником ядра правка внесена
коммитами (zonafilm.space, zonafilm12.site); инструмент — для витрин, где ядро
закреплено артефактом шаблона (zona-02), как apply-meta-description.py.

Нет якоря, нет правки или нет _page_gate в файле — отказ ДО записи. Повтор
ничего не меняет. `--check` — «приведён ли файл».

    python3 automation/host/apply-facet-page-gate.py [--check] <файл> [<файл>…]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

МЕТКА = "# Номер страницы путевого фасета — через _page_gate (apply-facet-page-gate)."
ЯКОРЯ = tuple(
    (f'''            зпр = dict(зпр)
            зпр["{ключ}"] = [{знач}]
            return self._отдать(в.список("/catalog", зпр).encode("utf-8"))''',
     f'''            зпр = dict(зпр)
            зпр["{ключ}"] = [{знач}]
            {МЕТКА}
            if self._page_gate(в, путь, "/catalog", зпр, None):
                return None
            return self._отдать(в.список("/catalog", зпр).encode("utf-8"))''')
    for ключ, знач in (("year", 'год.group("year")'), ("country", "код")))


def привести(текст: str) -> tuple[str, int]:
    if МЕТКА in текст:
        return текст, 0
    if "def _page_gate(" not in текст:
        raise ValueError("в файле нет _page_gate — разбирать номер нечем")
    n = 0
    for было, стало in ЯКОРЯ:
        if текст.count(было) != 1:
            raise ValueError("якорь маршрута фасета найден не ровно один раз")
        текст = текст.replace(было, стало)
        n += 1
    return текст, n


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
        print(f"{имя}: маршрутов приведено {n}")
    return код


if __name__ == "__main__":
    sys.exit(main())
