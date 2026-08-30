"""Кэш как отдельный модуль с собственным контрактом.

Правка, сделанная в родительской задаче, живёт в TypeScript одной витрины.
Здесь описан общий контракт и приведена эталонная реализация на Python, чтобы
второй сайт не начинал с чистого листа и не изобрёл несовместимое поведение.
Production-кэш в рамках 02A не меняется.

Каждый запрет ниже соответствует уже случившемуся:

* **5xx не кэшируется.** Иначе одна плохая минута источника становится
  пятнадцатью минутами плохой витрины.
* **Пустой ответ не становится новым last-known-good.** Каталог однажды
  «похудел» именно так: неполный ответ закэшировался как успешный.
* **Ключи скоупятся сайтом.** Три тенанта из одного образа не должны видеть
  кэш друг друга.
* **Свежесть новых серий не зависит от TTL общей страницы.** Полка новых серий
  инвалидируется по версии файла наблюдателя, а не по часам.
"""
from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, Generic, Protocol, TypeVar, runtime_checkable

T = TypeVar("T")


class CacheOutcome(str, Enum):
    HIT = "hit"
    MISS = "miss"
    STALE = "stale"
    ERROR_KEPT_GOOD = "error-kept-good"


@dataclass(frozen=True)
class CacheKey:
    """Ключ всегда знает свой сайт: общий кэш трёх тенантов — это утечка."""

    site_id: str
    space: str
    discriminator: str = ""

    def __str__(self) -> str:
        tail = f":{self.discriminator}" if self.discriminator else ""
        return f"{self.site_id}:{self.space}{tail}"


@dataclass(frozen=True)
class CachePolicy:
    ttl_seconds: float
    stale_while_revalidate_seconds: float = 0.0
    last_known_good: bool = True
    tags: tuple[str, ...] = ()
    negative_ttl_seconds: float = 0.0

    def __post_init__(self) -> None:
        if self.ttl_seconds <= 0:
            raise ValueError("TTL должен быть положительным; бессрочного кэша HTML не бывает")
        if self.stale_while_revalidate_seconds < 0:
            raise ValueError("окно фонового обновления не может быть отрицательным")


@dataclass
class CacheResult(Generic[T]):
    value: T
    outcome: CacheOutcome
    age_seconds: float


@dataclass(frozen=True)
class InvalidationRequest:
    """Просьба сбросить теги. Кэш не решает, что считать изменением."""

    site_id: str
    tags: tuple[str, ...]
    reason: str
    dry_run: bool = False


@runtime_checkable
class CacheProvider(Protocol):
    def get_or_load(self, key: CacheKey, policy: CachePolicy,
                    load: Callable[[], Any]) -> CacheResult: ...
    def invalidate(self, request: InvalidationRequest) -> tuple[str, ...]: ...
    def stats(self) -> dict[str, int]: ...


class UncacheableResponse(Exception):
    """Ответ, который нельзя запоминать: ошибка источника или пустой результат.

    Загрузчик поднимает это исключение сам — кэш не должен угадывать, что
    считать пустым: для полки пустота нормальна, для каталога она бедствие.
    """


@dataclass
class _Entry:
    value: Any
    stored_at: float


class LastKnownGoodStore:
    """Последнее хорошее значение, отдельно от горячего кэша.

    Отдельно — потому что инвалидация тега стирает горячее значение, а
    страховку на случай отказа источника стирать не следует.
    """

    def __init__(self) -> None:
        self._values: dict[str, Any] = {}
        self._lock = threading.RLock()

    def remember(self, key: CacheKey, value: Any) -> None:
        with self._lock:
            self._values[str(key)] = value

    def recall(self, key: CacheKey) -> Any | None:
        with self._lock:
            return self._values.get(str(key))


class RequestCoalescer:
    """Один промах — одно обращение к источнику.

    Без этого сброс тега на популярной странице превращается в лавину
    одинаковых запросов к поставщику.
    """

    def __init__(self) -> None:
        self._locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()

    def lock_for(self, key: CacheKey) -> threading.Lock:
        with self._guard:
            return self._locks.setdefault(str(key), threading.Lock())


