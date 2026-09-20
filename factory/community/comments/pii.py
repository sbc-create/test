"""PII scanner for comment bodies — flags, never auto-publishes."""

from __future__ import annotations

import re
from typing import Any

# Conservative patterns — high precision preferred over recall for research labels.
_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?\d{1,3}[\s\-.]?)?(?:\(?\d{3}\)?[\s\-.]?)\d{3}[\s\-.]?\d{2,4}(?!\d)"
)
_CARD_RE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
_TG_RE = re.compile(r"(?:t\.me/|telegram\.me/|@)[A-Za-z0-9_]{4,}", re.IGNORECASE)
_VK_RE = re.compile(r"(?:vk\.com/|vkontakte\.ru/)[A-Za-z0-9_./-]+", re.IGNORECASE)
_PASSPORT_RU_RE = re.compile(r"\b\d{2}\s?\d{2}\s?\d{6}\b")


def scan_pii(text: str) -> dict[str, Any]:
    """Return PII findings. Does not mutate text; callers decide quarantine."""
    findings: list[dict[str, str]] = []
    checks = (
        ("email", _EMAIL_RE),
        ("phone", _PHONE_RE),
        ("payment_card_like", _CARD_RE),
        ("messenger_handle", _TG_RE),
        ("social_profile", _VK_RE),
        ("document_id_like", _PASSPORT_RU_RE),
    )
    for kind, pattern in checks:
        for match in pattern.finditer(text or ""):
            findings.append({"type": kind, "span": match.group(0)[:32]})
    return {
        "has_pii": bool(findings),
        "findings": findings[:20],
        "count": len(findings),
    }


def redact_preview(text: str, findings: list[dict[str, str]] | None = None) -> str:
    """Redact matched spans for admin preview logs — never store raw PII in evidence."""
    out = text or ""
    scanned = findings if findings is not None else scan_pii(out)["findings"]
    for item in scanned:
        span = item.get("span") or ""
        if span:
            out = out.replace(span, f"[REDACTED:{item.get('type', 'pii')}]")
    return out
