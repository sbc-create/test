"""PII scanner + Qwen-bound redaction for comment bodies."""

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
_IPV4_RE = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
)
_SECRET_RE = re.compile(
    r"(?i)\b(?:api[_-]?key|token|secret|bearer)\s*[:=]\s*([A-Za-z0-9_\-.]{8,})"
)
_COOKIE_RE = re.compile(r"(?i)\b(?:session|sid|jwt)=([A-Za-z0-9_\-.]{8,})")

PLACEHOLDERS = {
    "email": "[EMAIL_REDACTED]",
    "phone": "[PHONE_REDACTED]",
    "payment_card_like": "[SECRET_REDACTED]",
    "messenger_handle": "[ACCOUNT_REDACTED]",
    "social_profile": "[ACCOUNT_REDACTED]",
    "document_id_like": "[SECRET_REDACTED]",
    "ip": "[IP_REDACTED]",
    "secret_like": "[SECRET_REDACTED]",
    "cookie_like": "[SECRET_REDACTED]",
}


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
        ("ip", _IPV4_RE),
        ("secret_like", _SECRET_RE),
        ("cookie_like", _COOKIE_RE),
    )
    for kind, pattern in checks:
        for match in pattern.finditer(text or ""):
            findings.append({"type": kind, "span": match.group(0)[:64]})
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


def redact_for_qwen(text: str) -> dict[str, Any]:
    """Return text safe to send to external Qwen — placeholders only, no raw PII."""
    scanned = scan_pii(text or "")
    out = text or ""
    spans = sorted(
        (f for f in scanned["findings"] if f.get("span")),
        key=lambda f: len(f["span"]),
        reverse=True,
    )
    for item in spans:
        span = item["span"]
        kind = item.get("type") or "secret_like"
        placeholder = PLACEHOLDERS.get(kind, "[SECRET_REDACTED]")
        out = out.replace(span, placeholder)
    return {
        "text": out,
        "pii_detected": bool(scanned["has_pii"]),
        "finding_types": sorted({f["type"] for f in scanned["findings"]}),
        "finding_count": scanned["count"],
    }
