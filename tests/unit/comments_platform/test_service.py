"""Service behaviour: idempotency, moderation, limits, and failing closed."""

from __future__ import annotations

import pytest

from factory.comments_platform import flags as flags_module
from factory.comments_platform import states
from factory.comments_platform.errors import (
    Conflict,
    FeatureDisabled,
    Forbidden,
    IdempotencyConflict,
    NotFound,
    PolicyViolation,
    RateLimited,
    ValidationFailed,
)
from factory.comments_platform.rbac import MODERATOR, USER, Principal
from factory.comments_platform.tenancy import ResourceRef

REF = ResourceRef("title", "tt-service")


@pytest.fixture
def lords(scopes):
    return scopes["lords"]


@pytest.fixture
def author(users):
    return users["lords"]


@pytest.fixture
def author_identity(identities):
    return identities["lords"]


@pytest.fixture
def moderator(moderators):
    return moderators["lords"]


def post(service, lords, author, author_identity, body="a perfectly ordinary comment", **kw):
    return service.create_comment(lords, author, author_identity, REF, body=body, **kw)


class TestGatesComeFirst:
    def test_reading_is_refused_when_the_gate_is_shut(self, store, registry, scopes, users):
        """`registry` is the shipped-default registry: every gate at 0."""
        from factory.comments_platform.service import CommentsService

        service = CommentsService(store, registry)
        with pytest.raises(FeatureDisabled) as exc:
            service.thread_view(scopes["lords"], users["lords"], REF)
        # 503, not 403: the page embedding the widget must degrade, not break.
        assert exc.value.http_status == 503

    def test_writing_is_refused_when_the_gate_is_shut(
        self, store, registry, scopes, users, identities
    ):
        from factory.comments_platform.service import CommentsService

        service = CommentsService(store, registry)
        with pytest.raises(FeatureDisabled):
            service.create_comment(
                scopes["lords"], users["lords"], identities["lords"], REF, body="hello"
            )

    def test_kill_switch_stops_writes_immediately(
        self, service, lords, author, author_identity
    ):
        post(service, lords, author, author_identity)
        flags_module.KillSwitch.engage_global()
        try:
            with pytest.raises(FeatureDisabled):
                post(service, lords, author, author_identity, body="a different comment entirely")
        finally:
            flags_module.KillSwitch.release_global()

    def test_kill_switch_release_restores_writes(self, service, lords, author, author_identity):
        flags_module.KillSwitch.engage_global()
        flags_module.KillSwitch.release_global()
        assert post(service, lords, author, author_identity)["comment"]["comment_id"]


class TestCreate:
    def test_a_comment_is_created_and_published_under_postmoderation(
        self, service, lords, author, author_identity
    ):
        result = post(service, lords, author, author_identity)
        assert result["moderation"]["state"] == states.PUBLISHED
        assert result["comment"]["body_html"]
        assert result["comment"]["anchor"].startswith("comment-")

    def test_html_in_a_body_is_inert_by_the_time_it_is_stored(
        self, service, store, lords, author, author_identity
    ):
        result = post(
            service, lords, author, author_identity,
            body="<script>alert(1)</script> hello",
        )
        row = store.get_comment(lords, result["comment"]["comment_id"])
        assert "<script>" not in row["body_html"]
        assert "&lt;script&gt;" in row["body_html"]

    def test_body_over_the_limit_is_refused_not_truncated(
        self, service, lords, author, author_identity
    ):
        with pytest.raises(ValidationFailed):
            post(service, lords, author, author_identity, body="x" * 5000)

    def test_empty_body_is_refused(self, service, lords, author, author_identity):
        with pytest.raises(ValidationFailed):
            post(service, lords, author, author_identity, body="   \n  ")

    def test_a_banned_author_cannot_write(
        self, service, lords, author, author_identity, moderator
    ):
        post(service, lords, author, author_identity)
        service.ban_subject(
            lords, moderator, author_identity.subject_id,
            banned=True, reason="repeated spam on this site",
        )
        with pytest.raises(Forbidden):
            post(service, lords, author, author_identity, body="let me back in please")

    def test_thread_is_keyed_by_content_not_by_slug(
        self, service, store, lords, author, author_identity
    ):
        post(service, lords, author, author_identity)
        first = store.find_thread(lords, REF)
        # A second comment on the same content id joins the same thread even
        # though nothing about a URL was supplied either time.
        post(service, lords, author, author_identity, body="a second, different comment")
        assert store.find_thread(lords, REF)["thread_id"] == first["thread_id"]


