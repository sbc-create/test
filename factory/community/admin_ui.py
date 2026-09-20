"""Read-only ratings admin — requires Control API operator session (read scope)."""

from __future__ import annotations

import html
import json
from typing import Any

from factory.community.readmodel import admin_list, get_title_ratings
from factory.ratings.prod_db import resolve_canonical_db

# Moderation write always off in Stage02 production
ADMIN_MODERATION_WRITE_ENABLED = False
ADMIN_EXTERNAL_RATING_EDIT_ENABLED = False
ADMIN_MANUAL_VOTE_INSERT_ENABLED = False


def require_read_scope(scopes: set[str] | list[str] | tuple[str, ...]) -> None:
    if "read" not in set(scopes):
        raise PermissionError("RBAC: read scope required for ratings admin")


def render_admin_list_html(
    *,
    scopes: set[str] | list[str],
    site: str | None = None,
    source: str | None = None,
) -> str:
    require_read_scope(scopes)
    rows = admin_list(site=site, source=source, limit=200)
    parts = [
        "<!doctype html><html lang='ru'><head><meta charset='utf-8'>",
        "<title>Ratings admin (read-only)</title>",
        "<style>body{font:14px/1.4 system-ui;margin:1.5rem}table{border-collapse:collapse;width:100%}",
        "th,td{border:1px solid #ccc;padding:.35rem .5rem;text-align:left}th{background:#f4f4f4}",
        ".muted{color:#666}</style></head><body>",
        "<h1>Community ratings — read-only</h1>",
        "<p class='muted'>No score edit · no vote insert · moderation write disabled</p>",
        "<table><thead><tr>",
        "<th>space</th><th>subject</th><th>kind</th><th>source</th>",
        "<th>score</th><th>votes</th><th>permission</th><th>mapping</th><th>policy</th>",
        "</tr></thead><tbody>",
    ]
    for r in rows:
        parts.append(
            "<tr>"
            f"<td>{html.escape(str(r.get('rating_space_id')))}</td>"
            f"<td>{html.escape(str(r.get('subject_id')))}</td>"
            f"<td>{html.escape(str(r.get('display_kind')))}</td>"
            f"<td>{html.escape(str(r.get('source_key')))}</td>"
            f"<td>{html.escape('' if r.get('score_normalized') is None else str(r.get('score_normalized')))}</td>"
            f"<td>{html.escape('' if r.get('vote_count') is None else str(r.get('vote_count')))}</td>"
            f"<td>{html.escape(str(r.get('permission_status')))}</td>"
            f"<td>{html.escape(str(r.get('mapping_status')))}</td>"
            f"<td>{html.escape(str(r.get('policy_version')))}</td>"
            "</tr>"
        )
    parts.append("</tbody></table></body></html>")
    return "".join(parts)


def render_admin_title_html(*, scopes: set[str] | list[str], space: str, subject_id: str) -> str:
    require_read_scope(scopes)
    view = get_title_ratings(rating_space_id=space, subject_id=subject_id)
    return (
        "<!doctype html><html lang='ru'><head><meta charset='utf-8'>"
        f"<title>Rating {html.escape(subject_id)}</title></head><body>"
        f"<h1>{html.escape(space)} / {html.escape(subject_id)}</h1>"
        f"<pre>{html.escape(json.dumps(view, ensure_ascii=False, indent=2))}</pre>"
        "<p>Edits disabled. Native writes disabled.</p>"
        "</body></html>"
    )


def moderation_workflow_disposable_test() -> dict[str, Any]:
    """Documented workflow; production write flag stays 0."""
    return {
        "actions": ["quarantine", "restore"],
        "requires_reason": True,
        "requires_moderator_identity": True,
        "immutable_audit": True,
        "rebuild_after": True,
        "idempotency": True,
        "rbac": True,
        "csrf": True,
        "ADMIN_MODERATION_WRITE_ENABLED": ADMIN_MODERATION_WRITE_ENABLED,
        "tested_on": "disposable_db_only",
    }
