"""Audit: complete, append-only, and safe to read."""

from __future__ import annotations

import pytest

from factory.comments_platform import audit
from factory.comments_platform.errors import ValidationFailed
from factory.comments_platform.rbac import MODERATOR, PLATFORM_OWNER, Principal
from factory.comments_platform.tenancy import ResourceRef

REF = ResourceRef("title", "tt-audit")


@pytest.fixture
def lords(scopes):
    return scopes["lords"]


@pytest.fixture
def actor(lords):
    return Principal(subject_id="mod-1", role=MODERATOR, scope=lords)


class TestRedaction:
    def test_a_comment_body_becomes_a_shape_not_a_copy(self):
        body = "the actual words somebody wrote"
        redacted = audit.redact({"body": body})
        assert redacted["body"]["chars"] == len(body)
        assert len(redacted["body"]["sha256"]) == 32
        assert "actual words" not in repr(redacted)

    def test_the_shape_distinguishes_two_different_bodies(self):
        a = audit.redact({"body": "one thing"})["body"]
        b = audit.redact({"body": "another thing"})["body"]
        assert a["sha256"] != b["sha256"], "the trail cannot tell an edit from a no-op"

    @pytest.mark.parametrize(
        "key",
        [
            "password", "user_password", "api_token", "auth_token", "secret",
            "credential", "authorization", "cookie", "session_id", "private_key",
            "email", "author_email", "ip", "ip_address", "remote_addr",
        ],
    )
    def test_secret_shaped_keys_are_replaced(self, key):
        assert audit.redact({key: "sensitive-value"})[key] == audit.REDACTED

    def test_an_email_in_free_text_is_scrubbed(self):
        out = audit.redact({"reason": "reported by someone@example.test for spam"})
        assert "someone@example.test" not in out["reason"]
        assert audit.REDACTED in out["reason"]

    def test_an_ipv4_in_free_text_is_scrubbed(self):
        out = audit.redact({"reason": "flood from 203.0.113.44 all evening"})
        assert "203.0.113.44" not in out["reason"]

    def test_an_ipv6_in_free_text_is_scrubbed(self):
        out = audit.redact({"reason": "flood from 2001:db8::ff00:42:8329 tonight"})
        assert "2001:db8::ff00:42:8329" not in out["reason"]

    def test_nested_structures_are_redacted_too(self):
        out = audit.redact({"outer": {"inner": {"password": "x", "body": "hello there"}}})
        assert out["outer"]["inner"]["password"] == audit.REDACTED
        assert out["outer"]["inner"]["body"]["chars"] == 11

    def test_recursion_is_bounded(self):
        deep: dict = {"k": "v"}
        for _ in range(30):
            deep = {"k": deep}
        assert audit.redact(deep)  # must not recurse forever

    def test_lists_are_redacted_and_bounded(self):
        out = audit.redact({"items": [{"password": "x"} for _ in range(200)]})
        assert len(out["items"]) == 50
        assert out["items"][0]["password"] == audit.REDACTED

    def test_ordinary_values_pass_through(self):
        out = audit.redact({"state": "published", "count": 3, "flag": True})
        assert out == {"state": "published", "count": 3, "flag": True}


