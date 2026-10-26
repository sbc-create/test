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


def _действующий_манифест():
    """Манифест без сайтов, исключённых из продвижения (решение владельца
    25.10.2026, factory.cell.withdrawn): им не создаются и не настраиваются
    проекты, не добавляется семантика. Чтение настроек (check) не фильтруется:
    это описание существующего, а не работа на сайт."""
    from factory.cell import withdrawn  # noqa: PLC0415
    from factory.topvisor.manifest import MANIFEST  # noqa: PLC0415

    выведено = withdrawn.выведенные()
    return tuple(s for s in MANIFEST if not withdrawn.выведен(s.domain, набор=выведено))


def cmd_plan(args: argparse.Namespace) -> int:
    client = _client(False)
    info = client.bank_info()
    balance = info.get("balance", info.get("sum"))
    current = client.projects()
    result = planning.build(current, balance=balance if isinstance(balance, int | float) else None,
                            manifest=_действующий_манифест())
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
    result = planning.build(current, manifest=_действующий_манифест())
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
    print(f"Групп создано: {заполнено['groups']}, "
          f"запросов добавлено: {заполнено['keywords']}, "
          f"поисковых систем добавлено: {заполнено['searchers']}, "
          f"регионов добавлено: {заполнено['regions']}, "
          f"возвращено из архива: {заполнено['unarchived']}")
    for строка in заполнено["notes"]:
        print(f"  ! {строка}")
    # Перечитываем: «добавлено» — это ответ на запись, а настроено то, что
    # сервис отдаёт при чтении.
    try:
        from factory.topvisor import manifest as м  # noqa: PLC0415
        from factory.topvisor.measure import регионы  # noqa: PLC0415

        for п in client.projects_with_regions():
            домен = planning.normalize_domain(str(п.get("url") or п.get("site") or ""))
            есть = {(р["searcher"], р["device"]) for р in регионы(п) if р["region_name"] == м.REGION_NAME}
            print(f"  после записи: #{п.get('id')} {домен} on={п.get('on')} регионы {sorted(есть)}")
    except FactoryError as exc:
        print(f"  ! перечитать регионы не удалось — {exc.reason}")
    return 0


def cmd_measure(args: argparse.Namespace) -> int:
    """Бесплатные измерения: настройки, история позиций, цена съёма."""
    from factory.topvisor import measure  # noqa: PLC0415

    client = _client(False)
    итог = measure.измерить(client)
    путь = measure.записать(итог)
    for с in итог["sites"]:
        полосы = {}
        for ч in с.get("checks") or []:
            for k, v in (ч.get("bands") or {}).items():
                полосы[k] = полосы.get(k, 0) + v
        print(f"  #{с.get('project_id')} {с['domain']:22s} {с['state']:13s} "
              f"запросов {с.get('keywords_total')} последний съём {с.get('last_check')} "
              f"цена съёма {с.get('price_one_check_rub')} ₽ полосы {полосы}"
              + (f" ошибка: {с['error']}" if с.get("error") else ""))
    print(f"итог: {путь}")
    return 0


def cmd_collect(args: argparse.Namespace) -> int:
    """Платный съём в пределах лимита владельца. Без лимита — BLOCKED_INPUT."""
    import datetime as dt  # noqa: PLC0415

    from factory.topvisor import collect, measure  # noqa: PLC0415

    лимит = collect.лимит()
    client = _client(not args.dry_run)
    итог = measure.измерить(client)
    measure.записать(итог)
    визиты = _поисковые_визиты()
    журнал = collect.расходы()
    сейчас = dt.datetime.now(dt.timezone.utc)
    запущено = 0
    for сайт, регионы in collect.очередь(итог, визиты):
        индексы = [р["index"] for р in регионы]
        try:
            цена = client.checker_price([сайт["project_id"]], индексы)
        except FactoryError as exc:
            print(f"  {сайт['domain']}: цена не получена — {exc.reason}")
            continue
        допуск, причина = collect.допуск_съёма(
            project_id=сайт["project_id"], regions=регионы, цена=цена,
            сейчас=сейчас, лимит_руб=лимит, журнал=журнал)
        print(f"  {сайт['domain']} {[р['searcher'] + '/' + str(р['device']) for р in регионы]}: {причина}")
        if допуск is None:
            continue
        try:
            client.call_paid(допуск.метод, допуск.payload(), допуск)
        except FactoryError as exc:
            print(f"    отказ сервиса: {exc.reason}")
            continue
        if not args.dry_run:
            collect.записать_расход(сайт["project_id"], сайт["domain"], допуск.regions_indexes,
                                    допуск.сумма, сейчас)
            журнал.append({"at": сейчас.strftime("%Y-%m-%dT%H:%M:%SZ"),
                           "project_id": сайт["project_id"],
                           "regions_indexes": list(допуск.regions_indexes), "price_rub": допуск.сумма})
            запущено += 1
    print(f"Запущено съёмов: {запущено}" + (" (dry-run: ничего не отправлено)" if args.dry_run else ""))
    return 0


