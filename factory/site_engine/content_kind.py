"""Единственный authoritative тип произведения.

Зачем модуль существует. Тип произведения выводился на витрине из строки
заголовка, из жанра и из подписи в таблице фактов — тремя способами
одновременно. Аудит 2026-09-05 нашёл 172 записи из 308, где четыре источника
одной страницы говорили разное: видимая подпись «Сериал», Schema.org `Movie`,
`og:type` `video.movie`, заголовок блока «О фильме». Поиск получает уверенное
утверждение, противоречащее собственным данным сайта.

Здесь тип устанавливается один раз, в ядре, и раздаётся готовым. Витрина,
SEO, Schema.org и Open Graph его не выводят, а получают.

Три правила, каждое стоило отдельного дефекта:

* **Отсутствие сезонов не доказывает фильм.** У поставщика `type` принимает
  ровно два значения — `movie` и `tv`, — и всё, что не сериал, попадало в
  «фильм». Измерено на боевом каталоге: 332 записи несут в тегах свой
  настоящий вид (`ona` 257, `ova` 44, `special` 31), и **все 332** расходятся
  с двоичным `type`.
* **Анимация — это не вид произведения, а его исполнение.** Аниме бывает и
  фильмом, и сериалом. Отображение `anime → ANIMATION` с запретом серий
  превращало аниме-сериал в анимационный фильм: отсюда 133 записи с
  «сезонами и сериями у несериального типа». Признак вынесен отдельным полем
  `is_animation`, и видом он не является.
* **UNKNOWN — не значение по умолчанию.** Это отказ утверждать. Он запрещает
  выпускать Schema.org и отправляет запись в разбор.
"""

from __future__ import annotations

import dataclasses
import enum

#: Версия словаря типов. Совместима по проводу с `seo-content-contract/1.0.0`:
#: значения MOVIE, SERIES, SEASON, EPISODE, OVA, ONA, SPECIAL, UNKNOWN
#: совпадают буквально. Minor — добавлены SHORT, MUSIC и признак анимации.
CONTRACT_VERSION = "content-kind/1.1.0"

#: Что означает каждая часть версии — чтобы её меняли осознанно.
VERSION_POLICY = (
    "major — у существующего типа изменился тип Schema.org или разрешённость "
    "сезонов и серий: потребитель обязан обновиться; "
    "minor — добавлен новый тип или необязательное поле; "
    "patch — уточнена формулировка, машинные значения те же."
)


class ContentKind(str, enum.Enum):
    """Виды произведений. Перечень закрыт: новый вид — это правка контракта."""

    MOVIE = "MOVIE"
    #: Проводное имя совпадает с `seo-content-contract/1.0.0`. Написание
    #: `TV_SERIES` принимается на входе как псевдоним, но наружу не уходит:
    #: два имени одного типа — это то же расхождение, только внутри контракта.
    SERIES = "SERIES"
    MINISERIES = "MINISERIES"
    SEASON = "SEASON"
    EPISODE = "EPISODE"
    OVA = "OVA"
    OAD = "OAD"
    ONA = "ONA"
    SPECIAL = "SPECIAL"
    SHORT = "SHORT"
    MUSIC = "MUSIC"
    DOCUMENTARY = "DOCUMENTARY"
    UNKNOWN = "UNKNOWN"


class ContentKindError(ValueError):
    """Тип не установлен или использован там, где его нет."""


@dataclasses.dataclass(frozen=True)
class KindContract:
    """Всё, что тип определяет. Ни одно поле не выбирается отдельно."""

    kind: ContentKind
    visible_type: str
    about_heading: str
    #: Пустая строка означает «разметку не выпускать вовсе».
    schema_type: str
    og_type: str
    allows_seasons: bool
    allows_episodes: bool
    requires_parent: tuple[ContentKind, ...] = ()
    #: Может ли у типа быть длительность одной единицы просмотра. У сериала
    #: длительность относится к серии, а не к сериалу целиком.
    has_duration: bool = True
    note: str = ""


