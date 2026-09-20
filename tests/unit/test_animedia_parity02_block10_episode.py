"""BLOCK_10: exact episode page is compact title derivative."""

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


def test_episode_has_title_context(fe):
    mod, catalog, details = fe
    вид = _вид(mod, catalog, details)
    item = next(з for з in вид.д.items if з["slug"] == "alpha-anime")
    det = details["details"]["alpha-anime"]
    html = вид.серия(item, det, 1, 3)
    assert 'data-episode-context="1"' in html
    assert "aep-ctx__poster" in html
    assert item["title"] in html
    assert "1 сезон, 3 серия" in html
    assert f'/title/{item["slug"]}/' in html
    assert 'data-b09="exact"' in html


def test_episode_keeps_poster_and_description_from_title(fe):
    mod, catalog, details = fe
    вид = _вид(mod, catalog, details)
    item = next(з for з in вид.д.items if з["slug"] == "alpha-anime")
    det = details["details"]["alpha-anime"]
    title_html = вид.тайтл(item, det)
    ep_html = вид.серия(item, det, 1, 2)
    assert item.get("poster")
    assert "ztitle__poster" in title_html or item["poster"] in title_html
    assert "aep-ctx__poster" in ep_html
    assert det["description"].strip()
    assert "ztitle__desc" in title_html
    assert "aep-ctx__desc" in ep_html


def test_episode_selects_route_before_provider(fe):
    mod, catalog, details = fe
    вид = _вид(mod, catalog, details)
    item = next(з for з in вид.д.items if з["slug"] == "alpha-anime")
    html = вид.серия(item, details["details"]["alpha-anime"], 1, 4)
    assert 'data-season="1"' in html
    assert 'data-episode="4"' in html
    assert 'data-player' in html
    # B09: player before parent context.
    assert html.find('data-b09="player"') < html.find('data-b09="parent"')
    assert html.find("zh--ep") < html.find('data-player')


def test_episode_prev_next_from_manifest(fe):
    mod, catalog, details = fe
    вид = _вид(mod, catalog, details)
    item = next(з for з in вид.д.items if з["slug"] == "alpha-anime")
    html = вид.серия(item, details["details"]["alpha-anime"], 1, 3)
    assert "zepnav" in html
    assert re.search(r"episode-2", html) or "S1E2" in html
    assert re.search(r"episode-4", html) or "S1E4" in html


def test_css_limits_empty_gap(fe):
    mod, _, _ = fe
    css = mod.АНИМЕДИА_СТИЛЬ
    assert ".aep-ctx" in css
    assert ".zh--ep" in css
