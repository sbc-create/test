"""Пользовательские оценки: create/update/retract, идемпотентность, изоляция."""

from __future__ import annotations

import contextlib
import threading

import pytest

from factory.unified_ratings.community import (
    NETWORK_RULE,
    CommunityRatings,
    UnknownSubject,
    VoteRejected,
)


def submit(community: CommunityRatings, *, actor="actor-1", score=8, key=None, tenant="yummy",
           subject="s-001"):
    return community.submit(
        tenant_id=tenant,
        subject_id=subject,
        actor_id=actor,
        score=score,
        idempotency_key=key or f"{actor}-{subject}-{score}",
    )


# ---------------------------------------------------------------------------
# create / update / retract
# ---------------------------------------------------------------------------


def test_create_vote(community):
    result = submit(community, score=8)
    assert result["your_score"] == 8
    assert result["title_id"] == "nova:t-001"
    assert result["aggregate"]["vote_count"] == 1
    assert result["aggregate"]["average"] == "8.00"
    assert result["aggregate"]["distribution"]["8"] == 1


def test_update_replaces_the_active_vote(community):
    submit(community, score=8, key="k1")
    result = submit(community, score=5, key="k2")
    assert result["your_score"] == 5
    assert result["aggregate"]["vote_count"] == 1
    assert result["aggregate"]["vote_sum"] == 5
    assert result["aggregate"]["distribution"]["8"] == 0
    assert result["aggregate"]["distribution"]["5"] == 1


def test_retract_removes_the_vote_from_the_aggregate(community):
    submit(community, score=9, key="k1")
    result = community.retract(
        tenant_id="yummy", subject_id="s-001", actor_id="actor-1", idempotency_key="k-del"
    )
    assert result["your_score"] is None
    assert result["aggregate"]["vote_count"] == 0
    # Отсутствие оценок — не ноль.
    assert result["aggregate"]["average"] is None


def test_retract_keeps_the_audit_trail(community):
    submit(community, score=9, key="k1")
    community.retract(
        tenant_id="yummy", subject_id="s-001", actor_id="actor-1", idempotency_key="k-del"
    )
    events = community.votes.store.conn.execute(
        "SELECT action FROM community_vote_events ORDER BY created_at"
    ).fetchall()
    actions = [e["action"] for e in events]
    assert "CREATE" in actions
    assert "DELETE" in actions


def test_my_vote_reflects_current_state(community):
    assert community.my_vote(tenant_id="yummy", subject_id="s-001", actor_id="actor-1") is None
    submit(community, score=7, key="k1")
    assert community.my_vote(tenant_id="yummy", subject_id="s-001", actor_id="actor-1") == 7
    community.retract(
        tenant_id="yummy", subject_id="s-001", actor_id="actor-1", idempotency_key="k-del"
    )
    assert community.my_vote(tenant_id="yummy", subject_id="s-001", actor_id="actor-1") is None


# ---------------------------------------------------------------------------
# идемпотентность и дубликаты
# ---------------------------------------------------------------------------


def test_repeating_the_same_request_does_not_create_a_second_vote(community):
    first = submit(community, score=8, key="same-key")
    second = submit(community, score=8, key="same-key")
    assert first["aggregate"]["vote_count"] == 1
    assert second["aggregate"]["vote_count"] == 1
    events = community.votes.store.conn.execute(
        "SELECT COUNT(*) AS n FROM community_vote_events"
    ).fetchone()
    assert events["n"] == 1


def test_same_key_with_a_different_payload_is_a_conflict(community):
    from factory.community.service import CommunityConflict

    submit(community, score=8, key="same-key")
    with pytest.raises(CommunityConflict):
        submit(community, score=3, key="same-key")


def test_idempotency_key_is_required(community):
    with pytest.raises(VoteRejected):
        community.submit(
            tenant_id="yummy", subject_id="s-001", actor_id="a", score=8, idempotency_key=""
        )


# ---------------------------------------------------------------------------
# сервер не доверяет интерфейсу
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("score", [0, 11, -1, 8.5, "8.5", "", None, True])
def test_invalid_scores_never_reach_the_ledger(community, score):
    with pytest.raises(VoteRejected):
        submit(community, score=score, key=f"bad-{score!r}")
    assert community.votes.store.conn.execute(
        "SELECT COUNT(*) AS n FROM community_vote_events"
    ).fetchone()["n"] == 0


def test_voting_for_an_unknown_subject_is_refused(community):
    with pytest.raises(UnknownSubject):
        submit(community, subject="does-not-exist", key="k")


def test_client_cannot_choose_the_title_id(community):
    """title_id не входит в подпись метода: подменять нечего."""
    import inspect

    params = inspect.signature(community.submit).parameters
    assert "title_id" not in params


# ---------------------------------------------------------------------------
# изоляция площадок
# ---------------------------------------------------------------------------


