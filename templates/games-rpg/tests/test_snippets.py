"""Сниппеты всех URL sitemap: описание 20–160 знаков; суффикс сайта в заголовке — только в пределах 70 знаков."""

import html
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from quest.server import App  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return App()


def test_titles_and_descriptions_fit(app):
    suffix = " · " + app.site.cfg["name"]
    for path in app.sitemap_urls():
        st, page, _ = app.route(path, {})
        assert st == 200, path
        title = html.unescape(re.search(r"<title>(.*?)</title>", page, re.S).group(1).strip())
        desc = html.unescape(re.search(r'<meta name="description" content="([^"]*)"', page).group(1))
        assert 20 <= len(desc) <= 160, (path, desc)
        assert len(title) <= 70 or not title.endswith(suffix), (path, title)
