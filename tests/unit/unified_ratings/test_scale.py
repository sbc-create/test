"""Нормализация: каждая шкала, обе границы, все отказы."""

from __future__ import annotations

import math
from decimal import Decimal

import pytest

from factory.unified_ratings.scale import (
    FormulaId,
    ScoreState,
    SourceScaleContract,
    normalize,
    validate_community_score,
)
from factory.unified_ratings.sources import (
    ANILIST_SCALE,
    KITSU_SCALE,
    PROVIDER_FEED_SCALE_IMDB,
    SHIKIMORI_SCALE,
    SIMKL_SCALE,
)


def contract(formula: FormulaId, maximum: int, *, verified: bool = True) -> SourceScaleContract:
    return SourceScaleContract(
        source_key="test",
        source_scale_min=Decimal(0),
        source_scale_max=Decimal(maximum),
        formula=formula,
        measures="тестовая шкала",
        raw_field="test",
        verified=verified,
    )


# ---------------------------------------------------------------------------
# каждая шкала
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("formula", "maximum", "raw", "expected"),
    [
        (FormulaId.IDENTITY_0_10, 10, 8.6, "8.6"),
        (FormulaId.IDENTITY_0_10, 10, 10, "10"),
        (FormulaId.DIVIDE_10_FROM_0_100, 100, 86, "8.6"),
        (FormulaId.DIVIDE_10_FROM_0_100, 100, "82.27", "8.227"),
        (FormulaId.MULTIPLY_2_FROM_0_5, 5, 4.25, "8.50"),
        (FormulaId.MULTIPLY_2_FROM_0_5, 5, 5, "10"),
    ],
)
def test_each_scale_normalizes_by_its_own_formula(formula, maximum, raw, expected):
    result = normalize(raw, contract(formula, maximum))
    assert result.state is ScoreState.OK
    assert str(result.normalized) == expected


def test_same_number_normalizes_differently_per_contract():
    """5 по пятибалльной — это 10, а 5 по стобалльной — вне нашей шкалы."""
    five_of_five = normalize(5, contract(FormulaId.MULTIPLY_2_FROM_0_5, 5))
    five_of_hundred = normalize(5, contract(FormulaId.DIVIDE_10_FROM_0_100, 100))
    assert five_of_five.state is ScoreState.OK
    assert str(five_of_five.normalized) == "10"
    assert five_of_hundred.state is ScoreState.OUT_OF_RANGE_LOW


# ---------------------------------------------------------------------------
# границы 1 и 10
# ---------------------------------------------------------------------------


def test_boundary_one_is_accepted():
    result = normalize(10, contract(FormulaId.DIVIDE_10_FROM_0_100, 100))
    assert result.state is ScoreState.OK
    assert result.normalized == Decimal(1)
    assert result.display() == "1.0"


def test_boundary_ten_is_accepted():
    result = normalize(100, contract(FormulaId.DIVIDE_10_FROM_0_100, 100))
    assert result.state is ScoreState.OK
    assert result.normalized == Decimal(10)
    assert result.display() == "10.0"


def test_just_below_one_is_not_clamped_up():
    """0.9 не превращается в 1.0: источник такой оценки не ставил."""
    result = normalize(9, contract(FormulaId.DIVIDE_10_FROM_0_100, 100))
    assert result.state is ScoreState.OUT_OF_RANGE_LOW
    assert result.normalized == Decimal("0.9")
    assert "не публикуется" in result.reason


def test_above_source_scale_is_contract_drift():
    result = normalize(11, contract(FormulaId.IDENTITY_0_10, 10))
    assert result.state is ScoreState.OUT_OF_RANGE_HIGH
    assert result.normalized is None


# ---------------------------------------------------------------------------
# отказы: 0, отрицательные, строки, NaN
# ---------------------------------------------------------------------------


def test_zero_is_not_a_rating():
    result = normalize(0, contract(FormulaId.IDENTITY_0_10, 10))
    assert result.state is ScoreState.ZERO_NOT_A_RATING
    assert result.normalized is None


