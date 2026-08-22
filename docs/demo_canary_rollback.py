"""Демонстрация: канарейка -> применение -> откат -> проверка целостности."""
import json, os, sys
from datetime import date

from seo_operator.audit import AuditLog
from seo_operator.cms import CMSAdapter, InMemoryCMS
from seo_operator.experiments.registry import Experiment, ExperimentRegistry
from seo_operator.state import Store

store, audit = Store(), AuditLog()
registry = ExperimentRegistry(store)
backend = InMemoryCMS({"demo-fixture::title/stellar-drift/meta": {
    "title": "Звёздный дрейф", "description": "Старое описание"}})
adapter = CMSAdapter(backend, store, audit)

before = backend.read("demo-fixture", "title/stellar-drift/meta")
exp_id = "EXP-20260822-demo-fixture-901"
registry.create(Experiment(
    id=exp_id, site_id="demo-fixture", page_type="title", query_cohort="exact_title",
    hypothesis="Добавление сезона в title повысит CTR на запросах точного названия.",
    evidence="CTR 1.9% при позиции 6.2 — ниже ожидаемого для позиции.",
    primary_variable="title_template", primary_kpi="clicks",
    baseline_start="2026-07-25", baseline_end="2026-08-22",
    guardrails=["indexed_coverage_drop", "soft_404_rate"],
    stop_loss={"clicks": 20, "impressions": 25},
    min_sample={"clicks": 40, "impressions": 1000},
    rollback_payload={"executable": True, "kind": "cms_restore", "site_id": "demo-fixture",
                      "target": "title/stellar-drift/meta", "restore": before},
    before_snapshot=before))
registry.start(exp_id, date(2026, 8, 22))

applied = adapter.mutate(
    site_id="demo-fixture", target="title/stellar-drift/meta",
    action="title_description_update", tier=1,
    new_payload={"title": "Звёздный дрейф — 2 сезон", "description": "Дата премьеры: 2026-09-05"},
    experiment_id=exp_id, dry_run=False, guard_payload={"publishes_content": False})

after_apply = backend.read("demo-fixture", "title/stellar-drift/meta")
rolled = adapter.rollback(exp_id)
after_rollback = backend.read("demo-fixture", "title/stellar-drift/meta")
registry.set_decision(exp_id, "rollback", {"reason": "демонстрация обратимости"}, 1.0, [])
chain_ok, chain_msg = audit.verify_chain()

print(json.dumps({
    "experiment": exp_id,
    "before": before,
    "after_apply": after_apply,
    "after_rollback": after_rollback,
    "restored_exactly": after_rollback == before,
    "snapshot_id": applied.snapshot_id,
    "rollback_operations": len(rolled),
    "experiment_status": registry.get(exp_id).status,
    "audit_chain_ok": chain_ok,
    "audit_records": len(list(audit.records(limit=100))),
}, ensure_ascii=False, indent=2))
assert after_rollback == before, "ОТКАТ НЕ ВОССТАНОВИЛ СОСТОЯНИЕ"
assert chain_ok, chain_msg
store.close(); audit.close()
