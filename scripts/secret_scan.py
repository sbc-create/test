#!/usr/bin/env python3
"""Скан отслеживаемых файлов на секреты.

Проверяются файлы под контролем версий: именно они попадают в git, в сборку и в
чужие руки. Обход всего дерева заодно читал бы `.venv`, `artifacts` и `var` —
минуты работы и проверка того, что в репозиторий не входит.

Тестовые файлы обрабатываются отдельно и это не поблажка. Тесты редакции и
guard-правил обязаны содержать похожие на секреты строки: без них нечего
редактировать и нечего блокировать, а проверка, которой не на чем сработать,
ничего не доказывает. Поэтому находка в `tests/` — ожидаемая фикстура и
перечисляется отдельным списком, а находка где угодно ещё — отказ.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURE_PREFIXES = ("tests/",)
SKIP_SUFFIX = {".png", ".jpg", ".jpeg", ".ico", ".woff", ".woff2", ".gz", ".tgz", ".tar", ".pdf"}

PATTERNS = {
    "приватный ключ": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "AWS-ключ": re.compile(r"AKIA[0-9A-Z]{16}"),
    "токен GitHub": re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    "OAuth-токен Яндекса": re.compile(r"\by[0-3]_[A-Za-z0-9_-]{20,}"),
    "htpasswd-хеш": re.compile(r"\$apr1\$|\$2[aby]\$\d\d\$"),
    "публичная переменная Publisher ID": re.compile("NEXT_PUBLIC_[A-Z_]*CDNVIDEOHUB"),
    "присвоенный токен CDNVideoHub": re.compile(
        r"(CDNVIDEOHUB_API_TOKEN|CDNVIDEOHUB_PUBLISHER_ID)\s*=\s*['\"]?[A-Za-z0-9]"
    ),
    "учётные данные в URL": re.compile(r"https?://[^/\s:@]+:[^/\s@]+@"),
}


def tracked_files() -> list:
    listing = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, text=True, check=True
    )
    return [name for name in listing.stdout.split("\0") if name]


def scan() -> dict:
    findings, fixtures, scanned = [], [], 0
    for name in tracked_files():
        path = ROOT / name
        if path.suffix in SKIP_SUFFIX or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        scanned += 1
        for label, pattern in PATTERNS.items():
            for match in pattern.finditer(text):
                line = text[: match.start()].count("\n") + 1
                record = {"file": name, "line": line, "pattern": label}
                target = fixtures if name.startswith(FIXTURE_PREFIXES) else findings
                target.append(record)
    return {"scanned": scanned, "findings": findings, "fixtures": fixtures}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="машинночитаемый вывод")
    args = parser.parse_args()

    report = scan()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"просканировано отслеживаемых файлов: {report['scanned']}")
        print(f"ожидаемых фикстур в tests/: {len(report['fixtures'])}")
        if report["findings"]:
            print("НАХОДКИ вне tests/:")
            for item in report["findings"]:
                print(f"  {item['file']}:{item['line']}: {item['pattern']}")
        else:
            print("находок вне tests/ нет")
    return 1 if report["findings"] else 0


if __name__ == "__main__":
    sys.exit(main())
