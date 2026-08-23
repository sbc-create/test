"""REQ-STATES: точные статусы и запрет произвольных переходов."""
import uuid

import pytest

from factory.errors import ALL_STATES, FAILURE_STATES, NON_RETRYABLE
from factory.state import TRANSITIONS, IllegalTransition, JobState


@pytest.fixture
def job():
    state = JobState.load_or_create(f"test-{uuid.uuid4().hex[:8]}", "pilot-local", "staging")
    yield state
    JobState.path_for(state.job_id).unlink(missing_ok=True)


def test_happy_path_staging(job):
    for target in ("VALIDATING", "READY", "BUILDING", "BUILT", "STAGING_DEPLOY", "STAGING_QA", "DONE"):
        job.transition(target)
    assert job.status == "DONE"
    assert len(job.history) == 7


def test_happy_path_production(job):
    for target in ("VALIDATING", "READY", "BUILDING", "BUILT", "AUTHORIZATION_CHECK",
                   "PRODUCTION_DEPLOY", "PRODUCTION_SMOKE", "MONITORING", "DONE"):
        job.transition(target)
    assert job.status == "DONE"


def test_staging_success_does_not_open_production(job):
    for target in ("VALIDATING", "READY", "BUILDING", "BUILT", "STAGING_DEPLOY", "STAGING_QA"):
        job.transition(target)
    assert not job.can_transition("PRODUCTION_DEPLOY"), "из STAGING_QA нельзя прыгнуть в production"
    assert job.can_transition("AUTHORIZATION_CHECK")


def test_illegal_transition_raises(job):
    job.transition("VALIDATING")
    with pytest.raises(IllegalTransition):
        job.transition("PRODUCTION_DEPLOY")


def test_unknown_status_rejected(job):
    with pytest.raises(ValueError):
        job.transition("SOMETHING_ELSE")


def test_state_survives_reload(job):
    job.transition("VALIDATING").transition("READY")
    job.checkpoint_at("validated")
    reloaded = JobState.load(job.job_id)
    assert reloaded.status == "READY" and reloaded.checkpoint == "validated"


def test_every_state_is_reachable_and_declared():
    declared = set(TRANSITIONS)
    assert declared == set(ALL_STATES), "все статусы обязаны иметь описанные переходы"
    for state, targets in TRANSITIONS.items():
        assert targets <= set(ALL_STATES), f"{state} ведёт в неизвестный статус"


def test_failure_states_are_terminal_for_the_run(job):
    job.transition("VALIDATING").transition("BLOCKED_INPUT")
    assert job.terminal
    assert job.can_transition("RECEIVED"), "исправленный вход запускается новым проходом"


def test_non_retryable_failures_are_declared():
    assert set(FAILURE_STATES) >= NON_RETRYABLE
    for state in ("BLOCKED_INPUT", "BLOCKED_LICENSE", "BLOCKED_RIGHTS", "BLOCKED_AUTHORIZATION", "BLOCKED_SEO"):
        assert state in NON_RETRYABLE, f"{state} нельзя ретраить: вход от этого не появится"
