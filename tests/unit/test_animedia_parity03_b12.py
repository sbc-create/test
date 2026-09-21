"""B12 — /new/ catalog-added pages and /search/ form, results, empty states.

Passport: ANIMEDIA_BLOCK_SPEC_V1/B12.
- required_fields: h1, results_or_empty_state
- desktop geometry: search block 130–160px, input 48–52px,
  new page size 10, search page size 24
- interactions: submit, clear, pagination
- seo: canonical param order new=[page], search=[q, page]; indexability untouched
- ranking comes from the Search API; the template must not re-rank.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.unit.test_animedia_visual_finalization import _load, _вид  # noqa: E402

EV = ROOT / "artifacts/evidence/animedia-blockwise-parity-03-2026-09-20"
CONTRACT_SHA = (EV / "00-contract" / "CONTRACT_SHA256.txt").read_text(
    encoding="utf-8").strip()


@pytest.fixture
def fe(tmp_path):
    return _load(tmp_path, version="1.2.4")


def _много(mod, catalog, details, сколько: int):
    """Catalog with `сколько` extra titles sharing one searchable token."""
    for n in range(сколько):
        catalog["items"].append({
            "slug": f"kenko-{n:03d}", "title": f"Кэнко {n:03d}", "kind": "Аниме",
            "year": 2020 + (n % 6), "published_at": "2026-09-01T00:00:00Z",
            "poster": f"/poster/k{n}.webp", "url": f"/title/kenko-{n:03d}/",
            "canonical_title_id": f"kenko-{n:03d}",
        })
    return _вид(mod, catalog, details)


def test_contract_digest_unchanged() -> None:
    assert CONTRACT_SHA == (
        "5f2112e25ef974333c388bad405abfae3c3d460a713b028afa3c0e549b8eaeb3")


# --- B12.1 /new/ -------------------------------------------------------

def test_new_page_size_is_ten(fe):
    mod, _, _ = fe
    assert mod.АНИМЕДИА_CATALOG_ADDED_PAGE_SIZE == 10


def test_new_without_ledger_is_honest_gap_not_published_at(fe):
    mod, catalog, details = fe
    вид = _вид(mod, catalog, details)
    html_ = вид._страница_новых_эпизодов({})
    assert 'data-b05-page="gap"' in html_
    assert 'data-catalog-freshness-gap="1"' in html_
    # published_at must never be presented as a catalog-added date.
    assert "Добавлено" not in html_
    assert "Вышла серия" not in html_


def test_new_invalid_page_is_a_real_404(fe):
    mod, catalog, details = fe
    вид = _вид(mod, catalog, details)
    вид._страница_новых_эпизодов({"page": ["7"]})
    assert вид._http_status == 404


# --- B12.2 search form -------------------------------------------------

def test_search_page_size_is_twentyfour(fe):
    mod, _, _ = fe
    assert mod.АНИМЕДИА_SEARCH_PAGE_SIZE == 24


def test_search_block_geometry_within_contract(fe):
    mod, _, _ = fe
    css = mod.АНИМЕДИА_СТИЛЬ
    блок = css[css.find(".asearch{"): css.find(".asearch{") + 400]
    assert "min-height:130px" in блок
    assert "max-height:160px" in блок
    поле = css[css.find(".asearch__form input"):
               css.find(".asearch__form input") + 300]
    assert "min-height:48px" in поле
    assert "max-height:52px" in поле


def test_search_form_is_on_the_page_with_submit_and_clear(fe):
    mod, catalog, details = fe
    вид = _вид(mod, catalog, details)
    пусто = вид.поиск({})
    assert 'data-b12="search-form"' in пусто
    assert 'action="/search/"' in пусто
    assert 'type="submit"' in пусто
    # Nothing to clear while the query is empty.
    assert 'data-b12-clear="1"' not in пусто
    с_запросом = вид.поиск({"q": ["Альфа"]})
    assert 'data-b12-clear="1"' in с_запросом
    assert 'href="/search/"' in с_запросом


def test_search_input_is_labelled(fe):
    mod, catalog, details = fe
    вид = _вид(mod, catalog, details)
    assert 'aria-label="Поиск по каталогу"' in вид.поиск({})


# --- B12.3 search results ----------------------------------------------

def test_empty_query_is_explicit_empty_state(fe):
    mod, catalog, details = fe
    вид = _вид(mod, catalog, details)
    html_ = вид.поиск({"q": [""]})
    assert 'data-b12-state="empty"' in html_
    assert mod.АНИМЕДИА_SEARCH_EMPTY in html_
    assert "<h1" in html_ and "Поиск" in html_
    assert вид._http_status == 200


def test_no_matches_is_zero_state_not_an_error(fe):
    mod, catalog, details = fe
    вид = _вид(mod, catalog, details)
    html_ = вид.поиск({"q": ["qzxwvbnm123"]})
    assert 'data-b12-state="zero"' in html_
    assert 'data-b12-count="0"' in html_
    assert mod.АНИМЕДИА_SEARCH_ZERO in html_
    assert вид._http_status == 200


def test_unavailable_search_api_is_page_error_not_zero(fe):
    mod, catalog, details = fe
    вид = _вид(mod, catalog, details)

    def падает(_q, предел=120):
        raise RuntimeError("search index unavailable")

    вид.д.искать = падает
    html_ = вид.поиск({"q": ["Альфа"]})
    assert 'data-b12-state="error"' in html_
    assert mod.АНИМЕДИА_SEARCH_ERROR in html_
    # An unreachable source is never reported as zero matches.
    assert mod.АНИМЕДИА_SEARCH_ZERO not in html_
    assert 'data-b12-count="0"' not in html_


def test_results_are_populated_and_counted(fe):
    mod, catalog, details = fe
    вид = _вид(mod, catalog, details)
    html_ = вид.поиск({"q": ["Альфа"]})
    assert 'data-b12-state="populated"' in html_
    assert re.search(r'data-b12-count="[1-9]\d*"', html_)
    assert "Совпадений:" in html_


def test_template_does_not_reorder_the_search_api(fe):
    mod, catalog, details = fe
    вид = _много(mod, catalog, details, 5)
    порядок = [з["slug"] for з in вид.д.искать("Кэнко")]
    html_ = вид.поиск({"q": ["Кэнко"]})
    появление = [(html_.find(f"/title/{s}/"), s) for s in порядок]
    assert all(поз >= 0 for поз, _ in появление)
    assert [s for _, s in sorted(появление)] == порядок


def test_duplicate_canonical_title_id_collapses_to_one_card(fe):
    mod, catalog, details = fe
    catalog["items"].append({
        "slug": "alpha-anime", "title": "Альфа dup", "kind": "Аниме",
        "year": 2026, "published_at": "2026-09-19T00:00:00Z",
        "poster": "/poster/a2.webp", "url": "/title/alpha-anime/",
        "canonical_title_id": "alpha-anime",
    })
    вид = _вид(mod, catalog, details)
    html_ = вид.поиск({"q": ["Альфа"]})
    сетка = html_[html_.find('data-b12-state="populated"'):]
    assert сетка.count('href="/title/alpha-anime/"') == 1


def test_pagination_appears_past_page_size_and_keeps_query(fe):
    mod, catalog, details = fe
    вид = _много(mod, catalog, details, 30)
    html_ = вид.поиск({"q": ["Кэнко"]})
    assert 'data-b12-page="1"' in html_
    assert 'data-b12-pages="2"' in html_
    # Page 2 link carries the query; q comes before page.
    assert re.search(r'href="/search/\?q=[^"]*&amp;page=2"', html_)
    assert 'aria-label="Страницы поиска"' in html_


def test_second_page_is_served_and_canonical_carries_q_then_page(fe):
    mod, catalog, details = fe
    вид = _много(mod, catalog, details, 30)
    html_ = вид.поиск({"q": ["Кэнко"], "page": ["2"]})
    assert вид._http_status == 200
    assert 'data-b12-page="2"' in html_
    канон = re.search(r'<link rel="canonical" href="([^"]+)"', html_)
    assert канон, "canonical link missing on a 200 search page"
    assert re.search(r"\?q=[^&]+&amp;page=2$", канон.group(1)) or \
        re.search(r"\?q=[^&]+&page=2$", канон.group(1))


def test_search_page_out_of_range_is_a_real_404(fe):
    mod, catalog, details = fe
    вид = _много(mod, catalog, details, 30)
    вид.поиск({"q": ["Кэнко"], "page": ["99"]})
    assert вид._http_status == 404


def test_search_page_non_numeric_is_a_real_404(fe):
    mod, catalog, details = fe
    вид = _много(mod, catalog, details, 30)
    вид.поиск({"q": ["Кэнко"], "page": ["abc"]})
    assert вид._http_status == 404


def test_first_page_canonical_has_no_page_param(fe):
    mod, catalog, details = fe
    вид = _много(mod, catalog, details, 30)
    html_ = вид.поиск({"q": ["Кэнко"]})
    канон = re.search(r'<link rel="canonical" href="([^"]+)"', html_)
    assert канон
    assert "page=" not in канон.group(1)


def test_search_does_not_touch_indexability(fe):
    mod, catalog, details = fe
    вид = _вид(mod, catalog, details)
    for зпр in ({}, {"q": ["Альфа"]}, {"q": ["qzxwvbnm123"]}):
        html_ = вид.поиск(зпр)
        assert "index, follow" not in html_
        assert 'name="robots"' not in html_ or "noindex" in html_


def test_readiness_strip_survives_on_search(fe):
    mod, catalog, details = fe
    вид = _вид(mod, catalog, details)
    полоса = вид.полоса_готовности()
    if полоса:
        assert полоса in вид.поиск({"q": ["Альфа"]})
