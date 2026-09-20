"""Qwen provider Protocol + Fake (deterministic) + Live (credential-gated)."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Protocol

from factory.community.comments.qwen.policy import POLICY_VERSION
from factory.community.comments.qwen.prompt import build_request_payload
from factory.community.comments.qwen.schema import validate_decision

CONFIG_ENV_KEYS = (
    "QWEN_COMMENTS_ENDPOINT",
    "QWEN_COMMENTS_TOKEN_FILE",
    "QWEN_COMMENTS_MODE",  # dry_run | http_post | fake
)

DEFAULT_TIMEOUT_SEC = 8.0
DEFAULT_MAX_RETRIES = 2
DEFAULT_MAX_RESPONSE_BYTES = 32_768
FAKE_MODEL = "fake-qwen-comments-v1"


class CircuitOpenError(RuntimeError):
    code = "CIRCUIT_OPEN"


class QwenProvider(Protocol):
    def moderate(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Return a decision dict (may still fail schema validation upstream)."""


def discover_config() -> dict[str, Any]:
    """Mirror factory.ratings.qwen_delivery.discover_config for comments."""
    endpoint = os.environ.get("QWEN_COMMENTS_ENDPOINT", "").strip()
    token_file = os.environ.get("QWEN_COMMENTS_TOKEN_FILE", "").strip()
    mode = os.environ.get("QWEN_COMMENTS_MODE", "").strip() or (
        "http_post" if endpoint else "unset"
    )
    configured = bool(endpoint and token_file and Path(token_file).is_file())
    return {
        "configured": configured,
        "endpoint_set": bool(endpoint),
        "token_file_set": bool(token_file),
        "token_file_exists": bool(token_file and Path(token_file).is_file()),
        "mode": mode,
        "QWEN_PROVIDER_CONFIGURED": "YES" if configured else "NO",
        "env_keys": list(CONFIG_ENV_KEYS),
        "note": "Do not invent endpoint/credentials; require ops-provided systemd credential",
        "live_disabled_unless_configured": True,
    }


class CircuitBreakerStub:
    """Minimal circuit breaker stub — opens after N consecutive failures."""

    def __init__(self, failure_threshold: int = 5) -> None:
        self.failure_threshold = failure_threshold
        self.consecutive_failures = 0
        self.open = False

    def record_success(self) -> None:
        self.consecutive_failures = 0
        self.open = False

    def record_failure(self) -> None:
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.failure_threshold:
            self.open = True

    def ensure_closed(self) -> None:
        if self.open:
            raise CircuitOpenError("qwen comments circuit open")


class FakeQwenProvider:
    """Deterministic rules for tests / canary without network."""

    model = FAKE_MODEL

    def moderate(self, payload: dict[str, Any]) -> dict[str, Any]:
        text = str(payload.get("comment_text") or "")
        lower = text.casefold()
        digest = str(payload.get("prompt_digest") or "fake-digest-missing")
        lang = "und"
        ctx = payload.get("context") or {}
        if isinstance(ctx, dict):
            lang = str(ctx.get("language") or "und")
            user_spoiler = bool(ctx.get("user_spoiler_flag"))
        else:
            user_spoiler = False

        action = "ALLOW"
        labels: list[str] = ["CLEAN"]
        confidence = 0.92
        spoiler = False
        needs_human = False
        reasons: list[str] = ["FAKE_ALLOW"]

        if re.search(r"ignore (previous|all) instructions|игнорир\w+ (предыдущ|все) инструк", lower):
            action, labels, confidence, reasons = (
                "HOLD_FOR_REVIEW",
                ["PROMPT_INJECTION"],
                0.95,
                ["FAKE_PROMPT_INJECTION"],
            )
            needs_human = True
        elif re.search(r"kill you|убить тебя|bomb threat|взорву", lower):
            action, labels, confidence, reasons = (
                "HIDE_HIGH_CONFIDENCE",
                ["THREAT"],
                0.97,
                ["FAKE_THREAT"],
            )
        elif re.search(r"https?://.*(exe|malware)|download.?virus", lower):
            action, labels, confidence, reasons = (
                "HIDE_HIGH_CONFIDENCE",
                ["MALWARE_LINK"],
                0.96,
                ["FAKE_MALWARE"],
            )
        elif re.search(
            r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b|passport\s*\d{6,}|паспорт|"
            r"[\w.+-]+@[\w-]+\.[\w.-]+",
            lower,
        ):
            action, labels, confidence, reasons = (
                "HIDE_HIGH_CONFIDENCE",
                ["PERSONAL_DATA"],
                0.9,
                ["FAKE_PII"],
            )
            needs_human = True
        elif re.search(
            r"buy (cheap|crypto|followers)|viagra|crypto pump|казино|промокод|"
            r"advertisement|promo code|free nitro",
            lower,
        ):
            action, labels, confidence, reasons = (
                "HIDE_HIGH_CONFIDENCE",
                ["SPAM", "ADVERTISEMENT"],
                0.9,
                ["FAKE_SPAM"],
            )
        elif re.search(
            r"\b(idiot|dumb|clown|moron|stupid)\b|мудак|идиот|дебил",
            lower,
        ):
            action, labels, confidence, reasons = (
                "HIDE_HIGH_CONFIDENCE",
                ["INSULT"],
                0.88,
                ["FAKE_INSULT"],
            )
        elif user_spoiler or re.search(r"spoiler|спойлер|ending is|в финале умирает", lower):
            action, labels, confidence, spoiler, reasons = (
                "ALLOW_COLLAPSED_SPOILER",
                ["SPOILER"],
                0.88,
                True,
                ["FAKE_SPOILER"],
            )
        elif re.search(r"\bunsure\b|не уверен|maybe hate|unclear tone|controversial take", lower):
            action, labels, confidence, reasons = (
                "HOLD_FOR_REVIEW",
                ["UNKNOWN"],
                0.40,
                ["FAKE_LOW_CONFIDENCE"],
            )
            needs_human = True

        decision = {
            "schema_version": "QWEN_DECISION_SCHEMA_V1",
            "policy_version": POLICY_VERSION,
            "action": action,
            "labels": labels,
            "confidence": confidence,
            "spoiler_detected": spoiler,
            "language": lang,
            "reason_codes": reasons,
            "needs_human_review": needs_human,
            "model": self.model,
            "prompt_digest": digest,
        }
        return decision


