"""Tests for Qwen V2 schema, caps, runtime preflight, PII→Qwen redaction."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.community.comments.pii import redact_for_qwen, scan_pii
from factory.community.comments.qwen.caps import (
    CapExceeded,
    CapLedger,
    assert_within_caps,
    record_call,
)
from factory.community.comments.qwen.gold_corpus import GOLD_CASES, case_digest, manifest, write_fixture
from factory.community.comments.qwen.prompt import build_request_payload
from factory.community.comments.qwen.runtime_preflight import runtime_preflight
from factory.community.comments.qwen.schema_v2 import (
    normalize_v2_to_v1,
    validate_decision_v2,
)


def _valid_v2(**over):
    base = {
        "schema_version": "QWEN_DECISION_SCHEMA_V2",
        "policy_version": "QWEN_MODERATION_POLICY_V1",
        "decision": "ALLOW",
        "labels": ["CLEAN"],
        "confidence": 0.91,
        "reason_codes": ["OK"],
        "language": "ru",
        "spoiler": False,
        "toxicity_score": 0.01,
        "spam_score": 0.0,
        "pii_detected": False,
        "prompt_injection_detected": False,
        "model": "test-model",
        "request_id": "req_abcdefghijklmnopqrstuvwxyz",
    }
    base.update(over)
    return base


def test_schema_v2_accepts_valid():
    out = validate_decision_v2(_valid_v2())
    assert out["ok"] is True


def test_schema_v2_rejects_unknown_decision_and_forbidden_keys():
    bad = _valid_v2(decision="DELETE_EVERYTHING", sql="drop table")
    out = validate_decision_v2(bad)
    assert out["ok"] is False


def test_schema_v2_request_id_mismatch():
    out = validate_decision_v2(_valid_v2(), expected_request_id="other_id_value_xx")
    assert out["ok"] is False
    assert "request_id_mismatch" in out["errors"]


def test_normalize_v2_maps_to_v1_actions():
    v1 = normalize_v2_to_v1(_valid_v2(decision="ALLOW_SPOILER_COLLAPSED", spoiler=True))
    assert v1["action"] == "ALLOW_COLLAPSED_SPOILER"
    assert v1["spoiler_detected"] is True
    v1h = normalize_v2_to_v1(_valid_v2(decision="HIDE", labels=["THREAT"]))
    assert v1h["action"] == "HIDE_HIGH_CONFIDENCE"


def test_redact_for_qwen_placeholders():
    text = "mail me user@example.com or +1 555-999-8888 from 203.0.113.9 api_key=sk_live_abcdefghi"
    out = redact_for_qwen(text)
    assert out["pii_detected"] is True
    assert "user@example.com" not in out["text"]
    assert "[EMAIL_REDACTED]" in out["text"]
    assert "[PHONE_REDACTED]" in out["text"] or "[IP_REDACTED]" in out["text"]
    assert "sk_live_abcdefghi" not in out["text"]


def test_payload_uses_redacted_text_only():
    payload = build_request_payload(
        "contact canary.user@example.com please",
        title="T",
        content_type="anime",
        is_reply=False,
        parent_excerpt=None,
        user_spoiler_flag=False,
        language="en",
        request_id="req_payload_test_0001",
    )
    assert "canary.user@example.com" not in payload["comment_text"]
    assert "[EMAIL_REDACTED]" in payload["comment_text"]
    assert payload["data_envelope"]["pii_placeholders_applied"] is True
    assert "device_id" not in payload
    assert payload["schema_version"] == "QWEN_DECISION_SCHEMA_V2"


def test_caps_block_over_request_limit(tmp_path):
    led = CapLedger()
    path = tmp_path / "ledger.json"
    for i in range(50):
        record_call(
            led,
            call_id=f"c{i}",
            is_retry=False,
            input_tokens=1,
            output_tokens=1,
            spend_rub=0.01,
            path=path,
        )
        led = CapLedger(**json.loads(path.read_text()))
    with pytest.raises(CapExceeded):
        record_call(
            led,
            call_id="c50",
            is_retry=False,
            input_tokens=1,
            output_tokens=1,
            spend_rub=0.01,
            path=path,
        )


def test_caps_reject_duplicate_call_id(tmp_path):
    led = CapLedger()
    path = tmp_path / "ledger.json"
    record_call(
        led, call_id="same", is_retry=False, input_tokens=1, output_tokens=1, spend_rub=0.0, path=path
    )
    led = CapLedger(**json.loads(path.read_text()))
    with pytest.raises(CapExceeded):
        record_call(
            led, call_id="same", is_retry=True, input_tokens=1, output_tokens=1, spend_rub=0.0, path=path
        )


def test_runtime_preflight_blocked_without_config():
    report = runtime_preflight()
    assert report["QWEN_PROVIDER_CONFIGURED"] == "NO"
    assert report["READY_FOR_REAL_CANARY"] is False
    assert report["checks"]["production_publication_off"] is True


def test_gold_corpus_has_40_cases_and_digests(tmp_path):
    assert len(GOLD_CASES) == 40
    man = manifest()
    assert man["count"] == 40
    digests = {c["body_digest"] for c in man["cases"]}
    assert len(digests) == 40
    p = write_fixture(tmp_path / "gold.json")
    loaded = json.loads(p.read_text())
    assert loaded["count"] == 40
    # evidence-style: digest matches body
    for c in GOLD_CASES:
        assert case_digest(c["body"]) == next(
            x["body_digest"] for x in man["cases"] if x["case_id"] == c["case_id"]
        )
