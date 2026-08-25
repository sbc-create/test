"""Прогноз количества сайтов (ТЗ §8) и Goal Planner (ТЗ §5 шаг 4)."""
from datetime import date

import pytest

from seo_operator.forecast import capacity as cap
from seo_operator.planner import (Category, IncompleteTask, Task, build_queue,
                                  compute_priority, default_evaluate_after, prioritize)
from seo_operator.statuses import Confidence, Status, measured, not_measured

AS_OF = "2026-08-20"


def _site(i: int, daily: int | None, age: int = 200, alive: bool = True,
          plateau: int | None = 150) -> cap.SiteFact:
    return cap.SiteFact(site_id=f"s{i}", direction="anime", age_days=age,
                        daily_unique=daily, is_alive=alive, days_to_plateau=plateau)


# --- перцентили и когорты -------------------------------------------------------

def test_percentiles_need_minimum_sample():
    sites = [_site(i, 1000) for i in range(3)]
    c = cap.cohort_stats(sites, 180, AS_OF)
    assert c.p50.status is Status.INCONCLUSIVE
    assert "< 5" in c.p50.note


def test_percentiles_computed_on_sufficient_sample():
    sites = [_site(i, v) for i, v in enumerate([100, 200, 300, 400, 500, 600, 700])]
    c = cap.cohort_stats(sites, 180, AS_OF)
    assert c.p25.measured and c.p50.value == 400 and c.p75.measured
    assert c.p25.value < c.p50.value < c.p75.value


def test_survival_rate_counts_dead_sites():
    sites = [_site(i, 1000) for i in range(6)] + [_site(99, None, alive=False)]
    c = cap.cohort_stats(sites, 180, AS_OF)
    assert c.survival_rate.value == pytest.approx(6 / 7, abs=0.01)


def test_unmeasured_sites_excluded_from_percentiles_but_not_survival():
    sites = [_site(i, 1000) for i in range(5)] + [_site(50, None)]
    c = cap.cohort_stats(sites, 180, AS_OF)
    assert c.measured == 5 and c.total == 6


# --- основной прогноз -----------------------------------------------------------

def test_forecast_inconclusive_without_mature_cohort():
    current = measured("organic_daily_unique", 50_000, "metrika", "28д", AS_OF)
    fc = cap.forecast([_site(0, 5000), _site(1, 6000)], current, AS_OF)
    assert all(s.required_new_sites.status is Status.INCONCLUSIVE for s in fc.scenarios)
    assert fc.required_range == "INCONCLUSIVE"
    assert any("Зрелых измеренных сайтов" in b for b in fc.blockers)


def test_forecast_inconclusive_when_current_not_measured():
    current = not_measured("organic_daily_unique", "счётчики не подключены")
    fc = cap.forecast([_site(i, 10_000) for i in range(10)], current, AS_OF)
    assert fc.gap.status is Status.NOT_MEASURED
    assert fc.required_range == "INCONCLUSIVE"
    assert any("разрыв до цели" in b.lower() for b in fc.blockers)


def test_three_scenarios_give_a_range_not_one_number():
    sites = [_site(i, v) for i, v in enumerate(
        [4_000, 6_000, 8_000, 10_000, 12_000, 14_000, 16_000, 18_000, 20_000, 25_000])]
    current = measured("organic_daily_unique", 133_000, "metrika", "28д", AS_OF)
    fc = cap.forecast(sites, current, AS_OF)

    assert all(s.required_new_sites.measured for s in fc.scenarios)
    needed = {s.scenario: int(s.required_new_sites.value) for s in fc.scenarios}
    # Пессимистичный сценарий требует БОЛЬШЕ сайтов, чем оптимистичный.
    assert needed[cap.Scenario.CONSERVATIVE] > needed[cap.Scenario.BASE] > needed[cap.Scenario.OPTIMISTIC]
    assert "-" in fc.required_range


def test_gap_is_target_minus_current():
    sites = [_site(i, 10_000) for i in range(10)]
    current = measured("organic_daily_unique", 1_000_000, "metrika", "28д", AS_OF)
    fc = cap.forecast(sites, current, AS_OF)
    assert fc.gap.value == 6_000_000


