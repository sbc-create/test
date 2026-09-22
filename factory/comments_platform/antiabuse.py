"""Deterministic anti-abuse.

Nothing here calls an external model. That is a deliberate constraint: the
previous stage of this work parked on `BLOCKED_QWEN_RUNTIME_CONFIG`, an owner
decision about an external runtime, and a moderation pipeline that cannot run
without it is a pipeline that cannot be tested, rehearsed or shipped. Every
rule below is a pure function of the comment, the tenant policy and rows this
database already holds, so the same input always yields the same verdict and a
test can prove it.

The rules answer three different questions and must not be conflated:

* *May this be written at all?* — bans, kill switch, rate limits. Refusal.
* *Is this the same thing again?* — exact and near duplicates. Refusal.
* *Does this look risky?* — stoplist, link density, shouting. Not refusal:
  it raises a risk score, and a risky comment is *held*, not rejected, because
  a false positive that silently discards a person's writing is worse than one
  that delays it.

When the anti-spam layer itself is unavailable, `evaluate` reports degraded and
the caller fails closed — see `states.initial_state`. Failing open would make
"take the filter down" a publishing strategy.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from .errors import PolicyViolation, RateLimited
from .sanitize import count_links
from .store import ISO, CommentsStore
from .tenancy import TenantScope

RULE_VERSION = "COMMENTS_ANTIABUSE_V1"

# Risk at or above this is held for review rather than published.
RISK_HOLD_THRESHOLD = 50

# Rate-limit buckets. Each is checked independently, so evading one by rotating
# another (a fresh guest token, say) still runs into the rest.
BUCKET_SUBJECT = "subject"
BUCKET_NETWORK = "network"
BUCKET_THREAD = "thread"
BUCKET_ENDPOINT = "endpoint"


@dataclass(frozen=True, slots=True)
class RiskSignal:
    rule: str
    weight: int
    detail: str = ""


@dataclass(frozen=True)
class Verdict:
    """What anti-abuse concluded, and why.

    The signals are kept rather than collapsed into a number so that a
    moderator reviewing a held comment can see which rule fired. A score with
    no explanation is a decision nobody can appeal.
    """

    risk_score: int
    signals: tuple[RiskSignal, ...] = ()
    degraded: bool = False

    @property
    def should_hold(self) -> bool:
        return self.degraded or self.risk_score >= RISK_HOLD_THRESHOLD

    def as_dict(self) -> dict[str, Any]:
        return {
            "rule_version": RULE_VERSION,
            "risk_score": self.risk_score,
            "degraded": self.degraded,
            # Rule names and weights only. The comment text is never here: this
            # structure reaches metrics and the audit trail.
            "signals": [{"rule": s.rule, "weight": s.weight} for s in self.signals],
        }


@dataclass
class Policy:
    """Tenant-local rules. Every field has a safe default."""

    stoplist: tuple[str, ...] = ()
    max_links: int = 2
    max_length: int = 4000
    max_depth: int = 3
    rate_per_minute: int = 3
    rate_per_hour: int = 20
    duplicate_window_seconds: int = 3600
    near_duplicate_threshold: int = 3
    report_brigade_threshold: int = 5
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_row(cls, row: Mapping[str, Any] | None) -> Policy:
        if not row:
            return cls()
        return cls(
            stoplist=tuple(row.get("stoplist") or ()),
            max_links=int(row.get("max_links", 2)),
            max_length=int(row.get("max_length", 4000)),
            max_depth=int(row.get("max_depth", 3)),
            rate_per_minute=int(row.get("rate_per_minute", 3)),
            rate_per_hour=int(row.get("rate_per_hour", 20)),
            duplicate_window_seconds=int(row.get("duplicate_window_seconds", 3600)),
        )


# --- digests --------------------------------------------------------------

_NON_WORD_RE = re.compile(r"[^\w\s]", re.UNICODE)
_SPACE_RE = re.compile(r"\s+")


def exact_digest(text: str) -> str:
    """Identity of the text as written, after the normalisation sanitize did."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def near_digest(text: str) -> str:
    """Identity of the text's *shape*.

    Case, punctuation, spacing and digits are removed, and the remaining word
    stems are sorted. "Buy now!!! www.x.test" and "buy NOW www.x.test ..." land
    on one value, which is what catches a spammer varying decoration between
    otherwise identical posts. It is deliberately not a similarity metric: a
    threshold on edit distance would be tunable, arguable and slow, whereas
    this is a hash lookup with a definite answer.
    """
    folded = unicodedata.normalize("NFKD", text).casefold()
    folded = _NON_WORD_RE.sub(" ", folded)
    folded = re.sub(r"\d+", "", folded)
    words = sorted({w for w in _SPACE_RE.split(folded) if len(w) > 2})
    if not words:
        return ""
    return hashlib.sha256(" ".join(words).encode("utf-8")).hexdigest()


