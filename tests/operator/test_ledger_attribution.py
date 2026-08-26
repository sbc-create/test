"""Action Ledger и атрибуция изменений (difference-in-differences)."""
import sqlite3
from datetime import date, timedelta

import pytest

from seo_operator import attribution as attr
from seo_operator.ledger import (Action, ActionLedger, IncompleteAction, LedgerImmutable,
                                 new_action_id)
from seo_operator.statuses import Confidence, ExperimentOutcome, Status


# ============================ Action Ledger ============================

@pytest.fixture()
def ledger():
    return ActionLedger(sqlite3.connect(":memory:"))


def _action(action_id="ACT-20260822-s1-0001", **kw):
    base = dict(
        action_id=action_id, site_id="s1", urls=["/page"], action_type="title_update",
        hypothesis="Уточнение title повысит CTR", expected_effect="+15% CTR за 14 дней",
        baseline={"ctr": 0.02, "clicks": 120}, success_criterion="CTR +15%",
        failure_criterion="CTR -5%", stop_criterion="клики -20%",
        risk="низкий, обратимо", rollback_plan="вернуть title из снапшота",
        executor="seo-operator", evaluate_after="2026-09-10")
    base.update(kw)
    return Action(**base)


@pytest.mark.parametrize("field_name", [
    "hypothesis", "expected_effect", "success_criterion",
    "failure_criterion", "stop_criterion", "risk", "rollback_plan",
])
def test_action_without_required_field_is_rejected(ledger, field_name):
    with pytest.raises(IncompleteAction):
        ledger.record(_action(**{field_name: ""}))


def test_action_without_baseline_is_rejected(ledger):
    with pytest.raises(IncompleteAction, match="baseline"):
        ledger.record(_action(baseline={}))


def test_action_without_urls_is_rejected(ledger):
    with pytest.raises(IncompleteAction):
        ledger.record(_action(urls=[]))


def test_action_with_bad_evaluate_date_is_rejected(ledger):
    with pytest.raises(IncompleteAction):
        ledger.record(_action(evaluate_after="скоро"))


def test_valid_action_is_recorded(ledger):
    ledger.record(_action())
    row = ledger.get("ACT-20260822-s1-0001")
    assert row["hypothesis"] and row["status"] == Status.READY.value


def test_execution_links_commit_and_release(ledger):
    ledger.record(_action())
    ledger.mark_executed("ACT-20260822-s1-0001", commit_sha="abc1234", release_id="rel-7")
    row = ledger.get("ACT-20260822-s1-0001")
    assert row["commit_sha"] == "abc1234" and row["release_id"] == "rel-7"
    assert row["executed_at"] and row["status"] == Status.RUNNING.value


def test_hypothesis_frozen_after_execution(ledger):
    """Иначе гипотезу можно подогнать под уже полученный результат."""
    ledger.record(_action())
    ledger.mark_executed("ACT-20260822-s1-0001", "abc", "rel-1")
    with pytest.raises(LedgerImmutable, match="заморожено"):
        ledger.amend("ACT-20260822-s1-0001", "hypothesis", "на самом деле другое", "подгонка")


def test_amendment_before_execution_is_allowed_and_logged(ledger):
    ledger.record(_action())
    ledger.amend("ACT-20260822-s1-0001", "hypothesis", "уточнённая гипотеза", "новая вводная")
    assert ledger.get("ACT-20260822-s1-0001")["hypothesis"] == "уточнённая гипотеза"
    amendments = ledger.amendments("ACT-20260822-s1-0001")
    assert len(amendments) == 1 and amendments[0]["reason"] == "новая вводная"


def test_non_frozen_field_can_be_amended_after_execution(ledger):
    ledger.record(_action())
    ledger.mark_executed("ACT-20260822-s1-0001", "abc", "rel-1")
    ledger.amend("ACT-20260822-s1-0001", "risk", "средний", "переоценка после выкладки")
    assert ledger.get("ACT-20260822-s1-0001")["risk"] == "средний"


def test_losses_are_recorded_not_hidden(ledger):
    ledger.record(_action())
    ledger.mark_executed("ACT-20260822-s1-0001", "abc", "rel-1")
    ledger.close("ACT-20260822-s1-0001", ExperimentOutcome.LOSS, Confidence.HIGH,
                 "CTR упал на 12%")
    row = ledger.get("ACT-20260822-s1-0001")
    assert row["outcome"] == "LOSS" and row["outcome_confidence"] == "HIGH"
    assert ledger.outcomes_summary()["LOSS"] == 1


def test_due_for_evaluation_lists_only_executed_and_ripe(ledger):
    ledger.record(_action("ACT-1", evaluate_after="2026-08-01"))
    ledger.mark_executed("ACT-1", "a", "r")
    ledger.record(_action("ACT-2", evaluate_after="2026-12-01"))
    ledger.mark_executed("ACT-2", "b", "r")
    ledger.record(_action("ACT-3", evaluate_after="2026-08-01"))   # не исполнено
    due = [r["action_id"] for r in ledger.due_for_evaluation(date(2026, 8, 22))]
    assert due == ["ACT-1"]


def test_actions_in_window_supports_change_analysis(ledger):
    ledger.record(_action("ACT-1"))
    ledger.mark_executed("ACT-1", "a", "r", executed_at="2026-08-10T09:00:00+00:00")
    ledger.record(_action("ACT-2"))
    ledger.mark_executed("ACT-2", "b", "r", executed_at="2026-07-01T09:00:00+00:00")
    found = ledger.actions_in_window("s1", date(2026, 8, 5), date(2026, 8, 15))
    assert [r["action_id"] for r in found] == ["ACT-1"]


