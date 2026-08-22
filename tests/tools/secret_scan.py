#!/usr/bin/env python3
"""Поиск секретов в том, что попадает в git и в артефакты.

Проверяются не «подозрительные слова», а фактические значения секретов стенда:
если пароль базы или ключ подписи оказался в отслеживаемом файле, это находка
независимо от того, как называется переменная.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def secret_values() -> dict[str, str]:
    values: dict[str, str] = {}
    for path, label in ((ROOT / "var/db/anime.password", "пароль базы"),
                        (ROOT / "var/secrets/payload_secret", "ключ подписи приложения")):
        if path.exists():
            value = path.read_text(encoding="utf-8").strip()
            if len(value) >= 8:
                values[value] = label
    return values

def tracked_files() -> list[Path]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True)
    return [ROOT / name for name in out.stdout.splitlines()]

def main() -> int:
    values = secret_values()
    if not values:
        print("SKIPPED: секретов стенда нет на диске, сравнивать не с чем")
        return 2

    findings = []
    scanned = 0
    for path in tracked_files():
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        scanned += 1
        for value, label in values.items():
            if value in content:
                findings.append({"file": str(path.relative_to(ROOT)), "secret": label})

    # Артефакты доказательств уезжают в отчёт целиком, включая логи серверов и
    # скриншоты, поэтому сканируется и var/artifacts, а не только коммитируемое.
    scan_roots = [ROOT / "artifacts", ROOT / "var" / "artifacts"]
    for path in (item for root in scan_roots if root.exists() for item in root.rglob("*")):
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        scanned += 1
        for value, label in values.items():
            if value in content:
                findings.append({"file": str(path.relative_to(ROOT)), "secret": label})

    report = {"scanned_files": scanned, "secret_kinds": sorted(values.values()), "findings": findings}
    out_path = ROOT / "var" / "artifacts" / "secret-scan.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if findings:
        print(f"НАЙДЕНЫ СЕКРЕТЫ в {len(findings)} файлах:")
        for item in findings[:20]:
            print(f"  {item['file']}: {item['secret']}")
        return 1
    print(f"секретов в отслеживаемых файлах и артефактах не найдено; просмотрено {scanned} файлов")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
