"""Реестр внешних источников оценок: доступ, шкала, лимиты, основание.

Каждый источник объявляет способ доступа по приоритету владельца:
официальный API → уже разрешённый коннектор проекта → публичный
документированный источник данных → разбор публичной страницы. Понижать
приоритет самостоятельно нельзя: если официальный API недоступен из-за
отсутствующего ключа, источник становится BLOCKED, а не «попробуем
распарсить страницу».

Контракты шкал подтверждены живыми read-only ответами (Этап A,
2026-09-21). Подтверждение — ссылка на файл evidence, а не слово
``verified=True`` в коде.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum

from factory.unified_ratings import (
    ADAPTER_VERSION_ANILIST,
    ADAPTER_VERSION_KITSU,
    ADAPTER_VERSION_PROVIDER_FEED,
    ADAPTER_VERSION_SHIKIMORI,
    ADAPTER_VERSION_SIMKL,
)
from factory.unified_ratings.scale import FormulaId, SourceScaleContract

DISCOVERY_EVIDENCE = "artifacts/evidence/unified-ratings-01/01-discovery/STAGE_A_DISCOVERY.json"


class AccessMethod(str, Enum):
    """Способ получения данных, в порядке приоритета владельца."""

    OFFICIAL_API = "OFFICIAL_API"
    EXISTING_PROJECT_CONNECTOR = "EXISTING_PROJECT_CONNECTOR"
    PUBLIC_DOCUMENTED_DATASET = "PUBLIC_DOCUMENTED_DATASET"
    PUBLIC_PAGE_PARSE = "PUBLIC_PAGE_PARSE"


class SourceStatus(str, Enum):
    READY = "READY"
    #: доступ технически возможен, но запрещён/не разрешён владельцем
    BLOCKED_AUTHORIZATION = "BLOCKED_AUTHORIZATION"
    #: нужен ключ/учётные данные, которых в secret storage нет
    BLOCKED_SECRET = "BLOCKED_SECRET"
    #: источник требует платной подписки, бюджета нет
    BLOCKED_PAID = "BLOCKED_PAID"
    #: источник недоступен по сети
    BLOCKED_ACCESS = "BLOCKED_ACCESS"
    #: значения приходят из уже разрешённого фида, свой сбор не запускается
    FEED_ONLY = "FEED_ONLY"


@dataclass(frozen=True)
class SourceDefinition:
    source_key: str
    display_name: str
    #: как называть источник в интерфейсе — ровно так и никак иначе
    ui_label: str
    adapter_version: str
    access_method: AccessMethod
    status: SourceStatus
    scale: SourceScaleContract
    #: лимиты, объявленные источником; наши не могут быть мягче
    documented_rate_limit: str
    max_rps: float
    max_requests_per_minute: int
    requires_credential: bool
    credential_ref: str = ""
    legal_basis: str = ""
    blocker: str = ""
    #: поля, которые нельзя принимать за оценку
    not_a_rating: tuple[str, ...] = field(default_factory=tuple)
    notes: str = ""

    @property
    def collectable(self) -> bool:
        """Можно ли запускать сбор. FEED_ONLY собирается не нами."""
        return self.status is SourceStatus.READY


# ---------------------------------------------------------------------------
# Контракты шкал
# ---------------------------------------------------------------------------

ANILIST_SCALE = SourceScaleContract(
    source_key="anilist",
    source_scale_min=Decimal(0),
    source_scale_max=Decimal(100),
    formula=FormulaId.DIVIDE_10_FROM_0_100,
    measures="взвешенная средняя оценка пользователей AniList",
    raw_field="Media.averageScore",
    verified=True,
    verified_evidence=(
        f"{DISCOVERY_EVIDENCE}: Media(id:1).averageScore=86, "
        "stats.scoreDistribution ключи 10..100 шагом 10"
    ),
    vote_count_field="Media.stats.scoreDistribution[].amount (сумма)",
    user_count_field="",
    notes=(
        "meanScore — вторая метрика того же поля, хранится в payload. "
        "popularity и favourites считают пользователей списка, а не голоса."
    ),
)

KITSU_SCALE = SourceScaleContract(
    source_key="kitsu",
    source_scale_min=Decimal(0),
    source_scale_max=Decimal(100),
    formula=FormulaId.DIVIDE_10_FROM_0_100,
    measures="средняя оценка пользователей Kitsu",
    raw_field="data.attributes.averageRating",
    verified=True,
    verified_evidence=(
        f"{DISCOVERY_EVIDENCE}: anime/1 averageRating='82.27' (строка), "
        "ratingFrequencies ключи 2..20 — это шкала 1–10 с шагом 0.5, умноженная на 2"
    ),
    vote_count_field="data.attributes.ratingFrequencies (сумма значений)",
    user_count_field="data.attributes.userCount",
    notes=(
        "averageRating приходит строкой и может быть null. userCount — число "
        "пользователей с тайтлом в библиотеке, оно больше числа оценивших и "
        "не является числом голосов."
    ),
)

SHIKIMORI_SCALE = SourceScaleContract(
    source_key="shikimori",
    source_scale_min=Decimal(0),
    source_scale_max=Decimal(10),
    formula=FormulaId.IDENTITY_0_10,
    measures="оценка Shikimori (не оценка MAL)",
    raw_field="animes[].score",
    verified=True,
    verified_evidence=(
        "docs/rights/shikimori-ratings.md + существующий проверенный адаптер "
        "factory/ratings/adapters/shikimori.py (live probe 2026-09-19)"
    ),
    vote_count_field="animes[].scoresStats[].count (сумма)",
    notes="malId — ключ сопоставления, а не оценка.",
)

SIMKL_SCALE = SourceScaleContract(
    source_key="simkl",
    source_scale_min=Decimal(0),
    source_scale_max=Decimal(10),
    formula=FormulaId.IDENTITY_0_10,
    measures="средняя оценка пользователей Simkl",
    raw_field="ratings.simkl.rating",
    # Контракт НЕ подтверждён: без client_id живой ответ получить нельзя,
    # а шкала по памяти — это выдуманная шкала.
    verified=False,
    verified_evidence="",
    vote_count_field="ratings.simkl.votes",
    notes=(
        "Шкала записана как ожидаемая, но не подтверждена: API вернул "
        "412 client_id_failed. До получения ключа нормализация Simkl "
        "возвращает CONTRACT_UNVERIFIED, а не число."
    ),
)

PROVIDER_FEED_SCALE_IMDB = SourceScaleContract(
    source_key="provider_feed_imdb",
    source_scale_min=Decimal(0),
    source_scale_max=Decimal(10),
    formula=FormulaId.IDENTITY_0_10,
    measures="оценка IMDb, переданная в договорном фиде поставщика",
    raw_field="catalog_item.imdb_rating",
    verified=True,
    verified_evidence="docs/rights/provider-feed-ratings.md; поле уже приходит в фиде",
    notes="Прямое обращение к IMDb запрещено; значение берётся только из фида.",
)

PROVIDER_FEED_SCALE_KP = SourceScaleContract(
    source_key="provider_feed_kinopoisk",
    source_scale_min=Decimal(0),
    source_scale_max=Decimal(10),
    formula=FormulaId.IDENTITY_0_10,
    measures="оценка Кинопоиска, переданная в договорном фиде поставщика",
    raw_field="catalog_item.kinopoisk_rating",
    verified=True,
    verified_evidence="docs/rights/provider-feed-ratings.md; поле уже приходит в фиде",
    notes="Прямое обращение к Кинопоиску запрещено; значение берётся только из фида.",
)


# ---------------------------------------------------------------------------
# Реестр источников
# ---------------------------------------------------------------------------

ANILIST = SourceDefinition(
    source_key="anilist",
    display_name="AniList",
    ui_label="AniList",
    adapter_version=ADAPTER_VERSION_ANILIST,
    access_method=AccessMethod.OFFICIAL_API,
    status=SourceStatus.READY,
    scale=ANILIST_SCALE,
    documented_rate_limit="X-RateLimit-Limit: 30 запросов в минуту (наблюдено 2026-09-21)",
    max_rps=0.4,
    max_requests_per_minute=20,
    requires_credential=False,
    legal_basis="публичный официальный GraphQL API без ключа; запросы read-only",
    not_a_rating=("popularity", "favourites", "rankings", "trending"),
    notes="Сервер сам объявляет лимит заголовком; наш cap ниже объявленного.",
)

KITSU = SourceDefinition(
    source_key="kitsu",
    display_name="Kitsu",
    ui_label="Kitsu",
    adapter_version=ADAPTER_VERSION_KITSU,
    access_method=AccessMethod.OFFICIAL_API,
    status=SourceStatus.READY,
    scale=KITSU_SCALE,
    documented_rate_limit="лимит в заголовках не объявлен; используем консервативный cap",
    max_rps=0.5,
    max_requests_per_minute=20,
    requires_credential=False,
    legal_basis="публичный официальный JSON:API без ключа; запросы read-only",
    not_a_rating=("popularityRank", "ratingRank", "userCount", "favoritesCount"),
    notes=(
        "Резервный источник. Лимит источником не документирован в ответе, "
        "поэтому выбран cap заведомо ниже нагрузки одного пользователя."
    ),
)

SIMKL = SourceDefinition(
    source_key="simkl",
    display_name="Simkl",
    ui_label="Simkl",
    adapter_version=ADAPTER_VERSION_SIMKL,
    access_method=AccessMethod.OFFICIAL_API,
    status=SourceStatus.BLOCKED_SECRET,
    scale=SIMKL_SCALE,
    documented_rate_limit="не измерено: до получения ключа запросы не выполняются",
    max_rps=0.5,
    max_requests_per_minute=20,
    requires_credential=True,
    credential_ref="secret_ref: simkl_client_id (в secret storage отсутствует)",
    legal_basis="официальный API требует регистрации приложения и client_id",
    blocker=(
        "GET https://api.simkl.com/anime/1 без ключа → HTTP 412 "
        '{"error":"client_id_failed"}. Ключа нет ни в secret storage, ни в '
        "inventory. Обход блокировки подделкой client_id или разбором "
        "страницы запрещён, поэтому источник остаётся BLOCKED_SECRET."
    ),
    notes=(
        "Владелец назвал Simkl основным источником там, где он применим. "
        "Разблокировка — одно внешнее действие: выдать client_id как secret_ref."
    ),
)

SHIKIMORI = SourceDefinition(
    source_key="shikimori",
    display_name="Shikimori",
    ui_label="Shikimori",
    adapter_version=ADAPTER_VERSION_SHIKIMORI,
    access_method=AccessMethod.EXISTING_PROJECT_CONNECTOR,
    status=SourceStatus.READY,
    scale=SHIKIMORI_SCALE,
    documented_rate_limit="5 rps / 90 rpm по документации источника",
    max_rps=2.0,
    max_requests_per_minute=60,
    requires_credential=False,
    credential_ref="secret_ref: shikimori_api_token (опционально)",
    legal_basis=(
        "docs/rights/shikimori-ratings.md; разрешение владельца 2026-09-19, "
        "config/rating-sources.yaml → authorization.status=granted"
    ),
    not_a_rating=("malId",),
    notes=(
        "Разрешённый доступ уже существует и проверен Stage 1–5; новый "
        "адаптер не создаётся, переиспользуется проверенный коннектор."
    ),
)

PROVIDER_FEED_IMDB = SourceDefinition(
    source_key="provider_feed_imdb",
    display_name="IMDb (договорный фид поставщика)",
    ui_label="IMDb",
    adapter_version=ADAPTER_VERSION_PROVIDER_FEED,
    access_method=AccessMethod.EXISTING_PROJECT_CONNECTOR,
    status=SourceStatus.FEED_ONLY,
    scale=PROVIDER_FEED_SCALE_IMDB,
    documented_rate_limit="наружу не ходит: значения уже есть в загруженном фиде",
    max_rps=0.0,
    max_requests_per_minute=0,
    requires_credential=False,
    legal_basis="docs/rights/provider-feed-ratings.md; разрешение владельца 2026-09-06",
    blocker="Новый сбор с imdb.com не запускается: скрапинг IMDb запрещён.",
)

PROVIDER_FEED_KINOPOISK = SourceDefinition(
    source_key="provider_feed_kinopoisk",
    display_name="Кинопоиск (договорный фид поставщика)",
    ui_label="Кинопоиск",
    adapter_version=ADAPTER_VERSION_PROVIDER_FEED,
    access_method=AccessMethod.EXISTING_PROJECT_CONNECTOR,
    status=SourceStatus.FEED_ONLY,
    scale=PROVIDER_FEED_SCALE_KP,
    documented_rate_limit="наружу не ходит: значения уже есть в загруженном фиде",
    max_rps=0.0,
    max_requests_per_minute=0,
    requires_credential=False,
    legal_basis="docs/rights/provider-feed-ratings.md; разрешение владельца 2026-09-06",
    blocker="Новый сбор с kinopoisk.ru не запускается: скрапинг Кинопоиска запрещён.",
)


REGISTRY: dict[str, SourceDefinition] = {
    s.source_key: s
    for s in (
        ANILIST,
        KITSU,
        SIMKL,
        SHIKIMORI,
        PROVIDER_FEED_IMDB,
        PROVIDER_FEED_KINOPOISK,
    )
}

#: Порядок отображения в интерфейсе. Наша и зрительская оценки идут первыми
#: и добавляются слоем отображения — здесь только внешние источники.
EXTERNAL_DISPLAY_ORDER: tuple[str, ...] = (
    "anilist",
    "simkl",
    "kitsu",
    "shikimori",
    "provider_feed_imdb",
    "provider_feed_kinopoisk",
)


def get(source_key: str) -> SourceDefinition:
    try:
        return REGISTRY[source_key]
    except KeyError:
        raise KeyError(f"источник не зарегистрирован: {source_key}") from None


def collectable_sources() -> list[SourceDefinition]:
    """Источники, для которых разрешён наш собственный сбор."""
    return [s for s in REGISTRY.values() if s.collectable]


def blocked_sources() -> list[SourceDefinition]:
    return [s for s in REGISTRY.values() if s.status is not SourceStatus.READY]
