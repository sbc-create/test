"""Синтетический каталог для fixture preview направления Lords.

Пока контракт CDNVideoHub и учётные данные не переданы, показывать нечего — но
проверять шаблон на пустом месте бессмысленно. Этот модуль даёт единственный
допустимый заменитель: полностью выдуманный каталог, который никогда не попадает
в production и помечен как тестовый в каждой записи, в HTML и в отчёте сборки.

Правила, которые здесь соблюдаются буквально:

* названия произведений, студий и подборок выдуманы; совпадение с существующими
  работами не подразумевается и не проверялось, потому что данные не выдаются за
  реальные;
* оценок, отзывов, правообладателей и дат реальных релизов здесь нет — их нельзя
  выдумать даже для витрины, поэтому соответствующих полей не существует вовсе;
* постеры — локально сгенерированные нейтральные SVG-заглушки, без единого
  внешнего запроса и без чужих изображений;
* каталог детерминирован: одинаковый вход даёт побайтно одинаковый выход, иначе
  повторная сборка не была бы проверяемой.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: Метка происхождения. Попадает в каждую запись, в HTML и в манифест сборки.
SOURCE = "fixture/test"

MOVIES = "movies"
SERIES = "series"
ANIMATION = "animation"
ANIME = "anime"
DORAMA = "dorama"

_ADJECTIVES = (
    "Тихий", "Северный", "Стеклянный", "Медный", "Поздний", "Бумажный",
    "Соляной", "Тёплый", "Дальний", "Пепельный", "Ржавый", "Лунный",
)
_NOUNS = (
    "перевал", "маяк", "циферблат", "паром", "чертёж", "переучёт",
    "сквозняк", "полустанок", "антракт", "обжиг", "невод", "разъезд",
)
_LATIN_LEFT = (
    "Quiet", "Northern", "Glass", "Copper", "Late", "Paper",
    "Salt", "Warm", "Distant", "Ashen", "Rust", "Lunar",
)
_LATIN_RIGHT = (
    "Pass", "Lighthouse", "Dial", "Ferry", "Blueprint", "Recount",
    "Draught", "Halt", "Interval", "Kiln", "Seine", "Siding",
)
_TRANSLIT = (
    "pereval", "mayak", "ciferblat", "parom", "chertyozh", "peruchyot",
    "skvoznyak", "polustanok", "antrakt", "obzhig", "nevod", "razyezd",
)
_ADJ_SLUG = (
    "tihiy", "severnyy", "steklyannyy", "mednyy", "pozdniy", "bumazhnyy",
    "solyanoy", "tyoplyy", "dalniy", "pepelnyy", "rzhavyy", "lunnyy",
)

_STUDIOS = (
    "Студия «Полутон»", "Кинолаборатория «Гряда»", "Мастерская «Оттиск»",
    "Объединение «Затвор»", "Ателье «Кромка»", "Цех «Литера»",
)

GENRES: tuple[tuple[str, str], ...] = (
    ("drama", "Драма"),
    ("detective", "Детектив"),
    ("adventure", "Приключения"),
    ("comedy", "Комедия"),
    ("thriller", "Триллер"),
    ("fantasy", "Фэнтези"),
    ("scifi", "Фантастика"),
    ("family", "Семейное"),
    ("historical", "Историческое"),
    ("mystery", "Мистика"),
)

COUNTRIES: tuple[tuple[str, str], ...] = (
    ("russia", "Россия"),
    ("france", "Франция"),
    ("japan", "Япония"),
    ("south-korea", "Южная Корея"),
    ("canada", "Канада"),
    ("poland", "Польша"),
)

YEARS: tuple[int, ...] = tuple(range(2016, 2026))

#: Сколько произведений каждого типа держит стенд. Числа подобраны так, чтобы
#: в каталоге была видна пагинация, а в каждом типе — больше одной страницы
#: фасетов.
TYPE_QUOTA: tuple[tuple[str, int], ...] = (
    (MOVIES, 26),
    (SERIES, 16),
    (ANIMATION, 8),
    (ANIME, 6),
    (DORAMA, 6),
)

AGE_RATINGS = ("6+", "12+", "16+", "18+")


@dataclass(frozen=True)
class Episode:
    number: int
    name: str
    runtime_min: int


@dataclass(frozen=True)
class Season:
    number: int
    episodes: tuple[Episode, ...]

    @property
    def runtime_min(self) -> int:
        return sum(e.runtime_min for e in self.episodes)


@dataclass(frozen=True)
class Title:
    slug: str
    name: str
    original_name: str
    content_type: str
    year: int
    country_slug: str
    country: str
    genre_slugs: tuple[str, ...]
    genres: tuple[str, ...]
    studio: str
    runtime_min: int
    age_rating: str
    summary: str
    seasons: tuple[Season, ...] = ()
    #: Происхождение. Единственное допустимое значение в этом модуле.
    source: str = SOURCE

    @property
    def fixture(self) -> bool:
        return True

    @property
    def episodic(self) -> bool:
        return bool(self.seasons)

    @property
    def episode_count(self) -> int:
        return sum(len(s.episodes) for s in self.seasons)

    @property
    def path(self) -> str:
        return f"/title/{self.slug}/"

    @property
    def poster_path(self) -> str:
        """Локальный адрес заглушки. Он же маршрут генерируемого SVG."""
        return f"/assets/posters/{self.slug}.svg"

    @property
    def poster_src(self) -> str:
        """Что показать в разметке. У фикстуры своего постера нет — только слот.

        Разделение нужно живому каталогу: там `poster_src` указывает на картинку
        источника, а `poster_path` остаётся локальным маршрутом. Пока это было
        одним свойством, внешние адреса становились страницами сайта.
        """
        return self.poster_path

    def as_dict(self) -> dict:
        return {
            "slug": self.slug,
            "name": self.name,
            "original_name": self.original_name,
            "content_type": self.content_type,
            "year": self.year,
            "country": self.country,
            "country_slug": self.country_slug,
            "genres": list(self.genres),
            "genre_slugs": list(self.genre_slugs),
            "studio": self.studio,
            "runtime_min": self.runtime_min,
            "age_rating": self.age_rating,
            "seasons": [
                {"number": s.number, "episodes": [
                    {"number": e.number, "name": e.name, "runtime_min": e.runtime_min}
                    for e in s.episodes
                ]}
                for s in self.seasons
            ],
            "source": self.source,
            "fixture": True,
        }


@dataclass(frozen=True)
class Collection:
    slug: str
    name: str
    summary: str
    title_slugs: tuple[str, ...]
    source: str = SOURCE

    @property
    def path(self) -> str:
        return f"/collections/{self.slug}/"


def _summary(name: str, kind: str, country: str, year: int) -> str:
    """Короткое описание. Текст собственный и ни на что не ссылается.

    Описание намеренно говорит о форме, а не о сюжете: сюжета у выдуманной
    записи нет, а пересказывать несуществующее — тот же вымысел, только длиннее.
    """
    forms = {
        MOVIES: "полнометражная работа",
        SERIES: "многосерийная работа",
        ANIMATION: "анимационная работа",
        ANIME: "анимационная работа японского производства",
        DORAMA: "многосерийная работа азиатского производства",
    }
    return (
        f"«{name}» — {forms[kind]} тестового каталога, {country}, {year} год. "
        "Запись создана для проверки шаблона: она не описывает существующее "
        "произведение и не содержит оценок, отзывов и сведений о правах."
    )


def _episode_name(index: int) -> str:
    return f"Серия {index}"


def _seasons_for(kind: str, index: int) -> tuple[Season, ...]:
    episodic = (
        kind in (SERIES, DORAMA, ANIME)
        # Мультипликация бывает и полнометражной, и многосерийной: чередование
        # даёт стенду обе формы в одном разделе.
        or (kind == ANIMATION and index % 2 == 0)
    )
    if not episodic:
        return ()
    count = 1 + (index % 3) if kind in (SERIES, ANIME) else 1
    seasons = []
    for season_no in range(1, count + 1):
        per = 4 + ((index + season_no) % 5)
        episodes = tuple(
            Episode(number=n, name=_episode_name(n), runtime_min=38 + ((index + n) % 12))
            for n in range(1, per + 1)
        )
        seasons.append(Season(number=season_no, episodes=episodes))
    return tuple(seasons)


def _make_title(kind: str, index: int, ordinal: int) -> Title:
    a = ordinal % len(_ADJECTIVES)
    n = (ordinal * 5 + index) % len(_NOUNS)
    name = f"{_ADJECTIVES[a]} {_NOUNS[n]}"
    slug = f"{_ADJ_SLUG[a]}-{_TRANSLIT[n]}-{2016 + (ordinal % 10)}"
    original = f"{_LATIN_LEFT[a]} {_LATIN_RIGHT[n]}"
    year = YEARS[ordinal % len(YEARS)]
    country_slug, country = COUNTRIES[(ordinal * 3 + index) % len(COUNTRIES)]
    if kind == ANIME:
        country_slug, country = "japan", "Япония"
    if kind == DORAMA:
        country_slug, country = COUNTRIES[3 - (ordinal % 2)]
    g1 = GENRES[(ordinal * 7 + index) % len(GENRES)]
    g2 = GENRES[(ordinal * 3 + 4) % len(GENRES)]
    genres = (g1,) if g1[0] == g2[0] else (g1, g2)
    seasons = _seasons_for(kind, ordinal)
    runtime = sum(s.runtime_min for s in seasons) if seasons else 82 + (ordinal % 45)
    return Title(
        slug=slug,
        name=name,
        original_name=original,
        content_type=kind,
        year=year,
        country_slug=country_slug,
        country=country,
        genre_slugs=tuple(g[0] for g in genres),
        genres=tuple(g[1] for g in genres),
        studio=_STUDIOS[(ordinal + index) % len(_STUDIOS)],
        runtime_min=runtime,
        age_rating=AGE_RATINGS[(ordinal + index) % len(AGE_RATINGS)],
        summary=_summary(name, kind, country, year),
        seasons=seasons,
    )


_COLLECTION_SPECS: tuple[tuple[str, str, str], ...] = (
    ("long-evenings", "Длинные вечера",
     "Список для тех случаев, когда время не ограничено: сюда попадают работы "
     "стенда с наибольшей продолжительностью."),
    ("first-season", "Начать сериал с первого сезона",
     "Многосерийные записи стенда, у которых сезон ровно один: удобный случай "
     "проверить, как страница ведёт себя без выбора сезона."),
    ("short-form", "Короткий метр",
     "Записи стенда с самой малой продолжительностью — проверка того, что "
     "карточка не рассыпается на коротких значениях."),
    ("northern-set", "Северный набор",
     "Произвольная тематическая группировка стенда: она существует, чтобы "
     "показать подборку, собранную не по формальному признаку каталога."),
)


@dataclass(frozen=True)
class Catalog:
    titles: tuple[Title, ...]
    collections: tuple[Collection, ...]
    _by_slug: dict = field(default_factory=dict, repr=False, compare=False)

    def by_slug(self, slug: str) -> Title | None:
        return self._by_slug.get(slug)

    def of_type(self, kind: str) -> tuple[Title, ...]:
        return tuple(t for t in self.titles if t.content_type == kind)

    def of_types(self, kinds) -> tuple[Title, ...]:
        allowed = set(kinds)
        return tuple(t for t in self.titles if t.content_type in allowed)

    def collection(self, slug: str) -> Collection | None:
        for item in self.collections:
            if item.slug == slug:
                return item
        return None

    def genres(self, kinds=None) -> tuple[tuple[str, str, int], ...]:
        """Жанры, за которыми стоит хотя бы одно произведение доступных типов."""
        pool = self.of_types(kinds) if kinds is not None else self.titles
        counts: dict[str, int] = {}
        for title in pool:
            for slug in title.genre_slugs:
                counts[slug] = counts.get(slug, 0) + 1
        return tuple(
            (slug, label, counts[slug]) for slug, label in GENRES if counts.get(slug)
        )

    def years(self, kinds=None) -> tuple[tuple[int, int], ...]:
        pool = self.of_types(kinds) if kinds is not None else self.titles
        counts: dict[int, int] = {}
        for title in pool:
            counts[title.year] = counts.get(title.year, 0) + 1
        return tuple((year, counts[year]) for year in sorted(counts, reverse=True))

    def countries(self, kinds=None) -> tuple[tuple[str, str, int], ...]:
        pool = self.of_types(kinds) if kinds is not None else self.titles
        counts: dict[str, int] = {}
        for title in pool:
            counts[title.country_slug] = counts.get(title.country_slug, 0) + 1
        return tuple(
            (slug, label, counts[slug]) for slug, label in COUNTRIES if counts.get(slug)
        )

    def capabilities(self) -> set[str]:
        """Типы, которые стенд действительно может показать.

        Значение подставляется вместо ответа API: состояние `enabled` получает
        только тип, за которым в каталоге есть записи. Это ровно то же правило,
        по которому будет работать настоящий источник.
        """
        present = {t.content_type for t in self.titles}
        if self.collections:
            present.add("collections")
        return present

    def as_dict(self) -> dict:
        return {
            "source": SOURCE,
            "fixture": True,
            "counts": {kind: len(self.of_type(kind)) for kind, _ in TYPE_QUOTA},
            "collections": len(self.collections),
            "titles": [t.as_dict() for t in self.titles],
        }


def build_catalog() -> Catalog:
    """Детерминированный каталог стенда. Ни сети, ни случайности, ни времени."""
    titles: list[Title] = []
    for index, (kind, quota) in enumerate(TYPE_QUOTA):
        for ordinal in range(quota):
            titles.append(_make_title(kind, index, ordinal))

    # Слаги обязаны быть уникальными: адрес — это первичный ключ сайта.
    seen: dict[str, int] = {}
    unique: list[Title] = []
    from dataclasses import replace
    for title in titles:
        count = seen.get(title.slug, 0)
        seen[title.slug] = count + 1
        if count:
            title = replace(title, slug=f"{title.slug}-{count + 1}")
        unique.append(title)

    by_length = sorted(unique, key=lambda t: (-t.runtime_min, t.slug))
    single_season = [t for t in unique if len(t.seasons) == 1]
    by_short = sorted(unique, key=lambda t: (t.runtime_min, t.slug))
    northern = [t for t in unique if t.name.startswith(("Северный", "Пепельный", "Соляной"))]

    picks = (
        tuple(t.slug for t in by_length[:12]),
        tuple(t.slug for t in single_season[:12]),
        tuple(t.slug for t in by_short[:12]),
        tuple(t.slug for t in northern[:12]) or tuple(t.slug for t in unique[:6]),
    )
    collections = tuple(
        Collection(slug=slug, name=name, summary=summary, title_slugs=slugs)
        for (slug, name, summary), slugs in zip(_COLLECTION_SPECS, picks, strict=True)
    )

    return Catalog(
        titles=tuple(unique),
        collections=collections,
        _by_slug={t.slug: t for t in unique},
    )
