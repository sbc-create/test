"""BLOCK_11–16: player, recommendations, collections, footer, theme, routes."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.unit.test_animedia_visual_finalization import _load, _вид  # noqa: E402


@pytest.fixture
def fe(tmp_path):
    return _load(tmp_path, version="1.2.4")


def test_player_shell_css_fills_16x9(fe):
    mod, _, _ = fe
    css = mod.АНИМЕДИА_СТИЛЬ
    assert "aspect-ratio:16/9" in css
    assert ".zpl__f iframe" in css
    assert "height:100% !important" in css
    assert "max-width:none !important" in css


def test_single_player_instance_on_title_and_episode(fe):
    mod, catalog, details = fe
    вид = _вид(mod, catalog, details)
    item = next(з for з in вид.д.items if з["slug"] == "alpha-anime")
    det = details["details"]["alpha-anime"]
    for html in (вид.тайтл(item, det), вид.серия(item, det, 1, 2)):
        assert html.count("data-player data-state") == 1


def test_recommendations_exclude_current_and_stable(fe):
    mod, catalog, details = fe
    вид = _вид(mod, catalog, details)
    item = next(з for з in вид.д.items if з["slug"] == "alpha-anime")
    det = details["details"]["alpha-anime"]
    a = [з["slug"] for з in вид.похожие(item, det, сколько=6)]
    b = [з["slug"] for з in вид.похожие(item, det, сколько=6)]
    assert a == b
    assert item["slug"] not in a
    assert len(a) == len(set(a))


def test_recommendations_differ_for_different_titles(fe):
    mod, catalog, details = fe
    вид = _вид(mod, catalog, details)
    alpha = next(з for з in вид.д.items if з["slug"] == "alpha-anime")
    delta = next(з for з in вид.д.items if з["slug"] == "delta-old")
    ra = [з["slug"] for з in вид.похожие(alpha, details["details"]["alpha-anime"])]
    rd = [з["slug"] for з in вид.похожие(delta, details["details"]["delta-old"])]
    assert ra != rd or not ra or not rd


def test_collections_hub_has_h1_and_count(fe):
    mod, catalog, details = fe
    html = _вид(mod, catalog, details).список("/collections", {})
    assert "<h1" in html and "Подборки" in html
    assert "Доступно подборок" in html
    assert 'href="#"' not in html


def test_footer_multicol_no_invented_contacts(fe):
    mod, catalog, details = fe
    html = _вид(mod, catalog, details).главная()
    assert 'class="zft__cols"' in html
    assert "Жанры" in html
    assert "t.me/" not in html
    assert 'href="#"' not in html
    assert "mailto:" not in html or "contact_email" in str(mod._аниме_owner_config())


def test_theme_boot_and_persistence_script(fe):
    mod, catalog, details = fe
    html = _вид(mod, catalog, details).главная()
    assert "animedia-theme" in html
    assert "data-theme-toggle" in html
    assert "localStorage" in html


def test_invalid_title_and_episode_404(fe):
    mod, catalog, details = fe
    вид = _вид(mod, catalog, details)
    assert вид.запись("no-such-slug-zzz") is None
    html = вид.не_найдено("/title/no-such-slug-zzz/")
    assert "404" in html or "не найдена" in html.lower()


def test_noindex_preserved(fe):
    mod, catalog, details = fe
    html = _вид(mod, catalog, details).главная()
    assert "noindex" in html.lower()