class TestReplies:
    def test_a_reply_records_its_parent_and_depth(
        self, service, lords, author, author_identity
    ):
        parent = post(service, lords, author, author_identity)["comment"]["comment_id"]
        reply = service.create_comment(
            lords, author, author_identity, REF, body="a reply to that", parent_id=parent
        )
        assert reply["comment"]["parent_id"] == parent
        assert reply["comment"]["depth"] == 1

    def test_nesting_stops_at_the_configured_depth(
        self, service, lords, author, author_identity
    ):
        parent = post(service, lords, author, author_identity)["comment"]["comment_id"]
        for level in range(1, 3):
            parent = service.create_comment(
                lords, author, author_identity, REF,
                body=f"reply at level {level} with enough words to be distinct",
                parent_id=parent,
            )["comment"]["comment_id"]
        with pytest.raises(PolicyViolation) as exc:
            service.create_comment(
                lords, author, author_identity, REF,
                body="one level too deep for this site's policy", parent_id=parent,
            )
        assert exc.value.rule == "MAX_DEPTH"

    def test_replying_to_a_hidden_comment_reports_it_as_missing(
        self, service, lords, author, author_identity, moderator
    ):
        parent = post(service, lords, author, author_identity)["comment"]["comment_id"]
        service.moderate(lords, moderator, parent, action="hide", reason="off topic")
        with pytest.raises(NotFound):
            service.create_comment(
                lords, author, author_identity, REF,
                body="replying to something I should not see", parent_id=parent,
            )


class TestIdempotency:
    def test_a_retried_write_replays_rather_than_duplicating(
        self, service, store, lords, author, author_identity
    ):
        first = post(service, lords, author, author_identity, idempotency_key="k-1")
        second = post(service, lords, author, author_identity, idempotency_key="k-1")
        assert first == second
        rows = store.execute_raw(
            "SELECT comment_id FROM cp_comments WHERE tenant_id = ? AND site_id = ?",
            (lords.tenant_id, lords.site_id),
        )
        assert len(rows) == 1, "the retry created a second comment"

    def test_reusing_a_key_for_different_content_is_a_conflict(
        self, service, lords, author, author_identity
    ):
        post(service, lords, author, author_identity, idempotency_key="k-2")
        with pytest.raises(IdempotencyConflict):
            post(
                service, lords, author, author_identity,
                body="an entirely different thought", idempotency_key="k-2",
            )

    def test_keys_are_scoped_per_subject(self, service, store, lords, author, author_identity):
        """Two people using the literal key "1" must not collide."""
        from factory.comments_platform.identity import Identity

        post(service, lords, author, author_identity, idempotency_key="1")

        other_identity = Identity(subject_id="g_someone_else", scope=lords, is_guest=True)
        other = Principal(subject_id=other_identity.subject_id, role=USER, scope=lords)
        # Same key, same body, different subject: a new comment, not a replay.
        service.create_comment(
            lords, other, other_identity, REF,
            body="a perfectly ordinary comment", idempotency_key="1",
        )
        rows = store.execute_raw(
            "SELECT comment_id FROM cp_comments WHERE tenant_id = ? AND site_id = ?",
            (lords.tenant_id, lords.site_id),
        )
        assert len(rows) == 2

    def test_a_write_without_a_key_still_works(self, service, lords, author, author_identity):
        assert post(service, lords, author, author_identity)["comment"]["comment_id"]


class TestDuplicatesAndFlood:
    def test_the_same_text_twice_is_refused(self, service, lords, author, author_identity):
        post(service, lords, author, author_identity, body="exactly the same words")
        with pytest.raises(PolicyViolation) as exc:
            post(service, lords, author, author_identity, body="exactly the same words")
        assert exc.value.rule == "EXACT_DUPLICATE"

    def test_near_duplicates_from_several_authors_are_caught(
        self, service, store, lords, identities
    ):
        """The coordinated case: one text, different decoration, many accounts."""
        from factory.comments_platform.identity import Identity

        base = "amazing offer visit our website today"
        decorations = ["!!!", "...", " ???", "!!", " --"]
        for index, decoration in enumerate(decorations):
            identity = Identity(
                subject_id=f"g_flooder{index}", scope=lords, is_guest=True
            )
            principal = Principal(subject_id=identity.subject_id, role=USER, scope=lords)
            if index < 3:
                service.create_comment(
                    lords, principal, identity, REF, body=base + decoration
                )
            else:
                with pytest.raises(PolicyViolation) as exc:
                    service.create_comment(
                        lords, principal, identity, REF, body=base + decoration
                    )
                assert exc.value.rule == "NEAR_DUPLICATE_FLOOD"
                break

    def test_rate_limit_stops_a_burst(self, service, lords, author, author_identity):
        with pytest.raises(RateLimited) as exc:
            for index in range(10):
                post(
                    service, lords, author, author_identity,
                    body=f"comment number {index} with enough distinct words to pass dedupe",
                )
        assert exc.value.retry_after_seconds > 0
        assert exc.value.http_status == 429


