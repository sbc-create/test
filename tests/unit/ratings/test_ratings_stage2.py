"""Stage 2 tests: AMD parser, local votes, formula, SLA, gateway contract."""

from __future__ import annotations

import threading
from decimal import Decimal
from pathlib import Path

import pytest

from factory.ratings.adapters.amd_online import AmdOnlineAdapter, _looks_like_challenge
from factory.ratings.adapters.amd_parser import AmdParseError, parse_detail_html
from factory.ratings.adapters.base import AdapterError, FetchResult
from factory.ratings.config import RatingsConfig
from factory.ratings.daily import (
    CoverageSnapshot,
    QwenDelivery,
    build_qwen_message,
    effective_daily_target,
    verify_reason_arithmetic,
    write_daily_report,
)
from factory.ratings.formula import combine_amd_local
from factory.ratings.gateway import RatingGateway
from factory.ratings.ingestion import IngestionEngine
from factory.ratings.local_votes import (
    ACTION_CREATE,
    ACTION_DELETE,
    ACTION_UPDATE,
    SCOPE_NETWORK,
    LocalVotesService,
    VoteConflict,
    VoteValidationError,
    upsert_combined,
)
from factory.ratings.mapping import resolve_mapping
from factory.ratings.models import (
    CatalogTitle,
    MappingMethod,
    MappingState,
    RatingObservation,
    TitleSourceMapping,
    ValidationState,
    utc_now_iso,
)
from factory.ratings.projection import apply_observation
from factory.ratings.rate_limit import RateLimiter
from factory.ratings.rotation import sort_for_rotation
from factory.ratings.source_registry import seed_registry
from factory.ratings.store import RatingsStore

ROOT = Path(__file__).resolve().parents[3]
AMD = ROOT / "tests" / "fixtures" / "ratings" / "amd"


@pytest.fixture
def store(tmp_path):
    s = RatingsStore(tmp_path / "r.sqlite")
    seed_registry(s)
    yield s
    s.close()


def _html(name: str) -> str:
    return (AMD / name).read_text(encoding="utf-8")


def test_amd_complete_fixture():
    d = parse_detail_html(
        _html("complete.html"),
        source_url="https://amd.online/5114-fullmetal.html",
    )
    assert d.score == Decimal("9.68")
    assert d.vote_count == 2031
    assert d.source_id == "5114"
    assert d.story_score == Decimal("9.7")
    assert d.voice_score == Decimal("9.6")
    # published score is NOT recomputed from components
    assert d.score != (d.story_score + d.characters_score + d.art_score + d.voice_score) / 4


def test_amd_missing_score():
    d = parse_detail_html(_html("missing_score.html"), source_url="https://amd.online/1001-x.html")
    assert d.score is None
    assert "SCORE_MISSING" in d.quality_flags


def test_amd_missing_vote_count():
    d = parse_detail_html(_html("missing_votes.html"), source_url="https://amd.online/1002-x.html")
    assert d.score == Decimal("8.50")
    assert d.vote_count is None
    assert "VOTE_COUNT_MISSING" in d.quality_flags


def test_amd_changed_markup():
    with pytest.raises(AmdParseError) as ei:
        parse_detail_html(_html("changed_markup.html"), source_url="https://amd.online/1001-x.html")
    assert ei.value.code == "MISSING_DATA_ID"


def test_amd_url_id_mismatch():
    with pytest.raises(AmdParseError) as ei:
        parse_detail_html(_html("id_mismatch.html"), source_url="https://amd.online/1001-x.html")
    assert ei.value.code == "ID_MISMATCH"


def test_amd_score_out_of_range():
    with pytest.raises(AmdParseError) as ei:
        parse_detail_html(_html("out_of_range.html"), source_url="https://amd.online/1003-x.html")
    assert ei.value.code == "OUT_OF_RANGE"


def test_amd_zero_score_becomes_null():
    html = """<!DOCTYPE html><html><body>
    <h1>Zero</h1><div class="amd-sub">Z</div>
    <div class="multirating" data-id="5723">
      <span class="multirating-itog-rateval">0.0</span>
      <span class="multirating-itog-votes">(0)</span>
      <div class="multirating-item" data-area="story"><span class="multirating-item-rateval-num">0</span></div>
      <div class="multirating-item" data-area="actors"><span class="multirating-item-rateval-num">0</span></div>
      <div class="multirating-item" data-area="graph"><span class="multirating-item-rateval-num">0</span></div>
      <div class="multirating-item" data-area="sound"><span class="multirating-item-rateval-num">0</span></div>
    </div></body></html>"""
    d = parse_detail_html(html, source_url="https://amd.online/5723-x.html")
    assert d.score is None
    assert d.vote_count == 0
    assert d.story_score is None
    assert "SCORE_ZERO_AS_NULL" in d.quality_flags


