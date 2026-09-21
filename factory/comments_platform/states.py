"""Comment lifecycle.

The six states are the ones the brief fixes: `pending`, `published`,
`quarantined`, `hidden`, `restored`, `removed`.

`restored` deserves a word, because it reads like a verb. It is kept as a
distinct state rather than folded back into `published` so that "this comment
is visible" and "this comment is visible again after a moderator reversed a
decision" stay tellable apart on the public surface and in metrics. Folding it
away would erase the only cheap signal that a moderation decision was wrong.

Two invariants hold across every transition:

* Nothing automated removes a body. `removed` and `hidden` are soft: the row
  and its text survive, because an automatic decision that destroys evidence
  cannot be reviewed and cannot be undone.
* Editing re-opens moderation. An edited comment re-enters the pipeline from
  the top, or "post an innocuous comment, wait for approval, rewrite it" is an
  open door.
"""

from __future__ import annotations

from typing import Any

from .errors import InvalidTransition

PENDING = "pending"
PUBLISHED = "published"
QUARANTINED = "quarantined"
HIDDEN = "hidden"
RESTORED = "restored"
REMOVED = "removed"

STATES = (PENDING, PUBLISHED, QUARANTINED, HIDDEN, RESTORED, REMOVED)

# What an anonymous reader may see. Everything else is invisible to the public
# surface — not merely styled differently, not present in embedded JSON, not
# present in hidden DOM. See ssr.py, where this same set gates rendering.
PUBLIC_VISIBLE = frozenset({PUBLISHED, RESTORED})

# What an author may additionally see about their *own* comment. An author who
# cannot see their pending comment assumes the site ate it and posts it again.
AUTHOR_VISIBLE_EXTRA = frozenset({PENDING, QUARANTINED, HIDDEN, REMOVED})
AUTHOR_VISIBLE = PUBLIC_VISIBLE | AUTHOR_VISIBLE_EXTRA

# States a moderator works through in the queue.
QUEUE_STATES = frozenset({PENDING, QUARANTINED})

# Bodies retained in the database for every state. All of them, on purpose.
RETAINS_BODY = frozenset(STATES)

# Counted in the public comment count.
COUNTED_STATES = PUBLIC_VISIBLE

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    PENDING: frozenset({PUBLISHED, QUARANTINED, HIDDEN, REMOVED}),
    PUBLISHED: frozenset({QUARANTINED, HIDDEN, REMOVED}),
    QUARANTINED: frozenset({PUBLISHED, RESTORED, HIDDEN, REMOVED}),
    HIDDEN: frozenset({RESTORED, QUARANTINED, REMOVED}),
    RESTORED: frozenset({QUARANTINED, HIDDEN, REMOVED}),
    # Terminal. A removed comment is not resurrected; if a removal was wrong,
    # the reversal is a new decision recorded against the audit trail, and the
    # operator path for it is an explicit admin restore that writes a new row.
    REMOVED: frozenset(),
}

# Transitions a machine may perform unaided. Everything else needs a human and
# a reason. Note that automation may hide but never remove.
AUTOMATIC_TRANSITIONS = frozenset(
    {
        (PENDING, PUBLISHED),
        (PENDING, QUARANTINED),
        (PENDING, HIDDEN),
        (PUBLISHED, QUARANTINED),
        (PUBLISHED, HIDDEN),
    }
)

# Manual transitions that cannot be taken without a written reason.
REASON_REQUIRED = frozenset(
    {
        (PUBLISHED, HIDDEN), (RESTORED, HIDDEN), (QUARANTINED, HIDDEN), (PENDING, HIDDEN),
        (PENDING, REMOVED), (PUBLISHED, REMOVED), (QUARANTINED, REMOVED),
        (HIDDEN, REMOVED), (RESTORED, REMOVED),
        (HIDDEN, RESTORED), (QUARANTINED, RESTORED),
    }
)

