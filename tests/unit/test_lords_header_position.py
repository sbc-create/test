"""REQ-LORDS-VISUAL: позиция шапки задаётся токеном профиля.

Паттерн перенесён из Zona (commit d96ae38): `theme.tokens.header_position`
управляет `position` у `.site-header`. Умолчание — прежнее поведение
(`sticky`), поэтому витрина, которая токен не объявляет, не меняется.
Animedia (amd.online): header.sticky = false → `static`.
"""

from __future__ import annotations

import re

from factory.lords import plan as plan_mod
from factory.lords import theme as theme_mod


def _site_header_position(css: str) -> str:
    match = re.search(r"\.site-header\s*\{([^}]*)\}", css)
    assert match, ".site-header rule missing from stylesheet"
    block = match.group(1)
    pos = re.search(r"position:\s*([^;]+);", block)
    assert pos, "position property missing from .site-header"
    return pos.group(1).strip()


class TestHeaderPositionDefaultSticky:
    def test_default_tokens_are_sticky(self):
        assert theme_mod.DEFAULT_TOKENS["header_position"] == "sticky"

    def test_profile_without_override_stays_sticky(self):
        profiles = plan_mod.load_profiles()
        css = theme_mod.stylesheet(profiles["lords-general"])
        assert _site_header_position(css) == "sticky"

    def test_empty_profile_stays_sticky(self):
        css = theme_mod.stylesheet({"profile": "probe", "theme": {"tokens": {}}})
        assert _site_header_position(css) == "sticky"


class TestAnimediaHeaderStatic:
    def test_animedia_portal_declares_static(self):
        profiles = plan_mod.load_profiles()
        tokens = (profiles["animedia-portal"].get("theme") or {}).get("tokens") or {}
        assert tokens.get("header_position") == "static"

    def test_animedia_stylesheet_uses_static(self):
        profiles = plan_mod.load_profiles()
        css = theme_mod.stylesheet(profiles["animedia-portal"])
        assert _site_header_position(css) == "static"