class TestRecording:
    def test_an_unknown_action_is_refused(self, store, lords, actor):
        with pytest.raises(ValidationFailed):
            audit.record(store, lords, action="moderation.vaporise", actor=actor)

    @pytest.mark.parametrize("action", sorted(audit.REASON_REQUIRED_ACTIONS))
    def test_actions_needing_a_reason_cannot_be_written_without_one(
        self, store, lords, actor, action
    ):
        with pytest.raises(ValidationFailed):
            audit.record(store, lords, action=action, actor=actor, reason="   ")

    def test_a_recorded_row_carries_the_full_contract(self, store, lords, actor):
        audit.record(
            store, lords,
            action="moderation.hide",
            actor=actor,
            object_type="comment",
            object_id="c_1",
            before={"state": "published"},
            after={"state": "hidden"},
            reason="off topic",
            request_id="req-9",
            rule_version="RV1",
            artifact_hash="abc123",
        )
        row = store.list_audit(lords)[0]
        for field in (
            "tenant_id", "site_id", "occurred_at", "actor_subject_id", "actor_role",
            "action", "object_type", "object_id", "before_redacted", "after_redacted",
            "reason", "request_id", "rule_version", "artifact_hash",
        ):
            assert field in row, f"{field} missing from the audit row"
        assert row["actor_role"] == MODERATOR
        assert row["occurred_at"].endswith("Z"), "audit time must be UTC"

    def test_break_glass_without_its_reason_is_refused(self, store, lords):
        owner = Principal(subject_id="owner", role=PLATFORM_OWNER, scope=lords)
        with pytest.raises(ValidationFailed):
            audit.record(
                store, lords, action="rbac.break_glass", actor=owner, reason="incident triage"
            )

    def test_break_glass_with_its_reason_is_recorded(self, store, lords):
        from factory.comments_platform.rbac import break_glass

        owner = Principal(subject_id="owner", role=PLATFORM_OWNER, scope=lords)
        escalated = break_glass(owner, "incident 4711: queue wedged, need direct access")
        audit.record(
            store, lords, action="rbac.break_glass", actor=escalated,
            reason=escalated.break_glass_reason,
        )
        assert store.list_audit(lords)[0]["action"] == "rbac.break_glass"


class TestTrailIsWrittenByTheService:
    def test_every_write_leaves_a_row(
        self, service, store, scopes, users, identities, moderators
    ):
        scope = scopes["lords"]
        created = service.create_comment(
            scope, users["lords"], identities["lords"], REF, body="a comment to act upon"
        )
        comment_id = created["comment"]["comment_id"]
        service.edit_own_comment(
            scope, users["lords"], identities["lords"], comment_id, body="an edited version"
        )
        service.moderate(
            scope, moderators["lords"], comment_id, action="hide", reason="off topic"
        )
        actions = [row["action"] for row in store.list_audit(scope)]
        assert "comment.create" in actions
        assert "comment.edit" in actions
        assert "moderation.hide" in actions

    def test_no_comment_text_reaches_the_trail(
        self, service, store, scopes, users, identities
    ):
        secret_words = "a phrase nobody should find in the audit trail"
        service.create_comment(
            scopes["lords"], users["lords"], identities["lords"], REF, body=secret_words
        )
        rows = store.list_audit(scopes["lords"])
        assert rows
        assert secret_words not in repr(rows)

    def test_the_trail_is_tenant_local(
        self, service, store, scopes, users, identities
    ):
        for tenant in ("lords", "zona"):
            service.create_comment(
                scopes[tenant], users[tenant], identities[tenant], REF,
                body=f"a comment written on {tenant}",
            )
        lords_rows = store.list_audit(scopes["lords"])
        assert all(r["tenant_id"] == "lords" for r in lords_rows)


class TestAppendOnly:
    def test_the_package_contains_no_update_or_delete_against_the_trail(self):
        """Append-only proved by inspection of the source, not by assertion."""
        import pathlib
        import re

        package = pathlib.Path(audit.__file__).parent
        offending = []
        pattern = re.compile(
            r"(UPDATE|DELETE\s+FROM)\s+cp_audit_events", re.IGNORECASE
        )
        for path in package.glob("*.py"):
            if pattern.search(path.read_text(encoding="utf-8")):
                offending.append(path.name)
        assert not offending, f"audit rows are mutated in {offending}"

    def test_verification_summary_reports_the_trail(self, store, lords, actor):
        audit.record(
            store, lords, action="moderation.hide", actor=actor, reason="off topic"
        )
        summary = audit.verify_append_only(store, lords)
        assert summary["count"] == 1
        assert summary["has_reason_where_required"] is True


class TestContract:
    def test_contract_names_what_is_never_recorded(self):
        contract = audit.audit_contract()
        never = " ".join(contract["never_recorded"]).lower()
        for item in ("comment text", "password", "token", "email", "raw ip"):
            assert item in never
        assert contract["append_only"] is True