def test_gap_is_zero_when_target_reached():
    sites = [_site(i, 10_000) for i in range(10)]
    current = measured("organic_daily_unique", 8_000_000, "metrika", "28д", AS_OF)
    fc = cap.forecast(sites, current, AS_OF)
    assert fc.gap.value == 0 and "цель достигнута" in fc.gap.note


def test_reserve_domains_account_for_survival_rate():
    sites = [_site(i, 10_000) for i in range(8)] + [_site(90 + i, None, alive=False) for i in range(2)]
    current = measured("organic_daily_unique", 80_000, "metrika", "28д", AS_OF)
    fc = cap.forecast(sites, current, AS_OF)
    base = next(s for s in fc.scenarios if s.scenario is cap.Scenario.BASE)
    assert base.reserve_domains.measured
    # Выживает 80% => на N рабочих нужно больше запусков, значит резерв > 0.
    assert int(base.reserve_domains.value) > 0


def test_confidence_drops_on_small_sample():
    sites = [_site(i, 10_000) for i in range(6)]
    current = measured("organic_daily_unique", 60_000, "metrika", "28д", AS_OF)
    fc = cap.forecast(sites, current, AS_OF)
    assert all(s.confidence is Confidence.LOW for s in fc.scenarios)


def test_confidence_high_on_large_sample_with_plateau_data():
    sites = [_site(i, 10_000 + i * 500) for i in range(25)]
    current = measured("organic_daily_unique", 250_000, "metrika", "28д", AS_OF)
    fc = cap.forecast(sites, current, AS_OF)
    assert all(s.confidence is Confidence.HIGH for s in fc.scenarios)


def test_growth_without_new_sites_is_offered_as_alternative():
    sites = [_site(i, v) for i, v in enumerate([1_000, 2_000, 3_000, 4_000, 10_000, 10_000])]
    current = measured("organic_daily_unique", 30_000, "metrika", "28д", AS_OF)
    fc = cap.forecast(sites, current, AS_OF)
    assert fc.growth_without_new_sites.measured
    assert int(fc.growth_without_new_sites.value) > 0


def test_growth_alternative_inconclusive_on_small_portfolio():
    current = measured("organic_daily_unique", 3_000, "metrika", "28д", AS_OF)
    fc = cap.forecast([_site(0, 3_000)], current, AS_OF)
    assert fc.growth_without_new_sites.status is Status.INCONCLUSIVE


def test_capacity_note_states_when_owner_input_missing():
    current = measured("organic_daily_unique", 100_000, "metrika", "28д", AS_OF)
    fc = cap.forecast([_site(i, 10_000) for i in range(10)], current, AS_OF)
    assert "не задана владельцем" in fc.operational_capacity_note
    fc2 = cap.forecast([_site(i, 10_000) for i in range(10)], current, AS_OF,
                       operational_capacity_sites_per_month=5)
    assert "5 сайтов/мес" in fc2.operational_capacity_note


def test_cannibalization_risk_is_always_stated():
    current = measured("organic_daily_unique", 100_000, "metrika", "28д", AS_OF)
    fc = cap.forecast([_site(i, 10_000) for i in range(10)], current, AS_OF)
    assert "каннибализац" in fc.cannibalization_risk_note.lower()


def test_render_table_has_all_three_scenarios():
    current = measured("organic_daily_unique", 100_000, "metrika", "28д", AS_OF)
    fc = cap.forecast([_site(i, 10_000 + i * 100) for i in range(10)], current, AS_OF)
    table = cap.render_table(fc)
    for label in ("Консервативный", "Базовый", "Оптимистичный"):
        assert label in table
    assert "Уверенность" in table


# --- Goal Planner ---------------------------------------------------------------

def _task(task_id="TASK-1", category=Category.CONTENT, gain=100.0,
          confidence=Confidence.MEDIUM, effort=4.0, risk=2.0, days=14, fit=1.0) -> Task:
    return Task(
        task_id=task_id, site_id="s1", category=category,
        problem="Кластер теряет клики при стабильной позиции",
        hypothesis="Уточнение title повысит CTR на 15%",
        urls=["/page"], cluster="c1", baseline={"ctr": 0.02, "clicks": 120},
        expected_traffic_gain=gain, confidence=confidence, strategic_fit=fit,
        effort=effort, risk=risk, time_to_result_days=days,
        success_criterion="CTR +15% против контроля",
        failure_criterion="CTR -5%", stop_criterion="падение кликов > 20%",
        rollback_plan="вернуть прежний title из снапшота",
        evaluate_after="2026-09-10")


