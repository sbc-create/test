"""Контракты v1: что движки обещают друг другу.

Здесь не описание таблиц и не схема хранения. Здесь — общий словарь: если два
движка понимают одно и то же поле по-разному, они не договорятся никаким API.

У каждого контракта названы владелец и потребители. Владелец — единственный, кто
пишет; остальные читают. Без этого «несколько источников истины» появляются сами
и обнаруживаются в момент расхождения.

Правило совместимости одно на все контракты: поле можно добавить со значением по
умолчанию; удалить или изменить смысл — нельзя без новой версии.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from factory.site_engine.contracts import ContractError, require_aware, utc_now

CONTRACTS_VERSION = "1.0"


# --------------------------------------------------------------------- время
class TimeSemantics(str, Enum):
    """Смысл временной отметки. Путаница здесь стоила ложного инцидента.

    `releaseAt` — когда произведение выходит у правообладателя.
    `announcedAt` — когда о выходе объявили.
    `publishedAt` — когда мы это опубликовали на витрине.
    `updatedAt` — когда запись менялась у поставщика.
    `observedAt` — когда **мы** увидели изменение.

    Подставлять `observedAt` вместо `releaseAt` запрещено: это превращает
    наблюдение в факт о произведении.
    """

    RELEASE_AT = "releaseAt"
    ANNOUNCED_AT = "announcedAt"
    PUBLISHED_AT = "publishedAt"
    UPDATED_AT = "updatedAt"
    OBSERVED_AT = "observedAt"


@dataclass(frozen=True)
class Timestamps:
    """Набор отметок. Отсутствующая отметка — `None`, а не «сегодня»."""

    observed_at: datetime = field(default_factory=utc_now)
    updated_at: datetime | None = None
    published_at: datetime | None = None
    announced_at: datetime | None = None
    release_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "observed_at", require_aware(self.observed_at, "observed_at"))
        for имя in ("updated_at", "published_at", "announced_at", "release_at"):
            значение = getattr(self, имя)
            if значение is not None:
                object.__setattr__(self, имя, require_aware(значение, имя))

    def as_dict(self) -> dict[str, str | None]:
        return {
            "observedAt": self.observed_at.isoformat(),
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
            "publishedAt": self.published_at.isoformat() if self.published_at else None,
            "announcedAt": self.announced_at.isoformat() if self.announced_at else None,
            "releaseAt": self.release_at.isoformat() if self.release_at else None,
        }


# ----------------------------------------------------------------- контракты
@dataclass(frozen=True)
class EditorialOverride:
    """Ручной текст поверх данных поставщика.

    Черновик не публикуется сам: `published` меняется отдельной командой с
    отдельным правом.
    """

    override_id: str
    site_ids: tuple[str, ...]
    subject_id: str
    fields: dict[str, Any]
    author: str
    published: bool = False
    version: int = 1
    timestamps: Timestamps = field(default_factory=Timestamps)

    def __post_init__(self) -> None:
        if not self.site_ids:
            raise ContractError("правка без витрин не применяется ни к чему")
        if not self.fields:
            raise ContractError("правка без полей ничего не меняет")


@dataclass(frozen=True)
class SeoDocument:
    """То, что SEO Engine отдаёт витрине. Провайдера он не знает."""

    document_id: str
    site_id: str
    path: str
    title: str
    description: str
    canonical: str
    robots: str
    schema_org: dict[str, Any] = field(default_factory=dict)
    version: int = 1
    timestamps: Timestamps = field(default_factory=Timestamps)

    def __post_init__(self) -> None:
        if not self.canonical.startswith("https://"):
            raise ContractError(f"canonical обязан быть публичным HTTPS: {self.canonical}")
        if self.robots not in {"index, follow", "noindex, follow", "noindex", "noindex, nofollow"}:
            raise ContractError(f"неизвестная директива robots: {self.robots}")


@dataclass(frozen=True)
class MediaAsset:
    """Изображение и его происхождение."""

    asset_id: str
    source_url: str
    local_path: str | None
    content_type: str
    bytes_size: int | None
    state: str = "unknown"          # fresh | stale | placeholder | missing
    version: int = 1
    timestamps: Timestamps = field(default_factory=Timestamps)

    def __post_init__(self) -> None:
        if self.content_type and not self.content_type.startswith("image/"):
            raise ContractError(f"медиа не изображение: {self.content_type}")
        if self.state not in {"fresh", "stale", "placeholder", "missing", "unknown"}:
            raise ContractError(f"неизвестное состояние медиа: {self.state}")


@dataclass(frozen=True)
class SchedulerJob:
    """Периодическая работа: чем является и когда шла."""

    job_id: str
    name: str
    schedule: str
    last_started_at: datetime | None = None
    last_finished_at: datetime | None = None
    last_result: str = "unknown"     # ok | failed | skipped | unknown
    consecutive_failures: int = 0
    version: int = 1

    def __post_init__(self) -> None:
        if self.last_result not in {"ok", "failed", "skipped", "unknown"}:
            raise ContractError(f"неизвестный итог задания: {self.last_result}")


@dataclass(frozen=True)
class PublishJob:
    """Сборка и публикация одного релиза."""

    publish_id: str
    site_id: str
    release_id: str
    rendered_pages: int
    changed_pages: int
    state: str = "planned"           # planned | building | published | rejected
    reason: str = ""
    version: int = 1
    timestamps: Timestamps = field(default_factory=Timestamps)

    def __post_init__(self) -> None:
        if self.changed_pages > self.rendered_pages:
            raise ContractError("переписано больше, чем отрисовано — счётчики несогласованы")


@dataclass(frozen=True)
class Deployment:
    """Что именно сейчас работает и откуда оно взялось."""

    deployment_id: str
    site_id: str
    revision: str
    digest: str = ""
    previous_revision: str = ""
    rollback_reference: str = ""
    version: int = 1
    timestamps: Timestamps = field(default_factory=Timestamps)

    def __post_init__(self) -> None:
        if self.revision and len(self.revision) not in (12, 40, 64):
            # Ревизия неизвестной длины — повод остановиться: в 02E ровно такая
            # проверка поймала «SHA» из 42 символов, которого не существовало.
            raise ContractError(f"ревизия неправдоподобной длины: {len(self.revision)}")


@dataclass(frozen=True)
class HealthSnapshot:
    """Снимок здоровья витрины."""

    site_id: str
    http_status: int
    index_age_seconds: int | None = None
    broken_images: int = 0
    player_pages: int | None = None
    checked_at: datetime = field(default_factory=utc_now)
    problems: tuple[str, ...] = ()

    @property
    def healthy(self) -> bool:
        return self.http_status == 200 and not self.problems and self.broken_images == 0


@dataclass(frozen=True)
class Tenant:
    """Витрина как единица владения и доступа."""

    tenant_id: str
    site_ids: tuple[str, ...]
    display_name: str = ""
    version: int = 1


@dataclass(frozen=True)
class User:
    """Лицо. Пароль здесь не хранится и храниться не должен."""

    user_id: str
    roles: tuple[str, ...]
    sites: tuple[str, ...] = ()
    display_name: str = ""
    active: bool = True
    version: int = 1

    def __post_init__(self) -> None:
        if not self.roles:
            raise ContractError(f"{self.user_id}: лицо без ролей ничего не может")


@dataclass(frozen=True)
class CacheTagContract:
    """Тег кэша: что он покрывает и кто вправе его сбрасывать."""

    tag: str
    covers: tuple[str, ...]
    owner: str
    invalidated_by: tuple[str, ...] = ()
    global_purge_allowed: bool = False

    def __post_init__(self) -> None:
        if self.global_purge_allowed:
            raise ContractError(
                f"тег {self.tag}: полная очистка запрещена — она превращает "
                "переживаемый сбой в одновременную поломку всех витрин"
            )


#: Реестр: контракт → версия, владелец, потребители.
REGISTRY: dict[str, dict[str, Any]] = {
    "NormalizedContentDocument": {"version": "1.0", "owner": "Content Engine",
                                  "consumers": ["Site Engine", "SEO Engine", "Control Plane"]},
    "SiteProfile": {"version": "1.0", "owner": "Site Engine",
                    "consumers": ["все движки"]},
    "EditorialOverride": {"version": "1.0", "owner": "Control Plane",
                          "consumers": ["Site Engine", "SEO Engine"]},
    "SeoDocument": {"version": "1.0", "owner": "SEO Engine",
                    "consumers": ["Site Engine"]},
    "MediaAsset": {"version": "1.0", "owner": "Media Engine",
                   "consumers": ["Site Engine", "Control Plane"]},
    "ContentEvent": {"version": "1.0", "owner": "Content Engine",
                     "consumers": ["Scheduler Engine", "Publishing Engine"]},
    "SchedulerJob": {"version": "1.0", "owner": "Scheduler Engine",
                     "consumers": ["Control Plane"]},
    "PublishJob": {"version": "1.0", "owner": "Publishing Engine",
                   "consumers": ["Control Plane"]},
    "Deployment": {"version": "1.0", "owner": "Publishing Engine",
                   "consumers": ["Control Plane"]},
    "HealthSnapshot": {"version": "1.0", "owner": "Scheduler Engine",
                       "consumers": ["Control Plane"]},
    "Tenant": {"version": "1.0", "owner": "Control Plane", "consumers": ["все движки"]},
    "User": {"version": "1.0", "owner": "Control Plane", "consumers": ["Control Plane"]},
    "Role": {"version": "1.0", "owner": "Control Plane", "consumers": ["Control Plane"]},
    "AuditEvent": {"version": "1.0", "owner": "Control Plane", "consumers": ["Control Plane"]},
    "CacheTagContract": {"version": "1.0", "owner": "Site Engine",
                         "consumers": ["Media Engine", "Publishing Engine", "SEO Engine"]},
}
