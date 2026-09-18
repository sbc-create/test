"""Регрессии overnight visual repair: поиск, encoding, рейтинги, полки."""

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
    каталог = tmp_path / "catalog.json"
    подробности = tmp_path / "details.json"
    плеер = tmp_path / "player.json"
    манифест = tmp_path / "manifest.json"

    каталог.write_text(json.dumps({
        "revision": "r1",
        "builtAt": "2026-09-19T00:00:00Z",
        "items": [
            {"slug": "matrica", "title": "Матрица", "kind": "Фильм", "year": 1999,
             "poster": "https://poster.cdnvideohub.com/a.webp",
             "published_at": "2026-09-01T00:00:00Z", "url": "/title/matrica/",
             "original_title": "The Matrix"},
            {"slug": "naruto", "title": "Наруто", "kind": "Аниме", "year": 2002,
             "poster": "https://poster.cdnvideohub.com/b.webp",
             "published_at": "2026-09-02T00:00:00Z", "url": "/title/naruto/"},
            {"slug": "007-doroga-k-millionu", "title": "007: Дорога к миллиону",
             "kind": "Сериал", "year": 2023,
             "poster": "https://poster.cdnvideohub.com/c.webp",
             "published_at": "2026-09-03T00:00:00Z",
             "url": "/title/007-doroga-k-millionu/"},
        ],
    }, ensure_ascii=False), encoding="utf-8")
    подробности.write_text(json.dumps({
        "catalog_revision": "r1",
        "details_total": 3,
        "details": {
            "matrica": {"imdb_rating": 8.7, "kinopoisk_rating": 8.5,
                        "id": "01915254-4513-7657-ad4b-d75fae15b061",
                        "external_ids": {"kp": "1"}},
            "naruto": {"id": "01915254-4513-7657-ad4b-d75fae15b062",
                       "external_ids": {"kp": "2"},
                       "seasons": [{"n": 1, "eps": 2, "avail": 2}]},
            "007-doroga-k-millionu": {
                "id": "01915254-4513-7657-ad4b-d75fae15b063",
                "external_ids": {"kp": "3"},
                "seasons": [{"n": 1, "eps": 1, "avail": 1}]},
        },
    }, ensure_ascii=False), encoding="utf-8")
    плеер.write_text(json.dumps({
        "publisher_id": "10238", "source_mode": "provider-id",
    }), encoding="utf-8")
    манифест.write_text(json.dumps({
        "schema_version": 1, "template_family": "lords", "design_version": "1.1.0",
        "source_commit": "0" * 40, "build_id": "test", "artifact_sha256": "a" * 64,
        "profile": "lords-new", "built_at": "2026-09-19T00:00:00Z",
    }), encoding="utf-8")

    monkeypatch.setenv("LORDS_TEMPLATE_MANIFEST", str(манифест))
    monkeypatch.setenv("LORDS_CATALOG", str(каталог))
    monkeypatch.setenv("LORDS_DETAILS", str(подробности))
    monkeypatch.setenv("LORDS_PLAYER_CONFIG", str(плеер))
    monkeypatch.setenv("LORDS_SITE_NAME", "Test")

    старое = sys.modules.get("seo_layer")
    sys.modules["seo_layer"] = _seo_stub()
    путь = str(PATHS.root / "factory" / "lords")
    added = путь not in sys.path
    if added:
        sys.path.insert(0, путь)
    try:
        for name in list(sys.modules):
            if name.startswith("nova_overnight"):
                sys.modules.pop(name, None)
        спец = importlib.util.spec_from_file_location("nova_overnight", ARTIFACT)
        модуль = importlib.util.module_from_spec(спец)
        спец.loader.exec_module(модуль)
    finally:
        if старое is None:
            sys.modules.pop("seo_layer", None)
        else:
            sys.modules["seo_layer"] = старое
        if added and путь in sys.path:
            sys.path.remove(путь)

    данные = модуль.Данные(str(каталог))
    дет = модуль.Подробности(str(подробности))
    индекс = модуль.построить_индекс(данные, дет)
    return модуль, данные, дет, индекс, каталог


