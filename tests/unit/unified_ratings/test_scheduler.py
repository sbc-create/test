"""Расписание: тиры, подстройка интервала, пауза, ограниченные повторы."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from factory.unified_ratings.scheduler import (
    MAX_FAILURE_STREAK,
    TIER_POLICY,
    Scheduler,
    Tier,
    classify,
)
from factory.unified_ratings.titles import CanonicalTitle

NOW = datetime(2026, 9, 21, 12, 0, 0, tzinfo=timezone.utc)


def title(year: int | None, title_id: str = "nova:t-001") -> CanonicalTitle:
    return CanonicalTitle(title_id=title_id, release_year=year, title_ru="Тайтл")


@pytest.fixture
def scheduler(store, seeded) -> Scheduler:
    return Scheduler(store)


# ---------------------------------------------------------------------------
# тиры
# ---------------------------------------------------------------------------


def test_airing_titles_are_checked_daily():
    assert classify(title(2026), now=NOW) is Tier.ONGOING
    assert TIER_POLICY[Tier.ONGOING].base_hours == 24


def test_recently_finished_weekly():
    assert classify(title(2025), now=NOW) is Tier.RECENT_FINISHED
    assert TIER_POLICY[Tier.RECENT_FINISHED].base_hours == 24 * 7


def test_archive_monthly():
    assert classify(title(1998), now=NOW) is Tier.ARCHIVE
    assert TIER_POLICY[Tier.ARCHIVE].base_hours == 24 * 30


def test_unknown_year_is_treated_as_archive():
    assert classify(title(None), now=NOW) is Tier.ARCHIVE


def test_explicit_ongoing_flag_wins_over_year():
    assert classify(title(2001), now=NOW, is_ongoing=True) is Tier.ONGOING


# ---------------------------------------------------------------------------
# постановка в расписание
# ---------------------------------------------------------------------------


def test_enrolling_sets_the_tier_interval(scheduler):
    plan = scheduler.enroll(title=title(1998), source_key="anilist", now=NOW)
    assert plan["tier"] == "ARCHIVE"
    assert plan["interval_hours"] == 24 * 30


def test_nothing_is_due_before_its_time(scheduler):
    scheduler.enroll(title=title(2026), source_key="anilist", now=NOW)
    assert scheduler.due(source_key="anilist", limit=10, now=NOW) == []
    later = NOW + timedelta(hours=25)
    assert scheduler.due(source_key="anilist", limit=10, now=later) == ["nova:t-001"]


# ---------------------------------------------------------------------------
# подстройка
# ---------------------------------------------------------------------------


def test_unchanged_pushes_the_next_check_out(scheduler):
    scheduler.enroll(title=title(2026), source_key="anilist", now=NOW)
    first = scheduler.observe(title_id="nova:t-001", source_key="anilist", outcome="unchanged",
                              now=NOW)
    assert first["interval_hours"] > 24
    assert first["unchanged_streak"] == 1
    second = scheduler.observe(title_id="nova:t-001", source_key="anilist", outcome="unchanged",
                               now=NOW)
    assert second["interval_hours"] >= first["interval_hours"]
    assert second["unchanged_streak"] == 2


def test_a_real_change_pulls_the_next_check_in(scheduler):
    scheduler.enroll(title=title(2026), source_key="anilist", now=NOW)
    scheduler.observe(title_id="nova:t-001", source_key="anilist", outcome="unchanged", now=NOW)
    changed = scheduler.observe(title_id="nova:t-001", source_key="anilist", outcome="changed",
                                now=NOW)
    assert changed["interval_hours"] < 36
    assert changed["unchanged_streak"] == 0
    assert changed["failure_streak"] == 0


def test_adaptation_stays_inside_the_tier_bounds(scheduler):
    scheduler.enroll(title=title(1998), source_key="anilist", now=NOW)
    policy = TIER_POLICY[Tier.ARCHIVE]
    for _ in range(20):
        state = scheduler.observe(
            title_id="nova:t-001", source_key="anilist", outcome="unchanged", now=NOW
        )
    assert state["interval_hours"] <= policy.max_hours
    for _ in range(20):
        state = scheduler.observe(
            title_id="nova:t-001", source_key="anilist", outcome="changed", now=NOW
        )
    assert state["interval_hours"] >= policy.min_hours


def test_failures_push_out_harder_and_are_counted(scheduler):
    scheduler.enroll(title=title(2026), source_key="anilist", now=NOW)
    state = scheduler.observe(title_id="nova:t-001", source_key="anilist", outcome="failed",
                              now=NOW)
    assert state["failure_streak"] == 1
    assert state["interval_hours"] >= 48


def test_repeated_failures_stop_the_retries(scheduler):
    scheduler.enroll(title=title(2026), source_key="anilist", now=NOW)
    for _ in range(MAX_FAILURE_STREAK):
        state = scheduler.observe(
            title_id="nova:t-001", source_key="anilist", outcome="failed", now=NOW
        )
    assert state["exhausted"] is True
    far_future = NOW + timedelta(days=365)
    assert scheduler.due(source_key="anilist", limit=10, now=far_future) == []


def test_unknown_outcome_is_refused(scheduler):
    scheduler.enroll(title=title(2026), source_key="anilist", now=NOW)
    with pytest.raises(ValueError):
        scheduler.observe(title_id="nova:t-001", source_key="anilist", outcome="maybe", now=NOW)


def test_observing_an_unscheduled_pair_is_an_error(scheduler):
    with pytest.raises(KeyError):
        scheduler.observe(title_id="nova:nope", source_key="anilist", outcome="changed", now=NOW)


# ---------------------------------------------------------------------------
# пауза источника
# ---------------------------------------------------------------------------


def test_a_rate_limited_source_pauses_until_its_allowed_time(scheduler):
    scheduler.enroll(title=title(2026), source_key="anilist", now=NOW)
    resume_at = NOW + timedelta(hours=48)
    scheduler.pause_source(source_key="anilist", until=resume_at, reason="HTTP 429")
    # Срок проверки наступил, но пауза источника ещё действует.
    assert scheduler.due(source_key="anilist", limit=10, now=NOW + timedelta(hours=25)) == []
    # После разрешённого времени тайтл возвращается в очередь сам.
    assert scheduler.due(source_key="anilist", limit=10, now=NOW + timedelta(hours=49)) == [
        "nova:t-001"
    ]


def test_resuming_a_source_returns_it_to_the_queue(scheduler):
    scheduler.enroll(title=title(2026), source_key="anilist", now=NOW)
    scheduler.pause_source(source_key="anilist", until=NOW + timedelta(days=10), reason="429")
    scheduler.resume_source(source_key="anilist")
    assert scheduler.due(source_key="anilist", limit=10, now=NOW + timedelta(hours=25)) == [
        "nova:t-001"
    ]


def test_pausing_one_source_leaves_the_others_running(scheduler):
    scheduler.enroll(title=title(2026), source_key="anilist", now=NOW)
    scheduler.enroll(title=title(2026), source_key="kitsu", now=NOW)
    scheduler.pause_source(source_key="anilist", until=NOW + timedelta(days=7), reason="429")
    later = NOW + timedelta(hours=25)
    assert scheduler.due(source_key="anilist", limit=10, now=later) == []
    assert scheduler.due(source_key="kitsu", limit=10, now=later) == ["nova:t-001"]


# ---------------------------------------------------------------------------
# план
# ---------------------------------------------------------------------------


def test_plan_reports_sources_separately_and_denies_a_joint_sweep(scheduler):
    scheduler.enroll(title=title(2026, "nova:t-001"), source_key="anilist", now=NOW)
    scheduler.enroll(title=title(1998, "nova:t-002"), source_key="kitsu", now=NOW)
    plan = scheduler.plan(now=NOW)
    assert plan["concurrent_full_sweep"] is False
    assert set(plan["sources"]) == {"anilist", "kitsu"}
    assert plan["sources"]["anilist"]["tiers"]["ONGOING"]["titles"] == 1
    assert plan["sources"]["kitsu"]["tiers"]["ARCHIVE"]["titles"] == 1


def test_due_respects_the_limit(scheduler, registry):
    for i in range(5):
        registry.upsert(CanonicalTitle(title_id=f"nova:b-{i}", release_year=2026))
        scheduler.enroll(title=title(2026, f"nova:b-{i}"), source_key="anilist", now=NOW)
    later = NOW + timedelta(hours=25)
    assert len(scheduler.due(source_key="anilist", limit=2, now=later)) == 2
