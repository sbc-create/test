# Контракт лент и коллекций контура ANIMEDIA.
#
# Копия нейтральной логики, перенесённая в собственный пакет: импорт из пакета
# с чужим именем был cross-tenant зависимостью, и запрет на него — часть
# контракта изоляции (config/animedia/TENANT_SCOPE.yaml).
#
# Логика не изменена: побайтовое равенство рендера проверяется отдельным шагом.
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

# Рядом с выкаченным артефактом пакета нет: deploy кладёт модули спутниками.
# Поэтому импорт двойной — сначала пакетом, затем плоским соседом.
try:
    from . import chronology as хронология
except ImportError:  # pragma: no cover — путь выкладки
    import chronology as хронология
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
        # Порядок «сначала новое» считается один раз и по правилам хронологии
        # контура: момент времени, факт раньше оценки, канонический ключ.
        # Прежде здесь сравнивались строки, и на этом снимке это давало
        # произвол: 4003 записи из 7425 несут одну отметку массовой загрузки,
        # а сортировка строк среди равных оставляла порядок файла.
        self._по_дате = хронология.по_добавлению(items)
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
        """Playable titles ordered by best source rating, then published_at.

        Must diverge from ``по_дате`` / recently_added: when most titles are
        playable, date order alone produced exact first-12 duplicates.
        """
        готово = []
        for з in self._по_дате:
            д = self.подробности.get(str(з.get("slug") or "")) or {}
            if д.get("playable") is True:
                готово.append(з)
        # Оценка решает первой, дальше — общая хронология контура: она даёт
        # устойчивый порядок при равных оценках и одинаковых датах.
        готово.sort(key=lambda з: (self._оценка(з), хронология.ключ_порядка(з)),
                    reverse=True)
        return готово

    def с_эпизодами(self) -> list[dict]:
        """Тайтлы, у которых в sidecar есть сезоны с доступными сериями.

        Это не episode.published_at: отдельной даты эпизода в снимке нет.
        Используем только как честный срез «сериалы с сериями», не как
        подмену «недавно добавленных».
        """
        готово = []
        for з in self._по_дате:
            д = self.подробности.get(str(з.get("slug") or "")) or {}
            сезоны = д.get("seasons") or []
            if not сезоны:
                continue
            if any(int(с.get("avail") or 0) > 0 for с in сезоны if isinstance(с, dict)):
                готово.append(з)
        return готово

    def по_типу(self, тип: str) -> list[dict]:
        тип = (тип or "").strip().lower()
        if not тип:
            return []
        готово = []
        for з in self._по_дате:
            д = self.подробности.get(str(з.get("slug") or "")) or {}
            if str(д.get("type") or "").strip().lower() == тип:
                готово.append(з)
        return готово

    def по_стране(self, страна: str) -> list[dict]:
        страна = (страна or "").strip().lower()
        if not страна:
            return []
        готово = []
        for з in self._по_дате:
            д = self.подробности.get(str(з.get("slug") or "")) or {}
            страны = [str(с).strip().lower() for с in (д.get("countries") or [])]
            if страна in страны:
                готово.append(з)
        return готово

    def по_жанру(self, жанр: str) -> list[dict]:
        жанр = (жанр or "").strip().lower()
        if not жанр:
            return []
        готово = []
        for з in self._по_дате:
            д = self.подробности.get(str(з.get("slug") or "")) or {}
            жанры = [str(г).strip().lower() for г in (д.get("genres") or [])]
            if any(жанр in г for г in жанры):
                готово.append(з)
        return готово

    def короткие_сериалы(self, максимум: int = 12) -> list[dict]:
        готово = []
        for з in self._по_дате:
            д = self.подробности.get(str(з.get("slug") or "")) or {}
            if str(д.get("type") or "").strip().lower() == "movie":
                continue
            сезоны = [с for с in (д.get("seasons") or []) if isinstance(с, dict)]
            if not сезоны:
                continue
            eps = max(int(с.get("eps") or 0) for с in сезоны)
            if 0 < eps <= максимум:
                готово.append(з)
        return готово

    def классика(self, до_года: int = 2005) -> list[dict]:
        return [з for з in self._по_дате
                if isinstance(з.get("year"), int) and з["year"] <= до_года]

    def года_равно(self, год: int) -> list[dict]:
        return [з for з in self._по_дате if з.get("year") == год]

    def эпизод_события(self) -> list[dict]:
        """Настоящие episode events, упорядоченные по дате появления СЕРИИ.

        Год произведения сюда не подставляется: лента новых серий, собранная по
        году тайтла, показывает не новые серии, а старые произведения. Порядок
        задаёт самая свежая дата серии у каждого тайтла; при равных датах
        действует общий устойчивый ключ хронологии контура.

        Без дат у серий лента пуста — это честное состояние, а не повод
        подменить её датой добавления тайтла.
        """
        собрано: list[tuple[dict, str]] = []
        for з in self._по_дате:
            д = self.подробности.get(str(з.get("slug") or "")) or {}
            свежайшая = None
            for с in (д.get("seasons") or []):
                if not isinstance(с, dict):
                    continue
                for эп in (с.get("episodes") or []):
                    if not isinstance(эп, dict):
                        continue
                    дата = эп.get("published_at") or эп.get("available_at")
                    момент = хронология.разобрать_момент(дата)
                    if момент is None:
                        continue
                    if свежайшая is None or момент > свежайшая:
                        свежайшая = момент
            if свежайшая is not None:
                собрано.append((з, свежайшая.isoformat()))
        упорядочено = хронология.по_эпизодам(
            [{**з, "episode_published_at": дата} for з, дата in собрано])
        # Наружу отдаются исходные записи: добавленное поле — только ключ
        # сортировки и в карточку попадать не должно.
        по_ключу = {хронология.канонический_идентификатор(з): з for з, _ in собрано}
        return [по_ключу[хронология.канонический_идентификатор(з)] for з in упорядочено]


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
    "current_year": lambda с, ф: (с.года(с.максимальный_год)
                                  if с.максимальный_год else []),
    "playable": lambda с, ф: с.играющие(),
    "with_episodes": lambda с, ф: с.с_эпизодами(),
    "episode_events": lambda с, ф: с.эпизод_события(),
    "by_type": lambda с, ф: с.по_типу(str(ф.get("type") or "")),
    "by_country": lambda с, ф: с.по_стране(str(ф.get("country") or "")),
    "by_genre": lambda с, ф: с.по_жанру(str(ф.get("genre") or "")),
    "short_series": lambda с, ф: с.короткие_сериалы(int(ф.get("max_eps") or 12)),
    "classic": lambda с, ф: с.классика(int(ф.get("until_year") or 2005)),
    "exact_year": lambda с, ф: с.года_равно(int(ф.get("year") or 0)),
}


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
              "Свежие поступления в каталог аниме.",
              "catalog", {}, {"field": "published_at", "order": "desc"},
              "published_at", "/collection/recently_added/"),
        _спец("recently_added_movies", семейство, "Новые фильмы",
              "Фильмы в порядке появления в каталоге.",
              "catalog", {"kind": кино}, {"field": "published_at", "order": "desc"},
              "published_at", "/collection/recently_added_movies/"),
        _спец("new_episodes", семейство, "Новые эпизоды",
              "Недавно вышедшие серии аниме.",
              "episodes", {"episode_events": True},
              {"field": "episode_published_at", "order": "desc"},
              "episode_published_at", "/collection/new_episodes/"),
        _спец("top_rated", семейство, "Высокие оценки",
              "Записи с подтверждённой оценкой источника, по убыванию.",
              "ratings", {"has_rating": True}, {"field": "rating", "order": "desc"},
              "rating", "/collection/top_rated/"),
        _спец("current_season", семейство, "Этого года",
              "Записи самого свежего года, представленного в каталоге.",
              "catalog", {"year": "max"}, {"field": "published_at", "order": "desc"},
              "year", "/collection/current_season/"),
        _спец("video_available", семейство, "С видео",
              "Тайтлы, которые можно смотреть прямо сейчас.",
              "catalog", {"playable": True}, {"field": "rating", "order": "desc"},
              "rating", "/collection/video_available/"),
    ]


