"""Живой обход сверяет canonical с доменом сайта, а не с адресом обхода.

Это разные вещи, и спутать их легко. Обход идёт по origin цели: на staging это
`http://127.0.0.1:<порт>`, потому что сайт слушает loopback за прокси.
Canonical на странице — публичный домен, `https://…`. Сравнение canonical с
адресом обхода пометило бы чужим доменом каждую индексируемую страницу и
превратило бы ворота в генератор ложных отказов.

Интеграционный тест обхода требует развёрнутой цели и в обычном прогоне не
запускается, поэтому проверка сделана здесь: `Crawler.fetch` подменяется, а
`routes.json` пишется вручную.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.seo import crawl as crawl_mod

PUBLIC = "https://pilot.localhost.test"
CRAWL_TARGET = "http://127.0.0.1:8123"


def _page(canonical: str) -> str:
    return (
        "<html><head>"
        f'<link rel="canonical" href="{canonical}">'
        "<title>Заголовок страницы</title>"
        "</head><body><h1>Заголовок</h1></body></html>"
    )


@pytest.fixture
def build(tmp_path: Path) -> Path:
    routes = {
        "base_url": PUBLIC,
        "max_depth": 2,
        "routes": [
            {
                "path": "/",
                "status": 200,
                "indexable": True,
                "in_sitemap": False,
                "canonical": f"{PUBLIC}/",
                "page_type": "home",
            }
        ],
        "redirects": [],
    }
    (tmp_path / "routes.json").write_text(json.dumps(routes), encoding="utf-8")
    return tmp_path


def _serve(monkeypatch, body: str) -> None:
    def fake_fetch(self, path: str):  # noqa: ANN001, ARG001
        return crawl_mod.Response(status=200, headers={}, body=body)

    monkeypatch.setattr(crawl_mod.Crawler, "fetch", fake_fetch)


def test_public_canonical_is_not_reported_as_foreign_domain(build, monkeypatch):
    """Обход по loopback, canonical публичный — это норма, а не нарушение."""
    _serve(monkeypatch, _page(f"{PUBLIC}/"))
    report = crawl_mod.crawl(CRAWL_TARGET, build, environment="staging")
    foreign = [f for f in report.findings if f.rule == "HR-2"]
    assert not foreign, [f.message for f in foreign]


def test_canonical_on_a_genuinely_foreign_domain_is_still_caught(build, monkeypatch):
    """Подмена домена обязана ловиться — ради неё проверка и существует."""
    _serve(monkeypatch, _page("https://attacker.tld/"))
    report = crawl_mod.crawl(CRAWL_TARGET, build, environment="staging")
    assert any(f.rule == "HR-2" for f in report.findings)


def test_canonical_pointing_at_another_page_of_the_same_site_is_caught(build, monkeypatch):
    """Свой домен, но другой путь — тот дефект, ради которого правилась сверка."""
    _serve(monkeypatch, _page(f"{PUBLIC}/arhiv/"))
    report = crawl_mod.crawl(CRAWL_TARGET, build, environment="staging")
    assert any(f.rule == "HR-1" and f.check == "canonical" for f in report.findings)
