"""Missing rating must not leave an empty black footer or invent 0.

P1 from THREE-DISTINCT audit: ~7/58 home cards had a blank rating strip.
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


@pytest.fixture
def fe(tmp_path, monkeypatch):
    корень = tmp_path / "site"
    корень.mkdir()
    items = [
        {"slug": "rated", "title": "Rated", "kind": "Фильм", "year": 2020,
         "poster": "https://p/a.webp", "url": "/title/rated/",
         "published_at": "2026-01-01T00:00:00Z"},
        {"slug": "unrated", "title": "Unrated", "kind": "Фильм", "year": 2021,
         "poster": "https://p/b.webp", "url": "/title/unrated/",
         "published_at": "2026-01-02T00:00:00Z"},
        {"slug": "noyear", "title": "No Year", "kind": "Фильм", "year": None,
         "poster": "https://p/c.webp", "url": "/title/noyear/",
         "published_at": "2026-01-03T00:00:00Z"},
    ]
    (корень / "cat.json").write_text(json.dumps({
        "version": 2, "count": 3, "items": items, "fields_absent": [],
        "site": "card-fix", "schema": "nova-catalog/2.0.0",
        "revision": "t", "builtAt": "2026-09-20T00:00:00Z",
    }), encoding="utf-8")
    (корень / "det.json").write_text(json.dumps({
        "schema": "nova-details/1.0.0", "site": "card-fix",
        "details_total": 3, "source": "test", "items_total": 3,
        "details": {
            "rated": {"kinopoisk_rating": 7.5, "imdb_rating": 8.1},
            "unrated": {},
            "noyear": {"kinopoisk_rating": 6.0},
        },
    }), encoding="utf-8")
    man = корень / "manifest.json"
    man.write_text(json.dumps({
        "schema_version": 1, "template_family": "lords",
        "design_version": "1.1.0", "source_commit": "0" * 40,
        "build_id": "TEST-CARD", "artifact_sha256": "0" * 64,
        "profile": "lords-general", "built_at": "2026-09-20T00:00:00Z",
    }), encoding="utf-8")
    monkeypatch.setenv("LORDS_TEMPLATE_MANIFEST", str(man))
    monkeypatch.setenv("LORDS_CATALOG", str(корень / "cat.json"))
    monkeypatch.setenv("LORDS_SITE_NAME", "Card Fix")
    monkeypatch.delenv("LORDS_DETAILS", raising=False)
    имя = "nova_card_rating_contract"
    спец = importlib.util.spec_from_file_location(имя, ИСХОДНИК)
    мод = importlib.util.module_from_spec(спец)
    sys.modules[имя] = мод
    спец.loader.exec_module(мод)
    мод.Обработчик.данные = мод.Данные(str(корень / "cat.json"))
    мод.Обработчик.подробности = мод.Подробности(str(корень / "det.json"))
    мод.Обработчик.индекс = мод.построить_индекс(
        мод.Обработчик.данные, мод.Обработчик.подробности)
    return мод


def _home(мод):
    gathered = {"body": b""}

    class Stub(мод.Обработчик):
        def __init__(self):
            self.path = "/"
            self.command = "GET"
            self.headers = {"Host": "test.example"}

        def _отдать(self, body, тип="text/html; charset=utf-8", код=200):
            gathered["body"] = body

        def send_response(self, код):
            pass

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
    s.маршрут_1_1("/", {})
    body = gathered["body"]
    return body.decode("utf-8") if isinstance(body, bytes) else body


class TestMissingRatingFooter:
    def test_no_empty_black_rating_strip(self, fe):
        html = _home(fe)
        # Empty decorative strips are forbidden.
        assert 'class="c__r" aria-hidden="true"' not in html
        assert "КП<i>0</i>" not in html
        assert "IMDb<i>0</i>" not in html

    def test_missing_rating_collapses_or_neutral_status(self, fe):
        html = _home(fe)
        # Either no c__r at all for unrated, or an honest status string.
        cards = re.findall(r'<a class="c"[^>]*>.*?</a>', html, re.S)
        unrated = [c for c in cards if "/title/unrated/" in c]
        assert unrated, "unrated card missing from home"
        card = unrated[0]
        if 'class="c__r"' in card:
            assert "Оценок пока нет" in card or "нет оценки" in card.lower()
        # Rated card still shows numbers
        rated = [c for c in cards if "/title/rated/" in c][0]
        assert "7.5" in rated or "8.1" in rated
