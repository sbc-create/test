"""Сводная оценка: минимум два источника, равные веса, отсутствие ≠ ноль."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from factory.unified_ratings.composite import (
    DISPLAY_NAME,
    FORMULA_VERSION,
    INTERNAL_NAME,
    MIN_SOURCES,
    compute,
    record_formula_change,
    recompute_many,
    store_composite,
)
from factory.unified_ratings.titles import utc_now

NOW = datetime(2026, 9, 22, 12, 0, 0, tzinfo=timezone.utc)


def put(store, *, source, normalized, raw="70", scale="100", votes=1000,
        state="OK", title_id="nova:t-001", checked=None, link_status="exact"):
    stamp = (checked or NOW).strftime("%Y-%m-%dT%H:%M:%SZ")
    with store.write_tx() as conn:
        conn.execute(
            """INSERT INTO unified_external_snapshots(
                   title_id, source_key, external_id, raw_score, source_scale_min,
                   source_scale_max, normalization_formula, normalized_score, vote_count,
                   fetched_at, adapter_version, raw_payload_sha256, content_hash,
                   validation_state)
               VALUES (?,?,'1',?,'0',?,'divide_10_from_0_100',?,?,?,'v','h',?,?)""",
            (title_id, source, raw, scale, normalized, votes, stamp, f"h-{source}", state),
        )
        sid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            """INSERT INTO unified_external_current(
                   title_id, source_key, snapshot_id, raw_score, source_scale_max,
                   normalized_score, vote_count, content_hash, validation_state,
                   fetched_at, last_checked_at, provenance_url)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,'')""",
            (title_id, source, sid, raw, scale, normalized, votes, f"h-{source}", state,
             stamp, stamp),
        )
        if link_status:
            conn.execute(
                """INSERT INTO unified_source_links(
                       title_id, source_key, external_id, match_method, confidence, status,
                       created_at, updated_at)
                   VALUES (?,?,?,'exact_external_id',1.0,?,?,?)""",
                (title_id, source, f"{source}:{title_id}", link_status, utc_now(), utc_now()),
            )


# ---------------------------------------------------------------------------
# минимум источников
# ---------------------------------------------------------------------------


def test_one_source_is_not_called_a_composite(store, seeded):
    put(store, source="anilist", normalized="8.0")
    result = compute(store, title_id="nova:t-001", now=NOW)
    assert result.state == "SINGLE_SOURCE_ONLY"
    assert result.value is None
    assert result.source_count == 1
    assert "сводной не называется" in result.reason


def test_two_sources_produce_a_composite(store, seeded):
    put(store, source="anilist", normalized="8.0")
    put(store, source="kitsu", normalized="7.0")
    result = compute(store, title_id="nova:t-001", now=NOW)
    assert result.state == "OK"
    assert result.value == "7.5"
    assert result.source_count == 2


def test_min_sources_is_two():
    assert MIN_SOURCES == 2


def test_no_sources_reports_absence_not_zero(store, seeded):
    result = compute(store, title_id="nova:t-001", now=NOW)
    assert result.state == "NO_SOURCES"
    assert result.value is None


# ---------------------------------------------------------------------------
# равные веса, а не голоса
# ---------------------------------------------------------------------------


def test_vote_counts_do_not_weight_the_result(store, seeded):
    """Источник со ста тысячами голосов не перевешивает источник с сотней."""
    put(store, source="anilist", normalized="9.0", votes=100_000)
    put(store, source="kitsu", normalized="5.0", votes=100)
    result = compute(store, title_id="nova:t-001", now=NOW)
    assert result.value == "7.0", "при равных весах это ровно середина"


def test_vote_counts_are_reported_separately_as_confidence(store, seeded):
    put(store, source="anilist", normalized="9.0", votes=50_000)
    put(store, source="kitsu", normalized="8.0", votes=20_000)
    result = compute(store, title_id="nova:t-001", now=NOW)
    assert result.total_votes == 70_000
    assert result.confidence in ("LOW", "MEDIUM", "HIGH")
    assert all(c.vote_count is not None for c in result.sources_used)


def test_four_sources_average_with_equal_weights(store, seeded):
    for source, value in (
        ("anilist", "8.0"), ("kitsu", "8.0"), ("shikimori", "9.0"),
        ("provider_feed_imdb", "7.0"),
    ):
        put(store, source=source, normalized=value)
    result = compute(store, title_id="nova:t-001", now=NOW)
    assert result.value == "8.0"
    assert result.source_count == 4


def test_rounding_is_one_decimal(store, seeded):
    put(store, source="anilist", normalized="8.25")
    put(store, source="kitsu", normalized="8.26")
    result = compute(store, title_id="nova:t-001", now=NOW)
    assert result.value == "8.3"
    assert len(result.value.split(".")[1]) == 1


# ---------------------------------------------------------------------------
# исключения
# ---------------------------------------------------------------------------


def test_missing_source_is_not_counted_as_zero(store, seeded):
    put(store, source="anilist", normalized="9.0")
    put(store, source="kitsu", normalized=None, raw=None, state="ABSENT")
    put(store, source="shikimori", normalized="8.0")
    result = compute(store, title_id="nova:t-001", now=NOW)
    assert result.value == "8.5", "отсутствующий источник выпал, а не обнулил среднее"
    assert any(e["source"] == "kitsu" for e in result.sources_excluded)


def test_ambiguous_match_is_excluded(store, seeded):
    put(store, source="anilist", normalized="9.0")
    put(store, source="kitsu", normalized="5.0", link_status="conflict")
    result = compute(store, title_id="nova:t-001", now=NOW)
    assert result.state == "SINGLE_SOURCE_ONLY"
    assert any("не подтверждено" in e["reason"] for e in result.sources_excluded)


def test_stale_source_is_excluded(store, seeded):
    put(store, source="anilist", normalized="9.0")
    put(store, source="kitsu", normalized="5.0", checked=NOW - timedelta(days=90))
    result = compute(store, title_id="nova:t-001", now=NOW)
    assert result.state == "SINGLE_SOURCE_ONLY"
    assert any("устарело" in e["reason"] for e in result.sources_excluded)


def test_unknown_source_is_not_admitted(store, seeded):
    put(store, source="anilist", normalized="9.0")
    put(store, source="kitsu", normalized="8.0")
    result = compute(
        store, title_id="nova:t-001", now=NOW, weights={"anilist": Decimal("1.0")}
    )
    assert result.state == "SINGLE_SOURCE_ONLY"
    assert any("не разрешён" in e["reason"] for e in result.sources_excluded)


# ---------------------------------------------------------------------------
# разные исходные шкалы
# ---------------------------------------------------------------------------


def test_sources_on_different_native_scales_combine_after_normalization(store, seeded):
    put(store, source="anilist", normalized="8.6", raw="86", scale="100")
    put(store, source="shikimori", normalized="7.4", raw="7.4", scale="10")
    result = compute(store, title_id="nova:t-001", now=NOW)
    assert result.value == "8.0"
    scales = {c.source_scale for c in result.sources_used}
    assert scales == {"0–100", "0–10"}
    raws = {c.raw_value for c in result.sources_used}
    assert raws == {"86", "7.4"}, "исходные значения сохранены без изменения"


# ---------------------------------------------------------------------------
# пересчёт и хранение
# ---------------------------------------------------------------------------


def test_recompute_after_one_source_changes(store, seeded):
    put(store, source="anilist", normalized="8.0")
    put(store, source="kitsu", normalized="6.0")
    assert compute(store, title_id="nova:t-001", now=NOW).value == "7.0"
    with store.write_tx() as conn:
        conn.execute(
            "UPDATE unified_external_current SET normalized_score='10.0' WHERE source_key='kitsu'"
        )
    assert compute(store, title_id="nova:t-001", now=NOW).value == "9.0"


def test_stored_composite_is_keyed_by_formula_version(store, seeded):
    put(store, source="anilist", normalized="8.0")
    put(store, source="kitsu", normalized="6.0")
    rating = compute(store, title_id="nova:t-001", now=NOW)
    store_composite(store, rating)
    row = store.query_one("SELECT * FROM unified_composite_ratings WHERE title_id='nova:t-001'")
    assert row["formula_version"] == FORMULA_VERSION
    assert row["value"] == "7.0"
    assert row["source_count"] == 2


def test_recompute_many_reports_each_state(store, seeded):
    put(store, source="anilist", normalized="8.0")
    put(store, source="kitsu", normalized="6.0")
    put(store, source="anilist", normalized="7.0", title_id="nova:t-002")
    counts = recompute_many(store, ["nova:t-001", "nova:t-002"], now=NOW)
    assert counts["OK"] == 1
    assert counts["SINGLE_SOURCE_ONLY"] == 1


def test_formula_change_is_audited(store, seeded):
    record_formula_change(
        store,
        version="equal_weight_mean_v1",
        weights={"anilist": Decimal("1.0")},
        actor="user-chief",
        rationale="первая версия",
    )
    row = store.query_one("SELECT * FROM unified_composite_formula_audit")
    assert row["formula_version"] == "equal_weight_mean_v1"
    assert row["min_sources"] == MIN_SOURCES
    assert row["actor"] == "user-chief"


# ---------------------------------------------------------------------------
# отделённость от двух других видов
# ---------------------------------------------------------------------------


def test_composite_is_named_apart_from_our_viewers_score(store, seeded):
    put(store, source="anilist", normalized="8.0")
    put(store, source="kitsu", normalized="6.0")
    payload = compute(store, title_id="nova:t-001", now=NOW).as_dict()
    assert payload["display_name"] == DISPLAY_NAME == "Сводная оценка"
    assert payload["internal_name"] == INTERNAL_NAME == "composite_external_rating"
    assert "Оценка зрителей" not in payload["display_name"]
    assert "не оценка зрителей нашего сайта" in payload["note"]


def test_composite_carries_its_metadata(store, seeded):
    put(store, source="anilist", normalized="8.0")
    put(store, source="kitsu", normalized="6.0")
    payload = compute(store, title_id="nova:t-001", now=NOW).as_dict()
    for key in (
        "formula_version", "calculated_at", "sources_used", "source_count",
        "confidence", "freshness_status",
    ):
        assert payload[key] is not None, key
    assert {c["source"] for c in payload["sources_used"]} == {"anilist", "kitsu"}


def test_composite_does_not_read_community_or_editorial(store, seeded, community):
    """Сводная — только внешние источники, даже когда есть свои оценки."""
    community.submit(
        tenant_id="yummy", subject_id="s-001", actor_id="a1", score=1, idempotency_key="k1"
    )
    put(store, source="anilist", normalized="9.0")
    put(store, source="kitsu", normalized="9.0")
    result = compute(store, title_id="nova:t-001", now=NOW)
    assert result.value == "9.0", "единица от зрителя не участвует в сводной оценке"
    assert {c.source_key for c in result.sources_used} == {"anilist", "kitsu"}


@pytest.mark.parametrize("state", ["ZERO_NOT_A_RATING", "OUT_OF_RANGE_LOW", "CONTRACT_UNVERIFIED"])
def test_invalid_states_never_enter_the_average(store, seeded, state):
    put(store, source="anilist", normalized="9.0")
    put(store, source="kitsu", normalized="0.0", state=state)
    result = compute(store, title_id="nova:t-001", now=NOW)
    assert result.state == "SINGLE_SOURCE_ONLY"
