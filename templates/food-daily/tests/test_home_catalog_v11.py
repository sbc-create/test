"""Главная и каталог: блюда на первом экране, подборки без повторов, выбранные условия снимаются по одному."""

import html as h
import re


def cards(html):
    return re.findall(r'class="card__link" href="(/recept/[^"]+)"', html)


def test_home_shelves_follow_tasks_without_repeats(app):
    _, html, _ = app.route("/", {})
    links = cards(html)
    assert links and len(links) == len(set(links))  # каждое блюдо на главной — один раз
    heads = re.findall(r'<h2 id="[a-z]+-h">([^<]+)</h2>', html)
    assert heads[:2] == ["Быстро: до 30 минут", "На завтрак"]
    assert "Супы" in heads and "К обеду и ужину: вторые блюда" in heads
    assert "Новые рецепты" not in heads
    # первая подборка идёт сразу за поиском: «Разделы» на телефоне — после неё
    assert html.index('id="quick-h"') < html.index('class="shelf shelf--flow"')


def test_few_ingredients_collection_counts_listed_products(site):
    title, _, items = site.collections()["do-shesti-produktov"]
    assert title == "До шести продуктов"
    assert items and all(len(r.ingredients) <= 6 for r in items)
    assert not [r for r in site.recipes if len(r.ingredients) <= 6 and r not in items]


def test_catalog_shows_applied_conditions_and_ways_out_of_empty_result(app):
    _, html, _ = app.route("/recepty/", {"produkt": ["kurica"], "vremya": ["do-20"], "tip": ["supy"]})
    chips = [(h.unescape(a), b) for a, b in re.findall(r'class="applied__chip" href="([^"]+)"[^>]*>([^<]+)', html)]
    assert chips == [
        ("/recepty/?vremya=do-20&tip=supy", "Продукт: курица"),
        ("/recepty/?produkt=kurica&tip=supy", "Время: до 20 минут"),
        ("/recepty/?produkt=kurica&vremya=do-20", "Раздел: супы"),
    ]
    ways = re.findall(r'<li><a href="[^"]+">без условия «([^»]+)»</a> — (\d+)', html)
    assert ways and all(int(n) > 0 for _, n in ways)  # «без условия — 0 рецептов» не предлагается
    for label, n in ways:
        href = h.unescape({b: a for a, b in chips}[label])
        q = dict(x.split("=") for x in href.split("?")[1].split("&"))
        _, again, _ = app.route("/recepty/", {k: [v] for k, v in q.items()})
        assert len(cards(again)) == int(n)
    _, plain, _ = app.route("/recepty/", {})
    assert "applied__chip" not in plain
