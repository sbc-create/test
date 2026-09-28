"""Search must not fill absent/weak queries with catalog noise.

P0 from LORDS-THREE-DISTINCT-TEMPLATES-02 independent visual audit:
`/search/?q=qzxv-no-such-title-visual-audit` returned 120 false cards.
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


def _items():
    return [
        {"slug": "matrica", "title": "Матрица", "kind": "Фильм", "year": 1999,
         "poster": "https://p/a.webp", "url": "/title/matrica/",
         "published_at": "2026-01-01T00:00:00Z", "original_title": "The Matrix"},
        {"slug": "temnyy-rycar", "title": "Тёмный рыцарь", "kind": "Фильм", "year": 2008,
         "poster": "https://p/b.webp", "url": "/title/temnyy-rycar/",
         "published_at": "2026-01-02T00:00:00Z", "original_title": "The Dark Knight"},
        {"slug": "zvezdnye-voyny", "title": "Звёздные войны", "kind": "Фильм", "year": 1977,
         "poster": "https://p/c.webp", "url": "/title/zvezdnye-voyny/",
         "published_at": "2026-01-03T00:00:00Z", "original_title": "Star Wars"},
        {"slug": "interstellar", "title": "Интерстеллар", "kind": "Фильм", "year": 2014,
         "poster": "https://p/d.webp", "url": "/title/interstellar/",
         "published_at": "2026-01-04T00:00:00Z", "original_title": "Interstellar"},
        {"slug": "pylnye-utesy", "title": "Пыльные утёсы", "kind": "Сериал", "year": 2024,
         "poster": "https://p/e.webp", "url": "/title/pylnye-utesy/",
         "published_at": "2026-01-05T00:00:00Z", "original_title": "Dusty Cliffs"},
        # Decoy whose original contains the English word "title"
        {"slug": "working-title", "title": "Рабочее название", "kind": "Фильм", "year": 2020,
         "poster": "https://p/f.webp", "url": "/title/working-title/",
         "published_at": "2026-01-06T00:00:00Z", "original_title": "A Working Title Story"},
    ]


@pytest.fixture
def данные(tmp_path, monkeypatch):
    корень = tmp_path / "site"
    корень.mkdir()
    cat = {
        "version": 2, "count": 6, "items": _items(), "fields_absent": [],
        "site": "search-fix", "schema": "nova-catalog/2.0.0",
        "revision": "t", "builtAt": "2026-09-20T00:00:00Z",
    }
    (корень / "search-fix-catalog.json").write_text(
        json.dumps(cat, ensure_ascii=False), encoding="utf-8")
    man = корень / "manifest.json"
    man.write_text(json.dumps({
        "schema_version": 1, "template_family": "lords",
        "design_version": "1.1.0", "source_commit": "0" * 40,
        "build_id": "TEST-SEARCH", "artifact_sha256": "0" * 64,
        "profile": "lords-general", "built_at": "2026-09-20T00:00:00Z",
    }), encoding="utf-8")
    monkeypatch.setenv("LORDS_TEMPLATE_MANIFEST", str(man))
    monkeypatch.setenv("LORDS_CATALOG", str(корень / "search-fix-catalog.json"))
    monkeypatch.setenv("LORDS_SITE_NAME", "Search Fix")
    monkeypatch.delenv("LORDS_DETAILS", raising=False)
    monkeypatch.delenv("LORDS_PLAYER_CONFIG", raising=False)

    имя = "nova_search_absent_contract"
    спец = importlib.util.spec_from_file_location(имя, ИСХОДНИК)
    мод = importlib.util.module_from_spec(спец)
    sys.modules[имя] = мод
    спец.loader.exec_module(мод)
    return мод.Данные(str(корень / "search-fix-catalog.json"))


class TestSearchAbsentAndExact:
    def test_nonsense_query_returns_zero(self, данные):
        hit = данные.искать("qzxv-no-such-title-visual-audit")
        assert hit == [], (
            f"absent query must not fill catalog noise, got {len(hit)}: "
            f"{[з['slug'] for з in hit]}")

    def test_zzzzzz_returns_zero(self, данные):
        assert данные.искать("зззззззззз") == []

    def test_exact_title_is_top1(self, данные):
        hit = данные.искать("Пыльные утёсы")
        assert hit and hit[0]["slug"] == "pylnye-utesy"

    def test_original_title_is_top1(self, данные):
        hit = данные.искать("The Matrix")
        assert hit and hit[0]["slug"] == "matrica"

    def test_translit_matrix(self, данные):
        hit = данные.искать("matrica")
        assert hit and hit[0]["slug"] == "matrica"

    def test_typo_still_finds_matrix(self, данные):
        hit = данные.искать("матрца")
        assert any(з["slug"] == "matrica" for з in hit)

    def test_layout_vfnhbwf_finds_matrix(self, данные):
        hit = данные.искать("vfnhbwf")
        assert any(з["slug"] == "matrica" for з in hit)
