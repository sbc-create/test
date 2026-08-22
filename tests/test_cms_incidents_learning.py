"""CMS-мутации со снапшотами, инциденты, обучение, жизненный цикл модулей."""
from datetime import date

import pytest

from seo_operator.cms import CMSAdapter, InMemoryCMS, UnconfiguredCMS
from seo_operator.guardrails import AuthorizationBlocked, GuardrailViolation


@pytest.fixture()
def adapter(store, audit):
    return CMSAdapter(InMemoryCMS({"demo-fixture::title/x/meta": {"title": "Старый"}}), store, audit)


# --- CMS ----------------------------------------------------------------------

def test_dry_run_does_not_write(adapter):
    result = adapter.mutate(
        site_id="demo-fixture", target="title/x/meta", action="title_description_update",
        tier=1, new_payload={"title": "Новый"}, experiment_id="EXP-1", dry_run=True)
    assert not result.applied and result.dry_run
    assert adapter.backend.read("demo-fixture", "title/x/meta") == {"title": "Старый"}
    assert result.audit_seq, "Даже dry-run оставляет audit record"


def test_apply_writes_and_snapshots(adapter, store):
    result = adapter.mutate(
        site_id="demo-fixture", target="title/x/meta", action="title_description_update",
        tier=1, new_payload={"title": "Новый"}, experiment_id="EXP-1", dry_run=False)
    assert result.applied
    assert adapter.backend.read("demo-fixture", "title/x/meta")["title"] == "Новый"
    assert store.snapshots_for("EXP-1"), "Снапшот обязателен"


def test_rollback_restores_previous_state(adapter):
    adapter.mutate(site_id="demo-fixture", target="title/x/meta",
                   action="title_description_update", tier=1,
                   new_payload={"title": "Новый"}, experiment_id="EXP-1", dry_run=False)
    results = adapter.rollback("EXP-1")
    assert results
    assert adapter.backend.read("demo-fixture", "title/x/meta") == {"title": "Старый"}


def test_rollback_is_idempotent(adapter):
    adapter.mutate(site_id="demo-fixture", target="title/x/meta",
                   action="title_description_update", tier=1,
                   new_payload={"title": "Новый"}, experiment_id="EXP-1", dry_run=False)
    adapter.rollback("EXP-1")
    assert adapter.rollback("EXP-1") == []


def test_action_outside_manifest_is_blocked(adapter):
    with pytest.raises(AuthorizationBlocked):
        adapter.mutate(site_id="demo-fixture", target="x", action="canonical_change", tier=2,
                       new_payload={}, experiment_id="EXP-1", dry_run=True)


def test_unconfigured_cms_refuses_honestly(store, audit):
    a = CMSAdapter(UnconfiguredCMS(), store, audit)
    with pytest.raises(AuthorizationBlocked):
        a.mutate(site_id="demo-fixture", target="x", action="title_description_update",
                 tier=1, new_payload={}, experiment_id="E", dry_run=True)


def test_fake_engagement_payload_blocked_at_cms_layer(adapter):
    with pytest.raises(GuardrailViolation):
        adapter.mutate(site_id="demo-fixture", target="comments", action="rating_write",
                       tier=1, new_payload={}, experiment_id="E", dry_run=True)


def test_contract_version_mismatch_blocks(store, audit):
    class OldCMS(InMemoryCMS):
        contract_version = "9.0.0"
    a = CMSAdapter(OldCMS(), store, audit)
    with pytest.raises(AuthorizationBlocked):
        a.mutate(site_id="demo-fixture", target="x", action="title_description_update",
                 tier=1, new_payload={}, experiment_id="E", dry_run=True)


# --- инциденты ----------------------------------------------------------------

def test_incident_conditions_detected():
    from seo_operator.incidents.manager import Signal, detect
    sig = Signal(site_id="demo-fixture", organic_clicks_drop_pct_7d=40,
                 wrong_canonical_or_robots=True, sitemap_url_count_delta_pct=120,
                 secret_exposure=True)
    conditions = {i.condition_id for i in detect(sig, date(2026, 8, 22))}
    assert {"SC-01", "SC-03", "SC-05", "SC-12"} <= conditions


