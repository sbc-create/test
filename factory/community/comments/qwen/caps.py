"""Request/token/spend caps for real Qwen staging canary."""

from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_LEDGER = Path(
    os.environ.get(
        "COMMUNITY_COMMENTS_QWEN_CAP_LEDGER",
        "/srv/site-factory/repo/var/community_comments/qwen_cap_ledger.json",
    )
)

REQUEST_CAP = int(os.environ.get("REAL_QWEN_REQUEST_CAP", "50"))
INPUT_TOKEN_CAP = int(os.environ.get("REAL_QWEN_INPUT_TOKEN_CAP", "100000"))
SPEND_CAP_RUB = float(os.environ.get("REAL_QWEN_SPEND_CAP_RUB", "100"))
PAID_RETRIES_MAX = 2

_lock = threading.RLock()


@dataclass
class CapLedger:
    authorization_id: str = ""
    requests: int = 0
    logical_tasks: int = 0
    retries: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    spend_rub: float = 0.0
    call_ids: list[str] = field(default_factory=list)
    updated_at: str = ""

    def snapshot(self) -> dict[str, Any]:
        return asdict(self)


class CapExceeded(RuntimeError):
    code = "CAP_EXCEEDED"


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_ledger(path: Path | None = None) -> CapLedger:
    p = path or Path(os.environ.get("COMMUNITY_COMMENTS_QWEN_CAP_LEDGER", str(DEFAULT_LEDGER)))
    with _lock:
        if not p.is_file():
            return CapLedger()
        raw = json.loads(p.read_text(encoding="utf-8"))
        return CapLedger(
            authorization_id=str(raw.get("authorization_id") or ""),
            requests=int(raw.get("requests") or 0),
            logical_tasks=int(raw.get("logical_tasks") or 0),
            retries=int(raw.get("retries") or 0),
            input_tokens=int(raw.get("input_tokens") or 0),
            output_tokens=int(raw.get("output_tokens") or 0),
            spend_rub=float(raw.get("spend_rub") or 0.0),
            call_ids=list(raw.get("call_ids") or []),
            updated_at=str(raw.get("updated_at") or ""),
        )


def save_ledger(ledger: CapLedger, path: Path | None = None) -> CapLedger:
    p = path or Path(os.environ.get("COMMUNITY_COMMENTS_QWEN_CAP_LEDGER", str(DEFAULT_LEDGER)))
    ledger.updated_at = _utc()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(ledger.snapshot(), indent=2) + "\n", encoding="utf-8")
    tmp.replace(p)
    return ledger


def assert_within_caps(
    ledger: CapLedger,
    *,
    extra_requests: int = 1,
    extra_input_tokens: int = 0,
    extra_spend_rub: float = 0.0,
) -> None:
    if ledger.requests + extra_requests > REQUEST_CAP:
        raise CapExceeded(
            f"REQUEST_CAP:{ledger.requests}+{extra_requests}>{REQUEST_CAP}"
        )
    if ledger.input_tokens + extra_input_tokens > INPUT_TOKEN_CAP:
        raise CapExceeded(
            f"TOKEN_CAP:{ledger.input_tokens}+{extra_input_tokens}>{INPUT_TOKEN_CAP}"
        )
    if ledger.spend_rub + extra_spend_rub > SPEND_CAP_RUB + 1e-9:
        raise CapExceeded(
            f"SPEND_CAP:{ledger.spend_rub}+{extra_spend_rub}>{SPEND_CAP_RUB}"
        )


def record_call(
    ledger: CapLedger,
    *,
    call_id: str,
    is_retry: bool,
    input_tokens: int,
    output_tokens: int,
    spend_rub: float,
    path: Path | None = None,
) -> CapLedger:
    with _lock:
        if call_id in ledger.call_ids:
            raise CapExceeded(f"DUPLICATE_PROVIDER_CALL:{call_id}")
        assert_within_caps(
            ledger,
            extra_requests=1,
            extra_input_tokens=max(0, int(input_tokens)),
            extra_spend_rub=max(0.0, float(spend_rub)),
        )
        ledger.requests += 1
        if is_retry:
            ledger.retries += 1
        else:
            ledger.logical_tasks += 1
        ledger.input_tokens += max(0, int(input_tokens))
        ledger.output_tokens += max(0, int(output_tokens))
        ledger.spend_rub += max(0.0, float(spend_rub))
        ledger.call_ids.append(call_id)
        return save_ledger(ledger, path=path)


def caps_public_status(ledger: CapLedger | None = None) -> dict[str, Any]:
    led = ledger or load_ledger()
    return {
        "REAL_QWEN_REQUEST_CAP": REQUEST_CAP,
        "REAL_QWEN_INPUT_TOKEN_CAP": INPUT_TOKEN_CAP,
        "REAL_QWEN_SPEND_CAP_RUB": SPEND_CAP_RUB,
        "PAID_RETRIES_MAX": PAID_RETRIES_MAX,
        "REAL_QWEN_REQUESTS": led.requests,
        "REAL_QWEN_LOGICAL_TASKS": led.logical_tasks,
        "REAL_QWEN_RETRIES": led.retries,
        "REAL_QWEN_INPUT_TOKENS": led.input_tokens,
        "REAL_QWEN_OUTPUT_TOKENS": led.output_tokens,
        "REAL_QWEN_ACTUAL_SPEND_RUB": led.spend_rub,
        "REQUEST_CAP_REMAINING": max(0, REQUEST_CAP - led.requests),
        "DUPLICATE_PROVIDER_CALLS": 0,
    }
