"""Editorial calendar, content backlog and the announcement lifecycle.

The central rule: a factual claim about a release may only exist if it carries a
confirmed source from the site's approved source registry. There is no code path
that produces a date, a cast, a rating or an availability statement without one,
because the constructor refuses to build the object.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum

from seo_operator.audit import new_id, utcnow


class SourceTrust(str, Enum):
    OFFICIAL = "official"  # правообладатель, официальный канал студии
    LICENSED_FEED = "licensed_feed"  # лицензированный каталог/фид
    PRESS_CONFIRMED = "press_confirmed"  # подтверждено профильным изданием
    UNCONFIRMED = "unconfirmed"  # слух, утечка, форум — публикации не подлежит


PUBLISHABLE_TRUST = frozenset(
    {SourceTrust.OFFICIAL, SourceTrust.LICENSED_FEED, SourceTrust.PRESS_CONFIRMED}
)


class AnnouncementState(str, Enum):
    ANNOUNCED = "announced"
    RELEASED = "released"
    DELAYED = "delayed"
    CANCELLED = "cancelled"
    RETIRED = "retired"  # снят с витрины, промо-блоки очищены


class UnsourcedClaimError(ValueError):
    """Raised when a factual claim is created without a publishable source."""


@dataclass(frozen=True)
class EditorialSource:
    """One entry in a site's approved source registry."""

    source_id: str
    name: str
    url: str
    trust: SourceTrust
    rights_confirmed: bool = False

    @property
    def publishable(self) -> bool:
        return self.trust in PUBLISHABLE_TRUST and self.rights_confirmed


@dataclass
class Claim:
    """A factual statement with its provenance."""

    field_name: str
    value: str
    source: EditorialSource
    observed_at: str = field(default_factory=utcnow)

    def __post_init__(self) -> None:
        if not self.source.publishable:
            raise UnsourcedClaimError(
                f"утверждение {self.field_name!r} опирается на источник "
                f"{self.source.source_id!r} с уровнем доверия "
                f"{self.source.trust.value!r} / rights_confirmed="
                f"{self.source.rights_confirmed} — публикация запрещена"
            )


@dataclass
class Announcement:
    """A future or just-released item tracked on a site."""

    site_id: str
    entity_id: str
    title_claim: Claim
    state: AnnouncementState = AnnouncementState.ANNOUNCED
    release_date_claim: Claim | None = None
    announcement_id: str = field(default_factory=lambda: new_id("ann"))
    pinned_until: str | None = None
    history: list[dict] = field(default_factory=list)

    @property
    def release_date(self) -> date | None:
        if not self.release_date_claim:
            return None
        return datetime.strptime(self.release_date_claim.value, "%Y-%m-%d").date()

    def transition(
        self, new_state: AnnouncementState, *, source: EditorialSource, note: str = ""
    ) -> None:
        """Change state. A transition is itself a claim and needs a source."""
        if not source.publishable:
            raise UnsourcedClaimError(
                f"переход в состояние {new_state.value!r} требует подтверждённого источника"
            )
        self.history.append(
            {
                "at": utcnow(),
                "from": self.state.value,
                "to": new_state.value,
                "source": source.source_id,
                "note": note,
            }
        )
        self.state = new_state

    def is_stale_promise(self, today: date) -> bool:
        """True when the site still promises something the date has passed for."""
        if self.state is not AnnouncementState.ANNOUNCED:
            return False
        rd = self.release_date
        return rd is not None and rd < today

    def pin_expired(self, today: date) -> bool:
        if not self.pinned_until:
            return False
        return datetime.strptime(self.pinned_until, "%Y-%m-%d").date() < today

    def to_dict(self) -> dict:
        data = asdict(self)
        data["state"] = self.state.value
        return data


def find_stale_promises(announcements, today: date) -> list[Announcement]:
    """Announcements whose date has passed but which were never updated."""
    return [a for a in announcements if a.is_stale_promise(today)]


def find_expired_pins(announcements, today: date) -> list[Announcement]:
    return [a for a in announcements if a.pin_expired(today)]


# --------------------------------------------------------------------------
# Editorial calendar and backlog
# --------------------------------------------------------------------------


class BacklogState(str, Enum):
    IDEA = "idea"
    READY = "ready"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    DROPPED = "dropped"


@dataclass
class BacklogItem:
    site_id: str
    title: str
    rubric: str
    intent: str
    state: BacklogState = BacklogState.IDEA
    priority: float = 0.0
    item_id: str = field(default_factory=lambda: new_id("bkl"))
    scheduled_for: str | None = None
    rationale: str = ""

    def to_dict(self) -> dict:
        data = asdict(self)
        data["state"] = self.state.value
        return data


@dataclass
class EditorialCalendar:
    """Per-site calendar. Deliberately per-site: a shared calendar is how
    identical content ends up on every domain."""

    site_id: str
    items: list[BacklogItem] = field(default_factory=list)

    def schedule(self, item: BacklogItem, when: date) -> None:
        if item.site_id != self.site_id:
            raise ValueError(
                f"материал сайта {item.site_id!r} нельзя ставить в календарь {self.site_id!r}"
            )
        item.scheduled_for = when.isoformat()
        item.state = BacklogState.SCHEDULED
        self.items.append(item)

    def due(self, today: date, horizon_days: int = 7) -> list[BacklogItem]:
        limit = today + timedelta(days=horizon_days)
        return [
            i
            for i in self.items
            if i.scheduled_for
            and today <= date.fromisoformat(i.scheduled_for) <= limit
            and i.state is BacklogState.SCHEDULED
        ]


def detect_cross_site_duplication(items) -> list[tuple[str, list[str]]]:
    """Find identical planned titles across different sites.

    Publishing the same text on every site is explicitly out of bounds, so the
    planner checks for it before anything reaches a calendar.
    """
    seen: dict[str, list[str]] = {}
    for item in items:
        key = item.title.strip().lower()
        seen.setdefault(key, []).append(item.site_id)
    return [(title, sites) for title, sites in seen.items() if len(set(sites)) > 1]
