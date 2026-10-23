"""Главная и каталог: выпечка на первом экране, температура рядом с поиском, условия снимаются по одному."""

import html as h
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bakebook.server import App  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return App()


def cards(html):
    return re.findall(r'class="bcard__link" href="(/recept/[^"]+)"', html)


def test_home_order_and_no_repeats(app):
    _, html, _ = app.route("/", {})
    links = cards(html)
    assert links and len(links) == len(set(links))
    # поиск и температуры — в первом блоке; первая подборка выпечки — сразу за ним, разделы — после неё
    assert html.index('class="hero-pair"') < html.index('id="h-oven-side"') < html.index('class="block block--first"')
    assert html.index('class="block block--first"') < html.index('id="h-groups"')
    assert html.count('href="/duhovka/#t-') == len(app.site.by_temp())  # блок температур один
    heads = re.findall(r'<h2 id="h-[a-z]+">([^<]+)</h2>', html)
    assert "Новые рецепты" not in heads


def test_home_shelf_titles_match_their_cards(app):
    from bakebook.site import GROUPS

    _, html, _ = app.route("/", {})
    shelves = re.findall(r'<h2 id="h-(sweet|more)">([^<]+)</h2>(.*?)</section>', html, re.S)
    assert shelves
    for key, title, body in shelves:
        groups = {app.site.by_slug[u.split("/")[2]].group for u in cards(body)}
        if key == "sweet":
            assert title == "Торты и пирожные" and groups <= {"tort", "zavarnoe", "deserty"}
        else:  # «Пироги, печенье и хлеб» — названы ровно те разделы, что в карточках
            assert all(GROUPS[g].lower() in title.lower() for g in groups)


def test_catalog_shows_applied_conditions_and_ways_out(app):
    _, html, _ = app.route("/recepty/", {"testo": ["zavarnoe"], "duhovka": ["net"]})
    chips = [(h.unescape(a), b) for a, b in re.findall(r'class="applied__chip" href="([^"]+)"[^>]*>([^<]+)', html)]
    assert chips == [
        ("/recepty/?duhovka=net", "Тесто: заварное тесто"),
        ("/recepty/?testo=zavarnoe", "Духовка: без духовки"),
    ]
    assert not cards(html)
    ways = re.findall(r'<li><a href="([^"]+)">без условия «[^»]+»</a> — (\d+)', html)
    assert len(ways) == 2
    for href, n in ways:
        k, v = h.unescape(href).split("?")[1].split("=")
        assert len(cards(app.route("/recepty/", {k: [v]})[1])) == int(n)
    assert "applied__chip" not in app.route("/recepty/", {})[1]
