"""Lords repair 2026-09-19: search, routes, aliases, home H2, player hub."""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

from factory.paths import PATHS

ARTIFACT = PATHS.root / "automation/host/lords-frontend.py"
UUID = "01a0ae3f-4381-7695-9d6b-4028dabf3561"


def _seo_stub():
    модуль = types.ModuleType("seo_layer")
    модуль.обогатить = lambda тело, тип, **кв: тело
    return модуль


@pytest.fixture
def frontend(tmp_path, monkeypatch):
    items = [
        {"slug": "matrica", "title": "Матрица (1999)", "kind": "Фильм", "year": 1999,
         "poster": "https://p/m.webp", "published_at": "2026-09-10T00:00:00Z",
         "url": "/title/matrica/", "original_title": "The Matrix",
         "aliases": ["Matrix"]},
        {"slug": "maori", "title": "Маори", "kind": "Фильм", "year": 2011,
         "poster": "https://p/o.webp", "published_at": "2026-08-01T00:00:00Z",
         "url": "/title/maori/"},
        {"slug": "sudmedekspert-stavshaya-domohozyaykoy", "title": "Судмедэксперт",
         "kind": "Сериал", "year": 2024, "poster": "https://p/s.webp",
         "published_at": "2026-09-12T00:00:00Z",
         "url": "/title/sudmedekspert-stavshaya-domohozyaykoy/"},
        {"slug": "naruto", "title": "Наруто", "kind": "Мультфильм", "year": 2002,
         "poster": "https://p/n.webp", "published_at": "2026-09-11T00:00:00Z",
         "url": "/title/naruto/"},
        {"slug": "avatar", "title": "Аватар", "kind": "Фильм", "year": 2009,
         "poster": "https://p/a.webp", "published_at": "2026-09-09T00:00:00Z",
         "url": "/title/avatar/", "original_title": "Avatar"},
    ]
    details = {
        "matrica": {"id": UUID, "external_ids": {"kp": "1"},
                    "kinopoisk_rating": 8.5, "imdb_rating": 8.7,
                    "genres": ["фантастика", "боевик"], "genre_codes": ["fantasy", "action"],
                    "countries": ["США"], "description": "Нео узнаёт правду."},
        "maori": {"id": UUID.replace("01a0", "01a1"), "external_ids": {"kp": "2"},
                  "genres": ["драма"], "genre_codes": ["drama"], "countries": ["Новая Зеландия"]},
        "sudmedekspert-stavshaya-domohozyaykoy": {
            "id": UUID.replace("01a0", "01a2"), "external_ids": {"kp": "3"},
            "seasons": [{"n": 1, "eps": 9, "avail": 3}],
            "genres": ["драма"], "genre_codes": ["drama"]},
        "naruto": {"id": UUID.replace("01a0", "01a3"), "external_ids": {"kp": "4"},
                   "genres": ["аниме"], "genre_codes": ["anime"]},
        "avatar": {"id": UUID.replace("01a0", "01a4"), "external_ids": {"kp": "5"},
                   "kinopoisk_rating": 7.9, "genres": ["фантастика"], "genre_codes": ["fantasy"],
                   "countries": ["США"]},
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
        "schema_version": 1, "template_family": "lords", "design_version": "1.1.0",
        "source_commit": "a" * 40, "runtime_commit": "b" * 40,
        "build_id": "test", "artifact_sha256": "c" * 64,
        "profile": "lords-new", "built_at": "2026-09-19T00:00:00Z",
    }), encoding="utf-8")

    monkeypatch.setenv("LORDS_TEMPLATE_MANIFEST", str(манифест))
    monkeypatch.setenv("LORDS_CATALOG", str(каталог))
    monkeypatch.setenv("LORDS_DETAILS", str(подробности))
    monkeypatch.setenv("LORDS_PLAYER_CONFIG", str(плеер))
    monkeypatch.setenv("LORDS_SITE_NAME", "Lordserial")
    monkeypatch.setenv("LORDS_TEMPLATE_FAMILY", "lords")

    старое = sys.modules.get("seo_layer")
    sys.modules["seo_layer"] = _seo_stub()
    путь = str(PATHS.root / "factory" / "lords")
    added = путь not in sys.path
    if added:
        sys.path.insert(0, путь)
    try:
        for name in list(sys.modules):
            if name.startswith("nova_lords_repair"):
                sys.modules.pop(name, None)
        спец = importlib.util.spec_from_file_location("nova_lords_repair", ARTIFACT)
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
    вид = модуль.ВидЛордс(модуль.СЕМЕЙСТВА_1_1["lords"], данные, дет, индекс, "Lordserial")
    return модуль, вид, данные, дет, индекс


