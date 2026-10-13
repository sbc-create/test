"""Общий счётчик собранного на главной (идея варианта B) поверх чек-листов глав варианта C."""

import html as h
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from saga.server import App  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return App()


def test_every_chapter_with_berries_has_berry_item(app):
    for gid in app.site.games:
        for row, g in zip(app.site.tally(gid), app.site.for_game(gid), strict=True):
            assert row["slug"] == g.slug and row["total"] == len(g.checklist)
            if g.red:  # иначе клубники главы нельзя было бы засчитать
                assert row["berry"] is not None and "клубник" in g.checklist[row["berry"] - 1].lower()
            for i in row["sides"]:
                assert "сторона" in g.checklist[i - 1].lower()


def test_home_tally_matches_source_totals(app):
    _, page, _ = app.route("/", {})
    raw = re.search(r'data-tally="([^"]+)"', page).group(1)
    rows = json.loads(h.unescape(raw))
    gid = next(iter(app.site.games))
    assert rows == app.site.tally(gid)
    assert f"/ {app.site.red_total(gid)}</dd>" in page
    assert f"/ {sum(len(r['sides']) for r in rows)}</dd>" in page and f"/ {len(rows)}</dd>" in page
