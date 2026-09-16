"""Быстрый путь свежести: изменение доезжает до витрины за минуты, а не за часы.

Разделение, ради которого написан модуль:

* **быстрый путь** идёт каждые пять минут и обрабатывает только изменения;
* **полная сверка** идёт раз в сутки, проверяет полноту и чинит расхождения;
* **полная пересборка** — только при смене шаблона, схемы или по команде.

Быстрый путь не ждёт окончания сверки. Пока они делят одну очередь и один
замок, «раз в сутки» превращается в «сутки задержки», и семичасовой цикл
возвращается через чёрный ход.

Времена. SLA считается от `detected_at` — первого наблюдения изменения нашим
опросом — до `live_verified_at`, подтверждения на публичном адресе. Время
поставщика хранится отдельно и никогда не подменяет наблюдение: у большинства
записей его нет, а у остальных оно не двигается при выходе серии.
"""
from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA_VERSION = "1.0"

#: Пороги SLA. Пятнадцать минут — обещание владельцу; десять — рубеж, на котором
#: ещё есть время вмешаться.
WARNING_AGE = timedelta(minutes=10)
CRITICAL_AGE = timedelta(minutes=15)

#: Замок считается брошенным, если его держат дольше трёх циклов. Меньше —
#: и живой долгий цикл убьют; больше — и очередь встанет незаметно.
STALE_LOCK = timedelta(minutes=15)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


@dataclass
class Timeline:
    """Все отметки времени одного изменения.

    Разделение `provider_timestamp` и `detected_at` — не педантизм: подмена
    одного другим выдаёт наше наблюдение за факт выхода серии, и тогда цифры
    свежести описывают не то, что мы обещали.
    """

    detected_at: datetime
    provider_timestamp: datetime | None = None
    event_created_at: datetime | None = None
    render_started_at: datetime | None = None
    render_finished_at: datetime | None = None
    published_at: datetime | None = None
    cache_invalidated_at: datetime | None = None
    live_verified_at: datetime | None = None

    @property
    def total_latency_seconds(self) -> float | None:
        if self.live_verified_at is None:
            return None
        return (self.live_verified_at - self.detected_at).total_seconds()

    def as_dict(self) -> dict:
        out = {k: _iso(v) for k, v in asdict(self).items()}
        out["total_latency_seconds"] = self.total_latency_seconds
        return out

    @classmethod
    def from_dict(cls, raw: dict) -> Timeline:
        return cls(**{
            k: _parse(raw.get(k))
            for k in (
                "detected_at", "provider_timestamp", "event_created_at",
                "render_started_at", "render_finished_at", "published_at",
                "cache_invalidated_at", "live_verified_at",
            )
        })


@dataclass
class QueueItem:
    idempotency_key: str
    event_type: str
    canonical_title_id: str
    payload: dict
    timeline: Timeline
    attempts: int = 0
    done: bool = False

    def as_dict(self) -> dict:
        return {
            "idempotency_key": self.idempotency_key,
            "event_type": self.event_type,
            "canonical_title_id": self.canonical_title_id,
            "payload": self.payload,
            "timeline": self.timeline.as_dict(),
            "attempts": self.attempts,
            "done": self.done,
        }

    @classmethod
    def from_dict(cls, raw: dict) -> QueueItem:
        return cls(
            idempotency_key=raw["idempotency_key"],
            event_type=raw["event_type"],
            canonical_title_id=raw["canonical_title_id"],
            payload=raw.get("payload") or {},
            timeline=Timeline.from_dict(raw.get("timeline") or {}),
            attempts=int(raw.get("attempts", 0)),
            done=bool(raw.get("done", False)),
        )


