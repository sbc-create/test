"""REQ-INPUT-REQUEST: один пакет вместо череды вопросов."""
import json

from factory.input_request import collect, generate
from factory.paths import PATHS


def test_collect_returns_structured_items():
    items = collect()
    assert items
    for item in items:
        assert set(item) == {"field", "why", "format", "example_without_secret", "where_to_put", "blocks_stage"}
        assert item["why"] and item["blocks_stage"]


def test_known_gaps_are_reported():
    fields = {item["field"] for item in collect()}
    for expected in ("dle_license", "dle_distribution", "dle_paths_profile", "ssh_host",
                     "vk_catalog", "vk_player_contract", "vk_ads_contract"):
        assert expected in fields, f"в запросе нет: {expected}"


def test_no_secret_values_in_examples():
    for item in collect():
        example = item["example_without_secret"].lower()
        assert "begin private key" not in example
        for marker in ("password:", "token: ey", "secret: "):
            assert marker not in example


def test_generate_writes_both_artifacts():
    md_path, json_path, items = generate()
    assert md_path.exists() and json_path.exists()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["count"] == len(items)
    text = md_path.read_text(encoding="utf-8")
    assert "| Поле |" in text
    assert all(item["field"] in text for item in items)
