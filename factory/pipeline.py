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

from factory import (audit, blueprint, build as build_mod, inventory, knowledge, licensing,
                     validation, verify as verify_mod)
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
    #: Задание следует вернуть в очередь, а не считать окончательно проваленным.
    requeue: bool = False


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
    package_env = package.get("environment") or "staging"
    # Флаг CLI не может подменить окружение пакета: иначе production-пакет
    # проходил бы по staging-ветке (без лицензии, авторизации и smoke), а адаптер
    # всё равно мутировал бы боевой хост.
    env_mismatch = bool(environment) and environment != package_env
    env = package_env
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
        if job.status != status:
            if job.can_transition(status):
                job.transition(status, blockers=blockers)
            else:
                # Молча гасить невозможный переход нельзя: состояние на диске
                # разойдётся с отчётом, и `factory status` покажет несуществующее задание.
                notes.append(f"Внимание: переход {job.status} → {status} недопустим; задание помечено QUARANTINED.")
                if job.can_transition("QUARANTINED"):
                    job.transition("QUARANTINED", blockers=blockers)
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
            # A: продолжение прерванного задания. Возобновление с середины конвейера
            # не поддерживается: незавершённый job переводится в карантин с причиной,
            # а не роняет worker недопустимым переходом.
            if job.status not in ("RECEIVED", "VALIDATING"):
                step("resume", "blocked", detail=f"Задание прервано в состоянии {job.status}", exit_code=1)
                return finish("QUARANTINED", [{
                    "status": "QUARANTINED", "field": "job.status",
                    "reason": f"Задание прервано в промежуточном состоянии {job.status}; продолжение с середины конвейера не поддерживается.",
                    "required_input": "Запусти задание заново с новым job_id после устранения причины остановки",
                    "blocks_stage": job.status,
                }])
            if job.status == "RECEIVED":
                job.transition("VALIDATING")

            if env_mismatch:
                step("environment", "blocked", detail=f"--environment={environment} против пакета {package_env}", exit_code=1)
                return finish("BLOCKED_INPUT", [{
                    "status": "BLOCKED_INPUT", "field": "environment",
                    "reason": f"Флаг --environment={environment} противоречит пакету ({package_env}).",
                    "required_input": "Приведи environment в пакете в соответствие или убери флаг",
                    "blocks_stage": "VALIDATING",
                }])

            frozen_ok, freeze_problems = knowledge.verify()
            if not frozen_ok:
                step("knowledge_freeze", "blocked", detail="; ".join(freeze_problems[:3]), exit_code=1)
                return finish("BLOCKED_INPUT", [{
                    "status": "BLOCKED_INPUT", "field": "knowledge/KNOWLEDGE_FREEZE.yaml",
                    "reason": "База знаний разошлась с freeze: " + "; ".join(freeze_problems[:5]),
                    "required_input": "Верни файлы к замороженному состоянию или пересобери freeze через /research-freeze",
                    "blocks_stage": "VALIDATING",
                }])
            step("knowledge_freeze", detail=f"freeze {knowledge.freeze_version()} цел")
            if not validation_result.ok:
                step("validate", "blocked", detail=validation_result.status, exit_code=1)
                return finish(validation_result.status, [b.as_dict() for b in validation_result.blockers])
            step("validate", detail="Пакет прошёл схему и семантику")
            notes.extend(validation_result.warnings)

            target_conf = inventory.target(package["target_ref"])

            # Авторизация и лицензия проверяются до сборки: блокер обязан называть
            # отсутствие разрешения, а не побочный эффект более позднего шага.
            if env == "production":
                if not package.get("production_authorized"):
                    step("authorization", "blocked", detail="production_authorized=false", exit_code=1)
                    return finish("BLOCKED_AUTHORIZATION", [BlockedAuthorization(
                        "Production не авторизован в manifest.", field="production_authorized",
                        required_input="production_authorized: true и заполненные authorized_by/authorized_at",
                        blocks_stage="PRODUCTION_DEPLOY").as_blocker()])
                if not allow_production:
                    step("authorization", "blocked", detail="нет флага --allow-production", exit_code=1)
                    return finish("BLOCKED_AUTHORIZATION", [BlockedAuthorization(
                        "Production-выкат требует явного подтверждения оператора.", field="cli",
                        required_input="Флаг --allow-production у команды deploy",
                        blocks_stage="PRODUCTION_DEPLOY").as_blocker()])
                license_result = licensing.require_license(package["domain"],
                                                           license_ref=package.get("dle_license_ref"),
                                                           environment="production")
                step("license", detail=f"Лицензия {license_result.license_ref} покрывает {license_result.registrable_domain}")
                if not target_conf.get("production_capable"):
                    return finish("BLOCKED_ACCESS", [BlockedAccess(
                        f"Цель «{target_conf.get('ref')}» не пригодна для production.", field="target_ref",
                        required_input="production_capable: true у проверенной цели",
                        blocks_stage="PRODUCTION_DEPLOY").as_blocker()])

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
            target = build_target(target_conf, package)

            # Цель, которая фактически ставит DLE, требует заполненного профиля путей:
            # раньше этот гейт существовал только в документации и в тестах.
            if target_conf.get("adapter") == "ssh_ansible":
                blueprint.require_ready("dle20")
                step("blueprint_profile", detail="Профиль путей DLE 20.0 заполнен")

            # ---------------------------------------------------------- деплой
            if env != "production":
                notes.append("Staging не является разрешением на production: нужны production_authorized, лицензия DLE и подтверждение оператора.")

            if dry_run:
                plan = target.plan(built.output, build_id)
                step("deploy", "skipped", detail=f"dry-run: шагов {len(plan.steps)}, мутаций 0")
                notes.append("Выполнен dry-run: инфраструктура не менялась.")
                return finish("BUILT", [])

            # Переход в деплой выполняется только для фактического выката:
            # в dry-run состояние обязано остаться на BUILT.
            if env == "production":
                job.transition("AUTHORIZATION_CHECK")
                step("authorization", detail="Авторизация, лицензия и пригодность цели подтверждены до сборки")
                job.transition("PRODUCTION_DEPLOY")
            else:
                job.transition("STAGING_DEPLOY")

            def do_deploy():
                return target.deploy(built.output, build_id, dry_run=False)

            deploy_result = run_with_retry(do_deploy, policy=DEFAULT_POLICY,
                                           on_retry=lambda attempt, exc, delay: notes.append(
                                               f"Повтор деплоя #{attempt} через {delay:.1f}s: {exc}"))
            release_id = deploy_result.release_id
            # Точка отката читается из состояния цели: значение «current до деплоя»
            # при повторном выкате того же релиза совпадает с самим релизом.
            previous_release = deploy_result.previous_release_id
            if hasattr(target, "_state"):
                previous_release = target._state().get("previous_release_id") or previous_release
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
                live_before = target.shared_digest() if hasattr(target, "shared_digest") else {}
                restored = target.restore(backup["ref"], probe)
                if restored and hasattr(target, "shared_digest"):
                    # Сравнение содержимым: бэкап снят мгновение назад, поэтому
                    # восстановленное дерево обязано совпасть с живым.
                    restored_digest = target._tree_digest(probe / "shared") if hasattr(target, "_tree_digest") else {}
                    restored = restored_digest == live_before
                backup["restore_verified"] = bool(restored)
                backup["verified_at"] = _now()
                step("restore_test", "ok" if restored else "failed",
                     detail=f"Восстановление бэкапа в {probe}: {'подтверждено' if restored else 'НЕ подтверждено'}",
                     exit_code=0 if restored else 1)
                checks.append({
                    "id": "backup-restore", "command": f"python3 -m factory deploy --site {site_id} (restore probe)",
                    "exit_code": 0 if restored else 1, "passed": bool(restored),
                    "artifact": str(probe.relative_to(PATHS.root)) if probe.exists() else backup["ref"],
                    "counts": {"archive": backup["ref"]}, "severity": "critical",
                })
                if not restored:
                    return finish("DEPLOY_FAILED", [{
                        "status": "DEPLOY_FAILED", "field": "backup.restore_verified",
                        "reason": "Восстановление бэкапа не подтверждено: наличие архива доказательством не считается.",
                        "required_input": "Работоспособный бэкап и доступ к нему",
                        "blocks_stage": "STAGING_DEPLOY",
                    }])

            # ---------------------------------------------------------- QA
            auth = target.staging_credentials() if hasattr(target, "staging_credentials") and env != "production" else ""
            if env != "production":
                job.transition("STAGING_QA")
            qa_checks, qa_reports = verify_mod.verify(site_id, package, built.output, base_url,
                                                      auth=auth, environment=env, skip_browser=skip_browser,
                                                      job_id=job.job_id)
            checks.extend(c.as_dict() for c in qa_checks)
            artifacts.extend(c.artifact for c in qa_checks)
            seo_dir = PATHS.artifact_dir("seo", site_id, job.job_id)
            combine(site_id, qa_reports, seo_dir)
            artifacts.append(str(seo_dir.relative_to(PATHS.root) / "seo-report.json"))
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

            non_critical_failures = [c for c in qa_checks if not c.passed and c.severity != "critical"]
            for check in non_critical_failures:
                status = check.counts.get("status")
                if status in ("skipped", "unavailable"):
                    notes.append(f"Проверка {check.id} не выполнялась ({status}): приёмка неполная, "
                                 f"результат нельзя считать полной приёмкой сайта.")
                else:
                    notes.append(f"Проверка {check.id} нашла замечания уровня major (exit {check.exit_code}); "
                                 f"см. артефакт {check.artifact}.")
            failed = [c for c in qa_checks if not c.passed and c.severity == "critical"]
            seo_failed = [c for c in failed if c.id.startswith("seo-")]
            def record_rollback(reason: str) -> None:
                """Откат — тоже мутация: его шаги обязаны попасть в отчёт."""
                nonlocal release_id, previous_release
                rollback_result = target.rollback()
                steps.extend(rollback_result.steps)
                mutations.extend(rollback_result.mutations)
                release_id = rollback_result.release_id
                previous_release = rollback_result.previous_release_id
                notes.append(f"Выполнен откат: {reason}. На цели релиз {release_id}.")

            if seo_failed:
                if package["rollback_policy"]["auto_rollback_on_smoke_failure"] and env == "production":
                    record_rollback("критические SEO-нарушения после выката")
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
                    record_rollback(f"production smoke не пройден: {detail}")
                    return finish("ROLLED_BACK", [{"status": "DEPLOY_FAILED", "field": "production_smoke",
                                                   "reason": detail, "required_input": "Рабочая сборка",
                                                   "blocks_stage": "PRODUCTION_SMOKE"}])
                job.transition("MONITORING")
                step("monitoring", detail=f"health endpoint: {package['monitoring_policy']['health_endpoint']}")
                return finish("DONE", [])

            return finish("DONE", [])

    except LockBusy as exc:
        # Гонка двух worker'ов — штатная ситуация: задание возвращается в очередь,
        # а не выводится из обработки навсегда.
        step("lock", "blocked", detail=str(exc), exit_code=1)
        outcome = finish("QUARANTINED", [{"status": "QUARANTINED", "field": "lock",
                                          "reason": str(exc),
                                          "required_input": "Повторить после освобождения блокировки",
                                          "blocks_stage": job.status}])
        outcome.requeue = True
        return outcome
    except FactoryError as exc:
        step("pipeline", "failed", detail=exc.reason, exit_code=1)
        return finish(exc.status, [exc.as_blocker()])
    except Exception as exc:  # noqa: BLE001 — аварийная ветка обязана быть журналируемой
        step("pipeline", "failed", detail=f"{type(exc).__name__}: {exc}", exit_code=1)
        return finish("QUARANTINED", [{
            "status": "QUARANTINED", "field": "pipeline",
            "reason": f"Непредвиденная ошибка: {type(exc).__name__}: {exc}",
            "required_input": "Разбор по журналу var/audit/audit.jsonl и артефактам задания",
            "blocks_stage": job.status,
        }])
