"""Three profiles must emit three design ids and distinct home IA.

Palette-only forks fail: require different data-design and different first
three semantic home block headings.
"""

from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import re
import sys
from urllib.parse import parse_qs

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ИСХОДНИК = КОРЕНЬ / "automation" / "host" / "lords-frontend.py"


def _boot(tmp_path, profile: str, monkeypatch):
    корень = tmp_path / profile
    корень.mkdir(parents=True, exist_ok=True)
    items = []
    for i in range(24):
        kind = ["Фильм", "Сериал", "Мультфильм"][i % 3]
        items.append({
            "slug": f"{profile}-{i}", "title": f"T{i}", "kind": kind, "year": 2020 + (i % 5),
            "poster": f"https://p/{i}.webp", "url": f"/title/{profile}-{i}/",
            "published_at": f"2026-01-{(i % 28) + 1:02d}T00:00:00Z",
        })
    (корень / "cat.json").write_text(json.dumps({
        "version": 2, "count": len(items), "items": items, "fields_absent": [],
        "site": profile, "schema": "nova-catalog/2.0.0",
        "revision": "t", "builtAt": "2026-09-20T00:00:00Z",
    }), encoding="utf-8")
    (корень / "det.json").write_text(json.dumps({
        "schema": "nova-details/1.0.0", "site": profile,
        "details_total": 0, "source": "test", "items_total": len(items),
        "details": {},
    }), encoding="utf-8")
    man = корень / "manifest.json"
    man.write_text(json.dumps({
        "schema_version": 1, "template_family": "lords",
        "design_version": "1.1.0", "source_commit": "0" * 40,
        "build_id": f"TEST-{profile}", "artifact_sha256": "0" * 64,
        "profile": profile, "built_at": "2026-09-20T00:00:00Z",
    }), encoding="utf-8")
    monkeypatch.setenv("LORDS_TEMPLATE_MANIFEST", str(man))
    monkeypatch.setenv("LORDS_CATALOG", str(корень / "cat.json"))
    monkeypatch.setenv("LORDS_SITE_NAME", profile)
    monkeypatch.delenv("LORDS_DETAILS", raising=False)
    monkeypatch.delenv("LORDS_PLAYER_CONFIG", raising=False)
    имя = f"nova_design_{profile.replace('-', '_')}"
    # Drop prior module so profile globals reload.
    sys.modules.pop(имя, None)
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


def _design(html: str) -> str:
    m = re.search(r'data-design="([^"]+)"', html)
    assert m, "data-design missing"
    return m.group(1)


def _first_h2(html: str, n: int = 3) -> list[str]:
    return re.findall(r"<h2[^>]*>(.*?)</h2>", html, re.S)[:n]


EXPECTED = {
    "lords-general": "lords-cinema-v2",
    "lords-new": "lords-series-feed-v2",
    "lords-curated": "lords-curated-v2",
}


@pytest.mark.parametrize("profile,design", list(EXPECTED.items()))
def test_profile_emits_target_design_id(tmp_path, monkeypatch, profile, design):
    мод = _boot(tmp_path, profile, monkeypatch)
    html = _home(мод)
    assert _design(html) == design


def test_three_designs_and_distinct_home_ia(tmp_path, monkeypatch):
    homes = {}
    for profile in EXPECTED:
        # Separate subdirs so manifests do not clash.
        homes[profile] = _home(_boot(tmp_path / "ia", profile, monkeypatch))
    designs = {_design(h) for h in homes.values()}
    assert designs == set(EXPECTED.values())
    headings = {p: _first_h2(h) for p, h in homes.items()}
    # First three semantic blocks must not be identical across all three.
    assert headings["lords-general"] != headings["lords-new"]
    assert headings["lords-general"] != headings["lords-curated"]
    assert headings["lords-new"] != headings["lords-curated"]