def test_measurable_share_excludes_inconclusive(ledger):
    for i, outcome in enumerate([ExperimentOutcome.WIN, ExperimentOutcome.LOSS,
                                 ExperimentOutcome.INCONCLUSIVE, ExperimentOutcome.INVALIDATED]):
        ledger.record(_action(f"ACT-{i}"))
        ledger.mark_executed(f"ACT-{i}", "a", "r")
        ledger.close(f"ACT-{i}", outcome, Confidence.MEDIUM, "d")
    assert ledger.measurable_share() == 0.5


def test_measurable_share_none_without_closed_actions(ledger):
    assert ledger.measurable_share() is None


def test_action_id_format():
    assert new_action_id("s1", 7, date(2026, 8, 22)) == "ACT-20260822-s1-0007"


# ============================ Атрибуция ============================

def _series(name: str, start: date, days: int, value_fn) -> attr.Series:
    return attr.Series(name=name, points={start + timedelta(days=i): float(value_fn(i))
                                          for i in range(days)})


CHANGE = date(2026, 8, 1)
TODAY = date(2026, 8, 20)


def test_short_window_gives_inconclusive():
    t = _series("t", CHANGE - timedelta(days=3), 6, lambda i: 100)
    r = attr.analyze(treatment=t, control=None, change_date=CHANGE, today=TODAY)
    assert r.outcome is ExperimentOutcome.INCONCLUSIVE and r.method is attr.Method.NONE


def test_before_after_never_claims_causation():
    """Рост после действия без контроля не является доказательством."""
    t = _series("t", CHANGE - timedelta(days=14), 28, lambda i: 100 if i < 14 else 140)
    r = attr.analyze(treatment=t, control=None, change_date=CHANGE, today=TODAY)
    assert r.method is attr.Method.BEFORE_AFTER
    assert r.confidence is Confidence.LOW
    assert not r.causal_claim_allowed
    assert "причинная связь не утверждается" in r.phrase()


def test_diff_in_diff_removes_seasonality():
    """Одинаковый рост в treatment и control — это сезон, а не эффект."""
    rise = lambda i: 100 if i < 14 else 140
    t = _series("t", CHANGE - timedelta(days=14), 28, rise)
    c = _series("c", CHANGE - timedelta(days=14), 28, rise)
    r = attr.analyze(treatment=t, control=c, change_date=CHANGE, today=TODAY)
    assert r.method is attr.Method.DIFF_IN_DIFF
    assert abs(r.lift_pct) < 0.01
    assert r.outcome is ExperimentOutcome.NEUTRAL


def test_diff_in_diff_detects_real_lift_and_allows_causal_claim():
    t = _series("t", CHANGE - timedelta(days=14), 28, lambda i: 100 if i < 14 else 150)
    c = _series("c", CHANGE - timedelta(days=14), 28, lambda i: 100 if i < 14 else 105)
    r = attr.analyze(treatment=t, control=c, change_date=CHANGE, today=TODAY)
    assert r.outcome is ExperimentOutcome.WIN
    assert r.confidence is Confidence.HIGH
    assert r.causal_claim_allowed
    assert "Действие дало" in r.phrase()


def test_diff_in_diff_detects_loss():
    t = _series("t", CHANGE - timedelta(days=14), 28, lambda i: 100 if i < 14 else 80)
    c = _series("c", CHANGE - timedelta(days=14), 28, lambda i: 100)
    r = attr.analyze(treatment=t, control=c, change_date=CHANGE, today=TODAY)
    assert r.outcome is ExperimentOutcome.LOSS


def test_hard_confounder_invalidates_experiment():
    t = _series("t", CHANGE - timedelta(days=14), 28, lambda i: 100 if i < 14 else 150)
    c = _series("c", CHANGE - timedelta(days=14), 28, lambda i: 100)
    r = attr.analyze(treatment=t, control=c, change_date=CHANGE, today=TODAY,
                     confounders=[attr.Confounder("outage", "сайт лежал 3 дня", "hard")])
    assert r.outcome is ExperimentOutcome.INVALIDATED
    assert "не делается" in r.phrase()


def test_soft_confounder_lowers_confidence():
    t = _series("t", CHANGE - timedelta(days=14), 28, lambda i: 100 if i < 14 else 150)
    c = _series("c", CHANGE - timedelta(days=14), 28, lambda i: 100)
    r = attr.analyze(treatment=t, control=c, change_date=CHANGE, today=TODAY,
                     confounders=[attr.Confounder("algo", "обновление алгоритма", "soft")])
    assert r.confidence is Confidence.MEDIUM
    assert not r.causal_claim_allowed


def test_data_lag_excludes_incomplete_tail():
    t = _series("t", CHANGE - timedelta(days=14), 28, lambda i: 100)
    r = attr.analyze(treatment=t, control=None, change_date=CHANGE, today=TODAY, lag_days=3)
    assert r.observations["after_days"] <= 14


def test_simultaneous_actions_are_not_separable():
    actions = [{"action_id": "A1", "action_type": "title", "executed_at": "2026-07-30T10:00:00",
                "hypothesis": "h1"},
               {"action_id": "A2", "action_type": "links", "executed_at": "2026-07-31T10:00:00",
                "hypothesis": "h2"}]
    linked = attr.link_to_actions(CHANGE, actions)
    assert len(linked) == 2
    assert all(not c["separable"] for c in linked)
    assert all("не определяется" in c["note"] for c in linked)


def test_single_action_is_separable():
    actions = [{"action_id": "A1", "action_type": "title", "executed_at": "2026-07-30T10:00:00",
                "hypothesis": "h1"}]
    linked = attr.link_to_actions(CHANGE, actions)
    assert linked[0]["separable"]
