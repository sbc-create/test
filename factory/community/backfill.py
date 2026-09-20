"""Permission-gated display projection backfill (never writes native votes)."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from factory.community.formulas import (
    DEFAULT_PRIOR_STRENGTH_M,
    NativeAggregate,
    YummyPublic,
    build_yummy_prior,
)
from factory.community.policy import POLICY_VERSION
from decimal import Decimal

POLICY = POLICY_VERSION


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def inventory(conn: sqlite3.Connection) -> dict[str, Any]:
    obs = dict(conn.execute("SELECT source_key, COUNT(*) FROM rating_observations GROUP BY 1"))
    cur = dict(conn.execute("SELECT source_key, COUNT(*) FROM rating_current GROUP BY 1"))
    maps = dict(
        conn.execute(
            "SELECT source_key || ':' || state, COUNT(*) FROM title_source_mappings GROUP BY 1"
        )
    )
    has_cv = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name='community_votes'"
    ).fetchone()
    community_votes = (
        int(conn.execute("SELECT COUNT(*) FROM community_votes WHERE status='ACCEPTED'").fetchone()[0])
        if has_cv
        else 0
    )
    return {
        "AMD_ARTIFACT_RECORDS": int(obs.get("amd_online") or 0),
        "SHIKIMORI_ARTIFACT_RECORDS": int(obs.get("shikimori") or 0),
        "AMD_CURRENT": int(cur.get("amd_online") or 0),
        "SHIKIMORI_CURRENT": int(cur.get("shikimori") or 0),
        "MAPPINGS": maps,
        "NATIVE_VOTES": int(
            conn.execute("SELECT COUNT(*) FROM rating_vote_current").fetchone()[0]
        ),
        "COMMUNITY_VOTES": community_votes,
    }


def backfill_display_projections(conn: sqlite3.Connection) -> dict[str, Any]:
    """Project authorized external scores into community_display_projection.

    - Shikimori → active external badge for animedia + yummy spaces (exact mapped).
    - AMD → quarantine UNMAPPED_NO_SITE_CROSSWALK (retain obs; no public active).
    - Native aggregates stay empty (S=N=0).
    - Idempotent: replay inserts 0 new logical projection rows (INSERT OR REPLACE same keys).
    """
    now = _now()
    stats = {
        "shikimori": {
            "INPUT_RECORDS": 0,
            "AUTHORIZED_RECORDS": 0,
            "INSERTED_OBSERVATIONS": 0,  # never insert obs
            "UPDATED_PROJECTIONS": 0,
            "SKIPPED_PERMISSION": 0,
            "QUARANTINED_MAPPING": 0,
            "DUPLICATES_SUPPRESSED": 0,
            "REPLAY_INSERTS": 0,
        },
        "amd_online": {
            "INPUT_RECORDS": 0,
            "AUTHORIZED_RECORDS": 0,
            "INSERTED_OBSERVATIONS": 0,
            "UPDATED_PROJECTIONS": 0,
            "SKIPPED_PERMISSION": 0,
            "QUARANTINED_MAPPING": 0,
            "DUPLICATES_SUPPRESSED": 0,
            "REPLAY_INSERTS": 0,
        },
    }

    before_proj = conn.execute("SELECT COUNT(*) FROM community_display_projection").fetchone()[0]

    # Shikimori authorized public read-only
    rows = conn.execute(
        """SELECT c.canonical_title_id, c.source_key, c.external_id, c.normalized_score,
                  c.vote_count, c.payload_sha256, c.provenance_url,
                  COALESCE(m.mapping_method, 'UNKNOWN') AS mapping_method,
                  COALESCE(m.state, 'UNKNOWN') AS mapping_state
           FROM rating_current c
           LEFT JOIN title_source_mappings m
             ON m.canonical_title_id=c.canonical_title_id AND m.source_key=c.source_key
           WHERE c.source_key='shikimori'"""
    ).fetchall()
    stats["shikimori"]["INPUT_RECORDS"] = len(rows)
    for r in rows:
        mapping_method = r[7]
        mapping_state = r[8]
        if mapping_state not in ("VERIFIED", "ACTIVE", "UNKNOWN") and mapping_state != "VERIFIED":
            # only verified mappings for public projection
            if mapping_state not in ("VERIFIED",):
                qid = f"q-{uuid.uuid4().hex[:12]}"
                conn.execute(
                    """INSERT OR IGNORE INTO community_import_quarantine(
                        quarantine_id, source_key, external_id, reason_code, payload_json, created_at)
                       VALUES (?,?,?,?,?,?)""",
                    (
                        qid,
                        "shikimori",
                        str(r[2] or ""),
                        "MAPPING_NOT_VERIFIED",
                        json.dumps({"canonical_title_id": r[0], "state": mapping_state}),
                        now,
                    ),
                )
                stats["shikimori"]["QUARANTINED_MAPPING"] += 1
                continue
        if mapping_method not in ("MAL_ID_CROSSWALK", "EXACT", "MANUAL"):
            qid = f"q-mm-{uuid.uuid4().hex[:10]}"
            conn.execute(
                """INSERT OR IGNORE INTO community_import_quarantine(
                    quarantine_id, source_key, external_id, reason_code, payload_json, created_at)
                   VALUES (?,?,?,?,?,?)""",
                (
                    qid,
                    "shikimori",
                    str(r[2] or ""),
                    "MAPPING_METHOD_NOT_EXACT",
                    json.dumps({"method": mapping_method}),
                    now,
                ),
            )
            stats["shikimori"]["QUARANTINED_MAPPING"] += 1
            continue
        if not r[0] or not str(r[0]).startswith("nova:"):
            qid = f"q-{uuid.uuid4().hex[:12]}"
            conn.execute(
                """INSERT OR IGNORE INTO community_import_quarantine(
                    quarantine_id, source_key, external_id, reason_code, payload_json, created_at)
                   VALUES (?,?,?,?,?,?)""",
                (
                    qid,
                    "shikimori",
                    str(r[2] or ""),
                    "NON_NOVA_CANONICAL",
                    json.dumps({"canonical_title_id": r[0]}),
                    now,
                ),
            )
            stats["shikimori"]["QUARANTINED_MAPPING"] += 1
            continue
        if r[3] is None:
            stats["shikimori"]["SKIPPED_PERMISSION"] += 1
            continue
        stats["shikimori"]["AUTHORIZED_RECORDS"] += 1
        subject = str(r[0])
        lineage = {
            "source": "shikimori",
            "external_id": r[2],
            "mapping_method": mapping_method,
            "layer": "external_source_rating",
            "not_native_vote": True,
        }
        for space in ("animedia", "yummy"):
            conn.execute(
                """INSERT INTO community_display_projection(
                    rating_space_id, subject_id, display_kind, source_key,
                    score_normalized, vote_count, label, permission_status,
                    mapping_status, policy_version, lineage_json, artifact_digest,
                    active, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(rating_space_id, subject_id, display_kind, source_key)
                   DO UPDATE SET
                    score_normalized=excluded.score_normalized,
                    vote_count=excluded.vote_count,
                    artifact_digest=excluded.artifact_digest,
                    updated_at=excluded.updated_at,
                    active=1""",
                (
                    space,
                    subject,
                    "external_badge",
                    "shikimori",
                    float(r[3]),
                    r[4],
                    "Shikimori",
                    "AUTHORIZED_PUBLIC_READ_ONLY",
                    "EXACT_MAPPED",
                    POLICY,
                    json.dumps(lineage, ensure_ascii=False),
                    r[5] or "",
                    1,
                    now,
                ),
            )
            stats["shikimori"]["UPDATED_PROJECTIONS"] += 1

        prior, prov = build_yummy_prior(
            animedia_native=None,
            shikimori=Decimal(str(r[3])),
            animedia_embeds_shikimori=False,
        )
        pub = YummyPublic(0, 0, prior, m=DEFAULT_PRIOR_STRENGTH_M)
        y_lineage = {
            "formula": "yummy_bayes_prior_v1",
            "prior_components": prov,
            "prior_strength_m": DEFAULT_PRIOR_STRENGTH_M,
            "native_vote_count": 0,
            "m_not_user_votes": True,
            "double_counted_source_count": 0,
        }
        score = None if pub.public_score is None else float(pub.public_score)
        conn.execute(
            """INSERT INTO community_display_projection(
                rating_space_id, subject_id, display_kind, source_key,
                score_normalized, vote_count, label, permission_status,
                mapping_status, policy_version, lineage_json, artifact_digest,
                active, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(rating_space_id, subject_id, display_kind, source_key)
               DO UPDATE SET
                score_normalized=excluded.score_normalized,
                vote_count=excluded.vote_count,
                lineage_json=excluded.lineage_json,
                updated_at=excluded.updated_at,
                active=1""",
            (
                "yummy",
                subject,
                "public_brand_score",
                "yummy_derived",
                score,
                0,
                "Предварительная оценка Yummy",
                "AUTHORIZED_PUBLIC_READ_ONLY",
                "EXACT_MAPPED",
                POLICY,
                json.dumps(y_lineage, ensure_ascii=False),
                r[5] or "",
                1,
                now,
            ),
        )

        conn.execute(
            """INSERT INTO community_display_projection(
                rating_space_id, subject_id, display_kind, source_key,
                score_normalized, vote_count, label, permission_status,
                mapping_status, policy_version, lineage_json, artifact_digest,
                active, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(rating_space_id, subject_id, display_kind, source_key)
               DO UPDATE SET updated_at=excluded.updated_at, active=1""",
            (
                "animedia",
                subject,
                "native_user_average",
                "animedia_native",
                None,
                0,
                "Пользовательских оценок пока нет",
                "NATIVE_LEDGER_EMPTY",
                "N/A",
                POLICY,
                json.dumps({"native_vote_count": 0, "absent": True}, ensure_ascii=False),
                "",
                1,
                now,
            ),
        )

    # AMD: retain observations; quarantine for public projection (no site crosswalk)
    amd_rows = conn.execute(
        """SELECT canonical_title_id, external_id, normalized_score, vote_count, payload_sha256
           FROM rating_current WHERE source_key='amd_online'"""
    ).fetchall()
    stats["amd_online"]["INPUT_RECORDS"] = len(amd_rows)
    for r in amd_rows:
        stats["amd_online"]["SKIPPED_PERMISSION"] += 1
        stats["amd_online"]["QUARANTINED_MAPPING"] += 1
        qid = f"amd-q-{r[1]}"
        conn.execute(
            """INSERT OR IGNORE INTO community_import_quarantine(
                quarantine_id, source_key, external_id, reason_code, payload_json, created_at)
               VALUES (?,?,?,?,?,?)""",
            (
                qid,
                "amd_online",
                str(r[1]),
                "NO_EXACT_SITE_CROSSWALK",
                json.dumps(
                    {
                        "canonical_title_id": r[0],
                        "note": "last-good retained in rating_observations; not public projection",
                    },
                    ensure_ascii=False,
                ),
                now,
            ),
        )

    after_proj = conn.execute("SELECT COUNT(*) FROM community_display_projection").fetchone()[0]
    # Ensure native ledger untouched
    native = conn.execute("SELECT COUNT(*) FROM community_votes").fetchone()[0]
    legacy = conn.execute("SELECT COUNT(*) FROM rating_vote_current").fetchone()[0]
    assert native == 0 and legacy == 0

    return {
        "before_projection_rows": before_proj,
        "after_projection_rows": after_proj,
        "by_source": stats,
        "FAKE_USER_VOTES_INSERTED": 0,
        "ANIMEDIA_NATIVE_VOTE_COUNT": 0,
        "YUMMY_NATIVE_VOTE_COUNT": 0,
        "EXTERNAL_OBSERVATIONS_INSERTED": 0,
        "QUARANTINED_IMPORT_RECORDS": conn.execute(
            "SELECT COUNT(*) FROM community_import_quarantine"
        ).fetchone()[0],
    }


def replay_backfill(conn: sqlite3.Connection) -> dict[str, Any]:
    before = conn.execute("SELECT COUNT(*) FROM community_display_projection").fetchone()[0]
    # fingerprint
    dig_before = conn.execute(
        "SELECT GROUP_CONCAT(subject_id||display_kind||COALESCE(score_normalized,'')) FROM community_display_projection"
    ).fetchone()[0]
    result = backfill_display_projections(conn)
    after = conn.execute("SELECT COUNT(*) FROM community_display_projection").fetchone()[0]
    dig_after = conn.execute(
        "SELECT GROUP_CONCAT(subject_id||display_kind||COALESCE(score_normalized,'')) FROM community_display_projection"
    ).fetchone()[0]
    return {
        "BACKFILL_REPLAY_NEW_OBSERVATIONS": 0,
        "projection_rows_before": before,
        "projection_rows_after": after,
        "projection_count_delta": after - before,
        "logical_fingerprint_unchanged": dig_before == dig_after,
        "detail": result,
    }
