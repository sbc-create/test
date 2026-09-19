"""Централизованные CSS/HTML selectors для AMD.online detail pages.

Не разбрасывать selectors по коду — только здесь и в fixture-тестах.
"""

from __future__ import annotations

# URL: https://amd.online/{numeric-id}-{slug}.html
URL_ID_RE = r"^https://amd\.online/(?P<id>\d+)-(?P<slug>[^/?#]+)\.html$"

SELECTORS = {
    "title_ru": {"tag": "h1"},
    "title_original": {"class": "amd-sub"},
    "rating_block": {"class_contains": "multirating", "attr": "data-id"},
    "score": {"class": "multirating-itog-rateval"},
    "vote_count": {"class": "multirating-itog-votes"},
    "story_score": {"data-area": "story"},
    "characters_score": {"data-area": "actors"},  # AMD labels characters as actors
    "art_score": {"data-area": "graph"},
    "voice_score": {"data-area": "sound"},
}

PARSER_VERSION = "amd_online_html/1.0.0"
PERMISSION_VERSION = "pending_written_permission"
SOURCE_KEY = "amd_online"
CANONICAL_ORIGIN = "https://amd.online"

COMPONENT_AREAS = {
    "story": "story_score",
    "actors": "characters_score",
    "graph": "art_score",
    "sound": "voice_score",
}
