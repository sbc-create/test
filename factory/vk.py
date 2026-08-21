"""Адаптеры белого VK-плеера.

Поверхность интерфейса намеренно узкая. Методов, которых нет в переданном contract,
здесь нет и быть не может: выдумывать SDK-вызовы запрещено (§9).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from factory.errors import BlockedRights

AVAILABLE = "available"
UNAVAILABLE = "unavailable"
UNKNOWN = "unknown"


@dataclass(frozen=True)
class VideoDescriptor:
    video_ref: str
    availability: str = UNKNOWN
    #: Только поля, явно разрешённые contract. Пусто = ничего не разрешено.
    allowed_fields: dict = field(default_factory=dict)


class VideoPlayerAdapter(Protocol):
    name: str

    def resolve(self, video_ref: str) -> VideoDescriptor: ...
    def embed_html(self, descriptor: VideoDescriptor) -> str: ...
    def aspect_ratio(self) -> str: ...
    def may_emit_video_object(self, descriptor: VideoDescriptor) -> bool: ...


class DisabledPlayer:
    """Плеер выключен: страницы рендерятся в состоянии content_unavailable."""

    name = "disabled"

    def resolve(self, video_ref: str) -> VideoDescriptor:
        return VideoDescriptor(video_ref, UNKNOWN)

    def embed_html(self, descriptor: VideoDescriptor) -> str:
        return ""

    def aspect_ratio(self) -> str:
        return "16 / 9"

    def may_emit_video_object(self, descriptor: VideoDescriptor) -> bool:
        return False


class MockPlayer:
    """Только staging. Нейтральный контейнер вместо плеера: contract не передан,
    поэтому реальная embed-схема неизвестна и не выдумывается."""

    name = "mock"

    def __init__(self, catalog: dict | None = None) -> None:
        self._catalog = catalog or {}

    def resolve(self, video_ref: str) -> VideoDescriptor:
        entry = self._catalog.get(video_ref) or {}
        return VideoDescriptor(video_ref, entry.get("availability", UNAVAILABLE), entry.get("allowed_fields", {}))

    def embed_html(self, descriptor: VideoDescriptor) -> str:
        if descriptor.availability != AVAILABLE:
            return ""
        return (
            '<div class="player-mock" role="region" aria-label="Видеоплеер (staging-заглушка)" '
            f'data-video-ref="{descriptor.video_ref}">'
            "<p>Staging: белый VK-плеер подключается после передачи contract. "
            "Контейнер сохраняет размеры, чтобы не возникало сдвига макета.</p></div>"
        )

    def aspect_ratio(self) -> str:
        return "16 / 9"

    def may_emit_video_object(self, descriptor: VideoDescriptor) -> bool:
        # Заглушка не является видимым видео → VideoObject запрещён (HR-6).
        return False


class OfficialPlayer:
    """Реальный белый плеер. Требует переданного contract: без него — BLOCKED_RIGHTS."""

    name = "official"

    def __init__(self, contract: dict | None) -> None:
        if not contract:
            raise BlockedRights(
                "Адаптер official требует переданного contract белого VK-плеера.",
                field="vk_video.contract_ref",
                required_input="Официальный/внутренний contract: embed-схема, параметры, разрешённые режимы воспроизведения",
                blocks_stage="BUILDING",
            )
        self._contract = contract

    def resolve(self, video_ref: str) -> VideoDescriptor:
        catalog = self._contract.get("catalog") or {}
        entry = catalog.get(video_ref) or {}
        return VideoDescriptor(video_ref, entry.get("availability", UNKNOWN), entry.get("allowed_fields", {}))

    def embed_html(self, descriptor: VideoDescriptor) -> str:
        template = self._contract.get("embed_template")
        if not template:
            raise BlockedRights(
                "В contract нет embed_template — схема встраивания плеера не передана.",
                field="vk_video.contract_ref",
                required_input="embed_template из официального contract",
                blocks_stage="BUILDING",
            )
        if descriptor.availability != AVAILABLE:
            return ""
        return str(template).replace("{video_ref}", descriptor.video_ref)

    def aspect_ratio(self) -> str:
        return str(self._contract.get("aspect_ratio") or "16 / 9")

    def may_emit_video_object(self, descriptor: VideoDescriptor) -> bool:
        return descriptor.availability == AVAILABLE and bool(self._contract.get("allows_video_object"))


def build_player(package: dict, contract: dict | None = None, catalog: dict | None = None) -> VideoPlayerAdapter:
    vk = package.get("vk_video") or {}
    environment = package.get("environment")
    adapter = vk.get("adapter", "disabled")
    if not vk.get("enabled") or adapter == "disabled":
        return DisabledPlayer()
    if adapter == "mock":
        if environment == "production":
            raise BlockedRights(
                "Mock-адаптер VK технически недоступен в production.",
                field="vk_video.adapter",
                required_input="adapter: official с подтверждённым contract",
                blocks_stage="PRODUCTION_DEPLOY",
            )
        return MockPlayer(catalog)
    return OfficialPlayer(contract)
