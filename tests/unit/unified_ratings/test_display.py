"""Отображение: источники раздельно, отсутствие не нулём, без общего среднего."""

from __future__ import annotations

import json

import pytest

from factory.unified_ratings.composite import compute
from factory.unified_ratings.display import Availability, DisplayModel, RowKind
from factory.unified_ratings.editorial import EditorialRatings, Principal
from factory.unified_ratings.titles import utc_now

EDITOR = Principal(actor_id="user-editor", role="content_editor")


def put_external(
    store, *, title_id="nova:t-001", source="anilist", raw="86", normalized="8.6",
    votes=170305, state="OK", users=None,
):
    with store.write_tx() as conn:
        conn.execute(
            """INSERT INTO unified_external_snapshots(
                   title_id, source_key, external_id, raw_score, source_scale_min,
                   source_scale_max, normalization_formula, normalized_score, vote_count,
                   user_count, fetched_at, adapter_version, raw_payload_sha256, content_hash,
                   validation_state)
               VALUES (?,?,'1',?,'0','100','divide_10_from_0_100',?,?,?,?,'v','h',?,?)""",
            (title_id, source, raw, normalized, votes, users, utc_now(), f"h-{source}", state),
        )
        snapshot_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            """INSERT INTO unified_external_current(
                   title_id, source_key, snapshot_id, raw_score, source_scale_max,
                   normalized_score, vote_count, user_count, content_hash, validation_state,
                   fetched_at, last_checked_at, provenance_url)
               VALUES (?,?,?,?,'100',?,?,?,?,?,?,?,?)""",
            (
                title_id, source, snapshot_id, raw, normalized, votes, users,
                f"h-{source}", state, utc_now(), utc_now(),
                f"https://example.test/{source}/1",
            ),
        )
        conn.execute(
            """INSERT INTO unified_source_links(
                   title_id, source_key, external_id, match_method, confidence, status,
                   created_at, updated_at)
               VALUES (?,?,'1','exact_external_id',1.0,'exact',?,?)""",
            (title_id, source, utc_now(), utc_now()),
        )


@pytest.fixture
def display(store, seeded) -> DisplayModel:
    return DisplayModel(store, editorial=EditorialRatings(store, registry=seeded))


def rows_by_key(display, **kwargs) -> dict:
    return {r.key: r for r in display.rows_for(**kwargs)}


# ---------------------------------------------------------------------------
# раздельность
# ---------------------------------------------------------------------------


def test_every_required_row_is_present(display):
    rows = rows_by_key(display, title_id="nova:t-001", tenant_id="yummy")
    for key in (
        "editorial", "community", "anilist", "simkl", "kitsu", "shikimori",
        "provider_feed_imdb", "provider_feed_kinopoisk",
    ):
        assert key in rows


def test_labels_name_each_source_exactly(display):
    rows = rows_by_key(display, title_id="nova:t-001", tenant_id="yummy")
    assert rows["editorial"].label == "Наша оценка"
    assert rows["community"].label == "Оценка зрителей"
    assert rows["anilist"].label == "AniList"
    assert rows["provider_feed_imdb"].label == "IMDb"
    assert rows["provider_feed_kinopoisk"].label == "Кинопоиск"


def test_editorial_and_community_are_different_row_kinds(display, store, seeded):
    EditorialRatings(store, registry=seeded).set_score(
        EDITOR, title_id="nova:t-001", score=9, rationale="разбор"
    )
    rows = rows_by_key(display, title_id="nova:t-001", tenant_id="yummy")
    assert rows["editorial"].kind is RowKind.EDITORIAL
    assert rows["community"].kind is RowKind.COMMUNITY
    assert rows["editorial"].display_value == "9/10"


def test_external_rows_carry_raw_value_scale_and_formula(display, store):
    put_external(store)
    row = rows_by_key(display, title_id="nova:t-001", tenant_id="yummy")["anilist"]
    assert row.availability is Availability.PRESENT
    assert row.display_value == "8.6"
    assert row.raw_value == "86"
    assert row.source_scale == "0–100"
    assert row.formula == "normalized = raw / 10"
    assert row.provenance_url


# ---------------------------------------------------------------------------
# отсутствие не становится нулём
# ---------------------------------------------------------------------------


def test_unlinked_source_says_so(display):
    row = rows_by_key(display, title_id="nova:t-001", tenant_id="yummy")["kitsu"]
    assert row.availability is Availability.NOT_LINKED
    assert row.display_value is None
    assert row.numeric is None
    assert row.reason


def test_blocked_source_reports_its_blocker(display):
    row = rows_by_key(display, title_id="nova:t-001", tenant_id="yummy")["simkl"]
    assert row.availability is Availability.SOURCE_BLOCKED
    assert row.display_value is None
    assert "client_id" in row.reason


