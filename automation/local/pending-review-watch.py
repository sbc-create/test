#!/usr/bin/env python3
"""Материалы, подготовленные сегодня и ещё НЕ получившие рецензии.

Зачем отдельный инструмент, когда есть `review-materials-batch.py`. Тот
разбирает партию и печатает подробности; здесь нужно другое — ОДНА строка на
ожидающий материал, пригодная для наблюдателя: пока ждать нечего, вывод пуст,
и наблюдатель молчит. Полный разбор для этого не годится: он печатает сводку
всегда, то есть «ждать нечего» и «ждёт двенадцать» выглядели бы одинаково
шумно.

Только чтение. Хранилища черновиков принадлежат витринам, и этот инструмент их
не меняет ни в одном случае.

    python3 automation/local/pending-review-watch.py [--date 2026-10-25]
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import pathlib
import sys

ХРАНИЛИЩА = "/srv/sites/*/runtime/overlays/*/drafts.json"


def записи(хранилище: dict) -> list[tuple[str, dict]]:
    """Пары (слаг, запись) для обоих видов хранилища: список и словарь.

    Два вида встречаются в живых хранилищах, и быстрая проверка, знающая один,
    трижды за ночь прочитала структуру неверно. Поэтому вид определяется здесь
    и в одном месте.
    """
    если = хранилище.get("items") if isinstance(хранилище, dict) else хранилище
    if isinstance(если, dict):
        return [(с, з) for с, з in если.items() if isinstance(з, dict)]
    return [((з or {}).get("slug") or "", з) for з in (если or [])
            if isinstance(з, dict)]


def ожидающие(дата: str, хранилища: str = ХРАНИЛИЩА) -> list[str]:
    итог = []
    for путь in sorted(glob.glob(хранилища)):
        домен = pathlib.Path(путь).parent.name
        try:
            данные = json.loads(pathlib.Path(путь).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # Нечитаемое хранилище — не «ничего не ждёт»: так и говорим.
            итог.append(f"ХРАНИЛИЩЕ НЕ ПРОЧИТАНО: {путь}")
            continue
        for слаг, запись in записи(данные):
            когда = str(запись.get("prepared_at") or "")
            отзыв = (запись.get("review") or {}).get("verdict")
            if слаг and когда.startswith(дата) and not отзыв:
                итог.append(f"ЖДЁТ РЕЦЕНЗИИ: {домен}/{слаг} подготовлен {когда}")
    return sorted(итог)


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--date", default=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"))
    а = р.parse_args(аргв)
    строки = ожидающие(а.date)
    for с in строки:
        print(с)
    return 0


if __name__ == "__main__":
    sys.exit(главное())
