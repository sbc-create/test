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
    # первая подборка идёт сразу за поиском; разделы — в меню шапки, отдельного блока «Разделы» на главной нет
    assert html.index('class="search search--hero"') < html.index('id="quick-h"')
    assert "sections-grid" not in html and 'id="sec-h' not in html
    nav = html[html.index('<nav class="sections'):]
    assert all(f'href="/recepty/{k}/"' in nav[: nav.index("</nav>")] for k in ("zavtraki", "supy", "salaty"))


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


def test_cook_mode_has_its_own_screen_styles():
    """Режим готовки — полноэкранный слой со своими стилями, а не текст внизу страницы."""
    from pathlib import Path

    css = (Path(__file__).resolve().parents[1] / "static" / "css" / "party.css").read_text()
    rule = re.search(r"\n\.cook \{([^}]+)\}", css)
    assert rule and "position: fixed" in rule.group(1) and "inset: 0" in rule.group(1)
    assert ".cook[hidden] { display: none; }" in css
    assert re.search(r"\.cook__nav \[data-cook-next\] \{[^}]+background", css)


def test_recipe_head_groups_facts_and_actions_in_one_panel(app, site):
    r = next(x for x in site.recipes if x.yield_n and x.total_minutes)
    _, html, _ = app.route(r.url, {})
    panel = html[html.index('class="recipe__panel"'): html.index('class="recipe__body"')]
    for part in ('class="facts"', 'href="#prigotovlenie"', "data-cook-open", "data-fav=", "data-print"):
        assert part in panel
    assert html.index('class="recipe__title"') < html.index('class="recipe__panel"')


def test_text_card_keeps_favourite_out_of_title_line():
    css = open("static/css/party.css", encoding="utf-8").read()
    assert ".card:not(.card--pic) .fav { top: auto; bottom:" in css
