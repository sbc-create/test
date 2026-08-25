"""Root-команды: установка панели и импорт существующих credentials.

Обе выполняются внутри root-процесса, запущенного systemd, и обе печатают
результат, но не значения. Отдельно от `factory secrets …` они существуют по
одной причине: `factory secrets …` запускается сессией агента, а эти команды
читают мастер-ключ и файлы секретов. Разделены процессы — разделены и права.

Запуск:

    sudo /srv/site-factory/repo/bin/secret-hub-install                              # установка панели
    sudo systemctl start site-factory-secret-hub-import@lords.service # ручной импорт

Код первичной регистрации passkey печатается в root-консоль установки и никуда
больше. После установки root не нужен: credentials вводятся и применяются из
панели, под входом по passkey.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from factory.errors import FactoryError
from factory.redaction import redact


def _hub():
    from factory.secret_hub.crypto import load_master_key
    from factory.secret_hub.registry import load as load_config
    from factory.secret_hub.service import Hub
    from factory.secret_hub.store import Store

    config = load_config()
    master = load_master_key()
    return Hub(config, master, Store(config.db_path, master))


def cmd_import(args) -> int:
    from factory.secret_hub import migrate

    hub = _hub()
    result = migrate.import_existing(hub, args.portfolio, archive=args.archive)
    print(redact(json.dumps(result, ensure_ascii=False, indent=2)))
    return 0 if result.get("imported") else 3


def cmd_reconcile(args) -> int:
    """Применяет уже сохранённые credentials там, где они ещё не применены.

    Новых версий не создаёт и повторного ввода не требует: работает с активной
    версией направления.
    """
    from factory.secret_hub import reconcile

    hub = _hub()
    report = reconcile.run(hub, only=args.portfolio, restart=not args.no_restart,
                           force=args.force)
    print(reconcile.format_report(report))

    # Отчёт говорит, что было сделано; проверка — что получилось. Смотрим на
    # диск и на systemd, а не на собственный вывод.
    checked = reconcile.audit(hub)
    print(reconcile.format_audit(checked))

    if not report.ok or not checked["ok"]:
        print("Применение завершено не полностью. Значения credentials не "
              "показывались и повторный ввод не требуется: направления хранят "
              "уже проверенную версию.", file=sys.stderr)
        return 3
    return 0


def cmd_install_panel(args) -> int:
    """Публикует панель в nginx, проверяет вживую и выдаёт код регистрации.

    Порядок жёсткий: сперва конфигурация и перезагрузка nginx, затем живая
    проверка по публичному имени, и только если она прошла — код регистрации.
    Показать адрес и код, не убедившись, что панель отвечает и никого не
    сломала, значит отправить владельца вводить credentials неизвестно куда.
    """
    from factory.secret_hub import publish
    from factory.secret_hub.panel import ui as panel_ui
    from factory.secret_hub.panel.store import PanelStore
    from factory.secret_hub.registry import load as load_config

    config = load_config()
    form = config.public_form
    if form is None:
        print("[BLOCKED_INPUT] public_form не описан в config/secret-hub.json.",
              file=sys.stderr)
        return 3

    try:
        result = publish.install_panel(form.vhost, form.server_name,
                                       form.loopback_port, form.path)
    except publish.PublishError as exc:
        print(f"[DEPLOY_FAILED] {exc}", file=sys.stderr)
        return 3
    print(f"  nginx: {result.get('detail')}")

    # Дождаться, пока перезагруженный nginx действительно начнёт отдавать
    # панель. `systemctl reload` возвращается сразу, а прежние рабочие
    # процессы продолжают отвечать по старой конфигурации: на боевой установке
    # проверка попала именно на них и получила 401 с realm основного сайта.
    served, detail = publish.wait_until_serving(form.server_name, form.path,
                                                panel_ui.MARKER)
    print(f"  применение конфигурации: {detail}")
    if not served:
        try:
            publish.uninstall_panel()
        except publish.PublishError as exc:
            print(f"  снятие панели: {exc}", file=sys.stderr)
        print("\n[QA_FAILED] Панель не начала отвечать после перезагрузки nginx: "
              "адрес и код не печатаются.", file=sys.stderr)
        return 3

    live = publish.verify_live(form.server_name, panel_ui.MARKER, path=form.path)
    print()
    print("  ЖИВАЯ ПРОВЕРКА НА УСТАНОВЛЕННОМ NGINX")
    for check in live.checks:
        print(f"    [{'ok  ' if check.ok else 'ОТКАЗ'}] {check.name}: {check.detail}")
    if not live.ok:
        try:
            publish.uninstall_panel()
        except publish.PublishError as exc:
            print(f"  снятие панели: {exc}", file=sys.stderr)
        print("\n[QA_FAILED] Живая проверка не пройдена: адрес и код не печатаются.",
              file=sys.stderr)
        return 3

    # Код регистрации выпускается только если ключей ещё нет: у владельца с
    # рабочим passkey новый ключ добавляется из самой панели, и печатать код в
    # консоль означало бы создать второй, никому не нужный вход.
    store = PanelStore(Path(form.panel_state_dir) / "panel.sqlite3",
                       enforce_permissions=False)
    try:
        code = None if (store.has_passkey() and not args.force_enrollment) \
            else store.create_enrollment(ttl_seconds=args.enroll_ttl)
    finally:
        store.close()

    minutes = max(1, args.enroll_ttl // 60)
    print()
    print("=" * 72)
    print("  ПАНЕЛЬ SECRET HUB УСТАНОВЛЕНА")
    print("=" * 72)
    print(f"  Адрес:  {form.url}")
    if code:
        print(f"  Код регистрации:  {code}")
        print(f"  Срок кода:        {minutes} мин")
        print()
        print("  Откройте адрес в браузере, введите код и создайте ключ")
        print("  устройства (Touch ID / Face ID). Коды восстановления панель")
        print("  покажет один раз — сохраните их сразу.")
    else:
        print("  Ключ уже зарегистрирован: код не выпускался.")
        print("  Вход в панель — по ключу устройства.")
    print()
    print("  Root больше не нужен: credentials вводятся и применяются из панели.")
    print("=" * 72)
    print()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="factory.secret_hub.rootcmd",
        description="Root-команды Secret Hub: установка панели и импорт")
    sub = parser.add_subparsers(dest="action", required=True)

    p = sub.add_parser("import", help="импортировать существующие файлы credentials")
    p.add_argument("portfolio")
    p.add_argument("--archive", action="store_true",
                   help="сделать архивную копию прежних файлов (0600). "
                        "Оригиналы не удаляются ни при каком флаге.")
    p.set_defaults(func=cmd_import)

    p = sub.add_parser("reconcile",
                       help="применить уже сохранённые credentials к потребителям")
    p.add_argument("--portfolio", help="только это направление")
    p.add_argument("--no-restart", action="store_true",
                   help="записать файлы, но не перезапускать unit'ы")
    p.add_argument("--force", action="store_true",
                   help="пересмотреть и уже применённые направления")
    p.set_defaults(func=cmd_reconcile)

    p = sub.add_parser("install-panel",
                       help="опубликовать панель в nginx, проверить вживую, выдать код")
    p.add_argument("--enroll-ttl", type=int, default=3600,
                   help="срок кода первичной регистрации, секунд")
    p.add_argument("--force-enrollment", action="store_true",
                   help="выпустить код, даже если ключ уже зарегистрирован")
    p.set_defaults(func=cmd_install_panel)

    args = parser.parse_args(argv)

    if os.geteuid() != 0:
        # Подсказка адресная: установка панели идёт лончером, импорт — своим
        # unit'ом с именем направления. Универсальная строка отправляла бы
        # оператора запускать то, чего нет.
        hint = {
            "install-panel": "sudo /srv/site-factory/repo/bin/secret-hub-install",
            "reconcile": "sudo /srv/site-factory/repo/bin/secret-hub-install",
            "import": "sudo systemctl start site-factory-secret-hub-import@<направление>.service",
        }[args.action]
        print("Эта команда выполняется только от root: она читает мастер-ключ и файлы "
              "секретов.", file=sys.stderr)
        print(f"нужно: {hint}", file=sys.stderr)
        return 3

    try:
        return args.func(args)
    except FactoryError as exc:
        print(f"[{exc.status}] {exc.reason}", file=sys.stderr)
        if exc.required_input:
            print(f"нужно: {exc.required_input}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
