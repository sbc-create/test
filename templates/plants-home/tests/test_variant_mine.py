"""Приёмочные тесты варианта C (my-collection): коллекция, сводка ядовитости и света, этикетки ухода."""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from flora.server import App  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return App()


def get(app, p, q=None):
    return app.route(p, q or {})


def canon(html):
    m = re.search(r'<link rel="canonical" href="([^"]+)"', html)
    return m.group(1) if m else None


def test_identity_port_storage(app):
    c = app.site.cfg
    assert (c["variant_id"], c["server"]["port"], c["storage_namespace"]) == ("my-collection", 8869, "ph-mine")
    assert not (ROOT / "static" / "js" / "herbarium.js").exists()


def test_toxicity_summary_follows_source_fields(app):
    plants = app.site.plants
    _, html, _ = get(app, "/moi-rasteniya/", {"r": [p.slug for p in plants]})
    block = re.search(r'<section class="tox".*?</section>', html, re.S).group(0)
    for p in plants:
        assert f'href="{p.url}"' in block, p.slug
    unknown = [p for p in plants if not p.poison and not p.poison_note]
    if unknown:
        assert "Нет данных — не значит «безопасно»." in block
    for p in plants:
        if p.poison:
            assert f">{p.ru_name}</a> ({p.poison})" in block


def test_labels_one_per_plant_with_source_link(app):
    sel = [p.slug for p in app.site.plants[:3]]
    st, html, _ = get(app, "/moi-rasteniya/", {"r": sel})
    assert st == 200 and canon(html) is None and html.count('<li class="label">') == 3
    for s in sel:
        assert f'href="/rastenie/{s}/">Карточка вида</a>' in html


def test_page_states(app):
    st, html, _ = get(app, "/moi-rasteniya/")
    assert (
        st == 200 and canon(html) == app.site.abs("/moi-rasteniya/") and html.count('name="r"') == len(app.site.plants)
    )
    st, html, _ = get(app, "/moi-rasteniya/", {"r": ["neizvestnoe"]})
    assert "Таких видов в справочнике нет" in html and canon(html) is None
