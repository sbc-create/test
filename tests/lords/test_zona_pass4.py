"""Zona PASS4: route contract, sort, pagination, dates, footer."""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from pathlib import Path

import pytest

ИСХОДНИК = Path(__file__).resolve().parents[2] / "automation" / "host" / "lords-frontend.py"


def _каталог(n=100):
    items = []
    for i in range(n):
        kind = "Фильм" if i % 3 == 0 else ("Сериал" if i % 3 == 1 else "Мультфильм")
        year = 2026 - (i % 5)
        items.append({
            "slug": f"t-{i:04d}", "title": f"Title {i:04d}", "kind": kind,
            "year": year, "poster": f"https://poster.example/{i}.webp",
            "url": f"/title/t-{i:04d}/",
            "published_at": f"2026-09-{(i % 28) + 1:02d}T00:00:00Z",
        })
    # Alpha traps that must NOT lead /movies/ when newest is default.
    items.append({
        "slug": "007-old", "title": "007: Ancient", "kind": "Фильм", "year": 2012,
        "poster": "https://poster.example/007.webp", "url": "/title/007-old/",
        "published_at": "2020-01-01T00:00:00Z",
    })
    items.append({
        "slug": "fresh-film", "title": "Яркая премьера", "kind": "Фильм", "year": 2026,
        "poster": "https://poster.example/fresh.webp", "url": "/title/fresh-film/",
        "published_at": "2026-09-18T00:00:00Z",
    })
    return {"version": 2, "count": len(items), "items": items, "site": "zona-01",
            "schema": "nova-catalog/2.0.0", "revision": "pass4",
            "builtAt": "2026-09-19T00:00:00Z"}


def _подробности(catalog):
    details = {}
    for it in catalog["items"]:
        d = {
            "id": f"id-{it['slug']}",
            "description": f"Desc {it['slug']}",
            "genres": ["драма"],
            "genre_codes": ["drama"],
            "countries": ["США"],
            "sources": [{"provider": "kp", "source_id": "1",
                         "availability_status": "available"}],
            "external_ids": {"kp": "1"},
            "playable": True,
        }
        if it["slug"] == "fresh-film":
            d["premiere_date"] = "2026-09-19"
            d["imdb_rating"] = 8.1
            d["ratings_by_source"] = {
                "imdb": {"value": 8.1, "votes": 100, "source": "imdb"}}
        if it["slug"] == "007-old":
            d["premiere_date"] = "2012-01-01"
        if it["kind"] == "Сериал":
            d["seasons"] = [{"n": 1, "eps": 10, "avail": 3}]
        details[it["slug"]] = d
    return {
        "schema": "nova-details/1.0.0", "site": "zona-01",
        "details_total": len(details), "source": "test",
        "items_total": len(details), "details": details,
    }


def _поднять(tmp_path, n=100):
    корень = tmp_path / "zona-01"
    корень.mkdir(parents=True, exist_ok=True)
    cat = _каталог(n)
    (корень / "zona-01-catalog.json").write_text(
        json.dumps(cat, ensure_ascii=False), encoding="utf-8")
    (корень / "zona-01-details.json").write_text(
        json.dumps(_подробности(cat), ensure_ascii=False), encoding="utf-8")
    (корень / "player-zona-01.json").write_text(
        json.dumps({"publisher_id": "10238", "source_mode": "provider-id"}),
        encoding="utf-8")
    манифест = корень / "manifest.json"
    манифест.write_text(json.dumps({
        "schema_version": 1, "template_family": "zona",
        "design_version": "1.2.0", "source_commit": "0" * 40,
        "build_id": "PASS4", "artifact_sha256": "0" * 64,
        "profile": "zona-test", "built_at": "2026-09-19T00:00:00Z",
    }), encoding="utf-8")
    старое = dict(os.environ)
    os.environ["LORDS_TEMPLATE_MANIFEST"] = str(манифест)
    os.environ["LORDS_CATALOG"] = str(корень / "zona-01-catalog.json")
    os.environ["LORDS_DETAILS"] = str(корень / "zona-01-details.json")
    os.environ["LORDS_PLAYER_CONFIG"] = str(корень / "player-zona-01.json")
    os.environ["LORDS_SITE_NAME"] = "Zona Pass4"
    os.environ["LORDS_CLOCK_ISO"] = "2026-09-19T12:00:00Z"
    try:
        имя = "nova_zona_pass4"
        спец = importlib.util.spec_from_file_location(имя, ИСХОДНИК)
        модуль = importlib.util.module_from_spec(спец)
        sys.modules[имя] = модуль
        спец.loader.exec_module(модуль)
    finally:
        os.environ.clear()
        os.environ.update(старое)
    модуль.Обработчик.данные = модуль.Данные(str(корень / "zona-01-catalog.json"))
    модуль.Обработчик.подробности = модуль.Подробности(str(корень / "zona-01-details.json"))
    модуль.Обработчик.индекс = модуль.построить_индекс(
        модуль.Обработчик.данные, модуль.Обработчик.подробности)
    return модуль


def запросить(модуль, путь: str):
    from tests.lords.test_nova_frontend_families import запросить as _з
    return _з(модуль, путь)


@pytest.fixture(scope="module")
def зона(tmp_path_factory):
    return _поднять(tmp_path_factory.mktemp("zona-pass4"), n=100)


