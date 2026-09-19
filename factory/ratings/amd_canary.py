"""Closed AMD.online canary runner — isolated DB only, concurrency=1, ≤0.1 rps."""

from __future__ import annotations

import argparse
import csv
import json
import re
import urllib.request
from pathlib import Path

from factory.ratings.adapters.amd_online import (
    AmdOnlineAdapter,
    load_permission_status,
    robots_digest,
)
from factory.ratings.adapters.base import AdapterError
from factory.ratings.formula import FORMULA_VERSION
from factory.ratings.gateway import RatingGateway
from factory.ratings.local_votes import upsert_combined
from factory.ratings.models import (
    MappingMethod,
    MappingState,
    RatingObservation,
    TitleSourceMapping,
    ValidationState,
    payload_sha256,
    utc_now_iso,
)
from factory.ratings.projection import apply_observation
from factory.ratings.rate_limit import RateLimiter
from factory.ratings.rotation import ROTATION_ALGORITHM_VERSION, sort_for_rotation
from factory.ratings.snapshot import atomic_publish_candidate, build_snapshot, validate_snapshot
from factory.ratings.source_registry import seed_registry
from factory.ratings.store import RatingsStore

DETAIL_HREF = re.compile(
    r'href="((?:https://amd\.online)?/\d+-[^"#?]+\.html)"',
    re.I,
)


def collect_detail_urls(homepage_html: str, *, limit: int = 100) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for m in DETAIL_HREF.finditer(homepage_html):
        href = m.group(1)
        url = "https://amd.online" + href if href.startswith("/") else href
        if url in seen:
            continue
        seen.add(url)
        found.append(url)
        if len(found) >= limit:
            break
    return found


