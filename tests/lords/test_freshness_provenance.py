"""Freshness contract: /new/ and recently_added share published_at provenance.

P0/P1: recently_added claimed the full catalog; copy said «аниме» on Lords;
/new/ showed release year without catalog_added_at/<time>.
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
ФРОНТ = КОРЕНЬ / "automation" / "host" / "lords-frontend.py"
КОНТРАКТ = КОРЕНЬ / "automation" / "host" / "collection_contract.py"


def _items(n=300):
    out = []
    for i in range(n):
        out.append({
            "slug": f"t{i}", "title": f"Title {i}", "kind": "Фильм",
            "year": 2011 if i % 5 == 0 else 2024,
            "poster": f"https://p/{i}.webp", "url": f"/title/t{i}/",
            "published_at": f"2026-01-{(i % 28) + 1:02d}T12:00:00Z",
        })
    # One without published_at must not drive «new»
    out.append({
        "slug": "no-date", "title": "No Date", "kind": "Фильм", "year": 2020,
        "poster": "https://p/x.webp", "url": "/title/no-date/",
        "published_at": "",
    })
    return out


@pytest.fixture
def fe(tmp_path, monkeypatch):
    корень = tmp_path / "site"
    корень.mkdir()
    items = _items(300)
    cat = {
        "version": 2, "count": len(items), "items": items, "fields_absent": [],
        "site": "fresh-fix", "schema": "nova-catalog/2.0.0",
        "revision": "rev-fresh", "builtAt": "2026-09-20T00:00:00Z",
    }
    (корень / "cat.json").write_text(json.dumps(cat), encoding="utf-8")
    (корень / "det.json").write_text(json.dumps({
        "schema": "nova-details/1.0.0", "site": "fresh-fix",
        "details_total": 0, "source": "test", "items_total": len(items),
        "details": {},
    }), encoding="utf-8")
    man = корень / "manifest.json"
    man.write_text(json.dumps({
        "schema_version": 1, "template_family": "lords",
        "design_version": "1.1.0", "source_commit": "0" * 40,
        "build_id": "TEST-FRESH", "artifact_sha256": "0" * 64,
        "profile": "lords-general", "built_at": "2026-09-20T00:00:00Z",
    }), encoding="utf-8")
    monkeypatch.setenv("LORDS_TEMPLATE_MANIFEST", str(man))
    monkeypatch.setenv("LORDS_CATALOG", str(корень / "cat.json"))
    monkeypatch.setenv("LORDS_SITE_NAME", "Fresh Fix")
    monkeypatch.delenv("LORDS_DETAILS", raising=False)
    monkeypatch.delenv("LORDS_PLAYER_CONFIG", raising=False)

    # Reload both modules with a unique name so contract patches apply.
    for path, имя in ((КОНТРАКТ, "cc_fresh"), (ФРОНТ, "nova_fresh_contract")):
        спец = importlib.util.spec_from_file_location(имя, path)
        мод = importlib.util.module_from_spec(спец)
        sys.modules[имя] = мод
        спец.loader.exec_module(мод)

    фронт = sys.modules["nova_fresh_contract"]
    # Wire collection contract into frontend if present
    if hasattr(фронт, "КОЛЛЕКЦИИ") and фронт.КОЛЛЕКЦИИ is None:
        pass
    фронт.Обработчик.данные = фронт.Данные(str(корень / "cat.json"))
    фронт.Обработчик.подробности = фронт.Подробности(str(корень / "det.json"))
    фронт.Обработчик.индекс = фронт.построить_индекс(
        фронт.Обработчик.данные, фронт.Обработчик.подробности)
    return фронт, sys.modules["cc_fresh"]


def _req(фронт, path: str):
    gathered = {"status": 200, "body": b""}

    class Stub(фронт.Обработчик):
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


class TestFreshnessContract:
    def test_recently_added_capped_not_full_catalog(self, fe):
        фронт, cc = fe
        д = фронт.Обработчик.данные
        п = фронт.Обработчик.подробности
        снимок = cc.Снимок(д.items, п.записи, revision=getattr(д, "revision", "") or "")
        данные = cc.разрешить("recently_added", снимок, "lords")
        assert данные is not None
        assert данные.total <= 240
        assert данные.total < len(д.items)
        assert all(к.raw.get("published_at") for к in данные.items)

    def test_lords_recently_added_copy_not_anime(self, fe):
        _, cc = fe
        спец = cc.спецификация("lords", "recently_added")
        assert спец is not None
        assert "аниме" not in спец.description.lower()

    def test_new_page_shows_time_and_as_of(self, fe):
        фронт, _ = fe
        status, body = _req(фронт, "/new/")
        assert status == 200
        assert "<time" in body and "datetime=" in body
        assert "as_of" in body or "по состоянию" in body.lower() or "добавлен" in body.lower()
        assert "аниме" not in body.lower()
