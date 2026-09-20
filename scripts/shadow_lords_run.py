#!/usr/bin/env python3
"""Shadow release for three Lords sites — zero live mutations."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from factory.release_orchestrator.approval import build_approval, write_approval
from factory.release_orchestrator.intake import plan_manifest_from_registry
from factory.release_orchestrator.manifest import digest_obj, write_manifest
from factory.release_orchestrator.reports import write_final_reports
from factory.release_orchestrator.runner import run_batch
from factory.release_orchestrator.registry import ReleaseRegistry
from factory.release_orchestrator.inotify_diag import diagnose
from factory.release_orchestrator.bypass import refuse_if_enforced

REPO = Path(__file__).resolve().parents[1]
SITES = ["lords-01", "lords-02", "lords-03"]
LIVE_PROBE_PATHS = [
    Path("/srv/lords/lords-01"),
    Path("/srv/lords/lords-02"),
    Path("/srv/lords/lords-03"),
]
AUTH = "SITE-FACTORY-RELEASE-ORCHESTRATOR-SHADOW-20260920-01"


def tree_fingerprint(root: Path) -> str:
    h = hashlib.sha256()
    if not root.exists():
        h.update(b"MISSING")
        return h.hexdigest()
    # metadata-only: path + size + mtime (no content rewrite risk)
    for path in sorted(root.rglob("*")):
        if path.is_file():
            st = path.stat()
            h.update(str(path.relative_to(root)).encode())
            h.update(str(st.st_size).encode())
            h.update(str(int(st.st_mtime)).encode())
            h.update(b"\0")
    return h.hexdigest()


def main() -> int:
    os.chdir(REPO)
    reg = ReleaseRegistry.load()
    release_id = "rel-shadow-lords-20260920-01"
    work = REPO / "var" / "release-orchestrator" / release_id
    art_root = work / "artifacts"
    report_dir = REPO / "reports" / "releases" / release_id
    work.mkdir(parents=True, exist_ok=True)
    art_root.mkdir(parents=True, exist_ok=True)

    before = {str(p): tree_fingerprint(p) for p in LIVE_PROBE_PATHS}
    (work / "live_before.json").write_text(json.dumps(before, indent=2) + "\n", encoding="utf-8")

    artifacts = {}
    for sid in SITES:
        ap = art_root / sid / "artifact.bin"
        ap.parent.mkdir(parents=True, exist_ok=True)
        payload = f"shadow-artifact:{sid}:{AUTH}\n".encode()
        ap.write_bytes(payload)
        artifacts[sid] = {
            "artifact_path": str(ap),
            "artifact_sha256": hashlib.sha256(payload).hexdigest(),
            "manifest_sha256": hashlib.sha256(f"site-manifest:{sid}".encode()).hexdigest(),
            "expected_build_id": f"shadow-build-{sid}",
            "expected_catalog_revision": "shadow-cat-1",
            "expected_details_revision": "shadow-det-1",
        }

    # Use a fixed source_head placeholder for shadow (40 hex) — not a live mutate.
    source_head = hashlib.sha1(b"shadow-source").hexdigest()
    manifest = plan_manifest_from_registry(
        release_id=release_id,
        site_ids=SITES,
        canary_site_id="lords-01",
        source_head=source_head,
        requested_by=AUTH,
        artifacts=artifacts,
        registry=reg,
        release_mode="shadow",
    )
    mpath = report_dir / "manifest.json"
    report_dir.mkdir(parents=True, exist_ok=True)
    digest = write_manifest(mpath, manifest)
    approval = build_approval(
        approval_id="apr-shadow-lords-20260920-01",
        release_id=release_id,
        manifest=manifest,
        approved_by=AUTH,
        allowed_indexability_changes=False,
        allowed_dns_changes=False,
        allowed_paid_operations=False,
        expires_at=manifest["expires_at"],
    )
    # Re-bind after canonical write
    from factory.release_orchestrator.manifest import load_manifest

    approval["manifest_digest"] = digest_obj(load_manifest(mpath))
    apath = report_dir / "approval.json"
    write_approval(apath, approval)

    result = run_batch(
        release_id=release_id,
        manifest_path=mpath,
        manifest_digest=digest,
        approval_path=apath,
        report_dir=report_dir,
        work_root=work / "sandbox",
        registry=reg,
        mutate=False,
        shadow=True,
    )
    write_final_reports(report_dir, verdict=result.verdict, extra={"authorization": AUTH})

    after = {str(p): tree_fingerprint(p) for p in LIVE_PROBE_PATHS}
    (work / "live_after.json").write_text(json.dumps(after, indent=2) + "\n", encoding="utf-8")
    mutations = [p for p in before if before[p] != after[p]]
    inotify = diagnose(apply_remediation=False)

    # Bypass refuse check (does not mutate)
    bypass_ok = False
    os.environ["RELEASE_ORCHESTRATOR_REQUIRED"] = "1"
    try:
        refuse_if_enforced("shadow-check")
    except SystemExit as exc:
        bypass_ok = exc.code == 78
    finally:
        os.environ.pop("RELEASE_ORCHESTRATOR_REQUIRED", None)

    summary = {
        "OWNER_AUTHORIZATION_ID": AUTH,
        "result": result.__dict__,
        "SHADOW_SITES_PLANNED": SITES,
        "SHADOW_SITES_PASSED": [s for s, st in result.sites.items() if st == "POST_DEPLOY_PASS"],
        "SHADOW_MUTATIONS": len(mutations),
        "mutation_paths": mutations,
        "INOTIFY_DIAGNOSIS": inotify.as_dict(),
        "BYPASS_REFUSE_PASS": bypass_ok,
        "live_before": before,
        "live_after": after,
    }
    (report_dir / "SHADOW_EVIDENCE.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    return 0 if result.global_state == "BATCH_PASS" and not mutations and bypass_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
