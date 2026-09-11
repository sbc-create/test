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


def событий(путь: str) -> int:
    c = sqlite3.connect(f"file:{путь}?mode=ro", uri=True)
    n = c.execute("SELECT count(*) FROM ledger_event").fetchone()[0]
    c.close()
    return n


def main() -> int:
    до = событий(КАНОН)
    врем = Path(tempfile.mkdtemp(prefix="ledger-tests-"))
    копия = врем / "ephemeral.sqlite3"
    ист = sqlite3.connect(f"file:{КАНОН}?mode=ro", uri=True)
    наз = sqlite3.connect(копия)
    with наз:
        ист.backup(наз)
    наз.close(); ист.close()

    окр = dict(os.environ, AUDIT_LEDGER_DB=str(копия),
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
            ["/home/claude/work-test/.venv/bin/python", "-m", "pytest",
             "tests/audit/", "-q"] + sys.argv[1:],
            cwd=str(КОРЕНЬ), env=окр)
        код = p.returncode
    finally:
        сервер.terminate()
        сервер.wait(timeout=30)
    после = событий(КАНОН)
    print(f"\n  канонический журнал: было {до}, стало {после}")
    if до != после:
        print("  ИЗОЛЯЦИЯ НАРУШЕНА: тесты записали в канонический журнал")
        return 1
    print(f"  эфемерная копия: {событий(str(копия))} событий, каталог {врем}")
    shutil.rmtree(врем, ignore_errors=True)
    return код


if __name__ == "__main__":
    sys.exit(main())
