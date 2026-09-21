"""Role-based access control. Default deny.

The grant table is the contract: a permission not written into a role's set is
denied, so adding a capability means editing this file, and a reviewer can see
the whole authority surface on one screen.

Four rules are not expressible as a grant table alone and are enforced in code:

* A moderator's authority stops at their own site. Scope is checked *before*
  the permission, so a `lords` moderator probing `zona` gets 404, never 403.
* Ownership beats role for a user's own objects — and only their own.
* Nobody may grant themselves a role, at any level, including platform owner.
  Self-elevation is the one move that turns a single compromised session into a
  full compromise.
* The author of a change may not approve that change's rollout.

Production deploy is deliberately *not* granted to tenant admins. Running a
site and shipping the shared module are different jobs; conflating them would
let one tenant's admin ship code to the other three.
"""

from __future__ import annotations

import hmac
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from .errors import Forbidden, Unauthenticated, ValidationFailed
from .tenancy import TenantScope

# --- Roles ---------------------------------------------------------------

PLATFORM_OWNER = "platform_owner"
TENANT_OWNER = "tenant_owner"
TENANT_ADMIN = "tenant_admin"
MODERATOR = "moderator"
AUDITOR = "auditor"
USER = "user"
SERVICE_ACCOUNT = "service_account"

ROLES = (
    PLATFORM_OWNER,
    TENANT_OWNER,
    TENANT_ADMIN,
    MODERATOR,
    AUDITOR,
    USER,
    SERVICE_ACCOUNT,
)

# Roles whose authority is confined to a single tenant/site pair.
TENANT_SCOPED_ROLES = frozenset({TENANT_OWNER, TENANT_ADMIN, MODERATOR, AUDITOR, SERVICE_ACCOUNT})

# --- Permissions ---------------------------------------------------------

P_READ_PUBLISHED = "comments.read_published"
P_READ_OWN = "comments.read_own"
P_CREATE = "comments.create"
P_EDIT_OWN = "comments.edit_own"
P_DELETE_OWN = "comments.delete_own"
P_REACT = "comments.react"
P_REPORT = "comments.report"

P_MODERATION_QUEUE = "moderation.queue"
P_MODERATION_HIDE = "moderation.hide"
P_MODERATION_RESTORE = "moderation.restore"
P_MODERATION_REMOVE = "moderation.remove"
P_MODERATION_RESOLVE_REPORT = "moderation.resolve_report"
P_BAN_USER = "moderation.ban_user"

P_POLICY_READ = "policy.read"
P_POLICY_WRITE = "policy.write"
P_FLAGS_WRITE = "flags.write"
P_KILL_SWITCH = "flags.kill_switch"

P_AUDIT_READ = "audit.read"
P_EXPORT_TENANT = "privacy.export"
P_DELETE_TENANT_DATA = "privacy.delete"

P_ROLE_GRANT = "rbac.grant"
P_PRODUCTION_DEPLOY = "release.production_deploy"
P_PRODUCTION_APPROVE = "release.production_approve"
P_BREAK_GLASS = "rbac.break_glass"

PERMISSIONS = frozenset(
    {
        P_READ_PUBLISHED, P_READ_OWN, P_CREATE, P_EDIT_OWN, P_DELETE_OWN, P_REACT, P_REPORT,
        P_MODERATION_QUEUE, P_MODERATION_HIDE, P_MODERATION_RESTORE, P_MODERATION_REMOVE,
        P_MODERATION_RESOLVE_REPORT, P_BAN_USER,
        P_POLICY_READ, P_POLICY_WRITE, P_FLAGS_WRITE, P_KILL_SWITCH,
        P_AUDIT_READ, P_EXPORT_TENANT, P_DELETE_TENANT_DATA,
        P_ROLE_GRANT, P_PRODUCTION_DEPLOY, P_PRODUCTION_APPROVE, P_BREAK_GLASS,
    }
)

_USER_GRANTS = frozenset(
    {P_READ_PUBLISHED, P_READ_OWN, P_CREATE, P_EDIT_OWN, P_DELETE_OWN, P_REACT, P_REPORT}
)

_MODERATOR_GRANTS = _USER_GRANTS | {
    P_MODERATION_QUEUE, P_MODERATION_HIDE, P_MODERATION_RESTORE, P_MODERATION_REMOVE,
    P_MODERATION_RESOLVE_REPORT, P_BAN_USER, P_POLICY_READ,
}

_TENANT_ADMIN_GRANTS = _MODERATOR_GRANTS | {
    P_POLICY_WRITE, P_AUDIT_READ, P_FLAGS_WRITE, P_KILL_SWITCH,
}

