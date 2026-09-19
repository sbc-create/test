"""Stage 4 pilot scheduler controls — seven-cycle auto-stop; default disabled."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from factory.ratings.scheduler import DEFAULT_STATE, SchedulerConfig, save_scheduler

PILOT_MAX_CYCLES = 7
PILOT_DAILY_ACCEPTED_TARGET = 100
PILOT_DAILY_CANDIDATE_CAP = 150


@dataclass
class PilotConfig:
    scope: str = "closed noindex ratings ingestion"
    daily_accepted_target: int = PILOT_DAILY_ACCEPTED_TARGET
    daily_candidate_cap: int = 150
    max_cycles: int = PILOT_MAX_CYCLES
    paid_operations: int = 0
    public_indexed_publication: int = 0
    scheduler_enabled: bool = False
    cycles_completed: int = 0
    automatic_stop_configured: bool = True
    request_rate_max_rps: float = 0.1
    source_concurrency: int = 1
    kill_switch: str = "enabled"
    authorized_sources: tuple[str, ...] = ("shikimori",)  # amd disabled

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["authorized_sources"] = list(self.authorized_sources)
        return d


def deterministic_cycle_id(day: str, source_digest: str, limit: int) -> str:
    raw = f"pilot-daily100|{day}|{source_digest}|{limit}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def pilot_state_path(root: Path) -> Path:
    return root / "var" / "ratings" / "pilot_state.json"


def load_pilot(root: Path) -> PilotConfig:
    path = pilot_state_path(root)
    cfg = PilotConfig()
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        for k, v in data.items():
            if hasattr(cfg, k) and k != "scheduler_enabled":
                setattr(cfg, k, v)
        cfg.scheduler_enabled = False  # never persist enabled without gates
    return cfg


def save_pilot(root: Path, cfg: PilotConfig) -> Path:
    path = pilot_state_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = cfg.as_dict()
    payload["scheduler_enabled"] = False
    payload["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    # Keep global scheduler disabled
    save_scheduler(SchedulerConfig(state=DEFAULT_STATE, current_daily_limit=0))
    return path


def should_auto_stop(cfg: PilotConfig) -> bool:
    return cfg.cycles_completed >= cfg.max_cycles


def coverage_aware_target(
    *,
    uncovered: int,
    due_refresh: int,
    cap: int = PILOT_DAILY_ACCEPTED_TARGET,
) -> dict[str, Any]:
    available = max(0, uncovered) + max(0, due_refresh)
    target = min(cap, available)
    shortfall_ok = target < cap
    reason = ""
    if available == 0:
        reason = "COVERAGE_COMPLETE_OR_NO_DUE_REFRESH"
    elif shortfall_ok:
        reason = "AVAILABLE_BELOW_CAP"
    return {
        "DAILY_ACCEPTED_TARGET": cap,
        "effective_target": target,
        "authorized_uncovered": uncovered,
        "authorized_due_refresh": due_refresh,
        "shortfall_allowed": shortfall_ok,
        "shortfall_reason": reason,
    }
