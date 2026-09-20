"""Public display helpers for anonymous comment authors.

Never expose internal identity_id. Use neutral «Гость» or a short
HMAC-scoped alias «Гость A7F2» within a title/thread scope.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from pathlib import Path

from factory.community.identity_v1 import IDENTITY_MODE

DISPLAY_NAME_NEUTRAL = "Гость"
PURPOSE = "comments_guest_alias_v1"


def _alias_secret() -> bytes:
    path = os.environ.get("COMMUNITY_IDENTITY_HMAC_SECRET_FILE", "").strip()
    if path and Path(path).is_file():
        return Path(path).read_bytes().strip()
    env = os.environ.get("COMMUNITY_IDENTITY_HMAC_SECRET", "").strip()
    if env:
        return env.encode()
    return b"dev-only-identity-rotate"


def guest_display_name(
    *,
    identity_id: str,
    site_space: str,
    title_id: str,
    distinguish: bool = False,
) -> str:
    """Return public-facing author label. Never returns identity_id."""
    if not distinguish:
        return DISPLAY_NAME_NEUTRAL
    msg = f"{PURPOSE}|{site_space}|{title_id}|{identity_id}".encode()
    digest = hmac.new(_alias_secret(), msg, hashlib.sha256).hexdigest()[:4].upper()
    return f"{DISPLAY_NAME_NEUTRAL} {digest}"


def public_author_dto(
    *,
    identity_id: str,
    site_space: str,
    title_id: str,
    thread_identity_ids: list[str] | None = None,
) -> dict[str, str]:
    """Safe author DTO for public/admin-preview responses."""
    peers = thread_identity_ids or []
    distinguish = len({*peers, identity_id}) > 1
    return {
        "display_name": guest_display_name(
            identity_id=identity_id,
            site_space=site_space,
            title_id=title_id,
            distinguish=distinguish,
        ),
        "identity_mode": IDENTITY_MODE,
        # Explicitly omit identity_id / device / cookie fields.
    }
