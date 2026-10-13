"""Сниппеты всех индексируемых страниц: описание 20–160 знаков и без «шт.»-заглушек; заголовок с суффиксом сайта —
только если он помещается в 70 знаков, иначе заголовок страницы без суффикса."""

import html
import re


def test_titles_and_descriptions_fit(app):
    suffix = app.site.cfg["seo"]["title_suffix"]
    for path, _ in app.sitemap_urls():
        st, page, _ = app.route(path, {})
        assert st == 200, path
        title = html.unescape(re.search(r"<title>(.*?)</title>", page, re.S).group(1).strip())
        desc = html.unescape(re.search(r'<meta name="description" content="([^"]*)"', page).group(1))
        assert 20 <= len(desc) <= 160 and not re.search(r"\d шт\.$", desc), (path, desc)
        assert len(title) <= 70 or not title.endswith(suffix), (path, title)
