"""Смена адреса рецепта: постоянный редирект со старого адреса, старый адрес нигде не публикуется."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD, NEW = "/recept/kurica-v-slivochnom-souse/", "/recept/kurica-v-smetanno-chesnochnom-souse/"


def test_old_address_redirects_permanently(app):
    assert json.loads((ROOT / "data" / "redirects.json").read_text())[OLD] == NEW
    st, _, headers = app.route(OLD, {})
    assert st == 301 and headers["Location"] == NEW
    st, html, _ = app.route(NEW, {})
    assert st == 200 and "Курица в сметанно-чесночном соусе" in html
    assert f'<link rel="canonical" href="{app.site.abs(NEW)}">' in html


def test_old_address_not_published(app):
    urls = [u for u, _ in app.sitemap_urls()]
    assert NEW in urls and OLD not in urls
    for u in urls:
        _, html, _ = app.route(u, {})
        assert OLD not in html, u


def test_redirect_targets_exist(app):
    for old, new in json.loads((ROOT / "data" / "redirects.json").read_text()).items():
        assert app.route(new, {})[0] == 200 and app.route(old, {})[0] == 301