class TestRiskAndFailClosed:
    def test_risky_content_is_held_rather_than_rejected(
        self, service, lords, author, author_identity
    ):
        result = post(
            service, lords, author, author_identity,
            body="BUY NOW CHEAP DEALS CLICK HERE https://spam.test/a",
        )
        assert result["moderation"]["held"] is True
        assert result["moderation"]["state"] == states.PENDING

    def test_a_held_comment_still_exists_for_its_author(
        self, service, store, lords, author, author_identity
    ):
        result = post(
            service, lords, author, author_identity,
            body="BUY NOW CHEAP DEALS CLICK HERE https://spam.test/b",
        )
        row = store.get_comment(lords, result["comment"]["comment_id"])
        assert row["body"], "a held comment must retain its text"

    def test_antispam_failure_holds_instead_of_publishing(
        self, service, lords, author, author_identity
    ):
        """Taking the filter down must not become a publishing strategy."""
        result = post(
            service, lords, author, author_identity,
            body="a completely ordinary sentence", antispam_degraded=True,
        )
        assert result["moderation"]["state"] == states.PENDING
        assert result["moderation"]["degraded"] is True


class TestEditAndDelete:
    def test_editing_keeps_a_revision(
        self, service, store, lords, author, author_identity
    ):
        comment_id = post(service, lords, author, author_identity)["comment"]["comment_id"]
        service.edit_own_comment(
            lords, author, author_identity, comment_id, body="a revised version of the text"
        )
        revisions = store.list_revisions(lords, comment_id)
        assert len(revisions) == 1
        assert revisions[0]["body"] == "a perfectly ordinary comment"

    def test_editing_an_approved_comment_sends_it_back_to_the_queue(
        self, store, scopes, users, identities, gates_open
    ):
        """Otherwise "post something bland, get approved, rewrite it" is a door."""
        from factory.comments_platform.service import CommentsService
        from factory.comments_platform.tenancy import SiteRegistry

        from .conftest import open_binding

        strict = SiteRegistry([open_binding("lords", "lords-main", moderation_mode="pre")])
        service = CommentsService(store, strict)
        scope, user, identity = scopes["lords"], users["lords"], identities["lords"]

        created = service.create_comment(scope, user, identity, REF, body="first version")
        comment_id = created["comment"]["comment_id"]
        assert created["moderation"]["state"] == states.PENDING

        # A moderator approves it, so it is genuinely public before the edit.
        moderator = Principal(subject_id="mod", role=MODERATOR, scope=scope)
        service.moderate(scope, moderator, comment_id, action="publish", reason="looks fine")
        assert store.get_comment(scope, comment_id)["state"] == states.PUBLISHED

        edited = service.edit_own_comment(
            scope, user, identity, comment_id, body="a wholly different second version"
        )
        assert edited["moderation"]["state"] == states.PENDING
        assert store.get_comment(scope, comment_id)["state"] == states.PENDING

    def test_a_removed_comment_cannot_be_edited(
        self, service, lords, author, author_identity
    ):
        comment_id = post(service, lords, author, author_identity)["comment"]["comment_id"]
        service.delete_own_comment(lords, author, comment_id)
        with pytest.raises(Conflict):
            service.edit_own_comment(
                lords, author, author_identity, comment_id, body="trying anyway"
            )

    def test_deleting_is_soft_and_keeps_the_body(
        self, service, store, lords, author, author_identity
    ):
        comment_id = post(service, lords, author, author_identity)["comment"]["comment_id"]
        service.delete_own_comment(lords, author, comment_id)
        row = store.get_comment(lords, comment_id)
        assert row["state"] == states.REMOVED
        assert row["body"], "a soft delete that destroys the body is not soft"

    def test_one_author_cannot_edit_another(
        self, service, lords, author, author_identity, identities
    ):
        comment_id = post(service, lords, author, author_identity)["comment"]["comment_id"]
        from factory.comments_platform.identity import Identity

        stranger_identity = Identity(subject_id="g_stranger", scope=lords, is_guest=True)
        stranger = Principal(subject_id="g_stranger", role=USER, scope=lords)
        with pytest.raises(Forbidden):
            service.edit_own_comment(
                lords, stranger, stranger_identity, comment_id, body="not mine to edit"
            )


