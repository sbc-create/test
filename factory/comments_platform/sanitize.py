"""Text normalisation and safe rendering.

The design rule is that HTML is *generated*, never *passed through*. The stored
body is plain text; the renderer escapes it completely and only then puts back
the handful of tags a comment is allowed to produce. There is no sanitiser
walking attacker-supplied markup looking for bad tags, because that is the
approach that keeps losing — this one cannot lose the same way, since no
attacker byte ever reaches the output as markup.

Links get `rel="ugc nofollow noopener noreferrer"` and `target="_blank"`. The
`ugc nofollow` pair is the SEO requirement; `noopener noreferrer` is the reason
a link in a comment cannot reach back into the opener window.
"""

from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from .errors import PolicyViolation, ValidationFailed

MAX_LENGTH_HARD_CAP = 8000
MIN_LENGTH = 1

# Only these schemes may appear in a rendered link. Everything else — including
# `javascript:`, `data:`, `vbscript:` and schemeless `//host` — renders as text.
ALLOWED_URL_SCHEMES = frozenset({"http", "https"})

# Characters with no business in a comment: C0/C1 controls except tab/newline,
# bidi overrides (which let a display string lie about its content), and zero
# width joiners used to smuggle lookalike text past a stoplist.
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]")
_BIDI_RE = re.compile(r"[‪-‮⁦-⁩]")
_ZERO_WIDTH_RE = re.compile(r"[​-‏﻿⁠]")
_EXCESS_NEWLINES_RE = re.compile(r"\n{3,}")
_EXCESS_SPACES_RE = re.compile(r"[ \t]{3,}")

_URL_IN_TEXT_RE = re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)


def normalise(text: str, *, max_length: int) -> str:
    """Canonicalise a submitted body into what will actually be stored.

    NFC first: without it `é` and `é` are different strings, and duplicate
    detection, stoplists and length limits all quietly disagree with the reader.
    """
    if not isinstance(text, str):
        raise ValidationFailed("body must be a string", field="body")

    value = unicodedata.normalize("NFC", text)
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = _CONTROL_RE.sub("", value)
    value = _BIDI_RE.sub("", value)
    value = _ZERO_WIDTH_RE.sub("", value)
    value = _EXCESS_SPACES_RE.sub("  ", value)
    value = _EXCESS_NEWLINES_RE.sub("\n\n", value)
    value = "\n".join(line.rstrip() for line in value.split("\n")).strip()

    limit = min(int(max_length), MAX_LENGTH_HARD_CAP)
    if len(value) < MIN_LENGTH:
        raise ValidationFailed("body is empty", field="body")
    if len(value) > limit:
        # Refused, not truncated. Silently cutting a comment in half publishes
        # something the author did not write.
        raise ValidationFailed(f"body exceeds {limit} characters", field="body")
    return value


def count_links(text: str) -> int:
    return len(_URL_IN_TEXT_RE.findall(text))


def enforce_link_cap(text: str, *, max_links: int) -> None:
    found = count_links(text)
    if found > max_links:
        raise PolicyViolation(
            f"{found} links exceed the limit of {max_links}", rule="LINK_CAP"
        )


def safe_href(raw: str) -> str | None:
    """Return a safe absolute URL, or None if the link must render as text."""
    candidate = raw.strip()
    # Strip characters that terminate an attribute or start a new one. They
    # cannot survive escaping anyway, but refusing early keeps the intent clear.
    if any(ch in candidate for ch in ('"', "'", "<", ">", "\\", "\n", "\t", " ")):
        return None
    if candidate.lower().startswith("www."):
        candidate = "https://" + candidate
    try:
        parts = urlsplit(candidate)
    except ValueError:
        return None
    if parts.scheme.lower() not in ALLOWED_URL_SCHEMES:
        return None
    if not parts.netloc:
        return None
    # `javascript&colon;` and friends are already dead because the scheme check
    # happens on the parsed value, not on a substring search.
    return candidate


def _escape(text: str) -> str:
    """Full escape, quotes included. Everything after this point is inert."""
    return html.escape(text, quote=True)


