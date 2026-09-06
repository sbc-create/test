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

from dataclasses import dataclass, replace, field
from datetime import datetime, timedelta, timezone

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
    #: Длительность в минутах или None, если источник её не передал. Ноль
    #: здесь не «пусто», а утверждение «серия идёт ноль минут» — утверждение
    #: ложное, и печаталось оно на боевых витринах у каждой серии.
    runtime_min: int | None = None


@dataclass(frozen=True)
class Season:
    number: int
    episodes: tuple[Episode, ...]

    @property
    def runtime_min(self) -> int | None:
        """Суммарная длительность сезона или None, если ничего не известно.

        Сумма неизвестных величин — не ноль. Складывается только известное;
        если известного нет вовсе, сезон честно не имеет длительности.
        """
        known = [e.runtime_min for e in self.episodes if e.runtime_min]
        return sum(known) if known else None


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
    #: Момент попадания записи в каталог. Проставляется сборкой каталога, а не
    #: здесь: он обязан быть детерминированным и разным у разных записей.
    #:
    #: Поле не украшение. Полка «недавно добавленные» отбирает по нему, и пока
    #: его не было, полка выходила пустой, карусель не рендерилась, и весь
    #: браузерный набор о ней ничего не проверял, оставаясь зелёным.
    created_at: str | None = None
    #: Подтверждено ли воспроизведение. `True` — поток проверен, `False` —
    #: проверен и не работает, `None` — не проверялся вовсе.
    #:
    #: Ранжировщик пускает в полки только подтверждённые: показывать в карусели
    #: запись, которая не откроется, значит обманывать зрителя. Пока поля не
    #: было, ни одна фикстурная запись не проходила допуск, и полка выходила
    #: пустой при любом наборе данных.
    playable: bool | None = None
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


#: Хвосты названий. Синтетические, как и всё в этом модуле; их работа —
#: растянуть длину имён до наблюдаемого в боевом каталоге диапазона, а не
#: изобразить настоящие произведения.
_SUBTITLES = (
    "Возвращение к началу",
    "Хроника долгого лета",
    "История одной переправы",
    "Между двух берегов",
    "Последняя ночь навигации",
)


def _make_title(kind: str, index: int, ordinal: int) -> Title:
    a = ordinal % len(_ADJECTIVES)
    n = (ordinal * 5 + index) % len(_NOUNS)
    name = f"{_ADJECTIVES[a]} {_NOUNS[n]}"
    # Каждой третьей записи достаётся подзаголовок. Это не украшение выдуманным
    # содержанием, а покрытие длины: у имён из двух слов потолок — двадцать
    # знаков, тогда как в боевом каталоге названия доходят до тридцати четырёх
    # и длиннее. Ворота, меряющие перенос, обрезку и увеличение текста, на
    # коротких именах молчат и выглядят зелёными, ничего не проверив.
    if ordinal % 3 == 2:
        name = f"{name}: {_SUBTITLES[(ordinal * 2 + index) % len(_SUBTITLES)]}"
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


