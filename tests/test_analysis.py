"""KPI на сопоставимых окнах, классификация интентов, каннибализация, opportunity."""
from datetime import date, timedelta

import pytest

from seo_operator.analysis import cannibalization, kpi, opportunity, queries


# --- KPI ----------------------------------------------------------------------

def _series(start: date, days: int, value_fn, completeness=1.0):
    return [{"date": (start + timedelta(days=i)).isoformat(),
             "value": value_fn(i), "completeness": completeness} for i in range(days)]


def test_comparable_window_aligns_weekdays():
    start = date(2026, 6, 1)
    rows = _series(start, 56, lambda i: 100)
    m = kpi.comparable_window(rows, "clicks", date(2026, 7, 26), 28)
    assert m.delta_pct == 0.0
    assert m.complete


def test_incomplete_days_are_excluded():
    start = date(2026, 6, 1)
    rows = _series(start, 56, lambda i: 100)
    rows[-3:] = [{**r, "completeness": 0.2} for r in rows[-3:]]
    m = kpi.comparable_window(rows, "clicks", date(2026, 7, 26), 28)
    assert m.comparable_days < 28


def test_growth_is_measured_against_previous_window():
    start = date(2026, 6, 1)
    rows = _series(start, 56, lambda i: 100 if i < 28 else 120)
    m = kpi.comparable_window(rows, "clicks", date(2026, 7, 26), 28)
    assert m.delta_pct is not None and m.delta_pct > 15
    assert m.direction == "up"


def test_position_buckets():
    rows = [{"position": 2}, {"position": 5}, {"position": 15}, {"position": 40}]
    b = kpi.position_buckets(rows)
    assert (b["top3"], b["top10"], b["top20"], b["beyond"]) == (1, 2, 3, 1)


def test_weighted_position_follows_demand():
    rows = [{"position": 1.0, "impressions": 10000}, {"position": 50.0, "impressions": 10}]
    assert kpi.weighted_position(rows) < 2.0
    assert kpi.median_position(rows) == 25.5


def test_ctr_vs_expected():
    assert kpi.ctr_vs_expected(1, 0.28) == pytest.approx(1.0, abs=0.02)
    assert kpi.ctr_vs_expected(1, 0.10) < 0.5


def test_impression_coverage_detects_dead_index():
    assert kpi.impression_coverage(50, 5000) == 0.01


# --- классификация ------------------------------------------------------------

@pytest.fixture()
def classifier(isolated_state):
    return queries.QueryClassifier(
        brand_tokens=["demo"],
        title_index={"звёздный дрейф": "stellar-drift", "stellar drift": "stellar-drift"})


@pytest.mark.parametrize("query,expected", [
    ("звёздный дрейф", "exact_title"),
    ("звездный дрейф 2 сезон", "season"),
    ("звёздный дрейф 5 серия", "episode"),
    ("звёздный дрейф смотреть онлайн", "watch_intent"),
    ("когда выйдет звёздный дрейф", "schedule_date"),
    ("новинки аниме", "new_or_announcement"),
    ("онгоинги 2026", "ongoing"),
    ("в каком порядке смотреть звёздный дрейф", "watch_order"),
    ("подборка похожих сериалов", "collection_recommendation"),
    ("плеер не работает", "support_error"),
    ("demo", "navigational"),
])
def test_intent_classification(classifier, query, expected):
    assert classifier.classify(query).intent == expected


def test_unknown_query_is_not_assigned(classifier):
    cq = classifier.classify("абырвалг 12345")
    assert cq.intent == "unknown"
    assert not cq.assignable


def test_brand_flag_is_orthogonal(classifier):
    assert classifier.classify("demo звёздный дрейф").is_brand is True
    assert classifier.classify("звёздный дрейф").is_brand is False


def test_yo_normalization(classifier):
    assert classifier.classify("звездный дрейф").matched_title == "stellar-drift"


def test_clustering_groups_by_intent_and_title(classifier):
    cqs = [classifier.classify(q) for q in
           ["звёздный дрейф 2 сезон", "stellar drift 2 сезон", "звёздный дрейф 5 серия"]]
    clusters = queries.cluster(cqs)
    assert len(clusters["season:stellar-drift"]) == 2
    assert len(clusters["episode:stellar-drift"]) == 1


# --- каннибализация -----------------------------------------------------------

