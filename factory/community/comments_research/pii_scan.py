"""PII scan and strip for research payloads — RAW_USER_IDENTITIES_STORED=0."""

from __future__ import annotations

import re
from typing import Any

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PHONE_RE = re.compile(
    r"(?<!\w)(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{2,4}\)?[\s-]?)?\d{3}[\s-]?\d{2,4}[\s-]?\d{2,4}(?!\w)"
)
IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
URL_PROFILE_RE = re.compile(
    r"https?://(?:www\.)?(?:vk\.com|t\.me|telegram\.me|instagram\.com|facebook\.com|"
    r"twitter\.com|x\.com|anilist\.co/user)/[^\s]+",
    re.I,
)

IDENTITY_KEYS = frozenset(
    {
        "username",
        "user_name",
        "display_name",
        "displayname",
        "avatar",
        "avatar_url",
        "profile_url",
        "profile",
        "email",
        "phone",
        "ip",
        "ip_address",
        "cookie",
        "cookies",
        "social",
        "social_links",
        "user",
        "author",
        "name",
    }
)


def scan_text_pii(text: str) -> dict[str, int]:
    text = text or ""
    return {
        "emails": len(EMAIL_RE.findall(text)),
        "phones": len(PHONE_RE.findall(text)),
        "ips": len(IPV4_RE.findall(text)),
        "profile_urls": len(URL_PROFILE_RE.findall(text)),
    }


def redact_text_pii(text: str) -> str:
    text = EMAIL_RE.sub("[REDACTED_EMAIL]", text or "")
    text = URL_PROFILE_RE.sub("[REDACTED_PROFILE_URL]", text)
    text = IPV4_RE.sub("[REDACTED_IP]", text)
    # phones last — higher false-positive rate; still strip for research safety
    text = PHONE_RE.sub("[REDACTED_PHONE]", text)
    return text


def strip_identity_fields(payload: dict[str, Any]) -> dict[str, Any]:
    """Drop identity-bearing keys recursively; keep structural non-identity data."""
    out: dict[str, Any] = {}
    for key, value in payload.items():
        lk = str(key).lower()
        if lk in IDENTITY_KEYS or lk.endswith("_username") or lk.endswith("_avatar"):
            continue
        if isinstance(value, dict):
            out[key] = strip_identity_fields(value)
        elif isinstance(value, list):
            out[key] = [
                strip_identity_fields(v) if isinstance(v, dict) else v for v in value
            ]
        else:
            out[key] = value
    return out


def pii_reject_reason(text: str) -> str | None:
    """Reject observation if residual high-risk PII remains after light redact check."""
    hits = scan_text_pii(text)
    if hits["emails"] or hits["phones"] or hits["ips"]:
        return "pii_pattern_in_body"
    return None
