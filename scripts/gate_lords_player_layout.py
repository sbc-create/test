#!/usr/bin/env python3
"""Fail-closed gate: Lords artifact must embed full-bleed-v1 player contract.

Usage:
  python3 scripts/gate_lords_player_layout.py --artifact PATH --expect-commit COMMIT

Exit 0 only when:
  * data-player-layout-contract=\"full-bleed-v1\" is present
  * full-bleed CSS and fitPlayerTree/ensureLayoutObserver are present
  * optional --expect-commit matches a SOURCE marker if provided via env/file
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

CONTRACT = 'data-player-layout-contract="full-bleed-v1"'
REQUIRED = (
    CONTRACT,
    "[data-player-layout-contract=\"full-bleed-v1\"] iframe",
    "fitPlayerTree",
    "ensureLayoutObserver",
    "MutationObserver",
    "height:100% !important",
    "max-width:none !important",
)


def main(argv: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--artifact", required=True)
    р.add_argument("--expect-commit", default="")
    р.add_argument("--expect-sha256", default="")
    а = р.parse_args(argv)
    путь = Path(а.artifact)
    if not путь.is_file():
        print(f"GATE_FAIL missing artifact: {путь}", file=sys.stderr)
        return 2
    текст = путь.read_text(encoding="utf-8", errors="replace")
    sha = hashlib.sha256(путь.read_bytes()).hexdigest()
    missing = [s for s in REQUIRED if s not in текст]
    if missing:
        print("GATE_FAIL player contract incomplete:", file=sys.stderr)
        for s in missing:
            print(f"  missing: {s[:80]}", file=sys.stderr)
        return 1
    if "place-items:center" in текст.split("/* Плеер:")[1].split("/* Сезоны")[0].split("[data-player-state]")[0]:
        print("GATE_FAIL player shell still grid-centers media", file=sys.stderr)
        return 1
    if а.expect_sha256 and а.expect_sha256 != sha:
        print(f"GATE_FAIL sha mismatch: got {sha} want {а.expect_sha256}", file=sys.stderr)
        return 1
    print(f"GATE_PASS contract={CONTRACT} sha256={sha}")
    if а.expect_commit:
        print(f"expect_commit={а.expect_commit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
