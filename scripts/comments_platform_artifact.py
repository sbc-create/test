#!/usr/bin/env python3
"""Compute — and optionally stamp — the comments widget artifact checksum.

A site pins `module_version` *and* `artifact_checksum`. The version says what
was intended; the checksum says what is actually being served. Without the
second, "lords is on 0.1.0" is a claim nobody can check after a bad copy, a
half-finished upload or a cache that kept yesterday's file.

The digest covers the widget's shipped files in a fixed order, each preceded by
its path and byte length. Including the path means renaming a file changes the
digest; including the length means two files cannot be concatenated into one
another's content without detection.

    python3 scripts/comments_platform_artifact.py            # print
    python3 scripts/comments_platform_artifact.py --stamp    # write into config
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WIDGET_DIR = REPO / "factory" / "comments_platform" / "widget"
CONFIG = REPO / "config" / "comments-platform" / "sites.json"

# Fixed order. Sorting by name rather than relying on directory order, so the
# digest is the same on any filesystem.
ARTIFACT_FILES = ("comments-widget.css", "comments-widget.js")


def compute_checksum() -> str:
    digest = hashlib.sha256()
    for name in ARTIFACT_FILES:
        path = WIDGET_DIR / name
        data = path.read_bytes()
        digest.update(f"{name}\x00{len(data)}\x00".encode())
        digest.update(data)
    return digest.hexdigest()


def stamp(checksum: str) -> int:
    raw = json.loads(CONFIG.read_text(encoding="utf-8"))
    changed = 0
    for site in raw.get("sites", []):
        if site.get("artifact_checksum") != checksum:
            site["artifact_checksum"] = checksum
            changed += 1
    CONFIG.write_text(
        json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return changed


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stamp", action="store_true", help="write the digest into the config")
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero if the config disagrees with the files on disk",
    )
    args = parser.parse_args(argv)

    checksum = compute_checksum()

    if args.check:
        raw = json.loads(CONFIG.read_text(encoding="utf-8"))
        stale = [
            site["site_id"]
            for site in raw.get("sites", [])
            if site.get("artifact_checksum") != checksum
        ]
        if stale:
            print(f"artifact checksum is stale for: {', '.join(stale)}", file=sys.stderr)
            print(f"expected {checksum}", file=sys.stderr)
            return 1
        print(f"artifact checksum up to date: {checksum}")
        return 0

    if args.stamp:
        changed = stamp(checksum)
        print(f"{checksum}  ({changed} site(s) updated)")
        return 0

    print(checksum)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
