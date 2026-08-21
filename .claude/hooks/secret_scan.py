#!/usr/bin/env python3
"""PostToolUse hook: ищет секреты, попавшие в только что записанный файл.

PostToolUse не может отменить запись, поэтому хук сообщает Claude о находке
(exit 2 → stderr показывается модели), чтобы секрет был убран немедленно.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import guard_rules as rules  # noqa: E402

MAX_BYTES = 2_000_000


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    path = (payload.get("tool_input") or {}).get("file_path") or ""
    if not path or not os.path.isfile(path):
        return 0
    try:
        if os.path.getsize(path) > MAX_BYTES:
            return 0
        text = open(path, "r", encoding="utf-8", errors="replace").read()
    except OSError:
        return 0
    findings = rules.scan_secret_content(text)
    if not findings:
        return 0
    kinds = ", ".join(sorted(set(findings)))
    print(
        f"[factory-guard G-SECRET-CONTENT] В файле {path} обнаружено похожее на секрет: {kinds}. "
        f"Секреты передаются только через secret_ref. Убери значение из файла немедленно.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
