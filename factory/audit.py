"""Журнал операций, меняющих окружение.

Каждая запись: job ID, site ID, commit фабрики, actor, target, время, exit code и
redacted output. Журнал — append-only JSONL, пригодный для восстановления хронологии.
"""
from __future__ import annotations

import getpass
import json
import os
import subprocess
import time
from pathlib import Path

from factory.paths import PATHS
from factory.redaction import redact, redact_obj


def factory_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=PATHS.root, capture_output=True, text=True, timeout=10, check=False
        )
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def actor() -> str:
    for key in ("FACTORY_ACTOR", "SUDO_USER", "USER", "LOGNAME"):
        value = os.environ.get(key)
        if value:
            return value
    try:
        return getpass.getuser()
    except Exception:  # noqa: BLE001
        return "unknown"


def audit_file() -> Path:
    PATHS.audit.mkdir(parents=True, exist_ok=True)
    return PATHS.audit / "audit.jsonl"


def record(
    *,
    job_id: str,
    site_id: str,
    environment: str,
    action: str,
    target: str,
    exit_code: int | None = None,
    output: str = "",
    mutation: bool = False,
    extra: dict | None = None,
) -> dict:
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "job_id": job_id,
        "site_id": site_id,
        "environment": environment,
        "action": action,
        "target": target,
        "actor": actor(),
        "factory_commit": factory_commit(),
        "mutation": mutation,
        "exit_code": exit_code,
        "output": redact(output)[:8000],
    }
    if extra:
        entry["extra"] = redact_obj(extra)
    with audit_file().open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def read_all() -> list[dict]:
    path = audit_file()
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
