"""Технические SEO-проверки."""
import pytest

from seo_operator.technical import Page, run_all, summarize
from seo_operator import technical as t


def _p(url="/a", **kw):
    return Page(url=url, **kw)


def test_server_error_is_critical():
    f = t.check_status_and_redirects([_p(status=503)])
    assert f[0].severity == "critical"


def test_linked_404_is_flagged_as_broken_link():
    f = t.check_status_and_redirects([_p(status=404, internal_links_in=5)])
    assert f[0].check == "broken_internal_link" and f[0].auto_fixable


def test_redirect_chain_detected():
    pages = [_p("/a", status=301, redirect_to="/b"), _p("/b", status=301, redirect_to="/c"),
             _p("/c", status=301, redirect_to="/d"), _p("/d")]
    assert any(f.check == "redirect_chain" for f in t.check_status_and_redirects(pages))


def test_cross_domain_canonical_is_critical():
    f = t.check_canonical([_p(canonical="https://other.invalid/x")], "demo.invalid")
    assert f[0].check == "canonical_cross_domain" and f[0].severity == "critical"


def test_sitemap_noindex_conflict():
    f = t.check_robots_conflicts([_p(robots_meta="noindex,follow", in_sitemap=True)])
    assert f[0].check == "sitemap_noindex_conflict"


def test_contradictory_robots_signals():
    f = t.check_robots_conflicts([_p(robots_meta="index,follow", x_robots="noindex")])
    assert any(x.check == "robots_signal_conflict" for x in f)


def test_sitemap_explosion_is_critical():
    pages = [_p(f"/{i}", in_sitemap=True) for i in range(100)]
    f = t.check_sitemap(pages, previous_sitemap_count := 10)
    assert any(x.check == "sitemap_explosion" for x in f)


def test_empty_indexable_page_is_critical():
    f = t.check_thin_and_duplicate([_p(rendered_main_text="")])
    assert f[0].check == "empty_page"


def test_thin_page_flagged():
    f = t.check_thin_and_duplicate([_p(rendered_main_text="слово " * 20)])
    assert any(x.check == "thin_page" for x in f)


def test_noindex_thin_page_not_flagged():
    f = t.check_thin_and_duplicate([_p(rendered_main_text="", robots_meta="noindex")])
    assert f == []


def test_duplicate_content_detected():
    pages = [_p("/a", content_hash="h", rendered_main_text="слово " * 200),
             _p("/b", content_hash="h", rendered_main_text="слово " * 200)]
    assert any(x.check == "duplicate_content" for x in t.check_thin_and_duplicate(pages))


def test_duplicate_titles_detected():
    pages = [_p("/a", title="Т", rendered_main_text="w " * 200),
             _p("/b", title="Т", rendered_main_text="w " * 200)]
    assert any(x.check == "duplicate_title" for x in t.check_thin_and_duplicate(pages))


def test_crawl_trap_detected():
    f = t.check_crawl_traps([_p("/list?a=1&b=2&c=3&d=4")])
    assert f[0].check == "crawl_trap"


def test_parameter_explosion_detected():
    pages = [_p(f"/l?page={i}") for i in range(60)]
    assert any(x.check == "parameter_explosion" for x in t.check_crawl_traps(pages))


def test_orphan_page_detected():
    f = t.check_orphans_and_depth([_p(depth=3, internal_links_in=0)])
    assert f[0].check == "orphan_page" and f[0].auto_fixable


def test_fake_review_schema_is_critical():
    f = t.check_structured_data([_p(structured_data=[{"@type": "Review"}])])
    assert f[0].check == "fake_review_schema" and f[0].severity == "critical"


def test_genuine_review_schema_passes():
    f = t.check_structured_data([_p(structured_data=[{"@type": "Review", "_is_genuine_review": True}])])
    assert f == []


def test_fabricated_aggregate_rating_is_critical():
    f = t.check_structured_data([_p(structured_data=[{"@type": "AggregateRating", "reviewCount": 100}])])
    assert any(x.check == "fabricated_rating" for x in f)


def test_real_aggregate_rating_passes():
    f = t.check_structured_data([_p(structured_data=[
        {"@type": "AggregateRating", "reviewCount": 100, "_from_real_published_ratings": True}])])
    assert f == []


def test_video_schema_without_media_flagged():
    f = t.check_structured_data([_p(media_available=False,
                                    structured_data=[{"@type": "VideoObject"}])])
    assert any(x.check == "video_schema_without_media" for x in f)


def test_cls_and_lcp_budgets():
    f = t.check_performance([_p(cls=0.4, lcp_ms=5000, console_errors=2, mobile_parity=False)])
    checks = {x.check for x in f}
    assert {"cls_regression", "lcp_regression", "console_errors", "mobile_parity"} <= checks


def test_staging_leak_is_critical():
    f = t.check_leaks([_p("https://staging.demo.invalid/x")], "demo.invalid")
    assert f[0].check == "staging_leak"


def test_cross_tenant_link_flagged():
    f = t.check_leaks([_p("https://demo.invalid/a", internal_links_out=["https://other.invalid/b"])],
                      "demo.invalid", other_domains=["other.invalid"])
    assert any(x.check == "cross_tenant_link" for x in f)


def test_run_all_sorts_by_severity_and_summarizes():
    pages = [
        _p("/ok", title="A", description="d", h1="H", rendered_main_text="слово " * 200,
           canonical="https://demo.invalid/ok", in_sitemap=True, internal_links_in=3),
        _p("/broken", status=503, internal_links_in=1),
    ]
    findings = run_all(pages, "demo.invalid")
    assert findings[0].severity == "critical"
    s = summarize(findings)
    assert s["total"] == len(findings) and "http_status" in s["blocking"]
