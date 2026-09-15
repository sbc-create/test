"""Проверка инфраструктурных адресов витрины."""

from __future__ import annotations

from seo_operator.infrastructure_probe import (
    ABSENT_PATH,
    Probe,
    as_dicts,
    check_absent_path,
    check_declared_endpoint,
    check_robots,
    check_sitemap,
    probe_site,
)

XML = "application/xml; charset=utf-8"


def probe(url="https://lordfilm47.space/x", status=200, ctype=XML, body="") -> Probe:
    return Probe(url=url, status_code=status, content_type=ctype, body=body)


def test_healthy_robots_has_no_findings() -> None:
    assert check_robots(probe(ctype="text/plain", body="User-agent: *\nDisallow: /\n")) == []


def test_missing_robots_is_critical() -> None:
    found = check_robots(probe(status=404, body=""))
    assert [f.id for f in found] == ["INF-001"]
    assert found[0].severity == "критично"


def test_empty_robots_is_reported() -> None:
    assert [f.id for f in check_robots(probe(ctype="text/plain", body="  "))] == ["INF-002"]


def test_sitemap_with_entries_when_expected_is_clean() -> None:
    body = "<urlset><url><loc>https://lordfilm47.space/</loc></url></urlset>"
    assert check_sitemap(probe(body=body), expect_entries=True) == []


def test_empty_sitemap_when_entries_expected_is_a_finding() -> None:
    """Ровно состояние yummyani.site на 2026-09-15: код 200 и пустой urlset."""
    body = '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>'
    found = check_sitemap(probe(body=body), expect_entries=True)
    assert [f.id for f in found] == ["INF-005"]


def test_empty_sitemap_is_not_a_finding_when_the_site_shows_nothing() -> None:
    """Витрина, чьи страницы дублируют соседнюю, не предъявляет их поиску.

    Ожидание приходит снаружи, а не выводится из вида документа: иначе честное
    решение редакции выглядело бы дефектом.
    """
    body = "<urlset></urlset>"
    assert check_sitemap(probe(body=body), expect_entries=False) == []


def test_entries_where_none_are_expected_are_reported() -> None:
    body = "<urlset><url><loc>https://x/</loc></url></urlset>"
    assert [f.id for f in check_sitemap(probe(body=body), expect_entries=False)] == ["INF-006"]


def test_unknown_policy_judges_the_sitemap_neither_way() -> None:
    """Неизвестная политика — причина промолчать, а не выбрать любую сторону.

    Подставив вместо неизвестности «карта должна быть пустой», проверка
    объявила дефектом нормальные карты Lords с пятьюдесятью тысячами адресов.
    Обратная подстановка так же неверна.
    """
    full = "<urlset><url><loc>https://x/</loc></url></urlset>"
    empty = "<urlset></urlset>"
    assert check_sitemap(probe(body=full), expect_entries=None) == []
    assert check_sitemap(probe(body=empty), expect_entries=None) == []


def test_sitemap_served_as_html_is_a_finding() -> None:
    body = "<urlset><url><loc>https://x/</loc></url></urlset>"
    found = check_sitemap(probe(ctype="text/html", body=body), expect_entries=True)
    assert [f.id for f in found] == ["INF-004"]


def test_absent_path_answering_404_is_correct() -> None:
    assert check_absent_path(probe(status=404)) == []


def test_absent_path_answering_200_is_a_soft_404() -> None:
    found = check_absent_path(probe(status=200))
    assert [f.id for f in found] == ["INF-007"]
    assert found[0].severity == "критично"
    assert "поиск примет страницу за настоящую" in found[0].summary


def test_absent_path_answering_something_else_is_milder() -> None:
    assert [f.id for f in check_absent_path(probe(status=500))] == ["INF-008"]


def test_declared_endpoint_returning_html_404_is_a_finding() -> None:
    """Состояние /api/v1/coverage на трёх витринах Lords, 2026-09-15.

    Матрица объявляет endpoint, витрина отдаёт HTML «Страница не найдена».
    Объявление, которому ничего не соответствует, хуже отсутствующего.
    """
    found = check_declared_endpoint(probe(status=404, ctype="text/html", body="<html>"))
    assert [f.id for f in found] == ["INF-009"]


def test_declared_endpoint_returning_wrong_type_is_a_finding() -> None:
    found = check_declared_endpoint(probe(status=200, ctype="text/html", body="<html>"))
    assert [f.id for f in found] == ["INF-010"]


def test_declared_endpoint_returning_json_is_clean() -> None:
    assert check_declared_endpoint(probe(status=200, ctype="application/json", body="{}")) == []


def test_probe_site_walks_every_expected_address() -> None:
    asked: list[str] = []

    def fetcher(url: str) -> Probe:
        asked.append(url)
        if url.endswith("/robots.txt"):
            return probe(url=url, ctype="text/plain", body="User-agent: *\nDisallow: /\n")
        if url.endswith("/sitemap.xml"):
            return probe(url=url, body="<urlset><url><loc>https://a/</loc></url></urlset>")
        if url.endswith(ABSENT_PATH):
            return probe(url=url, status=404, ctype="text/html", body="")
        return probe(url=url, status=200, ctype="application/json", body="{}")

    found = probe_site(
        "https://lordfilm47.space",
        fetcher=fetcher,
        expect_sitemap_entries=True,
        coverage_endpoint="/api/v1/coverage",
    )
    assert found == []
    assert [u.rsplit("lordfilm47.space", 1)[-1] for u in asked] == [
        "/robots.txt",
        "/sitemap.xml",
        ABSENT_PATH,
        "/api/v1/coverage",
    ]


def test_endpoint_is_not_probed_when_nothing_is_declared() -> None:
    asked: list[str] = []

    def fetcher(url: str) -> Probe:
        asked.append(url)
        return probe(url=url, status=404, ctype="text/html", body="")

    probe_site("https://x.test", fetcher=fetcher, expect_sitemap_entries=False)
    assert not any("coverage" in u for u in asked)


def test_findings_convert_to_the_common_shape() -> None:
    found = check_absent_path(probe(status=200))
    payload = as_dicts(found)
    assert payload[0]["category"] == "infrastructure"
    assert payload[0]["affected_urls"] == [found[0].url]
