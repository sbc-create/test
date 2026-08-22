"""
Расчёт opportunity score по NEW_RELEASE_PRIORITY_MODEL.yaml.

rights_and_content_readiness — жёсткие ворота: 0 обнуляет весь score,
поэтому «новинка без прав» никогда не всплывает в приоритетах.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from .. import config


@dataclass
class OpportunityInput:
    site_id: str
    subject: str                       # slug тайтла или URL
    demand: dict[str, float] = field(default_factory=dict)
    release_date: date | None = None
    release_confirmed: bool = False
    rights_ref: str | None = None
    source_confidence: str = "unknown"
    media_available: bool = False
    metadata_completeness: float = 0.0
    page_quality: dict[str, bool] = field(default_factory=dict)
    current_position: float | None = None
    target_position: float = 3.0
    business_priority: float = 1.0
    measurement: dict[str, bool] = field(default_factory=dict)
    risk: dict[str, float] = field(default_factory=dict)


@dataclass
class OpportunityScore:
    subject: str
    site_id: str
    score: float
    factors: dict[str, float]
    gates_failed: list[str]
    publishable: bool
    explanation: str


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _demand(inp: OpportunityInput, model: dict) -> float:
    weights = model["factors"]["demand_signal"]["weights"]
    total = sum(weights.values()) or 1.0
    acc = sum(weights.get(k, 0.0) * _clamp(v) for k, v in inp.demand.items())
    return round(acc / total, 4) if inp.demand else 0.0


def _freshness(inp: OpportunityInput, model: dict, today: date) -> float:
    spec = model["factors"]["release_freshness"]
    if inp.release_date is None:
        return 0.35          # нет подтверждённой даты — не выключаем, но и не разгоняем
    delta = (today - inp.release_date).days
    if delta < 0:
        boost_window = spec["boost_window_days_before_release"]
        return _clamp(1.0 if -delta <= boost_window else 0.6)
    half_life = spec["half_life_days"]
    return round(_clamp(math.pow(0.5, delta / half_life)), 4)


def _readiness(inp: OpportunityInput) -> float:
    if not inp.rights_ref:
        return 0.0
    if inp.source_confidence not in ("high", "confirmed"):
        return 0.0
    parts = [1.0, 1.0 if inp.media_available else 0.4, _clamp(inp.metadata_completeness)]
    return round(sum(parts) / len(parts), 4)


def _page_quality(inp: OpportunityInput) -> float:
    checks = ["substantive_content", "distinct_value", "canonical_correct",
              "internal_links_present", "render_ok"]
    if not inp.page_quality:
        return 0.0
    passed = sum(1 for c in checks if inp.page_quality.get(c))
    return round(passed / len(checks), 4)


def _ranking_gap(inp: OpportunityInput) -> float:
    if inp.current_position is None:
        return 0.9        # ещё не ранжируется — потенциал максимальный, но не 1.0
    return round(_clamp((inp.current_position - inp.target_position) / 20.0), 4)


def _measurement(inp: OpportunityInput) -> float:
    checks = ["data_freshness_ok", "sample_size_ok", "no_active_incident", "no_confounding_experiment"]
    if not inp.measurement:
        return 0.3
    passed = sum(1 for c in checks if inp.measurement.get(c))
    return round(passed / len(checks), 4)


def _risk(inp: OpportunityInput) -> float:
    base = 1.0
    base += 3.0 * _clamp(inp.risk.get("cannibalization_risk", 0.0))
    base += 4.0 * _clamp(inp.risk.get("rights_risk", 0.0))
    base += _clamp(inp.risk.get("effort_hours", 0.0) / 20.0) * 2.0
    base += 2.0 * _clamp(inp.risk.get("blast_radius", 0.0))
    return round(max(1.0, min(10.0, base)), 3)


def score(inp: OpportunityInput, today: date | None = None) -> OpportunityScore:
    model = config.priority_model()
    today = today or date.today()

    factors = {
        "demand_signal": _demand(inp, model),
        "release_freshness": _freshness(inp, model, today),
        "rights_and_content_readiness": _readiness(inp),
        "page_quality_readiness": _page_quality(inp),
        "ranking_gap": _ranking_gap(inp),
        "business_priority": round(_clamp(inp.business_priority, 0.5, 1.5), 3),
        "measurement_confidence": _measurement(inp),
        "risk_and_effort": _risk(inp),
    }

    gates_failed = []
    if factors["rights_and_content_readiness"] == 0.0:
        gates_failed.append("rights_and_content_readiness")
    quality_threshold = model["factors"]["page_quality_readiness"]["gate_threshold"]
    if factors["page_quality_readiness"] < quality_threshold:
        gates_failed.append("page_quality_readiness")

    numerator = 1.0
    for key in ("demand_signal", "release_freshness", "rights_and_content_readiness",
                "page_quality_readiness", "ranking_gap", "business_priority",
                "measurement_confidence"):
        numerator *= factors[key]
    raw = numerator / factors["risk_and_effort"]

    if "rights_and_content_readiness" in gates_failed:
        raw = 0.0

    hard_gates = model["hard_gates"]
    publishable = not gates_failed and all(
        inp.page_quality.get(g, False) or g in {
            "approved_rights_source", "real_title_identifiers_and_metadata",
            "player_or_unavailable_state_policy_applied", "sitemap_inclusion_planned",
            "readiness_checks_passed", "no_duplicate_or_cannibalization",
        } for g in hard_gates
    ) and bool(inp.rights_ref)

    if gates_failed:
        explanation = "Заблокировано воротами: " + ", ".join(gates_failed)
    elif raw == 0.0:
        explanation = "Нулевой score: отсутствует спрос или измеримость."
    else:
        top = sorted(((k, v) for k, v in factors.items() if k != "risk_and_effort"),
                     key=lambda t: t[1])[:2]
        explanation = "Ограничивающие факторы: " + ", ".join(f"{k}={v}" for k, v in top)

    return OpportunityScore(
        subject=inp.subject, site_id=inp.site_id,
        score=round(raw * 1000, 3), factors=factors,
        gates_failed=gates_failed, publishable=publishable, explanation=explanation,
    )


def rank(inputs: list[OpportunityInput], today: date | None = None) -> list[OpportunityScore]:
    return sorted((score(i, today) for i in inputs), key=lambda s: -s.score)
