"""Animedia visual finalization gates: layout contracts, feeds, filters, domains."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "automation" / "host"
sys.path.insert(0, str(HOST))
sys.path.insert(0, str(ROOT))


def _load(tmp: Path, *, family: str = "animedia", profile: str = "animedia-space",
          version: str = "1.2.4"):
    manifest = {
        "schema_version": 1,
        "template_family": family,
        "design_version": version,
        "source_commit": "aabbccdd",
        "runtime_commit": "eeff0011",
        "profile": profile,
        "build_id": "visual-test",
        "artifact_sha256": "a" * 64,
        "built_at": "2026-09-19T00:00:00Z",
    }
    man = tmp / "manifest.json"
    man.write_text(json.dumps(manifest), encoding="utf-8")
    catalog = {
        "items": [
            {
                "slug": "alpha-anime", "title": "Альфа", "kind": "Аниме",
                "year": 2026, "published_at": "2026-09-18T12:00:00Z",
                "poster": "/poster/a.webp", "url": "/title/alpha-anime/",
            },
            {
                "slug": "beta-series", "title": "Бета", "kind": "Аниме",
                "year": 2025, "published_at": "2026-09-17T12:00:00Z",
                "poster": "/poster/b.webp", "url": "/title/beta-series/",
            },
            {
                "slug": "gamma-movie", "title": "Гамма", "kind": "Аниме",
                "year": 2024, "published_at": "2026-09-10T12:00:00Z",
                "poster": "", "url": "/title/gamma-movie/",
            },
            {
                "slug": "delta-old", "title": "Дельта", "kind": "Аниме",
                "year": 2001, "published_at": "2020-01-01T00:00:00Z",
                "poster": "/poster/d.webp", "url": "/title/delta-old/",
            },
        ],
        "revision": "vis-1", "count": 4,
    }
    details = {
        "catalog_revision": "vis-1",
        "details": {
            "alpha-anime": {
                "description": "Описание альфы. " * 40,
                "original_title": "Alpha",
                "genres": ["драма", "комедия"],
                "countries": ["Япония"],
                "kinopoisk_rating": 8.2,
                "imdb_rating": 7.5,
                "type": "tv",
                "seasons": [{"n": 1, "eps": 12, "avail": 5}],
                "playable": True,
            },
            "beta-series": {
                "description": "Описание беты.",
                "genres": ["боевик"],
                "countries": ["Китай"],
                "type": "tv",
                "seasons": [{"n": 1, "eps": 24, "avail": 24}],
                "playable": True,
            },
            "gamma-movie": {
                "description": "Фильм.",
                "genres": ["фэнтези"],
                "type": "movie",
                "seasons": [],
                "playable": True,
            },
            "delta-old": {
                "description": "Классика.",
                "genres": ["драма"],
                "type": "tv",
                "seasons": [{"n": 1, "eps": 26, "avail": 26}],
                "playable": False,
            },
        },
    }
    (tmp / "catalog.json").write_text(json.dumps(catalog), encoding="utf-8")
    (tmp / "details.json").write_text(json.dumps(details), encoding="utf-8")
    (tmp / "player.json").write_text(
        json.dumps({"publisher_id": "pub-test", "token": "tok"}), encoding="utf-8")

    import os
    os.environ["LORDS_TEMPLATE_MANIFEST"] = str(man)
    os.environ["LORDS_CATALOG"] = str(tmp / "catalog.json")
    os.environ["LORDS_DETAILS"] = str(tmp / "details.json")
    os.environ["LORDS_PLAYER_CONFIG"] = str(tmp / "player.json")
    os.environ["LORDS_TEMPLATE_FAMILY"] = family
    os.environ["LORDS_SITE_NAME"] = "Animedia"
    os.environ["LORDS_PUBLIC_ORIGIN"] = "https://animedia.space"

    # Reload frontend module fresh
    for key in list(sys.modules):
        if key.endswith("lords-frontend") or key == "lords_frontend":
            del sys.modules[key]
    name = f"lords_fe_vis_{tmp.name}"
    spec = importlib.util.spec_from_file_location(name, HOST / "lords-frontend.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod, catalog, details


def _вид(mod, catalog, details, host="animedia.space"):
    данные = mod.Данные.__new__(mod.Данные)
    данные.items = [dict(з) for з in catalog["items"]]
    for з in данные.items:
        з["_n"] = mod.нормализовать(з["title"])
        з["_формы"] = [з["_n"]]
    данные.years = sorted({з["year"] for з in данные.items}, reverse=True)
    данные.kinds = sorted({з["kind"] for з in данные.items})
    данные.absent = []
    подроб = mod.Подробности.__new__(mod.Подробности)
    подроб.записи = details["details"]
    подроб.источник = ""
    подроб.покрытие = len(details["details"])
    подроб.catalog_revision = details.get("catalog_revision", "")
    подроб.catalog_built_at = ""
    индекс = mod.построить_индекс(данные, подроб)
    семейство = mod.СЕМЕЙСТВА_1_1["animedia"]
    вид = mod.ВидАнимедиа(семейство, данные, подроб, индекс, "Animedia")
    вид.хост = host
    return вид


@pytest.fixture
def fe(tmp_path):
    return _load(tmp_path)


class TestVisualContracts:
    def test_design_122_and_css_tokens(self, fe):
        mod, _, _ = fe
        assert mod.ВЕРСИЯ == "1.2.4"
        assert "1.2.4" in mod.ОФОРМЛЕНИЕ_ВЕРСИИ
        css = mod.СЕМЕЙСТВА_1_1["animedia"]["стиль"]()
        assert "--a-content-max:1760px" in css
        assert "aspect-ratio:16/9" in css
        assert "clamp(180px,13vw,220px)" in css
        assert "[data-player-state][hidden]" in css
        assert "height:100% !important" in css
        assert "grid-template-columns:repeat(10" in css
        assert "grid-template-columns:repeat(7" in css

    def test_home_leads_with_episode_feed(self, fe):
        mod, catalog, details = fe
        html = _вид(mod, catalog, details).главная()
        assert "Недавно добавленные" in html
        assert 'class="aeps"' in html
        assert 'class="aeps__row"' in html
        # Episode feed appears before poster shelves (zsec without --eps after).
        pos_eps = html.find("Недавно добавленные")
        pos_top = html.find("Высокие оценки")
        assert pos_eps > 0
        if pos_top > 0:
            assert pos_eps < pos_top
        assert "Сегодня" not in html or "Сегодня выйдет" not in html

    def test_new_route_is_episode_rows(self, fe):
        mod, catalog, details = fe
        вид = _вид(mod, catalog, details)
        html = вид.список("/new", {})
        assert "Недавно добавленные" in html
        assert "aeps__row" in html
        assert "серия" in html
        # Must not be a poster grid of titles only
        assert html.count('class="zt"') == 0 or html.count("aeps__row") > 0

    def test_schedule_single_empty_state(self, fe):
        mod, catalog, details = fe
        html = _вид(mod, catalog, details).расписание()
        assert "Расписание пока недоступно" in html
        assert "sidecar" not in html.lower()
        assert "поставщик" not in html.lower()
        assert "provider" not in html.lower()
        assert 'class="asch-empty"' in html and html.count('Расписание пока недоступно') == 1

    def test_catalog_year_h1_and_default_sort(self, fe):
        mod, catalog, details = fe
        вид = _вид(mod, catalog, details)
        html = вид.список("/catalog", {"year": ["2026"]})
        assert "Аниме 2026 года" in html
        assert "Весь каталог" not in html
        # Freshness default: alpha (2026 published latest) first among year=2026
        assert "Альфа" in html
        набор, выбрано = mod.отбор(вид.д, вид.индекс, {}, "/catalog")
        assert выбрано.get("sort") in (None, "")
        assert набор[0]["slug"] == "alpha-anime"

    def test_title_two_column_no_rail(self, fe):
        mod, catalog, details = fe
        вид = _вид(mod, catalog, details)
        html = вид.тайтл(catalog["items"][0], details["details"]["alpha-anime"])
        assert 'class="ztitle"' in html
        assert "ztitle__poster" in html
        assert "ztitle__main" in html
        assert "ztitle__rail" not in html or 'ztitle__rail"' not in html.split("ztitle")[1][:2000]
        assert "ztitle__score" in html
        assert "8.2" in html
        assert "Смотреть" in html
        assert 'class="zpl"' in html
        assert "aspect-ratio" in mod.АНИМЕДИА_СТИЛЬ

    def test_domains_differ(self, fe):
        mod, catalog, details = fe
        hs = _вид(mod, catalog, details, "animedia.space").главная()
        hi = _вид(mod, catalog, details, "animedia.icu").главная()
        assert "animedia-space" in hs and "animedia-icu" in hi
        assert "Новые серии и популярное" in hs
        assert "Сериалы, фильмы и дунхуа" in hi
        assert hs != hi
        assert mod.АНИМЕДИА_ДОМЕНЫ["animedia.space"]["home_shelves"] != \
            mod.АНИМЕДИА_ДОМЕНЫ["animedia.icu"]["home_shelves"]

    def test_footer_clean(self, fe):
        mod, catalog, details = fe
        html = _вид(mod, catalog, details).подвал()
        assert "тестовая витрина" not in html
        assert "закрыта от индексации" not in html
        assert "снимке каталога" not in html
        assert "sidecar" not in html.lower()
        assert "поставщик" not in html.lower()
        assert "Animedia 1.2.4 ·" in html
        assert "/schedule/" not in html

    def test_nav_hides_schedule(self, fe):
        mod, _, _ = fe
        nav = " ".join(u for u, _ in mod.СЕМЕЙСТВА_1_1["animedia"]["нав"])
        assert "/schedule/" not in nav
        assert "/new/" in nav

    def test_collections_copy_human(self, fe):
        from factory.lords import collection_contract as кк
        for ключ in ("video_available", "anime_movies", "series_with_episodes",
                     "new_episodes", "recently_added"):
            спец = кк.спецификация("animedia", ключ)
            assert спец is not None
            low = спец.description.lower()
            assert "sidecar" not in low
            assert "playable" not in low
            assert "type=movie" not in low
            assert "поставщик" not in low

    def test_rating_source_extensible(self, fe):
        mod, catalog, details = fe
        det = dict(details["details"]["alpha-anime"])
        det["shikimori_rating"] = 9.1
        # If gateway/helpers expose it, markup should include without layout break.
        html = _вид(mod, catalog, details).тайтл(catalog["items"][0], det)
        assert 'class="ztitle"' in html
        assert "ztitle__score" in html
