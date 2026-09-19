"""Ratings ingestion scheduler — installed but DISABLED by default (Stage 3)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from factory.paths import PATHS

SCHEDULER_STATE_VERSION = "ratings_scheduler_v1"
DEFAULT_STATE = "DISABLED"
EXIT_SHORTFALL = 3


@dataclass
class SchedulerConfig:
    final_accepted_target: int = 500
    final_candidate_cap: int = 750
    max_rate_rps: float = 0.1
    max_concurrency: int = 1
    timeout_hours: float = 3.0
    overlap_policy: str = "SKIP"
    lock: str = "single-flight"
    crash_resume: str = "checkpoint"
    kill_switch: str = "enabled"
    default_state: str = DEFAULT_STATE
    state: str = DEFAULT_STATE
    current_daily_limit: int = 0
    ramp_allowed: tuple[int, ...] = (100, 250, 500)
    auto_ramp: bool = False  # never auto-increase
    source_key: str = "amd_online"

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["ramp_allowed"] = list(self.ramp_allowed)
        d["auto_ramp"] = False
        return d


def scheduler_state_path() -> Path:
    return PATHS.root / "var" / "ratings" / "scheduler_state.json"


def load_scheduler(path: Path | None = None) -> SchedulerConfig:
    path = path or scheduler_state_path()
    cfg = SchedulerConfig()
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        for k, v in data.items():
            if hasattr(cfg, k) and k != "auto_ramp":
                setattr(cfg, k, v)
        cfg.auto_ramp = False
        cfg.state = data.get("state", DEFAULT_STATE)
        if cfg.state not in ("DISABLED", "ENABLED"):
            cfg.state = DEFAULT_STATE
    return cfg


def save_scheduler(cfg: SchedulerConfig, path: Path | None = None) -> Path:
    path = path or scheduler_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": SCHEDULER_STATE_VERSION,
        **cfg.as_dict(),
        "state": DEFAULT_STATE if cfg.state != "ENABLED" else "DISABLED",  # Stage 3 force off
        "note": "Stage 3: installed but DISABLED; ramp requires explicit confirmed stage",
    }
    # Force disabled on Stage 3 save
    payload["state"] = "DISABLED"
    payload["current_daily_limit"] = 0
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def assert_disabled(cfg: SchedulerConfig | None = None) -> dict[str, Any]:
    cfg = cfg or load_scheduler()
    return {
        "SCHEDULER_INSTALLED": "YES",
        "SCHEDULER_ENABLED": "NO" if cfg.state != "ENABLED" else "YES",
        "CURRENT_DAILY_LIMIT": 0 if cfg.state != "ENABLED" else cfg.current_daily_limit,
        "DEFAULT_STATE": DEFAULT_STATE,
        "AUTO_RAMP": False,
        "KILL_SWITCH": cfg.kill_switch,
        "EXIT_SHORTFALL": EXIT_SHORTFALL,
    }