def _аниме_подборки(семейство: str = "animedia") -> list[Спецификация]:
    """Независимые пользовательские подборки Animedia — без fallback на catalog[:N]."""
    return [
        _спец("anime_movies", семейство, "Аниме-фильмы",
              "Полнометражные аниме-фильмы.",
              "details", {"type": "movie"}, {"field": "published_at", "order": "desc"},
              "type", "/collection/anime_movies/"),
        _спец("donghua", семейство, "Дунхуа",
              "Произведения с подтверждённой страной Китай.",
              "details", {"country": "Китай"}, {"field": "published_at", "order": "desc"},
              "country", "/collection/donghua/"),
        _спец("short_series", семейство, "Короткие сериалы",
              "Сериалы до 12 серий включительно.",
              "details", {"max_eps": 12}, {"field": "published_at", "order": "desc"},
              "max_eps", "/collection/short_series/"),
        _спец("classic", семейство, "Классика",
              "Аниме до 2005 года включительно.",
              "catalog", {"until_year": 2005}, {"field": "year", "order": "desc"},
              "year", "/collection/classic/"),
        _спец("action", семейство, "Экшен",
              "Тайтлы с жанром «боевик».",
              "details", {"genre": "боевик"}, {"field": "published_at", "order": "desc"},
              "genre", "/collection/action/"),
        _спец("romance", семейство, "Романтика",
              "Тайтлы с жанром «романтика».",
              "details", {"genre": "романтика"}, {"field": "published_at", "order": "desc"},
              "genre", "/collection/romance/"),
        _спец("family", семейство, "Семейный просмотр",
              "Тайтлы с жанрами «семейный» или «детский».",
              "details", {"genre": "семей"}, {"field": "published_at", "order": "desc"},
              "genre", "/collection/family/"),
        _спец("series_with_episodes", семейство, "Сериалы с сериями",
              "Сериалы с доступными сериями для просмотра.",
              "details", {"with_episodes": True},
              {"field": "published_at", "order": "desc"},
              "seasons", "/collection/series_with_episodes/"),
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
    "zona": _общие("zona", "Фильм", "Сериал")
    + _недоступные("zona", ("popular_new_movies", "popular_series", "new_trailers")),
    "animedia": _общие("animedia", "Фильм", "Аниме")
    + _аниме_подборки("animedia")
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
            "episode_events" if спец.filter_spec.get("episode_events") else
            "with_episodes" if спец.filter_spec.get("with_episodes") else
            "by_type" if спец.filter_spec.get("type") else
            "by_country" if спец.filter_spec.get("country") else
            "by_genre" if спец.filter_spec.get("genre") else
            "short_series" if спец.filter_spec.get("max_eps") else
            "classic" if спец.filter_spec.get("until_year") else
            "exact_year" if isinstance(спец.filter_spec.get("year"), int) else
            "recent_of_kind" if спец.filter_spec.get("kind") else
            "top_rated" if спец.filter_spec.get("has_rating") else
            "current_year" if спец.filter_spec.get("year") == "max" else
            "playable" if спец.filter_spec.get("playable") else
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