CONTRACT: dict[ContentKind, KindContract] = {
    ContentKind.MOVIE: KindContract(
        kind=ContentKind.MOVIE,
        visible_type="Фильм",
        about_heading="О фильме",
        schema_type="Movie",
        og_type="video.movie",
        allows_seasons=False,
        allows_episodes=False,
        note="полнометражная работа; сезонов и серий у неё нет как понятия",
    ),
    ContentKind.SERIES: KindContract(
        kind=ContentKind.SERIES,
        visible_type="Сериал",
        about_heading="О сериале",
        schema_type="TVSeries",
        og_type="video.tv_show",
        allows_seasons=True,
        allows_episodes=True,
        has_duration=False,
        note="длительность относится к серии, а не к сериалу целиком",
    ),
    ContentKind.MINISERIES: KindContract(
        kind=ContentKind.MINISERIES,
        visible_type="Мини-сериал",
        about_heading="О сериале",
        schema_type="TVSeries",
        og_type="video.tv_show",
        allows_seasons=True,
        allows_episodes=True,
        has_duration=False,
        note="отдельного типа Schema.org нет; различие живёт в видимом названии",
    ),
    ContentKind.SEASON: KindContract(
        kind=ContentKind.SEASON,
        visible_type="Сезон",
        about_heading="О сезоне",
        schema_type="TVSeason",
        og_type="video.tv_show",
        allows_seasons=False,
        allows_episodes=True,
        requires_parent=(ContentKind.SERIES, ContentKind.MINISERIES),
        has_duration=False,
        note="сезон без сериала — не запись с пропущенным полем, а бессмыслица",
    ),
    ContentKind.EPISODE: KindContract(
        kind=ContentKind.EPISODE,
        visible_type="Серия",
        about_heading="О серии",
        schema_type="TVEpisode",
        og_type="video.episode",
        allows_seasons=False,
        allows_episodes=False,
        requires_parent=(ContentKind.SEASON,),
        note="описание серии не может быть копией описания сериала",
    ),
    ContentKind.OVA: KindContract(
        kind=ContentKind.OVA,
        visible_type="OVA",
        about_heading="Об OVA",
        schema_type="TVSeries",
        og_type="video.tv_show",
        allows_seasons=False,
        allows_episodes=True,
        has_duration=False,
        note="выпуск вне телевизионного показа; сквозная нумерация выпусков",
    ),
    ContentKind.OAD: KindContract(
        kind=ContentKind.OAD,
        visible_type="OAD",
        about_heading="Об OAD",
        schema_type="TVSeries",
        og_type="video.tv_show",
        allows_seasons=False,
        allows_episodes=True,
        has_duration=False,
        note="выпуск, приложенный к изданию исходного произведения",
    ),
    ContentKind.ONA: KindContract(
        kind=ContentKind.ONA,
        visible_type="ONA",
        about_heading="Об ONA",
        schema_type="TVSeries",
        og_type="video.tv_show",
        allows_seasons=False,
        allows_episodes=True,
        has_duration=False,
        note="выпуск для сетевого показа; в боевом каталоге это самый частый "
        "вид, потерянный двоичным type — 257 записей",
    ),
    ContentKind.SPECIAL: KindContract(
        kind=ContentKind.SPECIAL,
        visible_type="Спецвыпуск",
        about_heading="О спецвыпуске",
        schema_type="TVSpecial",
        og_type="video.tv_show",
        allows_seasons=False,
        allows_episodes=False,
        note="отдельный выпуск вне основной нумерации",
    ),
    ContentKind.SHORT: KindContract(
        kind=ContentKind.SHORT,
        visible_type="Короткометражный фильм",
        about_heading="О фильме",
        schema_type="Movie",
        og_type="video.movie",
        allows_seasons=False,
        allows_episodes=False,
        note="Schema.org отдельного типа для короткого метра не имеет: "
        "используется Movie, различие живёт в видимом названии и "
        "длительности. Выдумывать несуществующий тип разметки нельзя",
    ),
    ContentKind.MUSIC: KindContract(
        kind=ContentKind.MUSIC,
        visible_type="Музыкальное видео",
        about_heading="О видео",
        schema_type="MusicVideoObject",
        og_type="video.other",
        allows_seasons=False,
        allows_episodes=False,
        note="клип или музыкальный выпуск; MusicVideoObject — единственный "
        "тип Schema.org, который это описывает",
    ),
    ContentKind.DOCUMENTARY: KindContract(
        kind=ContentKind.DOCUMENTARY,
        visible_type="Документальный фильм",
        about_heading="О фильме",
        schema_type="Movie",
        og_type="video.movie",
        allows_seasons=False,
        allows_episodes=False,
        note="Schema.org различает документальное кино жанром, а не типом",
    ),
    ContentKind.UNKNOWN: KindContract(
        kind=ContentKind.UNKNOWN,
        visible_type="",
        about_heading="",
        schema_type="",
        og_type="",
        allows_seasons=False,
        allows_episodes=False,
        has_duration=False,
        note="тип не установлен: разметка не выпускается, запись уходит в разбор",
    ),
}

