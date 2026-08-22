"""
CLI оператора. Единая точка входа для планировщика и для человека.

Коды выхода: 0 ok, 1 ошибка, 3 BLOCKED_AUTHORIZATION, 4 BLOCKED_PROTECTED_GUARDRAIL.
Планировщик различает их без разбора текста.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

from . import config
from .audit import AuditLog
from .guardrails import AuthorizationBlocked, GuardrailViolation
from .state import Store

EXIT_OK, EXIT_ERROR, EXIT_BLOCKED_AUTH, EXIT_BLOCKED_GUARD = 0, 1, 3, 4


def _out(obj, as_json: bool) -> None:
    if as_json:
        print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))
    elif isinstance(obj, str):
        print(obj)
    else:
        print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


# --------------------------------------------------------------------------
# команды
# --------------------------------------------------------------------------

# Поля, где секрет мог бы протечь. Сравнение по сегментам имени, а не по подстроке:
# `brand_tokens` — легитимное поле, `oauth_token` — нет.
_SECRET_FIELD_SEGMENTS = {"secret", "token", "tokens", "password", "passwd",
                          "credential", "credentials", "apikey", "key", "oauth"}
_SECRET_FIELD_ALLOWLIST = {"brand_tokens", "rights_source_refs", "secret_ref"}


def _is_secret_field(name: str) -> bool:
    lowered = name.lower()
    if lowered in _SECRET_FIELD_ALLOWLIST or lowered.endswith("_ref") or lowered.endswith("_refs"):
        return False
    segments = set(re.split(r"[_\-\.]", lowered))
    return bool(segments & _SECRET_FIELD_SEGMENTS)


def cmd_portfolio(args) -> int:
    status = config.portfolio_status()
    sites = config.portfolio()
    if args.subcommand == "validate":
        problems = []
        for site in sites:
            manifest = config.authorization_manifest(site.site_id)
            if manifest is None:
                problems.append(f"{site.site_id}: нет authorization manifest")
            elif manifest.get("site_id") != site.site_id:
                problems.append(f"{site.site_id}: manifest.site_id не совпадает")
            for key in site.raw:
                if _is_secret_field(str(key)):
                    problems.append(f"{site.site_id}: секрет в registry — поле '{key}'")
        _out({"portfolio_status": status, "sites": len(sites), "problems": problems}, args.json)
        return EXIT_OK if not problems else EXIT_ERROR
    if args.subcommand == "status":
        _out({"portfolio_status": status,
              "sites": [{"site_id": s.site_id, "domain": s.domain, "env": s.environment,
                         "autonomy_tier": s.autonomy_tier} for s in sites]}, args.json)
        return EXIT_OK
    if args.subcommand == "report":
        _out({"portfolio_status": status, "expected": "15-20 сайтов",
              "configured": len(sites),
              "note": "Реальные сайты добавляются после передачи inventory и secret store."}, args.json)
        return EXIT_OK
    return EXIT_ERROR


def cmd_secrets_check(args) -> int:
    """Проверяет, что в репозитории нет значений секретов. Значения НИКОГДА не печатаются."""
    import re
    root = config.repo_root()
    patterns = [
        (r"ghp_[A-Za-z0-9]{20,}", "github token"),
        (r"AKIA[0-9A-Z]{16}", "aws key id"),
        (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "private key"),
        (r"ya29\.[A-Za-z0-9_\-]{20,}", "google oauth token"),
        (r"\by0_[A-Za-z0-9_\-]{20,}", "yandex oauth token"),
        (r"(?i)\b(password|secret|api_key)\s*[:=]\s*['\"][^'\"]{8,}['\"]", "inline credential"),
    ]
    findings = []
    for path in root.rglob("*"):
        if not path.is_file() or ".git/" in str(path) or "__pycache__" in str(path):
            continue
        if path.suffix in {".sqlite3", ".png", ".jpg", ".pdf"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pattern, label in patterns:
            for m in re.finditer(pattern, text):
                line = text[:m.start()].count("\n") + 1
                # Печатается только местоположение и тип. Значение не выводится.
                findings.append({"file": str(path.relative_to(root)), "line": line, "type": label})
    _out({"findings": findings, "clean": not findings,
          "note": "Значения секретов не выводятся по построению."}, args.json)
    return EXIT_OK if not findings else EXIT_ERROR


def cmd_daily_run(args) -> int:
    from .scheduler import DailyRun
    from .reporting import daily

    store = Store()
    audit = AuditLog()
    try:
        run = DailyRun(store, audit, dry_run=not args.apply,
                       today=date.fromisoformat(args.date) if args.date else None)
        report = run.run(args.site.split(",") if args.site else None)
        if args.json:
            _out({"run_date": report.run_date, "dry_run": report.dry_run,
                  "steps": [{"step": s.step.value, "status": s.status, "detail": s.detail}
                            for s in report.steps],
                  "blockers": len(report.blockers),
                  "protected_drift": report.protected_drift}, True)
        else:
            print(daily.render(report, config.portfolio_status()))
        store.mark_blockers_reported()
        if report.protected_drift:
            return EXIT_BLOCKED_GUARD
        if any(s.status == "error" for s in report.steps):
            return EXIT_ERROR
        return EXIT_OK
    finally:
        store.close()
        audit.close()


def cmd_weekly_report(args) -> int:
    from .experiments.registry import ExperimentRegistry
    from .reporting import weekly
    store = Store()
    try:
        print(weekly.render(store, ExperimentRegistry(store)))
        return EXIT_OK
    finally:
        store.close()


def cmd_experiment(args) -> int:
    from .experiments.registry import ExperimentRegistry
    from .cms import CMSAdapter, InMemoryCMS
    store = Store()
    audit = AuditLog()
    try:
        registry = ExperimentRegistry(store)
        if args.subcommand == "status":
            exps = registry.active(args.site) if args.site else registry.active()
            _out([{"id": e.id, "site": e.site_id, "status": e.status,
                   "hypothesis": e.hypothesis, "started": e.started_at} for e in exps], args.json)
            return EXIT_OK
        if args.subcommand == "rollback":
            adapter = CMSAdapter(InMemoryCMS(), store, audit)
            results = adapter.rollback(args.id)
            _out({"experiment": args.id, "rolled_back": len(results),
                  "targets": [r.target for r in results]}, args.json)
            return EXIT_OK
        if args.subcommand == "evaluate":
            exp = registry.get(args.id)
            if exp is None:
                _out({"error": f"Эксперимент {args.id} не найден"}, args.json)
                return EXIT_ERROR
            from .experiments.evaluator import evaluate
            rows = [{"date": r["observed_date"], exp.primary_kpi: r["value"],
                     "completeness": r["completeness"], "clicks": r["value"], "impressions": r["value"]}
                    for r in store.observations(exp.site_id, exp.primary_kpi)]
            ev = evaluate(exp, rows, [], {}, {})
            _out({"id": ev.experiment_id, "decision": ev.decision, "confidence": ev.confidence,
                  "lift_pct": ev.lift_pct, "explanation": ev.explanation}, args.json)
            return EXIT_OK
        _out({"error": f"Неизвестная подкоманда: {args.subcommand}"}, args.json)
        return EXIT_ERROR
    finally:
        store.close()
        audit.close()


def cmd_editorial(args) -> int:
    from .editorial import discovery
    store = Store()
    try:
        site = config.get_site(args.site)
        if args.subcommand == "discover":
            if not site.site_id.startswith("demo-"):
                raise AuthorizationBlocked(
                    f"Каталог не подключён для {site.site_id}.",
                    {"site": site.site_id, "needs": "cms_content_api + EDITORIAL_SOURCE_REGISTRY"})
            strategy = {"priority_segments": site.raw.get("priority_segments", [])}
            entries, opps = discovery.discover_from_fixture(site, strategy)
            _out({"entries": [e.to_dict() for e in entries],
                  "opportunities": [o.__dict__ for o in opps]}, True)
            return EXIT_OK
        _out({"error": f"Подкоманда '{args.subcommand}' требует подключённой CMS."}, args.json)
        return EXIT_BLOCKED_AUTH
    finally:
        store.close()


def cmd_cms_mutate(args) -> int:
    from .cms import CMSAdapter, InMemoryCMS, UnconfiguredCMS
    store = Store()
    audit = AuditLog()
    try:
        backend = InMemoryCMS() if args.site.startswith("demo-") else UnconfiguredCMS()
        adapter = CMSAdapter(backend, store, audit)
        result = adapter.mutate(
            site_id=args.site, target=args.target, action=args.action, tier=args.tier,
            new_payload=json.loads(args.payload) if args.payload else {},
            experiment_id=args.experiment, dry_run=not args.apply)
        _out({"applied": result.applied, "dry_run": result.dry_run, "target": result.target,
              "audit_seq": result.audit_seq, "message": result.message}, args.json)
        return EXIT_OK
    finally:
        store.close()
        audit.close()


def cmd_audit(args) -> int:
    audit = AuditLog()
    try:
        if args.subcommand == "verify":
            ok, msg = audit.verify_chain()
            _out({"chain_ok": ok, "message": msg}, args.json)
            return EXIT_OK if ok else EXIT_BLOCKED_GUARD
        records = list(audit.records(args.site, args.limit))
        _out([{"seq": r.seq, "ts": r.ts, "action": r.action, "site": r.site_id,
               "experiment": r.experiment_id} for r in records], args.json)
        return EXIT_OK
    finally:
        audit.close()


def cmd_guardrails(args) -> int:
    from .guardrails import protected_fingerprint, verify_integrity
    baseline_path = config.state_dir() / "protected-baseline.json"
    current = protected_fingerprint()
    if args.subcommand == "baseline":
        baseline_path.write_text(json.dumps(current, indent=2, sort_keys=True), encoding="utf-8")
        _out({"written": str(baseline_path), "files": len(current)}, args.json)
        return EXIT_OK
    if not baseline_path.exists():
        _out({"error": "Нет baseline. Выполните `seo guardrails baseline`."}, args.json)
        return EXIT_ERROR
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    drift = verify_integrity(baseline)
    _out({"drift": drift, "clean": not drift}, args.json)
    return EXIT_OK if not drift else EXIT_BLOCKED_GUARD


def cmd_permissions_test(args) -> int:
    """Прогон permission corpus без Claude: доказывает, что hook решает так, как заявлено."""
    sys.path.insert(0, str(config.repo_root() / ".claude" / "hooks"))
    from policy_engine import evaluate  # type: ignore
    corpus_path = config.repo_root() / "tests" / "permission_corpus.json"
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    root = str(config.repo_root())
    failures = []
    for case in corpus["allow"] + corpus["deny"]:
        expected = case["expect"]
        decision = evaluate(case["tool"], case["input"], root)
        if decision.permission != expected:
            failures.append({"name": case["name"], "expected": expected,
                             "got": decision.permission, "rule": decision.rule})
    _out({"total": len(corpus["allow"]) + len(corpus["deny"]),
          "allow_cases": len(corpus["allow"]), "deny_cases": len(corpus["deny"]),
          "failures": failures, "passed": not failures}, args.json)
    return EXIT_OK if not failures else EXIT_ERROR


# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="seo", description="Автономный SEO-оператор и главный редактор")
    p.add_argument("--json", action="store_true", help="машиночитаемый вывод")
    sub = p.add_subparsers(dest="command", required=True)

    pf = sub.add_parser("portfolio")
    pf.add_argument("subcommand", choices=["validate", "status", "report"])
    pf.set_defaults(func=cmd_portfolio)

    dr = sub.add_parser("daily-run")
    dr.add_argument("--apply", action="store_true", help="применять изменения (по умолчанию dry-run)")
    dr.add_argument("--dry-run", action="store_true", help="явный dry-run (поведение по умолчанию)")
    dr.add_argument("--site", help="список site_id через запятую")
    dr.add_argument("--date", help="дата прогона YYYY-MM-DD")
    dr.set_defaults(func=cmd_daily_run)

    sub.add_parser("weekly-report").set_defaults(func=cmd_weekly_report)

    ex = sub.add_parser("experiment")
    ex.add_argument("subcommand", choices=["status", "evaluate", "rollback"])
    ex.add_argument("--id")
    ex.add_argument("--site")
    ex.set_defaults(func=cmd_experiment)

    ed = sub.add_parser("editorial")
    ed.add_argument("subcommand", choices=["discover", "calendar", "backlog", "plan",
                                           "publish", "refresh", "expire", "report"])
    ed.add_argument("--site", required=True)
    ed.set_defaults(func=cmd_editorial)

    cm = sub.add_parser("cms-mutate")
    cm.add_argument("--site", required=True)
    cm.add_argument("--target", required=True)
    cm.add_argument("--action", required=True)
    cm.add_argument("--tier", type=int, default=1)
    cm.add_argument("--experiment")
    cm.add_argument("--payload")
    cm.add_argument("--apply", action="store_true")
    cm.add_argument("--dry-run", action="store_true")
    cm.set_defaults(func=cmd_cms_mutate)

    au = sub.add_parser("audit")
    au.add_argument("subcommand", choices=["list", "verify"])
    au.add_argument("--site")
    au.add_argument("--limit", type=int, default=50)
    au.set_defaults(func=cmd_audit)

    gr = sub.add_parser("guardrails")
    gr.add_argument("subcommand", choices=["baseline", "verify"])
    gr.set_defaults(func=cmd_guardrails)

    sc = sub.add_parser("secrets")
    sc.add_argument("subcommand", choices=["check"])
    sc.set_defaults(func=cmd_secrets_check)

    pt = sub.add_parser("permissions")
    pt.add_argument("subcommand", choices=["test"])
    pt.set_defaults(func=cmd_permissions_test)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except AuthorizationBlocked as exc:
        _out({"status": "BLOCKED_AUTHORIZATION", "detail": str(exc), "request": exc.request},
             getattr(args, "json", False))
        return EXIT_BLOCKED_AUTH
    except GuardrailViolation as exc:
        _out({"status": "BLOCKED_PROTECTED_GUARDRAIL", "detail": str(exc)},
             getattr(args, "json", False))
        return EXIT_BLOCKED_GUARD


if __name__ == "__main__":
    sys.exit(main())
