"""Unit tests for comments research dedupe."""

from __future__ import annotations

from factory.community.comments_research.dedupe import DedupeIndex, content_digest, normalize_text


def test_normalize_and_digest_stable():
    a = content_digest("Hello, World!!!")
    b = content_digest("  hello world  ")
    assert a == b
    assert normalize_text("A\u00a0B") == normalize_text("a b")


def test_exact_duplicate_rejected():
    idx = DedupeIndex()
    ok1, d1, _ = idx.offer("This is a unique research sentence about pacing.")
    ok2, d2, _ = idx.offer("This is a unique research sentence about pacing.")
    assert ok1 and d1
    assert not ok2 and d2 == d1
    assert idx.exact_rejected == 1


def test_near_duplicate_rejected():
    idx = DedupeIndex()
    base = "The cinematography is stunning and the soundtrack elevates every scene " * 3
    ok1, _, _ = idx.offer(base)
    ok2, _, _ = idx.offer(base + " extra tail words only")
    assert ok1
    assert not ok2
    assert idx.near_rejected == 1
