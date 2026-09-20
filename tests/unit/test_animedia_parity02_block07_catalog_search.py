"""BLOCK_07: compact catalog filters + search ranking contracts."""

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


def test_catalog_uses_compact_filters_not_year_wall(fe):
    mod, catalog, details = fe
    html = _вид(mod, catalog, details).список("/catalog", {})
    assert 'class="afilt"' in html
    assert "data-afilt-open" in html
    assert 'class="afilt__dd"' in html
    # No old wall nav of years as primary UI
    assert 'aria-label="Годы"' not in html
    assert 'aria-label="Жанры"' not in html


def test_active_filters_in_url_and_chips(fe):
    mod, catalog, details = fe
    html = _вид(mod, catalog, details).список(
        "/catalog", {"year": ["2026"], "sort": ["title"]})
    assert "afilt__chip" in html
    assert "2026" in html
    assert "Сбросить фильтры" in html
    assert "sort=title" in html or "sort=title" in html.replace("&amp;", "&")


def test_pagination_preserves_query(fe):
    mod, catalog, details = fe
    # Expand catalog so page 2 exists
    for i in range(60):
        catalog["items"].append({
            "slug": f"extra-{i}", "title": f"Extra {i}", "kind": "Аниме",
            "year": 2020, "published_at": f"2026-01-{(i % 28) + 1:02d}T00:00:00Z",
            "poster": "", "url": f"/title/extra-{i}/",
        })
        details["details"][f"extra-{i}"] = {"type": "tv", "genres": ["драма"]}
    вид = _вид(mod, catalog, details)
    html = вид.список("/catalog", {"year": ["2020"], "page": ["1"]})
    assert "year=2020" in html.replace("&amp;", "&")
    # page links keep year
    assert re.search(r'href="/catalog/\?[^"]*year=2020', html.replace("&amp;", "&"))


def test_invalid_catalog_page_is_404(fe):
    mod, catalog, details = fe
    вид = _вид(mod, catalog, details)
    html = вид.список("/catalog", {"page": ["99"]})
    assert getattr(вид, "_http_status", 200) == 404
    assert "не найдена" in html.lower() or "404" in html


def test_search_exact_russian_beats_fuzzy(fe):
    mod, catalog, details = fe
    # Add near-miss and exact
    catalog["items"].append({
        "slug": "alpha-near", "title": "Альфабет", "kind": "Аниме",
        "year": 2021, "published_at": "2026-01-01T00:00:00Z",
        "poster": "", "url": "/title/alpha-near/",
    })
    details["details"]["alpha-near"] = {"type": "tv", "genres": []}
    вид = _вид(mod, catalog, details)
    found = вид.д.искать("Альфа")
    assert found
    assert found[0]["slug"] == "alpha-anime"


def test_search_original_title_from_details(fe):
    mod, catalog, details = fe
    details["details"]["beta-series"]["original_title"] = "Beta Original Unique"
    вид = _вид(mod, catalog, details)
    found = вид.д.искать("Beta Original Unique")
    assert any(з["slug"] == "beta-series" for з in found)


def test_search_empty_and_zero(fe):
    mod, catalog, details = fe
    вид = _вид(mod, catalog, details)
    empty = вид.поиск({})
    assert "Запрос пуст" in empty or "Введите" in empty
    zero = вид.поиск({"q": ["zzz-no-such-title-qqq"]})
    assert "Совпадений нет" in zero or "ничего не нашлось" in zero.lower()


def test_years_not_hard_capped_in_filter(fe):
    mod, catalog, details = fe
    # many years
    for y in range(1990, 2027):
        catalog["items"].append({
            "slug": f"y{y}", "title": f"Y{y}", "kind": "Аниме",
            "year": y, "published_at": f"{y}-01-01T00:00:00Z",
            "poster": "", "url": f"/title/y{y}/",
        })
        details["details"][f"y{y}"] = {"type": "movie", "genres": []}
    html = _вид(mod, catalog, details).список("/catalog", {})
    assert "1990" in html and "2026" in html
