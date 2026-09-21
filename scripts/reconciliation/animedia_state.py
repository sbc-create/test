#!/usr/bin/env python3
"""Снимает фактическое состояние Animedia: что лежит на диске и что в памяти.

Манифест и заголовок витрины говорят про одно и то же разными голосами, и
расхождение между ними — обычный источник ложного «выложено». Здесь оба
голоса записаны рядом: digest файла на диске, digest релиза и то, что
процесс реально отдаёт по HTTP.

Скрипт только читает.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import urllib.request

FRONT = pathlib.Path("/srv/lords/.frontend")

ФАЙЛЫ = {
    "shared": FRONT / "lords-frontend.py",
    "release_b16": FRONT / "releases/20260921T153817Z-c8c4587-animedia-b16/lords-frontend.py",
    "release_rollback": FRONT / "releases/20260921T154512Z-8966632-animedia-rollback/lords-frontend.py",
}

МАНИФЕСТЫ = {
    "animedia-01 (icu)": FRONT / "template-manifest-animedia-01.json",
    "animedia-02 (space)": FRONT / "template-manifest-animedia-02.json",
    "animedia-01 .before-b16": FRONT / "template-manifest-animedia-01.json.before-b16",
    "animedia-02 .before-b16": FRONT / "template-manifest-animedia-02.json.before-b16",
}

ПОРТЫ = {"animedia-01 (icu)": 9121, "animedia-02 (space)": 9122}
ПРОЦЕССЫ = (664915, 2693863)


def sha(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    отчёт: dict[str, object] = {}

    файлы = {}
    for имя, путь in ФАЙЛЫ.items():
        if путь.exists():
            файлы[имя] = {"path": str(путь), "sha256": sha(путь),
                          "bytes": путь.stat().st_size}
        else:
            файлы[имя] = {"path": str(путь), "отсутствует": True}
    отчёт["файлы"] = файлы

    манифесты = {}
    for имя, путь in МАНИФЕСТЫ.items():
        if путь.exists():
            d = json.loads(путь.read_text(encoding="utf-8"))
            манифесты[имя] = {
                "build_id": d.get("build_id"),
                "artifact_sha256": d.get("artifact_sha256"),
                "source_commit": d.get("source_commit"),
                "profile": d.get("profile"),
                "mtime": путь.stat().st_mtime,
            }
    отчёт["манифесты"] = манифесты

    процессы = {}
    for pid in ПРОЦЕССЫ:
        try:
            cmd = pathlib.Path(f"/proc/{pid}/cmdline").read_bytes()
            процессы[pid] = cmd.replace(b"\0", b" ").decode("utf8", "replace").strip()
        except FileNotFoundError:
            процессы[pid] = "нет процесса"
    отчёт["процессы"] = процессы

    живое = {}
    for имя, порт in ПОРТЫ.items():
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{порт}/", timeout=30) as r:
                h = {k.lower(): v for k, v in r.headers.items()}
                живое[имя] = {
                    "port": порт, "status": r.status,
                    "profile": h.get("x-site-factory-profile"),
                    "build": h.get("x-site-factory-build-id"),
                    "artifact": h.get("x-site-factory-artifact-sha256"),
                    "revision": h.get("x-site-factory-template-revision"),
                    "robots": h.get("x-robots-tag"),
                }
        except Exception as e:
            живое[имя] = {"port": порт, "ошибка": str(e)}
    отчёт["живое"] = живое

    print(json.dumps(отчёт, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
