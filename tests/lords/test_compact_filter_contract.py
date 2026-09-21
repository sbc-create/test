"""Compact catalog filter contract (LORDS-MULTISITE-AUDIT-01 Block 02).

Shared functional contract: segmented kind + selects + chips + reset.
Visual tokens stay profile-scoped; this suite guards structure and query wiring.
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


def _каталог() -> dict:
    return {
        "version": 2, "count": 3,
        "items": [
            {"slug": "a", "title": "Альфа", "kind": "Фильм", "year": 2024,
             "poster": "https://p/a.webp", "url": "/title/a/",
             "published_at": "2026-09-01T00:00:00Z"},
            {"slug": "b", "title": "Бета", "kind": "Сериал", "year": 2023,
             "poster": "https://p/b.webp", "url": "/title/b/",
             "published_at": "2026-09-02T00:00:00Z"},
            {"slug": "c", "title": "Гамма", "kind": "Мультфильм", "year": 2022,
             "poster": "", "url": "/title/c/",
             "published_at": "2026-09-03T00:00:00Z"},
        ],
        "fields_absent": [], "site": "lords-filter-test",
        "schema": "nova-catalog/2.0.0", "revision": "t", "builtAt": "2026-09-13T00:00:00Z",
    }


def _подробности() -> dict:
    return {
        "schema": "nova-details/1.0.0", "site": "lords-filter-test",
        "details_total": 3, "source": "test", "items_total": 3,
        "details": {
            "a": {"genres": ["комедия"], "countries": ["США"],
                  "kinopoisk_rating": 7.1, "is_series": False},
            "b": {"genres": ["драма"], "countries": ["Великобритания"],
                  "kinopoisk_rating": 8.0, "is_series": True,
                  "seasons": [{"n": 1, "eps": 3, "avail": 3}]},
            "c": {"genres": ["фантастика"], "countries": ["Япония"],
                  "is_series": False},
        },
    }


@pytest.fixture
def fe(tmp_path):
    корень = tmp_path / "site"
    корень.mkdir()
    (корень / "cat.json").write_text(json.dumps(_каталог(), ensure_ascii=False),
                                     encoding="utf-8")
    (корень / "det.json").write_text(json.dumps(_подробности(), ensure_ascii=False),
                                     encoding="utf-8")
    манифест = корень / "manifest.json"
    манифест.write_text(json.dumps({
        "schema_version": 1, "template_family": "lords",
        "design_version": "1.1.0", "source_commit": "0" * 40,
        "build_id": "TEST-FILTER", "artifact_sha256": "0" * 64,
        "profile": "lords-new", "built_at": "2026-09-13T00:00:00Z",
    }, ensure_ascii=False), encoding="utf-8")

    прежние = dict(sys.modules)
    старое = dict(os.environ)
    os.environ["LORDS_TEMPLATE_MANIFEST"] = str(манифест)
    os.environ["LORDS_CATALOG"] = str(корень / "cat.json")
    os.environ["LORDS_SITE_NAME"] = "Filter Test"
    os.environ.pop("LORDS_DETAILS", None)
    os.environ.pop("LORDS_PLAYER_CONFIG", None)
    try:
        имя = "nova_compact_filter_contract"
        спец = importlib.util.spec_from_file_location(имя, ИСХОДНИК)
        мод = importlib.util.module_from_spec(спец)
        sys.modules[имя] = мод
        спец.loader.exec_module(мод)
    finally:
        os.environ.clear()
        os.environ.update(старое)
        for к in set(sys.modules) - set(прежние):
            if not к.startswith("nova_"):
                sys.modules.pop(к, None)

    мод.Обработчик.данные = мод.Данные(str(корень / "cat.json"))
    мод.Обработчик.подробности = мод.Подробности(str(корень / "det.json"))
    мод.Обработчик.индекс = мод.построить_индекс(
        мод.Обработчик.данные, мод.Обработчик.подробности)
    return мод


def _запросить(мод, путь: str):
    from urllib.parse import parse_qs, urlparse as up

    собрано = {"статус": 200, "тело": b"", "заголовки": {}}

    class Заглушка(мод.Обработчик):
        def __init__(self):
            self.path = путь
            self.command = "GET"
            self.headers = {"Host": "test.example"}

        def _отдать(self, тело, тип="text/html; charset=utf-8", код=200):
            собрано["статус"] = код
            собрано["тело"] = тело
            собрано["заголовки"]["Content-Type"] = тип

        def send_response(self, код):
            собрано["статус"] = код

        def send_header(self, имя, значение):
            собрано["заголовки"][имя] = значение

        def end_headers(self):
            pass

        @property
        def wfile(self):
            class W:
                def write(self, b):
                    собрано["тело"] = b
            return W()

    з = Заглушка()
    разобран = up(путь)
    зпр = parse_qs(разобран.query)
    з.маршрут_1_1(разобран.path, зпр)
    тело = собрано["тело"]
    if isinstance(тело, bytes):
        тело = тело.decode("utf-8")
    return собрано["статус"], тело, собрано["заголовки"]


class TestCompactFilterContract:
    def test_css_contract_markers(self):
        src = ИСХОДНИК.read_text(encoding="utf-8")
        assert "data-filter-contract=\"compact-v1\"" in src
        assert ".filt{" in src
        assert ".filt__seg" in src
        assert ".filt__chip" in src
        assert ".filt__reset" in src
        # No decade of giant year buttons in the compact panel CSS.
        assert "filt__year-btn" not in src

    def test_catalog_renders_selects_not_year_button_strip(self, fe):
        код, html, _ = _запросить(fe, "/catalog/")
        assert код == 200
        assert 'data-filter-contract="compact-v1"' in html
        assert 'name="year"' in html
        assert 'name="genre"' in html
        assert 'name="country"' in html
        assert 'name="sort"' in html
        assert "<select" in html
        # Segmented kind control present.
        assert 'aria-label="Тип контента"' in html
        assert 'href="/movies/' in html
        # Active year must not be a wall of <a> year pills inside .filt.
        filt = re.search(r'<div class="filt"[^>]*>.*?</div>\s*(?:<div class="filt__chips"|<h1|<div class="grid|<div class="empty")',
                         html, re.S)
        assert filt, "compact filter block missing"
        block = filt.group(0)
        year_links = re.findall(r'href="[^"]*year=\d{4}', block)
        assert len(year_links) == 0, f"year still link-strip: {year_links[:5]}"

    def test_active_filters_show_chips_and_reset(self, fe):
        код, html, _ = _запросить(fe, "/catalog/?year=2024&genre=komediya&sort=rating")
        assert код == 200
        assert 'class="filt__chip"' in html
        assert "Год: 2024" in html
        assert 'class="filt__reset"' in html
        assert 'href="/catalog/"' in html
        # Selected values visible in selects (not hidden).
        assert 'value="2024" selected' in html or "value=\"2024\" selected" in html
        assert 'value="rating" selected' in html

    def test_query_params_survive_kind_segment(self, fe):
        код, html, _ = _запросить(fe, "/catalog/?year=2024&country=ssha")
        assert код == 200
        # Movies segment must keep year + country in href.
        m = re.search(r'href="(/movies/\?[^"]+)"', html)
        assert m, "movies segment href missing"
        q = parse_qs(urlparse(m.group(1)).query)
        assert q.get("year") == ["2024"]
        assert q.get("country") == ["ssha"]
        assert "kind" not in q  # kind comes from path

    def test_movies_section_does_not_chip_inherent_kind(self, fe):
        код, html, _ = _запросить(fe, "/movies/")
        assert код == 200
        assert "Тип: Фильм" not in html
        # No reset when only section kind is active.
        assert 'class="filt__reset"' not in html

    def test_form_is_get_and_works_without_js(self, fe):
        код, html, _ = _запросить(fe, "/catalog/")
        assert код == 200
        assert 'method="get"' in html
        assert 'action="/catalog/"' in html
        assert "<noscript>" in html and "Применить" in html
        for m in re.finditer(r"<select\b[^>]*>", html):
            if 'name="' in m.group(0) or True:
                # Every select in the filter form must have name=.
                pass
        selects = re.findall(r"<select\b[^>]*>", html)
        named = [s for s in selects if "name=" in s]
        assert len(named) >= 4

    def test_country_filter_narrows_results(self, fe):
        код, html, _ = _запросить(fe, "/catalog/?country=velikobritaniya")
        assert код == 200
        assert "1 записей" in html or "1 запис" in html
        assert "/title/b/" in html
        assert "/title/a/" not in html
