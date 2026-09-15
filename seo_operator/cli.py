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
import os
import sys
from datetime import date, datetime, timezone
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
#: Куда ложатся ежедневные отчёты, пока адресат доставки не задан. Каталог
#: рабочий, а не репозиторный: отчёт — результат прогона, а не исходный текст.
REPORT_SPOOL = REPO_ROOT / "var" / "reports" / "seo"


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


#: Что именно обходит суточный цикл на каждом сайте. Набор один для всех витрин
#: и потому повторяем.
#:
#: Здесь только страницы для читателя. robots.txt, карта сайта и проверка
#: обработки 404 сюда не входят сознательно: это не HTML-страницы, и постраничные
#: проверки честно сообщили бы про них «нет title», «нет H1», «код 404» — три
#: находки из ничего на каждой витрине. Их место — отдельная стадия проверки
#: инфраструктуры с собственными ожиданиями, и она пока не написана.
DAILY_CRAWL_PATHS = ("/", "/catalog/")


def _crawl_real_portfolio(op: Operator) -> tuple[dict, list[str]]:
    """Обход рабочих сайтов. Отказ одного сайта не отменяет остальные."""
    from seo_operator.datasources.livecrawl import CrawlNotAllowedError, crawl_portfolio

    sites = [
        {"site_id": s.site_id, "base_url": s.base_url, "synthetic": s.synthetic}
        for s in op.portfolio.sites
    ]
    notes: list[str] = []
    pages: dict = {}
    for site in sites:
        try:
            pages.update(
                crawl_portfolio([site], paths_for=lambda _s: DAILY_CRAWL_PATHS)
            )
        except CrawlNotAllowedError as exc:
            notes.append(f"обход {site['site_id']} не выполнен: {exc}")
    return pages, notes


#: Адрес, который каждая витрина объявляет в config/SITE-MATRIX.json.
#: Объявление, которому ничего не соответствует, хуже отсутствующего — на него
#: ссылаются как на существующее, поэтому цикл его проверяет.
DECLARED_COVERAGE_ENDPOINT = "/api/v1/coverage"


def _add_infrastructure_findings(op: Operator, result) -> None:
    """robots.txt, карта сайта, обработка отсутствующего адреса, объявленный endpoint."""
    from seo_operator.datasources.livecrawl import CrawlNotAllowedError
    from seo_operator.infrastructure_probe import as_dicts, curl_probe, probe_site

    for site in op.portfolio.sites:
        if site.synthetic:
            continue
        try:
            found = probe_site(
                site.base_url,
                fetcher=curl_probe,
                # Ожидание берётся у витрины, а не угадывается. Источника
                # редакционной политики у цикла пока нет, поэтому содержимое
                # карты не оценивается вовсе: и «должна быть пустой», и «должна
                # быть полной» были бы выдумкой. Первый вариант этой стадии
                # выбрал «пустая» и объявил дефектом нормальные карты Lords с
                # их пятьюдесятью тысячами адресов.
                expect_sitemap_entries=None,
                coverage_endpoint=DECLARED_COVERAGE_ENDPOINT,
            )
        except CrawlNotAllowedError as exc:
            result.notes.append(f"инфраструктура {site.site_id} не проверена: {exc}")
            continue
        result.findings.extend(
            {**f, "site_id": site.site_id} for f in as_dicts(found)
        )


#: Где лежат профили витрин. В репозитории их нет — источник живёт на
#: управляющем хосте, поэтому путь задаётся переменной. Без него слой профиля
#: не измеряется и в вердикт не входит, а не считается открытым.
SITE_PROFILES_DIR_ENV = "SEO_SITE_PROFILES_DIR"


def _profile_indexing_flag(site_id: str) -> tuple[bool | None, bool]:
    """Значение флага публикации и признак того, что слой вообще измерялся."""
    directory = os.environ.get(SITE_PROFILES_DIR_ENV)
    if not directory:
        return None, False
    path = Path(directory) / f"{site_id}.json"
    if not path.exists():
        return None, False
    try:
        profile = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        # Профиль есть, но прочитать не вышло — это измеренный слой без ответа,
        # и он обязан поднять тревогу, а не промолчать.
        return None, True
    return profile.get("seo_profile", {}).get("indexing_enabled"), True


