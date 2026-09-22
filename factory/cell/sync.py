"""Доставка обновлений из центра в локальную копию сайта.

Разделение, из которого всё следует: **собирать** внешние данные центр может
один раз для всех, **обслуживать** страницы обязан сам сайт. Поэтому здесь нет
парсера — здесь приём уже собранного, и на каждом сайте он свой только в том
смысле, что курсор у каждого сайта свой.

Свойства, за которые отвечает модуль:

* **Долговечный курсор.** Позиция записывается атомарно и переживает падение.
  Прогон, убитый посреди партии, продолжается с последней применённой позиции,
  а не с начала и не с конца.
* **Повтор без дублей.** Событие, уже применённое, применяется повторно без
  последствий: идентификатор события запоминается. Повтор доставки — норма,
  а не авария.
* **Удаления доезжают.** Снятая с публикации запись исчезает и локально.
  Молчаливое «просто не прислали» удалением не считается: это разные события.
* **Атомарность партии.** Партия применяется целиком или не применяется вовсе.
  Половина применённой партии — это каталог, в котором у части записей новые
  серии, а у части старые, и различить их потом нечем.
* **Честная свежесть.** Недоступный источник не обнуляет метрику и не
  выдумывает данные: работает последний проверенный снимок, а свежесть
  помечается устаревшей с причиной.

Профиль сайта решает, что до него доезжает: весь центральный архив на витрину
не отправляется.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from factory.cell import ledger

SCHEMA_VERSION = "1.0"

UPSERT = "upsert"
DELETE = "delete"
EVENT_KINDS = (UPSERT, DELETE)

#: Свежесть, после которой снимок называется устаревшим. Не «примерно сутки»:
#: число названо, потому что предупреждение без порога никогда не срабатывает.
STALE_AFTER = timedelta(hours=6)
STUCK_AFTER = timedelta(hours=24)

#: Сколько раз повторяем неудачную доставку, прежде чем признать источник
#: недоступным. Бесконечный повтор превращает сбой источника в нагрузку на него.
MAX_ATTEMPTS = 3


class SyncError(RuntimeError):
    pass


class UpstreamUnavailable(SyncError):
    """Источник недоступен. Это не ноль записей и не пустой каталог."""


class SchemaRejected(SyncError):
    """Партия не прошла проверку схемы и не применялась."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(moment: datetime | None) -> str | None:
    return moment.isoformat() if moment else None


@dataclass(frozen=True)
class Event:
    """Одно изменение в ленте центра."""

    event_id: str
    seq: int
    kind: str
    title_uuid: str
    payload: dict[str, Any] = field(default_factory=dict)
    content_revision: int = 0
    profiles: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.kind not in EVENT_KINDS:
            raise SchemaRejected(f"неизвестный тип события: {self.kind}")
        if not self.event_id or not self.title_uuid:
            raise SchemaRejected("у события обязаны быть event_id и title_uuid")
        if self.kind == UPSERT and not self.payload:
            raise SchemaRejected(f"upsert {self.event_id} без полезной нагрузки")

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Event:
        missing = {"event_id", "seq", "kind", "title_uuid"} - set(raw)
        if missing:
            raise SchemaRejected(f"в событии нет обязательных полей: {sorted(missing)}")
        return cls(
            event_id=str(raw["event_id"]),
            seq=int(raw["seq"]),
            kind=str(raw["kind"]),
            title_uuid=str(raw["title_uuid"]),
            payload=dict(raw.get("payload") or {}),
            content_revision=int(raw.get("content_revision") or 0),
            profiles=tuple(raw.get("profiles") or ()),
        )


@dataclass
class Checkpoint:
    """Долговечная позиция доставки."""

    site_id: str
    seq: int = 0
    content_revision: int = 0
    applied_events: list[str] = field(default_factory=list)
    last_success: str | None = None
    last_attempt: str | None = None
    last_error: str | None = None
    consecutive_failures: int = 0

    #: Сколько идентификаторов событий помним для защиты от дублей. Помнить всё
    #: значит расти без границы; помнить мало — принять дубль после долгой паузы.
    memory: int = 2000

    def remember(self, event_id: str) -> None:
        self.applied_events.append(event_id)
        if len(self.applied_events) > self.memory:
            del self.applied_events[: len(self.applied_events) - self.memory]

    def seen(self, event_id: str) -> bool:
        return event_id in self.applied_events

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "site_id": self.site_id,
            "seq": self.seq,
            "content_revision": self.content_revision,
            "applied_events": list(self.applied_events),
            "last_success": self.last_success,
            "last_attempt": self.last_attempt,
            "last_error": self.last_error,
            "consecutive_failures": self.consecutive_failures,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Checkpoint:
        return cls(
            site_id=raw["site_id"],
            seq=int(raw.get("seq") or 0),
            content_revision=int(raw.get("content_revision") or 0),
            applied_events=list(raw.get("applied_events") or []),
            last_success=raw.get("last_success"),
            last_attempt=raw.get("last_attempt"),
            last_error=raw.get("last_error"),
            consecutive_failures=int(raw.get("consecutive_failures") or 0),
        )


def load_checkpoint(path: Path, site_id: str) -> Checkpoint:
    raw = ledger.read(path, default=None)
    if raw is None:
        return Checkpoint(site_id=site_id)
    if raw["site_id"] != site_id:
        raise SyncError(
            f"курсор принадлежит сайту {raw['site_id']}, а читает его {site_id}")
    return Checkpoint.from_dict(raw)


def save_checkpoint(path: Path, checkpoint: Checkpoint) -> None:
    ledger.write(path, checkpoint.to_dict())