def test_amd_vote_count_decrease_quarantine(store):
    """Decrease is flagged — last-good preserved via projection rules."""
    obs1 = RatingObservation(
        canonical_title_id="nova:a", source_key="amd_online", external_id="1",
        raw_score=9.0, source_scale=10.0, normalized_score=9.0, vote_count=100,
        score_distribution=None, source_updated_at="", observed_at=utc_now_iso(),
        payload_sha256="a1", adapter_version="t", provenance_url="https://amd.online/1-x.html",
        mapping_method=MappingMethod.SHIKIMORI_ID, validation_state=ValidationState.VALID,
        idempotency_key="amd1",
    )
    apply_observation(store, obs1, dry_run=False)
    # anomalous decrease observation marked invalid → preserve
    obs2 = RatingObservation(
        canonical_title_id="nova:a", source_key="amd_online", external_id="1",
        raw_score=9.0, source_scale=10.0, normalized_score=9.0, vote_count=10,
        score_distribution=None, source_updated_at="", observed_at=utc_now_iso(),
        payload_sha256="a2", adapter_version="t", provenance_url="https://amd.online/1-x.html",
        mapping_method=MappingMethod.SHIKIMORI_ID, validation_state=ValidationState.INVALID,
        idempotency_key="amd2",
    )
    r = apply_observation(store, obs2, dry_run=False)
    assert r["action"] == "preserved_last_good"
    assert store.get_current("nova:a", "amd_online")[0]["vote_count"] == 100


def test_amd_403_auto_stop():
    import urllib.error

    class H:
        def get(self, *a, **k):
            return None

    def opener(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 403, "forbidden", H(), None)

    a = AmdOnlineAdapter(
        opener=opener,
        allow_live=True,
        max_live_requests=5,
        permission_root=Path("/nonexistent"),
        rate_limiter=RateLimiter(max_rps=100, max_per_minute=1000, sleeper=lambda s: None),
        sleeper=lambda s: None,
    )
    # Force permission granted via monkey attribute
    a.permission = {"AMD_PERMISSION_STATUS": "GRANTED", "AMD_SOURCE_STATE": "READY", "AMD_PRODUCTION_INGESTION": "0"}
    with pytest.raises(AdapterError) as ei:
        a.fetch_detail_html("https://amd.online/1-x.html")
    assert ei.value.code == "AUTO_STOPPED"
    assert a.stats["http_403"] == 1
    assert a.stats["auto_stop_triggered"] == 1


def test_amd_digest_idempotency():
    html = _html("complete.html")
    d1 = parse_detail_html(html, source_url="https://amd.online/5114-fullmetal.html")
    d2 = parse_detail_html(html, source_url="https://amd.online/5114-fullmetal.html")
    assert d1.content_digest_sha256 == d2.content_digest_sha256


def test_amd_challenge_ignores_dle_captcha_var():
    # DLE JS var alone is not a challenge
    assert not _looks_like_challenge("var dle_captcha_type = '0';\n" + "x" * 9000 + "multirating")
    assert _looks_like_challenge("<html>ddos-guard checking</html>")
    assert _looks_like_challenge('<div id="challenge-form"></div>')
    assert _looks_like_challenge("<html>Just a moment... cloudflare</html>")
    # tiny page with captcha widget, no multirating → challenge
    assert _looks_like_challenge('<html><div class="g-recaptcha"></div></html>')
    assert _looks_like_challenge('<html><div class="hcaptcha"></div></html>')
    assert _looks_like_challenge('<html><div class="captcha-box"></div></html>')
    # real detail-sized page with multirating must not trip on widget-like strings alone
    detailish = "multirating-itog-rateval" + ("x" * 9000)
    assert not _looks_like_challenge(detailish)


def test_amd_closed_canary_allowed_by_default():
    a = AmdOnlineAdapter(permission_root=Path("/nonexistent"))
    assert a.closed_canary_allowed()
    assert a.closed_noindex_publication_allowed()
    assert a.public_indexed_blocked()
    assert not a.permission_blocks_bulk()


