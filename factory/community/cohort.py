"""Deterministic public-write cohort bucketing (1% canary)."""

from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from factory.community.policy import POLICY_VERSION


def _rollout_salt() -> bytes:
    path = os.environ.get("COMMUNITY_ROLLOUT_SALT_FILE", "").strip()
    if path and Path(path).is_file():
        return Path(path).read_bytes().strip()
    env = os.environ.get("COMMUNITY_ROLLOUT_SALT", "").strip()
    if env:
        return env.encode()
    # Stable dev salt — production unit injects real salt via credential file.
    return b"dev-only-rollout-salt"


@dataclass(frozen=True)
class CohortDecision:
    identity_id: str
    bucket: int
    rollout_percent: int
    eligible: bool
    policy_version: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "cohort_bucket": self.bucket,
            "rollout_percent": self.rollout_percent,
            "eligible": self.eligible,
            "policy_version": self.policy_version,
            # identity_id intentionally omitted from public dicts
        }


def cohort_bucket(
    identity_id: str,
    *,
    policy_version: str = POLICY_VERSION,
    salt: bytes | None = None,
) -> int:
    """stable_hash(identity_id + rollout_salt + policy_version) % 100"""
    s = salt if salt is not None else _rollout_salt()
    msg = f"{identity_id}|{policy_version}".encode()
    digest = hmac.new(s, msg, hashlib.sha256).digest()
    return int.from_bytes(digest[:4], "big") % 100


def decide_cohort(
    identity_id: str,
    *,
    rollout_percent: int,
    policy_version: str = POLICY_VERSION,
    salt: bytes | None = None,
) -> CohortDecision:
    pct = max(0, min(100, int(rollout_percent)))
    bucket = cohort_bucket(identity_id, policy_version=policy_version, salt=salt)
    return CohortDecision(
        identity_id=identity_id,
        bucket=bucket,
        rollout_percent=pct,
        eligible=bucket < pct,
        policy_version=policy_version,
    )


class CohortDenied(Exception):
    status = 403
