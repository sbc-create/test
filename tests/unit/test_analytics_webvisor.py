"""REQ-ANALYTICS-VISOR: записью сессий управляет code_options.visor.

История дефекта в двух шагах, и второй дороже первого.

Шаг первый: объект `webvisor` в запросе создания не передавался — Метрика
включила запись сессий сама, и отчёт показал `problems: []`.

Шаг второй: попытка выключить её через `webvisor.arch_enabled` получила
HTTP 400 «Could not read JSON, error in line 1, column 43, path:
counter.webvisor.arch_enabled». Поле устаревшее, Метрика его больше не слушает.
Настоящий переключатель — булево `code_options.visor` (официальное описание:
«Record and analysis of site user behavior»).

Файл проверяет поведение на поддельной Метрике, которая ведёт себя как
настоящая: отвергает устаревшее поле и хранит `code_options`.
"""
from __future__ import annotations

import json
import urllib.request

import pytest

from factory.analytics.credentials import OAuthToken
from factory.analytics.transport import RateLimiter, YandexApiClient
from factory.analytics.yandex import (
    VISOR_OPTION,
    YandexAnalyticsProvider,
    visor_state,
    webvisor_enabled,
)
from factory.errors import BlockedAnalyticsAccess
from factory.redaction import forget_secrets

TOKEN_VALUE = "y0_AgAAAABvisorTESTtoken01234567890"

#: Настройки кода счётчика, которые обязаны пережить выключение записи сессий.
EXISTING_OPTIONS = {
    "async": True,
    "visor": True,
    "track_hash": True,
    "clickmap": True,
    "ecommerce": False,
    "alternative_cdn": True,
    "informer": {"enabled": True, "type": "ext", "size": 3},
}


@pytest.fixture(autouse=True)
def _clean():
    yield
    forget_secrets()


@pytest.fixture
def token():
    return OAuthToken(TOKEN_VALUE, "тест")


class Metrika:
    """Поддельная Метрика с боевым поведением.

    Отвергает `webvisor.arch_enabled` ровно тем же ответом, что и настоящая:
    иначе тест доказывал бы работоспособность схемы, которой в API нет.
    """

    def __init__(self, code_options: dict | None = None, honour_put: bool = True):
        self.counter = {
            "id": 111881037,
            "name": "YummyAnime — yummyani.site",
            "status": "Active",
            "site2": {"site": "yummyani.site"},
            "goals": [],
            # Объект webvisor приходит в ответе, но управляющим не является.
            "webvisor": {"arch_enabled": True, "arch_type": "none", "wv_forms": True},
            "code_options": dict(EXISTING_OPTIONS if code_options is None else code_options),
        }
        self.honour_put = honour_put
        self.requests: list[tuple[str, str, dict | None, bytes]] = []

    def __call__(self, request: urllib.request.Request, timeout: float):
        method = request.get_method()
        path = request.full_url.split("?", 1)[0].split(".net", 1)[1]
        raw = request.data or b""
        body = json.loads(raw.decode("utf-8")) if raw else None
        self.requests.append((method, path, body, raw))

        if body and "counter" in body and "webvisor" in body["counter"]:
            # Дословный ответ настоящей Метрики на устаревшее поле.
            return 400, json.dumps({
                "errors": [{"error_type": "invalid_json",
                            "message": "Could not read JSON, error in line 1, column 43, "
                                       "path: counter.webvisor.arch_enabled"}],
                "message": "Could not read JSON, error in line 1, column 43, "
                           "path: counter.webvisor.arch_enabled",
                "code": 400,
            }).encode()

        if method == "GET" and path == "/management/v1/counters":
            return 200, json.dumps({"rows": 1, "counters": [self.counter]}).encode()
        if method == "GET" and path.startswith("/management/v1/counter/"):
            return 200, json.dumps({"counter": self.counter}).encode()
        if method == "PUT" and path.startswith("/management/v1/counter/"):
            if self.honour_put:
                self.counter["code_options"] = {
                    **self.counter["code_options"],
                    **(body["counter"].get("code_options") or {}),
                }
            return 200, json.dumps({"counter": self.counter}).encode()
        if method == "POST" and path == "/management/v1/counters":
            created = dict(body["counter"])
            created["id"] = 111881040
            created.setdefault("status", "Active")
            created.setdefault("goals", [])
            self.counter = created
            return 200, json.dumps({"counter": created}).encode()
        if method == "POST" and path.endswith("/goals"):
            goal = dict(body["goal"])
            goal["id"] = 900 + len(self.counter["goals"])
            self.counter.setdefault("goals", []).append(goal)
            return 200, json.dumps({"goal": goal}).encode()
        return 404, b'{"message":"unmapped"}'

    def puts(self) -> list[dict]:
        return [b for m, _, b, _ in self.requests if m == "PUT"]


