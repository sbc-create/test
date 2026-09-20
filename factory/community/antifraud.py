"""Antifraud / privacy guards for community ratings (no raw IP storage)."""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any


class KillSwitchActive(RuntimeError):
    status = 503


class RateLimited(RuntimeError):
    status = 429


class OriginRejected(RuntimeError):
    status = 403


@dataclass
class AntifraudConfig:
    kill_switch: bool = False
    read_only: bool = False
    hmac_secret: bytes = field(default_factory=lambda: os.environ.get("COMMUNITY_IP_HMAC_SECRET", "dev-only-rotate").encode())
    hmac_ttl_seconds: int = 86400
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


class ReadOnlyMode(RuntimeError):
    status = 503


class AntifraudGuard:
    def __init__(self, config: AntifraudConfig | None = None) -> None:
        self.config = config or AntifraudConfig()
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._seen_replay: dict[str, float] = {}
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
        keys = [f"acct:{account_id}", f"tok:{token_id}", f"ip:{ip_hmac_prefix}", "global:writes"]
        if subject_id:
            keys.append(f"title:{subject_id}")
        for key in keys:
            if not key.split(":", 1)[1]:
                continue
            q = self._hits[key]
            while q and t - q[0] > self.config.rate_limit_window_s:
                q.popleft()
            limit = self.config.rate_limit_max
            if key.startswith("title:"):
                limit = self.config.title_rate_limit_max
            elif key.startswith("global:"):
                limit = self.config.global_rate_limit_max
            if len(q) >= limit:
                raise RateLimited(f"rate limit exceeded for {key.split(':', 1)[0]}")
            q.append(t)
            burst = [x for x in q if t - x <= self.config.burst_window_s]
            if len(burst) >= self.config.burst_max and not key.startswith("global:"):
                self.alerts.append(
                    {
                        "type": "velocity_burst",
                        "key": key,
                        "count": len(burst),
                        "at": t,
                    }
                )
                raise RateLimited("burst detected")

    def check_replay(self, replay_id: str, *, now: float | None = None, ttl: float = 600.0) -> None:
        t = now if now is not None else time.time()
        # purge
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


def _ip_prefix(ip: str) -> str:
    ip = (ip or "").strip()
    if ":" in ip:
        # IPv6: keep first 4 hextets as coarse prefix
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
RATINGS_PUBLIC_ACTIVATION = 0  # owner-gated
RATINGS_KILL_SWITCH = 0
