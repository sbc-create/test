"""
Редакционный календарь: анонс -> релиз -> актуальный статус -> истечение.

Просроченный анонс на главной — это обещание, которое сайт не выполнил.
expire_stale() существует именно для того, чтобы этого не случалось молча.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, timedelta
from enum import Enum
from typing import Any

from .provenance import FactClaim, release_date_statement


class Status(str, Enum):
    DISCOVERED = "discovered"
    ANNOUNCED = "announced"          # «Скоро», дата подтверждена
    UNDATED = "undated"              # анонсировано, дата не объявлена
    RELEASED = "released"
    POSTPONED = "postponed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


TRANSITIONS: dict[Status, set[Status]] = {
    Status.DISCOVERED: {Status.ANNOUNCED, Status.UNDATED, Status.CANCELLED},
    Status.ANNOUNCED: {Status.RELEASED, Status.POSTPONED, Status.CANCELLED, Status.EXPIRED},
    Status.UNDATED: {Status.ANNOUNCED, Status.RELEASED, Status.CANCELLED},
    Status.POSTPONED: {Status.ANNOUNCED, Status.UNDATED, Status.CANCELLED},
    Status.RELEASED: set(),
    Status.CANCELLED: set(),
    Status.EXPIRED: {Status.ANNOUNCED, Status.RELEASED},
}


class InvalidTransition(Exception):
    pass


@dataclass
class CalendarEntry:
    external_id: str
    site_id: str
    title_ru: str
    title_original: str | None
    status: Status
    release_date: str | None
    release_date_confirmed: bool
    source: str
    source_confidence: str
    rights_ref: str | None
    checked_at: str
    pinned_until: str | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def date_display(self) -> str:
        return release_date_statement(FactClaim(
            field="release_date", value=self.release_date, source=self.source,
            confidence=self.source_confidence if self.release_date_confirmed else "low",
        ))

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        d["date_display"] = self.date_display
        return d


def transition(entry: CalendarEntry, new_status: Status, reason: str) -> CalendarEntry:
    if new_status not in TRANSITIONS[entry.status]:
        raise InvalidTransition(
            f"{entry.external_id}: переход {entry.status.value} -> {new_status.value} запрещён.")
    entry.status = new_status
    entry.notes.append(f"{date.today().isoformat()}: {new_status.value} — {reason}")
    if new_status in (Status.CANCELLED, Status.POSTPONED, Status.EXPIRED):
        entry.pinned_until = None      # снимаем пин немедленно
    return entry


def promote_released(entries: list[CalendarEntry], today: date | None = None) -> list[CalendarEntry]:
    """Автоматический перевод из «Скоро» в актуальный статус после выхода."""
    today = today or date.today()
    changed = []
    for e in entries:
        if e.status is not Status.ANNOUNCED or not e.release_date:
            continue
        if date.fromisoformat(e.release_date) <= today:
            changed.append(transition(e, Status.RELEASED, "дата выхода наступила"))
    return changed


def expire_stale(entries: list[CalendarEntry], today: date | None = None,
                 grace_days: int = 3) -> list[CalendarEntry]:
    """
    Анонс, чья дата прошла, но релиз не подтверждён, помечается EXPIRED и снимается с витрин.
    Молча оставлять его нельзя: главная будет обещать то, чего нет.
    """
    today = today or date.today()
    changed = []
    for e in entries:
        if e.status is not Status.ANNOUNCED or not e.release_date:
            continue
        rd = date.fromisoformat(e.release_date)
        if rd + timedelta(days=grace_days) < today:
            changed.append(transition(
                e, Status.EXPIRED,
                f"дата {rd.isoformat()} прошла более {grace_days} дн. назад без подтверждения выхода"))
    return changed


def stale_pins(entries: list[CalendarEntry], today: date | None = None) -> list[CalendarEntry]:
    today = today or date.today()
    return [e for e in entries
            if e.pinned_until and date.fromisoformat(e.pinned_until) < today]


def announceable(entry: CalendarEntry) -> tuple[bool, str]:
    """Можно ли ставить материал в блок «Скоро»."""
    if not entry.rights_ref:
        return False, "нет rights_ref"
    if entry.source_confidence not in ("high", "confirmed"):
        return False, f"source_confidence={entry.source_confidence}"
    if entry.status in (Status.CANCELLED, Status.EXPIRED):
        return False, f"статус {entry.status.value}"
    if entry.release_date and not entry.release_date_confirmed:
        return False, "дата не подтверждена — публиковать как «дата не объявлена», не как анонс с датой"
    return True, "ok"
