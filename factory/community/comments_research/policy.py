"""Load and query SOURCE_POLICY_V1.json."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

ALLOWED_COLLECT_CLASSES = frozenset(
    {
        "ALLOWED_API",
        "ALLOWED_PUBLIC_READ_DERIVED_ONLY",
        "ALLOWED_RAW_RESEARCH_RESTRICTED",
    }
)

BLOCKED_OR_REVIEW = frozenset({"BLOCKED", "REVIEW_REQUIRED"})


def policy_path(repo_root: Path) -> Path:
    return repo_root / "docs" / "community_comments" / "SOURCE_POLICY_V1.json"


@lru_cache(maxsize=4)
def load_policy(repo_root_str: str) -> dict[str, Any]:
    path = policy_path(Path(repo_root_str))
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "sources" not in data:
        raise ValueError(f"invalid source policy: {path}")
    return data


def sources_by_class(repo_root: Path, *classes: str) -> list[dict[str, Any]]:
    policy = load_policy(str(repo_root))
    wanted = set(classes)
    return [s for s in policy["sources"] if s.get("policy_class") in wanted]


def is_collectable(source: dict[str, Any]) -> bool:
    return (
        source.get("policy_class") in ALLOWED_COLLECT_CLASSES
        and bool(source.get("derived_analysis_allowed"))
        and not bool(source.get("raw_storage_allowed"))
    )


def assert_source_allowed_for_http(repo_root: Path, source_name: str) -> dict[str, Any]:
    policy = load_policy(str(repo_root))
    for src in policy["sources"]:
        if src.get("source_name") == source_name:
            if src.get("policy_class") in BLOCKED_OR_REVIEW and src.get(
                "policy_class"
            ) == "BLOCKED":
                raise PermissionError(f"BLOCKED source: {source_name}")
            if src.get("policy_class") == "BLOCKED":
                raise PermissionError(f"BLOCKED source: {source_name}")
            if not src.get("derived_analysis_allowed"):
                raise PermissionError(f"derived analysis not allowed: {source_name}")
            return src
    raise KeyError(f"unknown source: {source_name}")
