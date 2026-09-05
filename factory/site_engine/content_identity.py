"""ContentIdentity v1 — что именно за произведение перед нами.

До этого записи каталога не имели устойчивой личности. Тип выводился на
витрине из заголовка, рейтинг привязывался по совпадению русского названия, а
Schema.org собиралась из того, что оказалось под рукой. Три разных ответа на
один вопрос — не следствие небрежности, а следствие того, что вопрос никогда
не задавался в одном месте.

Здесь он задаётся один раз. Запись либо разрешена и знает, чем она
подтверждена, либо честно не разрешена — и тогда потребитель обязан вести
себя как при неизвестности, а не подставлять правдоподобное.

Два поля существуют ради возможности не верить результату задним числом:
`payload_hash` показывает, изменились ли входные данные, а `resolver_version`
и `mapping_method` — чем именно получен ответ. Без них «почему у этой записи
такой тип» отвечается только повторным разбором вручную.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import enum
import hashlib
import json
from typing import Any

from factory.site_engine.content_kind import ContentKind

SCHEMA_VERSION = "content-identity/1.0.0"


class IdentityStatus(str, enum.Enum):
    """Состояние сопоставления. UNMATCHED — это ответ, а не отсутствие ответа."""

    RESOLVED_EXACT_ID = "RESOLVED_EXACT_ID"
    RESOLVED_HIGH_CONFIDENCE = "RESOLVED_HIGH_CONFIDENCE"
    AMBIGUOUS = "AMBIGUOUS"
    CONFLICTED = "CONFLICTED"
    UNMATCHED = "UNMATCHED"
    NEEDS_SOURCE = "NEEDS_SOURCE"
    SOURCE_NOT_CONFIGURED = "SOURCE_NOT_CONFIGURED"


class MappingMethod(str, enum.Enum):
    EXACT_EXTERNAL_ID = "EXACT_EXTERNAL_ID"
    EXACT_PROVIDER_ASSET_ID = "EXACT_PROVIDER_ASSET_ID"
    ORIGINAL_TITLE_YEAR_KIND = "ORIGINAL_TITLE_YEAR_KIND"
    ALTERNATIVE_TITLE_YEAR_PLUS = "ALTERNATIVE_TITLE_YEAR_PLUS"
    NORMALIZED_TITLE_YEAR_PLUS = "NORMALIZED_TITLE_YEAR_PLUS"
    #: Тип установлен по данным самого каталога, без внешнего источника.
    CATALOG_INTRINSIC = "CATALOG_INTRINSIC"
    MANUAL_QUEUE = "MANUAL_QUEUE"
    NONE = "NONE"


@dataclasses.dataclass(frozen=True)
class SourceRef:
    """Откуда взято утверждение. Без этого «мы знаем» непроверяемо."""

    source: str
    source_entity_id: str = ""
    requested_at: str = ""
    source_updated_at: str = ""
    payload_hash: str = ""
    cache_status: str = ""
    license_policy_version: str = ""
    attribution: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "sourceEntityId": self.source_entity_id,
            "requestedAt": self.requested_at,
            "sourceUpdatedAt": self.source_updated_at,
            "payloadHash": self.payload_hash,
            "cacheStatus": self.cache_status,
            "licensePolicyVersion": self.license_policy_version,
            "attribution": self.attribution,
        }


@dataclasses.dataclass
class ContentIdentity:
    """Личность произведения. Ни одно поле не заполняется догадкой."""

    internal_entity_id: str
    provider_asset_id: str = ""
    content_kind: ContentKind = ContentKind.UNKNOWN
    #: Признак исполнения, а не вид. Аниме бывает и фильмом, и сериалом,
    #: поэтому в contentKind ему места нет.
    is_animation: bool | None = None
    displayed_title: str = ""
    original_title: str = ""
    alternative_titles: tuple[str, ...] = ()
    release_year: int | None = None
    release_date: str = ""
    country: str = ""
    language: str = ""
    #: Минуты. None означает «не измерено». Ноль запрещён: PT0M в разметке —
    #: это утверждение «идёт нисколько», а известно обратное.
    duration: int | None = None
    episode_count: int | None = None
    season_number: int | None = None
    external_ids: dict[str, str] = dataclasses.field(default_factory=dict)
    source_refs: tuple[SourceRef, ...] = ()
    identity_status: IdentityStatus = IdentityStatus.UNMATCHED
    mapping_method: MappingMethod = MappingMethod.NONE
    mapping_confidence: float = 0.0
    conflict_state: tuple[str, ...] = ()
    resolved_at: str = ""
    payload_hash: str = ""
    resolver_version: str = ""
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.duration == 0:
            raise ValueError(
                "duration=0 запрещено: отсутствующая длительность — это None, "
                "а ноль означает «идёт нисколько» и попадает в разметку как PT0M"
            )

    @property
    def resolved(self) -> bool:
        return self.identity_status in (
            IdentityStatus.RESOLVED_EXACT_ID,
            IdentityStatus.RESOLVED_HIGH_CONFIDENCE,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "internalEntityId": self.internal_entity_id,
            "providerAssetId": self.provider_asset_id,
            "contentKind": self.content_kind.value,
            "isAnimation": self.is_animation,
            "displayedTitle": self.displayed_title,
            "originalTitle": self.original_title,
            "alternativeTitles": list(self.alternative_titles),
            "releaseYear": self.release_year,
            "releaseDate": self.release_date,
            "country": self.country,
            "language": self.language,
            "duration": self.duration,
            "episodeCount": self.episode_count,
            "seasonNumber": self.season_number,
            "externalIds": dict(self.external_ids),
            "sourceRefs": [r.as_dict() for r in self.source_refs],
            "identityStatus": self.identity_status.value,
            "mappingMethod": self.mapping_method.value,
            "mappingConfidence": round(self.mapping_confidence, 4),
            "conflictState": list(self.conflict_state),
            "resolvedAt": self.resolved_at,
            "payloadHash": self.payload_hash,
            "resolverVersion": self.resolver_version,
        }


#: Поля, входящие в отпечаток. Служебные (время разбора, версия резолвера,
#: сама оценка) исключены намеренно: иначе повторный прогон того же входа дал
#: бы другой отпечаток, и «изменились ли данные» перестало бы быть вопросом
#: с ответом.
HASHED_FIELDS = (
    "providerAssetId",
    "contentKind",
    "isAnimation",
    "displayedTitle",
    "originalTitle",
    "alternativeTitles",
    "releaseYear",
    "releaseDate",
    "country",
    "language",
    "duration",
    "episodeCount",
    "seasonNumber",
    "externalIds",
)


def payload_hash(identity: ContentIdentity) -> str:
    """Отпечаток содержательной части. Одинаковый вход — одинаковый отпечаток."""
    данные = identity.as_dict()
    отобрано = {k: данные.get(k) for k in HASHED_FIELDS}
    сырое = json.dumps(отобрано, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(сырое.encode("utf-8")).hexdigest()[:32]


def stamp(
    identity: ContentIdentity, *, resolver_version: str, now: dt.datetime | None = None
) -> ContentIdentity:
    """Проставляет отпечаток, время и версию резолвера."""
    identity.payload_hash = payload_hash(identity)
    identity.resolver_version = resolver_version
    identity.resolved_at = (now or dt.datetime.now(dt.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return identity
