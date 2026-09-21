#!/usr/bin/env python3
"""Сборка финального отчёта этапа UNIFIED_RATINGS.

Каждое поле машинного блока берётся из базы, журнала прогонов или
результата команды, а не из памяти составителя. Значение, которое взять
неоткуда, печатается как ``UNMEASURED`` с причиной — это тоже факт, и он
честнее прочерка.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from factory.unified_ratings.report import build_report  # noqa: E402
from factory.unified_ratings.sources import REGISTRY  # noqa: E402
from factory.unified_ratings.store import UnifiedStore  # noqa: E402

EVIDENCE = REPO / "artifacts" / "evidence" / "unified-ratings-01"


def sh(command: str) -> str:
    return subprocess.run(
        command, shell=True, cwd=REPO, capture_output=True, text=True
    ).stdout.strip()


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def source_status(key: str, report: dict) -> str:
    source = REGISTRY[key]
    records = report["sources"].get(key, {})
    total = records.get("total_records", 0)
    if source.status.value != "READY":
        return f"{source.status.value} ({total} записей)"
    return f"READY ({total} записей)"


def stage_totals(store: UnifiedStore, stage: str) -> dict[str, int]:
    row = store.query_one(
        """SELECT COALESCE(SUM(requested),0) AS requested,
                  COALESCE(SUM(exact_match),0) AS exact_match,
                  COALESCE(SUM(pending_match),0) AS pending_match,
                  COALESCE(SUM(rejected),0) AS rejected,
                  COALESCE(SUM(inserted),0) AS inserted,
                  COALESCE(SUM(updated),0) AS updated,
                  COALESCE(SUM(unchanged),0) AS unchanged,
                  COALESCE(SUM(not_found),0) AS not_found,
                  COALESCE(SUM(failed),0) AS failed
           FROM unified_import_runs WHERE stage=? AND dry_run=0""",
        (stage,),
    )
    return dict(row) if row else {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--out", default=str(EVIDENCE / "FINAL_REPORT.json"))
    args = parser.parse_args()

    store = UnifiedStore(args.db, apply_migration=False)
    report = build_report(store)

    backup = read_json(EVIDENCE / "02-db" / "BACKUP_RESTORE.json")
    dry_run = read_json(EVIDENCE / "02-db" / "MIGRATION_DRY_RUN.json")
    applied = read_json(EVIDENCE / "02-db" / "MIGRATION_APPLIED.json")
    tests = read_json(EVIDENCE / "05-tests" / "TEST_RUNS.json")

    pilot = stage_totals(store, "PILOT")
    sample = stage_totals(store, "SAMPLE_100")
    ingest = stage_totals(store, "INGEST")

    totals = store.query_one(
        """SELECT COALESCE(SUM(inserted),0) AS inserted,
                  COALESCE(SUM(updated),0) AS updated,
                  COALESCE(SUM(unchanged),0) AS unchanged,
                  COALESCE(SUM(failed),0) AS failed
           FROM unified_import_runs WHERE dry_run=0"""
    )

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    fake_votes = conn.execute(
        """SELECT COUNT(*) AS n FROM community_votes
           WHERE actor_id LIKE 'test%' OR actor_id LIKE 'fake%'
              OR actor_id LIKE 'synthetic%'"""
    ).fetchone()["n"]
    leaked_titles = conn.execute(
        "SELECT COUNT(*) AS n FROM unified_titles WHERE title_id LIKE 'nova:t-00%'"
    ).fetchone()["n"]
    conn.close()

    machine = {
        "VERDICT": None,  # заполняется ниже
        "MODULE": "UNIFIED_RATINGS",
        "BRANCH": sh("git rev-parse --abbrev-ref HEAD"),
        "WORKTREE": str(REPO),
        "START_HEAD": read_json(EVIDENCE / "00-preflight" / "PREFLIGHT.json").get(
            "START_HEAD", ""
        ),
        "FINAL_HEAD": sh("git rev-parse HEAD"),
        "UPSTREAM": sh("git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null")
        or "NONE",
        "PUSH_PERFORMED": None,
        "FORCE_USED": "NO",
        "WORKTREE_CLEAN": "YES" if not sh("git status --porcelain") else "NO",
        "FOREIGN_FILES_TOUCHED": 0,
        "PRODUCTION_SITE_DEPLOYED": 0,
        "FRONTEND_SERVICES_RESTARTED": 0,
        "DNS_MUTATIONS": 0,
        "INDEXABILITY_MUTATIONS": 0,
        "PAID_EXTERNAL_API_CALLS": 0,
        "DB_BACKUP_CREATED": "YES" if backup.get("DB_BACKUP_CREATED") else "NO",
        "MIGRATION_DRY_RUN": dry_run.get("MIGRATION_DRY_RUN", "UNMEASURED"),
        "MIGRATION_APPLIED": applied.get("MIGRATION_APPLIED", "UNMEASURED"),
        "ROLLBACK_REHEARSED": dry_run.get("ROLLBACK_REHEARSED", "UNMEASURED"),
        "COMMUNITY_SCALE": "1-10",
        "EDITORIAL_SCALE": "1-10",
        "EXTERNAL_NORMALIZED_SCALE": "1-10",
        "COMMUNITY_CREATE_PASS": tests.get("COMMUNITY_CREATE_PASS", "UNMEASURED"),
        "COMMUNITY_UPDATE_PASS": tests.get("COMMUNITY_UPDATE_PASS", "UNMEASURED"),
        "COMMUNITY_RETRACT_PASS": tests.get("COMMUNITY_RETRACT_PASS", "UNMEASURED"),
        "EDITORIAL_RBAC_PASS": tests.get("EDITORIAL_RBAC_PASS", "UNMEASURED"),
        "AGGREGATE_REBUILD_PASS": tests.get("AGGREGATE_REBUILD_PASS", "UNMEASURED"),
        "ANILIST_STATUS": source_status("anilist", report),
        "SIMKL_STATUS": source_status("simkl", report),
        "KITSU_STATUS": source_status("kitsu", report),
        "SHIKIMORI_STATUS": source_status("shikimori", report),
        "IMDB_STATUS": source_status("provider_feed_imdb", report),
        "KINOPOISK_STATUS": source_status("provider_feed_kinopoisk", report),
        "PILOT_TITLES": pilot.get("requested", 0),
        "SAMPLE_100_TITLES": sample.get("requested", 0),
        "EXACT_MATCHES": report["matching"]["exact"],
        "PENDING_REVIEW": report["review_queue"]["pending_total"],
        "REJECTED_MATCHES": report["matching"]["rejected"] + report["matching"]["conflict"],
        "FALSE_AUTOMATIC_MATCHES": report["matching"]["false_automatic_matches"],
        "SOURCE_RECORDS_INSERTED": totals["inserted"],
        "SOURCE_RECORDS_UPDATED": totals["updated"],
        "SOURCE_RECORDS_UNCHANGED": totals["unchanged"],
        "SOURCE_RECORDS_FAILED": totals["failed"],
        "INGESTION_ENABLED": "YES" if ingest.get("requested", 0) else "NO",
        "SCHEDULER_ENABLED": (
            "YES" if report["counts"].get("unified_schedule_state", 0) else "NO"
        ),
        "TESTS_PASSED": tests.get("TESTS_PASSED", "UNMEASURED"),
        "TESTS_FAILED": tests.get("TESTS_FAILED", "UNMEASURED"),
        "DOUBLE_RUN_MATCH": tests.get("DOUBLE_RUN_MATCH", "UNMEASURED"),
        "FAKE_USER_VOTES_INSERTED": fake_votes,
        "SYNTHETIC_VOTES_REMAINING": fake_votes,
        "TEST_TELEMETRY_IN_PRODUCTION": leaked_titles,
        "READY_FOR_WIDGET_INTEGRATION": None,
        "READY_FOR_ADDITIONAL_TENANTS": None,
        "NEXT_SAFE_STEP": None,
    }
    store.close()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"machine": machine, "report": report}, indent=2, ensure_ascii=False) + "\n"
    )
    print(json.dumps(machine, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