def test_amd_permission_blocks_when_canary_disallowed():
    a = AmdOnlineAdapter(permission_root=Path("/nonexistent"), allow_live=False)
    a.permission = {
        **a.permission,
        "AMD_CLOSED_CANARY_INGESTION": "DENIED",
    }
    assert a.permission_blocks_bulk()
    with pytest.raises(AdapterError) as ei:
        a.fetch_detail_html("https://amd.online/1-x.html")
    assert ei.value.code == "SOURCE_POLICY_BLOCK"


def test_fuzzy_never_auto():
    t = CatalogTitle(canonical_title_id="n", title="Naruto Shippuuden", year=2007, kind="tv")
    d = resolve_mapping(t, source_key="amd_online", candidates=[{"external_id": "1", "name": "Naruto", "year": 2002, "kind": "tv"}])
    assert not d.auto_publish


def test_formula_examples():
    # 1
    r = combine_amd_local(amd_score="9.68", amd_vote_count=2031, accepted_local_vote_sum=0, accepted_local_vote_count=0)
    assert r.combined_ui == "9.68"
    assert r.baseline_weight == 100
    # 2
    r = combine_amd_local(amd_score="9.68", amd_vote_count=2031, accepted_local_vote_sum=8, accepted_local_vote_count=1)
    assert abs(float(r.combined_raw) - float(Decimal("976") / Decimal("101"))) < 1e-12
    assert r.combined_ui == "9.66"
    # 3 update 8→10
    r = combine_amd_local(amd_score="9.68", amd_vote_count=2031, accepted_local_vote_sum=10, accepted_local_vote_count=1)
    assert r.combined_ui == "9.68"
    # 4 delete
    r = combine_amd_local(amd_score="9.68", amd_vote_count=2031, accepted_local_vote_sum=0, accepted_local_vote_count=0)
    assert r.combined_ui == "9.68"
    # 5
    r = combine_amd_local(amd_score="9.68", amd_vote_count=2031, accepted_local_vote_sum=800, accepted_local_vote_count=100)
    assert r.combined_ui == "8.84"
    # 6 missing vote count
    r = combine_amd_local(amd_score="8.5", amd_vote_count=None, accepted_local_vote_sum=45, accepted_local_vote_count=5)
    assert r.baseline_weight == 25
    assert r.combined_ui == "8.58"
    assert "VOTE_COUNT_MISSING" in r.quality_flags
    # insufficient local without AMD
    r = combine_amd_local(amd_score=None, amd_vote_count=None, accepted_local_vote_sum=12, accepted_local_vote_count=3)
    assert r.combined_raw is None
    assert r.state == "INSUFFICIENT_LOCAL"


def test_local_vote_crud_and_idempotency(store):
    svc = LocalVotesService(store.conn)
    r1 = svc.apply(
        idempotency_key="k1", canonical_title_id="t1", voter_subject_id="u1",
        scope=SCOPE_NETWORK, action=ACTION_CREATE, new_score=8,
    )
    assert r1.body["aggregate"]["accepted_vote_count"] == 1
    assert r1.body["aggregate"]["accepted_vote_sum"] == 8
    # idempotent retry
    r1b = svc.apply(
        idempotency_key="k1", canonical_title_id="t1", voter_subject_id="u1",
        scope=SCOPE_NETWORK, action=ACTION_CREATE, new_score=8,
    )
    assert r1b.body["aggregate"]["accepted_vote_count"] == 1
    # same key different payload → 409
    with pytest.raises(VoteConflict):
        svc.apply(
            idempotency_key="k1", canonical_title_id="t1", voter_subject_id="u1",
            scope=SCOPE_NETWORK, action=ACTION_CREATE, new_score=9,
        )
    # update replaces
    r2 = svc.apply(
        idempotency_key="k2", canonical_title_id="t1", voter_subject_id="u1",
        scope=SCOPE_NETWORK, action=ACTION_UPDATE, new_score=10,
    )
    assert r2.body["aggregate"]["accepted_vote_count"] == 1
    assert r2.body["aggregate"]["accepted_vote_sum"] == 10
    # delete revokes
    r3 = svc.apply(
        idempotency_key="k3", canonical_title_id="t1", voter_subject_id="u1",
        scope=SCOPE_NETWORK, action=ACTION_DELETE,
    )
    assert r3.body["aggregate"]["accepted_vote_count"] == 0
    # zero forbidden
    with pytest.raises(VoteValidationError):
        svc.apply(
            idempotency_key="k0", canonical_title_id="t1", voter_subject_id="u2",
            scope=SCOPE_NETWORK, action=ACTION_CREATE, new_score=0,
        )


