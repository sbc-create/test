#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PROFILES = REPO / "config" / "site-profiles"
GIT_DIR = "/srv/site-factory/repo/.git"
IDS = [
    "lords-01",
    "lords-02",
    "lords-03",
    "animedia-01",
    "animedia-02",
    "zona-01",
    "yummyani-site",
    "yummyani-org",
    "yummyani-biz",
    "demo-books",
]


def main() -> None:
    PROFILES.mkdir(parents=True, exist_ok=True)
    for sid in IDS:
        data = subprocess.check_output(
            ["git", f"--git-dir={GIT_DIR}", "show", f"HEAD:config/site-profiles/{sid}.json"]
        )
        path = PROFILES / f"{sid}.json"
        path.write_bytes(data)
        print(sid, path.stat().st_size)


if __name__ == "__main__":
    main()
