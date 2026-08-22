"""Operator command line.

seo-operator probe                 проверить доступность источников
seo-operator inventory             read-only инвентаризация
seo-operator dry-run [--fixture]   рассчитать изменения, ничего не записывая
seo-operator canary  [--fixture]   применить изменения в пределах canary
seo-operator observe --experiment  оценить эксперимент и решить keep/rollback
seo-operator report  [--fixture]   сформировать ежедневный отчёт
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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="seo-operator", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("probe", help="проверить доступность источников")

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

    args = parser.parse_args(argv)

    if args.command == "probe":
        return cmd_probe(args)
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
