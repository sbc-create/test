"""The daily operator run.

Modes, in increasing order of consequence:

``inventory``  read-only; probes sources and reports what exists
``dry_run``    computes every change and writes none; produces the full plan
``canary``     applies changes to one low-risk site, within the canary limits
``observe``    reads results of running experiments and decides keep/rollback

There is no ``full`` mode. Widening beyond canary is a separate, explicit
decision recorded in the experiment registry, because "apply everywhere" is the
single most expensive mistake available to an unattended process.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path

from seo_operator.audit import AuditLog, Change, ChangeStatus, utcnow
from seo_operator.datasources.base import Availability
from seo_operator.datasources.live import probe_all
from seo_operator.experiments import (
    Experiment,
    Observation,
    Phase,
    Verdict,
    decide,
)
from seo_operator.quality import GateResult, QualityReport, evaluate
from seo_operator.registry import Portfolio, load_portfolio
from seo_operator.technical_seo import Page, run_all


class Mode(str, Enum):
    INVENTORY = "inventory"
    DRY_RUN = "dry_run"
    CANARY = "canary"
    OBSERVE = "observe"


class ProductionSafetyError(RuntimeError):
    """Raised when the operator is asked to act on a surface it must not touch."""


@dataclass
class RunResult:
    mode: Mode
    started_at: str
    portfolio_size: int
    real_sites: int
    quality: QualityReport
    probes: dict[str, Availability] = field(default_factory=dict)
    findings: list[dict] = field(default_factory=list)
    proposed_changes: list[Change] = field(default_factory=list)
    applied_changes: list[Change] = field(default_factory=list)
    rolled_back: list[dict] = field(default_factory=list)
    experiments: list[Experiment] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "mode": self.mode.value,
            "started_at": self.started_at,
            "portfolio_size": self.portfolio_size,
            "real_sites": self.real_sites,
            "quality": self.quality.to_dict(),
            "findings": self.findings,
            "proposed_changes": [c.to_record() for c in self.proposed_changes],
            "applied_changes": [c.to_record() for c in self.applied_changes],
            "rolled_back": self.rolled_back,
            "experiments": [e.to_dict() for e in self.experiments],
            "blockers": self.blockers,
            "notes": self.notes,
        }


class Operator:
    def __init__(
        self,
        portfolio: Portfolio | None = None,
        audit_log: AuditLog | None = None,
        *,
        allow_synthetic: bool = False,
    ) -> None:
        self.portfolio = portfolio if portfolio is not None else load_portfolio()
        self.audit = audit_log or AuditLog(Path("var/audit/operator.jsonl"))
        self.allow_synthetic = allow_synthetic

    # -- guards ---------------------------------------------------------
    def _assert_writable(self, site_id: str, mode: Mode) -> None:
        site = self.portfolio.get(site_id)
        if site.synthetic and not self.allow_synthetic:
            raise ProductionSafetyError(
                f"{site_id} — синтетический тенант; запись разрешена только "
                "при явном allow_synthetic (dry-run/тесты)"
            )
        if mode is Mode.DRY_RUN:
            raise ProductionSafetyError("dry-run не выполняет запись")

    # -- stages ---------------------------------------------------------
    def probe(self) -> dict[str, Availability]:
        return probe_all()

    def collect_blockers(self, probes: dict[str, Availability]) -> list[str]:
        blockers = [f"{name}: {a.detail}" for name, a in sorted(probes.items()) if not a.usable]
        if not self.portfolio.real_sites:
            blockers.insert(
                0,
                "портфель пуст: ни один реальный сайт не передан оператору "
                "(нет доменов, CMS и подтверждения прав)",
            )
        return blockers

    def analyse(self, pages: list[Page]) -> list[dict]:
        return run_all(pages)

    def propose(self, site_id: str, pages: list[Page], findings: list[dict]) -> list[Change]:
        """Turn findings into concrete, reversible changes.

        Only findings with a mechanical, verifiable fix become changes. Anything
        needing editorial judgement becomes a backlog item instead, so the
        unattended path never writes prose it cannot justify.
        """
        from seo_operator.audit import ChangeKind
        from seo_operator.technical_seo import TITLE_MAX

        changes: list[Change] = []
        by_url = {p.url: p for p in pages}

        for finding in findings:
            if finding["id"] == "ONP-002":  # title too long
                for url in finding["affected_urls"]:
                    page = by_url.get(url)
                    if not page or not page.title:
                        continue
                    trimmed = page.title[:TITLE_MAX].rstrip(" -—|,")
                    if trimmed == page.title or not trimmed:
                        continue
                    changes.append(
                        Change(
                            site_id=site_id,
                            entity_id=url,
                            kind=ChangeKind.TITLE,
                            field_name="title",
                            before=page.title,
                            after=trimmed,
                            reason=f"title длиннее {TITLE_MAX} символов и обрезается в выдаче",
                            source=finding["id"],
                        )
                    )
            elif finding["id"] == "IDX-001":  # cross-canonical
                for url in finding["affected_urls"]:
                    page = by_url.get(url)
                    if not page or page.canonical is None:
                        continue
                    changes.append(
                        Change(
                            site_id=site_id,
                            entity_id=url,
                            kind=ChangeKind.CANONICAL,
                            field_name="canonical",
                            before=page.canonical,
                            after=url,
                            reason="страница канонизирована на чужой URL без обоснования",
                            source=finding["id"],
                        )
                    )
        return changes

    def apply_canary(
        self, experiment: Experiment, changes: list[Change], *, sites_touched: int = 1
    ) -> list[Change]:
        """Apply changes under canary limits, recording each to the audit log."""
        experiment.validate_canary_scope(sites_touched=sites_touched)
        self._assert_writable(experiment.site_id, Mode.CANARY)

        applied: list[Change] = []
        for change in changes:
            change.status = ChangeStatus.APPLIED
            change.experiment_id = experiment.experiment_id
            self.audit.append(change.to_record())
            applied.append(change)
        experiment.changes.extend(applied)
        experiment.phase = Phase.CANARY
        experiment.record("canary_applied", f"{len(applied)} изменений")
        return applied

    def observe_and_decide(
        self, experiment: Experiment, observation: Observation
    ) -> tuple[Verdict, str, list[dict]]:
        """Decide the experiment's fate and, on rollback, emit the undo records."""
        verdict, reason = decide(observation)
        experiment.record("observation", f"{verdict.value}: {reason}")

        rolled_back: list[dict] = []
        if verdict is Verdict.ROLLBACK:
            for payload in experiment.rollback_payloads():
                record = {
                    "action": "rollback",
                    "at": utcnow(),
                    "experiment_id": experiment.experiment_id,
                    "reason": reason,
                    **payload,
                }
                self.audit.append(record)
                rolled_back.append(record)
            for change in experiment.changes:
                change.status = ChangeStatus.ROLLED_BACK
            experiment.phase = Phase.ROLLED_BACK
        elif verdict is Verdict.KEEP:
            experiment.phase = Phase.KEPT
        else:
            experiment.phase = Phase.OBSERVING

        return verdict, reason, rolled_back

    # -- orchestration ---------------------------------------------------
    def run(
        self,
        mode: Mode = Mode.DRY_RUN,
        *,
        pages_by_site: dict[str, list[Page]] | None = None,
        today: date | None = None,
    ) -> RunResult:
        today = today or date.today()
        probes = self.probe()
        quality = evaluate(probes)

        result = RunResult(
            mode=mode,
            started_at=utcnow(),
            portfolio_size=len(self.portfolio),
            real_sites=len(self.portfolio.real_sites),
            quality=quality,
            probes=probes,
            blockers=self.collect_blockers(probes),
        )

        if quality.result is GateResult.FAIL:
            result.notes.append(
                "gate качества данных: FAIL — метрики поисковой эффективности не измеряются, "
                "в отчёт выводится «не измерено», а не нули"
            )

        pages_by_site = pages_by_site or {}
        if not pages_by_site:
            result.notes.append("нет данных обхода: анализ страниц не выполнялся")
            return result

        for site_id, pages in pages_by_site.items():
            findings = self.analyse(pages)
            result.findings.extend([{**f, "site_id": site_id} for f in findings])
            if mode in (Mode.DRY_RUN, Mode.CANARY):
                result.proposed_changes.extend(self.propose(site_id, pages, findings))

        if mode is Mode.DRY_RUN:
            result.notes.append(
                f"dry-run: рассчитано {len(result.proposed_changes)} изменений, "
                "ни одно не применено"
            )

        return result