_TENANT_OWNER_GRANTS = _TENANT_ADMIN_GRANTS | {
    P_EXPORT_TENANT, P_DELETE_TENANT_DATA, P_ROLE_GRANT, P_PRODUCTION_APPROVE,
}

GRANTS: dict[str, frozenset[str]] = {
    # The platform owner is the only role that may ship the shared module.
    PLATFORM_OWNER: frozenset(PERMISSIONS),
    TENANT_OWNER: frozenset(_TENANT_OWNER_GRANTS),
    # Note the absence of P_PRODUCTION_DEPLOY and P_PRODUCTION_APPROVE here.
    TENANT_ADMIN: frozenset(_TENANT_ADMIN_GRANTS),
    MODERATOR: frozenset(_MODERATOR_GRANTS),
    AUDITOR: frozenset({P_AUDIT_READ, P_POLICY_READ, P_READ_PUBLISHED}),
    USER: frozenset(_USER_GRANTS),
    # A service account gets nothing by default; its token enumerates actions.
    SERVICE_ACCOUNT: frozenset(),
}

# Permissions that only ever belong to the platform, never to a tenant.
PLATFORM_ONLY = frozenset({P_PRODUCTION_DEPLOY, P_BREAK_GLASS})

# The longest a scoped service token may live. Short on purpose: a leaked token
# that outlives the incident that leaked it is a second incident.
SERVICE_TOKEN_MAX_TTL_SECONDS = 900


@dataclass(frozen=True)
class Principal:
    """Who is acting, and where they are allowed to act."""

    subject_id: str
    role: str
    scope: TenantScope | None = None
    # Present only for service accounts: the exact actions the token carries.
    token_actions: frozenset[str] = field(default_factory=frozenset)
    token_audience: str = ""
    token_expires_at: float = 0.0
    break_glass_reason: str = ""

    def __post_init__(self) -> None:
        if self.role not in ROLES:
            raise ValidationFailed(f"unknown role {self.role!r}", field="role")
        if self.role in TENANT_SCOPED_ROLES and self.scope is None:
            raise ValidationFailed(f"role {self.role} requires a tenant scope", field="scope")
        if self.role == SERVICE_ACCOUNT:
            unknown = set(self.token_actions) - set(PERMISSIONS)
            if unknown:
                raise ValidationFailed(
                    f"service token names unknown actions: {sorted(unknown)}",
                    field="token_actions",
                )
            if not self.token_audience:
                raise ValidationFailed("service token needs an audience", field="token_audience")

    @property
    def is_platform(self) -> bool:
        return self.role == PLATFORM_OWNER

    def token_expired(self, now: float | None = None) -> bool:
        if self.role != SERVICE_ACCOUNT:
            return False
        return (now if now is not None else time.time()) >= self.token_expires_at


def anonymous(scope: TenantScope, subject_id: str) -> Principal:
    """A guest is a `user`. Guests comment; that is the product."""
    return Principal(subject_id=subject_id, role=USER, scope=scope)


def granted(principal: Principal, permission: str) -> bool:
    """Pure grant-table lookup, before any scope or ownership check."""
    if permission not in PERMISSIONS:
        return False
    if permission in PLATFORM_ONLY and not principal.is_platform:
        return False
    if principal.role == SERVICE_ACCOUNT:
        return permission in principal.token_actions
    return permission in GRANTS.get(principal.role, frozenset())


def check_scope(principal: Principal, scope: TenantScope) -> None:
    """Scope first, always.

    Raising here rather than after the permission check is what keeps a foreign
    object indistinguishable from a missing one: the caller never gets far
    enough to learn whether the permission would have applied.
    """
    if principal.is_platform:
        return
    if principal.scope is None:
        raise Unauthenticated("principal has no scope")
    if principal.scope.tenant_id != scope.tenant_id or principal.scope.site_id != scope.site_id:
        # Deliberately the cross-tenant error: a 404 on the wire.
        principal.scope.assert_owns(scope.tenant_id, scope.site_id)


def authorize(
    principal: Principal,
    permission: str,
    scope: TenantScope,
    *,
    owner_subject_id: str | None = None,
    now: float | None = None,
) -> None:
    """The single entry point every write and privileged read goes through."""
    check_scope(principal, scope)

    if principal.role == SERVICE_ACCOUNT and principal.token_expired(now):
        raise Unauthenticated("service token expired")

    if not granted(principal, permission):
        raise Forbidden(f"role {principal.role} lacks {permission}", permission=permission)

    # Ownership gate for the *_own family. A grant of `edit_own` is not a grant
    # of `edit`, and this is where that distinction is actually enforced.
    if permission in (P_EDIT_OWN, P_DELETE_OWN, P_READ_OWN):
        if owner_subject_id is None:
            raise ValidationFailed("ownership check requires an owner", field="owner_subject_id")
        if not hmac.compare_digest(str(owner_subject_id), str(principal.subject_id)):
            # The object exists and belongs to this site, so 403 leaks nothing
            # the caller could not already observe in the published list.
            raise Forbidden("subject does not own this object", permission=permission)


