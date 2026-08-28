"""Единая модель признаков рекомендуемой записи.

Модуль намеренно ничего не знает ни про Lords, ни про Yummy, ни про конкретного
поставщика: он принимает уже нормализованные признаки. Так один и тот же
ранжировщик обслуживает шесть сегодняшних сайтов и переиспользуется будущими
доменами без копирования кодовой базы.

Главное правило модели: отсутствующий сигнал — это `None`, а не ноль. Ноль в
шкале оценок означает «оценили на ноль», ноль просмотров — «смотрели ноль раз»;
подставить его вместо неизвестности значит наказать запись за то, что о ней
просто нечего сказать.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone


def parse_time(value) -> datetime | None:
    """ISO-8601 → datetime в UTC. Мусор превращается в `None`, а не в эпоху."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


@dataclass(frozen=True)
class ItemFeatures:
    """Признаки одной записи.

    `content_id` — устойчивый идентификатор, по которому запись узнаётся между
    поставщиками, доменами и перезапусками. Слаг для этого не годится: он
    меняется вместе с названием и совпадает у разных записей.
    """

    content_id: str
    title: str = ""
    original_title: str | None = None
    content_type: str = ""
    direction: str | None = None
    provider_ids: dict = field(default_factory=dict)

    added_at: datetime | None = None
    release_date: datetime | None = None
    episode_updated_at: datetime | None = None

    genres: tuple[str, ...] = ()
    countries: tuple[str, ...] = ()
    persons: tuple[str, ...] = ()
    franchise_id: str | None = None

    poster: str | None = None
    backdrop: str | None = None

    #: True — источник подтвердил поток, False — подтвердил, что его нет,
    #: None — не проверяли. Только False запрещает показ.
    playback_state: bool | None = None
    has_title_page: bool = True

    kp_rating: float | None = None
    kp_votes: int | None = None
    imdb_rating: float | None = None
    imdb_votes: int | None = None

    metadata_completeness: float | None = None
    domain_eligibility: tuple[str, ...] = ()
    reference_mentions: tuple[dict, ...] = ()

    events_1d: int | None = None
    events_7d: int | None = None
    events_30d: int | None = None

    def with_(self, **changes) -> ItemFeatures:
        return replace(self, **changes)


def merge_duplicates(items) -> list[ItemFeatures]:
    """Сигналы об одной записи сливаются в одну запись.

    Один и тот же тайтл приходит из разных источников под разными слагами. Если
    их не слить, он займёт в полке два места подряд, а его сигналы окажутся
    поделены пополам и он проиграет тем, кто пришёл одним куском.

    Слияние идёт по `content_id`. Побеждает не последний, а более полный:
    подтверждённое воспроизведение важнее неизвестного, известная оценка важнее
    отсутствующей, счётчики складываются.
    """
    merged: dict[str, ItemFeatures] = {}
    for item in items:
        current = merged.get(item.content_id)
        if current is None:
            merged[item.content_id] = item
            continue
        merged[item.content_id] = _combine(current, item)
    return list(merged.values())


def _prefer(left, right):
    return left if left is not None else right


def _combine(left: ItemFeatures, right: ItemFeatures) -> ItemFeatures:
    def sum_counts(a, b):
        if a is None and b is None:
            return None
        return (a or 0) + (b or 0)

    # Подтверждённое «нечего играть» и подтверждённый поток важнее незнания;
    # если источники спорят, побеждает подтверждение потока: запись, которая
    # у кого-то играет, играет.
    playback = left.playback_state
    if playback is None:
        playback = right.playback_state
    elif right.playback_state is True:
        playback = True

    return left.with_(
        title=left.title or right.title,
        original_title=_prefer(left.original_title, right.original_title),
        content_type=left.content_type or right.content_type,
        direction=_prefer(left.direction, right.direction),
        provider_ids={**right.provider_ids, **left.provider_ids},
        added_at=_prefer(left.added_at, right.added_at),
        release_date=_prefer(left.release_date, right.release_date),
        episode_updated_at=_prefer(left.episode_updated_at, right.episode_updated_at),
        genres=left.genres or right.genres,
        countries=left.countries or right.countries,
        persons=left.persons or right.persons,
        franchise_id=_prefer(left.franchise_id, right.franchise_id),
        poster=_prefer(left.poster, right.poster),
        backdrop=_prefer(left.backdrop, right.backdrop),
        playback_state=playback,
        has_title_page=left.has_title_page and right.has_title_page,
        kp_rating=_prefer(left.kp_rating, right.kp_rating),
        kp_votes=_prefer(left.kp_votes, right.kp_votes),
        imdb_rating=_prefer(left.imdb_rating, right.imdb_rating),
        imdb_votes=_prefer(left.imdb_votes, right.imdb_votes),
        metadata_completeness=_prefer(left.metadata_completeness, right.metadata_completeness),
        domain_eligibility=tuple(dict.fromkeys(left.domain_eligibility + right.domain_eligibility)),
        reference_mentions=left.reference_mentions + right.reference_mentions,
        events_1d=sum_counts(left.events_1d, right.events_1d),
        events_7d=sum_counts(left.events_7d, right.events_7d),
        events_30d=sum_counts(left.events_30d, right.events_30d),
    )
