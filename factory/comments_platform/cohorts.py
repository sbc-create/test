"""Cohort gating: who, inside one site, is currently served comments.

The site flags in `flags.py` answer "is this capability on for this site".
That is not enough for a Stage 1 pilot, where the answer has to be "on for the
owner, off for everyone else, on the same page, at the same moment". So a
second axis exists: a cohort.

Two cohorts, and the asymmetry between them is the whole design:

* `PUBLIC` — every ordinary visitor. Gets nothing. Not an empty box, not a
  spinner, not a broken block: the page is served exactly as it is served
  today, because a pilot that visibly changes the site for people who are not
  in it is not a pilot.
* `OWNER_TEST` — a named audience proven by a signed cookie. Gets read, write
  and publication, all still bounded by the site flags above them.

How membership is proven, and why not the obvious alternatives:

* **Not a URL parameter.** A secret in a query string lands in access logs,
  `Referer` headers, browser history and any screenshot of the address bar. It
  is also trivially shareable by accident. The brief forbids it and it would
  be wrong regardless.
* **Not an IP allowlist.** An address is not a person: it changes on a phone,
  it is shared behind NAT, and it cannot be revoked for one individual. It is
  a coarse *additional* condition at best, never the mechanism.
* **A cookie holding an HMAC over (tenant, site, cohort, subject, expiry)**,
  signed with a per-tenant key that never leaves the server. The cookie proves
  membership without the server storing a session, it expires on its own, and
  revoking it is a key rotation.

The token is verified in constant time, checked against the exact scope it was
issued for, and refused when expired. A token minted for `animedia.icu` does
not work on `animedia.space`, because the site id is inside the signed message
rather than alongside it.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .errors import Unauthenticated, ValidationFailed
from .identity import SecretResolver
from .tenancy import TenantScope

PUBLIC = "public"
OWNER_TEST = "owner_test"

COHORTS = (PUBLIC, OWNER_TEST)

# The cookie a member of the owner cohort carries. Set by the operator once,
# over HTTPS, HttpOnly, SameSite=Lax, scoped to the site's own host.
COHORT_COOKIE = "cp_cohort"

# How long a cohort token stays valid. Short enough that a leaked token is a
# bounded problem, long enough that the owner is not re-issued one mid-test.
DEFAULT_TTL_SECONDS = 7 * 24 * 3600

# Cookie attributes the operator must use. Stated here so the runbook and the
# code cannot drift apart about what "securely" meant.
COOKIE_ATTRIBUTES = {
    "HttpOnly": True,
    "Secure": True,
    "SameSite": "Lax",
    "Path": "/",
    "Domain": "exact host only — never a parent domain",
}


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


@dataclass(frozen=True, slots=True)
class CohortMembership:
    cohort: str
    scope: TenantScope
    subject_id: str
    expires_at: int

    @property
    def is_owner_test(self) -> bool:
        return self.cohort == OWNER_TEST

    def as_dict(self) -> dict[str, Any]:
        # No token, no signature, no expiry secret — only what is safe to log.
        return {"cohort": self.cohort, "site_id": self.scope.site_id}


def _message(scope: TenantScope, cohort: str, subject_id: str, expires_at: int) -> bytes:
    # Every field that the token authorises is inside the signed message. A
    # field kept outside it could be changed by whoever holds the cookie.
    return f"{scope.tenant_id}\x1f{scope.site_id}\x1f{cohort}\x1f{subject_id}\x1f{expires_at}".encode()


def issue_cohort_token(
    secrets: SecretResolver,
    scope: TenantScope,
    *,
    cohort: str,
    subject_id: str,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    now: float | None = None,
) -> str:
    """Mint a cohort cookie value. Never logged, never printed into a report."""
    if cohort not in COHORTS:
        raise ValidationFailed(f"unknown cohort {cohort!r}", field="cohort")
    if cohort == PUBLIC:
        # A token for "everyone" would be a token that proves nothing while
        # looking like proof.
        raise ValidationFailed("the public cohort is not tokenised", field="cohort")
    if ttl_seconds <= 0 or ttl_seconds > DEFAULT_TTL_SECONDS:
        raise ValidationFailed(
            f"cohort ttl must be 1..{DEFAULT_TTL_SECONDS} seconds", field="ttl_seconds"
        )
    if not subject_id:
        raise ValidationFailed("a cohort token needs a subject", field="subject_id")

    expires_at = int((now if now is not None else time.time()) + ttl_seconds)
    key = secrets.tenant_key(scope.tenant_id, "cohort")
    signature = hmac.new(key, _message(scope, cohort, subject_id, expires_at), hashlib.sha256)
    payload = f"{cohort}.{subject_id}.{expires_at}"
    return f"{_b64(payload.encode())}.{_b64(signature.digest())}"


def verify_cohort_token(
    secrets: SecretResolver,
    scope: TenantScope,
    token: str,
    *,
    now: float | None = None,
) -> CohortMembership | None:
    """Return the membership a valid token proves, or None.

    None rather than an exception for a malformed or absent cookie: an
    ordinary visitor has no token, and that is not an error condition — it is
    the overwhelmingly common case.
    """
    if not token or token.count(".") != 1:
        return None
    payload_part, signature_part = token.split(".", 1)
    try:
        payload = _unb64(payload_part).decode("utf-8")
        signature = _unb64(signature_part)
    except (ValueError, UnicodeDecodeError):
        return None

    parts = payload.split(".")
    if len(parts) != 3:
        return None
    cohort, subject_id, expires_raw = parts
    if cohort not in COHORTS or cohort == PUBLIC:
        return None
    try:
        expires_at = int(expires_raw)
    except ValueError:
        return None

    key = secrets.tenant_key(scope.tenant_id, "cohort")
    expected = hmac.new(key, _message(scope, cohort, subject_id, expires_at), hashlib.sha256)
    # Constant time: a byte-by-byte comparison leaks the signature through
    # timing, one byte at a time.
    if not hmac.compare_digest(expected.digest(), signature):
        return None

    if (now if now is not None else time.time()) >= expires_at:
        return None

    return CohortMembership(
        cohort=cohort, scope=scope, subject_id=subject_id, expires_at=expires_at
    )


class CohortResolver:
    """Request context in, cohort out. The only way a caller joins a cohort."""

    def __init__(self, secrets: SecretResolver, *, cookie_name: str = COHORT_COOKIE) -> None:
        self._secrets = secrets
        self._cookie = cookie_name

    def resolve(
        self,
        scope: TenantScope,
        request_context: Mapping[str, Any],
        *,
        now: float | None = None,
    ) -> CohortMembership:
        """Membership from the cookie alone.

        Deliberately reads nothing else. Earlier drafts of this kind of gate
        tend to accumulate "or the query parameter, or the header, or this
        address range", and each addition is a way in that nobody is watching.
        """
        cookies = request_context.get("cookies") or {}
        token = str(cookies.get(self._cookie, "") or "")

        # A token supplied anywhere other than the cookie is refused loudly,
        # rather than ignored: it means an adapter is trying the forbidden
        # route, and silence would let that ship.
        for forbidden_source in ("query", "body"):
            container = request_context.get(forbidden_source) or {}
            if isinstance(container, Mapping) and any(
                str(k).lower() in (self._cookie, "cohort", "cp_cohort", "owner_token")
                for k in container
            ):
                raise ValidationFailed(
                    "a cohort token may only be presented as a cookie",
                    field=forbidden_source,
                )

        membership = verify_cohort_token(self._secrets, scope, token, now=now)
        if membership is not None:
            return membership
        return CohortMembership(
            cohort=PUBLIC, scope=scope, subject_id="", expires_at=0
        )

    def require_owner_test(
        self,
        scope: TenantScope,
        request_context: Mapping[str, Any],
        *,
        now: float | None = None,
    ) -> CohortMembership:
        membership = self.resolve(scope, request_context, now=now)
        if not membership.is_owner_test:
            raise Unauthenticated("this capability is limited to the owner test cohort")
        return membership


def cohort_contract() -> dict[str, Any]:
    return {
        "schema_version": "COMMENTS_COHORTS_V1",
        "cohorts": list(COHORTS),
        "membership_proof": "HMAC over (tenant, site, cohort, subject, expiry) under a per-tenant key",
        "transport": f"cookie {COHORT_COOKIE}",
        "cookie_attributes": COOKIE_ATTRIBUTES,
        "default_ttl_seconds": DEFAULT_TTL_SECONDS,
        "never": [
            "a token in a URL query string",
            "a token in a request body",
            "an IP allowlist used as the mechanism",
            "a server-side session store",
            "printing the token into a report, a log or a metric",
        ],
        "public_cohort_experience": (
            "identical to the site without comments — no container, no spinner, "
            "no empty block, no error"
        ),
        "cross_site": "a token names its site inside the signed message, so it does not travel",
        "revocation": "rotate the tenant cohort key",
    }
