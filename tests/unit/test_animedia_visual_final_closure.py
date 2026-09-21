"""Animedia visual final closure gates (1.2.4): shelves, related, footer, ads, theme."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.unit.test_animedia_visual_finalization import _load, _вид  # noqa: E402


@pytest.fixture
def fe(tmp_path):
    return _load(tmp_path, version="1.2.4")


class TestVisualFinalClosure:
    def test_design_124_tokens_and_six_col_grid(self, fe):
        mod, _, _ = fe
        assert mod.ВЕРСИЯ == "1.2.4"
        assert "1.2.4" in mod.ОФОРМЛЕНИЕ_ВЕРСИИ
        css = mod.СЕМЕЙСТВА_1_1["animedia"]["стиль"]()
        assert "--a-content-max:1760px" in css
        assert "calc(100% - var(--page-gutters))" in css
        assert "min-width:1200px){.zg{grid-template-columns:repeat(7" in css
        assert "min-width:1800px){.zg{grid-template-columns:repeat(10" in css
        assert "min-width:1024px){.zg{grid-template-columns:repeat(5" in css
        assert "max-height:320px" in css
        # BLOCK_02 (b74739f) swapped the hero poster's hard 152x214 for a
        # declared 2:3 frame that fills its track. The frame is still declared,
        # so the poster still cannot be sized by the image it loads.
        assert ".ahero .zt__p{border-radius:10px;width:100%;aspect-ratio:2/3" in css
        assert ".ahome-eps .aeps__thumb{width:60px" in css
        assert "[data-player-state][hidden]" in css
        assert "height:100% !important" in css
        assert "img,video,iframe" not in mod.АНИМЕДИА_СТИЛЬ

    def test_empty_ad_collapse_css(self, fe):
        # The collapse rule later gained min-height/max-height, so an exact
        # substring no longer matches. Assert the properties instead: a disabled
        # slot must take no space at all, not merely be invisible.
        mod, _, _ = fe
        css = mod.АНИМЕДИА_СТИЛЬ
        начало = css.find(".zad,.zad-home,.zad-mid,.zad-title{")
        assert начало >= 0, "ad slots have no collapse rule"
        правило = css[начало: css.find("}", начало) + 1]
        for свойство in ("display:none", "height:0", "min-height:0", "max-height:0",
                         "margin:0", "padding:0", "border:0", "overflow:hidden"):
            assert свойство in правило, (свойство, правило)

    def test_home_has_collapsed_ad_slots(self, fe):
        mod, catalog, details = fe
        html = _вид(mod, catalog, details).главная()
        assert 'data-ad-slot="home-after-hero"' in html
        assert 'data-ad-enabled="0"' in html
        assert 'data-ad-slot="home-mid-content"' in html

    def test_theme_toggle_and_persistence_script(self, fe):
        mod, catalog, details = fe
        html = _вид(mod, catalog, details).главная()
        assert "data-theme-toggle" in html
        assert "animedia-theme" in mod.СКРИПТ_АНИМЕДИА_ШАПКА
        assert "localStorage" in mod.СКРИПТ_АНИМЕДИА_ШАПКА

    def test_footer_compact_no_placeholder_genres(self, fe):
        mod, catalog, details = fe
        html = _вид(mod, catalog, details).подвал()
        assert "zft__inner" in html
        assert "zft__grid" not in html
        assert "появятся из снимка" not in html
        # B14 запретил внутренние знаки в подвале: прежняя стадия требовала
        # значок «Animedia <версия> · <коммит>», и он был на обоих боевых
        # доменах. Провенанс живёт в заголовках ответа и манифесте релиза.
        assert "Animedia 1.2.4 ·" not in html
        assert "zvb" not in html
        assert "mailto:" not in html
        assert "t.me/" not in html

    def test_owner_contact_renders_only_when_configured(self, fe, tmp_path, monkeypatch):
        mod, catalog, details = fe
        cfg = tmp_path / "owner.json"
        cfg.write_text(json.dumps({
            "contact_email": "ops@example.com",
            "telegram_url": "https://t.me/animedia_official_example",
            "privacy_url": "/privacy/",
        }), encoding="utf-8")
        monkeypatch.setattr(mod, "АНИМЕДИА_OWNER_CONFIG_PATH", str(cfg))
        html = _вид(mod, catalog, details).подвал()
        assert "ops@example.com" in html
        assert "https://t.me/animedia_official_example" in html
        assert "/privacy/" in html

    def test_related_section_class(self, fe):
        mod, catalog, details = fe
        html = _вид(mod, catalog, details).тайтл(
            catalog["items"][0], details["details"]["alpha-anime"])
        assert "zsec--rel" in html or "Смотрите также" in html
        assert "data-desc-toggle" in html
        assert "Развернуть" in html

    def test_missing_rating_not_zero(self, fe):
        mod, catalog, details = fe
        det = dict(details["details"]["gamma-movie"])
        det["kinopoisk_rating"] = 0
        det["imdb_rating"] = None
        det.pop("ratings_by_source", None)
        scores = mod.оценки_по_источникам(det)
        assert scores == []
        html = mod.разметка_оценок(det, "rbs", пусто=False)
        assert html == ""
        assert ">0<" not in html
        assert "0/" not in html

    def test_ratings_gateway_sources_only(self, fe):
        mod, catalog, details = fe
        det = details["details"]["alpha-anime"]
        # inject ratings_by_source
        det2 = dict(det)
        det2["ratings_by_source"] = {
            "shikimori": {"value": 8.4, "votes": 10},
            "kp": 0,
            "imdb": {"value": 7.1, "votes": 3},
        }
        scores = mod.оценки_по_источникам(det2)
        keys = [s["ключ"] for s in scores]
        assert "shikimori" in keys
        assert "imdb" in keys
        assert "kp" not in keys
        html = mod.разметка_оценок(det2, "rbs", пусто=False)
        assert "Shikimori" in html
        assert "IMDb" in html
        assert "КП" not in html

    def test_franchise_hidden_without_relations(self, fe):
        mod, catalog, details = fe
        вид = _вид(mod, catalog, details)
        assert вид._франшиза(details["details"]["alpha-anime"]) == ""

    def test_franchise_links_only_existing_slugs(self, fe):
        mod, catalog, details = fe
        вид = _вид(mod, catalog, details)
        html = вид._франшиза({
            "relations": [
                {"slug": "beta-series", "relation": "sequel", "title": "Бета"},
                {"slug": "missing-title", "relation": "prequel", "title": "Ghost"},
            ]
        })
        assert "/title/beta-series/" in html
        assert "missing-title" not in html

    def test_domains_still_distinct(self, fe):
        mod, catalog, details = fe
        hs = _вид(mod, catalog, details, "animedia.space").главная()
        hi = _вид(mod, catalog, details, "animedia.icu").главная()
        assert hs != hi
        assert "animedia-space" in hs and "animedia-icu" in hi

    def test_catalog_wrap_class(self, fe):
        mod, catalog, details = fe
        html = _вид(mod, catalog, details).список("/catalog", {})
        assert "zwrap--catalog" in html

    def test_css_isolation_no_global_hidden_override(self, fe):
        """No unscoped `[hidden]` rule — collapse rules must name their owner.

        The earlier substring form of this check also matched the tail of every
        scoped selector (`.zhd__drawer[hidden]{display…`), so it failed on rules
        that are exactly what the isolation contract wants. Match on selector
        boundaries instead: `[hidden]` may only appear attached to a class, an
        element or another attribute, never standing alone.
        """
        import re

        mod, _, _ = fe
        css = mod.АНИМЕДИА_СТИЛЬ
        безхозные = [
            m.group(0)
            for m in re.finditer(r"(?:^|[,{}\s])\[hidden\][^{,]*\{", css)
        ]
        assert безхозные == [], безхозные
        assert "iframe{max-width:100%;height:auto" not in css
