#!/usr/bin/env python3
"""Целы ли редакционные правки витрин: кто писал последним и какие поля живы.

Повод. 2026-10-11 прогон редактора перезаписал
`/srv/zonafilm-space/data/editorial-overrides.json` одними описаниями, и
внесённое название (решение D200) исчезло — страница вернулась к оригиналу.
Причина: правка «состав файла собирается из ЖИВОГО файла плюс свои описания» в
службу MCP не установлена, а старый код собирает файл целиком из своих полей.

Пока правка не установлена, файлы надо проверять, а не надеяться. Инструмент
только читает: показывает время записи, схему, число правок, набор полей и
авторов — и отдельно называет файлы, где НЕТ ни одного поля кроме описаний,
хотя раньше были другие.

    python3 automation/local/editorial-overrides-audit.py
    python3 automation/local/editorial-overrides-audit.py --json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

КОРНИ = Path("/srv")
#: Поля, которые ведёт не редактор: их исчезновение и есть потеря.
НЕ_ОПИСАНИЕ = ("name", "original_name", "poster_url", "year", "kind")


def файлы() -> list[Path]:
    return sorted(КОРНИ.glob("*/data/editorial-overrides.json"))


def разобрать(путь: Path) -> dict:
    с = путь.stat()
    итог = {
        "файл": str(путь),
        "витрина": путь.parent.parent.name,
        "изменён": dt.datetime.fromtimestamp(
            с.st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "байт": с.st_size,
    }
    try:
        документ = json.loads(путь.read_text(encoding="utf-8"))
    except (OSError, ValueError) as сбой:
        итог["ошибка"] = str(сбой)[:120]
        return итог
    итог["схема"] = документ.get("schema_version", "—")
    правки = документ.get("overrides")
    if правки is None:
        # Прежняя раскладка: правки лежали на верхнем уровне по ключу записи.
        правки = {к: v for к, v in документ.items()
                  if isinstance(v, dict) and ("fields" in v or "name" in v)}
    итог["правок"] = len(правки)
    поля: set[str] = set()
    авторы: set[str] = set()
    for з in правки.values():
        названные = з.get("fields")
        # `fields` встречается и списком имён, и словарём «имя → значение»:
        # первая версия разбора брала его за имя поля и печатала «fields»
        # вместо состава. Разбираются оба вида, иначе мера молчит о том, что
        # ищет.
        if isinstance(названные, dict):
            поля.update(названные)
        elif isinstance(названные, (list, tuple)):
            поля.update(названные)
        else:
            поля.update(к for к in з if к not in ("actor", "reason", "at"))
        if з.get("actor"):
            авторы.add(str(з["actor"]))
    итог["поля"] = sorted(поля)
    итог["авторы"] = sorted(авторы)
    итог["только_описания"] = bool(поля) and поля <= {"description"}
    итог["есть_чужие_поля"] = sorted(п for п in поля if п in НЕ_ОПИСАНИЕ)
    return итог


def главное(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description="целость редакционных правок")
    р.add_argument("--json", action="store_true")
    а = р.parse_args(аргв)
    найдено = [разобрать(п) for п in файлы()]
    if not найдено:
        print("файлов правок не найдено", file=sys.stderr)
        return 2
    if а.json:
        print(json.dumps(найдено, ensure_ascii=False, indent=2))
        return 0
    print(f"{'витрина':22} {'изменён':22} {'правок':>7} {'схема':>7}  поля")
    только_описания = []
    for и in найдено:
        if "ошибка" in и:
            print(f"{и['витрина']:22} НЕ ПРОЧИТАН: {и['ошибка']}")
            continue
        print(f"{и['витрина']:22} {и['изменён']:22} {и['правок']:>7} "
              f"{str(и['схема']):>7}  {', '.join(и['поля']) or '—'}")
        if и["только_описания"]:
            только_описания.append(и["витрина"])
    print(f"\nфайлов: {len(найдено)}; только описания: {len(только_описания)}")
    if только_описания:
        print("   " + " ".join(только_описания))
        print("   Это НЕ доказательство потери: у витрины могло не быть других")
        print("   полей. Доказательство — сравнение с тем, что вносилось:")
        print("   передачи 114/115/116 и журналы накладок.")
    for и in найдено:
        if и.get("есть_чужие_поля"):
            print(f"   {и['витрина']}: поля не редактора на месте — "
                  f"{', '.join(и['есть_чужие_поля'])}")
    return 0


if __name__ == "__main__":
    sys.exit(главное())
