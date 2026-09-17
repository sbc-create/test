"""Рендерер аниме-порталов: страницы собираются приложением на запросе."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from factory.site_engine.profiles import SiteProfile


@dataclass
class YummyRendererAdapter:
    """Гибридный рендерер Yummy: страницы собираются приложением на запросе."""

    name: str = "yummy-hybrid"
    render_mode: str = "hybrid"

    def supports(self, profile: SiteProfile) -> bool:
        return profile.render_mode == "hybrid" and profile.site_type == "anime-portal"

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "render_mode": self.render_mode,
            "release_layout": "общий образ на три тенанта, метка revision в образе",
            "rollback": "возврат к запомненному образу; базы резервируются до выкладки",
            "owns_data": False,
            "emits_events": False,
        }
