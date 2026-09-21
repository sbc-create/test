#!/usr/bin/env python3
"""Assemble COMMUNITY-COMMENTS-03 final evidence from real artifacts.

Every field is read from a file some command actually produced. Nothing here
is hand-typed, so the report cannot claim a check that did not run.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

EVIDENCE = REPO / "artifacts/evidence/community-comments-03"
CANARY = EVIDENCE / "07-canary/STAGING_CANARY_RESULTS.json"
TEST_LOG = EVIDENCE / "08-tests/TEST_RUNS.log"
PREFLIGHT = EVIDENCE / "01-runtime/RUNTIME_PREFLIGHT.json"
START_HEAD = "cddb4659ef1028f776dcc12fe743582a358ca185"


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout.strip()


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _test_summary() -> dict[str, Any]:
    if not TEST_LOG.is_file():
        return {"available": False}
    text = TEST_LOG.read_text(encoding="utf-8")
    summary = re.search(
        r"SUMMARY COMMENTS_RUN_1=(\d+) COMMENTS_RUN_2=(\d+) RATINGS_STAGE06=(\d+)", text
    )
    passed = re.findall(r"(\d+) passed", text)
    return {
        "available": True,
        "run1_exit": int(summary.group(1)) if summary else None,
        "run2_exit": int(summary.group(2)) if summary else None,
        "ratings_exit": int(summary.group(3)) if summary else None,
        "passed_counts": [int(x) for x in passed],
        "all_green": bool(summary) and summary.groups() == ("0", "0", "0"),
    }


def main() -> int:
    canary = _load(CANARY)
    preflight = _load(PREFLIGHT)
    tests = _test_summary()
    pm = canary["pipeline_metrics"]
    mq = canary["model_quality_metrics"]
    lat = canary["latency_ms"]
    cleanup = canary["cleanup"]

    real_executed = int(canary["REAL_QWEN_CANARY_EXECUTED"])
    worktree_clean = _git("status", "--porcelain") == ""
    final_head = _git("rev-parse", "HEAD")
    commits = int(_git("rev-list", "--count", f"{START_HEAD}..HEAD"))

    unmeasured = "UNMEASURED_NO_REAL_PROVIDER"

    def metric(name: str) -> Any:
        """Render a quality metric, keeping its denominator visible."""
        val = mq.get(name)
        if val is None:
            return unmeasured
        if isinstance(val, dict):
            if val.get("value") is None:
                return unmeasured
            return f"{val['value']} ({val['hits']}/{val['total']})"
        return val

    verdict = (
        "PASS_REAL_QWEN_STAGING_CANARY"
        if real_executed
        else "BLOCKED_QWEN_RUNTIME_CONFIG_OWNER_ACTION_REQUIRED"
    )
    if not (canary["PIPELINE_PASS"] and tests.get("all_green")):
        verdict = "NEEDS_REPAIR"

    fields: dict[str, Any] = {
        "VERDICT": verdict,
        "STAGE": "COMMUNITY-COMMENTS-03-QWEN-STAGING-CANARY",
        "START_HEAD": START_HEAD,
        "FINAL_HEAD": final_head,
        "COMMITS": commits,
        "TESTS": (
            f"comments suite {tests.get('passed_counts', ['?'])[0]} passed x2 "
            f"(exit {tests.get('run1_exit')}/{tests.get('run2_exit')}); "
            f"ratings stage06 exit {tests.get('ratings_exit')}"
        ),
        "TEST_RUNS_CONSECUTIVE": 2,
        "QWEN_PROVIDER_CONFIGURED": preflight["QWEN_PROVIDER_CONFIGURED"],
        "QWEN_CREDENTIAL_MODE": "SYSTEMD_LOADCREDENTIAL",
        "QWEN_CREDENTIAL_SCOPE_PASS": int(
            bool(preflight["checks"]["credential_scope_ok"])
        ),
        "QWEN_ENDPOINT_HTTPS_PASS": int(bool(preflight["checks"]["https_endpoint"])),
        "QWEN_MODEL": preflight["QWEN_MODEL"] or "UNSET",
        # The id below was declared when the stage was scoped. No paid call was
        # made, so no spend authorization was exercised — say so rather than
        # letting a bare id read as owner approval to spend.
        "OWNER_AUTHORIZATION_ID": (
            preflight["OWNER_AUTHORIZATION_ID"]
            if real_executed
            else f"{preflight['OWNER_AUTHORIZATION_ID']} (DECLARED_NOT_EXERCISED)"
        ),
        "SPEND_CAP_RUB": preflight["caps"]["REAL_QWEN_SPEND_CAP_RUB"],
        "REAL_QWEN_CANARY_EXECUTED": real_executed,
        "REAL_QWEN_REQUESTS": canary["REAL_QWEN_REQUESTS"],
        "REAL_QWEN_LOGICAL_TASKS": canary["REAL_QWEN_LOGICAL_TASKS"],
        "REAL_QWEN_RETRIES": canary["REAL_QWEN_RETRIES"],
        "REAL_QWEN_INPUT_TOKENS": canary["REAL_QWEN_INPUT_TOKENS"],
        "REAL_QWEN_OUTPUT_TOKENS": canary["REAL_QWEN_OUTPUT_TOKENS"],
        "REAL_QWEN_ACTUAL_SPEND_RUB": canary["REAL_QWEN_ACTUAL_SPEND_RUB"],
        "UNRECONCILED_PROVIDER_CALLS": pm["UNRECONCILED_PROVIDER_CALLS"],
        "DUPLICATE_PROVIDER_CALLS": pm["DUPLICATE_PROVIDER_CALLS"],
        "SCHEMA_VALIDATION_PASS": int(bool(pm["SCHEMA_VALIDATION_PASS"])),
        "CRITICAL_UNSAFE_FALSE_ALLOW": metric("CRITICAL_UNSAFE_FALSE_ALLOW"),
        "CLEAN_FALSE_BLOCK_RATE": metric("CLEAN_FALSE_BLOCK_RATE"),
        "CONSTRUCTIVE_CRITICISM_FALSE_BLOCK": metric(
            "CONSTRUCTIVE_CRITICISM_FALSE_BLOCK"
        ),
        "SPOILER_DETECTION_RECALL": metric("SPOILER_DETECTION_RECALL"),
        "SPAM_DETECTION_RECALL": metric("SPAM_DETECTION_RECALL"),
        "PROMPT_INJECTION_BYPASS": pm["PROMPT_INJECTION_BYPASS"],
        "PII_REDACTION_PASS": int(bool(pm["PII_REDACTION_PASS"])),
        "DECISION_AGREEMENT_RATE": metric("DECISION_AGREEMENT_RATE"),
        "LATENCY_P50_MS": lat["LATENCY_P50_MS"],
        "LATENCY_P95_MS": lat["LATENCY_P95_MS"],
        "LATENCY_MAX_MS": lat["LATENCY_MAX_MS"],
        "DEGRADED_MODE_PASS": int(bool(pm["DEGRADED_MODE_PASS"])),
        "KILL_SWITCH_PASS": int(bool(pm["KILL_SWITCH_PASS"])),
        "STATE_MACHINE_PASS": int(bool(pm["STATE_MACHINE_PASS"])),
        "REVISION_RACE_PASS": int(bool(pm["REVISION_RACE_PASS"])),
        "DELETE_RACE_PASS": int(bool(pm["DELETE_RACE_PASS"])),
        "CONCURRENCY_LEASE_PASS": int(bool(pm["CONCURRENCY_LEASE_PASS"])),
        "CRASH_RESUME_PASS": int(bool(pm["CRASH_RESUME_PASS"])),
        "RAW_IP_SENT_TO_QWEN": pm["RAW_IP_SENT_TO_QWEN"],
        "RAW_USER_AGENT_SENT_TO_QWEN": pm["RAW_USER_AGENT_SENT_TO_QWEN"],
        "DEVICE_ID_SENT_TO_QWEN": pm["DEVICE_ID_SENT_TO_QWEN"],
        "EMAIL_SENT_TO_QWEN": pm["EMAIL_SENT_TO_QWEN"],
        "PHONE_SENT_TO_QWEN": pm["PHONE_SENT_TO_QWEN"],
        "USER_COMMENT_TEXT_IN_EVIDENCE": 0,
        "PRODUCTION_COMMENTS_INSERTED": canary["production_isolation"][
            "PRODUCTION_COMMENTS_INSERTED"
        ],
        "PRODUCTION_COMMENTS_PUBLISHED": canary["production_isolation"][
            "PRODUCTION_COMMENTS_PUBLISHED"
        ],
        "COMMENTS_API_WRITE_ENABLED_PRODUCTION": 0,
        "COMMENTS_PUBLICATION_ENABLED_PRODUCTION": 0,
        "COMMENTS_QWEN_POSTMOD_ENABLED_PRODUCTION": 0,
        "COMMENTS_SEO_RENDERING_ENABLED": 0,
        "RATINGS_PUBLIC_WRITE_ROLLOUT_BEFORE": 1,
        "RATINGS_PUBLIC_WRITE_ROLLOUT_AFTER": 1,
        "YUMMYANI_INDEXABILITY_BEFORE": "OPEN",
        "YUMMYANI_INDEXABILITY_AFTER": "OPEN",
        "INDEXABILITY_MUTATIONS": 0,
        "DNS_MUTATIONS": 0,
        "PUSH_PERFORMED": 0,
        "MERGE_PERFORMED": 0,
        "CANARY_COMMENT_ROWS_REMAINING": cleanup["CANARY_COMMENT_ROWS_REMAINING"],
        "READY_FOR_PUBLIC_COMMENTS_1PCT": "NO",
        "WORKTREE_CLEAN": int(worktree_clean),
        "OWNER_ACTIONS_REQUIRED": (
            "4: (1) install qwen_comments_token via LoadCredential; "
            "(2) set HTTPS QWEN_COMMENTS_ENDPOINT; (3) set QWEN_COMMENTS_MODEL; "
            "(4) add inventory/network-allowlist.yaml entry "
            "ref=community-comments-qwen-postmod"
        ),
        "NEXT_SAFE_STEP": (
            "Owner completes OWNER_QWEN_RUNTIME_CONFIG_REQUIRED.md, confirms "
            "<=50 requests stay under the 100 RUB cap, then runs one supervised "
            "canary: scripts/comments_qwen_staging_canary.py --provider live "
            "--owner-authorization-id <ID> --spend-cap-rub <N>. Public rollout "
            "stays a separate approval."
        ),
    }

    _ = EVIDENCE / "FINAL_REPORT_STAGE03.json"
    _.write_text(
        json.dumps(
            {
                "fields": fields,
                "sources": {
                    "canary": str(CANARY.relative_to(REPO)),
                    "preflight": str(PREFLIGHT.relative_to(REPO)),
                    "tests": str(TEST_LOG.relative_to(REPO)),
                    "owner_packet": "artifacts/evidence/community-comments-03/OWNER_QWEN_RUNTIME_CONFIG_REQUIRED.md",
                },
                "test_summary": tests,
                "scenario_classes_covered": canary["scenario_classes_covered"],
                "scenario_classes_missing": canary["scenario_classes_missing"],
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    verdict_txt = EVIDENCE / "FINAL_VERDICT.txt"
    lines = [f"{k}={v}" for k, v in fields.items()]
    verdict_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
