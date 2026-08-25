"""Root-команды: ввод через форму и импорт существующих credentials.

Обе выполняются внутри root-процесса, запущенного systemd, и обе печатают
результат, но не значения. Отдельно от `factory secrets …` они существуют по
одной причине: `factory secrets …` запускается сессией агента, а эти команды
читают мастер-ключ и файлы секретов. Разделены процессы — разделены и права.

Запуск:

    sudo systemctl start site-factory-secret-hub-enroll@yami.service
    sudo systemctl start site-factory-secret-hub-import@lords.service

Одноразовый код формы попадает в журнал этого unit'а, то есть в root-консоль, и
никуда больше.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

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


def cmd_enroll(args) -> int:
    from factory.secret_hub import enroll

    hub = _hub()
    portfolio = hub.config.portfolio(args.portfolio)
    if portfolio.blocked_target is not None:
        print(f"[{portfolio.blocked_target.status}] {portfolio.blocked_target.reason}",
              file=sys.stderr)
        print(f"нужно: {portfolio.blocked_target.required_input}", file=sys.stderr)
        return 3

    result = enroll.start_session(hub, portfolio.id, ttl_seconds=args.ttl_seconds,
                                  host=args.host, port=args.port)
    # В выводе — исход, а не значения: ни кода доступа, ни credentials здесь нет.
    print(redact(json.dumps(
        {k: v for k, v in result.items() if k not in ("server", "session")},
        ensure_ascii=False, indent=2)))
    return 0 if result.get("outcome") == "stored" else 3


def cmd_import(args) -> int:
    from factory.secret_hub import migrate

    hub = _hub()
    result = migrate.import_existing(hub, args.portfolio, archive=args.archive)
    print(redact(json.dumps(result, ensure_ascii=False, indent=2)))
    return 0 if result.get("imported") else 3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="factory.secret_hub.rootcmd",
        description="Root-команды Secret Hub: ввод через форму и импорт")
    sub = parser.add_subparsers(dest="action", required=True)

    p = sub.add_parser("enroll", help="поднять одноразовую форму ввода")
    p.add_argument("portfolio")
    p.add_argument("--ttl-seconds", type=int)
    p.add_argument("--host")
    p.add_argument("--port", type=int)
    p.set_defaults(func=cmd_enroll)

    p = sub.add_parser("import", help="импортировать существующие файлы credentials")
    p.add_argument("portfolio")
    p.add_argument("--archive", action="store_true",
                   help="сделать архивную копию прежних файлов (0600). "
                        "Оригиналы не удаляются ни при каком флаге.")
    p.set_defaults(func=cmd_import)

    args = parser.parse_args(argv)

    if os.geteuid() != 0:
        print("Эта команда выполняется только от root: она читает мастер-ключ и файлы "
              "секретов.", file=sys.stderr)
        print("нужно: sudo systemctl start site-factory-secret-hub-"
              f"{args.action}@<направление>.service", file=sys.stderr)
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
