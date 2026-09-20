"""Recommendation contract: proven similarity or honest «Ещё в каталоге».

Related must exclude current/duplicates, prefer genre/year/country (or
series/franchise for series profile), and never present a bare catalog
slice as «Похожее».
"""

from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import sys

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ИСХОДНИК = КОРЕНЬ / "automation" / "host" / "lords-frontend.py"


def _catalog():
    return {
        "version": 2, "count": 8,
        "items": [
            {"slug": "matrix", "title": "Матрица", "kind": "Фильм", "year": 1999,
             "poster": "https://p/a.webp", "url": "/title/matrix/",
             "published_at": "2026-01-01T00:00:00Z"},
            {"slug": "matrix-reloaded", "title": "Матрица: Перезагрузка", "kind": "Фильм",
             "year": 2003, "poster": "https://p/b.webp", "url": "/title/matrix-reloaded/",
             "published_at": "2026-01-02T00:00:00Z"},
            {"slug": "dark-knight", "title": "Тёмный рыцарь", "kind": "Фильм", "year": 2008,
             "poster": "https://p/c.webp", "url": "/title/dark-knight/",
             "published_at": "2026-01-03T00:00:00Z"},
            {"slug": "inception", "title": "Начало", "kind": "Фильм", "year": 2010,
             "poster": "https://p/d.webp", "url": "/title/inception/",
             "published_at": "2026-01-04T00:00:00Z"},
            {"slug": "random-comedy", "title": "Случайная комедия", "kind": "Фильм",
             "year": 2020, "poster": "https://p/e.webp", "url": "/title/random-comedy/",
             "published_at": "2026-01-05T00:00:00Z"},
            {"slug": "series-a", "title": "Сериал А", "kind": "Сериал", "year": 2021,
             "poster": "https://p/f.webp", "url": "/title/series-a/",
             "published_at": "2026-01-06T00:00:00Z"},
            {"slug": "series-b", "title": "Сериал Б", "kind": "Сериал", "year": 2022,
             "poster": "https://p/g.webp", "url": "/title/series-b/",
             "published_at": "2026-01-07T00:00:00Z"},
            {"slug": "orphan", "title": "Сирота без жанров", "kind": "Фильм", "year": 1990,
             "poster": "https://p/h.webp", "url": "/title/orphan/",
             "published_at": "2026-01-08T00:00:00Z"},
        ],
        "fields_absent": [], "site": "rec-fix", "schema": "nova-catalog/2.0.0",
        "revision": "t", "builtAt": "2026-09-20T00:00:00Z",
    }


def _details():
    return {
        "schema": "nova-details/1.0.0", "site": "rec-fix",
        "details_total": 8, "source": "test", "items_total": 8,
        "details": {
            "matrix": {"genres": ["фантастика", "боевик"], "genre_codes": ["sci-fi", "action"],
                       "countries": ["США"], "is_series": False},
            "matrix-reloaded": {"genres": ["фантастика", "боевик"],
                                "genre_codes": ["sci-fi", "action"],
                                "countries": ["США"], "is_series": False},
            "dark-knight": {"genres": ["боевик", "криминал"],
                            "genre_codes": ["action", "crime"],
                            "countries": ["США"], "is_series": False},
            "inception": {"genres": ["фантастика", "боевик"],
                          "genre_codes": ["sci-fi", "action"],
                          "countries": ["США", "Великобритания"], "is_series": False},
            "random-comedy": {"genres": ["комедия"], "genre_codes": ["comedy"],
                              "countries": ["Россия"], "is_series": False},
            "series-a": {"genres": ["драма"], "genre_codes": ["drama"],
                         "countries": ["США"], "is_series": True,
                         "seasons": [{"n": 1, "eps": 3, "avail": 3}]},
            "series-b": {"genres": ["драма"], "genre_codes": ["drama"],
                         "countries": ["США"], "is_series": True,
                         "seasons": [{"n": 1, "eps": 2, "avail": 2}]},
            "orphan": {"genres": [], "genre_codes": [], "countries": [],
                       "is_series": False},
        },
    }


@pytest.fixture
def fe(tmp_path, monkeypatch):
    корень = tmp_path / "site"
    корень.mkdir()
    (корень / "cat.json").write_text(json.dumps(_catalog(), ensure_ascii=False),
                                     encoding="utf-8")
    (корень / "det.json").write_text(json.dumps(_details(), ensure_ascii=False),
                                     encoding="utf-8")
    man = корень / "manifest.json"
    man.write_text(json.dumps({
        "schema_version": 1, "template_family": "lords",
        "design_version": "1.1.0", "source_commit": "0" * 40,
        "build_id": "TEST-REC", "artifact_sha256": "0" * 64,
        "profile": "lords-general", "built_at": "2026-09-20T00:00:00Z",
    }), encoding="utf-8")
    monkeypatch.setenv("LORDS_TEMPLATE_MANIFEST", str(man))
    monkeypatch.setenv("LORDS_CATALOG", str(корень / "cat.json"))
    monkeypatch.setenv("LORDS_SITE_NAME", "Rec Fix")
    monkeypatch.delenv("LORDS_DETAILS", raising=False)
    monkeypatch.delenv("LORDS_PLAYER_CONFIG", raising=False)
    имя = "nova_rec_contract"
    спец = importlib.util.spec_from_file_location(имя, ИСХОДНИК)
    мод = importlib.util.module_from_spec(спец)
    sys.modules[имя] = мод
    спец.loader.exec_module(мод)
    данные = мод.Данные(str(корень / "cat.json"))
    подроб = мод.Подробности(str(корень / "det.json"))
    индекс = мод.построить_индекс(данные, подроб)
    вид = мод.ВидЛордс(мод.СЕМЕЙСТВА_1_1["lords"], данные, подроб, индекс, "Rec Fix")
    return мод, вид, данные, подроб


class TestRecommendationContract:
    def test_excludes_current_and_duplicates(self, fe):
        _, вид, данные, подроб = fe
        запись = данные.items[0]  # matrix
        деталь = подроб.get("matrix")
        hits = вид.похожие(запись, деталь, сколько=6)
        slugs = [з["slug"] for з in hits]
        assert "matrix" not in slugs
        assert len(slugs) == len(set(slugs))

    def test_genre_overlap_beats_catalog_tail(self, fe):
        _, вид, данные, подроб = fe
        запись = next(з for з in данные.items if з["slug"] == "matrix")
        hits = вид.похожие(запись, подроб.get("matrix"), сколько=4)
        slugs = [з["slug"] for з in hits]
        assert "matrix-reloaded" in slugs
        assert "inception" in slugs
        # Random comedy shares kind but not genre — must not outrank genre peers
        if "random-comedy" in slugs:
            assert slugs.index("random-comedy") > slugs.index("matrix-reloaded")

    def test_orphan_fallback_labeled_catalog_not_similar(self, fe):
        мод, вид, данные, подроб = fe
        запись = next(з for з in данные.items if з["slug"] == "orphan")
        hits, meta = вид.похожие_с_мета(запись, подроб.get("orphan"), сколько=4)
        assert meta["heading"] == "Ещё в каталоге"
        assert meta["reason_codes"]
        assert all(r.startswith("catalog_") or r == "kind_fallback"
                   for r in meta["reason_codes"])
        # HTML uses honest heading
        html = вид.тайтл(запись, подроб.get("orphan"))
        assert "Ещё в каталоге" in html
        assert 'data-rec-heading="Ещё в каталоге"' in html
        # Must not claim similarity when only kind_fallback filled the shelf.
        assert "<h2>Похожее</h2>" not in html
