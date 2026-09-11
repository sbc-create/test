"""Публикация событий из outbox в durable replayable feed.

Брокера нет, и заводить его это задание запрещает. Достаточно долговечной
ленты: события дописываются в JSONL строго по возрастанию seq, а отметка
публикации ставится в БД. Потребитель читает ленту по курсору и обязан быть
идемпотентным — доставка at-least-once, а не exactly-once.

Порядок операций важен: сначала запись в ленту, потом отметка в БД. При
обратном порядке падение между ними потеряло бы событие навсегда; при этом
порядке оно будет опубликовано повторно, что потребитель переживёт по
event_id.
"""
from __future__ import annotations

import json, sqlite3, sys, time
from pathlib import Path

ЛЕНТА = Path("/srv/site-factory/registry-core/feed/registry-events.jsonl")
ПОПЫТОК = 5


def опубликовать(соед: sqlite3.Connection, *, предел: int = 1000) -> dict:
    ЛЕНТА.parent.mkdir(parents=True, exist_ok=True)
    строки = [dict(р) for р in соед.execute(
        "SELECT * FROM outbox WHERE published_at IS NULL ORDER BY seq LIMIT ?",
        (предел,))]
    опубликовано = отказов = 0
    for с in строки:
        попытка, задержка = 0, 0.05
        while True:
            попытка += 1
            try:
                with ЛЕНТА.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(с, ensure_ascii=False) + "\n")
                    f.flush()
                соед.execute(
                    "UPDATE outbox SET published_at=datetime('now'), "
                    "attempts=attempts+1, last_error=NULL WHERE seq=?", (с["seq"],))
                опубликовано += 1
                break
            except Exception as e:                       # noqa: BLE001
                if попытка >= ПОПЫТОК:
                    соед.execute(
                        "UPDATE outbox SET attempts=attempts+1, last_error=? "
                        "WHERE seq=?", (f"{type(e).__name__}", с["seq"]))
                    отказов += 1
                    break
                time.sleep(задержка)
                задержка = min(задержка * 2, 2.0)        # ограниченный backoff
    осталось = соед.execute(
        "SELECT count(*) c FROM outbox WHERE published_at IS NULL").fetchone()["c"]
    мёртвые = соед.execute(
        "SELECT count(*) c FROM outbox WHERE published_at IS NULL AND attempts >= ?",
        (ПОПЫТОК,)).fetchone()["c"]
    return {"published": опубликовано, "failed": отказов, "backlog": осталось,
            "dead_letter": мёртвые, "feed": str(ЛЕНТА)}


if __name__ == "__main__":
    c = sqlite3.connect("/srv/site-factory/registry-core/registry.sqlite3",
                        timeout=30, isolation_level=None)
    c.row_factory = sqlite3.Row
    print(json.dumps(опубликовать(c), ensure_ascii=False))
