"""Technical preflight tests — no content judgement."""

from __future__ import annotations

import pytest

from factory.community.comments.preflight import PreflightError, preflight_or_reject, run_preflight


def test_ok_normal_comment():
    r = run_preflight("Этот фильм отличный и атмосферный")
    assert r["ok"] is True
    assert r["reject_code"] is None
    assert r["digest"]
    assert r["word_count"] >= 2


def test_unicode_nfc():
    # café composed vs decomposed
    r = run_preflight("café is great")
    assert r["ok"]
    assert "café" in r["body"] or "cafe" in r["body_normalized"]


def test_strips_html_xss():
    r = run_preflight("Hello <script>alert(1)</script> world")
    assert r["ok"]
    assert "<script>" not in r["body"]
    assert "alert" not in r["body"] or "script" not in r["body"].lower()


def test_too_long():
    with pytest.raises(PreflightError) as ei:
        run_preflight("word " * 2000)
    assert ei.value.reject_code == "TOO_LONG"


def test_too_short_words():
    with pytest.raises(PreflightError) as ei:
        run_preflight("hi")
    assert ei.value.reject_code == "TOO_SHORT"


def test_empty():
    with pytest.raises(PreflightError) as ei:
        run_preflight("   ")
    assert ei.value.reject_code in {"EMPTY", "TOO_SHORT", "SANITIZE"}


def test_too_many_links():
    body = "check https://a.example/x and https://b.example/y and https://c.example/z please"
    with pytest.raises(PreflightError) as ei:
        run_preflight(body)
    assert ei.value.reject_code == "TOO_MANY_LINKS"


def test_duplicate_digest_hook():
    seen: set[str] = set()

    def dup(d: str) -> bool:
        if d in seen:
            return True
        seen.add(d)
        return False

    r1 = run_preflight("unique comment about plot", duplicate_check=dup)
    assert r1["ok"]
    with pytest.raises(PreflightError) as ei:
        run_preflight("unique comment about plot", duplicate_check=dup)
    assert ei.value.reject_code == "DUPLICATE_DIGEST"


def test_flood_pattern():
    with pytest.raises(PreflightError) as ei:
        run_preflight("aaaaaaaaaaaaaaaa spam flood here")
    assert "FLOOD" in ei.value.reject_code


def test_newlines_limit():
    body = "line\n" * 50 + "end words"
    with pytest.raises(PreflightError) as ei:
        run_preflight(body)
    assert ei.value.reject_code == "TOO_MANY_NEWLINES"


def test_preflight_or_reject_wrapper():
    bad = preflight_or_reject("x")
    assert bad["ok"] is False
    assert bad["reject_code"]
    good = preflight_or_reject("two meaningful words here")
    assert good["ok"] is True


def test_does_not_judge_toxicity():
    # Preflight must accept rude-but-technical-ok text (Qwen's job)
    r = run_preflight("This movie is terrible garbage nonsense honestly")
    assert r["ok"] is True