def test_zero_and_absent_are_different_states():
    zero = normalize(0, contract(FormulaId.IDENTITY_0_10, 10))
    absent = normalize(None, contract(FormulaId.IDENTITY_0_10, 10))
    assert zero.state is not absent.state
    assert absent.state is ScoreState.ABSENT


def test_negative_is_rejected():
    result = normalize(-3, contract(FormulaId.IDENTITY_0_10, 10))
    assert result.state is ScoreState.INVALID_TYPE


@pytest.mark.parametrize("raw", ["отлично", "8/10", "n/a", "--", object()])
def test_non_numeric_strings_are_rejected(raw):
    result = normalize(raw, contract(FormulaId.IDENTITY_0_10, 10))
    assert result.state is ScoreState.INVALID_TYPE


def test_nan_and_inf_are_rejected():
    for raw in (float("nan"), float("inf"), float("-inf")):
        assert normalize(raw, contract(FormulaId.IDENTITY_0_10, 10)).state is ScoreState.INVALID_TYPE


def test_bool_is_not_a_number():
    """True == 1 в Python, но это не оценка 1."""
    assert normalize(True, contract(FormulaId.IDENTITY_0_10, 10)).state is ScoreState.INVALID_TYPE


def test_numeric_string_is_accepted_because_kitsu_sends_one():
    result = normalize("82.27", KITSU_SCALE)
    assert result.state is ScoreState.OK
    assert result.display() == "8.2"


# ---------------------------------------------------------------------------
# непроверенный контракт
# ---------------------------------------------------------------------------


def test_unverified_contract_refuses_to_normalize():
    result = normalize(8, contract(FormulaId.IDENTITY_0_10, 10, verified=False))
    assert result.state is ScoreState.CONTRACT_UNVERIFIED
    assert result.normalized is None


def test_simkl_contract_is_unverified_until_a_live_response():
    assert SIMKL_SCALE.verified is False
    assert normalize(8.4, SIMKL_SCALE).state is ScoreState.CONTRACT_UNVERIFIED


@pytest.mark.parametrize("scale", [ANILIST_SCALE, KITSU_SCALE, SHIKIMORI_SCALE, PROVIDER_FEED_SCALE_IMDB])
def test_shipping_contracts_carry_their_evidence(scale):
    assert scale.verified is True
    assert scale.verified_evidence.strip(), f"{scale.source_key}: подтверждение не указано"


# ---------------------------------------------------------------------------
# отображение
# ---------------------------------------------------------------------------


def test_external_scores_display_with_one_decimal():
    assert normalize("82.27", KITSU_SCALE).display() == "8.2"
    assert normalize(86, ANILIST_SCALE).display() == "8.6"
    assert normalize("8.25", SHIKIMORI_SCALE).display() == "8.3"


def test_scale_label_is_readable():
    assert ANILIST_SCALE.scale_label == "0–100"
    assert SHIKIMORI_SCALE.scale_label == "0–10"


def test_raw_and_normalized_are_both_preserved():
    result = normalize(86, ANILIST_SCALE)
    data = result.as_dict()
    assert data["raw_value"] == "86"
    assert data["source_scale"] == "0–100"
    assert data["formula"] == "divide_10_from_0_100"
    assert data["formula_expression"] == "normalized = raw / 10"
    assert data["normalized"] == "8.6"


# ---------------------------------------------------------------------------
# оценка человека — только целое 1–10
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", [1, 5, 10, "7", 8.0])
def test_community_score_accepts_integers_one_to_ten(value):
    assert 1 <= validate_community_score(value) <= 10


@pytest.mark.parametrize(
    "value", [0, 11, -1, 100, 8.5, "8.5", "", "восемь", None, True, False, math.nan]
)
def test_community_score_rejects_everything_else(value):
    with pytest.raises(ValueError):
        validate_community_score(value)
