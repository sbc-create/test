"""Filter state: selected year stays in UI; genres are unique.

P0: /catalog/?year=1902 returns 1 hit but year select shows «Все»;
changing genre drops 1902. Genre select can list duplicate labels/slugs.
"""

from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import re
import sys
from urllib.parse import parse_qs, urlparse

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ИСХОДНИК = КОРЕНЬ / "automation" / "host" / "lords-frontend.py"


def _items():
    items = []
    # Many recent years so [:20] would exclude 1902 without the inject fix.
    for i, year in enumerate(list(range(2026, 2006, -1)) + [1902]):
        items.append({
            "slug": f"t{i}-{year}", "title": f"Title {year}", "kind": "Фильм",
            "year": year, "poster": f"https://p/{i}.webp",
            "url": f"/title/t{i}-{year}/",
            "published_at": f"2026-01-{(i % 28) + 1:02d}T00:00:00Z",
        })
    return items


def _details(items):
    # Duplicate genre labels under different spellings/slugs to reproduce P0.
    details = {}
    for i, з in enumerate(items):
        genres = ["комедия", "Комедия", "боевик"] if i % 2 == 0 else ["драма", "Драма"]
        details[з["slug"]] = {
            "genres": genres, "countries": ["США"],
            "kinopoisk_rating": 7.0, "is_series": False,
        }
    return details


@pytest.fixture
def fe(tmp_path, monkeypatch):
    корень = tmp_path / "site"
    корень.mkdir()
    items = _items()
    cat = {
        "version": 2, "count": len(items), "items": items, "fields_absent": [],
        "site": "facet-fix", "schema": "nova-catalog/2.0.0",
        "revision": "t", "builtAt": "2026-09-20T00:00:00Z",
    }
    (корень / "cat.json").write_text(json.dumps(cat, ensure_ascii=False), encoding="utf-8")
    det = {
        "schema": "nova-details/1.0.0", "site": "facet-fix",
        "details_total": len(items), "source": "test", "items_total": len(items),
        "details": _details(items),
    }
    (корень / "det.json").write_text(json.dumps(det, ensure_ascii=False), encoding="utf-8")
    man = корень / "manifest.json"
    man.write_text(json.dumps({
        "schema_version": 1, "template_family": "lords",
        "design_version": "1.1.0", "source_commit": "0" * 40,
        "build_id": "TEST-FACET", "artifact_sha256": "0" * 64,
        "profile": "lords-general", "built_at": "2026-09-20T00:00:00Z",
    }), encoding="utf-8")
    monkeypatch.setenv("LORDS_TEMPLATE_MANIFEST", str(man))
    monkeypatch.setenv("LORDS_CATALOG", str(корень / "cat.json"))
    monkeypatch.setenv("LORDS_SITE_NAME", "Facet Fix")
    monkeypatch.delenv("LORDS_DETAILS", raising=False)
    monkeypatch.delenv("LORDS_PLAYER_CONFIG", raising=False)
    имя = "nova_facet_state_contract"
    спец = importlib.util.spec_from_file_location(имя, ИСХОДНИК)
    мод = importlib.util.module_from_spec(спец)
    sys.modules[имя] = мод
    спец.loader.exec_module(мод)
    мод.Обработчик.данные = мод.Данные(str(корень / "cat.json"))
    мод.Обработчик.подробности = мод.Подробности(str(корень / "det.json"))
    мод.Обработчик.индекс = мод.построить_индекс(
        мод.Обработчик.данные, мод.Обработчик.подробности)
    return мод


def _req(мод, path: str):
    gathered = {"status": 200, "body": b""}

    class Stub(мод.Обработчик):
        def __init__(self):
            self.path = path
            self.command = "GET"
            self.headers = {"Host": "test.example"}

        def _отдать(self, body, тип="text/html; charset=utf-8", код=200):
            gathered["status"] = код
            gathered["body"] = body

        def send_response(self, код):
            gathered["status"] = код

        def send_header(self, n, v):
            pass

        def end_headers(self):
            pass

        @property
        def wfile(self):
            class W:
                def write(self, b):
                    gathered["body"] = b
            return W()

    s = Stub()
    u = urlparse(path)
    s.маршрут_1_1(u.path, parse_qs(u.query))
    body = gathered["body"]
    if isinstance(body, bytes):
        body = body.decode("utf-8")
    return gathered["status"], body


def _year_select(body: str) -> str:
    m = re.search(r'<select name="year"[^>]*>(.*?)</select>', body, re.S)
    assert m, "year select missing"
    return m.group(1)


def _genre_options(body: str) -> list[tuple[str, str]]:
    m = re.search(r'<select name="genre"[^>]*>(.*?)</select>', body, re.S)
    assert m, "genre select missing"
    return re.findall(r'<option value="([^"]*)"[^>]*>([^<]*)</option>', m.group(1))


class TestYearFacetState:
    def test_legacy_year_is_selected_option(self, fe):
        status, body = _req(fe, "/catalog/?year=1902")
        assert status == 200
        sel = _year_select(body)
        assert 'value="1902" selected' in sel or 'value="1902" selected>' in sel.replace(
            " selected>", " selected>")
        assert re.search(r'<option value="1902"[^>]*selected', sel)

    def test_year_preserved_in_genre_segment_links(self, fe):
        status, body = _req(fe, "/catalog/?year=1902")
        assert status == 200
        # Kind segment / movies link must keep year=1902
        assert re.search(r'href="/movies/\?[^"]*year=1902', body)
        assert re.search(r'href="/series/\?[^"]*year=1902', body)

    def test_year_plus_genre_keeps_both(self, fe):
        # Pick a real genre code from the index
        idx = fe.Обработчик.индекс
        genre_code = (idx.get("genre_names") or [("comedy", "комедия")])[0][0]
        status, body = _req(fe, f"/catalog/?year=1902&genre={genre_code}")
        assert status == 200
        assert re.search(r'<option value="1902"[^>]*selected', _year_select(body))
        assert re.search(
            rf'<option value="{re.escape(genre_code)}"[^>]*selected', body)


class TestGenreDedupe:
    def test_genre_options_unique_by_value(self, fe):
        status, body = _req(fe, "/catalog/")
        assert status == 200
        opts = _genre_options(body)
        values = [v for v, _ in opts if v]  # skip empty «Все»
        assert len(values) == len(set(values)), f"duplicate genre values: {values}"

    def test_genre_labels_unique_casefold(self, fe):
        status, body = _req(fe, "/catalog/")
        assert status == 200
        opts = _genre_options(body)
        labels = [lbl.casefold() for _, lbl in opts if _]
        assert len(labels) == len(set(labels)), f"duplicate genre labels: {labels}"
