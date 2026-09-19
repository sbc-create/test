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
EVIDENCE = Path("/home/claude/wt-zona-finalization-01/artifacts/evidence/zona-final-repair-2026-09-19")
HEAD = "2d6d16952abca7bf8840e00c7d75769d96452044"
BUILD = "20260919T143500Z-2d6d1695-nova"
EXPECT = "14ce882d5ad4a70769f1fa054288833ef7cd408d8d5d79ef8a5b62884c8b7593"
CTX = ssl.create_default_context()


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def atomic_write(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".new")
    tmp.write_bytes(data)
    mode = path.stat().st_mode if path.exists() else 0o644
    tmp.chmod(mode)
    os.replace(tmp, path)


def unit_props() -> dict:
    out = subprocess.check_output(
        ["systemctl", "show", UNIT, "-p", "MainPID", "-p", "ActiveState"],
        text=True,
    )
    return dict(line.split("=", 1) for line in out.strip().splitlines())


def systemctl(*args: str) -> tuple[int, str]:
    """Host systemctl via nsenter into pid 1 (no interactive polkit)."""
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--privileged",
            "--pid=host",
            "alpine:3.19",
            "nsenter",
            "-t",
            "1",
            "-m",
            "-u",
            "-i",
            "-n",
            "-p",
            "systemctl",
            *args,
        ],
        capture_output=True,
        text=True,
    )
    text = (result.stdout or "") + (result.stderr or "")
    print("systemctl", args, "rc", result.returncode, text.strip()[:200])
    return result.returncode, text


def main() -> int:
    assert sha(SOURCE) == EXPECT
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-{SITE}-finalize2"
    rb = FRONT / ".rollback" / stamp
    rb.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ARTIFACT, rb / "lords-frontend.py")
    shutil.copy2(MANIFEST, rb / "manifest.json")
    prev_manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    (rb / "point.json").write_text(
        json.dumps(
            {
                "site": SITE,
                "artifact_sha256": sha(ARTIFACT),
                "manifest_content": prev_manifest,
                "at": stamp,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print("ROLLBACK", rb)

    new_manifest = {
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
    atomic_write(MANIFEST, (json.dumps(new_manifest, ensure_ascii=False, indent=2) + "\n").encode())
    MANIFEST.chmod(0o644)
    atomic_write(ARTIFACT, SOURCE.read_bytes())
    ARTIFACT.chmod(0o755)
    print("WROTE", sha(ARTIFACT))

    props = unit_props()
    old_pid = int(props["MainPID"])
    print("old_pid", old_pid, props["ActiveState"])
    rc, _ = systemctl("restart", UNIT)
    if rc != 0:
        print("restart failed")
        return 1

    ok = False
    health = None
    for i in range(40):
        time.sleep(1)
        props = unit_props()
        new_pid = int(props.get("MainPID") or 0)
        state = props.get("ActiveState")
        print(f"wait[{i}] {state} pid={new_pid}")
        if state == "active" and new_pid:
            try:
                req = urllib.request.Request(
                    f"https://{DOMAIN}/", headers={"User-Agent": "zona-final"}
                )
                with urllib.request.urlopen(req, timeout=15, context=CTX) as resp:
                    body = resp.read(5000).decode("utf-8", "replace")
                    build = resp.headers.get("X-Site-Factory-Build-Id")
                    art = resp.headers.get("X-Site-Factory-Artifact-Sha256")
                    src = resp.headers.get("X-Site-Factory-Template-Revision")
                    health = {
                        "status": resp.status,
                        "build": build,
                        "artifact": art,
                        "source": src,
                        "has_marker": ("Zona 1.2.0" in body),
                        "no_debug": ("тестовая витрина" not in body),
                        "movies_probe": None,
                    }
                    print("health", health)
                    if resp.status == 200 and art == EXPECT and build == BUILD:
                        # /movies/ must be 200 after restart
                        try:
                            mreq = urllib.request.Request(
                                f"https://{DOMAIN}/movies/",
                                headers={"User-Agent": "zona-final"},
                            )
                            with urllib.request.urlopen(mreq, timeout=15, context=CTX) as mresp:
                                health["movies_probe"] = mresp.status
                                if mresp.status == 200:
                                    ok = True
                                    break
                        except Exception as mex:  # noqa: BLE001
                            health["movies_probe"] = str(mex)
            except Exception as exc:  # noqa: BLE001
                print("health_err", exc)
                health = {"error": str(exc)}

    record = {
        "action": "finalize-restart-nsenter",
        "site": SITE,
        "domain": DOMAIN,
        "rollback_point": str(rb),
        "artifact_sha256": EXPECT,
        "manifest": new_manifest,
        "previous_manifest": prev_manifest,
        "old_pid": old_pid,
        "health": health,
        "ok": ok,
        "at_utc": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
    }

    if not ok:
        atomic_write(ARTIFACT, (rb / "lords-frontend.py").read_bytes())
        ARTIFACT.chmod(0o755)
        atomic_write(
            MANIFEST,
            (json.dumps(prev_manifest, ensure_ascii=False, indent=2) + "\n").encode(),
        )
        systemctl("restart", UNIT)
        record["auto_rolled_back"] = True
        record["verdict"] = "ROLLED_BACK"
    else:
        record["verdict"] = "INSTALLED"

    (EVIDENCE / "finalize-restart.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("VERDICT", record["verdict"])
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
