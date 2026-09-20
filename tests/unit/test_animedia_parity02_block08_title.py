"""BLOCK_08: title page context — poster, description, facts, ratings."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.unit.test_animedia_visual_finalization import _load, _вид  # noqa: E402


@pytest.fixture
def fe(tmp_path):
    return _load(tmp_path, version="1.2.4")


def _title_html(fe, slug="alpha-anime"):
    mod, catalog, details = fe
    вид = _вид(mod, catalog, details)
    item = next(з for з in вид.д.items if з["slug"] == slug)
    return вид.тайтл(item, details["details"][slug]), details["details"][slug], item


def test_title_renders_poster_when_source_has_it(fe):
    html, det, item = _title_html(fe, "alpha-anime")
    assert item.get("poster")
    assert "ztitle__poster" in html
    assert item["poster"] in html or "zhead__img" in html


def test_title_renders_description_when_present(fe):
    html, det, _ = _title_html(fe, "alpha-anime")
    assert det.get("description")
    assert "ztitle__desc" in html
    assert "Описание альфы" in html


def test_title_hides_description_when_absent(fe):
    mod, catalog, details = fe
    details["details"]["gamma-movie"]["description"] = ""
    details["details"]["gamma-movie"]["short_description"] = ""
    вид = _вид(mod, catalog, details)
    item = next(з for з in вид.д.items if з["slug"] == "gamma-movie")
    html = вид.тайтл(item, details["details"]["gamma-movie"])
    assert 'class="ztitle__desc"' not in html
    assert 'id="title-desc"' not in html


def test_title_has_breadcrumbs_genres_facts_cta(fe):
    html, det, item = _title_html(fe, "alpha-anime")
    assert "aria-label=\"Хлебные крошки\"" in html or "zcr" in html
    assert "ztitle__pills" in html
    assert "ztitle__facts" in html
    assert 'href="#watch"' in html
    assert "ztitle__cta" in html
    assert det.get("original_title")
    assert "Alpha" in html


def test_title_movie_and_series_shapes(fe):
    html_s, _, _ = _title_html(fe, "alpha-anime")
    html_m, _, _ = _title_html(fe, "gamma-movie")
    assert "Серии" in html_s or "zeps" in html_s or "zsea" in html_s
    assert "zpl" in html_s and "zpl" in html_m
