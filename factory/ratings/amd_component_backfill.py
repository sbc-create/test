"""Backfill AMD component scores into an existing closed-canary DB (≤0.1 rps)."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from factory.ratings.adapters.amd_online import AmdOnlineAdapter
from factory.ratings.adapters.base import AdapterError
from factory.ratings.formula import FORMULA_VERSION
from factory.ratings.gateway import RatingGateway
from factory.ratings.rate_limit import RateLimiter
from factory.ratings.rotation import ROTATION_ALGORITHM_VERSION, sort_for_rotation
from factory.ratings.snapshot import atomic_publish_candidate, build_snapshot, validate_snapshot
from factory.ratings.store import RatingsStore


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--db", required=True)
    p.add_argument("--evidence", required=True)
    p.add_argument("--outcomes", required=True, help="AMD_CLOSED_CANARY_OUTCOMES.csv")
    args = p.parse_args(argv)

    evidence = Path(args.evidence)
    store = RatingsStore(Path(args.db))
    adapter = AmdOnlineAdapter(
        allow_live=True,
        max_live_requests=200,
        rate_limiter=RateLimiter(max_rps=0.1, max_per_minute=6),
    )

    rows = []
    with Path(args.outcomes).open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if not (row.get("canonical_title_id") and row.get("url")):
                continue
            accepted = (
                row.get("result") in ("ACCEPTED", "inserted")
                or row.get("inserted") in ("True", "true", "1")
                or bool(row.get("score"))
            )
            if accepted:
                rows.append(row)

    updated = 0
    failed = 0
    for row in rows:
        url = row["url"]
        cid = row["canonical_title_id"]
        try:
            result = adapter.fetch_detail_html(url)
        except AdapterError as exc:
            failed += 1
            print(json.dumps({"url": url, "error": exc.code}))
            break
        if not result.found:
            failed += 1
            continue
        payload = result.payload or {}
        comps = {
            "story": payload.get("story_score"),
            "characters": payload.get("characters_score"),
            "art": payload.get("art_score"),
            "voice": payload.get("voice_score"),
        }
        store.conn.execute(
            """UPDATE rating_current SET component_scores=?, quality_flags=?
               WHERE canonical_title_id=? AND source_key=?""",
            (
                json.dumps(comps, ensure_ascii=False),
                json.dumps(payload.get("quality_flags") or [], ensure_ascii=False),
                cid,
                "amd_online",
            ),
        )
        updated += 1
        if updated % 10 == 0:
            print(json.dumps({"progress": updated, "comps_sample": comps}), flush=True)

    body = build_snapshot(store, primary_source="amd_online")
    assert validate_snapshot(body) == []
    pubs = {}
    for domain in ("animedia.icu", "animedia.space"):
        out = evidence / "closed-noindex" / domain / "ratings_snapshot_v1.candidate.json"
        pubs[domain] = atomic_publish_candidate(body, out)
        meta = {
            "domain": domain,
            "indexing": "noindex",
            "publication_mode": "CLOSED_NOINDEX_CANDIDATE",
            "public_indexed": False,
            "snapshot": pubs[domain],
            "robots_policy": "noindex, nofollow (closed nova)",
            "components_backfilled": True,
        }
        (evidence / "closed-noindex" / domain / "PUBLICATION.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    comb_rows = [dict(r) for r in store.conn.execute("SELECT * FROM rating_combined_projection")]
    ranked = sort_for_rotation(comb_rows)
    (evidence / "rotation_before_after.json").write_text(
        json.dumps(
            {
                "algorithm": ROTATION_ALGORITHM_VERSION,
                "formula": FORMULA_VERSION,
                "ranked_top20": ranked[:20],
                "count": len(ranked),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    sample_cid = rows[0]["canonical_title_id"] if rows else None
    if sample_cid:
        gw = RatingGateway.from_store(store, primary_source="amd_online")
        (evidence / "amd_gateway_sample.json").write_text(
            json.dumps(gw.contract(sample_cid), ensure_ascii=False, indent=2), encoding="utf-8"
        )

    report = {
        "backfill_updated": updated,
        "backfill_failed": failed,
        "auto_stopped": adapter.auto_stopped,
        "stop_reason": adapter.stop_reason,
        "adapter_stats": adapter.stats,
        "publications": pubs,
        "snapshot_digest": body.get("snapshot_sha256"),
    }
    (evidence / "AMD_COMPONENT_BACKFILL.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    store.close()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not adapter.auto_stopped else 2


if __name__ == "__main__":
    raise SystemExit(main())
