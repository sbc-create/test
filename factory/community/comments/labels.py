"""Heuristic labels for research + moderation scoring.

These scores NEVER auto-publish. Publication requires an explicit human
moderation action after gates (and COMMENTS_PUBLICATION_ENABLED — which
stays 0 in this stage).
"""

from __future__ import annotations

import re
from typing import Any

from factory.community.comments.pii import scan_pii

_SPOILER_RE = re.compile(
    r"(?i)\b(спойлер|spoiler|концовк\w*|финал\w*|ending|dies?|убив\w*)\b"
)
_TOXIC_RE = re.compile(
    r"(?i)\b(idiot|дурак|дебил|урод|ненавиж\w*|kill\s*yourself|убейся)\b"
)
_SPAM_URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
_SPAM_REPEAT_RE = re.compile(r"(.)\1{6,}")
_PROMO_RE = re.compile(r"(?i)\b(купить|промокод|скидка|free\s*nitro|crypto|казино)\b")
_POSITIVE_RE = re.compile(r"(?i)\b(люблю|нравится|отлично|супер|great|love|amazing)\b")
_NEGATIVE_RE = re.compile(r"(?i)\b(ненавижу|ужасно|отстой|плохо|hate|terrible|awful)\b")


def _clip(score: float) -> float:
    return max(0.0, min(1.0, float(score)))


def label_comment(body: str, *, body_normalized: str = "") -> dict[str, Any]:
    """Return heuristic label bundle. Never triggers publish."""
    text = body or ""
    norm = body_normalized or text.casefold()
    pii = scan_pii(text)

    spoiler = 0.85 if _SPOILER_RE.search(text) else 0.0
    toxicity = 0.9 if _TOXIC_RE.search(text) else 0.0
    spam = 0.0
    if _SPAM_URL_RE.search(text):
        spam += 0.4
    if _SPAM_REPEAT_RE.search(text):
        spam += 0.3
    if _PROMO_RE.search(text):
        spam += 0.5
    if len(norm) < 8 and _SPAM_URL_RE.search(text):
        spam += 0.2
    spam = _clip(spam)

    pos = 1.0 if _POSITIVE_RE.search(text) else 0.0
    neg = 1.0 if _NEGATIVE_RE.search(text) else 0.0
    if pos and neg:
        sentiment = "mixed"
        sentiment_score = 0.5
    elif pos:
        sentiment = "positive"
        sentiment_score = 0.8
    elif neg:
        sentiment = "negative"
        sentiment_score = 0.8
    else:
        sentiment = "neutral"
        sentiment_score = 0.0

    # Quality: prefer length in a readable band, punctuation present, low spam/tox.
    length = len(text.strip())
    quality = 0.5
    if 40 <= length <= 1200:
        quality += 0.25
    elif length < 15:
        quality -= 0.25
    if re.search(r"[.!?…]", text):
        quality += 0.1
    quality -= toxicity * 0.4
    quality -= spam * 0.4
    if pii["has_pii"]:
        quality -= 0.3
    quality = _clip(quality)

    risk = _clip(max(toxicity, spam, 0.7 if pii["has_pii"] else 0.0))
    return {
        "sentiment": sentiment,
        "sentiment_score": sentiment_score,
        "spoiler_score": spoiler,
        "spoiler_suggested": spoiler >= 0.5,
        "toxicity_score": toxicity,
        "spam_score": spam,
        "quality_score": quality,
        "pii": pii,
        "risk_score": risk,
        "auto_publish": False,  # hard invariant
        "labels_version": "COMMENT_LABELS_HEURISTIC_V1",
    }
