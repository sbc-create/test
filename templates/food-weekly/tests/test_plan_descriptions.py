"""Утверждения в описаниях планов совпадают с их составом (проверка контента 13.10.2026)."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from weekplan import planner  # noqa: E402
from weekplan.server import App  # noqa: E402

WORDS = {4: "четыре", 5: "пять", 6: "шесть", 7: "семь"}


@pytest.fixture(scope="module")
def app():
    return App()


def days_of(app, slug):
    return planner.resolve(app.plans[slug], app.catalogs, {})[0]


def test_quick_week(app):
    days = days_of(app, "bystraya-nedelya-dlya-dvoih")
    desc = app.plans["bystraya-nedelya-dlya-dvoih"]["description"]
    assert all((d["item"]["total_minutes"] or 999) <= 60 for day in days for d in day["dinner"])
    soups = sum(any(d["item"]["category"] == "supy" for d in day["lunch"]) for day in days)
    assert f"суп на обед — {WORDS[soups]} дней из семи" in desc or f"суп на обед — {WORDS[soups]} дня из семи" in desc
    weekend = [d["item"]["title"].lower() for day in days[5:] for d in day["breakfast"]]
    assert any("блины" in t for t in weekend) and any("запеканка" in t for t in weekend)


def test_family_week(app):
    days = days_of(app, "semejnaya-nedelya-na-chetveryh")
    desc = app.plans["semejnaya-nedelya-na-chetveryh"]["description"]
    soups = sum(any(d["item"]["category"] == "supy" for d in day["lunch"]) for day in days)
    breakfasts = {d["item"]["slug"] for day in days for d in day["breakfast"]}
    assert f"суп на обед — {WORDS[soups]} дней из семи" in desc
    assert f"{WORDS[len(breakfasts)]} разных завтраков" in desc
