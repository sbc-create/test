"""Владение полями карточки: кто вправе записать что.

Карточка произведения собирается из трёх разных источников, и у каждого своя
правда:

* **каталог** сообщает факты — название, год, сезоны, серии, доступность;
* **внешние оценки** приходят из общего сбора и принадлежат только себе;
* **SEO** пишет свои тексты и мета;
* **ручная правка** старше обоих автоматов и держится до явной отмены.

Правило «последний записавший победил» к карточке целиком не применяется, и это
главное, ради чего модуль существует. Обновление каталога, применённое целиком,
стирало SEO-описание; следующая SEO-правка возвращала описание и обнуляла число
серий. Круг замыкался, и каждый раз виноват был «сбой синхронизации».

Здесь запись адресуется устойчивому UUID и ожидаемой ревизии. Владелец пишет
только свои поля; попытка записать чужое — ошибка, а не тихое игнорирование.
Расхождение ревизий фиксируется конфликтом, а не переписывается молча.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

SCHEMA_VERSION = "1.0"


class Owner(str, Enum):
    CATALOG = "catalog"
    EXTERNAL_RATINGS = "external_ratings"
    SEO = "seo"
    MANUAL = "manual"


#: Кто чем владеет. Поля перечислены поимённо: «всё остальное» однажды включило
#: бы в себя поле, о котором никто не думал.
FIELD_OWNER: dict[str, Owner] = {
    "title": Owner.CATALOG,
    "original_name": Owner.CATALOG,
    "year": Owner.CATALOG,
    "kind": Owner.CATALOG,
    "seasons": Owner.CATALOG,
    "episodes": Owner.CATALOG,
    "availability": Owner.CATALOG,
    "poster_url": Owner.CATALOG,
    "genres": Owner.CATALOG,
    # Адресация плеера принадлежит каталогу: SEO не вправе переназначить
    # источник воспроизведения, а редактор — подставить другой идентификатор
    # вместо отсутствующего.
    "playback": Owner.CATALOG,
    "rating_external": Owner.EXTERNAL_RATINGS,
    "rating_external_source": Owner.EXTERNAL_RATINGS,
    "seo_title": Owner.SEO,
    "seo_description": Owner.SEO,
    "seo_text": Owner.SEO,
    "meta_keywords": Owner.SEO,
}


class OwnershipError(RuntimeError):
    pass


class NotFieldOwner(OwnershipError):
    """Владелец пишет только свои поля."""


class RevisionConflict(OwnershipError):
    """Запись основана на ревизии старее текущей. Конфликт фиксируется."""

    def __init__(self, message: str, *, expected: int, actual: int,
                 fields: tuple[str, ...]) -> None:
        super().__init__(message)
        self.expected = expected
        self.actual = actual
        self.fields = fields


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class FieldValue:
    value: Any
    owner: Owner
    revision: int
    updated_at: str
    #: Ручная правка объявляется закреплением: автомат её не трогает, пока
    #: закрепление не снято явно.
    pinned: bool = False
    source: str | None = None


@dataclass
class Record:
    """Карточка произведения, собранная по владельцам полей."""

    title_uuid: str
    site_id: str
    fields: dict[str, FieldValue] = field(default_factory=dict)
    revision: int = 0
    conflicts: list[dict[str, Any]] = field(default_factory=list)

    def value(self, name: str) -> Any:
        found = self.fields.get(name)
        return found.value if found else None

    def view(self) -> dict[str, Any]:
        return {name: fv.value for name, fv in sorted(self.fields.items())}

    def owner_of(self, name: str) -> Owner | None:
        found = self.fields.get(name)
        return found.owner if found else FIELD_OWNER.get(name)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "title_uuid": self.title_uuid,
            "site_id": self.site_id,
            "revision": self.revision,
            "fields": {
                name: {"value": fv.value, "owner": fv.owner.value,
                       "revision": fv.revision, "updated_at": fv.updated_at,
                       "pinned": fv.pinned, "source": fv.source}
                for name, fv in sorted(self.fields.items())
            },
            "conflicts": list(self.conflicts),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Record:
        return cls(
            title_uuid=raw["title_uuid"],
            site_id=raw["site_id"],
            revision=raw.get("revision", 0),
            fields={
                name: FieldValue(value=item["value"], owner=Owner(item["owner"]),
                                 revision=item["revision"], updated_at=item["updated_at"],
                                 pinned=item.get("pinned", False),
                                 source=item.get("source"))
                for name, item in (raw.get("fields") or {}).items()
            },
            conflicts=list(raw.get("conflicts") or []),
        )


@dataclass(frozen=True)
class Change:
    """Заявка на запись: кто, во что, какие поля, от какой ревизии."""

    title_uuid: str
    owner: Owner
    fields: dict[str, Any]
    expected_revision: int | None = None
    source: str | None = None
    reason: str = ""

    def __post_init__(self) -> None:
        if not self.title_uuid:
            raise OwnershipError("запись адресуется устойчивому UUID, а не названию")
        if not self.fields:
            raise OwnershipError("пустая заявка ничего не меняет")


def check_owner(owner: Owner, names: tuple[str, ...]) -> None:
    foreign = []
    for name in names:
        declared = FIELD_OWNER.get(name)
        if declared is None:
            raise NotFieldOwner(
                f"поле {name!r} не числится ни за одним владельцем; "
                "новое поле сначала получает владельца, потом значение"
            )
        if owner is not Owner.MANUAL and declared is not owner:
            foreign.append((name, declared.value))
    if foreign:
        raise NotFieldOwner(
            f"{owner.value} пытается записать чужие поля: "
            + ", ".join(f"{n} принадлежит {o}" for n, o in foreign)
        )


def apply(record: Record, change: Change, *, now: str | None = None) -> Record:
    """Применить заявку. Возвращает ту же запись, изменённую на месте.

    Конфликт ревизий не подавляется и не перезаписывается: он поднимается
    исключением и, если вызывающий его ловит, остаётся в `record.conflicts`.
    """
    if change.title_uuid != record.title_uuid:
        raise OwnershipError(
            f"заявка на {change.title_uuid}, запись — {record.title_uuid}")
    names = tuple(change.fields)
    check_owner(change.owner, names)

    if change.expected_revision is not None and change.expected_revision != record.revision:
        conflict = {
            "at": now or utc_now(),
            "owner": change.owner.value,
            "fields": list(names),
            "expected_revision": change.expected_revision,
            "actual_revision": record.revision,
            "reason": change.reason,
            "resolution": "not_applied",
        }
        record.conflicts.append(conflict)
        raise RevisionConflict(
            f"{change.owner.value} пишет от ревизии {change.expected_revision}, "
            f"а запись уже {record.revision}: расхождение зафиксировано, "
            "а не перезаписано",
            expected=change.expected_revision, actual=record.revision, fields=names,
        )

    stamp = now or utc_now()
    record.revision += 1
    for name, value in change.fields.items():
        existing = record.fields.get(name)
        if existing and existing.pinned and change.owner is not Owner.MANUAL:
            # Закреплённое значение автомат не трогает. Это не ошибка — это
            # решение редактора, и оно старше обновления источника.
            record.conflicts.append({
                "at": stamp, "owner": change.owner.value, "fields": [name],
                "resolution": "skipped_pinned",
                "reason": "значение закреплено ручной правкой",
            })
            continue
        record.fields[name] = FieldValue(
            value=value,
            owner=FIELD_OWNER.get(name, change.owner),
            revision=record.revision,
            updated_at=stamp,
            pinned=(change.owner is Owner.MANUAL),
            source=change.source,
        )
    return record


def unpin(record: Record, name: str) -> Record:
    """Снять закрепление ручной правки — только явно."""
    existing = record.fields.get(name)
    if not existing:
        raise OwnershipError(f"поля {name} в записи нет")
    existing.pinned = False
    return record


@dataclass
class ContentRevision:
    """Ревизия содержимого сайта.

    Живёт отдельно от версии кода: выкат кода не имеет права откатить
    содержимое, а правка содержимого — понизить версию кода.
    """

    value: int = 0
    updated_at: str = ""

    def advance(self, now: str | None = None) -> int:
        self.value += 1
        self.updated_at = now or utc_now()
        return self.value


def guard_content_revision(*, incoming: int, current: int, operation: str) -> None:
    """Выкат кода не перезаписывает более свежее содержимое."""
    if incoming < current:
        raise RevisionConflict(
            f"{operation} несёт content_revision {incoming}, а на месте уже "
            f"{current}: выкат кода не откатывает содержимое",
            expected=incoming, actual=current, fields=(),
        )


def merge_document(record: Record) -> str:
    return json.dumps(record.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)
