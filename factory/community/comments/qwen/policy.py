"""Versioned SSOT moderation policy for applying Qwen decisions (goal §13)."""

from __future__ import annotations

from typing import Any

from factory.community.comments import states

POLICY_VERSION = "QWEN_MODERATION_POLICY_V1"

QWEN_MODERATION_POLICY_V1: dict[str, Any] = {
    "policy_version": POLICY_VERSION,
    "confidence_thresholds": {
        "allow_min": 0.70,
        "hide_min": 0.85,
        "spoiler_min": 0.65,
        "low_confidence_max": 0.55,
    },
    "force_hide_labels": [
        "SEXUAL_CONTENT_MINORS",
        "THREAT",
        "HATE",
        "MALWARE_LINK",
    ],
    "hide_and_human_labels": [
        "PERSONAL_DATA",
        "SELF_HARM",
    ],
    "spoiler_action": "ALLOW_COLLAPSED_SPOILER",
    "criticism_allowed": True,
    "notes": [
        "Ordinary film criticism and negative ratings are not violations",
        "Disagreement with another user is not automatically harassment",
        "Spoilers are collapsed, never auto-deleted",
        "Physical deletion by automation is forbidden",
        "Low confidence always holds for human review",
    ],
}


def apply_action_to_status(
    action: str,
    labels: list[str] | None,
    confidence: float,
    *,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Map Qwen action + labels + confidence → new_status + reason.

    Override rules (policy SSOT):
    - low confidence → HELD_FOR_REVIEW
    - SEXUAL_CONTENT_MINORS / THREAT / HATE / MALWARE → HIDE
    - PERSONAL_DATA → HIDE + human review flag
    """
    pol = policy or QWEN_MODERATION_POLICY_V1
    thr = pol["confidence_thresholds"]
    labels = list(labels or [])
    label_set = set(labels)
    reason_codes: list[str] = []
    needs_human = False

    # Hard safety labels first
    force_hide = set(pol.get("force_hide_labels") or [])
    hit_force = sorted(label_set & force_hide)
    if hit_force:
        reason_codes.extend(f"FORCE_HIDE:{x}" for x in hit_force)
        return {
            "new_status": states.HIDDEN_QWEN_HIGH_CONFIDENCE,
            "reason": "force_hide_label",
            "reason_codes": reason_codes,
            "needs_human_review": True,
            "spoiler_collapsed": False,
            "policy_version": pol["policy_version"],
            "effective_action": "HIDE_HIGH_CONFIDENCE",
        }

    hide_human = set(pol.get("hide_and_human_labels") or [])
    hit_pd = sorted(label_set & hide_human)
    if hit_pd:
        reason_codes.extend(f"HIDE_HUMAN:{x}" for x in hit_pd)
        return {
            "new_status": states.HIDDEN_QWEN_HIGH_CONFIDENCE,
            "reason": "personal_data_or_self_harm",
            "reason_codes": reason_codes,
            "needs_human_review": True,
            "spoiler_collapsed": False,
            "policy_version": pol["policy_version"],
            "effective_action": "HIDE_HIGH_CONFIDENCE",
        }

    # Low confidence → hold regardless of proposed action
    if float(confidence) < float(thr["low_confidence_max"]):
        return {
            "new_status": states.HELD_FOR_REVIEW,
            "reason": "low_confidence",
            "reason_codes": ["LOW_CONFIDENCE"],
            "needs_human_review": True,
            "spoiler_collapsed": False,
            "policy_version": pol["policy_version"],
            "effective_action": "HOLD_FOR_REVIEW",
        }

    action_u = (action or "").upper()
    if action_u == "ALLOW":
        if float(confidence) < float(thr["allow_min"]):
            return {
                "new_status": states.HELD_FOR_REVIEW,
                "reason": "allow_below_threshold",
                "reason_codes": ["ALLOW_BELOW_THRESHOLD"],
                "needs_human_review": True,
                "spoiler_collapsed": False,
                "policy_version": pol["policy_version"],
                "effective_action": "HOLD_FOR_REVIEW",
            }
        return {
            "new_status": states.VISIBLE_QWEN_APPROVED,
            "reason": "allow",
            "reason_codes": reason_codes or ["ALLOW"],
            "needs_human_review": needs_human,
            "spoiler_collapsed": False,
            "policy_version": pol["policy_version"],
            "effective_action": "ALLOW",
        }

    if action_u == "ALLOW_COLLAPSED_SPOILER":
        return {
            "new_status": states.VISIBLE_SPOILER_COLLAPSED,
            "reason": "spoiler_collapsed",
            "reason_codes": reason_codes or ["SPOILER"],
            "needs_human_review": False,
            "spoiler_collapsed": True,
            "policy_version": pol["policy_version"],
            "effective_action": "ALLOW_COLLAPSED_SPOILER",
        }

    if action_u == "HIDE_HIGH_CONFIDENCE":
        if float(confidence) < float(thr["hide_min"]):
            return {
                "new_status": states.HELD_FOR_REVIEW,
                "reason": "hide_below_threshold",
                "reason_codes": ["HIDE_BELOW_THRESHOLD"],
                "needs_human_review": True,
                "spoiler_collapsed": False,
                "policy_version": pol["policy_version"],
                "effective_action": "HOLD_FOR_REVIEW",
            }
        return {
            "new_status": states.HIDDEN_QWEN_HIGH_CONFIDENCE,
            "reason": "hide_high_confidence",
            "reason_codes": reason_codes or ["HIDE"],
            "needs_human_review": False,
            "spoiler_collapsed": False,
            "policy_version": pol["policy_version"],
            "effective_action": "HIDE_HIGH_CONFIDENCE",
        }

    # HOLD_FOR_REVIEW or unknown action
    return {
        "new_status": states.HELD_FOR_REVIEW,
        "reason": "hold_for_review",
        "reason_codes": reason_codes or ["HOLD"],
        "needs_human_review": True,
        "spoiler_collapsed": False,
        "policy_version": pol["policy_version"],
        "effective_action": "HOLD_FOR_REVIEW",
    }
