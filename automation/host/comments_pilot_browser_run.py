#!/usr/bin/env python3
"""Bring up the shadow contour, run the browser acceptance, tear it down.

The browser half and the API half must see the same processes, not two
contours that merely look alike, so the lifecycle lives in one place. This
script starts the shadow contour, mints an owner cohort cookie for it, hands
both to Playwright through the environment, and shuts everything down
afterwards whatever the outcome.

The cookie is passed in the environment and never written to a file or printed.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from automation.host.comments_shadow_rehearsal import Shadow  # noqa: E402


def main() -> int:
    shadow = Shadow()
    shadow.start()
    jar, hdrs = shadow.owner_cookies()

    env = dict(os.environ)
    env["CP_PILOT_BASE"] = shadow.base
    env["CP_PILOT_COOKIE"] = jar["cp_cohort"]
    env["CP_PILOT_CSRF"] = jar["cp_csrf"]

    print(f"shadow contour on {shadow.base}", file=sys.stderr)
    try:
        return subprocess.run(
            ["npx", "playwright", "test", "--config=playwright.pilot.config.js",
             *sys.argv[1:]],
            cwd=str(REPO), env=env,
        ).returncode
    finally:
        shadow.stop()


if __name__ == "__main__":
    raise SystemExit(main())
