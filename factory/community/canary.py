"""Supervised canary native-vote runner (Animedia then Yummy)."""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from factory.community.antifraud import AntifraudConfig, AntifraudGuard
from factory.community.projection_refresh import export_sidecar, refresh_subject
from factory.community.service import CommunityVotesService
from factory.community.store import CommunityStore
from factory.ratings.prod_db import resolve_canonical_db

CANARY_ACTOR_PREFIX = "canary-cr03-"
SIDECAR = Path("/srv/lords/.frontend/community-ratings-projection.json")
YUMMY_OVERLAY_SIDECAR = Path(
    "/srv/sites/yummyani-staging/runtime/overlays/yummyani.site/community-ratings-projection.json"
)


@dataclass
class CanaryPlan:
    space: str
    subject_id: str  # nova:UUID
    actor_id: str
    live_path: str


def pick_animedia_title() -> CanaryPlan:
    """Exact-mapped title with live route; no existing canary votes."""
    db = resolve_canonical_db()
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """SELECT subject_id FROM community_display_projection
           WHERE rating_space_id='animedia' AND source_key='shikimori' AND active=1
           ORDER BY subject_id LIMIT 1"""
    ).fetchone()
    conn.close()
    assert row, "no shikimori projection"
    subject = row["subject_id"]
    bare = subject.replace("nova:", "")
    # map to slug
    details = json.loads(Path("/srv/lords/.frontend/animedia-01-details.json").read_text())[
        "details"
    ]
    slug = None
    for s, v in details.items():
        if str(v.get("id")) == bare:
            slug = s
            break
    assert slug, f"no slug for {bare}"
    actor = f"{CANARY_ACTOR_PREFIX}animedia-{hashlib.sha256(b'animedia-cr03').hexdigest()[:12]}"
    return CanaryPlan(
        space="animedia",
        subject_id=subject,
        actor_id=actor,
        live_path=f"/title/{slug}/",
    )


def _open_store() -> CommunityStore:
    # Reuse production DB file with community schema already applied
    return CommunityStore(resolve_canonical_db())


