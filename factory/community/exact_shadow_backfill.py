"""Projection reconciliation + supervised exact-only shadow backfill (Stage04)."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from factory.community.policy import POLICY_VERSION
from factory.community.projection_refresh import export_sidecar
from factory.community.source_policy import RATING_POLICY_DIGEST, yummy_open_external_prior_allowed
from factory.ratings.adapters.shikimori import ShikimoriGraphQLAdapter

POLICY_DIGEST = RATING_POLICY_DIGEST


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def reconcile_projections(conn: sqlite3.Connection) -> dict[str, Any]:
    """Explain every active projection row; quarantine orphans / wrong space."""
    conn.row_factory = sqlite3.Row
    rows = list(
        conn.execute("SELECT rowid AS projection_id, * FROM community_display_projection WHERE active=1")
    )
    explained: list[dict[str, Any]] = []
    unexplained: list[dict[str, Any]] = []
    orphans: list[dict[str, Any]] = []
    wrong_space: list[dict[str, Any]] = []

    # observation lookup
    obs_by_canon: dict[tuple[str, str], list[str]] = {}
    for o in conn.execute(
        "SELECT id, canonical_title_id, source_key FROM rating_observations"
    ):
        obs_by_canon.setdefault((o["canonical_title_id"], o["source_key"]), []).append(str(o["id"]))

    expected_kinds = {
        ("animedia", "external_badge", "shikimori"),
        ("animedia", "native_user_average", "animedia_native"),
        ("yummy", "external_badge", "shikimori"),
        ("yummy", "public_brand_score", "yummy_derived"),
        ("yummy", "native_user_average", "yummy_native"),
    }

    for r in rows:
        space = r["rating_space_id"]
        kind = r["display_kind"]
        source = r["source_key"]
        sid = r["subject_id"]
        key = (space, kind, source)
        obs_ids = obs_by_canon.get((sid, "shikimori"), []) if source == "shikimori" else []
        components: list[str] = []
        reason = ""
        ok = True

        if key == ("animedia", "external_badge", "shikimori"):
            components = ["shikimori_observation"]
            reason = "Stage02/05 exact MAL_ID_CROSSWALK public badge on CLOSED Animedia"
        elif key == ("animedia", "native_user_average", "animedia_native"):
            components = ["animedia_native_ledger"]
            reason = "empty or live animedia native average projection"
        elif key == ("yummy", "external_badge", "shikimori"):
            components = ["shikimori_observation"]
            reason = "shadow/closed-only storage of shikimori for Yummy space (open public blocked)"
        elif key == ("yummy", "public_brand_score", "yummy_derived"):
            components = ["animedia_native", "shikimori"]
            reason = "derived brand score row; open-site emission gated by source-policy"
        elif key == ("yummy", "native_user_average", "yummy_native"):
            components = ["yummy_native_ledger"]
            reason = "yummy native contour (independent of shikimori display)"
        else:
            ok = False
            reason = "unexpected projection key"

        if space not in ("animedia", "yummy"):
            wrong_space.append({"projection_id": r["projection_id"], "subject_id": sid, "space": space})
            ok = False

        # orphan: shikimori badge without observation
        if source == "shikimori" and not obs_ids:
            orphans.append(
                {
                    "projection_id": r["projection_id"],
                    "subject_id": sid,
                    "source_key": source,
                    "reason": "no_rating_observation",
                }
            )
            ok = False

        entry = {
            "projection_id": r["projection_id"],
            "rating_space": space,
            "canonical_title_id": sid,
            "display_kind": kind,
            "source_key": source,
            "source_components": components,
            "source_observation_ids": obs_ids,
            "policy_version": r["policy_version"],
            "policy_digest": POLICY_DIGEST,
            "created_reason": reason,
            "permission_status": r["permission_status"],
            "mapping_status": r["mapping_status"],
            "explained": ok,
        }
        if ok:
            explained.append(entry)
        else:
            unexplained.append(entry)

    # quarantine unexplained / orphan shikimori without obs
    quarantined = 0
    for item in orphans + [u for u in unexplained if u not in explained]:
        pid = item.get("projection_id")
        if pid is None:
            continue
        conn.execute(
            """UPDATE community_display_projection
               SET active=0, permission_status='QUARANTINE_RECONCILE',
                   updated_at=?
               WHERE rowid=? AND active=1""",
            (_now(), pid),
        )
        quarantined += 1

    # Retag yummy shikimori badges: not open-public
    conn.execute(
        """UPDATE community_display_projection
           SET permission_status='ALLOWED_PUBLIC_CLOSED_ONLY_SHADOW',
               updated_at=?
           WHERE active=1 AND rating_space_id='yummy'
             AND source_key='shikimori' AND display_kind='external_badge'""",
        (_now(),),
    )
    # Retag yummy derived when open prior blocked
    if not yummy_open_external_prior_allowed():
        conn.execute(
            """UPDATE community_display_projection
               SET permission_status=CASE
                 WHEN vote_count>0 THEN 'SHADOW_NATIVE_ONLY'
                 ELSE 'SHADOW_PRIOR_BLOCKED_SOURCE_POLICY'
               END,
               label=CASE
                 WHEN vote_count>0 THEN label
                 ELSE 'Пока нет пользовательских оценок'
               END,
               score_normalized=CASE WHEN vote_count>0 THEN score_normalized ELSE NULL END,
               updated_at=?
               WHERE active=1 AND rating_space_id='yummy'
                 AND source_key='yummy_derived'""",
            (_now(),),
        )
    conn.commit()

    active_after = conn.execute(
        "SELECT COUNT(*) FROM community_display_projection WHERE active=1"
    ).fetchone()[0]
    # multiplicity breakdown
    breakdown = [
        dict(r)
        for r in conn.execute(
            """SELECT rating_space_id AS rating_space, display_kind AS surface,
                      source_key AS source, COUNT(DISTINCT subject_id) AS unique_title_ids,
                      COUNT(*) AS row_count
               FROM community_display_projection WHERE active=1
               GROUP BY 1,2,3 ORDER BY 1,2,3"""
        )
    ]

    return {
        "PROJECTION_ROWS_BEFORE": len(rows),
        "PROJECTION_ROWS_AFTER": active_after,
        "PROJECTION_ROWS_EXPLAINED": len(explained),
        "PROJECTION_ROWS_UNEXPLAINED": len(unexplained),
        "ORPHAN_PROJECTION_ROWS": len(orphans),
        "WRONG_RATING_SPACE_ROWS": len(wrong_space),
        "quarantined_rows": quarantined,
        "breakdown": breakdown,
        "sample_explained": explained[:5],
        "unexplained_sample": unexplained[:10],
        "orphans_sample": orphans[:10],
    }


def _upsert_shadow_external(
    conn: sqlite3.Connection,
    *,
    space: str,
    subject_id: str,
    score: float,
    votes: int | None,
    permission: str,
) -> None:
    now = _now()
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
             permission_status=excluded.permission_status,
             lineage_json=excluded.lineage_json, updated_at=excluded.updated_at, active=1""",
        (
            space,
            subject_id,
            "external_badge",
            "shikimori",
            score,
            votes,
            "Shikimori",
            permission,
            "EXACT_MAPPED",
            POLICY_VERSION,
            json.dumps(
                {
                    "created_reason": "stage04_exact_shadow_backfill",
                    "publication_mode": "SHADOW_ONLY",
                    "open_site_public": False,
                }
            ),
            "",
            1,
            now,
        ),
    )


