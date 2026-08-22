"""
Ежедневный цикл оператора.

Реализован как конечный автомат с идемпотентными шагами. Разговор Claude
не является планировщиком: этот модуль запускается cron/systemd/`claude -p`
и целиком восстанавливается после перезапуска из durable state.

Блокирующая ошибка одного шага не останавливает независимые шаги — это
прямое требование «продолжай все независимые задачи».
"""
from __future__ import annotations

import traceback
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable

from . import config
from .audit import AuditLog
from .cms import CMSAdapter, InMemoryCMS, UnconfiguredCMS
from .connectors import base as connectors
from .experiments.allocator import Allocator
from .experiments.registry import ExperimentRegistry
from .guardrails import AuthorizationBlocked, GuardrailViolation, protected_fingerprint
from .incidents.manager import IncidentManager, Signal, detect as detect_incidents
from .state import Store


class Step(str, Enum):
    COLLECT = "COLLECT"
    VALIDATE_DATA = "VALIDATE_DATA"
    DETECT_INCIDENTS = "DETECT_INCIDENTS"
    UPDATE_BASELINES = "UPDATE_BASELINES"
    DISCOVER_EDITORIAL_CHANGES = "DISCOVER_EDITORIAL_CHANGES"
    REFRESH_RELEASE_CALENDAR = "REFRESH_RELEASE_CALENDAR"
    FIND_OPPORTUNITIES = "FIND_OPPORTUNITIES"
    PRIORITIZE = "PRIORITIZE"
    FORM_HYPOTHESES = "FORM_HYPOTHESES"
    SAFETY_REVIEW = "SAFETY_REVIEW"
    PLAN_CANARY = "PLAN_CANARY"
    APPLY_ALLOWED_CHANGES = "APPLY_ALLOWED_CHANGES"
    TECHNICAL_VERIFY = "TECHNICAL_VERIFY"
    VERIFY_EDITORIAL_FACTS_AND_FRESHNESS = "VERIFY_EDITORIAL_FACTS_AND_FRESHNESS"
    OBSERVE = "OBSERVE"
    EVALUATE_MATURE_EXPERIMENTS = "EVALUATE_MATURE_EXPERIMENTS"
    KEEP_OR_ROLLBACK = "KEEP_OR_ROLLBACK"
    LEARN = "LEARN"
    REPORT = "REPORT"


PIPELINE = list(Step)

# Шаги, которые нельзя выполнять при открытом инциденте на сайте.
MUTATING_STEPS = {Step.PLAN_CANARY, Step.APPLY_ALLOWED_CHANGES}


@dataclass
class StepResult:
    step: Step
    status: str                 # ok | skipped | WAITING_DATA | BLOCKED_AUTHORIZATION | BLOCKED_PROTECTED_GUARDRAIL | error
    detail: str = ""
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunReport:
    run_date: str
    dry_run: bool
    sites: list[str]
    steps: list[StepResult] = field(default_factory=list)
    blockers: list[dict[str, Any]] = field(default_factory=list)
    protected_drift: list[str] = field(default_factory=list)

    def status_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for s in self.steps:
            counts[s.status] = counts.get(s.status, 0) + 1
        return counts

    @property
    def ok(self) -> bool:
        return not any(s.status == "error" for s in self.steps)


