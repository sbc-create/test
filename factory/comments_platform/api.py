"""Versioned HTTP contract.

Framework-free on purpose. The handlers take a plain :class:`Request` and
return a plain :class:`Response`, so the same contract can sit behind whatever
each site already runs without dragging a web framework into the shared module
— and so the whole surface is testable without a server.

The version is in the path (`/api/comments/v1/...`). A site pins a module
version and a checksum; the API version is the second half of that promise,
because a compatible-looking change to a response shape breaks four sites at
once when there is only one deployment of this code.

Three request-level defences live here rather than in the service:

* **Scope comes from the Host header**, resolved against the registry. A body
  field naming a tenant is refused outright by `reject_client_supplied_scope`.
* **CORS is an exact allowlist** and is applied to the *response*, so a
  disallowed origin gets no `Access-Control-Allow-Origin` at all rather than a
  permissive echo.
* **CSRF is checked on every cookie-authenticated write.** Token auth does not
  need it — a cross-site form post cannot add an Authorization header — and
  requiring it there would only tempt somebody to disable the check.
"""

from __future__ import annotations

import hmac
import json
import sys
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from . import MODULE_VERSION
from .errors import (
    BadRequest,
    CommentsError,
    Forbidden,
    NotFound,
    ValidationFailed,
)
from .identity import Identity, IdentityResolver
from .rbac import USER, Principal
from .service import CommentsService
from .tenancy import (
    ResourceRef,
    SiteRegistry,
    TenantScope,
    reject_client_supplied_scope,
)

API_VERSION = "v1"
API_PREFIX = f"/api/comments/{API_VERSION}"

# Methods that change something and therefore need CSRF protection under cookie
# authentication.
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

