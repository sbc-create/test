"""PII scanner tests."""

from __future__ import annotations

from factory.community.comments.pii import redact_preview, scan_pii


def test_email_detected():
    out = scan_pii("Пишите на user@example.com пожалуйста")
    assert out["has_pii"] is True
    assert any(f["type"] == "email" for f in out["findings"])


def test_clean_text():
    out = scan_pii("Отличный сериал, особенно второй сезон.")
    assert out["has_pii"] is False


def test_redact_preview():
    text = "контакт: user@example.com конец"
    findings = scan_pii(text)["findings"]
    red = redact_preview(text, findings)
    assert "user@example.com" not in red
    assert "REDACTED" in red