def test_externally_explained_drop_is_not_an_incident():
    from seo_operator.incidents.manager import Signal, detect
    sig = Signal(site_id="demo-fixture", organic_clicks_drop_pct_7d=40, explained_by_external=True)
    assert not any(i.condition_id == "SC-01" for i in detect(sig, date(2026, 8, 22)))


def test_incident_freezes_only_affected_site(store, audit):
    from seo_operator.experiments.registry import Experiment, ExperimentRegistry
    from seo_operator.incidents.manager import IncidentManager, Signal, detect

    registry = ExperimentRegistry(store)

    def mk(exp_id, site_id):
        return Experiment(
            id=exp_id, site_id=site_id, hypothesis="h", evidence="e",
            primary_variable="v", primary_kpi="clicks", baseline_start="2026-07-01",
            baseline_end="2026-07-28", guardrails=["g"], stop_loss={"clicks": 20},
            min_sample={}, rollback_payload={"executable": True}, before_snapshot={"a": 1})

    registry.create(mk("E-DEMO", "demo-fixture"))
    registry.start("E-DEMO")
    registry.create(mk("E-OTHER", "other-site"))
    registry.start("E-OTHER")

    manager = IncidentManager(store, registry, audit)
    incident = detect(Signal(site_id="demo-fixture", wrong_canonical_or_robots=True),
                      date(2026, 8, 22))[0]
    out = manager.open(incident)

    assert out["frozen_experiments"] == ["E-DEMO"]
    assert registry.get("E-OTHER").status == "running", "Несвязанный сайт не трогаем"


def test_incident_not_closed_without_verification(store, audit):
    from seo_operator.experiments.registry import ExperimentRegistry
    from seo_operator.incidents.manager import IncidentManager
    m = IncidentManager(store, ExperimentRegistry(store), audit)
    store.open_incident("INC-1", "demo-fixture", "SC-01", "high", "d")
    assert m.close("INC-1", verified=False, note="")["closed"] is False
    assert m.close("INC-1", verified=True, note="восстановлено")["closed"] is True


def test_rollback_candidates_scoped_to_site(store, audit):
    from seo_operator.experiments.registry import ExperimentRegistry
    from seo_operator.incidents.manager import IncidentManager
    store.save_snapshot(site_id="demo-fixture", target="a", before={},
                        rollback_payload={"executable": True}, experiment_id="E1")
    store.save_snapshot(site_id="other-site", target="b", before={},
                        rollback_payload={"executable": True}, experiment_id="E2")
    m = IncidentManager(store, ExperimentRegistry(store), audit)
    candidates = m.candidate_rollbacks("demo-fixture", "2000-01-01")
    assert len(candidates) == 1 and candidates[0]["experiment_id"] == "E1"


# --- обучение -----------------------------------------------------------------

@pytest.fixture()
def learning(tmp_path, isolated_state):
    from seo_operator.learning.registry import LearningRegistry
    return LearningRegistry(tmp_path / "learning")


def _pattern(**kw):
    from seo_operator.learning.registry import ApplicabilityScope, Pattern
    base = dict(
        id="P-001", statement="Фактический подзаголовок в title повышает CTR",
        evidence_experiments=["EXP-1"],
        scope=ApplicabilityScope(page_types=["title"], query_intents=["exact_title"],
                                 traffic_band="medium"),
        observed_lift_pct=12.0, confidence=0.85, reproductions=1)
    base.update(kw)
    return Pattern(**base)


def test_pattern_without_explicit_scope_is_not_promoted(learning):
    from seo_operator.learning.registry import ApplicabilityScope, promotion_check
    from seo_operator.experiments.evaluator import Evaluation
    from seo_operator.experiments.registry import Experiment

    p = _pattern(scope=ApplicabilityScope())
    exp = Experiment(id="EXP-1", site_id="s", hypothesis="h", evidence="e", primary_variable="v",
                     primary_kpi="clicks", baseline_start="a", baseline_end="b",
                     guardrails=["g"], stop_loss={"clicks": 20}, min_sample={},
                     rollback_payload={"executable": True})
    ev = Evaluation("EXP-1", "keep", 0.9, 10, 2, 8, [], [], False, "ok")
    ok, checks = promotion_check(p, exp, ev, [])
    assert not ok and checks["applicability_scope_explicit"] is False


