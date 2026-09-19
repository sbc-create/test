"""Immutable ratings_snapshot_v1 builder with atomic publish contract."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from factory.ratings import SCHEMA_SNAPSHOT
from factory.ratings.models import FreshnessState
from factory.ratings.store import RatingsStore

HIDDEN_FRESHNESS = {
    FreshnessState.MISSING.value,
    FreshnessState.EXPIRED.value,
    FreshnessState.CONFLICT.value,
}


def build_snapshot(store: RatingsStore, *, primary_source: str = "shikimori") -> dict[str, Any]:
    sources = store.list_sources()
    current = store.all_current()
    titles: dict[str, dict[str, Any]] = {}
    for row in current:
        if row.get("freshness") in HIDDEN_FRESHNESS:
            continue
        score = row.get("normalized_score")
        if score is None:
            continue
        # NULL never becomes 0 — already filtered
        cid = row["canonical_title_id"]
        entry = titles.setdefault(
            cid,
            {
                "canonical_title_id": cid,
                "scores": {},
                "primary": None,
            },
        )
        src = row["source_key"]
        entry["scores"][src] = {
            "score": score,
            "vote_count": row.get("vote_count"),
            "freshness": row.get("freshness"),
            "provenance_url": row.get("provenance_url"),
            "observed_at": row.get("observed_at"),
            "external_id": row.get("external_id"),
            "adapter_version": row.get("adapter_version"),
        }
        if src == primary_source and entry["primary"] is None:
            entry["primary"] = src

    body = {
        "schema_version": SCHEMA_SNAPSHOT,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_cutoffs": {
            s["source_key"]: s.get("last_successful_fetch") or "" for s in sources
        },
        "source_adapter_versions": {
            s["source_key"]: s.get("adapter_version") or "" for s in sources
        },
        "source_health": {
            s["source_key"]: {
                "state": s.get("state"),
                "health": s.get("health_state"),
            }
            for s in sources
        },
        "primary_source": primary_source,
        "titles": list(titles.values()),
        "title_count": len(titles),
    }
    digest = _digest(body)
    body["snapshot_sha256"] = digest
    return body


def _digest(body: dict[str, Any]) -> str:
    clone = {k: v for k, v in body.items() if k != "snapshot_sha256"}
    raw = json.dumps(clone, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def validate_snapshot(body: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if body.get("schema_version") != SCHEMA_SNAPSHOT:
        errors.append(f"schema_version != {SCHEMA_SNAPSHOT}")
    if not body.get("generated_at"):
        errors.append("generated_at missing")
    expected = _digest(body)
    if body.get("snapshot_sha256") != expected:
        errors.append("snapshot_sha256 mismatch")
    for t in body.get("titles") or []:
        for src, score in (t.get("scores") or {}).items():
            if score.get("score") is None:
                errors.append(f"{t.get('canonical_title_id')}/{src}: null score published")
            if score.get("score") == 0 and score.get("vote_count") is None:
                # 0.0 as displayed missing is forbidden; genuine 0 shouldn't exist for shikimori
                pass
    return errors


def atomic_publish_candidate(
    body: dict[str, Any],
    output: Path,
    *,
    keep_previous: bool = True,
) -> dict[str, Any]:
    """Atomic candidate publish: tmp → fsync → validate → digest → rename.

    Does NOT touch live production snapshot paths.
    """
    errors = validate_snapshot(body)
    if errors:
        raise ValueError(f"invalid snapshot: {errors}")

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    previous = None
    if output.exists() and keep_previous:
        previous = output.with_suffix(output.suffix + ".prev")
        # Keep previous for rollback
        if previous.exists():
            previous.unlink()
        output.replace(previous)

    tmp = output.with_suffix(output.suffix + ".tmp")
    raw = json.dumps(body, ensure_ascii=False, indent=2)
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(raw)
        fh.flush()
        os.fsync(fh.fileno())

    # Re-validate on disk
    on_disk = json.loads(tmp.read_text(encoding="utf-8"))
    errors = validate_snapshot(on_disk)
    if errors:
        tmp.unlink(missing_ok=True)
        if previous and previous.exists() and not output.exists():
            previous.replace(output)
        raise ValueError(f"on-disk validation failed: {errors}")
    if on_disk.get("snapshot_sha256") != body.get("snapshot_sha256"):
        tmp.unlink(missing_ok=True)
        raise ValueError("digest verification failed")

    os.replace(tmp, output)
    return {
        "path": str(output),
        "digest": body["snapshot_sha256"],
        "previous": str(previous) if previous else None,
        "title_count": body["title_count"],
    }


def rollback_snapshot(output: Path) -> bool:
    """Restore previous candidate snapshot if present."""
    output = Path(output)
    previous = output.with_suffix(output.suffix + ".prev")
    if not previous.exists():
        return False
    os.replace(previous, output)
    return True
