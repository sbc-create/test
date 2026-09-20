"""Release batch state machine + atomic checkpoint."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SITE_STATES = (
    "PLANNED",
    "PREFLIGHT",
    "BUILT",
    "ARTIFACT_VERIFIED",
    "ROLLBACK_PREPARED",
    "STAGED",
    "RESTART_REQUESTED",
    "RUNTIME_WAIT",
    "RUNTIME_VERIFIED",
    "SMOKE_RUN_1",
    "SMOKE_RUN_2",
    "POST_DEPLOY_PASS",
    "FAILED",
    "ROLLED_BACK",
)

GLOBAL_STATES = (
    "BATCH_PLANNED",
    "CANARY_RUNNING",
    "CANARY_PASS",
    "SITES_RUNNING",
    "BATCH_PASS",
    "BATCH_PARTIAL",
    "BATCH_FAILED",
)

# Allowed site transitions (from → frozenset(to))
_SITE_TRANSITIONS: dict[str, frozenset[str]] = {
    "PLANNED": frozenset({"PREFLIGHT", "FAILED"}),
    "PREFLIGHT": frozenset({"BUILT", "FAILED"}),
    "BUILT": frozenset({"ARTIFACT_VERIFIED", "FAILED"}),
    "ARTIFACT_VERIFIED": frozenset({"ROLLBACK_PREPARED", "FAILED"}),
    "ROLLBACK_PREPARED": frozenset({"STAGED", "FAILED"}),
    "STAGED": frozenset({"RESTART_REQUESTED", "FAILED"}),
    "RESTART_REQUESTED": frozenset({"RUNTIME_WAIT", "FAILED"}),
    "RUNTIME_WAIT": frozenset({"RUNTIME_VERIFIED", "FAILED"}),
    "RUNTIME_VERIFIED": frozenset({"SMOKE_RUN_1", "FAILED"}),
    "SMOKE_RUN_1": frozenset({"SMOKE_RUN_2", "FAILED"}),
    "SMOKE_RUN_2": frozenset({"POST_DEPLOY_PASS", "FAILED"}),
    "POST_DEPLOY_PASS": frozenset(),
    "FAILED": frozenset({"ROLLED_BACK"}),
    "ROLLED_BACK": frozenset(),
}


class StateError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SiteCheckpoint:
    site_id: str
    stage: str = "PLANNED"
    attempts: dict[str, int] = field(default_factory=dict)
    notes: dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchCheckpoint:
    release_id: str
    global_state: str = "BATCH_PLANNED"
    active_site_id: str | None = None
    sites: dict[str, SiteCheckpoint] = field(default_factory=dict)
    updated_at: str = field(default_factory=_now)
    events: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "release_id": self.release_id,
            "global_state": self.global_state,
            "active_site_id": self.active_site_id,
            "sites": {
                sid: {
                    "site_id": sc.site_id,
                    "stage": sc.stage,
                    "attempts": sc.attempts,
                    "notes": sc.notes,
                }
                for sid, sc in self.sites.items()
            },
            "updated_at": self.updated_at,
            "events": list(self.events),
        }


def new_checkpoint(release_id: str, site_ids: list[str]) -> BatchCheckpoint:
    return BatchCheckpoint(
        release_id=release_id,
        sites={sid: SiteCheckpoint(site_id=sid) for sid in site_ids},
    )


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            try:
                os.unlink(tmp_name)
            except OSError:
                pass


def save_checkpoint(path: Path, checkpoint: BatchCheckpoint) -> None:
    checkpoint.updated_at = _now()
    atomic_write_json(path, checkpoint.as_dict())


def load_checkpoint(path: Path) -> BatchCheckpoint:
    data = json.loads(path.read_text(encoding="utf-8"))
    sites = {
        sid: SiteCheckpoint(
            site_id=row["site_id"],
            stage=row["stage"],
            attempts=dict(row.get("attempts") or {}),
            notes=dict(row.get("notes") or {}),
        )
        for sid, row in (data.get("sites") or {}).items()
    }
    return BatchCheckpoint(
        release_id=data["release_id"],
        global_state=data.get("global_state", "BATCH_PLANNED"),
        active_site_id=data.get("active_site_id"),
        sites=sites,
        updated_at=data.get("updated_at", _now()),
        events=list(data.get("events") or []),
    )


def transition_site(checkpoint: BatchCheckpoint, site_id: str, new_stage: str, **notes: Any) -> None:
    if new_stage not in SITE_STATES:
        raise StateError(f"unknown site stage: {new_stage}")
    site = checkpoint.sites[site_id]
    allowed = _SITE_TRANSITIONS.get(site.stage, frozenset())
    if new_stage != site.stage and new_stage not in allowed:
        raise StateError(f"illegal transition {site.stage} → {new_stage} for {site_id}")
    # Concurrency=1: only one site may be in deploy/restart window.
    deploy_window = {
        "STAGED",
        "RESTART_REQUESTED",
        "RUNTIME_WAIT",
        "RUNTIME_VERIFIED",
        "SMOKE_RUN_1",
        "SMOKE_RUN_2",
    }
    if new_stage in deploy_window:
        for other_id, other in checkpoint.sites.items():
            if other_id != site_id and other.stage in deploy_window:
                raise StateError(
                    f"RELEASE_CONCURRENCY=1 violated: {other_id} still in {other.stage}"
                )
        checkpoint.active_site_id = site_id
    site.stage = new_stage
    if notes:
        site.notes.update(notes)
    checkpoint.events.append(
        {"at": _now(), "site_id": site_id, "stage": new_stage, "notes": notes}
    )


def transition_global(checkpoint: BatchCheckpoint, new_state: str) -> None:
    if new_state not in GLOBAL_STATES:
        raise StateError(f"unknown global state: {new_state}")
    checkpoint.global_state = new_state
    checkpoint.events.append({"at": _now(), "global_state": new_state})


def site_done(stage: str) -> bool:
    return stage in {"POST_DEPLOY_PASS", "ROLLED_BACK"}


def pending_sites(checkpoint: BatchCheckpoint, ordered_ids: list[str]) -> list[str]:
    """Sites that still need work for idempotent resume."""
    out: list[str] = []
    for sid in ordered_ids:
        stage = checkpoint.sites[sid].stage
        if stage == "POST_DEPLOY_PASS":
            continue
        if stage == "ROLLED_BACK":
            continue
        out.append(sid)
    return out
