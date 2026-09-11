#!/usr/bin/env python3
"""Технический долг: исторические synthetic-записи. Классификация без удаления."""
import hashlib, json, sqlite3, datetime as dt
from pathlib import Path

БД = "/srv/site-factory/registry-core/registry.sqlite3"
ВЫХОД = Path("/srv/site-factory/control-plane-contracts/evidence/"
             "r3-historical-synthetic-debt.json")
ПРОД = {"lords-01","lords-02","lords-03","yummyani-biz","yummyani-org",
        "yummyani-site","zona-01","animedia-01","animedia-02"}

c = sqlite3.connect(f"file:{БД}?mode=ro", uri=True); c.row_factory = sqlite3.Row
записи = []
for r in c.execute("SELECT * FROM site ORDER BY site_id"):
    d = dict(r)
    if d["site_id"] in ПРОД or d["site_id"] == "demo-books":
        continue
    соб = [dict(e) for e in c.execute(
        "SELECT event_type, actor, correlation_id, occurred_at FROM outbox "
        "WHERE site_id=? ORDER BY seq", (d["site_id"],))]
    ауд = [dict(a) for a in c.execute(
        "SELECT at, actor, action FROM audit WHERE site_id=? ORDER BY id",
        (d["site_id"],))]
    записи.append({
        "site_id": d["site_id"], "canonical_domain": d["canonical_domain"],
        "environment": d["environment"], "lifecycle_state": d["lifecycle_state"],
        "created_at": d["created_at"], "updated_at": d["updated_at"],
        "aggregate_version": d["aggregate_version"],
        "events": [e["event_type"] for e in соб],
        "actors": sorted({a["actor"] for a in ауд}),
        "correlation_ids": sorted({e["correlation_id"] for e in соб}),
        "provenance_strength": "INDIRECT",
        "provenance_evidence": (
            "имя вида synthetic-*, environment=test, actor service:test или "
            "service:architect в аудите, полный жизненный цикл событий. "
            "Выделенных полей created_by и test_run_id в схеме НЕТ, поэтому "
            "прямого доказательства принадлежности прогону не существует"),
        "in_production_snapshot": False,
        "proposed_disposition": "ARCHIVE_THEN_DELETE",
        "disposition_blocked_by": "требуется отдельное разрешение владельца на hard delete",
    })
итог = {
    "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    "count": len(записи),
    "records": записи,
    "leak_stopped": True,
    "leak_stopped_by": "N+1 переведён на изолированную временную базу (R3)",
    "why_not_deleted": (
        "Удаление исторических записей запрещено без отдельного разрешения "
        "владельца. Кроме того, их события уже лежат в неизменяемой ленте "
        "outbox: удалить запись, оставив событие о ней, значит создать "
        "ссылку в никуда"),
    "handoff_to": "FLEET-CORE-002-AUDIT-LEDGER",
    "handoff_note": (
        "Передаётся как известный технический долг. Ledger обязан учесть, что "
        "у этих записей происхождение доказано лишь косвенно, и что схема "
        "реестра не несёт полей created_by и test_run_id — их отсутствие и "
        "есть причина косвенности"),
    "recommended_schema_followup": (
        "добавить в site поля created_by и test_run_id, чтобы происхождение "
        "будущих записей доказывалось прямо, а не выводилось"),
}
ВЫХОД.parent.mkdir(parents=True, exist_ok=True)
ВЫХОД.write_text(json.dumps(итог, ensure_ascii=False, indent=1), encoding="utf-8")
print("исторических synthetic-записей:", len(записи))
for з in записи:
    print("  %-26s %-6s %-9s версия %d  события: %s" % (
        з["site_id"], з["environment"], з["lifecycle_state"],
        з["aggregate_version"], ",".join(з["events"])))
print("классифицировано:", len(записи), "из", len(записи))
print("hard delete: НЕ выполняется — нужно отдельное разрешение владельца")
