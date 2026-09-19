"""AMD.online source adapter — closed-canary gated.

Modes (from AMD_PERMISSION_STATUS.md):

* AMD_CLOSED_CANARY_INGESTION=ALLOWED → live detail canary up to configured limit
* AMD_CLOSED_NOINDEX_PUBLICATION=ALLOWED → candidate snapshot for closed sites
* AMD_PUBLIC_INDEXED_PUBLICATION=BLOCKED_PENDING_SEPARATE_APPROVAL

Written commercial permission is a separate Stage-3+ gate for public indexing.
"""

from __future__ import annotations

import hashlib
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from factory.paths import PATHS
from factory.ratings.adapters.amd_parser import AmdParseError, parse_detail_html
from factory.ratings.adapters.amd_selectors import (
    CANONICAL_ORIGIN,
    PARSER_VERSION,
    PERMISSION_VERSION,
    SOURCE_KEY,
)
from factory.ratings.adapters.base import AdapterError, FetchResult
from factory.ratings.models import utc_now_iso
from factory.ratings.rate_limit import RateLimiter

ADAPTER_VERSION = "amd_online_html/1.0.0"
PERMISSION_EVIDENCE = "artifacts/evidence/ratings-ingestion-02/AMD_PERMISSION_STATUS.md"

_DEFAULTS = {
    "AMD_PERMISSION_STATUS": "NOT_PROVIDED",
    "AMD_CLOSED_CANARY_INGESTION": "ALLOWED",
    "AMD_CLOSED_NOINDEX_PUBLICATION": "ALLOWED",
    "AMD_PUBLIC_INDEXED_PUBLICATION": "BLOCKED_PENDING_SEPARATE_APPROVAL",
    "AMD_SOURCE_STATE": "CLOSED_CANARY_ALLOWED",
    "AMD_PRODUCTION_INGESTION": "0",
}


def load_permission_status(root: Path | None = None) -> dict[str, str]:
    root = root or PATHS.root
    path = root / PERMISSION_EVIDENCE
    status = dict(_DEFAULTS)
    if not path.is_file():
        return status
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        if "=" in line and not line.startswith("#") and not line.startswith(" "):
            key, _, val = line.partition("=")
            key = key.strip()
            if key in status or key.startswith("AMD_"):
                status[key] = val.strip()
    return status


