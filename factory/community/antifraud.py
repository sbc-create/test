"""Antifraud / privacy guards for community ratings (no raw IP storage)."""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class KillSwitchActive(RuntimeError):
    status = 503


class RateLimited(RuntimeError):
    status = 429


class OriginRejected(RuntimeError):
    status = 403


class ReadOnlyMode(RuntimeError):
    status = 503


def _load_pepper() -> bytes:
    path = os.environ.get("COMMUNITY_IP_HMAC_SECRET_FILE", "").strip()
    if path and Path(path).is_file():
        return Path(path).read_bytes().strip()
    return os.environ.get("COMMUNITY_IP_HMAC_SECRET", "dev-only-rotate").encode()


@dataclass
class AntifraudConfig:
    kill_switch: bool = False
    read_only: bool = False
    hmac_secret: bytes = field(default_factory=_load_pepper)
    hmac_ttl_seconds: int = 86400
    # Stage06 owner-approved starters (may be stricter than Stage05).
    per_identity_window_s: float = 600.0  # 10 min
    per_identity_max_10m: int = 20
    per_identity_day_s: float = 86400.0
    per_identity_max_day: int = 100
    per_identity_title_window_s: float = 3600.0
    per_identity_title_max_hour: int = 5
    per_network_window_s: float = 600.0
    per_network_max_10m: int = 100
    per_network_day_s: float = 86400.0
    per_network_max_day: int = 1000
    max_invalid_attempts_10m: int = 30
    # Legacy single-window knobs kept for Stage05 tests.
    rate_limit_window_s: float = 60.0
    rate_limit_max: int = 30
    burst_window_s: float = 10.0
    burst_max: int = 8
    title_rate_limit_max: int = 20
    global_rate_limit_max: int = 200
    allowed_origins: tuple[str, ...] = (
        "https://animedia.icu",
        "https://animedia.space",
        "https://yummyani.site",
        "https://yummyani.org",
        "https://yummyani.biz",
        "http://localhost",
        "http://127.0.0.1",
    )


