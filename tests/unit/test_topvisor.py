"""Тесты клиента Topvisor.

Мок-API вместо сети: у Topvisor платные маршруты, и набор тестов, который
ходит наружу, рано или поздно потратит деньги владельца.
"""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from factory.errors import BlockedAccess, BlockedAuthorization, BlockedInput, BlockedSecret, TransientError
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
    """Владелец переименовал проект в интерфейсе — второй создавать нельзя."""
    existing = [{"id": i, "url": s.url, "name": "как-то иначе"} for i, s in enumerate(MANIFEST)]
    result = planning.build(existing)
    assert all(a.method == "edit/projects_2/projects" for a in result.actions)
    assert not any(a.method == "add/projects_2/projects" for a in result.actions)


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

def test_six_projects_are_genuinely_different():
    assert len({s.domain for s in MANIFEST}) == 6
    assert len({s.name for s in MANIFEST}) == 6
    assert len({s.profile for s in MANIFEST}) == 6
    assert len({s.metrika_counter for s in MANIFEST}) == 6
    every_group = [g.name for s in MANIFEST for g in s.groups]
    every_keyword = [k for s in MANIFEST for g in s.groups for k in g.keywords]
    assert len(set(every_keyword)) == len(every_keyword), "одинаковые запросы на разных сайтах — шесть копий одного измерения"
    assert len(every_group) == len(MANIFEST) * 3


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
    expected = {
        "yummyani.site": 111881037, "yummyani.org": 111881038, "yummyani.biz": 111881039,
        "lordfilm47.space": 112010269, "lordserial33.biz": 112010274, "1lordserials1.online": 112010277,
    }
    assert {s.domain: s.metrika_counter for s in MANIFEST} == expected


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
