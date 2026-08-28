"""Audit records, before/after snapshots and rollback payloads.

Every mutation the operator performs is representable as a Change. A Change is
not applied unless it carries enough information to be undone, which is why
``rollback_payload`` is computed at construction time from the *observed*
before-state rather than from an assumption about it.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


class ChangeStatus(str, Enum):
    PROPOSED = "proposed"
    DRY_RUN = "dry_run"
    APPLIED = "applied"
    ROLLED_BACK = "rolled_back"
    REJECTED = "rejected"


class ChangeKind(str, Enum):
    TITLE = "title"
    DESCRIPTION = "description"
    H1 = "h1"
    INTRO = "intro"
    SYNOPSIS = "synopsis"
    FAQ = "faq"
    NAVIGATION = "navigation"
    INTERNAL_LINKS = "internal_links"
    HOMEPAGE_BLOCK = "homepage_block"
    COLLECTION = "collection"
    PIN = "pin"
    ANNOUNCEMENT = "announcement"
    CANONICAL = "canonical"
    ROBOTS = "robots"
    SITEMAP = "sitemap"


# Tenant-owned editorial fields. A catalogue sync must never overwrite these;
# see tests/operator/test_editorial.py::test_manual_fields_survive_sync.
TENANT_EDITORIAL_FIELDS = frozenset(
    {
        "title",
        "description",
        "h1",
        "intro",
        "synopsis",
        "faq",
        "editor_note",
        "collection_membership",
        "homepage_pin",
    }
)


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()
    ).hexdigest()[:16]


@dataclass
class Snapshot:
    """Immutable record of a field's value at a point in time."""

    site_id: str
    entity_id: str
    field_name: str
    value: Any
    taken_at: str = field(default_factory=utcnow)

    @property
    def digest(self) -> str:
        return _digest(self.value)

    def to_dict(self) -> dict:
        return {**asdict(self), "digest": self.digest}


@dataclass
class Change:
    """One reversible mutation."""

    site_id: str
    entity_id: str
    kind: ChangeKind
    field_name: str
    before: Any
    after: Any
    reason: str
    experiment_id: str | None = None
    change_id: str = field(default_factory=lambda: new_id("chg"))
    status: ChangeStatus = ChangeStatus.PROPOSED
    created_at: str = field(default_factory=utcnow)
    source: str | None = None

    def __post_init__(self) -> None:
        if not self.reason:
            raise ValueError("a change without a reason is not auditable")
        if self.before == self.after:
            raise ValueError("no-op change: before equals after")

    @property
    def before_snapshot(self) -> Snapshot:
        return Snapshot(self.site_id, self.entity_id, self.field_name, self.before)

    @property
    def after_snapshot(self) -> Snapshot:
        return Snapshot(self.site_id, self.entity_id, self.field_name, self.after)

    @property
    def rollback_payload(self) -> dict:
        """Exactly what must be written to undo this change."""
        return {
            "change_id": self.change_id,
            "site_id": self.site_id,
            "entity_id": self.entity_id,
            "field_name": self.field_name,
            "restore_value": self.before,
            "expected_current_digest": _digest(self.after),
            "experiment_id": self.experiment_id,
        }

    def to_record(self) -> dict:
        return {
            "change_id": self.change_id,
            "experiment_id": self.experiment_id,
            "site_id": self.site_id,
            "entity_id": self.entity_id,
            "kind": self.kind.value,
            "field_name": self.field_name,
            "status": self.status.value,
            "created_at": self.created_at,
            "reason": self.reason,
            "source": self.source,
            "before": self.before_snapshot.to_dict(),
            "after": self.after_snapshot.to_dict(),
            "rollback_payload": self.rollback_payload,
        }


class ConflictError(RuntimeError):
    """Raised when the live value is not what the rollback expects."""


class AuditLog:
    """Append-only JSONL audit log."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: dict) -> None:
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    def records(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [
            json.loads(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def by_experiment(self, experiment_id: str) -> list[dict]:
        return [r for r in self.records() if r.get("experiment_id") == experiment_id]


def apply_rollback(payload: dict, current_value: Any, *, strict: bool = True) -> Any:
    """Return the value to write back, verifying the world has not moved on.

    ``strict`` rollback refuses to clobber a value that someone else changed
    after the operator wrote it. That is the safe default: a human edit must win
    over an automatic revert.
    """
    if strict and _digest(current_value) != payload["expected_current_digest"]:
        raise ConflictError(
            f"{payload['entity_id']}.{payload['field_name']}: значение изменилось после "
            "записи оператором — откат отменён, чтобы не затереть более свежую правку"
        )
    return payload["restore_value"]


def protect_tenant_fields(incoming: dict, existing: dict) -> dict:
    """Merge a catalogue sync without touching tenant-owned editorial fields."""
    merged = dict(existing)
    for key, value in incoming.items():
        if key in TENANT_EDITORIAL_FIELDS and existing.get(key) not in (None, "", []):
            continue  # manual editorial value wins
        merged[key] = value
    return merged