class FreshnessQueue:
    """Очередь изменений, переживающая перезапуск.

    Хранится файлом и переписывается атомарно. Очередь, теряющаяся при
    перезапуске, гарантирует пропущенную серию ровно тогда, когда что-то пошло
    не так, — то есть в единственный момент, когда она нужна.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._items: dict[str, QueueItem] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if raw.get("schema_version") != SCHEMA_VERSION:
            return
        for item in raw.get("items", ()):
            восстановлен = QueueItem.from_dict(item)
            self._items[восстановлен.idempotency_key] = восстановлен

    def save(self) -> None:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "items": [i.as_dict() for i in self._items.values()],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
        tmp.replace(self.path)

    def offer(self, item: QueueItem) -> bool:
        """Положить изменение. Повтор того же не создаёт второй записи."""
        if item.idempotency_key in self._items:
            return False
        self._items[item.idempotency_key] = item
        return True

    def pending(self) -> list[QueueItem]:
        return [i for i in self._items.values() if not i.done]

    def complete(self, key: str, *, live_verified_at: datetime | None = None) -> None:
        item = self._items.get(key)
        if item is None:
            return
        item.done = True
        if live_verified_at is not None:
            item.timeline.live_verified_at = live_verified_at

    def oldest_pending_age(self, *, now: datetime | None = None) -> timedelta | None:
        now = now or utc_now()
        ожидающие = self.pending()
        if not ожидающие:
            return None
        return now - min(i.timeline.detected_at for i in ожидающие)

    def latencies(self) -> list[float]:
        return [
            i.timeline.total_latency_seconds
            for i in self._items.values()
            if i.timeline.total_latency_seconds is not None
        ]

    def percentile(self, p: float = 0.95) -> float | None:
        значения = sorted(self.latencies())
        if not значения:
            return None
        # Индекс по ближайшему рангу: на малых выборках это честнее
        # интерполяции, которая придумывает значение между измерениями.
        индекс = max(0, min(len(значения) - 1, int(round(p * len(значения) + 0.5)) - 1))
        return значения[индекс]

    def __len__(self) -> int:
        return len(self._items)


class Lock:
    """Замок цикла с признаком брошенности.

    Оборванный процесс оставляет замок, и без срока годности очередь встаёт
    навсегда — тихо, потому что снаружи это выглядит как «цикл идёт».
    """

    def __init__(self, path: Path, *, stale_after: timedelta = STALE_LOCK) -> None:
        self.path = path
        self.stale_after = stale_after

    def acquire(self, *, now: datetime | None = None) -> bool:
        now = now or utc_now()
        if self.path.exists():
            возраст = now - _parse(
                json.loads(self.path.read_text(encoding="utf-8")).get("taken_at")
            )
            if возраст < self.stale_after:
                return False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent))
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump({"taken_at": _iso(now), "pid": os.getpid()}, handle)
        os.replace(tmp, self.path)
        return True

    def release(self) -> None:
        self.path.unlink(missing_ok=True)

    def age(self, *, now: datetime | None = None) -> timedelta | None:
        if not self.path.exists():
            return None
        now = now or utc_now()
        return now - _parse(json.loads(self.path.read_text(encoding="utf-8")).get("taken_at"))


@dataclass
class SlaReport:
    level: str
    reasons: list[str] = field(default_factory=list)
    oldest_pending_seconds: float | None = None
    p95_seconds: float | None = None
    measured: int = 0

    def as_dict(self) -> dict:
        return {
            "level": self.level,
            "reasons": self.reasons,
            "oldest_pending_seconds": self.oldest_pending_seconds,
            "p95_seconds": self.p95_seconds,
            "measured": self.measured,
            "warning_after_seconds": WARNING_AGE.total_seconds(),
            "critical_after_seconds": CRITICAL_AGE.total_seconds(),
        }


def evaluate_sla(
    queue: FreshnessQueue,
    *,
    last_success: datetime | None = None,
    now: datetime | None = None,
) -> SlaReport:
    """Состояние свежести: не «работает ли», а «успеваем ли».

    Отсутствие изменений у поставщика задержкой не считается: пустая очередь
    означает, что менять нечего, а не что мы опоздали.
    """
    now = now or utc_now()
    отчёт = SlaReport(level="ok")
    возраст = queue.oldest_pending_age(now=now)
    if возраст is not None:
        отчёт.oldest_pending_seconds = возраст.total_seconds()
        if возраст >= CRITICAL_AGE:
            отчёт.level = "critical"
            отчёт.reasons.append(
                f"старейшее необработанное изменение ждёт {возраст.total_seconds():.0f} с "
                f"при обещании в {CRITICAL_AGE.total_seconds():.0f} с"
            )
        elif возраст >= WARNING_AGE:
            отчёт.level = "warning"
            отчёт.reasons.append(
                f"старейшее необработанное изменение ждёт {возраст.total_seconds():.0f} с"
            )

    if last_success is not None:
        простой = now - last_success
        if простой >= CRITICAL_AGE:
            отчёт.level = "critical"
            отчёт.reasons.append(
                f"успешного быстрого цикла не было {простой.total_seconds():.0f} с"
            )
        elif простой >= WARNING_AGE and отчёт.level == "ok":
            отчёт.level = "warning"
            отчёт.reasons.append(
                f"успешного быстрого цикла не было {простой.total_seconds():.0f} с"
            )

    измерено = queue.latencies()
    отчёт.measured = len(измерено)
    отчёт.p95_seconds = queue.percentile(0.95)
    if отчёт.p95_seconds is not None and отчёт.p95_seconds > CRITICAL_AGE.total_seconds():
        отчёт.level = "critical"
        отчёт.reasons.append(
            f"p95 задержки {отчёт.p95_seconds:.0f} с превышает обещание "
            f"{CRITICAL_AGE.total_seconds():.0f} с"
        )
    return отчёт


def provider_gap(queue: FreshnessQueue) -> bool:
    """Пусто ли у поставщика.

    Отсутствие изменений — не наша задержка, и записывается отдельно. Иначе
    тихие сутки выглядели бы как отказ системы.
    """
    return not queue.pending()


@dataclass
class CycleResult:
    started_at: datetime
    finished_at: datetime
    processed: int
    skipped_duplicates: int
    pages_rendered: int
    published: bool
    reason: str = ""

    @property
    def duration_seconds(self) -> float:
        return (self.finished_at - self.started_at).total_seconds()

    def as_dict(self) -> dict:
        return {
            "started_at": _iso(self.started_at),
            "finished_at": _iso(self.finished_at),
            "duration_seconds": self.duration_seconds,
            "processed": self.processed,
            "skipped_duplicates": self.skipped_duplicates,
            "pages_rendered": self.pages_rendered,
            "published": self.published,
            "reason": self.reason,
        }


def run_fast_cycle(
    queue: FreshnessQueue,
    *,
    incoming: Iterable[QueueItem] = (),
    render,
    publish,
    verify,
    now=None,
) -> CycleResult:
    """Один быстрый цикл: принять, перестроить затронутое, опубликовать, проверить.

    Рендер, публикация и проверка передаются снаружи. Цикл, сам решающий, как
    рендерить, невозможно проверить без витрины, — а проверять его надо чаще,
    чем есть витрины.
    """
    now = now or utc_now
    начало = now()
    новых = 0
    дублей = 0
    for item in incoming:
        if queue.offer(item):
            новых += 1
        else:
            дублей += 1

    ожидающие = queue.pending()
    if not ожидающие:
        конец = now()
        queue.save()
        return CycleResult(начало, конец, 0, дублей, 0, False,
                           reason="изменений нет — у поставщика пусто")

    страниц = 0
    for item in ожидающие:
        item.attempts += 1
        item.timeline.render_started_at = now()
        страниц += render(item)
        item.timeline.render_finished_at = now()

    publish()
    момент = now()
    for item in ожидающие:
        item.timeline.published_at = момент
        item.timeline.cache_invalidated_at = момент

    for item in ожидающие:
        if verify(item):
            queue.complete(item.idempotency_key, live_verified_at=now())

    queue.save()
    конец = now()
    return CycleResult(начало, конец, len(ожидающие), дублей, страниц, True)
