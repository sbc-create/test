"""Ссылки меню на рецепты food-daily ведут сразу на актуальный адрес основного варианта (без промежуточного 301)."""

import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from weekplan.server import App  # noqa: E402

OLD, NEW = "kurica-v-slivochnom-souse", "kurica-v-smetanno-chesnochnom-souse"


@pytest.fixture(scope="module")
def app():
    return App()


def test_catalog_uses_current_food_daily_addresses():
    net = yaml.safe_load((ROOT / "config" / "network.yaml").read_text())["sites"]["food-daily"]
    assert net["origin"]["preview"] == "http://127.0.0.1:8876"  # основной вариант C
    items = json.loads((ROOT / "data" / "catalog" / "food-daily.json").read_text())["items"]
    paths = {i["path"] for i in items}
    assert f"/recept/{NEW}/" in paths and f"/recept/{OLD}/" not in paths


def test_plans_reference_only_catalog_slugs():
    slugs = {i["slug"] for i in json.loads((ROOT / "data" / "catalog" / "food-daily.json").read_text())["items"]}
    for f in (ROOT / "data" / "plans").glob("*.json"):
        text = f.read_text()
        assert OLD not in text, f.name
        used = set(__import__("re").findall(r'"slug": "([a-z0-9-]+)"', text)) - {json.loads(text)["slug"]}
        assert used <= slugs, (f.name, used - slugs)


def test_menu_links_chicken_directly(app):
    for slug in ("bystraya-nedelya-dlya-dvoih", "semejnaya-nedelya-na-chetveryh"):
        _, html, _ = app.route(f"/menyu/{slug}/", {})
        assert f'href="http://127.0.0.1:8876/recept/{NEW}/"' in html
        assert OLD not in html
