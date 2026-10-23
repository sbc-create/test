"""Конфигурация домена https://bestreciept.site: адреса на домене, индексация закрыта, SITE_CONFIG — только config/."""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fooddaily import views  # noqa: E402

ORIGIN = "https://bestreciept.site"


@pytest.fixture()
def domain_app(monkeypatch):
    monkeypatch.setenv("SITE_CONFIG", "site.bestreciept.yaml")
    from fooddaily.server import App

    return App()


def test_domain_pages_point_to_domain_and_stay_closed(domain_app):
    a = domain_app
    assert a.site.cfg["mode"] == "production" and not a.site.cfg["production_authorized"]
    assert not a.site.indexable
    urls = a.sitemap_urls()
    urls = [u[0] if isinstance(u, tuple) else u for u in urls]
    assert len(urls) > 10
    for path in urls:
        st, html, headers = a.route(path, {})
        assert st == 200, path
        canon = re.search(r'<link rel="canonical" href="([^"]+)"', html)
        assert canon and canon.group(1).startswith(ORIGIN + "/"), path
        assert "noindex" in re.search(r'name="robots" content="([^"]+)"', html).group(1), path
        assert "127.0.0.1" not in html, path
    robots = a.route("/robots.txt", {})[1]
    assert "Disallow: /" in robots.splitlines()


@pytest.mark.parametrize("bad", ["../site.yaml", "/etc/passwd", "site.yaml.bak", "other.yaml", "site..yaml"])
def test_site_config_rejects_paths_outside_config(monkeypatch, bad):
    monkeypatch.setenv("SITE_CONFIG", bad)
    with pytest.raises(ValueError):
        views.config_file()


def test_default_config_is_preview(monkeypatch):
    monkeypatch.delenv("SITE_CONFIG", raising=False)
    assert views.config_file().name == "site.yaml"