_INLINE_CODE_RE = re.compile(r"`([^`\n]{1,200})`")
_BOLD_RE = re.compile(r"\*\*([^*\n]{1,500})\*\*")
_ITALIC_RE = re.compile(r"(?<!\*)\*([^*\n]{1,500})\*(?!\*)")
_SPOILER_RE = re.compile(r"\|\|(.+?)\|\|", re.DOTALL)
_LINK_RE = re.compile(r"\[([^\]\n]{1,200})\]\(([^)\s]{1,2000})\)")
_BARE_URL_RE = re.compile(r"(?<![\"'=>])\b(https?://[^\s<]{4,2000})")

LINK_REL = "ugc nofollow noopener noreferrer"


def render_html(text: str, *, allow_markdown: bool = True) -> str:
    """Escape first, then reintroduce the allowlisted constructs.

    The order is the whole security argument: by the time any pattern below
    runs, the input contains no `<`, `>` or quote characters at all, so a match
    can only ever have come from the author's literal text.
    """
    escaped = _escape(text)

    if not allow_markdown:
        return escaped.replace("\n", "<br>")

    placeholders: dict[str, str] = {}

    def stash(fragment: str) -> str:
        # Code spans must not have bold or links applied inside them, and a
        # link's href must not be re-processed as a bare URL.
        token = f"\x00P{len(placeholders)}\x00"
        placeholders[token] = fragment
        return token

    def code_sub(match: re.Match[str]) -> str:
        return stash(f"<code>{match.group(1)}</code>")

    def link_sub(match: re.Match[str]) -> str:
        label, raw_href = match.group(1), match.group(2)
        # The href was escaped along with everything else; unescape only to
        # parse it, and re-escape the value that actually lands in the markup.
        href = safe_href(html.unescape(raw_href))
        if href is None:
            return match.group(0)  # renders as the literal text the author typed
        return stash(
            f'<a href="{_escape(href)}" rel="{LINK_REL}" target="_blank">{label}</a>'
        )

    def bare_url_sub(match: re.Match[str]) -> str:
        href = safe_href(html.unescape(match.group(1)))
        if href is None:
            return match.group(0)
        shown = _escape(href if len(href) <= 60 else href[:57] + "...")
        return stash(f'<a href="{_escape(href)}" rel="{LINK_REL}" target="_blank">{shown}</a>')

    def spoiler_sub(match: re.Match[str]) -> str:
        inner = match.group(1)
        return (
            '<span class="cp-spoiler" data-cp-spoiler="1" tabindex="0" role="button" '
            'aria-expanded="false">'
            f'<span class="cp-spoiler__body">{inner}</span></span>'
        )

    out = _INLINE_CODE_RE.sub(code_sub, escaped)
    out = _LINK_RE.sub(link_sub, out)
    out = _BARE_URL_RE.sub(bare_url_sub, out)
    out = _BOLD_RE.sub(r"<strong>\1</strong>", out)
    out = _ITALIC_RE.sub(r"<em>\1</em>", out)
    out = _SPOILER_RE.sub(spoiler_sub, out)
    out = out.replace("\n", "<br>")

    for token, fragment in placeholders.items():
        out = out.replace(token, fragment)
    return out


def to_plain_preview(text: str, *, limit: int = 140) -> str:
    """A short, markup-free excerpt for moderation lists.

    Even this never reaches telemetry — see audit.py, which redacts bodies
    outright. It exists for the moderator's screen, which is a different
    audience with a different mandate.
    """
    flat = " ".join(text.split())
    if len(flat) <= limit:
        return flat
    return flat[: limit - 1] + "…"


@dataclass(frozen=True, slots=True)
class SanitizedBody:
    stored_text: str
    rendered_html: str
    link_count: int
    char_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "link_count": self.link_count,
            "char_count": self.char_count,
        }


def sanitize_body(
    raw: str, *, max_length: int, max_links: int, allow_markdown: bool = True
) -> SanitizedBody:
    stored = normalise(raw, max_length=max_length)
    enforce_link_cap(stored, max_links=max_links)
    return SanitizedBody(
        stored_text=stored,
        rendered_html=render_html(stored, allow_markdown=allow_markdown),
        link_count=count_links(stored),
        char_count=len(stored),
    )
