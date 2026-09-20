"""Technical preflight only — no sentiment / spoiler / toxicity judgement.

Goal §6: Unicode NFC, HTML/XSS strip, length, newlines, empty, duplicate
digest hook, external link cap, flood patterns. Content quality is Qwen's job.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from typing import Any

from factory.community.comments.sanitize import SanitizeError, sanitize_body

MAX_BODY_CHARS = 3000
MIN_WORDS = 2
MAX_NEWLINES = 40
MAX_EXTERNAL_LINKS = 2

_URL_RE = re.compile(
    r"(?i)\b(?:https?://|www\.)[^\s<>\"']+",
)
_FLOOD_REPEAT_RE = re.compile(r"(.)\1{12,}")
_FLOOD_TOKEN_RE = re.compile(r"(.{4,})\1{4,}", re.IGNORECASE)


class PreflightError(ValueError):
    def __init__(self, reject_code: str, message: str = "") -> None:
        self.reject_code = reject_code
        super().__init__(message or reject_code)


def body_digest(body_normalized: str) -> str:
    return hashlib.sha256(body_normalized.encode("utf-8")).hexdigest()


def _count_words(normalized: str) -> int:
    return len([w for w in normalized.split() if w])


def _count_newlines(text: str) -> int:
    return text.count("\n") + text.count("\r")


def _count_external_links(text: str) -> int:
    return len(_URL_RE.findall(text))


def _flood_detected(text: str, normalized: str) -> str | None:
    if _FLOOD_REPEAT_RE.search(text) or _FLOOD_REPEAT_RE.search(normalized):
        return "FLOOD_REPEATED_CHARS"
    if _FLOOD_TOKEN_RE.search(normalized.replace(" ", "")):
        return "FLOOD_REPEATED_TOKEN"
    # Extremely low entropy: same word repeated
    words = normalized.split()
    if len(words) >= 6 and len(set(words)) == 1:
        return "FLOOD_SINGLE_WORD_SPAM"
    return None


def run_preflight(
    raw: str | None,
    *,
    duplicate_check: Callable[[str], bool] | None = None,
    max_chars: int = MAX_BODY_CHARS,
    min_words: int = MIN_WORDS,
    max_newlines: int = MAX_NEWLINES,
    max_external_links: int = MAX_EXTERNAL_LINKS,
) -> dict[str, Any]:
    """Return {ok, body, body_normalized, digest, reject_code} or raise PreflightError.

    ``duplicate_check(digest)`` should return True when the digest is a duplicate
    that must be rejected. CSRF/rate limits belong at the API layer, not here.
    """
    try:
        cleaned = sanitize_body(raw, max_chars=max_chars)
    except SanitizeError as exc:
        code = "EMPTY" if "short" in str(exc).lower() or "empty" in str(exc).lower() else "SANITIZE"
        if "exceeds" in str(exc).lower():
            code = "TOO_LONG"
        raise PreflightError(code, str(exc)) from exc

    body = cleaned["body"]
    normalized = cleaned["body_normalized"]
    if not body.strip():
        raise PreflightError("EMPTY", "empty body")
    if _count_words(normalized) < min_words:
        raise PreflightError("TOO_SHORT", f"need at least {min_words} words")
    if _count_newlines(body) > max_newlines:
        raise PreflightError("TOO_MANY_NEWLINES", f"exceeds {max_newlines} newlines")
    links = _count_external_links(body)
    if links > max_external_links:
        raise PreflightError("TOO_MANY_LINKS", f"external links={links} max={max_external_links}")
    flood = _flood_detected(body, normalized)
    if flood:
        raise PreflightError(flood, flood)

    digest = body_digest(normalized)
    if duplicate_check is not None and duplicate_check(digest):
        raise PreflightError("DUPLICATE_DIGEST", "duplicate body digest")

    return {
        "ok": True,
        "body": body,
        "body_normalized": normalized,
        "digest": digest,
        "reject_code": None,
        "length": len(body),
        "word_count": _count_words(normalized),
        "external_links": links,
    }


def preflight_or_reject(raw: str | None, **kwargs: Any) -> dict[str, Any]:
    """Non-raising wrapper: always returns ok True/False with reject_code."""
    try:
        return run_preflight(raw, **kwargs)
    except PreflightError as exc:
        return {
            "ok": False,
            "body": "",
            "body_normalized": "",
            "digest": "",
            "reject_code": exc.reject_code,
        }
