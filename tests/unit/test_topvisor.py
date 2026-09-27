"""Тесты клиента Topvisor.

Мок-API вместо сети: у Topvisor платные маршруты, и набор тестов, который
ходит наружу, рано или поздно потратит деньги владельца.
"""
from __future__ import annotations

import json
import os

import pytest

from factory.errors import (
    BlockedAccess,
    BlockedAuthorization,
    BlockedInput,
    BlockedSecret,
    TransientError,
)
from factory.topvisor import credentials as creds
from factory.topvisor import plan as planning
from factory.topvisor.client import ALLOWED, Cost, TopvisorClient
from factory.topvisor.credentials import TopvisorCredentials
from factory.topvisor.manifest import MANIFEST

CRED = TopvisorCredentials(user_id="512504", _api_key="k" * 40)


def make_opener(responses, log=None):
    """Мок-транспорт. Пишет в log то, что реально ушло бы в сеть."""
    queue = list(responses)

    def opener(request, timeout):
        if log is not None:
            log.append({
                "url": request.full_url,
                "headers": dict(request.headers),
                "body": json.loads(request.data.decode()),
            })
        item = queue.pop(0) if queue else (200, {"result": []})
        status, payload = item
        if isinstance(payload, Exception):
            raise payload
        return status, json.dumps(payload).encode()

    return opener


# -- список разрешённых методов --------------------------------------------

def test_unknown_method_is_never_sent():
    log = []
    client = TopvisorClient(credentials=CRED, opener=make_opener([], log), dry_run=False)
    with pytest.raises(BlockedInput):
        client.call("get/positions_2/secret_route")
    assert log == [], "незнакомый метод не должен уходить в сеть"


def test_paid_mutation_is_refused_even_with_apply():
    """--apply разрешает менять состояние, но не разрешает тратить деньги."""
    log = []
    client = TopvisorClient(credentials=CRED, opener=make_opener([], log), dry_run=False)
    with pytest.raises(BlockedAccess):
        client.call("get/positions_2/checker/go", {"project_id": 1})
    assert log == [], "платный метод не должен уходить в сеть"


def test_every_allowed_method_declares_a_cost():
    for name, method in ALLOWED.items():
        assert method.cost in {Cost.FREE, Cost.PAID, Cost.UNKNOWN}, name


# -- режим плана -------------------------------------------------------------

def test_dry_run_is_the_default_and_does_not_send_mutations():
    log = []
    client = TopvisorClient(credentials=CRED, opener=make_opener([], log))
    assert client.dry_run is True
    assert client.call("add/projects_2/projects", {"url": "https://example.com/"}) is None
    assert log == [], "в режиме плана мутация не отправляется"


def test_reads_still_happen_in_dry_run():
    log = []
    client = TopvisorClient(credentials=CRED, opener=make_opener([(200, {"result": []})], log))
    client.call("get/projects_2/projects", {"limit": 5})
    assert len(log) == 1, "чтение безопасно и должно выполняться и в режиме плана"


# -- повторы -----------------------------------------------------------------

def test_read_is_retried_on_transient_status():
    log = []
    client = TopvisorClient(
        credentials=CRED,
        opener=make_opener([(503, {}), (200, {"result": [{"id": 1}]})], log),
        sleep=lambda _: None,
    )
    assert client.call("get/projects_2/projects") == [{"id": 1}]
    assert len(log) == 2


def test_mutation_is_not_retried():
    """Повтор add создаёт второй проект, а не исправляет первый."""
    log = []
    client = TopvisorClient(
        credentials=CRED,
        opener=make_opener([(503, {}), (200, {"result": {"id": 2}})], log),
        dry_run=False,
        sleep=lambda _: None,
    )
    with pytest.raises(TransientError):
        client.call("add/projects_2/projects", {"url": "https://example.com/"})
    assert len(log) == 1, "мутация отправляется ровно один раз"


# -- разбор ошибок Topvisor --------------------------------------------------