class AntifraudGuard:
    def __init__(self, config: AntifraudConfig | None = None) -> None:
        self.config = config or AntifraudConfig()
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._seen_replay: dict[str, float] = {}
        self._invalid: dict[str, deque[float]] = defaultdict(deque)
        self.alerts: list[dict[str, Any]] = []

    def assert_writable(self) -> None:
        if self.config.kill_switch:
            raise KillSwitchActive("community ratings kill switch active")
        if self.config.read_only:
            raise ReadOnlyMode("community ratings read-only emergency mode")

    def set_kill_switch(self, enabled: bool) -> None:
        self.config.kill_switch = bool(enabled)

    def set_read_only(self, enabled: bool) -> None:
        self.config.read_only = bool(enabled)

    def sync_from_rollout(self) -> None:
        try:
            from factory.community.rollout import load_flags

            flags = load_flags()
            self.config.kill_switch = bool(flags.KILL_SWITCH)
            self.config.read_only = bool(flags.READ_ONLY)
        except Exception:
            pass

    def check_origin(self, origin: str | None, *, csrf_token: str | None, session_csrf: str | None) -> None:
        if not origin:
            raise OriginRejected("missing Origin")
        ok = any(origin == o or origin.startswith(o + ":") for o in self.config.allowed_origins)
        if not ok:
            raise OriginRejected(f"origin not allowed: {origin}")
        if not csrf_token or not session_csrf or csrf_token != session_csrf:
            raise OriginRejected("CSRF token mismatch")

    def ip_prefix_hmac(self, ip: str, *, now: float | None = None) -> str:
        """Rotating HMAC of /24 (IPv4) or /64 truncated prefix — never store raw IP."""
        ts = int(now if now is not None else time.time())
        bucket = ts // self.config.hmac_ttl_seconds
        prefix = _ip_prefix(ip)
        msg = f"{bucket}:{prefix}".encode()
        return hmac.new(self.config.hmac_secret, msg, hashlib.sha256).hexdigest()[:32]

    def note_invalid(self, key: str, *, now: float | None = None) -> None:
        t = now if now is not None else time.time()
        q = self._invalid[key]
        while q and t - q[0] > 600.0:
            q.popleft()
        q.append(t)
        if len(q) >= self.config.max_invalid_attempts_10m:
            raise RateLimited("too many invalid attempts")

    def check_rate(
        self,
        *,
        account_id: str,
        token_id: str,
        ip_hmac_prefix: str,
        subject_id: str = "",
        now: float | None = None,
    ) -> None:
        t = now if now is not None else time.time()
        identity = token_id or account_id
        checks: list[tuple[str, float, int]] = []
        if identity:
            checks.append((f"id10m:{identity}", self.config.per_identity_window_s, self.config.per_identity_max_10m))
            checks.append((f"idday:{identity}", self.config.per_identity_day_s, self.config.per_identity_max_day))
            if subject_id:
                checks.append(
                    (
                        f"idtitle:{identity}:{subject_id}",
                        self.config.per_identity_title_window_s,
                        self.config.per_identity_title_max_hour,
                    )
                )
        if ip_hmac_prefix:
            checks.append(
                (f"net10m:{ip_hmac_prefix}", self.config.per_network_window_s, self.config.per_network_max_10m)
            )
            checks.append(
                (f"netday:{ip_hmac_prefix}", self.config.per_network_day_s, self.config.per_network_max_day)
            )
        # Legacy Stage05 windows
        legacy_keys = [f"acct:{account_id}", f"tok:{token_id}", f"ip:{ip_hmac_prefix}", "global:writes"]
        if subject_id:
            legacy_keys.append(f"title:{subject_id}")
        for key in legacy_keys:
            if not key.split(":", 1)[1]:
                continue
            limit = self.config.rate_limit_max
            if key.startswith("title:"):
                limit = self.config.title_rate_limit_max
            elif key.startswith("global:"):
                limit = self.config.global_rate_limit_max
            checks.append((key, self.config.rate_limit_window_s, limit))

        for key, window, limit in checks:
            q = self._hits[key]
            while q and t - q[0] > window:
                q.popleft()
            if len(q) >= limit:
                raise RateLimited(f"rate limit exceeded for {key.split(':', 1)[0]}")
            q.append(t)
            if window == self.config.rate_limit_window_s:
                burst = [x for x in q if t - x <= self.config.burst_window_s]
                if len(burst) >= self.config.burst_max and not key.startswith("global:"):
                    self.alerts.append(
                        {
                            "type": "velocity_burst",
                            "key": key.split(":", 1)[0],
                            "count": len(burst),
                            "at": t,
                        }
                    )
                    raise RateLimited("burst detected")

    def check_replay(self, replay_id: str, *, now: float | None = None, ttl: float = 600.0) -> None:
        t = now if now is not None else time.time()
        expired = [k for k, v in self._seen_replay.items() if t - v > ttl]
        for k in expired:
            del self._seen_replay[k]
        if replay_id in self._seen_replay:
            raise OriginRejected("replay detected")
        self._seen_replay[replay_id] = t

    def note_mass_vote_anomaly(self, *, subject_id: str, count: int, window_s: float) -> None:
        if count >= 50:
            self.alerts.append(
                {
                    "type": "mass_voting",
                    "subject_id": subject_id,
                    "count": count,
                    "window_s": window_s,
                }
            )

    def should_quarantine(
        self,
        *,
        identity_id: str,
        subject_id: str,
        titles_touched_recent: int = 0,
    ) -> tuple[bool, str]:
        """Heuristic quarantine — vote is kept, excluded from public aggregate."""
        if titles_touched_recent >= 30:
            return True, "too_many_titles_short_window"
        # Cookie forgery / CSRF already hard-denied; no auto-block on single odd request.
        return False, ""


def _ip_prefix(ip: str) -> str:
    ip = (ip or "").strip()
    # Strip obvious X-Forwarded-For chains — only first hop prefix hashed,
    # but callers should pass already-selected peer; never store raw.
    if "," in ip:
        ip = ip.split(",", 1)[0].strip()
    if ":" in ip:
        parts = ip.split(":")
        return ":".join(parts[:4])
    parts = ip.split(".")
    if len(parts) == 4:
        return ".".join(parts[:3]) + ".0"
    return "unknown"


# Feature flags (comments dark)
COMMENTS_ENABLED = 0
COMMENTS_PUBLICATION_ENABLED = 0
COMMENTS_SEO_RENDERING_ENABLED = 0
RATINGS_PUBLIC_ACTIVATION = 0  # owner-gated via rollout.py
RATINGS_KILL_SWITCH = 0
