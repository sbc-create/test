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

    p = sub.add_parser(
        "analytics-collect",
        help="read-only сбор показателей Метрики и Вебмастера",
    )
    p.add_argument("--date1", default="7daysAgo", help="начало периода")
    p.add_argument("--date2", default="yesterday", help="конец периода")
    p.add_argument("--json", action="store_true", help="машиночитаемый вывод")
    p.add_argument("--out", help="записать отчёт в файл")

    p = sub.add_parser("notify", help="доставка отчётов в Telegram (только из службы с LoadCredential)")
    p.add_argument("action", choices=("discover", "test", "daily", "alerts"))

    sub.add_parser("editor-gate", help="лёгкая проверка: нужен ли запуск модели (без модели и сети)")
    p = sub.add_parser("editor-held", help="закрыт ли адрес прежним отказом в пределах срока удержания")
    p.add_argument("url")
    sub.add_parser("editor-run-status", help="запуски фонового редактора: по расписанию и ручные")
    p = sub.add_parser("editor-run-verify", help="проверить запуск фонового редактора по следам")
    p.add_argument("--run-id", required=True)
    p.add_argument("--started-at", required=True)
    p.add_argument("--finished-at", required=True)
    p.add_argument("--out")

    p = sub.add_parser("seo-tech-next", help="техническое SEO: захватить следующую задачу очереди (без модели)")
    p.add_argument("--run-id", default="")
    p.add_argument("--peek", action="store_true",
                   help="только узнать, есть ли готовая задача: без захвата, уборки и модели (код 10 — есть, 0 — нет)")
    p = sub.add_parser("seo-tech-verify", help="техническое SEO: вердикт прогона по следам (ветка, D203, run.sh)")
    p.add_argument("--run-id", required=True)
    p.add_argument("--no-run-all", action="store_true", help="не гонять полный checks/run.sh")
    p.add_argument("--record", action="store_true", help="дописать вердикт в var/seo-tech/runs.jsonl")
    p.add_argument("--extra", default="{}", help="JSON-поля к записи (trigger, model_exit, …)")
    sub.add_parser("seo-tech-status", help="техническое SEO: состояние задач очереди по следам")
    p = sub.add_parser("seo-tech-publish", help="техническое SEO: выпустить проверенные ветки штатным путём (без модели)")
    p.add_argument("--dry-run", action="store_true", help="только сведения и решение, без push и заявок")
    p.add_argument("--limit", type=int, default=5)
    sub.add_parser("seo-tech-publish-status", help="техническое SEO: подготовлено / опубликовано по задачам")
    p = sub.add_parser("seo-tech-backlog", help="техническое SEO: пополнить очередь (диагностика, аудит ссылок, переносы)")
    p.add_argument("--if-older", type=int, default=0, help="пропустить, если прошлый проход моложе N секунд")
    p.add_argument("--links", choices=("auto", "yes", "no"), default="auto", help="аудит внутренних ссылок (auto — раз в сутки)")

    p = sub.add_parser("webmaster-apply-mapping",
                       help="перенести подтверждённые Вебмастером host_id в реестр (только локально)")
    p.add_argument("--apply", action="store_true", help="записать; без флага — только показать")

    sub.add_parser(
        "webmaster-inventory",
        help="read-only: почему у доменов нет данных Вебмастера (нет в аккаунте / не подтверждён / сопоставление)",
    )

    p = sub.add_parser(
        "regular",
        help="регулярный прогон по сети: check (6 ч), daily (09:00 МСК), weekly",
    )
    p.add_argument("mode", choices=("check", "daily", "weekly", "hourly", "status"))
    p.add_argument("--trigger", default=None, help="systemd-timer или manual")
    p.add_argument("--root", default=None, help="каталог состояния")

    args = parser.parse_args(argv)

    if args.command == "notify":
        from seo_operator import notify

        return notify.main([args.action])
    if args.command == "editor-gate":
        from seo_operator import editor_run

        # Коды: 10 — запускать, 0 — штатный отказ (пауза, ресурсы, нет работы),
        # 3 — НЕИСПРАВНОСТЬ шлюза. Прежде исключение давало 1, и editor-run.sh
        # превращал его в штатный выход 0 — поломка была неотличима от паузы.
        try:
            decision = editor_run.gate(refresh=True)
        except Exception as exc:  # noqa: BLE001 — любая поломка шлюза называется
            print(json.dumps({"run": False, "state": "error",
                              "reason": f"шлюз неисправен: {type(exc).__name__}: {exc}"[:400]},
                             ensure_ascii=False))
            return 3
        if decision["run"]:
            # Редактор идёт по этому списку, а не по сырому файлу кандидатов:
            # 2026-10-08 17:05 он взял первый кандидат, уже закрытый им же, и
            # остановился, хотя три других были свободны.
            out = editor_run.STATE / "next.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            # Разрешённые домены — из того же списка, по которому шлюз считает
            # работу: промпт раньше перечислял их вручную, и сайт, добавленный в
            # цикл (zonafilm.cc, 2026-10-10), модель отвергала как неразрешённый.
            # Переданные черновики — отдельное поле, а не «ещё кандидаты»:
            # у них уже есть текст и автор, и разбирать их надо иначе, чем
            # искать, о чём писать. Промпт велит начинать с них.
            out.write_text(json.dumps({"reason": decision["reason"],
                                       # Партия одного направления (50/50, 13.10):
                                       # домены партии, а не весь список.
                                       "domains": decision.get("domains") or editor_run.allowed_domains(),
                                       "direction": decision.get("allocated"),
                                       "allocation_note": decision.get("allocation_note", ""),
                                       "handoffs": decision.get("handoffs", []),
                                       "candidates": decision.get("next", [])},
                                      ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps({k: v for k, v in decision.items() if k != "next"}, ensure_ascii=False))
        return 10 if decision["run"] else 0
    if args.command == "editor-held":
        # Очередь повторяет SOURCES_MISSING через 24 ч и IDENTITY_UNCLEAR через
        # 72 ч без изменения условий (handoff §15.5); фабрика держит их 14
        # суток и открывает раньше только при новом реестре источников. Ответ
        # «held» — повторный сбор фактов не нужен: закрыть тем же исходом.
        import datetime as _dt

        from seo_operator import regular

        now = _dt.datetime.now(_dt.timezone.utc)
        urls, slugs = regular.result_holds(regular.SOURCES["queue_events"], now)
        ключ = args.url.rstrip("/").lower()
        slug = ключ.rsplit("/", 1)[-1]
        held = ключ in urls or slug in slugs
        last = regular.last_outcome(regular.SOURCES["queue_events"], args.url) if held else None
        print(json.dumps({"url": args.url, "held": held, "last": last}, ensure_ascii=False))
        return 0
    if args.command == "editor-run-status":
        from seo_operator import editor_run

        print(json.dumps(editor_run.status(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "editor-run-verify":
        from seo_operator import editor_run

        extra = ["--run-id", args.run_id, "--started-at", args.started_at, "--finished-at", args.finished_at]
        if args.out:
            extra += ["--out", args.out]
        return editor_run.main(extra)
    if args.command == "seo-tech-next":
        from seo_operator import tech_run

        # Коды: 10 — задача захвачена (var/seo-tech/next.json), 0 — работы нет,
        # 3 — неисправность (очередь не читается, git отказал) — не тихий 0.
        if args.peek:
            try:
                готовые = [з["id"] for з in tech_run.candidates(tech_run.load_queue())]
            except Exception as exc:  # noqa: BLE001
                print(json.dumps({"ready": None, "state": "error", "reason": f"{type(exc).__name__}: {exc}"[:400]},
                                 ensure_ascii=False))
                return 3
            print(json.dumps({"ready": готовые}, ensure_ascii=False))
            return 10 if готовые else 0
        if not args.run_id:
            print(json.dumps({"run": False, "state": "error", "reason": "нужен --run-id"}, ensure_ascii=False))
            return 3
        try:
            убрано = tech_run.prune_worktrees()
            захват = tech_run.claim_next(tech_run.load_queue(), args.run_id)
            if захват is None:
                print(json.dumps({"run": False, "reason": "нет задач queued с запасом попыток и без живого захвата",
                                  "pruned": убрано}, ensure_ascii=False))
                return 0
            захват = {**захват, "pruned": убрано}
        except Exception as exc:  # noqa: BLE001 — поломка называется
            print(json.dumps({"run": False, "state": "error", "reason": f"{type(exc).__name__}: {exc}"[:400]},
                             ensure_ascii=False))
            return 3
        print(json.dumps({"run": True, **захват}, ensure_ascii=False))
        return 10
    if args.command == "seo-tech-publish":
        from seo_operator import tech_publish

        итог = tech_publish.run(dry_run=args.dry_run, limit=args.limit)
        print(json.dumps(итог, ensure_ascii=False, indent=1))
        return 0
    if args.command == "seo-tech-publish-status":
        from seo_operator import tech_publish

        print(json.dumps(tech_publish.status(), ensure_ascii=False, indent=1))
        return 0
    if args.command == "seo-tech-backlog":
        from seo_operator import tech_backlog, tech_run

        if args.if_older and not tech_backlog.due(tech_run.STATE, args.if_older):
            print(json.dumps({"skipped": "прошлый проход моложе --if-older"}, ensure_ascii=False))
            return 0
        итог = tech_backlog.run(links={"auto": None, "yes": True, "no": False}[args.links])
        print(json.dumps(итог, ensure_ascii=False, indent=1))
        return 0
    if args.command == "seo-tech-verify":
        from seo_operator import tech_run

        итог = tech_run.verify(args.run_id, run_all=not args.no_run_all)
        if args.record:
            итог = tech_run.record(итог, json.loads(args.extra))
            tech_run.release_worktree(args.run_id)
        print(json.dumps(итог, ensure_ascii=False, indent=1))
        return 0 if итог["verdict"] == "VERIFIED" else 2
    if args.command == "seo-tech-status":
        from seo_operator import tech_run

        сводка = tech_run.task_state()
        print(json.dumps([{"id": з["id"], "site": з.get("site"), "queue_status": з.get("status"),
                           **сводка.get(з["id"], {})} for з in tech_run.load_queue()],
                         ensure_ascii=False, indent=1, default=str))
        return 0
    if args.command == "webmaster-apply-mapping":
        from seo_operator import webmaster_inventory

        result = webmaster_inventory.apply_mapping(dry_run=not args.apply)
        print(json.dumps(result, ensure_ascii=False, indent=1))
        return 0
    if args.command == "webmaster-inventory":
        from seo_operator import webmaster_inventory

        return webmaster_inventory.main()
    if args.command == "regular":
        from seo_operator import regular

        extra = [args.mode]
        if args.mode == "status":
            return regular.main(extra)
        if args.trigger:
            extra += ["--trigger", args.trigger]
        if args.root:
            extra += ["--root", args.root]
        return regular.main(extra)
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
