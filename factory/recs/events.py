"""События витрины и привязка просмотра к рекомендации.

Клик сам по себе мало что говорит: посетитель мог открыть карточку и уйти через
секунду. Полка считается удачной, когда после неё начали и продолжили смотреть,
поэтому главными метриками объявлены `play_start` и `play_30s`, а не `card_click`.

Чтобы просмотр можно было отнести к конкретной выдаче, каждый показ несёт
`request_id` и версию алгоритма. Без них нельзя ответить, какая именно версия
ранжирования привела к просмотру, и любое сравнение версий превращается в спор.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

IMPRESSION = "impression"
CARD_CLICK = "card_click"
TITLE_VIEW = "title_view"
PLAY_START = "play_start"
PLAY_30S = "play_30s"
PLAY_COMPLETE = "play_complete"

EVENT_KINDS = (IMPRESSION, CARD_CLICK, TITLE_VIEW, PLAY_START, PLAY_30S, PLAY_COMPLETE)
#: События, по которым судят о качестве полки.
SUCCESS_EVENTS = (PLAY_START, PLAY_30S)

REQUIRED_IMPRESSION_FIELDS = (
    "request_id", "session_id", "domain", "shelf_id", "content_id",
    "position", "algorithm_version", "timestamp",
)


@dataclass(frozen=True)
class Impression:
    request_id: str
    session_id: str
    domain: str
    shelf_id: str
    content_id: str
    position: int
    algorithm_version: str
    timestamp: datetime

    def as_dict(self) -> dict:
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data


@dataclass(frozen=True)
class Event:
    kind: str
    request_id: str
    session_id: str
    domain: str
    content_id: str
    timestamp: datetime
    shelf_id: str | None = None
    position: int | None = None
    algorithm_version: str | None = None

    def as_dict(self) -> dict:
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data


def build_impressions(shelf_id: str, domain: str, ranked, *, request_id: str,
                      session_id: str, algorithm_version: str,
                      now: datetime | None = None) -> list[Impression]:
    """Показ каждой карточки со своей позицией.

    Позиция записывается фактическая: без неё нельзя отличить «карточку не
    заметили» от «карточка была девятой и до неё не долистали».
    """
    now = now or datetime.now(timezone.utc)
    return [
        Impression(
            request_id=request_id, session_id=session_id, domain=domain,
            shelf_id=shelf_id, content_id=scored.item.content_id,
            position=index + 1, algorithm_version=algorithm_version, timestamp=now,
        )
        for index, scored in enumerate(ranked)
    ]


class EventLog:
    """Журнал показов и действий с привязкой одного к другому."""

    def __init__(self):
        self.impressions: list[Impression] = []
        self.events: list[Event] = []

    def record_impressions(self, impressions) -> None:
        self.impressions.extend(impressions)

    def record(self, kind: str, *, request_id: str, session_id: str, domain: str,
               content_id: str, now: datetime | None = None) -> Event:
        if kind not in EVENT_KINDS:
            raise ValueError(f"неизвестное событие: {kind!r}")
        now = now or datetime.now(timezone.utc)
        source = self.attribution(request_id, content_id)
        event = Event(
            kind=kind, request_id=request_id, session_id=session_id, domain=domain,
            content_id=content_id, timestamp=now,
            shelf_id=source.shelf_id if source else None,
            position=source.position if source else None,
            algorithm_version=source.algorithm_version if source else None,
        )
        self.events.append(event)
        return event

    def attribution(self, request_id: str, content_id: str) -> Impression | None:
        """Показ, к которому относится действие.

        Сопоставление идёт по паре «выдача + запись», а не по одной записи: тот
        же тайтл мог показаться в двух полках, и приписать просмотр не той полке
        значит похвалить не ту.
        """
        for impression in self.impressions:
            if impression.request_id == request_id and impression.content_id == content_id:
                return impression
        return None

    def success_events(self, shelf_id: str | None = None) -> list[Event]:
        return [e for e in self.events
                if e.kind in SUCCESS_EVENTS and (shelf_id is None or e.shelf_id == shelf_id)]

    def as_jsonl(self) -> str:
        rows = [{"type": "impression", **i.as_dict()} for i in self.impressions]
        rows += [{"type": "event", **e.as_dict()} for e in self.events]
        return "\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
