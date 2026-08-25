"""Статусы (ТЗ §14) и organic_daily_unique (ТЗ §2)."""
from datetime import date, timedelta

import pytest

from seo_operator.metrics import north_star as ns
from seo_operator.statuses import (THOUSANDS_SEPARATOR, Confidence, ExperimentOutcome,
                                   Measurement, Status, blocked, data_delay, inconclusive,
                                   measured, not_measured)


# --- Measurement запрещает подмену отсутствия данных числом ---------------------

@pytest.mark.parametrize("status", [
    Status.NOT_MEASURED, Status.DATA_DELAY, Status.INCONCLUSIVE,
    Status.FAILED, Status.BLOCKED_ACCESS, Status.BLOCKED_SECRET,
    Status.BLOCKED_RIGHTS, Status.BLOCKED_OWNER_DECISION, Status.BLOCKED_DEPLOYMENT,
])
def test_no_value_status_cannot_carry_a_number(status):
    with pytest.raises(ValueError, match="не заменяется числом"):
        Measurement(metric="m", value=0, status=status, source="s", period="p", as_of="a")


def test_ready_requires_a_value():
    with pytest.raises(ValueError, match="требует значения"):
        Measurement(metric="m", value=None, status=Status.READY, source="s", period="p", as_of="a")


def test_measured_render_carries_provenance():
    m = measured("clicks", 12345, "yandex_metrika", "2026-07-01..2026-07-28", "2026-07-28",
                 unit="уник./сут")
    text = m.render()
    # Разряды разделяются неразрывным пробелом намеренно (statuses.THOUSANDS_SEPARATOR).
    assert f"12{THOUSANDS_SEPARATOR}345" in text
    assert "yandex_metrika" in text and "2026-07-01..2026-07-28" in text and "2026-07-28" in text


def test_unmeasured_render_shows_status_not_zero():
    assert not_measured("clicks", "счётчик не подключён").render().startswith("NOT_MEASURED")
    assert "0" not in not_measured("clicks", "счётчик не подключён").render()


def test_blocked_rejects_non_blocked_status():
    with pytest.raises(ValueError):
        blocked("m", Status.READY, "reason")


def test_status_vocabulary_matches_spec():
    expected = {"READY", "RUNNING", "BLOCKED_ACCESS", "BLOCKED_SECRET", "BLOCKED_DEPLOYMENT",
                "BLOCKED_RIGHTS", "BLOCKED_OWNER_DECISION", "DATA_DELAY", "NOT_MEASURED",
                "INCONCLUSIVE", "FAILED", "ROLLED_BACK"}
    assert {s.value for s in Status} == expected


def test_experiment_outcomes_match_spec():
    assert {o.value for o in ExperimentOutcome} == {
        "WIN", "LOSS", "NEUTRAL", "INCONCLUSIVE", "INVALIDATED", "ROLLED_BACK"}


# --- organic_daily_unique -------------------------------------------------------

def _points(site: str, days: int, per_day: int, end: date,
            engine: ns.Engine = ns.Engine.YANDEX, completeness: float = 1.0,
            bot_filtered: bool = True) -> list[ns.DayPoint]:
    return [ns.DayPoint(site_id=site, day=end - timedelta(days=i), engine=engine,
                        unique_visitors=per_day, completeness=completeness,
                        source="yandex_metrika", is_bot_filtered=bot_filtered)
            for i in range(days)]


def test_median_needs_28_full_days():
    end = date(2026, 8, 20)
    m, used, _ = ns.median_28(_points("s1", 20, 1000, end), "s1", date(2026, 8, 21))
    assert m.status is Status.DATA_DELAY
    assert m.value is None
    assert used == 20


def test_median_over_28_full_days():
    end = date(2026, 8, 20)
    m, used, newest = ns.median_28(_points("s1", 28, 1000, end), "s1", date(2026, 8, 21))
    assert m.measured and m.value == 1000 and used == 28 and newest == end


def test_incomplete_days_are_not_mixed_with_full_ones():
    """Неполный день не должен занижать медиану."""
    end = date(2026, 8, 20)
    pts = _points("s1", 28, 1000, end)
    pts.append(ns.DayPoint("s1", end + timedelta(days=1), ns.Engine.YANDEX, 12, 0.2,
                           "yandex_metrika"))
    m, used, newest = ns.median_28(pts, "s1", date(2026, 8, 22))
    assert m.value == 1000, "Неполный день попал в расчёт"
    assert newest == end and used == 28


