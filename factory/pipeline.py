"""Оркестрация задания по state machine.

Каждый шаг идемпотентен, имеет timeout и точный статус отказа. Ретраятся только
явно временные ошибки. Успешный staging не открывает production автоматически.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from factory import audit, build as build_mod, inventory, licensing, validation, verify as verify_mod
from factory.errors import (
    BlockedAuthorization, BlockedAccess, FactoryError, QaFailed,
)
from factory.locks import LockBusy, site_lock
from factory.paths import PATHS
from factory.report import build_result, write_result
from factory.retry import DEFAULT_POLICY, run_with_retry
from factory.seo.report import combine
from factory.state import JobState
from factory.targets import build_target


@dataclass
class RunOutcome:
    status: str
    job_id: str
    site_id: str
    environment: str
    result_path: Path | None = None
    base_url: str | None = None
    checks: list[dict] = field(default_factory=list)
    blockers: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def run_job(site_id: str, *, environment: str | None = None, job_id: str | None = None,
            action: str = "create", dry_run: bool = False, skip_browser: bool = False,
            allow_production: bool = False) -> RunOutcome:
    started = _now()
    steps: list[dict] = []
    checks: list[dict] = []
    mutations: list[dict] = []
    notes: list[str] = []
    artifacts: list[str] = []
    backup: dict | None = None
    build_id = release_id = previous_release = None
    base_url = None
    seo_summary = None

    def step(step_id: str, status: str = "ok", *, detail: str = "", mutation: bool = False, exit_code: int | None = 0) -> None:
        steps.append({"id": step_id, "status": status, "started_at": _now(), "finished_at": _now(),
                      "exit_code": exit_code, "detail": detail, "mutation": mutation})

    validation_result = validation.validate(site_id)
    package = validation_result.package or {}
    env = environment or package.get("environment") or "staging"
    # Идентификатор уникален: секундной метки недостаточно, два запуска в одну
    # секунду получили бы один job_id и второй упал бы на переходе из DONE.
    generated = f"{site_id}-{action}-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{uuid.uuid4().hex[:6]}"
    job = JobState.load_or_create(job_id or generated, site_id, env, action)

    # Семантика «ровно один раз»: повторный запуск завершённого job'а возвращает
    # сохранённый результат, а не выполняет работу заново.
    if job.terminal:
        stored = PATHS.artifacts / "jobs" / site_id / f"{job.job_id}.json"
        if stored.exists():
            data = json.loads(stored.read_text(encoding="utf-8"))
            return RunOutcome(data["status"], job.job_id, site_id, env, stored, job.base_url,
                              data.get("checks", []), data.get("blockers", []),
                              data.get("notes", []) + ["Задание уже завершено: возвращён сохранённый результат."])

    def finish(status: str, blockers: list[dict]) -> RunOutcome:
        if job.status != status and job.can_transition(status):
            job.transition(status, blockers=blockers)
        result = build_result(job_id=job.job_id, site_id=site_id, environment=env, status=status,
                              started_at=started, requested_action=action, steps=steps, checks=checks,
                              artifacts=artifacts, mutations=mutations, blockers=blockers, backup=backup,
                              build_id=build_id, release_id=release_id, previous_release_id=previous_release,
                              seo_summary=seo_summary, notes=notes)
        path = write_result(result)
        audit.record(job_id=job.job_id, site_id=site_id, environment=env, action=action,
                     target=package.get("target_ref", "-"), exit_code=0 if status in ("DONE", "READY") else 1,
                     output=f"status={status}", mutation=bool(mutations),
                     extra={"checks": [c["id"] for c in checks], "blockers": blockers})
        return RunOutcome(status, job.job_id, site_id, env, path, base_url, checks, blockers, notes)

    try:
        with site_lock(site_id, env):
            # ---------------------------------------------------------- VALIDATING
            if job.status == "RECEIVED":
                job.transition("VALIDATING")
            if not validation_result.ok:
                step("validate", "blocked", detail=validation_result.status, exit_code=1)
                return finish(validation_result.status, [b.as_dict() for b in validation_result.blockers])
            step("validate", detail="Пакет прошёл схему и семантику")
            notes.extend(validation_result.warnings)
            job.transition("READY")

            # ---------------------------------------------------------- BUILDING
            job.transition("BUILDING")
            built = build_mod.build(site_id, environment=env)
            build_id = built.build_id
            job.build_id = build_id
            step("build", detail=f"build_id={build_id}, маршрутов {built.routes}")
            artifacts.append(f"artifacts/build/{site_id}/{build_id}/report.json")
            if built.skipped:
                notes.append(f"Материалов снято с публикации: {len(built.skipped)} (см. build report).")
            job.transition("BUILT")

            # ---------------------------------------------------------- целевое окружение
            target_conf = inventory.target(package["target_ref"])
            target = build_target(target_conf, package)

            if env == "production":
                job.transition("AUTHORIZATION_CHECK")
                if not package.get("production_authorized"):
                    step("authorization", "blocked", detail="production_authorized=false", exit_code=1)
                    return finish("BLOCKED_AUTHORIZATION", [BlockedAuthorization(
                        "Production не авторизован в manifest.", field="production_authorized",
                        required_input="production_authorized: true и заполненные authorized_by/authorized_at",
                        blocks_stage="PRODUCTION_DEPLOY").as_blocker()])
                if not allow_production:
                    step("authorization", "blocked", detail="Нет явного подтверждения оператора (--allow-production)", exit_code=1)
                    return finish("BLOCKED_AUTHORIZATION", [BlockedAuthorization(
                        "Production-выкат требует явного подтверждения оператора.", field="cli",
                        required_input="Флаг --allow-production у команды deploy",
                        blocks_stage="PRODUCTION_DEPLOY").as_blocker()])
                license_result = licensing.require_license(package["domain"], license_ref=package.get("dle_license_ref"), environment="production")
                step("license", detail=f"Лицензия {license_result.license_ref} покрывает {license_result.registrable_domain}")
                if not target_conf.get("production_capable"):
                    return finish("BLOCKED_ACCESS", [BlockedAccess(
                        f"Цель «{target_conf.get('ref')}» не пригодна для production.", field="target_ref",
                        required_input="production_capable: true у проверенной цели",
                        blocks_stage="PRODUCTION_DEPLOY").as_blocker()])
                job.transition("PRODUCTION_DEPLOY")
            else:
                job.transition("STAGING_DEPLOY")

            # ---------------------------------------------------------- деплой
            if env != "production":
                notes.append("Staging не является разрешением на production: нужны production_authorized, лицензия DLE и подтверждение оператора.")

            if dry_run:
                plan = target.plan(built.output, build_id)
                step("deploy", "skipped", detail=f"dry-run: шагов {len(plan.steps)}, мутаций 0")
                notes.append("Выполнен dry-run: инфраструктура не менялась.")
                return finish("BUILT", [])

            def do_deploy():
                return target.deploy(built.output, build_id, dry_run=False)

            deploy_result = run_with_retry(do_deploy, policy=DEFAULT_POLICY,
                                           on_retry=lambda attempt, exc, delay: notes.append(
                                               f"Повтор деплоя #{attempt} через {delay:.1f}s: {exc}"))
            release_id = deploy_result.release_id
            previous_release = deploy_result.previous_release_id
            base_url = deploy_result.base_url
            backup = deploy_result.backup
            steps.extend(deploy_result.steps)
            mutations.extend(deploy_result.mutations)
            job.release_id = release_id
            job.base_url = base_url
            job.checkpoint_at("deployed")

            # проверка восстановимости бэкапа — наличие файла доказательством не считается
            if backup and hasattr(target, "restore"):
                probe = PATHS.var / "restore-probe" / f"{site_id}-{build_id}"
                restored = target.restore(backup["ref"], probe)
                backup["restore_verified"] = bool(restored)
                backup["verified_at"] = _now()
                step("restore_test", "ok" if restored else "failed",
                     detail=f"Восстановление бэкапа в {probe}: {'подтверждено' if restored else 'НЕ подтверждено'}",
                     exit_code=0 if restored else 1)

            # ---------------------------------------------------------- QA
            auth = target.staging_credentials() if hasattr(target, "staging_credentials") and env != "production" else ""
            if env != "production":
                job.transition("STAGING_QA")
            qa_checks, qa_reports = verify_mod.verify(site_id, package, built.output, base_url,
                                                      auth=auth, environment=env, skip_browser=skip_browser)
            checks.extend(c.as_dict() for c in qa_checks)
            artifacts.extend(c.artifact for c in qa_checks)
            seo_summary_obj = combine(site_id, qa_reports)
            artifacts.append(f"artifacts/seo/{site_id}/seo-report.json")
            lint_counts = next((r.counts for r in qa_reports if r.name == "seo-lint"), {})
            crawl_counts = next((r.counts for r in qa_reports if r.name == "seo-crawl"), {})
            seo_summary = {
                "pages_total": int(lint_counts.get("routes", 0)),
                "indexable": int(lint_counts.get("indexable", 0)),
                "noindex": int(lint_counts.get("routes", 0)) - int(lint_counts.get("indexable", 0)),
                "in_sitemap": int(lint_counts.get("in_sitemap", 0)),
                "duplicate_titles": sum(1 for r in qa_reports for f in r.findings if f.check == "duplicate-title"),
                "duplicate_descriptions": sum(1 for r in qa_reports for f in r.findings if f.check == "duplicate-description"),
                "redirect_chains": sum(1 for r in qa_reports for f in r.findings if f.check == "redirect"),
                "orphan_pages": sum(1 for r in qa_reports for f in r.findings if f.check == "orphan"),
                "soft_404": sum(1 for r in qa_reports for f in r.findings if f.check == "soft404"),
                "broken_links": sum(1 for r in qa_reports for f in r.findings if f.check == "broken-link"),
                "jsonld_errors": sum(1 for r in qa_reports for f in r.findings if f.check == "jsonld"),
            }

            skipped = [c for c in qa_checks if not c.passed and c.severity != "critical"]
            for check in skipped:
                notes.append(f"Проверка {check.id} не выполнялась ({check.counts.get('status', 'skipped')}): приёмка неполная, "
                             f"результат нельзя считать полной приёмкой сайта.")
            failed = [c for c in qa_checks if not c.passed and c.severity == "critical"]
            seo_failed = [c for c in failed if c.id.startswith("seo-")]
            if seo_failed:
                if package["rollback_policy"]["auto_rollback_on_smoke_failure"] and env == "production":
                    target.rollback()
                    return finish("ROLLED_BACK", [{"status": "BLOCKED_SEO", "field": c.id,
                                                   "reason": "Критические SEO-нарушения после выката",
                                                   "required_input": "Исправление шаблонов/матрицы",
                                                   "blocks_stage": "PRODUCTION_SMOKE"} for c in seo_failed])
                return finish("BLOCKED_SEO", [{"status": "BLOCKED_SEO", "field": c.id,
                                               "reason": f"Проверка {c.id} не пройдена",
                                               "required_input": "Исправление шаблонов, матрицы или данных пакета",
                                               "blocks_stage": "STAGING_QA"} for c in seo_failed])
            if failed:
                return finish("QA_FAILED", [{"status": "QA_FAILED", "field": c.id,
                                             "reason": f"Проверка {c.id} не пройдена (exit {c.exit_code})",
                                             "required_input": f"См. артефакт {c.artifact}",
                                             "blocks_stage": "STAGING_QA"} for c in failed])

            if env == "production":
                job.transition("PRODUCTION_SMOKE")
                ok, detail = target.health()
                step("production_smoke", "ok" if ok else "failed", detail=detail, exit_code=0 if ok else 1)
                if not ok:
                    target.rollback()
                    return finish("ROLLED_BACK", [{"status": "DEPLOY_FAILED", "field": "production_smoke",
                                                   "reason": detail, "required_input": "Рабочая сборка",
                                                   "blocks_stage": "PRODUCTION_SMOKE"}])
                job.transition("MONITORING")
                step("monitoring", detail=f"health endpoint: {package['monitoring_policy']['health_endpoint']}")
                return finish("DONE", [])

            return finish("DONE", [])

    except LockBusy as exc:
        step("lock", "blocked", detail=str(exc), exit_code=1)
        return finish("QUARANTINED", [{"status": "QUARANTINED", "field": "lock",
                                       "reason": str(exc), "required_input": "Дождись завершения параллельного задания",
                                       "blocks_stage": job.status}])
    except FactoryError as exc:
        step("pipeline", "failed", detail=exc.reason, exit_code=1)
        return finish(exc.status, [exc.as_blocker()])