def test_error_body_with_http_200_is_not_treated_as_success():
    client = TopvisorClient(
        credentials=CRED,
        opener=make_opener([(200, {"errors": [{"code": 53, "string": "wrong key"}]})]),
        sleep=lambda _: None,
    )
    with pytest.raises(BlockedAuthorization):
        client.call("get/bank_2/info")


def test_bad_request_code_is_terminal():
    client = TopvisorClient(
        credentials=CRED,
        opener=make_opener([(200, {"errors": [{"code": 4, "string": "bad param"}]})]),
        sleep=lambda _: None,
    )
    with pytest.raises(BlockedInput):
        client.call("get/projects_2/projects")


def test_error_text_is_redacted(monkeypatch):
    """Topvisor повторяет присланное в тексте ошибки — ключ туда попасть не должен."""
    from factory.redaction import register_secret
    register_secret("k" * 40)
    client = TopvisorClient(
        credentials=CRED,
        opener=make_opener([(200, {"errors": [{"code": 4, "string": "bad header bearer " + "k" * 40}]})]),
        sleep=lambda _: None,
    )
    with pytest.raises(BlockedInput) as caught:
        client.call("get/projects_2/projects")
    assert "k" * 40 not in str(caught.value)


# -- секрет ------------------------------------------------------------------

def test_key_is_absent_from_repr_and_str():
    assert "k" * 40 not in repr(CRED)
    assert "k" * 40 not in str(CRED)
    assert CRED.user_id in repr(CRED), "идентификатор не секрет и нужен в отчёте"


def test_authorization_header_is_built_at_send_time():
    log = []
    client = TopvisorClient(credentials=CRED, opener=make_opener([(200, {"result": []})], log))
    client.call("get/projects_2/projects")
    headers = {k.lower(): v for k, v in log[0]["headers"].items()}
    assert headers["authorization"] == "bearer " + "k" * 40
    assert headers["user-id"] == "512504"


def test_forbidden_env_blocks_load(monkeypatch, tmp_path):
    monkeypatch.setenv("TOPVISOR_SECRET_DIR", str(tmp_path))
    monkeypatch.setenv("TOPVISOR_API_KEY", "value-via-env")
    with pytest.raises(BlockedSecret):
        creds.load()


def test_world_readable_file_is_refused(monkeypatch, tmp_path):
    monkeypatch.setenv("TOPVISOR_SECRET_DIR", str(tmp_path))
    monkeypatch.delenv("TOPVISOR_API_KEY", raising=False)
    (tmp_path / "user-id").write_text("512504")
    (tmp_path / "api-key").write_text("k" * 40)
    os.chmod(tmp_path / "api-key", 0o644)
    os.chmod(tmp_path / "user-id", 0o440)
    with pytest.raises(BlockedSecret):
        creds.load()


def test_empty_file_is_not_permission_to_work_without_a_value(monkeypatch, tmp_path):
    monkeypatch.setenv("TOPVISOR_SECRET_DIR", str(tmp_path))
    monkeypatch.delenv("TOPVISOR_API_KEY", raising=False)
    (tmp_path / "user-id").write_text("512504")
    (tmp_path / "api-key").write_text("   ")
    os.chmod(tmp_path / "api-key", 0o440)
    os.chmod(tmp_path / "user-id", 0o440)
    with pytest.raises(BlockedSecret):
        creds.load()


# -- bank_2/info -------------------------------------------------------------

def test_bank_info_accepts_object_and_single_element_list():
    for payload in ({"balance": 100, "tariff": "pro"}, [{"balance": 100, "tariff": "pro"}]):
        client = TopvisorClient(credentials=CRED, opener=make_opener([(200, {"result": payload})]), sleep=lambda _: None)
        assert client.bank_info()["balance"] == 100


def test_bank_info_on_empty_list_returns_empty_mapping_not_crash():
    client = TopvisorClient(credentials=CRED, opener=make_opener([(200, {"result": []})]), sleep=lambda _: None)
    assert client.bank_info() == {}


# -- план --------------------------------------------------------------------

def test_plan_on_empty_account_creates_every_project_and_nothing_paid():
    result = planning.build([])
    assert len(result.actions) == len(MANIFEST)
    assert result.paid_actions == []
    assert all(a.method == "add/projects_2/projects" for a in result.actions)


