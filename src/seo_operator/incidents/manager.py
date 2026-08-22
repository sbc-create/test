"""
Обнаружение инцидентов и восстановление.

Ключевое требование: заморозка только затронутого сайта. Инцидент на одном
сайте не должен останавливать портфель и не должен приводить к откату
несвязанных изменений.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from .. import config
from ..audit import AuditLog
from ..experiments.registry import ExperimentRegistry
from ..state import Store

SEVERITY = {
    "SC-01": "high", "SC-02": "high", "SC-03": "critical", "SC-04": "high",
    "SC-05": "critical", "SC-06": "critical", "SC-07": "critical", "SC-08": "critical",
    "SC-09": "critical", "SC-10": "high", "SC-11": "medium", "SC-12": "critical",
    "SC-13": "critical",
}


@dataclass
class Signal:
    """Наблюдаемое состояние сайта, по которому проверяются stop-условия."""
    site_id: str
    organic_clicks_drop_pct_7d: float = 0.0
    explained_by_external: bool = False
    indexed_coverage_drop_pct: float = 0.0
    wrong_canonical_or_robots: bool = False
    error_rate_above_budget: bool = False
    sitemap_url_count_delta_pct: float = 0.0
    tenant_leakage: bool = False
    rights_problem: bool = False
    security_or_manual_action: bool = False
    fake_or_demo_data_in_production: bool = False
    player_failure_rate_priority: float = 0.0
    cwv_severe_regression: bool = False
    secret_exposure: bool = False
    unexpected_mass_cms_mutation: bool = False


@dataclass
class DetectedIncident:
    incident_id: str
    site_id: str
    condition_id: str
    severity: str
    detail: str
    evidence: dict[str, Any] = field(default_factory=dict)


def detect(signal: Signal, today: date | None = None) -> list[DetectedIncident]:
    today = today or date.today()
    found: list[DetectedIncident] = []

    def add(cond: str, detail: str, evidence: dict[str, Any]) -> None:
        fingerprint = hashlib.sha256(
            f"{signal.site_id}:{cond}:{today}".encode()).hexdigest()[:12]
        found.append(DetectedIncident(
            incident_id=f"INC-{today:%Y%m%d}-{signal.site_id}-{fingerprint}",
            site_id=signal.site_id, condition_id=cond,
            severity=SEVERITY[cond], detail=detail, evidence=evidence))

    if signal.organic_clicks_drop_pct_7d >= 25 and not signal.explained_by_external:
        add("SC-01", f"Падение органических кликов {signal.organic_clicks_drop_pct_7d:.1f}% за 7 дн. "
                     "без внешнего объяснения.",
            {"drop_pct": signal.organic_clicks_drop_pct_7d})
    if signal.indexed_coverage_drop_pct >= 15:
        add("SC-02", f"Падение индексного покрытия {signal.indexed_coverage_drop_pct:.1f}%.",
            {"drop_pct": signal.indexed_coverage_drop_pct})
    if signal.wrong_canonical_or_robots:
        add("SC-03", "Обнаружен неверный canonical/robots/noindex.", {})
    if signal.error_rate_above_budget:
        add("SC-04", "Массовые 4xx/5xx/soft-404 сверх бюджета.", {})
    if abs(signal.sitemap_url_count_delta_pct) > 50:
        add("SC-05", f"Взрывное изменение sitemap: {signal.sitemap_url_count_delta_pct:+.0f}%.",
            {"delta_pct": signal.sitemap_url_count_delta_pct})
    if signal.tenant_leakage:
        add("SC-06", "Утечка между tenant.", {})
    if signal.rights_problem:
        add("SC-07", "Проблема с правами на контент.", {})
    if signal.security_or_manual_action:
        add("SC-08", "Security issue или ручные санкции.", {})
    if signal.fake_or_demo_data_in_production:
        add("SC-09", "Фиктивные/демо-данные в production.", {})
    if signal.player_failure_rate_priority > 0.05:
        add("SC-10", f"Отказы плеера на приоритетных страницах: {signal.player_failure_rate_priority:.1%}.",
            {"rate": signal.player_failure_rate_priority})
    if signal.cwv_severe_regression:
        add("SC-11", "Серьёзная регрессия CWV/CLS.", {})
    if signal.secret_exposure:
        add("SC-12", "Подозрение на раскрытие секрета.", {})
    if signal.unexpected_mass_cms_mutation:
        add("SC-13", "Неожиданная массовая CMS-мутация.", {})

    return found


class IncidentManager:
    def __init__(self, store: Store, registry: ExperimentRegistry, audit: AuditLog) -> None:
        self.store = store
        self.registry = registry
        self.audit = audit

    def open(self, incident: DetectedIncident) -> dict[str, Any]:
        """Открыть инцидент: заморозить эксперименты ТОЛЬКО этого сайта, сохранить доказательства."""
        self.store.open_incident(
            incident.incident_id, incident.site_id, incident.condition_id,
            incident.severity, incident.detail, incident.evidence)

        frozen = self.registry.freeze(incident.site_id, incident.condition_id)

        rec = self.audit.append(
            actor="seo-operator", action="incident_open",
            payload={"incident_id": incident.incident_id, "condition": incident.condition_id,
                     "detail": incident.detail, "frozen_experiments": frozen,
                     "evidence": incident.evidence},
            site_id=incident.site_id)

        return {"incident_id": incident.incident_id, "frozen_experiments": frozen,
                "audit_seq": rec.seq, "severity": incident.severity}

    def candidate_rollbacks(self, site_id: str, since_iso: str) -> list[dict[str, Any]]:
        """
        Последний причинно правдоподобный обратимый пакет изменений — только этого сайта.
        Несвязанные сайты не трогаются никогда (ROLLBACK_POLICY.never).
        """
        rows = self.store.conn.execute(
            "SELECT * FROM snapshots WHERE site_id=? AND rolled_back_at IS NULL AND created_at>=?"
            " ORDER BY created_at DESC", (site_id, since_iso)).fetchall()
        return [{"snapshot_id": r["id"], "target": r["target"],
                 "experiment_id": r["experiment_id"], "created_at": r["created_at"]} for r in rows]

    def close(self, incident_id: str, verified: bool, note: str) -> dict[str, Any]:
        if not verified:
            return {"closed": False, "reason": "Восстановление не подтверждено — инцидент остаётся открытым."}
        self.store.close_incident(incident_id)
        rec = self.audit.append(
            actor="seo-operator", action="incident_close",
            payload={"incident_id": incident_id, "note": note})
        return {"closed": True, "audit_seq": rec.seq}
