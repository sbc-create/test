"""Safe staging runtime discovery/preflight — never prints token bodies."""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from factory.community.comments.flags import comments_dark_flags
from factory.community.comments.qwen import caps
from factory.community.comments.qwen.discovery import discovery_report
from factory.community.comments.qwen.endpoint_policy import validate_endpoint
from factory.community.comments.qwen.provider import discover_config

OWNER_AUTHORIZATION_ID = "COMMUNITY-COMMENTS-QWEN-STAGING-CANARY-20260920-01"
EXPECTED_CREDENTIAL_NAME = "qwen_comments_token"
EXPECTED_ENV = (
    "QWEN_COMMENTS_ENDPOINT",
    "QWEN_COMMENTS_TOKEN_FILE",
    "QWEN_COMMENTS_MODE",
    "QWEN_COMMENTS_MODEL",
)


def endpoint_host(endpoint: str) -> str:
    if not endpoint:
        return ""
    u = urlparse(endpoint.strip())
    return u.hostname or ""


def credential_meta(token_file: str) -> dict[str, Any]:
    """Existence + permission status only — never read file body."""
    p = Path(token_file) if token_file else Path("")
    meta: dict[str, Any] = {
        "credential_exists": False,
        "credential_source_type": "systemd_LoadCredential_or_token_file",
        "credential_name": EXPECTED_CREDENTIAL_NAME,
        "credential_path_set": bool(token_file),
        "credential_permission_status": "MISSING",
        "mode_octal": None,
        "readable_by_process": False,
    }
    if not token_file:
        return meta
    if not p.is_file():
        meta["credential_permission_status"] = "PATH_SET_BUT_MISSING"
        return meta
    meta["credential_exists"] = True
    try:
        st = p.stat()
        mode = stat.S_IMODE(st.st_mode)
        meta["mode_octal"] = oct(mode)
        # Prefer owner-only readable (0o400/0o600)
        world_readable = bool(mode & stat.S_IROTH)
        group_writable = bool(mode & stat.S_IWGRP)
        if world_readable:
            meta["credential_permission_status"] = "INSECURE_WORLD_READABLE"
        elif group_writable:
            meta["credential_permission_status"] = "INSECURE_GROUP_WRITABLE"
        else:
            meta["credential_permission_status"] = "OK_RESTRICTED"
        meta["readable_by_process"] = os.access(p, os.R_OK)
        # Do NOT read contents.
    except OSError as exc:
        meta["credential_permission_status"] = f"STAT_ERROR:{type(exc).__name__}"
    return meta


