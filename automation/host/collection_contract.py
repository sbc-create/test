"""Единый контракт коллекций витрины.

Проблема, ради которой он появился: блок на главной показывал одну выборку, а
кнопка «Все →» вела в общий каталог или в другой раздел. На Animedia три блока
подряд были объявлены с фильтром `None` — то есть показывали одни и те же первые
записи каталога под тремя разными заголовками, и две ссылки из трёх уводили в
общий каталог.

Здесь коллекция описывается один раз: чем фильтруем, как сортируем, сколько
показываем в ленте и куда ведёт «Все →». Одна и та же функция `разрешить`
отдаёт и ленту (с лимитом), и полную страницу (со страницей). Шаблон не
повторяет фильтр и не придумывает адрес — он берёт их из спецификации.

Чего здесь принципиально нет: выдуманных данных. Если у контура нет признака
«сейчас выходит» или «популярное», коллекция объявляется с политикой `hide` и
просто не рисуется. Наполнять её похожими тайтлами запрещено — это и есть та
подмена, из-за которой блоки стали неразличимы.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

ВЕРСИЯ_КОНТРАКТА = 1

#: Политики пустого состояния. `hide` — блок не рисуется вовсе; `message` —
#: показывается короткая человеческая строка. Технических объяснений посетителю
#: не показывается ни в одном случае.
СКРЫТЬ = "hide"
СООБЩЕНИЕ = "message"


def _сейчас() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class Спецификация:
    """Описание коллекции. Одно на весь контур, а не по копии на шаблон."""

    collection_key: str
    family: str
    section_id: str
    title: str
    description: str
    source: str
    filter_spec: dict[str, Any]
    sort_spec: dict[str, str]
    freshness_rule: str
    card_limit: int
    view_all_path: str
    canonical_path: str
    empty_policy: str = СКРЫТЬ
    #: Коллекция, для которой у контура нет данных. Объявлена, чтобы её
    #: отсутствие было видимым фактом, а не забытой строкой в шаблоне.
    unavailable_reason: str = ""

    @property
    def доступна(self) -> bool:
        return not self.unavailable_reason


@dataclass
class Карточка:
    entity_id: str
    canonical_path: str
    title: str
    poster: str = ""
    badge: str = ""
    release_at: str = ""
    ratings: dict[str, float] = field(default_factory=dict)
    video_available: bool | None = None
    #: Исходная запись каталога. Нужна затем, чтобы шаблон рисовал карточку
    #: ровно теми же средствами, что и раньше: контракт меняет источник данных
    #: и адреса, но не оформление.
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def как_словарь(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "canonical_path": self.canonical_path,
            "title": self.title,
            "poster": self.poster,
            "badge": self.badge,
            "release_at": self.release_at,
            "ratings": dict(self.ratings),
            "video_available": self.video_available,
        }


@dataclass
class Коллекция:
    contract_version: int
    collection_key: str
    family: str
    section_id: str
    title: str
    description: str
    source: str
    filter_spec: dict[str, Any]
    sort_spec: dict[str, str]
    freshness_rule: str
    card_limit: int
    total: int
    items: list[Карточка]
    page: int
    view_all_path: str
    canonical_path: str
    generated_at: str
    data_revision: str
    empty_policy: str

    def как_словарь(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "collection_key": self.collection_key,
            "family": self.family,
            "section_id": self.section_id,
            "title": self.title,
            "description": self.description,
            "source": self.source,
            "filter_spec": dict(self.filter_spec),
            "sort_spec": dict(self.sort_spec),
            "freshness_rule": self.freshness_rule,
            "card_limit": self.card_limit,
            "total": self.total,
            "items": [к.как_словарь() for к in self.items],
            "page": self.page,
            "view_all_path": self.view_all_path,
            "canonical_path": self.canonical_path,
            "generated_at": self.generated_at,
            "data_revision": self.data_revision,
            "empty_policy": self.empty_policy,
        }


class Снимок:
    """Неизменяемый индексированный снимок каталога витрины.

    Ради него всё и затевалось: раньше каждый блок главной отдельно обходил
    весь каталог на каждом HTTP-запросе. Здесь порядок и разрезы считаются один
    раз на снимок, а блоки берут готовые срезы.
    """

    def __init__(self, items: list[dict], подробности: dict[str, dict] | None = None,
                 revision: str = "") -> None:
        self.items = items
        self.подробности = подробности or {}
        self.data_revision = revision or self._отпечаток(items)
        # Порядок по дате публикации считается один раз.
        self._по_дате = sorted(
            items, key=lambda з: str(з.get("published_at") or ""), reverse=True)
        self._по_виду: dict[str, list[dict]] = {}
        for з in self._по_дате:
            вид = str(з.get("kind") or "")
            if вид:
                self._по_виду.setdefault(вид, []).append(з)
        self._по_оценке = sorted(
            (з for з in items if self._оценка(з) > 0),
            key=self._оценка, reverse=True)
        годы = [з.get("year") for з in items if isinstance(з.get("year"), int)]
        self.максимальный_год = max(годы) if годы else None

    @staticmethod
    def _отпечаток(items: list[dict]) -> str:
        основа = "\n".join(sorted(str(з.get("slug") or "") for з in items))
        return hashlib.sha256(основа.encode("utf-8")).hexdigest()[:16]

    def _оценка(self, з: dict) -> float:
        д = self.подробности.get(str(з.get("slug") or "")) or {}
        лучшее = 0.0
        for поле in ("imdb_rating", "kinopoisk_rating"):
            значение = д.get(поле)
            try:
                число = float(значение)
            except (TypeError, ValueError):
                continue
            if 0.0 < число <= 10.0:
                лучшее = max(лучшее, число)
        return лучшее

    # --- срезы ------------------------------------------------------------

    def по_дате(self) -> list[dict]:
        return self._по_дате

    def по_виду(self, вид: str) -> list[dict]:
        return self._по_виду.get(вид, [])

    def по_оценке(self) -> list[dict]:
        return self._по_оценке

    def года(self, год: int) -> list[dict]:
        return [з for з in self._по_дате if з.get("year") == год]

    def играющие(self) -> list[dict]:
        готово = []
        for з in self._по_дате:
            д = self.подробности.get(str(з.get("slug") or "")) or {}
            if д.get("playable") is True:
                готово.append(з)
        return готово

    def по_жанру(self, код: str) -> list[dict]:
        if not код:
            return []
        out = []
        for з in self._по_дате:
            д = self.подробности.get(str(з.get("slug") or "")) or {}
            codes = list(д.get("genre_codes") or [])
            names = [str(g).lower() for g in (д.get("genres") or [])]
            if код in codes or код.lower() in names:
                out.append(з)
        return out

    def новинки_релиза(self, вид: str) -> list[dict]:
        """Titles with premiere_date in clock year, or year==clock year.

        Not the same as catalog ingest order (recently_added).
        """
        y = _clock_year()
        out = []
        for з in self.items:
            if вид and з.get("kind") != вид:
                continue
            д = self.подробности.get(str(з.get("slug") or "")) or {}
            prem = str(д.get("premiere_date") or "")[:10]
            if prem.startswith(str(y)):
                out.append(з)
                continue
            if з.get("year") == y:
                out.append(з)
        # Sort by premiere_date DESC then published_at.
        def key(з: dict) -> tuple:
            д = self.подробности.get(str(з.get("slug") or "")) or {}
            prem = str(д.get("premiere_date") or "")
            return (1 if prem else 0, prem, str(з.get("published_at") or ""))
        return sorted(out, key=key, reverse=True)


def _карточка(снимок: Снимок, з: dict) -> Карточка:
    слаг = str(з.get("slug") or "")
    д = снимок.подробности.get(слаг) or {}
    оценки = {}
    for поле, имя in (("imdb_rating", "imdb"), ("kinopoisk_rating", "kp")):
        try:
            число = float(д.get(поле))
        except (TypeError, ValueError):
            continue
        if 0.0 < число <= 10.0:
            оценки[имя] = число
    return Карточка(
        entity_id=str(д.get("id") or слаг),
        # Карточка всегда ведёт на собственный адрес своей сущности: ни на
        # соседний сезон, ни на другую часть франшизы.
        canonical_path=str(з.get("url") or f"/title/{слаг}/"),
        title=str(з.get("title") or ""),
        poster=str(з.get("poster") or ""),
        badge=str(з.get("kind") or ""),
        release_at=str(з.get("published_at") or ""),
        ratings=оценки,
        video_available=(д.get("playable") if "playable" in д else None),
        raw=з,
    )


#: Как получить набор записей коллекции. Каждая функция работает с готовыми
#: срезами снимка и не обходит каталог заново.
ВЫБОРКИ: dict[str, Callable[[Снимок, dict], list[dict]]] = {
    "recent": lambda с, ф: с.по_дате(),
    "recent_of_kind": lambda с, ф: с.по_виду(str(ф.get("kind") or "")),
    "top_rated": lambda с, ф: с.по_оценке(),
    # Clock year — never MAX(catalog year).
    "current_year": lambda с, ф: с.года(_clock_year()),
    "playable": lambda с, ф: с.играющие(),
    "genre": lambda с, ф: с.по_жанру(str(ф.get("genre") or "")),
    "new_releases_kind": lambda с, ф: с.новинки_релиза(str(ф.get("kind") or "")),
}


def _clock_year() -> int:
    import os
    raw = (os.environ.get("LORDS_CLOCK_ISO") or "").strip()
    if raw:
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).year
        except ValueError:
            pass
    return datetime.now(timezone.utc).year


def _спец(ключ: str, семейство: str, титул: str, описание: str, источник: str,
          фильтр: dict, сорт: dict, свежесть: str, путь: str,
          лимит: int = 12, причина: str = "") -> Спецификация:
    return Спецификация(
        collection_key=ключ, family=семейство, section_id=f"sec-{ключ}",
        title=титул, description=описание, source=источник,
        filter_spec=фильтр, sort_spec=сорт, freshness_rule=свежесть,
        card_limit=лимит, view_all_path=путь, canonical_path=путь,
        empty_policy=СКРЫТЬ, unavailable_reason=причина,
    )


def _общие(семейство: str, кино: str, сериал: str) -> list[Спецификация]:
    """Коллекции, которые опираются только на реально заполненные поля."""
    return [
        _спец("recently_added", семейство, "Недавно добавленные",
              "Записи в порядке появления в каталоге поставщика.",
              "catalog", {}, {"field": "published_at", "order": "desc"},
              "published_at", "/collection/recently_added/"),
        _спец("recently_added_movies", семейство, "Новые фильмы",
              "Фильмы в порядке появления в каталоге.",
              "catalog", {"kind": кино}, {"field": "published_at", "order": "desc"},
              "published_at", "/collection/recently_added_movies/"),
        _спец("new_episodes", семейство, "Новые эпизоды",
              "Сериалы в порядке появления в каталоге.",
              "catalog", {"kind": сериал}, {"field": "published_at", "order": "desc"},
              "published_at", "/collection/new_episodes/"),
        _спец("top_rated", семейство, "Высокие оценки",
              "Записи с подтверждённой оценкой источника, по убыванию.",
              "ratings", {"has_rating": True}, {"field": "rating", "order": "desc"},
              "rating", "/collection/top_rated/"),
        _спец("current_season", семейство, "Этого года",
              "Записи текущего календарного года.",
              "catalog", {"year": "current"}, {"field": "published_at", "order": "desc"},
              "year", "/collection/current_season/"),
        _спец("video_available", семейство, "С видео",
              "Записи, у которых поставщик подтвердил дорожку.",
              "catalog", {"playable": True}, {"field": "published_at", "order": "desc"},
              "published_at", "/collection/video_available/"),
    ]


#: Коллекции, объявленные, но не обеспеченные данными. Они не рисуются и не
#: наполняются похожими тайтлами: отсутствующий признак — это факт контура, а
#: не повод показать посетителю что-нибудь другое.
НЕТ_ДАННЫХ = {
    "ongoing": "у контура нет признака «сейчас выходит»",
    "today_schedule": "у контура нет дат выхода эпизодов",
    "popular_new_movies": "у контура нет показателя популярности",
    "popular_series": "у контура нет показателя популярности",
    "new_trailers": "у контура нет трейлеров",
    "announcements": "у контура нет анонсов",
    "news": "у контура нет новостной ленты",
    "actual": "у контура нет признака актуальности",
}


def _недоступные(семейство: str, ключи: tuple[str, ...]) -> list[Спецификация]:
    return [
        _спец(к, семейство, к.replace("_", " ").capitalize(),
              "Коллекция объявлена контрактом, но у контура нет данных для неё.",
              "unavailable", {}, {}, "", f"/collection/{к}/",
              причина=НЕТ_ДАННЫХ[к])
        for к in ключи
    ]


РЕЕСТР: dict[str, list[Спецификация]] = {
    "lords": _общие("lords", "Фильм", "Сериал"),
    "zona": (
        [
            _спец("recently_added", "zona", "Недавно добавленные",
                  "Записи в порядке появления в каталоге.",
                  "catalog", {}, {"field": "published_at", "order": "desc"},
                  "published_at", "/collection/recently_added/"),
            _спец("recently_added_movies", "zona", "Недавно добавленные фильмы",
                  "Фильмы в порядке появления в каталоге.",
                  "catalog", {"kind": "Фильм"}, {"field": "published_at", "order": "desc"},
                  "published_at", "/collection/recently_added_movies/"),
            _спец("new_movie_releases", "zona", "Премьеры фильмов",
                  "Фильмы с датой премьеры или годом текущего календарного года.",
                  "catalog", {"kind": "Фильм", "release_mode": "premiere"},
                  {"field": "premiere_date", "order": "desc"},
                  "premiere_date", "/collection/new_movie_releases/"),
            _спец("new_series_releases", "zona", "Новые сериалы",
                  "Сериалы текущего календарного года.",
                  "catalog", {"kind": "Сериал", "release_mode": "premiere"},
                  {"field": "premiere_date", "order": "desc"},
                  "premiere_date", "/collection/new_series_releases/"),
            _спец("new_episodes", "zona", "Новые эпизоды",
                  "Сериалы в порядке появления в каталоге.",
                  "catalog", {"kind": "Сериал"}, {"field": "published_at", "order": "desc"},
                  "published_at", "/collection/new_episodes/"),
            _спец("top_rated", "zona", "Высокие оценки",
                  "Записи с подтверждённой оценкой источника.",
                  "ratings", {"has_rating": True}, {"field": "rating", "order": "desc"},
                  "rating", "/collection/top_rated/"),
            _спец("current_season", "zona", "Этого года",
                  "Записи текущего календарного года.",
                  "catalog", {"year": "current"}, {"field": "published_at", "order": "desc"},
                  "year", "/collection/current_season/"),
            _спец("video_available", "zona", "С видео",
                  "Записи с подтверждённой playable-дорожкой.",
                  "catalog", {"playable": True}, {"field": "published_at", "order": "desc"},
                  "published_at", "/collection/video_available/"),
            _спец("genre_comedy", "zona", "Комедии",
                  "Комедии из каталога.",
                  "catalog", {"genre": "comedy"}, {"field": "published_at", "order": "desc"},
                  "genre", "/collection/genre_comedy/"),
            _спец("genre_drama", "zona", "Драмы",
                  "Драмы из каталога.",
                  "catalog", {"genre": "drama"}, {"field": "published_at", "order": "desc"},
                  "genre", "/collection/genre_drama/"),
            _спец("genre_thriller", "zona", "Триллеры",
                  "Триллеры из каталога.",
                  "catalog", {"genre": "triller"}, {"field": "published_at", "order": "desc"},
                  "genre", "/collection/genre_thriller/"),
            _спец("genre_animation", "zona", "Анимация",
                  "Анимация и мультфильмы.",
                  "catalog", {"kind": "Мультфильм"}, {"field": "published_at", "order": "desc"},
                  "published_at", "/collection/genre_animation/"),
        ]
        + _недоступные("zona", ("popular_new_movies", "popular_series", "new_trailers"))
    ),
    "animedia": _общие("animedia", "Фильм", "Аниме")
    + _недоступные("animedia", ("ongoing", "today_schedule")),
    "yummy": _общие("yummy", "Фильм", "Аниме")
    + _недоступные("yummy", ("actual", "news", "announcements")),
}


def спецификации(семейство: str) -> list[Спецификация]:
    return РЕЕСТР.get(семейство, [])


def спецификация(семейство: str, ключ: str) -> Спецификация | None:
    for с in спецификации(семейство):
        if с.collection_key == ключ:
            return с
    return None


def разрешить(ключ: str, снимок: Снимок, семейство: str, *,
              предел: int | None = None, страница: int = 1,
              на_странице: int = 60) -> Коллекция | None:
    """Единственная точка, которая превращает ключ коллекции в записи.

    Лента вызывает её с пределом, полная страница — со страницей. Отсюда и
    берётся совпадение: обе получают один и тот же порядок из одного снимка.
    """
    спец = спецификация(семейство, ключ)
    if спец is None:
        return None
    if not спец.доступна:
        набор: list[dict] = []
    else:
        имя_выборки = (
            "recent_of_kind" if спец.filter_spec.get("kind") and not спец.filter_spec.get("genre")
            and спец.filter_spec.get("release_mode") != "premiere"
            else
            "new_releases_kind" if спец.filter_spec.get("release_mode") == "premiere" else
            "top_rated" if спец.filter_spec.get("has_rating") else
            "current_year" if спец.filter_spec.get("year") in ("max", "current") else
            "playable" if спец.filter_spec.get("playable") else
            "genre" if спец.filter_spec.get("genre") else
            "recent")
        набор = ВЫБОРКИ[имя_выборки](снимок, спец.filter_spec)

    всего = len(набор)
    if предел is not None:
        кусок = набор[:предел]
        номер = 1
    else:
        номер = max(1, страница)
        кусок = набор[(номер - 1) * на_странице: номер * на_странице]

    return Коллекция(
        contract_version=ВЕРСИЯ_КОНТРАКТА,
        collection_key=спец.collection_key, family=спец.family,
        section_id=спец.section_id, title=спец.title,
        description=спец.description, source=спец.source,
        filter_spec=dict(спец.filter_spec), sort_spec=dict(спец.sort_spec),
        freshness_rule=спец.freshness_rule, card_limit=спец.card_limit,
        total=всего, items=[_карточка(снимок, з) for з in кусок],
        page=номер, view_all_path=спец.view_all_path,
        canonical_path=спец.canonical_path, generated_at=_сейчас(),
        data_revision=снимок.data_revision, empty_policy=спец.empty_policy,
    )
