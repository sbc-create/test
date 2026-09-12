#!/usr/bin/env python3
"""Копия и восстановление хранилища наборов изменений.

Копия снимается через backup API sqlite3, а не `cp`: копирование файла под
активной записью даёт склейку двух состояний, в которой часть набора уже
перешла в новое состояние, а часть ещё нет.

Восстановление всегда проверяется в изоляции. Копия, которую ни разу не
разворачивали, — это предположение о копии.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

from . import store as S

КАТАЛОГ = Path(os.environ.get(
    "CHANGESET_BACKUP_DIR", "/srv/site-factory/changeset-store/backups"))

#: Копия вне хоста — контракт, а не факт: второй хост не выделен.
OFF_HOST_BACKUP = "PLANNED"


def _версии() -> dict:
    м = Path("/srv/site-factory/control-api/release-manifest.json")
    итог = {"source_commit": None, "artifact_sha256": None}
    if м.is_file():
        try:
            d = json.loads(м.read_text(encoding="utf-8"))
            итог = {"source_commit": d.get("sha"), "artifact_sha256": d.get("digest")}
        except ValueError:
            pass
    return итог


def _слепок(c: sqlite3.Connection) -> dict:
    по_состояниям = {r["status"]: r["n"] for r in c.execute(
        "SELECT status, count(*) n FROM changeset GROUP BY status")}
    наборов = c.execute("SELECT count(*) FROM changeset").fetchone()[0]
    переходов = c.execute("SELECT count(*) FROM changeset_transition").fetchone()[0]
    целей = c.execute("SELECT count(*) FROM changeset_target").fetchone()[0]
    ящик = c.execute("SELECT count(*) FROM changeset_outbox").fetchone()[0]
    задолженность = c.execute("SELECT count(*) FROM changeset_outbox "
                              "WHERE published_at IS NULL").fetchone()[0]
    dlq = c.execute("SELECT count(*) FROM changeset_dlq").fetchone()[0]
    замки = c.execute("SELECT count(*) FROM changeset_lock").fetchone()[0]
    # Отпечаток истории решений: восстановление обязано вернуть её целиком,
    # а не «столько же строк».
    строки = [tuple(r) for r in c.execute(
        "SELECT changeset_id, action, from_status, to_status, actor_id, "
        "occurred_at FROM changeset_transition ORDER BY seq")]
    отпечаток = hashlib.sha256(
        json.dumps(строки, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return {"changesets": наборов, "by_status": по_состояниям,
            "transitions": переходов, "targets": целей,
            "outbox": ящик, "outbox_backlog": задолженность, "dlq": dlq,
            "locks": замки, "transition_digest": отпечаток}


def создать() -> dict:
    КАТАЛОГ.mkdir(parents=True, exist_ok=True)
    метка = S.сейчас().replace(":", "").replace("-", "")[:15]
    цель = КАТАЛОГ / f"changesets-{метка}.sqlite3"
    ист = S.открыть()
    слепок = _слепок(ист)
    наз = sqlite3.connect(цель)
    with наз:
        ист.backup(наз)
    наз.close(); ист.close()
    сумма = hashlib.sha256(цель.read_bytes()).hexdigest()
    манифест = {"backup_file": цель.name, "created_at": S.сейчас(),
                "sha256": сумма, "size": цель.stat().st_size,
                "source_snapshot": слепок, "versions": _версии(),
                "off_host_backup": OFF_HOST_BACKUP}
    цель.with_suffix(".manifest.json").write_text(
        json.dumps(манифест, ensure_ascii=False, indent=2), encoding="utf-8")
    return манифест


def восстановить(файл: Path) -> dict:
    манифест = json.loads(файл.with_suffix(".manifest.json")
                          .read_text(encoding="utf-8"))
    сумма = hashlib.sha256(файл.read_bytes()).hexdigest()
    с_манифестом = сумма == манифест["sha256"]
    with tempfile.TemporaryDirectory(prefix="changeset-restore-") as d:
        копия = Path(d) / "restored.sqlite3"
        копия.write_bytes(файл.read_bytes())
        c = sqlite3.connect(f"file:{копия}?mode=ro", uri=True)
        c.row_factory = sqlite3.Row
        восст = _слепок(c)
        триггеры = sorted(x[0] for x in c.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger'"))
        c.close()
    исх = манифест["source_snapshot"]
    расхождения = {k: [исх[k], восст[k]] for k in исх if исх[k] != восст[k]}
    # Запрет прямой записи состояния обязан пережить восстановление: копия без
    # триггера — обычная таблица, а не машина состояний.
    ok = (с_манифестом and not расхождения
          and "cs_no_direct_status" in триггеры)
    return {"restore_verdict": "PASS" if ok else "FAIL",
            "checksum_matches_manifest": с_манифестом,
            "restored_snapshot": восст, "manifest_snapshot": исх,
            "mismatches": расхождения, "guards": триггеры,
            "versions": манифест.get("versions", {}),
            "off_host_backup": OFF_HOST_BACKUP}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="копия хранилища наборов")
    ap.add_argument("режим", choices=["create", "restore", "cycle"])
    ap.add_argument("--file")
    a = ap.parse_args(argv)
    м = None
    if a.режим in ("create", "cycle"):
        м = создать()
        print("копия:", json.dumps(м, ensure_ascii=False, indent=2))
    if a.режим in ("restore", "cycle"):
        f = Path(a.file) if a.file else КАТАЛОГ / м["backup_file"]
        r = восстановить(f)
        print("восстановление:", json.dumps(r, ensure_ascii=False, indent=2))
        return 0 if r["restore_verdict"] == "PASS" else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
