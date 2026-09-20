"""Comment body sanitization — strip HTML/XSS vectors, normalize Unicode."""

from __future__ import annotations

import html
import re
import unicodedata
from typing import Any

MAX_BODY_CHARS = 4000
MIN_BODY_CHARS = 1

# Tags and event handlers commonly used in XSS payloads.
_TAG_RE = re.compile(r"<[^>]*>", re.IGNORECASE | re.DOTALL)
_SCRIPT_RE = re.compile(r"<\s*/?\s*script\b[^>]*>", re.IGNORECASE | re.DOTALL)
_EVENT_ATTR_RE = re.compile(r"\bon\w+\s*=", re.IGNORECASE)
_JS_URI_RE = re.compile(r"javascript\s*:", re.IGNORECASE)
_DATA_URI_RE = re.compile(r"data\s*:\s*text/html", re.IGNORECASE)
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_ZW_RE = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]")


class SanitizeError(ValueError):
    code = "SanitizeError"


def normalize_unicode(text: str) -> str:
    """NFC normalize and strip zero-width / bidi override abuse."""
    text = unicodedata.normalize("NFC", text)
    text = _ZW_RE.sub("", text)
    text = _CONTROL_RE.sub("", text)
    return text


def strip_html(text: str) -> str:
    text = _SCRIPT_RE.sub("", text)
    text = _TAG_RE.sub("", text)
    text = _EVENT_ATTR_RE.sub("", text)
    text = _JS_URI_RE.sub("", text)
    text = _DATA_URI_RE.sub("", text)
    return text


def sanitize_body(raw: str | None, *, max_chars: int = MAX_BODY_CHARS) -> dict[str, Any]:
    """Return sanitized body + normalized form for duplicate detection.

    Never returns HTML. Output is plain text safe for JSON and SSR escaping.
    """
    if raw is None:
        raise SanitizeError("empty body")
    if not isinstance(raw, str):
        raise SanitizeError("body must be string")
    text = normalize_unicode(raw)
    text = strip_html(text)
    # Decode entities then strip again so &lt;script&gt; cannot reappear as tags.
    text = html.unescape(text)
    text = strip_html(text)
    text = normalize_unicode(text)
    text = text.strip()
    if len(text) < MIN_BODY_CHARS:
        raise SanitizeError("body too short")
    if len(text) > max_chars:
        raise SanitizeError(f"body exceeds {max_chars} characters")
    normalized = " ".join(text.casefold().split())
    return {
        "body": text,
        "body_normalized": normalized,
        "length": len(text),
        "escaped_preview": html.escape(text, quote=True),
    }
