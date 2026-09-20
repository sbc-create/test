"""Load and validate rating_policy_v1 (activation remains owner-gated)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from factory.paths import PATHS

POLICY_VERSION = "rating_policy_v1"
DEFAULT_POLICY_PATH = PATHS.root / "config" / "community" / "rating_policy_v1.json"


@dataclass(frozen=True)
class RatingPolicy:
    raw: dict[str, Any]

    @property
    def version(self) -> str:
        return str(self.raw.get("version") or POLICY_VERSION)

    @property
    def activated(self) -> bool:
        return bool(self.raw.get("activated"))

    def space(self, rating_space_id: str) -> dict[str, Any]:
        spaces = self.raw.get("spaces") or {}
        if rating_space_id not in spaces:
            raise KeyError(f"unknown rating_space_id={rating_space_id}")
        return dict(spaces[rating_space_id])

    def as_dict(self) -> dict[str, Any]:
        return dict(self.raw)


def load_policy(path: Path | None = None) -> RatingPolicy:
    p = path or DEFAULT_POLICY_PATH
    data = json.loads(p.read_text(encoding="utf-8"))
    if data.get("version") != POLICY_VERSION:
        raise ValueError(f"unexpected policy version {data.get('version')}")
    return RatingPolicy(raw=data)


def assert_not_activated_for_shadow(policy: RatingPolicy) -> None:
    """Stage-6 foundation must not silently activate production policy."""
    if policy.activated:
        raise RuntimeError("rating_policy_v1 activated without owner gate")
