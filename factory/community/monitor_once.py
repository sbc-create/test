"""Read-only monitor tick: integrity, aggregate mismatch, kill gates."""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from factory.community import metrics
from factory.community.rollout import load_flags, trigger_kill_switch
from factory.ratings.prod_db import resolve_canonical_db

REPORT_DIR = Path("/srv/site-factory/repo/var/ratings/monitor")


def run() -> dict:
    db = Path(resolve_canonical_db())
    flags = load_flags()
    report: dict = {
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "db": str(db),
        "flags": {
            "PUBLIC_WRITE_ENABLED": flags.PUBLIC_WRITE_ENABLED,
            "PUBLIC_WRITE_ROLLOUT_PERCENT": flags.PUBLIC_WRITE_ROLLOUT_PERCENT,
            "KILL_SWITCH": flags.KILL_SWITCH,
        },
    }
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        integ = c.execute("pragma integrity_check").fetchone()[0]
        fk = c.execute("pragma foreign_key_check").fetchall()
        mismatches = 0
        for row in c.execute(
            "select rating_space_id, subject_id, vote_sum, vote_count from community_aggregates"
        ):
            s, n = c.execute(
                """select coalesce(sum(score),0), count(*) from community_votes
                   where rating_space_id=? and subject_id=? and status='ACCEPTED'
                   and dimension='overall'""",
                (row[0], row[1]),
            ).fetchone()
            if int(s) != int(row[2]) or int(n) != int(row[3]):
                mismatches += 1
        cross = c.execute(
            """select count(*) from community_votes
               where rating_space_id='animedia'
               and actor_id in (
                 select actor_id from community_votes where rating_space_id='yummy'
               ) and status='ACCEPTED'"""
        ).fetchone()[0]
        # crude: identities that wrote both spaces in same stage — still useful signal
        report.update(
            {
                "SQLITE_INTEGRITY_CHECK": integ,
                "FOREIGN_KEY_FAILURES": len(fk),
                "AGGREGATE_REBUILD_MISMATCHES": mismatches,
                "CROSS_SPACE_IDENTITY_OVERLAP_ACCEPTED": cross,
            }
        )
    finally:
        c.close()

    snap = metrics.snapshot(
        kill_switch_state=int(flags.KILL_SWITCH),
        rollout_percent=int(flags.PUBLIC_WRITE_ROLLOUT_PERCENT),
    )
    report["metrics"] = snap
    write_5xx = int(snap.get("write_5xx") or 0)
    attempts = int(snap.get("write_attempts") or 0)
    rate = (100.0 * write_5xx / attempts) if attempts else 0.0
    kill_reason = None
    if mismatches > 0:
        kill_reason = "AGGREGATE_REBUILD_MISMATCHES"
    elif integ != "ok":
        kill_reason = "DB_CORRUPTION"
    elif len(fk) > 0:
        kill_reason = "FOREIGN_KEY_FAILURES"
    elif int(flags.PUBLIC_WRITE_ROLLOUT_PERCENT) > 1:
        kill_reason = "PUBLIC_WRITE_PERCENT > 1"
    elif write_5xx >= 3:
        kill_reason = "WRITE_5XX_COUNT >= 3"
    elif attempts >= 50 and rate > 2.0:
        kill_reason = "WRITE_5XX_RATE_PERCENT > 2"

    if kill_reason and not flags.KILL_SWITCH:
        trigger_kill_switch(kill_reason)
        report["KILL_SWITCH_TRIGGERED"] = 1
        report["KILL_SWITCH_REASON"] = kill_reason
    else:
        report["KILL_SWITCH_TRIGGERED"] = 0

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORT_DIR / f"monitor-{report['at'].replace(':', '')}.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    latest = REPORT_DIR / "latest.json"
    latest.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    report["report_path"] = str(out)
    return report


def main() -> int:
    rep = run()
    print(json.dumps({"ok": True, "kill": rep.get("KILL_SWITCH_TRIGGERED"), "path": rep.get("report_path")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