@pytest.mark.parametrize("field_name,value", [
    ("problem", ""), ("hypothesis", ""), ("success_criterion", ""),
    ("failure_criterion", ""), ("stop_criterion", ""), ("rollback_plan", ""),
])
def test_task_without_required_fields_is_rejected(field_name, value):
    t = _task()
    setattr(t, field_name, value)
    with pytest.raises(IncompleteTask):
        compute_priority(t)


def test_task_with_zero_effort_is_rejected():
    """Иначе приоритет уходит в бесконечность и выдавливает всё остальное."""
    with pytest.raises(IncompleteTask):
        compute_priority(_task(effort=0))


def test_task_without_baseline_is_rejected():
    t = _task()
    t.baseline = {}
    with pytest.raises(IncompleteTask):
        compute_priority(t)


def test_priority_grows_with_gain_and_confidence():
    low = compute_priority(_task(gain=100, confidence=Confidence.LOW))
    high = compute_priority(_task(gain=100, confidence=Confidence.HIGH))
    bigger = compute_priority(_task(gain=500, confidence=Confidence.HIGH))
    assert low < high < bigger


def test_priority_falls_with_effort_risk_and_time():
    cheap = compute_priority(_task(effort=1, risk=1, days=7))
    costly = compute_priority(_task(effort=10, risk=5, days=90))
    assert costly < cheap


def test_prioritize_sorts_descending():
    tasks = [_task("a", gain=10), _task("b", gain=1000), _task("c", gain=100)]
    assert [t.task_id for t in prioritize(tasks)] == ["b", "c", "a"]


def test_queue_reserves_capacity_for_technical_health():
    """Косметика с высоким приоритетом не должна вытеснять техдолг."""
    cosmetic = [_task(f"ctr{i}", Category.CTR, gain=5000, effort=0.5, risk=1, days=7)
                for i in range(20)]
    technical = [_task(f"tech{i}", Category.TECHNICAL_HEALTH, gain=50, effort=8, risk=3, days=30)
                 for i in range(5)]
    q = build_queue(cosmetic + technical, capacity=10)
    assert any(t.category is Category.TECHNICAL_HEALTH for t in q.selected)
    assert q.balance.get("technical_health", 0) >= 2


def test_queue_warns_when_skewed_to_cosmetics():
    cosmetic = [_task(f"ctr{i}", Category.CTR, gain=5000, effort=0.5, risk=1, days=7)
                for i in range(20)]
    q = build_queue(cosmetic, capacity=10)
    assert any("косметик" in w.lower() for w in q.warnings)
    assert any("технического здоровья" in w for w in q.warnings)


def test_queue_warns_when_a_category_has_no_tasks():
    only_content = [_task(f"c{i}", Category.CONTENT, gain=100) for i in range(10)]
    q = build_queue(only_content, capacity=10)
    assert any("пробел в диагностике" in w for w in q.warnings)


def test_queue_respects_capacity():
    tasks = [_task(f"t{i}", Category.CONTENT, gain=100 + i) for i in range(50)]
    q = build_queue(tasks, capacity=7)
    assert len(q.selected) == 7 and len(q.deferred) == 43


def test_queue_has_no_duplicates():
    tasks = ([_task(f"tech{i}", Category.TECHNICAL_HEALTH, gain=900) for i in range(5)]
             + [_task(f"c{i}", Category.CONTENT, gain=100) for i in range(10)])
    q = build_queue(tasks, capacity=10)
    ids = [t.task_id for t in q.selected]
    assert len(ids) == len(set(ids))


def test_zero_capacity_defers_everything():
    q = build_queue([_task()], capacity=0)
    assert q.selected == [] and len(q.deferred) == 1


def test_evaluate_after_includes_data_lag():
    d = default_evaluate_after(14, today=date(2026, 8, 22), data_lag_days=3)
    assert d == "2026-09-08"
