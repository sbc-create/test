"""Рендерер витрин Lords: статические релизы с переключением симлинка.

Отдельный файл, а не соседний класс в адаптере каталога: поставщик и
рендерер — разные модули реестра с разными разрешёнными зависимостями, и
гейт границ проверяет это по файлу. Пока оба жили вместе, файл требовал
прав обоих модулей сразу — то есть границы не было.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from factory.site_engine.profiles import SiteProfile


@dataclass
class LordsRendererAdapter:
    """Статический рендерер Lords.

    Живой код рендера остаётся на месте; адаптер сообщает движку, что этот тип
    сайта существует и какими свойствами обладает. Ровно этого не хватало
    `factory.build`, чтобы не импортировать `factory.lords` напрямую.
    """

    name: str = "lords-static"
    render_mode: str = "static"

    def supports(self, profile: SiteProfile) -> bool:
        return profile.render_mode == "static" and profile.site_type == "video-showcase"

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "render_mode": self.render_mode,
            "release_layout": "/srv/lords/<site>/releases/<sha12> + симлинк current",
            "rollback": "переключение симлинка, без пересборки и простоя",
            "owns_data": False,
            "emits_events": False,
        }
