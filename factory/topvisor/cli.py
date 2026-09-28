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
    for строка in описать_связь_с_метрикой(client, projects):
        print(строка)
    for строка in описать_настройки(client, projects):
        print(строка)
    return 0


def описать_настройки(client, projects: list[dict]) -> list[str]:
    """Фактические настройки проектов манифеста, прочитанные из сервиса.

    «Проект создан» и «проект настроен» — разные состояния. Создание отвечает
    только за домен и название; поисковые системы, регион и семантика задаются
    отдельно, и в плане таких действий до сих пор не было ни одного —
    проверено: `add/projects_2/searchers` и `add/keywords_2/*` в плане не
    встречались. Поэтому отчёт обязан показывать не манифест, а то, что в
    аккаунте действительно есть.

    Ошибку чтения печатаем целиком: у Topvisor она называет параметр, который
    он ожидал, и это единственный законный способ узнать контракт — в отличие
    от перебора имён методов.
    """
    from factory.topvisor.manifest import by_domain  # noqa: PLC0415
    from factory.topvisor.plan import normalize_domain  # noqa: PLC0415

    свои = []
    for проект in projects:
        домен = normalize_domain(str(проект.get("url") or проект.get("site") or ""))
        if домен and by_domain(домен):
            свои.append((домен, проект))
    if not свои:
        return ["  настройки проектов        : ни один проект аккаунта не описан манифестом"]

    строки = ["  фактические настройки проектов манифеста:"]
    for домен, проект in sorted(свои):
        spec = by_domain(домен)
        ид = проект.get("id")
        части = []
        # Единственное число задаётся явно: отрезать последнюю букву от «группы»
        # и «запросы» даёт «групп» и «запрос» — отчёт читают люди.
        for имя, один, читатель, ожидание in (
            ("группы", "группы", client.keyword_groups, len(spec.groups)),
            ("запросы", "запроса", client.keywords,
             sum(len(g.keywords) for g in spec.groups)),
        ):
            try:
                факт = читатель(ид)
            except FactoryError as exc:
                части.append(f"{имя}: НЕ ПРОЧИТАНО — {exc.reason}")
                continue
            части.append(f"{имя}: {len(факт)} из {ожидание} по манифесту")
            if факт:
                # Состав полей нужен затем, чтобы форму запроса на ДОБАВЛЕНИЕ
                # взять из ответа сервиса, а не придумать. Печатается по одному
                # образцу на вид объекта — этого достаточно и не раздувает отчёт.
                части.append(f"поля {один}: " + ", ".join(sorted(факт[0])))
        строки.append(f"    #{ид} {домен}: " + "; ".join(части))
    return строки


#: Поля-кандидаты, которыми у Topvisor могла бы задаваться привязка счётчика.
#: Список — не утверждение, что такое поле есть. Он нужен, чтобы на вопрос
#: «поддерживает ли используемый API привязку» ответил сам API, а не догадка.
КАНДИДАТЫ_СВЯЗИ = ("metrika_counter_id", "metrika_counter", "counter_id")


def проба_связи(client, поля: tuple[str, ...] = КАНДИДАТЫ_СВЯЗИ) -> dict[str, str]:
    """Спросить API про каждое поле-кандидат по отдельности.

    Почему нельзя обойтись разбором обычного списка проектов: он запрашивается с
    явным `fields` из пяти колонок, и постороннего поля в ответе не будет никогда
    — ни при поддержке, ни без неё. Вывод «поля нет» на таком ответе был бы
    следствием собственного запроса, а не свойством API. Ровно этот способ
    ошибаться уже стоил дня: метод без `fields` отдаёт один `id`, и план не
    узнавал существующие проекты.

    Три различимых исхода на каждое поле:

    * ``принято``   — поле пришло в ответе, привязка задаётся им;
    * ``отвергнуто``— API ответил ошибкой, и в значении стоит её код;
    * ``пропущено`` — ошибки нет, но поля в ответе тоже нет: метод его
      игнорирует, и привязкой это не является.
    """
    исходы: dict[str, str] = {}
    for имя in поля:
        try:
            ответ = client.call("get/projects_2/projects",
                                {"limit": 1, "fields": ["id", имя]})
        except FactoryError as exc:
            исходы[имя] = f"отвергнуто: {exc.reason}"
            continue
        записи = [p for p in (ответ or []) if isinstance(p, dict)]
        if not записи:
            исходы[имя] = "не измерено: API вернул пустой список проектов"
        elif any(имя in p for p in записи):
            исходы[имя] = "принято"
        else:
            исходы[имя] = "пропущено: поля нет в ответе"
    return исходы