def test_guardrail_breach_blocks_promotion(learning):
    from seo_operator.learning.registry import promotion_check
    from seo_operator.experiments.evaluator import Evaluation
    from seo_operator.experiments.registry import Experiment
    exp = Experiment(id="EXP-1", site_id="s", hypothesis="h", evidence="e", primary_variable="v",
                     primary_kpi="clicks", baseline_start="a", baseline_end="b",
                     guardrails=["g"], stop_loss={"clicks": 20}, min_sample={},
                     rollback_payload={"executable": True})
    ev = Evaluation("EXP-1", "keep", 0.9, 10, 2, 8, ["soft_404 вырос"], [], False, "ok")
    ok, checks = promotion_check(_pattern(), exp, ev, [])
    assert not ok and checks["guardrails_cleared"] is False


def test_protected_drift_blocks_promotion(learning):
    from seo_operator.learning.registry import promotion_check
    from seo_operator.experiments.evaluator import Evaluation
    from seo_operator.experiments.registry import Experiment
    exp = Experiment(id="EXP-1", site_id="s", hypothesis="h", evidence="e", primary_variable="v",
                     primary_kpi="clicks", baseline_start="a", baseline_end="b",
                     guardrails=["g"], stop_loss={"clicks": 20}, min_sample={},
                     rollback_payload={"executable": True})
    ev = Evaluation("EXP-1", "keep", 0.9, 10, 2, 8, [], [], False, "ok")
    ok, checks = promotion_check(_pattern(), exp, ev, [".claude/settings.json"])
    assert not ok and checks["protected_rules_unchanged"] is False


def test_activation_requires_all_checks(learning):
    learning.add_candidate(_pattern())
    assert learning.activate("P-001", {"a": True, "b": False}) is False
    assert learning.activate("P-001", {"a": True, "b": True}) is True
    assert [p for p in learning.patterns() if p["id"] == "P-001"][0]["status"] == "active"


def test_failed_patterns_are_kept_and_consulted(learning):
    from seo_operator.learning.registry import ApplicabilityScope
    learning.record_failure(
        "P-BAD", "Массовая генерация подборок повышает трафик",
        "Падение качества и каннибализация; откачено.", ["EXP-9"],
        ApplicabilityScope(page_types=["collection"], query_intents=["genre_theme"],
                           traffic_band="low"))
    assert learning.is_known_failure("Массовая генерация подборок повышает трафик", "collection")
    assert learning.is_known_failure("что-то другое") is None
    assert len(learning.failed()) == 1


def test_backtest_detects_non_transferable_pattern(learning):
    from seo_operator.learning.registry import backtest
    historical = [{"experiment_id": f"EXP-{i}", "page_type": "title",
                   "intent": "exact_title", "lift_pct": -12} for i in range(2, 6)]
    assert backtest(_pattern(), historical)["verdict"] == "contradicted"


def test_backtest_confirms_transferable_pattern(learning):
    from seo_operator.learning.registry import backtest
    historical = [{"experiment_id": f"EXP-{i}", "page_type": "title",
                   "intent": "exact_title", "lift_pct": 9} for i in range(2, 6)]
    assert backtest(_pattern(), historical)["verdict"] == "holds"


def test_backtest_reports_insufficient_data(learning):
    from seo_operator.learning.registry import backtest
    assert backtest(_pattern(), [])["verdict"] == "insufficient_data"


# --- модули -------------------------------------------------------------------

def _manifest(**kw):
    from seo_operator.modules.lifecycle import ModuleManifest
    base = dict(
        name="cannibalization-detector", purpose="Находит конкурирующие URL",
        owner="seo-operator", input_schema={}, output_schema={},
        data_sensitivity="operational", permissions=["read:analytics"],
        allowed_sites=["demo-fixture"], mutation_scope=[],
        dependencies={"PyYAML": "6.0.1"}, timeouts_s=60, retries=2,
        quotas={"gsc": 100}, tests=["tests/test_analysis.py"],
        rollout={"initial_share": 0.1}, rollback={"kind": "disable"},
        metrics=["conflicts_found"], version="0.1.0")
    base.update(kw)
    return ModuleManifest(**base)


