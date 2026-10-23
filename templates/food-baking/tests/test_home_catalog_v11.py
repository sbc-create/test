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
    # 24.10: сначала выпечка — поиск, сезонная подборка, разделы; подбор по духовке — полосой после них,
    # а быстрый доступ к нему — значок «По температуре» в шапке
    marks = ('class="find find--hero"', 'class="block block--first"', 'id="h-groups"', 'id="h-oven"')
    order = [html.index(x) for x in marks]
    assert order == sorted(order)
    head = html[html.index('<header class="spine"'): html.index("</header>")]
    assert 'href="/duhovka/"' in head and 'href="/pechem/"' in head
    menu = head[head.index('class="toc-nav"'):]
    assert 'href="/duhovka/"' not in menu  # меню — только разделы выпечки
    # число рецептов при температуре — отдельный значок, для скринридера — словами
    badge = r'180 °C<span class="temp-jump__n" aria-hidden="true">\d+</span><span class="sr"> — \d+ рецепт'
    assert re.search(badge, html)
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


def test_card_shows_oven_and_bake_time_only_from_recipe(app):
    _, html, _ = app.route("/recepty/", {})
    shown = [r for r in app.site.recipes if f'href="{r.url}"' in html]
    assert len(shown) >= 10
    for r in shown:
        card = html[html.index(f'href="{r.url}"'):]
        bake = card[card.index('class="bcard__bake"'): card.index("</p>", card.index('class="bcard__bake"'))]
        if r.temps:
            assert f"{r.temps[0]}" in bake
        else:
            assert "без духовки" in bake
        # время выпекания — только когда в рецепте один этап выпекания; несколько этапов не сводятся в одно число
        # и при одной температуре: «220 / 200 °C · 20 мин» не говорит, к какой температуре относится время
        assert ("bcard__bt" in bake) == (len(r.temps) == 1 and len(r.oven["bake_times"]) == 1)


def test_recipe_panel_holds_facts_and_jump(app):
    r = app.site.recipes[0]
    _, html, _ = app.route(r.url, {})
    panel = html[html.index('class="recipe-panel"'): html.index('class="sheet-b__body"')]
    assert 'class="facts-b"' in panel and 'href="#prigotovlenie"' in panel and "facts-b__oven" in panel


def test_view_alone_is_not_a_filter_condition(app):
    _, html, _ = app.route("/recepty/", {"vid": ["tablica"]})
    assert "<h1>Все рецепты выпечки</h1>" in html and "по выбранным условиям" not in html and ">Обычный вид</a>" in html
    _, html, _ = app.route("/recepty/", {"duhovka": ["net"]})
    assert "<h1>Подбор выпечки</h1>" in html and "по выбранным условиям" in html


def test_doughs_page_counts_in_words(app):
    _, html, _ = app.route("/testo/", {})
    assert re.search(r"<i>\d+ рецепт(а|ов)? →</i>", html)


def test_image_jobs_first_delivery_is_home_first_cards(app):
    import json
    from pathlib import Path

    spec = json.loads(Path("data/media/image-jobs.json").read_text(encoding="utf-8"))
    _, html, _ = app.route("/", {})
    first = list(dict.fromkeys(re.findall(r'class="bcard__link" href="/recept/([^/"]+)/"', html)))[:6]
    assert spec["first_delivery"] == first == [j["slug"] for j in spec["jobs"][:6]]
    assert all(j["recipe_id"] and j["alt"] and j["kind"] == "illustration" for j in spec["jobs"])


def test_multistage_bake_step_is_not_reduced_to_one_number(app):
    # «Пеките 20 минут, затем при 200 градусах ещё 15–20 минут»: извлечён один таймер на два этапа —
    # сводка не пишет «Выпекать 20 мин», а отправляет к шагу
    r = next(x for x in app.site.recipes if x.slug == "tort-karpatka")
    assert r.bake_unclear_steps == {8}
    _, html, _ = app.route(r.url, {})
    bake = re.search(r'facts-b__bake"><span>Выпекать</span><b>(.*?)</b>', html).group(1)
    assert bake.startswith("в несколько этапов") and "20 мин" not in bake
    # «за 10–20 минут до конца», «1 часа 20 минут», «затем дно, — … 10 минут» — не этапы
    assert not [x.slug for x in app.site.recipes if x.bake_unclear_steps and x.slug != "tort-karpatka"]


def test_search_refine_counts_match_cards(app):
    _, html, _ = app.route("/poisk/", {"q": ["шоколад"]})
    total = len(cards(html))
    chips = re.findall(r'razdel=([a-z]+)"[^>]*>[^<]+<span class="refine__n">(\d+)</span>', html)
    assert chips and sum(int(n) for _, n in chips) == total
    for key, n in chips:
        _, part, _ = app.route("/poisk/", {"q": ["шоколад"], "razdel": [key]})
        assert len(cards(part)) == int(n)


def test_batch_oven_plan_keeps_multistage_honest(app):
    _, html, _ = app.route("/pechem/", {"r": ["tort-karpatka", "limonnyj-keks"]})
    plan = re.sub(r"<[^>]+>", " ", re.search(r'<ol class="ovenline">(.*?)</ol>', html, re.S).group(1))
    assert "(220 → 200 °C)" in plan and "в несколько этапов" in plan
    assert not re.search(r"вишней\s*—\s*20 мин", plan)
