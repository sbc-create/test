"""REQ-CONTRACT-MOCK: шаблон собирается и проверяется без живой CMS.

Без такого источника «независимая сборка шаблона» остаётся словами: лента
упирается в чужой стенд, и падение витрины неотличимо от падения источника.

Маршрутизация проверяется чистой функцией, а не поднятым портом: тест на
настоящем сокете падает от занятого порта и таймаутов, то есть мигает.
"""

from __future__ import annotations

import json

from factory.contracts.fixtures import STATES, VIEW_MODELS
from factory.contracts.mock_server import resolve


def test_health_reports_fixture_count() -> None:
    status, body = resolve("/health")
    assert status == 200
    assert body["fixtures"] > 0


def test_index_lists_names_states_and_edges() -> None:
    status, body = resolve("/viewmodels")
    assert status == 200
    assert set(body["view_models"]) == set(VIEW_MODELS)
    assert set(body["states"]) == set(STATES)
    assert body["edges"]


def test_view_model_defaults_to_normal() -> None:
    assert resolve("/viewmodel/title_card")[1]["state"] == "normal"


def test_every_view_model_and_state_is_reachable() -> None:
    for name in VIEW_MODELS:
        for state in STATES:
            status, body = resolve(f"/viewmodel/{name}/{state}")
            assert status == 200, (name, state)
            assert body["state"] == state


def test_edge_route_is_reachable() -> None:
    status, body = resolve("/viewmodel/listing/edge/long_text")
    assert status == 200
    assert body["edge"] == "long_text"


def test_unknown_name_is_404_not_empty_body() -> None:
    """Молчаливая пустота выглядит как «данных нет» и уводит расследование."""
    status, body = resolve("/viewmodel/нет-такой")
    assert status == 404
    assert body["error"]


def test_unknown_state_and_path_are_404() -> None:
    assert resolve("/viewmodel/title_card/нет-такого")[0] == 404
    assert resolve("/совсем/другое")[0] == 404


def test_query_string_is_ignored() -> None:
    assert resolve("/viewmodel/title_card?cachebust=1")[0] == 200


def test_bulk_route_is_serialisable() -> None:
    status, body = resolve("/fixtures")
    assert status == 200
    json.dumps(body, ensure_ascii=False)
