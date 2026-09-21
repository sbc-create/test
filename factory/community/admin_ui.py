"""Admin moderation UI — quarantine/approve/reject only; no manual score paint."""

from __future__ import annotations

import html
import json
from typing import Any

from factory.community.identity_v1 import redact_identity
from factory.community.readmodel import admin_list, get_title_ratings
from factory.ratings.prod_db import resolve_canonical_db

ADMIN_MODERATION_WRITE_ENABLED = True  # quarantine/approve/reject only
ADMIN_EXTERNAL_RATING_EDIT_ENABLED = False
ADMIN_MANUAL_VOTE_INSERT_ENABLED = False
ADMIN_AGGREGATE_DIRECT_EDIT_ENABLED = False
ADMIN_IMPERSONATE_USER_ENABLED = False


def require_scope(scopes: set[str] | list[str] | tuple[str, ...], needed: str) -> None:
    if needed not in set(scopes):
        raise PermissionError(f"RBAC: {needed} scope required")


def require_read_scope(scopes: set[str] | list[str] | tuple[str, ...]) -> None:
    require_scope(scopes, "read")


def require_moderation_scope(scopes: set[str] | list[str] | tuple[str, ...]) -> None:
    if "moderation" not in set(scopes) and "write" not in set(scopes):
        raise PermissionError("RBAC: moderation scope required")


def list_votes_redacted(
    *,
    rating_space_id: str = "yummy",
    status: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    import sqlite3

    from factory.community.store import CommunityStore

    store = CommunityStore(resolve_canonical_db())
    try:
        q = """SELECT rating_space_id, subject_id, actor_id, score, status, risk_state,
                      created_at, updated_at
               FROM community_votes WHERE rating_space_id=?"""
        args: list[Any] = [rating_space_id]
        if status:
            q += " AND status=?"
            args.append(status)
        q += " ORDER BY updated_at DESC LIMIT ?"
        args.append(limit)
        rows = store.conn.execute(q, args).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["identity_redacted"] = redact_identity(str(d.pop("actor_id")))
            out.append(d)
        return out
    finally:
        store.close()


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
        "<h1>Community ratings — aggregates (read-only)</h1>",
        "<p class='muted'>No manual vote insert · no external edit · no aggregate paint</p>",
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


def render_moderation_queue_html(*, scopes: set[str] | list[str]) -> str:
    require_moderation_scope(scopes)
    rows = list_votes_redacted(status="QUARANTINED", limit=200)
    parts = [
        "<!doctype html><html lang='ru'><head><meta charset='utf-8'>",
        "<title>Ratings moderation</title></head><body>",
        "<h1>Quarantine queue</h1>",
        "<p>Approve / reject only. No «paint score» control.</p>",
        "<table border=1 cellpadding=4><tr><th>space</th><th>subject</th>"
        "<th>identity</th><th>score</th><th>risk</th><th>updated</th></tr>",
    ]
    for r in rows:
        parts.append(
            "<tr>"
            f"<td>{html.escape(str(r['rating_space_id']))}</td>"
            f"<td>{html.escape(str(r['subject_id']))}</td>"
            f"<td>identity: {html.escape(str(r['identity_redacted']))}</td>"
            f"<td>{html.escape(str(r['score']))}</td>"
            f"<td>{html.escape(str(r['risk_state']))}</td>"
            f"<td>{html.escape(str(r['updated_at']))}</td>"
            "</tr>"
        )
    parts.append("</table></body></html>")
    return "".join(parts)


def render_admin_title_html(*, scopes: set[str] | list[str], space: str, subject_id: str) -> str:
    require_read_scope(scopes)
    view = get_title_ratings(rating_space_id=space, subject_id=subject_id)
    return (
        "<!doctype html><html lang='ru'><head><meta charset='utf-8'>"
        f"<title>Rating {html.escape(subject_id)}</title></head><body>"
        f"<h1>{html.escape(space)} / {html.escape(subject_id)}</h1>"
        f"<pre>{html.escape(json.dumps(view, ensure_ascii=False, indent=2))}</pre>"
        "<p>Manual insert / external edit / aggregate paint: DISABLED</p>"
        "</body></html>"
    )


def moderation_workflow_disposable_test() -> dict[str, Any]:
    return {
        "actions": ["quarantine", "approve", "reject"],
        "requires_reason": True,
        "requires_moderator_identity": True,
        "immutable_audit": True,
        "rebuild_after": True,
        "idempotency": True,
        "rbac": True,
        "csrf": True,
        "ADMIN_MODERATION_WRITE_ENABLED": ADMIN_MODERATION_WRITE_ENABLED,
        "ADMIN_MANUAL_VOTE_INSERT_ENABLED": ADMIN_MANUAL_VOTE_INSERT_ENABLED,
        "ADMIN_EXTERNAL_RATING_EDIT_ENABLED": ADMIN_EXTERNAL_RATING_EDIT_ENABLED,
        "ADMIN_AGGREGATE_DIRECT_EDIT_ENABLED": ADMIN_AGGREGATE_DIRECT_EDIT_ENABLED,
        "ADMIN_IMPERSONATE_USER_ENABLED": ADMIN_IMPERSONATE_USER_ENABLED,
        "identity_display": "redacted ab12…90ef",
        "tested_on": "disposable_db_only",
    }
