"""Lords player media viewport must fill the shell (no small centered iframe).

P0 contract:
* `.pl__frame` is a 16:9 relative viewport (not grid+center for media)
* host / video-player / iframe absolute-fill the viewport
* global `iframe{height:auto}` is overridden inside the player
* user-facing note never shows «состояние неизвестно»
* client script re-fits media after SDK injection
"""

from __future__ import annotations

import pathlib
import re

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ИСХОДНИК = КОРЕНЬ / "automation" / "host" / "lords-frontend.py"


def _текст() -> str:
    return ИСХОДНИК.read_text(encoding="utf-8")


def _lords_player_css() -> str:
    текст = _текст()
    m = re.search(
        r"/\* Плеер: полоса вкладок.*?/\* Сезоны и серии\.",
        текст,
        re.S,
    )
    assert m, "не найден CSS-блок Lords-плеера"
    return m.group(0)


def _подпись_fn_source() -> str:
    текст = _текст()
    m = re.search(r"def _подпись_плеера\(код: str\) -> str:.*?(?=\ndef )", текст, re.S)
    assert m
    return m.group(0)


def _client_script() -> str:
    текст = _текст()
    m = re.search(r"СКРИПТ_ПЛЕЕРА_КЛИЕНТ = \"\"\"(.*?)\"\"\"", текст, re.S)
    assert m
    return m.group(1)


class TestPlayerViewportCssContract:
    def test_frame_is_relative_16x9_not_grid_center(self):
        css = _lords_player_css()
        head = css.split("[data-player-state]")[0]
        assert "aspect-ratio:16/9" in css.replace(" ", "")
        assert "place-items:center" not in head
        assert "display:grid" not in head
        assert "position:relative" in css
        assert "width:100%" in css

    def test_host_and_iframe_absolute_fill(self):
        css = _lords_player_css().replace("\n", "")
        assert "[data-player-host]{position:absolute;inset:0" in css
        assert "video-player{position:absolute;inset:0" in css
        assert ".pl__frame iframe,.pl__frame video" in css
        assert "max-width:none !important" in css
        assert "max-height:none !important" in css
        assert "height:100% !important" in css

    def test_global_iframe_height_auto_overridden_in_player(self):
        текст = _текст()
        assert "img,video,iframe,svg{max-width:100%;height:auto;display:block}" in текст
        css = _lords_player_css()
        assert "max-width:none !important" in css
        assert "height:100% !important" in css


class TestPlayerStatusCopy:
    def test_resolving_maps_to_loading_not_unknown(self):
        src = _подпись_fn_source()
        # Lords branch (non-animedia) must not default to «состояние неизвестно».
        lords = src.split('if СЕМЕЙСТВО == "animedia":', 1)[1]
        lords = lords.split("return {", 1)[1]
        assert '"resolving": "Загрузка плеера…"' in lords or \
               '"resolving":"Загрузка плеера…"' in lords.replace(" ", "")
        assert '"active": ""' in lords or '"active":""' in lords.replace(" ", "")
        assert '"ok": ""' in lords or '"ok":""' in lords.replace(" ", "")
        assert "состояние неизвестно" not in lords
        assert '.get(код, "")' in src

    def test_empty_note_hidden(self):
        assert ".pl__note:empty{display:none}" in _текст()


class TestClientFitGuard:
    def test_client_script_fits_shadow_iframe(self):
        скрипт = _client_script()
        assert "fitPlayerTree" in скрипт
        assert "fitMedia" in скрипт
        assert "MutationObserver" in скрипт
        assert "max-width" in скрипт and "none" in скрипт
        assert "состояние неизвестно" not in скрипт
        assert "Загрузка плеера…" in скрипт
        assert "syncNote" in скрипт

    def test_client_script_single_player_query(self):
        скрипт = _client_script()
        assert скрипт.count("querySelector('[data-player]')") == 1
        assert "querySelectorAll('[data-player]')" not in скрипт

    def test_async_refit_on_interval_and_mutation(self):
        скрипт = _client_script()
        assert "fitPlayerTree(node)" in скрипт
        assert скрипт.count("fitPlayerTree") >= 3


class TestFillRatioHelpers:
    """Pure geometry gate used by browser evidence / future e2e."""

    @staticmethod
    def ratios(shell, iframe):
        sw = max(shell["width"], 1)
        sh = max(shell["height"], 1)
        return iframe["width"] / sw, iframe["height"] / sh

    def test_small_centered_fails_gate(self):
        w, h = self.ratios(
            {"width": 1170, "height": 658},
            {"width": 640, "height": 360},
        )
        assert w < 0.98 and h < 0.98

    def test_full_fill_passes_gate(self):
        w, h = self.ratios(
            {"width": 1170, "height": 658},
            {"width": 1170, "height": 658},
        )
        assert w >= 0.98 and h >= 0.98


class TestNoTransformScaleCheat:
    def test_no_scale_workaround_in_player_css(self):
        css = _lords_player_css()
        assert "transform:scale" not in css.replace(" ", "").lower()
        assert "zoom:" not in css.lower()
