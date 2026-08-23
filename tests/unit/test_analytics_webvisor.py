"""REQ-ANALYTICS-WEBVISOR: запись сессий выключается явно, а не «по умолчанию».

Дефект найден боевым запуском 2026-08-23: объект `webvisor` в запросе создания
не передавался — и Метрика создала все три счётчика с ВКЛЮЧЁННОЙ записью
сессий. Значение по умолчанию у неё «включено», поэтому «не передавать поле» не
равно «выключено».

Вторая половина дефекта хуже первой: ветка создания не записывала это в
`problems`, и отчёт показывал `problems: []` у счётчика, нарушающего прямое
требование задания. Молчание отчёта нарушения не отменяет.
"""
from __future__ import annotations

import json
import urllib.request

import pytest

from factory.analytics.credentials import OAuthToken
from factory.analytics.transport import RateLimiter, YandexApiClient
from factory.analytics.yandex import (
    WEBVISOR_OFF,
    YandexAnalyticsProvider,
    webvisor_enabled,
)
from factory.errors import BlockedAnalyticsAccess
from factory.redaction import forget_secrets

TOKEN_VALUE = "y0_AgAAAABwebvisorTESTtoken012345678"


@pytest.fixture(autouse=True)
def _clean():
    yield
    forget_secrets()


@pytest.fixture
def token():
    return OAuthToken(TOKEN_VALUE, "тест")


class MetrikaWithWebvisorOn:
    """Метрика, которая включает Вебвизор сама, если её не попросили иначе.

    Ровно это и произошло на боевом запуске, поэтому подделка воспроизводит
    поведение, а не удобную для теста фикцию.
    """

    def __init__(self, honour_request: bool = True):
        self.counters: list[dict] = []
        self.requests: list[tuple[str, str, dict | None]] = []
        self._next_id = 111881037
        self.honour_request = honour_request

    def __call__(self, request: urllib.request.Request, timeout: float):
        method = request.get_method()
        path = request.full_url.split("?", 1)[0].split(".net", 1)[1]
        body = json.loads(request.data.decode("utf-8")) if request.data else None
        self.requests.append((method, path, body))

        if method == "GET" and path == "/management/v1/counters":
            return 200, json.dumps({"rows": len(self.counters), "counters": self.counters}).encode()
        if method == "POST" and path == "/management/v1/counters":
            counter = dict(body["counter"])
            counter["id"] = self._next_id
            self._next_id += 1
            counter.setdefault("status", "Active")
            counter.setdefault("goals", [])
            asked = counter.get("webvisor") or {}
            enabled = not (self.honour_request and asked.get("arch_enabled") is False)
            counter["webvisor"] = {"arch_enabled": enabled, "wv_forms": enabled,
                                   "arch_type": "none", "load_player_type": "proxy"}
            self.counters.append(counter)
            return 200, json.dumps({"counter": counter}).encode()
        if method == "GET" and path.startswith("/management/v1/counter/"):
            cid = int(path.split("/")[4])
            for counter in self.counters:
                if counter["id"] == cid:
                    return 200, json.dumps({"counter": counter}).encode()
            return 404, b'{"message":"not found"}'
        if method == "PUT" and path.startswith("/management/v1/counter/"):
            cid = int(path.split("/")[4])
            for counter in self.counters:
                if counter["id"] == cid:
                    if self.honour_request:
                        counter["webvisor"] = {**counter["webvisor"], **body["counter"]["webvisor"]}
                    return 200, json.dumps({"counter": counter}).encode()
            return 404, b'{"message":"not found"}'
        if method == "POST" and path.endswith("/goals"):
            return 200, json.dumps({"goal": {"id": 1, **body["goal"]}}).encode()
        return 404, b'{"message":"unmapped"}'


def _provider(fake, token, *, dry_run=False) -> YandexAnalyticsProvider:
    provider = YandexAnalyticsProvider(token=token, dry_run=dry_run)
    provider._metrika = YandexApiClient(
        "https://api-metrika.yandex.net", token, service="metrika", dry_run=dry_run,
        opener=fake, rate_limiter=RateLimiter(min_interval=0), sleep=lambda _s: None)
    return provider


