"""Default-suite hook: full-bleed viewport e2e is release-blocking when browser exists."""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
CONFIG = КОРЕНЬ / "playwright.lords-viewport.config.js"


@pytest.mark.skipif(
    os.environ.get("FACTORY_SKIP_BROWSER") == "1",
    reason="FACTORY_SKIP_BROWSER=1",
)
def test_full_bleed_viewport_gate_in_default_suite():
    npx = shutil.which("npx")
    if not npx or not (КОРЕНЬ / "node_modules" / "@playwright" / "test").is_dir():
        pytest.skip("@playwright/test not installed")
    env = os.environ.copy()
    if not env.get("FACTORY_CHROMIUM"):
        # Prefer repo-local or system chromium when present.
        for candidate in (
            "/usr/bin/chromium-browser",
            "/usr/bin/chromium",
            "/usr/bin/google-chrome",
        ):
            if pathlib.Path(candidate).is_file():
                env["FACTORY_CHROMIUM"] = candidate
                break
    proc = subprocess.run(
        [npx, "playwright", "test", f"--config={CONFIG}", "--reporter=line"],
        cwd=str(КОРЕНЬ),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
