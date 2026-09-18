#!/usr/bin/env python3
"""Operator-applied раскатка закрытых nova-витрин (Lords/Animedia/Zona).

Вызывает официальные automation/host/deploy-nova-lords.sh и
deploy-nova-family.sh. Provenance берётся из nova_closed_provenance:
source_commit — профильный worktree, runtime_commit — общий lords-frontend.py.

Запуск:

  FACTORY_OWNER_ROOT_MANDATE=SITE_FACTORY_ROOT_20260909 \\
    python3 automation/host/apply-nova-closed-update.py

  APPLY_SITES=zona-01   — только перечисленные site id
  DRY_RUN=1             — план без мутаций
  NOVA_INSTALL_FRONTEND=1 на первой витрине с runtime (по умолчанию да, если
                          в APPLY_SITES есть сайт и нужен runtime; для
                          zona-only frontend не переустанавливается)
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation" / "host"))
from nova_closed_provenance import (  # noqa: E402
    CLOSED_SITES,
    RUNTIME_COMMIT,
    RUNTIME_REPO,
    build_manifest,
    by_site,
)

FRONT = Path("/srv/lords/.frontend")
MANDATE = "SITE_FACTORY_ROOT_20260909"
MANDATE_ENV = "FACTORY_OWNER_ROOT_MANDATE"


def say(msg: str) -> None:
    print(f"[apply-nova] {msg}", flush=True)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(cmd: list[str], *, env: dict | None = None, check: bool = True) -> subprocess.CompletedProcess:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    merged[MANDATE_ENV] = MANDATE
    say("$ " + " ".join(cmd))
    result = subprocess.run(cmd, env=merged, check=False, text=True, capture_output=True)
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n", flush=True)
    if result.stderr:
        print(result.stderr, end="" if result.stderr.endswith("\n") else "\n", flush=True)
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
    return result


def selected_sites() -> list:
    wanted = {s.strip() for s in os.environ.get("APPLY_SITES", "").split(",") if s.strip()}
    if not wanted:
        return list(CLOSED_SITES)
    known = by_site()
    missing = wanted - set(known)
    if missing:
        raise SystemExit(f"неизвестные APPLY_SITES: {sorted(missing)}")
    return [known[name] for name in ("lords-02", "animedia-01", "animedia-02", "zona-01") if name in wanted]


def main() -> int:
    dry = os.environ.get("DRY_RUN", "") == "1"
    sites = selected_sites()
    frontend_src = Path(RUNTIME_REPO) / "automation/host/lords-frontend.py"
    if not frontend_src.is_file():
        say(f"нет runtime frontend: {frontend_src}")
        return 2
    art = sha256(frontend_src)
    when = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())

    # Frontend ставится один раз и только из runtime-repo. Профильный Zona
    # worktree не перезаписывает общий рантайм.
    install_on = None
    if os.environ.get("FORCE_INSTALL_FRONTEND", "") == "1":
        install_on = sites[0]["site"]
    elif len(sites) == len(CLOSED_SITES):
        install_on = "lords-02"

    say(f"artifact_sha256={art}")
    say(f"runtime_commit={RUNTIME_COMMIT}")
    if (FRONT / "lords-frontend.py").exists():
        say(f"live_before={sha256(FRONT / 'lords-frontend.py')}")
    for s in sites:
        say(
            f"plan {s['site']} source={s['source_commit'][:12]} "
            f"runtime={s['runtime_commit'][:12]} profile={s['profile']} repo={s['source_repo']}"
        )

    if dry:
        for s in sites:
            build_id = f"{when}-{s['source_commit'][:8]}-nova"
            manifest = build_manifest(
                family=s["family"],
                design_version=s["design_version"],
                source_commit=s["source_commit"],
                runtime_commit=s["runtime_commit"],
                build_id=build_id,
                artifact_sha256=art,
                profile=s["profile"],
                built_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            )
            say(f"dry-manifest {s['site']}: source={manifest['source_commit'][:12]} runtime={manifest['runtime_commit'][:12]}")
        say("DRY_RUN=1 — мутаций нет")
        return 0

    if os.environ.get(MANDATE_ENV) != MANDATE:
        os.environ[MANDATE_ENV] = MANDATE

    rb = FRONT / ".rollback" / f"pre-closed-update-{when}"
    rb.mkdir(parents=True, exist_ok=True)
    for name in (
        "lords-frontend.py",
        "collection_contract.py",
        *[f"template-manifest-{s['site']}.json" for s in sites],
    ):
        src = FRONT / name
        if src.exists():
            shutil.copy2(src, rb / name)
    (rb / "rollback-meta.json").write_text(
        json.dumps(
            {
                "created_at": when,
                "artifact_sha256": art,
                "runtime_commit": RUNTIME_COMMIT,
                "sites": [
                    {
                        "site": s["site"],
                        "source_commit": s["source_commit"],
                        "runtime_commit": s["runtime_commit"],
                    }
                    for s in sites
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    say(f"rollback snapshot: {rb}")

    ports = {
        "lords-02": ("9111", "Lordserial"),
        "animedia-01": ("9121", "Animedia"),
        "animedia-02": ("9122", "Animedia"),
        "zona-01": ("9120", "Zona Cinema"),
    }
    legacy = {
        "lords-02": "/srv/lords/lords-02/current/site",
        "animedia-01": "/srv/lords/animedia-01/current/site",
        "animedia-02": "/srv/lords/animedia-02/current/site",
        "zona-01": "/srv/lords/zona-01/current/site",
    }

    applied: list[str] = []
    try:
        for s in sites:
            port, sitename = ports[s["site"]]
            build_id = f"{when}-{s['source_commit'][:8]}-nova"
            install = "1" if s["site"] == install_on else "0"
            if s["family"] == "lords":
                script = ROOT / "automation/host/deploy-nova-lords.sh"
                args = [
                    s["site"], s["domain"], port, s["profile"], sitename, build_id, art,
                ]
            else:
                script = ROOT / "automation/host/deploy-nova-family.sh"
                args = [
                    s["site"], s["domain"], port, s["family"], s["profile"], sitename,
                    s["design_version"], build_id, art, legacy[s["site"]],
                ]
            env_vars = {
                "REPO": s["source_repo"],
                "SOURCE_COMMIT": s["source_commit"],
                "RUNTIME_COMMIT": s["runtime_commit"],
                "NOVA_INSTALL_FRONTEND": install,
                "RUNTIME_REPO": s["runtime_repo"],
                MANDATE_ENV: MANDATE,
            }
            if s["family"] == "lords":
                env_vars["DESIGN_VERSION"] = s["design_version"]
            env_cmd = [
                "sudo", "-n", "env",
                *[f"{k}={v}" for k, v in env_vars.items()],
                "bash", str(script), *args,
            ]
            run(env_cmd, env={MANDATE_ENV: MANDATE})
            applied.append(s["site"])

            # Доказательство: на диске именно source/runtime из карты.
            live_m = json.loads((FRONT / f"template-manifest-{s['site']}.json").read_text(encoding="utf-8"))
            if live_m.get("source_commit") != s["source_commit"]:
                raise RuntimeError(
                    f"{s['site']}: source_commit={live_m.get('source_commit')} "
                    f"ожидался {s['source_commit']}"
                )
            if live_m.get("runtime_commit") != s["runtime_commit"]:
                raise RuntimeError(
                    f"{s['site']}: runtime_commit={live_m.get('runtime_commit')} "
                    f"ожидался {s['runtime_commit']}"
                )
            if live_m.get("profile") != s["profile"]:
                raise RuntimeError(f"{s['site']}: profile={live_m.get('profile')} ожидался {s['profile']}")

        run(["sudo", "-n", "nginx", "-t"], env={MANDATE_ENV: MANDATE})
        for s in sites:
            unit = f"nova-{s['site']}.service"
            out = run(["systemctl", "is-active", unit], check=False)
            if out.returncode != 0:
                raise RuntimeError(f"{unit} not active")
            say(f"{unit}: active")
    except Exception as exc:
        say(f"ОТКАЗ после {applied}: {exc}")
        say(f"откат: манифесты и frontend в {rb}")
        return 1

    out_dir = ROOT / "var" / "build" / "nova-closed-update-20260918"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "apply-result.json").write_text(
        json.dumps(
            {
                "ok": True,
                "applied_at": when,
                "artifact_sha256": art,
                "runtime_commit": RUNTIME_COMMIT,
                "rollback": str(rb),
                "sites": [
                    {
                        "site": s["site"],
                        "domain": s["domain"],
                        "source_commit": s["source_commit"],
                        "runtime_commit": s["runtime_commit"],
                        "profile": s["profile"],
                        "build_id": f"{when}-{s['source_commit'][:8]}-nova",
                    }
                    for s in sites
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    say("DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
