"""Аудит: кто, когда, что и почему. Запись только добавляется.

Модуль сознательно беден. Аудит, в который можно записать задним числом или из
которого можно удалить, не аудит, поэтому здесь нет ни изменения, ни удаления.
"""
from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from factory.site_engine.contracts import ContractError, require_aware, utc_now


@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    actor: str
    action: str
    subject: str
    at: datetime
    reason: str = ""
    site_ids: tuple[str, ...] = ()
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    correlation_id: str | None = None

    def __post_init__(self) -> None:
        if not self.actor:
            raise ContractError("действие без автора не аудируется")
        if not self.action:
            raise ContractError("действие без имени не аудируется")
        object.__setattr__(self, "at", require_aware(self.at, "at"))

    def digest(self) -> str:
        """Отпечаток записи: подмена содержимого перестаёт быть незаметной."""
        payload = json.dumps(
            {
                "event_id": self.event_id,
                "actor": self.actor,
                "action": self.action,
                "subject": self.subject,
                "at": self.at.isoformat(),
                "before": self.before,
                "after": self.after,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


class AuditLog:
    """Журнал, в который можно только дописывать."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []
        self._lock = threading.RLock()

    def record(self, event: AuditEvent) -> AuditEvent:
        with self._lock:
            self._events.append(event)
        return event

    def __iter__(self) -> Iterator[AuditEvent]:
        with self._lock:
            return iter(list(self._events))

    def __len__(self) -> int:
        return len(self._events)

    def for_subject(self, subject: str) -> tuple[AuditEvent, ...]:
        return tuple(e for e in self if e.subject == subject)

    def for_actor(self, actor: str) -> tuple[AuditEvent, ...]:
        return tuple(e for e in self if e.actor == actor)


def event(
    *,
    actor: str,
    action: str,
    subject: str,
    reason: str = "",
    site_ids: tuple[str, ...] = (),
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    correlation_id: str | None = None,
    event_id: str | None = None,
    at: datetime | None = None,
) -> AuditEvent:
    stamp = at or utc_now()
    generated = event_id or hashlib.sha256(
        f"{actor}|{action}|{subject}|{stamp.isoformat()}".encode()
    ).hexdigest()[:16]
    return AuditEvent(
        event_id=generated,
        actor=actor,
        action=action,
        subject=subject,
        at=stamp,
        reason=reason,
        site_ids=site_ids,
        before=before,
        after=after,
        correlation_id=correlation_id,
    )