@dataclass
class ApplyResult:
    applied: int = 0
    duplicates: int = 0
    deleted: int = 0
    skipped_profile: int = 0
    seq: int = 0
    content_revision: int = 0
    stale: bool = False
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "applied": self.applied, "duplicates": self.duplicates,
            "deleted": self.deleted, "skipped_profile": self.skipped_profile,
            "seq": self.seq, "content_revision": self.content_revision,
            "stale": self.stale, "reason": self.reason,
        }


def pull(*, site_id: str, profile: str, fetch: Callable[[int], list[dict[str, Any]]],
         checkpoint_path: Path, apply_batch: Callable[[list[Event]], None],
         now: datetime | None = None, max_attempts: int = MAX_ATTEMPTS) -> ApplyResult:
    """Забрать и применить изменения с позиции курсора.

    `apply_batch` обязана быть атомарной: модуль вызывает её один раз на партию
    и двигает курсор только после её успеха. Если она бросит исключение, курсор
    останется на месте, и партия приедет снова.
    """
    moment = now or utc_now()
    checkpoint = load_checkpoint(checkpoint_path, site_id)
    checkpoint.last_attempt = moment.isoformat()

    raw_events: list[dict[str, Any]] | None = None
    error: str | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            raw_events = fetch(checkpoint.seq)
            error = None
            break
        except Exception as exc:  # источник недоступен — это исход, а не падение
            error = f"попытка {attempt}/{max_attempts}: {exc}"

    if raw_events is None:
        checkpoint.consecutive_failures += 1
        checkpoint.last_error = error
        save_checkpoint(checkpoint_path, checkpoint)
        # Работает последний проверенный снимок. Ноль записей мы не пишем и
        # новых данных не обещаем.
        raise UpstreamUnavailable(
            f"{site_id}: источник недоступен ({error}); "
            f"витрина работает на снимке ревизии {checkpoint.content_revision}, "
            "свежесть помечена устаревшей"
        )

    events = [Event.from_dict(raw) for raw in raw_events]
    events.sort(key=lambda e: e.seq)

    result = ApplyResult(seq=checkpoint.seq, content_revision=checkpoint.content_revision)
    batch: list[Event] = []
    for event in events:
        # Позиция курсора — главный признак, а память событий — дополнительный.
        # Порядок именно такой, потому что память ограничена: событие, уже
        # применённое и вытесненное из неё, при повторной присылке было бы
        # применено снова. Для upsert это означает возврат старого значения
        # поверх нового — «синхронизация откатила правку», которую потом ищут
        # в редакторе.
        if event.seq <= checkpoint.seq:
            result.duplicates += 1
            continue
        if checkpoint.seen(event.event_id):
            result.duplicates += 1
            continue
        if event.profiles and profile not in event.profiles:
            # До витрины доезжает только её профиль: весь центральный архив на
            # каждый сайт не отправляется.
            result.skipped_profile += 1
            result.seq = max(result.seq, event.seq)
            continue
        batch.append(event)

    if batch:
        # Партия применяется целиком. Исключение отсюда оставляет курсор на
        # месте, и та же партия приедет снова — это и есть повтор без дублей.
        apply_batch(batch)
        for event in batch:
            checkpoint.remember(event.event_id)
            if event.kind == DELETE:
                result.deleted += 1
            else:
                result.applied += 1
            result.seq = max(result.seq, event.seq)
            result.content_revision = max(result.content_revision, event.content_revision)

    checkpoint.seq = max(checkpoint.seq, result.seq)
    checkpoint.content_revision = max(checkpoint.content_revision, result.content_revision)
    checkpoint.last_success = moment.isoformat()
    checkpoint.last_error = None
    checkpoint.consecutive_failures = 0
    save_checkpoint(checkpoint_path, checkpoint)
    result.seq = checkpoint.seq
    result.content_revision = checkpoint.content_revision
    return result


def freshness(checkpoint_path: Path, site_id: str, *,
              now: datetime | None = None) -> dict[str, Any]:
    """Отчёт о свежести. Недоступный источник называется недоступным."""
    moment = now or utc_now()
    checkpoint = load_checkpoint(checkpoint_path, site_id)
    last_success = (datetime.fromisoformat(checkpoint.last_success)
                    if checkpoint.last_success else None)
    age = (moment - last_success) if last_success else None
    if last_success is None:
        state, reason = "unmeasured", "доставка ни разу не завершалась успешно"
    elif age is not None and age >= STUCK_AFTER:
        state, reason = "stuck", f"последнее успешное обновление {age} назад"
    elif age is not None and age >= STALE_AFTER:
        state, reason = "stale", f"последнее успешное обновление {age} назад"
    else:
        state, reason = "fresh", None
    return {
        "site_id": site_id,
        "state": state,
        "reason": reason,
        "last_success": checkpoint.last_success,
        "last_attempt": checkpoint.last_attempt,
        "last_error": checkpoint.last_error,
        "consecutive_failures": checkpoint.consecutive_failures,
        "content_revision": checkpoint.content_revision,
        "seq": checkpoint.seq,
        "lag_seconds": int(age.total_seconds()) if age else None,
        "observed_at": _iso(moment),
    }


def validate_feed(raw_events: list[dict[str, Any]]) -> list[Event]:
    """Проверить ленту схемой до применения.

    Отдельная функция, потому что «проверим по ходу» означает, что половина
    партии уже применена, когда обнаружилась ошибка в её хвосте.
    """
    return [Event.from_dict(raw) for raw in raw_events]


def catalog_document(records: dict[str, Any]) -> str:
    return json.dumps(records, ensure_ascii=False, indent=2, sort_keys=True)