def _provider(fake, token, *, dry_run=False) -> YandexAnalyticsProvider:
    provider = YandexAnalyticsProvider(token=token, dry_run=dry_run)
    provider._metrika = YandexApiClient(
        "https://api-metrika.yandex.net", token, service="metrika", dry_run=dry_run,
        opener=fake, rate_limiter=RateLimiter(min_interval=0), sleep=lambda _s: None)
    return provider


# ------------------------------------------------ устаревшее поле не уходит
def test_arch_enabled_is_never_sent(token):
    """Главный regression: именно это поле вернуло HTTP 400 на боевом запуске."""
    fake = Metrika()
    _provider(fake, token).ensure_webvisor_disabled(111881037)
    for _method, _path, body, raw in fake.requests:
        assert b"arch_enabled" not in raw, f"устаревшее поле ушло в запрос: {raw[:200]!r}"
        if body and "counter" in body:
            assert "webvisor" not in body["counter"]


def test_creation_never_sends_the_webvisor_object(token):
    """При создании не уходит ни устаревший `webvisor`, ни `code_options`.

    `code_options` перестал уходить 2026-08-27: Метрика принимает его только на
    изменении счётчика, а на создании отвечает
    `HTTP 400 … path: counter.code_options.visor`. Выяснилось это на трёх
    доменах Lords — первом настоящем создании счётчика в истории проекта.
    Выключение записи сессий никуда не делось, оно выполняется следующим
    запросом и проверено остальными тестами этого файла.
    """
    fake = Metrika(code_options={})
    _provider(fake, token).ensure_metrica_counter("yummyani.new", "новый")
    post = next(b for m, p, b, _ in fake.requests
                if m == "POST" and p == "/management/v1/counters")
    assert "webvisor" not in post["counter"]
    assert "code_options" not in post["counter"]


def test_the_fake_really_rejects_the_deprecated_field(token):
    """Подделка обязана быть строгой, иначе тесты выше ничего не стерегут."""
    fake = Metrika()
    client = YandexApiClient(
        "https://api-metrika.yandex.net", token, service="metrika", dry_run=False,
        opener=fake, rate_limiter=RateLimiter(min_interval=0), sleep=lambda _s: None)
    with pytest.raises(BlockedAnalyticsAccess, match="400"):
        client.request("PUT", "/management/v1/counter/111881037",
                       body={"counter": {"webvisor": {"arch_enabled": False}}})


# ------------------------------------------------------- сериализация JSON
def test_visor_is_sent_as_a_real_json_boolean(token):
    """`false`, а не `"false"`, не `0` и не `False`: проверяются сырые байты."""
    fake = Metrika()
    _provider(fake, token).ensure_webvisor_disabled(111881037)
    raw = next(raw for m, _, _, raw in fake.requests if m == "PUT")
    text = raw.decode("utf-8")

    assert '"visor": false' in text or '"visor":false' in text, text
    assert '"visor": "false"' not in text
    assert '"visor": 0' not in text
    assert "False" not in text, "в теле оказался Python-литерал вместо JSON"

    body = json.loads(text)
    value = body["counter"]["code_options"]["visor"]
    assert value is False and isinstance(value, bool)


def test_request_declares_json_content_type(token):
    captured = {}

    def opener(request, timeout):
        captured["type"] = request.get_header("Content-type")
        captured["body"] = request.data
        return 200, json.dumps({"counter": {"id": 1, "code_options": {"visor": False}}}).encode()

    client = YandexApiClient(
        "https://api-metrika.yandex.net", token, service="metrika", dry_run=False,
        opener=opener, rate_limiter=RateLimiter(min_interval=0), sleep=lambda _s: None)
    client.request("PUT", "/management/v1/counter/1",
                   body={"counter": {"code_options": {"visor": False}}})
    assert captured["type"] == "application/json"
    json.loads(captured["body"].decode("utf-8"))


# --------------------------------------------- остальные настройки целы
def test_other_code_options_survive(token):
    fake = Metrika()
    _provider(fake, token).ensure_webvisor_disabled(111881037)
    sent = fake.puts()[0]["counter"]["code_options"]

    assert sent[VISOR_OPTION] is False
    for key, value in EXISTING_OPTIONS.items():
        if key == VISOR_OPTION:
            continue
        assert sent[key] == value, f"настройка {key} потерялась при выключении записи сессий"
    assert fake.counter["code_options"]["clickmap"] is True
    assert fake.counter["code_options"]["informer"] == EXISTING_OPTIONS["informer"]


def test_only_code_options_is_sent(token):
    """Ни имя, ни домен, ни цели PUT не переписывает."""
    fake = Metrika()
    _provider(fake, token).ensure_webvisor_disabled(111881037)
    assert set(fake.puts()[0]["counter"]) == {"code_options"}


