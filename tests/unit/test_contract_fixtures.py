"""REQ-CONTRACT-FIXTURES: все шаблоны проверяются на одних и тех же данных.

Шаблон — слой представления, и проверять его надо на фиксированных данных, а не
на живой CMS: иначе падение витрины неотличимо от падения источника, а два
шаблона, проверенные на разных данных, оба «зелёные» без всякого смысла.

Здесь закрепляются три свойства набора и одно смысловое различие, которое чаще
всего теряют: degraded — это не error.
"""

from __future__ import annotations

import json

import pytest

from factory.contracts.fixtures import (
    EDGES,
    LONG_TEXT,
    STATES,
    VIEW_MODELS,
    all_fixtures,
    edge_fixture,
    fixture,
)


def test_every_view_model_has_every_state() -> None:
    """Шаблон, умеющий только normal, ломается ровно тогда, когда данных нет."""
    for view_model in VIEW_MODELS:
        for state in STATES:
            data = fixture(view_model, state)
            assert data["state"] == state, (view_model, state)


def test_fixtures_are_deterministic() -> None:
    """Иначе снимок вёрстки меняется сам по себе и проверки отключают как мигающие."""
    assert fixture("title_card") == fixture("title_card")
    assert all_fixtures() == all_fixtures()


def test_consumer_cannot_poison_the_next_call() -> None:
    """Возвращается копия: правка у потребителя не должна протекать дальше."""
    first = fixture("listing")
    first["items"].clear()
    first["heading"] = "испорчено"
    assert fixture("listing")["items"], "мутация утекла в следующий вызов"
    assert fixture("listing")["heading"] != "испорчено"


def test_every_fixture_is_json_serialisable() -> None:
    """Mock-сервер отдаёт это по сети, значит оно обязано сериализоваться."""
    json.dumps(all_fixtures(), ensure_ascii=False)


def test_degraded_keeps_data_and_error_does_not() -> None:
    """Смешение этих состояний и даёт пустую витрину там, где можно было
    отдать вчерашний снимок."""
    degraded = fixture("listing", "degraded")
    assert degraded["items"], "degraded обязан сохранить данные"
    assert degraded["stale_since"], "устаревание обязано быть помечено честно"

    error = fixture("listing", "error")
    assert "items" not in error, "error не показывает данных"
    assert error["message"]


def test_empty_is_not_error() -> None:
    """Пусто — это законный ответ, а не сбой."""
    empty = fixture("listing", "empty")
    assert empty["items"] == []
    assert "message" not in empty


def test_rating_always_carries_provenance() -> None:
    """Голое число запрещено: 7.5 по трём голосам и по тридцати тысячам — разное."""
    rating = fixture("rating")
    for field in ("source", "fetched_at", "vote_count", "confidence", "scale_max"):
        assert rating[field] is not None, f"у оценки нет {field}"


def test_event_time_is_not_render_time() -> None:
    """Карточка обязана нести время события, а не время отрисовки."""
    assert fixture("title_card")["event_at"]


def test_edge_long_text_reaches_nested_items() -> None:
    """Вёрстка разъезжается на длинном заголовке внутри списка, а не только сверху."""
    data = edge_fixture("listing", "long_text")
    assert data["heading"] == LONG_TEXT
    assert data["items"][0]["name"] == LONG_TEXT


def test_edge_missing_media_is_none_not_absent() -> None:
    """Отсутствие картинки должно быть выражено явно, чтобы шаблон его обработал."""
    data = edge_fixture("title_card", "missing_media")
    assert "poster_url" in data and data["poster_url"] is None


def test_edge_unknown_optional_is_none_never_zero() -> None:
    """Ноль вместо отсутствия — это ложь пользователю про оценку."""
    data = edge_fixture("title_card", "unknown_optional")
    assert data["rating"] is None
    assert data["rating"] != 0


def test_all_fixtures_covers_states_and_edges() -> None:
    keys = all_fixtures()
    expected = len(VIEW_MODELS) * (len(STATES) + len(EDGES))
    assert len(keys) == expected
    assert "player/error" in keys
    assert "title_card/edge:long_text" in keys


def test_unknown_names_raise_rather_than_return_empty() -> None:
    """Молчаливая пустота вместо ошибки прячет опечатку в имени."""
    with pytest.raises(KeyError):
        fixture("нет-такой")
    with pytest.raises(KeyError):
        fixture("title_card", "нет-такого")
    with pytest.raises(KeyError):
        edge_fixture("title_card", "нет-такого")
