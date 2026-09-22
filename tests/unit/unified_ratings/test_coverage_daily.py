"""Покрытие, суточная квота и проекция витрины.

Главное, что здесь проверяется, — знаменатель. Строки источников,
внешние идентификаторы и произведения это три разные величины, и отчёт
обязан их различать: 5603 строки при 53 596 произведениях легко выдать
за десять процентов покрытия, хотя покрыто втрое меньше.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from factory.unified_ratings.coverage import CoverageReporter, classify_kind
from factory.unified_ratings.daily_queue import DAILY_TARGET, DailyQueue, Mode, Priority
from factory.unified_ratings.site_projection import build_flags, build_projection
from factory.unified_ratings.titles import CanonicalTitle, utc_now

NOW = datetime(2026, 9, 22, 12, 0, 0, tzinfo=timezone.utc)


def put_rating(store, *, title_id, source, normalized="8.0", state="OK", checked=NOW, votes=100):
    stamp = checked.strftime("%Y-%m-%dT%H:%M:%SZ")
    with store.write_tx() as conn:
        conn.execute(
            """INSERT INTO unified_external_snapshots(
                   title_id, source_key, external_id, raw_score, source_scale_min,
                   source_scale_max, normalization_formula, normalized_score, vote_count,
                   fetched_at, adapter_version, raw_payload_sha256, content_hash, validation_state)
               VALUES (?,?,?,'80','0','100','divide_10_from_0_100',?,?,?,'v','h',?,?)""",
            (title_id, source, f"{source}-{title_id}", normalized, votes, stamp,
             f"h-{source}-{title_id}", state),
        )
        sid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            """INSERT INTO unified_external_current(
                   title_id, source_key, snapshot_id, raw_score, source_scale_max,
                   normalized_score, vote_count, content_hash, validation_state,
                   fetched_at, last_checked_at, provenance_url)
               VALUES (?,?,?,'80','100',?,?,?,?,?,?,'')""",
            (title_id, source, sid, normalized, votes, f"h-{source}-{title_id}", state,
             stamp, stamp),
        )
        conn.execute(
            """INSERT INTO unified_source_links(
                   title_id, source_key, external_id, match_method, confidence, status,
                   created_at, updated_at)
               VALUES (?,?,?,'exact_external_id',1.0,'exact',?,?)""",
            (title_id, source, f"{source}-{title_id}", utc_now(), utc_now()),
        )


# ---------------------------------------------------------------------------
# знаменатель
# ---------------------------------------------------------------------------


def test_coverage_counts_titles_not_source_rows(store, seeded):
    put_rating(store, title_id="nova:t-001", source="anilist")
    put_rating(store, title_id="nova:t-001", source="kitsu")
    put_rating(store, title_id="nova:t-001", source="shikimori")
    report = CoverageReporter(store, now=NOW).report()
    catalog = report["slices"]["catalog"]
    assert catalog["titles_total"] == 2
    assert catalog["with_any_external_rating"]["count"] == 1, "три строки — одно произведение"
    assert catalog["distinct_counts"]["source_records"] == 3
    assert catalog["distinct_counts"]["ratings_with_value"] == 3
    assert catalog["distinct_counts"]["unique_titles"] == 2


def test_percent_is_taken_from_unique_titles(store, seeded):
    put_rating(store, title_id="nova:t-001", source="anilist")
    catalog = CoverageReporter(store, now=NOW).report()["slices"]["catalog"]
    assert catalog["with_any_external_rating"]["percent"] == 50.0


def test_two_plus_sources_is_counted_separately(store, seeded):
    put_rating(store, title_id="nova:t-001", source="anilist")
    put_rating(store, title_id="nova:t-001", source="kitsu")
    put_rating(store, title_id="nova:t-002", source="anilist")
    catalog = CoverageReporter(store, now=NOW).report()["slices"]["catalog"]
    assert catalog["with_any_external_rating"]["count"] == 2
    assert catalog["with_2plus_external_ratings"]["count"] == 1


def test_site_slice_uses_the_sites_own_denominator(store, seeded):
    put_rating(store, title_id="nova:t-001", source="anilist")
    report = CoverageReporter(store, now=NOW).report(site_slices={"animedia.icu": {"nova:t-001"}})
    site = report["slices"]["animedia.icu"]
    assert site["titles_total"] == 1
    assert site["with_any_external_rating"]["percent"] == 100.0
    assert report["slices"]["catalog"]["with_any_external_rating"]["percent"] == 50.0


def test_absent_rating_is_not_counted_as_covered(store, seeded):
    put_rating(store, title_id="nova:t-001", source="anilist", state="ABSENT", normalized=None)
    catalog = CoverageReporter(store, now=NOW).report()["slices"]["catalog"]
    assert catalog["with_any_external_rating"]["count"] == 0
    assert catalog["without_any_rating"]["count"] == 2


def test_stale_records_are_reported(store, seeded):
    put_rating(store, title_id="nova:t-001", source="anilist", checked=NOW - timedelta(days=120))
    catalog = CoverageReporter(store, now=NOW).report()["slices"]["catalog"]
    assert catalog["stale_by_sla"]["count"] == 1


def test_titles_without_external_ids_are_reported(store, registry):
    registry.upsert(CanonicalTitle(title_id="nova:bare", title_ru="Без идентификаторов"))
    catalog = CoverageReporter(store, now=NOW).report()["slices"]["catalog"]
    assert catalog["without_external_ids"]["count"] == 1


@pytest.mark.parametrize(
    ("kind", "expected"),
    [("tv", "series"), ("movie", "movie"), ("ova", "ova"), ("special", "special"), ("", "unknown")],
)
def test_kind_classification(kind, expected):
    assert classify_kind(kind) == expected


# ---------------------------------------------------------------------------
# суточная квота
# ---------------------------------------------------------------------------


def test_queue_puts_site_titles_before_the_rest(store, seeded):
    queue = DailyQueue(store, site_title_ids={"nova:t-002"}, now=NOW)
    items = queue.build(limit=50)
    assert items, "очередь не должна быть пустой при непокрытом каталоге"
    site_first = [i for i in items if i.priority is Priority.SITE_TITLE_NO_RATING]
    assert site_first
    assert all(
        int(items[i].priority) <= int(items[i + 1].priority) for i in range(len(items) - 1)
    ), "очередь отсортирована по приоритету"


def test_backlog_counts_pairs_never_collected(store, seeded):
    queue = DailyQueue(store, now=NOW)
    before = queue.backlog_size()
    put_rating(store, title_id="nova:t-001", source="anilist")
    assert queue.backlog_size() == before - 1


def test_completed_counts_only_real_changes(store, seeded):
    """Снимок создаётся лишь при изменении содержимого — он и есть зачёт."""
    put_rating(store, title_id="nova:t-001", source="anilist")
    put_rating(store, title_id="nova:t-002", source="anilist")
    done = DailyQueue(store, now=NOW).completed_today()
    assert done["completed"] == 2
    assert done["titles_first_rating"] == 2


def test_checking_without_change_does_not_count(store, seeded):
    put_rating(store, title_id="nova:t-001", source="anilist")
    with store.write_tx() as conn:
        conn.execute(
            "UPDATE unified_external_current SET last_checked_at=?, unchanged_streak=5",
            (NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),),
        )
    assert DailyQueue(store, now=NOW).completed_today()["completed"] == 1, (
        "обновление времени проверки новых снимков не создаёт"
    )


def test_shortfall_is_explained_not_padded(store, seeded):
    report = DailyQueue(store, now=NOW).report()
    assert report.target == DAILY_TARGET == 500
    assert report.completed < report.target
    assert report.shortfall_reason, "недобор обязан быть объяснён"
    assert report.mode == Mode.FILL


def test_exhausted_backlog_switches_to_refresh_mode(store, registry):
    """Пустой каталог — backlog нулевой; выдумывать записи нельзя."""
    report = DailyQueue(store, now=NOW).report()
    assert report.pending_backlog == 0
    assert report.mode == Mode.REFRESH
    assert "backlog исчерпан" in report.shortfall_reason


def test_blocked_secret_source_is_named_in_the_report(store, seeded):
    report = DailyQueue(store, now=NOW).report()
    assert any("simkl" in s for s in report.blocked_sources)
    assert report.blocked_by_secret >= 1


def test_forecast_uses_actual_throughput_not_the_target(store, seeded):
    put_rating(store, title_id="nova:t-001", source="anilist")
    report = DailyQueue(store, now=NOW).report()
    if report.completed:
        expected = -(-report.pending_backlog // report.completed)
        assert report.estimated_days_remaining() == expected


# ---------------------------------------------------------------------------
# проекция витрины
# ---------------------------------------------------------------------------


def test_projection_keeps_sources_separate(store, seeded):
    put_rating(store, title_id="nova:t-001", source="anilist", normalized="8.0")
    put_rating(store, title_id="nova:t-001", source="kitsu", normalized="7.0")
    proj = build_projection(store, space="animedia", title_ids={"nova:t-001"})
    entry = proj["titles"]["t-001"]["animedia"]
    assert [e["source"] for e in entry["external"]] == ["anilist", "kitsu"]
    assert entry["composite"]["value"] == "7.5"
    assert entry["composite"]["source_count"] == 2


def test_projection_omits_composite_with_one_source(store, seeded):
    put_rating(store, title_id="nova:t-001", source="anilist")
    entry = build_projection(store, space="animedia", title_ids={"nova:t-001"})[
        "titles"
    ]["t-001"]["animedia"]
    assert "composite" not in entry
    assert len(entry["external"]) == 1


def test_projection_excludes_ambiguous_links(store, seeded):
    put_rating(store, title_id="nova:t-001", source="anilist")
    with store.write_tx() as conn:
        conn.execute(
            "UPDATE unified_source_links SET status='conflict' WHERE source_key='anilist'"
        )
    proj = build_projection(store, space="animedia", title_ids={"nova:t-001"})
    assert "t-001" not in proj["titles"], "спорное сопоставление не показывается"


def test_empty_cohort_means_nobody(store, seeded):
    put_rating(store, title_id="nova:t-001", source="anilist")
    proj = build_projection(store, space="animedia", title_ids={"nova:t-001"}, cohort=set())
    assert proj["titles"] == {}
    assert proj["cohort_size"] == 0


def test_projection_never_enables_itself(store, seeded):
    put_rating(store, title_id="nova:t-001", source="anilist")
    proj = build_projection(store, space="animedia", title_ids={"nova:t-001"})
    assert proj["public_read_enabled"] is False
    assert proj["public_write_enabled"] is False


def test_flags_default_to_write_disabled():
    flags = build_flags(space="animedia", cohort={"a"}, public_read=True, public_write=False)
    assert flags["RATINGS_PUBLIC_READ_ANIMEDIA"] == 1
    assert flags["RATINGS_PUBLIC_WRITE_ANIMEDIA"] == 0
    assert flags["PUBLIC_WRITE_ROLLOUT_PERCENT"] == 0
    assert flags["owner_test_access_only"] is True
    assert flags["allowlist"]["animedia"] == ["a"]


def test_community_and_editorial_stay_separate_in_the_projection(store, seeded, community):
    put_rating(store, title_id="nova:t-001", source="anilist", normalized="9.0")
    put_rating(store, title_id="nova:t-001", source="kitsu", normalized="9.0")
    community.registry.map_tenant_subject(
        tenant_id="animedia", subject_id="a-001", title_id="nova:t-001"
    )
    community.submit(
        tenant_id="animedia", subject_id="a-001", actor_id="a1", score=3, idempotency_key="k1"
    )
    entry = build_projection(store, space="animedia", title_ids={"nova:t-001"})[
        "titles"
    ]["t-001"]["animedia"]
    assert entry["composite"]["value"] == "9.0", "тройка зрителя не входит в сводную"
    assert entry["native"]["average"] == "3.00"
    assert entry["native"]["label"] == "Оценка зрителей"


def test_daily_payload_separates_the_run_from_the_day(store, seeded, tmp_path, monkeypatch):
    """«За прогон» и «за сутки» — разные числа под разными именами.

    Прогон, запущенный после полного бэкфилла, видит в ленте чужие
    пятьсот изменений. Если отчёт назовёт их своими, он объявит цель
    выполненной, не собрав ничего; если сравнит цель со своими двадцатью
    двумя, объявит недобор там, где сутки отработаны. Оба числа
    печатаются, и причина недобора считается от суточного.
    """
    import importlib.util

    from pathlib import Path

    repo = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location(
        "ur_daily", repo / "tools" / "unified_ratings_daily.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    source = (repo / "tools" / "unified_ratings_daily.py").read_text(encoding="utf-8")
    assert '"DAILY_COMPLETED": report.completed' in source
    assert '"DAILY_COMPLETED_THIS_RUN": achieved' in source
    assert '"DAILY_SHORTFALL_REASON": "" if report.met else report.shortfall_reason' in source
    assert "achieved >= args.target" not in source.split("payload = {")[1], (
        "причина недобора не должна считаться от счётчика одного прогона"
    )