def run_space_canary(plan: CanaryPlan, *, yummy_prior: dict[str, Any] | None = None) -> dict[str, Any]:
    store = _open_store()
    svc = CommunityVotesService(store)
    evidence: dict[str, Any] = {
        "plan": plan.__dict__,
        "steps": [],
        "cast_count": 0,
        "update_count": 0,
        "retract_count": 0,
        "concurrent_duplicate_votes": 0,
        "idempotency_replay_mutations": 0,
        "preview_equals_write": True,
        "formula_max_delta": 0.0,
        "votes_remaining": None,
    }
    prior_kw = {"yummy_prior_inputs": yummy_prior} if yummy_prior else {}

    def step(name: str, **payload: Any) -> None:
        evidence["steps"].append({"name": name, **payload})

    # 1 preview 7
    prev7 = svc.preview_one(
        rating_space_id=plan.space,
        subject_id=plan.subject_id,
        actor_id=plan.actor_id,
        score=7,
        **prior_kw,
    )
    step("preview_7", preview=prev7)

    # 2 concurrent cast same idempotency key
    idem = f"canary-cast-{plan.space}-{uuid.uuid4().hex}"
    results: list[dict[str, Any]] = []

    def cast_once() -> dict[str, Any]:
        return svc.put_vote(
            idempotency_key=idem,
            rating_space_id=plan.space,
            subject_id=plan.subject_id,
            actor_id=plan.actor_id,
            score=7,
            **prior_kw,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futs = [pool.submit(cast_once) for _ in range(2)]
        results = [f.result() for f in futs]
    # one vote row
    n_votes = store.conn.execute(
        """SELECT COUNT(*) FROM community_votes
           WHERE rating_space_id=? AND subject_id=? AND actor_id=? AND status='ACCEPTED'""",
        (plan.space, plan.subject_id, plan.actor_id),
    ).fetchone()[0]
    if n_votes != 1:
        evidence["concurrent_duplicate_votes"] = int(n_votes) - 1
    evidence["cast_count"] = 1
    cast_res = results[0]
    # preview equals write
    if prev7.get("after") != cast_res.get("after"):
        evidence["preview_equals_write"] = False
    step("cast_7_concurrent", results=results, active_votes=n_votes)
    refresh_subject(store.conn, subject_id=plan.subject_id)
    export_sidecar(store.conn, SIDECAR)
    if YUMMY_OVERLAY_SIDECAR.parent.is_dir():
        export_sidecar(store.conn, YUMMY_OVERLAY_SIDECAR)

    # 3 idempotency replay
    before_events = store.conn.execute(
        "SELECT COUNT(*) FROM community_vote_events WHERE actor_id=?", (plan.actor_id,)
    ).fetchone()[0]
    replay = svc.put_vote(
        idempotency_key=idem,
        rating_space_id=plan.space,
        subject_id=plan.subject_id,
        actor_id=plan.actor_id,
        score=7,
        **prior_kw,
    )
    after_events = store.conn.execute(
        "SELECT COUNT(*) FROM community_vote_events WHERE actor_id=?", (plan.actor_id,)
    ).fetchone()[0]
    if after_events != before_events:
        evidence["idempotency_replay_mutations"] += after_events - before_events
    step("idempotency_replay_cast", replay=replay, events_delta=after_events - before_events)

    # 4 preview update 9
    prev9 = svc.preview_one(
        rating_space_id=plan.space,
        subject_id=plan.subject_id,
        actor_id=plan.actor_id,
        score=9,
        **prior_kw,
    )
    step("preview_update_9", preview=prev9)
    upd = svc.put_vote(
        idempotency_key=f"canary-upd-{plan.space}-{uuid.uuid4().hex}",
        rating_space_id=plan.space,
        subject_id=plan.subject_id,
        actor_id=plan.actor_id,
        score=9,
        **prior_kw,
    )
    evidence["update_count"] = 1
    if prev9.get("after") != upd.get("after"):
        evidence["preview_equals_write"] = False
    # N still 1
    agg = store.get_aggregate(rating_space_id=plan.space, subject_id=plan.subject_id)
    step("update_9", result=upd, vote_count=agg["vote_count"])
    refresh_subject(store.conn, subject_id=plan.subject_id)
    export_sidecar(store.conn, SIDECAR)
    if YUMMY_OVERLAY_SIDECAR.parent.is_dir():
        export_sidecar(store.conn, YUMMY_OVERLAY_SIDECAR)

    # 5 retract
    ret = svc.delete_vote(
        idempotency_key=f"canary-del-{plan.space}-{uuid.uuid4().hex}",
        rating_space_id=plan.space,
        subject_id=plan.subject_id,
        actor_id=plan.actor_id,
        **prior_kw,
    )
    evidence["retract_count"] = 1
    step("retract", result=ret)
    # repeat retract noop
    ret2 = svc.delete_vote(
        idempotency_key=f"canary-del2-{plan.space}-{uuid.uuid4().hex}",
        rating_space_id=plan.space,
        subject_id=plan.subject_id,
        actor_id=plan.actor_id,
        **prior_kw,
    )
    step("retract_repeat", result=ret2)
    refresh_subject(store.conn, subject_id=plan.subject_id)
    export_sidecar(store.conn, SIDECAR)
    if YUMMY_OVERLAY_SIDECAR.parent.is_dir():
        export_sidecar(store.conn, YUMMY_OVERLAY_SIDECAR)

    remaining = store.conn.execute(
        """SELECT COUNT(*) FROM community_votes
           WHERE actor_id LIKE ? AND status='ACCEPTED'""",
        (f"{CANARY_ACTOR_PREFIX}%",),
    ).fetchone()[0]
    evidence["votes_remaining"] = remaining
    store.close()
    return evidence


def purge_canary_votes() -> dict[str, Any]:
    store = _open_store()
    actors = [
        r[0]
        for r in store.conn.execute(
            "SELECT DISTINCT actor_id FROM community_votes WHERE actor_id LIKE ?",
            (f"{CANARY_ACTOR_PREFIX}%",),
        )
    ]
    subjects = [
        r[0]
        for r in store.conn.execute(
            "SELECT DISTINCT subject_id FROM community_votes WHERE actor_id LIKE ?",
            (f"{CANARY_ACTOR_PREFIX}%",),
        )
    ]
    # Hard-delete canary vote rows (immutable audit events retained).
    deleted = store.conn.execute(
        "DELETE FROM community_votes WHERE actor_id LIKE ?",
        (f"{CANARY_ACTOR_PREFIX}%",),
    ).rowcount
    for space, sid in store.conn.execute(
        "SELECT DISTINCT rating_space_id, subject_id FROM community_aggregates"
    ):
        rebuilt = store.rebuild_aggregate_from_votes(rating_space_id=space, subject_id=sid)
        store.conn.execute(
            """UPDATE community_aggregates SET vote_sum=?, vote_count=?, aggregate_version=aggregate_version+1
               WHERE rating_space_id=? AND subject_id=?""",
            (rebuilt["vote_sum"], rebuilt["vote_count"], space, sid),
        )
        refresh_subject(store.conn, subject_id=sid)
    for sid in subjects:
        refresh_subject(store.conn, subject_id=sid)
    export_sidecar(store.conn, SIDECAR)
    if YUMMY_OVERLAY_SIDECAR.parent.is_dir():
        export_sidecar(store.conn, YUMMY_OVERLAY_SIDECAR)
    left = store.conn.execute(
        "SELECT COUNT(*) FROM community_votes WHERE actor_id LIKE ?",
        (f"{CANARY_ACTOR_PREFIX}%",),
    ).fetchone()[0]
    store.conn.commit()
    store.close()
    return {
        "purged_actors": actors,
        "subjects": subjects,
        "hard_deleted_rows": deleted,
        "votes_remaining": left,
        "accepted_remaining": left,
    }
