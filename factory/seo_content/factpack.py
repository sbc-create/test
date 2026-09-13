"""Неизменяемый пакет фактов, из которого только и может вырасти текст.

Устройство модуля отвечает на один вопрос: откуда взялось каждое слово.
Ответ даётся не проверкой готового текста, а конструкцией пакета — значения
поля не существует, пока нет факта с этим `field_path`. Поэтому «год 2019»
нельзя получить, не предъявив источник: обращение к несуществующему полю
возвращает `None`, и генератор обязан выбрать `NEEDS_FACTS` или `OMIT`.

Пакет строится из канонического события и после сборки не меняется. Правка
фактов — это новый пакет с новым `sha256`, а значит и новая ревизия
черновика: старый текст не может тихо пережить смену данных, на которых он
построен.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from enum import Enum
from typing import Any, Iterable, Mapping

#: Канонические события входа. SEO не обходит витрину в поисках новинок:
#: появление и правка контента приходят событием, иначе источник изменения
#: неизвестен и снимок фактов не к чему привязать.
EVENTS = (
    "title.created",
    "title.updated",
    "season.created",
    "season.updated",
    "episode.created",
    "episode.updated",
    "metadata.corrected",
)

ENTITY_TYPES = ("title", "season", "episode")

#: Какую сущность описывает событие.
EVENT_ENTITY = {
    "title.created": "title",
    "title.updated": "title",
    "season.created": "season",
    "season.updated": "season",
    "episode.created": "episode",
    "episode.updated": "episode",
    # Правка метаданных адресуется той сущности, которую правят: событие
    # несёт entity_type само.
    "metadata.corrected": None,
}

SCHEMA_VERSION = "seo.fact_pack/1.0.0"
RESOURCE_KIND = "seo.fact_pack"


class ConflictStatus(str, Enum):
    """Состояние факта относительно других источников того же поля."""

    NONE = "NONE"              # единственный источник либо источники согласны
    CONFLICT = "CONFLICT"      # источники расходятся; выбор делает не модель
    RESOLVED = "RESOLVED"      # расхождение снято владельцем данных, не нами
    SUPERSEDED = "SUPERSEDED"  # вытеснен более поздним снимком того же источника


class SpoilerLevel(str, Enum):
    NONE = "NONE"        # ничего сверх аннотации
    PREMISE = "PREMISE"  # завязка: то, что известно из первых минут
    MIDPOINT = "MIDPOINT"
    FULL = "FULL"


class VideoAvailability(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"  # не измеряли; утверждать о доступности нельзя


class FactPackError(ValueError):
    """Пакет собрать нельзя. Код — машинный, текст — для человека."""

    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


#: Поля, которые обязаны иметь источник, если присутствуют. Список закрыт
#: намеренно: свободная форма позволила бы завести «поле» на ходу.
FIELD_PATHS = (
    "/canonical_title_ru",
    "/original_title",
    "/alternative_titles",
    "/work_type",
    "/year",
    "/year_end",
    "/countries",
    "/genres",
    "/age_rating",
    "/release_status",
    "/season_count",
    "/declared_episode_count",
    "/actual_episode_count",
    "/season_number",
    "/episode_in_season_number",
    "/episode_absolute_number",
    "/episode_source_number",
    "/episode_display_number",
    "/synopsis_short",
    "/synopsis_long",
    "/characters",
    "/creators",
    "/previous_season_ref",
    "/previous_episode_ref",
    "/spoiler_level",
    "/video_availability",
    "/season_synopsis",
    "/episode_synopsis",
    "/episode_title",
    "/distinctive_feature",
    "/premise_subject",
    "/premise_conflict",
    "/setting",
    "/season_arc",
    "/season_position",
    "/episode_focus",
    "/studio",
    "/franchise_id",
    "/source_material",
)

_ПУТЬ = re.compile(r"^/[a-z][a-z0-9_]*$")


def canonical_json(данные: Any) -> str:
    """Каноническая форма для отпечатка: один порядок ключей, один пробел."""
    return json.dumps(данные, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), default=str)


def sha256_of(данные: Any) -> str:
    return hashlib.sha256(canonical_json(данные).encode("utf-8")).hexdigest()


@dataclasses.dataclass(frozen=True, slots=True)
class Fact:
    """Одно утверждение об одном поле, привязанное к снимку источника.

    `value` хранится рядом с происхождением, а не отдельно от него: значение
    без источника не может быть построено, потому что конструктор требует
    оба.
    """

    fact_id: str
    source_id: str
    provider: str
    retrieved_at: str
    snapshot_hash: str
    field_path: str
    value: Any
    confidence: float
    conflict_status: ConflictStatus = ConflictStatus.NONE
    #: Лицензия/политика использования источника. Отсутствие — не «свободно».
    source_license: str = "UNKNOWN"

    def __post_init__(self) -> None:
        if not _ПУТЬ.match(self.field_path):
            raise FactPackError("FIELD_PATH_MALFORMED", self.field_path)
        if self.field_path not in FIELD_PATHS:
            raise FactPackError("FIELD_PATH_UNKNOWN", self.field_path)
        if not (0.0 <= float(self.confidence) <= 1.0):
            raise FactPackError("CONFIDENCE_OUT_OF_RANGE", str(self.confidence))
        for поле in ("fact_id", "source_id", "provider", "retrieved_at",
                     "snapshot_hash"):
            if not str(getattr(self, поле)).strip():
                raise FactPackError("FACT_PROVENANCE_INCOMPLETE", поле)

    def to_dict(self) -> dict[str, Any]:
        д = dataclasses.asdict(self)
        д["conflict_status"] = self.conflict_status.value
        return д


@dataclasses.dataclass(frozen=True, slots=True)
class SEOFactPack:
    """Снимок фактов о сущности. После сборки не меняется.

    Скалярных полей у пакета нет — есть факты. Любое значение достаётся
    методом `value`, и если факта нет, значения нет тоже. Это единственная
    причина, по которой «выдумать год ради длины предложения» невозможно:
    выдумывать пришлось бы факт с источником и снимком.
    """

    site_id: str
    entity_type: str
    entity_id: str
    title_id: str
    season_id: str | None
    episode_id: str | None
    locale: str
    facts: tuple[Fact, ...]
    event_type: str
    event_id: str
    version: int = 1
    schema_version: str = SCHEMA_VERSION
    resource_kind: str = RESOURCE_KIND

    def __post_init__(self) -> None:
        if self.entity_type not in ENTITY_TYPES:
            raise FactPackError("ENTITY_TYPE_UNKNOWN", self.entity_type)
        if self.event_type not in EVENTS:
            raise FactPackError("EVENT_TYPE_UNKNOWN", self.event_type)
        if self.entity_type == "season" and not self.season_id:
            raise FactPackError("SEASON_ID_REQUIRED", self.entity_id)
        if self.entity_type == "episode" and not self.episode_id:
            raise FactPackError("EPISODE_ID_REQUIRED", self.entity_id)
        видели: set[str] = set()
        for ф in self.facts:
            if ф.fact_id in видели:
                raise FactPackError("FACT_ID_DUPLICATE", ф.fact_id)
            видели.add(ф.fact_id)

    # --- доступ к значениям ------------------------------------------------

    def facts_for(self, field_path: str) -> tuple[Fact, ...]:
        живые = tuple(ф for ф in self.facts
                      if ф.field_path == field_path
                      and ф.conflict_status is not ConflictStatus.SUPERSEDED)
        return живые

    def value(self, field_path: str) -> Any:
        """Значение поля или `None`, если факта нет.

        При расхождении источников значение не выдаётся: выбрать «удобный»
        вариант — это и есть выдумывание. Вызывающий обязан проверить
        `conflicts()` и вернуть `FACT_CONFLICT`.
        """
        живые = self.facts_for(field_path)
        if not живые:
            return None
        значения = {canonical_json(ф.value) for ф in живые}
        if len(значения) > 1:
            return None
        if any(ф.conflict_status is ConflictStatus.CONFLICT for ф in живые):
            return None
        return живые[0].value

    def fact_id_for(self, field_path: str) -> str | None:
        живые = self.facts_for(field_path)
        return живые[0].fact_id if живые and self.value(field_path) is not None else None

    def has(self, field_path: str) -> bool:
        return self.value(field_path) is not None

    def conflicts(self) -> tuple[str, ...]:
        """Поля, по которым источники расходятся."""
        спорные: set[str] = set()
        for путь in {ф.field_path for ф in self.facts}:
            живые = self.facts_for(путь)
            if not живые:
                continue
            if any(ф.conflict_status is ConflictStatus.CONFLICT for ф in живые):
                спорные.add(путь)
            elif len({canonical_json(ф.value) for ф in живые}) > 1:
                спорные.add(путь)
        return tuple(sorted(спорные))

    def sources(self) -> tuple[dict[str, str], ...]:
        видели: dict[str, dict[str, str]] = {}
        for ф in self.facts:
            видели.setdefault(ф.source_id, {
                "source_id": ф.source_id, "provider": ф.provider,
                "source_license": ф.source_license})
        return tuple(видели[k] for k in sorted(видели))

    # --- отпечаток ---------------------------------------------------------

    def payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "resource_kind": self.resource_kind,
            "site_id": self.site_id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "title_id": self.title_id,
            "season_id": self.season_id,
            "episode_id": self.episode_id,
            "locale": self.locale,
            "version": self.version,
            "event_type": self.event_type,
            "event_id": self.event_id,
            "facts": [ф.to_dict() for ф in
                      sorted(self.facts, key=lambda f: (f.field_path, f.fact_id))],
        }

    @property
    def sha256(self) -> str:
        """Отпечаток пакета.

        `event_id` в отпечаток НЕ входит, хотя в записи присутствует:
        повторная доставка того же содержимого другим событием обязана дать
        тот же отпечаток, иначе дубль события породил бы новую ревизию текста
        без изменения фактов. Происхождение при этом не теряется — оно
        хранится рядом, просто не участвует в сравнении.
        """
        тело = {k: v for k, v in self.payload().items() if k != "event_id"}
        return sha256_of(тело)

    def with_facts(self, facts: Iterable[Fact], *, event_type: str,
                   event_id: str) -> "SEOFactPack":
        """Новая ревизия. Прежний экземпляр не затрагивается."""
        return dataclasses.replace(self, facts=tuple(facts),
                                   version=self.version + 1,
                                   event_type=event_type, event_id=event_id)


def from_event(событие: Mapping[str, Any]) -> SEOFactPack:
    """Собрать пакет из канонического события.

    Событие несёт факты вместе с происхождением. Если оно приносит значение
    без источника, пакет не собирается: это и есть граница, на которой
    выдуманные данные останавливаются.
    """
    тип = событие.get("event_type")
    if тип not in EVENTS:
        raise FactPackError("EVENT_TYPE_UNKNOWN", str(тип))

    entity_type = событие.get("entity_type") or EVENT_ENTITY.get(тип)
    if entity_type is None:
        raise FactPackError(
            "ENTITY_TYPE_REQUIRED",
            f"{тип} не указывает сущность: правка метаданных адресуется той "
            f"сущности, которую правят")

    сырые = событие.get("facts") or []
    факты: list[Fact] = []
    for i, ф in enumerate(сырые):
        отсутствуют = [k for k in ("source_id", "provider", "retrieved_at",
                                   "snapshot_hash", "field_path")
                       if not str(ф.get(k, "")).strip()]
        if отсутствуют:
            raise FactPackError(
                "FACT_PROVENANCE_INCOMPLETE",
                f"факт #{i} ({ф.get('field_path', '?')}) без "
                f"{', '.join(отсутствуют)}: значение без источника не факт")
        факты.append(Fact(
            fact_id=str(ф.get("fact_id") or f"f{i:04d}"),
            source_id=str(ф["source_id"]), provider=str(ф["provider"]),
            retrieved_at=str(ф["retrieved_at"]),
            snapshot_hash=str(ф["snapshot_hash"]),
            field_path=str(ф["field_path"]), value=ф.get("value"),
            confidence=float(ф.get("confidence", 1.0)),
            conflict_status=ConflictStatus(ф.get("conflict_status", "NONE")),
            source_license=str(ф.get("source_license") or "UNKNOWN"),
        ))

    for обязательное in ("site_id", "entity_id", "title_id", "event_id"):
        if not str(событие.get(обязательное, "")).strip():
            raise FactPackError("EVENT_FIELD_MISSING", обязательное)

    return SEOFactPack(
        site_id=str(событие["site_id"]), entity_type=entity_type,
        entity_id=str(событие["entity_id"]), title_id=str(событие["title_id"]),
        season_id=(str(событие["season_id"])
                   if событие.get("season_id") is not None else None),
        episode_id=(str(событие["episode_id"])
                    if событие.get("episode_id") is not None else None),
        locale=str(событие.get("locale") or "ru"), facts=tuple(факты),
        event_type=тип, event_id=str(событие["event_id"]),
        version=int(событие.get("version") or 1),
    )