# --- individual rules -----------------------------------------------------

_SHOUT_RE = re.compile(r"[A-ZА-ЯЁ]{6,}")


def stoplist_signal(text: str, stoplist: Sequence[str]) -> RiskSignal | None:
    """Case-insensitive substring match over a tenant's own list.

    Tenant-local on purpose: what `lords` considers unacceptable is not what
    `animedia` considers unacceptable, and a shared list would impose one
    community's norms on three others.
    """
    if not stoplist:
        return None
    haystack = text.casefold()
    hits = [term for term in stoplist if term and term.casefold() in haystack]
    if not hits:
        return None
    # The matched term is named in the detail, which goes to the moderator's
    # screen, and is not carried into metrics — see Verdict.as_dict.
    return RiskSignal("STOPLIST", 60, detail=f"{len(hits)} term(s)")


def link_density_signal(text: str, *, max_links: int) -> RiskSignal | None:
    links = count_links(text)
    if links == 0:
        return None
    if links > max_links:
        return RiskSignal("LINK_CAP_EXCEEDED", 70, detail=f"{links} links")
    # Within the cap but link-heavy relative to the writing around it.
    words = len(_SPACE_RE.split(text.strip()))
    if words < 12 and links >= 1:
        return RiskSignal("LINK_WITHOUT_CONTENT", 45, detail=f"{links} links, {words} words")
    return None


def shouting_signal(text: str) -> RiskSignal | None:
    letters = [c for c in text if c.isalpha()]
    if len(letters) < 20:
        return None
    upper = sum(1 for c in letters if c.isupper())
    if upper / len(letters) > 0.7:
        return RiskSignal("SHOUTING", 15, detail="mostly uppercase")
    if len(_SHOUT_RE.findall(text)) >= 3:
        return RiskSignal("SHOUTING", 10, detail="repeated uppercase runs")
    return None


def repetition_signal(text: str) -> RiskSignal | None:
    """One word or character repeated to fill space."""
    if re.search(r"(.)\1{9,}", text):
        return RiskSignal("CHARACTER_FLOOD", 40, detail="repeated character run")
    words = [w for w in _SPACE_RE.split(text.casefold()) if w]
    if len(words) >= 8:
        most = max(words.count(w) for w in set(words))
        if most / len(words) > 0.5:
            return RiskSignal("WORD_FLOOD", 35, detail="one word over half the text")
    return None


def fresh_author_with_link_signal(text: str, *, author_comment_count: int) -> RiskSignal | None:
    """A first comment that exists to carry a link is the classic spam shape."""
    if author_comment_count == 0 and count_links(text) > 0:
        return RiskSignal("FIRST_POST_WITH_LINK", 35, detail="no history")
    return None


# --- the checks that refuse --------------------------------------------