#: Где живёт словарь написаний. Отдельным файлом, а не литералами здесь:
#: это данные поставщика, а универсальному слою запрещено называть предметную
#: область. Гейт границ поймал слово «anime» в коде ядра — справедливо.
VOCABULARY_REF = "config/content-kind-vocabulary.yaml"

#: Запасной словарь на случай отсутствующего файла. Содержит только написания,
#: совпадающие с именами самих видов: расширять перечень отсутствие настройки
#: не вправе, а обнулять его — тем более.
#: Встроенный словарь написаний. Файл настройки его ДОПОЛНЯЕТ, а не заменяет.
#:
#: Прежде встроенным был перечень из одних имён самих видов, и при отсутствии
#: файла «movie» и «tv» переставали распознаваться: весь каталог молча
#: становился UNKNOWN. Молчаливое обнуление хуже отказа — оно выглядит как
#: «поставщик не назвал тип», хотя тип назван.
#:
#: Способов исполнения здесь нет: универсальному слою запрещено называть
#: предметную область, и эти написания живут только в файле настройки. При его
#: отсутствии признак остаётся None — «не измерено», а не «нет».
_ВСТРОЕННЫЙ = {
    "MOVIE": ["movie", "film", "feature", "фильм"],
    "SERIES": ["series", "tvseries", "tv", "tvshow", "show", "сериал", "tv_series"],
    "MINISERIES": ["miniseries", "минисериал"],
    "SEASON": ["season", "сезон"],
    "EPISODE": ["episode", "серия", "эпизод"],
    "OVA": ["ova"],
    "OAD": ["oad"],
    "ONA": ["ona"],
    "SPECIAL": ["special", "specials", "tvspecial", "спецвыпуск"],
    "SHORT": ["short", "shortfilm", "короткометражка"],
    "MUSIC": ["music", "musicvideo", "pv", "клип"],
    "DOCUMENTARY": ["documentary", "документальный"],
}

#: Теги, несущие вид. Тоже встроены: без них запись с уточняющим тегом теряла
#: бы его при отсутствии файла.
_ВСТРОЕННЫЕ_ТЕГИ = {
    "OVA": ["ova"],
    "OAD": ["oad"],
    "ONA": ["ona"],
    "SPECIAL": ["special", "specials"],
    "SHORT": ["short"],
    "MUSIC": ["music", "pv"],
    "DOCUMENTARY": ["documentary"],
}