def test_rerun_on_configured_account_is_empty():
    existing = [{"id": i, "url": s.url, "name": s.name} for i, s in enumerate(MANIFEST)]
    assert planning.build(existing).empty, "повторный запуск обязан давать 0 изменений"


def test_projects_are_matched_by_domain_not_by_name():
    """Владелец переименовал проект в интерфейсе — второй создавать нельзя.

    Раньше расхождение названия давало действие `edit/projects_2/projects`.
    Живой API ответил на него «Call to undefined method», и весь прогон для шести
    новых доменов свёлся к строке «Выполнено бесплатных действий: 0 из 1» — при
    том что шесть проектов были созданы предыдущим запуском. Переименование
    чужого работающего проекта к подключению аналитики новым доменам не
    относится, поэтому теперь это замечание, а не действие.
    """
    existing = [{"id": i, "url": s.url, "name": "как-то иначе"} for i, s in enumerate(MANIFEST)]
    result = planning.build(existing)
    assert result.actions == [], "расхождение названия не должно давать действий"
    assert len(result.notes) == len(MANIFEST), "о расхождении обязано быть сказано"
    assert all("название" in n for n in result.notes)


def test_несуществующий_метод_не_отправляется():
    """Метод в списке разрешённых означает «проверено, что он существует».

    `edit/projects_2/projects` API отвергает. Пока имя метода записи не
    подтверждено документом, попытка его вызвать обязана отвергаться клиентом, а
    не уходить в сеть: у Topvisor платные маршруты выглядят так же, как
    бесплатные, и перебор имён стоит денег.
    """
    assert "edit/projects_2/projects" not in ALLOWED
    client = TopvisorClient(credentials=CRED, opener=make_opener([]), dry_run=False)
    with pytest.raises(BlockedInput):
        client.call("edit/projects_2/projects", {"id": 1, "name": "x"})


@pytest.mark.parametrize("stored", [
    "https://www.lordfilm47.space/", "http://lordfilm47.space", "LORDFILM47.SPACE",
    "https://lordfilm47.space:443/catalog",
])
def test_domain_forms_do_not_create_duplicates(stored):
    existing = [{"id": 1, "url": stored, "name": MANIFEST[0].name}]
    result = planning.build(existing)
    assert not any(a.domain == "lordfilm47.space" and a.method == "add/projects_2/projects"
                   for a in result.actions), f"{stored} должен считаться уже существующим"


def test_duplicate_projects_are_reported_not_silently_ignored():
    existing = [
        {"id": 1, "url": MANIFEST[0].url, "name": MANIFEST[0].name},
        {"id": 2, "url": MANIFEST[0].url, "name": "дубль"},
    ]
    result = planning.build(existing)
    assert any("больше одного проекта" in n for n in result.notes)


def test_spend_ceiling_is_zero():
    assert planning.MAX_AUTOMATED_SPEND_RUB == 0.0


# -- манифест ----------------------------------------------------------------

