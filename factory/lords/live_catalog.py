"""Живой каталог CDNVideoHub в виде `Catalog`, пригодного для `render_site`.

Зачем этот модуль. У Lords есть полный рендерер: главная с секциями, каталог с
пагинацией, жанры, годы, страны, подборки, расписание, поиск и страницы
тайтлов. Он принимает любой `Catalog`, но собрать `Catalog` можно было только
из фикстур. Живые записи шли мимо него — их выкладывал черновой сборщик, и на
публичных доменах стояла одна страница со всем каталогом сразу: 4316 карточек,
988 КБ на запрос, без пагинации, без навигации и с сырым `cartoon` в типе.

Модуль — мост между источником и рендерером. Правило у него одно: ничего не
додумывать. Список CDNVideoHub отдаёт имя, тип, год, постер, теги и две оценки;
страны, студии, хронометража, возраста и описания в нём нет. Эти поля остаются
пустыми, и разметка обязана их скрыть, а не показать «Фильм · 2023 · » с
повисшим разделителем.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from factory.lords import fixtures as fx

#: Происхождение записей этого каталога. Отличается от `fx.SOURCE` намеренно:
#: по нему видно, что каталог живой, а не синтетический.
SOURCE = "cdnvideohub-live"

#: Тип источника → тип рендерера. Только подтверждённые значения: то, чего в
#: карте нет, разрешается флагом `is_series`, а не догадкой по строке.
TYPE_MAP: dict[str, str] = {
    "movie": fx.MOVIES,
    "film": fx.MOVIES,
    "tv": fx.SERIES,
    "series": fx.SERIES,
    "show": fx.SERIES,
    "cartoon": fx.ANIMATION,
    "animation": fx.ANIMATION,
    "animated_series": fx.ANIMATION,
    "anime": fx.ANIME,
    "dorama": fx.DORAMA,
    "drama": fx.DORAMA,
}

_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "c",
    "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e",
    "ю": "yu", "я": "ya",
}


def slugify(value: str) -> str:
    """Адрес из названия. Пусто на входе — пусто на выходе, без выдумки."""
    lowered = (value or "").strip().lower()
    out: list[str] = []
    for char in lowered:
        if char in _TRANSLIT:
            out.append(_TRANSLIT[char])
        elif char.isalnum() and char.isascii():
            out.append(char)
        elif unicodedata.category(char).startswith("L") or unicodedata.category(char) == "Nd":
            # Незнакомая письменность: пропускаем символ, а не весь тайтл.
            continue
        else:
            out.append("-")
    slug = re.sub(r"-{2,}", "-", "".join(out)).strip("-")
    return slug[:80]


#: Возрастные отметки, которые источник кладёт в общий список тегов.
#: Диапазон широкий: числовые («16», «13+»), индийские («U/A 16+», «A», «AA»),
#: австралийские («MA 15+»), британские («12A»), американские («R», «PG-13»)
#: и явное отсутствие оценки («NR», «Not Yet Rated»).
_AGE_TAG = re.compile(
    r"^(?:\d{1,2}\+?|\d{1,2}A|U/A\s*\d{1,2}\+?|MA\s*\d{1,2}\+?"
    r"|NR|Not\s+Yet\s+Rated|R|G|PG(?:-13)?|A|AA|AL|TV-[A-Z0-9]+)$",
    re.IGNORECASE,
)

#: Пометки формы. Источник знает о типе больше, чем говорит поле `type`:
#: мультфильмы и аниме приходят как `movie`/`tv` и различаются только тегом.
_FORMAT_TAGS: dict[str, str] = {
    "cartoon": fx.ANIMATION,
    "animation": fx.ANIMATION,
    "anime": fx.ANIME,
    "ona": fx.ANIME,
    "ova": fx.ANIME,
    "dorama": fx.DORAMA,
}

#: Суффикс пользовательских дескрипторов MyDramaList. Посетителю он не нужен.
_VOTE_SUFFIX = re.compile(r"\s*\(Vote tags\)\s*$", re.IGNORECASE)


def classify_tags(tags) -> tuple[str, str | None, tuple[str, ...]]:
    """Разбирает список тегов на возраст, пометку формы и собственно теги.

    Возвращает `(age_rating, format_type, tags)`. Пустая строка и `None` —
    это «источник не сказал», а не «неизвестно»: показывать такое поле не нужно.
    """
    age = ""
    format_type: str | None = None
    rest: list[str] = []
    for raw in tags or []:
        tag = str(raw).strip()
        if not tag:
            continue
        if not age and _AGE_TAG.match(tag):
            age = tag
            continue
        if _AGE_TAG.match(tag):
            # Вторая возрастная отметка ничего не добавляет и точно не жанр.
            continue
        lowered = tag.lower()
        if lowered in _FORMAT_TAGS:
            format_type = format_type or _FORMAT_TAGS[lowered]
            continue
        cleaned = _VOTE_SUFFIX.sub("", tag).strip()
        if cleaned:
            rest.append(cleaned)
    return age, format_type, tuple(rest)


@dataclass(frozen=True)
class LiveTitle:
    """Тайтл живого каталога.

    Повторяет набор полей `fx.Title`, потому что рендерер обращается именно к
    ним, и добавляет то, чего у фикстуры быть не может: подтверждённые оценки и
    настоящий постер источника. `fixture` здесь `False` — на этом строится
    отличие живой карточки от синтетической в разметке.
    """

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
    seasons: tuple = ()
    source: str = SOURCE
    external_id: str = ""
    poster_url: str | None = None
    kinopoisk_rating: float | None = None
    imdb_rating: float | None = None
    licensed: bool | None = None
    #: Пришло из detail. Списочный ответ этого не даёт.
    directors: tuple[str, ...] = ()
    actors: tuple[str, ...] = ()
    premiere_date: str | None = None
    seasons_count: int = 0
    voices: tuple[str, ...] = ()
    created_at: str | None = None
    updated_at: str | None = None
    playback: dict | None = None

    @property
    def fixture(self) -> bool:
        return False

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
        """Локальный маршрут заглушки — всегда наш, никогда чужой адрес."""
        return f"/assets/posters/{self.slug}.svg"

    @property
    def poster_src(self) -> str:
        """Картинка источника, если она есть; иначе слот, а не битое изображение."""
        return self.poster_url or self.poster_path

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
            "seasons": [],
            "source": self.source,
            "fixture": False,
            "external_id": self.external_id,
            "kinopoisk_rating": self.kinopoisk_rating,
            "imdb_rating": self.imdb_rating,
        }


def _content_type(raw_type: str | None, is_series: bool | None) -> str:
    key = (raw_type or "").strip().lower()
    if key in TYPE_MAP:
        return TYPE_MAP[key]
    # Строку типа источник может завести новую в любой день; `is_series` —
    # булев факт, и опираться на него честнее, чем угадывать по незнакомому слову.
    if is_series is True:
        return fx.SERIES
    return fx.MOVIES


def _rating(value) -> float | None:
    """Оценка или ничего. Ноль — это оценка, а не отсутствие оценки."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if 0.0 <= number <= 10.0 else None


