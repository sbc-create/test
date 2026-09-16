"""Контракт visual-scoring: веса, допуски, пороги и запреты.

Тесты проверяют правило, а не кандидата. Ни один тест не использует данные
reference pack amd.online и не выносит по нему вердикт: контракт, настроенный
по результату конкретного кандидата, перестаёт быть измерением.
"""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from factory.visual_scoring import (
    ComponentScore,
    ContractError,
    Identity,
    ScoringResult,
    aggregate,
    assign_component,
    check_compatibility,
    check_independence,
    check_weight_sums,
    compare,
    decide,
    exclusions_digest,
    load_contract,
    score_categorical,
    score_color,
    score_numeric,
    score_token,
    valid_exclusion,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPONENTS = ("structure_order", "geometry", "typography", "colors", "cards_media", "responsive")


@pytest.fixture(scope="module")
def contract() -> dict:
    return load_contract("1.0.0", root=REPO_ROOT / "contracts" / "visual-scoring")


def _cells(contract: dict, score_by_cell) -> list[ComponentScore]:
    """Разложить заданный балл ячейки по компонентам без искажения весов."""
    weights = {k: Decimal(str(v)) for k, v in contract["weights"]["components"].items()}
    out = []
    for surface in contract["required_surfaces"]:
        for viewport in contract["required_viewports"]:
            value = Decimal(str(score_by_cell(surface, viewport)))
            for component in COMPONENTS:
                out.append(ComponentScore(surface, viewport, component, value,
                                          weights[component], 1, 0))
    return out


def _result(contract: dict, score_by_cell, **overrides) -> ScoringResult:
    components = _cells(contract, score_by_cell)
    overall, surfaces, viewports = aggregate(components, contract)
    base = {
        "overall_score": overall, "surface_scores": surfaces, "viewport_scores": viewports,
        "component_scores": components, "hard_failures": [],
        "evidence_completeness": Decimal("100"), "comparisons_performed": len(components),
        "certification_status": "", "blocked_reasons": [],
    }
    base.update(overrides)
    return ScoringResult(**base)


#: По одному токену на каждый компонент — иначе компонент остался бы без
#: эталонных измерений и полнота evidence честно упала бы ниже 100.
_VALUES = {
    "section_order": "header,main,footer",   # structure_order
    "content_width": 1200,                   # geometry
    "type_body_font_size": 16,               # typography
    "accent_color": "#3366cc",               # colors
    "card_aspect_ratio": 1.5,                # cards_media
    "horizontal_overflow": False,            # responsive
}
_UNITS = {
    "section_order": "order", "content_width": "px", "type_body_font_size": "px",
    "accent_color": "color", "card_aspect_ratio": "ratio", "horizontal_overflow": "bool",
}


def _tokens(value_for, surfaces=None, viewports=None) -> list[dict]:
    """Полный набор измерений: 5 поверхностей x 3 ширины x 6 компонентов."""
    surfaces = surfaces if surfaces is not None else \
        ["home", "catalog", "collection_hub", "title", "not_found"]
    viewports = viewports if viewports is not None else [390, 768, 1440]
    out = []
    for surface in surfaces:
        for viewport in viewports:
            for name in _VALUES:
                out.append({
                    "name": name, "value": value_for(name, surface, viewport),
                    "unit": _UNITS[name], "surface": surface, "viewport": viewport,
                    "method": "CDP getBoundingClientRect",
                    "evidence": f"artifacts/capture/{surface}/measurements.json#/{viewport}",
                })
    return out


_ENV = {
    "renderer_engine": "chromium", "renderer_driver_version": "1.62.1",
    "browser_build": "chromium-1234", "device_pixel_ratio": 1,
    "screenshot_capture_mode": "viewport", "locale": "ru-RU",
    "timezone": "Europe/Moscow", "animation_policy": "reduce",
}


def _pack(contract, reference, candidate, **overrides) -> dict:
    """Аргументы compare() с тремя разными субъектами по умолчанию."""
    args = {
        "reference_tokens": reference, "candidate_tokens": candidate, "contract": contract,
        "checker": Identity("checker-01", "CHECKER"),
        "pack_author": Identity("templates-01", "TEMPLATES"),
        "candidate_author": Identity("candidate-01", "CANDIDATE"),
        "reference_environment": dict(_ENV), "candidate_environment": dict(_ENV),
    }
    args.update(overrides)
    return args


# --- 1. веса -----------------------------------------------------------------


def test_every_weight_matrix_sums_to_one_hundred(contract):
    assert check_weight_sums(contract) == []


@pytest.mark.parametrize("matrix", ["surfaces", "viewports", "components"])
def test_broken_weight_matrix_is_rejected(contract, matrix):
    """Опечатка в весах обязана валить загрузку, а не молча смещать оценку."""
    broken = json.loads(json.dumps(contract))
    key = next(iter(broken["weights"][matrix]))
    broken["weights"][matrix][key] += 1
    assert check_weight_sums(broken) != []


def test_load_contract_refuses_inconsistent_weights(tmp_path, contract):
    broken = json.loads(json.dumps(contract))
    broken["weights"]["surfaces"]["home"] = 99
    version_dir = tmp_path / "9.9.9"
    version_dir.mkdir()
    (version_dir / "scoring-contract.json").write_text(json.dumps(broken), encoding="utf-8")
    with pytest.raises(ContractError):
        load_contract("9.9.9", root=tmp_path)


def test_missing_contract_raises_rather_than_defaulting(tmp_path):
    """Отсутствующий контракт не заменяется значениями по умолчанию."""
    with pytest.raises(FileNotFoundError):
        load_contract("0.0.0", root=tmp_path)


# --- 2. граничные значения порога --------------------------------------------


@pytest.mark.parametrize("cell,expected", [
    ("79.99", "VISUAL_REJECTED"),
    ("80.00", "VISUAL_CERTIFIED"),
    ("80.01", "VISUAL_CERTIFIED"),
])
def test_overall_threshold_boundaries(contract, cell, expected):
    result = _result(contract, lambda s, v: cell)
    status, _ = decide(result, contract)
    assert status == expected


def test_threshold_uses_the_reported_rounded_value(contract):
    """Отчёт и вердикт не могут разойтись: сравнивается округлённое значение."""
    result = _result(contract, lambda s, v: "79.996")
    status, _ = decide(result, contract)
    assert status == "VISUAL_CERTIFIED"
    assert result.overall_score.quantize(Decimal("0.01")) == Decimal("80.00")


# --- 3. минимумы surface и viewport ------------------------------------------


def test_surface_below_minimum_rejects_despite_high_overall(contract):
    """Один проваленный surface не компенсируется остальными."""
    result = _result(contract, lambda s, v: "69.99" if s == "not_found" else "100")
    status, reasons = decide(result, contract)
    assert status == "VISUAL_REJECTED"
    assert any("not_found" in r for r in reasons)


def test_surface_at_minimum_passes(contract):
    result = _result(contract, lambda s, v: "70.00" if s == "not_found" else "100")
    assert decide(result, contract)[0] == "VISUAL_CERTIFIED"


def test_viewport_below_minimum_rejects(contract):
    result = _result(contract, lambda s, v: "64.99" if v == 390 else "100")
    status, reasons = decide(result, contract)
    assert status == "VISUAL_REJECTED"
    assert any("390" in r for r in reasons)


def test_viewport_at_minimum_passes(contract):
    result = _result(contract, lambda s, v: "65.00" if v == 390 else "100")
    assert decide(result, contract)[0] == "VISUAL_CERTIFIED"


# --- 4. линейная числовая шкала ----------------------------------------------


@pytest.mark.parametrize("reference,candidate,expected", [
    (100, 100, "100"),      # совпадение
    (100, 105, "100"),      # ровно 5 % — ещё полная оценка
    (100, 95, "100"),       # отклонение в меньшую сторону симметрично
    (100, 115, "50"),       # середина полосы
    (100, 125, "0"),        # ровно 25 % — уже ноль
    (100, 400, "0"),        # далеко за полосой
])
def test_numeric_linear_scoring(contract, reference, candidate, expected):
    assert score_numeric(reference, candidate, contract) == Decimal(expected)


def test_numeric_scoring_is_monotonic(contract):
    """Рост отклонения не может поднимать балл."""
    scores = [score_numeric(100, 100 + d, contract) for d in range(0, 30)]
    assert scores == sorted(scores, reverse=True)


def test_zero_reference_does_not_divide(contract):
    assert score_numeric(0, 0, contract) == Decimal("100")
    assert score_numeric(0, 1, contract) == Decimal("0")


def test_categorical_is_exact_or_zero():
    assert score_categorical(True, True) == Decimal("100")
    assert score_categorical(True, False) == Decimal("0")
    assert score_categorical("header,main,footer", "header,footer,main") == Decimal("0")


def test_color_exact_match_scores_full(contract):
    assert score_color("#1A2B3C", "1a2b3c", contract) == Decimal("100")


def test_color_far_apart_scores_zero(contract):
    assert score_color("#000000", "#ffffff", contract) == Decimal("0")


def test_color_scoring_is_bounded(contract):
    value = score_color("#3366cc", "#3a6ccd", contract)
    assert Decimal("0") <= value <= Decimal("100")


# --- 5. отсутствующее измерение ----------------------------------------------


def test_missing_candidate_token_scores_zero(contract):
    reference = {"name": "content_width", "value": 378, "unit": "px"}
    assert score_token(reference, None, contract) == Decimal("0")


def test_extra_candidate_token_cannot_raise_the_score(contract):
    """Токена нет в эталоне — он не участвует в расчёте и не даёт баллов."""
    reference = _tokens(lambda name, s, v: _VALUES[name])
    plain = compare(**_pack(contract, reference, reference))
    padded_candidate = reference + [
        {"name": "bonus_width", "value": 999, "unit": "px", "surface": "home",
         "viewport": 390, "method": "CDP", "evidence": "artifacts/x#/1",
         "component": "geometry"}]
    padded = compare(**_pack(contract, reference, padded_candidate))
    assert padded.overall_score == plain.overall_score
    assert padded.comparisons_performed == plain.comparisons_performed


# --- 6-7. исключения ---------------------------------------------------------


def test_declared_exclusion_needs_reason_and_provenance(contract):
    good = {"scope": "ads", "reason": "монетизация эталона",
            "provenance": "EXCLUSIONS.md", "declared_at": "2026-09-16T00:00:00Z"}
    assert valid_exclusion(good, contract)
    for field in ("reason", "provenance", "declared_at"):
        bad = dict(good)
        bad[field] = ""
        assert not valid_exclusion(bad, contract)


def test_late_exclusion_changes_the_digest(contract):
    declared = [{"scope": "ads", "reason": "монетизация", "provenance": "EXCLUSIONS.md",
                 "declared_at": "2026-09-16T00:00:00Z"}]
    before = exclusions_digest(declared)
    late = declared + [{"scope": "grid_gap", "reason": "неудобно", "provenance": "нет",
                        "declared_at": "2026-09-17T00:00:00Z"}]
    assert exclusions_digest(late) != before


def test_exclusion_digest_is_order_independent():
    """Перестановка списка — не подмена: значение имеет состав, а не порядок."""
    a = {"scope": "ads", "reason": "r", "provenance": "p", "declared_at": "t"}
    b = {"scope": "trackers", "reason": "r", "provenance": "p", "declared_at": "t"}
    assert exclusions_digest([a, b]) == exclusions_digest([b, a])


def test_exclusion_digest_changes_when_content_changes():
    a = {"scope": "ads", "reason": "r", "provenance": "p", "declared_at": "t"}
    changed = dict(a, reason="другая причина")
    assert exclusions_digest([a]) != exclusions_digest([changed])


def test_excluded_component_weight_is_redistributed(contract):
    """Исключённый компонент не обнуляет ячейку и не даёт даровых баллов."""
    weights = {k: Decimal(str(v)) for k, v in contract["weights"]["components"].items()}
    components = []
    for surface in contract["required_surfaces"]:
        for viewport in contract["required_viewports"]:
            for component in COMPONENTS:
                excluded = component == "colors"
                components.append(ComponentScore(
                    surface, viewport, component,
                    Decimal("0") if excluded else Decimal("90"),
                    weights[component], 0 if excluded else 1, 0,
                    excluded=excluded,
                    exclusion_reason="эталон цвет не измеряет" if excluded else None))
    overall, _, _ = aggregate(components, contract)
    assert overall == Decimal("90")


def test_undeclared_missing_component_blocks_instead_of_passing(contract):
    """Непокрытый и необъявленный компонент блокирует, а не снижает балл молча."""
    result = _result(contract, lambda s, v: "100",
                     evidence_completeness=Decimal("96.5"))
    status, reasons = decide(result, contract)
    assert status == "BLOCKED_EVIDENCE_INCOMPLETE"
    assert any("полнота evidence" in r for r in reasons)


# --- 8-9. hard-fail и дайджесты ----------------------------------------------


def test_hard_fail_overrides_a_perfect_score(contract):
    result = _result(contract, lambda s, v: "100", hard_failures=[
        {"code": "HORIZONTAL_OVERFLOW", "detail": "появилась горизонтальная прокрутка"}])
    status, reasons = decide(result, contract)
    assert status == "VISUAL_REJECTED"
    assert reasons == ["hard-fail: HORIZONTAL_OVERFLOW"]


def test_digest_mismatch_is_a_hard_fail(contract):
    result = _result(contract, lambda s, v: "100", hard_failures=[
        {"code": "DIGEST_MISMATCH", "detail": "снимок home@390 не совпал"}])
    assert decide(result, contract)[0] == "VISUAL_REJECTED"


def test_every_required_hard_fail_code_is_declared(contract):
    declared = {f["code"] for f in contract["hard_failures"]}
    assert declared == {
        "MISSING_SURFACE", "MISSING_VIEWPORT", "DIGEST_MISMATCH",
        "MEASUREMENT_WITHOUT_PROVENANCE", "EVIDENCE_MUTATED_DURING_RUN",
        "HORIZONTAL_OVERFLOW", "REQUIRED_BLOCK_ABSENT", "CONTENT_OVERLAP",
        "CHECKER_NOT_INDEPENDENT", "CONTRACT_MUTATED_AFTER_RESULT",
        "UNDECLARED_EXCLUSION",
    }


# --- 10. независимость -------------------------------------------------------


def test_checker_equal_to_pack_author_is_a_violation(contract):
    same = Identity("agent-a", "TEMPLATES")
    failures = check_independence(same, same, Identity("agent-b", "CANDIDATE"))
    result = _result(contract, lambda s, v: "100", hard_failures=failures)
    assert decide(result, contract)[0] == "BLOCKED_INDEPENDENCE_VIOLATION"


def test_checker_equal_to_candidate_author_is_a_violation(contract):
    checker = Identity("agent-b", "CHECKER")
    failures = check_independence(checker, Identity("agent-a", "TEMPLATES"), checker)
    assert failures and failures[0]["code"] == "CHECKER_NOT_INDEPENDENT"


def test_three_distinct_subjects_pass_independence():
    assert check_independence(Identity("c", "CHECKER"), Identity("a", "PACK"),
                              Identity("b", "CANDIDATE")) == []


# --- 11. совместимость -------------------------------------------------------


def test_environment_mismatch_is_reported():
    reference = {"browser_build": "chromium-1234", "device_pixel_ratio": 1}
    candidate = {"browser_build": "chromium-1200", "device_pixel_ratio": 1}
    mismatches = check_compatibility(reference, candidate)
    assert any("browser_build" in m for m in mismatches)


def test_unprovable_range_is_forbidden():
    both = {"apiVersionRange": "latest"}
    assert any("запрещено контрактом" in m for m in check_compatibility(both, both))


def test_identical_environment_has_no_mismatch():
    env = {"browser_build": "chromium-1234", "locale": "ru-RU"}
    assert check_compatibility(env, env) == []


def test_contract_pins_versions_instead_of_guessing(contract):
    """Недоказуемый диапазон закреплён версией, а не словом latest."""
    compat = contract["compatibility"]
    assert compat["renderer"]["driver_version"]["value"] == "1.62.1"
    assert compat["renderer"]["browser_build"]["value"] == "chromium-1234"
    assert compat["python_runtime"]["value"] == "3.11"
    for key in ("locale", "timezone", "font_availability", "animation_policy"):
        assert compat[key]["kind"] == "must_be_declared"
        assert compat[key]["value"] is None


# --- 12-13. детерминированность ----------------------------------------------


def test_repeated_run_is_identical(contract):
    first = _result(contract, lambda s, v: "83.33")
    second = _result(contract, lambda s, v: "83.33")
    assert first.overall_score == second.overall_score
    assert first.surface_scores == second.surface_scores
    assert first.viewport_scores == second.viewport_scores


def test_component_order_does_not_change_the_result(contract):
    components = _cells(contract, lambda s, v: "77.7")
    straight = aggregate(components, contract)
    shuffled = aggregate(list(reversed(components)), contract)
    assert straight == shuffled


def test_intermediate_values_are_not_rounded(contract):
    """Округление на каждом шаге копит ошибку — округляется только отчёт."""
    result = _result(contract, lambda s, v: "33.333" if v != 1440 else "33.334")
    # Точное взвешенное значение: 0.30*33.333 + 0.30*33.333 + 0.40*33.334.
    assert result.overall_score == Decimal("33.3334")
    # Четвёртый знак сохранён, то есть промежуточного округления не было.
    assert result.overall_score != result.overall_score.quantize(Decimal("0.01"))
    assert result.overall_score.quantize(Decimal("0.01")) == Decimal("33.33")


# --- 14. запрет тихого успеха ------------------------------------------------


def test_zero_comparisons_cannot_pass(contract):
    result = _result(contract, lambda s, v: "100", comparisons_performed=0)
    status, reasons = decide(result, contract)
    assert status == "BLOCKED_EVIDENCE_INCOMPLETE"
    assert reasons == ["ноль выполненных сравнений не является успехом"]


def test_incomplete_evidence_cannot_pass(contract):
    result = _result(contract, lambda s, v: "100", evidence_completeness=Decimal("99.99"))
    assert decide(result, contract)[0] == "BLOCKED_EVIDENCE_INCOMPLETE"


# --- классификация токенов ---------------------------------------------------


@pytest.mark.parametrize("name,component", [
    ("content_width", "geometry"),
    ("outer_gutter", "geometry"),
    ("grid_columns", "geometry"),
    ("grid_gap", "geometry"),
    ("header_height", "geometry"),
    ("page_height", "geometry"),
    ("type_h1_font_size", "typography"),
    ("type_body_font_weight", "typography"),
    ("type_h2_line_height", "typography"),
    ("card_aspect_ratio", "cards_media"),
    ("cards_sampled", "cards_media"),
    ("horizontal_overflow", "responsive"),
    ("content_overlap", "responsive"),
    ("section_order", "structure_order"),
    ("header_present", "structure_order"),
    ("accent_color", "colors"),
    ("card_radius", "cards_media"),
])
def test_component_assignment_is_rule_driven(contract, name, component):
    assert assign_component({"name": name}, contract) == component


def test_explicit_component_field_wins(contract):
    assert assign_component({"name": "content_width", "component": "colors"}, contract) == "colors"


def test_unknown_token_is_not_silently_dropped(contract):
    assert assign_component({"name": "zzz_unknown_thing"}, contract) == "UNASSIGNED"


def test_screenshot_digest_is_not_a_scored_unit(contract):
    assert "sha256" in contract["non_scoring_units"]


# --- форма контракта ---------------------------------------------------------


def test_contract_declares_required_surfaces_and_viewports(contract):
    assert contract["required_surfaces"] == ["home", "catalog", "collection_hub", "title", "not_found"]
    assert contract["required_viewports"] == [390, 768, 1440]


def test_contract_version_is_immutable_and_pinned(contract):
    assert contract["contract_version"] == "visual-scoring/1.0.0"
    assert contract["status"] == "immutable"


# --- сквозной расчёт через compare() -----------------------------------------


def test_identical_packs_certify(contract):
    """Полное совпадение при трёх разных субъектах даёт сертификацию."""
    reference = _tokens(lambda name, s, v: _VALUES[name])
    result = compare(**_pack(contract, reference, reference))
    assert result.certification_status == "VISUAL_CERTIFIED"
    assert result.overall_score == Decimal("100")
    assert result.evidence_completeness == Decimal("100")
    assert result.comparisons_performed == 90
    assert result.hard_failures == []


def test_missing_candidate_token_lowers_completeness_and_blocks(contract):
    """Пропущенное измерение не проходит мимо: оно и 0 баллов, и неполнота."""
    reference = _tokens(lambda name, s, v: _VALUES[name])
    candidate = [t for t in reference
                 if not (t["surface"] == "home" and t["viewport"] == 390
                         and t["name"] == "content_width")]
    result = compare(**_pack(contract, reference, candidate))
    assert result.certification_status == "BLOCKED_EVIDENCE_INCOMPLETE"
    assert result.evidence_completeness < Decimal("100")
    assert result.comparisons_performed == 89


def test_missing_surface_is_a_hard_fail(contract):
    reference = _tokens(lambda name, s, v: _VALUES[name])
    candidate = [t for t in reference if t["surface"] != "not_found"]
    result = compare(**_pack(contract, reference, candidate))
    assert result.certification_status == "VISUAL_REJECTED"
    assert {f["code"] for f in result.hard_failures} == {"MISSING_SURFACE"}


def test_missing_viewport_is_a_hard_fail(contract):
    reference = _tokens(lambda name, s, v: _VALUES[name])
    candidate = [t for t in reference if t["viewport"] != 1440]
    result = compare(**_pack(contract, reference, candidate))
    assert "MISSING_VIEWPORT" in {f["code"] for f in result.hard_failures}


def test_token_without_provenance_is_a_hard_fail(contract):
    reference = _tokens(lambda name, s, v: _VALUES[name])
    stripped = [dict(t, evidence="") if t["name"] == "content_width" else t for t in reference]
    result = compare(**_pack(contract, reference, stripped))
    assert "MEASUREMENT_WITHOUT_PROVENANCE" in {f["code"] for f in result.hard_failures}
    assert result.certification_status == "VISUAL_REJECTED"


def test_digest_mismatch_blocks_a_perfect_candidate(contract):
    reference = _tokens(lambda name, s, v: _VALUES[name])
    result = compare(**_pack(contract, reference, reference, digest_checks=[
        {"scope": "reference", "name": "home@390", "recorded": "sha256:aa", "observed": "sha256:bb"}]))
    assert result.certification_status == "VISUAL_REJECTED"
    assert {f["code"] for f in result.hard_failures} == {"DIGEST_MISMATCH"}


def test_compatibility_mismatch_blocks_before_scoring_verdict(contract):
    reference = _tokens(lambda name, s, v: _VALUES[name])
    other_env = dict(_ENV, browser_build="chromium-1200")
    result = compare(**_pack(contract, reference, reference, candidate_environment=other_env))
    assert result.certification_status == "BLOCKED_COMPATIBILITY_MISMATCH"
    assert any("browser_build" in r for r in result.blocked_reasons)


def test_independence_violation_outranks_a_perfect_score(contract):
    reference = _tokens(lambda name, s, v: _VALUES[name])
    same = Identity("templates-01", "TEMPLATES")
    result = compare(**_pack(contract, reference, reference, checker=same, pack_author=same))
    assert result.certification_status == "BLOCKED_INDEPENDENCE_VIOLATION"
    assert result.overall_score == Decimal("100")


def test_late_exclusion_is_detected_by_the_baseline_digest(contract):
    reference = _tokens(lambda name, s, v: _VALUES[name])
    declared = [{"scope": "ads", "reason": "монетизация эталона",
                 "provenance": "EXCLUSIONS.md", "declared_at": "2026-09-16T00:00:00Z"}]
    baseline = exclusions_digest(declared)
    late = declared + [{"scope": "colors", "reason": "портит оценку",
                        "provenance": "нет", "declared_at": "2026-09-17T00:00:00Z"}]
    result = compare(**_pack(contract, reference, reference,
                             declared_exclusions=late, baseline_exclusions_digest=baseline))
    assert "UNDECLARED_EXCLUSION" in {f["code"] for f in result.hard_failures}
    assert result.certification_status == "VISUAL_REJECTED"


def test_declared_component_exclusion_redistributes_weight(contract):
    """Заранее исключённый компонент не мешает сертификации и не дарит баллов."""
    reference = [t for t in _tokens(lambda name, s, v: _VALUES[name]) if t["name"] != "accent_color"]
    excluded = [{"scope": "colors", "component": "colors",
                 "reason": "эталон цвет не измеряет", "provenance": "EXCLUSIONS.md",
                 "declared_at": "2026-09-16T00:00:00Z"}]
    result = compare(**_pack(contract, reference, reference,
                             declared_exclusions=excluded,
                             baseline_exclusions_digest=exclusions_digest(excluded)))
    assert result.certification_status == "VISUAL_CERTIFIED"
    assert result.evidence_completeness == Decimal("100")
    assert result.weight_redistribution
    assert all(r["to_weight"] > r["from_weight"] for r in result.weight_redistribution)


def test_unmeasured_component_without_exclusion_blocks(contract):
    """Тот же пробел без объявления блокирует, а не проходит тихо."""
    reference = [t for t in _tokens(lambda name, s, v: _VALUES[name]) if t["name"] != "accent_color"]
    result = compare(**_pack(contract, reference, reference))
    assert result.certification_status == "BLOCKED_EVIDENCE_INCOMPLETE"
    assert result.evidence_completeness < Decimal("100")


def test_empty_input_cannot_pass(contract):
    result = compare(**_pack(contract, [], []))
    assert result.certification_status != "VISUAL_CERTIFIED"
    assert result.comparisons_performed == 0


def test_compare_is_deterministic_across_runs(contract):
    reference = _tokens(lambda name, s, v: _VALUES[name])
    candidate = _tokens(lambda name, s, v:
                        1290 if name == "content_width" else _VALUES[name])
    first = compare(**_pack(contract, reference, candidate))
    second = compare(**_pack(contract, list(reversed(reference)), list(reversed(candidate))))
    assert first.overall_score == second.overall_score
    assert first.surface_scores == second.surface_scores
    assert first.viewport_scores == second.viewport_scores
    assert first.certification_status == second.certification_status


def test_large_geometry_drift_rejects(contract):
    """Отклонение геометрии за полосу допуска обязано отклонять кандидата."""
    reference = _tokens(lambda name, s, v: _VALUES[name])
    candidate = _tokens(lambda name, s, v:
                        600 if name == "content_width" else _VALUES[name])
    result = compare(**_pack(contract, reference, candidate))
    assert result.certification_status == "VISUAL_REJECTED"
    assert result.overall_score < Decimal("80")


def test_contract_files_match_their_recorded_checksums():
    """Правка выпущенной версии обязана обнаруживаться, а не проходить тихо."""
    import hashlib

    base = REPO_ROOT / "contracts" / "visual-scoring" / "1.0.0"
    recorded = json.loads((base / "checksums.json").read_text(encoding="utf-8"))
    for name, digest in sorted(recorded["files"].items()):
        path = (base / name).resolve()
        actual = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == digest, f"{name} изменён после выпуска версии"


def test_all_statuses_are_declared(contract):
    assert set(contract["statuses"]) == {
        "VISUAL_CERTIFIED", "VISUAL_REJECTED", "BLOCKED_EVIDENCE_INCOMPLETE",
        "BLOCKED_COMPATIBILITY_MISMATCH", "BLOCKED_INDEPENDENCE_VIOLATION",
        "BLOCKED_SCORING_CONTRACT_MISSING",
    }