class AntiAbuse:
    def __init__(self, store: CommentsStore, *, now: datetime | None = None) -> None:
        self._store = store
        self._fixed_now = now

    def _now(self) -> datetime:
        return self._fixed_now or datetime.now(timezone.utc)

    def _since(self, seconds: int) -> str:
        return (self._now() - timedelta(seconds=seconds)).strftime(ISO)

    def check_rate_limits(
        self,
        scope: TenantScope,
        *,
        subject_id: str,
        network_hmac: str,
        thread_id: str,
        endpoint: str,
        policy: Policy,
    ) -> None:
        """Four independent buckets. Passing one does not excuse another."""
        checks = [
            (BUCKET_SUBJECT, subject_id, policy.rate_per_minute, 60),
            (BUCKET_SUBJECT, subject_id, policy.rate_per_hour, 3600),
            (BUCKET_THREAD, f"{subject_id}:{thread_id}", policy.rate_per_minute * 2, 60),
            (BUCKET_ENDPOINT, f"{subject_id}:{endpoint}", policy.rate_per_minute * 3, 60),
        ]
        if network_hmac:
            # A network bucket is what makes rotating the guest token pointless.
            checks.append((BUCKET_NETWORK, network_hmac, policy.rate_per_minute * 4, 60))
            checks.append((BUCKET_NETWORK, network_hmac, policy.rate_per_hour * 4, 3600))

        for bucket, key, limit, window in checks:
            if limit <= 0:
                continue
            seen = self._store.count_rate_events(
                scope, bucket=bucket, principal_key=key, since_iso=self._since(window)
            )
            if seen >= limit:
                raise RateLimited(
                    f"{bucket} bucket exhausted: {seen} >= {limit} in {window}s",
                    retry_after_seconds=window,
                    bucket=bucket,
                )

    def record_attempt(
        self,
        scope: TenantScope,
        *,
        subject_id: str,
        network_hmac: str,
        thread_id: str,
        endpoint: str,
    ) -> None:
        self._store.record_rate_event(
            scope, bucket=BUCKET_SUBJECT, principal_key=subject_id, endpoint=endpoint
        )
        self._store.record_rate_event(
            scope, bucket=BUCKET_THREAD, principal_key=f"{subject_id}:{thread_id}",
            endpoint=endpoint,
        )
        self._store.record_rate_event(
            scope, bucket=BUCKET_ENDPOINT, principal_key=f"{subject_id}:{endpoint}",
            endpoint=endpoint,
        )
        if network_hmac:
            self._store.record_rate_event(
                scope, bucket=BUCKET_NETWORK, principal_key=network_hmac, endpoint=endpoint
            )

    def check_duplicates(
        self,
        scope: TenantScope,
        *,
        subject_id: str,
        thread_id: str,
        text: str,
        policy: Policy,
    ) -> None:
        window = self._since(policy.duplicate_window_seconds)
        if self._store.digest_seen(
            scope, subject_id=subject_id, thread_id=thread_id,
            digest=exact_digest(text), since_iso=window,
        ):
            raise PolicyViolation("this comment was already posted", rule="EXACT_DUPLICATE")

        shape = near_digest(text)
        if shape:
            seen = self._store.near_digest_count(
                scope, thread_id=thread_id, near_digest=shape, since_iso=window
            )
            if seen >= policy.near_duplicate_threshold:
                # Thread-wide, not per author: this is the coordinated case,
                # where several accounts post the same thing with different
                # punctuation.
                raise PolicyViolation(
                    f"the same text appeared {seen} times in this thread",
                    rule="NEAR_DUPLICATE_FLOOD",
                )

    def evaluate(
        self,
        scope: TenantScope,
        *,
        text: str,
        subject_id: str,
        policy: Policy,
        author_comment_count: int = 0,
        degraded: bool = False,
    ) -> Verdict:
        """Score the content. Never refuses — refusal is the caller's decision."""
        if degraded:
            # No signals: claiming a score computed while the layer was down
            # would be a fabricated measurement.
            return Verdict(risk_score=0, signals=(), degraded=True)

        signals = [
            s
            for s in (
                stoplist_signal(text, policy.stoplist),
                link_density_signal(text, max_links=policy.max_links),
                shouting_signal(text),
                repetition_signal(text),
                fresh_author_with_link_signal(text, author_comment_count=author_comment_count),
            )
            if s is not None
        ]
        score = min(100, sum(s.weight for s in signals))
        return Verdict(risk_score=score, signals=tuple(signals), degraded=False)

    def detect_report_brigade(
        self, scope: TenantScope, comment_id: str, *, policy: Policy
    ) -> bool:
        """Many reporters from few places is a brigade, not a consensus."""
        reporters = self._store.distinct_reporters(scope, comment_id)
        if reporters < policy.report_brigade_threshold:
            return False
        networks = self._store.distinct_report_networks(scope, comment_id)
        if networks == 0:
            return False
        # Five reporters behind one network identifier is one person with a
        # script; five reporters behind five is a thread that needs a moderator.
        return reporters / max(networks, 1) >= 3


def policy_document() -> dict[str, Any]:
    return {
        "schema_version": RULE_VERSION,
        "external_model_required": False,
        "hold_threshold": RISK_HOLD_THRESHOLD,
        "buckets": [BUCKET_SUBJECT, BUCKET_NETWORK, BUCKET_THREAD, BUCKET_ENDPOINT],
        "refusing_rules": ["EXACT_DUPLICATE", "NEAR_DUPLICATE_FLOOD", "rate limits", "ban"],
        "scoring_rules": [
            "STOPLIST", "LINK_CAP_EXCEEDED", "LINK_WITHOUT_CONTENT",
            "SHOUTING", "CHARACTER_FLOOD", "WORD_FLOOD", "FIRST_POST_WITH_LINK",
        ],
        "on_degraded": "fail closed — the comment is held, never published unchecked",
        "telemetry_contains_text": False,
    }
