"""Persistent rollout / kill-switch flags for community public writes."""

from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_FLAGS_PATH = Path(
    os.environ.get(
        "COMMUNITY_ROLLOUT_FLAGS_PATH",
        "/srv/site-factory/repo/var/ratings/community_rollout_flags.json",
    )
)

OWNER_APPROVAL_ID = "COMMUNITY-RATINGS-YUMMY-PUBLIC-WRITE-1PCT-20260920-01"
MAX_ROLLOUT_PERCENT_THIS_STAGE = 1


@dataclass
class RolloutFlags:
    PUBLIC_WRITE_ENABLED: int = 0
    PUBLIC_WRITE_ROLLOUT_PERCENT: int = 0
    PUBLIC_WRITE_MAX_PERCENT: int = MAX_ROLLOUT_PERCENT_THIS_STAGE
    KILL_SWITCH: int = 0
    READ_ONLY: int = 0
    PUBLIC_SCORE_MODE: str = "NATIVE_ONLY"
    IDENTITY_MODE: str = "SIGNED_PSEUDONYMOUS_DEVICE_V1"
    STRUCTURED_AGGREGATE_RATING_ENABLED: int = 0
    YUMMY_EXTERNAL_PRIOR_PUBLIC_DISPLAY: int = 0
    YUMMY_SHIKIMORI_PUBLIC_DISPLAY: int = 0
    YUMMY_DERIVED_RATING_PUBLIC_DISPLAY: int = 0
    ANIMEDIA_NATIVE_WRITE_CHANGE: int = 0
    COMMENTS_WRITE: int = 0
    COMMENTS_PUBLIC_READ: int = 0
    COMMENTS_SEO_RENDERING: int = 0
    OWNER_APPROVAL_ID: str = OWNER_APPROVAL_ID
    PUBLIC_WRITE_STARTED_AT: str = ""
    KILL_SWITCH_REASON: str = ""
    KILL_SWITCH_AT: str = ""
    updated_at: str = ""

    def clamp(self) -> "RolloutFlags":
        # Hard ceiling for this stage — never exceed 1% even if file is tampered.
        self.PUBLIC_WRITE_MAX_PERCENT = MAX_ROLLOUT_PERCENT_THIS_STAGE
        if self.PUBLIC_WRITE_ROLLOUT_PERCENT > MAX_ROLLOUT_PERCENT_THIS_STAGE:
            self.PUBLIC_WRITE_ROLLOUT_PERCENT = MAX_ROLLOUT_PERCENT_THIS_STAGE
        if self.KILL_SWITCH:
            self.PUBLIC_WRITE_ENABLED = 0
        return self


_lock = threading.RLock()


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def flags_path() -> Path:
    return Path(os.environ.get("COMMUNITY_ROLLOUT_FLAGS_PATH", str(DEFAULT_FLAGS_PATH)))


def load_flags(path: Path | None = None) -> RolloutFlags:
    p = path or flags_path()
    with _lock:
        if not p.is_file():
            return RolloutFlags().clamp()
        raw = json.loads(p.read_text(encoding="utf-8"))
        base = asdict(RolloutFlags())
        base.update({k: raw[k] for k in base if k in raw})
        return RolloutFlags(**base).clamp()


def save_flags(flags: RolloutFlags, path: Path | None = None) -> RolloutFlags:
    p = path or flags_path()
    flags = flags.clamp()
    flags.updated_at = _utc()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    payload = asdict(flags)
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(p)
    return flags


def enable_1pct_canary(*, started_at: str | None = None) -> RolloutFlags:
    flags = load_flags()
    if flags.KILL_SWITCH:
        raise RuntimeError("cannot enable writes while kill switch is ON")
    flags.PUBLIC_WRITE_ENABLED = 1
    flags.PUBLIC_WRITE_ROLLOUT_PERCENT = 1
    flags.PUBLIC_WRITE_MAX_PERCENT = 1
    flags.PUBLIC_WRITE_STARTED_AT = started_at or _utc()
    flags.OWNER_APPROVAL_ID = OWNER_APPROVAL_ID
    flags.IDENTITY_MODE = "SIGNED_PSEUDONYMOUS_DEVICE_V1"
    flags.PUBLIC_SCORE_MODE = "NATIVE_ONLY"
    flags.STRUCTURED_AGGREGATE_RATING_ENABLED = 0
    return save_flags(flags)


def trigger_kill_switch(reason: str) -> RolloutFlags:
    flags = load_flags()
    flags.KILL_SWITCH = 1
    flags.PUBLIC_WRITE_ENABLED = 0
    flags.KILL_SWITCH_REASON = reason[:500]
    flags.KILL_SWITCH_AT = _utc()
    return save_flags(flags)


def disable_public_writes() -> RolloutFlags:
    flags = load_flags()
    flags.PUBLIC_WRITE_ENABLED = 0
    return save_flags(flags)


def writes_allowed(flags: RolloutFlags | None = None) -> bool:
    f = flags or load_flags()
    return bool(f.PUBLIC_WRITE_ENABLED) and not bool(f.KILL_SWITCH) and not bool(f.READ_ONLY)


def as_public_dict(flags: RolloutFlags | None = None) -> dict[str, Any]:
    f = flags or load_flags()
    return {
        "PUBLIC_WRITE_ENABLED": int(f.PUBLIC_WRITE_ENABLED),
        "PUBLIC_WRITE_ROLLOUT_PERCENT": int(f.PUBLIC_WRITE_ROLLOUT_PERCENT),
        "PUBLIC_WRITE_MAX_PERCENT": int(f.PUBLIC_WRITE_MAX_PERCENT),
        "KILL_SWITCH": int(f.KILL_SWITCH),
        "READ_ONLY": int(f.READ_ONLY),
        "PUBLIC_SCORE_MODE": f.PUBLIC_SCORE_MODE,
        "IDENTITY_MODE": f.IDENTITY_MODE,
        "STRUCTURED_AGGREGATE_RATING_ENABLED": int(f.STRUCTURED_AGGREGATE_RATING_ENABLED),
        "PUBLIC_WRITE_STARTED_AT": f.PUBLIC_WRITE_STARTED_AT,
        "OWNER_APPROVAL_ID": f.OWNER_APPROVAL_ID,
    }
