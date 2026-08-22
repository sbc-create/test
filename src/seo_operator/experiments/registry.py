"""Реестр экспериментов. Без stop-loss и rollback payload эксперимент не стартует."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

from .. import config
from ..guardrails import GuardrailViolation
from ..state import Store

STATUSES = {"draft", "running", "observing", "mature", "kept", "rolled_back", "inconclusive", "frozen"}


@dataclass
class Experiment:
    id: str
    site_id: str
    hypothesis: str
    evidence: str
    primary_variable: str
    primary_kpi: str
    baseline_start: str
    baseline_end: str
    guardrails: list[str]
    stop_loss: dict[str, Any]
    min_sample: dict[str, Any]
    page_type: str | None = None
    query_cohort: str | None = None
    secondary_changes: list[str] = field(default_factory=list)
    control_cohort: str | None = None
    rollback_payload: dict[str, Any] | None = None
    before_snapshot: dict[str, Any] | None = None
    started_at: str | None = None
    ends_at: str | None = None
    status: str = "draft"
    audit_refs: list[str] = field(default_factory=list)
    result: dict[str, Any] | None = None
    confidence: float | None = None
    confounders: list[str] = field(default_factory=list)
    decision: str | None = None
    learned_rule_candidate: str | None = None


def new_id(site_id: str, seq: int, today: date | None = None) -> str:
    today = today or date.today()
    return f"EXP-{today:%Y%m%d}-{site_id}-{seq:03d}"


class ExperimentRegistry:
    def __init__(self, store: Store) -> None:
        self.store = store

    # ---------- создание ----------

    def next_sequence(self, site_id: str, today: date | None = None) -> int:
        today = today or date.today()
        prefix = f"EXP-{today:%Y%m%d}-{site_id}-"
        row = self.store.conn.execute(
            "SELECT COUNT(*) c FROM experiments WHERE id LIKE ?", (prefix + "%",)).fetchone()
        return row["c"] + 1

    def validate(self, exp: Experiment) -> None:
        if not exp.hypothesis.strip():
            raise GuardrailViolation("GR-007", "Эксперимент без гипотезы.")
        if not exp.evidence.strip():
            raise GuardrailViolation("GR-007", "Эксперимент без доказательной базы.")
        if not exp.primary_variable.strip():
            raise GuardrailViolation("GR-007", "Не задана единственная основная переменная.")
        if len(exp.secondary_changes) > 0 and not exp.result:
            # допустимо только если изменения неотделимы — это фиксируется явно
            for change in exp.secondary_changes:
                if not change.startswith("inseparable:"):
                    raise GuardrailViolation(
                        "GR-007",
                        f"Побочное изменение '{change}' не помечено как неотделимое (inseparable:).")
        if not exp.stop_loss:
            raise GuardrailViolation("GR-007", "Эксперимент без stop-loss не стартует.")
        if not exp.guardrails:
            raise GuardrailViolation("GR-007", "Эксперимент без guardrail-метрик не стартует.")
        if not exp.rollback_payload or not exp.rollback_payload.get("executable"):
            raise GuardrailViolation("GR-006", "Нет исполняемого rollback payload.")
        if not exp.before_snapshot:
            raise GuardrailViolation("GR-006", "Нет before-snapshot.")

    def create(self, exp: Experiment) -> Experiment:
        self.validate(exp)
        now = datetime.now(timezone.utc).isoformat()
        self.store.conn.execute(
            """INSERT INTO experiments
               (id, site_id, page_type, query_cohort, hypothesis, evidence, primary_variable,
                secondary_changes, baseline_start, baseline_end, control_cohort, started_at, ends_at,
                primary_kpi, guardrails, min_sample, stop_loss, rollback_payload, before_snapshot,
                audit_refs, status, confounders, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (exp.id, exp.site_id, exp.page_type, exp.query_cohort, exp.hypothesis, exp.evidence,
             exp.primary_variable, json.dumps(exp.secondary_changes), exp.baseline_start,
             exp.baseline_end, exp.control_cohort, exp.started_at, exp.ends_at, exp.primary_kpi,
             json.dumps(exp.guardrails), json.dumps(exp.min_sample), json.dumps(exp.stop_loss),
             json.dumps(exp.rollback_payload), json.dumps(exp.before_snapshot),
             json.dumps(exp.audit_refs), exp.status, json.dumps(exp.confounders), now, now),
        )
        self.store.conn.commit()
        return exp

    # ---------- чтение ----------

    def get(self, exp_id: str) -> Experiment | None:
        row = self.store.conn.execute("SELECT * FROM experiments WHERE id=?", (exp_id,)).fetchone()
        return self._row_to_exp(row) if row else None

    def by_status(self, status: str, site_id: str | None = None) -> list[Experiment]:
        if site_id:
            rows = self.store.conn.execute(
                "SELECT * FROM experiments WHERE status=? AND site_id=?", (status, site_id))
        else:
            rows = self.store.conn.execute("SELECT * FROM experiments WHERE status=?", (status,))
        return [self._row_to_exp(r) for r in rows]

    def active(self, site_id: str | None = None) -> list[Experiment]:
        return self.by_status("running", site_id) + self.by_status("observing", site_id)

    @staticmethod
    def _row_to_exp(row) -> Experiment:
        def j(v, default):
            return json.loads(v) if v else default
        return Experiment(
            id=row["id"], site_id=row["site_id"], page_type=row["page_type"],
            query_cohort=row["query_cohort"], hypothesis=row["hypothesis"], evidence=row["evidence"],
            primary_variable=row["primary_variable"], secondary_changes=j(row["secondary_changes"], []),
            baseline_start=row["baseline_start"], baseline_end=row["baseline_end"],
            control_cohort=row["control_cohort"], started_at=row["started_at"], ends_at=row["ends_at"],
            primary_kpi=row["primary_kpi"], guardrails=j(row["guardrails"], []),
            min_sample=j(row["min_sample"], {}), stop_loss=j(row["stop_loss"], {}),
            rollback_payload=j(row["rollback_payload"], None), before_snapshot=j(row["before_snapshot"], None),
            audit_refs=j(row["audit_refs"], []), status=row["status"],
            result=j(row["result"], None), confidence=row["confidence"],
            confounders=j(row["confounders"], []), decision=row["decision"],
            learned_rule_candidate=row["learned_rule_candidate"],
        )

    # ---------- переходы ----------

    def start(self, exp_id: str, today: date | None = None) -> Experiment:
        exp = self.get(exp_id)
        if exp is None:
            raise KeyError(exp_id)
        if exp.status != "draft":
            raise GuardrailViolation("GR-007", f"Старт возможен только из draft (сейчас {exp.status}).")
        today = today or date.today()
        policy = config.experiment_policy()
        ends = today + timedelta(days=policy["maturity"]["min_observation_days"])
        self._update(exp_id, status="running", started_at=today.isoformat(), ends_at=ends.isoformat())
        return self.get(exp_id)  # type: ignore[return-value]

    def freeze(self, site_id: str, reason: str) -> list[str]:
        """Инцидент замораживает эксперименты только затронутого сайта."""
        frozen = []
        for exp in self.active(site_id):
            self._update(exp.id, status="frozen",
                         confounders=json.dumps(exp.confounders + [f"frozen:{reason}"]))
            frozen.append(exp.id)
        return frozen

    def set_decision(self, exp_id: str, decision: str, result: dict[str, Any],
                     confidence: float, confounders: list[str],
                     learned_rule: str | None = None) -> None:
        status_map = {"keep": "kept", "rollback": "rolled_back",
                      "inconclusive": "inconclusive", "iterate": "inconclusive"}
        self._update(
            exp_id, status=status_map.get(decision, "observing"), decision=decision,
            result=json.dumps(result, ensure_ascii=False), confidence=confidence,
            confounders=json.dumps(confounders, ensure_ascii=False),
            learned_rule_candidate=learned_rule,
        )

    def _update(self, exp_id: str, **fields: Any) -> None:
        if not fields:
            return
        for key in fields:
            if not re.fullmatch(r"[a-z_]+", key):
                raise ValueError(f"Недопустимое имя поля: {key}")
        sets = ", ".join(f"{k}=?" for k in fields)
        args = list(fields.values()) + [datetime.now(timezone.utc).isoformat(), exp_id]
        self.store.conn.execute(f"UPDATE experiments SET {sets}, updated_at=? WHERE id=?", args)
        self.store.conn.commit()
