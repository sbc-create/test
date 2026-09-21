"""Единый контракт адаптера источника оценок."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class SourceFetch:
    """Сырой результат одного источника по одному внешнему идентификатору.

    ``raw_score`` остаётся в том виде, в каком его вернул источник — строкой
    у Kitsu, целым у AniList. Приведение к числу делает нормализация, и
    делает его по контракту источника, а не по догадке адаптера.
    """

    source_key: str
    external_id: str
    found: bool
    raw_score: Any = None
    vote_count: int | None = None
    #: число пользователей, если источник отличает его от числа голосов
    user_count: int | None = None
    score_distribution: dict[str, int] | None = None
    #: Идентификаторы, которые источник объявляет сам (например, AniList
    #: отдаёт ``idMal``). Это независимое свидетельство о том, про какой
    #: тайтл ответ: сравнивать наш идентификатор с ним же, как с «их»
    #: значением, — проверка, которая не может не пройти.
    crosswalk_ids: dict[str, str] = field(default_factory=dict)
    source_rating_date: str = ""
    source_updated_at: str = ""
    provenance_url: str = ""
    #: названия источника — только для проверки сопоставления, не для каталога
    titles: dict[str, str] = field(default_factory=dict)
    year: int | None = None
    kind: str = ""
    episodes: int | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def payload_sha256(self) -> str:
        blob = json.dumps(self.raw_payload, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def content_hash(self) -> str:
        """Хеш только тех полей, изменение которых создаёт новую версию.

        Время ответа и служебные поля сюда не входят: источник, у которого
        оценка не изменилась, не должен порождать новую версию только
        потому, что ответ пришёл в другую секунду.
        """
        material = json.dumps(
            {
                "source": self.source_key,
                "external_id": self.external_id,
                "raw_score": None if self.raw_score is None else str(self.raw_score),
                "vote_count": self.vote_count,
                "user_count": self.user_count,
                "distribution": self.score_distribution,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Capabilities:
    source_key: str
    supports_batch: bool
    max_batch_size: int
    supports_vote_count: bool
    supports_user_count: bool
    supports_distribution: bool
    #: умеет ли источник отдавать «что изменилось с момента X»
    supports_source_side_incremental: bool
    incremental_mode: str
    external_id_space: str
    requires_credential: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_key": self.source_key,
            "supports_batch": self.supports_batch,
            "max_batch_size": self.max_batch_size,
            "supports_vote_count": self.supports_vote_count,
            "supports_user_count": self.supports_user_count,
            "supports_distribution": self.supports_distribution,
            "supports_source_side_incremental": self.supports_source_side_incremental,
            "incremental_mode": self.incremental_mode,
            "external_id_space": self.external_id_space,
            "requires_credential": self.requires_credential,
        }


class HealthState(str):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"
    UNMEASURED = "UNMEASURED"


@runtime_checkable
class UnifiedSourceAdapter(Protocol):
    source_key: str
    adapter_version: str

    def capabilities(self) -> Capabilities: ...

    def fetch_by_external_ids(self, external_ids: list[str]) -> dict[str, SourceFetch]: ...

    def health(self) -> dict[str, Any]: ...
