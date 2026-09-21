#!/usr/bin/env python3
"""Stage lords-02 visual-repair artifact (--no-restart) + collection_contract."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "automation" / "host" / "lords-frontend.py"
CC = ROOT / "automation" / "host" / "collection_contract.py"
EV = ROOT / "artifacts" / "evidence" / "lords-visual-repair-2026-09-20"
BUILD = EV / "02-build"
DEPLOY = EV / "deploy" / "lords-02"
FRONT = Path("/srv/lords/.frontend")


def main() -> int:
    BUILD.mkdir(parents=True, exist_ok=True)
    DEPLOY.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(SRC.read_bytes()).hexdigest()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=ROOT).strip()
    build_id = datetime.now(timezone.utc).strftime("20260920T%H%M%SZ") + "-4f8ef5a-visual"
    # Canary allowlist only accepts automation/host (or rollback). Evidence copy
    # is still written for provenance; install uses the live source path.
    rel_copy = BUILD / f"lords-frontend-{build_id}.py"
    cc_copy = BUILD / f"collection_contract-{build_id}.py"
    shutil.copy2(SRC, rel_copy)
    shutil.copy2(CC, cc_copy)
    install_artifact = SRC
    rel = {
        "final_code_head": head,
        "source_dirty": True,
        "source_path": str(SRC),
        "install_artifact_path": str(install_artifact),
        "release_copy": str(rel_copy),
        "collection_contract_copy": str(cc_copy),
        "artifact_sha256": sha,
        "build_id": build_id,
        "design_version": "1.1.0",
        "player_layout_contract": "full-bleed-v1",
        "deploy_order": ["lords-02", "lords-01", "lords-03"],
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "sites": {
            "lords-01": {
                "domain": "lordfilm47.space",
                "profile": "lords-general",
                "design": "lords-cinema-v2",
                "unit": "lords-nova-01.service",
            },
            "lords-02": {
                "domain": "lordserial33.biz",
                "profile": "lords-new",
                "design": "lords-series-feed-v2",
                "unit": "nova-lords-02.service",
            },
            "lords-03": {
                "domain": "1lordserials1.online",
                "profile": "lords-curated",
                "design": "lords-curated-v2",
                "unit": "nova-lords-03.service",
            },
        },
    }
    (BUILD / "RELEASE.json").write_text(json.dumps(rel, ensure_ascii=False, indent=2), encoding="utf-8")
    print("RELEASE", build_id, sha)

    # collection_contract sidecar (imported by runtime)
    cc_dst = FRONT / "collection_contract.py"
    bak = FRONT / ".rollback" / f"{build_id}-collection_contract.bak"
    bak.parent.mkdir(parents=True, exist_ok=True)
    if cc_dst.is_file():
        shutil.copy2(cc_dst, bak)
    shutil.copy2(cc_copy, cc_dst)
    print("collection_contract staged; bak=", bak)

    cmd = [
        sys.executable,
        str(ROOT / "automation" / "host" / "lords-nova-canary.py"),
        "install",
        "--site", "lords-02",
        "--artifact", str(install_artifact),
        "--expect-sha256", sha,
        "--design-version", "1.1.0",
        "--commit", head,
        "--build-id", build_id,
        "--record", str(DEPLOY / "stage.json"),
        "--no-restart",
    ]
    print("RUN", " ".join(cmd))
    return subprocess.call(cmd, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
