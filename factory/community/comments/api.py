"""HTTP-facing community comments API (dark mode).

Reuses SIGNED_PSEUDONYMOUS_DEVICE_V1 identity cookie (yummy_cr_vid).
Does not mint a second cookie. Writes gated by COMMENTS_API_WRITE_ENABLED.
"""

from __future__ import annotations

import secrets
from typing import Any

from factory.community.antifraud import AntifraudGuard, OriginRejected, RateLimited
from factory.community.comments import flags as comment_flags
from factory.community.comments.admin import CommentsAdmin
from factory.community.comments.service import (
    CommentsError,
    CommentsService,
)
from factory.community.identity_v1 import (
    COOKIE_NAME as IDENTITY_COOKIE,
    IdentityError,
    reject_client_supplied_user_id,
    resolve_or_mint,
)

# Same CSRF cookie family as ratings — no parallel session cookie.
CSRF_COOKIE = "yummy_cr_csrf"
MAX_BODY_BYTES = 8192


class CommunityCommentsAPI:
    def __init__(
        self,
        service: CommentsService,
        guard: AntifraudGuard | None = None,
    ) -> None:
        self.service = service
        self.guard = guard or AntifraudGuard()
        self.admin = CommentsAdmin(service)

    def flags(self) -> dict[str, Any]:
        return {
            "status": 200,
            "flags": comment_flags.comments_dark_flags(),
            "identity_cookie": IDENTITY_COOKIE,
            "isolation": comment_flags.isolation_invariants(),
        }

    def _resolve_identity(
        self,
        *,
        cookie_header: str = "",
        client_body: dict[str, Any] | None = None,
    ) -> tuple[str, str | None]:
        reject_client_supplied_user_id(client_body)
        resolved, set_cookie = resolve_or_mint(cookie_header or None)
        return resolved.identity_id, set_cookie

    def _check_csrf(
        self,
        *,
        origin: str | None,
        csrf_token: str | None,
        session_csrf: str | None,
    ) -> None:
        self.guard.check_origin(origin, csrf_token=csrf_token, session_csrf=session_csrf)

    def _err(self, exc: Exception) -> dict[str, Any]:
        if isinstance(exc, CommentsError):
            return {"status": exc.status, "code": exc.code, "error": str(exc)}
        if isinstance(exc, OriginRejected):
            return {"status": 403, "code": "OriginRejected", "error": str(exc)}
        if isinstance(exc, RateLimited):
            return {"status": 429, "code": "RateLimited", "error": str(exc)}
        if isinstance(exc, IdentityError):
            return {"status": getattr(exc, "status", 401), "code": "IdentityError", "error": str(exc)}
        if isinstance(exc, PermissionError):
            return {"status": 403, "code": "Forbidden", "error": str(exc)}
        return {"status": 500, "code": "InternalError", "error": "internal error"}

    def list_comments(
        self,
        *,
        site_space: str,
        title_id: str,
        cookie_header: str = "",
        admin_preview: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        try:
            comment_flags.assert_comments_dark()
            identity_id, _ = self._resolve_identity(cookie_header=cookie_header)
            result = self.service.list_for_title(
                site_space=site_space,
                title_id=title_id,
                viewer_identity_id=identity_id,
                admin_preview=admin_preview,
                limit=limit,
                offset=offset,
            )
            return result
        except Exception as exc:  # noqa: BLE001 — API boundary
            return self._err(exc)

    def create_comment(
        self,
        *,
        site_space: str,
        title_id: str,
        body: str,
        parent_comment_id: str = "",
        spoiler: bool = False,
        origin: str | None = None,
        csrf_token: str | None = None,
        session_csrf: str | None = None,
        cookie_header: str = "",
        client_body: dict[str, Any] | None = None,
        bypass_write_flag_for_tests: bool = False,
    ) -> dict[str, Any]:
        try:
            self._check_csrf(origin=origin, csrf_token=csrf_token, session_csrf=session_csrf)
            identity_id, set_cookie = self._resolve_identity(
                cookie_header=cookie_header, client_body=client_body
            )
            result = self.service.create(
                site_space=site_space,
                title_id=title_id,
                identity_id=identity_id,
                body=body,
                parent_comment_id=parent_comment_id,
                spoiler=spoiler,
                bypass_write_flag_for_tests=bypass_write_flag_for_tests,
            )
            if set_cookie:
                result["set_cookie"] = set_cookie
            return result
        except Exception as exc:  # noqa: BLE001
            return self._err(exc)

    def edit_comment(
        self,
        *,
        comment_id: str,
        body: str,
        origin: str | None = None,
        csrf_token: str | None = None,
        session_csrf: str | None = None,
        cookie_header: str = "",
        bypass_write_flag_for_tests: bool = False,
    ) -> dict[str, Any]:
        try:
            self._check_csrf(origin=origin, csrf_token=csrf_token, session_csrf=session_csrf)
            identity_id, _ = self._resolve_identity(cookie_header=cookie_header)
            return self.service.edit(
                comment_id=comment_id,
                identity_id=identity_id,
                body=body,
                bypass_write_flag_for_tests=bypass_write_flag_for_tests,
            )
        except Exception as exc:  # noqa: BLE001
            return self._err(exc)

    def delete_comment(
        self,
        *,
        comment_id: str,
        origin: str | None = None,
        csrf_token: str | None = None,
        session_csrf: str | None = None,
        cookie_header: str = "",
        bypass_write_flag_for_tests: bool = False,
    ) -> dict[str, Any]:
        try:
            self._check_csrf(origin=origin, csrf_token=csrf_token, session_csrf=session_csrf)
            identity_id, _ = self._resolve_identity(cookie_header=cookie_header)
            return self.service.delete_by_user(
                comment_id=comment_id,
                identity_id=identity_id,
                bypass_write_flag_for_tests=bypass_write_flag_for_tests,
            )
        except Exception as exc:  # noqa: BLE001
            return self._err(exc)

    def report_comment(
        self,
        *,
        comment_id: str,
        reason_code: str,
        detail: str = "",
        origin: str | None = None,
        csrf_token: str | None = None,
        session_csrf: str | None = None,
        cookie_header: str = "",
        bypass_write_flag_for_tests: bool = False,
    ) -> dict[str, Any]:
        try:
            self._check_csrf(origin=origin, csrf_token=csrf_token, session_csrf=session_csrf)
            identity_id, _ = self._resolve_identity(cookie_header=cookie_header)
            return self.service.report(
                comment_id=comment_id,
                identity_id=identity_id,
                reason_code=reason_code,
                detail=detail,
                bypass_write_flag_for_tests=bypass_write_flag_for_tests,
            )
        except Exception as exc:  # noqa: BLE001
            return self._err(exc)

    def admin_action(
        self,
        *,
        scopes: set[str] | list[str] | tuple[str, ...],
        comment_id: str,
        action: str,
        moderator_cookie_header: str = "",
        reason_code: str = "",
        report_id: str = "",
    ) -> dict[str, Any]:
        try:
            identity_id, _ = self._resolve_identity(cookie_header=moderator_cookie_header)
            return self.admin.apply(
                scopes=scopes,
                comment_id=comment_id,
                action=action,
                moderator_identity_id=identity_id,
                reason_code=reason_code,
                report_id=report_id,
            )
        except Exception as exc:  # noqa: BLE001
            return self._err(exc)

    def mint_csrf(self) -> dict[str, str]:
        token = secrets.token_urlsafe(24)
        return {"csrf_token": token, "cookie_name": CSRF_COOKIE}
