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


def test_paginated_description_keeps_whole_sentences_within_limit():
    """С 39 рецептами «Завтраки» стали двухстраничными: «… Страница 2 из 2.» выводило описание за 160 знаков."""
    from fooddaily.seo import fit_description

    head = "Сырники, оладьи, каши и яйца — то, что успеваешь утром."
    long = head + " 12 рецептов: " + ", ".join(["Блюдо"] * 20) + "."
    out = fit_description(long, 160 - len(" Страница 2 из 2."))
    assert out == head
    assert fit_description("Коротко.", 50) == "Коротко."
    assert fit_description("Одно " * 40, 30).endswith("…") and len(fit_description("Одно " * 40, 30)) <= 30
