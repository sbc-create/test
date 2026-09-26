"""Командный интерфейс переносимой ячейки сайта.

Все команды принимают `--site` и все изменяющие — `--dry-run`. Это не
украшение: переносить сайт вслепую нельзя, а «посмотреть, что будет» обязано
быть дешевле, чем «сделать и откатить».

Команда никогда не переключает домен и не трогает живые сайты. Переключение
маршрутизации — отдельный разрешённый шаг с подтверждением владельца.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from factory.cell import onboarding, registry, siterepo, sync, templates, transfer
from factory.cell import release as release_mod
from factory.paths import PATHS


def _print(payload) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def _layout(args) -> transfer.Layout:
    root = Path(args.root) if args.root else PATHS.var / "cells" / args.site
    return transfer.Layout(root=root)


def cmd_registry(args) -> int:
    if args.site:
        try:
            _print(registry.route(args.site))
        except registry.RegistryError as exc:
            print(f"BLOCKED_INPUT: {exc}", file=sys.stderr)
            return 2
        return 0
    cells = [c.to_dict() for c in registry.all_cells()]
    problems = registry.consistency_report()
    _print({"cells": cells, "total": len(cells), "consistency_problems": problems})
    return 0


def cmd_templates(args) -> int:
    pool = templates.load()
    free = templates.free_templates()
    _print({
        "free": list(free),
        "free_total": len(free),
        "templates": [{"template_id": e["template_id"], "status": e["status"],
                       "site_id": (e.get("assignment") or {}).get("site_id")}
                      for e in pool["templates"]],
    })
    if not free:
        print("Свободных шаблонов нет: пополнение пула — вход от владельца.",
              file=sys.stderr)
    return 0


def cmd_reserve(args) -> int:
    if args.dry_run:
        _print({"status": "dry-run", "would_reserve_for": args.site,
                "free": list(templates.free_templates())})
        return 0
    try:
        reservation = templates.reserve(order_id=args.order, site_id=args.site,
                                        domain=args.domain, family=args.family)
    except templates.PoolExhausted as exc:
        print(f"BLOCKED_INPUT: {exc}", file=sys.stderr)
        return 2
    except templates.TemplateError as exc:
        print(f"BLOCKED_INPUT: {exc}", file=sys.stderr)
        return 2
    _print({"template_id": reservation.template_id, "status": reservation.status})
    return 0


def cmd_repo(args) -> int:
    cell = registry.resolve(args.site)
    pool_entry = next((e for e in templates.load()["templates"]
                       if e["template_id"] == cell.template.get("template_id")), None)
    if pool_entry is None:
        print(f"BLOCKED_INPUT: шаблон {cell.template.get('template_id')} не найден в пуле",
              file=sys.stderr)
        return 2
    destination = Path(args.destination) if args.destination else cell.repo_path
    if args.dry_run:
        _print({"status": "dry-run", "would_create": str(destination),
                "template_id": pool_entry["template_id"]})
        return 0
    repo = siterepo.generate(
        site_id=cell.site_id, domain=cell.domain, aliases=cell.aliases,
        template_id=pool_entry["template_id"],
        template_source=PATHS.root / pool_entry["source"],
        modules=tuple(args.modules or ()), pins=cell.pins,
        publisher=cell.publisher, deploy_target=cell.deploy_target,
        destination=destination, force=args.force)
    _print({"site_id": repo.site_id, "path": str(repo.path), "commit": repo.commit})
    return 0


def cmd_release(args) -> int:
    cell = registry.resolve(args.site)
    repo = Path(args.repo) if args.repo else cell.repo_path
    output = Path(args.output) if args.output else PATHS.artifacts / "cells" / cell.site_id
    if args.dry_run:
        _print({"status": "dry-run", "repo": str(repo),
                "head": siterepo.head_commit(repo),
                "clean": siterepo.is_clean(repo)})
        return 0
    rel = release_mod.build(site_id=cell.site_id, repo=repo, output_dir=output)
    registry.update(cell.site_id, {"deployed": {
        "release_digest": rel.digest, "source_commit": rel.source_commit,
        "artifact": str(rel.artifact), "built_at": rel.manifest["built_at"]}})
    _print({"artifact": str(rel.artifact), "manifest": str(rel.manifest_path),
            "digest": rel.digest, "source_commit": rel.source_commit})
    return 0


def cmd_install(args) -> int:
    cell = registry.resolve(args.site)
    artifact = Path(args.artifact)
    manifest = Path(args.manifest) if args.manifest else Path(
        str(artifact).replace(".tar.gz", f".{release_mod.MANIFEST_NAME}"))
    result = transfer.install(site_id=cell.site_id, artifact=artifact,
                              manifest=manifest, layout=_layout(args).ensure(),
                              dry_run=args.dry_run,
                              expected_digest=args.expect_digest)
    _print(result)
    return 0


def cmd_verify(args) -> int:
    cell = registry.resolve(args.site)
    routes = tuple(args.route or ())
    report = transfer.verify(site_id=cell.site_id, layout=_layout(args),
                             expected_routes=routes)
    _print(report)
    return 0 if report["status"] == "PASS" else 1


def cmd_export(args) -> int:
    cell = registry.resolve(args.site)
    destination = Path(args.output) if args.output else (
        PATHS.var / "cells" / cell.site_id / "export")
    pkg = transfer.export(site_id=cell.site_id, layout=_layout(args),
                          destination=destination, dry_run=args.dry_run)
    _print({"path": str(pkg.path), **pkg.manifest})
    return 0


def cmd_cutover(args) -> int:
    cell = registry.resolve(args.site)
    target = transfer.Layout(root=Path(args.target)).ensure()
    result = transfer.cutover(site_id=cell.site_id, source=_layout(args),
                              target=target, reason=args.reason,
                              dry_run=args.dry_run)
    _print(result)
    return 0 if result["status"] in ("PASS", "dry-run") else 1


def cmd_rollback(args) -> int:
    cell = registry.resolve(args.site)
    result = transfer.rollback(site_id=cell.site_id, layout=_layout(args),
                               reason=args.reason, dry_run=args.dry_run)
    _print(result)
    return 0


def cmd_freshness(args) -> int:
    cell = registry.resolve(args.site)
    path = _layout(args).data / "sync-checkpoint.json"
    _print(sync.freshness(path, cell.site_id))
    return 0


def cmd_onboarding(args) -> int:
    root = PATHS.var / "cells" / "onboarding"
    root.mkdir(parents=True, exist_ok=True)
    path = onboarding.progress_path(root, args.order)
    if not path.exists():
        print(f"BLOCKED_INPUT: заказа {args.order} нет", file=sys.stderr)
        return 2
    progress = onboarding.Progress.from_dict(json.loads(path.read_text(encoding="utf-8")))
    _print(progress.summary())
    return 0 if progress.complete else 1


def cmd_extracted(args) -> int:
    """Перечислить выделенные сайты либо отказать старому пути выкладки.

    Нужна старым сценариям хоста: они написаны на shell и работают списком
    витрин, а знание о том, кто уже уехал в свой репозиторий, обязано быть в
    одном месте, а не продублировано в каждом сценарии своим списком.

    Отказ — на весь запуск, а не на одну витрину: сценарий, тронувший две из
    трёх, оставляет контур в состоянии, которого нет ни в одном отчёте.
    """
    выделенные = registry.extracted_sites()
    проверяемые = [s for s in (args.modules or []) if s]
    if not проверяемые:
        _print({"extracted": выделенные, "total": len(выделенные)})
        return 0
    конфликты = {s: выделенные[s] for s in проверяемые if s in выделенные}
    if конфликты:
        for сайт, remote in sorted(конфликты.items()):
            print(f"BLOCKED_SITE_EXTRACTED: {сайт} выделен в {remote}; "
                  "общий путь выкладки его не трогает", file=sys.stderr)
        return 3
    return 0


def cmd_activate(args) -> int:
    """Активация зарегистрированного сайта из коммита его репозитория.

    Никакого пути к скрипту или артефакту команда не принимает: это и есть
    граница. Подробности — `factory/cell/admin_exec.py`.
    """
    from factory.cell import admin_exec
    if not args.site or not args.commit:
        print("нужны --site и --commit", file=sys.stderr)
        return 2
    try:
        # Сухой прогон — умолчание КОМАНДЫ, а не только модуля. Флаг
        # `--dry-run` как единственная защита означал бы, что забытый флаг
        # переключает боевую витрину: команда без аргументов обязана быть
        # безопасной.
        итог = admin_exec.активировать(
            args.site, commit=args.commit,
            dry_run=not args.confirm_activation,
            expect_digest=args.expect_digest or None)
    except admin_exec.ExecutorRefused as exc:
        print(f"BLOCKED_INPUT: {exc}", file=sys.stderr)
        return 2
    _print(итог)
    return 0 if итог["status"] in ("dry-run", "activated") else 1


def cmd_deliver(args) -> int:
    """Опубликовать обновлённый контент в хранилища выделенных ячеек."""
    from factory.cell import delivery
    if args.site:
        try:
            итоги = [delivery.доставить(args.site, dry_run=args.dry_run)]
        except delivery.DeliveryError as exc:
            print(f"BLOCKED_INPUT: {exc}", file=sys.stderr)
            return 2
    else:
        итоги = delivery.доставить_всем(dry_run=args.dry_run)
    _print({"dry_run": args.dry_run, "sites": [и.as_dict() for и in итоги]})
    return 0


def cmd_runtime(args) -> int:
    """Где витрина живёт: ответ для производителей содержимого."""
    from factory.cell import runtime as rt
    if args.site:
        try:
            _print(rt.размещение(args.site).as_dict())
        except (rt.RuntimeUnknown, registry.RegistryError) as exc:
            print(f"BLOCKED_INPUT: {exc}", file=sys.stderr)
            return 2
        return 0
    _print(rt.для_производителя())
    return 0


def cmd_submit(args) -> int:
    """Подать заявку на выпуск. SHA и digest приходят из проверенной сборки."""
    from factory.cell import queue as q
    if not (args.site and args.commit and args.expect_digest):
        print("нужны --site, --commit и --expect-digest", file=sys.stderr)
        return 2
    try:
        заявка = q.собрать(args.site, args.commit, args.expect_digest,
                           operation=args.cell_operation, ci_run=args.ci_run or "",
                           repo=args.repo or "", note=args.reason)
        итог = q.подать(заявка)
    except q.RequestRejected as exc:
        print(f"BLOCKED_INPUT: {exc}", file=sys.stderr)
        return 2
    _print(итог)
    return 0


def cmd_trigger(args) -> int:
    """Опросить GitHub и подать заявки на невыложенные выпуски."""
    from factory.cell import trigger as tr
    if args.site:
        try:
            итоги = [tr.проверить_сайт(args.site, submit=args.confirm_activation)]
        except (tr.TriggerError, registry.RegistryError) as exc:
            print(f"BLOCKED_INPUT: {exc}", file=sys.stderr)
            return 2
    else:
        итоги = tr.обойти(submit=args.confirm_activation)
    _print({"submitted": args.confirm_activation, "sites": итоги})
    return 0


def cmd_serve(args) -> int:
    """Разобрать очередь заявок. Привилегированная сторона."""
    from factory.cell import executor
    итоги = executor.обслужить_очередь(dry_run=not args.confirm_activation)
    _print({"processed": len(итоги), "results": итоги})
    return 0 if all(и.get("status") == "ok" for и in итоги) else 1


def cmd_ci_ready(args) -> int:
    """Готов ли исполнитель проверять происхождение выпуска.

    Печатает состояние по каждому репозиторию и возвращает ненулевой код, если
    хотя бы один недоступен: «установлен» и «готов к выпуску» — разные вещи, и
    сценарий установки обязан их различать.
    """
    from factory.cell import executor
    итог = executor.готовность_проверки()
    print(json.dumps(итог, ensure_ascii=False, indent=2))
    return 0 if итог["ready"] else 1


def cmd_provenance(args) -> int:
    """Какой выпуск исполняется и кем установлен. Обход очереди виден сразу."""
    from factory.cell import executor
    итог = executor.происхождение_выпусков()
    print(json.dumps(итог, ensure_ascii=False, indent=2))
    return 1 if итог["bypassed"] else 0


def cmd_newsite(args) -> int:
    """Новый сайт семейства ИЗ ШАБЛОНА, а не с чужого домена.

    Отличие от `repo`: тот выделяет действующий сайт и берёт рантайм из его
    релиза на хосте. Здесь исходник — сам репозиторий шаблона, и закрепление
    называет его коммит. Иначе исправление, внесённое в шаблон, до новых
    витрин не доезжает.
    """
    from factory.cell import newsite

    пробелы = [имя for имя, значение in (
        ("--site", args.site), ("--domain", args.domain),
        ("--template", getattr(args, "template", None)),
        ("--port", getattr(args, "port", None))) if not значение]
    if пробелы:
        _print({"status": "BLOCKED_INPUT", "missing": пробелы})
        return 2
    заказ = newsite.Заказ(
        site_id=args.site, domain=args.domain, profile=args.template,
        port=int(args.port), family=args.family or "lords",
        site_name=getattr(args, "site_name", "") or "",
        remote=getattr(args, "remote", "") or "")
    куда = Path(args.destination) if args.destination else (
        PATHS.root / "var" / "new-sites" / заказ.site_id)
    if args.dry_run:
        _print({"status": "plan", "site_id": заказ.site_id, "destination": str(куда),
                "profile": заказ.profile,
                "runtime_files": list(newsite.РАНТАЙМ_LORDS)})
        return 0
    реестр = Path(args.registry) if getattr(args, "registry", None) else None
    итог = newsite.создать(заказ, корень=PATHS.root, куда=куда, force=args.force,
                           реестр=реестр,
                           регистрировать=not getattr(args, "no_register", False))
    _print(итог)
    return 0


ACTIONS = {
    "newsite": cmd_newsite,
    "registry": cmd_registry,
    "templates": cmd_templates,
    "reserve": cmd_reserve,
    "repo": cmd_repo,
    "release": cmd_release,
    "install": cmd_install,
    "verify": cmd_verify,
    "export": cmd_export,
    "cutover": cmd_cutover,
    "rollback": cmd_rollback,
    "freshness": cmd_freshness,
    "onboarding": cmd_onboarding,
    "extracted": cmd_extracted,
    "activate": cmd_activate,
    "deliver": cmd_deliver,
    "runtime": cmd_runtime,
    "submit": cmd_submit,
    "serve": cmd_serve,
    "trigger": cmd_trigger,
    "ci-ready": cmd_ci_ready,
    "provenance": cmd_provenance,
}


def register(subparsers) -> None:
    parser = subparsers.add_parser(
        "cell", help="переносимая ячейка сайта: реестр, шаблон, repo, релиз, перенос")
    parser.add_argument("cell_action", choices=sorted(ACTIONS))
    parser.add_argument("--site", help="site_id или домен")
    parser.add_argument("--domain", help="домен для нового заказа")
    parser.add_argument("--order", help="идентификатор заказа (идемпотентность)")
    parser.add_argument("--family", help="семейство шаблонов")
    parser.add_argument("--repo", help="путь к проекту сайта")
    parser.add_argument("--destination", help="куда создать проект сайта")
    parser.add_argument("--template", help="профиль шаблона для newsite")
    parser.add_argument("--port", help="порт витрины для newsite")
    parser.add_argument("--site-name", dest="site_name",
                        help="видимое имя витрины для newsite")
    parser.add_argument("--remote",
                        help="адрес собственного репозитория сайта; без него "
                             "доставка содержимого в ячейку отказывает")
    parser.add_argument("--registry",
                        help="файл реестра ячеек (по умолчанию config/site-cells.json)")
    parser.add_argument("--no-register", dest="no_register", action="store_true",
                        help="не записывать ячейку в реестр: сайт не будет "
                             "получать доставку содержимого")
    parser.add_argument("--output", help="куда положить результат")
    parser.add_argument("--artifact", help="путь к артефакту релиза")
    parser.add_argument("--manifest", help="путь к release-manifest.json")
    parser.add_argument("--expect-digest", help="ожидаемый digest артефакта")
    parser.add_argument("--commit", help="коммит репозитория сайта для activate")
    parser.add_argument("--ci-run", help="номер прогона CI для submit")
    parser.add_argument("--cell-operation", default="activate",
                        help="операция заявки: activate|update|deliver|rollback")
    parser.add_argument("--confirm-activation", action="store_true",
                        help="выполнить активацию на самом деле; без него activate только показывает план")
    parser.add_argument("--root", help="корень размещения сайта на этой машине")
    parser.add_argument("--target", help="корень целевого размещения для cutover")
    parser.add_argument("--route", action="append",
                        help="ожидаемый маршрут для verify (можно повторять)")
    parser.add_argument("--modules", nargs="*",
                        help="модули профиля; для extracted — проверяемые site_id")
    parser.add_argument("--reason", default="", help="причина операции для журнала")
    parser.add_argument("--force", action="store_true", help="перезаписать проект сайта")
    parser.add_argument("--dry-run", action="store_true",
                        help="показать план, ничего не меняя")
    parser.set_defaults(func=lambda args: ACTIONS[args.cell_action](args))
