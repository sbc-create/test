"""Heuristic labels for research observations (not production moderation verdicts)."""

from __future__ import annotations

import re
from typing import Any

SPOILER_RE = re.compile(
    r"\b(spoiler|spoilers|спойлер|спойлеры|развязка|ending\s+reveals?)\b", re.I
)
TOXIC_RE = re.compile(
    r"\b(kill\s+yourself|kys|hate\s+you|idiot|moron|дебил|урод|ненавижу\s+тебя)\b",
    re.I,
)
SPAM_RE = re.compile(
    r"(https?://\S+){2,}|\b(buy\s+now|crypto\s+signal|казино|промокод|viagra)\b",
    re.I,
)
POS_RE = re.compile(
    r"\b(love|loved|amazing|masterpiece|great|excellent|прекрасно|шедевр|отлично|люблю)\b",
    re.I,
)
NEG_RE = re.compile(
    r"\b(hate|awful|terrible|worst|boring|ужасно|скучно|ненавижу|отстой)\b", re.I
)


def detect_language(text: str) -> str:
    if not text:
        return "und"
    cyr = sum(1 for ch in text if "\u0400" <= ch <= "\u04FF")
    latin = sum(1 for ch in text if ("a" <= ch.lower() <= "z"))
    if cyr >= 20 and cyr > latin:
        return "ru"
    if latin >= 20 and latin >= cyr:
        return "en"
    if cyr > 0 and cyr >= latin:
        return "ru"
    if latin > 0:
        return "en"
    return "other"


def structural_template(text: str) -> dict[str, Any]:
    text = text or ""
    sentences = [s for s in re.split(r"[.!?…]+", text) if s.strip()]
    words = re.findall(r"\w+", text, flags=re.UNICODE)
    return {
        "char_len": len(text),
        "word_count": len(words),
        "sentence_count": len(sentences),
        "question_mark": 1 if "?" in text or "？" in text else 0,
        "exclamation": 1 if "!" in text else 0,
        "has_url": 1 if re.search(r"https?://", text) else 0,
        "avg_word_len": round(sum(len(w) for w in words) / len(words), 2) if words else 0.0,
        "newline_count": text.count("\n"),
    }


def label_observation(text: str) -> dict[str, Any]:
    text = text or ""
    pos = len(POS_RE.findall(text))
    neg = len(NEG_RE.findall(text))
    if pos > neg and pos > 0:
        sentiment = "positive"
    elif neg > pos and neg > 0:
        sentiment = "negative"
    elif pos or neg:
        sentiment = "mixed"
    else:
        sentiment = "neutral"

    spoiler = bool(SPOILER_RE.search(text))
    toxic = bool(TOXIC_RE.search(text))
    spam = bool(SPAM_RE.search(text))
    words = len(re.findall(r"\w+", text, flags=re.UNICODE))
    if words < 8:
        quality = "too_short"
    elif spam or toxic:
        quality = "low"
    elif words >= 40:
        quality = "high"
    else:
        quality = "medium"

    usefulness = "low"
    if quality == "high" and not spam and not toxic:
        usefulness = "high"
    elif quality == "medium" and not spam:
        usefulness = "medium"

    return {
        "sentiment": sentiment,
        "spoiler": spoiler,
        "toxicity": "likely" if toxic else "unlikely",
        "spam": spam,
        "quality": quality,
        "usefulness": usefulness,
        "language": detect_language(text),
        "structural_template": structural_template(text),
    }
