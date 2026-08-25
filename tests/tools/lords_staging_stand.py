#!/usr/bin/env python3
"""Локальный запуск трёх публичных стендов Lords из настоящих пакетов.

Отличие от `lords_stand.py` принципиальное. Тот поднимает рендерер прямо из
репозитория и проверяет шаблон. Этот распаковывает архивы, которые поедут на
сервер, и запускает их собственный `serve.py` — то есть проверяет ровно то, что
будет работать в production-контуре стенда, включая рантайм пакета.

Порты те же, что в реестре направления: 9101, 9102, 9103.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from factory.paths import PATHS  # noqa: E402

STAGING = PATHS.root / "artifacts/lords/staging/staging.json"
BUNDLES = PATHS.root / "artifacts/lords/bundle"
WORKDIR = PATHS.root / "var/lords-staging"
HOST = "127.0.0.1"


def ensure_built() -> dict:
    if not STAGING.exists():
        subprocess.run([sys.executable, "-m", "factory", "lords-staging"],
                       cwd=ROOT, check=True, capture_output=True)
    return json.loads(STAGING.read_text(encoding="utf-8"))


def unpack(site_id: str) -> Path:
    """Распаковка начисто: остаток прошлого релиза дал бы ложный результат."""
    target = WORKDIR / site_id
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    with tarfile.open(BUNDLES / f"{site_id}.tar") as archive:
        archive.extractall(target)
    return target


def wait_ready(port: int, attempts: int = 40) -> bool:
    for _ in range(attempts):
        try:
            with urllib.request.urlopen(
                    f"http://{HOST}:{port}/readyz", timeout=2) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(0.25)
    return False


def main() -> int:
    summary = ensure_built()
    processes = []
    try:
        for site in summary["sites"]:
            directory = unpack(site["site_id"])
            process = subprocess.Popen(
                [sys.executable, "serve.py"],
                cwd=directory,
                env={"LORDS_HOST": HOST, "LORDS_PORT": str(site["port"]),
                     "PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"},
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            processes.append(process)
            if not wait_ready(site["port"]):
                raise RuntimeError(f"{site['site_id']} не ответил на /readyz")
            print(json.dumps({
                "site_id": site["site_id"], "profile": site["profile"],
                "apex": site["apex"], "url": f"http://{HOST}:{site['port']}/",
            }, ensure_ascii=False), flush=True)

        print(f"стенды Lords подняты: {len(processes)}", flush=True)
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        for process in processes:
            process.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
