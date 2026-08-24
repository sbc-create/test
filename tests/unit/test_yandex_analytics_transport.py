"""REQ-ANALYTICS-HTTP: коды ответа разбираются по-разному и по делу.

429 и временные 5xx повторяются с задержкой; 401, 403, 404 и 422 не
повторяются никогда — они не изменятся сами, а повтор POST рискует создать
дубль. Всё, что не удалось, становится BLOCKED_ANALYTICS_ACCESS, а не пустым
результатом, который отчёт нарисует как «0 визитов».
"""
from __future__ import annotations

import json

import pytest

from factory.analytics.credentials import OAuthToken
from factory.analytics.transport import RateLimiter, YandexApiClient
from factory.errors import BlockedAnalyticsAccess
from factory.redaction import PLACEHOLDER, forget_secrets, redact
from factory.retry import RetryPolicy

TOKEN_VALUE = "y0_AgAAAABtransportTESTtoken01234567"


@pytest.fixture(autouse=True)
def _clean():
    yield
    forget_secrets()


@pytest.fixture
def token():
    return OAuthToken(TOKEN_VALUE, "тест")


class ScriptedOpener:
    """Отдаёт заранее записанную последовательность ответов."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = 0

    def __call__(self, request, timeout):
        self.calls += 1
        status, payload = self.responses[min(self.calls - 1, len(self.responses) - 1)]
        body = json.dumps(payload).encode() if payload is not None else b""
        return status, body


def _client(opener, token, *, dry_run=False, attempts=4, sleeps=None):
    return YandexApiClient(
        "https://api-metrika.yandex.net", token, service="metrika", dry_run=dry_run,
        opener=opener, rate_limiter=RateLimiter(min_interval=0),
        retry_policy=RetryPolicy(max_attempts=attempts, base_delay=0.01, max_delay=0.02),
        sleep=(sleeps.append if sleeps is not None else (lambda _s: None)),
    )


# ------------------------------------------------------------ не повторяются
@pytest.mark.parametrize("status,fragment", [
    (401, "токен не принят"),
    (403, "нет прав"),
    (404, "не найден"),
    (422, "некорректный"),
])
def test_terminal_statuses_are_not_retried(status, fragment, token):
    opener = ScriptedOpener((status, {"message": "нет"}))
    client = _client(opener, token)
    with pytest.raises(BlockedAnalyticsAccess) as excinfo:
        client.get("/management/v1/counters")
    assert opener.calls == 1, "терминальный ответ повторять нельзя"
    assert fragment in excinfo.value.reason


def test_401_asks_for_rotation_not_for_new_permissions(token):
    opener = ScriptedOpener((401, {"message": "expired"}))
    with pytest.raises(BlockedAnalyticsAccess) as excinfo:
        _client(opener, token).get("/management/v1/counters")
    assert "ротация" in excinfo.value.required_input


def test_403_asks_for_permissions_not_for_a_new_token(token):
    opener = ScriptedOpener((403, {"message": "forbidden"}))
    with pytest.raises(BlockedAnalyticsAccess) as excinfo:
        _client(opener, token).get("/management/v1/counters")
    assert "прав" in excinfo.value.required_input


# ----------------------------------------------------------------- повторы
@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_retryable_statuses_are_retried_then_succeed(status, token):
    opener = ScriptedOpener((status, None), (status, None), (200, {"rows": 0, "counters": []}))
    sleeps: list[float] = []
    response = _client(opener, token, sleeps=sleeps).get("/management/v1/counters")
    assert response.ok and opener.calls == 3
    assert len(sleeps) == 2, "повтор без паузы — это не backoff"
    assert sleeps[1] >= sleeps[0] * 0.5, "задержка обязана расти"


@pytest.mark.parametrize("status", [429, 503])
def test_exhausted_retries_become_a_named_blocker(status, token):
    opener = ScriptedOpener((status, None))
    with pytest.raises(BlockedAnalyticsAccess) as excinfo:
        _client(opener, token, attempts=3).get("/management/v1/counters")
    assert opener.calls == 3
    assert "Повторы исчерпаны" in excinfo.value.reason
    assert excinfo.value.status == "BLOCKED_ANALYTICS_ACCESS"


def test_analytics_access_failure_is_not_retried_by_the_pipeline():
    """Повтор задания создал бы второй счётчик: статус обязан быть нерепитабельным."""
    from factory.errors import NON_RETRYABLE

    assert "BLOCKED_ANALYTICS_ACCESS" in NON_RETRYABLE
    assert not BlockedAnalyticsAccess("x").retryable


def test_network_failure_is_retried_then_named(token):
    class Failing:
        calls = 0

        def __call__(self, request, timeout):
            Failing.calls += 1
            raise OSError("нет сети")

    with pytest.raises(BlockedAnalyticsAccess) as excinfo:
        _client(Failing(), token, attempts=2).get("/management/v1/counters")
    assert Failing.calls == 2
    assert "сеть недоступна" in excinfo.value.reason


def test_allowed_status_is_not_an_error(token):
    """409 HOST_ALREADY_ADDED — это идемпотентность, а не сбой."""
    opener = ScriptedOpener((409, {"error_code": "HOST_ALREADY_ADDED"}))
    response = _client(opener, token).request(
        "POST", "/v4/user/1/hosts", body={"host_url": "https://x.tld"},
        allow_statuses=frozenset({409}))
    assert response.status == 409 and not response.ok


# ------------------------------------------------------------------ dry-run
def test_dry_run_never_sends_a_mutating_request(token):
    opener = ScriptedOpener((200, {"counter": {"id": 1}}))
    response = _client(opener, token, dry_run=True).post(
        "/management/v1/counters", body={"counter": {"name": "x"}})
    assert response.planned and opener.calls == 0


def test_dry_run_still_reads(token):
    opener = ScriptedOpener((200, {"rows": 0, "counters": []}))
    response = _client(opener, token, dry_run=True).get("/management/v1/counters")
    assert response.ok and opener.calls == 1


# ------------------------------------------------------------- лимит частоты
def test_requests_are_rate_limited(token):
    clock = {"now": 0.0}
    slept: list[float] = []

    limiter = RateLimiter(
        min_interval=0.5,
        sleep=lambda seconds: (slept.append(seconds), clock.__setitem__("now", clock["now"] + seconds)),
        clock=lambda: clock["now"],
    )
    client = YandexApiClient(
        "https://api-metrika.yandex.net", token, service="metrika", dry_run=False,
        opener=ScriptedOpener((200, {"rows": 0})), rate_limiter=limiter, sleep=lambda _s: None)
    client.get("/management/v1/counters")
    client.get("/management/v1/counters")
    assert slept, "второй запрос ушёл без паузы — лимита частоты нет"


# ------------------------------------------------------------------ редакция
def test_error_body_is_redacted_before_it_reaches_the_report(token):
    """Яндекс может вернуть эхо запроса. В отчёт токен из него попасть не должен."""
    opener = ScriptedOpener((403, {"message": f"bad token OAuth {TOKEN_VALUE}"}))
    with pytest.raises(BlockedAnalyticsAccess) as excinfo:
        _client(opener, token).get("/management/v1/counters")
    assert TOKEN_VALUE not in excinfo.value.reason
    assert PLACEHOLDER in excinfo.value.reason


def test_audit_entry_carries_no_token(token, tmp_path, monkeypatch):
    from factory import audit

    entries: list[dict] = []
    monkeypatch.setattr(audit, "record", lambda **kw: entries.append(kw))
    opener = ScriptedOpener((200, {"rows": 0, "counters": []}))
    _client(opener, token).get("/management/v1/counters")

    assert entries, "вызов API обязан попасть в audit trail"
    text = json.dumps(entries, ensure_ascii=False, default=str)
    assert TOKEN_VALUE not in text
    assert entries[0]["action"] == "analytics.metrika.get"
    assert entries[0]["exit_code"] == 200
    assert entries[0]["mutation"] is False


def test_mutation_is_marked_in_the_audit_trail(token, monkeypatch):
    from factory import audit

    entries: list[dict] = []
    monkeypatch.setattr(audit, "record", lambda **kw: entries.append(kw))
    _client(ScriptedOpener((200, {"counter": {"id": 5}})), token).post(
        "/management/v1/counters", body={"counter": {"name": "x"}})
    assert entries[0]["mutation"] is True


def test_authorization_header_is_built_from_the_token(token):
    seen = {}

    def opener(request, timeout):
        seen["auth"] = request.get_header("Authorization")
        return 200, b"{}"

    _client(opener, token).get("/management/v1/counters")
    assert seen["auth"] == f"OAuth {TOKEN_VALUE}"
    # И он же обязан быть вырезан из любого текста, который куда-то выводится.
    assert TOKEN_VALUE not in redact(f"header={seen['auth']}")