def описать_связь_с_метрикой(client, projects: list[dict]) -> list[str]:
    """Что API говорит о привязке счётчика — и чего он не говорит.

    Локальная запись идентификатора в манифест выглядит как подключение и им не
    является. Единственный источник ответа — сам API, поэтому вопрос задаётся
    ему, а результат печатается тем словом, которым он получен.
    """
    if not projects:
        return ["  связь с Метрикой           : не измерена — в аккаунте нет ни одного проекта"]
    исходы = проба_связи(client)
    принятые = sorted(и for и, з in исходы.items() if з == "принято")
    строки = ["  связь с Метрикой           : "
              + ("поддерживается полем " + ", ".join(принятые) if принятые
                 else "этим методом API не подтверждена")]
    for имя in sorted(исходы):
        строки.append(f"    {имя:20s} {исходы[имя]}")
    if принятые:
        строки.append("    поле принято на чтении; метод записи нужно подтвердить документом — edit/projects_2/projects API отвергает")
    else:
        строки.append("    счётчик остаётся объявленным только в манифесте — "
                      "это НЕ подключение и так и записывается в отчёт")
    return строки


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
        # РАННЕГО ВОЗВРАТА ЗДЕСЬ БЫТЬ НЕ ДОЛЖНО. План отвечает только на вопрос
        # «какие проекты создать»; когда все девять уже созданы, он пуст — и
        # команда печатала «желаемое состояние уже достигнуто», не дойдя до
        # второй фазы. Семантика при этом оставалась нулевой у всех девяти
        # новых проектов, а отчёт выглядел успешным. Пустой проект — не
        # мониторинг, а запись о намерении.
        print("Проекты: изменений нет, все объявленные манифестом существуют.")
    elif result.paid_actions:
        # Платные действия не выполняются даже с --apply: они перечисляются,
        # и решение остаётся за владельцем.
        print("В плане есть платные действия — они не выполняются автоматически:")
        for action in result.paid_actions:
            print(f"  [{action.cost}] {action.method} {action.domain}: {action.summary}")
    if result.free_actions:
        done = 0
        for action in result.free_actions:
            try:
                client.call(action.method, action.payload)
                done += 1
                print(f"  выполнено: {action.method} {action.domain} — {action.summary}")
            except FactoryError as exc:
                print(f"  отказ: {action.method} {action.domain}: {exc.reason}",
                      file=sys.stderr)
        print(f"Выполнено бесплатных действий: {done} из {len(result.free_actions)}")
        # Список проектов перечитывается: только что созданные должны попасть
        # во вторую фазу тем же запуском, а не следующим.
        current = client.projects()
    # Проекты созданы — но проект без семантики не мониторинг, а пустая запись.
    # Поэтому вторая фаза: группы запросов и сами запросы.
    заполнено = наполнить_семантику(client, current)
    print(f"Групп создано: {заполнено['groups']}, запросов добавлено: {заполнено['keywords']}")
    for строка in заполнено["notes"]:
        print(f"  ! {строка}")
    return 0


def наполнить_семантику(client, projects: list[dict]) -> dict:
    """Группы запросов и запросы по манифесту — второй фазой, после проектов.

    Почему отдельной фазой, а не действием плана. Запрос привязывается к ГРУППЕ
    по её идентификатору, а идентификатор появляется только после создания
    группы. Статический план такого порядка выразить не может: он пришлось бы
    строить на угаданных заранее id.

    Почему это вообще понадобилось. В плане не было ни одного действия на
    семантику, и шесть новых проектов существовали с нулём групп и нулём
    запросов — при этом манифест выглядел выполненным, потому что «проект есть».
    Прогон 2026-09-27 22:46 показал это числами: у старых проектов 5–14 групп и
    39–82 запроса, у новых по нулю.

    Идемпотентность по ИМЕНИ: существующая группа не создаётся заново, уже
    добавленный запрос не добавляется повторно. Имя — единственный признак,
    который есть и в манифесте, и в ответе сервиса (`get` отдаёт `id` и `name`).

    Форма запроса на добавление взята из состава полей, который отдаёт чтение, а
    не подобрана перебором. Если сервис ожидает другие имена параметров, он
    ответит ошибкой с их указанием — и она попадёт в отчёт целиком, как это уже
    произошло с `fields[n].name` и `Call to undefined method`.
    """
    from factory.topvisor.manifest import by_domain  # noqa: PLC0415
    from factory.topvisor.plan import normalize_domain  # noqa: PLC0415

    итог = {"groups": 0, "keywords": 0, "notes": []}
    for проект in projects:
        домен = normalize_domain(str(проект.get("url") or проект.get("site") or ""))
        spec = by_domain(домен) if домен else None
        if spec is None:
            continue
        ид = проект.get("id")
        try:
            было = {str(g.get("name") or ""): g.get("id") for g in client.keyword_groups(ид)}
        except FactoryError as exc:
            итог["notes"].append(f"{домен}: группы не прочитаны — {exc.reason}")
            continue
        for группа in spec.groups:
            if группа.name in было:
                continue
            try:
                client.call("add/keywords_2/groups",
                            {"project_id": int(ид), "name": группа.name})
                итог["groups"] += 1
            except FactoryError as exc:
                итог["notes"].append(
                    f"{домен}: группа «{группа.name}» не создана — {exc.reason}")
        # Перечитываем: идентификаторы групп нужны для запросов и берутся из
        # сервиса, а не из ответа на создание — ответы у методов разной формы.
        try:
            стало = {str(g.get("name") or ""): g.get("id") for g in client.keyword_groups(ид)}
            запросы = {str(k.get("name") or "") for k in client.keywords(ид)}
        except FactoryError as exc:
            итог["notes"].append(f"{домен}: перечитать не удалось — {exc.reason}")
            continue
        for группа in spec.groups:
            group_id = стало.get(группа.name)
            if group_id is None:
                итог["notes"].append(
                    f"{домен}: группы «{группа.name}» нет после создания — запросы не добавляю")
                continue
            новые = [к for к in группа.keywords if к not in запросы]
            if not новые:
                continue
            try:
                client.call("add/keywords_2/keywords",
                            {"project_id": int(ид), "group_id": int(group_id),
                             "keywords": list(новые)})
                итог["keywords"] += len(новые)
            except FactoryError as exc:
                итог["notes"].append(
                    f"{домен}/«{группа.name}»: запросы не добавлены — {exc.reason}")
    return итог


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