class TestSearchRanking:
    def test_matrix_ranks_matrix_above_maori(self, frontend):
        модуль, *_ = frontend
        данные = frontend[2]
        hits = данные.искать("matrix")
        titles = [з["title"] for з in hits]
        assert titles, "matrix must find something"
        assert "Матрица" in titles[0]
        if "Маори" in titles:
            assert titles.index(next(t for t in titles if "Матрица" in t)) < titles.index("Маори")

    def test_cyrillic_matrix(self, frontend):
        данные = frontend[2]
        hits = данные.искать("Матрица")
        assert hits and "Матрица" in hits[0]["title"]

    def test_soft_match_rejects_maori_for_matrix(self, frontend):
        модуль = frontend[0]
        assert модуль._мягкое_совпадение("matrix", "maori") is False
        assert модуль._мягкое_совпадение("matrix", "matrica") is True


class TestRoutesAndFilters:
    def test_country_and_sort_applied(self, frontend):
        модуль, вид, данные, дет, индекс = frontend
        набор, выб = модуль.отбор(данные, индекс, {"country": ["ssha"], "sort": ["rating"]},
                                  "/catalog")
        assert выб["country"] == "ssha"
        assert all("matrica" == з["slug"] or "avatar" == з["slug"] for з in набор) or набор == []
        # USA normalized
        набор2, _ = модуль.отбор(данные, индекс, {"country": ["сша"], "sort": ["rating"]},
                                 "/catalog")
        assert {з["slug"] for з in набор2} == {"matrica", "avatar"}

    def test_unknown_genre_not_silent(self, frontend):
        модуль, _, данные, _, индекс = frontend
        набор, выб = модуль.отбор(данные, индекс, {"genre": ["no-such"]}, "/catalog")
        assert набор == []
        assert выб.get("_unknown") == "1"

    def test_new_capped(self, frontend):
        модуль, _, данные, _, индекс = frontend
        # inflate
        for i in range(300):
            данные.items.append({
                "slug": f"x{i}", "title": f"X{i}", "kind": "Фильм", "year": 2020,
                "published_at": f"2026-01-{(i % 28) + 1:02d}T00:00:00Z",
                "url": f"/title/x{i}/", "_n": f"x{i}", "_формы": [f"x{i}"],
            })
        набор, _ = модуль.отбор(данные, индекс, {}, "/new")
        assert len(набор) <= 240


class TestHomeAndChrome:
    def test_home_uses_h2_sections(self, frontend):
        _, вид, *_ = frontend
        html = вид.главная()
        assert "<h2>" in html
        assert "Весь раздел" in html
        assert "tabs__pill" not in html or html.count("sec-rail") >= 1
        assert "тестовая витрина" not in html
        assert "Template:" not in html
        assert "Lords ·" in html
        assert "data-nav-toggle" in html
        assert 'id="hd-nav"' in html

    def test_collections_hub_distinct(self, frontend):
        _, вид, *_ = frontend
        html = вид.хаб_подборок()
        assert "Подборки" in html
        assert "не полный каталог" in html or "пусто" in html.lower() or "hub__c" in html


class TestPlayerAndAlias:
    def test_hub_awaiting_compact_copy(self, frontend):
        модуль, вид, данные, дет, _ = frontend
        запись = next(з for з in данные.items if "sudmed" in з["slug"])
        деталь = дет.get(запись["slug"])
        html = вид.тайтл(запись, деталь)
        assert 'data-state="awaiting"' in html
        assert "<video-player" not in html

    def test_episode7_unavailable(self, frontend):
        модуль, вид, данные, дет, _ = frontend
        запись = next(з for з in данные.items if "sudmed" in з["slug"])
        деталь = дет.get(запись["slug"])
        html = вид.серия(запись, деталь, 1, 7)
        assert 'data-state="unavailable"' in html
        assert "<video-player" not in html

    def test_episode3_playable_attr(self, frontend):
        _, вид, данные, дет, _ = frontend
        запись = next(з for з in данные.items if "sudmed" in з["slug"])
        деталь = дет.get(запись["slug"])
        html = вид.серия(запись, деталь, 1, 3)
        assert 'episode="3"' in html
        assert html.count("<video-player") == 1

    def test_slug_alias_table(self, frontend):
        модуль = frontend[0]
        assert модуль.Обработчик.SLUG_ALIASES[
            "sudmedekspert-stavshaya-domokhozyaykoy"
        ] == "sudmedekspert-stavshaya-domohozyaykoy"

    def test_kind_routes_declared(self, frontend):
        модуль = frontend[0]
        assert модуль.Обработчик.МАРШРУТЫ_ВИДА["/movies"] == "Фильм"
        assert "/series" in модуль.Обработчик.МАРШРУТЫ_ВИДА
