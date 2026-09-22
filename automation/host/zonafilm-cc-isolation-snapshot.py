#!/usr/bin/env python3
"""Снимок состояния соседей: доказательство, что их не тронули.

Изоляция — это утверждение о том, чего не произошло, и проверять его нужно
измерением, а не памятью. Инструмент снимает отпечаток каждого файла в путях
рантайма фабрики, а второй запуск сравнивает снимки и печатает ровно три
списка: добавлено, изменено, удалено.

Отпечаток. Файлы до `--hash-limit` байт (по умолчанию 4 МиБ) считаются
sha256 — это точное равенство. Файлы крупнее (каталоги витрин — десятки
мегабайт) описываются тройкой (размер, mtime_ns, владелец): пересчитывать
полгигабайта на каждом шаге приёмки значило бы не делать проверку вовсе.
Разница подхода отмечена в снимке полем `how`, чтобы «не изменился» большого
файла нельзя было прочитать как побайтовое равенство.

Ничего не меняет. Только читает.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

DEFAULT_ROOTS = (
    "/srv/lords/.frontend",
    "/etc/nginx/lords",
    "/etc/systemd/system",
)

SKIP_DIR_NAMES = {"__pycache__", ".git"}


def fingerprint(path: Path, hash_limit: int) -> dict:
    stat = path.lstat()
    entry = {
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "uid": stat.st_uid,
        "mode": oct(stat.st_mode),
    }
    if path.is_symlink():
        entry["how"] = "symlink"
        entry["target"] = os.readlink(path)
        return entry
    if stat.st_size <= hash_limit:
        try:
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1 << 20), b""):
                    digest.update(chunk)
            entry["how"] = "sha256"
            entry["sha256"] = digest.hexdigest()
        except OSError as exc:
            entry["how"] = "unreadable"
            entry["error"] = f"{type(exc).__name__}"
    else:
        entry["how"] = "stat"
    return entry


def walk(roots: list[str], hash_limit: int) -> dict:
    out: dict[str, dict] = {}
    for root in roots:
        base = Path(root)
        if not base.exists():
            continue
        for current, dirs, files in os.walk(base, followlinks=False):
            dirs[:] = [d for d in dirs if d not in SKIP_DIR_NAMES]
            for name in dirs + files:
                path = Path(current) / name
                if path.is_dir() and not path.is_symlink():
                    continue
                try:
                    out[str(path)] = fingerprint(path, hash_limit)
                except OSError:
                    out[str(path)] = {"how": "unreadable"}
    return out


def compare(before: dict, after: dict, allow_prefixes: list[str]) -> dict:
    def allowed(path: str) -> bool:
        return any(path.startswith(prefix) for prefix in allow_prefixes)

    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed = sorted(p for p in set(before) & set(after) if before[p] != after[p])

    report = {
        "added": added,
        "removed": removed,
        "changed": changed,
        "added_outside_tenant": [p for p in added if not allowed(p)],
        "removed_outside_tenant": [p for p in removed if not allowed(p)],
        "changed_outside_tenant": [p for p in changed if not allowed(p)],
    }
    report["cross_tenant_writes"] = (
        len(report["added_outside_tenant"])
        + len(report["removed_outside_tenant"])
        + len(report["changed_outside_tenant"])
    )
    report["changed_detail"] = {
        p: {"before": before[p], "after": after[p]}
        for p in report["changed_outside_tenant"][:50]
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, help="записать снимок сюда")
    parser.add_argument("--compare-to", type=Path, help="сравнить текущее состояние с этим снимком")
    parser.add_argument("--allow-prefix", action="append", default=[],
                        help="путь, запись в который разрешена этому контуру")
    parser.add_argument("--root", action="append", default=[])
    parser.add_argument("--hash-limit", type=int, default=4 << 20)
    args = parser.parse_args()

    roots = args.root or list(DEFAULT_ROOTS)
    current = walk(roots, args.hash_limit)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps({"roots": roots, "hash_limit": args.hash_limit, "files": current},
                       ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        print(f"снимок: {len(current)} путей → {args.out}")

    if args.compare_to:
        before = json.loads(args.compare_to.read_text(encoding="utf-8"))["files"]
        report = compare(before, current, args.allow_prefix)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1 if report["cross_tenant_writes"] else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
