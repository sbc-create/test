"""Unit tests for comments research PII scan/strip."""

from __future__ import annotations

from factory.community.comments_research.corpus_store import assert_derived_only_row
from factory.community.comments_research.pii_scan import (
    pii_reject_reason,
    redact_text_pii,
    scan_text_pii,
    strip_identity_fields,
)


def test_strip_identity_fields_removes_user_blob():
    payload = {
        "id": 1,
        "user": {"name": "alice", "avatar": "http://x/a.png"},
        "media": {"title": {"romaji": "Test"}},
        "email": "a@b.c",
    }
    cleaned = strip_identity_fields(payload)
    assert "user" not in cleaned
    assert "email" not in cleaned
    assert cleaned["media"]["title"]["romaji"] == "Test"


def test_scan_and_redact_email_phone_ip():
    text = "Contact me at demo@example.com or +1 555-123-4567 from 203.0.113.10"
    hits = scan_text_pii(text)
    assert hits["emails"] == 1
    assert hits["ips"] == 1
    red = redact_text_pii(text)
    assert "demo@example.com" not in red
    assert "203.0.113.10" not in red
    assert pii_reject_reason(text) == "pii_pattern_in_body"


def test_derived_only_row_rejects_body():
    row = {
        "storage_mode": "DERIVED_ONLY",
        "body": "full comment text must not be stored",
    }
    try:
        assert_derived_only_row(row)
        raised = False
    except ValueError:
        raised = True
    assert raised
