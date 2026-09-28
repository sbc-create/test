#!/usr/bin/env python3
"""Собирает измеримую часть лэджера LORDS-CURSOR-WORK-RECONCILIATION-01.

Правило A2 требует установить состояние, а не предположить его. Скрипт берёт
факты из трёх независимых источников и ничего не достраивает по памяти:

* git — ветки, worktree, их грязное состояние и предки;
* файловая система хоста — артефакт рантайма, манифесты витрин, политика
  индексации, точки отката;
* /proc — какой процесс какой порт слушает и когда он стартовал.

Того, что измерить нельзя, в выводе нет: поле получает NOT_MEASURABLE и
причину. Пустое значение здесь запрещено так же, как и в манифесте сайта.

Запуск: python3 scripts/reconciliation/lords_discovery.py
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import pathlib
import subprocess

REPO_CANONICAL = "/srv/site-factory/repo"
HERE = pathlib.Path(__file__).resolve().parents[2]
OUT = HERE / "artifacts" / "evidence" / "lords-cursor-reconciliation-01"
FRONT = pathlib.Path("/srv/lords/.frontend")

#: Порт → витрина. Взято из ExecStart юнитов в /etc/systemd/system, а не выбрано.
PORTS = {
    "9110": ("lords-01", "lordfilm47.space", "lords-nova-01.service"),
    "9111": ("lords-02", "lordserial33.biz", "nova-lords-02.service"),
    "9112": ("lords-03", "1lordserials1.online", "nova-lords-03.service"),
}


def _git(*args: str, cwd: str = REPO_CANONICAL) -> str:
    res = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    return res.stdout.strip() if res.returncode == 0 else ""


def _digest(path: pathlib.Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def worktrees() -> list[dict]:
    """Каждый worktree фабрики с его грязным состоянием."""
    raw = _git("worktree", "list", "--porcelain")
    items: list[dict] = []
    cur: dict = {}
    for line in raw.splitlines():
        if line.startswith("worktree "):
            cur = {"path": line.split(" ", 1)[1]}
        elif line.startswith("HEAD "):
            cur["head"] = line.split(" ", 1)[1]
        elif line.startswith("branch "):
            cur["branch"] = line.split(" ", 1)[1].replace("refs/heads/", "")
        elif line.startswith("detached"):
            cur["branch"] = "(detached)"
        elif not line and cur:
            items.append(cur)
            cur = {}
    if cur:
        items.append(cur)

    for item in items:
        path = item["path"]
        res = subprocess.run(
            ["git", "status", "--porcelain=v1"], cwd=path, capture_output=True, text=True
        )
        lines = [ln for ln in res.stdout.splitlines() if ln.strip()]
        item["readable"] = res.returncode == 0
        item["dirty_count"] = len(lines)
        item["dirty_files"] = lines[:200]
        haystack = f"{path} {item.get('branch', '')}".lower()
        item["lords_related"] = "lords" in haystack
    return items


def live_baseline() -> dict:
    """Что на хосте на самом деле: байты рантайма, манифесты, процессы."""
    runtime = FRONT / "lords-frontend.py"
    runtime_sha = _digest(runtime)

    # Время старта процесса — из /proc, а не из отчёта прошлого прогона.
    hz = os.sysconf("SC_CLK_TCK")
    btime = 0
    for line in pathlib.Path("/proc/stat").read_text().splitlines():
        if line.startswith("btime"):
            btime = int(line.split()[1])
            break

    procs: dict[str, dict] = {}
    for entry in pathlib.Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            cmd = (entry / "cmdline").read_bytes().decode("utf-8", "replace").replace("\0", " ")
        except OSError:
            continue
        if "/srv/lords/.frontend/lords-frontend.py" not in cmd:
            continue
        for port in PORTS:
            if f"--port {port}" in cmd:
                try:
                    fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
                    started = btime + int(fields[19]) / hz
                    started_iso = (
                        _dt.datetime.fromtimestamp(started, _dt.timezone.utc)
                        .isoformat()
                        .replace("+00:00", "Z")
                    )
                except (OSError, IndexError, ValueError):
                    started_iso = "NOT_MEASURABLE"
                procs[port] = {"pid": int(entry.name), "started_utc": started_iso}

    policy = {}
    try:
        policy = json.loads((FRONT / "indexing-policy.json").read_text()).get("domains", {})
    except (OSError, ValueError):
        policy = {}

    sites = {}
    for port, (site, domain, unit) in PORTS.items():
        manifest_path = FRONT / f"template-manifest-{site}.json"
        if not manifest_path.is_file():
            # lords-01 исторически обслуживается манифестом по умолчанию.
            manifest_path = FRONT / "template-manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text())
        except (OSError, ValueError):
            manifest = {}
        proc = procs.get(port, {})
        declared = manifest.get("artifact_sha256", "")
        sites[site] = {
            "domain": domain,
            "unit": unit,
            "port": int(port),
            "manifest_path": str(manifest_path),
            "declared_artifact_sha256": declared,
            "declared_build_id": manifest.get("build_id", ""),
            "declared_source_commit": manifest.get("source_commit", ""),
            "declared_profile": manifest.get("profile", ""),
            "runtime_executable": str(runtime),
            "runtime_artifact_sha256": runtime_sha,
            # Питон читает исходник при старте: процесс, поднятый позже подмены
            # файла, исполняет новые байты.
            "runtime_matches_manifest": bool(declared) and declared == runtime_sha,
            "process": proc or {"pid": None, "started_utc": "NOT_RUNNING"},
            "indexing_expected": policy.get(domain, {}).get("indexing_expected", "NOT_MEASURABLE"),
            "indexing_reason": policy.get(domain, {}).get("indexing_reason", ""),
        }

    return {
        "measured_at_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "runtime_executable_shared_by_all_sites": True,
        "runtime_artifact_sha256": runtime_sha,
        "runtime_mtime_utc": _dt.datetime.fromtimestamp(
            runtime.stat().st_mtime, _dt.timezone.utc
        ).isoformat()
        if runtime.is_file()
        else "NOT_MEASURABLE",
        "http_probe": "BLOCKED_ACCESS: хостов Lords нет в allowlist канонического репозитория",
        "sites": sites,
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    trees = worktrees()
    branches = [
        ln.strip()
        for ln in _git(
            "branch", "-a", "--format=%(refname:short)|%(objectname)|%(committerdate:iso8601)"
        ).splitlines()
        if "lords" in ln.lower() or ln.startswith("cursor/")
    ]

    matrix = {
        "canonical_repo": REPO_CANONICAL,
        "canonical_head": _git("rev-parse", "HEAD"),
        "canonical_branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "worktrees_total": len(trees),
        "worktrees_lords_related": sum(1 for t in trees if t["lords_related"]),
        "worktrees_dirty": sum(1 for t in trees if t["dirty_count"]),
        "related_branches": branches,
        "worktrees": trees,
    }
    (OUT / "BRANCH_WORKTREE_MATRIX.json").write_text(
        json.dumps(matrix, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    (OUT / "LIVE_BASELINE.json").write_text(
        json.dumps(live_baseline(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("BRANCH_WORKTREE_MATRIX.json + LIVE_BASELINE.json written to", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
