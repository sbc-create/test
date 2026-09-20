"""Staging canary entrypoint — refuses to run without real runtime config.

Never substitutes FakeQwenProvider for a claimed real canary.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from factory.community.comments.qwen.runtime_preflight import runtime_preflight


def main() -> int:
    report = runtime_preflight()
    out = Path("artifacts/evidence/community-comments-03/01-runtime/RUNTIME_PREFLIGHT.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if not report.get("READY_FOR_REAL_CANARY"):
        print(
            json.dumps(
                {
                    "VERDICT": "BLOCKED_QWEN_RUNTIME_CONFIG",
                    "READY_FOR_REAL_CANARY": False,
                    "BLOCKED_REASON": report.get("BLOCKED_REASON"),
                    "QWEN_PROVIDER_CONFIGURED": report.get("QWEN_PROVIDER_CONFIGURED"),
                    "QWEN_ENDPOINT_HOST": report.get("QWEN_ENDPOINT_HOST"),
                    "note": "Real canary not started; fake provider must not be used as substitute.",
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 2
    # Live path is intentionally not auto-executed here without explicit owner
    # endpoint+model filled in the unit. When READY, invoke scripts/comments_qwen_real_canary.py
    print(
        json.dumps(
            {
                "READY_FOR_REAL_CANARY": True,
                "next": "scripts/comments_qwen_real_canary.py",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
