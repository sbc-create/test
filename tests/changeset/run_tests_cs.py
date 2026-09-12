#!/usr/bin/env python3
"""Изолированный прогон проверок контура изменений.

Поднимает отдельный экземпляр Control API поверх КОПИЙ канонических баз и
собственного хранилища наборов, прогоняет обе серии проверок и сверяет
канонические Registry и Audit Ledger до и после. Совпадение счётчиков само по
себе ничего не доказывает, поэтому сверяется и точное множество записей.
"""
from __future__ import annotations

import ctypes
import json
import os
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ВЫПУСК = Path(os.environ.get("CHANGESET_RELEASE",
                             "/srv/site-factory/control-api/current")).resolve()
КОРЕНЬ = Path(__file__).resolve().parents[2]
ЖУРНАЛ = "/srv/site-factory/audit-ledger/audit_ledger.sqlite3"
РЕЕСТР = "/srv/site-factory/registry-core/registry.sqlite3"
ПОРТ = int(os.environ.get("CHANGESET_TEST_PORT", "8792"))
PR_SET_PDEATHSIG = 1


def _умереть_с_родителем() -> None:
    try:
        ctypes.CDLL("libc.so.6", use_errno=True).prctl(
            PR_SET_PDEATHSIG, signal.SIGKILL, 0, 0, 0)
    except OSError:
        pass


def снимок(путь: str, таблица: str, ключ: str) -> dict:
    c = sqlite3.connect(f"file:{путь}?mode=ro", uri=True)
    try:
        n = c.execute(f"SELECT count(*) FROM {таблица}").fetchone()[0]
        ids = {r[0] for r in c.execute(f"SELECT {ключ} FROM {таблица}")}
    finally:
        c.close()
    return {"count": n, "ids": ids}


def снимок_журнала() -> dict:
    c = sqlite3.connect(f"file:{ЖУРНАЛ}?mode=ro", uri=True)
    try:
        n, s = c.execute("SELECT count(*), coalesce(max(ledger_seq),0) "
                         "FROM ledger_event").fetchone()
        h = c.execute("SELECT event_hash FROM ledger_event ORDER BY ledger_seq "
                      "DESC LIMIT 1").fetchone()
        cp = c.execute("SELECT checkpoint_id FROM ledger_checkpoint "
                       "ORDER BY ledger_seq DESC LIMIT 1").fetchone()
        ids = {r[0] for r in c.execute("SELECT event_id FROM ledger_event")}
    finally:
        c.close()
    return {"count": n, "last_seq": s, "chain_root": h[0] if h else None,
            "checkpoint": cp[0] if cp else None, "ids": ids}


def кратко(с: dict) -> str:
    return (f"count={с['count']} last_seq={с.get('last_seq')} "
            f"root={(с.get('chain_root') or '')[:12]} cp={с.get('checkpoint')}")


def main() -> int:
    журнал_до = снимок_журнала()
    реестр_до = снимок(РЕЕСТР, "site", "site_id")
    врем = Path(tempfile.mkdtemp(prefix="changeset-tests-"))

    окр = dict(
        os.environ,
        SITE_ENGINE_HTTP="1", SITE_ENGINE_API_ENABLED="1",
        SITE_ENGINE_CONTROL_WRITES="0",
        CHANGESET_DB=str(врем / "changesets.sqlite3"),
        FAKE_ADAPTER_DB=str(врем / "fake.sqlite3"),
        CHANGESET_ENABLE_FAKE_ADAPTER="1",
        CHANGESET_APPROVAL_KEY="ключ-эфемерного-прогона-0123456789",
        CHANGESET_API_BASE=f"http://127.0.0.1:{ПОРТ}",
        CONTROL_API_BASE=f"http://127.0.0.1:{ПОРТ}",
        AUDIT_LEDGER_DB=str(врем / "ledger.sqlite3"),
        AUDIT_FEED=str(врем / "feed.jsonl"),
        PYTHONPATH=str(ВЫПУСК),
    )
    # Копия журнала: эфемерный экземпляр обязан писать в неё, а не в канон.
    ист = sqlite3.connect(f"file:{ЖУРНАЛ}?mode=ro", uri=True)
    наз = sqlite3.connect(врем / "ledger.sqlite3")
    with наз:
        ист.backup(наз)
    наз.close(); ист.close()

    сервер = subprocess.Popen(
        [str(ВЫПУСК / ".venv/bin/python"), "-m", "factory.site_engine.api.server",
         "--root", "/srv/site-factory/repo", "--host", "127.0.0.1",
         "--port", str(ПОРТ)],
        cwd=ВЫПУСК, env=окр, preexec_fn=_умереть_с_родителем,
        stdout=(врем / "server.log").open("w"), stderr=subprocess.STDOUT)
    код = 1
    try:
        for _ in range(80):
            try:
                with urllib.request.urlopen(
                        f"http://127.0.0.1:{ПОРТ}/api/v1/workflows", timeout=5):
                    break
            except (urllib.error.HTTPError, urllib.error.URLError, OSError):
                time.sleep(0.5)
        else:
            print("эфемерный экземпляр не поднялся:",
                  (врем / "server.log").read_text()[-2000:])
            return 1
        p = subprocess.run(
            [str(ВЫПУСК / ".venv/bin/python"), "-m", "pytest",
             "tests/changeset/", "-q", "-p", "no:cacheprovider"] + sys.argv[1:],
            cwd=str(КОРЕНЬ), env=окр)
        код = p.returncode
    finally:
        сервер.terminate()
        try:
            сервер.wait(timeout=30)
        except subprocess.TimeoutExpired:
            сервер.kill()
            сервер.wait(timeout=10)

    журнал_после = снимок_журнала()
    реестр_после = снимок(РЕЕСТР, "site", "site_id")
    расхождения = {}
    for имя, до, после in (("audit_ledger", журнал_до, журнал_после),
                           ("registry", реестр_до, реестр_после)):
        if до != после:
            расхождения[имя] = {
                "count": [до["count"], после["count"]],
                "new_ids": sorted(после["ids"] - до["ids"])[:5],
                "lost_ids": sorted(до["ids"] - после["ids"])[:5]}
    print(f"\n  канонический Audit Ledger до:    {кратко(журнал_до)}")
    print(f"  канонический Audit Ledger после: {кратко(журнал_после)}")
    print(f"  канонический Registry: {реестр_до['count']} -> "
          f"{реестр_после['count']}")
    print(f"  CANONICAL_TEST_EVENT_DELTA={журнал_после['count'] - журнал_до['count']}")
    if расхождения:
        print("  ИЗОЛЯЦИЯ НАРУШЕНА:", json.dumps(расхождения, ensure_ascii=False))
        код = код or 1
        return 1
    print(f"  изоляция подтверждена; временный каталог {врем}")
    shutil.rmtree(врем, ignore_errors=True)
    return код


if __name__ == "__main__":
    sys.exit(main())