def test_creation_asks_for_webvisor_off_explicitly(token):
    fake = MetrikaWithWebvisorOn()
    _provider(fake, token).ensure_metrica_counter("yummyani.site", "YummyAnime — yummyani.site")
    body = next(b for m, p, b in fake.requests if m == "POST" and p == "/management/v1/counters")
    assert body["counter"]["webvisor"] == WEBVISOR_OFF, (
        "объект webvisor обязан быть в запросе: без него Метрика включает запись сессий"
    )


def test_counter_is_created_with_webvisor_off(token):
    fake = MetrikaWithWebvisorOn()
    state = _provider(fake, token).ensure_metrica_counter("yummyani.site", "n")
    assert state.webvisor is False
    assert state.problems == ()


def test_a_server_that_ignores_the_request_is_reported_not_hidden(token):
    """Если Метрика всё равно включит запись — это попадёт в problems, а не в тишину."""
    fake = MetrikaWithWebvisorOn(honour_request=False)
    state = _provider(fake, token).ensure_metrica_counter("yummyani.site", "n")
    assert state.webvisor is True
    assert state.problems, "problems: [] у счётчика с включённым Вебвизором — это ложный отчёт"
    assert "Вебвизор" in state.problems[0]


def test_disable_is_idempotent_and_reads_before_writing(token):
    fake = MetrikaWithWebvisorOn(honour_request=False)
    provider = _provider(fake, token)
    state = provider.ensure_metrica_counter("yummyani.site", "n")

    fake.honour_request = True
    first = provider.ensure_webvisor_disabled(state.counter_id)
    assert first["changed"] is True and first["webvisor"] is False
    puts = sum(1 for m, _, _ in fake.requests if m == "PUT")
    assert puts == 1

    second = provider.ensure_webvisor_disabled(state.counter_id)
    assert second["changed"] is False
    assert sum(1 for m, _, _ in fake.requests if m == "PUT") == puts, (
        "повторный вызов не должен слать PUT: выключать уже нечего"
    )


def test_disable_sends_only_the_webvisor_object(token):
    """Частичное обновление: остальные настройки счётчика не переписываются."""
    fake = MetrikaWithWebvisorOn(honour_request=False)
    provider = _provider(fake, token)
    state = provider.ensure_metrica_counter("yummyani.site", "n")
    fake.honour_request = True
    provider.ensure_webvisor_disabled(state.counter_id)

    body = next(b for m, _, b in fake.requests if m == "PUT")
    assert set(body["counter"]) == {"webvisor"}
    assert body["counter"]["webvisor"] == WEBVISOR_OFF


def test_disable_verifies_the_result(token):
    """«Отправили PUT» — не то же самое, что «выключено». Проверяется факт."""
    fake = MetrikaWithWebvisorOn(honour_request=False)
    provider = _provider(fake, token)
    state = provider.ensure_metrica_counter("yummyani.site", "n")
    with pytest.raises(BlockedAnalyticsAccess, match="остался включённым"):
        provider.ensure_webvisor_disabled(state.counter_id)


def test_dry_run_never_writes(token):
    fake = MetrikaWithWebvisorOn(honour_request=False)
    provider = _provider(fake, token)
    provider.dry_run = False
    state = provider.ensure_metrica_counter("yummyani.site", "n")
    provider.dry_run = True
    provider.metrika.dry_run = True

    result = provider.ensure_webvisor_disabled(state.counter_id)
    assert result["changed"] is False and result.get("planned") is True
    assert not any(m == "PUT" for m, _, _ in fake.requests)


@pytest.mark.parametrize("webvisor,expected", [
    ({"arch_enabled": True, "wv_forms": False}, True),
    ({"arch_enabled": False, "wv_forms": True}, True),
    ({"arch_enabled": False, "wv_forms": False}, False),
    ({"arch_enabled": False, "wv_forms": False, "arch_type": "none"}, False),
])
def test_either_flag_counts_as_enabled(webvisor, expected):
    assert webvisor_enabled({"webvisor": webvisor}) is expected


def test_registry_records_the_real_state_including_problems():
    """Реестр в git обязан говорить правду о боевых счётчиках."""
    from factory.analytics import registry

    for entry in registry.properties():
        raw = entry.raw
        assert raw["counter_id"], f"{entry.domain}: боевой counter_id не записан"
        if raw["webvisor"]:
            assert any("Вебвизор" in p for p in raw["problems"]), (
                f"{entry.domain}: Вебвизор включён, но в problems об этом ни слова"
            )
