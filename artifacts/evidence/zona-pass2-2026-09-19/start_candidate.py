"""Start Zona PASS2 candidate on an alternate port for pre-switch QA."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path("/home/claude/wt-zona-finalization-01")
ART = ROOT / "automation" / "host" / "lords-frontend.py"
PORT = 19120
LOG = ROOT / "artifacts" / "evidence" / "zona-pass2-2026-09-19" / "candidate.log"
PID = ROOT / "artifacts" / "evidence" / "zona-pass2-2026-09-19" / "candidate.pid"


def main() -> int:
    env = os.environ.copy()
    env.update({
        "LORDS_TEMPLATE_MANIFEST": "/srv/lords/.frontend/template-manifest-zona-01.json",
        "LORDS_CATALOG": "/srv/lords/.frontend/zona-01-catalog.json",
        "LORDS_DETAILS": "/srv/lords/.frontend/zona-01-details.json",
        "LORDS_PLAYER_CONFIG": "/srv/lords/.frontend/player-zona-01.json",
        "LORDS_SITE_NAME": "Zona",
        "PYTHONDONTWRITEBYTECODE": "1",
        "LORDS_METRIKA_COUNTER": "112582938",
    })
    logf = open(LOG, "w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, str(ART), "--host", "127.0.0.1", "--port", str(PORT)],
        env=env,
        stdout=logf,
        stderr=subprocess.STDOUT,
        cwd=str(ROOT),
    )
    PID.write_text(str(proc.pid) + "\n", encoding="utf-8")
    # wait for listen
    for _ in range(40):
        time.sleep(0.25)
        try:
            import urllib.request
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/healthz", timeout=1)
            print(f"candidate_ready port={PORT} pid={proc.pid}")
            return 0
        except Exception:
            if proc.poll() is not None:
                print("candidate exited", proc.returncode)
                print(LOG.read_text(encoding="utf-8", errors="replace")[-2000:])
                return 1
    print("candidate_timeout")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
