"""Invalid catalog page must be HTTP 404, not soft-clamped last page.

P0: /catalog/?page=999999 returned last-page cards under the invalid URL.
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
    items = []
    for i in range(60):  # > 48 → at least 2 pages
        items.append({
            "slug": f"t{i}", "title": f"Title {i}", "kind": "Фильм", "year": 2020,
            "poster": f"https://p/{i}.webp", "url": f"/title/t{i}/",
            "published_at": f"2026-01-{(i % 28) + 1:02d}T00:00:00Z",
        })
    cat = {"version": 2, "count": len(items), "items": items, "fields_absent": [],
           "site": "page-fix", "schema": "nova-catalog/2.0.0",
           "revision": "t", "builtAt": "2026-09-20T00:00:00Z"}
    (корень / "page-fix-catalog.json").write_text(json.dumps(cat), encoding="utf-8")
    (корень / "page-fix-details.json").write_text(json.dumps({
        "schema": "nova-details/1.0.0", "site": "page-fix", "details_total": 0,
        "source": "test", "items_total": len(items), "details": {},
    }), encoding="utf-8")
    man = корень / "manifest.json"
    man.write_text(json.dumps({
        "schema_version": 1, "template_family": "lords",
        "design_version": "1.1.0", "source_commit": "0" * 40,
        "build_id": "TEST-PAGE", "artifact_sha256": "0" * 64,
        "profile": "lords-general", "built_at": "2026-09-20T00:00:00Z",
    }), encoding="utf-8")
    monkeypatch.setenv("LORDS_TEMPLATE_MANIFEST", str(man))
    monkeypatch.setenv("LORDS_CATALOG", str(корень / "page-fix-catalog.json"))
    monkeypatch.setenv("LORDS_SITE_NAME", "Page Fix")
    monkeypatch.delenv("LORDS_DETAILS", raising=False)
    monkeypatch.delenv("LORDS_PLAYER_CONFIG", raising=False)
    имя = "nova_page_404_contract"
    спец = importlib.util.spec_from_file_location(имя, ИСХОДНИК)
    мод = importlib.util.module_from_spec(спец)
    sys.modules[имя] = мод
    спец.loader.exec_module(мод)
    мод.Обработчик.данные = мод.Данные(str(корень / "page-fix-catalog.json"))
    мод.Обработчик.подробности = мод.Подробности(str(корень / "page-fix-details.json"))
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


class TestInvalidPagination404:
    def test_huge_page_is_http_404(self, fe):
        status, body = _req(fe, "/catalog/?page=999999")
        assert status == 404
        assert 'class="c"' not in body or "Не найдено" in body or "не найден" in body.lower()

    def test_page_zero_is_404(self, fe):
        status, _ = _req(fe, "/catalog/?page=0")
        assert status == 404

    def test_negative_page_is_404(self, fe):
        status, _ = _req(fe, "/catalog/?page=-3")
        assert status == 404

    def test_nonnumeric_page_is_404(self, fe):
        status, _ = _req(fe, "/catalog/?page=abc")
        assert status == 404

    def test_valid_last_page_is_200(self, fe):
        # 60 items / 48 → 2 pages
        status, body = _req(fe, "/catalog/?page=2")
        assert status == 200
        assert re.search(r'<a class="c"', body)