def test_quarantined_excluded(store):
    svc = LocalVotesService(store.conn)
    svc.apply(
        idempotency_key="q1", canonical_title_id="t2", voter_subject_id="u1",
        scope=SCOPE_NETWORK, action=ACTION_CREATE, new_score=9, quarantine=True,
    )
    agg = svc.get_aggregate("t2")
    assert agg is None or agg["accepted_vote_count"] == 0


def test_concurrent_votes(tmp_path):
    db = tmp_path / "conc.sqlite"
    store = RatingsStore(db)
    seed_registry(store)
    store.close()
    errors = []

    def worker(i):
        try:
            s = RatingsStore(db)
            LocalVotesService(s.conn).apply(
                idempotency_key=f"c-{i}", canonical_title_id="tc", voter_subject_id=f"u{i}",
                scope=SCOPE_NETWORK, action=ACTION_CREATE, new_score=7,
            )
            s.close()
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    s = RatingsStore(db)
    assert LocalVotesService(s.conn).get_aggregate("tc")["accepted_vote_count"] == 8
    s.close()


def test_sources_remain_separate(store):
    apply_observation(
        store,
        RatingObservation(
            canonical_title_id="t", source_key="amd_online", external_id="1",
            raw_score=9.68, source_scale=10.0, normalized_score=9.68, vote_count=2031,
            score_distribution=None, source_updated_at="", observed_at=utc_now_iso(),
            payload_sha256="amd", adapter_version="t", provenance_url="https://amd.online/1-x.html",
            mapping_method=MappingMethod.MANUAL, validation_state=ValidationState.VALID,
            idempotency_key="s-amd",
        ),
        dry_run=False,
    )
    apply_observation(
        store,
        RatingObservation(
            canonical_title_id="t", source_key="shikimori", external_id="1",
            raw_score=9.2, source_scale=10.0, normalized_score=9.2, vote_count=10000,
            score_distribution=None, source_updated_at="", observed_at=utc_now_iso(),
            payload_sha256="shi", adapter_version="t", provenance_url="https://shikimori.io/animes/1",
            mapping_method=MappingMethod.SHIKIMORI_ID, validation_state=ValidationState.VALID,
            idempotency_key="s-shi",
        ),
        dry_run=False,
    )
    svc = LocalVotesService(store.conn)
    svc.apply(
        idempotency_key="s-loc", canonical_title_id="t", voter_subject_id="u",
        scope=SCOPE_NETWORK, action=ACTION_CREATE, new_score=8,
    )
    upsert_combined(store.conn, canonical_title_id="t", amd_score="9.68", amd_vote_count=2031)
    cur = {r["source_key"]: r for r in store.get_current("t")}
    assert "amd_online" in cur and "shikimori" in cur
    comb = dict(store.conn.execute("SELECT * FROM rating_combined_projection WHERE canonical_title_id='t'").fetchone())
    # combined uses AMD+local only — not shikimori 9.2
    assert comb["combined_ui"] == "9.66"
    gw = RatingGateway.from_store(store)
    c = gw.contract("t")
    sources = {s["source"] for s in c["ratingSources"]}
    assert sources == {"amd_online", "shikimori"}
    assert c["combinedRating"]["score"] == 9.66
    assert c["localRating"]["voteCount"] == 1


def test_rotation_ordering():
    rows = [
        {"canonical_title_id": "b", "combined_raw": "8.0", "local_vote_count": 1, "amd_vote_count": 10, "updated_at": "2026-01-02T00:00:00Z"},
        {"canonical_title_id": "a", "combined_raw": "9.0", "local_vote_count": 0, "amd_vote_count": 5, "updated_at": "2026-01-01T00:00:00Z"},
        {"canonical_title_id": "c", "combined_raw": "9.0", "local_vote_count": 2, "amd_vote_count": None, "updated_at": "2026-01-03T00:00:00Z"},
    ]
    ranked = sort_for_rotation(rows)
    assert ranked[0]["canonical_title_id"] == "c"  # 9.0 with more local votes
    assert ranked[1]["canonical_title_id"] == "a"
    assert ranked[2]["canonical_title_id"] == "b"


