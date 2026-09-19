"""Тонкий adapter: старые импорты factory.lords.rating_gateway → factory.ratings.

Историческое размещение в lords/ не означает, что рейтинги принадлежат только
Lords. Реализация — в factory.ratings.gateway.
"""

from __future__ import annotations

from factory.ratings.gateway import (  # noqa: F401
    RatingGateway,
    format_score,
    format_ui_line,
    format_votes,
)

__all__ = ["RatingGateway", "format_score", "format_ui_line", "format_votes"]
