"""Error taxonomy for the shared comments platform.

Two rules shape this module.

Existence is a secret. A moderator of `lords` asking for a `zona` comment and
a moderator of `lords` asking for a comment that was never written must get the
same answer, or the API becomes an oracle for what other sites hold. So
cross-tenant access raises :class:`NotFound`, never :class:`Forbidden`, and the
public surface never distinguishes "hidden from you" from "not there".

Errors are safe to serialise. The client gets a stable machine code, a generic
message and the request id; it never gets a database error, a stack frame, a
row count, a tenant name it did not already have, or the text of somebody
else's comment.
"""

from __future__ import annotations

from typing import Any


class CommentsError(Exception):
    """Base class. `code` is the contract; `message` is for humans."""

    code = "InternalError"
    http_status = 500
    # Message sent to the client. Deliberately coarse.
    public_message = "internal error"

    def __init__(self, detail: str = "", **context: Any) -> None:
        super().__init__(detail or self.public_message)
        # `detail` is for logs and tests. It never reaches the client.
        self.detail = detail
        self.context = context

    def to_public(self, request_id: str) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.public_message,
                "request_id": request_id,
            }
        }


class BadRequest(CommentsError):
    code = "BadRequest"
    http_status = 400
    public_message = "request is not valid"


class ValidationFailed(BadRequest):
    code = "ValidationFailed"
    public_message = "request failed validation"

    def __init__(self, detail: str = "", *, field: str = "", **context: Any) -> None:
        super().__init__(detail, field=field, **context)
        self.field = field

    def to_public(self, request_id: str) -> dict[str, Any]:
        payload = super().to_public(request_id)
        # The field name is safe: the client sent it. The value is not echoed.
        if self.field:
            payload["error"]["field"] = self.field
        return payload


class Unauthenticated(CommentsError):
    code = "Unauthenticated"
    http_status = 401
    public_message = "authentication required"


class Forbidden(CommentsError):
    """Use only when the subject's own tenant already proves the object exists.

    If denying would disclose that an object exists in *another* tenant, raise
    :class:`NotFound` instead.
    """

    code = "Forbidden"
    http_status = 403
    public_message = "not permitted"


class NotFound(CommentsError):
    code = "NotFound"
    http_status = 404
    public_message = "not found"


class CrossTenantDenied(NotFound):
    """A tenant boundary was crossed.

    It presents as 404 on the wire so that existence stays secret, but it keeps
    its own class and code so that metrics and tests can count boundary hits
    rather than guessing from the 404 stream.
    """

    code = "NotFound"
    public_message = "not found"


class Conflict(CommentsError):
    code = "Conflict"
    http_status = 409
    public_message = "conflicting state"


class IdempotencyConflict(Conflict):
    """Same idempotency key, different payload.

    A retry of the same write is not an error — it replays the first result.
    Reusing a key for a *different* body is, because one of the two writes
    would silently vanish.
    """

    code = "IdempotencyConflict"
    public_message = "idempotency key already used with a different request"


class RateLimited(CommentsError):
    code = "RateLimited"
    http_status = 429
    public_message = "too many requests"

    def __init__(self, detail: str = "", *, retry_after_seconds: int = 60, **context: Any) -> None:
        super().__init__(detail, retry_after_seconds=retry_after_seconds, **context)
        self.retry_after_seconds = retry_after_seconds

    def to_public(self, request_id: str) -> dict[str, Any]:
        payload = super().to_public(request_id)
        payload["error"]["retry_after_seconds"] = self.retry_after_seconds
        return payload


class FeatureDisabled(CommentsError):
    """A kill switch or a flag is off.

    503 rather than 403: the caller is allowed, the capability is not currently
    being served. It is also what lets the widget fail open — a page that gets
    503 from comments still renders.
    """

    code = "FeatureDisabled"
    http_status = 503
    public_message = "comments are not available"


class ModerationRequired(CommentsError):
    """The write was accepted but is not public yet.

    Not an error to the author, who must see their own pending comment; it is
    modelled as an exception only where a caller asked for a published object.
    """

    code = "ModerationRequired"
    http_status = 202
    public_message = "awaiting moderation"


class InvalidTransition(Conflict):
    code = "InvalidTransition"
    public_message = "state transition is not allowed"


class PolicyViolation(BadRequest):
    """Content was rejected by a deterministic policy (links, stoplist, length)."""

    code = "PolicyViolation"
    public_message = "content rejected by policy"

    def __init__(self, detail: str = "", *, rule: str = "", **context: Any) -> None:
        super().__init__(detail, rule=rule, **context)
        self.rule = rule

    def to_public(self, request_id: str) -> dict[str, Any]:
        payload = super().to_public(request_id)
        # The rule id is disclosed on purpose: an author who cannot learn why a
        # comment was refused simply retries the same text.
        if self.rule:
            payload["error"]["rule"] = self.rule
        return payload


# Codes the public client may ever observe. A code outside this set escaping to
# a browser is a defect, and a test asserts the set rather than trusting review.
PUBLIC_ERROR_CODES = frozenset(
    {
        "BadRequest",
        "ValidationFailed",
        "Unauthenticated",
        "Forbidden",
        "NotFound",
        "Conflict",
        "IdempotencyConflict",
        "RateLimited",
        "FeatureDisabled",
        "ModerationRequired",
        "InvalidTransition",
        "PolicyViolation",
        "InternalError",
    }
)
