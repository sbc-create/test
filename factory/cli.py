"""CLI фабрики. Единственный интерфейс изменения окружений.

Прямой ssh/scp/rsync запрещён hook'ом и permission-правилами: любые мутации идут
через эти команды, которые проверяют manifest, allowlist, авторизацию, backup и ворота.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path

from factory import audit, blueprint, inventory, knowledge, licensing, pipeline, validation
from factory import build as build_mod
from factory import queue as queue_mod
from factory import verify as verify_mod
from factory.analytics import cli as analytics_cli
from factory.errors import FactoryError
from factory.locks import LockBusy, site_lock
from factory.paths import PATHS
from factory.report import build_result, write_result
from factory.seo import crawl as crawl_mod
from factory.seo import lint as lint_mod
from factory.seo import matrix as matrix_mod
from factory.seo import render_check
from factory.seo.report import combine
from factory.state import all_jobs
from factory.targets import build_target

EXIT_OK, EXIT_FAILED, EXIT_BLOCKED = 0, 1, 2


def _print(data, as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))


def _target_for(site_id: str):
    package = validation.load_package(site_id)
    conf = inventory.target(package["target_ref"])
    return package, conf, build_target(conf, package)


def _auth_for(target, environment: str) -> str:
    if environment == "production" or not hasattr(target, "staging_credentials"):
        return ""
    return target.staging_credentials()


def _latest_build(site_id: str) -> Path:
    latest = build_mod.latest_build(site_id)
    if not latest:
        raise SystemExit("Сборки нет. Сначала выполни `python3 -m factory build --site <site_id>`.")
    return latest


# ---------------------------------------------------------------- команды

def cmd_validate(args) -> int:
    result = validation.validate(args.site)
    _print(result.as_dict(), args.json)
    if not args.json:
        print(f"site: {args.site}\nstatus: {result.status}")
        for blocker in result.blockers:
            print(f"  [{blocker.status}] {blocker.field}: {blocker.reason}\n      нужно: {blocker.required_input}")
        for warning in result.warnings:
            print(f"  [warn] {warning}")
    return EXIT_OK if result.ok else EXIT_BLOCKED


def cmd_plan(args) -> int:
    result = validation.validate(args.site)
    if not result.ok:
        _print(result.as_dict(), args.json)
        if not args.json:
            print(f"status: {result.status} — план не строится по невалидному пакету")
        return EXIT_BLOCKED
    package, conf, target = _target_for(args.site)
    build_id = build_mod.compute_build_id(args.site, package)
    plan = target.plan(PATHS.build_dir(args.site, build_id), build_id)
    payload = plan.as_dict()
    payload["mutations_applied"] = 0
    _print(payload, args.json)
    if not args.json:
        print(f"site: {args.site} | build_id: {build_id} | цель: {conf.get('ref')} ({conf.get('adapter')})")
        for step in plan.steps:
            print(f"  {step['id']:20} mutation={str(step['mutation']):5} {step['detail']}")
        print(f"мутаций в плане: {plan.mutations}; применено сейчас: 0")
    return EXIT_OK


def cmd_build(args) -> int:
    try:
        result = build_mod.build(args.site, environment=args.environment, force=args.force)
    except FactoryError as exc:
        _print({"status": exc.status, "blocker": exc.as_blocker()}, args.json)
        if not args.json:
            print(f"[{exc.status}] {exc.reason}\n нужно: {exc.required_input}")
        return EXIT_BLOCKED
    _print(result.as_dict(), args.json)
    if not args.json:
        print(f"build_id: {result.build_id}\nмаршрутов: {result.routes} | редиректов: {result.redirects}")
        print(f"по типам: {result.counts}")
        for skip in result.skipped:
            print(f"  снято с публикации: {skip['id']} — {skip['reason']}")
    return EXIT_OK


def cmd_deploy(args) -> int:
    outcome = pipeline.run_job(args.site, environment=args.environment, dry_run=args.dry_run,
                               skip_browser=args.skip_browser, allow_production=args.allow_production)
    _print({"status": outcome.status, "job_id": outcome.job_id, "base_url": outcome.base_url,
            "result": str(outcome.result_path) if outcome.result_path else None,
            "blockers": outcome.blockers, "notes": outcome.notes}, args.json)
    if not args.json:
        print(f"job: {outcome.job_id}\nstatus: {outcome.status}")
        if outcome.base_url:
            print(f"url: {outcome.base_url}")
        for check in outcome.checks:
            print(f"  {'PASS' if check['passed'] else 'FAIL'} {check['id']:20} exit={check['exit_code']} artifact={check['artifact']}")
        for blocker in outcome.blockers:
            print(f"  [{blocker['status']}] {blocker['field']}: {blocker['reason']}")
        for note in outcome.notes:
            print(f"  note: {note}")
        if outcome.result_path:
            print(f"результат задания: {outcome.result_path}")
    if outcome.status not in ("DONE", "BUILT"):
        return EXIT_BLOCKED
    # Статус DONE при непройденных проверках не должен выглядеть полным успехом.
    return EXIT_FAILED if any(not c.get("passed") for c in outcome.checks) else EXIT_OK


def cmd_verify(args) -> int:
    from factory import verify as verify_mod
    package, conf, target = _target_for(args.site)
    build_dir = _latest_build(args.site)
    base_url = args.base or target.base_url()
    auth = _auth_for(target, package["environment"])
    checks, reports = verify_mod.verify(args.site, package, build_dir, base_url, auth=auth,
                                        environment=package["environment"], skip_browser=args.skip_browser,
                                        job_id=args.job_id)
    summary = combine(args.site, reports)
    payload = {"site_id": args.site, "base_url": base_url, "passed": all(c.passed for c in checks),
               "checks": [c.as_dict() for c in checks], "seo": summary["totals"]}
    _print(payload, args.json)
    if not args.json:
        print(f"site: {args.site} | url: {base_url}")
        for check in checks:
            print(f"  {'PASS' if check.passed else 'FAIL'} {check.id:20} exit={check.exit_code} artifact={check.artifact}")
        print(f"SEO: critical={summary['totals']['critical']} major={summary['totals']['major']} minor={summary['totals']['minor']}")
    return EXIT_OK if payload["passed"] else EXIT_FAILED


def _assert_target_usable(site_id: str) -> None:
    """Цель обязана быть объявлена пригодной для окружения пакета."""
    package = validation.load_package(site_id)
    target_conf = inventory.target(package.get("target_ref", ""))
    environment = package.get("environment")
    if environment not in (target_conf.get("environments") or []):
        raise FactoryError(
            f"Цель {target_conf.get('ref')} не объявлена для окружения {environment}.")
    if environment == "production" and not target_conf.get("production_capable"):
        raise FactoryError(f"Цель {target_conf.get('ref')} не пригодна для production.")


def cmd_rollback(args) -> int:
    # Пригодность цели проверяется и на откате: иначе для будущей production-цели
    # откат оказался бы единственным путём, не спрашивающим разрешения.
    _assert_target_usable(args.site)
    """Откат — такая же мутация, как деплой: под блокировкой, с авторизацией и отчётом."""
    package, conf, target = _target_for(args.site)
    environment = package["environment"]
    if args.environment and args.environment != environment:
        print(f"--environment={args.environment} противоречит пакету ({environment}).", file=sys.stderr)
        return EXIT_BLOCKED
    if environment == "production":
        if not package.get("production_authorized"):
            print("[BLOCKED_AUTHORIZATION] Откат production требует production_authorized: true.", file=sys.stderr)
            return EXIT_BLOCKED
        if not args.allow_production:
            print("[BLOCKED_AUTHORIZATION] Откат production требует явного --allow-production.", file=sys.stderr)
            return EXIT_BLOCKED
        licensing.require_license(package["domain"], license_ref=package.get("dle_license_ref"), environment="production")

    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    job_id = f"{args.site}-rollback-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{uuid.uuid4().hex[:6]}"
    try:
        with site_lock(args.site, environment):
            result = target.rollback()
            ok, health_detail = target.health()
    except LockBusy as exc:
        print(f"[QUARANTINED] {exc}", file=sys.stderr)
        return EXIT_BLOCKED
    except FactoryError as exc:
        _print({"status": exc.status, "blocker": exc.as_blocker()}, args.json)
        if not args.json:
            print(f"[{exc.status}] {exc.reason}", file=sys.stderr)
        return EXIT_BLOCKED

    steps = list(result.steps)
    if not any(step["id"] == "post_rollback_health" for step in steps):
        steps.append({"id": "post_rollback_health", "status": "ok" if ok else "failed",
                      "started_at": started, "finished_at": started,
                      "exit_code": 0 if ok else 1, "detail": health_detail, "mutation": False})
    job_result = build_result(
        job_id=job_id, site_id=args.site, environment=environment, status="ROLLED_BACK" if ok else "DEPLOY_FAILED",
        started_at=started, requested_action="rollback", steps=steps,
        checks=[{"id": "post-rollback-health", "command": f"python3 -m factory rollback --site {args.site}",
                 "exit_code": 0 if ok else 1, "passed": ok, "artifact": "var/audit/audit.jsonl",
                 "counts": {"detail": health_detail}, "severity": "critical"}],
        artifacts=["var/audit/audit.jsonl"], mutations=result.mutations,
        release_id=result.release_id, previous_release_id=result.previous_release_id,
        notes=["Откат кода не откатывает БД: при миграции восстанавливай из бэкапа этого релиза."])
    path = write_result(job_result)
    audit.record(job_id=job_id, site_id=args.site, environment=environment, action="rollback",
                 target=package["target_ref"], exit_code=0 if ok else 1,
                 output=f"release={result.release_id} health={health_detail}", mutation=True)
    _print({"status": job_result["status"], "result": str(path), **result.as_dict()}, args.json)
    if not args.json:
        print(f"откат выполнен: current → {result.release_id} (был {result.previous_release_id})")
        for step in steps:
            print(f"  {step['id']:20} {step['status']} {step['detail'][:60]}")
        print(f"результат задания: {path}")
    return EXIT_OK if ok else EXIT_FAILED


def cmd_decommission(args) -> int:
    """Останавливает стенд и освобождает порт; каталог цели удаляется по флагу."""
    package, conf, target = _target_for(args.site)
    stopped = False
    if hasattr(target, "stop"):
        target.stop()
        stopped = True
    removed = False
    if args.purge and hasattr(target, "root") and target.root.exists():
        import shutil
        shutil.rmtree(target.root, ignore_errors=True)
        removed = True
    audit.record(job_id=f"decommission-{args.site}", site_id=args.site,
                 environment=package["environment"], action="decommission",
                 target=package["target_ref"], exit_code=0,
                 output=f"stopped={stopped} purged={removed}", mutation=True)
    payload = {"site_id": args.site, "stopped": stopped, "purged": removed}
    _print(payload, args.json)
    if not args.json:
        print(f"стенд остановлен: {stopped} | каталог цели удалён: {removed}")
    return EXIT_OK


def cmd_status(args) -> int:
    jobs = [j for j in all_jobs() if not args.site or j.site_id == args.site]
    payload = {"queue": queue_mod.counts(), "jobs": [j.as_dict() for j in jobs]}
    _print(payload, args.json)
    if not args.json:
        print(f"очередь: {payload['queue']}")
        for job in jobs:
            print(f"  {job.job_id:38} {job.site_id:14} {job.environment:10} {job.status:22} checkpoint={job.checkpoint}")
    return EXIT_OK


def cmd_resume(args) -> int:
    stale = queue_mod.requeue_stale(args.max_age)
    processed, requeued = 0, 0
    while True:
        item = queue_mod.claim()
        if not item:
            break
        outcome = pipeline.run_job(item.site_id, environment=item.environment, job_id=item.job_id,
                                   action=item.action, skip_browser=args.skip_browser)
        if getattr(outcome, "requeue", False) and item.attempts < queue_mod.MAX_ATTEMPTS:
            # Гонка за блокировку — не повод выводить валидное задание из обработки.
            queue_mod.requeue(item)
            requeued += 1
            break
        stage = "done" if outcome.status == "DONE" else ("quarantine" if outcome.status == "QUARANTINED" else "failed")
        queue_mod.finish(item, stage, detail=outcome.status)
        processed += 1
    payload = {"stale": stale, "processed": processed, "requeued": requeued, "queue": queue_mod.counts()}
    _print(payload, args.json)
    if not args.json:
        print(f"возвращено зависших: {len(stale['requeued'])} | в карантин: {len(stale['quarantined'])} "
              f"| обработано: {processed} | возвращено в очередь: {requeued} | очередь: {payload['queue']}")
    return EXIT_OK


def cmd_report(args) -> int:
    job_dir = PATHS.artifacts / "jobs" / args.site
    results = list(job_dir.glob("*.json")) if job_dir.exists() else []
    if not results:
        print(f"Результатов заданий для «{args.site}» нет.")
        return EXIT_FAILED
    # Сортировка по времени завершения: имена заданий содержат случайный суффикс,
    # и лексикографический порядок перестал совпадать с хронологическим.
    def finished(path):
        try:
            return json.loads(path.read_text(encoding="utf-8")).get("finished_at", "")
        except (OSError, json.JSONDecodeError):
            return ""
    latest = json.loads(sorted(results, key=finished)[-1].read_text(encoding="utf-8"))
    incomplete = [c for c in latest["checks"] if not c["passed"]]
    _print(latest, args.json)
    if not args.json:
        print(f"job: {latest['job_id']} | статус: {latest['status']} | commit: {latest['factory_commit'][:12]}")
        print(f"freeze: {latest.get('knowledge_freeze_version')} | build: {latest.get('build_id')} | release: {latest.get('release_id')}")
        for check in latest["checks"]:
            exit_code = check["exit_code"] if check["exit_code"] is not None else "не запускалась"
            print(f"  {'PASS' if check['passed'] else 'FAIL'} {check['id']:20} exit={exit_code} {check['artifact']}")
        for blocker in latest["blockers"]:
            print(f"  [{blocker['status']}] {blocker['field']}: {blocker['reason']}")
        # Примечания объясняют, почему при статусе DONE есть непройденные проверки.
        for note in latest.get("notes", []):
            print(f"  note: {note}")
        if incomplete:
            print(f"  ВНИМАНИЕ: приёмка неполная — не пройдено проверок: {len(incomplete)}")
    if latest["status"] not in ("DONE", "READY", "BUILT"):
        return EXIT_BLOCKED
    return EXIT_FAILED if incomplete else EXIT_OK


def cmd_queue(args) -> int:
    if args.queue_action == "enqueue":
        if not args.site:
            print("Для enqueue обязателен --site: очередь не принимает задание без сайта.", file=sys.stderr)
            return EXIT_BLOCKED
        result = validation.validate(args.site)
        if not result.ok:
            # Невалидный пакет не попадает в очередь: иначе worker всё равно вернёт блокер,
            # а задание будет числиться принятым.
            _print(result.as_dict(), args.json)
            if not args.json:
                print(f"status: {result.status} — задание не поставлено")
                for blocker in result.blockers:
                    print(f"  [{blocker.status}] {blocker.field}: {blocker.reason}")
            return EXIT_BLOCKED
        item = queue_mod.enqueue(args.site, action=args.action, environment=args.environment)
        _print(item.as_dict(), args.json)
        if not args.json:
            print(f"поставлено в очередь: {item.job_id}")
    elif args.queue_action == "list":
        payload = queue_mod.counts()
        _print(payload, args.json)
        if not args.json:
            print(payload)
    return EXIT_OK


def cmd_reference(args) -> int:
    """Измерение референсного интерфейса по записи inventory."""
    from factory import reference
    summary = reference.measure(args.ref)
    _print(summary, args.json)
    if not args.json:
        print(f"источник: {summary['ref']} | статус: {summary['status']}")
        if summary.get("viewports_measured"):
            print("измерено вьюпортов:", ", ".join(summary["viewports_measured"]))
            print("артефакт:", summary["artifact"])
        else:
            print("измерение не выполнено:", summary.get("reason") or summary.get("stderr", "")[:300])
    return EXIT_OK if summary["status"] == "measured" else EXIT_FAILED


def cmd_seo_cross_site(args) -> int:
    """Ворота уникальности между сайтами одной группы на живом стенде."""
    package, conf, target = _target_for(args.site)
    base = args.base or target.base_url()
    if not base:
        print("сайт не развёрнут: сравнивать нечего. Сначала `factory deploy`.")
        return EXIT_FAILED
    out_dir = PATHS.artifact_dir("seo", args.site)
    report = verify_mod.cross_site_uniqueness(base, package, out_dir)
    _print(report.as_dict(), args.json)
    if not args.json:
        print(f"{report.name}: {'PASSED' if report.passed else 'FAILED'} | {report.counts}")
        for finding in report.findings[:30]:
            print(f"  [{finding.severity}] {finding.rule:8} {finding.url[:60]:62} {finding.message[:70]}")
        print(f"артефакт: artifacts/seo/{args.site}/cross-site-uniqueness.json")
    # Непроведённая проверка не «пройдена»: сравнивать было не с чем.
    return EXIT_OK if report.passed else EXIT_FAILED


def cmd_seo(args, mode: str) -> int:
    package, conf, target = _target_for(args.site)
    build_dir = _latest_build(args.site)
    environment = package["environment"]
    auth = _auth_for(target, environment)
    reports = []
    if mode in ("plan",):
        payload = {"page_types": [p["id"] for p in matrix_mod.load()["page_types"]],
                   "hard_rules": [r["id"] for r in matrix_mod.hard_rules()],
                   "url_policy": matrix_mod.url_policy()}
        _print(payload, args.json)
        if not args.json:
            print("типы страниц:", ", ".join(payload["page_types"]))
            print("жёсткие правила:", ", ".join(payload["hard_rules"]))
            print("политика URL:", json.dumps(payload["url_policy"], ensure_ascii=False))
        return EXIT_OK
    if mode == "lint":
        reports.append(lint_mod.lint(build_dir, environment=environment))
    elif mode == "crawl":
        reports.append(crawl_mod.crawl(args.base or target.base_url(), build_dir, auth=auth, environment=environment))
    elif mode == "render":
        reports.append(render_check.run(args.base or target.base_url(), build_dir,
                                        PATHS.artifact_dir("qa", args.site), auth=auth))
    elif mode == "report":
        reports.append(lint_mod.lint(build_dir, environment=environment))
        reports.append(crawl_mod.crawl(args.base or target.base_url(), build_dir, auth=auth, environment=environment))
    summary = combine(args.site, reports)
    _print(summary, args.json)
    if not args.json:
        for report in reports:
            print(f"{report.name}: {'PASSED' if report.passed else 'FAILED'} | {report.counts}")
            for finding in report.findings[:30]:
                print(f"  [{finding.severity}] {finding.check:18} {finding.url[:44]:46} {finding.message[:70]}")
        if summary["partial"]:
            print(f"отчёт частичный, не выполнялись: {', '.join(summary['missing_reports'])}")
        print(f"артефакт: artifacts/seo/{args.site}/seo-report.json")
    # Код возврата отражает результат запущенных проверок; неполнота набора
    # фиксируется флагом partial в артефакте, а не превращает зелёный линт в красный.
    return EXIT_OK if all(report.passed for report in reports) else EXIT_FAILED


def cmd_knowledge(args) -> int:
    if args.knowledge_action == "freeze":
        data = knowledge.freeze(args.version)
        _print(data, args.json)
        if not args.json:
            print(f"заморожено файлов: {data['file_count']} | версия: {data['freeze_version']} | дайджест: {data['aggregate_sha256'][:16]}")
        return EXIT_OK
    ok, problems = knowledge.verify()
    _print({"ok": ok, "problems": problems, "freeze_version": knowledge.freeze_version()}, args.json)
    if not args.json:
        print(f"freeze: {knowledge.freeze_version()} | целостность: {'OK' if ok else 'НАРУШЕНА'}")
        for problem in problems:
            print(f"  - {problem}")
    return EXIT_OK if ok else EXIT_FAILED


def cmd_db(args) -> int:
    """Провизия локальной базы стенда.

    Команда существовала как обещание: `factory.database.load_credentials`
    отправляет оператора именно сюда (`required_input`), но подкоманды не было,
    и на чистом хосте стенд blueprint'а поднять было нечем. Сам привилегированный
    шаг делает проверенный wrapper `factory.database.provision` — здесь только
    разбор аргументов, без единой собственной операции над кластером.
    """
    from factory import database

    credentials = database.provision(args.scope, environment=args.environment, rotate=args.rotate)
    # Значение пароля не печатается никогда: наружу идёт только ссылка на файл.
    _print(credentials.as_dict(), args.json)
    if not args.json:
        print(f"база: {credentials.database} | роль: {credentials.user} | "
              f"пароль: {credentials.password_ref}")
    return EXIT_OK


def cmd_blueprint(args) -> int:
    status = blueprint.check(args.blueprint)
    _print(status.as_dict(), args.json)
    if not args.json:
        print(f"blueprint {status.blueprint}: {'готов' if status.ready else 'НЕ готов'}")
        for problem in status.problems:
            print(f"  - {problem}")
    return EXIT_OK if status.ready else EXIT_BLOCKED


def _lords_sites(args) -> list:
    """Пакеты направления. Один сайт по `--site`, иначе все пакеты lords."""
    import yaml

    if getattr(args, "site", None):
        return [args.site]
    out = []
    for path in sorted(PATHS.sites.glob("*/package.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if data.get("blueprint") == "lords":
            out.append(str(data.get("site_id") or path.parent.name))
    return out


def cmd_lords_preview(args) -> int:
    """Собирает стенд и, по просьбе, поднимает его локально."""
    from factory.lords import preview as lords_preview

    sites = _lords_sites(args)
    if not sites:
        print("пакеты направления lords не найдены")
        return 1

    results = []
    for site_id in sites:
        result = lords_preview.build_preview(site_id)
        results.append(result)
        report = result.report
        print(f"{site_id} [{report['profile']}] документов: {report['documents']}, "
              f"страниц: {report['pages']}, индексируемых: {report['indexable_pages']}, "
              f"sitemap: {report['sitemap_urls']}, отпечаток: {report['digest'][:16]}")
        print(f"  каталог: {report['directory']}")
        print(f"  источник данных: {report['catalog']['source']}, "
              f"записей: {report['catalog']['titles']}")
        print(f"  плеер: {report['player']['status']} (проверка контракта: "
              f"{'пройдена' if report['player']['passed'] else 'не запускалась'})")
        for blocked in report["blocked_inputs"]:
            print(f"  блокер: {blocked['code']} → {', '.join(blocked['blocks'])}")

    if not args.serve:
        return 0
    if len(results) != 1:
        print("для --serve укажи один сайт через --site")
        return 2
    server, _ = lords_preview.serve(results[0].site_id, host=args.host, port=args.port)
    host, port = server.server_address[0], server.server_address[1]
    print(f"стенд {results[0].site_id} доступен на http://{host}:{port}/ — Ctrl+C завершает")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("остановлен")
    finally:
        server.server_close()
    return 0


def cmd_lords_bundle(args) -> int:
    """Собирает переносимый пакет стенда: документы, рантайм, откат."""
    from factory.lords import bundle as lords_bundle

    sites = _lords_sites(args)
    if not sites:
        print("пакеты направления lords не найдены")
        return 1
    for site_id in sites:
        result = lords_bundle.build_bundle(site_id)
        print(f"{site_id}: {result['archive']}")
        print(f"  файлов: {result['files']}, sha256: {result['sha256'][:16]}, "
              f"отпечаток сайта: {result['digest'][:16]}")
        print(f"  откат: {result['rollback']}")
    return 0


def cmd_lords_plan(args) -> int:
    """Dry-run направления Lords: план сайтов, ворота дублей и план синхронизации.

    Команда ничего не мутирует и ничего не запрашивает по сети. Она отвечает на
    вопрос «что получится», а не «что развёрнуто», поэтому работает и на пакетах,
    у которых ещё нет домена, цели выката и учётных данных.

    `--assume-source fixture` моделирует переданные учётные данные и источник,
    подтверждающий ровно те типы, что включены в manifest. Это единственный
    способ проверить ворота дублей до появления токена, и в отчёте такой прогон
    помечен явно: он не выдаётся за живой.
    """
    import json as _json

    import yaml as _yaml

    from factory.lords import content_api, gate
    from factory.lords import content_types as ct
    from factory.lords import plan as lords_plan

    fixture = args.assume_source == "fixture"
    packages = []
    for path in sorted(PATHS.sites.glob("*/package.yaml")):
        data = _yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if data.get("blueprint") != "lords":
            continue
        if args.site and data.get("site_id") != args.site:
            continue
        packages.append(data)
    if not packages:
        print("пакеты направления lords не найдены")
        return 3

    plans, sync_reports = [], []
    for package in packages:
        capabilities = set(ct.configured(package)) if fixture else None
        capabilities = {n for n, on in ct.configured(package).items() if on} if fixture else None
        plans.append(lords_plan.build_plan(
            package, credentials_available=fixture, api_capabilities=capabilities))
        sync_reports.append(content_api.dry_run(
            package, token_present=fixture, publisher_id_present=fixture))

    for site_plan in plans:
        counts = ct.counts(site_plan.type_states)
        print(f"[{site_plan.site_id}] профиль {site_plan.profile} | "
              f"страниц {len(site_plan.pages)} | индексируемых {len(site_plan.indexable_paths)} | "
              f"в sitemap {len(site_plan.sitemap_paths)} | типы {counts}")
        for absent in site_plan.absent:
            print(f"    нет раздела {absent['path']:14} {absent['state']}: {absent['reason']}")

    report = gate.check_plans(plans)
    overlap = gate.ownership_overlap(plans)
    print(f"\nворота уникальности: находок {len(report.critical)} | "
          f"canonical: {report.counts.get('canonical_check')}")
    for finding in report.critical:
        print(f"    [{finding.rule}] {finding.url}: {finding.message}")
    if overlap:
        for item in overlap:
            print(f"    раздел {item['section']} индексируют несколько сайтов: {item['sites']}")

    print(f"\nисточник данных: {sync_reports[0]['readiness']} — {sync_reports[0]['reason']}")

    out = PATHS.artifact_dir("lords", "plan")
    payload = {
        "mode": "fixture" if fixture else "real",
        "live_request_performed": False,
        "plans": [p.as_dict() for p in plans],
        "uniqueness": report.as_dict(),
        "ownership_overlap": overlap,
        "content_sync": sync_reports,
    }
    artifact = out / "lords-plan.json"
    artifact.write_text(_json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"артефакт: {artifact.relative_to(PATHS.root)}")

    return 0 if not report.critical and not overlap else 1


def cmd_env_report(args) -> int:
    import shutil
    tools = {name: bool(shutil.which(name)) for name in
             ("python3", "php", "node", "npm", "git", "ansible-playbook", "nginx", "mysql", "docker", "rsync")}
    payload = {"tools": tools, "inventory": inventory.as_dict(),
               "browser": dict(zip(("available", "detail"), render_check.available(), strict=False)),
               "knowledge_freeze": knowledge.freeze_version()}
    out = PATHS.artifact_dir("env") / "env-report.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _print(payload, args.json)
    if not args.json:
        print(json.dumps(payload["tools"], ensure_ascii=False))
        print(f"артефакт: {out.relative_to(PATHS.root)}")
    return EXIT_OK


def cmd_input_request(args) -> int:
    from factory.input_request import generate
    md_path, json_path, items = generate()
    _print({"items": items, "markdown": str(md_path), "json": str(json_path)}, args.json)
    if not args.json:
        print(f"недостающих входных данных: {len(items)}")
        print(f"  {md_path.relative_to(PATHS.root)}\n  {json_path.relative_to(PATHS.root)}")
    return EXIT_OK


def cmd_selfcheck(args) -> int:
    problems: list[str] = []
    claude_md = PATHS.root / "CLAUDE.md"
    lines = len(claude_md.read_text(encoding="utf-8").splitlines()) if claude_md.exists() else 0
    if lines == 0:
        problems.append("CLAUDE.md отсутствует")
    elif lines > 200:
        problems.append(f"CLAUDE.md {lines} строк — больше рекомендованных 200")
    settings = PATHS.root / ".claude" / "settings.json"
    try:
        data = json.loads(settings.read_text(encoding="utf-8"))
        if data.get("permissions", {}).get("defaultMode") == "bypassPermissions":
            problems.append("defaultMode=bypassPermissions запрещён")
        if not data.get("permissions", {}).get("deny"):
            problems.append("нет deny-правил в settings.json")
        for hook_group in data.get("hooks", {}).get("PreToolUse", []):
            for hook in hook_group.get("hooks", []):
                script = hook["command"].split()[-1].replace("${CLAUDE_PROJECT_DIR}", str(PATHS.root))
                if not Path(script).exists():
                    problems.append(f"hook-скрипт не найден: {script}")
    except (OSError, json.JSONDecodeError) as exc:
        problems.append(f"settings.json нечитаем: {exc}")
    payload = {"claude_md_lines": lines, "problems": problems, "ok": not problems}
    _print(payload, args.json)
    if not args.json:
        print(f"CLAUDE.md: {lines} строк | проблем: {len(problems)}")
        for problem in problems:
            print(f"  - {problem}")
    return EXIT_OK if not problems else EXIT_FAILED


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="factory", description="DLE Site Factory")
    parser.add_argument("--json", action="store_true", help="машиночитаемый вывод")
    sub = parser.add_subparsers(dest="command", required=True)

    def with_site(name, help_text):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--site", required=True)
        return p

    p = with_site("validate", "проверить пакет сайта")
    p.set_defaults(func=cmd_validate)
    p = with_site("plan", "показать план без мутаций")
    p.set_defaults(func=cmd_plan)
    p = with_site("build", "собрать сайт")
    p.add_argument("--environment", choices=["staging", "production"])
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_build)
    p = with_site("deploy", "выкатить сайт через конвейер")
    p.add_argument("--environment", choices=["staging", "production"])
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--skip-browser", action="store_true")
    p.add_argument("--allow-production", action="store_true", help="явное подтверждение оператора для production")
    p.set_defaults(func=cmd_deploy)
    p = with_site("verify", "прогнать ворота качества")
    p.add_argument("--base")
    p.add_argument("--skip-browser", action="store_true")
    p.add_argument("--job-id", help="изолировать артефакты проверки в каталоге задания")
    p.set_defaults(func=cmd_verify)
    p = with_site("rollback", "откатить на предыдущий релиз")
    p.add_argument("--environment", choices=["staging", "production"])
    p.add_argument("--allow-production", action="store_true", help="явное подтверждение оператора для production")
    p.set_defaults(func=cmd_rollback)
    p = with_site("decommission", "остановить стенд и освободить порт")
    p.add_argument("--purge", action="store_true", help="удалить каталог цели вместе с релизами")
    p.set_defaults(func=cmd_decommission)
    p = sub.add_parser("status", help="состояние заданий и очереди")
    p.add_argument("--site")
    p.set_defaults(func=cmd_status)
    p = sub.add_parser("resume", help="продолжить обработку очереди")
    p.add_argument("--max-age", type=int, default=3600)
    p.add_argument("--skip-browser", action="store_true")
    p.set_defaults(func=cmd_resume)
    p = with_site("report", "последний результат задания")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("queue", help="работа с очередью")
    p.add_argument("queue_action", choices=["enqueue", "list"])
    p.add_argument("--site")
    p.add_argument("--action", default="create")
    p.add_argument("--environment", default="staging")
    p.set_defaults(func=cmd_queue)

    p = sub.add_parser("reference-audit", help="read-only измерение референсного интерфейса")
    p.add_argument("--ref", required=True)
    p.set_defaults(func=cmd_reference)

    p = sub.add_parser("seo-cross-site", help="SEO: уникальность между сайтами группы")
    p.add_argument("--site", required=True)
    p.add_argument("--base")
    p.set_defaults(func=cmd_seo_cross_site)

    for mode in ("plan", "lint", "crawl", "render", "report"):
        p = sub.add_parser(f"seo-{mode}", help=f"SEO: {mode}")
        p.add_argument("--site", required=True)
        p.add_argument("--base")
        p.set_defaults(func=lambda a, m=mode: cmd_seo(a, m))

    p = sub.add_parser("knowledge", help="база знаний")
    p.add_argument("knowledge_action", choices=["freeze", "verify"])
    p.add_argument("--version", default="unversioned")
    p.set_defaults(func=cmd_knowledge)

    p = sub.add_parser("db", help="провизия локальной базы стенда")
    p.add_argument("db_action", choices=["provision"], nargs="?", default="provision")
    p.add_argument("--scope", required=True)
    # production сюда не попадает: wrapper сам отказывает, но и CLI не предлагает.
    p.add_argument("--environment", default="staging", choices=["staging"])
    p.add_argument("--rotate", action="store_true", help="сменить пароль существующей роли")
    p.set_defaults(func=cmd_db)

    p = sub.add_parser("blueprint", help="проверка blueprint")
    p.add_argument("blueprint_action", choices=["check"], nargs="?", default="check")
    p.add_argument("--blueprint", default="dle20")
    p.set_defaults(func=cmd_blueprint)

    analytics_cli.register(sub)

    p = sub.add_parser("lords-plan", help="Lords: dry-run плана сайтов и ворот дублей")
    p.add_argument("--site", help="только один сайт направления")
    p.add_argument("--assume-source", choices=["none", "fixture"], default="none",
                   help="fixture моделирует переданные учётные данные и источник")
    p.set_defaults(func=cmd_lords_plan)

    p = sub.add_parser("lords-preview", help="Lords: собрать стенд на синтетическом каталоге")
    p.add_argument("--site", help="один сайт направления; без него — все")
    p.add_argument("--serve", action="store_true", help="запустить локальный сервер стенда")
    p.add_argument("--host", default="127.0.0.1", help="интерфейс локального сервера")
    p.add_argument("--port", type=int, default=8080, help="порт локального сервера")
    p.set_defaults(func=cmd_lords_preview)

    p = sub.add_parser("lords-bundle", help="Lords: воспроизводимый пакет стенда")
    p.add_argument("--site", help="один сайт направления; без него — все")
    p.set_defaults(func=cmd_lords_bundle)

    p = sub.add_parser("env-report", help="read-only отчёт об окружении")
    p.set_defaults(func=cmd_env_report)
    p = sub.add_parser("input-request", help="сформировать пакет недостающих данных")
    p.set_defaults(func=cmd_input_request)
    p = sub.add_parser("selfcheck", help="самопроверка конфигурации Claude Code")
    p.add_argument("what", nargs="?", default="claude-config")
    p.set_defaults(func=cmd_selfcheck)

    args = parser.parse_args(argv)
    PATHS.ensure_runtime()
    try:
        return args.func(args)
    except FactoryError as exc:
        print(f"[{exc.status}] {exc.reason}", file=sys.stderr)
        if exc.required_input:
            print(f"нужно: {exc.required_input}", file=sys.stderr)
        return EXIT_BLOCKED
