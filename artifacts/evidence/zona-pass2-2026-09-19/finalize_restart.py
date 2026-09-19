"""Zona PASS2 closed deploy: flock, rollback, artifact, zona manifest, nsenter restart."""
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
ARTIFACT = FRONT / "lords-frontend.py"
MANIFEST = FRONT / "template-manifest-zona-01.json"
LOCK = FRONT / ".deploy.lock"
SOURCE = Path("/home/claude/wt-zona-finalization-01/automation/host/lords-frontend.py")
EVIDENCE = Path("/home/claude/wt-zona-finalization-01/artifacts/evidence/zona-pass2-2026-09-19")
HEAD = subprocess.check_output(
    ["git", "-C", str(SOURCE.parents[2]), "rev-parse", "HEAD"], text=True
).strip()
EXPECT = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
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
    print("systemctl", args, "rc", result.returncode, text.strip()[:240])
    return result.returncode, text


def fetch(path: str) -> tuple[int, dict, str]:
    req = urllib.request.Request(
        f"https://{DOMAIN}{path}",
        headers={"User-Agent": "zona-pass2-finalize", "Cache-Control": "no-cache"},
    )
    with urllib.request.urlopen(req, timeout=45, context=CTX) as r:
        body = r.read().decode("utf-8", "replace")
        return r.status, dict(r.headers.items()), body


def main() -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    assert sha(SOURCE) == EXPECT

    # Neighbor fingerprints before mutate
    before_neighbors = {name: sha(FRONT / name) for name in NEIGHBOR_MANIFESTS if (FRONT / name).exists()}
    (EVIDENCE / "before-neighbor-manifests.json").write_text(
        json.dumps(before_neighbors, indent=2) + "\n", encoding="utf-8"
    )

    with open(LOCK, "a+", encoding="utf-8") as lockf:
        print("acquiring deploy lock", LOCK)
        fcntl.flock(lockf.fileno(), fcntl.LOCK_EX)
        lockf.seek(0)
        lockf.truncate()
        lockf.write(json.dumps({"site": SITE, "head": HEAD, "at": BUILD}) + "\n")
        lockf.flush()

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-{SITE}-pass2"
        rollback = FRONT / ".rollback" / stamp
        rollback.mkdir(parents=True, exist_ok=True)
        if ARTIFACT.exists():
            shutil.copy2(ARTIFACT, rollback / "lords-frontend.py")
        if MANIFEST.exists():
            shutil.copy2(MANIFEST, rollback / "template-manifest-zona-01.json")
        (rollback / "meta.json").write_text(json.dumps({
            "site": SITE, "expect": EXPECT, "head": HEAD, "build": BUILD,
            "created": stamp, "previous_live_sha": sha(ARTIFACT) if ARTIFACT.exists() else None,
        }, indent=2) + "\n", encoding="utf-8")

        (EVIDENCE / "deploy-ids.txt").write_text(
            f"{EXPECT}\n{HEAD}\n{BUILD}\n{rollback}\n", encoding="utf-8"
        )

        atomic_write(ARTIFACT, SOURCE.read_bytes())
        assert sha(ARTIFACT) == EXPECT

        prev = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}
        manifest = {
            "schema_version": 1,
            "template_family": "zona",
            "design_version": "1.2.0",
            "source_commit": HEAD,
            "runtime_commit": HEAD,
            "build_id": BUILD,
            "artifact_sha256": EXPECT,
            "profile": prev.get("profile") or "zona-general",
            "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        atomic_write(MANIFEST, (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode())

        rc, _ = systemctl("restart", UNIT)
        if rc != 0:
            print("restart failed")
            return 2
        time.sleep(6)
        systemctl("is-active", UNIT)

        checks = {}
        for path in (
            "/healthz",
            "/",
            "/search/?q=%D0%B7%D0%B2%D0%B5%D0%B7%D0%B4%D0%BD%D1%8B%D0%B5%20%D0%B2%D0%BE%D0%B9%D0%BD%D1%8B",
            "/title/aida-vozvraschaetsya/",
            "/title/v-lovushke/",
            "/title/voy-2/",
            "/movies/",
        ):
            try:
                status, headers, body = fetch(path)
                checks[path] = {
                    "status": status,
                    "build": headers.get("X-Site-Factory-Build-Id"),
                    "artifact": headers.get("X-Site-Factory-Artifact-Sha256"),
                    "source": headers.get("X-Site-Factory-Template-Revision"),
                    "robots": headers.get("X-Robots-Tag"),
                    "postMessage_client": "addEventListener('message'" in body or "eventType" in body,
                    "banner_false": 'is-show-banner="false"' in body,
                    "results_heading": "Результаты поиска" in body,
                    "footer_zones": "Каталог и информация" in body,
                    "jargon": "Провайдер не отдал" in body,
                    "marker": ("Zona · v" in body),
                }
            except Exception as exc:
                checks[path] = {"error": str(exc)}

        after_neighbors = {name: sha(FRONT / name) for name in NEIGHBOR_MANIFESTS if (FRONT / name).exists()}
        report = {
            "rollback": str(rollback),
            "artifact_sha": sha(ARTIFACT),
            "manifest": manifest,
            "checks": checks,
            "neighbors_unchanged": before_neighbors == after_neighbors,
            "before_neighbors": before_neighbors,
            "after_neighbors": after_neighbors,
        }
        (EVIDENCE / "after").mkdir(parents=True, exist_ok=True)
        (EVIDENCE / "after" / "finalize.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps({
            "rollback": str(rollback),
            "build": BUILD,
            "artifact": EXPECT[:16],
            "neighbors_unchanged": report["neighbors_unchanged"],
            "home": checks.get("/"),
            "aida": {k: checks.get("/title/aida-vozvraschaetsya/", {}).get(k)
                     for k in ("status", "build", "artifact", "postMessage_client", "banner_false", "jargon")},
            "search": {k: checks.get("/search/?q=%D0%B7%D0%B2%D0%B5%D0%B7%D0%B4%D0%BD%D1%8B%D0%B5%20%D0%B2%D0%BE%D0%B9%D0%BD%D1%8B", {}).get(k)
                       for k in ("status", "results_heading")},
        }, ensure_ascii=False, indent=2))

        home = checks.get("/", {})
        aida = checks.get("/title/aida-vozvraschaetsya/", {})
        if home.get("status") != 200 or aida.get("status") != 200:
            return 3
        if aida.get("artifact") != EXPECT:
            print("artifact mismatch", aida.get("artifact"), EXPECT)
            return 4
        if not aida.get("postMessage_client"):
            print("postMessage client missing")
            return 5
        if aida.get("jargon"):
            print("provider jargon still present")
            return 6
        if not report["neighbors_unchanged"]:
            print("neighbor manifests changed")
            return 7
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
