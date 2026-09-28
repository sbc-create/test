"""Нормализованная модель Site Engine.

Здесь живут определения, на которые ссылаются все остальные модули, и не живёт
ничего больше: ни HTTP, ни файлов, ни базы, ни имён конкретных сайтов. Это
проверяется гейтом границ, а не обещанием.

Три правила, которые модель обязана удерживать, потому что каждое куплено
инцидентом:

* **Время поставщика и время наблюдения — разные поля.** Публичный API
  поставщика не отдаёт `updated_at` в карточке вовсе. Подставлять момент
  нашего опроса вместо времени источника значит выдавать наблюдение за факт.
* **Отсутствие значения — это `None`, а не ноль и не пустая строка.** Оценка
  0.0 и «оценки нет» — разные утверждения, и витрина показывает их по-разному.
* **У всякого значения есть происхождение.** Поле `provenance` отвечает на
  вопрос «откуда это известно», и ответ «неоткуда» тоже допустим.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any

SCHEMA_VERSION = "1.0"


class ContractError(Exception):
    """Нарушение контракта нормализованной модели."""


class Provenance(str, Enum):
    """Откуда известно значение.

    `DERIVED` — вычислено нами из других полей; `OBSERVED` — увидено при
    обходе, но источником не заявлено. Их различие важно: производное значение
    нельзя предъявлять как сообщённое поставщиком.
    """

    PROVIDER = "provider"
    OBSERVED = "observed"
    DERIVED = "derived"
    EDITORIAL = "editorial"
    UNKNOWN = "unknown"


class EventType(str, Enum):
    TITLE_CREATED = "TITLE_CREATED"
    TITLE_UPDATED = "TITLE_UPDATED"
    EPISODE_ADDED = "EPISODE_ADDED"
    SEASON_ADDED = "SEASON_ADDED"
    #: Появилась новая озвучка. Наблюдатель Yummy выпускает такие события
    #: на живой витрине, а контракт их не знал: строгий переводчик ленты
    #: упёрся в них на первой же записи. Род события, который система
    #: производит, а контракт не выражает, — неполнота контракта, а не
    #: лишнее событие.
    VOICEOVER_ADDED = "VOICEOVER_ADDED"
    PLAYBACK_AVAILABLE = "PLAYBACK_AVAILABLE"
    PLAYBACK_UNAVAILABLE = "PLAYBACK_UNAVAILABLE"
    RATING_UPDATED = "RATING_UPDATED"
    SCHEDULE_UPDATED = "SCHEDULE_UPDATED"
    ANNOUNCEMENT_UPDATED = "ANNOUNCEMENT_UPDATED"
    SOURCE_ANOMALY = "SOURCE_ANOMALY"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def require_aware(value: datetime | None, field_name: str) -> datetime | None:
    """Время без зоны — источник ошибок, которые всплывают через полгода.

    Наивная метка молча трактуется как локальная, а хост живёт в UTC, витрины —
    в Москве, поставщик — неизвестно где. Поэтому наивное время не принимается
    вовсе, а не «нормализуется» догадкой.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        raise ContractError(f"{field_name}: время без часового пояса не принимается")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class ExternalIds:
    """Идентификаторы в чужих системах.

    Ровно те пять, что отдаёт поставщик. Список закрыт намеренно: угаданный
    идентификатор ведёт на чужую карточку, и заметить это по внешнему виду
    невозможно.
    """

    kp: str | None = None
    imdb: str | None = None
    tmdb: str | None = None
    mdl: str | None = None
    mal: str | None = None

    def as_dict(self) -> dict[str, str]:
        return {k: v for k, v in self.__dict__.items() if v}


@dataclass(frozen=True)
class Rating:
    """Оценка из одного источника.

    Шкала фиксирована: 0.1–10. Значение вне неё — не «плохая оценка», а признак
    того, что источник понят неверно, и оно отклоняется.
    """

    source: str
    value: float
    provenance: Provenance = Provenance.PROVIDER
    observed_at: datetime | None = None

    MIN = 0.1
    MAX = 10.0

    def __post_init__(self) -> None:
        if not (self.MIN <= self.value <= self.MAX):
            raise ContractError(
                f"оценка {self.value} вне шкалы {self.MIN}–{self.MAX}: "
                "источник понят неверно"
            )
        object.__setattr__(self, "observed_at", require_aware(self.observed_at, "observed_at"))


@dataclass(frozen=True)
class Episode:
    number: int
    season_number: int
    title: str | None = None
    air_date: str | None = None
    provenance: Provenance = Provenance.PROVIDER


