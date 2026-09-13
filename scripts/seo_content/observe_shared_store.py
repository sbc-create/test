#!/usr/bin/env python3
"""Наблюдение за общим Changeset Store — только чтение.

Файл общего хранилища доступен текущему пользователю и на запись. Поэтому
«мы туда не писали» — не утверждение, а обязательство, и проверять его надо
измерением: отпечаток файла, число строк, отпечаток содержимого ключевых
таблиц до и после работы.

База открывается в режиме `mode=ro`. Хвост предыдущего этапа (R4) не
удаляется: его уборка принадлежит владельцу хранилища, а не этому контуру.

    python3 scripts/seo_content/observe_shared_store.py --out before.json
    python3 scripts/seo_content/observe_shared_store.py --out after.json \
        --compare before.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sqlite3
import sys

БАЗА = "/srv/site-factory/changeset-store/changesets.sqlite3"
ЖУРНАЛ = "/srv/site-factory/audit-ledger/audit_ledger.sqlite3"

#: Таблицы, строки которых считаются «ключевыми» для отчёта R4.
КЛЮЧЕВЫЕ = ("changeset", "changeset_target", "seo_content_proposal")


def отпечаток_файла(путь: str) -> dict:
    п = pathlib.Path(путь)
    if not п.exists():
        return {"path": путь, "exists": False}
    данные = п.read_bytes()
    return {"path": путь, "exists": True, "bytes": len(данные),
            "sha256": hashlib.sha256(данные).hexdigest()}


def снимок_базы(путь: str) -> dict:
    п = pathlib.Path(путь)
    if not п.exists():
        return {"path": путь, "exists": False}
    соед = sqlite3.connect(f"file:{путь}?mode=ro", uri=True)
    try:
        таблицы = [r[0] for r in соед.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        строки = {т: соед.execute(f"SELECT COUNT(*) FROM {т}").fetchone()[0]
                  for т in таблицы}
        # Отпечаток содержимого: идентификаторы и полное тело строк отдельно,
        # чтобы отличить «добавили запись» от «переписали существующую».
        идентификаторы, содержимое = {}, {}
        for т in таблицы:
            колонки = [r[1] for r in соед.execute(f"PRAGMA table_info({т})")]
            if not колонки:
                continue
            первичный = колонки[0]
            ид = [str(r[0]) for r in соед.execute(
                f"SELECT {первичный} FROM {т} ORDER BY 1")]
            идентификаторы[т] = hashlib.sha256(
                "\x1f".join(ид).encode()).hexdigest()
            тела = [
                "\x1f".join("" if v is None else str(v) for v in строка)
                for строка in соед.execute(
                    f"SELECT * FROM {т} ORDER BY {первичный}")]
            содержимое[т] = hashlib.sha256(
                "\x1e".join(тела).encode()).hexdigest()
    finally:
        соед.close()
    return {"path": путь, "exists": True, "tables": таблицы, "rows": строки,
            "identifier_hash": идентификаторы, "content_hash": содержимое,
            "key_rows": sum(строки.get(т, 0) for т in КЛЮЧЕВЫЕ),
            "outbox_rows": строки.get("changeset_outbox", 0)}


def снимок_журнала(путь: str) -> dict:
    п = pathlib.Path(путь)
    if not п.exists():
        return {"path": путь, "exists": False}
    соед = sqlite3.connect(f"file:{путь}?mode=ro", uri=True)
    try:
        таблицы = [r[0] for r in соед.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")]
        событий = {}
        for т in таблицы:
            колонки = {r[1] for r in соед.execute(f"PRAGMA table_info({т})")}
            if "event_type" in колонки or "kind" in колонки or т.endswith("event"):
                событий[т] = соед.execute(
                    f"SELECT COUNT(*) FROM {т}").fetchone()[0]
        # Хвост R4 в журнале — события предложения набора изменений: по
        # четыре с каждой стороны границы, восемь всего. Считаются они
        # поимённо, а не подстрокой «seo»: подстрока поймала бы и посторонние
        # события, и число в отчёте перестало бы что-либо означать.
        хвост = {}
        по_типам = {}
        for т in событий:
            колонки = {r[1] for r in соед.execute(f"PRAGMA table_info({т})")}
            поле = "event_type" if "event_type" in колонки else (
                "kind" if "kind" in колонки else None)
            if поле is None:
                continue
            по_типам[т] = dict(соед.execute(
                f"SELECT {поле}, COUNT(*) FROM {т} GROUP BY 1").fetchall())
            for имя in ("seo.changeset.proposed.v1", "changeset.proposed.v1"):
                хвост[имя] = хвост.get(имя, 0) + по_типам[т].get(имя, 0)
    finally:
        соед.close()
    return {"path": путь, "exists": True, "event_tables": событий,
            "r4_tail_events": хвост,
            "r4_tail_total": sum(хвост.values()),
            "events_by_type": по_типам}


def сравнить(до: dict, после: dict) -> dict:
    итог = {"SHARED_STORE_WRITES": 0,
            "SHARED_STORE_IDENTIFIER_DELTA": 0,
            "SHARED_STORE_CONTENT_HASH_DELTA": 0,
            "FILE_SHA256_CHANGED": False, "details": []}
    а, б = до.get("changeset_store", {}), после.get("changeset_store", {})
    if not (а.get("exists") and б.get("exists")):
        итог["details"].append("хранилище отсутствует в одном из снимков")
        return итог
    for т in sorted(set(а["rows"]) | set(б["rows"])):
        было, стало = а["rows"].get(т, 0), б["rows"].get(т, 0)
        if было != стало:
            итог["SHARED_STORE_WRITES"] += abs(стало - было)
            итог["details"].append(f"{т}: строк было {было}, стало {стало}")
        if а["identifier_hash"].get(т) != б["identifier_hash"].get(т):
            итог["SHARED_STORE_IDENTIFIER_DELTA"] += 1
            итог["details"].append(f"{т}: изменился состав идентификаторов")
        if а["content_hash"].get(т) != б["content_hash"].get(т):
            итог["SHARED_STORE_CONTENT_HASH_DELTA"] += 1
            итог["details"].append(f"{т}: изменилось содержимое строк")
    файл_а = до.get("file", {}).get("sha256")
    файл_б = после.get("file", {}).get("sha256")
    журнал_а = до.get("audit_ledger", {})
    журнал_б = после.get("audit_ledger", {})
    if журнал_а.get("exists") and журнал_б.get("exists"):
        было = журнал_а.get("event_tables", {}).get("ledger_event", 0)
        стало = журнал_б.get("event_tables", {}).get("ledger_event", 0)
        итог["AUDIT_LEDGER_APPENDS"] = стало - было
        if стало != было:
            итог["details"].append(
                f"журнал: событий было {было}, стало {стало}")
        итог["R4_AUDIT_EVENTS_OBSERVED"] = журнал_б.get("r4_tail_total", 0)

    итог["FILE_SHA256_CHANGED"] = файл_а != файл_б
    if итог["FILE_SHA256_CHANGED"]:
        итог["details"].append(
            "отпечаток файла изменился; это может быть WAL-контрольная точка "
            "стороннего процесса — смотреть на строки и содержимое")
    return итог


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--out", required=True)
    р.add_argument("--compare", default=None)
    а = р.parse_args(аргв)

    снимок = {"changeset_store": снимок_базы(БАЗА),
              "file": отпечаток_файла(БАЗА),
              "audit_ledger": снимок_журнала(ЖУРНАЛ),
              "mode": "READ_ONLY"}
    if а.compare:
        до = json.loads(pathlib.Path(а.compare).read_text("utf-8"))
        снимок["comparison"] = сравнить(до, снимок)
    путь = pathlib.Path(а.out)
    путь.parent.mkdir(parents=True, exist_ok=True)
    путь.write_text(json.dumps(снимок, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    print(json.dumps({k: v for k, v in снимок.items()
                      if k in ("comparison", "file")}
                     | {"key_rows": снимок["changeset_store"].get("key_rows"),
                        "outbox_rows": снимок["changeset_store"].get("outbox_rows"),
                        "rows": снимок["changeset_store"].get("rows")},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(главное())
