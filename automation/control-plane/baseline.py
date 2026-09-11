#!/usr/bin/env python3
"""Этап 1: исходное состояние реестра с классификацией и происхождением."""
import hashlib, json, pathlib, shutil, sqlite3, subprocess, datetime as dt

БД = "/srv/site-factory/registry-core/registry.sqlite3"
B = pathlib.Path("/srv/site-factory/registry-core/backup")
ОТЧЁТ = pathlib.Path("/srv/site-factory/control-plane-contracts/evidence/r3-baseline.json")
TS = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

B.mkdir(parents=True, exist_ok=True)
копия = B / f"registry.sqlite3.{TS}.before-r3"
shutil.copyfile(БД, копия)
сумма_копии = hashlib.sha256(копия.read_bytes()).hexdigest()

c = sqlite3.connect(БД); c.row_factory = sqlite3.Row
записи = [dict(r) for r in c.execute("SELECT * FROM site ORDER BY site_id")]
ids = sorted(r["site_id"] for r in записи)
H = hashlib.sha256(json.dumps(ids, ensure_ascii=False).encode()).hexdigest()
prod = [r for r in записи if r["environment"] == "production"
        and r["lifecycle_state"] == "ACTIVE"]

ПРОД = {"lords-01","lords-02","lords-03","yummyani-biz","yummyani-org",
        "yummyani-site","zona-01","animedia-01","animedia-02"}

def класс(r):
    if r["site_id"] in ПРОД:
        return "PRODUCTION"
    if r["site_id"] == "demo-books":
        return "DEMO"
    if r["environment"] == "test" or r["site_id"].startswith("synthetic"):
        return "SYNTHETIC_TEST"
    return "UNKNOWN"

классы = {}
синтетика = []
for r in записи:
    k = класс(r)
    классы[k] = классы.get(k, 0) + 1
    if k == "SYNTHETIC_TEST":
        # Происхождение: что есть в данных, и ничего сверх того.
        соб = [dict(e) for e in c.execute(
            "SELECT event_id, event_type, actor, correlation_id, occurred_at, "
            "published_at FROM outbox WHERE site_id=? ORDER BY seq",
            (r["site_id"],))]
        ауд = [dict(a) for a in c.execute(
            "SELECT at, actor, action FROM audit WHERE site_id=? ORDER BY id",
            (r["site_id"],))]
        синтетика.append({
            "site_id": r["site_id"], "environment": r["environment"],
            "lifecycle_state": r["lifecycle_state"],
            "canonical_domain": r["canonical_domain"],
            "created_at": r["created_at"], "updated_at": r["updated_at"],
            # Поля created_by и test_run_id в схеме ОТСУТСТВУЮТ. Вписать их
            # задним числом значило бы выдумать происхождение.
            "created_by_field_present": "created_by" in r,
            "test_run_id_field_present": "test_run_id" in r,
            "actor_from_audit": sorted({a["actor"] for a in ауд}) or None,
            "correlation_ids": sorted({e["correlation_id"] for e in соб}),
            "events": [e["event_type"] for e in соб],
            "events_in_outbox": len(соб),
            "unpublished_events": sum(1 for e in соб if not e["published_at"]),
            "presumed_origin": ("прогон N+1 контрактного теста; доказательство "
                                "косвенное — actor и correlation_id из аудита, "
                                "выделенного поля происхождения в схеме нет")})

backlog = c.execute("SELECT count(*) n FROM outbox WHERE published_at IS NULL"
                    ).fetchone()["n"]
слушателей = subprocess.run(["bash","-c","ss -lnt 2>/dev/null | grep -c 8790"],
                            capture_output=True, text=True).stdout.strip()

итог = {"captured_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "backup_path": str(копия), "backup_sha256": сумма_копии,
        "B_unfiltered_count": len(записи), "S_site_ids": ids, "H_checksum": H,
        "production_active": len(prod), "outbox_backlog": backlog,
        "listeners_8790": int(слушателей or 0),
        "classification": классы, "synthetic_records": синтетика}
ОТЧЁТ.parent.mkdir(parents=True, exist_ok=True)
ОТЧЁТ.write_text(json.dumps(итог, ensure_ascii=False, indent=1), encoding="utf-8")

print("BASELINE")
print("  B (всего записей):", len(записи))
print("  H (checksum S):   ", H[:32])
print("  production ACTIVE:", len(prod))
print("  outbox backlog:   ", backlog, " слушателей:", слушателей)
print("  классификация:    ", классы)
print("  backup:", копия.name, сумма_копии[:16])
print("\n  синтетические записи:")
for s in синтетика:
    print("   %-26s %-6s %-9s создана %s" % (
        s["site_id"], s["environment"], s["lifecycle_state"], s["created_at"]))
    print("      события: %s; в outbox %d, неопубликованных %d" % (
        ",".join(s["events"]), s["events_in_outbox"], s["unpublished_events"]))
    print("      actor: %s; полей created_by/test_run_id в схеме: %s/%s" % (
        s["actor_from_audit"], s["created_by_field_present"],
        s["test_run_id_field_present"]))
