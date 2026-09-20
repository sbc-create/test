"""Runtime overlay: merge community projection into vitrine detail ratings.

Loaded by lords-frontend.py. Flags + allowlist gate public merge.
Never enables native writes. Never emits AggregateRating.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
FLAGS_PATH = ROOT / "community-ratings-flags.json"
PROJ_PATH = ROOT / "community-ratings-projection.json"

_cache: dict[str, Any] = {"flags": None, "proj": None, "mtime": None}


def _load() -> tuple[dict[str, Any], dict[str, Any]]:
    flags = {"RATINGS_PUBLIC_READ_ANIMEDIA": 0, "RATINGS_PUBLIC_READ_YUMMY": 0, "allowlist": {}}
    if FLAGS_PATH.is_file():
        flags.update(json.loads(FLAGS_PATH.read_text(encoding="utf-8")))
    proj: dict[str, Any] = {}
    if PROJ_PATH.is_file():
        raw = json.loads(PROJ_PATH.read_text(encoding="utf-8"))
        proj = raw.get("titles") or {}
    return flags, proj


def merge_into_detail(detail: dict[str, Any], *, space: str = "animedia") -> dict[str, Any]:
    if not isinstance(detail, dict):
        return detail
    flags, proj = _load()
    flag_key = (
        "RATINGS_PUBLIC_READ_ANIMEDIA"
        if space == "animedia"
        else "RATINGS_PUBLIC_READ_YUMMY"
    )
    if not int(flags.get(flag_key) or 0):
        return detail
    subject = str(detail.get("id") or "").strip()
    if not subject:
        return detail
    allow = flags.get("allowlist") or {}
    allowed_ids = set(allow.get(space) or [])
    # allowlist may store nova: or bare
    variants = {subject, f"nova:{subject}", subject.replace("nova:", "")}
    if allowed_ids:
        ok = bool(variants & set(allowed_ids) | {a.replace("nova:", "") for a in allowed_ids} & variants)
        if not ok:
            # also allow full rollout when allowlist empty or "*" 
            if "*" not in allowed_ids:
                return detail
    entry = proj.get(subject) or proj.get(f"nova:{subject}") or proj.get(subject.replace("nova:", ""))
    if not entry:
        return detail
    space_data = entry.get(space) or {}
    out = dict(detail)
    rbs = dict(out.get("ratings_by_source") or {})
    for e in space_data.get("external") or []:
        if e.get("source") == "shikimori" and e.get("score") is not None:
            rbs["shikimori"] = {
                "value": e["score"],
                "scale": 10.0,
                "votes": e.get("votes"),
                "source": "shikimori",
                "community_projection": True,
                "not_native_vote": True,
            }
    out["ratings_by_source"] = rbs
    native = space_data.get("native")
    if native:
        out["community_native"] = native
    brand = space_data.get("brand")
    if brand and space == "yummy":
        out["community_brand"] = brand
    out["aggregate_rating_schema_org"] = False
    out["community_writes_enabled"] = False
    return out
