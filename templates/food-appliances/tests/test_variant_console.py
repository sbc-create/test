"""Приёмочные тесты варианта B (step-console): таблица рецептов, настройки прибора в шагах, таймеры, отметки."""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from techkitchen.server import App  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return App()


def get(app, p, q=None):
    return app.route(p, q or {})


def step_html(html, n):
    return re.search(rf'<li id="shag-{n}"[^>]*>(.*?)</li>', html, re.S).group(1)


def test_variant_identity_and_port(app):
    _, html, _ = get(app, "/")
    assert '<meta name="site-factory-variant-id" content="step-console">' in html
    assert app.site.cfg["server"]["port"] == 8866 and "8850" not in app.site.cfg["origin"]["preview"]


def test_settings_sit_in_the_source_step(app):
    for r in app.site.recipes:
        _, html, _ = get(app, r.url)
        for m in r.modes:
            assert f"«{m['name']}»" in step_html(html, m["step"]), (r.slug, m)
        for t in r.temperatures:
            assert f"{t['value_c']} °C" in step_html(html, t["step"]), (r.slug, t)
        for t in r.appliance_times:
            assert f'data-minutes="{t["min"]}"' in step_html(html, t["step"]), (r.slug, t)
        assert html.count("data-step-done=") == len(r.steps)
        # табло из A перенесено (решение владельца 13.10.2026); пульт в шагах остался
        assert html.count('class="display"') == 1


def test_home_and_appliance_tables(app):
    _, html, _ = get(app, "/")
    assert html.count('<tr><th scope="row">') == len(app.site.recipes)
    for a in ("multivarka", "aerogril"):
        items = app.site.for_appliance(a)
        if items:
            _, html, _ = get(app, f"/pribor/{a}/")
            rows = re.findall(r'<tr><th scope="row"><a href="([^"]+)"', html)
            assert rows == [r.url for r in items]


def test_storage_namespace_is_own():
    js = (ROOT / "static" / "js" / "console.js").read_text()
    assert '"fab.steps."' in js and not (ROOT / "static" / "css" / "panel.css").exists()
