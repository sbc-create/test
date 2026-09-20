"""Dedupe helpers for research observations (digest / near-duplicate)."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Iterable


_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = text.casefold().strip()
    text = _PUNCT_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text)
    return text.strip()


def content_digest(text: str) -> str:
    norm = normalize_text(text)
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def near_duplicate_key(text: str, *, prefix_chars: int = 160) -> str:
    """Cheap near-dup key: normalized prefix hash (not cryptographic identity)."""
    norm = normalize_text(text)
    prefix = norm[:prefix_chars]
    return hashlib.sha256(prefix.encode("utf-8")).hexdigest()


class DedupeIndex:
    def __init__(self) -> None:
        self._exact: set[str] = set()
        self._near: set[str] = set()
        self.exact_rejected = 0
        self.near_rejected = 0

    def seen_exact(self, digest: str) -> bool:
        return digest in self._exact

    def offer(self, text: str) -> tuple[bool, str, str]:
        """Return (accepted, digest, near_key). Reject exact/near duplicates."""
        digest = content_digest(text)
        if digest in self._exact:
            self.exact_rejected += 1
            return False, digest, ""
        near = near_duplicate_key(text)
        if near in self._near:
            self.near_rejected += 1
            return False, digest, near
        self._exact.add(digest)
        self._near.add(near)
        return True, digest, near

    def load_digests(self, digests: Iterable[str]) -> None:
        for d in digests:
            if d:
                self._exact.add(d)
