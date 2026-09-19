"""Qwen delivery: durable outbox + dry-run receipt (no invented endpoints)."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from factory.ratings.qwen_report import QWEN_PERMISSIONS, sanitize_report
from factory.ratings.secrets import redact_headers

OUTBOX_SCHEMA = "qwen_delivery_outbox_v1"
CONFIG_ENV_KEYS = (
    "QWEN_DELIVERY_ENDPOINT",
    "QWEN_DELIVERY_TOKEN_FILE",
    "QWEN_DELIVERY_MODE",  # dry_run | http_post
)


def discover_config() -> dict[str, Any]:
    import os

    endpoint = os.environ.get("QWEN_DELIVERY_ENDPOINT", "").strip()
    token_file = os.environ.get("QWEN_DELIVERY_TOKEN_FILE", "").strip()
    mode = os.environ.get("QWEN_DELIVERY_MODE", "").strip() or ("http_post" if endpoint else "")
    configured = bool(endpoint and token_file and Path(token_file).is_file())
    return {
        "configured": configured,
        "endpoint_set": bool(endpoint),
        "token_file_set": bool(token_file),
        "token_file_exists": bool(token_file and Path(token_file).is_file()),
        "mode": mode or "unset",
        "QWEN_DELIVERY_CONFIGURED": "YES" if configured else "NO",
        "env_keys": list(CONFIG_ENV_KEYS),
        "note": "Do not invent endpoint/credentials; require ops-provided config",
    }


def ensure_outbox(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS qwen_delivery_outbox (
            dedupe_id TEXT PRIMARY KEY,
            report_id TEXT NOT NULL,
            cycle_id TEXT NOT NULL,
            payload_digest TEXT NOT NULL,
            status TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            receipt_json TEXT NOT NULL DEFAULT '{}',
            last_error TEXT NOT NULL DEFAULT ''
        )
        """
    )
    conn.commit()
    conn.close()


def _dedupe_id(cycle_id: str, report_id: str, digest: str) -> str:
    raw = f"{cycle_id}|{report_id}|{digest}"
    return hashlib.sha256(raw.encode()).hexdigest()


def enqueue_and_dry_run(
    *,
    outbox_db: Path,
    report: dict[str, Any],
    cycle_id: str,
) -> dict[str, Any]:
    """Validate, enqueue durable outbox, dry-run deliver (no network)."""
    ensure_outbox(outbox_db)
    clean = sanitize_report(dict(report))
    report_id = clean.get("report_id") or clean.get("run_id") or f"rpt-{uuid.uuid4().hex[:12]}"
    clean["report_id"] = report_id
    clean["cycle_id"] = cycle_id
    clean["qwen_permissions"] = QWEN_PERMISSIONS
    clean["QWEN_WRITE_PERMISSIONS"] = 0
    blob = json.dumps(clean, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256(blob.encode()).hexdigest()
    dedupe = _dedupe_id(cycle_id, report_id, digest)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    conn = sqlite3.connect(str(outbox_db))
    existing = conn.execute(
        "SELECT status, receipt_json FROM qwen_delivery_outbox WHERE dedupe_id=?",
        (dedupe,),
    ).fetchone()
    if existing:
        conn.close()
        return {
            "dedupe_id": dedupe,
            "status": existing[0],
            "receipt": json.loads(existing[1] or "{}"),
            "duplicate": True,
            "QWEN_DRY_RUN_RECEIPT_PASS": existing[0] in ("DRY_RUN_ACK", "DELIVERED"),
        }

    cfg = discover_config()
    if not cfg["configured"]:
        receipt = {
            "ack": "DRY_RUN_NO_CONFIG",
            "at": now,
            "delivery": "BLOCKED_NO_CONFIG",
            "payload_digest": digest,
            "redacted_headers_example": redact_headers({"Authorization": "Bearer EXAMPLE"}),
        }
        status = "DRY_RUN_ACK"
    else:
        # Still dry-run in Stage 4 first launch unless mode explicitly dry_run
        receipt = {
            "ack": "DRY_RUN_CONFIGURED_BUT_NOT_LIVE",
            "at": now,
            "delivery": "DRY_RUN",
            "payload_digest": digest,
            "endpoint_configured": True,
        }
        status = "DRY_RUN_ACK"

    conn.execute(
        """INSERT INTO qwen_delivery_outbox
           (dedupe_id, report_id, cycle_id, payload_digest, status, attempts, created_at, updated_at, receipt_json)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (dedupe, report_id, cycle_id, digest, status, 1, now, now, json.dumps(receipt)),
    )
    conn.commit()
    conn.close()
    return {
        "dedupe_id": dedupe,
        "report_id": report_id,
        "cycle_id": cycle_id,
        "payload_digest": digest,
        "status": status,
        "receipt": receipt,
        "duplicate": False,
        "config": cfg,
        "QWEN_DRY_RUN_RECEIPT_PASS": True,
        "QWEN_DELIVERY_CONFIGURED": cfg["QWEN_DELIVERY_CONFIGURED"],
        "QWEN_WRITE_PERMISSIONS": 0,
    }
