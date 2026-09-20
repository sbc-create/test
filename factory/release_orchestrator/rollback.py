"""Rollback prepare with digest + rehearsal before deploy."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


class RollbackError(ValueError):
    pass


REQUIRED_MARKERS = ("CURRENT", "version.json")


@dataclass
class RollbackPrep:
    site_id: str
    backup_path: str
    digest: str
    rollback_prepared: int
    rollback_digest_match: int
    rollback_rehearsal_pass: int


def _sha256_tree(root: Path) -> str:
    h = hashlib.sha256()
    if not root.exists():
        h.update(b"EMPTY")
        return h.hexdigest()
    files = sorted(p for p in root.rglob("*") if p.is_file())
    for path in files:
        rel = path.relative_to(root).as_posix().encode("utf-8")
        h.update(rel)
        h.update(b"\0")
        h.update(path.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def prepare_rollback(
    *,
    site_id: str,
    live_root: Path,
    backup_root: Path,
    required_files: Iterable[str] = REQUIRED_MARKERS,
) -> RollbackPrep:
    if not live_root.exists():
        raise RollbackError(f"live root missing for {site_id}: {live_root}")
    backup_root.mkdir(parents=True, exist_ok=True)
    target = backup_root / site_id
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(live_root, target)
    for name in required_files:
        if not (target / name).exists():
            raise RollbackError(f"rollback backup missing required files: {[name]}")

    # Digest after required files are present; write marker afterward without
    # including it in the compared tree hash.
    content_digest = _sha256_tree(target)
    (target / "ROLLBACK_DIGEST").write_text(content_digest + "\n", encoding="utf-8")

    missing = [name for name in required_files if not (target / name).exists()]
    if missing:
        raise RollbackError(f"rollback backup missing required files: {missing}")

    # Rehearsal: restore into a temp sibling and compare content digest
    # (excluding the marker file written after hashing).
    rehearsal = backup_root / f"{site_id}.rehearsal"
    if rehearsal.exists():
        shutil.rmtree(rehearsal)
    shutil.copytree(target, rehearsal)
    for name in required_files:
        if not (rehearsal / name).exists():
            raise RollbackError(f"rehearsal missing {name}")
    marker = rehearsal / "ROLLBACK_DIGEST"
    if marker.exists():
        marker.unlink()
    rehearsal_digest = _sha256_tree(rehearsal)
    match = 1 if rehearsal_digest == content_digest else 0
    if not match:
        raise RollbackError("ROLLBACK_DIGEST_MATCH failed")
    meta = {
        "site_id": site_id,
        "backup_path": str(target),
        "digest": content_digest,
        "ROLLBACK_PREPARED": 1,
        "ROLLBACK_DIGEST_MATCH": 1,
        "ROLLBACK_REHEARSAL_PASS": 1,
    }
    (target / "rollback.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return RollbackPrep(
        site_id=site_id,
        backup_path=str(target),
        digest=content_digest,
        rollback_prepared=1,
        rollback_digest_match=1,
        rollback_rehearsal_pass=1,
    )


def restore_from_backup(backup_path: Path, live_root: Path) -> None:
    if not backup_path.exists():
        raise RollbackError(f"backup missing: {backup_path}")
    if live_root.exists():
        shutil.rmtree(live_root)
    shutil.copytree(backup_path, live_root)
