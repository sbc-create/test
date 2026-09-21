"""Identity.

This service stores no passwords and no raw IP addresses. It accepts an opaque
authenticated subject from whatever auth contour a site already runs, and for
sites without login it mints a guest pseudonym.

The property that matters is non-correlation. The same person, the same
browser, the same device visiting `lords` and `zona` must produce two public
ids with no computable relationship, or the comments platform quietly becomes
a cross-site tracker — and one that any API consumer could query. That is
achieved by deriving every public id under a *per-tenant* key: without the
`zona` key, a `lords` id says nothing about the `zona` id, and neither key
lives in this repository.

Network identifiers get the same treatment plus rotation. Anti-abuse needs to
know "these twelve comments came from one place"; it does not need to know
which place, and it does not need to know next week. So the stored value is
HMAC(tenant key, IP + epoch), the epoch turns over daily, and the raw address
is never written anywhere — not to a row, not to a log, not to a metric.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

from .errors import Unauthenticated, ValidationFailed
from .tenancy import TenantScope

# How long a network HMAC epoch lasts. One day: long enough for flood detection
# to see a pattern, short enough that the value is not a durable identifier.
NETWORK_EPOCH_SECONDS = 86_400

# How long network-derived anti-abuse rows may be retained, documented here
# because a retention period that lives only in an operator's head is not a
# retention period.
NETWORK_HMAC_RETENTION_DAYS = 7

GUEST_PREFIX = "g_"
AUTH_PREFIX = "u_"


class SecretResolver(Protocol):
    """Supplies per-tenant keys.

    Deliberately an interface, not a dict of values. Keys reach the process
    through systemd LoadCredential from a file outside the repository; nothing
    here reads `.env`, and no key is ever placed in a default argument.
    """

    def tenant_key(self, tenant_id: str, purpose: str) -> bytes: ...


class InMemorySecretResolver:
    """For tests and local rehearsal only.

    It generates random keys on demand, which is exactly wrong for production —
    restarting would orphan every pseudonym — and exactly right for a test,
    where key material must never be a fixed constant somebody could copy into
    a deployment.
    """

    def __init__(self, seed: Mapping[str, bytes] | None = None) -> None:
        self._keys: dict[str, bytes] = dict(seed or {})

    def tenant_key(self, tenant_id: str, purpose: str) -> bytes:
        slot = f"{tenant_id}:{purpose}"
        if slot not in self._keys:
            self._keys[slot] = secrets.token_bytes(32)
        return self._keys[slot]


@dataclass(frozen=True, slots=True)
class Identity:
    """Who wrote a comment, as far as this platform is willing to know."""

    subject_id: str  # public, tenant-local, opaque
    scope: TenantScope
    is_guest: bool
    display_name: str = ""
    # Present only in memory while handling a request; never persisted.
    network_hmac: str = ""

    def __post_init__(self) -> None:
        if not self.subject_id:
            raise ValidationFailed("subject_id is required", field="subject_id")

    def as_public_dict(self) -> dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "display_name": self.display_name,
            "is_guest": self.is_guest,
        }


def _b64ish(digest: bytes, length: int = 24) -> str:
    """Hex is fine and unambiguous; 24 chars of it is 96 bits of collision space."""
    return digest.hex()[:length]


def derive_public_subject_id(
    secrets_resolver: SecretResolver,
    scope: TenantScope,
    *,
    upstream_subject: str,
    is_guest: bool,
) -> str:
    """Map an upstream identity to a tenant-local public id.

    The site_id is inside the message but the key is per *tenant*: two sites of
    one tenant are still separated, while the key boundary guarantees that a
    holder of one tenant's data cannot derive another tenant's ids even with
    the full upstream subject in hand.
    """
    if not upstream_subject:
        raise Unauthenticated("no upstream subject to derive from")
    key = secrets_resolver.tenant_key(scope.tenant_id, "subject")
    message = f"{scope.tenant_id}\x1f{scope.site_id}\x1f{upstream_subject}".encode()
    digest = hmac.new(key, message, hashlib.sha256).digest()
    return (GUEST_PREFIX if is_guest else AUTH_PREFIX) + _b64ish(digest)


def derive_network_hmac(
    secrets_resolver: SecretResolver,
    scope: TenantScope,
    *,
    remote_addr: str,
    now: datetime | None = None,
) -> str:
    """Rotating, tenant-scoped, one-way network identifier.

    The raw address goes in and does not come out: nothing in the return value,
    the logs or the audit trail can be turned back into an IP without the
    tenant key, and even with it only within the current epoch.
    """
    if not remote_addr:
        return ""
    moment = now or datetime.now(timezone.utc)
    epoch = int(moment.timestamp()) // NETWORK_EPOCH_SECONDS
    key = secrets_resolver.tenant_key(scope.tenant_id, "network")
    message = f"{scope.tenant_id}\x1f{remote_addr}\x1f{epoch}".encode()
    return "n_" + _b64ish(hmac.new(key, message, hashlib.sha256).digest(), 20)


class IdentityProvider(Protocol):
    """What a site's existing auth contour must supply.

    One method, one job: turn a request into an opaque upstream subject, or
    None for an anonymous visitor. The comments platform never sees a password,
    a session cookie's contents or an email address.
    """

    def authenticated_subject(self, request_context: Mapping[str, Any]) -> str | None: ...


class GuestIdentityProvider:
    """Issues and recognises tenant-local guest pseudonyms.

    A guest token is a random opaque string the browser keeps. It is not a
    device fingerprint and not derived from one: fingerprinting would defeat
    the entire non-correlation property this module exists to provide.
    """

    def __init__(self, secrets_resolver: SecretResolver) -> None:
        self._secrets = secrets_resolver

    @staticmethod
    def issue_guest_token() -> str:
        return secrets.token_urlsafe(24)

    def identity_for_guest(
        self, scope: TenantScope, guest_token: str, *, display_name: str = ""
    ) -> Identity:
        if not guest_token or len(guest_token) < 16:
            raise ValidationFailed("guest token is missing or too short", field="guest_token")
        subject = derive_public_subject_id(
            self._secrets, scope, upstream_subject=guest_token, is_guest=True
        )
        return Identity(
            subject_id=subject,
            scope=scope,
            is_guest=True,
            display_name=display_name or f"guest-{subject[len(GUEST_PREFIX):][:6]}",
        )


class IdentityResolver:
    """Front door: request context in, :class:`Identity` out."""

    def __init__(
        self,
        secrets_resolver: SecretResolver,
        upstream: IdentityProvider | None = None,
    ) -> None:
        self._secrets = secrets_resolver
        self._upstream = upstream
        self._guests = GuestIdentityProvider(secrets_resolver)

    def resolve(
        self,
        scope: TenantScope,
        request_context: Mapping[str, Any],
        *,
        allow_guests: bool = True,
        now: datetime | None = None,
    ) -> Identity:
        upstream_subject = (
            self._upstream.authenticated_subject(request_context) if self._upstream else None
        )
        network = derive_network_hmac(
            self._secrets,
            scope,
            remote_addr=str(request_context.get("remote_addr", "")),
            now=now,
        )

        if upstream_subject:
            subject = derive_public_subject_id(
                self._secrets, scope, upstream_subject=upstream_subject, is_guest=False
            )
            return Identity(
                subject_id=subject,
                scope=scope,
                is_guest=False,
                display_name=str(request_context.get("display_name", "") or "")[:64],
                network_hmac=network,
            )

        if not allow_guests:
            raise Unauthenticated("this site requires an authenticated subject")

        token = str(request_context.get("guest_token", "") or "")
        identity = self._guests.identity_for_guest(scope, token)
        return Identity(
            subject_id=identity.subject_id,
            scope=scope,
            is_guest=True,
            display_name=identity.display_name,
            network_hmac=network,
        )


@dataclass
class TenantLocalProfile:
    """Nickname, reputation, mute and ban — all per site, never shared.

    A ban on `lords` must not follow a person to `zona`: they are different
    communities with different rules, and a shared ban list would also be a
    shared identity, which is the thing this module refuses to build.
    """

    scope: TenantScope
    subject_id: str
    display_name: str = ""
    reputation: int = 0
    muted_until: str = ""
    banned: bool = False
    ban_reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def key(self) -> tuple[str, str, str]:
        return (self.scope.tenant_id, self.scope.site_id, self.subject_id)


def privacy_notes() -> dict[str, Any]:
    """Machine-readable statement of what is and is not retained."""
    return {
        "schema_version": "COMMENTS_IDENTITY_PRIVACY_V1",
        "stores_passwords": False,
        "stores_raw_ip": False,
        "stores_email": False,
        "network_identifier": "HMAC(tenant key, ip + daily epoch), one-way",
        "network_epoch_seconds": NETWORK_EPOCH_SECONDS,
        "network_retention_days": NETWORK_HMAC_RETENTION_DAYS,
        "public_id_derivation": "HMAC(per-tenant key, tenant + site + upstream subject)",
        "cross_tenant_correlation": "not computable without both tenant keys",
        "guest_token": "random, not a device fingerprint",
        "profile_scope": "per tenant and site; nicknames, reputation, mutes and bans do not travel",
    }
