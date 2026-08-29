"""Мост между каталогом Lords и общим ранжировщиком.

Ранжировщик намеренно ничего не знает про Lords, поэтому перевод из записи
каталога в набор признаков живёт здесь. Так же будут подключаться будущие
домены: свой адаптер, общий Ranker.

Одно правило переносится сюда без послаблений: в карусель попадает только то,
у чего источник подтвердил поток. Витрина обещает просмотр, и обещание должно
быть исполнимым — иначе посетитель кликает первую карточку и упирается в
чёрный прямоугольник, как это уже было.
"""
from __future__ import annotations

from datetime import datetime, timezone

from factory.recs import shelves as shelves_mod
from factory.recs.model import ItemFeatures, parse_time
from factory.recs.ranker import ALGORITHM_VERSION

#: Полки главной и их порядок. Разные полки отвечают на разные вопросы и
#: опираются на разные даты — смешивать их нельзя.
HOME_SHELVES = (
    shelves_mod.LATEST_ADDED,
    shelves_mod.HIGH_RATED,
    shelves_mod.UPDATED_SERIES,
)


def features_from_title(title) -> ItemFeatures:
    """Запись каталога → признаки для ранжировщика."""
    playback = getattr(title, "playback", None) or {}
    external = getattr(title, "external_id", None) or getattr(title, "slug", "")
    return ItemFeatures(
        content_id=str(external),
        title=title.name or "",
        original_title=getattr(title, "original_name", None),
        content_type=title.content_type,
        provider_ids={k: str(v) for k, v in (playback or {}).items() if v},
        added_at=parse_time(getattr(title, "created_at", None)),
        release_date=_year_as_date(getattr(title, "year", None)),
        episode_updated_at=parse_time(getattr(title, "updated_at", None))
        if getattr(title, "episodic", False) else None,
        genres=tuple(getattr(title, "genres", ()) or ()),
        countries=tuple(c for c in (getattr(title, "country", None),) if c),
        franchise_id=None,
        poster=getattr(title, "poster_url", None) or getattr(title, "poster_src", None),
        path=getattr(title, "path", None),
        playback_state=getattr(title, "playable", None),
        has_title_page=True,
        kp_rating=getattr(title, "kinopoisk_rating", None),
        imdb_rating=getattr(title, "imdb_rating", None),
    )


def _year_as_date(year) -> datetime | None:
    """Год выпуска как дата. Точнее источник не сообщает, и выдумывать не нужно."""
    if not isinstance(year, int) or not (1900 <= year <= 2100):
        return None
    return datetime(year, 1, 1, tzinfo=timezone.utc)


def build_home_shelves(titles, *, now=None, limit: int = 18, domain: str | None = None,
                       editorial=None, shelf_ids=HOME_SHELVES) -> list:
    """Полки главной, собранные ранжировщиком, а не вручную."""
    items = [features_from_title(t) for t in titles]
    built = []
    for shelf_id in shelf_ids:
        shelf = shelves_mod.build_shelf(
            shelf_id, items, now=now, limit=limit, domain=domain, editorial=editorial)
        if len(shelf) >= 4:
            built.append(shelf)
    return built


def carousel_shelf(titles, *, now=None, limit: int = 18, domain: str | None = None,
                   editorial=None):
    """Верхняя карусель: самые свежие из подтверждённо смотрибельных."""
    items = [features_from_title(t) for t in titles]
    return shelves_mod.build_shelf(
        shelves_mod.LATEST_ADDED, items, now=now, limit=limit,
        domain=domain, editorial=editorial)


__all__ = ["ALGORITHM_VERSION", "build_home_shelves", "carousel_shelf",
           "features_from_title", "HOME_SHELVES"]
