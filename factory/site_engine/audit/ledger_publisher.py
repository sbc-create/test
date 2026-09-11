#!/usr/bin/env python3
"""Публикация ledger-outbox в durable-ленту.

Самоподавление: событие `audit.event.appended.v1` уходит в ленту, но НЕ
возвращается в журнал как новое событие. Иначе каждая запись порождала бы
запись о записи, и журнал рос бы сам от себя без внешних причин.
"""
from __future__ import annotations
import json, os, sys, time
from pathlib import Path
from . import ledger_store as store

ЖУРНАЛ = os.environ.get("AUDIT_LEDGER_DB",
                        "/srv/site-factory/audit-ledger/audit_ledger.sqlite3")
ЛЕНТА = Path(os.environ.get(
    "AUDIT_FEED", "/srv/site-factory/audit-ledger/feed/audit-events.jsonl"))
#: Типы, которые журнал порождает сам о себе и никогда не поглощает обратно.
САМОСОБЫТИЯ = {"audit.event.appended.v1"}


def опубликовать(предел: int = 5000) -> dict:
    ЛЕНТА.parent.mkdir(parents=True, exist_ok=True)
    c = store.открыть(ЖУРНАЛ)
    строки = [dict(r) for r in c.execute(
        "SELECT * FROM ledger_outbox WHERE published_at IS NULL "
        "ORDER BY seq LIMIT ?", (предел,))]
    опубликовано = 0
    for s in строки:
        # Сначала лента, потом отметка: при обратном порядке падение между
        # ними потеряло бы событие навсегда.
        with ЛЕНТА.open("a", encoding="utf-8") as f:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
            f.flush()
        c.execute("UPDATE ledger_outbox SET published_at=?, attempts=attempts+1 "
                  "WHERE seq=?", (store.сейчас(), s["seq"]))
        опубликовано += 1
    backlog = c.execute("SELECT count(*) c FROM ledger_outbox "
                        "WHERE published_at IS NULL").fetchone()["c"]
    # Проверка отсутствия рекурсии: самособытий в самом журнале быть не должно.
    рекурсия = c.execute(
        "SELECT count(*) c FROM ledger_event WHERE event_type IN (%s)"
        % ",".join("?" * len(САМОСОБЫТИЯ)), tuple(САМОСОБЫТИЯ)).fetchone()["c"]
    c.close()
    return {"published": опубликовано, "backlog": backlog,
            "self_event_recursion": рекурсия, "feed": str(ЛЕНТА)}


if __name__ == "__main__":
    print(json.dumps(опубликовать(), ensure_ascii=False))