class TestReactions:
    def test_one_person_gets_one_reaction(
        self, service, lords, author, author_identity
    ):
        comment_id = post(service, lords, author, author_identity)["comment"]["comment_id"]
        service.set_reaction(lords, author, author_identity, comment_id, "like")
        result = service.set_reaction(lords, author, author_identity, comment_id, "like")
        assert result["reaction_count"] == 1, "a double click inflated the count"

    def test_changing_a_reaction_does_not_add_one(
        self, service, lords, author, author_identity
    ):
        comment_id = post(service, lords, author, author_identity)["comment"]["comment_id"]
        service.set_reaction(lords, author, author_identity, comment_id, "like")
        result = service.set_reaction(lords, author, author_identity, comment_id, "helpful")
        assert result["reaction_count"] == 1
        assert result["reaction"] == "helpful"

    def test_clearing_a_reaction_decrements_deterministically(
        self, service, lords, author, author_identity
    ):
        comment_id = post(service, lords, author, author_identity)["comment"]["comment_id"]
        service.set_reaction(lords, author, author_identity, comment_id, "like")
        result = service.clear_reaction(lords, author, author_identity, comment_id)
        assert result["reaction_count"] == 0

    def test_unknown_reaction_is_refused(self, service, lords, author, author_identity):
        comment_id = post(service, lords, author, author_identity)["comment"]["comment_id"]
        with pytest.raises(ValidationFailed):
            service.set_reaction(lords, author, author_identity, comment_id, "rocket")

    def test_reacting_to_a_hidden_comment_reports_it_missing(
        self, service, lords, author, author_identity, moderator
    ):
        comment_id = post(service, lords, author, author_identity)["comment"]["comment_id"]
        service.moderate(lords, moderator, comment_id, action="hide", reason="off topic")
        with pytest.raises(NotFound):
            service.set_reaction(lords, author, author_identity, comment_id, "like")


class TestReports:
    def test_a_repeat_report_is_indistinguishable_from_the_first(
        self, service, lords, author, author_identity
    ):
        comment_id = post(service, lords, author, author_identity)["comment"]["comment_id"]
        first = service.report_comment(
            lords, author, author_identity, comment_id, reason="spam"
        )
        second = service.report_comment(
            lords, author, author_identity, comment_id, reason="spam"
        )
        assert first == second, "the response revealed whether a report was new"

    def test_a_repeat_report_does_not_inflate_the_count(
        self, service, store, lords, author, author_identity
    ):
        comment_id = post(service, lords, author, author_identity)["comment"]["comment_id"]
        for _ in range(4):
            service.report_comment(lords, author, author_identity, comment_id, reason="spam")
        assert store.distinct_reporters(lords, comment_id) == 1

    def test_unknown_reason_is_refused(self, service, lords, author, author_identity):
        comment_id = post(service, lords, author, author_identity)["comment"]["comment_id"]
        with pytest.raises(ValidationFailed):
            service.report_comment(
                lords, author, author_identity, comment_id, reason="i just dislike it"
            )


class TestModerationRequiresReasons:
    @pytest.mark.parametrize("action", ["hide", "remove", "restore"])
    def test_a_moderation_action_without_a_reason_is_refused(
        self, service, lords, author, author_identity, moderator, action
    ):
        comment_id = post(service, lords, author, author_identity)["comment"]["comment_id"]
        if action == "restore":
            service.moderate(lords, moderator, comment_id, action="hide", reason="first hide")
        with pytest.raises(Exception) as exc:
            service.moderate(lords, moderator, comment_id, action=action, reason="")
        assert "reason" in str(exc.value).lower()

    def test_a_moderation_action_writes_an_action_row(
        self, service, store, lords, author, author_identity, moderator
    ):
        comment_id = post(service, lords, author, author_identity)["comment"]["comment_id"]
        service.moderate(lords, moderator, comment_id, action="hide", reason="off topic")
        actions = store.list_moderation_actions(lords, comment_id)
        assert len(actions) == 1
        assert actions[0]["reason"] == "off topic"
        assert actions[0]["actor_role"] == MODERATOR
        assert actions[0]["automatic"] == 0

    def test_a_hidden_comment_can_be_restored(
        self, service, lords, author, author_identity, moderator
    ):
        comment_id = post(service, lords, author, author_identity)["comment"]["comment_id"]
        service.moderate(lords, moderator, comment_id, action="hide", reason="mistaken hide")
        result = service.moderate(
            lords, moderator, comment_id, action="restore", reason="reviewed, it is fine"
        )
        assert result["state"] == states.RESTORED

    def test_a_user_cannot_moderate(self, service, lords, author, author_identity):
        comment_id = post(service, lords, author, author_identity)["comment"]["comment_id"]
        with pytest.raises(Forbidden):
            service.moderate(lords, author, comment_id, action="remove", reason="mine now")
