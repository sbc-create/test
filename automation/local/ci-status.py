#!/usr/bin/env python3
"""Состояние последнего прогона CI по каждому репозиторию сайта. Только чтение.

    python3 automation/local/ci-status.py [<проект> …]

Без аргументов — все не-Yummy репозитории: витринами Yummy распоряжается другое
окно, и их прогоны здесь не трогаются даже чтением списка, чтобы отчёт не
выглядел работой по ним.

Печатает: репозиторий, ветку, голову, состояние прогона на ЭТОЙ голове. Строка
«прогона на голове нет» — это факт, а не ошибка: он мог ещё не начаться.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
РЕПОЗИТОРИИ = КОРЕНЬ / "var" / "site-repos"


def гит(репо: pathlib.Path, *арг: str) -> str:
    return (subprocess.run(["git", "-C", str(репо), *арг],
                           capture_output=True, text=True).stdout or "").strip()


def прогоны(удалённый: str, предел: int = 12) -> list[dict]:
    г = subprocess.run(
        ["gh", "run", "list", "--repo", удалённый, "--limit", str(предел),
         "--json", "headSha,status,conclusion,displayTitle,databaseId,headBranch"],
        capture_output=True, text=True, timeout=180)
    try:
        return json.loads(г.stdout or "[]")
    except ValueError:
        return []


def главная(argv: list[str]) -> int:
    выбор = argv[1:]
    цели = [п for п in sorted(РЕПОЗИТОРИИ.iterdir())
            if (п / ".git").is_dir() and not п.name.startswith("yummy")
            and (not выбор or п.name in выбор)]
    print(f"{'репозиторий':24} {'голова':14} {'состояние':12} {'итог':9} прогон")
    зелёных = 0
    for репо in цели:
        ветка = гит(репо, "rev-parse", "--abbrev-ref", "HEAD")
        голова = гит(репо, "rev-parse", "HEAD")
        адрес = гит(репо, "remote", "get-url", "origin")
        удалённый = adres = адрес.replace("https://github.com/", "").removesuffix(".git")
        найден = None
        for п_ in прогоны(удалённый):
            if п_.get("headSha") == голова and п_.get("headBranch") == ветка:
                найден = п_
                break
        if найден is None:
            print(f"{репо.name:24} {голова[:12]:14} {'прогона на голове нет':22}")
            continue
        состояние = найден.get("status") or ""
        итог = найден.get("conclusion") or ""
        зелёных += int(итог == "success")
        print(f"{репо.name:24} {голова[:12]:14} {состояние:12} {итог:9} "
              f"{найден.get('databaseId')}")
    print(f"\nрепозиториев {len(цели)}, зелёных прогонов на голове {зелёных}")
    return 0


if __name__ == "__main__":
    raise SystemExit(главная(sys.argv))