@pytest.mark.parametrize("capability", [
    "widen_own_credentials", "modify_protected_guardrails", "disable_tests_hooks_sandbox",
    "enable_fake_engagement", "change_dns_or_ssh_scope", "modify_own_permission_rules",
    "modify_unattended_profile", "modify_own_guard_hook", "install_unverified_code",
    "claim_success_without_evidence", "deploy_to_all_sites_immediately",
])
def test_module_cannot_request_forbidden_capability(capability):
    from seo_operator.modules.lifecycle import validate_manifest
    problems = validate_manifest(_manifest(requested_capabilities=[capability]))
    assert any("BLOCKED_PROTECTED_GUARDRAIL" in p for p in problems)


def test_unpinned_dependency_rejected():
    from seo_operator.modules.lifecycle import validate_manifest
    assert any("не закреплена" in p for p in validate_manifest(_manifest(dependencies={"x": "latest"})))


def test_module_without_tests_rejected():
    from seo_operator.modules.lifecycle import validate_manifest
    assert any("без тестов" in p for p in validate_manifest(_manifest(tests=[])))


def test_module_cannot_launch_on_all_sites_at_once():
    from seo_operator.modules.lifecycle import validate_manifest
    problems = validate_manifest(_manifest(allowed_sites=["a", "b", "c"],
                                           rollout={"initial_share": 1.0}))
    assert any("Мгновенная раскатка" in p for p in problems)


def test_sensitive_module_requires_security_review():
    from seo_operator.modules.lifecycle import validate_manifest
    assert any("security review" in p for p in validate_manifest(_manifest(data_sensitivity="rights")))


def test_valid_manifest_passes():
    from seo_operator.modules.lifecycle import validate_manifest
    assert validate_manifest(_manifest()) == []


def test_stage_cannot_be_skipped():
    from seo_operator.modules.lifecycle import ModuleRecord, Stage, advance
    rec = ModuleRecord(manifest=_manifest())
    with pytest.raises(GuardrailViolation):
        advance(rec, Stage.CANARY, {"canary_scope": "1 site"})


def test_stage_requires_evidence():
    from seo_operator.modules.lifecycle import ModuleRecord, Stage, advance
    rec = ModuleRecord(manifest=_manifest())
    with pytest.raises(GuardrailViolation):
        advance(rec, Stage.SPEC_CREATED, {})


def test_promotion_requires_proven_metrics():
    from seo_operator.modules.lifecycle import ModuleRecord, Stage, advance
    rec = ModuleRecord(manifest=_manifest())
    evidence = {
        Stage.SPEC_CREATED: {"spec_path": "docs/spec.md"},
        Stage.THREAT_AND_DATA_REVIEW: {"threat_review": "ok"},
        Stage.IMPLEMENTED_IN_ISOLATED_BRANCH: {"branch": "seo/module-x"},
        Stage.UNIT_TESTED: {"unit_test_result": "42 passed"},
        Stage.INTEGRATION_TESTED: {"integration_test_result": "ok"},
        Stage.STAGING: {"staging_result": "ok"},
        Stage.CANARY: {"canary_scope": "demo-fixture"},
        Stage.OBSERVED: {"observation_result": "21 дн."},
    }
    for stage, ev in evidence.items():
        advance(rec, stage, ev)
    with pytest.raises(GuardrailViolation):
        advance(rec, Stage.PROMOTED, {"promotion_evidence": {"metrics_improved": False}})
    advance(rec, Stage.PROMOTED, {"promotion_evidence": {"metrics_improved": True}})
    assert rec.stage is Stage.PROMOTED


def test_module_needing_migration_asks_once():
    from seo_operator.modules.lifecycle import needs_owner_approval
    needed, reasons = needs_owner_approval(_manifest(permissions=["schema_migration:add_column"]))
    assert needed and reasons
