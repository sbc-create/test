"""Profile-aware artifact checks (BLOCK 08).

Ensures a tenant artifact cannot be silently reused for another site.
Full builders remain allowlisted handlers; this module verifies embeds.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class BuildGuardError(ValueError):
    pass


REQUIRED_EMBEDS = (
    "site_id",
    "domain",
    "profile",
    "design_id",
    "source_head",
    "artifact_sha256",
    "catalog_revision",
    "details_revision",
    "indexability",
)


def verify_artifact_embeds(meta_path: Path, expected: dict[str, Any]) -> None:
    data = json.loads(Path(meta_path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise BuildGuardError("artifact meta must be object")
    for key in REQUIRED_EMBEDS:
        if key not in data:
            raise BuildGuardError(f"missing embed: {key}")
        want = expected.get(key) or expected.get(f"expected_{key}") or expected.get(
            "template_profile" if key == "profile" else key
        )
        if want is not None and str(data[key]) != str(want):
            raise BuildGuardError(f"embed mismatch {key}: {data[key]!r} != {want!r}")


def assert_unique_digests(rows: list[dict[str, Any]]) -> None:
    seen: dict[str, str] = {}
    for row in rows:
        digest = row["artifact_sha256"]
        sid = row["site_id"]
        if digest in seen and seen[digest] != sid:
            raise BuildGuardError(
                f"cross-tenant artifact digest collision: {digest} ({seen[digest]} vs {sid})"
            )
        seen[digest] = sid