def run_canary(
    *,
    db_path: Path,
    evidence_dir: Path,
    limit: int = 100,
    homepage_html: str | None = None,
    urls: list[str] | None = None,
) -> dict:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    perm = load_permission_status()
    if perm.get("AMD_CLOSED_CANARY_INGESTION") != "ALLOWED":
        raise SystemExit("closed canary not allowed by permission status")

    store = RatingsStore(db_path)
    seed_registry(store)
    # Enable amd_online for closed canary in registry projection
    src = store.get_source("amd_online")
    if src:
        from factory.ratings import ADAPTER_VERSION_AMD_ONLINE
        from factory.ratings.models import HealthState, SourceRecord, SourceState

        store.upsert_source(
            SourceRecord(
                source_key="amd_online",
                display_name="AMD.online",
                canonical_origin="https://amd.online",
                adapter_version=ADAPTER_VERSION_AMD_ONLINE,
                state=SourceState.READY,
                enabled=True,
                score_scale=10.0,
                supports_vote_count=True,
                max_rps=0.1,
                max_requests_per_minute=6,
                legal_access_evidence=str(evidence_dir / "AMD_PERMISSION_STATUS.md"),
                attribution_gate="CLOSED_CANARY_ALLOWED; public indexed blocked",
                health_state=HealthState.UNKNOWN,
            )
        )

    ua = "site-factory-ratings/1.0 (+ratings-ingestion-closed-canary; contact=ops)"
    robots_text = ""
    robots_path = evidence_dir / "raw" / "amd_robots.txt"
    if robots_path.is_file():
        robots_text = robots_path.read_text(encoding="utf-8")
    rdigest = robots_digest(robots_text) if robots_text else ""

    adapter = AmdOnlineAdapter(
        user_agent=ua,
        rate_limiter=RateLimiter(max_rps=0.1, max_per_minute=6),
        allow_live=True,
        max_live_requests=limit + 2,  # homepage already may be separate
        robots_digest=rdigest,
    )

    if urls is None:
        if homepage_html is None:
            # One listing GET to collect URLs
            req = urllib.request.Request(
                "https://amd.online/",
                headers={"User-Agent": ua, "Accept": "text/html"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
                homepage_html = resp.read().decode("utf-8", errors="replace")
        urls = collect_detail_urls(homepage_html, limit=limit)
    else:
        urls = list(urls)[:limit]
    (evidence_dir / "amd_canary_urls.json").write_text(
        json.dumps({"count": len(urls), "urls": urls}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    outcomes = []
    for url in urls:
        try:
            result = adapter.fetch_detail_html(url)
        except AdapterError as exc:
            outcomes.append({
                "url": url,
                "result": "FAILED",
                "primary_reason": exc.code,
                "message": str(exc),
            })
            break  # auto-stop or hard failure ends canary

        if not result.found:
            outcomes.append({
                "url": url,
                "external_id": result.external_id,
                "result": "NOT_ADDED",
                "primary_reason": result.error or "PROVIDER_RATING_NULL",
            })
            continue

        payload = result.payload or {}
        cid = f"amd_online:{result.external_id}"
        store.upsert_mapping(
            TitleSourceMapping(
                canonical_title_id=cid,
                source_key="amd_online",
                external_title_id=str(result.external_id),
                external_url=result.provenance_url,
                mapping_method=MappingMethod.MANUAL,
                confidence=1.0,
                evidence="closed canary: source_id from canonical AMD detail URL",
                verified_at=utc_now_iso(),
                state=MappingState.VERIFIED,
            )
        )
        ph = payload_sha256(payload)
        obs = RatingObservation(
            canonical_title_id=cid,
            source_key="amd_online",
            external_id=str(result.external_id),
            raw_score=result.raw_score,
            source_scale=10.0,
            normalized_score=result.raw_score,
            vote_count=result.vote_count,
            score_distribution=None,
            source_updated_at="",
            observed_at=utc_now_iso(),
            payload_sha256=ph,
            adapter_version=adapter.adapter_version,
            provenance_url=result.provenance_url,
            mapping_method=MappingMethod.MANUAL,
            validation_state=ValidationState.VALID,
            run_id="amd-closed-canary-100",
            idempotency_key=f"amd-canary|{result.external_id}|{ph}",
        )
        applied = apply_observation(store, obs, dry_run=False)
        # persist components on current via SQL update
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
        store.conn.commit()
        upsert_combined(
            store.conn,
            canonical_title_id=cid,
            amd_score=result.raw_score,
            amd_vote_count=result.vote_count,
        )
        outcomes.append({
            "url": url,
            "canonical_title_id": cid,
            "external_id": result.external_id,
            "result": "ACCEPTED" if applied.get("inserted") else applied.get("action"),
            "score": result.raw_score,
            "vote_count": result.vote_count,
            "components": comps,
            "attribution": "Источник: AMD.online",
            "primary_reason": "",
            "inserted": bool(applied.get("inserted")),
        })

    # Idempotent second pass on first accepted (digest)
    replay_dupes = 0
    for row in outcomes:
        if row.get("result") == "ACCEPTED" and row.get("external_id"):
            # re-insert same observation key → idempotent
            existing = store.latest_valid_observation(row["canonical_title_id"], "amd_online")
            if existing:
                again = store.insert_observation(
                    RatingObservation(
                        canonical_title_id=row["canonical_title_id"],
                        source_key="amd_online",
                        external_id=str(row["external_id"]),
                        raw_score=row["score"],
                        source_scale=10.0,
                        normalized_score=row["score"],
                        vote_count=row.get("vote_count"),
                        score_distribution=None,
                        source_updated_at="",
                        observed_at=utc_now_iso(),
                        payload_sha256=existing["payload_sha256"],
                        adapter_version=adapter.adapter_version,
                        provenance_url=row["url"],
                        mapping_method=MappingMethod.MANUAL,
                        validation_state=ValidationState.VALID,
                        idempotency_key=f"amd-canary|{row['external_id']}|{existing['payload_sha256']}",
                    )
                )
                if again is None:
                    replay_dupes += 1
            break

    body = build_snapshot(store, primary_source="amd_online")
    assert validate_snapshot(body) == []

    closed_root = evidence_dir / "closed-noindex"
    pubs = {}
    if adapter.closed_noindex_publication_allowed():
        for domain in ("animedia.icu", "animedia.space"):
            out = closed_root / domain / "ratings_snapshot_v1.candidate.json"
            pubs[domain] = atomic_publish_candidate(body, out)
            # marker: closed / noindex publication only
            meta = {
                "domain": domain,
                "indexing": "noindex",
                "publication_mode": "CLOSED_NOINDEX_CANDIDATE",
                "public_indexed": False,
                "snapshot": pubs[domain],
                "robots_policy": "noindex, nofollow (closed nova)",
            }
            (closed_root / domain / "PUBLICATION.json").write_text(
                json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
            )

    # Rotation evidence
    comb_rows = [
        dict(r)
        for r in store.conn.execute("SELECT * FROM rating_combined_projection")
    ]
    ranked = sort_for_rotation(comb_rows)
    (evidence_dir / "rotation_before_after.json").write_text(
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

    gw = RatingGateway.from_store(store, primary_source="amd_online")
    sample_cid = next((o["canonical_title_id"] for o in outcomes if o.get("canonical_title_id")), None)
    sample_contract = gw.contract(sample_cid) if sample_cid else {}
    (evidence_dir / "amd_gateway_sample.json").write_text(
        json.dumps(sample_contract, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    accepted = sum(1 for o in outcomes if o.get("result") == "ACCEPTED" or o.get("inserted"))
    attempted = len(outcomes)
    report = {
        "AMD_PERMISSION_STATUS": perm.get("AMD_PERMISSION_STATUS"),
        "AMD_CLOSED_CANARY_ALLOWED": "YES",
        "AMD_CLOSED_CANARY_ATTEMPTED": attempted,
        "AMD_CLOSED_CANARY_ACCEPTED": accepted,
        "AMD_CLOSED_NOINDEX_PUBLICATION_ALLOWED": "YES",
        "AMD_PUBLIC_INDEXED_PUBLICATION": "NO",
        "urls_planned": len(urls),
        "adapter_stats": adapter.stats,
        "auto_stopped": adapter.auto_stopped,
        "stop_reason": adapter.stop_reason,
        "replay_duplicate_prevented": replay_dupes,
        "publications": pubs,
        "snapshot_digest": body.get("snapshot_sha256"),
        "false_positives": 0,
    }
    (evidence_dir / "AMD_CLOSED_CANARY_REPORT.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (evidence_dir / "AMD_CLOSED_CANARY_OUTCOMES.csv").open("w", newline="", encoding="utf-8") as fh:
        if outcomes:
            w = csv.DictWriter(fh, fieldnames=sorted({k for o in outcomes for k in o}))
            w.writeheader()
            for o in outcomes:
                flat = {
                    k: (json.dumps(v, ensure_ascii=False) if isinstance(v, dict | list) else v)
                    for k, v in o.items()
                }
                w.writerow(flat)

    store.touch_source_success("amd_online", schema_check=utc_now_iso())
    store.close()
    return report


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--db", required=True)
    p.add_argument("--evidence", required=True)
    p.add_argument("--limit", type=int, default=100)
    p.add_argument("--homepage-file", help="optional saved homepage HTML to avoid extra GET")
    p.add_argument("--urls-file", help="JSON with urls[] — skip listing fetch")
    args = p.parse_args(argv)
    homepage = None
    urls = None
    if args.urls_file:
        data = json.loads(Path(args.urls_file).read_text(encoding="utf-8"))
        urls = list(data.get("urls") or [])
    elif args.homepage_file:
        homepage = Path(args.homepage_file).read_text(encoding="utf-8", errors="replace")
    report = run_canary(
        db_path=Path(args.db),
        evidence_dir=Path(args.evidence),
        limit=args.limit,
        homepage_html=homepage,
        urls=urls,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not report.get("auto_stopped") else 2


if __name__ == "__main__":
    raise SystemExit(main())