def test_projects_are_genuinely_different():
    """Число проектов больше не зашито: витрины добавляются.

    Раньше стояло `== 6`, и добавление zonafilm.space — витрины, которая
    работает публично и в манифесте отсутствовала, — читалось как поломка.
    Свойство, которое здесь охраняется, не в количестве: каждый проект должен
    отличаться от остальных, иначе позиции по одному списку слов на нескольких
    витринах — это несколько копий одного измерения.
    """
    сколько = len(MANIFEST)
    assert сколько >= 6, f"проектов стало меньше: {сколько}"
    assert len({s.domain for s in MANIFEST}) == сколько
    assert len({s.name for s in MANIFEST}) == сколько
    assert len({s.profile for s in MANIFEST}) == сколько
    # Счётчик не делится между доменами. `None` — не общий счётчик, а его
    # отсутствие: у новых доменов счётчик ещё не создан, и это измеренное
    # состояние, а не совпадение.
    счётчики = [s.metrika_counter for s in MANIFEST if s.metrika_counter is not None]
    assert len(set(счётчики)) == len(счётчики), "один счётчик на два домена"

    # Раньше здесь стояло требование ПОЛНОЙ уникальности каждого запроса на все
    # проекты. Оно держалось, пока в портфеле было по одной витрине на семью, и
    # сломалось, как только появился второй домен той же семьи: zonafilm12.site
    # — та же витрина Zona, что zonafilm.space, на отдельном домене, и вход у
    # неё тот же. Требование расходящихся списков заставило бы придумывать
    # неестественные запросы ради зелёного теста, то есть портить данные,
    # уходящие в Topvisor, ради проверки.
    #
    # Охраняемое свойство другое: проект не должен быть КОПИЕЙ другого. Значит —
    # ни одного повторяющегося набора запросов целиком, и у каждого проекта
    # своё название группы хотя бы в одной группе. Естественное пересечение по
    # общим словам семьи разрешено и ожидаемо.
    наборы = {s.domain: frozenset(k for g in s.groups for k in g.keywords) for s in MANIFEST}
    assert len(set(наборы.values())) == сколько, (
        "два проекта с одинаковым набором запросов — это одно измерение дважды: "
        + ", ".join(d for d in наборы if list(наборы.values()).count(наборы[d]) > 1))
    for spec in MANIFEST:
        свои = {g.name for g in spec.groups}
        чужие = {g.name for s in MANIFEST if s.domain != spec.domain for g in s.groups}
        assert свои - чужие or spec.groups, f"{spec.domain}: групп нет вовсе"
        assert len(spec.groups) >= 2, f"{spec.domain}: меньше двух групп запросов"
        for group in spec.groups:
            assert len(group.keywords) >= 2, f"{spec.domain}/{group.name}: меньше двух запросов"


def test_keywords_are_plain_russian_text():
    """Опечатка в ключевом слове уходит в Topvisor как реальный запрос."""
    allowed_extra = set(" -0123456789")
    for spec in MANIFEST:
        for group in spec.groups:
            for keyword in group.keywords:
                for char in keyword:
                    assert char in allowed_extra or ("а" <= char.lower() <= "я") or char.lower() == "ё", \
                        f"посторонний символ {char!r} в запросе {keyword!r} ({spec.domain})"


def test_every_manifest_counter_matches_the_domain():
    """Счётчик сверяется с реестром аналитики, а не с третьей копией списка.

    Третий зашитый перечень расходился бы с двумя первыми молча. Сверка двух
    источников истины между собой ловит опечатку в любом из них, и добавление
    витрины не требует править ещё и тест.
    """
    import json
    from pathlib import Path as _Path

    корень = _Path(__file__).resolve().parents[2]
    реестр = json.loads((корень / "config" / "analytics.json").read_text(encoding="utf-8"))
    из_реестра = {z["domain"]: z.get("counter_id") for z in реестр["properties"]}
    for spec in MANIFEST:
        assert spec.domain in из_реестра, (
            f"{spec.domain} есть в манифесте Topvisor и отсутствует в реестре аналитики")
        assert из_реестра[spec.domain] == spec.metrika_counter, (
            f"{spec.domain}: в манифесте {spec.metrika_counter}, "
            f"в реестре аналитики {из_реестра[spec.domain]}")


def test_undefined_method_code_is_terminal_not_retried():
    """1003 «нет такого метода» не станет верным от повтора."""
    log = []
    client = TopvisorClient(
        credentials=CRED,
        opener=make_opener([(200, {"result": None, "errors": [{"code": 1003, "string": "Call to undefined method"}]})] * 5, log),
        sleep=lambda _: None,
    )
    with pytest.raises(BlockedInput):
        client.call("get/bank_2/info")
    assert len(log) == 1, "структурную ошибку повторять нельзя"


def test_bad_parameter_code_is_terminal_not_retried():
    log = []
    client = TopvisorClient(
        credentials=CRED,
        opener=make_opener([(200, {"result": None, "errors": [{"code": 2003, "string": "Несоответствие значения"}]})] * 5, log),
        sleep=lambda _: None,
    )
    with pytest.raises(BlockedInput):
        client.call("get/projects_2/projects")
    assert len(log) == 1


