#!/usr/bin/env python3
"""Откат кандидата и возврат вперёд — выполненные, а не подготовленные.

Подготовленный откат доказательством не является: доказывает только
выполненный. Здесь кандидат и предыдущий артефакт подставляются под одну
ссылку по очереди, и после каждой подстановки витрина опрашивается по HTTP.

Ничего производственного не затрагивается: и ссылка, и сервер — локальные.

    python3 scripts/lords_candidate_rollback_proof.py --candidate var/lords-candidate \
        --previous /home/claude/wt-zone-r2/var/build-a/lords-02 --port 8931
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.error
import urllib.request

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(КОРЕНЬ))

from factory.lords import artifact as artifact_mod   # noqa: E402


def подставить(ссылка: pathlib.Path, цель: pathlib.Path) -> None:
    """Атомарная замена ссылки: сначала новая рядом, затем переименование."""
    временная = ссылка.with_name(ссылка.name + ".new")
    if временная.is_symlink() or временная.exists():
        временная.unlink()
    временная.symlink_to(цель)
    os.replace(временная, ссылка)


def опросить(база: str, пути: list[str]) -> dict:
    итог = {}
    for п in пути:
        try:
            with urllib.request.urlopen(база + п, timeout=15) as о:
                тело = о.read()
                итог[п] = {"status": о.status, "bytes": len(тело)}
        except urllib.error.HTTPError as ош:
            итог[п] = {"status": ош.code, "bytes": 0}
        except Exception as ош:                       # сеть/сервер недоступны
            итог[п] = {"status": None, "error": type(ош).__name__}
    return итог


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--candidate", required=True)
    р.add_argument("--previous", required=True)
    р.add_argument("--port", type=int, default=8931)
    р.add_argument("--out", default="artifacts/lords-visual-parity/rollback-proof.json")
    а = р.parse_args(аргв)

    кандидат = pathlib.Path(а.candidate).resolve()
    прежний = pathlib.Path(а.previous).resolve()
    for п in (кандидат, прежний):
        if not (п / "route-map.json").is_file():
            raise SystemExit(f"{п}: это не собранная витрина")

    отпечатки = {"candidate": artifact_mod.отпечаток(кандидат),
                 "previous": artifact_mod.отпечаток(прежний)}
    if отпечатки["candidate"] == отпечатки["previous"]:
        raise SystemExit("артефакты совпадают: откат нечем отличить от возврата")

    корень = КОРЕНЬ / "var" / "rollback-stand"
    корень.mkdir(parents=True, exist_ok=True)
    ссылка = корень / "current"
    подставить(ссылка, кандидат)

    сервер = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(а.port), "--bind", "127.0.0.1"],
        cwd=str(ссылка), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    база = f"http://127.0.0.1:{а.port}"
    шаги = []
    try:
        time.sleep(1.5)
        ПУТИ = ["/", "/catalog/", "/assets/site.css"]
        for имя, цель in (("apply", кандидат), ("rollback", прежний),
                          ("restore_forward", кандидат)):
            подставить(ссылка, цель)
            # http.server держит корень открытым по пути, поэтому сервер
            # перезапускается: подмена ссылки под работающим процессом ничего
            # не доказала бы — он продолжал бы отдавать прежний каталог.
            сервер.terminate(); сервер.wait(timeout=10)
            сервер = subprocess.Popen(
                [sys.executable, "-m", "http.server", str(а.port), "--bind", "127.0.0.1"],
                cwd=str(ссылка), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1.5)
            ответы = опросить(база, ПУТИ)
            css = urllib.request.urlopen(база + "/assets/site.css", timeout=15).read()
            шаги.append({"шаг": имя, "цель": цель.name,
                         "artifact_sha256": artifact_mod.отпечаток(цель),
                         "ответы": ответы,
                         "container_1100": b"--container: 1100px" in css})
    finally:
        сервер.terminate()
        try:
            сервер.wait(timeout=10)
        except Exception:
            сервер.kill()

    итог = {"fingerprints": отпечатки, "steps": шаги,
            "rollback_executed": any(ш["шаг"] == "rollback" for ш in шаги),
            "restore_forward_executed": any(ш["шаг"] == "restore_forward" for ш in шаги),
            "all_http_200": all(о["status"] == 200 for ш in шаги
                                for о in ш["ответы"].values())}
    путь = КОРЕНЬ / а.out
    путь.parent.mkdir(parents=True, exist_ok=True)
    путь.write_text(json.dumps(итог, ensure_ascii=False, indent=1) + "\n",
                    encoding="utf-8")
    print(json.dumps(итог, ensure_ascii=False, indent=1))
    return 0 if итог["all_http_200"] else 1


if __name__ == "__main__":
    raise SystemExit(главное())
