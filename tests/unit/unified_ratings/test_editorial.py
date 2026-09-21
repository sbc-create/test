"""Редакционная оценка: RBAC, audit, preview, отделённость от других видов."""

from __future__ import annotations

import json

import pytest

from factory.unified_ratings.editorial import (
    EditorialDenied,
    EditorialRatings,
    EditorialRejected,
    Principal,
)

EDITOR = Principal(actor_id="user-editor", role="content_editor")
CHIEF = Principal(actor_id="user-chief", role="editor_in_chief")
AUDITOR = Principal(actor_id="user-auditor", role="editorial_auditor")
VISITOR = Principal(actor_id="user-visitor", role="viewer")
SUPPORT = Principal(actor_id="user-support", role="support_agent")


@pytest.fixture
def editorial(store, seeded) -> EditorialRatings:
    return EditorialRatings(store, registry=seeded)


# ---------------------------------------------------------------------------
# RBAC
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("principal", [EDITOR, CHIEF])
def test_allowed_roles_may_set_a_score(editorial, principal):
    rating = editorial.set_score(
        principal, title_id="nova:t-001", score=8, rationale="разбор редакции"
    )
    assert rating.score == 8
    assert rating.author_role == principal.role


@pytest.mark.parametrize("principal", [VISITOR, SUPPORT, AUDITOR])
def test_other_roles_are_denied(editorial, principal):
    with pytest.raises(EditorialDenied):
        editorial.set_score(principal, title_id="nova:t-001", score=8, rationale="почему бы нет")


def test_denied_role_leaves_no_row_and_no_audit(editorial, store):
    with pytest.raises(EditorialDenied):
        editorial.set_score(VISITOR, title_id="nova:t-001", score=8, rationale="x")
    assert store.count("unified_editorial_ratings") == 0
    assert store.count("unified_editorial_audit") == 0


def test_auditor_may_read_history_but_not_write(editorial):
    editorial.set_score(EDITOR, title_id="nova:t-001", score=8, rationale="разбор")
    assert editorial.history(AUDITOR, title_id="nova:t-001")
    with pytest.raises(EditorialDenied):
        editorial.set_score(AUDITOR, title_id="nova:t-001", score=9, rationale="нет")


def test_visitor_may_not_read_history(editorial):
    with pytest.raises(EditorialDenied):
        editorial.history(VISITOR)


# ---------------------------------------------------------------------------
# значения
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("score", [0, 11, -2, 8.5, "8.5", None, True])
def test_only_integers_one_to_ten_are_accepted(editorial, score):
    with pytest.raises(EditorialRejected):
        editorial.set_score(EDITOR, title_id="nova:t-001", score=score, rationale="основание")


@pytest.mark.parametrize("score", [1, 10])
def test_boundaries_are_accepted(editorial, score):
    assert editorial.set_score(
        EDITOR, title_id="nova:t-001", score=score, rationale="граница"
    ).score == score


def test_rationale_is_required(editorial):
    with pytest.raises(EditorialRejected):
        editorial.set_score(EDITOR, title_id="nova:t-001", score=8, rationale="   ")


def test_unknown_title_is_refused(editorial):
    with pytest.raises(EditorialRejected):
        editorial.set_score(EDITOR, title_id="nova:nope", score=8, rationale="основание")


# ---------------------------------------------------------------------------
# audit
# ---------------------------------------------------------------------------


def test_audit_records_who_when_old_and_new(editorial):
    editorial.set_score(EDITOR, title_id="nova:t-001", score=7, rationale="первая оценка")
    editorial.set_score(CHIEF, title_id="nova:t-001", score=9, rationale="пересмотр после финала")
    history = editorial.history(CHIEF, title_id="nova:t-001")
    assert [h["action"] for h in history] == ["UPDATE", "SET"]
    latest = history[0]
    assert latest["old_score"] == 7
    assert latest["new_score"] == 9
    assert latest["actor_id"] == "user-chief"
    assert latest["actor_role"] == "editor_in_chief"
    assert latest["rationale"] == "пересмотр после финала"
    assert latest["created_at"]


def test_withdraw_keeps_history_and_hides_the_value(editorial):
    editorial.set_score(EDITOR, title_id="nova:t-001", score=7, rationale="оценка")
    withdrawn = editorial.withdraw(
        CHIEF, title_id="nova:t-001", rationale="пересматриваем после перевода"
    )
    assert withdrawn.status == "WITHDRAWN"
    assert withdrawn.as_dict()["score"] is None
    assert editorial.effective(title_id="nova:t-001") is None
    actions = [h["action"] for h in editorial.history(CHIEF, title_id="nova:t-001")]
    assert "WITHDRAW" in actions and "SET" in actions


def test_withdraw_requires_a_rationale(editorial):
    editorial.set_score(EDITOR, title_id="nova:t-001", score=7, rationale="оценка")
    with pytest.raises(EditorialRejected):
        editorial.withdraw(EDITOR, title_id="nova:t-001", rationale="")


def test_restoring_after_withdrawal_is_recorded_as_such(editorial):
    editorial.set_score(EDITOR, title_id="nova:t-001", score=7, rationale="оценка")
    editorial.withdraw(EDITOR, title_id="nova:t-001", rationale="снимаем")
    editorial.set_score(EDITOR, title_id="nova:t-001", score=8, rationale="возвращаем")
    assert editorial.history(EDITOR, title_id="nova:t-001")[0]["action"] == "RESTORE"


