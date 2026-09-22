#!/usr/bin/env python3
"""Локальный прогон кандидата Zona: поднять витрину и снять с неё измерения.

Ничего в production не трогает: витрина поднимается из рабочего дерева, на
свободном порту 194xx, со своим манифестом и своей копией снимка. Процесс
гасится по завершении, даже если приёмка упала.

Снимок задаётся каталогом: либо выборка (`zona-sample-snapshot.py`), либо
боевой снимок целиком. Второе честнее, но дороже: полный снимок поднимается
минутами, выборка — секундами.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
РАНТАЙМ = КОРЕНЬ / "automation/host/lords-frontend.py"
ПРИЁМКА = КОРЕНЬ / "automation/host/zona-visual-audit.py"
БОЕВОЙ = Path("/srv/lords/.frontend")


def свободный_порт(начало: int = 19400, конец: int = 19499) -> int:
    for п in range(начало, конец):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", п))
            except OSError:
                continue
            return п
    raise SystemExit("нет свободного порта в 194xx")


def манифест(куда: Path, design: str, build_id: str) -> Path:
    путь = куда / "template-manifest-zona-local.json"
    путь.write_text(json.dumps({
        "schema_version": 1, "template_family": "zona", "design_version": design,
        "source_commit": "local", "build_id": build_id, "artifact_sha256": "local",
        "profile": "zona-general", "built_at": "2026-09-22T00:00:00Z",
        "domain": "zonafilm.space", "service_name": "local-stand",
        "expected_indexability": "noindex,nofollow",
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    return путь


def ждать(base: str, proc, таймаут: float) -> bool:
    предел = time.time() + таймаут
    while time.time() < предел:
        if proc.poll() is not None:
            return False
        try:
            urllib.request.urlopen(base + "/", timeout=5).read(64)
            return True
        except urllib.error.HTTPError:
            return True
        except Exception:
            time.sleep(0.5)
    return False


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--snapshot", required=True,
                   help="каталог со снимком или 'production' для боевого")
    р.add_argument("--out", required=True)
    р.add_argument("--tag", default="run1")
    р.add_argument("--design", default="1.3.0")
    р.add_argument("--widths", default="320,390,768,1024,1440,1920")
    р.add_argument("--pages", default="")
    р.add_argument("--shots", action="store_true")
    р.add_argument("--boot-timeout", type=float, default=900.0)
    р.add_argument("--clock", default="2026-09-22T06:00:00Z")
    а = р.parse_args()

    выход = Path(а.out)
    выход.mkdir(parents=True, exist_ok=True)
    корень_снимка = БОЕВОЙ if а.snapshot == "production" else Path(а.snapshot)
    каталог = корень_снимка / "zona-01-catalog.json"
    if not каталог.is_file():
        raise SystemExit(f"снимка нет: {каталог}")

    порт = свободный_порт()
    среда = dict(os.environ)
    среда.update({
        "LORDS_TEMPLATE_MANIFEST": str(манифест(выход, а.design, f"zona-local-{а.tag}")),
        "LORDS_CATALOG": str(каталог),
        "LORDS_DETAILS": str(корень_снимка / "zona-01-details.json"),
        "LORDS_POPULAR_WEEKLY": str(корень_снимка / "zona-01-popular-weekly.json"),
        "LORDS_LEGACY_ROOT": str(выход / "legacy-root-otsutstvuet"),
        "LORDS_SITE_NAME": "Zona",
        "LORDS_CLOCK_ISO": а.clock,
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    среда.pop("LORDS_LEGACY_UPSTREAM", None)
    среда.pop("LORDS_METRIKA_COUNTER", None)

    лог = (выход / f"stand-{а.tag}.log").open("wb")
    proc = subprocess.Popen(
        [sys.executable, str(РАНТАЙМ), "--host", "127.0.0.1", "--port", str(порт)],
        stdout=лог, stderr=subprocess.STDOUT, env=среда, start_new_session=True)
    base = f"http://127.0.0.1:{порт}"
    t0 = time.time()
    try:
        if not ждать(base, proc, а.boot_timeout):
            лог.close()
            хвост = (выход / f"stand-{а.tag}.log").read_text(
                encoding="utf-8", errors="replace")[-2000:]
            raise SystemExit(f"витрина не поднялась за {а.boot_timeout}s:\n{хвост}")
        print(f"стенд поднят за {time.time() - t0:.1f}s на {base}", flush=True)
        команда = [sys.executable, str(ПРИЁМКА), "--base", base, "--out", а.out,
                   "--tag", а.tag, "--widths", а.widths]
        if а.pages:
            команда += ["--pages", а.pages]
        if а.shots:
            команда.append("--shots")
        код = subprocess.call(команда)
    finally:
        if proc.poll() is None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                proc.wait(timeout=20)
            except Exception:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except Exception:
                    pass
        лог.close()
    return код


if __name__ == "__main__":
    sys.exit(main())
