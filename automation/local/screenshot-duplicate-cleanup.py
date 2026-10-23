#!/usr/bin/env python3
"""Удаление ПОДТВЕРЖДЁННЫХ дублей снимков приёмки. По одному файлу, с описью.

Разрешение владельца на удаление дано 23.10. Инструмент написан так, чтобы это
разрешение нельзя было применить шире, чем оно дано.

ЧТО УДАЛЯЕТСЯ ТОЛЬКО ПРИ ВЫПОЛНЕНИИ ВСЕХ УСЛОВИЙ:

1. файл помечен в описи как ЛИШНЯЯ копия (`image-duplicate-census.py`);
2. это СНИМОК ПРИЁМКИ: путь содержит `artifacts/evidence`, `report`, `shots`
   или `evidence`, и расширение — изображение. Постеры, данные витрин,
   оформление и резервные копии в выборку не попадают по построению;
3. файл лежит либо в ПРЕЖНЕМ каталоге релиза (текущий, кандидат, `previous` и
   два свежайших исключены: правило «предыдущий рабочий релиз сохраняется»),
   либо в рабочей копии сессии, которой не касались;
4. рабочая копия НЕ активна: исключаются свежие и копии работающих линий;
5. сам файл не менялся больше 7 суток;
6. на путь не ссылается ни один отчёт (проверено по документам);
7. **суммы сверены ЗАНОВО в момент удаления**: sha256 удаляемого совпадает с
   sha256 сохраняемой копии, и сохраняемая копия существует и читается.

Если седьмое условие не выполняется — файл НЕ удаляется, и причина попадает в
опись. Опись «удалённый путь → сохранённая копия» пишется ДО удаления и
остаётся артефактом: без неё удаление необратимо и непроверяемо.

Каталоги не удаляются никогда — только отдельные файлы.

    python3 automation/local/screenshot-duplicate-cleanup.py --census … --plan out.csv
    python3 automation/local/screenshot-duplicate-cleanup.py --census … --plan out.csv --apply

Коды: 0 — выполнено (или план построен), 1 — ни одного файла не отобрано,
2 — опись не прочитана.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import os
import pathlib
import shutil
import sys
import time

РАСШИРЕНИЯ = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif")
ПРИЗНАК_СНИМКА = ("/artifacts/evidence/", "/report/", "/reports/", "/shots/",
                  "/evidence/")
#: Рабочие копии, которые не трогаются ни при каких условиях: активные линии.
#: `wt-portable-site-cell-01` — копия соседней линии, которая работает прямо
#: сейчас (выпускает T328–T330); её старый `.git` об этом не говорит, поэтому
#: исключение задано по имени, а не по времени.
АКТИВНЫЕ_КОПИИ = ("wt-nova-publish-memory-02", "wt-portable-site-cell-01",
                  "wt-lastmod")
ВОЗРАСТ_СУТОК = 7


def сумма(путь: str) -> str | None:
    х = hashlib.sha256()
    try:
        with open(путь, "rb") as ф:
            while True:
                кусок = ф.read(1 << 20)
                if not кусок:
                    break
                х.update(кусок)
    except OSError:
        return None
    return х.hexdigest()


def защищённые_релизы(пути: list[str]) -> dict[str, set[str]]:
    """корень сайта → релизы, которые нельзя трогать."""
    сайты: dict[str, set[str]] = collections.defaultdict(set)
    for п in пути:
        if "/releases/" not in п:
            continue
        корень, остаток = п.split("/releases/", 1)
        сайты[корень].add(остаток.split("/", 1)[0])
    итог: dict[str, set[str]] = {}
    for корень, релизы in сайты.items():
        щит = set()
        for имя in ("current", "candidate", "previous", "last-good"):
            цель = os.path.realpath(os.path.join(корень, имя))
            if "/releases/" in цель:
                щит.add(цель.split("/releases/", 1)[1].split("/", 1)[0])
        времена = []
        for р in релизы:
            try:
                времена.append((os.path.getmtime(
                    os.path.join(корень, "releases", р)), р))
            except OSError:
                continue
        времена.sort(reverse=True)
        щит.update(р for _, р in времена[:2])
        итог[корень] = щит
    return итог


def снимок_приёмки(путь: str) -> bool:
    return (путь.lower().endswith(РАСШИРЕНИЯ)
            and any(п in путь for п in ПРИЗНАК_СНИМКА))


def активная_копия(путь: str) -> bool:
    return any(f"/{и}/" in путь or путь.endswith(f"/{и}")
               for и in АКТИВНЫЕ_КОПИИ)


def доработать(опись: str, применять: bool) -> int:
    """Только строки «НЕ УДАЛЁН» из готовой описи, со сверкой сумм заново.

    Для владельца: план уже проверен, пересобирать его не нужно, а доверять
    ему на слово нельзя — поэтому суммы считаются ещё раз, у удаляемого и у
    сохраняемого, и расхождение останавливает файл, а не прогон.
    """
    try:
        строки = list(csv.DictReader(open(опись, encoding="utf-8")))
    except OSError as сбой:
        print(f"НЕ ВЫПОЛНЕНО: опись не прочитана: {сбой}")
        return 2
    осталось = [с for с in строки if с.get("исход", "") != "удалён"]
    print(f"в описи {len(строки)}, к доработке {len(осталось)}")
    место_до = shutil.disk_usage("/").free
    удалено = байт = 0
    пропуски = collections.Counter()
    for с in осталось:
        путь, хранитель = с["удалить"], с["сохранить"]
        if not os.path.isfile(путь):
            с["исход"] = "уже отсутствует"
            пропуски["уже отсутствует"] += 1
            continue
        if not os.path.isfile(хранитель):
            с["исход"] = "НЕ УДАЛЁН: сохраняемой копии нет"
            пропуски["сохраняемой копии нет"] += 1
            continue
        моя, его = сумма(путь), сумма(хранитель)
        if not моя or not его or моя != его or моя != с["sha256"]:
            с["исход"] = "НЕ УДАЛЁН: суммы не сошлись при повторной сверке"
            пропуски["суммы не сошлись"] += 1
            continue
        if not применять:
            с["исход"] = "готов к удалению (суммы сверены)"
            continue
        try:
            размер = os.path.getsize(путь)
            os.remove(путь)
        except OSError as сбой:
            с["исход"] = f"НЕ УДАЛЁН: {type(сбой).__name__}: {сбой}"
            пропуски[type(сбой).__name__] += 1
            continue
        с["исход"] = "удалён"
        удалено += 1
        байт += размер
    with open(опись, "w", newline="", encoding="utf-8") as ф:
        з = csv.DictWriter(ф, fieldnames=["удалить", "сохранить", "sha256",
                                          "байт", "исход"])
        з.writeheader()
        for с in строки:
            з.writerow({к: с.get(к, "") for к in з.fieldnames})
    место_после = shutil.disk_usage("/").free
    if применять:
        print(f"УДАЛЕНО: {удалено} файлов, {байт/2**30:.2f} ГиБ")
        print(f"свободно до {место_до/2**30:.2f} ГиБ,"
              f" после {место_после/2**30:.2f} ГиБ")
    else:
        готовы = len([с for с in осталось
                      if с["исход"].startswith("готов")])
        print(f"суммы сверены, готовы к удалению: {готовы};"
              f" НИЧЕГО НЕ УДАЛЕНО (нет --apply)")
    if пропуски:
        print("не удалены:", dict(пропуски))
    print(f"опись обновлена: {опись}")
    return 0


def главное(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--census", default="",
                   help="опись дублей; не нужна в режиме"
                        " --retry-from-manifest")
    р.add_argument("--plan", required=True)
    р.add_argument("--apply", action="store_true")
    р.add_argument("--retry-from-manifest", action="store_true",
                   help="доработать по готовой описи только строки"
                        " «НЕ УДАЛЁН», сверив суммы заново")
    а = р.parse_args(аргв)

    if а.retry_from_manifest:
        return доработать(а.plan, а.apply)
    if not а.census:
        print("НЕ ВЫПОЛНЕНО: нужен --census либо --retry-from-manifest")
        return 2

    try:
        строки = list(csv.DictReader(open(а.census, encoding="utf-8")))
    except OSError as сбой:
        print(f"НЕ ВЫПОЛНЕНО: опись не прочитана: {сбой}")
        return 2

    хранители: dict[str, list[str]] = collections.defaultdict(list)
    лишние: dict[str, list[str]] = collections.defaultdict(list)
    for с in строки:
        (лишние if с["копия"] == "лишняя" else хранители)[с["сумма"]].append(
            с["путь"])

    все_пути = [с["путь"] for с in строки]
    щиты = защищённые_релизы(все_пути)
    порог = time.time() - ВОЗРАСТ_СУТОК * 86400

    отобрано: list[dict] = []
    отказы = collections.Counter()
    for ключ, пути in лишние.items():
        for путь in пути:
            if not снимок_приёмки(путь):
                отказы["не снимок приёмки"] += 1
                continue
            if активная_копия(путь):
                отказы["рабочая копия активной линии"] += 1
                continue
            if "/releases/" in путь:
                корень, остаток = путь.split("/releases/", 1)
                релиз = остаток.split("/", 1)[0]
                if релиз in щиты.get(корень, set()):
                    отказы["текущий, кандидат или свежий релиз"] += 1
                    continue
            try:
                if os.path.getmtime(путь) > порог:
                    отказы["файл менялся за 7 суток"] += 1
                    continue
            except OSError:
                отказы["файл исчез до проверки"] += 1
                continue
            отобрано.append({"сумма_описи": ключ, "путь": путь})

    if not отобрано:
        print("НЕ ВЫПОЛНЕНО: ни один файл не прошёл условия")
        return 1

    # --- сверка сумм ЗАНОВО, перед записью плана --------------------------
    план: list[dict] = []
    пропуски = collections.Counter()
    кеш_хранителей: dict[str, tuple[str, str] | None] = {}
    for запись in отобрано:
        путь = запись["путь"]
        моя = сумма(путь)
        if not моя:
            пропуски["удаляемый не прочитан"] += 1
            continue
        ключ = запись["сумма_описи"]
        if ключ not in кеш_хранителей:
            найден = None
            for к in хранители.get(ключ, []):
                если = сумма(к)
                if если and если == моя:
                    найден = (к, если)
                    break
            кеш_хранителей[ключ] = найден
        хранитель = кеш_хранителей[ключ]
        if not хранитель:
            пропуски["сохраняемая копия не найдена или сумма не сошлась"] += 1
            continue
        if хранитель[1] != моя:
            пропуски["суммы разошлись при повторной сверке"] += 1
            continue
        план.append({"удалить": путь, "sha256": моя,
                     "сохранить": хранитель[0],
                     "байт": os.path.getsize(путь)})

    место_до = shutil.disk_usage("/").free
    with open(а.plan, "w", newline="", encoding="utf-8") as ф:
        з = csv.DictWriter(ф, fieldnames=["удалить", "сохранить", "sha256",
                                          "байт", "исход"])
        з.writeheader()
        for с in план:
            з.writerow({**с, "исход": "запланировано"})

    print(f"кандидатов в описи: {sum(len(п) for п in лишние.values())}")
    print("отсеяно условиями:")
    for причина, n in отказы.most_common():
        print(f"   {n:7}  {причина}")
    print(f"прошло условия: {len(отобрано)}")
    print("не прошло сверку сумм:" if пропуски else "сверку сумм прошли все")
    for причина, n in пропуски.most_common():
        print(f"   {n:7}  {причина}")
    print(f"\nК УДАЛЕНИЮ: {len(план)} файлов,"
          f" {sum(с['байт'] for с in план)/2**30:.2f} ГиБ")
    print(f"свободно до: {место_до/2**30:.2f} ГиБ")
    print(f"опись плана: {а.plan}")

    if not а.apply:
        print("\nплан построен, НИЧЕГО НЕ УДАЛЕНО (нет --apply)")
        return 0

    удалено = 0
    байт = 0
    сбои = collections.Counter()
    for с in план:
        try:
            os.remove(с["удалить"])
        except OSError as сбой:
            сбои[type(сбой).__name__] += 1
            с["исход"] = f"НЕ УДАЛЁН: {type(сбой).__name__}: {сбой}"
            continue
        с["исход"] = "удалён"
        удалено += 1
        байт += с["байт"]

    with open(а.plan, "w", newline="", encoding="utf-8") as ф:
        з = csv.DictWriter(ф, fieldnames=["удалить", "сохранить", "sha256",
                                          "байт", "исход"])
        з.writeheader()
        for с in план:
            з.writerow(с)

    место_после = shutil.disk_usage("/").free
    print(f"\nУДАЛЕНО: {удалено} файлов, {байт/2**30:.2f} ГиБ")
    if сбои:
        print("сбои удаления:", dict(сбои))
    print(f"свободно до:    {место_до/2**30:.2f} ГиБ")
    print(f"свободно после: {место_после/2**30:.2f} ГиБ"
          f" (прирост {(место_после - место_до)/2**30:+.2f} ГиБ)")
    print(f"опись с исходами: {а.plan}")
    return 0


if __name__ == "__main__":
    sys.exit(главное())