def test_bot_traffic_is_excluded():
    end = date(2026, 8, 20)
    pts = _points("s1", 28, 1000, end, bot_filtered=False)
    m, _, _ = ns.median_28(pts, "s1", date(2026, 8, 21))
    assert m.status is Status.NOT_MEASURED


def test_no_data_is_not_measured_not_zero():
    m, _, _ = ns.median_28([], "s1", date(2026, 8, 21))
    assert m.status is Status.NOT_MEASURED and m.value is None


def test_engines_are_reported_separately():
    end = date(2026, 8, 20)
    pts = _points("s1", 28, 700, end, ns.Engine.YANDEX) + \
          _points("s1", 28, 300, end, ns.Engine.GOOGLE)
    engines = ns.by_engine(pts, "s1", date(2026, 8, 21))
    assert engines[ns.Engine.YANDEX].value == 700
    assert engines[ns.Engine.GOOGLE].value == 300
    assert engines[ns.Engine.OTHER].status is Status.NOT_MEASURED


def test_daily_total_sums_engines_within_a_day():
    end = date(2026, 8, 20)
    pts = _points("s1", 28, 700, end, ns.Engine.YANDEX) + \
          _points("s1", 28, 300, end, ns.Engine.GOOGLE)
    m, _, _ = ns.median_28(pts, "s1", date(2026, 8, 21))
    assert m.value == 1000


@pytest.mark.parametrize("source", ["paid", "direct", "referral", "internal", "bot", "social"])
def test_non_organic_sources_are_excluded(source):
    assert ns.validate_source_excluded(source)


def test_organic_source_is_not_excluded():
    assert not ns.validate_source_excluded("organic")


# --- портфель и дедупликация ----------------------------------------------------

def _portfolio(n: int, per_day: int, end: date) -> dict[str, list[ns.DayPoint]]:
    return {f"site-{i}": _points(f"site-{i}", 28, per_day, end) for i in range(n)}


def test_sum_is_not_called_unique_audience_without_dedup():
    end = date(2026, 8, 20)
    p = ns.portfolio_north_star(_portfolio(3, 1000, end), date(2026, 8, 21),
                                dedup_mode=ns.DedupMode.NONE)
    assert p.sum_of_counters.value == 3000
    assert p.deduplicated.status is Status.NOT_MEASURED
    assert "уникальной аудиторией портфеля" in p.caveat
    assert p.headline is p.sum_of_counters


def test_estimated_overlap_is_subtracted_and_labelled():
    end = date(2026, 8, 20)
    p = ns.portfolio_north_star(_portfolio(3, 1000, end), date(2026, 8, 21),
                                dedup_mode=ns.DedupMode.ESTIMATED, overlap_share=0.2)
    assert p.deduplicated.value == 2400
    assert "оценка" in p.deduplicated.note.lower()
    assert p.headline is p.deduplicated


def test_exact_dedup_allows_unique_audience_claim():
    end = date(2026, 8, 20)
    p = ns.portfolio_north_star(_portfolio(2, 1000, end), date(2026, 8, 21),
                                dedup_mode=ns.DedupMode.EXACT)
    assert p.deduplicated.value == 2000
    assert "уникальной аудиторией портфеля" in p.caveat


def test_invalid_overlap_share_rejected():
    end = date(2026, 8, 20)
    with pytest.raises(ValueError):
        ns.portfolio_north_star(_portfolio(2, 1000, end), date(2026, 8, 21),
                                dedup_mode=ns.DedupMode.ESTIMATED, overlap_share=1.5)


def test_portfolio_with_no_measurable_sites_is_not_measured():
    end = date(2026, 8, 20)
    partial = {"s1": _points("s1", 5, 1000, end)}
    p = ns.portfolio_north_star(partial, date(2026, 8, 21))
    assert p.sum_of_counters.status is Status.NOT_MEASURED
    assert "не измерен" in p.caveat


def test_partially_measured_portfolio_reports_how_many_counted():
    end = date(2026, 8, 20)
    sites = _portfolio(3, 1000, end)
    sites["site-unmeasured"] = _points("site-unmeasured", 4, 500, end)
    p = ns.portfolio_north_star(sites, date(2026, 8, 21))
    assert p.sum_of_counters.value == 3000
    assert "3 из 4" in p.sum_of_counters.period