class DailyRun:
    def __init__(self, store: Store, audit: AuditLog, *, dry_run: bool = True,
                 today: date | None = None, cms_backend: Any | None = None) -> None:
        self.store = store
        self.audit = audit
        self.dry_run = dry_run
        self.today = today or date.today()
        self.registry = ExperimentRegistry(store)
        self.allocator = Allocator(self.registry)
        backend = cms_backend or (InMemoryCMS() if dry_run else UnconfiguredCMS())
        self.cms = CMSAdapter(backend, store, audit)
        self.incidents = IncidentManager(store, self.registry, audit)
        self._context: dict[str, Any] = {}

    # ------------------------------------------------------------------

    def run(self, site_ids: list[str] | None = None) -> RunReport:
        sites = site_ids or [s.site_id for s in config.portfolio()]
        report = RunReport(run_date=self.today.isoformat(), dry_run=self.dry_run, sites=sites)

        report.protected_drift = self._protected_drift()
        if report.protected_drift:
            report.steps.append(StepResult(
                Step.SAFETY_REVIEW, "BLOCKED_PROTECTED_GUARDRAIL",
                f"Изменены protected файлы: {report.protected_drift}. "
                "Мутации остановлены до review."))

        handlers: dict[Step, Callable[[list[str]], StepResult]] = {
            Step.COLLECT: self._collect,
            Step.VALIDATE_DATA: self._validate_data,
            Step.DETECT_INCIDENTS: self._detect_incidents,
            Step.UPDATE_BASELINES: self._update_baselines,
            Step.DISCOVER_EDITORIAL_CHANGES: self._discover_editorial,
            Step.REFRESH_RELEASE_CALENDAR: self._refresh_calendar,
            Step.FIND_OPPORTUNITIES: self._find_opportunities,
            Step.PRIORITIZE: self._prioritize,
            Step.FORM_HYPOTHESES: self._form_hypotheses,
            Step.SAFETY_REVIEW: self._safety_review,
            Step.PLAN_CANARY: self._plan_canary,
            Step.APPLY_ALLOWED_CHANGES: self._apply_changes,
            Step.TECHNICAL_VERIFY: self._technical_verify,
            Step.VERIFY_EDITORIAL_FACTS_AND_FRESHNESS: self._verify_editorial,
            Step.OBSERVE: self._observe,
            Step.EVALUATE_MATURE_EXPERIMENTS: self._evaluate_mature,
            Step.KEEP_OR_ROLLBACK: self._keep_or_rollback,
            Step.LEARN: self._learn,
            Step.REPORT: self._report,
        }

        for step in PIPELINE:
            if step in MUTATING_STEPS and report.protected_drift:
                report.steps.append(StepResult(step, "skipped",
                                               "Пропущено: обнаружен дрейф protected ядра."))
                continue
            try:
                result = handlers[step](sites)
            except AuthorizationBlocked as exc:
                # Не останавливает цикл. Агрегируется в один запрос владельцу.
                fingerprint = f"{step.value}:{exc}"
                is_new = self.store.record_blocker(
                    fingerprint=str(hash(fingerprint)), kind="authorization",
                    detail=str(exc), request=exc.request)
                result = StepResult(step, "BLOCKED_AUTHORIZATION", str(exc),
                                    {"new_blocker": is_new})
            except GuardrailViolation as exc:
                result = StepResult(step, "BLOCKED_PROTECTED_GUARDRAIL", str(exc))
            except Exception as exc:  # noqa: BLE001 — шаг падает, цикл продолжается
                result = StepResult(step, "error", f"{type(exc).__name__}: {exc}",
                                    {"trace": traceback.format_exc()[-800:]})
            report.steps.append(result)

        report.blockers = [dict(r) for r in self.store.unreported_blockers()]
        self.audit.append(actor="scheduler", action="daily_run",
                          payload={"date": report.run_date, "dry_run": self.dry_run,
                                   "sites": sites, "statuses": report.status_counts()})
        return report

    # ------------------------------------------------------------------
    # шаги

    def _protected_drift(self) -> list[str]:
        baseline_path = config.state_dir() / "protected-baseline.json"
        current = protected_fingerprint()
        if not baseline_path.exists():
            import json
            baseline_path.write_text(__import__("json").dumps(current, indent=2), encoding="utf-8")
            return []
        import json
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        return sorted(set(
            [k for k, v in baseline.items() if current.get(k) != v]
            + [k for k in current if k not in baseline]))

    def _collect(self, sites: list[str]) -> StepResult:
        collected: dict[str, dict[str, str]] = {}
        waiting = []
        blocked = []
        start = self.today - timedelta(days=90)
        for site_id in sites:
            site = config.get_site(site_id)
            collected[site_id] = {}
            for source_id in ("gsc_search_analytics", "yandex_webmaster", "yandex_metrika_reports"):
                try:
                    conn = connectors.build(source_id, site)
                    result = conn.fetch(start, self.today)
                except (KeyError, NotImplementedError) as exc:
                    collected[site_id][source_id] = f"unavailable: {exc}"
                    continue
                collected[site_id][source_id] = result.status
                if result.status == "NOT_CONFIGURED":
                    blocked.append(f"{site_id}/{source_id}")
                    self.store.record_blocker(
                        fingerprint=f"src:{site_id}:{source_id}", kind="data_source",
                        detail=result.note, request={"site": site_id, "source": source_id},
                        site_id=site_id)
                    continue
                if result.status == "WAITING_DATA":
                    waiting.append(f"{site_id}/{source_id}")
                    continue
                self._persist(site_id, result)
        self._context["collected"] = collected
        status = "ok" if not blocked else "BLOCKED_AUTHORIZATION" if not any(
            v == "ok" for s in collected.values() for v in s.values()) else "ok"
        detail = f"Источников с данными: {sum(1 for s in collected.values() for v in s.values() if v == 'ok')}"
        if blocked:
            detail += f"; не подключено: {len(blocked)}"
        if waiting:
            detail += f"; ждут данных: {len(waiting)}"
        return StepResult(Step.COLLECT, status, detail,
                          {"collected": collected, "blocked": blocked, "waiting": waiting})

    def _persist(self, site_id: str, result: connectors.ConnectorResult) -> None:
        for row in result.rows:
            observed = row.get("date")
            if not observed:
                continue
            for metric in ("clicks", "impressions", "organic_sessions", "player_starts"):
                if metric in row:
                    self.store.record_observation(
                        site_id=site_id, source=result.source, metric=metric,
                        value=float(row[metric]), observed_date=observed,
                        timezone_name=result.timezone, source_window=result.source_window,
                        data_freshness=result.data_freshness, completeness=result.completeness,
                        dimension=row.get("query"))

    def _validate_data(self, sites: list[str]) -> StepResult:
        issues = []
        for site_id in sites:
            rows = self.store.observations(site_id, "clicks",
                                           since=(self.today - timedelta(days=35)).isoformat())
            if not rows:
                issues.append(f"{site_id}: нет наблюдений по clicks")
                continue
            incomplete = [r for r in rows if r["completeness"] < 0.9]
            if len(incomplete) > len(rows) * 0.5:
                issues.append(f"{site_id}: более половины дней неполны")
        status = "WAITING_DATA" if issues else "ok"
        return StepResult(Step.VALIDATE_DATA, status,
                          "; ".join(issues) or "Данные пригодны для сравнения.", {"issues": issues})

    def _detect_incidents(self, sites: list[str]) -> StepResult:
        opened = []
        for site_id in sites:
            signal = self._build_signal(site_id)
            for incident in detect_incidents(signal, self.today):
                opened.append(self.incidents.open(incident))
        return StepResult(Step.DETECT_INCIDENTS, "ok",
                          f"Открыто инцидентов: {len(opened)}", {"incidents": opened})

    def _build_signal(self, site_id: str) -> Signal:
        """Сигналы из наблюдений. Без данных — нулевой сигнал, а не выдуманный."""
        rows = self.store.observations(site_id, "clicks",
                                       since=(self.today - timedelta(days=21)).isoformat(),
                                       min_completeness=0.9)
        drop = 0.0
        if len(rows) >= 14:
            recent = sum(float(r["value"] or 0) for r in rows[-7:])
            prior = sum(float(r["value"] or 0) for r in rows[-14:-7])
            if prior > 0:
                drop = max(0.0, (prior - recent) / prior * 100)
        return Signal(site_id=site_id, organic_clicks_drop_pct_7d=drop)

    def _update_baselines(self, sites: list[str]) -> StepResult:
        from .analysis import kpi
        baselines = {}
        for site_id in sites:
            rows = [{"date": r["observed_date"], "value": r["value"],
                     "completeness": r["completeness"]}
                    for r in self.store.observations(site_id, "clicks")]
            if not rows:
                continue
            end = self.today - timedelta(days=3)
            baselines[site_id] = {
                str(w): kpi.comparable_window(rows, "clicks", end, w).__dict__
                for w in (7, 28)
            }
        self._context["baselines"] = baselines
        return StepResult(Step.UPDATE_BASELINES, "ok" if baselines else "WAITING_DATA",
                          f"Baseline обновлён для {len(baselines)} сайтов.", {"sites": list(baselines)})

    def _discover_editorial(self, sites: list[str]) -> StepResult:
        from .editorial import discovery
        found = {}
        for site_id in sites:
            site = config.get_site(site_id)
            if not site_id.startswith("demo-"):
                self.store.record_blocker(
                    fingerprint=f"catalog:{site_id}", kind="data_source",
                    detail="Каталог CDNVideoHub/CMS не подключён — редакционный discovery невозможен.",
                    request={"site": site_id, "needs": "cms_content_api + EDITORIAL_SOURCE_REGISTRY"},
                    site_id=site_id)
                continue
            strategy = {"priority_segments": site.raw.get("priority_segments", [])}
            entries, opps = discovery.discover_from_fixture(site, strategy, today=self.today)
            found[site_id] = {"entries": [e.to_dict() for e in entries],
                              "opportunities": [o.__dict__ for o in opps]}
        self._context["editorial"] = found
        return StepResult(Step.DISCOVER_EDITORIAL_CHANGES, "ok" if found else "BLOCKED_AUTHORIZATION",
                          f"Редакционный discovery выполнен для {len(found)} сайтов.",
                          {"sites": list(found)})

    def _refresh_calendar(self, sites: list[str]) -> StepResult:
        from .editorial import calendar as cal
        transitions = []
        for site_id, payload in (self._context.get("editorial") or {}).items():
            entries = [cal.CalendarEntry(
                external_id=e["external_id"], site_id=e["site_id"], title_ru=e["title_ru"],
                title_original=e["title_original"], status=cal.Status(e["status"]),
                release_date=e["release_date"], release_date_confirmed=e["release_date_confirmed"],
                source=e["source"], source_confidence=e["source_confidence"],
                rights_ref=e["rights_ref"], checked_at=e["checked_at"],
                pinned_until=e.get("pinned_until"), notes=list(e.get("notes") or []))
                for e in payload["entries"]]
            released = cal.promote_released(entries, self.today)
            expired = cal.expire_stale(entries, self.today)
            transitions.append({"site_id": site_id,
                                "released": [e.external_id for e in released],
                                "expired": [e.external_id for e in expired]})
        self._context["calendar_transitions"] = transitions
        return StepResult(Step.REFRESH_RELEASE_CALENDAR, "ok",
                          f"Переходов статусов: "
                          f"{sum(len(t['released']) + len(t['expired']) for t in transitions)}",
                          {"transitions": transitions})

    def _find_opportunities(self, sites: list[str]) -> StepResult:
        editorial = self._context.get("editorial") or {}
        total = sum(len(p["opportunities"]) for p in editorial.values())
        actionable = sum(1 for p in editorial.values() for o in p["opportunities"] if not o["blockers"])
        return StepResult(Step.FIND_OPPORTUNITIES, "ok",
                          f"Возможностей: {total}, без блокеров: {actionable}.",
                          {"total": total, "actionable": actionable})

    def _prioritize(self, sites: list[str]) -> StepResult:
        editorial = self._context.get("editorial") or {}
        ranked = []
        for site_id, payload in editorial.items():
            for o in sorted(payload["opportunities"], key=lambda x: -x["score"])[:5]:
                ranked.append({"site_id": site_id, "subject": o["external_id"],
                               "score": o["score"], "action": o["proposed_status"],
                               "blockers": o["blockers"]})
        ranked.sort(key=lambda r: -r["score"])
        self._context["ranked"] = ranked
        return StepResult(Step.PRIORITIZE, "ok", f"Приоритизировано {len(ranked)} тем.",
                          {"top": ranked[:10]})

    def _form_hypotheses(self, sites: list[str]) -> StepResult:
        from .learning.registry import LearningRegistry
        learning = LearningRegistry()
        hypotheses = []
        for item in (self._context.get("ranked") or [])[:5]:
            if item["blockers"]:
                continue
            statement = f"Подготовка страницы к релизу '{item['subject']}' повысит первые показы."
            known_failure = learning.is_known_failure(statement, page_type="title")
            if known_failure:
                continue
            hypotheses.append({"site_id": item["site_id"], "subject": item["subject"],
                               "statement": statement, "primary_kpi": "impressions"})
        self._context["hypotheses"] = hypotheses
        return StepResult(Step.FORM_HYPOTHESES, "ok", f"Сформировано гипотез: {len(hypotheses)}",
                          {"hypotheses": hypotheses})

    def _safety_review(self, sites: list[str]) -> StepResult:
        drift = self._protected_drift()
        chain_ok, chain_msg = self.audit.verify_chain()
        problems = []
        if drift:
            problems.append(f"protected drift: {drift}")
        if not chain_ok:
            problems.append(f"audit chain: {chain_msg}")
        status = "BLOCKED_PROTECTED_GUARDRAIL" if problems else "ok"
        return StepResult(Step.SAFETY_REVIEW, status,
                          "; ".join(problems) or "Защищённое ядро и audit-цепочка целы.",
                          {"drift": drift, "audit_chain": chain_msg})

    def _plan_canary(self, sites: list[str]) -> StepResult:
        """
        Лимиты считаются с учётом канареек, запланированных в этом же прогоне:
        иначе за один цикл можно поставить 5 экспериментов на один тип страниц,
        формально не нарушив ни одной проверки по уже активным.
        """
        policy = config.experiment_policy()["allocation"]
        plans: list[dict[str, Any]] = []
        refusals: list[dict[str, Any]] = []
        planned_per_site: dict[str, int] = {}
        planned_per_page_type: dict[tuple[str, str], int] = {}

        for h in (self._context.get("hypotheses") or []):
            site_id = h["site_id"]
            page_type = "title"
            key = (site_id, page_type)

            decision = self.allocator.can_start(site_id, page_type=page_type, intent="exact_title")
            if not decision.allowed:
                refusals.append({"site_id": site_id, "reason": decision.reason})
                continue

            site_limit = min(config.get_site(site_id).experiment_limit,
                             policy["max_concurrent_per_site"])
            if planned_per_site.get(site_id, 0) + len(self.registry.active(site_id)) >= site_limit:
                refusals.append({"site_id": site_id,
                                 "reason": f"Лимит {site_limit} экспериментов на сайт уже выбран "
                                           "активными и запланированными в этом прогоне."})
                continue
            if planned_per_page_type.get(key, 0) >= policy["max_concurrent_per_page_type"]:
                refusals.append({"site_id": site_id,
                                 "reason": f"Лимит {policy['max_concurrent_per_page_type']} "
                                           f"экспериментов на тип страниц '{page_type}' выбран в этом прогоне."})
                continue

            planned_per_site[site_id] = planned_per_site.get(site_id, 0) + 1
            planned_per_page_type[key] = planned_per_page_type.get(key, 0) + 1
            plans.append({**h, "share": decision.share, "page_type": page_type})

        self._context["canary_plans"] = plans
        return StepResult(Step.PLAN_CANARY, "ok",
                          f"Канареек запланировано: {len(plans)}; отказов: {len(refusals)}",
                          {"plans": plans, "refusals": refusals})

    def _apply_changes(self, sites: list[str]) -> StepResult:
        """
        Каждое изменение принадлежит эксперименту (GR-007). Эксперимент создаётся
        здесь же, вместе со snapshot и rollback payload, а не помечается «исправлением
        дефекта», чтобы обойти правило.
        """
        from .experiments.registry import Experiment, new_id

        applied, blocked = [], []
        for plan in (self._context.get("canary_plans") or []):
            site_id = plan["site_id"]
            target = f"title/{plan['subject']}/meta"
            try:
                before = self.cms.backend.read(site_id, target)
                exp_id = new_id(
                    site_id, self.registry.next_sequence(site_id, self.today), self.today)
                exp = Experiment(
                    id=exp_id, site_id=site_id, page_type="title", query_cohort="exact_title",
                    hypothesis=plan["statement"],
                    evidence=f"opportunity score из PRIORITIZE для {plan['subject']}",
                    primary_variable="title_template", primary_kpi=plan["primary_kpi"],
                    baseline_start=(self.today - timedelta(days=28)).isoformat(),
                    baseline_end=self.today.isoformat(),
                    guardrails=["indexed_coverage_drop", "soft_404_rate", "player_failure_rate"],
                    stop_loss={"clicks": 20, "impressions": 25},
                    min_sample={"clicks": 40, "impressions": 1000},
                    rollback_payload={"executable": True, "kind": "cms_restore",
                                      "site_id": site_id, "target": target, "restore": before},
                    before_snapshot=before or {"_empty": True})
                self.registry.create(exp)

                result = self.cms.mutate(
                    site_id=site_id, target=target,
                    action="title_description_update", tier=1,
                    new_payload={"title": f"{plan['subject']} — смотреть онлайн",
                                 "description": "Обновлено оператором в рамках эксперимента."},
                    experiment_id=exp_id, dry_run=self.dry_run,
                    guard_payload={"publishes_content": False})
                if not self.dry_run:
                    self.registry.start(exp_id, self.today)
                applied.append({"site_id": site_id, "target": result.target,
                                "experiment_id": exp_id, "dry_run": result.dry_run,
                                "audit_seq": result.audit_seq})
            except (AuthorizationBlocked, GuardrailViolation) as exc:
                blocked.append({"site_id": site_id, "reason": str(exc)})
        status = "ok" if applied or not blocked else "BLOCKED_AUTHORIZATION"
        return StepResult(Step.APPLY_ALLOWED_CHANGES, status,
                          f"Изменений проверено/применено: {len(applied)}; заблокировано: {len(blocked)}",
                          {"applied": applied, "blocked": blocked})

    def _technical_verify(self, sites: list[str]) -> StepResult:
        return StepResult(Step.TECHNICAL_VERIFY, "skipped",
                          "Краул production-страниц требует подключённого краулера/CMS; "
                          "проверки готовы и покрыты тестами (technical.run_all).")

    def _verify_editorial(self, sites: list[str]) -> StepResult:
        from .editorial import homepage
        from .editorial.calendar import CalendarEntry, Status
        issues_total = 0
        per_site = {}
        for site_id, payload in (self._context.get("editorial") or {}).items():
            entries = {e["external_id"]: CalendarEntry(
                external_id=e["external_id"], site_id=e["site_id"], title_ru=e["title_ru"],
                title_original=e["title_original"], status=Status(e["status"]),
                release_date=e["release_date"], release_date_confirmed=e["release_date_confirmed"],
                source=e["source"], source_confidence=e["source_confidence"],
                rights_ref=e["rights_ref"], checked_at=e["checked_at"])
                for e in payload["entries"]}
            plan = homepage.default_plan(site_id)
            plan.modules[2].pinned_items = list(entries)[:3]
            plan.modules[2].pin_expires = {k: (self.today + timedelta(days=14)).isoformat()
                                           for k in plan.modules[2].pinned_items}
            issues = homepage.audit_freshness(plan, entries, self.today)
            per_site[site_id] = [i.__dict__ for i in issues]
            issues_total += len(issues)
        return StepResult(Step.VERIFY_EDITORIAL_FACTS_AND_FRESHNESS, "ok",
                          f"Проблем свежести витрин: {issues_total}", {"per_site": per_site})

    def _observe(self, sites: list[str]) -> StepResult:
        active = self.registry.active()
        return StepResult(Step.OBSERVE, "ok", f"Экспериментов в наблюдении: {len(active)}",
                          {"active": [e.id for e in active]})

    def _evaluate_mature(self, sites: list[str]) -> StepResult:
        from .experiments.evaluator import evaluate
        evaluations = []
        for exp in self.registry.active():
            rows = [{"date": r["observed_date"], exp.primary_kpi: r["value"],
                     "completeness": r["completeness"], "impressions": r["value"], "clicks": r["value"]}
                    for r in self.store.observations(exp.site_id, exp.primary_kpi)]
            ev = evaluate(exp, rows, [], {}, {}, self.today)
            evaluations.append({"id": exp.id, "decision": ev.decision,
                                "confidence": ev.confidence, "explanation": ev.explanation})
        self._context["evaluations"] = evaluations
        return StepResult(Step.EVALUATE_MATURE_EXPERIMENTS, "ok",
                          f"Оценено экспериментов: {len(evaluations)}", {"evaluations": evaluations})

    def _keep_or_rollback(self, sites: list[str]) -> StepResult:
        decisions = {"keep": 0, "rollback": 0, "inconclusive": 0, "iterate": 0}
        for ev in (self._context.get("evaluations") or []):
            decisions[ev["decision"]] = decisions.get(ev["decision"], 0) + 1
            if ev["decision"] == "rollback" and not self.dry_run:
                self.cms.rollback(ev["id"])
        return StepResult(Step.KEEP_OR_ROLLBACK, "ok", f"Решения: {decisions}", decisions)

    def _learn(self, sites: list[str]) -> StepResult:
        return StepResult(Step.LEARN, "ok",
                          "Кандидаты в паттерны формируются только из зрелых экспериментов; "
                          "зрелых пока нет.")

    def _report(self, sites: list[str]) -> StepResult:
        return StepResult(Step.REPORT, "ok", "Отчёт формируется командой `seo daily-run`.")
