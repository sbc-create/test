#!/usr/bin/env python3
"""«Похожие» Lords: признаки соседей — один раз на снимок (T030). Перенос по якорям.

Профиль 13.10: холодная страница тайтла почти целиком — `похожие_с_мета`:
на каждый тайтл проход по всему каталогу, и у КАЖДОЙ записи заново строятся
множества жанров и стран (страны — через транслит и нормализацию). Признаки
соседа от текущего тайтла не зависят, поэтому считаются один раз на снимок
(отпечаток данных и подробностей; срок 30 мин — подробности обновляются и на
месте). Баллы, причины, сортировка и добор — дословно прежние: меняется только
заголовок цикла. Равенство — checks/similar_features.py ячейки (исходный цикл
против нового на выборке тайтлов реального снимка).

Якоря: заголовок цикла `for сосед in self.д.items:` с построением
`чужие_жанры`/`чужие_страны` (ровно один) и `def запрос_строкой(` (перед ним —
функция признаков). Нет якоря — отказ ДО записи. Повторный запуск ничего не
меняет.

    python3 automation/host/apply-similar-features.py [--check] <файл> [<файл>…]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

МЕТКА = "#: Признаки соседей для похожих — один раз на снимок (apply-similar-features)"
ЦИКЛ = '''        for сосед in self.д.items:
            slug = сосед.get("slug")
            if not slug or slug == текущий:
                continue
            д = self.п.get(slug) if self.п else {}
            чужие_жанры = set(д.get("genre_codes") or [])
            if not чужие_жанры and д.get("genres"):
                чужие_жанры = {нормализовать(транслит(г)) for г in д["genres"] if г}
                чужие_жанры.discard("")
            чужие_страны = {нормализовать(транслит(с)) for с in (д.get("countries") or []) if с}
            чужие_страны.discard("")
'''
НОВЫЙ_ЦИКЛ = '''        for slug, чужие_жанры, чужие_страны, сосед in _признаки_соседей(self):
            if slug == текущий:
                continue
'''
ЯКОРЬ_ФУНКЦИИ = "def запрос_строкой("
ФУНКЦИЯ = МЕТКА + '''
_ПРИЗНАКИ_СОСЕДЕЙ: dict = {}


def _признаки_соседей(вид) -> list:
    """(slug, жанры, страны, запись) в порядке каталога — как строил прежний цикл."""
    import time
    ключ = tuple((id(о), getattr(о, "mtime", None), getattr(о, "revision", None))
                 for о in (вид.д, вид.п))
    сейчас = time.monotonic()
    готово = _ПРИЗНАКИ_СОСЕДЕЙ.get(ключ)
    if готово is not None and сейчас - готово[0] < 1800.0:
        return готово[1]
    признаки = []
    for сосед in вид.д.items:
        slug = сосед.get("slug")
        if not slug:
            continue
        д = вид.п.get(slug) if вид.п else {}
        чужие_жанры = set(д.get("genre_codes") or [])
        if not чужие_жанры and д.get("genres"):
            чужие_жанры = {нормализовать(транслит(г)) for г in д["genres"] if г}
            чужие_жанры.discard("")
        чужие_страны = {нормализовать(транслит(с)) for с in (д.get("countries") or []) if с}
        чужие_страны.discard("")
        признаки.append((slug, frozenset(чужие_жанры), frozenset(чужие_страны), сосед))
    _ПРИЗНАКИ_СОСЕДЕЙ.clear()
    _ПРИЗНАКИ_СОСЕДЕЙ[ключ] = (сейчас, признаки)
    return признаки


'''


def привести(текст: str) -> tuple[str, int]:
    if МЕТКА in текст:
        return текст, 0
    if текст.count(ЦИКЛ) != 1:
        raise SystemExit(f"заголовок цикла похожих найден {текст.count(ЦИКЛ)} раз(а), ожидался 1 — файл не тронут")
    if текст.count(ЯКОРЬ_ФУНКЦИИ) != 1:
        raise SystemExit(f"«{ЯКОРЬ_ФУНКЦИИ}» найден {текст.count(ЯКОРЬ_ФУНКЦИИ)} раз(а) — файл не тронут")
    текст = текст.replace(ЦИКЛ, НОВЫЙ_ЦИКЛ).replace(ЯКОРЬ_ФУНКЦИИ, ФУНКЦИЯ + ЯКОРЬ_ФУНКЦИИ, 1)
    return текст, 1


def main() -> int:
    п = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    п.add_argument("--check", action="store_true")
    п.add_argument("файлы", nargs="+")
    а = п.parse_args()
    плохо = 0
    for имя in а.файлы:
        путь = Path(имя)
        текст = путь.read_text(encoding="utf-8")
        if а.check:
            ок = МЕТКА in текст
            print(f"{имя}: {'приведён' if ок else 'НЕ приведён'}")
            плохо += 0 if ок else 1
            continue
        новый, n = привести(текст)
        if n:
            путь.write_text(новый, encoding="utf-8")
        print(f"{имя}: {'приведён' if n else 'уже приведён'}")
    return 1 if плохо else 0


if __name__ == "__main__":
    sys.exit(main())
