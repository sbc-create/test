#!/usr/bin/env python3
"""Реальное состояние КАЖДОГО действующего домена — одной таблицей.

Поручение владельца 27.10: «сверь охват: заявлено 11 подготовленных доменов, в
таблице девять, lordserials22.info пропущен. Для каждого активного домена
укажи реальное состояние».

Расхождение между «заявлено» и «в таблице» возникает там, где таблицу пишут
руками: домен, по которому в этот раз ничего не делали, просто не попадает в
строку, и его состояние перестаёт быть видимым. Поэтому строки берутся из
РЕЕСТРА ячеек, а не из памяти: пропустить домен нечем.

Что в строке и откуда:

  состояние      `status` паспорта ячейки;
  пин            сверка рантайма проекта с каноном (`cell-pin-freshness`);
  продвижение    можно ли продвинуть шаблон (`promote-cell-pins --check`);
  подборки       объявлены ли редакционные подборки в проекте витрины;
  пауза          действующие ограничения из очереди домена, если они названы.

Только чтение: ни один паспорт, проект и очередь не правятся. Сеть не
опрашивается — это снимок СОСТОЯНИЯ РЕПОЗИТОРИЯ, а не живая проверка, и так и
подписано: живые коды ответа снимают другие инструменты.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
РЕЕСТР = КОРЕНЬ / "config" / "site-cells.json"
ОЧЕРЕДИ = КОРЕНЬ / "config" / "domain-queues"


def _модуль(имя: str, файл: str):
    сп = importlib.util.spec_from_file_location(имя, КОРЕНЬ / "automation" / "local" / файл)
    м = importlib.util.module_from_spec(сп)
    sys.modules[имя] = м
    сп.loader.exec_module(м)
    return м


def пауза_домена(домен: str) -> str:
    """Названное ограничение из очереди домена. Пусто — ограничения не названо."""
    путь = ОЧЕРЕДИ / f"{домен}.json"
    if not путь.is_file():
        return ""
    try:
        д = json.loads(путь.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    причина = str(д.get("stage_reason") or "").strip()
    ждут = [з for з in (д.get("tasks") or [])
            if str(з.get("state") or "") not in ("закрыто", "опубликовано")]
    блок = next((str(з.get("blocked_by") or "").strip() for з in ждут
                 if з.get("blocked_by")), "")
    return (причина or блок)[:120]


def подборки_витрины(проект: pathlib.Path) -> str:
    ф = проект / "config" / "collections.json"
    if not ф.is_file():
        return "нет"
    try:
        д = json.loads(ф.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "файл не читается"
    кол = д.get("collections") or []
    состояние = str(д.get("status") or "").strip()
    return f"{len(кол)} ({состояние or 'состояние не названо'})"


def строки() -> list:
    свежесть = _модуль("afs_freshness", "cell-pin-freshness.py")
    продвижение = _модуль("afs_promote", "promote-cell-pins.py")
    по_ячейке = {з["site_id"]: з for з in свежесть.свежесть()}
    итог = []
    данные = json.loads(РЕЕСТР.read_text(encoding="utf-8"))
    for я in данные.get("cells") or []:
        отозван = bool((я.get("withdrawal") or {}).get("withdrawn"))
        site_id = я.get("site_id")
        домен = я.get("domain") or ""
        путь = ((я.get("repo") or {}).get("path") or "").strip()
        проект = (КОРЕНЬ / путь) if путь else None
        пин = (по_ячейке.get(site_id) or {}).get("исход", "—")
        try:
            пр = продвижение.разбор(site_id)["исход"]
        except Exception:  # noqa: BLE001 — состояние строки важнее исключения
            пр = "не разобрано"
        итог.append({
            "site_id": site_id, "домен": домен,
            "состояние": "ОТОЗВАН" if отозван else (я.get("status") or "—"),
            "пин": пин, "продвижение": пр,
            "подборки": подборки_витрины(проект) if проект and проект.is_dir() else "проекта нет",
            "ограничение": пауза_домена(домен),
        })
    return итог


def главная(аргв=None) -> int:
    р = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    р.add_argument("--json", action="store_true")
    р.add_argument("--active", action="store_true",
                   help="только действующие: без отозванных и без площадок-проб")
    а = р.parse_args(аргв)
    всё = строки()
    если_надо = [с for с in всё
                 if not (а.active and (с["состояние"] in ("ОТОЗВАН",)
                                       or с["домен"].endswith(".localhost")
                                       or ".localhost." in с["домен"]))]
    if а.json:
        print(json.dumps({"строк": len(если_надо), "домены": если_надо},
                         ensure_ascii=False, indent=1))
        return 0
    print(f"{'домен':24} {'состояние':9} {'пин':15} {'продвижение':15} "
          f"{'подборки':22} ограничение")
    for с in если_надо:
        print(f"{с['домен']:24} {с['состояние']:9} {с['пин']:15} "
              f"{с['продвижение']:15} {с['подборки']:22} {с['ограничение']}")
    print(f"\nстрок: {len(если_надо)} — из реестра ячеек, не из памяти; "
          f"живые коды ответа здесь НЕ снимаются")
    return 0


if __name__ == "__main__":
    raise SystemExit(главная())