def title_from_item(entry: dict) -> LiveTitle | None:
    """Одна запись источника. `None`, если её нельзя адресовать."""
    external_id = str(entry.get("external_id") or "").strip()
    name = str(entry.get("name") or "").strip()
    if not external_id or not name:
        return None

    slug = slugify(name) or slugify(external_id) or external_id.lower()
    # `tags` источника — не список жанров: там вперемешку возрастные отметки,
    # пометки формы и пользовательские дескрипторы. Разбираем, а не показываем.
    age_rating, format_type, tags = classify_tags(entry.get("tags"))
    year = entry.get("year")

    # Ниже — поля, которых в списочном ответе нет: они появляются после
    # обогащения из detail. Пока обогащение не дошло до записи, поля пустые, и
    # разметка их скрывает — это честнее, чем «неизвестно» в каждой строке.
    countries = [c for c in (entry.get("countries") or []) if isinstance(c, str) and c.strip()]
    detail_genres = [g for g in (entry.get("genres") or []) if isinstance(g, str) and g.strip()]
    crew = entry.get("crew") or []
    directors = tuple(
        str(p.get("person_name")).strip() for p in crew
        if isinstance(p, dict) and p.get("role") == "director" and p.get("person_name")
    )
    actors = tuple(
        str(p.get("person_name")).strip() for p in crew
        if isinstance(p, dict) and p.get("role") == "actor" and p.get("person_name")
    )
    duration = entry.get("duration")
    voices = tuple(
        str(v).strip() for v in (entry.get("available_voices") or []) if str(v).strip()
    )

    return LiveTitle(
        slug=slug,
        name=name,
        # Списочный ответ не содержит оригинального названия, страны, студии,
        # хронометража, возрастного ограничения и описания. Пустая строка здесь
        # — это «источник не сказал», а не «неизвестно».
        original_name=str(entry.get("original_name") or "").strip(),
        # Пометка формы точнее поля `type`: мультфильмы и аниме приходят как
        # movie/tv и отличаются только тегом.
        content_type=format_type or _content_type(entry.get("type"), entry.get("is_series")),
        year=int(year) if isinstance(year, int) else 0,
        country_slug=slugify(countries[0]) if countries else "",
        country=", ".join(countries),
        # Настоящие жанры из detail вытесняют теги: теги описывают запись,
        # но жанрами не являются — среди них лежат и возрастные отметки.
        genre_slugs=tuple(slugify(g) or "tag" for g in (detail_genres or tags)),
        genres=tuple(detail_genres or tags),
        studio="",
        runtime_min=int(duration) if isinstance(duration, int) and duration > 0 else 0,
        age_rating=age_rating,
        summary=str(entry.get("description") or "").strip(),
        seasons=(),
        external_id=external_id,
        poster_url=(entry.get("poster_url") or None),
        kinopoisk_rating=_rating(entry.get("kinopoisk_rating")),
        imdb_rating=_rating(entry.get("imdb_rating")),
        licensed=entry.get("licensed") if isinstance(entry.get("licensed"), bool) else None,
        directors=directors,
        actors=actors,
        premiere_date=str(entry.get("premiere_date") or "").strip() or None,
        seasons_count=int(entry.get("seasons_count") or 0),
        voices=voices,
        created_at=entry.get("created_at"),
        updated_at=entry.get("updated_at"),
        playback=entry.get("playback"),
    )


def catalog_from_live(items, collections=()) -> fx.Catalog:
    """Каталог из записей источника.

    Непригодная запись пропускается по одной, а не роняет весь каталог: витрина
    без одного тайтла лучше витрины без всех.
    """
    titles: list[LiveTitle] = []
    seen: dict[str, int] = {}
    for entry in items or []:
        title = title_from_item(entry)
        if title is None:
            continue
        # Слаг — первичный ключ адреса. Совпадение имён встречается, и второй
        # тайтл обязан получить собственный адрес, а не затереть первый.
        count = seen.get(title.slug, 0)
        seen[title.slug] = count + 1
        if count:
            from dataclasses import replace
            title = replace(title, slug=f"{title.slug}-{count + 1}")
        titles.append(title)

    by_slug = {t.slug: t for t in titles}
    return fx.Catalog(titles=tuple(titles), collections=tuple(collections), _by_slug=by_slug)