def test_intra_site_conflict_picks_useful_page(isolated_state):
    rows = [
        {"cluster_key": "exact_title:x", "url": "/a", "site_id": "s1", "impressions": 5000, "position": 4},
        {"cluster_key": "exact_title:x", "url": "/b", "site_id": "s1", "impressions": 3000, "position": 2},
    ]
    meta = {
        "/a": {"has_media_available": True, "content_depth_score": 0.9, "internal_links_in": 8,
               "engagement_score": 0.8, "canonical_self": True, "position": 4},
        "/b": {"has_media_available": False, "content_depth_score": 0.1, "internal_links_in": 0,
               "engagement_score": 0.1, "canonical_self": False, "position": 2},
    }
    conflicts = cannibalization.detect(rows, meta)
    assert len(conflicts) == 1
    # Побеждает полезная страница, а не та, что стоит выше.
    assert conflicts[0].recommended_primary == "/a"
    assert cannibalization.auto_resolvable(conflicts[0])


def test_cross_tenant_conflict_is_never_auto_resolved(isolated_state):
    rows = [
        {"cluster_key": "exact_title:x", "url": "https://a.example/t", "site_id": "s1", "impressions": 900, "position": 5},
        {"cluster_key": "exact_title:x", "url": "https://b.example/t", "site_id": "s2", "impressions": 800, "position": 6},
    ]
    conflicts = cannibalization.detect(rows)
    assert conflicts[0].scope == "cross_tenant"
    assert conflicts[0].severity == "high"
    assert not cannibalization.auto_resolvable(conflicts[0])


def test_low_traffic_pairs_ignored(isolated_state):
    rows = [
        {"cluster_key": "k", "url": "/a", "site_id": "s1", "impressions": 5, "position": 4},
        {"cluster_key": "k", "url": "/b", "site_id": "s1", "impressions": 3, "position": 6},
    ]
    assert cannibalization.detect(rows) == []


# --- opportunity --------------------------------------------------------------

def _oi(**kw):
    base = dict(
        site_id="demo-fixture", subject="stellar-drift",
        demand={"gsc_impressions_trend_28d": 0.8, "yandex_query_history_trend": 0.7},
        release_date=date(2026, 9, 5), release_confirmed=True,
        rights_ref="rights://demo/stellar-drift", source_confidence="high",
        media_available=True, metadata_completeness=0.9,
        page_quality={"substantive_content": True, "distinct_value": True,
                      "canonical_correct": True, "internal_links_present": True, "render_ok": True},
        current_position=18.0, business_priority=1.2,
        measurement={"data_freshness_ok": True, "sample_size_ok": True,
                     "no_active_incident": True, "no_confounding_experiment": True},
        risk={"cannibalization_risk": 0.1, "rights_risk": 0.0, "effort_hours": 4, "blast_radius": 0.1})
    base.update(kw)
    return opportunity.OpportunityInput(**base)


def test_missing_rights_zeroes_score(isolated_state):
    s = opportunity.score(_oi(rights_ref=None), today=date(2026, 8, 22))
    assert s.score == 0.0
    assert "rights_and_content_readiness" in s.gates_failed
    assert not s.publishable


def test_low_source_confidence_zeroes_score(isolated_state):
    s = opportunity.score(_oi(source_confidence="medium"), today=date(2026, 8, 22))
    assert s.score == 0.0


def test_poor_page_quality_fails_gate(isolated_state):
    s = opportunity.score(_oi(page_quality={"substantive_content": False, "distinct_value": False,
                                            "canonical_correct": True, "internal_links_present": False,
                                            "render_ok": True}),
                          today=date(2026, 8, 22))
    assert "page_quality_readiness" in s.gates_failed


def test_ready_release_scores_positive(isolated_state):
    s = opportunity.score(_oi(), today=date(2026, 8, 22))
    assert s.score > 0 and not s.gates_failed


def test_pre_release_window_gets_boost(isolated_state):
    near = opportunity.score(_oi(release_date=date(2026, 8, 30)), today=date(2026, 8, 22))
    far = opportunity.score(_oi(release_date=date(2027, 3, 1)), today=date(2026, 8, 22))
    assert near.score > far.score


def test_high_risk_lowers_score(isolated_state):
    low = opportunity.score(_oi(), today=date(2026, 8, 22))
    high = opportunity.score(_oi(risk={"cannibalization_risk": 0.9, "rights_risk": 0.5,
                                       "effort_hours": 20, "blast_radius": 1.0}),
                             today=date(2026, 8, 22))
    assert high.score < low.score


def test_ranking_gap_prefers_reachable_targets(isolated_state):
    already_top = opportunity.score(_oi(current_position=2.0), today=date(2026, 8, 22))
    far_back = opportunity.score(_oi(current_position=18.0), today=date(2026, 8, 22))
    assert far_back.score > already_top.score
