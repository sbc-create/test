"""Animedia parity: hero carousel, logo accent, new-episodes list rhythm."""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

from factory.paths import PATHS

ARTIFACT = PATHS.root / "automation/host/lords-frontend.py"


def _seo_stub():
    модуль = types.ModuleType("seo_layer")
    модуль.обогатить = lambda тело, тип, **кв: тело
    return модуль


@pytest.fixture
def frontend(tmp_path, monkeypatch):
    items = []
    details = {}
    for i in range(1, 16):
        slug = f"anime-{i:02d}"
        items.append({
            "slug": slug, "title": f"Аниме {i}", "kind": "Аниме", "year": 2020 + (i % 5),
            "poster": f"https://poster.cdnvideohub.com/{i}.webp",
            "published_at": f"2026-09-{i:02d}T00:00:00Z",
            "url": f"/title/{slug}/",
        })
        details[slug] = {
            "id": f"01a0ae3f-4381-7695-9d6b-4028dabf35{i:02d}",
            "external_ids": {"kp": str(i)},
            "kinopoisk_rating": 7.0 + i / 100,
            "seasons": [{"n": 1, "eps": 12, "avail": 3}],
        }
    каталог = tmp_path / "catalog.json"
    подробности = tmp_path / "details.json"
    плеер = tmp_path / "player.json"
    манифест = tmp_path / "manifest.json"
    каталог.write_text(json.dumps({
        "revision": "r1", "builtAt": "2026-09-19T00:00:00Z", "items": items,
    }, ensure_ascii=False), encoding="utf-8")
    подробности.write_text(json.dumps({"details": details}, ensure_ascii=False), encoding="utf-8")
    плеер.write_text(json.dumps({"publisher_id": "10238", "source_mode": "provider-id"}),
                     encoding="utf-8")
    манифест.write_text(json.dumps({
        "schema_version": 1, "template_family": "animedia", "design_version": "1.2.0",
        "source_commit": "0" * 40, "build_id": "test", "artifact_sha256": "a" * 64,
        "profile": "animedia-general", "built_at": "2026-09-19T00:00:00Z",
    }), encoding="utf-8")

    monkeypatch.setenv("LORDS_TEMPLATE_MANIFEST", str(манифест))
    monkeypatch.setenv("LORDS_CATALOG", str(каталог))
    monkeypatch.setenv("LORDS_DETAILS", str(подробности))
    monkeypatch.setenv("LORDS_PLAYER_CONFIG", str(плеер))
    monkeypatch.setenv("LORDS_SITE_NAME", "Animedia")
    monkeypatch.setenv("LORDS_TEMPLATE_FAMILY", "animedia")

    старое = sys.modules.get("seo_layer")
    sys.modules["seo_layer"] = _seo_stub()
    путь = str(PATHS.root / "factory" / "lords")
    added = путь not in sys.path
    if added:
        sys.path.insert(0, путь)
    try:
        for name in list(sys.modules):
            if name.startswith("nova_ani_parity"):
                sys.modules.pop(name, None)
        спец = importlib.util.spec_from_file_location("nova_ani_parity", ARTIFACT)
        модуль = importlib.util.module_from_spec(спец)
        спец.loader.exec_module(модуль)
    finally:
        if старое is None:
            sys.modules.pop("seo_layer", None)
        else:
            sys.modules["seo_layer"] = старое
        if added and путь in sys.path:
            sys.path.remove(путь)

    модуль.ПЛЕЕР.clear()
    модуль.ПЛЕЕР.update(json.loads(плеер.read_text(encoding="utf-8")))
    данные = модуль.Данные(str(каталог))
    дет = модуль.Подробности(str(подробности))
    индекс = модуль.построить_индекс(данные, дет)
    # Force animedia family tokens
    сем = dict(модуль.СЕМЕЙСТВА_1_1.get("animedia") or модуль.СЕМЕЙСТВА_1_1["zona"])
    if hasattr(модуль, "СЕМЕЙСТВА_1_2") and "animedia" in getattr(модуль, "СЕМЕЙСТВА_1_2", {}):
        сем = модуль.СЕМЕЙСТВА_1_2["animedia"]
    вид = модуль.ВидАнимедиа(сем, данные, дет, индекс, "Animedia")
    return модуль, вид


class TestAnimediaParitySurfaces:
    def test_logo_accents_the_brand_prefix(self, frontend):
        # BLOCK_02 taxonomy header (dfd8e6b) moved the accent from the trailing
        # "dia" to the leading "Ani": the brand reads Ani+media, and no foreign
        # icon or Premium badge rides along with it.
        _, вид = frontend
        html = вид.логотип()
        assert 'class="zhd__logo"' in html
        assert "<b>Ani</b>media" in html
        assert "premium" not in html.lower()

    def test_home_hero_is_not_built_from_the_catalog(self, frontend):
        # The hero shelf is curated, so it may only come from an approved
        # WeeklyPopularSnapshot (BLOCK_02). Without one it collapses and
        # declares the gap instead of borrowing rows from the catalog.
        _, вид = frontend
        html = вид.главная()
        assert 'data-popular-gap="1"' in html
        assert 'class="ahero"' not in html or "ahero--gap" in html
        assert 'Мы в Telegram' not in html
        assert 'class="premium"' not in html.lower()
        assert "/telegram" not in html.lower()

    def test_new_episodes_uses_list_rhythm(self, frontend):
        _, вид = frontend
        набор = вид.д.items[:6]
        html = вид.секция("new_episodes", "Новые серии аниме", "/new/", набор, "пусто")
        assert "zsec--eps" in html
        assert 'class="zl"' in html
        assert 'class="zr"' in html
        assert 'class="zg"' not in html

    def test_grid_sections_stay_tiles(self, frontend):
        _, вид = frontend
        набор = вид.д.items[:4]
        html = вид.секция("recently_added", "Новые аниме на сайте", "/new/", набор, "пусто")
        assert "zsec--eps" not in html
        assert 'class="zg"' in html

    def test_empty_hero_omitted(self, frontend):
        _, вид = frontend
        assert вид.верхняя_карусель([]) == ""

    def test_shell_includes_hamburger(self, frontend):
        # BLOCK_01/BLOCK_02 renamed the toggle from data-nav-toggle to
        # data-drawer-toggle and gave the drawer its own close and backdrop
        # hooks. The shell still has to ship a reachable mobile menu.
        _, вид = frontend
        html = вид.оболочка("<p>x</p>", "t", "/", актив="/")
        assert "data-drawer-toggle" in html
        assert "data-drawer-close" in html
        assert "data-drawer-backdrop" in html
        assert 'id="zhd-nav"' in html
        assert 'id="zhd-drawer"' in html
        assert "<b>Ani</b>media" in html