class LiveQwenProvider:
    """HTTPS provider — disabled unless discover_config() reports configured."""

    def __init__(
        self,
        *,
        timeout_sec: float = DEFAULT_TIMEOUT_SEC,
        max_retries: int = DEFAULT_MAX_RETRIES,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        circuit: CircuitBreakerStub | None = None,
    ) -> None:
        self.timeout_sec = timeout_sec
        self.max_retries = max_retries
        self.max_response_bytes = max_response_bytes
        self.circuit = circuit or CircuitBreakerStub()

    def moderate(self, payload: dict[str, Any]) -> dict[str, Any]:
        cfg = discover_config()
        if not cfg["configured"]:
            raise RuntimeError("QWEN_PROVIDER_NOT_CONFIGURED")
        self.circuit.ensure_closed()
        endpoint = os.environ["QWEN_COMMENTS_ENDPOINT"].strip()
        token_path = Path(os.environ["QWEN_COMMENTS_TOKEN_FILE"].strip())
        token = token_path.read_text(encoding="utf-8").strip()
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        last_err: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                req = urllib.request.Request(
                    endpoint,
                    data=body,
                    method="POST",
                    headers={
                        "Content-Type": "application/json; charset=utf-8",
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/json",
                    },
                )
                with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                    raw = resp.read(self.max_response_bytes + 1)
                if len(raw) > self.max_response_bytes:
                    raise ValueError("response exceeds size limit")
                decision = json.loads(raw.decode("utf-8"))
                self.circuit.record_success()
                return decision
            except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
                last_err = exc
                self.circuit.record_failure()
                if self.circuit.open:
                    raise CircuitOpenError(str(exc)) from exc
                if attempt >= self.max_retries:
                    break
        assert last_err is not None
        raise RuntimeError(f"qwen live request failed: {last_err.__class__.__name__}") from last_err


def moderate_comment(
    provider: QwenProvider,
    *,
    comment_text: str,
    title: str = "",
    content_type: str = "",
    is_reply: bool = False,
    parent_excerpt: str | None = None,
    user_spoiler_flag: bool = False,
    language: str = "und",
) -> dict[str, Any]:
    """Build payload, call provider, validate decision. Returns decision or raises."""
    payload = build_request_payload(
        comment_text,
        title,
        content_type,
        is_reply,
        parent_excerpt,
        user_spoiler_flag,
        language,
    )
    decision = provider.moderate(payload)
    result = validate_decision(decision, comment_text=comment_text)
    if not result["ok"]:
        raise ValueError(f"schema mismatch: {result['errors']}")
    return decision