def _загрузить_словарь(root=None) -> dict:
    from pathlib import Path

    import yaml

    основа = {
        "aliases": {k: list(v) for k, v in _ВСТРОЕННЫЙ.items()},
        "animation_markers": [],
        "kind_tags": {k: list(v) for k, v in _ВСТРОЕННЫЕ_ТЕГИ.items()},
        "vocabulary_version": "builtin",
    }
    if root is None:
        try:
            from factory.paths import PATHS

            root = PATHS.root
        except Exception:  # noqa: BLE001
            return основа
    путь = Path(root) / VOCABULARY_REF
    if not путь.exists():
        return основа
    данные = yaml.safe_load(путь.read_text(encoding="utf-8")) or {}
    # Файл дополняет встроенное, а не заменяет: неполный файл иначе молча
    # выключал бы распознавание типов, которые в нём просто не перечислили.
    итог = dict(основа)
    for ключ in ("aliases", "kind_tags"):
        слитое = {k: list(v) for k, v in основа[ключ].items()}
        for вид, написания in (данные.get(ключ) or {}).items():
            слитое[вид] = sorted(set(слитое.get(вид, [])) | set(написания or []))
        итог[ключ] = слитое
    итог["animation_markers"] = list(данные.get("animation_markers") or [])
    итог["vocabulary_version"] = str(данные.get("vocabulary_version", "builtin"))
    return итог


_СЛОВАРЬ = _загрузить_словарь()

#: Написание источника → вид. Собирается из словаря, а не пишется здесь.
ALIASES: dict[str, ContentKind] = {
    написание: ContentKind(вид)
    for вид, написания in (_СЛОВАРЬ["aliases"] or {}).items()
    for написание in (написания or [])
}

#: Способ исполнения. Отдельно от вида намеренно: признак ортогонален виду.
ANIMATION_MARKERS = frozenset(_СЛОВАРЬ["animation_markers"] or ())

#: Теги, несущие вид произведения.
KIND_TAGS: dict[str, ContentKind] = {
    тег: ContentKind(вид)
    for вид, теги in (_СЛОВАРЬ["kind_tags"] or {}).items()
    for тег in (теги or [])
}

VOCABULARY_VERSION = str(_СЛОВАРЬ.get("vocabulary_version", "builtin"))


def normalise_alias(raw: str) -> str:
    return (raw or "").strip().lower().replace(" ", "").replace("-", "")


_ALIAS_INDEX = {normalise_alias(k): v for k, v in ALIASES.items()}
#: `tv_series` и `tv-series` обязаны вести к одному типу, поэтому нижнее
#: подчёркивание нормализуется отдельно от построения индекса.
_ALIAS_INDEX.update({normalise_alias(k).replace("_", ""): v for k, v in ALIASES.items()})


def resolve(raw: str | None) -> ContentKind:
    """Тип по строке источника. Неизвестное написание даёт UNKNOWN.

    Догадок нет: функция смотрит только на переданную строку и таблицу.
    """
    if raw is None:
        return ContentKind.UNKNOWN
    return _ALIAS_INDEX.get(normalise_alias(str(raw)).replace("_", ""), ContentKind.UNKNOWN)


def is_animation_marker(raw: str | None) -> bool:
    """Признак анимации. Видом произведения не является и им не становится."""
    return normalise_alias(str(raw or "")) in {normalise_alias(m) for m in ANIMATION_MARKERS}


def contract_for(kind: ContentKind | str) -> KindContract:
    """Контракт типа. Незнакомое значение — ошибка, а не молчаливый UNKNOWN.

    Здесь молчание опаснее отказа: вызывающий уже решил, что тип известен,
    и подстановка UNKNOWN выпустила бы пустую разметку вместо явной поломки.
    """
    if isinstance(kind, str) and not isinstance(kind, ContentKind):
        try:
            kind = ContentKind(kind)
        except ValueError as ошибка:
            raise ContentKindError(f"тип {kind!r} вне контракта") from ошибка
    return CONTRACT[kind]


def schema_type_for(kind: ContentKind | str) -> str:
    """Тип Schema.org. Пустая строка означает «разметку не выпускать»."""
    return contract_for(kind).schema_type


def emits_schema(kind: ContentKind | str) -> bool:
    return bool(schema_type_for(kind))
