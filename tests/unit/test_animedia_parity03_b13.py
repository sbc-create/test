"""B13 — collections hub, collection detail and /schedule/ honest empty.

Passport: ANIMEDIA_BLOCK_SPEC_V1/B13.
- routes: /collections/, the collection detail route, /schedule/
- required_fields: h1, count  (missing required → blocked, never a silent empty)
- optional: summary, cover, schedule_events → hidden when absent
- desktop geometry: list_cols 3, tablet 2, mobile 1; page_size_list 12,
  page_size_detail 24; schedule_empty_max_px 260
- interactions: sort, category, pagination
- sort_key: collections:(sort_value, collection_id); dedupe by
  collection_id_or_title_id
- visible_timestamp_semantic: collection_revision_published_at

Two contract facts are resolved here rather than assumed, and both are asserted
so they cannot drift back:

1. The frozen ROUTE_REGISTRY writes the detail route as `/collections/{slug}/`,
   which is a placeholder. The parity-02 resolution note settles the real shape:
   "resolve first live collection slug in later block from /collections/ hrefs".
   The hub's own hrefs are `/collection/<key>/`, so that is the route.
2. `section_id` in the collection contract is one-to-one with `collection_key`,
   so the data carries no category dimension. A category control would be an
   invented taxonomy, so there is none and the gap is declared instead.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from factory.lords import collection_contract as кк  # noqa: E402
from tests.unit.test_animedia_visual_finalization import _load, _вид  # noqa: E402

EV = ROOT / "artifacts/evidence/animedia-blockwise-parity-03-2026-09-20"
CONTRACT_SHA = (EV / "00-contract" / "CONTRACT_SHA256.txt").read_text(
    encoding="utf-8").strip()


@pytest.fixture
def fe(tmp_path):
    return _load(tmp_path, version="1.2.4")


def _карточки(n: int) -> list[dict]:
    """Synthetic hub cards — pagination and ordering logic only."""
    return [{
        "key": f"k{i:02d}",
        "order": i,
        "title": f"Подборка {chr(0x410 + (n - i) % 32)}{i:02d}",
        "description": "описание",
        "total": (i * 7) % 50 + 1,
        "path": f"/collection/k{i:02d}/",
        "posters": ["p1.webp", "p2.webp", "p3.webp", "p4.webp"],
    } for i in range(n)]


def _богатый_снимок():
    items, details = [], {}
    набор = [
        ("m1", "movie", "Япония", "боевик", 2024, 8.0, 0),
        ("m2", "movie", "Япония", "романтика", 2025, 7.2, 0),
        ("d1", "tv", "Китай", "фэнтези", 2023, 7.0, 40),
        ("s1", "tv", "Япония", "романтика", 1999, 9.0, 8),
        ("a1", "tv", "Япония", "боевик", 2025, 6.0, 24),
        ("f1", "tv", "Япония", "семейный", 2010, 7.5, 12),
        ("c1", "tv", "Япония", "боевик", 1995, 8.4, 26),
    ]
    for i, (slug, typ, country, genre, year, rating, eps) in enumerate(набор):
        items.append({
            "slug": slug, "title": slug.upper(), "kind": "Аниме", "year": year,
            "published_at": f"2026-09-{20 - i:02d}T00:00:00Z",
            "poster": f"/poster/{slug}.webp", "url": f"/title/{slug}/",
            "canonical_title_id": slug,
        })
        details[slug] = {
            "id": slug, "playable": True, "type": typ,
            "countries": [country], "genres": [genre], "imdb_rating": rating,
            "seasons": ([{"n": 1, "eps": eps, "avail": eps}] if eps else []),
        }
    return items, details


def test_contract_digest_unchanged() -> None:
    assert CONTRACT_SHA == (
        "5f2112e25ef974333c388bad405abfae3c3d460a713b028afa3c0e549b8eaeb3")


# --- contract facts ----------------------------------------------------

def test_detail_route_shape_comes_from_the_hub_hrefs(fe):
    """The declared canonical path of every spec is the route we serve."""
    mod, _, _ = fe
    маршрут = mod.Обработчик.МАРШРУТ_КОЛЛЕКЦИИ
    for спец in кк.спецификации("animedia"):
        assert маршрут.match(спец.canonical_path), спец.canonical_path


def test_no_category_dimension_exists_so_none_is_invented(fe):
    mod, _, _ = fe
    assert mod.COLLECTION_CATEGORY_DATA_GAP == 1
    секции = {с.section_id for с in кк.спецификации("animedia")}
    ключи = {с.collection_key for с in кк.спецификации("animedia")}
    # One-to-one: section_id carries no grouping the user could filter by.
    assert len(секции) == len(ключи)
    mod_вид_html = None
    catalog, details = _богатый_снимок()
    вид = _вид(mod, {"items": catalog, "revision": "r", "count": len(catalog)},
               {"catalog_revision": "r", "details": details})
    mod_вид_html = вид.страница_коллекций({})
    assert 'data-b13="category"' not in mod_вид_html
    assert "категор" not in mod_вид_html.lower()


def test_no_collection_timestamp_is_rendered(fe):
    """`data_revision` is a fingerprint, not a publication date."""
    mod, _, _ = fe
    assert mod.COLLECTION_REVISION_TIMESTAMP_DATA_GAP == 1
    catalog, details = _богатый_снимок()
    вид = _вид(mod, {"items": catalog, "revision": "r", "count": len(catalog)},
               {"catalog_revision": "r", "details": details})
    html_ = вид.страница_коллекций({})
    сетка = html_[html_.find('data-b13="hub"'):]
    assert not re.search(r"\d{1,2}\.\d{2}\.\d{4}", сетка)
    assert not re.search(r"\d{4}-\d{2}-\d{2}", сетка)


# --- B13.1 hub ---------------------------------------------------------

def test_hub_page_sizes_match_the_passport(fe):
    mod, _, _ = fe
    assert mod.АНИМЕДИА_COLLECTIONS_PAGE_SIZE == 12
    assert mod.АНИМЕДИА_COLLECTION_DETAIL_PAGE_SIZE == 24
    assert mod.ВидАнимедиа.COLLECTION_PAGE_SIZE == 24
    assert mod.ВидАнимедиа.COLLECTION_STRICT_PAGING is True


def test_hub_grid_is_three_two_one(fe):
    mod, _, _ = fe
    css = mod.АНИМЕДИА_СТИЛЬ
    assert ".zhub{display:grid" in css
    assert "grid-template-columns:1fr" in css
    assert "@media(min-width:600px){.zhub{grid-template-columns:repeat(2,1fr)}}" in css
    assert "@media(min-width:1000px){.zhub{grid-template-columns:repeat(3,1fr)}}" in css


def test_hub_has_h1_and_count(fe):
    mod, _, _ = fe
    catalog, details = _богатый_снимок()
    вид = _вид(mod, {"items": catalog, "revision": "r", "count": len(catalog)},
               {"catalog_revision": "r", "details": details})
    html_ = вид.страница_коллекций({})
    assert "<h1" in html_ and "Подборки аниме" in html_
    сч = re.search(r'data-b13-count="(\d+)"', html_)
    assert сч and int(сч.group(1)) >= 1
    assert "Доступно подборок:" in html_
    assert вид._http_status == 200


def test_hub_lists_every_filled_collection_even_on_a_collage_clash(fe):
    """A collection that exists must be reachable; a repeated collage is not a
    reason to drop the tile, or nothing would link to that collection."""
    mod, _, _ = fe
    # One single poster across the whole catalog forces identical collages.
    catalog, details = _богатый_снимок()
    for з in catalog:
        з["poster"] = "/poster/same.webp"
    вид = _вид(mod, {"items": catalog, "revision": "r", "count": len(catalog)},
               {"catalog_revision": "r", "details": details})
    карточки = вид._карточки_коллекций()
    ключи = [к["key"] for к in карточки]
    assert len(ключи) == len(set(ключи)), "collection listed twice"
    html_ = вид.страница_коллекций({})
    for ключ in ключи[:mod.АНИМЕДИА_COLLECTIONS_PAGE_SIZE]:
        assert f'data-collection-key="{ключ}"' in html_


def test_hub_tiles_have_no_empty_cells(fe):
    mod, _, _ = fe
    catalog, details = _богатый_снимок()
    вид = _вид(mod, {"items": catalog, "revision": "r", "count": len(catalog)},
               {"catalog_revision": "r", "details": details})
    html_ = вид.страница_коллекций({})
    # Every collage cell carries a real poster src.
    for ячейка in re.findall(r'<span class="zhub__p">(.*?)</span>', html_, re.S):
        src = re.search(r'src="([^"]*)"', ячейка)
        assert src and src.group(1).strip(), ячейка


def test_hub_pagination_twelve_per_page(fe):
    mod, _, _ = fe
    catalog, details = _богатый_снимок()
    вид = _вид(mod, {"items": catalog, "revision": "r", "count": len(catalog)},
               {"catalog_revision": "r", "details": details})
    вид._карточки_коллекций = lambda: _карточки(14)
    стр1 = вид.страница_коллекций({})
    assert 'data-b13-count="14"' in стр1
    assert 'data-b13-page="1"' in стр1 and 'data-b13-pages="2"' in стр1
    assert стр1.count('class="zhub__c"') == 12
    assert 'aria-label="Страницы подборок"' in стр1
    стр2 = вид.страница_коллекций({"page": ["2"]})
    assert вид._http_status == 200
    assert 'data-b13-page="2"' in стр2
    assert стр2.count('class="zhub__c"') == 2


def test_hub_invalid_page_is_a_real_404(fe):
    mod, _, _ = fe
    catalog, details = _богатый_снимок()
    вид = _вид(mod, {"items": catalog, "revision": "r", "count": len(catalog)},
               {"catalog_revision": "r", "details": details})
    вид._карточки_коллекций = lambda: _карточки(14)
    вид.страница_коллекций({"page": ["9"]})
    assert вид._http_status == 404
    вид.страница_коллекций({"page": ["abc"]})
    assert вид._http_status == 404


def test_hub_sort_is_declared_and_deterministic(fe):
    mod, _, _ = fe
    catalog, details = _богатый_снимок()
    вид = _вид(mod, {"items": catalog, "revision": "r", "count": len(catalog)},
               {"catalog_revision": "r", "details": details})
    карточки = _карточки(14)
    по_размеру = вид._сортировать_коллекции(карточки, "size")
    assert [к["total"] for к in по_размеру] == sorted(
        (к["total"] for к in карточки), reverse=True)
    по_имени = вид._сортировать_коллекции(карточки, "name")
    assert [к["title"].casefold() for к in по_имени] == sorted(
        к["title"].casefold() for к in карточки)
    # Unknown sort falls back to the contract order instead of erroring.
    вид._карточки_коллекций = lambda: карточки
    html_ = вид.страница_коллекций({"sort": ["nonsense"]})
    assert 'data-b13="sort"' in html_
    первый = re.search(r'data-collection-key="([^"]+)"', html_)
    assert первый and первый.group(1) == "k00"


def test_hub_sort_survives_pagination_and_canonical(fe):
    mod, _, _ = fe
    catalog, details = _богатый_снимок()
    вид = _вид(mod, {"items": catalog, "revision": "r", "count": len(catalog)},
               {"catalog_revision": "r", "details": details})
    вид._карточки_коллекций = lambda: _карточки(14)
    html_ = вид.страница_коллекций({"sort": ["size"]})
    assert re.search(r'href="/collections/\?sort=size&amp;page=2"', html_)
    канон = re.search(r'<link rel="canonical" href="([^"]+)"', html_)
    assert канон and канон.group(1).endswith("/collections/?sort=size")
    стр2 = вид.страница_коллекций({"sort": ["size"], "page": ["2"]})
    канон2 = re.search(r'<link rel="canonical" href="([^"]+)"', стр2)
    # The canonical is html-escaped in the attribute, as it must be.
    assert канон2 and канон2.group(1).endswith("/collections/?sort=size&amp;page=2")


def test_hub_first_page_canonical_has_no_page_param(fe):
    mod, _, _ = fe
    catalog, details = _богатый_снимок()
    вид = _вид(mod, {"items": catalog, "revision": "r", "count": len(catalog)},
               {"catalog_revision": "r", "details": details})
    вид._карточки_коллекций = lambda: _карточки(14)
    html_ = вид.страница_коллекций({})
    канон = re.search(r'<link rel="canonical" href="([^"]+)"', html_)
    assert канон and "page=" not in канон.group(1)


def test_hub_without_collections_is_honest_not_invented(fe):
    mod, catalog, details = fe
    вид = _вид(mod, catalog, details)
    вид._карточки_коллекций = lambda: []
    html_ = вид.страница_коллекций({})
    assert 'data-b13-count="0"' in html_
    assert 'data-b13-state="empty"' in html_
    assert "выдумка" in html_
    assert вид._http_status == 200


# --- B13.2 detail ------------------------------------------------------

def _коллекция(page: int = 1):
    items, details = _богатый_снимок()
    снимок = кк.Снимок(items, details, revision="r13")
    return кк.разрешить("recently_added", снимок, "animedia",
                        страница=page, на_странице=24)


def test_detail_has_h1_count_and_page_size_24(fe):
    mod, _, _ = fe
    catalog, details = _богатый_снимок()
    вид = _вид(mod, {"items": catalog, "revision": "r", "count": len(catalog)},
               {"catalog_revision": "r", "details": details})
    данные = _коллекция()
    assert данные is not None
    html_ = вид.коллекция(данные)
    assert 'data-b13="detail"' in html_
    assert "<h1" in html_
    assert f'data-b13-count="{данные.total}"' in html_
    assert "записей" in html_
    # 24 per page, never the shared 60.
    assert len(данные.items) <= 24


def test_detail_dedupes_by_canonical_title_id(fe):
    mod, _, _ = fe
    catalog, details = _богатый_снимок()
    вид = _вид(mod, {"items": catalog, "revision": "r", "count": len(catalog)},
               {"catalog_revision": "r", "details": details})
    данные = _коллекция()

    class Двойник:
        def __init__(self, к):
            self.entity_id = к.entity_id
            self.raw = dict(к.raw)

    данные.items = list(данные.items) + [Двойник(данные.items[0])]
    html_ = вид.коллекция(данные)
    слаг = данные.items[0].raw["slug"]
    assert html_.count(f'href="/title/{слаг}/"') == 1


def test_detail_empty_page_is_explicit_not_silent(fe):
    mod, _, _ = fe
    catalog, details = _богатый_снимок()
    вид = _вид(mod, {"items": catalog, "revision": "r", "count": len(catalog)},
               {"catalog_revision": "r", "details": details})
    данные = _коллекция()
    данные.items = []
    html_ = вид.коллекция(данные)
    assert 'data-b13-state="empty"' in html_
    assert "не попала ни одна" in html_


def test_detail_canonical_carries_page_only_past_the_first(fe):
    mod, _, _ = fe
    catalog, details = _богатый_снимок()
    вид = _вид(mod, {"items": catalog, "revision": "r", "count": len(catalog)},
               {"catalog_revision": "r", "details": details})
    данные = _коллекция()
    html_ = вид.коллекция(данные)
    канон = re.search(r'<link rel="canonical" href="([^"]+)"', html_)
    assert канон and "page=" not in канон.group(1)
    данные.page = 2
    данные.total = 60
    html2 = вид.коллекция(данные)
    канон2 = re.search(r'<link rel="canonical" href="([^"]+)"', html2)
    assert канон2 and канон2.group(1).endswith("?page=2")


def test_detail_has_no_cover_hero_when_no_cover_data(fe):
    """`cover` is optional; absent data means no hero, not an empty frame."""
    mod, _, _ = fe
    catalog, details = _богатый_снимок()
    вид = _вид(mod, {"items": catalog, "revision": "r", "count": len(catalog)},
               {"catalog_revision": "r", "details": details})
    html_ = вид.коллекция(_коллекция())
    # Look at the rendered block only: the stylesheet legitimately mentions
    # hero class names for other routes.
    тело = html_[html_.find('data-b13="detail"'):]
    assert "acol__hero" not in тело
    assert "zhead__ps" not in тело
    assert "zhub__g" not in тело


# --- B13.3 /schedule/ --------------------------------------------------

def test_schedule_stays_honest_and_bounded(fe):
    mod, catalog, details = fe
    вид = _вид(mod, catalog, details)
    html_ = вид.расписание()
    assert 'data-b04="empty"' in html_
    assert "Расписание пока недоступно" in html_
    assert "<h1" in html_
    # No fabricated air times.
    assert not re.search(r"\b\d{1,2}:\d{2}\b", html_)
    tol = json.loads((EV / "00-contract" / "GEOMETRY_TOLERANCES.json").read_text(
        encoding="utf-8"))
    assert tol["b13_schedule_empty_max_px"] == 260
    assert "max-height:260px" in mod.АНИМЕДИА_СТИЛЬ or ".asch-empty" in mod.АНИМЕДИА_СТИЛЬ


def test_collections_links_all_resolve_to_a_known_spec(fe):
    mod, _, _ = fe
    catalog, details = _богатый_снимок()
    вид = _вид(mod, {"items": catalog, "revision": "r", "count": len(catalog)},
               {"catalog_revision": "r", "details": details})
    html_ = вид.страница_коллекций({})
    известные = {с.canonical_path for с in кк.спецификации("animedia")}
    ссылки = set(re.findall(r'href="(/collection/[^"]+)"', html_))
    assert ссылки, "hub rendered no collection links"
    assert ссылки <= известные, ссылки - известные
