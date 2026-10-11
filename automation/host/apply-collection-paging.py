#!/usr/bin/env python3
"""Коллекции Zona: self-canonical страницы N>1 и разбор номера страницы. Перенос по якорям.

REQ-SEO-PAGINATION п.2, п.3, п.8 (приёмка Архитектора 11.10): /collection/<ключ>/?page=2
объявлял канонической первую страницу, ?page=1 не перенаправлялся, abc/0 отдавали копию
первой страницы, 9999 — пустой шаблон с 200. В репозиториях с исходником ядра правка
внесена коммитами (zonafilm.space 21a3d2e, zonafilm12.site 2d565ba); инструмент — для
витрин, где ядро закреплено артефактом шаблона (zona-02), как apply-facet-page-gate.py.

Нет якоря или он не единственный — отказ ДО записи. Повтор ничего не меняет.
`--check` — «приведён ли файл».

    python3 automation/host/apply-collection-paging.py [--check] <файл> [<файл>…]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

МЕТКА = "# Номер страницы коллекции разбирается (apply-collection-paging)."
ВИД_БЫЛО = '''        return self.оболочка(тело, f"{данные.title} — {self.имя}",
                             данные.canonical_path, актив="/collections/",
                             описание=данные.description,
'''
ВИД_СТАЛО = '''        # Страница N>1 коллекции — self-canonical и номер в заголовке (п.3).
        хвост = f" — страница {данные.page}" if данные.page > 1 else ""
        return self.оболочка(тело, f"{данные.title}{хвост} — {self.имя}",
                             данные.canonical_path + (f"?page={данные.page}" if данные.page > 1 else ""),
                             актив="/collections/",
                             описание=(данные.description or "") + хвост,
'''
МАРШРУТ_БЫЛО = '''        try:
            страница = max(1, int((зпр.get("page") or ["1"])[0] or 1))
        except (TypeError, ValueError):
            страница = 1
        данные = КОЛЛЕКЦИИ.разрешить(ключ, снимок, СЕМЕЙСТВО, страница=страница)
        if данные is None:
'''
МАРШРУТ_СТАЛО = f'''        {МЕТКА}
        # REQ-SEO-PAGINATION п.2, п.8: ?page=1 → 308 без номера, 0/abc → 400
        # (как в каталоге Zona), за пределом → 404.
        сырой = str((зпр.get("page") or [""])[0] or "").strip()
        if сырой == "1":
            пары = {{к: (зн or [""])[0] for к, зн in зпр.items()
                    if к != "page" and not к.startswith("_")}}
            return self._переход(путь + (запрос_строкой(пары) if пары else ""))
        if сырой and (not сырой.isdigit() or int(сырой) < 1):
            return self._отдать(в.не_найдено(путь).encode("utf-8"), код=400)
        страница = int(сырой) if сырой else 1
        данные = КОЛЛЕКЦИИ.разрешить(ключ, снимок, СЕМЕЙСТВО, страница=страница)
        if данные is None or (страница > 1 and not данные.items):
'''


def привести(текст: str) -> tuple[str, int]:
    if МЕТКА in текст:
        return текст, 0
    if "def запрос_строкой(" not in текст:
        raise ValueError("в файле нет запрос_строкой — собрать адрес перехода нечем")
    n = 0
    for было, стало in ((ВИД_БЫЛО, ВИД_СТАЛО), (МАРШРУТ_БЫЛО, МАРШРУТ_СТАЛО)):
        if текст.count(было) != 1:
            raise ValueError("якорь коллекции найден не ровно один раз")
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
        print(f"{имя}: мест приведено {n}")
    return код


if __name__ == "__main__":
    sys.exit(main())