# ------------------------------------------------------------ подтверждение
def test_unconfirmed_disable_raises_blocked_analytics_access(token):
    fake = Metrika(honour_put=False)
    with pytest.raises(BlockedAnalyticsAccess) as excinfo:
        _provider(fake, token).ensure_webvisor_disabled(111881037)
    assert excinfo.value.status == "BLOCKED_ANALYTICS_ACCESS"
    assert "не подтверждена" in excinfo.value.reason


def test_missing_code_options_is_not_treated_as_disabled(token):
    """Непроверенное не объявляется выполненным."""
    fake = Metrika(code_options={})
    fake.counter.pop("code_options")
    fake.honour_put = False
    with pytest.raises(BlockedAnalyticsAccess):
        _provider(fake, token).ensure_webvisor_disabled(111881037)


def test_successful_disable_is_confirmed_by_a_second_get(token):
    fake = Metrika()
    result = _provider(fake, token).ensure_webvisor_disabled(111881037)
    assert result == {"counter_id": 111881037, "visor": False, "changed": True,
                      "reason": "запись сессий выключена"}
    gets = [p for m, p, _, _ in fake.requests if m == "GET"]
    assert len(gets) == 2, "результат обязан перечитываться после PUT"


# ---------------------------------------------------------- идемпотентность
def test_second_run_sends_no_put(token):
    fake = Metrika()
    provider = _provider(fake, token)
    first = provider.ensure_webvisor_disabled(111881037)
    assert first["changed"] is True

    second = provider.ensure_webvisor_disabled(111881037)
    assert second["changed"] is False
    assert len(fake.puts()) == 1, "выключать уже нечего — PUT слать не нужно"


def test_second_run_creates_neither_counter_nor_goals(token):
    """Повторный прогон чинит настройку и не плодит объекты."""
    from factory.analytics import events as events_mod

    fake = Metrika(code_options={"visor": True})
    fake.counter["goals"] = [
        {"id": 900 + index, "name": event.goal_name, "type": "action",
         "conditions": [{"type": "exact", "url": event.id}]}
        for index, event in enumerate(events_mod.EVENTS)
    ]
    provider = _provider(fake, token)

    state = provider.ensure_metrica_counter("yummyani.site", "YummyAnime — yummyani.site")
    assert state.reused and state.counter_id == 111881037
    state = provider.ensure_metrica_goals(state.counter_id, state)
    provider.ensure_webvisor_disabled(state.counter_id)

    assert state.goals_created == ()
    assert len(state.goals_present) == 9
    posts = [p for m, p, _, _ in fake.requests if m == "POST"]
    assert posts == [], f"повторный прогон создал объекты: {posts}"
    assert len(fake.counter["goals"]) == 9


def test_goal_ids_are_collected_for_all_nine_events(token):
    from factory.analytics import events as events_mod

    fake = Metrika()
    fake.counter["goals"] = [
        {"id": 900 + index, "name": event.goal_name, "type": "action",
         "conditions": [{"type": "exact", "url": event.id}]}
        for index, event in enumerate(events_mod.EVENTS)
    ]
    mapping = _provider(fake, token).list_goal_ids(111881037)
    assert set(mapping) == set(events_mod.EVENT_IDS)
    assert len(mapping) == 9
    assert all(isinstance(v, int) for v in mapping.values())


# ------------------------------------------------------------- режим плана
def test_dry_run_sends_no_put(token):
    fake = Metrika()
    result = _provider(fake, token, dry_run=True).ensure_webvisor_disabled(111881037)
    assert result["changed"] is False and result["planned"] is True
    assert fake.puts() == []


# ------------------------------------------------------------- детектор
@pytest.mark.parametrize("counter,expected", [
    ({"code_options": {"visor": True}}, True),
    ({"code_options": {"visor": False}}, False),
    ({"code_options": {"visor": 1}}, True),
    ({"code_options": {"visor": 0}}, False),
    ({"code_options": {"async": True}}, None),
    ({"webvisor": {"arch_enabled": True}}, None),
    ({}, None),
])
def test_visor_state_reads_only_code_options(counter, expected):
    """Устаревший объект webvisor на решение не влияет ни в какую сторону."""
    assert visor_state(counter) is expected


def test_unmeasured_state_counts_as_enabled():
    """Не измерено — значит попробуем выключить и проверим, а не «наверное, выключено»."""
    assert webvisor_enabled({}) is True
    assert webvisor_enabled({"code_options": {"visor": False}}) is False


def test_registry_records_the_real_state_including_problems():
    from factory.analytics import registry

    for entry in registry.properties():
        raw = entry.raw
        assert raw["counter_id"], f"{entry.domain}: боевой counter_id не записан"
        if raw["webvisor"]:
            assert any("сесси" in p or "Вебвизор" in p for p in raw["problems"]), (
                f"{entry.domain}: запись сессий включена, но в problems об этом ни слова"
            )
