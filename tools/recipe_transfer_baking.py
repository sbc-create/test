"""Перенос записи выпечки из конвейера food-daily (bestreciept) в факты food-baking (myfood).

    python3 tools/recipe_transfer_baking.py <food-daily.sqlite3> <record_id>=<группа> [...]

Лежит в координационном репозитории: шаблоны изолированы и друг на друга не ссылаются.

Запись конвейера уже содержит факты из Recipe-разметки страницы eda.rambler.ru (статус
topic_mismatch: выпечка не по теме повседневного сайта). Сеть не используется: факты и шаги берутся
из записи, духовка и форма разбираются функцией импорта myfood (`oven_facts`). Неполная запись
(complete = 0) не переносится. Шаги источника — только в закрытое хранилище (как у импорта).
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(
    0,
    str(
        Path(__file__).resolve().parents[1].parent
        / "wt-template-food-baking-b"
        / "templates"
        / "food-baking"
    ),
)
from bakebook.importer import FACTS, PRIVATE, oven_facts  # noqa: E402
from bakebook.site import GROUPS  # noqa: E402


def transfer(db_path: str, record_id: str, group: str) -> dict:
    if group not in GROUPS:
        raise ValueError(f"неизвестная группа {group!r}")
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    r = db.execute("SELECT * FROM records WHERE record_id=?", (record_id,)).fetchone()
    if not r:
        raise ValueError(f"{record_id}: записи нет")
    if not r["complete"]:
        raise ValueError(f"{record_id}: запись неполная — не переносится")
    f = json.loads(r["facts_json"])
    url = r["source_url"]
    rid = "fb-" + hashlib.sha256(url.encode()).hexdigest()[:12]
    steps = list(f["steps"])
    facts = {
        "source_url": url,
        "title": f["title"],
        "servings": f["servings"],
        "prep_minutes": f["prep_minutes"],
        "cook_minutes": f["cook_minutes"],
        "total_minutes": f["total_minutes"],
        "ingredients": [
            {k: i[k] for k in ("raw", "name", "quantity", "unit")}
            | ({"note": i["note"]} if i.get("note") else {})
            for i in f["ingredients"]
        ],
        "source_category": f.get("category"),
        "oven": oven_facts(steps),
        "parser_version": r["parser_version"],
        "remarks": list(f.get("remarks") or [])
        + [
            f"перенесено из записи конвейера food-daily {record_id} (без новой загрузки страницы)"
        ],
        "complete": True,
        "content_hash": r["content_hash"],
        "record_id": rid,
        "group_hint": group,
        "step_count": len(steps),
        "fetched_at": r["fetched_at"],
    }
    PRIVATE.mkdir(parents=True, exist_ok=True)
    payload = {"source_url": url, "steps": steps, "fetched_at": r["fetched_at"]}
    (PRIVATE / f"{rid}.json.gz").write_bytes(
        gzip.compress(json.dumps(payload, ensure_ascii=False).encode())
    )
    (FACTS / f"{rid}.json").write_text(json.dumps(facts, ensure_ascii=False, indent=1) + "\n")
    return {
        "record_id": rid,
        "from": record_id,
        "title": f["title"],
        "group": group,
        "oven": facts["oven"],
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="recipe_transfer_baking")
    ap.add_argument("db")
    ap.add_argument("pairs", nargs="+", help="record_id=группа")
    a = ap.parse_args(argv)
    out = [transfer(a.db, *p.split("=", 1)) for p in a.pairs]
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
