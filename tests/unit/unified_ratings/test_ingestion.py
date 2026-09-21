"""Конвейер импорта: неизменившееся, изменившееся, прерывание и продолжение."""

from __future__ import annotations

import pytest

from factory.ratings.adapters.base import AdapterError
from factory.unified_ratings.adapters.base import Capabilities, SourceFetch
from factory.unified_ratings.ingestion import IngestionRefused, Ingestor
from factory.unified_ratings.sources import ANILIST, SIMKL, SourceStatus
from factory.unified_ratings.titles import CanonicalTitle


class StubAdapter:
    """Адаптер, отвечающий заранее заданными данными."""

    source_key = "anilist"
    adapter_version = "anilist-graphql/1.0.0"

    def __init__(self, responses: dict[str, dict], *, fail: Exception | None = None) -> None:
        self.responses = responses
        self.fail = fail
        self.calls: list[list[str]] = []
        self.client = None

    def capabilities(self) -> Capabilities:
        return Capabilities(
            source_key=self.source_key,
            supports_batch=True,
            max_batch_size=25,
            supports_vote_count=True,
            supports_user_count=False,
            supports_distribution=True,
            supports_source_side_incremental=False,
            incremental_mode="локальный checkpoint",
            external_id_space="anilist",
            requires_credential=False,
        )

    def fetch_by_mal_ids(self, mal_ids: list[str]) -> dict[str, SourceFetch]:
        self.calls.append(list(mal_ids))
        if self.fail is not None:
            raise self.fail
        out: dict[str, SourceFetch] = {}
        for mal_id in mal_ids:
            spec = self.responses.get(mal_id)
            if spec is None:
                out[mal_id] = SourceFetch(
                    source_key=self.source_key, external_id=mal_id, found=False, error="NOT_FOUND"
                )
                continue
            out[mal_id] = SourceFetch(
                source_key=self.source_key,
                external_id=mal_id,
                found=spec.get("score") is not None,
                raw_score=spec.get("score"),
                vote_count=spec.get("votes"),
                source_updated_at=spec.get("updated_at", ""),
                provenance_url=f"https://anilist.co/anime/{mal_id}",
                titles={"romaji": spec.get("title", "Cowboy Bebop")},
                year=spec.get("year", 1998),
                kind=spec.get("kind", "TV"),
                episodes=spec.get("episodes", 26),
                raw_payload={"averageScore": spec.get("score"), "fetched_marker": spec.get("marker", "")},
            )
        return out

    def fetch_by_external_ids(self, external_ids: list[str]) -> dict[str, SourceFetch]:
        return self.fetch_by_mal_ids(external_ids)

    def health(self) -> dict:
        return {"source_key": self.source_key, "state": "HEALTHY"}


@pytest.fixture
def titles(seeded) -> list[CanonicalTitle]:
    return [seeded.get("nova:t-001"), seeded.get("nova:t-002")]


def ingestor(store, adapter, *, dry_run=False) -> Ingestor:
    return Ingestor(store, ANILIST, adapter, dry_run=dry_run)


# ---------------------------------------------------------------------------
# первый импорт
# ---------------------------------------------------------------------------


def test_first_import_inserts_and_records_provenance(store, titles):
    adapter = StubAdapter({"1": {"score": 86, "votes": 170305}})
    result = ingestor(store, adapter).run(titles, stage="PILOT")
    assert result.counters.inserted == 1
    row = store.query_one("SELECT * FROM unified_external_snapshots WHERE title_id='nova:t-001'")
    assert row["raw_score"] == "86"
    assert row["normalized_score"] == "8.6"
    assert row["source_scale_max"] == "100"
    assert row["normalization_formula"] == "divide_10_from_0_100"
    assert row["vote_count"] == 170305
    assert row["adapter_version"] == "anilist-graphql/1.0.0"
    assert row["raw_payload_sha256"]
    assert "provenance_url" in row["provenance_json"]


def test_absent_score_is_recorded_as_absent_not_zero(store, titles):
    adapter = StubAdapter({"1": {"score": None, "votes": 41}})
    ingestor(store, adapter).run(titles)
    row = store.query_one("SELECT * FROM unified_external_current WHERE title_id='nova:t-001'")
    assert row["validation_state"] == "ABSENT"
    assert row["normalized_score"] is None
    assert row["vote_count"] == 41