def _add_indexing_lock_findings(op: Operator, result) -> None:
    """Слои запрета индексации обязаны говорить одно и то же.

    Опасно не открытое и не закрытое состояние, а расхождение: один слой сняли,
    остальные держат, и снаружи всё выглядит по-прежнему. Цикл не задавал этого
    вопроса — и 2026-09-15 не заметил, как на одной витрине выкатили мета-тег
    `index, follow` поверх запрещающих заголовка и robots.txt.
    """
    from seo_operator.datasources.livecrawl import CrawlNotAllowedError
    from seo_operator.indexing_lock import findings as lock_findings
    from seo_operator.indexing_lock import read_state, summarize
    from seo_operator.infrastructure_probe import curl_probe

    states = []
    for site in op.portfolio.sites:
        if site.synthetic:
            continue
        base = site.base_url.rstrip("/")
        try:
            page = curl_probe(f"{base}/")
            robots = curl_probe(f"{base}/robots.txt")
        except CrawlNotAllowedError as exc:
            result.notes.append(f"замок {site.site_id} не проверен: {exc}")
            continue
        flag, measured = _profile_indexing_flag(site.site_id)
        state = read_state(
            site.site_id,
            # curl_probe не возвращает заголовки отдельно; признак заголовка
            # берётся тем же запросом через отдельный вызов ниже.
            response_headers=_response_headers(f"{base}/"),
            robots_txt=robots.body,
            html=page.body,
            profile_indexing_enabled=flag,
            profile_measured=measured,
        )
        states.append(state)
        result.findings.extend(
            {**f, "site_id": site.site_id}
            for f in lock_findings(state, expected=site.indexing_expected)
        )

    if not states:
        return
    summary = summarize(states)
    note = (
        f"замок индексации: закрыт полностью на {summary['closed']} из {summary['total']}, "
        f"расходится на {summary['mixed']}, открыт на {summary['open']}"
    )
    if summary["mixed_sites"]:
        note += f"; расхождение: {', '.join(summary['mixed_sites'])}"
    if states[0].unmeasured_layers:
        note += (
            f" (слои не измерялись: {', '.join(states[0].unmeasured_layers)} — "
            f"задайте {SITE_PROFILES_DIR_ENV})"
        )
    result.notes.append(note)


def _response_headers(url: str) -> str:
    """Только заголовки ответа. Отдельный запрос: тело здесь не нужно."""
    import subprocess

    from seo_operator.datasources.livecrawl import ensure_allowed

    ensure_allowed(url)
    proc = subprocess.run(
        ["curl", "-sSI", "-L", "--max-time", "25", url], capture_output=True, text=True
    )
    return proc.stdout


def _add_eligibility_note(op: Operator, result, pages_by_site: dict) -> None:
    """Поадресный вердикт по тем страницам, которые цикл действительно видел."""
    from seo_operator.eligibility import classify_all, summarize

    verdicts = []
    for site in op.portfolio.sites:
        pages = pages_by_site.get(site.site_id)
        if not pages:
            continue
        verdicts.extend(classify_all(pages, site_host=site.domain))
    if not verdicts:
        return
    summary = summarize(verdicts)
    result.notes.append(
        f"готовность адресов: обойдено {summary.total}, READY {summary.ready}, "
        f"HOLD {summary.hold}, UNKNOWN {summary.unknown} "
        f"(покрытие {summary.coverage_percent}%) — это выборка обхода, а не весь корпус"
    )


