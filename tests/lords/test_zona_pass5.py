"""Zona PASS5: densify cards, year facets full-set, page size 28, footer fallback."""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from pathlib import Path

import pytest

ИСХОДНИК = Path(__file__).resolve().parents[2] / "automation" / "host" / "lords-frontend.py"


def _каталог(n=300):
    items = []
    for i in range(n):
        kind = "Фильм" if i % 3 == 0 else ("Сериал" if i % 3 == 1 else "Мультфильм")
        year = 2026 - (i % 40)
        items.append({
            "slug": f"t-{i:04d}", "title": f"Title {i:04d}", "kind": kind,
            "year": year, "poster": f"https://poster.example/{i}.webp",
            "url": f"/title/t-{i:04d}/",
            "published_at": f"2026-09-{(i % 28) + 1:02d}T00:00:00Z",
        })
    items.append({
        "slug": "deep-1995", "title": "Deep Archive 1995", "kind": "Фильм",
        "year": 1995, "poster": "https://poster.example/deep.webp",
        "url": "/title/deep-1995/",
        "published_at": "2010-01-01T00:00:00Z",
    })
    items.append({
        "slug": "fresh-film", "title": "Яркая премьера", "kind": "Фильм", "year": 2026,
        "poster": "https://poster.example/fresh.webp", "url": "/title/fresh-film/",
        "published_at": "2026-09-18T00:00:00Z",
    })
    return {"version": 2, "count": len(items), "items": items, "site": "zona-01",
            "schema": "nova-catalog/2.0.0", "revision": "pass5",
            "builtAt": "2026-09-19T00:00:00Z"}


def _подробности(catalog):
    details = {}
    for it in catalog["items"]:
        d = {
            "id": f"id-{it['slug']}",
            "description": f"Desc for {it['slug']} with enough text to wrap two lines on a card.",
            "genres": ["драма", "триллер"],
            "genre_codes": ["drama", "triller"],
            "countries": ["США"],
            "sources": [{"provider": "kp", "source_id": "1",
                         "availability_status": "available"}],
            "external_ids": {"kp": "1"},
            "playable": True,
            "imdb_rating": 7.2,
            "kinopoisk_rating": 7.4,
            "ratings_by_source": {
                "imdb": {"value": 7.2, "votes": 10, "source": "imdb"},
                "kp": {"value": 7.4, "votes": 10, "source": "kp"},
            },
        }
        if it["slug"] == "fresh-film":
            d["premiere_date"] = "2026-09-19"
        if it["kind"] == "Сериал":
            d["seasons"] = [{"n": 1, "eps": 10, "avail": 3}]
        details[it["slug"]] = d
    return {
        "schema": "nova-details/1.0.0", "site": "zona-01",
        "details_total": len(details), "source": "test",
        "items_total": len(details), "details": details,
    }


def _поднять(tmp_path, n=300):
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
        "build_id": "PASS5", "artifact_sha256": "0" * 64,
        "profile": "zona-test", "built_at": "2026-09-19T00:00:00Z",
    }), encoding="utf-8")
    старое = dict(os.environ)
    os.environ["LORDS_TEMPLATE_MANIFEST"] = str(манифест)
    os.environ["LORDS_CATALOG"] = str(корень / "zona-01-catalog.json")
    os.environ["LORDS_DETAILS"] = str(корень / "zona-01-details.json")
    os.environ["LORDS_PLAYER_CONFIG"] = str(корень / "player-zona-01.json")
    os.environ["LORDS_SITE_NAME"] = "Zona Pass5"
    os.environ["LORDS_CLOCK_ISO"] = "2026-09-19T12:00:00Z"
    try:
        имя = "nova_zona_pass5"
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
    return _поднять(tmp_path_factory.mktemp("zona-pass5"), n=300)


class TestPageSize:
    def test_page_size_is_28(self, зона):
        assert зона.НА_СТРАНИЦЕ_1_1 == 28


class TestYearFacets:
    def test_year_facets_not_capped_at_24(self, зона):
        о = запросить(зона, "/movies/")
        assert о.статус == 200
        assert "zona-year-facet" in о.тело
        assert re.search(r"199[0-9]|198[0-9]", о.тело)

    def test_year_1995_reachable(self, зона):
        о = запросить(зона, "/movies/?year=1995")
        assert о.статус == 200
        assert "Deep Archive" in о.тело or "deep-1995" in о.тело

    def test_record_after_240_in_year_facet(self, зона):
        о = запросить(зона, "/movies/")
        assert "1995" in о.тело


class TestCardInformation:
    def test_card_shows_country_genre_and_sourced_rating(self, зона):
        о = запросить(зона, "/movies/")
        assert "КП" in о.тело
        assert "IMDb" in о.тело
        assert "США" in о.тело or "драма" in о.тело
        assert "N/A" not in о.тело

    def test_css_has_seven_and_eight_columns(self, зона):
        assert "repeat(7," in зона.ЗОНА_СТИЛЬ
        assert "repeat(8," in зона.ЗОНА_СТИЛЬ
        assert "--z-card-max:180px" in зона.ЗОНА_СТИЛЬ


class TestFooterFallback:
    def test_footer_has_two_link_columns_without_contacts(self, зона):
        о = запросить(зона, "/")
        assert о.тело.count("zft__col--links") >= 2
        assert "Разделы появятся" not in о.тело
        assert "Документы не опубликованы" not in о.тело
        assert 'data-contact-config-missing="1"' in о.тело


class TestDetailFacts:
    def test_title_has_semantic_facts(self, зона):
        о = запросить(зона, "/title/fresh-film/")
        assert о.статус == 200
        assert 'data-testid="title-facts"' in о.тело
        assert "<dt>" in о.тело


class TestNoIndex:
    def test_noindex_preserved(self, зона):
        о = запросить(зона, "/")
        assert "noindex" in о.тело