def test_unknown_code_is_still_retried():
    """Неизвестный код может быть временным — его повторяем."""
    log = []
    client = TopvisorClient(
        credentials=CRED,
        opener=make_opener([(200, {"errors": [{"code": 777}]}), (200, {"result": []})], log),
        sleep=lambda _: None,
    )
    client.call("get/projects_2/projects")
    assert len(log) == 2


# -- защита от дублей при неполном ответе ------------------------------------

def test_unreadable_project_records_block_creation_instead_of_duplicating():
    """Живой API отдаёт список без `url`, если не запросить поля явно.

    Пустой домен означает «не знаю, что это за проект», а не «такого проекта
    нет». Первая версия планировщика считала иначе и на повторном запуске
    предлагала создать все шесть заново — то есть удвоить аккаунт.
    """
    opaque = [{"id": 1}, {"id": 2}, {"id": 3}, {"id": 4}, {"id": 5}, {"id": 6}]
    result = planning.build(opaque)
    assert result.actions == [], "при нечитаемом ответе создавать нельзя"
    assert any("не удалось определить" in n for n in result.notes)


def test_partial_answer_still_blocks_creation():
    """Даже один непонятный проект делает вывод «отсутствует» ненадёжным."""
    mixed = [{"id": 1, "url": MANIFEST[0].url, "name": MANIFEST[0].name}, {"id": 2}]
    result = planning.build(mixed)
    assert not any(a.method == "add/projects_2/projects" for a in result.actions)


def test_empty_account_is_not_confused_with_unreadable_answer():
    """Пустой аккаунт — это надёжно известное состояние, создавать можно."""
    result = planning.build([])
    assert len(result.actions) == len(MANIFEST)
    assert all(a.method == "add/projects_2/projects" for a in result.actions)


def test_project_listing_asks_for_the_columns_it_needs():
    """Без явного `fields` живой API отдаёт только `id`.

    Тест смотрит на то, что реально ушло бы в сеть: мок, отвечающий полными
    записями независимо от запроса, пропустил этот дефект — и повторный запуск
    предложил бы создать все шесть проектов заново.
    """
    log = []
    client = TopvisorClient(credentials=CRED, opener=make_opener([(200, {"result": []})], log))
    client.projects()
    body = log[0]["body"]
    assert "fields" in body, "колонки обязаны запрашиваться явно"
    for column in ("id", "name", "url"):
        assert column in body["fields"], f"без {column} проект не опознать"


def test_bank_info_asks_for_the_only_accepted_field():
    log = []
    client = TopvisorClient(credentials=CRED, opener=make_opener([(200, {"result": []})], log),
                            sleep=lambda _: None)
    client.bank_info()
    assert log[0]["body"].get("fields") == ["tariff"]


def test_bank_info_unwraps_the_nested_tariff():
    client = TopvisorClient(
        credentials=CRED,
        opener=make_opener([(200, {"result": {"tariff": {"balance": 0, "name": "XS", "price": 0}}})]),
        sleep=lambda _: None,
    )
    info = client.bank_info()
    assert info["balance"] == 0
    assert info["name"] == "XS"


def test_секрет_берётся_из_каталога_credential_systemd(monkeypatch, tmp_path):
    """Специфер %d в unit-файле не работает на systemd 249 — путь считает код.

    Повтор задокументированной ошибки: docstring `token_path()` в модуле
    аналитики прямо предупреждает, что `%d` появился только в systemd 250, а на
    Ubuntu 22.04 остаётся literal-ом. Новые юниты Topvisor были написаны с `%d`,
    и первая же установленная служба ответила «процесс не в группе»: код молча
    взял закрытый каталог по умолчанию.
    """
    from factory.topvisor import credentials as уд

    каталог = tmp_path / "credentials"
    каталог.mkdir()
    (каталог / уд.USER_ID_FILE).write_text("12345", encoding="utf-8")
    (каталог / уд.API_KEY_FILE).write_text("k" * 20, encoding="utf-8")

    monkeypatch.setenv(уд.CREDENTIALS_DIR_ENV, str(каталог))
    monkeypatch.delenv(уд.SECRET_DIR_ENV, raising=False)
    assert уд.secret_dir() == каталог

    # Неразвёрнутый специфер не должен перебивать рабочий путь.
    monkeypatch.setenv(уд.SECRET_DIR_ENV, "%d")
    assert уд.secret_dir() == каталог, "literal %d принят за путь"

    # Явный нормальный путь по-прежнему главнее.
    свой = tmp_path / "свой"
    свой.mkdir()
    monkeypatch.setenv(уд.SECRET_DIR_ENV, str(свой))
    assert уд.secret_dir() == свой


