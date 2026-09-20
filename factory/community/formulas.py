"""Animedia native average and Yummy Bayesian public brand score."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

ANIMEDIA_FORMULA = "animedia_native_average_v1"
YUMMY_FORMULA = "yummy_bayes_prior_v1"

# Config defaults mirrored from rating_policy_v1 (not magic-scattered)
DEFAULT_YUMMY_WEIGHTS = {"animedia_native": Decimal("0.70"), "shikimori": Decimal("0.30")}
DEFAULT_PRIOR_STRENGTH_M = 10


def _d(value: Decimal | float | int | str | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def round_display(value: Decimal, places: str = "0.01") -> Decimal:
    return value.quantize(Decimal(places), rounding=ROUND_HALF_UP)


def format_delta(delta: Decimal, *, step: Decimal = Decimal("0.01")) -> str:
    if abs(delta) < step:
        return "изменение менее 0,01"
    sign = "+" if delta > 0 else ""
    return f"{sign}{round_display(delta, '0.001')}"


@dataclass(frozen=True)
class NativeAggregate:
    vote_sum: int  # S
    vote_count: int  # N
    formula: str = ANIMEDIA_FORMULA

    @property
    def average(self) -> Decimal | None:
        if self.vote_count <= 0:
            return None
        return Decimal(self.vote_sum) / Decimal(self.vote_count)

    def after_create(self, score: int) -> NativeAggregate:
        return NativeAggregate(self.vote_sum + score, self.vote_count + 1, self.formula)

    def after_update(self, old: int, new: int) -> NativeAggregate:
        return NativeAggregate(self.vote_sum - old + new, self.vote_count, self.formula)

    def after_delete(self, old: int) -> NativeAggregate:
        n = self.vote_count - 1
        if n <= 0:
            return NativeAggregate(0, 0, self.formula)
        return NativeAggregate(self.vote_sum - old, n, self.formula)

    def assert_invariants(self) -> None:
        n, s = self.vote_count, self.vote_sum
        if n < 0 or s < 0:
            raise ValueError("negative aggregate")
        if n == 0:
            if s != 0:
                raise ValueError("empty aggregate must have S=0")
            return
        if not (n <= s <= 10 * n):
            raise ValueError(f"invariant N<=S<=10N failed: N={n} S={s}")


def build_yummy_prior(
    *,
    animedia_native: Decimal | None,
    shikimori: Decimal | None,
    weights: dict[str, Decimal] | None = None,
    animedia_embeds_shikimori: bool = False,
) -> tuple[Decimal | None, dict[str, Any]]:
    """Build P_Y with renormalization; never substitute missing with 0.

    Double-count guard: if Animedia native already embeds Shikimori, use
    Animedia-only prior (drop Shikimori component).
    """
    w = dict(weights or DEFAULT_YUMMY_WEIGHTS)
    provenance: dict[str, Any] = {
        "animedia_embeds_shikimori": animedia_embeds_shikimori,
        "components_used": [],
        "double_counted_source_count": 0,
    }
    if animedia_embeds_shikimori and animedia_native is not None:
        provenance["components_used"] = ["animedia_native"]
        provenance["shikimori_excluded_reason"] = "animedia_already_embeds_shikimori"
        return animedia_native, provenance

    parts: list[tuple[str, Decimal, Decimal]] = []
    if animedia_native is not None:
        parts.append(("animedia_native", animedia_native, w.get("animedia_native", Decimal("0"))))
    if shikimori is not None:
        parts.append(("shikimori", shikimori, w.get("shikimori", Decimal("0"))))
    if not parts:
        provenance["components_used"] = []
        return None, provenance
    weight_sum = sum(p[2] for p in parts)
    if weight_sum <= 0:
        return None, provenance
    total = sum(score * (wt / weight_sum) for _, score, wt in parts)
    provenance["components_used"] = [p[0] for p in parts]
    provenance["renormalized_weights"] = {p[0]: str(p[2] / weight_sum) for p in parts}
    return total, provenance


@dataclass(frozen=True)
class YummyPublic:
    vote_sum: int
    vote_count: int
    prior: Decimal | None
    m: int = DEFAULT_PRIOR_STRENGTH_M
    formula: str = YUMMY_FORMULA

    @property
    def raw_average(self) -> Decimal | None:
        if self.vote_count <= 0:
            return None
        return Decimal(self.vote_sum) / Decimal(self.vote_count)

    @property
    def public_score(self) -> Decimal | None:
        """Y = (S + m*P) / (N + m); if no prior and N=0 → absent."""
        if self.prior is None:
            return self.raw_average
        n, s, m = self.vote_count, self.vote_sum, self.m
        return (Decimal(s) + Decimal(m) * self.prior) / (Decimal(n) + Decimal(m))

    def displayed_vote_count(self) -> int:
        """m never added to displayed user vote count."""
        return self.vote_count

    def after_create(self, score: int) -> YummyPublic:
        return YummyPublic(self.vote_sum + score, self.vote_count + 1, self.prior, self.m)

    def after_update(self, old: int, new: int) -> YummyPublic:
        return YummyPublic(self.vote_sum - old + new, self.vote_count, self.prior, self.m)

    def after_delete(self, old: int) -> YummyPublic:
        n = self.vote_count - 1
        if n < 0:
            raise ValueError("cannot delete below zero")
        if n == 0:
            return YummyPublic(0, 0, self.prior, self.m)
        return YummyPublic(self.vote_sum - old, n, self.prior, self.m)


def compare_yummy_grid() -> list[dict[str, Any]]:
    """Comparative table for owner policy approval (weights × m × N × vote)."""
    rows: list[dict[str, Any]] = []
    weight_sets = (
        {"animedia_native": Decimal("0.5"), "shikimori": Decimal("0.5")},
        {"animedia_native": Decimal("0.7"), "shikimori": Decimal("0.3")},
        {"animedia_native": Decimal("0.8"), "shikimori": Decimal("0.2")},
    )
    for weights in weight_sets:
        prior, prov = build_yummy_prior(
            animedia_native=Decimal("8.4"),
            shikimori=Decimal("7.9"),
            weights=weights,
        )
        for m in (5, 10, 25, 50):
            for n in (0, 1, 5, 10, 100, 1000):
                # synthetic equal votes of 8
                s = 8 * n
                pub = YummyPublic(s, n, prior, m=m)
                for vote in (1, 5, 9, 10):
                    nxt = pub.after_create(vote) if n == 0 and False else None
                    # show baseline public + one-step create from empty-ish
                    base = pub.public_score
                    after = YummyPublic(s + vote, n + 1, prior, m=m).public_score
                    rows.append(
                        {
                            "weights": {k: str(v) for k, v in weights.items()},
                            "m": m,
                            "N": n,
                            "vote": vote,
                            "P_Y": None if prior is None else str(round_display(prior, "0.001")),
                            "Y_before": None if base is None else str(round_display(base, "0.001")),
                            "Y_after_vote": None if after is None else str(round_display(after, "0.001")),
                            "components": prov.get("components_used"),
                        }
                    )
    return rows