def test_zero_score_is_recorded_as_not_a_rating(store, titles):
    adapter = StubAdapter({"1": {"score": 0, "votes": 0}})
    ingestor(store, adapter).run(titles)
    row = store.query_one("SELECT * FROM unified_external_current WHERE title_id='nova:t-001'")
    assert row["validation_state"] == "ZERO_NOT_A_RATING"
    assert row["normalized_score"] is None


# ---------------------------------------------------------------------------
# неизменившееся и изменившееся
# ---------------------------------------------------------------------------


def test_unchanged_import_creates_no_new_version(store, titles):
    adapter = StubAdapter({"1": {"score": 86, "votes": 170305}})
    engine = ingestor(store, adapter)
    engine.run(titles, stage="FIRST")
    before = store.count("unified_external_snapshots")
    result = engine.run(titles, stage="SECOND")
    assert result.counters.unchanged == 1
    assert result.counters.inserted == 0
    assert result.counters.updated == 0
    assert store.count("unified_external_snapshots") == before


def test_unchanged_import_still_advances_the_check_time(store, titles):
    adapter = StubAdapter({"1": {"score": 86, "votes": 170305}})
    engine = ingestor(store, adapter)
    engine.run(titles)
    engine.run(titles)
    row = store.query_one("SELECT * FROM unified_external_current WHERE title_id='nova:t-001'")
    assert row["unchanged_streak"] == 1
    assert row["last_checked_at"] >= row["fetched_at"]


def test_a_different_response_time_alone_is_still_unchanged(store, titles):
    """В content_hash не входит время: иначе новая версия была бы ежедневной."""
    engine = ingestor(store, StubAdapter({"1": {"score": 86, "votes": 10, "updated_at": "A"}}))
    engine.run(titles)
    engine.adapter = StubAdapter({"1": {"score": 86, "votes": 10, "updated_at": "B"}})
    result = engine.run(titles)
    assert result.counters.unchanged == 1
    assert store.count("unified_external_snapshots") == 1


def test_changed_import_creates_a_new_version_linked_to_the_previous(store, titles):
    engine = ingestor(store, StubAdapter({"1": {"score": 86, "votes": 100}}))
    engine.run(titles)
    first = store.query_one("SELECT snapshot_id FROM unified_external_current")["snapshot_id"]
    engine.adapter = StubAdapter({"1": {"score": 87, "votes": 120}})
    result = engine.run(titles)
    assert result.counters.updated == 1
    assert store.count("unified_external_snapshots") == 2
    latest = store.query_one(
        "SELECT * FROM unified_external_snapshots ORDER BY snapshot_id DESC LIMIT 1"
    )
    assert latest["prev_snapshot_id"] == first
    assert latest["normalized_score"] == "8.7"
    current = store.query_one("SELECT * FROM unified_external_current")
    assert current["unchanged_streak"] == 0


def test_a_vote_count_change_alone_is_a_change(store, titles):
    engine = ingestor(store, StubAdapter({"1": {"score": 86, "votes": 100}}))
    engine.run(titles)
    engine.adapter = StubAdapter({"1": {"score": 86, "votes": 200}})
    assert engine.run(titles).counters.updated == 1


# ---------------------------------------------------------------------------
# прерывание и продолжение
# ---------------------------------------------------------------------------


def test_a_failed_run_is_still_recorded(store, titles):
    adapter = StubAdapter({}, fail=AdapterError("TIMEOUT", "источник не ответил"))
    result = ingestor(store, adapter).run(titles, stage="PILOT")
    assert result.status == "FAILED"
    row = store.query_one("SELECT * FROM unified_import_runs WHERE run_id=?", (result.run_id,))
    assert row["status"] == "FAILED"
    assert row["finished_at"]
    assert "TIMEOUT" in row["notes"]


def test_a_rate_limited_run_is_counted_as_such(store, titles):
    adapter = StubAdapter({}, fail=AdapterError("RATE_LIMITED", "429", retry_after=30))
    result = ingestor(store, adapter).run(titles)
    assert result.counters.rate_limited == 1
    assert result.status == "FAILED"


