"""Comments kill switch — no-deploy capability flips + audit trail (goal §19)."""

from __future__ import annotations

import json
import os
import threading
import uuid
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from factory.community.store import CommunityStore

DEFAULT_FLAGS_PATH = Path(
    os.environ.get(
        "COMMUNITY_COMMENTS_KILL_SWITCH_PATH",
        "/srv/site-factory/repo/var/community_comments/kill_switch_flags.json",
    )
)
DEFAULT_AUDIT_JSONL = Path(
    os.environ.get(
        "COMMUNITY_COMMENTS_KILL_SWITCH_AUDIT_PATH",
        "/srv/site-factory/repo/var/community_comments/kill_switch_audit.jsonl",
    )
)

_lock = threading.RLock()


@dataclass
class KillSwitchCapabilities:
    block_writes: int = 0
    hide_new_public: int = 0
    force_pending_hidden: int = 0
    stop_worker: int = 0
    hide_module: int = 0
    keep_reading_approved: int = 1
    reason: str = ""
    updated_at: str = ""
    actor: str = ""


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def flags_path() -> Path:
    return Path(
        os.environ.get("COMMUNITY_COMMENTS_KILL_SWITCH_PATH", str(DEFAULT_FLAGS_PATH))
    )


def audit_jsonl_path() -> Path:
    return Path(
        os.environ.get(
            "COMMUNITY_COMMENTS_KILL_SWITCH_AUDIT_PATH", str(DEFAULT_AUDIT_JSONL)
        )
    )


def load_capabilities(path: Path | None = None) -> KillSwitchCapabilities:
    p = path or flags_path()
    with _lock:
        if not p.is_file():
            return KillSwitchCapabilities()
        raw = json.loads(p.read_text(encoding="utf-8"))
        allowed = {f.name for f in fields(KillSwitchCapabilities)}
        data = {k: raw[k] for k in allowed if k in raw}
        return KillSwitchCapabilities(**data)


def save_capabilities(
    caps: KillSwitchCapabilities,
    path: Path | None = None,
    *,
    actor: str = "operator",
    store: CommunityStore | None = None,
    detail: str = "",
) -> KillSwitchCapabilities:
    p = path or flags_path()
    caps.updated_at = _utc()
    caps.actor = actor
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(caps)
    with _lock:
        p.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        _append_audit(payload, action="save", actor=actor, detail=detail, store=store)
    return caps


def _append_audit(
    capabilities: dict[str, Any],
    *,
    action: str,
    actor: str,
    detail: str,
    store: CommunityStore | None,
) -> None:
    rec = {
        "audit_id": f"cks_{uuid.uuid4().hex}",
        "action": action,
        "capabilities": {
            k: capabilities.get(k)
            for k in (
                "block_writes",
                "hide_new_public",
                "force_pending_hidden",
                "stop_worker",
                "hide_module",
                "keep_reading_approved",
            )
        },
        "actor": actor,
        "detail": detail,
        "created_at": _utc(),
    }
    # Never put secrets in audit
    for banned in ("token", "password", "secret", "authorization"):
        rec.pop(banned, None)
    path = audit_jsonl_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    if store is not None:
        store.conn.execute(
            """INSERT INTO community_comment_kill_switch_audit
               (audit_id, action, capabilities_json, actor, detail, created_at)
               VALUES (?,?,?,?,?,?)""",
            (
                rec["audit_id"],
                action,
                json.dumps(rec["capabilities"], ensure_ascii=False),
                actor,
                detail,
                rec["created_at"],
            ),
        )


def drill_and_restore(
    *,
    path: Path | None = None,
    store: CommunityStore | None = None,
    actor: str = "drill",
) -> dict[str, Any]:
    """Supervised drill: flip all protective caps on, then restore defaults."""
    p = path or flags_path()
    before = load_capabilities(p)
    engaged = KillSwitchCapabilities(
        block_writes=1,
        hide_new_public=1,
        force_pending_hidden=1,
        stop_worker=1,
        hide_module=1,
        keep_reading_approved=1,
        reason="supervised_drill",
    )
    save_capabilities(engaged, p, actor=actor, store=store, detail="drill_engage")
    mid = load_capabilities(p)
    restored = KillSwitchCapabilities(
        block_writes=0,
        hide_new_public=0,
        force_pending_hidden=0,
        stop_worker=0,
        hide_module=0,
        keep_reading_approved=1,
        reason="drill_restore",
    )
    save_capabilities(restored, p, actor=actor, store=store, detail="drill_restore")
    after = load_capabilities(p)
    return {
        "before": asdict(before),
        "engaged": asdict(mid),
        "after": asdict(after),
        "restored": True,
        "audit_jsonl": str(audit_jsonl_path()),
    }
