#!/usr/bin/env python3
"""Прогон тестов по эфемерной копии журнала.

Канонический журнал неизменяем: написанное в него тестом остаётся там навсегда.
Поэтому тесты получают собственный экземпляр API поверх копии, а канонический
журнал по окончании обязан иметь ровно то же число событий, что и до прогона.
Это проверяется здесь же — обещание изоляции без проверки ничего не стоит.
"""
from __future__ import annotations
import os, shutil, sqlite3, subprocess, sys, tempfile, time, urllib.error, urllib.request
from pathlib import Path

КАНОН = "/srv/site-factory/audit-ledger/audit_ledger.sqlite3"
ВЫПУСК = "/srv/site-factory/control-api/current"
КОРЕНЬ = Path(__file__).resolve().parents[2]
ПОРТ = 8791
ТОКЕНЫ = {"AUDIT_TOKEN_ARCHITECT": "arch-local-token",
          "AUDIT_TOKEN_REGISTRY": "reg-local-token",
          "AUDIT_TOKEN_QWEN": "qwen-local-token",
          "AUDIT_TOKEN_TEMPLATES": "tpl-local-token"}


def снимок(путь: str) -> dict:
    c = sqlite3.connect(f"file:{путь}?mode=ro", uri=True)
    n = c.execute("SELECT count(*) FROM ledger_event").fetchone()[0]
    посл = c.execute("SELECT coalesce(max(ledger_seq),0) FROM ledger_event").fetchone()[0]
    корень = c.execute("SELECT event_hash FROM ledger_event "
                       "ORDER BY ledger_seq DESC LIMIT 1").fetchone()
    cp = c.execute("SELECT checkpoint_id FROM ledger_checkpoint "
                   "ORDER BY ledger_seq DESC LIMIT 1").fetchone()
    ids = {r[0] for r in c.execute("SELECT event_id FROM ledger_event")}
    c.close()
    return {"count": n, "last_seq": посл,
            "chain_root": корень[0] if корень else None,
            "checkpoint": cp[0] if cp else None, "ids": ids}


def событий(путь: str) -> int:
    return снимок(путь)["count"]


def main() -> int:
    до = снимок(КАНОН)
    врем = Path(tempfile.mkdtemp(prefix="ledger-tests-"))
    копия = врем / "ephemeral.sqlite3"
    ист = sqlite3.connect(f"file:{КАНОН}?mode=ro", uri=True)
    наз = sqlite3.connect(копия)
    with наз:
        ист.backup(наз)
    наз.close(); ист.close()

    # Эфемерный экземпляр поднимается ради журнала. Управляющая запись ему не
    # нужна, а протокол запуска требует под неё токены — брать их сюда значило
    # бы тащить в тестовый контур права, которых тест не использует.
    окр = dict(os.environ, SITE_ENGINE_CONTROL_WRITES="0",
               AUDIT_LEDGER_DB=str(копия),
               AUDIT_API_BASE=f"http://127.0.0.1:{ПОРТ}",
               AUDIT_FEED=str(врем / "feed.jsonl"),
               SITE_ENGINE_HTTP="1", SITE_ENGINE_ADMIN="1",
               SITE_ENGINE_API_ENABLED="1", **ТОКЕНЫ)
    выпуск = Path(ВЫПУСК).resolve()
    сервер = subprocess.Popen(
        [str(выпуск / ".venv/bin/python"), "-m", "factory.site_engine.api.server",
         "--root", "/srv/site-factory/repo", "--host", "127.0.0.1",
         "--port", str(ПОРТ)],
        cwd=выпуск, env=окр,
        stdout=(врем / "server.log").open("w"), stderr=subprocess.STDOUT)
    try:
        for _ in range(80):
            try:
                with urllib.request.urlopen(
                        f"http://127.0.0.1:{ПОРТ}/api/v1/audit/health", timeout=5):
                    break
            except (urllib.error.URLError, OSError):
                time.sleep(0.5)
        else:
            print("эфемерный экземпляр не поднялся:",
                  (врем / "server.log").read_text()[-2000:])
            return 1
        p = subprocess.run(
            [str(выпуск / ".venv/bin/python"), "-m", "pytest",
             "tests/audit/", "-q"] + sys.argv[1:],
            cwd=str(КОРЕНЬ), env=окр)
        код = p.returncode
    finally:
        сервер.terminate()
        сервер.wait(timeout=30)
    после = снимок(КАНОН)
    расхождения = {k: (до[k], после[k]) for k in
                   ("count", "last_seq", "chain_root", "checkpoint")
                   if до[k] != после[k]}
    добавленные = после["ids"] - до["ids"]
    print(f"\n  канонический журнал: было {до['count']}, стало {после['count']}")
    print(f"  последняя позиция: {до['last_seq']} -> {после['last_seq']}")
    print(f"  корень цепи неизменен: {до['chain_root'] == после['chain_root']}")
    print(f"  checkpoint неизменен: {до['checkpoint'] == после['checkpoint']}")
    print(f"  новых event_id: {len(добавленные)}")
    if расхождения or добавленные:
        print(f"  ИЗОЛЯЦИЯ НАРУШЕНА: {расхождения}, новые {sorted(добавленные)[:5]}")
        return 1
    print(f"  эфемерная копия: {событий(str(копия))} событий, каталог {врем}")
    shutil.rmtree(врем, ignore_errors=True)
    return код


if __name__ == "__main__":
    sys.exit(main())
