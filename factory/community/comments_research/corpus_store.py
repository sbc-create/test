"""DERIVED_ONLY corpus persistence (JSONL under var/; aggregates may go to artifacts)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator


@dataclass(frozen=True)
class CorpusPaths:
    root: Path
    derived_jsonl: Path
    checkpoint: Path
    summary_json: Path
    raw_quarantine_dir: Path  # never committed; only if policy ever allows raw


def default_paths(repo_root: Path, out_dir: Path | None = None) -> CorpusPaths:
    base = out_dir or (repo_root / "var" / "community_comments_research")
    base.mkdir(parents=True, exist_ok=True)
    raw = base / "raw_restricted"
    raw.mkdir(parents=True, exist_ok=True)
    return CorpusPaths(
        root=base,
        derived_jsonl=base / "derived_observations.jsonl",
        checkpoint=base / "checkpoint.json",
        summary_json=base / "CORPUS_SUMMARY.json",
        raw_quarantine_dir=raw,
    )


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    if not path.exists():
        return
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def load_checkpoint(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "page": 1,
            "accepted": 0,
            "attempted": 0,
            "http_counters": {},
            "title_counts": {},
            "digests": [],
            "stop_reason": None,
        }
    return json.loads(path.read_text(encoding="utf-8"))


def save_checkpoint(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_summary(path: Path, summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def assert_derived_only_row(row: dict[str, Any]) -> None:
    forbidden = ("body", "full_text", "raw_text", "comment_text", "username", "email", "ip")
    for key in forbidden:
        if key in row and row[key] not in (None, "", 0):
            raise ValueError(f"DERIVED_ONLY violation: field {key} present")
    mode = row.get("storage_mode")
    if mode not in {"DERIVED_ONLY", "SYNTHETIC_RESEARCH_FIXTURE"}:
        raise ValueError(f"unexpected storage_mode={mode}")