def _facet(counts: dict[str, int], labels: dict[str, str],
           vocabulary: tuple[tuple[str, str], ...]) -> tuple[tuple[str, str, int], ...]:
    """Фасет по данным, а не по словарю.

    Прежде значения пересекались с зашитым перечнем `GENRES`/`COUNTRIES`, и
    всё, чего в нём нет, исчезало молча: ни ошибки, ни записи в журнале.
    Перечень фикстурный и на английских слагах — `canada`, `france`, — а живой
    источник отдаёт русские названия, из которых `slugify` делает
    транслитерацию: `kanada`, `franciya`. Совпасть они не могут никогда, и на
    боевой витрине страница «Страны» была пуста при шестидесяти шести странах
    в данных.

    Теперь перечень задаёт только ПОРЯДОК известных значений и их подписи;
    состав задают данные. Подпись неизвестного значения берётся из самих
    данных — она там и есть, в исходном виде.
    """
    # Курируемый перечень ведёт намеренно, даже если частота у него ниже.
    # Источник отдаёт вперемешку жанры и пометки: на живом каталоге «западный
    # контент» встречается 964 раза, а «драма» — 505, и ставить первым
    # «западный контент» значило бы возглавить список жанров тем, что жанром
    # не является. Отбор в перечне уже сделан человеком; данные добавляют
    # хвост, а не переписывают начало.
    known = [(slug, label) for slug, label in vocabulary if counts.get(slug)]
    seen = {slug for slug, _ in known}
    # Остальное — по убыванию частоты: у длинного перечня порядок обязан быть
    # осмысленным, а алфавит транслитерации осмысленным не является.
    rest = sorted(
        ((slug, labels.get(slug) or slug) for slug in counts if slug and slug not in seen),
        key=lambda pair: (-counts[pair[0]], pair[1]),
    )
    return tuple((slug, label, counts[slug]) for slug, label in known + rest if slug)


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
        labels: dict[str, str] = {}
        for title in pool:
            names = tuple(title.genres or ())
            for index, slug in enumerate(title.genre_slugs):
                if not slug:
                    continue
                counts[slug] = counts.get(slug, 0) + 1
                if slug not in labels and index < len(names) and names[index]:
                    labels[slug] = names[index]
        return _facet(counts, labels, GENRES)

    def years(self, kinds=None) -> tuple[tuple[int, int], ...]:
        pool = self.of_types(kinds) if kinds is not None else self.titles
        counts: dict[int, int] = {}
        for title in pool:
            counts[title.year] = counts.get(title.year, 0) + 1
        return tuple((year, counts[year]) for year in sorted(counts, reverse=True))

    def countries(self, kinds=None) -> tuple[tuple[str, str, int], ...]:
        pool = self.of_types(kinds) if kinds is not None else self.titles
        counts: dict[str, int] = {}
        labels: dict[str, str] = {}
        for title in pool:
            slug = title.country_slug
            if not slug:
                # Пустое значение — отсутствие данных, а не категория:
                # посадочная страница под него вела бы в никуда.
                continue
            counts[slug] = counts.get(slug, 0) + 1
            if slug not in labels:
                # У записи может быть несколько стран через запятую; подписью
                # служит первая — та же, из которой получен слаг.
                labels[slug] = (title.country or "").split(",")[0].strip() or slug
        return _facet(counts, labels, COUNTRIES)

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


#: Точка отсчёта дат каталога стенда. Значение синтетическое и намеренно
#: постоянное: оно задаёт порядок «свежести», не претендуя быть настоящей датой.
CATALOG_EPOCH = datetime(2026, 1, 1, tzinfo=timezone.utc)

#: Раскладка состояний воспроизведения по кругу. Одиннадцать позиций: девять
#: подтверждённых, одна отказавшая, одна непроверенная. Пропорция взята так,
#: чтобы подтверждённых хватало на полки, а обе прочие ветки всё равно попадали
#: на стенд и под ворота.
PLAYBACK_MIX = (True, True, True, True, False, True, True, True, None, True, True)


def build_catalog() -> Catalog:
    """Детерминированный каталог стенда. Ни сети, ни случайности, ни времени."""
    titles: list[Title] = []
    for index, (kind, quota) in enumerate(TYPE_QUOTA):
        for ordinal in range(quota):
            titles.append(_make_title(kind, index, ordinal))

    # Слаги обязаны быть уникальными: адрес — это первичный ключ сайта.
    seen: dict[str, int] = {}
    unique: list[Title] = []
    for title in titles:
        count = seen.get(title.slug, 0)
        seen[title.slug] = count + 1
        if count:
            title = replace(title, slug=f"{title.slug}-{count + 1}")
        unique.append(title)

    # Даты добавления: фиксированная точка отсчёта и шаг в сутки по порядку
    # записи. Ни `datetime.now`, ни случайности — иначе каталог перестанет быть
    # воспроизводимым, а вместе с ним поплывут отпечаток сборки и эталон
    # раскладки. Порядок обратный: первая запись — самая свежая.
    # Смесь состояний намеренная, а не «всё работает». Стенд обязан показывать
    # и запасные состояния плеера: если бы все записи были подтверждены, ветки
    # «поток не работает» и «не проверялся» не отрисовывались бы никогда, и
    # ворота молчали бы о них ровно так же, как молчали о карусели.
    unique = [
        replace(
            title,
            created_at=(CATALOG_EPOCH - timedelta(days=position)).isoformat(),
            playable=PLAYBACK_MIX[position % len(PLAYBACK_MIX)],
        )
        for position, title in enumerate(unique)
    ]

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
