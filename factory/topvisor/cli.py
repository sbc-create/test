"""Командный интерфейс Topvisor.

По умолчанию ничего не меняет. Изменения включаются флагом ``--apply``, и даже
он не разрешает платные операции — для них нужен отдельный расчёт и отдельное
решение владельца.
"""
from __future__ import annotations

import argparse
import json
import sys

from factory.errors import FactoryError
from factory.topvisor import plan as planning
from factory.topvisor.client import ALLOWED, TopvisorClient
from factory.topvisor.credentials import load


def _client(apply_changes: bool) -> TopvisorClient:
    return TopvisorClient(credentials=load(), dry_run=not apply_changes)


def cmd_check(args: argparse.Namespace) -> int:
    """Бесплатная проверка доступа: профиль, баланс, список проектов."""
    client = _client(False)
    info = client.bank_info()
    projects = client.projects()
    # Печатаем только безопасные сведения. Ключа здесь нет и быть не может.
    print("Доступ к Topvisor: подтверждён")
    print(f"  идентификатор пользователя : {client.credentials.user_id}")
    balance = info.get("balance", info.get("sum"))
    if balance is not None:
        print(f"  баланс                     : {balance}")
    for label, key in (("тариф", "name"), ("стоимость тарифа", "price"),
                       ("действует до", "state_time_end")):
        if info.get(key) not in (None, ""):
            print(f"  {label:26s} : {info[key]}")
    print(f"  проектов в аккаунте        : {len(projects)}")
    for project in projects:
        print(f"    #{project.get('id')} {project.get('url')} — {project.get('name')}")
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    client = _client(False)
    info = client.bank_info()
    balance = info.get("balance", info.get("sum"))
    current = client.projects()
    result = planning.build(current, balance=balance if isinstance(balance, int | float) else None)
    document = result.as_dict()
    if args.json:
        print(json.dumps(document, ensure_ascii=False, indent=2))
        return 0
    print(f"Действий в плане: {len(result.actions)} (бесплатных {len(result.free_actions)}, платных {len(result.paid_actions)})")
    for action in result.actions:
        print(f"  [{action.cost}] {action.method}  {action.domain}: {action.summary}")
    for note in result.notes:
        print(f"  ! {note}")
    if result.empty:
        print("Изменений не требуется — желаемое состояние уже достигнуто.")
    print(f"Потолок автоматических трат: {planning.MAX_AUTOMATED_SPEND_RUB} ₽")
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    client = _client(True)
    current = client.projects()
    result = planning.build(current)
    if result.empty:
        print("0 изменений: желаемое состояние уже достигнуто.")
        return 0
    if result.paid_actions:
        # Платные действия не выполняются даже с --apply: они перечисляются,
        # и решение остаётся за владельцем.
        print("В плане есть платные действия — они не выполняются автоматически:")
        for action in result.paid_actions:
            print(f"  [{action.cost}] {action.method} {action.domain}: {action.summary}")
    done = 0
    for action in result.free_actions:
        try:
            client.call(action.method, action.payload)
            done += 1
            print(f"  выполнено: {action.method} {action.domain} — {action.summary}")
        except FactoryError as exc:
            print(f"  отказ: {action.method} {action.domain}: {exc.reason}", file=sys.stderr)
    print(f"Выполнено бесплатных действий: {done} из {len(result.free_actions)}")
    return 0


def cmd_methods(args: argparse.Namespace) -> int:
    for name, method in sorted(ALLOWED.items()):
        kind = "мутация" if method.mutation else "чтение "
        print(f"  [{method.cost:7s}] {kind} {name:34s} {method.description}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="factory topvisor", description="Работа с Topvisor")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="бесплатная проверка доступа").set_defaults(func=cmd_check)
    p = sub.add_parser("plan", help="показать план, ничего не меняя")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_plan)
    a = sub.add_parser("apply", help="выполнить бесплатные действия плана")
    a.set_defaults(func=cmd_apply)
    sub.add_parser("methods", help="разрешённые методы и их стоимость").set_defaults(func=cmd_methods)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except FactoryError as exc:
        print(f"BLOCKED: {exc.reason}", file=sys.stderr)
        if exc.required_input:
            print(f"нужно: {exc.required_input}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