def test_tenant_aggregates_are_isolated(community):
    submit(community, actor="a1", score=10, key="y1", tenant="yummy", subject="s-001")
    submit(community, actor="a2", score=2, key="m1", tenant="animedia", subject="a-001")
    yummy = community.get_aggregate(scope_kind="tenant", scope_id="yummy", title_id="nova:t-001")
    animedia = community.get_aggregate(
        scope_kind="tenant", scope_id="animedia", title_id="nova:t-001"
    )
    assert yummy.vote_count == 1 and yummy.average == "10.00"
    assert animedia.vote_count == 1 and animedia.average == "2.00"


def test_the_same_actor_on_two_tenants_counts_once_on_the_network(community):
    submit(community, actor="a1", score=10, key="y1", tenant="yummy", subject="s-001")
    submit(community, actor="a1", score=2, key="m1", tenant="animedia", subject="a-001")
    network = community.rebuild_network(title_id="nova:t-001")
    assert network.vote_count == 1, "простое сложение дало бы этому участнику два голоса"
    assert network.as_dict()["rule"] == NETWORK_RULE


def test_a_vote_on_one_tenant_does_not_touch_another_titles_aggregate(community):
    submit(community, actor="a1", score=9, key="k1", tenant="yummy", subject="s-001")
    other = community.get_aggregate(scope_kind="tenant", scope_id="yummy", title_id="nova:t-002")
    assert other is None


# ---------------------------------------------------------------------------
# агрегат
# ---------------------------------------------------------------------------


def test_aggregate_rebuild_matches_the_ledger(community):
    for i, score in enumerate([1, 5, 10, 10, 7]):
        submit(community, actor=f"a{i}", score=score, key=f"k{i}")
    check = community.verify_aggregate(
        scope_kind="tenant", scope_id="yummy", title_id="nova:t-001"
    )
    assert check["match"] is True
    assert check["ledger_vote_count"] == 5
    assert check["stored_vote_count"] == 5


def test_tampered_aggregate_is_detected_by_checksum(community):
    submit(community, actor="a1", score=9, key="k1")
    with community.store.write_tx() as conn:
        conn.execute(
            "UPDATE unified_user_aggregates SET vote_count=99, vote_sum=99 WHERE title_id=?",
            ("nova:t-001",),
        )
    check = community.verify_aggregate(
        scope_kind="tenant", scope_id="yummy", title_id="nova:t-001"
    )
    assert check["match"] is False
    assert check["ledger_vote_count"] == 1
    assert check["stored_vote_count"] == 99


def test_distribution_covers_the_full_one_to_ten_range(community):
    submit(community, actor="a1", score=3, key="k1")
    aggregate = community.get_aggregate(
        scope_kind="tenant", scope_id="yummy", title_id="nova:t-001"
    )
    assert sorted(aggregate.distribution.keys(), key=int) == [str(i) for i in range(1, 11)]
    assert aggregate.distribution["3"] == 1


def test_rebuild_is_repeatable(community):
    submit(community, actor="a1", score=6, key="k1")
    first = community.rebuild(tenant_id="yummy", title_id="nova:t-001")
    second = community.rebuild(tenant_id="yummy", title_id="nova:t-001")
    assert first.checksum == second.checksum
    assert first.vote_count == second.vote_count


# ---------------------------------------------------------------------------
# одновременные голоса
# ---------------------------------------------------------------------------


def test_concurrent_votes_are_all_counted_once(community):
    errors: list[Exception] = []

    def vote(index: int) -> None:
        try:
            community.submit(
                tenant_id="yummy",
                subject_id="s-001",
                actor_id=f"actor-{index}",
                score=(index % 10) + 1,
                idempotency_key=f"concurrent-{index}",
            )
        except Exception as exc:  # noqa: BLE001 — собираем для отчёта теста
            errors.append(exc)

    threads = [threading.Thread(target=vote, args=(i,)) for i in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"одновременные голоса дали ошибки: {errors}"
    check = community.verify_aggregate(
        scope_kind="tenant", scope_id="yummy", title_id="nova:t-001"
    )
    assert check["ledger_vote_count"] == 12
    assert check["match"] is True


def test_concurrent_duplicates_of_one_key_create_one_vote(community):
    def vote() -> None:
        # Гонка за один ключ ожидаема: проигравшие получают конфликт,
        # и это ровно то поведение, которое проверяется ниже по числу
        # записанных событий.
        with contextlib.suppress(Exception):
            community.submit(
                tenant_id="yummy",
                subject_id="s-001",
                actor_id="actor-dup",
                score=7,
                idempotency_key="one-key",
            )

    threads = [threading.Thread(target=vote) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    rows = community.votes.store.conn.execute(
        "SELECT COUNT(*) AS n FROM community_vote_events WHERE idempotency_key='one-key'"
    ).fetchone()
    assert rows["n"] == 1
