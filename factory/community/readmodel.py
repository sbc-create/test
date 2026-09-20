"""Centralized community ratings read-model for templates and admin."""

from __future__ import annotations

import json
import sqlite3
from decimal import Decimal
from pathlib import Path
from typing import Any

from factory.community.formulas import round_display
from factory.community.policy import POLICY_VERSION
from factory.ratings.prod_db import resolve_canonical_db


def _conn(db: Path | None = None) -> sqlite3.Connection:
    path = db or resolve_canonical_db()
    c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def flag(name: str, db: Path | None = None) -> int:
    try:
        c = _conn(db)
        row = c.execute(
            "SELECT value FROM community_feature_flags WHERE flag=?", (name,)
        ).fetchone()
        c.close()
        return int(row["value"]) if row else 0
    except sqlite3.Error:
        return 0


def subject_variants(subject_id: str) -> list[str]:
    s = subject_id.strip()
    out = [s]
    if s.startswith("nova:"):
        out.append(s[5:])
    else:
        out.append(f"nova:{s}")
    return out


def get_title_ratings(
    *,
    rating_space_id: str,
    subject_id: str,
    db: Path | None = None,
) -> dict[str, Any]:
    """Unified view-model: external badges + native + optional brand score."""
    c = _conn(db)
    variants = subject_variants(subject_id)
    placeholders = ",".join("?" * len(variants))
    rows = c.execute(
        f"""SELECT * FROM community_display_projection
            WHERE rating_space_id=? AND subject_id IN ({placeholders}) AND active=1""",
        (rating_space_id, *variants),
    ).fetchall()
    c.close()

    external: list[dict[str, Any]] = []
    native = {
        "label": "Оценка Animedia" if rating_space_id == "animedia" else "Оценка Yummy",
        "score": None,
        "vote_count": 0,
        "absent": True,
        "absent_label": "Пользовательских оценок пока нет",
    }
    brand = None
    for r in rows:
        kind = r["display_kind"]
        if kind == "external_badge":
            vc = r["vote_count"]
            external.append(
                {
                    "source": r["source_key"],
                    "label": r["label"],
                    "score": None
                    if r["score_normalized"] is None
                    else str(round_display(Decimal(str(r["score_normalized"])))),
                    "vote_count": vc,  # may be None — never coerce to 0 incorrectly; SQL int ok
                    "permission_status": r["permission_status"],
                    "mapping_status": r["mapping_status"],
                    "lineage": json.loads(r["lineage_json"] or "{}"),
                }
            )
        elif kind == "native_user_average":
            native = {
                "label": "Оценка Animedia"
                if rating_space_id == "animedia"
                else "Оценка Yummy (сырая)",
                "score": None
                if r["score_normalized"] is None
                else str(round_display(Decimal(str(r["score_normalized"])))),
                "vote_count": int(r["vote_count"] or 0),
                "absent": r["score_normalized"] is None or int(r["vote_count"] or 0) == 0,
                "absent_label": r["label"] or "Пользовательских оценок пока нет",
            }
        elif kind == "public_brand_score" and rating_space_id == "yummy":
            brand = {
                "label": r["label"] or "Предварительная оценка Yummy",
                "score": None
                if r["score_normalized"] is None
                else str(round_display(Decimal(str(r["score_normalized"])))),
                "vote_count": int(r["vote_count"] or 0),  # native only
                "tooltip": (
                    "Расчётная оценка: голоса пользователей Yummy и версионируемая база "
                    "Animedia/Shikimori. Число голосов — только реальные голоса Yummy."
                ),
                "lineage": json.loads(r["lineage_json"] or "{}"),
            }

    return {
        "rating_space_id": rating_space_id,
        "subject_id": subject_id,
        "policy_version": POLICY_VERSION,
        "external": external,
        "native": native,
        "public_brand": brand,
        "writes_enabled": False,
        "aggregate_rating_schema_org": False,
        "comments_enabled": False,
    }


def compact_card_badge(view: dict[str, Any]) -> dict[str, Any] | None:
    """One compact badge for cards: prefer brand/native score, else first external."""
    if view.get("public_brand") and view["public_brand"].get("score") is not None:
        return {
            "label": view["public_brand"]["label"],
            "score": view["public_brand"]["score"],
            "kind": "derived",
        }
    native = view.get("native") or {}
    if not native.get("absent") and native.get("score") is not None:
        return {"label": native["label"], "score": native["score"], "kind": "native"}
    if view.get("external"):
        e = view["external"][0]
        if e.get("score") is not None:
            return {"label": e["label"], "score": e["score"], "kind": "external"}
    return None


def admin_list(
    *,
    site: str | None = None,
    source: str | None = None,
    limit: int = 100,
    db: Path | None = None,
) -> list[dict[str, Any]]:
    c = _conn(db)
    q = "SELECT * FROM community_display_projection WHERE 1=1"
    args: list[Any] = []
    if site:
        q += " AND rating_space_id=?"
        args.append(site)
    if source:
        q += " AND source_key=?"
        args.append(source)
    q += " ORDER BY updated_at DESC LIMIT ?"
    args.append(limit)
    rows = [dict(r) for r in c.execute(q, args).fetchall()]
    c.close()
    return rows
