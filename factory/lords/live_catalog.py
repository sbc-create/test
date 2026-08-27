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
    tags = [t.strip() for t in (entry.get("tags") or []) if isinstance(t, str) and t.strip()]
    year = entry.get("year")

    return LiveTitle(
        slug=slug,
        name=name,
        # Списочный ответ не содержит оригинального названия, страны, студии,
        # хронометража, возрастного ограничения и описания. Пустая строка здесь
        # — это «источник не сказал», а не «неизвестно».
        original_name="",
        content_type=_content_type(entry.get("type"), entry.get("is_series")),
        year=int(year) if isinstance(year, int) else 0,
        country_slug="",
        country="",
        genre_slugs=tuple(slugify(t) or "zhanr" for t in tags),
        genres=tuple(tags),
        studio="",
        runtime_min=0,
        age_rating="",
        summary="",
        seasons=(),
        external_id=external_id,
        poster_url=(entry.get("poster_url") or None),
        kinopoisk_rating=_rating(entry.get("kinopoisk_rating")),
        imdb_rating=_rating(entry.get("imdb_rating")),
        licensed=entry.get("licensed") if isinstance(entry.get("licensed"), bool) else None,
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