class TestSearchLatinSlugMixed:
    def test_forms_include_slug_and_translit(self, frontend):
        модуль, данные, *_ = frontend
        by_slug = {з["slug"]: з for з in данные.items}
        assert "matrica" in by_slug["matrica"]["_формы"]
        assert "naruto" in by_slug["naruto"]["_формы"]
        assert модуль.нормализовать("The Matrix") in by_slug["matrica"]["_формы"]

        assert "matrica" in {з["slug"] for з in данные.искать("matrix")}
        assert "naruto" in {з["slug"] for з in данные.искать("naruto")}
        assert "007-doroga-k-millionu" in {
            з["slug"] for з in данные.искать("007-doroga-k-millionu")}
        assert "matrica" in {з["slug"] for з in данные.искать("Matrix матрица")}
        assert "matrica" in {з["slug"] for з in данные.искать("vfnhbwf")}


class TestQueryEncoding:
    def test_запрос_строкой_percent_encodes_cyrillic(self, frontend):
        модуль, *_ = frontend
        s = модуль.запрос_строкой({"kind": "Фильм"})
        assert "Фильм" not in s
        assert "%D0%A4" in s.upper()
        assert s.startswith("?")

    def test_закодировать_запрос_keeps_path(self, frontend):
        модуль, *_ = frontend
        u = модуль.закодировать_запрос("/catalog/?kind=Сериал&page=2")
        assert u.startswith("/catalog/?")
        assert "Сериал" not in u
        assert "page=2" in u


class TestLordsCardRatings:
    def test_omits_dash_when_ratings_absent(self, frontend):
        модуль, данные, дет, индекс, _ = frontend
        вид = модуль.ВидЛордс(
            модуль.СЕМЕЙСТВА_1_1["lords"], данные, дет, индекс, "Test")
        html_no = вид.карточка(next(з for з in данные.items if з["slug"] == "naruto"))
        assert "<em>—</em>" not in html_no
        html_yes = вид.карточка(next(з for з in данные.items if з["slug"] == "matrica"))
        assert "8.5" in html_yes and "КП" in html_yes


class TestEmptyShelfPolicy:
    def test_zona_hides_empty_trailers(self, frontend):
        модуль, данные, дет, индекс, _ = frontend
        вид = модуль.ВидЗона(
            модуль.СЕМЕЙСТВА_1_1["zona"], данные, дет, индекс, "Test")
        assert вид.секция("trailers", "Новые трейлеры", "", [], "нет данных") == ""

    def test_animedia_hides_empty_ongoing_today(self, frontend):
        модуль, данные, дет, индекс, _ = frontend
        assert hasattr(модуль, "ВидАнимедиа")
        вид = модуль.ВидАнимедиа(
            модуль.СЕМЕЙСТВА_1_1["animedia"], данные, дет, индекс, "Test")
        assert вид.секция("ongoing", "Онгоинги", "", [], "нет") == ""
        assert вид.секция("today-schedule", "Сегодня выйдет", "", [], "нет") == ""

    def test_animedia_shell_has_mobile_nav_toggle(self, frontend):
        модуль, данные, дет, индекс, _ = frontend
        вид = модуль.ВидАнимедиа(
            модуль.СЕМЕЙСТВА_1_1["animedia"], данные, дет, индекс, "Test")
        html = вид.оболочка("<p>x</p>", "t", "/", актив="/")
        assert 'data-nav-toggle' in html
        assert 'id="zhd-nav"' in html
        assert "zhd__menu" in html
        assert "СКРИПТ_АНИМЕДИА_ШАПКА" not in html  # inlined, not name
        assert "data-nav-toggle" in модуль.СКРИПТ_АНИМЕДИА_ШАПКА
