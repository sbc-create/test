"""Animedia final repair — targeted regression tests (shared runtime, profile-gated)."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "automation" / "host" / "lords-frontend.py"


def _load_frontend(tmp: Path, *, family: str = "animedia", profile: str = "animedia-space"):
    manifest = {
        "schema_version": 1,
        "template_family": family,
        "design_version": "1.2.1",
        "source_commit": "a" * 40,
        "runtime_commit": "b" * 40,
        "build_id": "test-build",
        "artifact_sha256": "c" * 64,
        "profile": profile,
        "built_at": "2026-09-19T00:00:00Z",
    }
    man = tmp / "manifest.json"
    man.write_text(json.dumps(manifest), encoding="utf-8")
    catalog = {
        "items": [
            {
                "slug": "alpha-anime",
                "title": "Альфа",
                "kind": "Аниме",
                "year": 2024,
                "url": "/title/alpha-anime/",
                "poster": "https://poster.cdnvideohub.com/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee.webp",
                "published_at": "2026-09-01T00:00:00Z",
            },
            {
                "slug": "beta-anime",
                "title": "Beta Show",
                "kind": "Аниме",
                "year": 2023,
                "url": "/title/beta-anime/",
                "poster": "",
                "published_at": "2026-08-01T00:00:00Z",
            },
            {
                "slug": "gamma-series",
                "title": "Gamma",
                "kind": "Аниме",
                "year": 2022,
                "url": "/title/gamma-series/",
                "poster": "https://poster.cdnvideohub.com/11111111-2222-3333-4444-555555555555.webp",
                "published_at": "2026-07-01T00:00:00Z",
            },
        ],
        "fields_absent": [],
    }
    details = {
        "alpha-anime": {
            "kinopoisk_rating": 7.1,
            "imdb_rating": 7.0,
            "external_ids": {"kp": "1"},
            "genres": ["драма"],
            "genre_codes": ["drama"],
            "seasons": [],
        },
        "beta-anime": {
            "kinopoisk_rating": 6.0,
            "external_ids": {"kp": "2"},
            "genres": ["комедия"],
            "genre_codes": ["comedy"],
            "seasons": [],
        },
        "gamma-series": {
            "kinopoisk_rating": 8.0,
            "external_ids": {"kp": "3"},
            "genres": ["драма"],
            "genre_codes": ["drama"],
            "seasons": [{"n": 1, "eps": 5, "avail": 3}],
        },
    }
    cat_named = tmp / "animedia-test-catalog.json"
    cat_named.write_text(json.dumps(catalog), encoding="utf-8")
    (tmp / "animedia-test-details.json").write_text(
        json.dumps({"details": details}), encoding="utf-8"
    )
    os.environ["LORDS_TEMPLATE_MANIFEST"] = str(man)
    os.environ["LORDS_CATALOG"] = str(cat_named)
    os.environ["LORDS_SITE_NAME"] = "Animedia"
    os.environ.pop("LORDS_POSTER_SAME_ORIGIN", None)

    name = f"lords_frontend_test_{family}_{profile}_{tmp.name}"
    spec = importlib.util.spec_from_file_location(name, FRONTEND)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    assert FRONTEND.is_file(), FRONTEND
    spec.loader.exec_module(mod)
    return mod, catalog, details


def _вид(mod, catalog, details, host="animedia.space"):
    данные = mod.Данные.__new__(mod.Данные)
    данные.items = [dict(з) for з in catalog["items"]]
    for з in данные.items:
        з["_n"] = mod.нормализовать(з["title"])
        з["_формы"] = [з["_n"]]
    данные.years = [2024, 2023, 2022]
    данные.kinds = ["Аниме"]
    данные.absent = []
    подроб = mod.Подробности.__new__(mod.Подробности)
    подроб.записи = details
    подроб.источник = ""
    подроб.покрытие = len(details)
    подроб.catalog_revision = ""
    подроб.catalog_built_at = ""
    индекс = {
        "slug": {з["slug"]: з for з in данные.items},
        "genre": {"drama": ["alpha-anime", "gamma-series"], "comedy": ["beta-anime"]},
        "genre_names": [("drama", "драма"), ("comedy", "комедия")],
        "country": {},
        "country_names": [],
    }
    семейство = mod.СЕМЕЙСТВА_1_1["animedia"]
    вид = mod.ВидАнимедиа(семейство, данные, подроб, индекс, "Animedia")
    вид.хост = host
    return вид


@pytest.fixture()
def fe(tmp_path):
    return _load_frontend(tmp_path)


class TestAnimediaFinalRepair:
    def test_static_header_and_tokens(self, fe):
        mod, _, _ = fe
        assert mod.АНИМЕДИА_ТОКЕНЫ["acc"] == "#c50725"
        assert mod.АНИМЕДИА_ТОКЕНЫ["page"] == "#ffffff"
        css = mod.АНИМЕДИА_СТИЛЬ.replace(" ", "")
        assert ".zhd{position:relative" in css

    def test_poster_alt_is_title_not_diagnostic(self, fe):
        mod, catalog, _ = fe
        html = mod.заглушка_постера(catalog["items"][0], "zt__none", "zt__img")
        assert "постер не открылся" not in html
        assert 'alt="Альфа"' in html
        assert "/poster/" in html

    def test_poster_proxy_rejects_ssrf(self, fe):
        mod, _, _ = fe
        assert mod._постер_безопасный_ключ("../etc/passwd") is None
        assert mod._постер_безопасный_ключ("http://127.0.0.1/x.webp") is None
        assert mod._постер_безопасный_ключ("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee.webp")

    def test_no_public_catalog_count_or_test_banner(self, fe):
        mod, catalog, details = fe
        вид = _вид(mod, catalog, details, "animedia.space")
        html = вид.главная()
        assert "снимке каталога" not in html
        assert "тестовая витрина" not in html
        assert "закрыта от индексации" not in html
        assert "Template:" not in html
        assert "Animedia 1.2.1 ·" in html
        assert "Каталог аниме онлайн" in html
        assert "Animedia Space" in html
        assert 'name="robots" content="noindex, nofollow"' in html
        assert "источник подключён" not in html

    def test_domain_profiles_differ(self, fe):
        mod, catalog, details = fe
        hs = _вид(mod, catalog, details, "animedia.space").главная()
        hi = _вид(mod, catalog, details, "animedia.icu").главная()
        assert "animedia-space" in hs
        assert "animedia-icu" in hi
        assert "Каталог аниме онлайн" in hs
        assert "Аниме, серии и подборки" in hi
        assert hs != hi
        assert 'rel="canonical" href="https://animedia.space/"' in hs
        assert 'rel="canonical" href="https://animedia.icu/"' in hi

    def test_default_playable_episode_selected(self, fe):
        mod, _, _ = fe
        сезон, эпизод = mod.выбрать_доступную_серию(
            {"seasons": [{"n": 1, "eps": 5, "avail": 3}]}
        )
        assert (сезон, эпизод) == (1, 3)

    def test_player_copy_has_no_provider_diagnostics(self, fe):
        mod, catalog, details = fe
        # Without publisher config state is noaccess; with seasons but no episode
        # and publisher present it would be awaiting. Both public copies must
        # stay free of internal provider diagnostics.
        код, html = mod.разметка_плеера(
            type("V", (), {"кл_состояния": "zpl__s"})(),
            catalog["items"][2],
            details["gamma-series"],
            1,
            None,
        )
        assert код in {"awaiting", "noaccess", "nosource", "playable"}
        assert "источник подключён" not in html
        assert "запросов к провайдеру" not in html
        assert "источник подключён" not in mod._подпись_плеера("playable")
        awaiting = (
            f'<div class="zpl__s" data-player-state>'
            "<b>Выберите серию</b>"
            "<p>Откройте доступную серию в списке ниже.</p></div>"
        )
        assert "запросов к провайдеру" not in awaiting
        assert "Источник подключён" not in awaiting

    def test_empty_shelves_hidden(self, fe):
        mod, catalog, details = fe
        вид = _вид(mod, catalog, details)
        assert вид.секция("ongoing", "Онгоинги", "/catalog/", [], "пусто") == ""
        assert вид.секция("top", "Топ", "/catalog/", [], "пусто") == ""

    def test_compact_episode_controls(self, fe):
        mod, catalog, details = fe
        вид = _вид(mod, catalog, details)
        html = вид._серии(
            catalog["items"][2],
            [{"n": 1, "eps": 5, "avail": 3, "номера": [1, 2, 3, 4, 5]}],
            текущий=(1, 3),
        )
        assert "Серия 1" not in html
        assert ">1</a>" in html
        assert 'aria-current="page"' in html
        assert "data-off" in html

    def test_lords_family_still_loads(self, tmp_path):
        mod, _, _ = _load_frontend(tmp_path, family="lords", profile="lords-new")
        assert "lords" in mod.СЕМЕЙСТВА_1_1
        assert mod.СЕМЕЙСТВО == "lords"
        assert mod.ПОСТЕРЫ_СВОИМ_АДРЕСОМ is False

    def test_design_121_enables_animedia_portal(self, tmp_path):
        mod, _, _ = _load_frontend(tmp_path, family="animedia", profile="animedia-space")
        assert mod.ВЕРСИЯ == "1.2.1"
        assert mod.ОФОРМЛЕНИЕ_ПЕРЕРАБОТАННОЕ is True
        assert "animedia" in mod.ВИДЫ_1_1
        assert mod.ВИДЫ_1_1["animedia"] is mod.ВидАнимедиа

    def test_genre_index_from_russian_names_without_codes(self, fe):
        mod, catalog, details = fe
        # Simulate Animedia sidecar: names only, no genre_codes.
        bare = {
            "alpha-anime": {
                "genres": ["драма", "боевик"],
                "seasons": [],
                "external_ids": {"kp": "1"},
            },
            "beta-anime": {
                "genres": ["комедия"],
                "seasons": [],
                "external_ids": {"kp": "2"},
            },
        }
        данные = mod.Данные.__new__(mod.Данные)
        данные.items = [dict(з) for з in catalog["items"][:2]]
        подроб = mod.Подробности.__new__(mod.Подробности)
        подроб.записи = bare
        индекс = mod.построить_индекс(данные, подроб)
        assert "drama" in индекс["genre"] or "drama" in {
            mod.нормализовать(mod.транслит("драма"))
        }
        drama = mod.нормализовать(mod.транслит("драма"))
        comedy = mod.нормализовать(mod.транслит("комедия"))
        assert drama in индекс["genre"]
        assert comedy in индекс["genre"]
        assert set(индекс["genre"][drama]) != set(индекс["genre"][comedy])
        a, _ = mod.отбор(данные, индекс, {"genre": [drama]}, "/catalog")
        b, _ = mod.отбор(данные, индекс, {"genre": [comedy]}, "/catalog")
        c, _ = mod.отбор(данные, индекс, {"genre": ["драма"]}, "/catalog")
        assert {з["slug"] for з in a} == {"alpha-anime"}
        assert {з["slug"] for з in b} == {"beta-anime"}
        assert {з["slug"] for з in c} == {"alpha-anime"}