def test_history_export_is_line_delimited_json(editorial):
    editorial.set_score(EDITOR, title_id="nova:t-001", score=7, rationale="оценка")
    editorial.set_score(EDITOR, title_id="nova:t-002", score=3, rationale="оценка")
    lines = editorial.export_history(AUDITOR).splitlines()
    assert len(lines) == 2
    assert all(json.loads(line)["actor_id"] == "user-editor" for line in lines)


# ---------------------------------------------------------------------------
# область действия
# ---------------------------------------------------------------------------


def test_tenant_and_global_scores_are_separate_rows(editorial, store):
    editorial.set_score(EDITOR, title_id="nova:t-001", score=8, rationale="глобальная")
    editorial.set_score(
        EDITOR, title_id="nova:t-001", score=6, rationale="для площадки",
        scope_kind="tenant", scope_id="yummy",
    )
    assert store.count("unified_editorial_ratings") == 2
    assert editorial.effective(title_id="nova:t-001", tenant_id="yummy").score == 6
    assert editorial.effective(title_id="nova:t-001").score == 8


def test_withdrawing_a_tenant_score_falls_back_explicitly(editorial):
    editorial.set_score(EDITOR, title_id="nova:t-001", score=8, rationale="глобальная")
    editorial.set_score(
        EDITOR, title_id="nova:t-001", score=6, rationale="площадка",
        scope_kind="tenant", scope_id="yummy",
    )
    editorial.withdraw(
        EDITOR, title_id="nova:t-001", rationale="снимаем", scope_kind="tenant", scope_id="yummy"
    )
    assert editorial.effective(title_id="nova:t-001", tenant_id="yummy").score == 8


def test_tenant_scope_requires_an_identifier(editorial):
    with pytest.raises(EditorialRejected):
        editorial.set_score(
            EDITOR, title_id="nova:t-001", score=8, rationale="x", scope_kind="tenant"
        )


# ---------------------------------------------------------------------------
# массовое изменение
# ---------------------------------------------------------------------------


def test_bulk_requires_a_preview(editorial):
    changes = [{"title_id": "nova:t-001", "score": 8}]
    with pytest.raises(EditorialRejected):
        editorial.apply_bulk(EDITOR, changes, preview={}, rationale="пакет")


def test_bulk_preview_shows_old_and_new(editorial):
    editorial.set_score(EDITOR, title_id="nova:t-001", score=4, rationale="было")
    preview = editorial.preview_bulk(
        EDITOR, [{"title_id": "nova:t-001", "score": 9}, {"title_id": "nova:t-002", "score": 6}]
    )
    rows = {r["title_id"]: r for r in preview["rows"]}
    assert rows["nova:t-001"]["old_score"] == 4
    assert rows["nova:t-001"]["new_score"] == 9
    assert rows["nova:t-002"]["old_score"] is None
    assert preview["applicable"] is True


def test_bulk_refuses_when_the_set_changed_after_preview(editorial):
    changes = [{"title_id": "nova:t-001", "score": 8}]
    preview = editorial.preview_bulk(EDITOR, changes)
    changed = [{"title_id": "nova:t-001", "score": 2}]
    with pytest.raises(EditorialRejected):
        editorial.apply_bulk(EDITOR, changed, preview=preview, rationale="пакет")


def test_bulk_applies_and_tags_every_row_with_the_batch(editorial):
    changes = [{"title_id": "nova:t-001", "score": 8}, {"title_id": "nova:t-002", "score": 5}]
    preview = editorial.preview_bulk(EDITOR, changes)
    result = editorial.apply_bulk(EDITOR, changes, preview=preview, rationale="итоги сезона")
    assert result["applied"] == 2
    batches = {h["batch_id"] for h in editorial.history(EDITOR)}
    assert batches == {result["batch_id"]}


def test_bulk_preview_reports_problems_and_blocks_apply(editorial):
    preview = editorial.preview_bulk(
        EDITOR, [{"title_id": "nova:t-001", "score": 8}, {"title_id": "nova:missing", "score": 5}]
    )
    assert preview["applicable"] is False
    assert preview["problems"]
    with pytest.raises(EditorialRejected):
        editorial.apply_bulk(EDITOR, [], preview=preview, rationale="пакет")


# ---------------------------------------------------------------------------
# отделённость от других видов оценок
# ---------------------------------------------------------------------------


def test_editorial_score_never_enters_the_vote_ledger(editorial, community):
    editorial.set_score(EDITOR, title_id="nova:t-001", score=10, rationale="шедевр")
    votes = community.votes.store.conn.execute(
        "SELECT COUNT(*) AS n FROM community_vote_events"
    ).fetchone()
    assert votes["n"] == 0
    community.rebuild(tenant_id="yummy", title_id="nova:t-001")
    aggregate = community.get_aggregate(
        scope_kind="tenant", scope_id="yummy", title_id="nova:t-001"
    )
    assert aggregate.vote_count == 0


def test_editorial_score_is_labelled_as_ours(editorial):
    rating = editorial.set_score(EDITOR, title_id="nova:t-001", score=8, rationale="разбор")
    payload = rating.as_dict()
    assert payload["label"] == "Наша оценка"
    for foreign in ("IMDb", "Кинопоиск", "AniList", "Kitsu", "Shikimori", "Оценка зрителей"):
        assert foreign not in json.dumps(payload, ensure_ascii=False)
