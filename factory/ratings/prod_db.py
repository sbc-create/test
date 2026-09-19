"""Canonical production ratings DB path resolution and migration gates."""

from __future__ import annotations

import hashlib
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from factory.paths import PATHS

# Authoritative path from systemd ReadWritePaths=.../var/ratings
SRV_RATINGS_DIR = Path("/srv/site-factory/repo/var/ratings")
CANONICAL_DB_NAME = "ratings.sqlite"


def resolve_canonical_db() -> Path:
    """Resolve canonical ratings DB. Prefer host systemd path; else worktree var/."""
    srv = SRV_RATINGS_DIR / CANONICAL_DB_NAME
    if SRV_RATINGS_DIR.is_dir() and os_accessible(SRV_RATINGS_DIR):
        return srv
    return PATHS.root / "var" / "ratings" / CANONICAL_DB_NAME


def os_accessible(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def schema_inventory(db_path: Path) -> dict[str, Any]:
    if not db_path.is_file():
        return {"exists": False, "tables": [], "migrations": []}
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    tables = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
    ]
    migrations = []
    if "schema_migrations" in tables:
        migrations = [
            dict(r)
            for r in conn.execute(
                "SELECT version, description, applied_at FROM schema_migrations ORDER BY version"
            )
        ]
    counts = {}
    for t in tables:
        if t.startswith("sqlite_"):
            continue
        try:
            counts[t] = conn.execute(f"SELECT COUNT(*) AS c FROM {t}").fetchone()[0]
        except sqlite3.Error:
            counts[t] = None
    conn.close()
    return {"exists": True, "path": str(db_path), "tables": tables, "migrations": migrations, "counts": counts}


def backup_db(db_path: Path, backup_dir: Path) -> dict[str, Any]:
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if not db_path.is_file():
        empty = backup_dir / f"ratings.empty.{ts}.marker"
        empty.write_text("no db yet\n", encoding="utf-8")
        return {"status": "NO_DB_YET", "marker": str(empty)}
    dest = backup_dir / f"ratings.sqlite.{ts}.bak"
    shutil.copy2(db_path, dest)
    digest = hashlib.sha256(dest.read_bytes()).hexdigest()
    # verify copy
    assert hashlib.sha256(db_path.read_bytes()).hexdigest() == digest
    return {"status": "OK", "path": str(dest), "sha256": digest, "bytes": dest.stat().st_size}


def apply_migrations(db_path: Path) -> dict[str, Any]:
    """Apply 0002/0003/0004 via RatingsStore init (transactional per migration module)."""
    from factory.ratings.store import RatingsStore

    before = schema_inventory(db_path)
    store = RatingsStore(db_path)
    after = schema_inventory(db_path)
    store.close()
    return {"before": before, "after": after, "db_path": str(db_path)}


def rollback_copy_proof(backup_path: Path, scratch_path: Path) -> dict[str, Any]:
    """Restore backup onto isolated scratch and confirm it opens."""
    scratch_path.parent.mkdir(parents=True, exist_ok=True)
    if backup_path.suffix == ".marker" or not backup_path.is_file() or backup_path.stat().st_size < 100:
        # empty DB case — create fresh store on scratch then discard
        from factory.ratings.store import RatingsStore

        if scratch_path.exists():
            scratch_path.unlink()
        store = RatingsStore(scratch_path)
        ok = schema_inventory(scratch_path)
        store.close()
        return {"status": "EMPTY_BASELINE_OK", "scratch": str(scratch_path), "schema": ok}
    shutil.copy2(backup_path, scratch_path)
    conn = sqlite3.connect(str(scratch_path))
    n = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
    conn.close()
    return {"status": "RESTORED_OK", "scratch": str(scratch_path), "tables": n}