def test_coverage_targets():
    assert effective_daily_target(117) == 117
    assert effective_daily_target(1) == 1
    assert effective_daily_target(900) == 500
    assert effective_daily_target(0, full_coverage=True) == 0
    snap = CoverageSnapshot(
        source_applicable_total_start=1000,
        covered_valid_start=1000,
        uncovered_actionable_start=0,
    )
    d = snap.as_dict()
    assert d["full_coverage_mode"] is True
    assert d["effective_daily_target"] == 0
    snap2 = CoverageSnapshot(
        source_applicable_total_start=1000,
        covered_valid_start=800,
        uncovered_actionable_start=0,
        policy_excluded_start=200,
    )
    d2 = snap2.as_dict()
    assert d2["full_coverage_mode"] is False
    assert d2["actionable_saturated"] is True


def test_reason_arithmetic_and_qwen(tmp_path):
    assert verify_reason_arithmetic(
        attempted_unique=10,
        newly_covered=3,
        reason_counts={"PROVIDER_TITLE_NOT_FOUND": 4, "AMBIGUOUS_MAPPING": 3},
    )
    assert not verify_reason_arithmetic(
        attempted_unique=10, newly_covered=3, reason_counts={"X": 1}
    )
    report = {
        "report_date": "2026-09-19",
        "status": "GREEN",
        "mode": "BACKFILL",
        "catalog": {
            "covered_valid": 100,
            "source_applicable": 200,
            "gross_coverage_pct": 50.0,
            "eligible_coverage_pct": 55.0,
            "uncovered_actionable": 100,
        },
        "sla": {"effective_target": 100, "newly_covered": 92},
        "outcomes": {"not_added": 8},
        "new_titles": {"overdue_24h": 0},
        "refresh": {"refresh_changed": 0},
        "sources": {"shikimori": {"added": 92}},
        "amd_online": {"accepted": 0, "permission_status": "NOT_PROVIDED"},
        "user_votes": {"accepted": 0, "ranking_positions_changed": 0},
        "eta": "2026-10-02",
        "report_path": "x",
    }
    msg = build_qwen_message(report)
    assert "STATUS=GREEN" in msg
    paths = write_daily_report(report, tmp_path)
    assert Path(paths["qwen_message"]).is_file()
    delivery = QwenDelivery(configured=False).deliver(msg, dry_run=True)
    assert delivery["QWEN_DELIVERY"] == "NOT_CONFIGURED"
    assert delivery["DELIVERED"] is False


def test_null_not_rendered_as_zero():
    gw = RatingGateway({"titles": []})
    c = gw.contract("missing")
    assert c["ratingSources"] == []
    assert c.get("combinedRating") is None


def test_shikimori_canary_apply_path(store, tmp_path):
    class Fake:
        source_key = "shikimori"
        adapter_version = "test"
        rate_limiter = RateLimiter(max_rps=100, max_per_minute=1000, sleeper=lambda s: None)

        def fetch_by_ids(self, ids):
            out = {}
            for i in ids:
                if i.endswith("x"):
                    out[i] = FetchResult(external_id=i, found=False, error="NOT_FOUND")
                else:
                    out[i] = FetchResult(
                        external_id=i, found=True, raw_score=8.0, vote_count=10,
                        payload={"id": i, "score": 8.0, "score_source": "shikimori"},
                        provenance_url=f"https://shikimori.io/animes/{i}",
                    )
            return out

    for i in range(5):
        eid = str(i) if i < 4 else "4x"
        store.upsert_mapping(
            TitleSourceMapping(
                canonical_title_id=f"nova:{i}", source_key="shikimori",
                external_title_id=eid, mapping_method=MappingMethod.MAL_ID_CROSSWALK,
                confidence=1.0, state=MappingState.VERIFIED, verified_at=utc_now_iso(),
            )
        )
        store.enqueue(canonical_title_id=f"nova:{i}", source_key="shikimori", priority=10, priority_label="new_catalog")
    cfg = RatingsConfig.from_env(db_path=tmp_path / "c.sqlite", evidence_dir=tmp_path / "e")
    engine = IngestionEngine(store, Fake(), cfg)
    m = engine.ingest(source_key="shikimori", limit=5, apply=True, dry_run=False, use_lock=False, idempotency_key="canary-t")
    assert m.attempted == 5
    assert m.matched == 4
    assert m.inserted == 4
    assert m.not_found == 1
    # replay
    m2 = engine.ingest(source_key="shikimori", limit=5, apply=True, dry_run=False, use_lock=False, idempotency_key="canary-t")
    assert m2.checkpoint.get("idempotent_replay") is True
    assert store.observation_count() == 4
