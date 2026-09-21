"""Endpoint allowlist + validation for the Qwen comments provider.

COMMUNITY-COMMENTS-03 block B08.

`inventory/` is the only source of reachable hosts (`.claude/rules/infrastructure.md`:
a value absent from inventory does not exist — the answer is ``BLOCKED_ACCESS``,
not a guess). This gate refuses a Qwen endpoint that:

* is not HTTPS, or carries userinfo / query / fragment (secret-leak shapes),
* resolves to no host, an IP literal, or a loopback / private / link-local name,
* uses a non-443 port,
* names a host absent from ``inventory/network-allowlist.yaml``,
* names an allowlisted host whose entry does not permit ``POST``.

No allowlist entry for a Qwen comments host exists today, so a correct owner
configuration needs both the runtime values *and* an inventory entry.
"""

from __future__ import annotations

import ipaddress
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

DEFAULT_ALLOWLIST = Path("inventory/network-allowlist.yaml")

REQUIRED_METHOD = "POST"
ALLOWED_PORTS = frozenset({None, 443})

# An allowlist entry authorizes one purpose, not "any outbound call". A host
# admitted for e.g. comments *research* must not double as a moderation
# provider, so the entry has to carry this exact ref.
REQUIRED_ALLOWLIST_REF = "community-comments-qwen-postmod"

# Hostnames that must never be a provider endpoint even if someone lists them.
FORBIDDEN_HOST_SUFFIXES = (
    ".local",
    ".internal",
    ".localdomain",
)
FORBIDDEN_HOSTS = frozenset({"localhost", "localhost.localdomain"})


def load_allowlist(path: Path | None = None) -> list[dict[str, Any]]:
    """Load inventory host entries. Missing file → empty allowlist (deny-all)."""
    p = path or DEFAULT_ALLOWLIST
    if not p.is_file():
        return []
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    hosts = raw.get("hosts") or []
    return [h for h in hosts if isinstance(h, dict)]


def _is_ip_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


def _is_non_public_ip(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return bool(
        ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved
    )


def validate_endpoint(
    endpoint: str,
    *,
    allowlist_path: Path | None = None,
) -> dict[str, Any]:
    """Validate a Qwen comments endpoint. Returns a sanitized structured verdict.

    The returned dict never contains credentials: userinfo, query and fragment
    are reported as booleans, never echoed.
    """
    errors: list[str] = []
    raw = (endpoint or "").strip()
    result: dict[str, Any] = {
        "schema_version": "COMMENTS_QWEN_ENDPOINT_POLICY_V1",
        "endpoint_set": bool(raw),
        "scheme_https": False,
        "host": "",
        "port": None,
        "has_userinfo": False,
        "has_query": False,
        "has_fragment": False,
        "is_ip_literal": False,
        "is_non_public": False,
        "allowlisted": False,
        "allowlist_ref": "",
        "purpose_bound": False,
        "post_permitted": False,
        "errors": errors,
        "ok": False,
    }
    if not raw:
        errors.append("endpoint_not_set")
        return result

    try:
        parts = urlsplit(raw)
    except ValueError:
        errors.append("endpoint_unparseable")
        return result

    result["scheme_https"] = parts.scheme.lower() == "https"
    if not result["scheme_https"]:
        errors.append("endpoint_not_https")

    host = (parts.hostname or "").strip().lower().rstrip(".")
    result["host"] = host
    if not host:
        errors.append("endpoint_host_missing")

    result["has_userinfo"] = bool(parts.username or parts.password)
    if result["has_userinfo"]:
        errors.append("endpoint_carries_userinfo")

    result["has_query"] = bool(parts.query)
    if result["has_query"]:
        errors.append("endpoint_carries_query")

    result["has_fragment"] = bool(parts.fragment)
    if result["has_fragment"]:
        errors.append("endpoint_carries_fragment")

    try:
        port = parts.port
    except ValueError:
        port = None
        errors.append("endpoint_port_invalid")
    result["port"] = port
    if port not in ALLOWED_PORTS:
        errors.append(f"endpoint_port_not_allowed:{port}")

    if host:
        result["is_ip_literal"] = _is_ip_literal(host)
        if result["is_ip_literal"]:
            errors.append("endpoint_is_ip_literal")
        result["is_non_public"] = _is_non_public_ip(host)
        if result["is_non_public"]:
            errors.append("endpoint_is_non_public_address")
        if host in FORBIDDEN_HOSTS or host.endswith(FORBIDDEN_HOST_SUFFIXES):
            errors.append("endpoint_is_internal_hostname")

    entries = load_allowlist(allowlist_path)
    match = next(
        (e for e in entries if str(e.get("host", "")).strip().lower() == host),
        None,
    )
    if host and match is not None:
        result["allowlisted"] = True
        result["allowlist_ref"] = str(match.get("ref") or "")
        methods = [str(m).upper() for m in (match.get("methods") or [])]
        result["post_permitted"] = REQUIRED_METHOD in methods
        if not result["post_permitted"]:
            errors.append("endpoint_allowlist_entry_forbids_post")
        result["purpose_bound"] = result["allowlist_ref"] == REQUIRED_ALLOWLIST_REF
        if not result["purpose_bound"]:
            errors.append("endpoint_allowlist_entry_not_scoped_to_comments_postmod")
    elif host:
        errors.append("endpoint_host_not_in_inventory_allowlist")

    result["ok"] = not errors
    return result


def endpoint_policy_status(
    endpoint: str, *, allowlist_path: Path | None = None
) -> dict[str, Any]:
    """Compact status for preflight/evidence embedding."""
    v = validate_endpoint(endpoint, allowlist_path=allowlist_path)
    return {
        "QWEN_ENDPOINT_HTTPS_PASS": bool(v["scheme_https"]),
        "QWEN_ENDPOINT_ALLOWLIST_PASS": bool(
            v["allowlisted"] and v["post_permitted"] and v["purpose_bound"]
        ),
        "QWEN_ENDPOINT_POLICY_PASS": bool(v["ok"]),
        "QWEN_ENDPOINT_HOST": v["host"],
        "errors": list(v["errors"]),
    }
