"""Operator command line.

seo-operator probe                 проверить доступность источников
seo-operator inventory             read-only инвентаризация
seo-operator dry-run [--fixture]   рассчитать изменения, ничего не записывая
seo-operator canary  [--fixture]   применить изменения в пределах canary
seo-operator observe --experiment  оценить эксперимент и решить keep/rollback
seo-operator report  [--fixture]   сформировать ежедневный отчёт
seo-operator analytics-collect     read-only сбор показателей Метрики и Вебмастера
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from seo_operator.audit import AuditLog
from seo_operator.datasources.live import probe_all
from seo_operator.pipeline import Mode, Operator
from seo_operator.registry import load_portfolio
from seo_operator.reporting import daily_report, weekly_report

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_PORTFOLIO = REPO_ROOT / "config" / "portfolio.fixture.json"
REAL_PORTFOLIO = REPO_ROOT / "config" / "portfolio.json"
FIXTURE_PAGES = REPO_ROOT / "tests" / "fixtures" / "crawl.fixture-anime.json"


def _load_pages(path: Path):
    from seo_operator.technical_seo import Page

    data = json.loads(path.read_text(encoding="utf-8"))
    return [Page(**p) for p in data["pages"]]


def _operator(use_fixture: bool) -> Operator:
    portfolio_path = FIXTURE_PORTFOLIO if use_fixture else REAL_PORTFOLIO
    return Operator(
        portfolio=load_portfolio(portfolio_path),
        audit_log=AuditLog(REPO_ROOT / "var" / "audit" / "operator.jsonl"),
        allow_synthetic=use_fixture,
    )


def cmd_probe(_args) -> int:
    probes = probe_all()
    for name, availability in sorted(probes.items()):
        mark = "OK " if availability.usable else "НЕТ"
        print(f"[{mark}] {name:24} {availability.status.value:20} {availability.detail}")
    unusable = [n for n, a in probes.items() if not a.usable]
    print(f"\nдоступно {len(probes) - len(unusable)} из {len(probes)} источников")
    return 0


def cmd_factory_portfolio(args) -> int:
    """Портфель, каким его видит оператор поверх пакетов фабрики.

    Команда только читает: реальный реестр config/portfolio.json заполняет
    владелец. Возврат 3 означает, что ни один сайт не готов к работе с живыми
    данными — это нормальное состояние до передачи доменов и доступов, но
    молчаливым нулём его выдавать нельзя.
    """
    from seo_operator.factory_bridge import portfolio_view

    view = portfolio_view(REPO_ROOT)
    if args.json:
        print(json.dumps(view, ensure_ascii=False, indent=2))
    else:
        for site in view["sites"]:
            mark = "OK " if site["readiness"] == "READY" else "БЛОК"
            print(f"[{mark}] {site['site_id']:22} {site['readiness']:28} {site['base_url']}")
        counts = view["counts"]
        print(
            f"\nвсего сайтов {counts['total']}, готово {counts['ready']}, "
            f"заблокировано {counts['blocked']}"
        )
    return 0 if view["counts"]["ready"] else 3


def cmd_run(args, mode: Mode) -> int:
    op = _operator(args.fixture)
    pages_by_site = {}
    if args.fixture and FIXTURE_PAGES.exists():
        pages_by_site = {"fixture-anime": _load_pages(FIXTURE_PAGES)}

    result = op.run(mode, pages_by_site=pages_by_site, today=date.today())

    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, default=str))
    else:
        print(daily_report(result))

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(daily_report(result), encoding="utf-8")
        print(f"\nотчёт записан: {args.out}", file=sys.stderr)

    return 0


def cmd_weekly(args) -> int:
    """Weekly report over the runs recorded this week.

    With no historical runs stored yet, it summarises the current run and says
    so, rather than implying a week of history exists.
    """
    op = _operator(args.fixture)
    pages_by_site = {}
    if args.fixture and FIXTURE_PAGES.exists():
        pages_by_site = {"fixture-anime": _load_pages(FIXTURE_PAGES)}

    results = [op.run(Mode.DRY_RUN, pages_by_site=pages_by_site, today=date.today())]
    text = weekly_report(results, date.today())

    print(text)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"\nотчёт записан: {args.out}", file=sys.stderr)
    return 0


def cmd_analytics_collect(args) -> int:
    """Ежедневный сбор. Ничего не меняет и не отправляет — только читает.

    Возвращает 0 даже когда измерить не удалось ничего: отсутствие данных о
    неразвёрнутом сайте — это правильный результат, а не сбой сбора. Ненулевой
    код здесь означал бы, что таймер каждое утро рапортует об аварии там, где
    аварии нет.
    """
    from seo_operator.analytics_collect import collect

    report = collect(
        date1=args.date1,
        date2=args.date2,
        artifacts_dir=REPO_ROOT / "artifacts" / "analytics",
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        summary = report["summary"]
        print(f"период {report['period']['date1']} … {report['period']['date2']}")
        for domain in report["domains"]:
            print(
                f"\n{domain['domain']}  "
                f"измерено {domain['measured_count']}/{domain['total_count']}"
            )
            for item in domain["measurements"]:
                value = item["value"] if item["measured"] else f"не измерено — {item['reason']}"
                print(f"  {item['title']:34} {str(value)[:80]}")
        print(f"\n{summary['note']}")
    if args.out:
        pathlib_path = Path(args.out)
        pathlib_path.parent.mkdir(parents=True, exist_ok=True)
        pathlib_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


def cmd_host_verify(args) -> int:
    """
    Гейт BLOCKED_WRONG_HOST. Возвращает 3 при несовпадении, чтобы юниты
    и скрипты останавливались до, а не после изменений.
    """
    from seo_operator import hostcheck

    check = hostcheck.check(hostcheck.EXPECTED_HOST)
    print(check.render())
    return 0 if check.passed else 3


def cmd_portfolio_reconcile(args) -> int:
    """
    Портфель из всех доступных реестров. Один файл истиной не считается:
    config/portfolio.json может быть пуст, пока в analytics.json и
    config/directions/*.json уже есть домены.
    """
    from seo_operator import inventory

    inv, extra = inventory.build(
        repo_root=REPO_ROOT,
        host_available=args.assume_host,
        host_unavailable_reason="сессия выполняется не на целевом хосте",
    )
    if args.json:
        print(
            json.dumps(
                {
                    "portfolio_sites_total": inv.total,
                    "domains": {
                        d: {f: r.render_field(f) for f in sorted(r.facts)}
                        for d, r in sorted(inv.domains.items())
                    },
                    "inventory_drift": [
                        {"kind": d.kind.value, "domain": d.domain,
                         "detail": d.detail, "blocking": d.blocking}
                        for d in inv.drift
                    ],
                    "targets": extra["targets"],
                    "secret_hub": extra["secret_hub"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"PORTFOLIO_SITES_TOTAL={inv.total}")
        print()
        print(inventory.render_table(inv))
        print()
        print("INVENTORY_DRIFT:")
        for d in inv.drift:
            print(f"  - {'BLOCKING ' if d.blocking else ''}{d}")
    # Блокирующий drift — это состояние, требующее решения, а не ошибка команды.
    return 3 if any(d.blocking for d in inv.drift) else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="seo-operator", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("probe", help="проверить доступность источников")

    p = sub.add_parser(
        "factory-portfolio",
        help="портфель по пакетам сайтов фабрики (только чтение)",
    )
    p.add_argument("--json", action="store_true", help="машиночитаемый вывод")

    for name, help_text in (
        ("inventory", "read-only инвентаризация"),
        ("dry-run", "рассчитать изменения без записи"),
        ("canary", "применить изменения в пределах canary"),
        ("report", "сформировать ежедневный отчёт"),
        ("weekly", "сформировать недельный отчёт"),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument(
            "--fixture",
            action="store_true",
            help="использовать синтетический тенант вместо реального портфеля",
        )
        p.add_argument("--json", action="store_true", help="машиночитаемый вывод")
        p.add_argument("--out", help="записать отчёт в файл")

    sub.add_parser(
        "host-verify",
        help="проверить, что сессия выполняется на целевом хосте",
    )

    p = sub.add_parser(
        "portfolio-reconcile",
        help="собрать портфель из всех реестров и показать INVENTORY_DRIFT",
    )
    p.add_argument("--json", action="store_true", help="машиночитаемый вывод")
    p.add_argument(
        "--assume-host",
        action="store_true",
        help="считать nginx/systemd/deployment/live доступными (только на целевом хосте)",
    )

    p = sub.add_parser(
        "analytics-collect",
        help="read-only сбор показателей Метрики и Вебмастера",
    )
    p.add_argument("--date1", default="7daysAgo", help="начало периода")
    p.add_argument("--date2", default="yesterday", help="конец периода")
    p.add_argument("--json", action="store_true", help="машиночитаемый вывод")
    p.add_argument("--out", help="записать отчёт в файл")

    args = parser.parse_args(argv)

    if args.command == "host-verify":
        return cmd_host_verify(args)
    if args.command == "portfolio-reconcile":
        return cmd_portfolio_reconcile(args)
    if args.command == "analytics-collect":
        return cmd_analytics_collect(args)
    if args.command == "probe":
        return cmd_probe(args)
    if args.command == "factory-portfolio":
        return cmd_factory_portfolio(args)
    if args.command == "inventory":
        return cmd_run(args, Mode.INVENTORY)
    if args.command == "dry-run":
        return cmd_run(args, Mode.DRY_RUN)
    if args.command == "canary":
        return cmd_run(args, Mode.CANARY)
    if args.command == "report":
        return cmd_run(args, Mode.DRY_RUN)
    if args.command == "weekly":
        return cmd_weekly(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
