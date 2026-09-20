"""Provenance DAG helpers for Yummy formula components (Stage04)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from factory.community.formulas import (
    DEFAULT_PRIOR_STRENGTH_M,
    DEFAULT_YUMMY_WEIGHTS,
    NativeAggregate,
    YummyPublic,
    build_yummy_prior,
)


LAYER_ORDER = (
    "raw_source",
    "observation",
    "projection",
    "aggregate",
    "display_score",
    "structured_data",
)


def animedia_native_dag(*, vote_sum: int, vote_count: int) -> dict[str, Any]:
    agg = NativeAggregate(vote_sum, vote_count)
    return {
        "component": "animedia_native",
        "contains_shikimori": False,
        "layers": {
            "raw_source": "community_votes(rating_space=animedia)",
            "observation": None,
            "projection": "community_display_projection native_user_average/animedia_native",
            "aggregate": {"S": agg.vote_sum, "N": agg.vote_count, "A": None if agg.average is None else str(agg.average)},
            "display_score": "UI rounding only; absent when N=0",
            "structured_data": "not_emitted_from_canary",
        },
    }


def shikimori_dag(*, score: Decimal | None, observation_id: str | None) -> dict[str, Any]:
    return {
        "component": "shikimori",
        "contains_shikimori": True,
        "layers": {
            "raw_source": "shikimori GraphQL score",
            "observation": observation_id,
            "projection": "community_display_projection external_badge/shikimori",
            "aggregate": None,
            "display_score": "external badge only when source-policy allows",
            "structured_data": "never_as_Animedia_or_Yummy_native",
        },
        "score": None if score is None else str(score),
    }


def yummy_prior_dag(
    *,
    animedia_native: Decimal | None,
    shikimori: Decimal | None,
) -> dict[str, Any]:
    prior, prov = build_yummy_prior(
        animedia_native=animedia_native,
        shikimori=shikimori,
        animedia_embeds_shikimori=False,
        animedia_projected=None,
    )
    return {
        "component": "yummy_prior",
        "YUMMY_PRIOR_WEIGHT_ANIMEDIA_NATIVE": str(DEFAULT_YUMMY_WEIGHTS["animedia_native"]),
        "YUMMY_PRIOR_WEIGHT_SHIKIMORI": str(DEFAULT_YUMMY_WEIGHTS["shikimori"]),
        "YUMMY_PRIOR_STRENGTH": DEFAULT_PRIOR_STRENGTH_M,
        "P": None if prior is None else str(prior),
        "provenance": prov,
        "SOURCE_LINEAGE_DOUBLE_COUNT_COUNT": prov.get("double_counted_source_count", 0),
        "SHIKIMORI_INDIRECT_DOUBLE_COUNT_COUNT": prov.get(
            "shikimori_indirect_double_count_count", 0
        ),
        "PRIOR_COMPONENTS_INDEPENDENT": int(bool(prov.get("prior_components_independent"))),
        "forbidden_as_input": ["animedia_projected", "amd_online", "animedia_blend"],
        "layers": {
            "raw_source": "animedia_native ledger XOR/AND shikimori observation",
            "observation": "shikimori observation id when present",
            "projection": "yummy_derived public_brand_score (shadow when open-site blocked)",
            "aggregate": "YummyPublic prior only; m not in vote_count",
            "display_score": "preliminary label iff prior public-allowed; else native-absent",
            "structured_data": "STRUCTURED_AGGREGATE_RATING_EMITTED=0",
        },
    }


def yummy_public_dag(
    *,
    vote_sum: int,
    vote_count: int,
    prior: Decimal | None,
) -> dict[str, Any]:
    pub = YummyPublic(vote_sum, vote_count, prior, m=DEFAULT_PRIOR_STRENGTH_M)
    return {
        "component": "yummy_public",
        "N": pub.vote_count,
        "S": pub.vote_sum,
        "displayed_vote_count": pub.displayed_vote_count(),
        "prior_strength_m": DEFAULT_PRIOR_STRENGTH_M,
        "prior_strength_exposed_as_votes": False,
        "Y": None if pub.public_score is None else str(pub.public_score),
        "layers": LAYER_ORDER,
    }


def prove_no_double_count() -> dict[str, Any]:
    """Static proof used by tests + evidence."""
    # Case: both components present, native does not embed shiki
    p, prov = build_yummy_prior(
        animedia_native=Decimal("8.0"),
        shikimori=Decimal("7.0"),
        animedia_embeds_shikimori=False,
    )
    expected = Decimal("0.70") * Decimal("8.0") + Decimal("0.30") * Decimal("7.0")
    # Case: N_A=0 → shiki-only renormalize
    p2, prov2 = build_yummy_prior(
        animedia_native=None,
        shikimori=Decimal("7.0"),
        animedia_embeds_shikimori=False,
    )
    # Case: projected forbidden
    projected_rejected = False
    try:
        build_yummy_prior(
            animedia_native=None,
            shikimori=Decimal("7.0"),
            animedia_projected=Decimal("8.5"),
        )
    except ValueError:
        projected_rejected = True
    return {
        "both_components_P": str(p),
        "both_components_expected": str(expected),
        "both_match": p == expected,
        "shiki_only_P": str(p2),
        "animedia_projected_rejected": projected_rejected,
        "SOURCE_LINEAGE_DOUBLE_COUNT_COUNT": prov["double_counted_source_count"],
        "SHIKIMORI_INDIRECT_DOUBLE_COUNT_COUNT": prov["shikimori_indirect_double_count_count"],
        "PRIOR_COMPONENTS_INDEPENDENT": int(prov["prior_components_independent"]),
        "YUMMY_PRIOR_WEIGHT_ANIMEDIA_NATIVE": prov["YUMMY_PRIOR_WEIGHT_ANIMEDIA_NATIVE"],
        "YUMMY_PRIOR_WEIGHT_SHIKIMORI": prov["YUMMY_PRIOR_WEIGHT_SHIKIMORI"],
        "dag_animedia": animedia_native_dag(vote_sum=0, vote_count=0),
        "dag_prior": yummy_prior_dag(animedia_native=Decimal("8.0"), shikimori=Decimal("7.0")),
        "components_used_both": prov["components_used"],
        "components_used_shiki_only": prov2["components_used"],
    }