@dataclass(frozen=True)
class Season:
    """Сезон в том виде, в каком его сообщает источник.

    Списка серий у поставщика нет ни на одном маршруте — есть два счётчика.
    Поэтому дельта серий считается по ним, и модель не притворяется, будто
    знает поимённо каждую серию.
    """

    number: int
    name: str | None = None
    episodes_count: int | None = None
    available_episodes_count: int | None = None
    episodes: tuple[Episode, ...] = ()

    def __post_init__(self) -> None:
        for name in ("episodes_count", "available_episodes_count"):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ContractError(f"{name}: отрицательное количество серий")


@dataclass(frozen=True)
class EpisodeCounts:
    """Счётчики серий, когда поимённого списка сезонов нет.

    Наблюдатель хранит именно так: `availableEpisodes`, `plannedEpisodes`,
    `maxSeason`, `maxEpisode`, `seasonsCount`. Достраивать из них список
    сезонов значит выдумывать структуру, которой источник не сообщал, поэтому
    счётчики остаются счётчиками.

    Заполнены не у всех: из 6774 наблюдаемых записей `availableEpisodes` есть у
    4997. Отсутствие — это `None`, а не ноль: «серий нет» и «неизвестно,
    сколько серий» — разные утверждения, и полка обязана различать их.
    """

    available: int | None = None
    planned: int | None = None
    max_season: int | None = None
    max_episode: int | None = None
    seasons_count: int | None = None
    provenance: Provenance = Provenance.PROVIDER

    def __post_init__(self) -> None:
        for name in ("available", "planned", "max_season", "max_episode", "seasons_count"):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ContractError(f"{name}: отрицательное количество")

    @property
    def known(self) -> bool:
        return self.available is not None


@dataclass(frozen=True)
class PlaybackAvailability:
    available: bool
    checked_at: datetime | None = None
    provenance: Provenance = Provenance.OBSERVED

    def __post_init__(self) -> None:
        object.__setattr__(self, "checked_at", require_aware(self.checked_at, "checked_at"))


@dataclass(frozen=True)
class Title:
    """Тайтл нормализованной модели.

    `provider_timestamp` отделён от `observed_at` сознательно и может быть
    пустым: поставщик его не сообщает. `observed_at` пустым не бывает — за него
    отвечаем мы.
    """

    canonical_id: str
    provider: str
    provider_id: str
    name: str
    observed_at: datetime
    provider_timestamp: datetime | None = None
    original_name: str | None = None
    year: int | None = None
    kind: str | None = None
    genres: tuple[str, ...] = ()
    countries: tuple[str, ...] = ()
    external_ids: ExternalIds = field(default_factory=ExternalIds)
    ratings: tuple[Rating, ...] = ()
    seasons: tuple[Season, ...] = ()
    playback: PlaybackAvailability | None = None
    episode_counts: EpisodeCounts | None = None
    poster_url: str | None = None
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.canonical_id:
            raise ContractError("canonical_id обязателен: без него запись не с чем сопоставить")
        if not self.name.strip():
            raise ContractError("имя тайтла пустое: показывать нечего")
        object.__setattr__(self, "observed_at", require_aware(self.observed_at, "observed_at"))
        object.__setattr__(
            self, "provider_timestamp", require_aware(self.provider_timestamp, "provider_timestamp")
        )

    @property
    def available_episodes(self) -> int | None:
        """Сколько серий доступно.

        Возвращает `None`, а не ноль, когда неизвестно: источник сообщает
        счётчики не у всех записей, и ноль на витрине означал бы «серий нет»,
        чего никто не утверждал.
        """
        if self.seasons:
            known = [s.available_episodes_count for s in self.seasons
                     if s.available_episodes_count is not None]
            return sum(known) if known else None
        if self.episode_counts is not None:
            return self.episode_counts.available
        return None

    def best_rating(self) -> Rating | None:
        """Кинопоиск, затем IMDb, затем что есть. Порядок задан владельцем."""
        order = ("kinopoisk", "imdb")
        for wanted in order:
            for rating in self.ratings:
                if rating.source == wanted:
                    return rating
        return self.ratings[0] if self.ratings else None

    def with_overrides(self, overrides: dict[str, Any]) -> Title:
        """Наложение редакторских правок поверх данных поставщика.

        Исходная запись не меняется: правки живут отдельно и применяются при
        показе. Это и есть правило «provider-данные read-only» — оно выражено
        типом, а не соглашением.
        """
        allowed = {"name", "original_name", "poster_url", "year", "kind"}
        unknown = set(overrides) - allowed
        if unknown:
            raise ContractError(
                f"редакторская правка не может менять {sorted(unknown)}: "
                "эти поля принадлежат поставщику"
            )
        return replace(self, **overrides)


