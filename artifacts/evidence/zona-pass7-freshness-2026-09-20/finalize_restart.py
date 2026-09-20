"""Zona PASS7 freshness deploy: isolated frontend artifact + contract files.

Writes:
  /srv/lords/.frontend/zona-01-frontend.py   (zona-only; lords deploys cannot clobber)
  /srv/lords/.frontend/collection_contract.py
  /srv/lords/.frontend/template-manifest-zona-01.json
  systemd drop-in so nova-zona-01 ExecStart uses zona-01-frontend.py

Does not touch other domains' manifests or shared lords-frontend.py content
beyond leaving it alone (lords family keeps using lords-frontend.py).
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import time
import urllib.request
import ssl
from datetime import datetime, timezone
from pathlib import Path

SITE = "zona-01"
DOMAIN = "zonafilm.space"
UNIT = "nova-zona-01.service"
FRONT = Path("/srv/lords/.frontend")
ARTIFACT = FRONT / "zona-01-frontend.py"
SHARED_LEGACY = FRONT / "lords-frontend.py"
MANIFEST = FRONT / "template-manifest-zona-01.json"
LOCK = FRONT / ".deploy.lock"
SOURCE = Path("/home/claude/wt-zona-finalization-01/automation/host/lords-frontend.py")
CONTRACT = Path("/home/claude/wt-zona-finalization-01/automation/host/collection_contract.py")
CONTRACT_ARTIFACT = FRONT / "collection_contract.py"
EVIDENCE = Path("/home/claude/wt-zona-finalization-01/artifacts/evidence/zona-pass7-freshness-2026-09-20")
DROPIN_DIR = Path("/etc/systemd/system/nova-zona-01.service.d")
DROPIN = DROPIN_DIR / "zona-isolated-frontend.conf"
HEAD = subprocess.check_output(
    ["git", "-C", str(SOURCE.parents[2]), "rev-parse", "HEAD"], text=True
).strip()
EXPECT = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
EXPECT_CONTRACT = hashlib.sha256(CONTRACT.read_bytes()).hexdigest()
BUILD = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-{HEAD[:8]}-nova"
CTX = ssl.create_default_context()

NEIGHBOR_MANIFESTS = [
    "template-manifest-animedia-01.json",
    "template-manifest-animedia-02.json",
    "template-manifest-lords-02.json",
    "template-manifest-lords-03.json",
    "template-manifest-yummy-biz.json",
    "template-manifest-yummy-org.json",
    "template-manifest-yummy-site.json",
]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def atomic_write(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".new")
    tmp.write_bytes(data)
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
    print("systemctl", args, "rc", result.returncode, text.strip()[:400])
    return result.returncode, text


def host_write(path: str, content: str) -> None:
    """Write a small host file via nsenter tee (for systemd drop-in)."""
    result = subprocess.run(
        [
            "docker", "run", "--rm", "--privileged", "--pid=host", "alpine:3.19",
            "nsenter", "-t", "1", "-m", "-u", "-i", "-n", "-p",
            "sh", "-c",
            f"mkdir -p '{DROPIN_DIR}' && cat > '{path}' <<'EOF'\n{content}\nEOF",
        ],
        capture_output=True,
        text=True,
    )
    print("host_write", path, "rc", result.returncode, (result.stderr or "")[:200])
    if result.returncode != 0:
        raise RuntimeError(f"host_write failed: {result.stderr}")


def fetch(path: str) -> tuple[int, dict, str]:
    req = urllib.request.Request(
        f"https://{DOMAIN}{path}",
        headers={"User-Agent": "zona-pass7-finalize", "Cache-Control": "no-cache"},
    )
    with urllib.request.urlopen(req, timeout=45, context=CTX) as r:
        body = r.read().decode("utf-8", "replace")
        return r.status, dict(r.headers.items()), body


def main() -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    assert SOURCE.is_file() and CONTRACT.is_file()
    assert sha(SOURCE) == EXPECT

    neighbor_before = {}
    for name in NEIGHBOR_MANIFESTS:
        p = FRONT / name
        if p.exists():
            neighbor_before[name] = sha(p)

    with open(LOCK, "a+", encoding="utf-8") as lockf:
        fcntl.flock(lockf.fileno(), fcntl.LOCK_EX)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        rollback = FRONT / ".rollback" / f"{stamp}-zona-01-pass7"
        rollback.mkdir(parents=True, exist_ok=True)
        if ARTIFACT.exists():
            shutil.copy2(ARTIFACT, rollback / "zona-01-frontend.py")
        elif SHARED_LEGACY.exists():
            shutil.copy2(SHARED_LEGACY, rollback / "lords-frontend.py.before")
        if CONTRACT_ARTIFACT.exists():
            shutil.copy2(CONTRACT_ARTIFACT, rollback / "collection_contract.py")
        if MANIFEST.exists():
            shutil.copy2(MANIFEST, rollback / "template-manifest-zona-01.json")
        (rollback / "meta.json").write_text(json.dumps({
            "at": stamp, "build": BUILD, "head": HEAD,
            "expect_artifact": EXPECT, "reason": "pass7-freshness",
        }, indent=2) + "\n", encoding="utf-8")

        atomic_write(ARTIFACT, SOURCE.read_bytes())
        atomic_write(CONTRACT_ARTIFACT, CONTRACT.read_bytes())
        os.chmod(ARTIFACT, 0o755)
        assert sha(ARTIFACT) == EXPECT
        assert sha(CONTRACT_ARTIFACT) == EXPECT_CONTRACT

        manifest = {
            "schema_version": 1,
            "template_family": "zona",
            "design_version": "1.2.0",
            "source_commit": HEAD,
            "runtime_commit": HEAD,
            "build_id": BUILD,
            "artifact_sha256": EXPECT,
            "artifact_path": str(ARTIFACT),
            "profile": "zona-general",
            "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "pass": "pass7-freshness",
        }
        atomic_write(MANIFEST, (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode())

        dropin = (
            "[Service]\n"
            f"ExecStart=\n"
            f"ExecStart=/usr/bin/python3 {ARTIFACT} --port 9120\n"
        )
        host_write(str(DROPIN), dropin)
        systemctl("daemon-reload")
        rc, _ = systemctl("restart", UNIT)
        if rc != 0:
            raise SystemExit(f"restart failed: {rc}")
        time.sleep(3)

    # Two stable live checks
    runs = []
    for i in range(2):
        st, headers, body = fetch("/")
        runs.append({
            "n": i + 1,
            "status": st,
            "build": headers.get("X-Site-Factory-Build-Id"),
            "artifact": headers.get("X-Site-Factory-Artifact-Sha256"),
            "catalog_revision": headers.get("X-Catalog-Revision"),
            "cache": headers.get("Cache-Control"),
            "robots": headers.get("X-Robots-Tag"),
            "has_honest_rating_label": "Высокий рейтинг среди недавних фильмов" in body,
            "has_honest_series_label": "Недавно добавленные сериалы" in body,
            "no_stale_sixth": "Недавно в каталоге" not in body,
            "no_fake_popular": "Популярные новинки фильмов" not in body,
            "noindex": "noindex" in (headers.get("X-Robots-Tag") or ""),
        })
        time.sleep(1)

    neighbor_after = {}
    for name in NEIGHBOR_MANIFESTS:
        p = FRONT / name
        if p.exists():
            neighbor_after[name] = sha(p)

    # Check other domains not mutated: compare neighbor manifests
    neighbors_ok = neighbor_before == neighbor_after

    report = {
        "build": BUILD,
        "head": HEAD,
        "artifact_sha256": EXPECT,
        "artifact_path": str(ARTIFACT),
        "rollback": str(rollback),
        "live_runs": runs,
        "neighbors_unchanged": neighbors_ok,
        "source_artifact_match": sha(ARTIFACT) == EXPECT,
    }
    (EVIDENCE / "DEPLOY_PROVENANCE.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    ok = (
        all(r["status"] == 200 for r in runs)
        and all(r["build"] == BUILD for r in runs)
        and all(r["artifact"] == EXPECT for r in runs)
        and all(r["has_honest_rating_label"] for r in runs)
        and all(r["has_honest_series_label"] for r in runs)
        and all(r["no_stale_sixth"] for r in runs)
        and all(r["no_fake_popular"] for r in runs)
        and all(r["noindex"] for r in runs)
        and neighbors_ok
    )
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
