"""Refresh community_display_projection after native vote mutations."""

from __future__ import annotations

import json
import sqlite3
from decimal import Decimal
from pathlib import Path
from typing import Any

from factory.community.formulas import (
    DEFAULT_PRIOR_STRENGTH_M,
    NativeAggregate,
    YummyPublic,
    build_yummy_prior,
)
from factory.community.policy import POLICY_VERSION
from factory.ratings.models import utc_now_iso


def _canon(subject_id: str) -> str:
    return subject_id if subject_id.startswith("nova:") else f"nova:{subject_id}"


def _agg(conn: sqlite3.Connection, space: str, subject_id: str) -> NativeAggregate:
    canon = _canon(subject_id)
    for sid in (canon, subject_id, canon.replace("nova:", "")):
        row = conn.execute(
            """SELECT vote_sum, vote_count FROM community_aggregates
               WHERE rating_space_id=? AND subject_id=? AND dimension='overall'""",
            (space, sid),
        ).fetchone()
        if row:
            return NativeAggregate(int(row[0]), int(row[1]))
    return NativeAggregate(0, 0)


def refresh_subject(conn: sqlite3.Connection, *, subject_id: str) -> dict[str, Any]:
    now = utc_now_iso()
    canon = _canon(subject_id)
    a = _agg(conn, "animedia", subject_id)
    animedia_label = (
        "Пользовательских оценок пока нет" if a.vote_count == 0 else "Оценка Animedia"
    )
    conn.execute(
        """INSERT INTO community_display_projection(
            rating_space_id, subject_id, display_kind, source_key,
            score_normalized, vote_count, label, permission_status,
            mapping_status, policy_version, lineage_json, artifact_digest,
            active, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(rating_space_id, subject_id, display_kind, source_key)
           DO UPDATE SET score_normalized=excluded.score_normalized,
             vote_count=excluded.vote_count, label=excluded.label,
             lineage_json=excluded.lineage_json, updated_at=excluded.updated_at, active=1""",
        (
            "animedia",
            canon,
            "native_user_average",
            "animedia_native",
            None if a.average is None else float(a.average),
            a.vote_count,
            animedia_label,
            "NATIVE_LEDGER",
            "N/A",
            POLICY_VERSION,
            json.dumps(
                {
                    "native_vote_count": a.vote_count,
                    "vote_sum": a.vote_sum,
                    "absent": a.vote_count == 0,
                }
            ),
            "",
            1,
            now,
        ),
    )

    shiki = conn.execute(
        """SELECT score_normalized FROM community_display_projection
           WHERE rating_space_id='yummy' AND subject_id=? AND source_key='shikimori'
             AND display_kind='external_badge' AND active=1""",
        (canon,),
    ).fetchone()
    shiki_score = Decimal(str(shiki[0])) if shiki and shiki[0] is not None else None
    prior, prov = build_yummy_prior(
        animedia_native=a.average,
        shikimori=shiki_score,
        animedia_embeds_shikimori=False,
    )
    y = _agg(conn, "yummy", subject_id)
    pub = YummyPublic(y.vote_sum, y.vote_count, prior, m=DEFAULT_PRIOR_STRENGTH_M)
    label = "Оценка Yummy" if y.vote_count > 0 else "Предварительная оценка Yummy"
    conn.execute(
        """INSERT INTO community_display_projection(
            rating_space_id, subject_id, display_kind, source_key,
            score_normalized, vote_count, label, permission_status,
            mapping_status, policy_version, lineage_json, artifact_digest,
            active, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(rating_space_id, subject_id, display_kind, source_key)
           DO UPDATE SET score_normalized=excluded.score_normalized,
             vote_count=excluded.vote_count, label=excluded.label,
             lineage_json=excluded.lineage_json, updated_at=excluded.updated_at, active=1""",
        (
            "yummy",
            canon,
            "public_brand_score",
            "yummy_derived",
            None if pub.public_score is None else float(pub.public_score),
            y.vote_count,
            label,
            "AUTHORIZED_PUBLIC_READ_ONLY",
            "EXACT_MAPPED",
            POLICY_VERSION,
            json.dumps(
                {
                    "prior": None if prior is None else str(prior),
                    "prior_components": prov,
                    "prior_strength_m": DEFAULT_PRIOR_STRENGTH_M,
                    "native_vote_count": y.vote_count,
                    "m_not_user_votes": True,
                    "double_counted_source_count": 0,
                }
            ),
            "",
            1,
            now,
        ),
    )
    return {
        "animedia": {
            "S": a.vote_sum,
            "N": a.vote_count,
            "A": None if a.average is None else str(a.average),
        },
        "yummy": {
            "S": y.vote_sum,
            "N": y.vote_count,
            "Y": None if pub.public_score is None else str(pub.public_score),
            "P": None if prior is None else str(prior),
        },
    }


def export_sidecar(conn: sqlite3.Connection, path: Path) -> str:
    conn.row_factory = sqlite3.Row
    proj: dict[str, Any] = {}
    for r in conn.execute("SELECT * FROM community_display_projection WHERE active=1"):
        sid = r["subject_id"]
        space = r["rating_space_id"]
        entry = proj.setdefault(sid, {})
        space_e = entry.setdefault(space, {"external": [], "native": None, "brand": None})
        kind = r["display_kind"]
        if kind == "external_badge":
            space_e["external"].append(
                {
                    "source": r["source_key"],
                    "label": r["label"],
                    "score": r["score_normalized"],
                    "votes": r["vote_count"],
                }
            )
        elif kind == "native_user_average":
            space_e["native"] = {
                "label": r["label"],
                "score": r["score_normalized"],
                "votes": r["vote_count"],
            }
        elif kind == "public_brand_score":
            space_e["brand"] = {
                "label": r["label"],
                "score": r["score_normalized"],
                "votes": r["vote_count"],
            }
    out: dict[str, Any] = {}
    for sid, val in proj.items():
        out[sid] = val
        if sid.startswith("nova:"):
            out[sid[5:]] = val
    payload = {
        "version": "community-ratings-03",
        "policy": POLICY_VERSION,
        "policy_digest": "a2daf212d92ea40dc3de658806fb6f5f5cf7ae77890ff0c25f81bd89088c17d5",
        "writes_enabled": False,
        "titles": out,
    }
    text = json.dumps(payload, ensure_ascii=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return text
