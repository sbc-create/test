"""Repo-wide Qwen runtime configuration discovery + credential scope audit.

COMMUNITY-COMMENTS-03 block B07.

Answers one question only: *does a Qwen runtime configuration already exist in
this factory whose declared scope permits community-comments post-moderation?*

Hard rules enforced here:

* Presence and scope only. This module never reads a credential body, never
  emits a token, and never puts a secret path's *contents* anywhere.
* A credential belonging to another module is never reusable unless that
  module's declared scope explicitly covers comments post-moderation.
  Absence of an explicit grant is ``BLOCKED``, never "probably fine".
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# Declared Qwen/LLM-adjacent runtime configuration families known to the factory.
# `scope` is the scope the owner granted that family, not an aspiration.
KNOWN_QWEN_CONFIG_FAMILIES: tuple[dict[str, Any], ...] = (
    {
        "family": "ratings_qwen_delivery",
        "module": "factory/ratings/qwen_delivery.py",
        "env_keys": (
            "QWEN_DELIVERY_ENDPOINT",
            "QWEN_DELIVERY_TOKEN_FILE",
            "QWEN_DELIVERY_MODE",
        ),
        "declared_scope": "ratings-ingestion daily report delivery (outbound report POST)",
        "grants_comments_postmoderation": False,
        "scope_reuse_verdict": "BLOCKED_SCOPE_MISMATCH",
        "scope_reuse_reason": (
            "Scope is ratings report delivery. It authorizes shipping a finished "
            "report, not submitting user-authored comment text for classification. "
            "Reusing this token for comments would send new data categories to an "
            "endpoint the owner approved for a different payload."
        ),
        "evidence_ref": "artifacts/evidence/ratings-ingestion-04/QWEN_DELIVERY_CONFIG_REQUIRED.md",
    },
    {
        "family": "comments_qwen_postmod",
        "module": "factory/community/comments/qwen/provider.py",
        "env_keys": (
            "QWEN_COMMENTS_ENDPOINT",
            "QWEN_COMMENTS_TOKEN_FILE",
            "QWEN_COMMENTS_MODE",
            "QWEN_COMMENTS_MODEL",
        ),
        "declared_scope": "community-comments post-moderation classification (this stage)",
        "grants_comments_postmoderation": True,
        "scope_reuse_verdict": "OWN_SCOPE",
        "scope_reuse_reason": "Purpose-built credential for this stage.",
        "evidence_ref": "artifacts/evidence/community-comments-03/01-runtime/RUNTIME_PREFLIGHT.json",
    },
    {
        "family": "control_plane_qwen_consumer",
        "module": "docs/ai/control-plane.md",
        "env_keys": (),
        "declared_scope": (
            "Qwen as an *inbound* consumer of the factory control API "
            "(declared OpenAPI routes only)"
        ),
        "grants_comments_postmoderation": False,
        "scope_reuse_verdict": "NOT_A_CREDENTIAL",
        "scope_reuse_reason": (
            "Opposite direction: this is external automation calling the factory, "
            "not the factory holding an outbound provider token. Nothing to reuse."
        ),
        "evidence_ref": "docs/ai/control-plane.md",
    },
)


def _env_presence(env_keys: tuple[str, ...]) -> dict[str, bool]:
    """Report which env keys are *set* and non-empty. Values are never returned."""
    return {key: bool(os.environ.get(key, "").strip()) for key in env_keys}


def _token_file_presence(env_key: str) -> dict[str, Any]:
    """Existence + mode of a token file. Contents are never read."""
    raw = os.environ.get(env_key, "").strip()
    meta: dict[str, Any] = {
        "path_env_key": env_key,
        "path_set": bool(raw),
        "exists": False,
        "mode_octal": None,
    }
    if not raw:
        return meta
    p = Path(raw)
    if p.is_file():
        meta["exists"] = True
        try:
            meta["mode_octal"] = oct(p.stat().st_mode & 0o777)
        except OSError as exc:  # pragma: no cover - defensive
            meta["mode_octal"] = f"STAT_ERROR:{type(exc).__name__}"
    return meta


def discover_families() -> list[dict[str, Any]]:
    """Presence + scope for every known Qwen config family. No secrets."""
    out: list[dict[str, Any]] = []
    for fam in KNOWN_QWEN_CONFIG_FAMILIES:
        env_keys: tuple[str, ...] = tuple(fam["env_keys"])
        presence = _env_presence(env_keys)
        token_key = next((k for k in env_keys if k.endswith("_TOKEN_FILE")), "")
        token_meta = _token_file_presence(token_key) if token_key else None
        configured = bool(presence) and all(presence.values()) and bool(
            token_meta and token_meta["exists"]
        )
        out.append(
            {
                "family": fam["family"],
                "module": fam["module"],
                "declared_scope": fam["declared_scope"],
                "env_keys_present": presence,
                "token_file": token_meta,
                "configured": configured,
                "grants_comments_postmoderation": fam["grants_comments_postmoderation"],
                "scope_reuse_verdict": fam["scope_reuse_verdict"],
                "scope_reuse_reason": fam["scope_reuse_reason"],
                "evidence_ref": fam["evidence_ref"],
            }
        )
    return out


def discovery_report() -> dict[str, Any]:
    """Full B07 report: which config exists, and may any of it be reused here?"""
    families = discover_families()
    own = next(
        (f for f in families if f["family"] == "comments_qwen_postmod"), None
    )
    reusable = [
        f
        for f in families
        if f["configured"]
        and f["grants_comments_postmoderation"]
        and f["family"] != "comments_qwen_postmod"
    ]
    own_configured = bool(own and own["configured"])
    blocked_reuse = [
        {
            "family": f["family"],
            "verdict": f["scope_reuse_verdict"],
            "reason": f["scope_reuse_reason"],
        }
        for f in families
        if not f["grants_comments_postmoderation"]
    ]
    return {
        "schema_version": "COMMENTS_QWEN_RUNTIME_DISCOVERY_V1",
        "families_scanned": len(families),
        "families": families,
        "QWEN_COMMENTS_CREDENTIAL_CONFIGURED": "YES" if own_configured else "NO",
        "REUSABLE_FOREIGN_CREDENTIALS": len(reusable),
        "blocked_reuse": blocked_reuse,
        "CREDENTIAL_SCOPE_PASS": bool(own_configured),
        "verdict": "OWN_CREDENTIAL_PRESENT"
        if own_configured
        else "NO_IN_SCOPE_CREDENTIAL",
        "notes": [
            "Presence and scope only — no credential body is read or emitted.",
            "A foreign-module token is never borrowed; scope must grant comments "
            "post-moderation explicitly.",
        ],
    }