def _поисковые_визиты() -> dict[str, float]:
    """Поисковые визиты Метрики за последние 7 дней — только для порядка
    очереди съёма. Нет выгрузки — пустой порядок, не ошибка."""
    import collections  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    путь = Path(__file__).resolve().parents[2] / "var" / "analytics" / "cabinet-latest.json"
    try:
        выгрузка = json.loads(путь.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    итог: dict[str, float] = collections.Counter()
    for з in выгрузка.get("domains") or []:
        строки = [с for м in з.get("measurements") or []
                  if м.get("key") == "daily_search_landing_pages" and м.get("measured")
                  for с in м.get("value") or []]
        даты = sorted({(с.get("dimensions") or [{}])[0].get("name") for с in строки} - {None})
        последние = set(даты[-7:])
        for с in строки:
            if (с.get("dimensions") or [{}])[0].get("name") in последние:
                итог[з["domain"]] += float((с.get("metrics") or [0])[0] or 0)
    return dict(итог)


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

    from factory.cell import withdrawn  # noqa: PLC0415

    итог = {"groups": 0, "keywords": 0, "searchers": 0, "regions": 0, "unarchived": 0, "notes": []}
    _КЛЮЧИ_РЕГИОНОВ.clear()
    _ПРОЕКТЫ_С_РЕГИОНАМИ.clear()
    for проект in projects:
        домен = normalize_domain(str(проект.get("url") or проект.get("site") or ""))
        spec = by_domain(домен) if домен else None
        if spec is None or withdrawn.выведен(домен):
            continue
        # Измеренные входы из config/topvisor-cores.json — к группам стратегии.
        from factory.topvisor.manifest import с_ядром  # noqa: PLC0415

        spec = с_ядром(spec)
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
        _поисковые_системы(client, ид, домен, spec, итог)
    return итог


def _поисковые_системы(client, ид, домен: str, spec, итог: dict) -> None:
    """Поисковые системы и регионы проекта: ЧИТАЕМ, добавляем недостающее,
    ПЕРЕЧИТЫВАЕМ.

    Чтение — `get/projects_2/projects` с `show_searchers_and_regions: 2`
    (документация Топвизора, 26.10.2026): у проекта список поисковых систем,
    у каждой — регионы с ключом, устройством и глубиной. Прежнее
    `get/projects_2/searchers` у API не существует, поэтому раньше здесь была
    названная блокировка (U7); теперь метод чтения подтверждён документом.

    Целевая конфигурация — `manifest.TARGET_REGIONS` в регионе
    `REGION_NAME`. Ключ региона берётся из ответа сервиса: из уже настроенного
    региона любого проекта аккаунта или из справочника. Регион с другим
    именем не трогается и не удаляется — удаление ломает историю.
    """
    from factory.topvisor import manifest as м  # noqa: PLC0415
    from factory.topvisor.measure import регионы  # noqa: PLC0415

    объявлено = tuple(getattr(spec, "searchers", ()) or ())
    if not объявлено:
        return
    try:
        проект = _проект_с_регионами(client, ид)
    except FactoryError as exc:
        итог["notes"].append(f"{домен}: регионы не прочитаны — {exc.reason}; ничего не добавляю")
        return
    if проект is None:
        итог["notes"].append(f"{домен}: проект #{ид} не найден при чтении регионов")
        return
    есть_пс = {_число((п or {}).get("key", (п or {}).get("searcher_key")))
               for п in проект.get("searchers") or [] if isinstance(п, dict)}
    есть = {(р["searcher_key"], р["device"], str(р["region_name"] or "")) for р in регионы(проект)}
    for ключ_пс, устройство in м.TARGET_REGIONS:
        if ключ_пс not in объявлено:
            continue
        if ключ_пс not in есть_пс:
            try:
                client.call("add/positions_2/searchers",
                            {"project_id": int(ид), "searcher_key": int(ключ_пс)})
                есть_пс.add(ключ_пс)
                итог["searchers"] += 1
            except FactoryError as exc:
                итог["notes"].append(f"{домен}: поисковая система {ключ_пс} не добавлена — {exc.reason}")
                continue
        имя_устр = {0: "desktop", 1: "tablet", 2: "smartphone"}[устройство]
        if (ключ_пс, имя_устр, м.REGION_NAME) in есть:
            continue
        ключ_рег = _ключ_региона(client, ключ_пс, итог)
        if ключ_рег is None:
            continue
        полезная = {"project_id": int(ид), "searcher_key": int(ключ_пс),
                    "region_key": int(ключ_рег), "region_lang": м.REGION_LANG,
                    "region_device": int(устройство), "region_depth": int(м.REGION_DEPTH)}
        try:
            _добавить_регион(client, полезная)
            итог["regions"] = итог.get("regions", 0) + 1
        except FactoryError as exc:
            итог["notes"].append(
                f"{домен}: регион {м.REGION_NAME}/{имя_устр} для ПС {ключ_пс} не добавлен — {exc.reason}")
    # Архивный проект не проверяется и не отдаёт историю. Активный сайт сети
    # в архиве — это потеря измерений, а не решение о паузе: пауза опыта
    # касается изменений сайта, не замеров.
    if _число(проект.get("on")) == -1:
        try:
            client.call("edit/projects_2/projects/on",
                        {"filters": [{"name": "id", "operator": "EQUALS", "values": [int(ид)]}],
                         "on": 0})
            итог["unarchived"] = итог.get("unarchived", 0) + 1
            итог["notes"].append(f"{домен}: проект #{ид} был архивным (on=-1) — возвращён в обычные")
        except FactoryError as exc:
            итог["notes"].append(f"{домен}: проект #{ид} архивный, вернуть не удалось — {exc.reason}")


def _число(значение):
    try:
        return int(str(значение).strip())
    except (TypeError, ValueError):
        return None


_КЛЮЧИ_РЕГИОНОВ: dict[int, int | None] = {}
_ПРОЕКТЫ_С_РЕГИОНАМИ: dict[int, dict] = {}


def _проект_с_регионами(client, ид) -> dict | None:
    if not _ПРОЕКТЫ_С_РЕГИОНАМИ:
        for п in client.projects_with_regions():
            if _число(п.get("id")) is not None:
                _ПРОЕКТЫ_С_РЕГИОНАМИ[_число(п.get("id"))] = п
    return _ПРОЕКТЫ_С_РЕГИОНАМИ.get(_число(ид))


def _ключ_региона(client, ключ_пс: int, итог: dict) -> int | None:
    """Ключ региона `REGION_NAME` для поисковой системы — из ответа сервиса.

    Сначала — из уже настроенных регионов проектов аккаунта (это ключ,
    который сервис сам записал), затем — справочник. Неоднозначность
    (несколько разных ключей с тем же именем) — замечание, а не выбор."""
    from factory.topvisor import manifest as м  # noqa: PLC0415
    from factory.topvisor.measure import регионы  # noqa: PLC0415

    if ключ_пс in _КЛЮЧИ_РЕГИОНОВ:
        return _КЛЮЧИ_РЕГИОНОВ[ключ_пс]
    ключи = {р["region_key"] for п in _ПРОЕКТЫ_С_РЕГИОНАМИ.values() for р in регионы(п)
             if р["searcher_key"] == ключ_пс and р["region_name"] == м.REGION_NAME
             and р["region_key"] is not None}
    if not ключи:
        try:
            найдено = client.find_regions(м.REGION_NAME, ключ_пс, м.REGION_COUNTRY)
        except FactoryError as exc:
            итог["notes"].append(f"справочник регионов ПС {ключ_пс} не прочитан — {exc.reason}")
            найдено = []
        ключи = {_число(р.get("key")) for р in найдено
                 if str(р.get("name") or "").strip() == м.REGION_NAME and _число(р.get("key")) is not None}
    if len(ключи) != 1:
        итог["notes"].append(
            f"ПС {ключ_пс}: ключ региона «{м.REGION_NAME}» не определён однозначно "
            f"({sorted(ключи) or 'не найден'}) — регион не добавляю")
        _КЛЮЧИ_РЕГИОНОВ[ключ_пс] = None
        return None
    _КЛЮЧИ_РЕГИОНОВ[ключ_пс] = ключи.pop()
    return _КЛЮЧИ_РЕГИОНОВ[ключ_пс]


def _добавить_регион(client, полезная: dict) -> None:
    """Имя метода — из документа; второе написание пробуется только при
    отказе «нет такого метода» на первое (см. client.ALLOWED)."""
    try:
        client.call("add/positions_2/searchers/regions", полезная)
    except FactoryError as exc:
        if "undefined method" not in str(exc.reason).lower():
            raise
        client.call("add/positions_2/searchers_regions", полезная)


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
    sub.add_parser("measure", help="бесплатные измерения: настройки, история, цена").set_defaults(func=cmd_measure)
    c = sub.add_parser("collect", help="платный съём в пределах лимита владельца")
    c.add_argument("--dry-run", action="store_true", help="решить и показать, ничего не отправляя")
    c.set_defaults(func=cmd_collect)
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
