#!/usr/bin/env python3
"""Резервная копия и восстановление Audit Ledger.

Копия снимается через sqlite3 backup API — не `cp`: копирование файла под
активной записью даёт склейку двух состояний, которую цепь хешей честно
объявит повреждённой.

Восстановление всегда проверяется в изоляции, в отдельном каталоге. Копия,
которую ни разу не разворачивали, — это предположение о копии, а не копия.
"""
from __future__ import annotations
import argparse, hashlib, json, os, sqlite3, sys, tempfile
from pathlib import Path
from . import ledger_store as store

ЖУРНАЛ = os.environ.get("AUDIT_LEDGER_DB",
                        "/srv/site-factory/audit-ledger/audit_ledger.sqlite3")
КАТАЛОГ = Path(os.environ.get("AUDIT_BACKUP_DIR",
                              "/srv/site-factory/audit-ledger/backups"))
#: Копия вне этого хоста — контракт, а не факт. Пока реальное восстановление с
#: другого хоста не выполнено и не измерено, состояние остаётся NOT_READY.
OFF_HOST_BACKUP = "NOT_READY"
OFF_HOST_ПРИЧИНА = ("второй хост не выделен владельцем; восстановление вне "
                    "этого хоста не выполнялось и не проверялось")


def _слепок(c) -> dict:
    r = c.execute("SELECT count(*) n, coalesce(max(ledger_seq),0) s "
                  "FROM ledger_event").fetchone()
    cp = c.execute("SELECT checkpoint_id, ledger_seq, chain_root FROM "
                   "ledger_checkpoint ORDER BY ledger_seq DESC LIMIT 1").fetchone()
    посл = c.execute("SELECT event_hash FROM ledger_event ORDER BY ledger_seq "
                     "DESC LIMIT 1").fetchone()
    return {"count": r["n"], "last_seq": r["s"],
            "last_event_hash": посл["event_hash"] if посл else None,
            "checkpoint_id": cp["checkpoint_id"] if cp else None,
            "checkpoint_upto_seq": cp["ledger_seq"] if cp else None,
            "chain_root": cp["chain_root"] if cp else None}


def создать() -> dict:
    КАТАЛОГ.mkdir(parents=True, exist_ok=True)
    зап = store.открыть(ЖУРНАЛ)
    store.checkpoint(зап)
    зап.close()
    метка = store.сейчас().replace(":", "").replace("-", "")[:15]
    цель = КАТАЛОГ / f"audit-ledger-{метка}.sqlite3"
    ист = sqlite3.connect(f"file:{ЖУРНАЛ}?mode=ro", uri=True)
    ист.row_factory = sqlite3.Row
    слепок = _слепок(ист)
    наз = sqlite3.connect(цель)
    with наз:
        ист.backup(наз)
    наз.close(); ист.close()
    сумма = hashlib.sha256(цель.read_bytes()).hexdigest()
    манифест = {"backup_file": цель.name, "created_at": store.сейчас(),
                "sha256": сумма, "size": цель.stat().st_size,
                "source": ЖУРНАЛ, "source_snapshot": слепок,
                "off_host_backup": OFF_HOST_BACKUP,
                "off_host_reason": OFF_HOST_ПРИЧИНА}
    (цель.with_suffix(".manifest.json")).write_text(
        json.dumps(манифест, ensure_ascii=False, indent=2), encoding="utf-8")
    return манифест


def восстановить(файл: Path) -> dict:
    """Развернуть копию в отдельном каталоге и сверить с манифестом."""
    манифест = json.loads(файл.with_suffix(".manifest.json")
                          .read_text(encoding="utf-8"))
    сумма = hashlib.sha256(файл.read_bytes()).hexdigest()
    с_манифестом = (сумма == манифест["sha256"])
    with tempfile.TemporaryDirectory(prefix="ledger-restore-") as d:
        копия = Path(d) / "restored.sqlite3"
        копия.write_bytes(файл.read_bytes())
        c = sqlite3.connect(f"file:{копия}?mode=ro", uri=True)
        c.row_factory = sqlite3.Row
        восст = _слепок(c)
        цепь = store.проверить_цепь(c)
        # Триггеры неизменяемости должны пережить восстановление: копия без
        # них была бы обычной таблицей, а не журналом.
        триггеры = sorted(x[0] for x in c.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger'"))
        c.close()
    исх = манифест["source_snapshot"]
    поля = ("count", "last_seq", "last_event_hash", "checkpoint_id",
            "checkpoint_upto_seq", "chain_root")
    расхождения = {k: [исх[k], восст[k]] for k in поля if исх[k] != восст[k]}
    ok = (с_манифестом and not расхождения and цепь["ok"]
          and {"le_no_update", "le_no_delete"} <= set(триггеры))
    return {"restore_verdict": "PASS" if ok else "FAIL",
            "checksum_matches_manifest": с_манифестом,
            "restored_snapshot": восст, "manifest_snapshot": исх,
            "mismatches": расхождения, "chain_ok": цепь["ok"],
            "immutability_triggers": триггеры,
            "off_host_backup": OFF_HOST_BACKUP,
            "off_host_reason": OFF_HOST_ПРИЧИНА}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("режим", choices=["create", "restore", "cycle"])
    ap.add_argument("--file")
    a = ap.parse_args()
    if a.режим in ("create", "cycle"):
        м = создать()
        print("копия:", json.dumps(м, ensure_ascii=False, indent=2))
    if a.режим in ("restore", "cycle"):
        f = Path(a.file) if a.file else КАТАЛОГ / м["backup_file"]
        r = восстановить(f)
        print("восстановление:", json.dumps(r, ensure_ascii=False, indent=2))
        sys.exit(0 if r["restore_verdict"] == "PASS" else 1)
