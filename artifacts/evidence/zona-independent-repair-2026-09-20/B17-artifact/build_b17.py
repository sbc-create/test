#!/usr/bin/env python3
"""B17: rebuild candidate artifact from FINAL_CODE_HEAD + owner packet (no deploy)."""
from __future__ import annotations

import hashlib
import json
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path

ROOT = Path("/home/claude/wt-zona-finalization-01")
OUT = ROOT / "artifacts/zona-independent-repair-artifact"
EV = ROOT / "artifacts/evidence/zona-independent-repair-2026-09-20"
B15 = EV / "B15-matrix"
B17 = EV / "B17-artifact"
OUT.mkdir(parents=True, exist_ok=True)
B17.mkdir(parents=True, exist_ok=True)

FILES = [
    "automation/host/lords-frontend.py",
    "automation/host/genre_aliases.py",
    "automation/host/collection_contract.py",
]


def sh(*args: str) -> str:
    return subprocess.check_output(list(args), cwd=ROOT, text=True).strip()


def main() -> None:
    final_head = sh("git", "rev-parse", "HEAD")
    start_head = "db8a54fd72f18532aca1c4be5793dd24f6cd8129"
    art = OUT / f"zona-01-frontend-{final_head[:12]}.tar.gz"
    subprocess.check_call(
        ["git", "archive", "--format=tar.gz", f"--output={art}",
         final_head, "--", *FILES],
        cwd=ROOT,
    )
    art_sha = hashlib.sha256(art.read_bytes()).hexdigest()
    # Code-tree digest: sha256 of concatenated blob hashes of FILES at HEAD
    digests = []
    for f in FILES:
        blob = subprocess.check_output(["git", "show", f"{final_head}:{f}"], cwd=ROOT)
        digests.append(hashlib.sha256(blob).hexdigest())
    code_tree = hashlib.sha256("\n".join(digests).encode()).hexdigest()
    built_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # Restore drill
    with tempfile.TemporaryDirectory() as td:
        with tarfile.open(art, "r:gz") as tf:
            tf.extractall(td)
        for f in FILES:
            extracted = Path(td) / f
            assert extracted.is_file(), f"missing {f}"
            blob = subprocess.check_output(["git", "show", f"{final_head}:{f}"], cwd=ROOT)
            assert hashlib.sha256(extracted.read_bytes()).hexdigest() == hashlib.sha256(blob).hexdigest()

    b15 = json.loads((B15 / "PASSPORT.json").read_text(encoding="utf-8"))
    manifest = {
        "schema_version": 1,
        "template_family": "zona",
        "design_version": "1.2.0",
        "source_commit": final_head,
        "build_id": f"zona-independent-repair-{final_head[:12]}",
        "artifact_sha256": art_sha,
        "code_tree_digest": code_tree,
        "profile": "zona-01",
        "built_at": built_at,
        "artifact_path": str(art.relative_to(ROOT)),
        "contract_digest": (
            "1bcfd44734c8cc4041fa6f5a9b28ac9169ceba41dd2f08494b5236043c6fe017"
        ),
        "expected_indexability": "noindex,nofollow",
        "files": FILES,
        "domain": "zonafilm.space",
        "service_name": "nova-zona-01",
        "OWNER_DECISION_ID": "ZONA-INDEPENDENT-REPAIR-ACCEPTANCE-20260920-01",
        "start_head": start_head,
        "local_b15_responsive_matrix_pass": b15.get("RESPONSIVE_MATRIX_PASS"),
    }
    man_path = OUT / "template-manifest.json"
    man_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    man_sha = hashlib.sha256(man_path.read_bytes()).hexdigest()
    (OUT / "MANIFEST.sha256").write_text(f"{man_sha}  template-manifest.json\n", encoding="utf-8")
    (OUT / "ARTIFACT.sha256").write_text(f"{art_sha}  {art.name}\n", encoding="utf-8")
    (OUT / "CODE_TREE.sha256").write_text(f"{code_tree}  files\n", encoding="utf-8")

    old_art = "5fb6295cc7d8a7a1508dfb4be90b2a6e37dc97422e07547679eb535a9b0d2145"
    packet = {
        "OWNER_DECISION_ID": "ZONA-INDEPENDENT-REPAIR-ACCEPTANCE-20260920-01",
        "FINAL_CODE_HEAD": final_head,
        "START_HEAD": start_head,
        "ARTIFACT_SOURCE_HEAD": final_head,
        "CODE_TREE_DIGEST": code_tree,
        "ARTIFACT_SHA256": art_sha,
        "MANIFEST_SHA256": man_sha,
        "ARTIFACT_PATH": str(art.relative_to(ROOT)),
        "DEPLOY_SCOPE": "zona-01 template frontend only",
        "SERVICE_NAME": "nova-zona-01",
        "DOMAIN": "zonafilm.space",
        "PROFILE": "zona-01",
        "EXPECTED_INDEXABILITY": "noindex,nofollow",
        "INDEXABILITY_MUTATIONS_ALLOWED": 0,
        "ROLLBACK_PATH": (
            "Restore prior artifact "
            f"{old_art} + template-manifest under /srv/lords/.frontend/; "
            "systemctl restart nova-zona-01"
        ),
        "OLD_DIGEST": old_art,
        "RESTORE_COMMAND": (
            f"Install artifact {old_art}; systemctl restart nova-zona-01; "
            "verify X-Robots-Tag noindex and build header match prior digest"
        ),
        "RESTORE_VERIFIED_LOCAL": True,
        "RESTART_COMMAND": "systemctl restart nova-zona-01",
        "OWNER_DEPLOY_APPROVAL_ID": None,
        "DEPLOY_AUTHORIZED": False,
        "DEPLOY_PERFORMED": 0,
        "READY_FOR_OWNER_DEPLOY": False,
        "READY_FOR_OWNER_VISUAL_REVIEW": False,
        "blocker_code": "OWNER_DEPLOY_APPROVAL_REQUIRED_AND_RESIDUALS",
        "LOCAL_B15_RESPONSIVE_MATRIX_PASS": b15.get("RESPONSIVE_MATRIX_PASS"),
        "RESIDUAL_BACKLOG": [
            "B14A empty/degraded matrix incomplete",
            "B16 full-catalog pagination oracle + TTFB evidence incomplete",
            "B18 after-live matrix not started (no deploy)",
            "real-provider playback currentTime>=3s not proven in this run",
            "owner contact/legal still OWNER_DATA_REQUIRED",
            "reference geometry deviation table vs frozen 42 captures not fully filled",
        ],
        "OWNER_DATA_GAPS": [
            "footer contact/legal URLs",
            "episode event ledger",
        ],
    }
    (B17 / "OWNER_DEPLOY_PACKET.json").write_text(
        json.dumps(packet, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (B17 / "PASSPORT.json").write_text(json.dumps({
        "block": "B17",
        "status": "PASS_LOCAL_PACKET",
        "FINAL_CODE_HEAD": final_head,
        "ARTIFACT_SHA256": art_sha,
        "MANIFEST_SHA256": man_sha,
        "CODE_TREE_DIGEST": code_tree,
        "READY_FOR_OWNER_DEPLOY": False,
        "reason": "Packet ready for owner binding; deploy blocked until OWNER_DEPLOY_APPROVAL_ID and residual gates.",
        "updated_at": built_at,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "FINAL_CODE_HEAD": final_head,
        "ARTIFACT_SHA256": art_sha,
        "MANIFEST_SHA256": man_sha,
        "CODE_TREE_DIGEST": code_tree,
        "READY_FOR_OWNER_DEPLOY": False,
    }, indent=2))


if __name__ == "__main__":
    main()
