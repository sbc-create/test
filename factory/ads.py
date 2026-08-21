"""Рекламный контур VK/Adman/AdTech.

Слой рекламы отделён от слоя контента. Без переданного contract рекламные слоты не
рендерятся вовсе, но резервирование размеров сохраняется, чтобы включение рекламы
позже не создавало сдвиг макета.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from factory.errors import BlockedRights


@dataclass(frozen=True)
class AdSlot:
    placement_id: str
    height: int
    html: str = ""


class AdsAdapter(Protocol):
    name: str

    def slots(self, page_type: str) -> list[AdSlot]: ...
    def allowed_events(self) -> list[str]: ...


class DisabledAds:
    name = "disabled"

    def slots(self, page_type: str) -> list[AdSlot]:
        return []

    def allowed_events(self) -> list[str]:
        return []


class MockAds:
    """Только staging: резервирует размер, не загружает никаких внешних скриптов."""

    name = "mock"

    def __init__(self, placements: list[dict]) -> None:
        self._placements = placements or []

    def slots(self, page_type: str) -> list[AdSlot]:
        out: list[AdSlot] = []
        for placement in self._placements:
            if page_type in (placement.get("page_types") or []):
                size = placement.get("reserved_size") or {}
                out.append(
                    AdSlot(
                        str(placement.get("placement_id")),
                        int(size.get("height") or 250),
                        '<p class="ad-placeholder">Рекламный слот зарезервирован (staging). '
                        "Внешние скрипты не подключаются до передачи contract.</p>",
                    )
                )
        return out

    def allowed_events(self) -> list[str]:
        return []


class OfficialAds:
    name = "official"

    def __init__(self, contract: dict | None, placements: list[dict]) -> None:
        if not contract:
            raise BlockedRights(
                "Рекламный адаптер official требует переданного contract VK/Adman/AdTech.",
                field="advertising.contract_ref",
                required_input="Contract с placement/product/video/timestamp mappings и перечнем разрешённых событий",
                blocks_stage="BUILDING",
            )
        self._contract = contract
        self._placements = placements or []

    def slots(self, page_type: str) -> list[AdSlot]:
        templates = self._contract.get("slot_templates") or {}
        out: list[AdSlot] = []
        for placement in self._placements:
            if page_type not in (placement.get("page_types") or []):
                continue
            pid = str(placement.get("placement_id"))
            template = templates.get(pid)
            if not template:
                raise BlockedRights(
                    f"В contract нет разметки для placement «{pid}».",
                    field="advertising.placements",
                    required_input="slot_templates для каждого переданного placement_id",
                    blocks_stage="BUILDING",
                )
            size = placement.get("reserved_size") or {}
            out.append(AdSlot(pid, int(size.get("height") or 250), str(template)))
        return out

    def allowed_events(self) -> list[str]:
        return list(self._contract.get("allowed_events") or [])


def build_ads(package: dict, contract: dict | None = None) -> AdsAdapter:
    ads = package.get("advertising") or {}
    if not ads.get("enabled") or ads.get("adapter", "disabled") == "disabled":
        return DisabledAds()
    if ads.get("adapter") == "mock":
        if package.get("environment") == "production":
            raise BlockedRights(
                "Mock рекламного контура технически недоступен в production.",
                field="advertising.adapter",
                required_input="adapter: official",
                blocks_stage="PRODUCTION_DEPLOY",
            )
        return MockAds(ads.get("placements") or [])
    return OfficialAds(contract, ads.get("placements") or [])
