"""Moderation state machine, including what automation may never do."""

from __future__ import annotations

import pytest

from factory.comments_platform import states
from factory.comments_platform.errors import InvalidTransition


class TestVisibility:
    def test_only_published_and_restored_are_public(self):
        assert {states.PUBLISHED, states.RESTORED} == states.PUBLIC_VISIBLE

    @pytest.mark.parametrize(
        "state", [states.PENDING, states.QUARANTINED, states.HIDDEN, states.REMOVED]
    )
    def test_non_public_states_are_invisible_to_the_public(self, state):
        assert not states.is_public_visible(state)
        assert not states.is_counted(state)

    def test_author_sees_their_own_pending_comment(self):
        assert states.is_author_visible(states.PENDING)
        assert states.is_author_visible(states.QUARANTINED)
        assert states.is_author_visible(states.HIDDEN)

    def test_count_matches_public_visibility(self):
        assert states.COUNTED_STATES == states.PUBLIC_VISIBLE

    def test_unknown_state_is_refused(self):
        with pytest.raises(InvalidTransition):
            states.is_public_visible("approved")


class TestBodyRetention:
    def test_every_state_retains_the_body(self):
        assert frozenset(states.STATES) == states.RETAINS_BODY


class TestTransitions:
    def test_removed_is_terminal(self):
        assert states.ALLOWED_TRANSITIONS[states.REMOVED] == frozenset()
        for target in states.STATES:
            if target == states.REMOVED:
                continue
            with pytest.raises(InvalidTransition):
                states.validate_transition(states.REMOVED, target, reason="undo please")

    def test_same_state_is_an_idempotent_no_op(self):
        for state in states.STATES:
            assert states.validate_transition(state, state) == state

    def test_pending_may_publish(self):
        assert states.validate_transition(states.PENDING, states.PUBLISHED) == states.PUBLISHED

    def test_hidden_restores_rather_than_republishes(self):
        assert states.transition_allowed(states.HIDDEN, states.RESTORED)
        assert not states.transition_allowed(states.HIDDEN, states.PUBLISHED)

    def test_unknown_transition_is_refused(self):
        with pytest.raises(InvalidTransition):
            states.validate_transition(states.PUBLISHED, states.PENDING)


class TestAutomationLimits:
    def test_automation_may_never_remove(self):
        for src in states.STATES:
            if src == states.REMOVED:
                continue
            with pytest.raises(InvalidTransition):
                states.validate_transition(src, states.REMOVED, actor="automation")

    def test_automation_may_hide_and_quarantine(self):
        states.validate_transition(states.PUBLISHED, states.HIDDEN, actor="automation")
        states.validate_transition(states.PENDING, states.QUARANTINED, actor="automation")

    def test_automation_may_not_restore(self):
        with pytest.raises(InvalidTransition):
            states.validate_transition(states.HIDDEN, states.RESTORED, actor="automation")

    def test_automatic_decisions_are_reversible_by_a_human(self):
        for state in states.REVERSIBLE_AUTOMATIC:
            assert states.transition_allowed(state, states.RESTORED) or states.transition_allowed(
                state, states.PUBLISHED
            ), state


class TestReasons:
    @pytest.mark.parametrize(
        "src,dst",
        [
            (states.PUBLISHED, states.HIDDEN),
            (states.PUBLISHED, states.REMOVED),
            (states.HIDDEN, states.RESTORED),
            (states.QUARANTINED, states.REMOVED),
        ],
    )
    def test_manual_action_without_a_reason_is_refused(self, src, dst):
        with pytest.raises(InvalidTransition):
            states.validate_transition(src, dst, actor="human", reason="")
        with pytest.raises(InvalidTransition):
            states.validate_transition(src, dst, actor="human", reason="   ")
        assert states.validate_transition(src, dst, actor="human", reason="spam wave") == dst


class TestEditReopensModeration:
    def test_edit_under_premoderation_returns_to_pending(self):
        assert states.state_after_edit(states.PUBLISHED, moderation_mode="pre") == states.PENDING

    def test_edit_under_postmoderation_stays_published_but_is_rechecked(self):
        assert states.state_after_edit(states.PUBLISHED, moderation_mode="post") == states.PUBLISHED

    def test_removed_comment_cannot_be_edited(self):
        with pytest.raises(InvalidTransition):
            states.state_after_edit(states.REMOVED, moderation_mode="pre")


class TestInitialState:
    def test_premoderation_holds_everything(self):
        assert (
            states.initial_state(moderation_mode="pre", risk_flagged=False, antispam_degraded=False)
            == states.PENDING
        )

    def test_postmoderation_publishes_clean_content(self):
        assert (
            states.initial_state(moderation_mode="post", risk_flagged=False, antispam_degraded=False)
            == states.PUBLISHED
        )

    def test_risky_content_is_held_even_under_postmoderation(self):
        assert (
            states.initial_state(moderation_mode="post", risk_flagged=True, antispam_degraded=False)
            == states.PENDING
        )

    def test_antispam_failure_fails_closed(self):
        """Taking the spam filter down must not become a publishing strategy."""
        assert (
            states.initial_state(moderation_mode="post", risk_flagged=False, antispam_degraded=True)
            == states.PENDING
        )


class TestDocument:
    def test_document_is_complete(self):
        doc = states.state_machine_document()
        assert set(doc["states"]) == set(states.STATES)
        assert set(doc["allowed_transitions"]) == set(states.STATES)
        assert doc["schema_version"] == "COMMENTS_STATE_MACHINE_V1"
