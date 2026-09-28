"""Responsive header contract for Lords sheet (Block 04).

Live CSS risk: hamburger hid at 768px while six nav links need ~1000px;
open menu used flex-nowrap 70px row without overlay → clipped links.
"""

from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import re
import sys

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ИСХОДНИК = КОРЕНЬ / "automation" / "host" / "lords-frontend.py"


@pytest.fixture(scope="module")
def мод(tmp_path_factory):
    корень = tmp_path_factory.mktemp("nav")
    cat = {
        "version": 2, "count": 1,
        "items": [{"slug": "a", "title": "A", "kind": "Фильм", "year": 2020,
                   "poster": "https://p/a.webp", "url": "/title/a/",
                   "published_at": "2026-01-01T00:00:00Z"}],
        "fields_absent": [], "site": "nav", "schema": "nova-catalog/2.0.0",
        "revision": "t", "builtAt": "2026-09-20T00:00:00Z",
    }
    (корень / "cat.json").write_text(json.dumps(cat), encoding="utf-8")
    man = корень / "manifest.json"
    man.write_text(json.dumps({
        "schema_version": 1, "template_family": "lords",
        "design_version": "1.1.0", "source_commit": "0" * 40,
        "build_id": "TEST-NAV", "artifact_sha256": "0" * 64,
        "profile": "lords-general", "built_at": "2026-09-20T00:00:00Z",
    }), encoding="utf-8")
    os.environ["LORDS_TEMPLATE_MANIFEST"] = str(man)
    os.environ["LORDS_CATALOG"] = str(корень / "cat.json")
    os.environ["LORDS_SITE_NAME"] = "Nav Fix"
    os.environ.pop("LORDS_DETAILS", None)
    имя = "nova_responsive_nav_contract"
    спец = importlib.util.spec_from_file_location(имя, ИСХОДНИК)
    m = importlib.util.module_from_spec(спец)
    sys.modules[имя] = m
    спец.loader.exec_module(m)
    return m


class TestResponsiveNavCssContract:
    def test_hamburger_survives_past_768(self, мод):
        css = мод.ЛОРДС_СТИЛЬ
        # Must not hide menu button at the old 768 breakpoint alone.
        assert not re.search(
            r"@media\(min-width:768px\)\{\.hd__menu\{display:none\}\}", css), (
            "hamburger must remain until fit-breakpoint (~1024), not 768")
        assert re.search(
            r"@media\(min-width:1024px\)\{\.hd__menu\{display:none\}\}", css)

    def test_open_nav_is_overlay_drawer(self, мод):
        css = мод.ЛОРДС_СТИЛЬ
        assert "position:absolute" in css or "position:fixed" in css
        # Open state must not rely on flex-wrap into a 70px nowrap row alone.
        assert re.search(r"\.hd__nav\.is-open\{[^}]*display:flex", css)
        assert "hd__nav" in css and ("z-index" in css)

    def test_desktop_nav_row_from_1024(self, мод):
        css = мод.ЛОРДС_СТИЛЬ
        assert re.search(
            r"@media\(min-width:1024px\)\{[^}]*\.hd__nav\{[^}]*display:flex",
            css, re.S) or re.search(
            r"@media\(min-width:1024px\)\{\.hd__nav\{display:flex", css)

    def test_search_icon_is_svg_not_neuter(self, мод):
        from urllib.parse import parse_qs, urlparse

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

        мод.Обработчик.данные = мод.Данные(os.environ["LORDS_CATALOG"])
        мод.Обработчик.подробности = мод.Подробности("")
        мод.Обработчик.индекс = {
            "slug": {}, "genre": {}, "genre_names": [],
            "country": {}, "country_names": [],
        }
        s = Stub()
        s.маршрут_1_1("/", {})
        html = gathered["body"].decode("utf-8") if isinstance(gathered["body"], bytes) else gathered["body"]
        assert "&#9906;" not in html and "⚲" not in html
        assert "<svg" in html and 'aria-label="Найти"' in html

    def test_nav_script_closes_on_outside_click(self, мод):
        js = мод.СКРИПТ_ЛОРДС_ШАПКА
        assert "Escape" in js
        assert "closest('.hd')" in js
