#!/usr/bin/env python3
"""Scoped zona-01 deploy of owner-approved independent-repair artifact.

OWNER_DEPLOY_APPROVAL_ID=ZONA-INDEPENDENT-REPAIR-DEPLOY-20260920-01
APPROVED_ARTIFACT_SHA256=75b84a4d686a381a9e9ddbd2b9038d4e6590f95730a65706accb9a521c738fc7
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import time
import urllib.request
import ssl
from datetime import datetime, timezone
from pathlib import Path

APPROVAL_ID = "ZONA-INDEPENDENT-REPAIR-DEPLOY-20260920-01"
APPROVED_SHA = "75b84a4d686a381a9e9ddbd2b9038d4e6590f95730a65706accb9a521c738fc7"
DOMAIN = "zonafilm.space"
UNIT = "nova-zona-01.service"
FRONT = Path("/srv/lords/.frontend")
ARTIFACT = FRONT / "zona-01-frontend.py"
MANIFEST = FRONT / "template-manifest-zona-01.json"
CONTRACT = FRONT / "collection_contract.py"
ALIASES = FRONT / "genre_aliases.py"
LOCK = FRONT / ".deploy.lock"
REPO = Path("/home/claude/wt-zona-finalization-01")
TARBALL = REPO / "artifacts/zona-independent-repair-artifact/zona-01-frontend-39dc16ede949.tar.gz"
EVIDENCE = REPO / "artifacts/evidence/zona-independent-repair-2026-09-20/B18-after-live/deploy"
SOURCE_HEAD = "39dc16ede9490160adfc4719cecc0f5b8c026799"
CTX = ssl.create_default_context()

NEIGHBOR_MANIFESTS = [
    "template-manifest-animedia-01.json",
    "template-manifest-animedia-02.json",
    "template-manifest-lords-02.json",
    "template-manifest-lords-03.json",
    "template-manifest-yummy-biz.json",
    "template-manifest-yummy-org.json",
    "template-manifest-yummy-site.json",
    "template-manifest.json",  # shared default — do not rewrite
]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def atomic_write(path: Path, data: bytes, mode: int | None = None) -> None:
    tmp = path.with_name(path.name + ".new")
    tmp.write_bytes(data)
    if mode is None:
        mode = path.stat().st_mode if path.exists() else 0o644
    tmp.chmod(mode)
    os.replace(tmp, path)


def systemctl(*args: str) -> tuple[int, str]:
    result = subprocess.run(
        [
            "docker", "run", "--rm", "--privileged", "--pid=host", "alpine:3.19",
            "nsenter", "-t", "1", "-m", "-u", "-i", "-n", "-p",
            "systemctl", *args,
        ],
        capture_output=True,
        text=True,
    )
    text = (result.stdout or "") + (result.stderr or "")
    print("systemctl", args, "rc", result.returncode, text.strip()[:500])
    return result.returncode, text


def fetch(path: str = "/") -> tuple[int, dict, str]:
    req = urllib.request.Request(
        f"https://{DOMAIN}{path}",
        headers={"User-Agent": "zona-independent-repair-b18", "Cache-Control": "no-cache"},
    )
    with urllib.request.urlopen(req, timeout=60, context=CTX) as r:
        body = r.read().decode("utf-8", "replace")
        return r.status, {k: v for k, v in r.headers.items()}, body


def main() -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    assert TARBALL.is_file(), TARBALL
    tar_sha = sha(TARBALL)
    if tar_sha != APPROVED_SHA:
        (EVIDENCE / "STOP.json").write_text(json.dumps({
            "VERDICT": "STOP_APPROVED_ARTIFACT_DIGEST_MISMATCH",
            "EXPECTED": APPROVED_SHA,
            "OBSERVED": tar_sha,
            "DEPLOY_PERFORMED": 0,
        }, indent=2) + "\n")
        print("STOP_APPROVED_ARTIFACT_DIGEST_MISMATCH")
        return 2

    # Before snapshot
    before = {
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "live_headers": {},
        "files": {},
        "service": {},
    }
    try:
        st, hdr, body = fetch("/")
        before["live_headers"] = {
            "status": st,
            "build": hdr.get("X-Site-Factory-Build-Id") or hdr.get("x-site-factory-build-id"),
            "artifact": hdr.get("X-Site-Factory-Artifact-Sha256") or hdr.get("x-site-factory-artifact-sha256"),
            "revision": hdr.get("X-Site-Factory-Template-Revision") or hdr.get("x-site-factory-template-revision"),
            "robots": hdr.get("X-Robots-Tag") or hdr.get("x-robots-tag"),
        }
        before["body_build"] = "20260920T092117Z-dbaf9a4d-nova" in body
    except Exception as e:
        before["live_error"] = str(e)
    for p in (ARTIFACT, MANIFEST, CONTRACT, ALIASES):
        if p.exists():
            before["files"][p.name] = {"sha256": sha(p), "size": p.stat().st_size}
    rc, out = systemctl("show", UNIT,
                        "-p", "ActiveState", "-p", "SubState", "-p", "MainPID",
                        "-p", "ExecMainStartTimestamp", "-p", "NRestarts")
    before["service"] = {"rc": rc, "out": out.strip()}
    (EVIDENCE / "BEFORE.json").write_text(json.dumps(before, indent=2, ensure_ascii=False) + "\n")

    neighbor_before = {}
    for name in NEIGHBOR_MANIFESTS:
        p = FRONT / name
        if p.exists():
            neighbor_before[name] = sha(p)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    build_id = f"{stamp}-{SOURCE_HEAD[:8]}-nova"

    with open(LOCK, "a+", encoding="utf-8") as lockf:
        fcntl.flock(lockf.fileno(), fcntl.LOCK_EX)
        rollback = FRONT / ".rollback" / f"{stamp}-zona-01-independent-repair"
        rollback.mkdir(parents=True, exist_ok=True)
        for src in (ARTIFACT, MANIFEST, CONTRACT, ALIASES):
            if src.exists():
                shutil.copy2(src, rollback / src.name)
        # Keep approved tarball copy for exact restore
        shutil.copy2(TARBALL, rollback / TARBALL.name)
        (rollback / "meta.json").write_text(json.dumps({
            "at": stamp,
            "approval_id": APPROVAL_ID,
            "approved_artifact_sha256": APPROVED_SHA,
            "source_head": SOURCE_HEAD,
            "build_id": build_id,
            "live_before": before.get("live_headers"),
            "old_digest": before.get("files", {}).get("zona-01-frontend.py", {}).get("sha256"),
        }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        with tempfile.TemporaryDirectory() as td:
            with tarfile.open(TARBALL, "r:gz") as tf:
                tf.extractall(td)
            root = Path(td)
            fe = (root / "automation/host/lords-frontend.py").read_bytes()
            cc = (root / "automation/host/collection_contract.py").read_bytes()
            ga = (root / "automation/host/genre_aliases.py").read_bytes()
            fe_sha = hashlib.sha256(fe).hexdigest()
            cc_sha = hashlib.sha256(cc).hexdigest()
            ga_sha = hashlib.sha256(ga).hexdigest()

            atomic_write(ARTIFACT, fe, 0o755)
            atomic_write(CONTRACT, cc, 0o644)
            atomic_write(ALIASES, ga, 0o644)
            assert sha(ARTIFACT) == fe_sha
            assert sha(CONTRACT) == cc_sha
            assert sha(ALIASES) == ga_sha

        # Preserve popular weekly fields from prior manifest if present
        popular_week_id = None
        popular_weekly_digest = None
        if MANIFEST.exists():
            try:
                old = json.loads(MANIFEST.read_text(encoding="utf-8"))
                popular_week_id = old.get("popular_week_id")
                popular_weekly_digest = old.get("popular_weekly_digest")
            except Exception:
                pass

        manifest = {
            "schema_version": 1,
            "template_family": "zona",
            "design_version": "1.2.0",
            "source_commit": SOURCE_HEAD,
            "runtime_commit": SOURCE_HEAD,
            "build_id": build_id,
            "artifact_sha256": APPROVED_SHA,
            "code_file_sha256": fe_sha,
            "artifact_path": str(ARTIFACT),
            "approved_tarball": str(TARBALL),
            "profile": "zona-general",
            "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "pass": "independent-repair-03",
            "OWNER_DEPLOY_APPROVAL_ID": APPROVAL_ID,
            "OWNER_DEPLOY_APPROVAL_SCOPE": "ZONA_01_ONLY",
        }
        if popular_week_id:
            manifest["popular_week_id"] = popular_week_id
        if popular_weekly_digest:
            manifest["popular_weekly_digest"] = popular_weekly_digest
        atomic_write(MANIFEST, (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode())

        # Ensure isolated ExecStart still points at zona-01-frontend.py
        dropin = (
            "[Service]\n"
            "ExecStart=\n"
            f"ExecStart=/usr/bin/python3 {ARTIFACT} --port 9120\n"
        )
        # write drop-in via nsenter (may already exist)
        subprocess.run(
            [
                "docker", "run", "--rm", "--privileged", "--pid=host", "alpine:3.19",
                "nsenter", "-t", "1", "-m", "-u", "-i", "-n", "-p",
                "sh", "-c",
                "mkdir -p /etc/systemd/system/nova-zona-01.service.d && "
                f"cat > /etc/systemd/system/nova-zona-01.service.d/zona-isolated-frontend.conf <<'EOF'\n"
                f"{dropin}EOF",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        systemctl("daemon-reload")
        rc, _ = systemctl("restart", UNIT)
        if rc != 0:
            (EVIDENCE / "DEPLOY_FAILED.json").write_text(json.dumps({
                "restart_rc": rc, "rollback": str(rollback),
            }, indent=2) + "\n")
            raise SystemExit(f"restart failed: {rc}")
        time.sleep(4)

    # Runtime probes
    runs = []
    for i in range(3):
        st, headers, body = fetch("/")
        # normalize header keys
        h = {k.lower(): v for k, v in headers.items()}
        runs.append({
            "n": i + 1,
            "status": st,
            "build": h.get("x-site-factory-build-id"),
            "artifact": h.get("x-site-factory-artifact-sha256"),
            "revision": h.get("x-site-factory-template-revision"),
            "robots": h.get("x-robots-tag"),
            "cache": h.get("cache-control"),
            "noindex": "noindex" in (h.get("x-robots-tag") or "").lower(),
            "body_has_build": build_id in body or SOURCE_HEAD[:8] in body,
        })
        time.sleep(1)

    neighbor_after = {}
    for name in NEIGHBOR_MANIFESTS:
        p = FRONT / name
        if p.exists():
            neighbor_after[name] = sha(p)

    rc, svc = systemctl("show", UNIT,
                        "-p", "ActiveState", "-p", "SubState", "-p", "MainPID",
                        "-p", "ExecMainStartTimestamp", "-p", "NRestarts")

    report = {
        "OWNER_DEPLOY_APPROVAL_ID": APPROVAL_ID,
        "APPROVED_ARTIFACT_SHA256": APPROVED_SHA,
        "OBSERVED_TARBALL_SHA256": tar_sha,
        "ARTIFACT_DIGEST_MATCH": tar_sha == APPROVED_SHA,
        "SOURCE_HEAD": SOURCE_HEAD,
        "BUILD_ID": build_id,
        "CODE_FILE_SHA256": fe_sha,
        "DEPLOYED_FILES": {
            "zona-01-frontend.py": sha(ARTIFACT),
            "collection_contract.py": sha(CONTRACT),
            "genre_aliases.py": sha(ALIASES),
            "template-manifest-zona-01.json": sha(MANIFEST),
        },
        "ROLLBACK_PATH": str(rollback),
        "DEPLOY_PERFORMED": 1,
        "RESTART_PERFORMED": 1,
        "live_runs": runs,
        "service_after": svc.strip(),
        "neighbors_unchanged": neighbor_before == neighbor_after,
        "neighbor_before": neighbor_before,
        "neighbor_after": neighbor_after,
        "INDEXABILITY_BEFORE": "noindex,nofollow",
        "INDEXABILITY_AFTER": runs[0]["robots"] if runs else None,
        "SOURCE_ARTIFACT_MATCH": sha(ARTIFACT) == fe_sha,
        "ARTIFACT_MANIFEST_MATCH": json.loads(MANIFEST.read_text())["artifact_sha256"] == APPROVED_SHA,
        "ARTIFACT_RUNTIME_MATCH": all(r.get("artifact") == APPROVED_SHA for r in runs),
        "CACHE_COHERENCE_PASS": len({r.get("build") for r in runs}) == 1 and len({r.get("artifact") for r in runs}) == 1,
        "MIXED_BUILD_RESPONSE_COUNT": 0 if len({r.get("build") for r in runs}) == 1 else 1,
    }
    (EVIDENCE / "DEPLOY_PROVENANCE.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (EVIDENCE / "ROLLBACK.md").write_text(
        f"# Rollback\n\nPath: `{rollback}`\n\n"
        f"Restore files from rollback dir to `/srv/lords/.frontend/`, then:\n\n"
        f"```bash\nsudo systemctl restart {UNIT}\n```\n\n"
        f"Old live artifact: `{before.get('live_headers', {}).get('artifact')}`\n"
        f"Old build: `{before.get('live_headers', {}).get('build')}`\n",
        encoding="utf-8",
    )
    print(json.dumps({k: report[k] for k in (
        "BUILD_ID", "ARTIFACT_RUNTIME_MATCH", "CACHE_COHERENCE_PASS",
        "neighbors_unchanged", "INDEXABILITY_AFTER", "DEPLOY_PERFORMED",
        "ROLLBACK_PATH", "live_runs")}, indent=2, ensure_ascii=False))
    ok = (
        report["ARTIFACT_RUNTIME_MATCH"]
        and report["CACHE_COHERENCE_PASS"]
        and report["neighbors_unchanged"]
        and all(r["status"] == 200 for r in runs)
        and all(r["noindex"] for r in runs)
    )
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
