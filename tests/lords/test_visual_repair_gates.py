"""Visual-repair gates for Lords three-profile card registry.

Fixture-level checks: green brand, no tech footer, no anime copy, no 118px
margin, honest section labels, and distinct card-type CSS per design.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import re
import sys

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ИСХОДНИК = КОРЕНЬ / "automation" / "host" / "lords-frontend.py"


def _boot(tmp_path, profile: str, monkeypatch):
    корень = tmp_path / profile
    корень.mkdir(parents=True, exist_ok=True)
    items = []
    for i in range(36):
        kind = ["Фильм", "Сериал", "Мультфильм"][i % 3]
        items.append({
            "slug": f"{profile}-{i}",
            "title": f"Title {i} very long name for clamp",
            "kind": kind,
            "year": 2011 + (i % 14),
            "poster": f"https://p/{i}.webp",
            "url": f"/title/{profile}-{i}/",
            "published_at": f"2026-09-{(i % 28) + 1:02d}T00:00:00Z",
            "_rating": 7.0 + (i % 20) / 10.0,
        })
    (корень / "cat.json").write_text(json.dumps({
        "version": 2, "count": len(items), "items": items, "fields_absent": [],
        "site": profile, "schema": "nova-catalog/2.0.0",
        "revision": "t", "builtAt": "2026-09-20T00:00:00Z",
        "years": [2011, 2015, 2020, 2024, 2025, 2026],
    }), encoding="utf-8")
    (корень / "det.json").write_text(json.dumps({
        "schema": "nova-details/1.0.0", "site": profile,
        "details_total": 0, "source": "test", "items_total": len(items),
        "details": {
            f"{profile}-1": {
                "seasons": [{"n": 2, "eps": 12}],
                "kinopoisk_rating": 7.5,
            }
        },
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
    имя = f"nova_vr_{profile.replace('-', '_')}"
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


@pytest.mark.parametrize("profile,design,card", [
    ("lords-general", "lords-cinema-v2", "poster"),
    ("lords-new", "lords-series-feed-v2", "episode"),
    ("lords-curated", "lords-curated-v2", "editorial"),
])
def test_visual_repair_home_gates(tmp_path, monkeypatch, profile, design, card):
    html = _home(_boot(tmp_path, profile, monkeypatch))
    assert f'data-design="{design}"' in html
    assert "margin-top:118px" not in html
    assert "Lords ·" not in html or "Lords · 1." not in html
    assert not re.search(r"Lords · \d+\.\d+\.\d+ · [0-9a-f]{7,}", html)
    assert "каталог аниме" not in html.casefold()
    assert "закрытого снимка" not in html
    assert "оценки приходят из источника" not in html
    assert "#3F7D26" in html or "#3f7d26" in html
    assert "#a34b2c" not in html.casefold()
    assert "#2f6fed" not in html.casefold()
    assert "#6b3d6e" not in html.casefold()
    assert f"c--{card}" in html
    assert f'data-card-type="{card}"' in html
    assert "aspect-ratio:16/10" not in html
    if card == "editorial":
        assert ".c--editorial .c__p{aspect-ratio:2/3}" in html or "c--editorial" in html
        assert "Выбор редакции" not in html
        assert "Страны и эпохи" not in html or "Жанры" in html
    if card == "episode":
        assert "grid--episode" in html
        assert "Продолжающиеся сериалы" not in html
    if card == "poster":
        assert "grid--poster" in html
        assert "Недавно добавлено" in html or "Популярное" in html


def test_three_profiles_structurally_distinct(tmp_path, monkeypatch):
    homes = {
        p: _home(_boot(tmp_path / "d", p, monkeypatch))
        for p in ("lords-general", "lords-new", "lords-curated")
    }
    types = {p: re.search(r'data-card-type="([^"]+)"', h).group(1) for p, h in homes.items()}
    assert types["lords-general"] == "poster"
    assert types["lords-new"] == "episode"
    assert types["lords-curated"] == "editorial"
    navs = {p: re.findall(r'<nav id="hd-nav"[^>]*>(.*?)</nav>', h, re.S)[0] for p, h in homes.items()}
    assert navs["lords-general"] != navs["lords-new"]
    assert navs["lords-general"] != navs["lords-curated"]
    assert navs["lords-new"] != navs["lords-curated"]