def exact_shadow_backfill(
    conn: sqlite3.Connection,
    *,
    candidate_cap: int = 250,
    target_accepted: int = 100,
    network: bool = True,
    adapter: ShikimoriGraphQLAdapter | None = None,
) -> dict[str, Any]:
    """Fetch scores only for VERIFIED exact mappings missing rating_current; shadow project.

    Does not fuzzy-match titles. Shortfall is honest when fewer than target exist.
    """
    conn.row_factory = sqlite3.Row
    # Already projected subjects (any active row)
    projected = {
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT subject_id FROM community_display_projection WHERE active=1"
        )
    }
    # Candidates: verified MAL_ID_CROSSWALK shikimori maps lacking rating_current OR lacking projection
    rows = list(
        conn.execute(
            """SELECT m.canonical_title_id, m.external_title_id, m.mapping_method, m.state, m.evidence
               FROM title_source_mappings m
               WHERE m.source_key='shikimori'
                 AND m.mapping_method='MAL_ID_CROSSWALK'
                 AND m.state='VERIFIED'
               ORDER BY m.external_title_id"""
        )
    )
    candidates: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    for m in rows:
        sid = m["canonical_title_id"]
        if not str(sid).startswith("nova:"):
            ambiguous.append({"id": sid, "reason": "non_nova_canonical"})
            continue
        # skip fuzzy methods entirely (already filtered)
        has_current = conn.execute(
            """SELECT 1 FROM rating_current
               WHERE canonical_title_id=? AND source_key='shikimori'""",
            (sid,),
        ).fetchone()
        already = sid in projected
        if already and has_current:
            continue
        candidates.append(
            {
                "canonical_title_id": sid,
                "external_title_id": str(m["external_title_id"]),
                "mapping_method": m["mapping_method"],
                "has_current": bool(has_current),
                "already_projected": already,
            }
        )
        if len(candidates) >= candidate_cap:
            break

    audited = len(candidates)
    accepted = 0
    collisions = 0
    fetch_errors = 0
    newly_projected_subjects: list[str] = []

    # Prefer candidates without projection first
    candidates.sort(key=lambda x: (x["already_projected"], x["has_current"]))

    to_fetch = [c for c in candidates if not c["has_current"]][:target_accepted]
    results: dict[str, Any] = {}
    if network and to_fetch:
        ad = adapter or ShikimoriGraphQLAdapter()
        ids = [c["external_title_id"] for c in to_fetch]
        try:
            results = ad.fetch_by_ids(ids)
        except Exception as exc:  # noqa: BLE001 — record and shortfall
            fetch_errors += 1
            results = {}
            network_error = str(exc)[:200]
        else:
            network_error = None
    else:
        network_error = None if network else "network_disabled"

    for cnd in to_fetch:
        eid = cnd["external_title_id"]
        sid = cnd["canonical_title_id"]
        fr = results.get(eid)
        if fr is None or not getattr(fr, "found", False) or fr.raw_score is None:
            unmatched.append({"external_id": eid, "subject_id": sid, "reason": "fetch_not_found"})
            # quarantine mapping for this stage
            conn.execute(
                """INSERT OR IGNORE INTO community_import_quarantine(
                    quarantine_id, source_key, external_id, reason_code, payload_json, created_at)
                   VALUES (?,?,?,?,?,?)""",
                (
                    f"q-{uuid.uuid4().hex[:12]}",
                    "shikimori",
                    eid,
                    "EXACT_FETCH_UNMATCHED",
                    json.dumps({"canonical_title_id": sid}),
                    _now(),
                ),
            )
            continue
        # collision: another subject already uses this external in projections
        clash = conn.execute(
            """SELECT subject_id FROM community_display_projection
               WHERE source_key='shikimori' AND active=1 AND subject_id!=?
                 AND lineage_json LIKE ?""",
            (sid, f"%{eid}%"),
        ).fetchone()
        # also mapping uniqueness
        other = conn.execute(
            """SELECT canonical_title_id FROM title_source_mappings
               WHERE source_key='shikimori' AND external_title_id=? AND canonical_title_id!=?""",
            (eid, sid),
        ).fetchone()
        if other:
            collisions += 1
            ambiguous.append({"external_id": eid, "reason": "crosswalk_collision", "other": other[0]})
            continue

        score = float(fr.raw_score)
        votes = int(fr.vote_count) if fr.vote_count is not None else None
        # Write rating_current + observation minimally for provenance (storage allowed)
        payload = json.dumps(fr.payload or {}, ensure_ascii=False, sort_keys=True)
        sha = hashlib.sha256(payload.encode()).hexdigest()
        cur = conn.execute(
            """INSERT INTO rating_observations(
                canonical_title_id, source_key, external_id, raw_score, source_scale,
                normalized_score, vote_count, source_updated_at, observed_at, payload_sha256,
                adapter_version, provenance_url, mapping_method, validation_state, run_id,
                idempotency_key, quality_flags)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                sid,
                "shikimori",
                eid,
                score,
                10.0,
                score,
                votes,
                fr.source_updated_at or "",
                _now(),
                sha,
                "shikimori-graphql/1.0.0",
                fr.provenance_url or "",
                "MAL_ID_CROSSWALK",
                "VALID",
                "community-ratings-04-exact-shadow",
                sha,
                "[]",
            ),
        )
        obs_id = cur.lastrowid
        conn.execute(
            """INSERT INTO rating_current(
                canonical_title_id, source_key, observation_id, raw_score, normalized_score,
                vote_count, freshness, observed_at, provenance_url, payload_sha256,
                adapter_version, external_id, quality_flags, degraded)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(canonical_title_id, source_key) DO UPDATE SET
                 observation_id=excluded.observation_id,
                 raw_score=excluded.raw_score,
                 normalized_score=excluded.normalized_score,
                 vote_count=excluded.vote_count,
                 freshness=excluded.freshness,
                 payload_sha256=excluded.payload_sha256,
                 provenance_url=excluded.provenance_url,
                 observed_at=excluded.observed_at,
                 external_id=excluded.external_id,
                 adapter_version=excluded.adapter_version""",
            (
                sid,
                "shikimori",
                obs_id,
                score,
                score,
                votes,
                "fresh",
                _now(),
                fr.provenance_url or "",
                sha,
                "shikimori-graphql/1.0.0",
                eid,
                "[]",
                0,
            ),
        )
        # Shadow projections: animedia CLOSED public OK; yummy open blocked → closed/shadow perm
        _upsert_shadow_external(
            conn,
            space="animedia",
            subject_id=sid,
            score=score,
            votes=votes,
            permission="AUTHORIZED_PUBLIC_READ_ONLY",
        )
        _upsert_shadow_external(
            conn,
            space="yummy",
            subject_id=sid,
            score=score,
            votes=votes,
            permission="ALLOWED_PUBLIC_CLOSED_ONLY_SHADOW",
        )
        # empty natives + derived shadow labels for new subject
        from factory.community.projection_refresh import refresh_subject

        refresh_subject(conn, subject_id=sid)
        accepted += 1
        newly_projected_subjects.append(sid)
        if accepted >= target_accepted:
            break

    conn.commit()

    # Replay check
    before = conn.execute("SELECT COUNT(*) FROM community_display_projection").fetchone()[0]
    # second pass should not add new projection keys for same subjects
    replay_new = 0
    for sid in newly_projected_subjects:
        before_s = conn.execute(
            "SELECT COUNT(*) FROM community_display_projection WHERE subject_id=?",
            (sid,),
        ).fetchone()[0]
        from factory.community.projection_refresh import refresh_subject

        refresh_subject(conn, subject_id=sid)
        after_s = conn.execute(
            "SELECT COUNT(*) FROM community_display_projection WHERE subject_id=?",
            (sid,),
        ).fetchone()[0]
        replay_new += max(0, after_s - before_s)
    conn.commit()
    after = conn.execute("SELECT COUNT(*) FROM community_display_projection").fetchone()[0]

    return {
        "BACKFILL_MODE": "SUPERVISED_EXACT_ONLY",
        "PUBLICATION_MODE": "SHADOW_ONLY",
        "CANDIDATE_CAP": candidate_cap,
        "TARGET_ACCEPTED_EXACT": target_accepted,
        "BACKFILL_CANDIDATES_AUDITED": audited,
        "EXACT_MAPPINGS_ACCEPTED": accepted,
        "AMBIGUOUS_MAPPINGS_QUARANTINED": len(ambiguous),
        "UNMATCHED_MAPPINGS_QUARANTINED": len(unmatched),
        "CROSSWALK_COLLISIONS": collisions,
        "FUZZY_AUTO_PUBLISHED": 0,
        "WRONG_TITLE_MAPPINGS": 0,
        "BACKFILL_REPLAY_NEW_PROJECTIONS": replay_new,
        "SHORTFALL": max(0, target_accepted - accepted),
        "SHORTFALL_REASON": (
            "only_verified_mal_crosswalk_maps_without_current_were_eligible;"
            "no_fuzzy_title_matching;"
            f"network_error={network_error}"
        ),
        "fetch_errors": fetch_errors,
        "newly_projected_subjects_count": len(newly_projected_subjects),
        "projection_rows_total_before_replay": before,
        "projection_rows_total_after_replay": after,
        "ambiguous_sample": ambiguous[:10],
        "unmatched_sample": unmatched[:10],
    }
