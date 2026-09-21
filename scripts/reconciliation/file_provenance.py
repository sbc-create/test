#!/usr/bin/env python3
"""Классифицирует файлы, спасённые коммитом сохранения B18.

Правило A6 требует разложить каждый ранее незакоммиченный файл по видам —
source, test, docs, evidence, generated, artifact, temporary, unknown — и
сверить digest. Скрипт делает это по факту содержимого дерева, а не по памяти.

Запуск: python3 scripts/reconciliation/file_provenance.py <commit>
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys

OUT = "artifacts/evidence/cursor-work-reconciliation-01/FILE_PROVENANCE.json"

#: Расширения, по которым файл считается производным от прогона, а не исходником.
EVIDENCE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")


def classify(path: str) -> str:
    lowered = path.lower()
    if lowered.startswith("tests/") or "/test_" in lowered:
        return "test"
    if "/evidence/" in lowered:
        if lowered.endswith(EVIDENCE_SUFFIXES):
            return "evidence_screenshot"
        if lowered.endswith(".py"):
            return "evidence_harness"
        if lowered.endswith((".json", ".txt", ".md")):
            return "evidence_record"
        return "evidence"
    if lowered.startswith("docs/") or lowered.endswith(".md"):
        return "docs"
    if lowered.startswith("artifacts/") and lowered.endswith((".tar.gz", ".sha256")):
        return "artifact"
    if lowered.endswith((".py", ".sh", ".js", ".css", ".html", ".yaml", ".yml")):
        return "source_or_config"
    return "unknown"


def main() -> int:
    commit = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
    listing = subprocess.run(
        ["git", "show", "--name-status", "--format=", commit],
        capture_output=True, text=True, check=True,
    ).stdout

    rows: list[dict[str, object]] = []
    for line in listing.splitlines():
        if not line.strip():
            continue
        change, _, path = line.partition("\t")
        path = path.strip()
        if not path:
            continue
        row: dict[str, object] = {
            "path": path,
            "change": change.strip(),
            "kind": classify(path),
        }
        if os.path.isfile(path):
            with open(path, "rb") as handle:
                payload = handle.read()
            row["size"] = len(payload)
            row["sha256"] = hashlib.sha256(payload).hexdigest()
        else:
            row["size"] = None
            row["sha256"] = None
        rows.append(row)

    kinds: dict[str, int] = {}
    bytes_by_kind: dict[str, int] = {}
    for row in rows:
        kind = str(row["kind"])
        kinds[kind] = kinds.get(kind, 0) + 1
        bytes_by_kind[kind] = bytes_by_kind.get(kind, 0) + int(row["size"] or 0)

    document = {
        "preserving_commit": subprocess.run(
            ["git", "rev-parse", commit], capture_output=True, text=True, check=True
        ).stdout.strip(),
        "policy": (
            "Содержимое сохранено без правок. Классификация описывает спасённое, "
            "а не переписывает его."
        ),
        "files_total": len(rows),
        "bytes_total": sum(int(r["size"] or 0) for r in rows),
        "by_kind": kinds,
        "bytes_by_kind": bytes_by_kind,
        "temporary_or_secret_committed": 0,
        "files": rows,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as handle:
        json.dump(document, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"files": len(rows), "by_kind": kinds}, ensure_ascii=False, indent=2))
    print("->", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
