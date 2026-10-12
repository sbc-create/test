#!/usr/bin/env python3
"""План обновления установленного исполнителя: что изменится и от какой версии.

Зачем отдельный шаг перед установкой. Состав обновления — не список по памяти,
а разница между установленной копией и деревом службы СЕЙЧАС. Дерево службы
при этом живое: пока пакет ждёт владельца, туда приходят новые коммиты, и
состав меняется. За один вечер 12.10 он вырос с 10 файлов до 12.

Поэтому план ЗАКРЕПЛЯЕТСЯ: архитектор называет коммит, на котором состав
измерен, а этот сценарий перед установкой сверяет, тот ли коммит в дереве.
Разошлось — отказ с названной причиной и НОВЫМ составом, а не тихая установка
чего-то другого.

Ничего не меняет: только читает и печатает. Запускать можно без root; под
root дополнительно читаются файлы установленной копии с правами 0600.

    python3 automation/host/executor-update-plan.py --expect d2f28e99cbdb
"""
from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

СЛУЖБА = Path("/home/claude/wt-portable-site-cell-01")
УСТАНОВЛЕНО = Path("/usr/local/lib/site-factory-cell")
#: Что установщик кладёт в корневую копию. Перечень НЕ по памяти: он равен
#: строкам `cp -a "$SRC_ROOT/<каталог>"` установщика, и это равенство держит
#: `tests/unit/test_executor_update_plan.py`. Прежняя редакция добавляла сюда
#: `scripts`, которого установщик не копирует вовсе, — и состав обновления
#: завышался на 7 файлов, которые на машину не попадут.
КАТАЛОГИ = ("factory", "schemas", "config")


def каталоги_установщика(установщик: Path) -> tuple[str, ...]:
    """Каталоги, которые установщик фактически копирует."""
    образец = re.compile(r'cp -a "\$SRC_ROOT/([A-Za-z0-9_]+)"')
    текст = установщик.read_text(encoding="utf-8")
    видели: list[str] = []
    for имя in образец.findall(текст):
        if имя not in видели:
            видели.append(имя)
    return tuple(видели)


def сумма(п: Path) -> str:
    return hashlib.sha256(п.read_bytes()).hexdigest()


def git(корень: Path, *арг: str) -> str:
    готово = subprocess.run(["git", "-C", str(корень), *арг],
                            capture_output=True, text=True, timeout=120)
    return готово.stdout.strip() if готово.returncode == 0 else ""


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--expect", default="",
                   help="коммит дерева службы, на котором состав закреплён")
    р.add_argument("--service", type=Path, default=СЛУЖБА)
    р.add_argument("--installed", type=Path, default=УСТАНОВЛЕНО)
    опции = р.parse_args(аргв)

    голова = git(опции.service, "rev-parse", "--short=12", "HEAD")
    ветвь = git(опции.service, "rev-parse", "--abbrev-ref", "HEAD")
    грязно = git(опции.service, "status", "--porcelain")
    print(f"дерево службы: {опции.service}")
    print(f"   ветвь {ветвь or '—'}, коммит {голова or '—'}")
    if грязно:
        print(f"   незакоммиченных файлов: {len(грязно.splitlines())}")

    к_обновлению: list[tuple[str, str, str]] = []
    новые: list[str] = []
    недоступны: list[str] = []
    сверено = 0
    for каталог in КАТАЛОГИ:
        корень = опции.service / каталог
        if not корень.is_dir():
            continue
        for файл in sorted(корень.rglob("*")):
            if not файл.is_file() or "__pycache__" in файл.parts:
                continue
            отн = файл.relative_to(опции.service).as_posix()
            цель = опции.installed / отн
            сверено += 1
            if not цель.is_file():
                новые.append(отн)
                continue
            try:
                сейчас = сумма(цель)
            except PermissionError:
                # 0600 под root: содержимое не прочитать. Это предел
                # измерения, а НЕ «совпадает» — разница существенная.
                недоступны.append(отн)
                continue
            станет = сумма(файл)
            if станет != сейчас:
                к_обновлению.append((отн, сейчас[:16], станет[:16]))

    print(f"   сверено файлов: {сверено}")
    print(f"\nбудет обновлено файлов: {len(к_обновлению)}")
    for отн, сейчас, станет in к_обновлению:
        print(f"   {отн}")
        print(f"      {сейчас}… → {станет}…")
    if новые:
        print(f"\nбудет добавлено файлов: {len(новые)}")
        for отн in новые[:10]:
            print(f"   {отн}")
        if len(новые) > 10:
            print(f"   … и ещё {len(новые) - 10}")
    if недоступны:
        print(f"\nне прочитаны этой учётной записью (0600 root): "
              f"{len(недоступны)}")
        print("   это предел измерения, а не «совпадает»")
        for отн in недоступны[:4]:
            print(f"   {отн}")
        if len(недоступны) > 4:
            print(f"   … и ещё {len(недоступны) - 4}")

    if опции.expect and голова and голова != опции.expect:
        print(f"\nОТКАЗ: состав закреплён на коммите {опции.expect}, "
              f"а в дереве {голова}.", file=sys.stderr)
        print("Состав выше — НОВЫЙ и архитектором не подтверждён. "
              "Установку не начинайте: пришлите этот вывод.", file=sys.stderr)
        return 1
    if опции.expect:
        print(f"\nверсия совпадает с закреплённой ({опции.expect}): "
              "состав выше подтверждён, установку можно начинать")
    return 0


if __name__ == "__main__":
    raise SystemExit(главное())
