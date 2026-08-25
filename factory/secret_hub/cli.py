"""`python3 -m factory secrets …` — управление хабом без доступа к значениям.

Все команды разговаривают с сервисом по unix-сокету и печатают то, что он
вернул. Ни одна из них не открывает хранилище, не читает мастер-ключ и не
касается файлов секретов: у сессии, из которой они запускаются, на это нет прав,
и это не ограничение реализации, а её цель.

`status` печатает ровно то, что перечислено в задании: направление, настроено ли,
проверено ли, дата обновления, отпечаток, потребители, состояние выката. Версия
показывается рядом — по ней различают «то же значение перевыдали» и «значение
сменили».
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from factory.errors import BlockedAccess, BlockedInput
from factory.secret_hub import service
from factory.secret_hub.registry import load as load_config

EXIT_OK = 0
EXIT_BLOCKED = 3

ACTIONS = ("status", "verify", "apply", "rotate", "revoke", "list", "discover", "enroll", "import")

#: Команды, требующие --portfolio. `status`, `list` и `discover` работают по всем.
NEEDS_PORTFOLIO = frozenset({"verify", "apply", "rotate", "revoke", "enroll", "import"})


def _call(socket_path: Path, payload: dict) -> dict:
    try:
        return service.request(socket_path, payload)
    except FileNotFoundError:
        raise BlockedAccess(
            f"Сервис Secret Hub не запущен: сокета {socket_path} нет.",
            field=str(socket_path),
            required_input="sudo systemctl start site-factory-secret-hub.service",
            blocks_stage="VALIDATING",
        ) from None
    except PermissionError:
        raise BlockedAccess(
            f"Нет прав на обращение к {socket_path}. Доступ выдаётся членством в группе "
            "управления; значения секретов членство всё равно не открывает.",
            field=str(socket_path),
            required_input="Членство в группе управления хабом",
            blocks_stage="VALIDATING",
        ) from None
    except (ConnectionError, OSError) as exc:
        raise BlockedAccess(
            f"Сервис Secret Hub не ответил ({exc.__class__.__name__}).",
            field=str(socket_path),
            required_input="Работающий site-factory-secret-hub.service",
            blocks_stage="VALIDATING",
        ) from None


def _print_status(response: dict) -> None:
    key = response.get("master_key") or {}
    store = response.get("store") or {}
    print("Мастер-ключ: " + ("на месте, закрыт правильно" if key.get("stored_correctly")
                             else "; ".join(key.get("problems") or ["состояние не измерено"])))
    problems = store.get("permission_problems") or []
    print(f"Хранилище:   {store.get('path')} — "
          + ("права в порядке" if not problems else "; ".join(problems)))
    print()

    header = f"{'НАПРАВЛЕНИЕ':<10} {'НАСТРОЕНО':<10} {'ПРОВЕРЕНО':<10} {'ОБНОВЛЕНО':<21} {'ОТПЕЧАТОК':<24} ВЫКАТ"
    print(header)
    print("-" * len(header))
    for row in response.get("portfolios", []):
        blocked = row.get("blocked_target")
        configured = "BLOCKED_TARGET" if blocked else ("да" if row.get("configured") else "нет")
        verified = "—" if blocked else ("да" if row.get("verified") else "нет")
        deployment = _deployment_summary(row)
        print(f"{row['portfolio']:<10} {configured:<10} {verified:<10} "
              f"{str(row.get('updated_at') or '—'):<21} "
              f"{str(row.get('fingerprint') or '—'):<24} {deployment}")
        for consumer in row.get("consumers", []):
            mark = "ok" if consumer.get("target_ok") else "цель недоступна"
            files = ", ".join(
                f"{f['field']}={'есть' if f.get('present') else 'нет'}"
                + (f" ({f['mode']})" if f.get("mode") else "")
                for f in consumer.get("files", [])
            )
            print(f"    └ {consumer['consumer']:<22} {mark:<16} {files}")
            for problem in consumer.get("problems", []):
                print(f"        ! {problem}")
        if blocked:
            print(f"    └ {blocked['status']}: {blocked['reason']}")
            print(f"      нужно: {blocked['required_input']}")
    print()
    print("Значения секретов не показываются и не могут быть получены через этот интерфейс:")
    print("операции, возвращающей значение, у сервиса нет.")


def _deployment_summary(row: dict) -> str:
    entries = row.get("deployment") or []
    if not entries:
        return "не применялось"
    applied = sum(1 for e in entries if e.get("status") == "applied")
    return f"{applied}/{len(entries)} применено"


def _print_apply(response: dict) -> None:
    if response.get("status") == "verification_failed":
        print(f"[{response['portfolio']}] не применено: {response.get('reason')}")
        print("Работающие сайты не тронуты: применение непроверенных credentials не начиналось.")
        return
    if response.get("status") == "not_configured":
        print(f"[{response['portfolio']}] {response.get('reason')}")
        return
    verdict = "применено" if response.get("ok") else "ОТКАЗ"
    print(f"[{response['portfolio']}] {verdict}, версия {response.get('version')}")
    for consumer in response.get("consumers", []):
        line = f"  {consumer['consumer']:<24} {consumer['status']}"
        if consumer.get("restarted"):
            line += f"  (перезапущено: {', '.join(consumer['restarted'])})"
        print(line)
        if consumer.get("detail"):
            print(f"      {consumer['detail']}")
    if response.get("rolled_back"):
        print("  Направление возвращено к предыдущему состоянию целиком.")
    if response.get("store_backup"):
        print(f"  Бэкап хранилища: {response['store_backup']}")


def _print_verify(response: dict) -> None:
    outcome = response.get("outcome")
    labels = {
        "accepted": "провайдер принял credentials",
        "rejected": "провайдер отверг credentials",
        "unmeasured": "проверка не выполнена",
        "not_configured": "направление не настроено",
    }
    print(f"[{response['portfolio']}] {labels.get(outcome, outcome)}")
    if response.get("reason"):
        print(f"  {response['reason']}")
    if response.get("http_status") is not None:
        print(f"  HTTP {response['http_status']}  {response.get('url', '')}")
    if response.get("verified_at"):
        print(f"  verified_at: {response['verified_at']}")


def _print_discover(response: dict) -> None:
    print("Обнаруженные файлы credentials (содержимое не читалось):")
    for item in response.get("discovered", []):
        # Три состояния, а не два: «?» означает «каталог закрыт, не измерено».
        # Печатать «есть» там, где посмотреть не дали, значило бы сообщить как
        # факт то, чего никто не проверял.
        state = {True: "есть", False: "нет", None: "?"}[item.get("exists")]
        size = f"{item['size_bytes']} байт" if item.get("size_bytes") is not None else "—"
        print(f"  {item['portfolio']:<8} {item['field']:<14} {state:<5} {size:<10} "
              f"{item.get('mode') or '—':<6} {item['path']}")
        for problem in item.get("problems", []):
            print(f"      ! {problem}")
    print()
    print(response.get("note", ""))


PRINTERS = {
    "status": _print_status,
    "apply": _print_apply,
    "rotate": lambda r: (print(f"[{r['portfolio']}] новая версия {r.get('version')}"),
                         _print_apply(r["apply"]) if r.get("apply") else None),
    "verify": _print_verify,
    "discover": _print_discover,
}


def run(args) -> int:
    action = args.secrets_action
    config = load_config()

    if action == "discover":
        # Единственная команда, выполняемая в процессе сессии: она только
        # смотрит на файлы через stat и не открывает их.
        from factory.secret_hub import migrate

        response = migrate.report(config, getattr(args, "portfolio", None))
        response["ok"] = True
    else:
        if action in NEEDS_PORTFOLIO and not args.portfolio:
            raise BlockedInput(
                f"Команде «{action}» нужно направление: она меняет состояние конкретного "
                "направления, и выполнять её «по всем сразу» — не значение по умолчанию.",
                field="--portfolio",
                required_input=f"--portfolio <{ '|'.join(config.ids()) }>",
                blocks_stage="VALIDATING",
            )
        payload: dict = {"op": action}
        if args.portfolio:
            payload["portfolio"] = args.portfolio
        if action in ("apply", "rotate"):
            payload["restart"] = not args.no_restart
        if action == "rotate":
            payload["apply"] = not args.no_apply
        if action == "import":
            payload["archive"] = args.archive
        if action == "enroll" and args.ttl_seconds:
            payload["ttl_seconds"] = args.ttl_seconds
        response = _call(config.socket_path, payload)

    if getattr(args, "json", False):
        print(json.dumps(response, ensure_ascii=False, indent=2))
        return EXIT_OK if response.get("ok") else EXIT_BLOCKED

    if not response.get("ok"):
        print(f"[{response.get('error', 'ОТКАЗ')}] {response.get('reason', '')}", file=sys.stderr)
        if response.get("required_input"):
            print(f"нужно: {response['required_input']}", file=sys.stderr)
        return EXIT_BLOCKED

    printer = PRINTERS.get(action)
    if printer:
        printer(response)
    else:
        print(json.dumps(response, ensure_ascii=False, indent=2))
    return EXIT_OK


def register(subparsers) -> None:
    parser = subparsers.add_parser(
        "secrets", help="центральный Secret Hub: состояние, проверка, применение")
    parser.add_argument("secrets_action", choices=ACTIONS)
    parser.add_argument("--portfolio", help="направление: yami, lords, amedia, …")
    parser.add_argument("--no-restart", action="store_true",
                        help="apply/rotate: записать файлы, но не перезапускать unit'ы")
    parser.add_argument("--no-apply", action="store_true",
                        help="rotate: создать версию, но не применять её")
    parser.add_argument("--archive", action="store_true",
                        help="import: сделать архивную копию прежних файлов (0600). "
                             "Оригиналы не удаляются ни при каком флаге.")
    parser.add_argument("--ttl-seconds", type=int,
                        help=f"enroll: срок жизни формы, не больше "
                             f"{15 * 60} с")
    parser.set_defaults(func=run)