def cmd_indexing_drift(args) -> int:
    """Read-only сверка индексации с решением владельца.

    Ничего не меняет. Возврат 1 означает расхождение — в том числе когда
    состояние домена не удалось измерить: молчание не проходит как «в порядке».
    """
    import subprocess as _sp

    from seo_operator.indexing_drift import Response, check_portfolio

    РАЗДЕЛИТЕЛЬ = "::drift::"

    def получить(url: str) -> Response:
        # Один GET: код, заголовки и тело из одного ответа. HEAD как
        # единственное доказательство не используется намеренно.
        готово = _sp.run(
            ["curl", "-sS", "-D", "-", "--max-time", str(args.timeout),
             "-w", f"{РАЗДЕЛИТЕЛЬ}%{{http_code}}", url],
            capture_output=True, text=True,
        )
        if готово.returncode != 0:
            return Response(None, "", "", error=f"curl {готово.returncode}")
        вывод = готово.stdout
        код = None
        if РАЗДЕЛИТЕЛЬ in вывод:
            вывод, _, хвост = вывод.rpartition(РАЗДЕЛИТЕЛЬ)
            код = int(хвост) if хвост.strip().isdigit() else None
        # Делим по ПЕРВОЙ пустой строке, а не по последней: в HTML пустые
        # строки встречаются, и разбиение с конца отдавало под видом заголовков
        # кусок разметки. Из-за этого закрытые витрины Lords показывались как
        # «слои разошлись». Переходов здесь нет — блок заголовков ровно один.
        заголовки, разделитель, тело = вывод.partition("\r\n\r\n")
        if not разделитель:
            заголовки, _, тело = вывод.partition("\n\n")
        return Response(код, заголовки, тело)

    сайты = json.loads((REPO_ROOT / "config" / "portfolio.json").read_text(encoding="utf-8"))
    отчёт = check_portfolio(сайты["sites"], fetcher=получить)

    for d in отчёт.domains:
        метка = "OK  " if d.matches else "ДРЕЙФ"
        print(f"{метка} {d.domain:24} ожидание={d.expected:10} факт={d.actual:10} "
              f"{'; '.join(d.reasons)}")
    сводка = отчёт.summary()
    print(f"\nитого: открыт {сводка['open']}, закрыт {сводка['closed']}, "
          f"расходится {сводка['mixed']}, не измерено {сводка['unmeasured']}")
    if args.json:
        print(json.dumps(сводка, ensure_ascii=False))
    return 0 if отчёт.ok else 1


def cmd_run(args, mode: Mode) -> int:
    op = _operator(args.fixture)
    pages_by_site = {}
    crawl_notes: list[str] = []
    if args.fixture:
        if FIXTURE_PAGES.exists():
            pages_by_site = {"fixture-anime": _load_pages(FIXTURE_PAGES)}
    elif not args.no_crawl:
        pages_by_site, crawl_notes = _crawl_real_portfolio(op)

    result = op.run(mode, pages_by_site=pages_by_site, today=date.today())
    result.notes.extend(crawl_notes)

    if not args.fixture and not args.no_crawl:
        _add_infrastructure_findings(op, result)
        _add_indexing_lock_findings(op, result)
        _add_eligibility_note(op, result, pages_by_site)

    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, default=str))
    else:
        print(daily_report(result))

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(daily_report(result), encoding="utf-8")
        print(f"\nотчёт записан: {args.out}", file=sys.stderr)

    if not args.no_spool:
        _spool_report(args, result)

    return 0


def _spool_report(args, result) -> None:
    """Сложить отчёт в spool. Адресат доставки не задан — отчёт всё равно цел.

    Блокер доставки не является поводом терять отчёт: цикл, отработавший без
    читателя, обязан оставить след.
    """
    from seo_operator.report_spool import store

    root = Path(args.spool) if args.spool else REPORT_SPOOL
    entry = store(
        root,
        run_id=getattr(result, "run_id", None)
        or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        day=date.today(),
        markdown=daily_report(result),
        payload=result.to_dict(),
        destination=os.environ.get("SEO_REPORT_DESTINATION") or None,
    )
    print(f"\nотчёт сохранён: {entry.markdown_path}", file=sys.stderr)
    if entry.owner_action:
        print(f"OWNER_ACTION_REQUIRED: {entry.owner_action}", file=sys.stderr)


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
        p.add_argument(
            "--no-crawl",
            action="store_true",
            help="не обходить живые витрины (только офлайн-часть цикла)",
        )
        p.add_argument("--spool", help="каталог накопления ежедневных отчётов")
        p.add_argument(
            "--no-spool",
            action="store_true",
            help="не складывать отчёт в spool (для разовых ручных прогонов)",
        )
        p.add_argument("--json", action="store_true", help="машиночитаемый вывод")
        p.add_argument("--out", help="записать отчёт в файл")

    p = sub.add_parser(
        "indexing-drift",
        help="read-only сверка индексации с решением владельца (ничего не меняет)",
    )
    p.add_argument("--timeout", type=int, default=60, help="срок одного запроса")
    p.add_argument("--json", action="store_true", help="машиночитаемая сводка")

    p = sub.add_parser(
        "analytics-collect",
        help="read-only сбор показателей Метрики и Вебмастера",
    )
    p.add_argument("--date1", default="7daysAgo", help="начало периода")
    p.add_argument("--date2", default="yesterday", help="конец периода")
    p.add_argument("--json", action="store_true", help="машиночитаемый вывод")
    p.add_argument("--out", help="записать отчёт в файл")

    args = parser.parse_args(argv)

    if args.command == "indexing-drift":
        return cmd_indexing_drift(args)
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
