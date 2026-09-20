"""SIGNED_PSEUDONYMOUS_DEVICE_V1 — opaque server-minted voter identity.

Registration is not required. The server issues a random opaque id, signs it
with a server secret, and stores only the opaque id in the vote ledger.
Raw IP / email / FIO / phone / browser fingerprint are never part of the id.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

IDENTITY_MODE = "SIGNED_PSEUDONYMOUS_DEVICE_V1"
COOKIE_NAME = "yummy_cr_vid"
COOKIE_PATH = "/"
COOKIE_MAX_AGE = 31536000  # 1 year
COOKIE_ATTRS = ("Secure", "HttpOnly", "SameSite=Lax", f"Path={COOKIE_PATH}")

# Space isolation: this cookie/identity is valid only for the yummy rating space.
BOUND_RATING_SPACE = "yummy"
TOKEN_VERSION = "v1"


class IdentityError(Exception):
    status = 401


class IdentityForgery(IdentityError):
    status = 401


def _load_secret_bytes(env_name: str, file_env: str) -> bytes:
    path = os.environ.get(file_env, "").strip()
    if path:
        raw = Path(path).read_bytes().strip()
        if raw:
            return raw
    env = os.environ.get(env_name, "").strip()
    if env:
        return env.encode()
    # Dev/test fallback — production unit must inject real credential.
    return b"dev-only-identity-rotate"


def identity_signing_secrets() -> tuple[bytes, tuple[bytes, ...]]:
    """Return (current_secret, older_secrets_for_verify)."""
    current = _load_secret_bytes(
        "COMMUNITY_IDENTITY_HMAC_SECRET",
        "COMMUNITY_IDENTITY_HMAC_SECRET_FILE",
    )
    older: list[bytes] = []
    for i in (1, 2):
        env = f"COMMUNITY_IDENTITY_HMAC_SECRET_PREV{i}"
        file_env = f"COMMUNITY_IDENTITY_HMAC_SECRET_PREV{i}_FILE"
        try:
            older.append(_load_secret_bytes(env, file_env))
        except OSError:
            continue
        if not os.environ.get(env) and not os.environ.get(file_env):
            older.pop()
    return current, tuple(older)


def mint_identity_id() -> str:
    """Cryptographically strong opaque id — no user attributes."""
    return secrets.token_hex(16)  # 128-bit


def _sign(identity_id: str, secret: bytes, *, space: str = BOUND_RATING_SPACE) -> str:
    msg = f"{TOKEN_VERSION}|{space}|{identity_id}".encode()
    return hmac.new(secret, msg, hashlib.sha256).hexdigest()


def issue_token(*, identity_id: str | None = None, space: str = BOUND_RATING_SPACE) -> str:
    if space != BOUND_RATING_SPACE:
        raise IdentityError(f"identity space not allowed: {space}")
    iid = identity_id or mint_identity_id()
    if not _valid_opaque_id(iid):
        raise IdentityError("invalid identity id shape")
    current, _ = identity_signing_secrets()
    sig = _sign(iid, current, space=space)
    return f"{TOKEN_VERSION}.{iid}.{sig}"


def _valid_opaque_id(identity_id: str) -> bool:
    if not identity_id or len(identity_id) != 32:
        return False
    try:
        int(identity_id, 16)
    except ValueError:
        return False
    return True


def verify_token(token: str | None, *, space: str = BOUND_RATING_SPACE) -> str:
    """Return identity_id or raise. Constant-time signature check."""
    if not token or not isinstance(token, str):
        raise IdentityError("missing identity cookie")
    parts = token.strip().split(".")
    if len(parts) != 3:
        raise IdentityForgery("malformed identity token")
    ver, iid, sig = parts
    if ver != TOKEN_VERSION:
        raise IdentityForgery("unsupported identity token version")
    if space != BOUND_RATING_SPACE:
        raise IdentityForgery("cross-space identity rejected")
    if not _valid_opaque_id(iid):
        raise IdentityForgery("invalid identity id")
    if not isinstance(sig, str) or len(sig) != 64:
        raise IdentityForgery("invalid signature shape")
    current, older = identity_signing_secrets()
    candidates = (current, *older)
    ok = False
    for secret in candidates:
        expected = _sign(iid, secret, space=space)
        if hmac.compare_digest(expected, sig):
            ok = True
            break
    if not ok:
        raise IdentityForgery("identity signature mismatch")
    return iid


def parse_cookie_header(cookie_header: str | None, name: str = COOKIE_NAME) -> str | None:
    if not cookie_header:
        return None
    for part in cookie_header.split(";"):
        part = part.strip()
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        if k.strip() == name:
            return v.strip()
    return None


def set_cookie_header(token: str, *, max_age: int = COOKIE_MAX_AGE) -> str:
    attrs = "; ".join(COOKIE_ATTRS)
    return f"{COOKIE_NAME}={token}; Max-Age={max_age}; {attrs}"


def clear_cookie_header() -> str:
    attrs = "; ".join(COOKIE_ATTRS)
    return f"{COOKIE_NAME}=; Max-Age=0; {attrs}"


def redact_identity(identity_id: str) -> str:
    """Admin display: ab12…90ef"""
    if len(identity_id) < 8:
        return "****"
    return f"{identity_id[:4]}…{identity_id[-4:]}"


@dataclass(frozen=True)
class ResolvedIdentity:
    identity_id: str
    rating_space_id: str
    mode: str = IDENTITY_MODE
    minted: bool = False

    def as_public(self) -> dict[str, Any]:
        return {
            "identity_mode": self.mode,
            "rating_space_id": self.rating_space_id,
            "identity_redacted": redact_identity(self.identity_id),
            "minted": self.minted,
            # Never expose full id to public clients in JSON bodies.
        }


def resolve_or_mint(
    cookie_header: str | None,
    *,
    space: str = BOUND_RATING_SPACE,
    mint_if_missing: bool = True,
) -> tuple[ResolvedIdentity, str | None]:
    """Returns (identity, set_cookie_value_or_None)."""
    raw = parse_cookie_header(cookie_header)
    if raw:
        iid = verify_token(raw, space=space)
        return ResolvedIdentity(iid, space, minted=False), None
    if not mint_if_missing:
        raise IdentityError("missing identity cookie")
    iid = mint_identity_id()
    token = issue_token(identity_id=iid, space=space)
    return ResolvedIdentity(iid, space, minted=True), token


def reject_client_supplied_user_id(body: dict[str, Any] | None) -> None:
    """Public API must ignore/reject client-provided user ids."""
    if not body:
        return
    forbidden = (
        "user_id",
        "userId",
        "actor_id",
        "actorId",
        "identity_id",
        "identityId",
        "pseudonymous_identity_id",
        "account_id",
        "accountId",
    )
    for key in forbidden:
        if key in body:
            raise IdentityForgery(f"client-supplied {key} rejected")
