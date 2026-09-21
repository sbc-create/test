"""RBAC matrix: every role against every permission, in and out of scope."""

from __future__ import annotations

import pytest

from factory.comments_platform import rbac
from factory.comments_platform.errors import (
    CrossTenantDenied,
    Forbidden,
    Unauthenticated,
    ValidationFailed,
)
from factory.comments_platform.tenancy import TenantScope

LORDS = TenantScope("lords", "lords-main")
ZONA = TenantScope("zona", "zona-main")
LORDS_OTHER_SITE = TenantScope("lords", "lords-staging")


def principal(role: str, scope: TenantScope | None = LORDS, subject: str = "s1") -> rbac.Principal:
    if role == rbac.PLATFORM_OWNER:
        return rbac.Principal(subject_id=subject, role=role, scope=scope)
    if role == rbac.SERVICE_ACCOUNT:
        return rbac.issue_service_principal(
            subject, scope or LORDS, [rbac.P_READ_PUBLISHED],
            audience="comments-api", ttl_seconds=60,
        )
    return rbac.Principal(subject_id=subject, role=role, scope=scope)


class TestDefaultDeny:
    def test_every_permission_is_in_the_matrix(self):
        for role, perms in rbac.GRANTS.items():
            assert perms <= rbac.PERMISSIONS, f"{role} grants an unknown permission"

    @pytest.mark.parametrize("role", rbac.ROLES)
    def test_unknown_permission_is_denied_for_every_role(self, role):
        assert not rbac.granted(principal(role), "comments.take_over_the_world")

    def test_matrix_document_is_serialisable_and_complete(self):
        doc = rbac.role_matrix()
        assert doc["default"] == "deny"
        assert set(doc["grants"]) == set(rbac.ROLES)
        assert sorted(doc["permissions"]) == sorted(rbac.PERMISSIONS)


class TestRoleSeparation:
    def test_tenant_admin_cannot_deploy_to_production(self):
        assert not rbac.granted(principal(rbac.TENANT_ADMIN), rbac.P_PRODUCTION_DEPLOY)

    def test_tenant_admin_cannot_approve_production(self):
        assert not rbac.granted(principal(rbac.TENANT_ADMIN), rbac.P_PRODUCTION_APPROVE)

    def test_only_platform_owner_may_deploy(self):
        for role in rbac.ROLES:
            allowed = rbac.granted(principal(role), rbac.P_PRODUCTION_DEPLOY)
            assert allowed == (role == rbac.PLATFORM_OWNER), role

    def test_only_platform_owner_may_break_glass(self):
        for role in rbac.ROLES:
            allowed = rbac.granted(principal(role), rbac.P_BREAK_GLASS)
            assert allowed == (role == rbac.PLATFORM_OWNER), role

    def test_auditor_reads_but_never_writes(self):
        auditor = principal(rbac.AUDITOR)
        assert rbac.granted(auditor, rbac.P_AUDIT_READ)
        for write in (
            rbac.P_MODERATION_HIDE, rbac.P_MODERATION_REMOVE, rbac.P_POLICY_WRITE,
            rbac.P_CREATE, rbac.P_BAN_USER, rbac.P_FLAGS_WRITE,
        ):
            assert not rbac.granted(auditor, write), write

    def test_user_holds_no_moderation_power(self):
        user = principal(rbac.USER)
        for perm in (
            rbac.P_MODERATION_QUEUE, rbac.P_MODERATION_HIDE, rbac.P_MODERATION_REMOVE,
            rbac.P_BAN_USER, rbac.P_AUDIT_READ, rbac.P_POLICY_WRITE,
        ):
            assert not rbac.granted(user, perm), perm

    def test_moderator_cannot_change_policy_or_flags(self):
        mod = principal(rbac.MODERATOR)
        assert not rbac.granted(mod, rbac.P_POLICY_WRITE)
        assert not rbac.granted(mod, rbac.P_FLAGS_WRITE)


class TestScopeBeatsPermission:
    @pytest.mark.parametrize(
        "role", [rbac.TENANT_OWNER, rbac.TENANT_ADMIN, rbac.MODERATOR, rbac.AUDITOR, rbac.USER]
    )
    def test_foreign_tenant_is_refused_as_not_found(self, role):
        actor = principal(role, LORDS)
        with pytest.raises(CrossTenantDenied) as exc:
            rbac.authorize(actor, rbac.P_READ_PUBLISHED, ZONA)
        assert exc.value.http_status == 404

    def test_same_tenant_other_site_is_also_refused(self):
        actor = principal(rbac.MODERATOR, LORDS)
        with pytest.raises(CrossTenantDenied):
            rbac.authorize(actor, rbac.P_MODERATION_QUEUE, LORDS_OTHER_SITE)

    def test_scope_is_checked_before_permission(self):
        """A role lacking the permission AND out of scope must give 404, not 403.

        Otherwise the two error codes together reveal which tenant an object
        lives in.
        """
        actor = principal(rbac.USER, LORDS)
        with pytest.raises(CrossTenantDenied):
            rbac.authorize(actor, rbac.P_MODERATION_REMOVE, ZONA)

    def test_platform_owner_crosses_scope_by_design(self):
        rbac.authorize(principal(rbac.PLATFORM_OWNER), rbac.P_AUDIT_READ, ZONA)

    def test_tenant_scoped_role_without_scope_is_rejected_at_construction(self):
        with pytest.raises(ValidationFailed):
            rbac.Principal(subject_id="s", role=rbac.MODERATOR, scope=None)