def authorize_role_grant(
    granter: Principal, target_subject_id: str, target_role: str, scope: TenantScope
) -> None:
    """Granting a role. Self-elevation is refused unconditionally."""
    authorize(granter, P_ROLE_GRANT, scope)
    if target_role not in ROLES:
        raise ValidationFailed(f"unknown role {target_role!r}", field="role")
    if hmac.compare_digest(str(target_subject_id), str(granter.subject_id)):
        raise Forbidden("a principal may not change its own role", permission=P_ROLE_GRANT)
    # A tenant owner cannot mint a platform owner; authority may not be
    # escalated sideways by granting it to a confederate either.
    if target_role == PLATFORM_OWNER and not granter.is_platform:
        raise Forbidden("only the platform owner may grant platform_owner", permission=P_ROLE_GRANT)


def authorize_production_approval(
    approver: Principal, *, change_author_subject_id: str, scope: TenantScope
) -> None:
    """Four-eyes on rollout: the author of a change never approves it."""
    authorize(approver, P_PRODUCTION_APPROVE, scope)
    if hmac.compare_digest(str(change_author_subject_id), str(approver.subject_id)):
        raise Forbidden(
            "the author of a change may not approve its rollout",
            permission=P_PRODUCTION_APPROVE,
        )


def issue_service_principal(
    subject_id: str,
    scope: TenantScope,
    actions: Iterable[str],
    *,
    audience: str,
    ttl_seconds: int,
    now: float | None = None,
) -> Principal:
    if ttl_seconds <= 0 or ttl_seconds > SERVICE_TOKEN_MAX_TTL_SECONDS:
        raise ValidationFailed(
            f"service token ttl must be 1..{SERVICE_TOKEN_MAX_TTL_SECONDS} seconds",
            field="ttl_seconds",
        )
    requested = frozenset(actions)
    forbidden = requested & PLATFORM_ONLY
    if forbidden:
        raise Forbidden(
            f"service tokens may not carry platform-only actions: {sorted(forbidden)}",
            permission=sorted(forbidden)[0],
        )
    base = now if now is not None else time.time()
    return Principal(
        subject_id=subject_id,
        role=SERVICE_ACCOUNT,
        scope=scope,
        token_actions=requested,
        token_audience=audience,
        token_expires_at=base + ttl_seconds,
    )


def break_glass(principal: Principal, reason: str) -> Principal:
    """Escalate to platform authority, with a reason, for one operation.

    The reason is mandatory because the audit record is the only thing that
    makes this reversible after the fact. The caller is expected to write that
    record; :func:`comments_platform.audit.record` refuses a break-glass event
    without one.
    """
    authorize_break_glass(principal)
    if not reason or len(reason.strip()) < 12:
        raise ValidationFailed(
            "break-glass needs a substantive reason (12 characters or more)", field="reason"
        )
    return Principal(
        subject_id=principal.subject_id,
        role=PLATFORM_OWNER,
        scope=principal.scope,
        break_glass_reason=reason.strip(),
    )


def authorize_break_glass(principal: Principal) -> None:
    if not principal.is_platform:
        raise Forbidden("break-glass is reserved to the platform owner", permission=P_BREAK_GLASS)


def role_matrix() -> dict[str, Any]:
    """Serialisable grant table, for docs and for the RBAC matrix test."""
    return {
        "schema_version": "COMMENTS_RBAC_V1",
        "default": "deny",
        "roles": list(ROLES),
        "tenant_scoped_roles": sorted(TENANT_SCOPED_ROLES),
        "platform_only_permissions": sorted(PLATFORM_ONLY),
        "permissions": sorted(PERMISSIONS),
        "grants": {role: sorted(perms) for role, perms in GRANTS.items()},
        "invariants": [
            "scope is checked before permission, so cross-tenant reads present as 404",
            "tenant_admin does not hold release.production_deploy",
            "no principal may change its own role",
            "the author of a change may not approve its production rollout",
            f"service token ttl <= {SERVICE_TOKEN_MAX_TTL_SECONDS}s and enumerates its actions",
        ],
    }
