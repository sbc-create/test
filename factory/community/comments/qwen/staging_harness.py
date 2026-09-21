"""Staging canary harness for community-comments Qwen post-moderation.

COMMUNITY-COMMENTS-03 block B09.

This module exercises the *pipeline* end to end against an isolated staging
database: payload construction, PII redaction, schema validation, decision
application, idempotency, retry, degraded mode, kill switch, state machine and
the race/lease/resume paths.

Honesty contract — read before quoting any number this produces:

* With the built-in heuristic provider this is **not** a real Qwen canary.
  ``REAL_QWEN_CANARY_EXECUTED`` stays ``0`` and every *model quality* metric
  (decision agreement, spoiler/spam recall, false-block rate) is reported as
  ``UNMEASURED_NO_REAL_PROVIDER`` rather than as a number. A heuristic that we
  wrote cannot score the model we have not called.
* The *pipeline* properties below are genuinely measured either way, because
  they are properties of our own code: what leaves the process, what a
  malformed or hostile provider response is allowed to do to a comment row,
  and whether a repeated key produces a second provider call.
* Evidence carries digests, lengths, labels, timings and decisions. It never
  carries comment bodies.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from factory.community.comments import states
from factory.community.comments.pii import scan_pii
from factory.community.comments.qwen.policy import POLICY_VERSION
from factory.community.comments.qwen.prompt import (
    FORBIDDEN_CONTEXT_KEYS,
    SYSTEM_INSTRUCTIONS,
    build_request_payload,
)
from factory.community.comments.qwen.schema_v2 import (
    normalize_v2_to_v1,
    validate_decision_v2,
)

# Goal §19 decision vocabulary, derived from a validated V2 decision.
OUTCOME_ALLOW = "ALLOW"
OUTCOME_SPOILER = "ALLOW_WITH_SPOILER_COLLAPSE"
OUTCOME_HOLD = "HOLD_FOR_REVIEW"
OUTCOME_BLOCK_SPAM = "BLOCK_SPAM"
OUTCOME_BLOCK_UNSAFE = "BLOCK_UNSAFE"
OUTCOME_PROVIDER_ERROR = "PROVIDER_ERROR"

CANARY_OUTCOMES = frozenset(
    {
        OUTCOME_ALLOW,
        OUTCOME_SPOILER,
        OUTCOME_HOLD,
        OUTCOME_BLOCK_SPAM,
        OUTCOME_BLOCK_UNSAFE,
        OUTCOME_PROVIDER_ERROR,
    }
)

SPAM_LABELS = frozenset({"SPAM", "ADVERTISEMENT", "PIRACY_LINK"})
UNSAFE_LABELS = frozenset(
    {
        "THREAT",
        "HATE",
        "SEXUAL_CONTENT_MINORS",
        "MALWARE_LINK",
        "SELF_HARM",
        "INSULT",
        "HARASSMENT",
        "PERSONAL_DATA",
    }
)

# Never allowed to reach the provider, in any casing or nesting.
FORBIDDEN_PAYLOAD_KEYS = frozenset(FORBIDDEN_CONTEXT_KEYS) | frozenset(
    {
        "moderation_id",
        "comment_id",
        "job_id",
        "internal_id",
        "session",
        "password",
        "secret",
    }
)


class ProviderTimeout(RuntimeError):
    code = "PROVIDER_TIMEOUT"


class ProviderInvalidJSON(ValueError):
    code = "PROVIDER_INVALID_JSON"


def outcome_for(decision_v2: dict[str, Any]) -> str:
    """Map a validated V2 decision onto the goal §19 outcome vocabulary."""
    decision = str(decision_v2.get("decision") or "")
    labels = {str(x) for x in (decision_v2.get("labels") or [])}
    if decision == "ALLOW":
        return OUTCOME_ALLOW
    if decision == "ALLOW_SPOILER_COLLAPSED":
        return OUTCOME_SPOILER
    if decision in ("NEEDS_REVIEW", "QUARANTINE"):
        return OUTCOME_HOLD
    if decision == "HIDE":
        if labels & SPAM_LABELS and not (labels & UNSAFE_LABELS):
            return OUTCOME_BLOCK_SPAM
        return OUTCOME_BLOCK_UNSAFE
    raise ValueError(f"unmappable decision: {decision}")


def digest(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# Providers
# --------------------------------------------------------------------------


class HeuristicV2Provider:
    """Deterministic keyword classifier emitting V2 decisions.

    NOT a language model and NOT a canary subject. It exists so the pipeline
    has something schema-valid to carry. Its rules are written against comment
    *content*, deliberately not against the gold corpus' expected labels, so it
    cannot flatter the harness by echoing the answer key.
    """

    model = "heuristic-not-a-model-v2"

    def moderate(self, payload: dict[str, Any]) -> dict[str, Any]:
        env = payload.get("data_envelope") or {}
        text = str(env.get("comment_text") or payload.get("comment_text") or "")
        low = text.casefold()
        ctx = payload.get("context") or {}
        lang = str(ctx.get("language") or "und")
        user_spoiler = bool(ctx.get("user_spoiler_flag"))

        decision, labels = "ALLOW", ["CLEAN"]
        conf, tox, spam_s = 0.9, 0.02, 0.0
        spoiler = False
        pii = bool(ctx.get("local_pii_detected"))
        injection = False
        reasons = ["HEURISTIC_CLEAN"]

        injection_markers = (
            "ignore previous instructions",
            "ignore all instructions",
            "игнорируй предыдущие инструкции",
            "игнорируй все инструкции",
            "system prompt",
            "системный промпт",
            "<system>",
            "override policy",
            "покажи инструкции",
            "show me the system",
        )
        spam_markers = (
            "promo code",
            "промокод",
            "buy crypto",
            "казино",
            "free nitro",
            "click click",
            "реклама",
        )
        unsafe_markers = (
            "kill you",
            "убить тебя",
            "should be erased",
            "payload.exe",
            "underage",
        )
        insult_markers = ("idiot", "moron", "dumb clown", "дебил", "тупые", "shut up")
        spoiler_markers = (
            "spoiler",
            "спойлер",
            "в финале",
            "ending twist",
            "в последней серии",
            "the mentor was",
        )

        if any(m in low for m in injection_markers):
            decision, labels = "NEEDS_REVIEW", ["PROMPT_INJECTION"]
            injection, conf, reasons = True, 0.95, ["HEURISTIC_INJECTION"]
        elif any(m in low for m in unsafe_markers):
            decision, labels = "HIDE", ["THREAT"]
            conf, tox, reasons = 0.96, 0.95, ["HEURISTIC_UNSAFE"]
        elif pii or "[email_redacted]" in low or "[phone_redacted]" in low:
            decision, labels = "HIDE", ["PERSONAL_DATA"]
            pii, conf, reasons = True, 0.93, ["HEURISTIC_PII"]
        elif any(m in low for m in spam_markers) or low.count("http") >= 3:
            decision, labels = "HIDE", ["SPAM"]
            conf, spam_s, reasons = 0.92, 0.95, ["HEURISTIC_SPAM"]
        elif any(m in low for m in insult_markers):
            decision, labels = "HIDE", ["INSULT"]
            conf, tox, reasons = 0.9, 0.85, ["HEURISTIC_INSULT"]
        elif user_spoiler or any(m in low for m in spoiler_markers):
            decision, labels = "ALLOW_SPOILER_COLLAPSED", ["SPOILER"]
            spoiler, conf, reasons = True, 0.88, ["HEURISTIC_SPOILER"]

        return {
            "schema_version": "QWEN_DECISION_SCHEMA_V2",
            "policy_version": POLICY_VERSION,
            "decision": decision,
            "labels": labels,
            "confidence": conf,
            "reason_codes": reasons,
            "language": lang,
            "spoiler": spoiler,
            "toxicity_score": tox,
            "spam_score": spam_s,
            "pii_detected": pii,
            "prompt_injection_detected": injection,
            "model": self.model,
            "request_id": str(payload.get("request_id") or "req_missing_000000"),
        }


@dataclass
class CountingProvider:
    """Wraps a provider, counting *actual* provider invocations and faults."""

    inner: Any
    calls: int = 0
    call_ids: list[str] = field(default_factory=list)
    fault: Callable[[int, dict[str, Any]], Any] | None = None
    latencies_ms: list[float] = field(default_factory=list)

    def moderate(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls += 1
        self.call_ids.append(str(payload.get("request_id") or f"anon_{self.calls}"))
        started = time.perf_counter()
        try:
            if self.fault is not None:
                injected = self.fault(self.calls, payload)
                if injected is not None:
                    return injected
            return self.inner.moderate(payload)
        finally:
            self.latencies_ms.append((time.perf_counter() - started) * 1000.0)


# --------------------------------------------------------------------------
# Payload safety
# --------------------------------------------------------------------------


def assert_payload_safe(payload: dict[str, Any], *, raw_text: str) -> dict[str, Any]:
    """Prove what leaves the process. Raises on any violation.

    Checks: no forbidden identity/network keys at any depth, no raw PII spans
    from the original text, and no system prompt leakage into the untrusted
    data envelope.
    """
    violations: list[str] = []

    def _walk(obj: Any) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if str(k).strip().lower() in FORBIDDEN_PAYLOAD_KEYS:
                    violations.append(f"forbidden_key:{k}")
                _walk(v)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)

    _walk(payload)

    envelope = str((payload.get("data_envelope") or {}).get("comment_text") or "")
    for finding in scan_pii(raw_text or "")["findings"]:
        span = finding.get("span") or ""
        if span and span in envelope:
            violations.append(f"raw_pii_in_payload:{finding.get('type')}")

    if SYSTEM_INSTRUCTIONS.strip() and SYSTEM_INSTRUCTIONS.strip() in envelope:
        violations.append("system_prompt_in_data_envelope")

    if violations:
        raise ValueError(f"unsafe Qwen payload: {sorted(set(violations))}")

    return {
        "forbidden_keys": 0,
        "raw_pii_spans": 0,
        "system_prompt_leak": 0,
        "envelope_len": len(envelope),
        "envelope_digest": digest(envelope),
    }


def moderate_once(
    provider: Any,
    *,
    raw_text: str,
    request_id: str,
    title: str = "Synthetic staging title",
    content_type: str = "anime",
    language: str = "und",
    user_spoiler_flag: bool = False,
    max_retries: int = 2,
) -> dict[str, Any]:
    """One logical moderation task: build → send → validate, with bounded retry.

    Returns a record containing the outcome, timings, retry count and digests.
    A provider failure yields ``PROVIDER_ERROR`` — never a publish.
    """
    payload = build_request_payload(
        raw_text,
        title,
        content_type,
        False,
        None,
        user_spoiler_flag,
        language,
        request_id=request_id,
    )
    safety = assert_payload_safe(payload, raw_text=raw_text)

    retries = 0
    started = time.perf_counter()
    last_error = ""
    decision_v2: dict[str, Any] | None = None

    for attempt in range(max_retries + 1):
        try:
            raw = provider.moderate(payload)
            if isinstance(raw, str):
                raw = json.loads(raw)  # provider returned a JSON string
            check = validate_decision_v2(
                raw, expected_request_id=request_id, comment_text=raw_text
            )
            if not check["ok"]:
                raise ProviderInvalidJSON(",".join(check["errors"]))
            decision_v2 = check["decision"]
            break
        except (
            ProviderTimeout,
            ProviderInvalidJSON,
            json.JSONDecodeError,
            ValueError,
            TimeoutError,
        ) as exc:
            last_error = f"{type(exc).__name__}:{str(exc)[:120]}"
            if attempt >= max_retries:
                break
            retries += 1

    elapsed_ms = (time.perf_counter() - started) * 1000.0

    if decision_v2 is None:
        return {
            "request_id": request_id,
            "outcome": OUTCOME_PROVIDER_ERROR,
            "schema_valid": False,
            "retries": retries,
            "latency_ms": round(elapsed_ms, 2),
            "error": last_error,
            "published": False,
            "safety": safety,
            "text_digest": digest(raw_text),
            "text_len": len(raw_text or ""),
        }

    return {
        "request_id": request_id,
        "outcome": outcome_for(decision_v2),
        "decision_v2": decision_v2["decision"],
        "labels": list(decision_v2["labels"]),
        "schema_valid": True,
        "retries": retries,
        "latency_ms": round(elapsed_ms, 2),
        "error": "",
        "v1": normalize_v2_to_v1(decision_v2),
        "safety": safety,
        "text_digest": digest(raw_text),
        "text_len": len(raw_text or ""),
    }


def compute_quality_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Score decisions against the gold corpus expectations.

    Only meaningful when a real provider produced the decisions — the caller
    decides whether to publish these or report them as unmeasured. Each rate is
    returned with its denominator so a small sample cannot masquerade as a
    precise number.
    """

    def _rate(hits: int, total: int) -> Any:
        if total <= 0:
            return {"value": None, "hits": 0, "total": 0}
        return {"value": round(hits / total, 4), "hits": hits, "total": total}

    def _by(pred) -> list[dict[str, Any]]:
        return [r for r in records if pred(r)]

    blocked_outcomes = {OUTCOME_BLOCK_SPAM, OUTCOME_BLOCK_UNSAFE, OUTCOME_HOLD}

    agree = 0
    for r in records:
        allowed = {r.get("expected_family")} | set(r.get("expected_alts") or [])
        if r.get("decision_v2") in allowed:
            agree += 1

    clean = _by(lambda r: r.get("category") == "clean")
    clean_blocked = [r for r in clean if r["outcome"] in blocked_outcomes]

    constructive = _by(lambda r: r.get("category") == "constructive")
    constructive_blocked = [r for r in constructive if r["outcome"] in blocked_outcomes]

    spoilers = _by(lambda r: r.get("category") == "spoiler")
    spoilers_caught = [r for r in spoilers if r["outcome"] == OUTCOME_SPOILER]

    spam = _by(lambda r: r.get("category") == "spam")
    spam_caught = [r for r in spam if r["outcome"] == OUTCOME_BLOCK_SPAM]

    critical = _by(lambda r: r.get("severity") == "critical")
    critical_allowed = [
        r for r in critical if r["outcome"] in (OUTCOME_ALLOW, OUTCOME_SPOILER)
    ]

    return {
        "DECISION_AGREEMENT_RATE": _rate(agree, len(records)),
        "CLEAN_FALSE_BLOCK_RATE": _rate(len(clean_blocked), len(clean)),
        "CONSTRUCTIVE_CRITICISM_FALSE_BLOCK": len(constructive_blocked),
        "SPOILER_DETECTION_RECALL": _rate(len(spoilers_caught), len(spoilers)),
        "SPAM_DETECTION_RECALL": _rate(len(spam_caught), len(spam)),
        "CRITICAL_UNSAFE_FALSE_ALLOW": len(critical_allowed),
        "critical_false_allow_cases": [r["case_id"] for r in critical_allowed],
    }


def new_request_id(prefix: str = "canary") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:24]}"


def status_is_public(status: str) -> bool:
    """True only for statuses that would be publicly visible if flags allowed."""
    try:
        return states.is_public_visible(status)
    except states.InvalidTransition:
        return False