def test_resume_after_interruption_keeps_completed_work(store, titles):
    """Прерванный прогон не откатывает уже записанное и не дублирует его."""
    engine = ingestor(store, StubAdapter({"1": {"score": 86, "votes": 100}}))
    first = engine.run([titles[0]], stage="PART_1")
    assert first.counters.inserted == 1
    checkpoint = first.next_checkpoint
    assert checkpoint

    engine.adapter = StubAdapter(
        {"1": {"score": 86, "votes": 100}, "2": {"score": 70, "votes": 50, "year": 2016, "kind": "MOVIE"}}
    )
    second = engine.run(titles, stage="PART_2", cursor_in=checkpoint)
    assert second.counters.inserted == 1, "второй тайтл дописан"
    assert second.counters.unchanged == 1, "первый не переписан"
    assert store.count("unified_external_snapshots") == 2


def test_every_run_appears_in_the_journal_with_full_counters(store, titles):
    engine = ingestor(store, StubAdapter({"1": {"score": 86, "votes": 100}}))
    result = engine.run(titles, stage="PILOT")
    row = store.query_one("SELECT * FROM unified_import_runs WHERE run_id=?", (result.run_id,))
    for column in (
        "requested", "received", "exact_match", "pending_match", "rejected",
        "inserted", "updated", "unchanged", "failed", "rate_limited", "retries",
    ):
        assert row[column] is not None, f"журнал не содержит {column}"
    assert row["cursor_out"]
    assert row["next_checkpoint"]
    assert row["code_version"]
    assert row["stage"] == "PILOT"


# ---------------------------------------------------------------------------
# сопоставление внутри импорта
# ---------------------------------------------------------------------------


def test_disagreeing_facts_go_to_the_review_queue_not_to_the_snapshot(store, titles):
    adapter = StubAdapter({"1": {"score": 86, "votes": 100, "year": 2015}})
    result = ingestor(store, adapter).run(titles)
    assert result.counters.pending_match == 1
    assert result.counters.inserted == 0
    assert store.count("unified_external_snapshots") == 0
    review = store.query_one("SELECT * FROM unified_review_queue")
    assert review["reason_code"] == "YEAR_MISMATCH"
    assert review["status"] == "PENDING"
    link = store.query_one("SELECT * FROM unified_source_links")
    assert link["status"] == "conflict"


def test_review_queue_does_not_duplicate_the_same_open_item(store, titles):
    adapter = StubAdapter({"1": {"score": 86, "votes": 100, "year": 2015}})
    engine = ingestor(store, adapter)
    engine.run(titles)
    engine.run(titles)
    assert store.count("unified_review_queue") == 1


def test_accepted_links_are_marked_exact(store, titles):
    adapter = StubAdapter({"1": {"score": 86, "votes": 100}})
    ingestor(store, adapter).run(titles)
    link = store.query_one("SELECT * FROM unified_source_links WHERE title_id='nova:t-001'")
    assert link["status"] == "exact"
    assert link["match_method"] == "exact_external_id"
    assert link["confidence"] == 1.0
    assert link["verified_at"]


# ---------------------------------------------------------------------------
# отказ собирать заблокированный источник
# ---------------------------------------------------------------------------


def test_blocked_source_is_refused_before_any_request(store, titles):
    adapter = StubAdapter({"1": {"score": 8}})
    assert SIMKL.status is SourceStatus.BLOCKED_SECRET
    with pytest.raises(IngestionRefused) as exc:
        Ingestor(store, SIMKL, adapter, dry_run=False).run(titles)
    assert "BLOCKED_SECRET" in str(exc.value)
    assert adapter.calls == []


def test_dry_run_writes_nothing(store, titles):
    adapter = StubAdapter({"1": {"score": 86, "votes": 100}})
    result = ingestor(store, adapter, dry_run=True).run(titles)
    assert result.counters.inserted == 1, "счётчики считают то, что произошло бы"
    assert store.count("unified_external_snapshots") == 0
    assert store.count("unified_external_current") == 0


def test_titles_without_the_needed_external_id_are_not_requested(store, registry):
    registry.upsert(
        CanonicalTitle(title_id="nova:t-009", title_ru="Без идентификаторов", release_year=2020)
    )
    adapter = StubAdapter({})
    result = ingestor(store, adapter).run([registry.get("nova:t-009")])
    assert result.status == "NOTHING_TO_DO"
    assert adapter.calls == []