class InMemoryCache:
    """Эталонная реализация контракта.

    Часы передаются параметром: поведение TTL иначе нечем проверить, а тест,
    который спит две секунды, — плохой тест.
    """

    def __init__(self, clock: Callable[[], float] | None = None) -> None:
        import time

        self._clock = clock or time.monotonic
        self._entries: dict[str, _Entry] = {}
        self._tags: dict[str, set[str]] = {}
        self._lkg = LastKnownGoodStore()
        self._coalescer = RequestCoalescer()
        self._stats: dict[str, int] = {o.value: 0 for o in CacheOutcome}
        self._lock = threading.RLock()

    def get_or_load(self, key: CacheKey, policy: CachePolicy,
                    load: Callable[[], Any]) -> CacheResult:
        name = str(key)
        with self._lock:
            entry = self._entries.get(name)
        now = self._clock()

        if entry is not None:
            age = now - entry.stored_at
            if age < policy.ttl_seconds:
                return self._done(entry.value, CacheOutcome.HIT, age)
            if age < policy.ttl_seconds + policy.stale_while_revalidate_seconds:
                # Отдаём прежнее и обновляем при следующем обращении: фонового
                # потока здесь нет намеренно, он превратил бы простой кэш в
                # планировщик.
                self._refresh_quietly(key, policy, load)
                return self._done(entry.value, CacheOutcome.STALE, age)

        with self._coalescer.lock_for(key):
            with self._lock:
                entry = self._entries.get(name)
            now = self._clock()
            if entry is not None and now - entry.stored_at < policy.ttl_seconds:
                return self._done(entry.value, CacheOutcome.HIT, now - entry.stored_at)
            try:
                value = load()
            except UncacheableResponse:
                good = self._lkg.recall(key) if policy.last_known_good else None
                if good is not None:
                    return self._done(good, CacheOutcome.ERROR_KEPT_GOOD, 0.0)
                raise
            self._store(key, policy, value)
            return self._done(value, CacheOutcome.MISS, 0.0)

    def _refresh_quietly(self, key: CacheKey, policy: CachePolicy,
                         load: Callable[[], Any]) -> None:
        try:
            value = load()
        except UncacheableResponse:
            # Отказ при фоновом обновлении не должен стирать хорошее значение.
            return
        self._store(key, policy, value)

    def _store(self, key: CacheKey, policy: CachePolicy, value: Any) -> None:
        name = str(key)
        with self._lock:
            self._entries[name] = _Entry(value=value, stored_at=self._clock())
            for tag in policy.tags:
                self._tags.setdefault(self._scoped(key.site_id, tag), set()).add(name)
        if policy.last_known_good:
            self._lkg.remember(key, value)

    def _done(self, value: Any, outcome: CacheOutcome, age: float) -> CacheResult:
        with self._lock:
            self._stats[outcome.value] += 1
        return CacheResult(value=value, outcome=outcome, age_seconds=age)

    @staticmethod
    def _scoped(site_id: str, tag: str) -> str:
        return f"{site_id}/{tag}"

    def invalidate(self, request: InvalidationRequest) -> tuple[str, ...]:
        """Возвращает ключи, которые были бы сброшены. При `dry_run` — не сбрасывает."""
        affected: set[str] = set()
        with self._lock:
            for tag in request.tags:
                affected |= self._tags.get(self._scoped(request.site_id, tag), set())
            if not request.dry_run:
                for name in affected:
                    self._entries.pop(name, None)
                for tag in request.tags:
                    self._tags.pop(self._scoped(request.site_id, tag), None)
        return tuple(sorted(affected))

    def stats(self) -> dict[str, int]:
        with self._lock:
            return dict(self._stats)


class FileVersionCache:
    """Кэш, ключом которого служит состояние файла, а не часы.

    Нужен там, где TTL вреден: снимок наблюдателя переписывается каждые
    несколько минут, и полка новых серий обязана увидеть новую версию сразу.
    Часы дали бы либо задержку, либо отсутствие экономии. Свежесть здесь не
    приносится в жертву вовсе — исчезает только повторный разбор.
    """

    def __init__(self) -> None:
        self._values: dict[str, tuple[str, Any]] = {}
        self._lock = threading.RLock()
        self.hits = 0
        self.misses = 0

    def get_or_load(self, key: CacheKey, version: str,
                    load: Callable[[], Any]) -> Any:
        name = str(key)
        with self._lock:
            known = self._values.get(name)
            if known is not None and known[0] == version:
                self.hits += 1
                return known[1]
        value = load()
        with self._lock:
            self._values[name] = (version, value)
            self.misses += 1
        return value


def tags_for_event(event_type: str) -> tuple[str, ...]:
    from factory.site_engine.contracts import EVENT_CACHE_TAGS, EventType

    try:
        return EVENT_CACHE_TAGS[EventType(event_type)]
    except ValueError:
        return ()


FORBIDDEN: dict[str, str] = {
    "cache_errors": "ошибки источника не кэшируются",
    "empty_response_as_success": "пустой ответ не становится новым last-known-good",
    "indefinite_html_cache": "бессрочного кэша HTML не бывает",
}