class AmdOnlineAdapter:
    source_key = SOURCE_KEY
    adapter_version = ADAPTER_VERSION

    def __init__(
        self,
        *,
        user_agent: str = "site-factory-ratings/1.0 (+ratings-ingestion; contact=ops)",
        rate_limiter: RateLimiter | None = None,
        opener: Callable | None = None,
        permission_root: Path | None = None,
        allow_live: bool = False,
        max_live_requests: int = 0,
        sleeper: Callable[[float], None] | None = None,
        robots_digest: str = "",
    ) -> None:
        self.user_agent = user_agent
        self.rate_limiter = rate_limiter or RateLimiter(max_rps=0.1, max_per_minute=6)
        self.opener = opener
        self.permission = load_permission_status(permission_root)
        self.allow_live = allow_live
        self.max_live_requests = max_live_requests
        self._live_used = 0
        self.sleeper = sleeper or time.sleep
        self.robots_digest = robots_digest
        self.auto_stopped = False
        self.stop_reason = ""
        self.stats = {
            "attempted": 0,
            "matched": 0,
            "accepted": 0,
            "rejected": 0,
            "quarantined": 0,
            "http_403": 0,
            "http_429": 0,
            "challenges": 0,
            "robots_digest_changed": 0,
            "last_good_retained": 0,
            "auto_stop_triggered": 0,
        }

    def closed_canary_allowed(self) -> bool:
        return self.permission.get("AMD_CLOSED_CANARY_INGESTION") == "ALLOWED"

    def closed_noindex_publication_allowed(self) -> bool:
        return self.permission.get("AMD_CLOSED_NOINDEX_PUBLICATION") == "ALLOWED"

    def public_indexed_blocked(self) -> bool:
        return self.permission.get("AMD_PUBLIC_INDEXED_PUBLICATION") != "ALLOWED"

    def permission_blocks_bulk(self) -> bool:
        """Blocks only when closed canary is not allowed."""
        return not self.closed_canary_allowed()

    def fetch_detail_html(self, url: str, *, html: str | None = None) -> FetchResult:
        if self.auto_stopped:
            raise AdapterError("AUTO_STOPPED", self.stop_reason, hard_circuit=True)

        if html is None:
            if self.permission_blocks_bulk() and not self.allow_live:
                raise AdapterError(
                    "SOURCE_POLICY_BLOCK",
                    "AMD_CLOSED_CANARY_INGESTION not ALLOWED",
                    hard_circuit=True,
                )
            if not self.closed_canary_allowed() and not self.allow_live:
                raise AdapterError(
                    "SOURCE_POLICY_BLOCK",
                    "closed canary not allowed",
                    hard_circuit=True,
                )
            if self._live_used >= self.max_live_requests:
                raise AdapterError(
                    "SOURCE_POLICY_BLOCK",
                    f"live request budget exhausted ({self.max_live_requests})",
                    hard_circuit=True,
                )
            html = self._get(url)
            self._live_used += 1

        self.stats["attempted"] += 1
        try:
            detail = parse_detail_html(
                html,
                source_url=url,
                fetched_at_utc=utc_now_iso(),
                robots_digest=self.robots_digest,
            )
        except AmdParseError as exc:
            self.stats["rejected"] += 1
            if exc.code in ("ID_MISMATCH",):
                self.stats["quarantined"] += 1
            return FetchResult(
                external_id=url,
                found=False,
                error=exc.code,
                payload={"code": exc.code, "message": str(exc)},
            )

        self.stats["matched"] += 1
        if detail.score is None:
            self.stats["rejected"] += 1
            return FetchResult(
                external_id=detail.source_id,
                found=False,
                error="PROVIDER_RATING_NULL",
                payload=detail.as_dict(),
                provenance_url=detail.canonical_url,
            )

        score = float(detail.score)
        self.stats["accepted"] += 1
        return FetchResult(
            external_id=detail.source_id,
            found=True,
            raw_score=score,
            vote_count=detail.vote_count,
            provenance_url=detail.canonical_url,
            name=detail.title_original or detail.title_ru,
            russian=detail.title_ru,
            payload=detail.as_dict(),
            source_updated_at="",
        )

    def fetch_by_ids(self, external_ids: list[str]) -> dict[str, FetchResult]:
        raise AdapterError(
            "SOURCE_POLICY_BLOCK",
            "amd_online requires canonical detail URLs, not bare id batch",
            retryable=False,
        )

    def check_schema(self) -> dict[str, Any]:
        return {
            "adapter_version": self.adapter_version,
            "parser_version": PARSER_VERSION,
            "permission_version": PERMISSION_VERSION,
            "canonical_origin": CANONICAL_ORIGIN,
            "permission": self.permission,
            "closed_canary_allowed": self.closed_canary_allowed(),
            "closed_noindex_publication_allowed": self.closed_noindex_publication_allowed(),
            "public_indexed_blocked": self.public_indexed_blocked(),
            "selectors": [
                "h1",
                "amd-sub",
                "multirating data-id",
                "multirating-itog-rateval",
                "multirating-itog-votes",
                'data-area="story|actors|graph|sound"',
            ],
        }

    def _stop(self, reason: str) -> None:
        self.auto_stopped = True
        self.stop_reason = reason
        self.stats["auto_stop_triggered"] = 1
        raise AdapterError("AUTO_STOPPED", reason, hard_circuit=True)

    def _get(self, url: str) -> str:
        self.rate_limiter.wait()
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.user_agent, "Accept": "text/html"},
            method="GET",
        )
        open_fn = self.opener or (
            lambda r, timeout: urllib.request.urlopen(r, timeout=timeout)  # noqa: S310
        )
        try:
            with open_fn(req, 30) as resp:
                status = getattr(resp, "status", None) or getattr(resp, "code", 200)
                final_url = getattr(resp, "url", url)
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 403:
                self.stats["http_403"] += 1
                self._stop("HTTP_403")
            if exc.code == 429:
                self.stats["http_429"] += 1
                self._stop("HTTP_429")
            raise AdapterError("HTTP_ERROR", f"HTTP {exc.code}", retryable=False) from exc
        except urllib.error.URLError as exc:
            raise AdapterError("TIMEOUT", str(exc), retryable=True) from exc

        text = raw.decode("utf-8", errors="replace")
        if _looks_like_challenge(text):
            self.stats["challenges"] += 1
            self._stop("CHALLENGE")
        if final_url and "amd.online" not in final_url:
            self._stop("UNEXPECTED_REDIRECT")
        if status and int(status) in (403, 429):
            self._stop(f"HTTP_{status}")
        return text


def _looks_like_challenge(html: str) -> bool:
    """Detect real anti-bot challenges; ignore DLE ``dle_captcha_type`` JS vars."""
    low = html.lower()
    if "ddos-guard" in low or "checking your browser" in low:
        return True
    if "cf-browser-verification" in low or 'id="challenge-form"' in low:
        return True
    if "just a moment" in low and "cloudflare" in low:
        return True
    # DLE embeds dle_captcha_type in every page — not a challenge.
    return (
        ("g-recaptcha" in low or "hcaptcha" in low or "captcha-box" in low)
        and "multirating" not in low
        and len(html) < 8000
    )


def robots_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
