#!/usr/bin/env python3
"""Не накопились ли снимки приёмки снова. Только чтение.

Зачем проверка, а не памятка. 23.10 на хосте нашлось 25 579 изображений на
10,01 ГиБ, из них 84 % — одни и те же снимки приёмки, размноженные по каждому
каталогу релиза и каждой рабочей копии. Из-за места встала суточная публикация
каталогов (MOD-144). Памятка «не копите снимки» это не предотвратит: копит не
человек, а сборка, которая кладёт снимки внутрь релиза, и прогон, который
оставляет их в рабочей копии. Поэтому правило задано ПОРОГАМИ и проверяется.

ПРАВИЛО ХРАНЕНИЯ, которое проверка закрепляет:

1. СНИМКИ НЕ ЛЕЖАТ ВНУТРИ РЕЛИЗА. Релиз отдаёт витрина, релизов копится
   десятки, и каждый несёт свою копию отчёта. Предел: не больше
   `--per-release` изображений в каталоге одного релиза.
2. СНИМКИ НЕ ЖИВУТ В РАБОЧЕЙ КОПИИ ДОЛЬШЕ СРОКА. Прогон закончен — остаётся
   эталон, пара «до/после» и образец, а не весь набор. Предел:
   не больше `--per-worktree-mib` старше `--days` суток в одной копии.
3. ПО ХОСТУ ЕСТЬ ПОТОЛОК. Он нужен не вместо первых двух, а чтобы отказ был
   виден даже если нарушение размазано тонким слоем: `--host-gib`.

Исходы различимы: ИСПРАВНО, ПРЕВЫШЕНО (с перечнем мест и чисел), НЕ ИЗМЕРЕНО
(с причиной). «Нет данных» не выдаётся за «в порядке».

ЧЕГО ПРОВЕРКА НЕ ДЕЛАЕТ: не удаляет и не решает, что ценно. Ценность
разбирает `screenshot-value-census.py`, снятие — `screenshot-retire.py`.

    python3 automation/local/screenshot-retention-guard.py
    python3 automation/local/screenshot-retention-guard.py --root /srv --json

Коды: 0 — исправно, 1 — превышено, 2 — не измерено.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import pathlib
import sys
import time

РАСШИРЕНИЯ = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif")
ПРОПУСК = {".git", "node_modules", ".next", "__pycache__", ".pytest_cache",
           ".ruff_cache", "site-packages", ".venv"}
#: Снимком приёмки считается изображение в каталоге прогона, а не оформление
#: сайта: иначе проверка ругалась бы на логотипы и постеры шаблона.
ПРИЗНАК_СНИМКА = ("/artifacts/", "/report/", "/reports/", "/shots/",
                  "/evidence/", "/checks/", "/var/")
НЕ_СНИМОК = ("/templates/", "/brand/", "/public/", "/static/", "/assets/",
             "/poster/", "/media/")


def снимок(путь: str) -> bool:
    низкий = путь.lower()
    if not низкий.endswith(РАСШИРЕНИЯ):
        return False
    if any(с in низкий for с in НЕ_СНИМОК):
        return False
    return any(с in низкий for с in ПРИЗНАК_СНИМКА)


def обойти(корни: list[str]) -> list[tuple[int, float, str]]:
    итог: list[tuple[int, float, str]] = []
    for корень in корни:
        for каталог, подкаталоги, файлы in os.walk(корень,
                                                   onerror=lambda _: None):
            подкаталоги[:] = [п for п in подкаталоги if п not in ПРОПУСК]
            for имя in файлы:
                путь = os.path.join(каталог, имя)
                if not снимок(путь):
                    continue
                try:
                    ст = os.stat(путь)
                except OSError:
                    continue
                итог.append((ст.st_size, ст.st_mtime, путь))
    return итог


def главное(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--root", action="append", default=[])
    р.add_argument("--list", dest="перечень", default="",
                   help="готовая опись «размер<TAB>путь» вместо обхода:"
                        " один обход на три проверки")
    р.add_argument("--per-release", type=int, default=20)
    р.add_argument("--per-worktree-mib", type=float, default=100.0)
    р.add_argument("--days", type=int, default=30)
    р.add_argument("--host-gib", type=float, default=2.0)
    р.add_argument("--json", action="store_true")
    а = р.parse_args(аргв)

    if а.перечень:
        существуют = [а.перечень]
        файлы = []
        try:
            строки = pathlib.Path(а.перечень).read_text(
                encoding="utf-8", errors="replace").splitlines()
        except OSError as сбой:
            print(f"НЕ ИЗМЕРЕНО: опись не прочитана: {сбой}")
            return 2
        for с in строки:
            if "\t" not in с:
                continue
            размер, путь = с.split("\t", 1)
            if not снимок(путь):
                continue
            try:
                файлы.append((int(размер), os.path.getmtime(путь), путь))
            except (ValueError, OSError):
                continue
    else:
        корни = а.root or ["/srv", "/home/claude"]
        существуют = [к for к in корни if os.path.isdir(к)]
        if not существуют:
            print(f"НЕ ИЗМЕРЕНО: ни один корень не найден: {корни}")
            return 2
        файлы = обойти(существуют)
    if not файлы:
        итог = {"исход": "ИСПРАВНО", "почему": "снимков не найдено",
                "корни": существуют, "файлов": 0}
        print(json.dumps(итог, ensure_ascii=False) if а.json
              else "исход: ИСПРАВНО — снимков приёмки не найдено")
        return 0

    порог_времени = time.time() - а.days * 86400
    по_релизу = collections.Counter()
    байт_копии = collections.Counter()
    всего = 0
    for размер, когда, путь in файлы:
        всего += размер
        if "/releases/" in путь:
            корень, остаток = путь.split("/releases/", 1)
            по_релизу[f"{корень}/releases/{остаток.split('/', 1)[0]}"] += 1
        части = путь.split("/")
        if len(части) > 3 and части[1] == "home" and части[3].startswith("wt-"):
            if когда < порог_времени:
                байт_копии["/".join(части[:4])] += размер

    релизы = [(м, n) for м, n in по_релизу.items() if n > а.per_release]
    копии = [(м, б) for м, б in байт_копии.items()
             if б / 2**20 > а.per_worktree_mib]
    хост_превышен = всего / 2**30 > а.host_gib

    нарушения = {
        "релизы_с_снимками": sorted(релизы, key=lambda п: -п[1])[:10],
        "копии_со_старыми_снимками": [
            (м, round(б / 2**20, 1))
            for м, б in sorted(копии, key=lambda п: -п[1])[:10]],
        "хост_гиб": round(всего / 2**30, 2),
    }
    исход = ("ПРЕВЫШЕНО" if (релизы or копии or хост_превышен) else "ИСПРАВНО")
    итог = {"исход": исход, "корни": существуют, "файлов": len(файлы),
            "объём_гиб": round(всего / 2**30, 2),
            "пределы": {"на_релиз": а.per_release,
                        "на_копию_миб": а.per_worktree_mib,
                        "суток": а.days, "на_хост_гиб": а.host_gib},
            "нарушения": нарушения}

    if а.json:
        print(json.dumps(итог, ensure_ascii=False, indent=1))
    else:
        print(f"исход: {исход}")
        print(f"   снимков {len(файлы)}, объём {всего/2**30:.2f} ГиБ"
              f" (потолок хоста {а.host_gib} ГиБ)")
        if релизы:
            print(f"   релизов со снимками больше {а.per_release}:"
                  f" {len(релизы)}")
            for м, n in sorted(релизы, key=lambda п: -п[1])[:5]:
                print(f"      {n:5} снимков  {м}")
        if копии:
            print(f"   рабочих копий со снимками старше {а.days} суток"
                  f" больше {а.per_worktree_mib} МиБ: {len(копии)}")
            for м, б in sorted(копии, key=lambda п: -п[1])[:5]:
                print(f"      {б/2**20:7.1f} МиБ  {м}")
        if исход == "ПРЕВЫШЕНО":
            print("   что делать: разобрать ценность"
                  " (`screenshot-value-census.py`), затем снять лишнее"
                  " (`screenshot-retire.py` — он сначала сохраняет образец)")
    return 1 if исход == "ПРЕВЫШЕНО" else 0


if __name__ == "__main__":
    sys.exit(главное())
