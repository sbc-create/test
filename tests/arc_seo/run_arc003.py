#!/usr/bin/env python3
"""Изолированный прогон FLEET-ARC-003 на кандидатском рантайме.

Поднимает отдельный экземпляр Control API, обслуживающий КАНДИДАТСКИЙ набор
контрактов 1.3.2 и собственные эфемерные хранилища. Канонические Registry,
ChangeSet Store и Audit Ledger в прогоне не участвуют; их отпечатки
снимаются до и после, и совпадение сверяется по точным множествам, а не по
счётчикам.
"""
from __future__ import annotations

import ctypes
import hashlib
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

КОРЕНЬ = Path(__file__).resolve().parents[2]
ВЫПУСК = Path(os.environ.get("ARC003_RELEASE",
                             "/srv/site-factory/control-api/current")).resolve()
КАНДИДАТ = КОРЕНЬ / "contracts/control-plane/1.3.2"
def свободный_порт() -> int:
    """Порт выбирает операционная система.

    Фиксированный номер однажды окажется занят предыдущим экземпляром,
    который ещё не закрыл сокет. Тогда прогон молча обратится к ЧУЖОМУ
    серверу и проверит не то, что поднял, — отказ при этом будет
    перемежающимся и необъяснимым.
    """
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


ПОРТ = int(os.environ["ARC003_PORT"]) if os.environ.get("ARC003_PORT") \
    else свободный_порт()
Ж = "/srv/site-factory/audit-ledger/audit_ledger.sqlite3"
Р = "/srv/site-factory/registry-core/registry.sqlite3"
C = "/srv/site-factory/changeset-store/changesets.sqlite3"
PR_SET_PDEATHSIG = 1


def _умереть_с_родителем() -> None:
    try:
        ctypes.CDLL("libc.so.6", use_errno=True).prctl(
            PR_SET_PDEATHSIG, signal.SIGKILL, 0, 0, 0)
    except OSError:
        pass


def снимок() -> dict:
    """Точный отпечаток канонических хранилищ, а не их размеры."""
    итог: dict = {}
    for имя, путь, таблица, ключ in (
            ("registry", Р, "site", "site_id"),
            ("audit", Ж, "ledger_event", "event_id"),
            ("changeset", C, "changeset", "changeset_id")):
        if not Path(путь).is_file():
            итог[имя] = {"count": 0, "ids": []}
            continue
        c = sqlite3.connect(f"file:{путь}?mode=ro", uri=True)
        try:
            ids = sorted(r[0] for r in c.execute(f"SELECT {ключ} FROM {таблица}"))
        finally:
            c.close()
        итог[имя] = {"count": len(ids),
                     "digest": hashlib.sha256(
                         json.dumps(ids).encode()).hexdigest()[:16]}
    c = sqlite3.connect(f"file:{Ж}?mode=ro", uri=True)
    try:
        h = c.execute("SELECT event_hash FROM ledger_event ORDER BY ledger_seq "
                      "DESC LIMIT 1").fetchone()
        итог["audit"]["chain_root"] = h[0][:16] if h else None
        итог["audit"]["business"] = c.execute(
            "SELECT count(*) FROM ledger_event WHERE event_type NOT LIKE 'test.%'"
        ).fetchone()[0]
    finally:
        c.close()
    return итог


def отпечаток_набора() -> str:
    суммы = json.loads((КАНДИДАТ / "checksums.json").read_text(encoding="utf-8"))
    return hashlib.sha256(
        json.dumps(суммы["files"], sort_keys=True).encode()).hexdigest()


def main() -> int:
    до = снимок()
    врем = Path(tempfile.mkdtemp(prefix="arc003-"))
    сумма = отпечаток_набора()

    окр = dict(
        os.environ,
        SITE_ENGINE_HTTP="1", SITE_ENGINE_API_ENABLED="1",
        SITE_ENGINE_CONTROL_WRITES="0",
        CONTROL_PLANE_BUNDLE_DIR=str(КАНДИДАТ),
        CANDIDATE_API_BASE=f"http://127.0.0.1:{ПОРТ}",
        CANDIDATE_BUNDLE_SHA256=сумма,
        CONTROL_API_BASE=f"http://127.0.0.1:{ПОРТ}",
        CHANGESET_DB=str(врем / "changesets.sqlite3"),
        AUDIT_LEDGER_DB=str(врем / "ledger.sqlite3"),
        AUDIT_FEED=str(врем / "feed.jsonl"),
        SEO_SURFACE_DB=str(врем / "seo-surface.sqlite3"),
        CHANGESET_APPROVAL_KEY="arc003-прогон-ключ-0123456789",
        APPROVAL_CALLER="control-plane",
        PYTHONPATH=str(ВЫПУСК),
    )

    сервер = subprocess.Popen(
        [str(ВЫПУСК / ".venv/bin/python"), "-m",
         "factory.site_engine.api.server", "--root", "/srv/site-factory/repo",
         "--host", "127.0.0.1", "--port", str(ПОРТ)],
        cwd=ВЫПУСК, env=окр, preexec_fn=_умереть_с_родителем,
        stdout=(врем / "server.log").open("w"), stderr=subprocess.STDOUT)
    код = 1
    try:
        for _ in range(80):
            try:
                with urllib.request.urlopen(
                        f"http://127.0.0.1:{ПОРТ}/api/v1/capabilities",
                        timeout=5) as о:
                    д = json.loads(о.read())
                    if д.get("bundle_version") == "1.3.2":
                        break
            except (urllib.error.HTTPError, urllib.error.URLError, OSError):
                pass
            if сервер.poll() is not None:
                # Экземпляр умер, не начав слушать: дальше ждать бессмысленно,
                # а ответ с этого порта пришёл бы уже не от него.
                print("кандидатский экземпляр завершился с кодом",
                      сервер.returncode)
                print((врем / "server.log").read_text()[-2000:])
                return 1
            time.sleep(0.5)
        else:
            print("кандидатский экземпляр не поднялся или отдаёт не тот набор:")
            print((врем / "server.log").read_text()[-2000:])
            return 1
        print(f"  кандидатский рантайм на {ПОРТ}, набор 1.3.2, "
              f"отпечаток {сумма[:16]}")
        p = subprocess.run(
            [str(ВЫПУСК / ".venv/bin/python"), "-m", "pytest", "tests/arc_seo/",
             "-q", "-p", "no:cacheprovider"] + sys.argv[1:],
            cwd=str(КОРЕНЬ), env=окр)
        код = p.returncode
    finally:
        сервер.terminate()
        try:
            сервер.wait(timeout=30)
        except subprocess.TimeoutExpired:
            сервер.kill()
            сервер.wait(timeout=10)

    после = снимок()
    расхождения = {k: [до[k], после[k]] for k in до if до[k] != после[k]}
    print(f"\n  канонические хранилища до:    {json.dumps(до, ensure_ascii=False)}")
    print(f"  канонические хранилища после: {json.dumps(после, ensure_ascii=False)}")
    if расхождения:
        print("  ИЗОЛЯЦИЯ НАРУШЕНА:", json.dumps(расхождения, ensure_ascii=False))
        return 1
    print("  изоляция подтверждена: канонические хранилища не изменились")
    shutil.rmtree(врем, ignore_errors=True)
    return код


if __name__ == "__main__":
    sys.exit(main())
