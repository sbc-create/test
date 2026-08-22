"""Technical SEO check tests. Each check gets a positive and a negative case."""

from __future__ import annotations

from seo_operator.technical_seo import Page, run_all

CLEAN = Page(
    url="https://a.example/title/1",
    status_code=200,
    title="Название сериала — 2 сезон",
    description="Описание страницы длиной в разумных пределах для сниппета.",
    h1=["Название сериала"],
    canonical="https://a.example/title/1",
    indexable=True,
    raw_html_text_length=5000,
    rendered_text_length=5200,
    open_graph={"og:title": "t", "og:description": "d", "og:image": "i", "og:type": "video"},
    internal_links_in=4,
    in_sitemap=True,
    lastmod="2026-08-20",
    player_available=True,
    content_status="published",
    lcp_ms=1800,
    cls=0.02,
    queries=["название сериала 2 сезон"],
)


def ids(findings):
    return {f["id"] for f in findings}


def test_clean_page_produces_no_findings():
    assert run_all([CLEAN]) == []


def test_empty_crawl_produces_no_findings():
    """An empty findings list must mean 'clean', and only ever come from a real run."""
    assert run_all([]) == []


def test_js_only_html_flagged():
    p = Page(
        url="https://a.example/x",
        raw_html_text_length=100,
        rendered_text_length=5000,
        indexable=True,
        internal_links_in=1,
        in_sitemap=True,
        title="t",
        description="d",
        h1=["h"],
        canonical="https://a.example/x",
        open_graph=CLEAN.open_graph,
        status_code=200,
    )
    assert "SSR-001" in ids(run_all([p]))


def test_duplicate_titles_flagged():
    a = Page(
        url="https://a.example/1",
        title="Одинаковый",
        indexable=True,
        in_sitemap=True,
        internal_links_in=1,
        open_graph=CLEAN.open_graph,
        description="d",
        h1=["h"],
        canonical="https://a.example/1",
        status_code=200,
    )
    b = Page(
        url="https://a.example/2",
        title="Одинаковый",
        indexable=True,
        in_sitemap=True,
        internal_links_in=1,
        open_graph=CLEAN.open_graph,
        description="d",
        h1=["h"],
        canonical="https://a.example/2",
        status_code=200,
    )
    assert "ONP-003" in ids(run_all([a, b]))


def test_long_title_flagged():
    p = Page(url="https://a.example/1", title="Очень длинный заголовок " * 5)
    assert "ONP-002" in ids(run_all([p]))


def test_cross_canonical_flagged():
    p = Page(url="https://a.example/1", canonical="https://a.example/other")
    assert "IDX-001" in ids(run_all([p]))


def test_self_canonical_with_trailing_slash_is_not_flagged():
    p = Page(url="https://a.example/1/", canonical="https://a.example/1")
    assert "IDX-001" not in ids(run_all([p]))


def test_error_status_is_critical():
    p = Page(url="https://a.example/1", status_code=500)
    findings = [f for f in run_all([p]) if f["id"] == "TEC-001"]
    assert findings and findings[0]["severity"] == "critical"


def test_redirect_chain_flagged():
    p = Page(url="https://a.example/1", redirect_chain=["/a", "/b", "/c"])
    assert "TEC-002" in ids(run_all([p]))


def test_orphan_flagged():
    p = Page(url="https://a.example/1", indexable=True, internal_links_in=0)
    assert "LNK-001" in ids(run_all([p]))


def test_missing_from_sitemap_flagged():
    p = Page(url="https://a.example/1", indexable=True, in_sitemap=False, internal_links_in=2)
    assert "IDX-002" in ids(run_all([p]))


def test_fabricated_rating_markup_is_critical():
    """Markup asserting a rating with no on-page confirmation must be blocked."""
    p = Page(
        url="https://a.example/1",
        structured_data=[{"@type": "Movie", "aggregateRating": {"ratingValue": 9.1}}],
    )
    findings = [f for f in run_all([p]) if f["id"] == "SD-002"]
    assert findings and findings[0]["severity"] == "critical"


def test_verified_rating_markup_is_allowed():
    p = Page(
        url="https://a.example/1",
        status_code=200,
        title="t",
        description="d",
        h1=["h"],
        canonical="https://a.example/1",
        indexable=True,
        internal_links_in=1,
        in_sitemap=True,
        lastmod="2026-08-20",
        open_graph=CLEAN.open_graph,
        raw_html_text_length=100,
        rendered_text_length=100,
        structured_data=[
            {"@type": "Movie", "aggregateRating": {"ratingValue": 9.1}, "_verified_on_page": True}
        ],
    )
    assert "SD-002" not in ids(run_all([p]))


def test_cannibalization_flagged():
    a = Page(
        url="https://a.example/1",
        indexable=True,
        queries=["смотреть онлайн"],
        internal_links_in=1,
        in_sitemap=True,
    )
    b = Page(
        url="https://a.example/2",
        indexable=True,
        queries=["Смотреть Онлайн"],
        internal_links_in=1,
        in_sitemap=True,
    )
    assert "ONP-008" in ids(run_all([a, b]))


def test_broken_player_on_published_page_is_critical():
    p = Page(url="https://a.example/1", player_available=False, content_status="published")
    findings = [f for f in run_all([p]) if f["id"] == "TEC-003"]
    assert findings and findings[0]["severity"] == "critical"


def test_unpublished_page_with_no_player_is_not_flagged():
    p = Page(url="https://a.example/1", player_available=False, content_status="draft")
    assert "TEC-003" not in ids(run_all([p]))


def test_core_web_vitals_flagged():
    p = Page(url="https://a.example/1", lcp_ms=4000, cls=0.3)
    assert {"PRF-001", "PRF-002"} <= ids(run_all([p]))


def test_unmeasured_vitals_are_not_flagged():
    """None means 'not measured' and must not be treated as a failure."""
    p = Page(url="https://a.example/1", lcp_ms=None, cls=None)
    assert not ({"PRF-001", "PRF-002"} & ids(run_all([p])))


def test_findings_sorted_by_severity():
    p = Page(url="https://a.example/1", status_code=500, title="x" * 100)
    sev = [f["severity"] for f in run_all([p])]
    assert sev == sorted(sev, key=lambda s: ["critical", "high", "medium", "low", "info"].index(s))
