"""Приёмочные тесты варианта C (home-audit): обход квартиры по комнатам и личный план."""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from udobdom.server import App  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return App()


def get(app, p, q=None):
    return app.route(p, q or {})


def canon(html):
    m = re.search(r'<link rel="canonical" href="([^"]+)"', html)
    return m.group(1) if m else None


def test_identity_port_storage(app):
    assert app.site.cfg["variant_id"] == "home-audit" and app.site.cfg["server"]["port"] == 8867
    assert app.site.cfg["storage_namespace"] == "hp-audit"
    assert not (ROOT / "static" / "js" / "home.js").exists() and not (ROOT / "static" / "css" / "rooms.css").exists()


def test_route_covers_every_room_once(app):
    rooms = app.audit_rooms()
    _, html, _ = get(app, "/")
    assert re.findall(r'<li><a href="/obhod/([a-z-]+)/">', html) == rooms
    for i, r in enumerate(rooms):
        _, html, _ = get(app, f"/obhod/{r}/")
        nxt = f"/obhod/{rooms[i + 1]}/" if i + 1 < len(rooms) else "/obhod/plan/"
        assert f'action="{nxt}"' in html
        assert html.count('name="m" value=') == len(app.site.in_room(r))


def test_selection_is_carried_between_rooms(app):
    rooms = app.audit_rooms()
    first = app.site.in_room(rooms[0])[0].slug
    st, html, _ = get(app, f"/obhod/{rooms[1]}/", {"m": [first, "neizvestno"]})
    assert st == 200 and f'<input type="hidden" name="m" value="{first}">' in html and "neizvestno" not in html
    assert canon(html) is None and 'content="noindex' in html


def test_plan_groups_rooms_and_merges_needs(app):
    mats = app.site.materials[:4]
    st, html, _ = get(app, "/obhod/plan/", {"m": [m.slug for m in mats]})
    assert st == 200 and canon(html) is None
    for m in mats:
        assert f'href="{m.url}"' in html and f'data-done="{m.slug}"' in html
    needs = {x["text"] for m in mats for x in m.need}
    block = re.search(r'<section class="plan-need".*?</section>', html, re.S).group(0)
    assert block.count("<li>") == len(needs)


def test_empty_plan_has_honest_state(app):
    st, html, _ = get(app, "/obhod/plan/")
    assert st == 200 and "Пока ничего не отмечено" in html and canon(html) == app.site.abs("/obhod/plan/")
    assert 'href="#"' not in html
