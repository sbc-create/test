"""API модуля: CSRF, когорта записи, kill switch, изоляция площадок."""

from __future__ import annotations

import pytest

from factory.community.antifraud import AntifraudGuard
from factory.unified_ratings.api import ApiError, UnifiedRatingsApi

ORIGIN = "https://animedia.icu"
CSRF = "csrf-token-value"


@pytest.fixture
def api(community, seeded):
    seeded.map_tenant_subject(tenant_id="animedia", subject_id="a-002", title_id="nova:t-002")
    return UnifiedRatingsApi(community, write_cohort={"owner-1"}, public_write=False)


def put(api, *, actor="owner-1", score=8, subject="a-001", space="animedia",
        key="k1", origin=ORIGIN, csrf_header=CSRF, csrf_cookie=CSRF):
    return api.put_vote(
        space=space, subject_id=subject, actor_id=actor, score=score,
        idempotency_key=key, origin=origin, csrf_header=csrf_header, csrf_cookie=csrf_cookie,
    )


# ---------------------------------------------------------------------------
# чтение открыто, запись — нет
# ---------------------------------------------------------------------------


def test_reading_is_open_to_any_visitor(api):
    result = api.me(space="animedia", subject_id="a-001", actor_id="visitor", origin=ORIGIN)
    assert result["scale"] == "1-10"
    assert result["your_score"] is None
    assert result["write_enabled"] is False


def test_visitor_outside_cohort_cannot_vote(api):
    with pytest.raises(ApiError) as exc:
        put(api, actor="visitor")
    assert exc.value.status == 403
    assert exc.value.code == "NOT_IN_TEST_COHORT"


def test_cohort_member_can_vote(api):
    result = put(api, actor="owner-1", score=9)
    assert result["your_score"] == 9
    assert result["aggregate"]["vote_count"] == 1


def test_public_write_opens_voting_to_everyone(community, seeded):
    api = UnifiedRatingsApi(community, write_cohort=set(), public_write=True)
    assert put(api, actor="anyone")["your_score"] == 8


# ---------------------------------------------------------------------------
# CSRF и Origin
# ---------------------------------------------------------------------------


def test_missing_csrf_is_refused(api):
    with pytest.raises(ApiError) as exc:
        put(api, csrf_header=None)
    assert exc.value.code == "CSRF_FAILED"


def test_mismatched_csrf_is_refused(api):
    with pytest.raises(ApiError) as exc:
        put(api, csrf_header="one", csrf_cookie="another")
    assert exc.value.code == "CSRF_FAILED"


def test_foreign_origin_is_refused(api):
    with pytest.raises(ApiError) as exc:
        put(api, origin="https://evil.example")
    assert exc.value.code == "ORIGIN_MISMATCH"


def test_unknown_space_is_refused(api):
    with pytest.raises(ApiError) as exc:
        api.me(space="zona", subject_id="a-001", actor_id="v", origin=ORIGIN)
    assert exc.value.code == "UNKNOWN_SPACE"


def test_second_domain_is_not_served(api):
    """animedia.space на этом этапе не обслуживается вовсе."""
    with pytest.raises(ApiError) as exc:
        put(api, space="animedia_space")
    assert exc.value.code == "UNKNOWN_SPACE"


# ---------------------------------------------------------------------------
# значения и идемпотентность
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("score", [0, 11, -1, 8.5, "8.5", None, True])
def test_server_does_not_trust_the_score_from_the_client(api, score):
    with pytest.raises(ApiError) as exc:
        put(api, score=score, key=f"bad-{score!r}")
    assert exc.value.code == "INVALID_SCORE"


def test_idempotency_key_is_required(api):
    with pytest.raises(ApiError) as exc:
        put(api, key="")
    assert exc.value.code == "IDEMPOTENCY_REQUIRED"


def test_repeating_a_request_does_not_double_the_vote(api):
    put(api, key="same", score=7)
    result = put(api, key="same", score=7)
    assert result["aggregate"]["vote_count"] == 1


def test_client_cannot_send_title_id(api):
    import inspect

    assert "title_id" not in inspect.signature(api.put_vote).parameters


def test_unknown_subject_is_refused(api):
    with pytest.raises(ApiError) as exc:
        put(api, subject="does-not-exist")
    assert exc.value.status == 404


# ---------------------------------------------------------------------------
# изменение и отзыв
# ---------------------------------------------------------------------------


def test_change_and_retract(api):
    put(api, key="k1", score=4)
    changed = put(api, key="k2", score=9)
    assert changed["your_score"] == 9
    assert changed["aggregate"]["vote_count"] == 1
    removed = api.delete_vote(
        space="animedia", subject_id="a-001", actor_id="owner-1",
        idempotency_key="k3", origin=ORIGIN, csrf_header=CSRF, csrf_cookie=CSRF,
    )
    assert removed["your_score"] is None
    assert removed["aggregate"]["vote_count"] == 0
    assert removed["aggregate"]["average"] is None


def test_retract_also_requires_csrf_and_cohort(api):
    put(api, key="k1", score=4)
    with pytest.raises(ApiError) as exc:
        api.delete_vote(
            space="animedia", subject_id="a-001", actor_id="visitor",
            idempotency_key="k9", origin=ORIGIN, csrf_header=CSRF, csrf_cookie=CSRF,
        )
    assert exc.value.code == "NOT_IN_TEST_COHORT"


# ---------------------------------------------------------------------------
# kill switch
# ---------------------------------------------------------------------------


def test_kill_switch_stops_writes_but_not_reads(api):
    api.guard.set_kill_switch(True)
    with pytest.raises(ApiError) as exc:
        put(api)
    assert exc.value.status == 503
    assert exc.value.code == "KILL_SWITCH"
    assert api.me(space="animedia", subject_id="a-001", actor_id="v", origin=ORIGIN) is not None


def test_read_only_mode_stops_writes(api):
    api.guard.set_read_only(True)
    with pytest.raises(ApiError) as exc:
        put(api)
    assert exc.value.code == "READ_ONLY"


def test_health_reports_the_switches(api):
    health = api.health()
    assert health["public_write"] is False
    assert health["write_cohort_size"] == 1
    assert health["kill_switch"] is False


# ---------------------------------------------------------------------------
# изоляция между произведениями и площадками
# ---------------------------------------------------------------------------


def test_a_vote_on_one_subject_does_not_move_another(api):
    put(api, subject="a-001", score=10, key="k1")
    other = api.me(space="animedia", subject_id="a-002", actor_id="owner-1", origin=ORIGIN)
    assert other["your_score"] is None
    assert other["aggregate"] is None or other["aggregate"]["vote_count"] == 0


def test_votes_stay_inside_their_space(api, community):
    put(api, subject="a-001", score=10, key="k1")
    yummy = community.get_aggregate(
        scope_kind="tenant", scope_id="yummy", title_id="nova:t-001"
    )
    assert yummy is None or yummy.vote_count == 0


def test_guard_is_the_shared_one(api):
    assert isinstance(api.guard, AntifraudGuard)
