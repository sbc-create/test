"""Complete zona-01 closed update after canary write: restart unit, verify."""
from __future__ import annotations

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
SOURCE = Path("/home/claude/wt-zona-finalization-01/automation/host/lords-frontend.py")
EVIDENCE = Path("/home/claude/wt-zona-finalization-01/artifacts/evidence/zona-followup-2026-09-19")
IDS = (EVIDENCE / "deploy-ids.txt").read_text().strip().splitlines()
EXPECT, HEAD, BUILD = IDS[0], IDS[1], IDS[2]
CTX = ssl.create_default_context()


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
    print("systemctl", args, "rc", result.returncode, text.strip()[:200])
    return result.returncode, text


def fetch(path: str) -> tuple[int, dict, str]:
    req = urllib.request.Request(
        f"https://{DOMAIN}{path}",
        headers={"User-Agent": "zona-followup-finalize", "Cache-Control": "no-cache"},
    )
    with urllib.request.urlopen(req, timeout=30, context=CTX) as r:
        body = r.read().decode("utf-8", "replace")
        return r.status, dict(r.headers.items()), body


def main() -> int:
    assert sha(SOURCE) == EXPECT, (sha(SOURCE), EXPECT)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-{SITE}-followup"
    rollback = FRONT / ".rollback" / stamp
    rollback.mkdir(parents=True, exist_ok=True)
    if ARTIFACT.exists():
        shutil.copy2(ARTIFACT, rollback / "lords-frontend.py")
    if MANIFEST.exists():
        shutil.copy2(MANIFEST, rollback / "template-manifest-zona-01.json")
    (rollback / "meta.json").write_text(json.dumps({
        "site": SITE, "expect": EXPECT, "head": HEAD, "build": BUILD,
        "created": stamp,
    }, indent=2) + "\n")

    atomic_write(ARTIFACT, SOURCE.read_bytes())
    assert sha(ARTIFACT) == EXPECT

    prev = {}
    if MANIFEST.exists():
        prev = json.loads(MANIFEST.read_text())
    manifest = {
        "schema_version": 1,
        "template_family": "zona",
        "design_version": "1.2.0",
        "source_commit": HEAD,
        "runtime_commit": HEAD,
        "build_id": BUILD,
        "artifact_sha256": EXPECT,
        "profile": "zona-general",
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if prev.get("profile"):
        manifest["profile"] = prev["profile"]
    atomic_write(MANIFEST, (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode())

    rc, _ = systemctl("restart", UNIT)
    if rc != 0:
        print("restart failed; attempting rollback files")
        return 2
    time.sleep(5)
    rc, _ = systemctl("is-active", UNIT)
    props = subprocess.check_output(
        ["systemctl", "show", UNIT, "-p", "MainPID", "-p", "ActiveState"],
        text=True,
    )
    print(props)

    checks = {}
    for path in ("/healthz", "/", "/title/aida-vozvraschaetsya/", "/movies/"):
        try:
            status, headers, body = fetch(path)
            checks[path] = {
                "status": status,
                "build": headers.get("X-Site-Factory-Build-Id"),
                "artifact": headers.get("X-Site-Factory-Artifact-Sha256"),
                "source": headers.get("X-Site-Factory-Template-Revision"),
                "robots": headers.get("X-Robots-Tag"),
                "has_resolving_or_ready": (
                    'data-state="resolving"' in body or 'data-state="ok"' in body
                    or 'data-state="nosource"' in body or 'data-state="provider"' in body
                ),
                "kp_preferred": 'data-aggregator="kp"' in body and 'data-title-id="11922371"' in body
                if "aida" in path else None,
                "connected_false_positive": "источник подключён" in body.lower()
                and 'data-state="resolving"' in body,
                "ztitle": 'class="ztitle"' in body,
                "zgenres": "Смотреть по жанрам" in body,
            }
        except Exception as exc:
            checks[path] = {"error": str(exc)}

    report = {
        "rollback": str(rollback),
        "artifact_sha": sha(ARTIFACT),
        "manifest": manifest,
        "checks": checks,
    }
    (EVIDENCE / "after" / "finalize.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))

    aida = checks.get("/title/aida-vozvraschaetsya/", {})
    home = checks.get("/", {})
    if aida.get("status") != 200 or home.get("status") != 200:
        return 3
    if aida.get("artifact") != EXPECT:
        print("artifact header mismatch", aida.get("artifact"), EXPECT)
        return 4
    if not aida.get("kp_preferred"):
        print("aida did not prefer kp")
        return 5
    if aida.get("connected_false_positive"):
        print("false connected label still present")
        return 6
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