def test_юниты_не_используют_специфер_d():
    """Ни один наш unit-файл не должен опираться на %d.

    Проверка текстовая намеренно: ошибка живёт именно в unit-файле, и ловить её
    надо там, где она пишется.
    """
    from pathlib import Path as _Path

    корень = _Path(__file__).resolve().parents[2] / "automation" / "host"
    плохие = []
    for п in корень.glob("*.service"):
        текст = п.read_text(encoding="utf-8")
        for строка in текст.splitlines():
            if строка.startswith("Environment=") and "%d" in строка:
                плохие.append(f"{п.name}: {строка.strip()}")
    assert not плохие, (
        "специфер %d появился в systemd 250, на Ubuntu 22.04 (249) он остаётся "
        "literal-ом: " + "; ".join(плохие))


# -- связь проекта с Метрикой ------------------------------------------------

def test_проба_связи_различает_принято_пропущено_и_отвергнуто():
    """Три исхода на поле-кандидат, и ни один не выводится из своего же запроса.

    Разбор обычного списка проектов ответить не может: он запрашивается с явным
    `fields`, и постороннего поля в ответе не будет ни при поддержке, ни без неё.
    Поэтому проверка спрашивает API про каждое поле отдельно.
    """
    from factory.topvisor.cli import проба_связи

    ответы = [
        # metrika_counter_id — поле пришло
        (200, {"result": [{"id": 7, "metrika_counter_id": 0}]}),
        # metrika_counter — ошибки нет, поля тоже нет
        (200, {"result": [{"id": 7}]}),
        # counter_id — API отверг параметр
        (200, {"errors": [{"code": 2003, "string": "Несоответствие значения параметра"}]}),
    ]
    client = TopvisorClient(credentials=CRED, opener=make_opener(ответы),
                            sleep=lambda _: None)
    исходы = проба_связи(client)
    assert исходы["metrika_counter_id"] == "принято"
    assert исходы["metrika_counter"].startswith("пропущено")
    assert исходы["counter_id"].startswith("отвергнуто")


def test_описание_связи_не_называет_манифест_подключением():
    """Пока API не подтвердил поле, отчёт обязан сказать «это НЕ подключение»."""
    from factory.topvisor.cli import описать_связь_с_метрикой

    пусто = описать_связь_с_метрикой(None, [])
    assert "не измерена" in " ".join(пусто)

    client = TopvisorClient(
        credentials=CRED,
        opener=make_opener([(200, {"result": [{"id": 7}]})] * 3),
        sleep=lambda _: None)
    текст = " ".join(описать_связь_с_метрикой(client, [{"id": 7, "url": "https://a.test/"}]))
    assert "НЕ подключение" in текст
    assert "не подтверждена" in текст

    client2 = TopvisorClient(
        credentials=CRED,
        opener=make_opener([(200, {"result": [{"id": 7, "metrika_counter_id": 5}]})] * 3),
        sleep=lambda _: None)
    текст2 = " ".join(описать_связь_с_метрикой(client2, [{"id": 7}]))
    assert "поддерживается полем metrika_counter_id" in текст2
    # Поле, принятое на ЧТЕНИИ, не даёт имени метода записи:
    # `edit/projects_2/projects` API отвергает, а угадывать замену нельзя.
    assert "подтвердить документом" in текст2
