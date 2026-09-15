"""Поадресная готовность к индексации."""

from __future__ import annotations

import pytest

from seo_operator.eligibility import (
    HOLD,
    READY,
    USEFUL_TEXT_MIN_CHARS,
    classify,
    classify_all,
    sitemap_candidates,
    summarize,
)
from seo_operator.technical_seo import Page


def good_page(**kw) -> Page:
    defaults = {
        "url": "https://lordfilm47.space/title/007-doroga-k-millionu/",
        "status_code": 200,
        "title": "007: Дорога к миллиону — смотреть онлайн",
        "description": "Описание фильма, собранное из подтверждённых сведений каталога.",
        "h1": ["007: Дорога к миллиону"],
        "canonical": "https://lordfilm47.space/title/007-doroga-k-millionu/",
        "indexable": False,
        "rendered_text_length": 1525,
        "open_graph": {"og:title": "007: Дорога к миллиону"},
        "structured_data": [{"@type": "WebSite"}, {"@type": "BreadcrumbList"}],
        "internal_links_in": 4,
        "internal_links_out": 12,
        "player_available": True,
    }
    defaults.update(kw)
    return Page(**defaults)


def test_complete_page_is_ready() -> None:
    result = classify(good_page(), site_host="lordfilm47.space", require_player=True)
    assert result.verdict == READY
    assert result.reasons == ()


def test_global_indexing_lock_is_not_a_reason_to_hold() -> None:
    """Замок на индексации — намеренное состояние, а не дефект страницы.

    Если бы он считался причиной, готовых адресов не было бы ни одного и
    измерять готовность было бы нечем.
    """
    locked = good_page(indexable=False)
    assert classify(locked, site_host="lordfilm47.space").verdict == READY


def test_page_level_noindex_does_hold() -> None:
    result = classify(good_page(), site_host="lordfilm47.space", page_level_noindex=True)
    assert result.verdict == HOLD
    assert "PAGE_RULE_NOINDEX" in result.reasons


def test_cross_domain_canonical_holds_and_names_the_foreign_host() -> None:
    page = good_page(canonical="https://lordfilm47.space/title/22-7/")
    result = classify(page, site_host="animedia.space")
    assert result.verdict == HOLD
    assert "CROSS_DOMAIN_CANONICAL:lordfilm47.space" in result.reasons


def test_unmeasured_field_is_a_reason_not_an_unknown_verdict() -> None:
    page = good_page(status_code=None, rendered_text_length=None)
    result = classify(page, site_host="lordfilm47.space")
    assert result.verdict == HOLD
    assert "NOT_MEASURED:status_code" in result.reasons
    assert "NOT_MEASURED:rendered_text_length" in result.reasons


def test_thin_page_is_held() -> None:
    page = good_page(rendered_text_length=USEFUL_TEXT_MIN_CHARS - 1)
    assert "THIN_CONTENT" in classify(page, site_host="lordfilm47.space").reasons


def test_watchable_page_without_player_is_held() -> None:
    page = good_page(player_available=False)
    result = classify(page, site_host="lordfilm47.space", require_player=True)
    assert "PLAYER_UNAVAILABLE" in result.reasons


def test_player_is_only_required_where_it_is_asked_for() -> None:
    page = good_page(player_available=False)
    result = classify(page, site_host="lordfilm47.space", require_player=False)
    assert result.verdict == READY


@pytest.mark.parametrize(
    "marker",
    [
        "SITE_LEGAL_NAME",
        "SITE_CONTACT_EMAIL",
        "будут опубликованы после заполнения",
        "сведения не выдумываются",
        "тестовая витрина",
    ],
)
def test_public_placeholder_is_never_ready(marker: str) -> None:
    page = good_page(description=f"Текст витрины. {marker}. Продолжение текста.")
    result = classify(page, site_host="lordfilm47.space")
    assert result.verdict == HOLD
    assert any(r.startswith("PLACEHOLDER:") for r in result.reasons)


def test_orphan_page_is_held() -> None:
    page = good_page(internal_links_in=0)
    assert "ORPHAN" in classify(page, site_host="lordfilm47.space").reasons


def test_structured_data_inside_graph_counts() -> None:
    page = good_page(structured_data=[{"@graph": [{"@type": "TVSeries"}]}])
    assert classify(page, site_host="lordfilm47.space").verdict == READY


def test_summary_has_no_unknown_bucket_and_counts_reasons() -> None:
    pages = [
        good_page(),
        good_page(url="https://lordfilm47.space/a/", canonical="https://lordfilm47.space/a/",
                  rendered_text_length=10),
        good_page(url="https://lordfilm47.space/b/", canonical="https://lordfilm47.space/b/",
                  internal_links_in=0),
    ]
    results = classify_all(pages, site_host="lordfilm47.space")
    summary = summarize(results)
    assert summary.total == 3
    assert summary.ready == 1
    assert summary.hold == 2
    assert summary.unknown == 0
    assert summary.by_reason["THIN_CONTENT"] == 1
    assert summary.by_reason["ORPHAN"] == 1
    assert summary.coverage_percent == pytest.approx(33.33)


def test_only_ready_urls_are_offered_to_a_future_sitemap() -> None:
    pages = [
        good_page(),
        good_page(url="https://lordfilm47.space/thin/", canonical="https://lordfilm47.space/thin/",
                  rendered_text_length=1),
    ]
    candidates = sitemap_candidates(classify_all(pages, site_host="lordfilm47.space"))
    assert candidates == ["https://lordfilm47.space/title/007-doroga-k-millionu/"]


def test_every_page_gets_a_verdict() -> None:
    pages = [good_page(url=f"https://lordfilm47.space/p{i}/") for i in range(25)]
    results = classify_all(pages, site_host="lordfilm47.space")
    assert len(results) == len(pages)
    assert all(r.verdict in (READY, HOLD) for r in results)
    assert summarize(results).unknown == 0