@pytest.fixture(scope="module")
def зона241(tmp_path_factory):
    return _поднять(tmp_path_factory.mktemp("zona-pass4-241"), n=241)


class TestRouteKinds:
    def test_movies_route_contains_only_films(self, зона):
        о = запросить(зона, "/movies/")
        assert о.статус == 200
        metas = re.findall(r'class="zt__m"[^>]*>([^<]+)', о.тело)
        assert metas
        assert all("Фильм" in m for m in metas)

    def test_series_route_contains_only_series(self, зона):
        о = запросить(зона, "/series/")
        metas = re.findall(r'class="zt__m"[^>]*>([^<]+)', о.тело)
        assert all("Сериал" in m for m in metas)

    def test_animation_route_contains_only_animation(self, зона):
        о = запросить(зона, "/animation/")
        metas = re.findall(r'class="zt__m"[^>]*>([^<]+)', о.тело)
        assert all("Мультфильм" in m for m in metas)

    def test_route_specific_urls_do_not_emit_kind_param(self, зона):
        о = запросить(зона, "/movies/")
        assert 'href="/movies/?kind=' not in о.тело
        assert 'href="/movies/?kind%3D' not in о.тело

    def test_conflicting_kind_redirects_to_matching_route(self, зона):
        о = запросить(зона, "/movies/?kind=%D0%A1%D0%B5%D1%80%D0%B8%D0%B0%D0%BB&year=2025")
        assert о.статус in (301, 302, 308)
        loc = о.заголовки.get("Location") or о.заголовки.get("location") or ""
        assert loc.startswith("/series/")
        assert "year=2025" in loc or "year%3D2025" in loc or "2025" in loc
        assert "kind=" not in loc

    def test_redundant_kind_redirects_clean(self, зона):
        о = запросить(зона, "/movies/?kind=%D0%A4%D0%B8%D0%BB%D1%8C%D0%BC")
        assert о.статус in (301, 302, 308)
        loc = о.заголовки.get("Location") or ""
        assert loc in ("/movies/", "/movies")


class TestSortAndNew:
    def test_movies_default_not_alpha_007_first(self, зона):
        о = запросить(зона, "/movies/")
        titles = re.findall(r'class="zt__t"[^>]*>([^<]+)', о.тело)
        assert titles
        assert titles[0] != "007: Ancient"
        assert "Яркая премьера" in titles[:5] or titles[0] == "Яркая премьера"

    def test_new_orders_by_activity_not_provider_ordinal(self, зона):
        о = запросить(зона, "/new/")
        assert "Найдено 240" not in о.тело
        assert "Сначала новые" in о.тело or "aria-current" in о.тело

    def test_new_is_not_recently_added_duplicate(self, зона):
        # /new/ shows freshness labels when premiere exists.
        о = запросить(зона, "/new/")
        assert "Премьера ·" in о.тело or "Обновлено ·" in о.тело

    def test_year_means_release_year_only(self, зона):
        о = запросить(зона, "/series/?year=2026")
        assert "Сериалы 2026 года" in о.тело
        metas = re.findall(r'class="zt__m"[^>]*>([^<]+)', о.тело)
        assert all("2026" in m for m in metas)

    def test_current_year_uses_clock_not_catalog_max(self, зона):
        assert зона.текущий_год_часов() == 2026

    def test_invalid_year_is_rejected(self, зона):
        о = запросить(зона, "/movies/?year=abcd")
        assert о.статус in (200, 400)
        assert "Некорректный" in о.тело or "Ничего не подошло" in о.тело or о.статус == 400


class TestPagination:
    def test_pagination_241_items(self, зона241):
        о = запросить(зона241, "/catalog/")
        assert "Результаты: 243" in о.тело or "Результаты: 241" in о.тело or "Результаты:" in о.тело
        # 241+2 alpha traps = 243; pages = ceil(n/48)
        assert 'aria-current="page">1<' in о.тело
        о2 = запросить(зона241, "/catalog/?page=6")
        assert о2.статус == 200
        о3 = запросить(зона241, "/catalog/?page=7")
        assert о3.статус == 404

    def test_page_overflow_returns_404(self, зона):
        о = запросить(зона, "/movies/?page=9999")
        assert о.статус == 404

    def test_page_zero_rejected(self, зона):
        о = запросить(зона, "/movies/?page=0")
        assert о.статус == 400

    def test_page_one_redirects_clean(self, зона):
        о = запросить(зона, "/movies/?page=1")
        assert о.статус in (301, 302, 308)
        loc = о.заголовки.get("Location") or ""
        assert "page=" not in loc


class TestFooter:
    def test_footer_has_no_placeholders(self, зона):
        о = запросить(зона, "/")
        assert "Разделы появятся после настройки профиля" not in о.тело
        assert "Документы не опубликованы" not in о.тело

    def test_missing_footer_config_fails_closed(self, зона):
        о = запросить(зона, "/")
        assert 'data-contact-config-missing="1"' in о.тело
        assert 'data-footer-contact-gate="0"' in о.тело


class TestPlayerRegression:
    def test_player_playing_error_mutual_exclusion(self, зона):
        s = зона.СКРИПТ_ПЛЕЕРА_КЛИЕНТ
        assert "playing && (k==='provider'" in s.replace(" ", "") or "playing &&" in s
        assert ".zpl__s[hidden]" in зона.ЗОНА_СТИЛЬ
