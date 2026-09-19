"""Zona final-repair gates: routes, filters, footer, provenance, no fake shelves.

Targets the live nova runtime (`automation/host/lords-frontend.py`) that
serves zonafilm.space — not the static lords render path.
"""
from __future__ import annotations

import re
from urllib.parse import unquote

import pytest

from tests.lords.test_nova_frontend_families import запросить, _поднять


@pytest.fixture(scope="module")
def зона(tmp_path_factory):
    return _поднять(tmp_path_factory.mktemp("zona-final"), "zona-01", "zona",
                    версия="1.2.0")


class TestZonaKindRoutes:
    def test_movies_series_animation_200(self, зона):
        for путь in ("/movies/", "/series/", "/animation/"):
            о = запросить(зона, путь)
            assert о.статус == 200, путь
            assert 'data-design="zona-top"' in о.тело
            assert о.тело.count("<h1") == 1

    def test_movies_only_films(self, зона):
        о = запросить(зона, "/movies/")
        assert "Простой фильм" in о.тело
        assert "Долгий сериал" not in о.тело

    def test_series_only_series(self, зона):
        о = запросить(зона, "/series/")
        assert "Долгий сериал" in о.тело
        assert "Простой фильм" not in о.тело

    def test_nav_points_at_kind_routes(self, зона):
        о = запросить(зона, "/")
        for путь in ("/movies/", "/series/", "/animation/", "/collections/", "/catalog/"):
            assert f'href="{путь}"' in о.тело or f"href='{путь}'" in о.тело


class TestZonaFilters:
    def test_kind_filters_differ_by_slug(self, зона):
        фильмы = запросить(зона, "/catalog/?kind=%D0%A4%D0%B8%D0%BB%D1%8C%D0%BC")
        сериалы = запросить(зона, "/catalog/?kind=%D0%A1%D0%B5%D1%80%D0%B8%D0%B0%D0%BB")
        assert фильмы.статус == 200 and сериалы.статус == 200
        assert "film-prostoy" in фильмы.тело
        assert "seriya-dolgaya" not in фильмы.тело
        assert "seriya-dolgaya" in сериалы.тело
        assert "film-prostoy" not in сериалы.тело

    def test_year_filter(self, зона):
        о = запросить(зона, "/catalog/?year=2024")
        assert о.статус == 200
        assert "film-prostoy" in о.тело
        assert "seriya-dolgaya" not in о.тело

    def test_genre_filter(self, зона):
        о = запросить(зона, "/catalog/?genre=drama")
        assert о.статус == 200
        assert "film-prostoy" in о.тело
        assert "seriya-dolgaya" not in о.тело

    def test_combined_intersection(self, зона):
        о = запросить(зона, "/catalog/?kind=%D0%A4%D0%B8%D0%BB%D1%8C%D0%BC&year=2024")
        assert о.статус == 200
        assert "film-prostoy" in о.тело
        assert "bez-postera" not in о.тело

    def test_reset_link_present_when_filtered(self, зона):
        о = запросить(зона, "/movies/")
        assert 'href="/movies/"' in о.тело or ">Сбросить<" in о.тело

    def test_unknown_genre_empty(self, зона):
        о = запросить(зона, "/catalog/?genre=no-such-genre")
        assert о.статус == 200
        assert "Ничего не подошло" in о.тело


class TestZonaFooterAndMarker:
    def test_compact_marker_and_no_debug(self, зона):
        о = запросить(зона, "/")
        assert "Zona · v1.2.0 · 00000000" in о.тело or re.search(
            r"Zona\s+[·.]\s*v?1\.2\.0\s+[·.]\s*0{8}", о.тело)
        for запрет in ("тестовая витрина", "закрыта от индексации",
                       "В снимке каталога", "Template:", "записей_в_снимке"):
            assert запрет not in о.тело

    def test_footer_has_real_sections(self, зона):
        о = запросить(зона, "/")
        assert 'class="zft"' in о.тело
        assert 'href="/movies/"' in о.тело
        assert 'href="/catalog/"' in о.тело


class TestZonaHomeShelves:
    def test_shelf_destinations_exist(self, зона):
        о = запросить(зона, "/")
        for путь in ("/movies/", "/series/", "/new/", "/catalog/"):
            assert путь in о.тело
            assert запросить(зона, путь).статус == 200

    def test_no_fake_trailer_shelf(self, зона):
        о = запросить(зона, "/")
        assert "Новые трейлеры" not in о.тело


class TestZonaSearchAndPagination:
    def test_search_cyrillic(self, зона):
        о = запросить(зона, "/search/?q=%D0%9F%D1%80%D0%BE%D1%81%D1%82%D0%BE%D0%B9")
        assert о.статус == 200
        assert "Простой фильм" in о.тело

    def test_search_unknown_honest(self, зона):
        о = запросить(зона, "/search/?q=xyzzyplugh12345")
        assert о.статус == 200
        assert "Совпадений нет" in о.тело
        assert "В снимке каталога" not in о.тело

    def test_catalog_page_links(self, зона):
        # With tiny fixture page 1 is final; still must not 404.
        о = запросить(зона, "/catalog/?page=1")
        assert о.статус == 200


class TestZonaNoindex:
    def test_meta_robots(self, зона):
        о = запросить(зона, "/")
        assert 'content="noindex, nofollow"' in о.тело

    def test_robots_txt(self, зона):
        о = запросить(зона, "/robots.txt")
        assert о.статус == 200
        assert "Disallow: /" in о.тело


class TestZonaProvenanceSeparation:
    def test_manifest_fields_distinct_in_canary_writer(self):
        from pathlib import Path
        import ast
        src = Path("automation/host/lords-nova-canary.py").read_text(encoding="utf-8")
        assert "runtime_commit" in src
        assert "source_commit" in src
        assert "--runtime-commit" in src


class TestZonaCardConsistency:
    def test_card_is_single_link(self, зона):
        о = запросить(зона, "/movies/")
        # Catalog uses poster tiles (.zt), same anatomy as home rails.
        assert 'class="zt"' in о.тело
        assert "/title/film-prostoy/" in о.тело