SECURITY_HEADERS = {
    # The API returns JSON only; these stop a browser from ever treating a
    # response as a document.
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


@dataclass
class Request:
    method: str
    path: str
    host: str
    headers: Mapping[str, str] = field(default_factory=dict)
    query: Mapping[str, str] = field(default_factory=dict)
    body: Mapping[str, Any] | None = None
    cookies: Mapping[str, str] = field(default_factory=dict)
    remote_addr: str = ""

    def header(self, name: str) -> str:
        lowered = name.lower()
        for key, value in self.headers.items():
            if key.lower() == lowered:
                return value
        return ""

    @property
    def origin(self) -> str:
        return self.header("origin")

    @property
    def request_id(self) -> str:
        return self.header("x-request-id") or f"req_{uuid.uuid4().hex[:16]}"

    @property
    def uses_cookie_auth(self) -> bool:
        return bool(self.cookies) and not self.header("authorization")


@dataclass
class Response:
    status: int
    body: dict[str, Any]
    headers: dict[str, str] = field(default_factory=dict)

    def json(self) -> str:
        return json.dumps(self.body, ensure_ascii=False)


class CommentsApi:
    def __init__(
        self,
        service: CommentsService,
        registry: SiteRegistry,
        identity_resolver: IdentityResolver,
        *,
        csrf_cookie: str = "cp_csrf",
        csrf_header: str = "X-CP-CSRF",
    ) -> None:
        self._service = service
        self._registry = registry
        self._identities = identity_resolver
        self._csrf_cookie = csrf_cookie
        self._csrf_header = csrf_header

    # --- request plumbing -------------------------------------------------

    def _resolve_scope(self, request: Request) -> tuple[TenantScope, Any]:
        """Host header in, scope out. The only path by which scope is set."""
        binding = self._registry.resolve_host(request.host)
        return binding.scope, binding

    def _check_csrf(self, request: Request) -> None:
        if request.method not in UNSAFE_METHODS or not request.uses_cookie_auth:
            return
        sent = request.header(self._csrf_header)
        expected = request.cookies.get(self._csrf_cookie, "")
        if not sent or not expected or not hmac.compare_digest(sent, expected):
            raise Forbidden("CSRF token missing or mismatched")

    def _cors_headers(self, request: Request, binding: Any) -> dict[str, str]:
        origin = request.origin
        if not self._registry.origin_allowed(binding, origin):
            # No header at all. Echoing a disallowed origin, or falling back to
            # `*`, is how an allowlist becomes decoration.
            return {}
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Headers": f"Content-Type, {self._csrf_header}, X-Request-Id",
            "Access-Control-Allow-Methods": "GET, POST, PATCH, DELETE, OPTIONS",
            "Vary": "Origin",
        }

    def _identity(self, scope: TenantScope, request: Request) -> Identity:
        return self._identities.resolve(
            scope,
            {
                "guest_token": request.cookies.get("cp_guest", ""),
                "remote_addr": request.remote_addr,
                "display_name": (request.body or {}).get("display_name", ""),
                "authorization": request.header("authorization"),
            },
        )

    @staticmethod
    def _principal(scope: TenantScope, identity: Identity) -> Principal:
        """A browser caller is always a `user`.

        Elevated roles arrive through a separate, authenticated admin surface;
        no header on a public request can produce one.
        """
        return Principal(subject_id=identity.subject_id, role=USER, scope=scope)

    def handle(self, request: Request, *, cohort: str = "public") -> Response:
        """Single entry point. Every error leaves through one place.

        The cohort arrives from the caller (the gateway resolves it from a
        signed cookie) rather than being read here, so this module keeps no
        opinion about audiences and a deployment that forgets to resolve one
        gets `public` — the answer that serves nothing.
        """
        request_id = request.request_id
        binding = None
        try:
            reject_client_supplied_scope(request.body)
            reject_client_supplied_scope(request.query)
            scope, binding = self._resolve_scope(request)

            if request.method == "OPTIONS":
                return self._finish(
                    Response(204, {}), request, binding, request_id
                )

            self._check_csrf(request)
            handler, params = self._route(request)
            if handler is None:
                raise NotFound("no such endpoint")
            response = handler(request, scope, binding, params, request_id, cohort)
            return self._finish(response, request, binding, request_id)

        except CommentsError as exc:
            return self._finish(
                Response(exc.http_status, exc.to_public(request_id)),
                request,
                binding,
                request_id,
            )
        except Exception:  # noqa: BLE001 — the boundary must not leak internals
            # No message, no type, no traceback *to the client*. The request id
            # is the handle an operator uses to find the real error, so the
            # real error has to reach the log — silently swallowing it here is
            # what makes a 500 undiagnosable.
            import traceback as _traceback

            sys.stderr.write(
                f"[comments] request_id={request_id} unhandled:\n{_traceback.format_exc()}"
            )
            return self._finish(
                Response(
                    500,
                    {"error": {"code": "InternalError", "message": "internal error",
                               "request_id": request_id}},
                ),
                request,
                binding,
                request_id,
            )

    def _finish(
        self, response: Response, request: Request, binding: Any, request_id: str
    ) -> Response:
        response.headers.update(SECURITY_HEADERS)
        response.headers["X-Request-Id"] = request_id
        response.headers["X-Comments-Module-Version"] = MODULE_VERSION
        if binding is not None:
            response.headers.update(self._cors_headers(request, binding))
        return response

    # --- routing ----------------------------------------------------------

    def _route(self, request: Request) -> tuple[Callable | None, dict[str, str]]:
        path = request.path
        if not path.startswith(API_PREFIX):
            return None, {}
        tail = path[len(API_PREFIX):].strip("/")
        parts = tail.split("/") if tail else []
        method = request.method.upper()

        # /threads
        if parts == ["threads"] and method == "GET":
            return self._get_thread, {}
        if parts == ["threads", "count"] and method == "GET":
            return self._get_count, {}
        # /comments
        if parts == ["comments"] and method == "POST":
            return self._post_comment, {}
        if len(parts) == 2 and parts[0] == "comments" and method == "PATCH":
            return self._patch_comment, {"comment_id": parts[1]}
        if len(parts) == 2 and parts[0] == "comments" and method == "DELETE":
            return self._delete_comment, {"comment_id": parts[1]}
        if len(parts) == 3 and parts[0] == "comments" and parts[2] == "reactions":
            if method == "POST":
                return self._post_reaction, {"comment_id": parts[1]}
            if method == "DELETE":
                return self._delete_reaction, {"comment_id": parts[1]}
        if len(parts) == 3 and parts[0] == "comments" and parts[2] == "reports" \
                and method == "POST":
            return self._post_report, {"comment_id": parts[1]}
        return None, {}

    # --- handlers ---------------------------------------------------------

    def _ref_from_query(self, request: Request) -> ResourceRef:
        resource_type = request.query.get("resource_type", "")
        content_id = request.query.get("canonical_content_id", "")
        if not resource_type or not content_id:
            raise ValidationFailed(
                "resource_type and canonical_content_id are required",
                field="canonical_content_id",
            )
        return ResourceRef(resource_type, content_id)

    def _get_thread(self, request, scope, binding, params, request_id, cohort) -> Response:
        identity = self._identity(scope, request)
        principal = self._principal(scope, identity)
        view = self._service.thread_view(
            scope,
            principal,
            self._ref_from_query(request),
            sort=request.query.get("sort", "new"),
            limit=int(request.query.get("limit", "20") or 20),
            cursor=request.query.get("cursor", ""),
            viewer_subject_id=identity.subject_id,
            cohort=cohort,
        )
        return Response(200, view.as_dict())

    def _get_count(self, request, scope, binding, params, request_id, cohort) -> Response:
        identity = self._identity(scope, request)
        principal = self._principal(scope, identity)
        count = self._service.comment_count(
            scope, principal, self._ref_from_query(request), cohort=cohort
        )
        return Response(200, {"count": count})

    def _body(self, request: Request) -> Mapping[str, Any]:
        if not isinstance(request.body, Mapping):
            raise BadRequest("a JSON object body is required")
        return request.body

    def _post_comment(self, request, scope, binding, params, request_id, cohort) -> Response:
        body = self._body(request)
        identity = self._identity(scope, request)
        principal = self._principal(scope, identity)
        result = self._service.create_comment(
            scope,
            principal,
            identity,
            ResourceRef(
                str(body.get("resource_type", "")), str(body.get("canonical_content_id", ""))
            ),
            body=str(body.get("body", "")),
            parent_id=str(body.get("parent_id", "") or ""),
            idempotency_key=request.header("idempotency-key"),
            request_id=request_id,
            cohort=cohort,
        )
        # 202 when held: the write succeeded, the comment is not public yet,
        # and the widget needs to tell the author that rather than pretend.
        status = 201 if not result["moderation"]["held"] else 202
        return Response(status, result)

    def _patch_comment(self, request, scope, binding, params, request_id, cohort) -> Response:
        body = self._body(request)
        identity = self._identity(scope, request)
        principal = self._principal(scope, identity)
        result = self._service.edit_own_comment(
            scope, principal, identity, params["comment_id"],
            body=str(body.get("body", "")), request_id=request_id, cohort=cohort,
        )
        return Response(200, result)

    def _delete_comment(self, request, scope, binding, params, request_id, cohort) -> Response:
        identity = self._identity(scope, request)
        principal = self._principal(scope, identity)
        result = self._service.delete_own_comment(
            scope, principal, params["comment_id"], request_id=request_id, cohort=cohort
        )
        return Response(200, result)

    def _post_reaction(self, request, scope, binding, params, request_id, cohort) -> Response:
        body = self._body(request)
        identity = self._identity(scope, request)
        principal = self._principal(scope, identity)
        result = self._service.set_reaction(
            scope, principal, identity, params["comment_id"],
            str(body.get("reaction", "")), request_id=request_id, cohort=cohort,
        )
        return Response(200, result)

    def _delete_reaction(self, request, scope, binding, params, request_id, cohort) -> Response:
        identity = self._identity(scope, request)
        principal = self._principal(scope, identity)
        result = self._service.clear_reaction(
            scope, principal, identity, params["comment_id"], cohort=cohort
        )
        return Response(200, result)

    def _post_report(self, request, scope, binding, params, request_id, cohort) -> Response:
        body = self._body(request)
        identity = self._identity(scope, request)
        principal = self._principal(scope, identity)
        result = self._service.report_comment(
            scope, principal, identity, params["comment_id"],
            reason=str(body.get("reason", "")),
            note=str(body.get("note", "")),
            request_id=request_id,
            cohort=cohort,
        )
        return Response(202, result)


