"""Заморозка базы знаний: KNOWLEDGE_FREEZE.yaml с SHA-256 каждого файла."""
from __future__ import annotations

import hashlib
import time
from pathlib import Path

import yaml

from factory.paths import PATHS

FREEZE_FILE = "KNOWLEDGE_FREEZE.yaml"
TRACKED_SUFFIXES = (".md", ".yaml", ".yml", ".json")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def tracked_files() -> list[Path]:
    root = PATHS.knowledge
    files = [
        p for p in sorted(root.rglob("*"))
        if p.is_file() and p.suffix in TRACKED_SUFFIXES and p.name != FREEZE_FILE
    ]
    return files


def build_freeze(version: str) -> dict:
    files = tracked_files()
    entries = [
        {"path": str(p.relative_to(PATHS.root)), "sha256": sha256_file(p), "bytes": p.stat().st_size}
        for p in files
    ]
    digest = hashlib.sha256("\n".join(f"{e['path']}:{e['sha256']}" for e in entries).encode()).hexdigest()
    return {
        "schema_version": 1,
        "freeze_version": version,
        "frozen_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "file_count": len(entries),
        "aggregate_sha256": digest,
        "files": entries,
    }


def freeze(version: str) -> dict:
    data = build_freeze(version)
    path = PATHS.knowledge / FREEZE_FILE
    path.write_text(
        "# Сгенерировано `python3 -m factory knowledge freeze`. Вручную не редактируется.\n"
        + yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return data


def load_freeze() -> dict | None:
    path = PATHS.knowledge / FREEZE_FILE
    if not path.exists():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8")) or None


def verify() -> tuple[bool, list[str]]:
    """Возвращает (ok, список расхождений)."""
    data = load_freeze()
    if not data:
        return False, [f"{FREEZE_FILE} отсутствует: база знаний не заморожена."]
    problems: list[str] = []
    recorded = {e["path"]: e["sha256"] for e in data.get("files", [])}
    actual = {str(p.relative_to(PATHS.root)): sha256_file(p) for p in tracked_files()}
    for path, sha in recorded.items():
        if path not in actual:
            problems.append(f"удалён после заморозки: {path}")
        elif actual[path] != sha:
            problems.append(f"изменён после заморозки: {path}")
    for path in actual:
        if path not in recorded:
            problems.append(f"добавлен после заморозки: {path}")
    return (not problems), problems


def freeze_version() -> str | None:
    data = load_freeze()
    return data.get("freeze_version") if data else None