def test_absent_external_score_is_not_zero(display, store):
    put_external(store, source="shikimori", raw=None, normalized=None, state="ABSENT", votes=None)
    row = rows_by_key(display, title_id="nova:t-001", tenant_id="yummy")["shikimori"]
    assert row.availability is Availability.NO_RATING_AT_SOURCE
    assert row.display_value is None


def test_pending_review_is_not_published(display, store):
    with store.write_tx() as conn:
        conn.execute(
            """INSERT INTO unified_source_links(
                   title_id, source_key, external_id, match_method, confidence, status,
                   created_at, updated_at)
               VALUES ('nova:t-001','kitsu','9','fuzzy_candidate',0.9,'pending','n','n')"""
        )
    row = rows_by_key(display, title_id="nova:t-001", tenant_id="yummy")["kitsu"]
    assert row.availability is Availability.PENDING_REVIEW
    assert row.display_value is None


def test_no_zero_appears_anywhere_when_nothing_is_known(display):
    payload = display.view(title_id="nova:t-001", tenant_id="yummy")
    for row in payload["rows"]:
        assert row["display_value"] in (None,), row
        assert row["numeric"] is None


def test_community_with_no_votes_reads_as_no_votes(display, community):
    community.rebuild(tenant_id="yummy", title_id="nova:t-001")
    row = rows_by_key(display, title_id="nova:t-001", tenant_id="yummy")["community"]
    assert row.availability is Availability.NO_RATING_AT_SOURCE
    assert row.vote_count == 0
    assert row.display_value is None
    assert "пока нет оценок" in row.reason


def test_community_average_and_count_are_shown_together(display, community):
    for i, score in enumerate([8, 9, 10]):
        community.submit(
            tenant_id="yummy", subject_id="s-001", actor_id=f"a{i}", score=score,
            idempotency_key=f"k{i}",
        )
    row = rows_by_key(display, title_id="nova:t-001", tenant_id="yummy")["community"]
    assert row.availability is Availability.PRESENT
    assert row.display_value == "9.0"
    assert row.vote_count == 3


def test_kitsu_user_count_is_kept_apart_from_votes(display, store):
    put_external(store, source="kitsu", raw="82.27", normalized="8.227", votes=25, users=162344)
    row = rows_by_key(display, title_id="nova:t-001", tenant_id="yummy")["kitsu"]
    assert row.vote_count == 25
    assert row.user_count == 162344


# ---------------------------------------------------------------------------
# без общего среднего
# ---------------------------------------------------------------------------


def test_view_does_not_produce_a_single_combined_rating(display, store):
    put_external(store, source="anilist", normalized="8.6")
    put_external(store, source="shikimori", normalized="7.0")
    payload = display.view(title_id="nova:t-001", tenant_id="yummy")
    assert payload["combined_rating"] is None
    assert payload["combined_rating_note"]


def test_view_is_json_serialisable(display, store):
    put_external(store)
    json.dumps(display.view(title_id="nova:t-001", tenant_id="yummy"), ensure_ascii=False)


# ---------------------------------------------------------------------------
# сортировочный показатель
# ---------------------------------------------------------------------------


def test_composite_refuses_on_a_thin_sample(store, seeded):
    put_external(store, source="anilist", normalized="9.9", votes=3)
    result = compute(store, title_id="nova:t-001", tenant_id="yummy")
    assert result.value is None
    assert result.state == "INSUFFICIENT_DATA"
    assert result.reason


def test_composite_names_what_it_used_and_what_it_skipped(store, seeded):
    put_external(store, source="anilist", normalized="8.6", votes=170305)
    put_external(store, source="kitsu", normalized="8.2", votes=None)
    result = compute(store, title_id="nova:t-001", tenant_id="yummy")
    used = {s["source"] for s in result.sources_used}
    skipped = {s["source"] for s in result.sources_excluded}
    assert "anilist" in used
    assert "kitsu" in skipped, "источник без числа голосов не участвует"
    assert result.formula_version == "weighted_bayes_v1"


def test_composite_pulls_a_thin_but_admitted_sample_toward_the_prior(store, seeded):
    put_external(store, source="anilist", normalized="10", votes=60)
    result = compute(store, title_id="nova:t-001", tenant_id="yummy")
    assert result.state == "OK"
    from decimal import Decimal

    assert Decimal(result.value) < Decimal("10")
    assert Decimal(result.value) > Decimal("5.5")


def test_composite_does_not_replace_the_source_values(store, seeded, display):
    put_external(store, source="anilist", normalized="8.6", votes=170305)
    compute(store, title_id="nova:t-001", tenant_id="yummy")
    row = rows_by_key(display, title_id="nova:t-001", tenant_id="yummy")["anilist"]
    assert row.display_value == "8.6"


def test_composite_ignores_scores_that_failed_validation(store, seeded):
    put_external(store, source="anilist", raw="0", normalized=None, state="ZERO_NOT_A_RATING",
                 votes=100000)
    result = compute(store, title_id="nova:t-001", tenant_id="yummy")
    assert result.value is None
    assert any(s["source"] == "anilist" for s in result.sources_excluded)
