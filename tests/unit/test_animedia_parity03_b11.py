"""B11 catalog — H1/count, compact filters, 2/4/6 grid, pagination, facets, dedupe."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.unit.test_animedia_visual_finalization import _load, _вид  # noqa: E402

EV = ROOT / "artifacts/evidence/animedia-blockwise-parity-03-2026-09-20"
CONTRACT_SHA = (EV / "00-contract" / "CONTRACT_SHA256.txt").read_text(encoding="utf-8").strip()


@pytest.fixture
def fe(tmp_path):
    return _load(tmp_path, version="1.2.4")


def test_contract_digest_unchanged() -> None:
    assert CONTRACT_SHA == "5f2112e25ef974333c388bad405abfae3c3d460a713b028afa3c0e549b8eaeb3"


def test_catalog_h1_count_filters_empty(fe):
    mod, catalog, details = fe
    вид = _вид(mod, catalog, details)
    html = вид.список("/catalog", {})
    assert 'data-b11="catalog"' in html
    assert "<h1" in html and "Весь каталог" in html
    assert 'data-b11-count="1"' in html
    assert "Найдено" in html
    assert 'class="afilt afilt--closed"' in html
    empty = вид.список("/catalog", {"genre": ["no-such-genre-zzz"]})
    assert 'data-b11-empty="1"' in empty
    assert "Ничего не подошло" in empty


def test_catalog_grid_css_2_4_6(fe):
    mod, _, _ = fe
    css = mod.АНИМЕДИА_СТИЛЬ
    assert ".zwrap--catalog .zg" in css
    assert "repeat(6,minmax(0,1fr))" in css
    # Catalog must not keep home 7-col density at 1440.
    block = css[css.find("B11 catalog grid"): css.find("B11 catalog grid") + 500]
    assert "repeat(7," not in block
    assert "repeat(6,minmax(0,1fr))" in block
    assert "afilt--closed" in css and "max-height:112px" in css


def test_catalog_dedupe_by_title_id(fe):
    mod, catalog, details = fe
    # Duplicate slug/title_id rows must collapse to one card.
    catalog["items"].append({
        "slug": "alpha-anime", "title": "Альфа dup", "kind": "Аниме",
        "year": 2026, "published_at": "2026-09-19T00:00:00Z",
        "poster": "/poster/a2.webp", "url": "/title/alpha-anime/",
        "canonical_title_id": "alpha-anime",
    })
    вид = _вид(mod, catalog, details)
    набор, _ = mod.отбор(вид.д, вид.индекс, {}, "/catalog")
    slugs = [з["slug"] for з in набор]
    assert slugs.count("alpha-anime") == 1


def test_pagination_preserves_filters(fe):
    mod, catalog, details = fe
    for i in range(50):
        catalog["items"].append({
            "slug": f"page-{i}", "title": f"Page {i}", "kind": "Аниме",
            "year": 2020, "published_at": f"2026-01-{(i % 28) + 1:02d}T00:00:00Z",
            "poster": "", "url": f"/title/page-{i}/",
        })
        details["details"][f"page-{i}"] = {"type": "tv", "genres": ["драма"]}
    вид = _вид(mod, catalog, details)
    html = вид.список("/catalog", {"year": ["2020"], "page": ["1"]})
    flat = html.replace("&amp;", "&")
    assert "year=2020" in flat
    assert re.search(r'href="/catalog/\?[^"]*year=2020', flat)
    assert 'aria-label="Страницы"' in html or 'class="zpg"' in html


def test_invalid_page_404(fe):
    mod, catalog, details = fe
    вид = _вид(mod, catalog, details)
    html = вид.список("/catalog", {"page": ["99"]})
    assert getattr(вид, "_http_status", 200) == 404


def test_catalog_facet_route_pattern(fe):
    mod, catalog, details = fe
    rx = mod.Обработчик.МАРШРУТ_КАТАЛОГ_ФАСЕТ
    assert rx.match("/catalog/2026/").group("facet") == "2026"
    assert rx.match("/catalog/tv/").group("facet") == "tv"
    assert rx.match("/catalog/drama/") is not None
    assert rx.match("/catalog/") is None
    # Resolve facet via same filters as path would apply.
    вид = _вид(mod, catalog, details)
    year_html = вид.список("/catalog", {"year": ["2026"]})
    assert 'data-catalog-facet="year:2026"' in year_html
    assert "Аниме 2026" in year_html
    type_html = вид.список("/catalog", {"type": ["movie"]})
    assert 'data-catalog-facet="type:movie"' in type_html


def test_year_facet_h1(fe):
    mod, catalog, details = fe
    html = _вид(mod, catalog, details).список("/catalog", {"year": ["2026"]})
    assert "<h1" in html
    assert "2026" in html
    assert "Найдено" in html


def test_no_rating_zero_on_cards(fe):
    mod, catalog, details = fe
    # gamma has no ratings in fixture
    html = _вид(mod, catalog, details).список("/catalog", {})
    # Must not paint fabricated 0.0 scores on cards.
    assert not re.search(r'zt__r[^>]*>[\s\S]{0,80}>\s*0(?:\.0)?\s*<', html)
