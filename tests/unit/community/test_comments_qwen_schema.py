"""Qwen decision schema + policy mapping tests."""

from __future__ import annotations

from factory.community.comments import states
from factory.community.comments.qwen.policy import apply_action_to_status
from factory.community.comments.qwen.provider import FakeQwenProvider, discover_config
from factory.community.comments.qwen.schema import validate_decision


def _base(**overrides):
    d = {
        "schema_version": "QWEN_DECISION_SCHEMA_V1",
        "policy_version": "QWEN_MODERATION_POLICY_V1",
        "action": "ALLOW",
        "labels": ["CLEAN"],
        "confidence": 0.9,
        "spoiler_detected": False,
        "language": "ru",
        "reason_codes": ["OK"],
        "needs_human_review": False,
        "model": "test-model",
        "prompt_digest": "a" * 64,
    }
    d.update(overrides)
    return d


def test_valid_decision():
    r = validate_decision(_base())
    assert r["ok"] is True
    assert r["errors"] == []


def test_rejects_bad_action():
    r = validate_decision(_base(action="DELETE"))
    assert r["ok"] is False


def test_rejects_unknown_label():
    r = validate_decision(_base(labels=["NOT_A_LABEL"]))
    assert r["ok"] is False


def test_rejects_echo_full_comment():
    text = "This is a sufficiently long comment body to detect echo"
    r = validate_decision(_base(reason_codes=[text]), comment_text=text)
    assert r["ok"] is False
    assert any("echo" in e.lower() for e in r["errors"])


def test_rejects_forbidden_body_field():
    d = _base()
    d["comment_text"] = "nope"
    r = validate_decision(d)
    assert r["ok"] is False


def test_policy_allow():
    m = apply_action_to_status("ALLOW", ["CLEAN"], 0.9)
    assert m["new_status"] == states.VISIBLE_QWEN_APPROVED


def test_policy_spoiler():
    m = apply_action_to_status("ALLOW_COLLAPSED_SPOILER", ["SPOILER"], 0.8)
    assert m["new_status"] == states.VISIBLE_SPOILER_COLLAPSED
    assert m["spoiler_collapsed"] is True


def test_policy_low_confidence_hold():
    m = apply_action_to_status("ALLOW", ["CLEAN"], 0.2)
    assert m["new_status"] == states.HELD_FOR_REVIEW


def test_policy_force_hide_threat():
    m = apply_action_to_status("ALLOW", ["THREAT"], 0.99)
    assert m["new_status"] == states.HIDDEN_QWEN_HIGH_CONFIDENCE
    assert m["needs_human_review"] is True


def test_policy_personal_data():
    m = apply_action_to_status("HOLD_FOR_REVIEW", ["PERSONAL_DATA"], 0.8)
    assert m["new_status"] == states.HIDDEN_QWEN_HIGH_CONFIDENCE
    assert m["needs_human_review"] is True


def test_criticism_allowed_path():
    m = apply_action_to_status("ALLOW", ["CLEAN"], 0.85)
    assert m["new_status"] == states.VISIBLE_QWEN_APPROVED


def test_fake_provider_deterministic():
    p = FakeQwenProvider()
    d = p.moderate(
        {
            "comment_text": "great show overall",
            "prompt_digest": "b" * 64,
            "context": {"language": "en", "user_spoiler_flag": False},
        }
    )
    assert validate_decision(d)["ok"]
    assert d["action"] == "ALLOW"


def test_fake_provider_threat():
    p = FakeQwenProvider()
    d = p.moderate({"comment_text": "I will kill you tonight", "prompt_digest": "c" * 64})
    assert d["action"] == "HIDE_HIGH_CONFIDENCE"
    assert "THREAT" in d["labels"]


def test_discover_config_unconfigured():
    cfg = discover_config()
    assert cfg["QWEN_PROVIDER_CONFIGURED"] in {"YES", "NO"}
    # Default CI/dev has no credential file
    assert cfg["live_disabled_unless_configured"] is True
