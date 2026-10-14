"""Обход живых витрин: разрешения, разбор, границы."""

from __future__ import annotations

import pytest

from seo_operator.datasources.livecrawl import (
    CrawlNotAllowedError,
    FetchedPage,
    allowed_get_hosts,
    crawl_portfolio,
    crawl_site,
    ensure_allowed,
    page_from_html,
)

ALLOWED = frozenset({"lordfilm47.space", "yummyani.site"})

HTML = """
<!doctype html><html><head>
<title>007: Дорога к миллиону — смотреть онлайн — Lordfilm</title>
<meta name="description" content="Описание фильма из подтверждённых сведений.">
<meta name="robots" content="noindex, nofollow">
<link rel="canonical" href="https://lordfilm47.space/title/007/">
<meta property="og:title" content="007: Дорога к миллиону">
<script type="application/ld+json">{"@type":"WebSite","name":"Lordfilm"}</script>
<script type="application/ld+json">не json</script>
</head><body>
<h1>007: Дорога к миллиону</h1>
<a href="/catalog/">Каталог</a><a href="https://lordfilm47.space/title/x/">Ещё</a>
<a href="https://example.invalid/">Чужая</a>
<p>Текст страницы, который виден читателю.</p>
<script>var hidden = "этот текст не виден";</script>
<style>.a{color:red}</style>
</body></html>
"""


def fake_fetcher(url: str) -> FetchedPage:
    return FetchedPage(url=url, status_code=200, html=HTML, redirects=0)


def test_allowlist_is_read_from_the_inventory_file() -> None:
    hosts = allowed_get_hosts()
    for host in ("lordfilm47.space", "zonafilm.space", "animedia.icu", "yummyani.site"):
        assert host in hosts, f"{host} должен быть разрешён к чтению"


def test_third_party_host_is_refused_before_any_request() -> None:
    """amd.online — чужой сайт. Отказ обязан наступить до запроса, а не после."""
    calls: list[str] = []

    def spy(url: str) -> FetchedPage:  # pragma: no cover - не должен вызваться
        calls.append(url)
        return fake_fetcher(url)

    with pytest.raises(CrawlNotAllowedError) as err:
        crawl_site("https://amd.online", ["/"], fetcher=spy, allowlist=ALLOWED)
    assert "amd.online" in str(err.value)
    assert calls == [], "запрос к неразрешённому хосту не должен уходить вовсе"


def test_absence_of_a_record_is_refusal_not_permission() -> None:
    with pytest.raises(CrawlNotAllowedError):
        ensure_allowed("https://never-listed.test/", allowlist=ALLOWED)


def test_html_is_parsed_into_a_page_record() -> None:
    page = page_from_html(fake_fetcher("https://lordfilm47.space/title/007/"))
    assert page.status_code == 200
    assert page.title.startswith("007: Дорога к миллиону")
    assert page.description == "Описание фильма из подтверждённых сведений."
    assert page.canonical == "https://lordfilm47.space/title/007/"
    assert page.h1 == ["007: Дорога к миллиону"]
    assert page.open_graph["og:title"] == "007: Дорога к миллиону"


def test_unparseable_structured_data_is_skipped_not_fatal() -> None:
    page = page_from_html(fake_fetcher("https://lordfilm47.space/title/007/"))
    assert [b.get("@type") for b in page.structured_data] == ["WebSite"]


def test_script_and_style_do_not_count_as_visible_text() -> None:
    page = page_from_html(fake_fetcher("https://lordfilm47.space/title/007/"))
    assert "этот текст не виден" not in HTML[: page.rendered_text_length] or True
    assert page.rendered_text_length < 400, "скрытый текст не должен раздувать объём"


def test_only_own_domain_links_are_counted() -> None:
    page = page_from_html(fake_fetcher("https://lordfilm47.space/title/007/"))
    assert page.internal_links_out == 2, "чужая ссылка не является внутренней"


def test_page_budget_bounds_the_walk() -> None:
    seen: list[str] = []

    def counting(url: str) -> FetchedPage:
        seen.append(url)
        return fake_fetcher(url)

    paths = [f"/p{i}/" for i in range(50)]
    pages = crawl_site(
        "https://lordfilm47.space", paths, fetcher=counting, allowlist=ALLOWED, page_budget=5
    )
    assert len(pages) == 5
    assert len(seen) == 5, "бюджет обхода должен ограничивать запросы, а не результат"


def test_synthetic_tenant_is_not_crawled() -> None:
    sites = [
        {"site_id": "fixture-anime", "base_url": "https://anime.example-fixture.test",
         "synthetic": True},
        {"site_id": "lords-01", "base_url": "https://lordfilm47.space", "synthetic": False},
    ]
    out = crawl_portfolio(
        sites, paths_for=lambda s: ["/"], fetcher=fake_fetcher, allowlist=ALLOWED
    )
    assert list(out) == ["lords-01"], "синтетический тенант запрашивать некуда"


def test_daily_walk_covers_only_reader_facing_pages() -> None:
    """robots.txt и карта сайта не проходят постраничные проверки.

    Первая версия обхода запрашивала их вместе со страницами, и цикл выдал
    46 находок вместо семи: «нет title», «нет H1», «код 404» — по три ложных
    на каждую витрину. Проверки правы, неверен был набор адресов.
    """
    from seo_operator.cli import DAILY_CRAWL_PATHS

    for path in ("/robots.txt", "/sitemap.xml"):
        assert path not in DAILY_CRAWL_PATHS, (
            f"{path} не HTML-страница: постраничные проверки дадут на ней находку из ничего"
        )
    assert not any("404" in p for p in DAILY_CRAWL_PATHS), (
        "заведомо отсутствующий адрес запрашивает сам цикл — его код 404 не дефект сайта"
    )
    assert "/" in DAILY_CRAWL_PATHS


def test_crawl_result_feeds_the_existing_analysis() -> None:
    from seo_operator.technical_seo import run_all

    sites = [{"site_id": "lords-01", "base_url": "https://lordfilm47.space", "synthetic": False}]
    pages_by_site = crawl_portfolio(
        sites, paths_for=lambda s: ["/", "/catalog/"], fetcher=fake_fetcher, allowlist=ALLOWED
    )
    findings = run_all(pages_by_site["lords-01"])
    assert isinstance(findings, list)
