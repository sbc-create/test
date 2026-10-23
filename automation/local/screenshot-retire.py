#!/usr/bin/env python3
"""Снятие снимков завершённой работы: сначала СОХРАНИТЬ вид, потом удалить.

Разрешение владельца на удаление подтверждённо ненужных снимков дано 23.10.
Здесь важнее другое его требование: «если важная информация существует только
на изображении, сначала сохрани и проверь её содержание; внешний вид страницы
одним текстом не заменяй».

Поэтому порядок такой и только такой:

1. по каждому файлу записывается опись: путь, байты, РАЗМЕР В ПИКСЕЛЯХ, время
   изменения, sha256 — это то, что текстом сохранить можно;
2. для каждого КАТАЛОГА сохраняется уменьшенный образец (ширина 320, WebP) —
   вид страницы остаётся виден, а не описан словами. Один образец на каталог,
   а не на файл: каталог прогона содержит один и тот же вид в разных
   разрешениях и темах, и образец показывает, что это было;
3. образец ПРОВЕРЯЕТСЯ обратным чтением: если он не открывается, файлы этого
   каталога НЕ удаляются;
4. только после этого удаляются исходники, по одному файлу.

Каталоги не удаляются. Группы «визуальный эталон», «сравнение до/после»,
«нужен проверке», «фикстура проверки», «текущий релиз», «откатная копия»,
«живая рабочая копия» в выборку не попадают по построению: инструмент работает
по колонке `группа` описи и берёт только названную ключом.

    python3 automation/local/screenshot-retire.py --census … --group "остаток завершённой работы" \
        --only /wt-x/ --thumbs var/retired-thumbs --manifest out.csv [--apply]

Коды: 0 — выполнено или план построен, 1 — нечего снимать, 2 — опись не читается.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import io
import os
import pathlib
import shutil
import sys
import time

ШИРИНА_ОБРАЗЦА = 320


def сумма(путь: str) -> str | None:
    х = hashlib.sha256()
    try:
        with open(путь, "rb") as ф:
            while True:
                к = ф.read(1 << 20)
                if not к:
                    break
                х.update(к)
    except OSError:
        return None
    return х.hexdigest()


def главное(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--census", required=True)
    р.add_argument("--group", required=True)
    р.add_argument("--only", action="append", default=[],
                   help="брать только пути, содержащие эту подстроку")
    р.add_argument("--thumbs", required=True)
    р.add_argument("--manifest", required=True)
    р.add_argument("--apply", action="store_true")
    а = р.parse_args(аргв)

    try:
        from PIL import Image
    except ImportError as сбой:
        print(f"НЕ ВЫПОЛНЕНО: {type(сбой).__name__}: {сбой}."
              " Без библиотеки нельзя сохранить вид, а удалять без этого"
              " запрещено условием владельца")
        return 2
    try:
        строки = list(csv.DictReader(open(а.census, encoding="utf-8")))
    except OSError as сбой:
        print(f"НЕ ВЫПОЛНЕНО: опись не прочитана: {сбой}")
        return 2

    отобрано = [с for с in строки if с.get("группа") == а.group
                and (not а.only or any(к in с["путь"] for к in а.only))]
    if not отобрано:
        print("НЕЧЕГО СНИМАТЬ: по этой группе и фильтру файлов нет")
        return 1

    по_каталогу: dict[str, list[dict]] = collections.defaultdict(list)
    for с in отобрано:
        по_каталогу[os.path.dirname(с["путь"])].append(с)

    образцы = pathlib.Path(а.thumbs)
    образцы.mkdir(parents=True, exist_ok=True)
    записи: list[dict] = []
    готовые_каталоги: set[str] = set()
    образцов = 0
    for каталог, файлы in sorted(по_каталогу.items()):
        самый = max(файлы, key=lambda з: int(з["байт"]))
        имя = (каталог.strip("/").replace("/", "__")
               + "__" + os.path.basename(самый["путь"]) + ".webp")
        цель = образцы / имя
        ладно = False
        почему = ""
        try:
            с_исходником = Image.open(самый["путь"])
            с_исходником.load()
            ш, в = с_исходником.size
            новая_в = max(1, round(в * ШИРИНА_ОБРАЗЦА / ш)) if ш else 1
            уменьшенный = с_исходником.convert("RGB").resize(
                (min(ш, ШИРИНА_ОБРАЗЦА), новая_в), Image.LANCZOS)
            буфер = io.BytesIO()
            уменьшенный.save(буфер, format="WEBP", quality=80, method=6)
            байты = буфер.getvalue()
            if а.apply:
                цель.write_bytes(байты)
                # проверка обратным чтением: образец должен открываться
                проба = Image.open(цель)
                проба.load()
            ладно = True
            образцов += 1
        except Exception as сбой:                    # noqa: BLE001
            почему = f"{type(сбой).__name__}: {сбой}"[:120]
        if ладно:
            готовые_каталоги.add(каталог)
        for с in файлы:
            записи.append({
                "путь": с["путь"], "байт": с["байт"],
                "каталог": каталог,
                "образец": имя if ладно else "",
                "образец_ок": "да" if ладно else f"НЕТ: {почему}",
                "исход": "ожидает" if ладно else "НЕ УДАЛЁН: нет образца",
            })

    # пиксели и суммы — по каждому файлу, это и есть сохранённое текстом
    for з in записи:
        з["sha256"] = сумма(з["путь"]) or ""
        try:
            ст = os.stat(з["путь"])
            з["изменён"] = time.strftime("%Y-%m-%dT%H:%MZ",
                                         time.gmtime(ст.st_mtime))
        except OSError:
            з["изменён"] = ""
        try:
            с_и = Image.open(з["путь"])
            з["пиксели"] = f"{с_и.size[0]}x{с_и.size[1]}"
            з["формат"] = (с_и.format or "").lower()
        except Exception:                            # noqa: BLE001
            з["пиксели"] = ""
            з["формат"] = ""

    место_до = shutil.disk_usage("/").free
    поля = ["путь", "байт", "пиксели", "формат", "изменён", "sha256",
            "каталог", "образец", "образец_ок", "исход"]

    удалено = байт_удалено = 0
    сбои = collections.Counter()
    if а.apply:
        for з in записи:
            if з["исход"] != "ожидает":
                continue
            try:
                размер = os.path.getsize(з["путь"])
                os.remove(з["путь"])
            except OSError as сбой:
                з["исход"] = f"НЕ УДАЛЁН: {type(сбой).__name__}"
                сбои[type(сбой).__name__] += 1
                continue
            з["исход"] = "удалён"
            удалено += 1
            байт_удалено += размер

    with open(а.manifest, "w", newline="", encoding="utf-8") as ф:
        з_ = csv.DictWriter(ф, fieldnames=поля)
        з_.writeheader()
        for з in записи:
            з_.writerow({к: з.get(к, "") for к in поля})

    место_после = shutil.disk_usage("/").free
    print(f"отобрано файлов: {len(записи)} в {len(по_каталогу)} каталогах")
    print(f"образцов сохранено: {образцов} из {len(по_каталогу)} каталогов")
    без_образца = len([з for з in записи if not з["образец"]])
    if без_образца:
        print(f"файлов БЕЗ образца (не удаляются): {без_образца}")
    if а.apply:
        print(f"УДАЛЕНО: {удалено} файлов, {байт_удалено/2**20:.1f} МиБ")
        if сбои:
            print("сбои:", dict(сбои))
        print(f"свободно до {место_до/2**30:.2f} ГиБ,"
              f" после {место_после/2**30:.2f} ГиБ")
        образцы_вес = sum(ф.stat().st_size for ф in образцы.iterdir()
                          if ф.is_file())
        print(f"образцы заняли: {образцы_вес/2**20:.1f} МиБ в {образцы}")
    else:
        print("план построен, НИЧЕГО НЕ УДАЛЕНО и образцы НЕ записаны"
              " (нет --apply)")
    print(f"опись: {а.manifest}")
    return 0


if __name__ == "__main__":
    sys.exit(главное())