class TestOwnership:
    def test_user_edits_only_their_own_comment(self):
        actor = principal(rbac.USER, LORDS, subject="alice")
        rbac.authorize(actor, rbac.P_EDIT_OWN, LORDS, owner_subject_id="alice")
        with pytest.raises(Forbidden):
            rbac.authorize(actor, rbac.P_EDIT_OWN, LORDS, owner_subject_id="bob")

    def test_moderator_cannot_use_edit_own_on_another_author(self):
        actor = principal(rbac.MODERATOR, LORDS, subject="mod")
        with pytest.raises(Forbidden):
            rbac.authorize(actor, rbac.P_EDIT_OWN, LORDS, owner_subject_id="alice")

    def test_ownership_check_requires_an_owner(self):
        actor = principal(rbac.USER, LORDS, subject="alice")
        with pytest.raises(ValidationFailed):
            rbac.authorize(actor, rbac.P_DELETE_OWN, LORDS)


class TestSelfElevation:
    @pytest.mark.parametrize("role", [rbac.PLATFORM_OWNER, rbac.TENANT_OWNER])
    def test_nobody_grants_themselves_a_role(self, role):
        actor = principal(role, LORDS, subject="self")
        with pytest.raises(Forbidden):
            rbac.authorize_role_grant(actor, "self", rbac.PLATFORM_OWNER, LORDS)

    def test_tenant_owner_cannot_mint_a_platform_owner(self):
        actor = principal(rbac.TENANT_OWNER, LORDS, subject="owner")
        with pytest.raises(Forbidden):
            rbac.authorize_role_grant(actor, "confederate", rbac.PLATFORM_OWNER, LORDS)

    def test_tenant_owner_may_grant_a_moderator(self):
        actor = principal(rbac.TENANT_OWNER, LORDS, subject="owner")
        rbac.authorize_role_grant(actor, "newmod", rbac.MODERATOR, LORDS)

    def test_moderator_cannot_grant_at_all(self):
        actor = principal(rbac.MODERATOR, LORDS, subject="mod")
        with pytest.raises(Forbidden):
            rbac.authorize_role_grant(actor, "other", rbac.MODERATOR, LORDS)


class TestFourEyes:
    def test_author_cannot_approve_own_rollout(self):
        actor = principal(rbac.TENANT_OWNER, LORDS, subject="dev")
        with pytest.raises(Forbidden):
            rbac.authorize_production_approval(actor, change_author_subject_id="dev", scope=LORDS)

    def test_a_different_owner_may_approve(self):
        actor = principal(rbac.TENANT_OWNER, LORDS, subject="reviewer")
        rbac.authorize_production_approval(actor, change_author_subject_id="dev", scope=LORDS)


class TestServiceTokens:
    def test_token_carries_only_enumerated_actions(self):
        svc = rbac.issue_service_principal(
            "svc", LORDS, [rbac.P_READ_PUBLISHED], audience="a", ttl_seconds=60
        )
        assert rbac.granted(svc, rbac.P_READ_PUBLISHED)
        assert not rbac.granted(svc, rbac.P_CREATE)
        assert not rbac.granted(svc, rbac.P_MODERATION_REMOVE)

    def test_ttl_is_capped(self):
        with pytest.raises(ValidationFailed):
            rbac.issue_service_principal(
                "svc", LORDS, [], audience="a",
                ttl_seconds=rbac.SERVICE_TOKEN_MAX_TTL_SECONDS + 1,
            )

    def test_zero_or_negative_ttl_is_refused(self):
        for ttl in (0, -1):
            with pytest.raises(ValidationFailed):
                rbac.issue_service_principal("svc", LORDS, [], audience="a", ttl_seconds=ttl)

    def test_expired_token_is_unauthenticated(self):
        svc = rbac.issue_service_principal(
            "svc", LORDS, [rbac.P_READ_PUBLISHED], audience="a", ttl_seconds=10, now=1000.0
        )
        rbac.authorize(svc, rbac.P_READ_PUBLISHED, LORDS, now=1005.0)
        with pytest.raises(Unauthenticated):
            rbac.authorize(svc, rbac.P_READ_PUBLISHED, LORDS, now=1011.0)

    def test_token_may_not_carry_platform_only_actions(self):
        with pytest.raises(Forbidden):
            rbac.issue_service_principal(
                "svc", LORDS, [rbac.P_PRODUCTION_DEPLOY], audience="a", ttl_seconds=60
            )

    def test_token_needs_an_audience(self):
        with pytest.raises(ValidationFailed):
            rbac.Principal(
                subject_id="svc", role=rbac.SERVICE_ACCOUNT, scope=LORDS,
                token_actions=frozenset({rbac.P_READ_PUBLISHED}), token_audience="",
            )

    def test_token_naming_an_unknown_action_is_refused(self):
        with pytest.raises(ValidationFailed):
            rbac.Principal(
                subject_id="svc", role=rbac.SERVICE_ACCOUNT, scope=LORDS,
                token_actions=frozenset({"comments.invent"}), token_audience="a",
            )


class TestBreakGlass:
    def test_requires_platform_owner(self):
        with pytest.raises(Forbidden):
            rbac.break_glass(principal(rbac.TENANT_OWNER), "production incident 4711 triage")

    def test_requires_a_substantive_reason(self):
        owner = principal(rbac.PLATFORM_OWNER)
        for reason in ("", "   ", "oops"):
            with pytest.raises(ValidationFailed):
                rbac.break_glass(owner, reason)

    def test_returns_a_principal_carrying_the_reason(self):
        owner = principal(rbac.PLATFORM_OWNER)
        escalated = rbac.break_glass(owner, "incident 4711: moderation queue stuck")
        assert escalated.break_glass_reason
        assert escalated.is_platform