# Automatic decisions that a moderator must be able to walk back.
REVERSIBLE_AUTOMATIC = frozenset({QUARANTINED, HIDDEN})


def validate_state(state: str) -> str:
    if state not in STATES:
        raise InvalidTransition(f"unknown state: {state!r}")
    return state


def is_public_visible(state: str) -> bool:
    return validate_state(state) in PUBLIC_VISIBLE


def is_author_visible(state: str) -> bool:
    return validate_state(state) in AUTHOR_VISIBLE


def is_counted(state: str) -> bool:
    return validate_state(state) in COUNTED_STATES


def transition_allowed(src: str, dst: str) -> bool:
    validate_state(src)
    validate_state(dst)
    if src == dst:
        return True
    return dst in ALLOWED_TRANSITIONS[src]


def requires_reason(src: str, dst: str) -> bool:
    return (validate_state(src), validate_state(dst)) in REASON_REQUIRED


def is_automatic(src: str, dst: str) -> bool:
    return (validate_state(src), validate_state(dst)) in AUTOMATIC_TRANSITIONS


def validate_transition(src: str, dst: str, *, actor: str = "human", reason: str = "") -> str:
    """Return the destination state, or explain precisely why it is refused."""
    validate_state(src)
    validate_state(dst)
    if src == dst:
        return dst  # idempotent no-op: a retried moderation click is not an error
    if dst not in ALLOWED_TRANSITIONS[src]:
        raise InvalidTransition(f"transition not allowed: {src} -> {dst}")
    if actor == "automation":
        if (src, dst) not in AUTOMATIC_TRANSITIONS:
            raise InvalidTransition(f"automation may not perform {src} -> {dst}")
        if dst == REMOVED:
            raise InvalidTransition("automation may never remove a comment")
    elif requires_reason(src, dst) and not (reason or "").strip():
        raise InvalidTransition(f"{src} -> {dst} requires a reason")
    return dst


def state_after_edit(current: str, *, moderation_mode: str) -> str:
    """An edit re-enters moderation.

    A removed comment cannot be edited at all — the caller checks that before
    reaching here, and this guard is the second line.
    """
    validate_state(current)
    if current == REMOVED:
        raise InvalidTransition("a removed comment cannot be edited")
    return PENDING if moderation_mode == "pre" else PUBLISHED


def initial_state(*, moderation_mode: str, risk_flagged: bool, antispam_degraded: bool) -> str:
    """Where a brand-new comment lands.

    `antispam_degraded` is the fail-closed path: when the anti-spam layer is
    unavailable we hold the comment rather than publish it unchecked. Failing
    open here would make "take the spam filter down" a publishing strategy.
    """
    if antispam_degraded or risk_flagged:
        return PENDING
    return PENDING if moderation_mode == "pre" else PUBLISHED


def state_machine_document() -> dict[str, Any]:
    return {
        "schema_version": "COMMENTS_STATE_MACHINE_V1",
        "states": list(STATES),
        "public_visible": sorted(PUBLIC_VISIBLE),
        "author_visible_extra": sorted(AUTHOR_VISIBLE_EXTRA),
        "queue_states": sorted(QUEUE_STATES),
        "counted_states": sorted(COUNTED_STATES),
        "retains_body": sorted(RETAINS_BODY),
        "allowed_transitions": {k: sorted(v) for k, v in sorted(ALLOWED_TRANSITIONS.items())},
        "automatic_transitions": sorted(f"{a}->{b}" for a, b in AUTOMATIC_TRANSITIONS),
        "reason_required": sorted(f"{a}->{b}" for a, b in REASON_REQUIRED),
        "reversible_automatic": sorted(REVERSIBLE_AUTOMATIC),
        "invariants": [
            "no state deletes the body; removal and hiding are soft",
            "automation may hide but may never remove",
            "an edit re-enters moderation",
            "removed is terminal",
        ],
    }