@dataclass(frozen=True)
class ContentEvent:
    """Утверждение «мы увидели изменение».

    Не «поставщик изменил» и не «вышла серия». Разница стоила одного ложного
    инцидента и одного ложного срабатывания на 1483 события.
    """

    event_id: str
    event_type: EventType
    provider: str
    provider_id: str
    canonical_title_id: str
    observed_at: datetime
    idempotency_key: str
    payload: dict[str, Any] = field(default_factory=dict)
    site_id: str | None = None
    provider_timestamp: datetime | None = None
    source_fingerprint: dict[str, Any] | None = None
    correlation_id: str | None = None
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.idempotency_key:
            raise ContractError(
                "idempotency_key обязателен: без него повторный цикл положит "
                "одно изменение в ленту дважды"
            )
        object.__setattr__(self, "observed_at", require_aware(self.observed_at, "observed_at"))
        object.__setattr__(
            self, "provider_timestamp", require_aware(self.provider_timestamp, "provider_timestamp")
        )

    def cache_tags(self) -> tuple[str, ...]:
        """Событие, не сбрасывающее ни одного тега, до страницы не доедет."""
        return EVENT_CACHE_TAGS.get(self.event_type, ())


EVENT_CACHE_TAGS: dict[EventType, tuple[str, ...]] = {
    EventType.EPISODE_ADDED: ("title", "shelf:new-episodes", "catalog"),
    EventType.SEASON_ADDED: ("title", "catalog"),
    # Новая озвучка меняет карточку тайтла, но не состав каталога и не
    # полку новых серий: серии от неё не прибавляется.
    EventType.VOICEOVER_ADDED: ("title",),
    EventType.TITLE_CREATED: ("shelf:new-titles", "catalog"),
    EventType.TITLE_UPDATED: ("title", "catalog"),
    EventType.PLAYBACK_AVAILABLE: ("title", "shelf:watchable"),
    EventType.PLAYBACK_UNAVAILABLE: ("title", "shelf:watchable"),
    EventType.RATING_UPDATED: ("title", "ratings"),
    EventType.SCHEDULE_UPDATED: ("schedule",),
    EventType.ANNOUNCEMENT_UPDATED: ("announcements",),
    EventType.SOURCE_ANOMALY: (),
}


def idempotency_key(event_type: EventType, canonical_id: str, marker: str) -> str:
    """Один и тот же факт обязан дать один и тот же ключ.

    Маркер — то, что отличает событие: номер серии, значение оценки. Времени в
    ключе нет намеренно: иначе повторный цикл с тем же изменением положил бы его
    в ленту второй раз.

    Живёт в контрактах, а не в загрузчике, потому что ключ обязаны одинаково
    вычислять все, кто выпускает события, — включая переводчиков чужих форматов.
    """
    import hashlib

    return hashlib.sha256(
        f"{event_type.value}|{canonical_id}|{marker}".encode()
    ).hexdigest()[:32]


@dataclass(frozen=True)
class CoverageReport:
    """Полнота, а не факт успешного прогона.

    Успешно завершившийся обход, собравший половину каталога, — это неудача,
    которая выглядит как удача. Ровно так каталог Lords месяцами обрывался на
    4800 записях, отвечая при этом HTTP 200.
    """

    site_id: str
    source_total: int | None
    local_total: int
    observed_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "observed_at", require_aware(self.observed_at, "observed_at"))

    @property
    def missing(self) -> int | None:
        if self.source_total is None:
            return None
        return max(0, self.source_total - self.local_total)

    @property
    def ratio(self) -> float | None:
        if not self.source_total:
            return None
        return self.local_total / self.source_total

    @property
    def complete(self) -> bool | None:
        """`None` — не «полно» и не «неполно», а «источник не сказал сколько»."""
        if self.source_total is None:
            return None
        return self.local_total >= self.source_total


@dataclass(frozen=True)
class IngestionRun:
    run_id: str
    site_id: str
    started_at: datetime
    finished_at: datetime | None = None
    pages_walked: int = 0
    titles_seen: int = 0
    failures: int = 0
    truncated: bool = False
    coverage: CoverageReport | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "started_at", require_aware(self.started_at, "started_at"))
        object.__setattr__(self, "finished_at", require_aware(self.finished_at, "finished_at"))

    @property
    def status(self) -> str:
        if self.finished_at is None:
            return "running"
        if self.truncated:
            # Обрыв каталога — не успех. Публиковать неполный каталог как
            # полный нельзя, и статус обязан это говорить.
            return "truncated"
        return "failed" if self.failures else "succeeded"
