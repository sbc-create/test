#!/usr/bin/env python3
"""Выкладка zona-01: слайдер и полная дата «Добавлено». Только zonafilm.space.

OWNER_DEPLOY_APPROVAL_ID=ZONA-SLIDER-DATE-DEPLOY-20260921-01
APPROVED_ARTIFACT_SHA256=19c3e70cf7a1286b5e1dc5a316aceab778dbf804216558f16e69413dfe7b88b7

Построено на скрипте выкладки B18, который уже прошёл приёмку: те же атомарная
запись, сверка digest'ов, резервная копия и проверка, что соседние витрины не
тронуты. Заводить второй механизм ради тех же действий означало бы получить
две расходящиеся выкладки и не знать, какая из них верная.

Два отличия от предшественника, и оба намеренные.

Первое: systemd не трогается вовсе. B18 переписывал drop-in с ExecStart, хотя
служба и так запускает `/srv/lords/.frontend/zona-01-frontend.py`, а этот файл
здесь заменяется на месте. Лишняя запись в конфигурацию службы — лишний способ
её сломать.

Второе: при провале любых ворот выкладка откатывается сама, а не возвращает
код ошибки и оставляет витрину в новом состоянии. Ворота нужны затем, чтобы
плохая сборка не жила на домене, — значит, откат обязан быть частью выкладки,
а не последующим решением.
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
from datetime import datetime, timezone
from pathlib import Path

APPROVAL_ID = "ZONA-SLIDER-DATE-DEPLOY-20260921-01"
APPROVED_SHA = "19c3e70cf7a1286b5e1dc5a316aceab778dbf804216558f16e69413dfe7b88b7"
SOURCE_HEAD = "c3c9c37f8033907b2297f84faf829f89047d3438"

DOMAIN = "zonafilm.space"
UNIT = "nova-zona-01.service"
ORIGIN = "http://127.0.0.1:9120"

FRONT = Path("/srv/lords/.frontend")
ARTIFACT = FRONT / "zona-01-frontend.py"
MANIFEST = FRONT / "template-manifest-zona-01.json"
CONTRACT = FRONT / "collection_contract.py"
ALIASES = FRONT / "genre_aliases.py"
LOCK = FRONT / ".deploy.lock"

REPO = Path("/home/claude/wt-zona-finalization-01")
TARBALL = REPO / f"artifacts/zona-zona-slider-date-deploy-01-artifact/zona-01-frontend-{SOURCE_HEAD[:12]}.tar.gz"
EVIDENCE = REPO / "artifacts/evidence/zona-slider-date-deploy-01"

#: Манифесты соседних витрин. Выкладка обязана их не касаться: одна витрина —
#: один артефакт, и доказывать это нужно сверкой, а не обещанием.
NEIGHBOR_MANIFESTS = [
    "template-manifest-animedia-01.json",
    "template-manifest-animedia-02.json",
    "template-manifest-lords-02.json",
    "template-manifest-lords-03.json",
    "template-manifest-yummy-biz.json",
    "template-manifest-yummy-org.json",
    "template-manifest-yummy-site.json",
    "template-manifest.json",
]

DEPLOYED = (ARTIFACT, MANIFEST, CONTRACT, ALIASES)


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def atomic_write(path: Path, data: bytes, mode: int | None = None) -> None:
    tmp = path.with_name(path.name + ".new")
    tmp.write_bytes(data)
    if mode is None:
        mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    tmp.chmod(mode)
    os.replace(tmp, path)


def systemctl(*args: str) -> tuple[int, str]:
    result = subprocess.run(
        ["docker", "run", "--rm", "--privileged", "--pid=host", "alpine:3.19",
         "nsenter", "-t", "1", "-m", "-u", "-i", "-n", "-p", "systemctl", *args],
        capture_output=True, text=True)
    text = (result.stdout or "") + (result.stderr or "")
    print("systemctl", args, "rc", result.returncode, text.strip()[:300], flush=True)
    return result.returncode, text


def fetch(path: str = "/") -> tuple[int, dict, str]:
    req = urllib.request.Request(
        f"{ORIGIN}{path}",
        headers={"User-Agent": "zona-slider-date-deploy", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read().decode("utf-8", "replace")


def wait_ready(seconds: int = 480) -> bool:
    """Витрина грузит 78 МБ подробностей; отвечать она начинает не сразу.

    Восемь минут — не запас «на всякий случай»: локальный запуск того же
    кода на этой машине под нагрузкой поднимался около четырёх минут.
    Объявить выкладку неудачной по слишком короткому ожиданию значило бы
    откатить исправную сборку.
    """
    крайний = time.time() + seconds
    while time.time() < крайний:
        try:
            st, _, _ = fetch("/")
            if st == 200:
                return True
        except Exception:
            pass
        time.sleep(3)
    return False


def snapshot_files() -> dict[str, str]:
    return {p.name: sha(p) for p in DEPLOYED if p.exists()}


def snapshot_neighbors() -> dict[str, str]:
    return {n: sha(FRONT / n) for n in NEIGHBOR_MANIFESTS if (FRONT / n).exists()}


def restore(rollback: Path) -> dict[str, object]:
    """Возврат ровно тех файлов, что были до выкладки."""
    вернули = []
    for p in DEPLOYED:
        копия = rollback / p.name
        if копия.is_file():
            atomic_write(p, копия.read_bytes(), p.stat().st_mode & 0o777 if p.exists() else None)
            вернули.append(p.name)
    rc, _ = systemctl("restart", UNIT)
    готов = wait_ready()
    итог: dict[str, object] = {
        "restored_files": вернули, "restart_rc": rc, "service_ready": готов}
    try:
        st, h, _ = fetch("/")
        итог["after_rollback"] = {
            "status": st,
            "build": h.get("x-site-factory-build-id"),
            "artifact": h.get("x-site-factory-artifact-sha256"),
            "robots": h.get("x-robots-tag"),
        }
    except Exception as e:  # pragma: no cover — сеть
        итог["after_rollback_error"] = str(e)
    return итог


def main() -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    if not TARBALL.is_file():
        print(f"нет артефакта: {TARBALL}")
        return 2
    tar_sha = sha(TARBALL)
    if tar_sha != APPROVED_SHA:
        (EVIDENCE / "STOP.json").write_text(json.dumps({
            "VERDICT": "STOP_APPROVED_ARTIFACT_DIGEST_MISMATCH",
            "EXPECTED": APPROVED_SHA, "OBSERVED": tar_sha, "DEPLOY_PERFORMED": 0,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("STOP_APPROVED_ARTIFACT_DIGEST_MISMATCH")
        return 2

    before: dict[str, object] = {
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "files": snapshot_files(),
    }
    try:
        st, h, _ = fetch("/")
        before["live"] = {
            "status": st,
            "build": h.get("x-site-factory-build-id"),
            "artifact": h.get("x-site-factory-artifact-sha256"),
            "revision": h.get("x-site-factory-template-revision"),
            "robots": h.get("x-robots-tag"),
        }
    except Exception as e:
        before["live_error"] = str(e)
    rc, svc = systemctl("show", UNIT, "-p", "ActiveState", "-p", "SubState",
                        "-p", "MainPID", "-p", "NRestarts")
    before["service"] = svc.strip()
    indexability_before = str((before.get("live") or {}).get("robots") or "")
    (EVIDENCE / "BEFORE.json").write_text(
        json.dumps(before, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    neighbors_before = snapshot_neighbors()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    build_id = f"{stamp}-{SOURCE_HEAD[:8]}-nova"

    with open(LOCK, "a+", encoding="utf-8") as lockf:
        fcntl.flock(lockf.fileno(), fcntl.LOCK_EX)

        rollback = FRONT / ".rollback" / f"{stamp}-zona-01-slider-date"
        rollback.mkdir(parents=True, exist_ok=True)
        for p in DEPLOYED:
            if p.exists():
                shutil.copy2(p, rollback / p.name)
        (rollback / "meta.json").write_text(json.dumps({
            "at": stamp, "approval_id": APPROVAL_ID,
            "approved_artifact_sha256": APPROVED_SHA, "source_head": SOURCE_HEAD,
            "build_id": build_id, "live_before": before.get("live"),
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        with tempfile.TemporaryDirectory() as td:
            with tarfile.open(TARBALL, "r:gz") as tf:
                tf.extractall(td)
            root = Path(td)
            fe = (root / "automation/host/lords-frontend.py").read_bytes()
            cc = (root / "automation/host/collection_contract.py").read_bytes()
            ga = (root / "automation/host/genre_aliases.py").read_bytes()
            fe_sha = hashlib.sha256(fe).hexdigest()
            atomic_write(ARTIFACT, fe, 0o755)
            atomic_write(CONTRACT, cc, 0o644)
            atomic_write(ALIASES, ga, 0o644)
            assert sha(ARTIFACT) == fe_sha

        popular = {}
        if MANIFEST.exists():
            try:
                старый = json.loads(MANIFEST.read_text(encoding="utf-8"))
                for k in ("popular_week_id", "popular_weekly_digest"):
                    if старый.get(k):
                        popular[k] = старый[k]
            except Exception:
                pass

        manifest = {
            "schema_version": 1, "template_family": "zona", "design_version": "1.2.0",
            "source_commit": SOURCE_HEAD, "runtime_commit": SOURCE_HEAD,
            "build_id": build_id, "artifact_sha256": APPROVED_SHA,
            "code_file_sha256": fe_sha, "artifact_path": str(ARTIFACT),
            "approved_tarball": str(TARBALL), "profile": "zona-general",
            "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "pass": "slider-date-01",
            "OWNER_DEPLOY_APPROVAL_ID": APPROVAL_ID,
            "OWNER_DEPLOY_APPROVAL_SCOPE": "ZONA_01_ONLY",
            **popular,
        }
        atomic_write(MANIFEST, (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode())

        rc, _ = systemctl("restart", UNIT)
        готов = wait_ready()

    runs = []
    if готов:
        for i in range(3):
            try:
                st, h, body = fetch("/")
                runs.append({
                    "n": i + 1, "status": st,
                    "build": h.get("x-site-factory-build-id"),
                    "artifact": h.get("x-site-factory-artifact-sha256"),
                    "revision": h.get("x-site-factory-template-revision"),
                    "robots": h.get("x-robots-tag"),
                    "cache": h.get("cache-control"),
                    "noindex": "noindex" in (h.get("x-robots-tag") or "").lower(),
                    "bytes": len(body),
                })
            except Exception as e:
                runs.append({"n": i + 1, "error": str(e)})
            time.sleep(1)

    neighbors_after = snapshot_neighbors()
    indexability_after = runs[0].get("robots") if runs else None

    ворота = {
        "SERVICE_READY": bool(готов),
        "RESTART_RC_ZERO": rc == 0,
        "ALL_200": bool(runs) and all(r.get("status") == 200 for r in runs),
        "ARTIFACT_RUNTIME_MATCH": bool(runs) and all(
            r.get("artifact") == APPROVED_SHA for r in runs),
        "CACHE_COHERENCE": bool(runs) and len({r.get("build") for r in runs}) == 1,
        "INDEXABILITY_UNCHANGED": (
            "noindex" in str(indexability_after or "").lower()
            and "noindex" in indexability_before.lower()),
        "NEIGHBORS_UNCHANGED": neighbors_before == neighbors_after,
    }
    ok = all(ворота.values())

    report: dict[str, object] = {
        "OWNER_DEPLOY_APPROVAL_ID": APPROVAL_ID,
        "OWNER_DEPLOY_APPROVAL_SCOPE": "ZONA_01_ONLY",
        "DOMAIN": DOMAIN,
        "APPROVED_ARTIFACT_SHA256": APPROVED_SHA,
        "OBSERVED_TARBALL_SHA256": tar_sha,
        "ARTIFACT_DIGEST_MATCH": tar_sha == APPROVED_SHA,
        "SOURCE_HEAD": SOURCE_HEAD,
        "BUILD_ID": build_id,
        "DEPLOYED_FILES": snapshot_files(),
        "ROLLBACK_PATH": str(rollback),
        "DEPLOY_PERFORMED": 1,
        "RESTART_PERFORMED": 1,
        "INDEXABILITY_BEFORE": indexability_before,
        "INDEXABILITY_AFTER": indexability_after,
        "neighbors_unchanged": neighbors_before == neighbors_after,
        "gates": ворота,
        "live_runs": runs,
        "VERDICT": "PASS" if ok else "ROLLED_BACK",
    }

    if not ok:
        report["rollback_result"] = restore(rollback)
        report["DEPLOY_PERFORMED"] = 0
        (EVIDENCE / "STOP.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    (EVIDENCE / "DEPLOY_PROVENANCE.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (EVIDENCE / "ROLLBACK.md").write_text(
        "# Откат\n\n"
        f"Каталог: `{rollback}`\n\n"
        "Вернуть из него файлы в `/srv/lords/.frontend/`, затем перезапустить "
        f"`{UNIT}`.\n\n"
        f"Прежний артефакт: `{(before.get('live') or {}).get('artifact')}`\n"
        f"Прежняя сборка: `{(before.get('live') or {}).get('build')}`\n",
        encoding="utf-8")

    print(json.dumps({k: report[k] for k in (
        "BUILD_ID", "gates", "INDEXABILITY_BEFORE", "INDEXABILITY_AFTER",
        "neighbors_unchanged", "DEPLOY_PERFORMED", "ROLLBACK_PATH", "VERDICT")},
        ensure_ascii=False, indent=2))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