def openapi_document() -> dict[str, Any]:
    """The published contract.

    Written by hand rather than generated from the handlers, because a spec
    derived from the implementation agrees with the implementation by
    construction and therefore proves nothing. A test compares the two.
    """
    error_schema = {
        "type": "object",
        "properties": {
            "error": {
                "type": "object",
                "required": ["code", "message", "request_id"],
                "properties": {
                    "code": {"type": "string"},
                    "message": {"type": "string"},
                    "request_id": {"type": "string"},
                },
            }
        },
    }
    comment_schema = {
        "type": "object",
        "required": ["comment_id", "state", "created_at", "anchor"],
        "properties": {
            "comment_id": {"type": "string"},
            "parent_id": {"type": ["string", "null"]},
            "depth": {"type": "integer"},
            "author": {
                "type": "object",
                "properties": {"subject_id": {"type": "string"}},
            },
            "state": {"type": "string"},
            "is_own": {"type": "boolean"},
            "body_html": {"type": "string"},
            "created_at": {"type": "string"},
            "edited_at": {"type": ["string", "null"]},
            "revision": {"type": "integer"},
            "reaction_count": {"type": "integer"},
            "reply_count": {"type": "integer"},
            "anchor": {"type": "string"},
        },
    }
    responses = {
        "400": {"description": "malformed request", "schema": error_schema},
        "401": {"description": "authentication required", "schema": error_schema},
        "403": {"description": "not permitted or CSRF failed", "schema": error_schema},
        "404": {
            "description": "not found — also returned for another tenant's object",
            "schema": error_schema,
        },
        "409": {"description": "conflict, including idempotency key reuse", "schema": error_schema},
        "429": {"description": "rate limited", "schema": error_schema},
        "503": {"description": "comments disabled or stopped", "schema": error_schema},
    }
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Site Factory shared comments",
            "version": API_VERSION,
            "x-module-version": MODULE_VERSION,
            "description": (
                "One shared comments module for every site. Tenant and site are "
                "derived server-side from the request host and are never accepted "
                "from a client."
            ),
        },
        "x-tenancy": {
            "resolved_from": ["Host header", "scoped service credential"],
            "never_accepted_from": ["query", "body", "cookie", "frontend config"],
            "cross_tenant_response": "404",
        },
        "paths": {
            f"{API_PREFIX}/threads": {
                "get": {
                    "summary": "A page of published comments for one piece of content",
                    "parameters": [
                        {"name": "resource_type", "in": "query", "required": True},
                        {"name": "canonical_content_id", "in": "query", "required": True},
                        {"name": "sort", "in": "query", "schema": {
                            "enum": ["new", "old", "popular"]}},
                        {"name": "limit", "in": "query"},
                        {"name": "cursor", "in": "query"},
                    ],
                    "responses": {"200": {"description": "thread page"}, **responses},
                }
            },
            f"{API_PREFIX}/threads/count": {
                "get": {
                    "summary": "Published comment count",
                    "responses": {"200": {"description": "count"}, **responses},
                }
            },
            f"{API_PREFIX}/comments": {
                "post": {
                    "summary": "Create a comment or a reply",
                    "parameters": [
                        {"name": "Idempotency-Key", "in": "header", "required": False},
                    ],
                    "responses": {
                        "201": {"description": "published", "schema": comment_schema},
                        "202": {"description": "accepted, awaiting moderation"},
                        **responses,
                    },
                }
            },
            f"{API_PREFIX}/comments/{{comment_id}}": {
                "patch": {
                    "summary": "Edit your own comment; re-enters moderation",
                    "responses": {"200": {"description": "updated"}, **responses},
                },
                "delete": {
                    "summary": "Delete your own comment (soft)",
                    "responses": {"200": {"description": "removed"}, **responses},
                },
            },
            f"{API_PREFIX}/comments/{{comment_id}}/reactions": {
                "post": {
                    "summary": "Set or change your reaction",
                    "responses": {"200": {"description": "counted"}, **responses},
                },
                "delete": {
                    "summary": "Remove your reaction",
                    "responses": {"200": {"description": "counted"}, **responses},
                },
            },
            f"{API_PREFIX}/comments/{{comment_id}}/reports": {
                "post": {
                    "summary": "Report a comment",
                    "responses": {
                        "202": {
                            "description":
                                "accepted — identical whether or not the report was new",
                        },
                        **responses,
                    },
                }
            },
        },
        "x-security": {
            "cors": "exact origin allowlist per site; no wildcard, no echo",
            "csrf": "required on unsafe methods under cookie authentication",
            "headers": sorted(SECURITY_HEADERS),
            "never_returned_to_public_clients": [
                "pending, quarantined, hidden or removed comments",
                "tenant_id or site_id",
                "risk scores and report counts",
                "raw comment bodies (only rendered, sanitised HTML)",
            ],
        },
    }