def runtime_preflight() -> dict[str, Any]:
    """Return sanitized preflight report. Never includes token/Authorization."""
    cfg = discover_config()
    endpoint = os.environ.get("QWEN_COMMENTS_ENDPOINT", "").strip()
    token_file = os.environ.get("QWEN_COMMENTS_TOKEN_FILE", "").strip()
    mode = os.environ.get("QWEN_COMMENTS_MODE", "").strip() or cfg.get("mode")
    model = os.environ.get("QWEN_COMMENTS_MODEL", "").strip()
    timeout = float(os.environ.get("QWEN_COMMENTS_TIMEOUT_SEC", "20") or 20)
    host = endpoint_host(endpoint)
    https_ok = endpoint.lower().startswith("https://") if endpoint else False
    cred = credential_meta(token_file)
    endpoint_policy = validate_endpoint(endpoint)
    discovery = discovery_report()
    flags = comments_dark_flags()
    publication_off = flags.get("COMMENTS_PUBLICATION_ENABLED", 1) == 0
    prod_postmod_off = flags.get("COMMENTS_QWEN_POSTMOD_ENABLED", 1) == 0
    seo_off = flags.get("COMMENTS_SEO_RENDERING_ENABLED", 1) == 0

    checks = {
        "https_endpoint": https_ok,
        "endpoint_host_present": bool(host),
        "endpoint_allowlisted": bool(
            endpoint_policy["allowlisted"]
            and endpoint_policy["post_permitted"]
            and endpoint_policy["purpose_bound"]
        ),
        "endpoint_policy_ok": bool(endpoint_policy["ok"]),
        "credential_scope_ok": bool(discovery["CREDENTIAL_SCOPE_PASS"]),
        "credential_exists": bool(cred["credential_exists"]),
        "credential_permissions_ok": cred["credential_permission_status"] == "OK_RESTRICTED",
        "model_set": bool(model),
        "timeout_set": timeout > 0,
        "timeout_le_20": timeout <= 20.0,
        "request_cap_set": caps.REQUEST_CAP > 0,
        "token_cap_set": caps.INPUT_TOKEN_CAP > 0,
        "spend_cap_set": caps.SPEND_CAP_RUB > 0,
        "production_publication_off": publication_off,
        "production_postmod_off": prod_postmod_off,
        "seo_rendering_off": seo_off,
        "mode_http_post": mode == "http_post",
    }
    ready = all(
        [
            checks["https_endpoint"],
            checks["endpoint_allowlisted"],
            checks["endpoint_policy_ok"],
            checks["credential_scope_ok"],
            checks["credential_exists"],
            checks["credential_permissions_ok"],
            checks["model_set"],
            checks["timeout_le_20"],
            checks["production_publication_off"],
            checks["mode_http_post"],
        ]
    )
    return {
        "OWNER_AUTHORIZATION_ID": OWNER_AUTHORIZATION_ID,
        "EXPECTED_CREDENTIAL_NAME": EXPECTED_CREDENTIAL_NAME,
        "QWEN_PROVIDER_CONFIGURED": "YES" if ready else "NO",
        "QWEN_CREDENTIAL_MODE": "LoadCredential" if cred["credential_path_set"] else "UNSET",
        "QWEN_ENDPOINT_HOST": host,
        "QWEN_MODEL": model or "",
        "timeout_sec": timeout,
        "checks": checks,
        "credential": cred,
        "endpoint_policy": endpoint_policy,
        "credential_scope": {
            "QWEN_COMMENTS_CREDENTIAL_CONFIGURED": discovery[
                "QWEN_COMMENTS_CREDENTIAL_CONFIGURED"
            ],
            "CREDENTIAL_SCOPE_PASS": discovery["CREDENTIAL_SCOPE_PASS"],
            "REUSABLE_FOREIGN_CREDENTIALS": discovery["REUSABLE_FOREIGN_CREDENTIALS"],
            "verdict": discovery["verdict"],
        },
        "discover": {
            "configured": cfg.get("configured"),
            "endpoint_set": cfg.get("endpoint_set"),
            "token_file_set": cfg.get("token_file_set"),
            "token_file_exists": cfg.get("token_file_exists"),
            "mode": cfg.get("mode"),
        },
        "caps": caps.caps_public_status(),
        "READY_FOR_REAL_CANARY": bool(ready),
        "BLOCKED_REASON": None if ready else _blocked_reason(checks),
        "BLOCKING_CHECKS": [] if ready else sorted(k for k, v in checks.items() if not v),
    }


def _blocked_reason(checks: dict[str, bool]) -> str:
    """Name the most actionable failing gate rather than a generic message."""
    if not checks["credential_exists"]:
        return "missing_qwen_comments_credential"
    if not checks["credential_permissions_ok"]:
        return "qwen_comments_credential_permissions_insecure"
    if not checks["credential_scope_ok"]:
        return "qwen_comments_credential_scope_unconfirmed"
    if not checks["https_endpoint"]:
        return "qwen_comments_endpoint_not_https"
    if not checks["endpoint_allowlisted"]:
        return "qwen_comments_endpoint_not_in_inventory_allowlist"
    if not checks["endpoint_policy_ok"]:
        return "qwen_comments_endpoint_policy_violation"
    if not checks["model_set"]:
        return "qwen_comments_model_not_set"
    if not checks["mode_http_post"]:
        return "qwen_comments_mode_not_http_post"
    return "missing_or_incomplete_qwen_runtime_config"
