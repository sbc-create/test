"""Команды `python3 -m factory analytics …`.

Все команды по умолчанию ничего не меняют на стороне Яндекса. Запись включается
единственным явным флагом ``--confirm-writes``: разрешение на необратимое
действие даётся команде, а не режиму работы.

Ни одна команда не печатает токен, его часть, отпечаток файла секрета или
персональные данные аккаунта. В отчёт идут HTTP-статусы, публичные counter ID и
проверяемые состояния.
"""
from __future__ import annotations

import json
import time

from factory.analytics import client_codegen, events, registry, snippet
from factory.analytics.credentials import inspect_token_file
from factory.analytics.gate import indexing_allowed
from factory.analytics.yandex import (
    BLOCKED_DEPLOYMENT,
    YandexAnalyticsProvider,
    normalize_domain,
)
from factory.errors import BlockedAnalyticsAccess, FactoryError

EXIT_OK, EXIT_FAILED, EXIT_BLOCKED = 0, 1, 2


def _emit(payload: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


def _provider(args) -> YandexAnalyticsProvider:
    return YandexAnalyticsProvider(dry_run=not getattr(args, "confirm_writes", False))


def _selected(args) -> list[dict]:
    """Записи реестра, к которым относится команда."""
    entries = registry.load()["properties"]
    domain = getattr(args, "domain", None)
    if domain:
        target = normalize_domain(domain)
        chosen = [e for e in entries if normalize_domain(e["domain"]) == target]
        if not chosen:
            raise SystemExit(f"домен {target} отсутствует в {registry.REGISTRY_PATH}")
        return chosen
    site = getattr(args, "site", None)
    if site:
        chosen = [e for e in entries if e.get("site_id") == site]
        if not chosen:
            raise SystemExit(f"сайт {site} не связан ни с одним доменом в {registry.REGISTRY_PATH}")
        return chosen
    return entries


# --------------------------------------------------------------- команды
def cmd_probe(args) -> int:
    """Безопасная проверка доступа: HTTP-статус и подтверждённые возможности."""
    report = _provider(args).validate_credentials()
    payload = report.as_dict()
    _emit(payload, args.json)
    if not args.json:
        token = payload["token_file"]
        print(f"файл секрета: {token['path']}")
        print(f"  хранится корректно: {token['stored_correctly']}  доступен процессу: {token['readable']}")
        for problem in token["problems"]:
            print(f"  ! {problem}")
        print(f"METRIKA_API   HTTP {report.metrika_status}  ok={report.metrika_ok}")
        print(f"WEBMASTER_API HTTP {report.webmaster_status}  ok={report.webmaster_ok}")
        print(f"возможности: {', '.join(report.capabilities) or 'не подтверждены'}")
        for problem in report.problems:
            print(f"  ! {problem}")
    return EXIT_OK if report.ok else EXIT_BLOCKED


def cmd_plan(args) -> int:
    """Что будет сделано. Ни одного запроса на запись."""
    provider = YandexAnalyticsProvider(dry_run=True)
    plan = {"provider": provider.name, "writes": [], "domains": []}
    for entry in _selected(args):
        domain = entry["domain"]
        state = provider.ensure_metrica_counter(domain, entry["counter_name"])
        if state.counter_id:
            state = provider.ensure_metrica_goals(state.counter_id, state)
        item = state.as_dict()
        item["webmaster"] = {
            "planned_host_url": f"https://{domain}",
            "verification_status": entry["webmaster"]["verification_status"],
            "note": "регистрация и подтверждение отложены до ответа домена по HTTPS",
        }
        allowed, reason = indexing_allowed(
            {"seo_indexing_enabled": entry["seo_indexing_enabled"],
             "production_authorized": False,
             "webmaster": {"enabled": True,
                           "verification_status": entry["webmaster"]["verification_status"]}},
            "production",
        )
        item["indexing_allowed"] = allowed
        item["indexing_reason"] = reason
        plan["domains"].append(item)
        if state.planned:
            plan["writes"].append(f"создать счётчик «{entry['counter_name']}» для {domain}")
        for goal in state.goals_planned:
            plan["writes"].append(f"создать цель «{goal}» у счётчика {state.counter_id or '(нового)'}")
    _emit(plan, args.json)
    if not args.json:
        for item in plan["domains"]:
            mark = "переиспользовать" if item["reused"] else "создать" if item["planned"] else "?"
            print(f"{item['domain']}: {mark}, counter_id={item['counter_id']}, "
                  f"целей есть {len(item['goals_present'])}/9, индексация={item['indexing_allowed']}")
        print(f"\nзаписей потребуется: {len(plan['writes'])}")
        for write in plan["writes"]:
            print(f"  · {write}")
    return EXIT_OK


def cmd_apply(args) -> int:
    """Создаёт или переиспользует счётчики и цели. Запись — только с --confirm-writes."""
    provider = _provider(args)
    results = []
    exit_code = EXIT_OK

    for entry in _selected(args):
        domain = entry["domain"]
        try:
            state = provider.ensure_metrica_counter(domain, entry["counter_name"])
            if state.counter_id and not state.problems:
                state = provider.ensure_metrica_goals(state.counter_id, state)
        except FactoryError as exc:
            results.append({"domain": domain, "status": exc.status, "reason": exc.reason})
            exit_code = EXIT_BLOCKED
            continue

        update = {
            "domain": domain,
            "counter_id": state.counter_id,
            "counter_state": (
                "ambiguous" if state.problems and not state.counter_id else
                "created" if state.created else
                "reused" if state.reused else "planned"
            ),
            "webvisor": state.webvisor,
            "goals": sorted(set(state.goals_present) | set(state.goals_created)),
            "last_checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "problems": list(state.problems),
        }
        if not provider.dry_run:
            registry.upsert(update)
        results.append(state.as_dict())
        if state.problems:
            exit_code = EXIT_BLOCKED

    payload = {"dry_run": provider.dry_run, "results": results}
    _emit(payload, args.json)
    if not args.json:
        for item in results:
            print(json.dumps(item, ensure_ascii=False))
        if provider.dry_run:
            print("\nрежим плана: ни одного запроса на запись не отправлено. "
                  "Для записи добавь --confirm-writes.")
    return exit_code


def cmd_status(args) -> int:
    """Состояние из реестра. Сеть трогается только с --live."""
    data = registry.load()
    payload = {
        "seo_indexing_enabled": data["seo_indexing_enabled"],
        "token_file": inspect_token_file().as_dict(),
        "domains": [],
    }
    live = None
    if getattr(args, "live", False):
        try:
            live = YandexAnalyticsProvider(dry_run=True).status(
                [e["domain"] for e in data["properties"]]
            )["domains"]
        except BlockedAnalyticsAccess as exc:
            payload["live_error"] = exc.reason

    for entry in data["properties"]:
        item = {
            "domain": entry["domain"],
            "counter_id": entry["counter_id"],
            "counter_state": entry.get("counter_state"),
            "goals": len(entry.get("goals") or []),
            "goals_expected": len(events.EVENT_IDS),
            "webvisor": entry.get("webvisor", False),
            "webmaster": entry["webmaster"]["verification_status"],
            "seo_indexing_enabled": entry["seo_indexing_enabled"],
        }
        if live is not None:
            item["live"] = live.get(normalize_domain(entry["domain"]))
        payload["domains"].append(item)

    _emit(payload, args.json)
    if not args.json:
        print(f"SEO_INDEXING_ENABLED = {str(payload['seo_indexing_enabled']).lower()}")
        for item in payload["domains"]:
            print(f"{item['domain']:16} counter={item['counter_id'] or '—':<10} "
                  f"целей {item['goals']}/{item['goals_expected']}  "
                  f"вебвизор={item['webvisor']}  вебмастер={item['webmaster']}  "
                  f"индексация={item['seo_indexing_enabled']}")
    return EXIT_OK


def cmd_webmaster(args) -> int:
    """План или подтверждение прав. Неразвёрнутый домен не подтверждается."""
    provider = _provider(args)
    results = []
    for entry in _selected(args):
        domain = entry["domain"]
        state = provider.ensure_webmaster_host(domain, deployment_ready=args.deployment_ready)
        item = state.as_dict()
        if state.host_id and args.deployment_ready:
            marker = provider.get_verification_marker(state.host_id)
            item["verification"] = {
                "state": marker["verification_state"],
                "applicable_verifiers": marker["applicable_verifiers"],
                "marker_present": bool(marker["verification_uin"]),
            }
            if args.verify:
                item["verify"] = provider.verify_webmaster_host(
                    state.host_id,
                    verification_type=args.verification_type,
                    marker_reachable=args.marker_reachable,
                )
        results.append(item)

    _emit({"results": results}, args.json)
    if not args.json:
        for item in results:
            print(f"{item['domain']}: {item['verification_state']}, host_id={item['host_id']}")
            for problem in item["problems"]:
                print(f"  ! {problem}")
        if not args.deployment_ready:
            print(f"\nсостояние {BLOCKED_DEPLOYMENT}: домены ещё не отвечают по HTTPS. "
                  "Это не ошибка и не DONE — это отложенный шаг.")
    return EXIT_OK


def cmd_report(args) -> int:
    """Read-only отчёт Метрики. Нет данных — «не измерено», а не ноль."""
    provider = YandexAnalyticsProvider(dry_run=True)
    contract = provider.contract["metrika"]["reporting"]
    metrics = list(contract["metrics_used"].values())
    out = []
    for entry in _selected(args):
        if not entry["counter_id"]:
            out.append({"domain": entry["domain"], "measured": False,
                        "reason": "счётчик не создан — показатели не измерены"})
            continue
        try:
            report = provider.get_metrica_report(
                entry["counter_id"], date1=args.date1, date2=args.date2, metrics=metrics)
            report["domain"] = entry["domain"]
            report["measured"] = True
            out.append(report)
        except BlockedAnalyticsAccess as exc:
            out.append({"domain": entry["domain"], "measured": False, "reason": exc.reason})
    _emit({"reports": out}, args.json)
    if not args.json:
        for item in out:
            if item.get("measured"):
                print(f"{item['domain']}: totals={item['totals']} sampled={item['sampled']}")
            else:
                print(f"{item['domain']}: не измерено — {item['reason']}")
    return EXIT_OK


def cmd_rotate_check(args) -> int:
    result = YandexAnalyticsProvider(dry_run=True).rotate_credentials_check()
    _emit(result, args.json)
    if not args.json:
        print(f"ротация требуется: {result['rotation_required']}")
        print(f"причина: {result['reason']}")
    return EXIT_BLOCKED if result["rotation_required"] else EXIT_OK


def cmd_disable(args) -> int:
    provider = YandexAnalyticsProvider(dry_run=not args.confirm_writes)
    results = []
    for entry in _selected(args):
        result = provider.disable(entry["domain"])
        if args.confirm_writes:
            registry.upsert({"domain": entry["domain"], "analytics_enabled": False,
                             "counter_state": "disabled"})
        results.append(result)
    _emit({"results": results}, args.json)
    if not args.json:
        for item in results:
            print(f"{item['domain']}: {item['effect']}")
    return EXIT_OK


def cmd_codegen(args) -> int:
    written = client_codegen.write_all()
    _emit({"written": written}, args.json)
    if not args.json:
        for path in written:
            print(f"сгенерирован {path}")
    return EXIT_OK


def cmd_events(args) -> int:
    _emit(events.as_dict(), True)
    return EXIT_OK


def cmd_marker(args) -> int:
    """Печатает разметку маркера подтверждения для домена из реестра."""
    for entry in _selected(args):
        marker = entry["webmaster"].get("verification_marker")
        meta = snippet.verification_meta(marker)
        html_file = snippet.verification_html_file(marker)
        print(f"{entry['domain']}: {meta or 'маркер ещё не получен'}")
        if html_file:
            print(f"  файл: {html_file[0]}")
    return EXIT_OK


ACTIONS = {
    "probe": cmd_probe,
    "plan": cmd_plan,
    "apply": cmd_apply,
    "status": cmd_status,
    "webmaster": cmd_webmaster,
    "report": cmd_report,
    "rotate-check": cmd_rotate_check,
    "disable": cmd_disable,
    "codegen": cmd_codegen,
    "events": cmd_events,
    "marker": cmd_marker,
}


def register(subparsers) -> None:
    parser = subparsers.add_parser("analytics", help="Яндекс.Метрика и Яндекс.Вебмастер")
    parser.add_argument("analytics_action", choices=sorted(ACTIONS))
    parser.add_argument("--site", help="site_id из sites/")
    parser.add_argument("--domain", help="домен из config/analytics.json")
    parser.add_argument(
        "--confirm-writes", action="store_true",
        help="разрешить реальные записи в Метрику. Без флага команда только планирует.")
    parser.add_argument("--live", action="store_true", help="status: сверить с API")
    parser.add_argument(
        "--deployment-ready", action="store_true",
        help="webmaster: домен фактически отвечает по HTTPS (проверено оператором)")
    parser.add_argument("--verify", action="store_true", help="webmaster: запустить подтверждение прав")
    parser.add_argument(
        "--marker-reachable", action="store_true",
        help="webmaster: маркер подтверждения фактически отдаётся по HTTP")
    parser.add_argument("--verification-type", default="META_TAG",
                        choices=["META_TAG", "HTML_FILE", "DNS"])
    parser.add_argument("--date1", default="7daysAgo", help="report: начало периода")
    parser.add_argument("--date2", default="yesterday", help="report: конец периода")
    parser.set_defaults(func=lambda args: ACTIONS[args.analytics_action](args))
