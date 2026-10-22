"""Приёмочные тесты варианта C (party-list): несколько рецептов на компанию → общий пересчитанный список."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAIR = ["plov-s-kuricej", "grecheskij-salat"]


def get(app, path, q=None):
    return app.route(path, q or {})


def canon(html):
    m = re.search(r'<link rel="canonical" href="([^"]+)"', html)
    return m.group(1) if m else None


def test_identity_port_storage(app):
    c = app.site.cfg
    assert (c["variant_id"], c["server"]["port"], c["storage_namespace"]) == ("party-list", 8876, "fdc")
    js = (ROOT / "static" / "js" / "party.js").read_text()
    assert '"fdc.' in js and '"fd.' not in js and not (ROOT / "static" / "js" / "site.js").exists()


def test_scaling_follows_recipe_rules(site):
    guests = 8
    p = site.party(PAIR, guests)
    for it in p["items"]:
        total = 0.0
        for slug in PAIR:
            r = site.by_slug[slug]
            for i, _ in r.ingredients:
                if i.name.lower() == it["name"].lower() and i.unit == it["unit"] and i.quantity is not None:
                    total += i.quantity * (guests / r.yield_n if i.scalable and r.yield_n else 1)
        assert abs(total - it["q"]) < 1e-6, it["name"]


def test_guests_equal_servings_means_no_change(site):
    r = site.by_slug["plov-s-kuricej"]
    p = site.party([r.slug], r.servings)
    src = {
        (i.name.lower(), i.unit): i.quantity
        for i, _ in r.ingredients
        if i.quantity is not None and i.unit != "to_taste"
    }
    for it in p["items"]:
        assert abs(src[(it["name"].lower(), it["unit"])] - it["q"]) < 1e-9


def test_page_states(app):
    st, html, _ = get(app, "/na-kompaniyu/")
    assert st == 200 and canon(html) == app.site.abs("/na-kompaniyu/") and "data-plist" not in html
    st, html, _ = get(app, "/na-kompaniyu/", {"r": PAIR, "gosti": ["8"]})
    assert st == 200 and canon(html) is None and "data-plist" in html
    assert get(app, "/na-kompaniyu/", {"gosti": ["50"]})[0] == 400
    assert get(app, "/na-kompaniyu/", {"r": ["neizvestno"]})[0] == 400
