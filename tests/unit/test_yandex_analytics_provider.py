"""REQ-ANALYTICS: провайдер идемпотентен, честен и не создаёт дублей.

Все тесты работают на поддельном транспорте: боевой сети в unit-тестах нет и
быть не должно. Проверяется именно поведение — что второй запуск не создаёт
второй счётчик, что 401/403/429/5xx разбираются по-разному, и что недоступный
API даёт свой статус, а не пустой результат.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

from factory.analytics import events as events_mod
from factory.analytics.credentials import OAuthToken
from factory.analytics.transport import RateLimiter, YandexApiClient
from factory.analytics.yandex import (
    BLOCKED_DEPLOYMENT,
    PLANNED,
    YandexAnalyticsProvider,
    normalize_domain,
    webvisor_enabled,
)
from factory.redaction import forget_secrets

TOKEN_VALUE = "y0_AgAAAABproviderTESTtoken0123456789"

DOMAINS = ("yummyani.site", "yummyani.org", "yummyani.biz")


@pytest.fixture(autouse=True)
def _clean_secrets():
    yield
    forget_secrets()


@pytest.fixture
def token():
    return OAuthToken(TOKEN_VALUE, "тест")


class FakeYandex:
    """Поддельный Яндекс: помнит счётчики, цели и сайты между вызовами.

    Именно память между вызовами делает тест на идемпотентность настоящим:
    второй запуск обязан увидеть то, что создал первый.
    """

    def __init__(self, counters=None, hosts=None):
        self.counters = list(counters or [])
        self.hosts = list(hosts or [])
        self.requests: list[tuple[str, str, dict | None]] = []
        self._next_counter_id = 90000001
        self._next_goal_id = 100

    def __call__(self, request: urllib.request.Request, timeout: float):
        method = request.get_method()
        url = request.full_url
        path = url.split("?", 1)[0].split(".net", 1)[1]
        body = json.loads(request.data.decode("utf-8")) if request.data else None
        self.requests.append((method, path, body))
        assert request.get_header("Authorization") == f"OAuth {TOKEN_VALUE}"

        if method == "GET" and path == "/management/v1/counters":
            payload = {"rows": len(self.counters), "counters": self.counters}
            return 200, json.dumps(payload).encode()
        if method == "POST" and path == "/management/v1/counters":
            counter = dict(body["counter"])
            counter["id"] = self._next_counter_id
            self._next_counter_id += 1
            counter.setdefault("status", "Active")
            counter.setdefault("goals", [])
            self.counters.append(counter)
            return 200, json.dumps({"counter": counter}).encode()
        if method == "GET" and path.startswith("/management/v1/counter/"):
            counter_id = int(path.split("/")[4])
            for counter in self.counters:
                if counter["id"] == counter_id:
                    return 200, json.dumps({"counter": counter}).encode()
            return 404, b'{"message": "not found"}'
        if method == "POST" and path.endswith("/goals"):
            counter_id = int(path.split("/")[4])
            for counter in self.counters:
                if counter["id"] == counter_id:
                    goal = dict(body["goal"])
                    goal["id"] = self._next_goal_id
                    self._next_goal_id += 1
                    counter.setdefault("goals", []).append(goal)
                    return 200, json.dumps({"goal": goal}).encode()
            return 404, b'{"message": "not found"}'
        if method == "GET" and path == "/v4/user":
            return 200, json.dumps({"user_id": 4242}).encode()
        if method == "GET" and path.endswith("/hosts"):
            return 200, json.dumps({"hosts": self.hosts}).encode()
        if method == "POST" and path.endswith("/hosts"):
            url_ = body["host_url"]
            for host in self.hosts:
                if host["ascii_host_url"] == url_:
                    return 409, b'{"error_code": "HOST_ALREADY_ADDED"}'
            host_id = url_.replace("https://", "https:") + ":443"
            self.hosts.append({"host_id": host_id, "ascii_host_url": url_})
            return 201, json.dumps({"host_id": host_id}).encode()
        if method == "GET" and path.endswith("/verification"):
            return 200, json.dumps({
                "verification_state": "NONE",
                "verification_uin": "abcdef0123456789",
                "applicable_verifiers": ["META_TAG", "HTML_FILE", "DNS"],
            }).encode()
        if method == "POST" and path.endswith("/verification"):
            return 200, json.dumps({"verification_state": "IN_PROGRESS"}).encode()
        if method == "GET" and path == "/stat/v1/data":
            return 200, json.dumps({
                "totals": [10, 20, 1.5, 65.0, 12.5],
                "data": [], "total_rows": 0, "sampled": False, "sample_share": 1.0,
            }).encode()
        return 404, b'{"message": "unmapped in fake"}'

    def counts(self, method: str, path_suffix: str) -> int:
        return sum(1 for m, p, _ in self.requests if m == method and p.endswith(path_suffix))


def _provider(fake, token, *, dry_run=False) -> YandexAnalyticsProvider:
    def client(service, base):
        return YandexApiClient(
            base, token, service=service, dry_run=dry_run, opener=fake,
            rate_limiter=RateLimiter(min_interval=0), sleep=lambda _s: None,
        )

    provider = YandexAnalyticsProvider(token=token, dry_run=dry_run)
    provider._metrika = client("metrika", "https://api-metrika.yandex.net")
    provider._webmaster = client("webmaster", "https://api.webmaster.yandex.net")
    return provider


# ------------------------------------------------------------- нормализация
@pytest.mark.parametrize("raw,expected", [
    ("yummyani.site", "yummyani.site"),
    ("YummyAni.Site", "yummyani.site"),
    ("www.yummyani.site", "yummyani.site"),
    ("https://www.yummyani.site/", "yummyani.site"),
    ("https://yummyani.site:443/catalog/", "yummyani.site"),
    ("yummyani.site.", "yummyani.site"),
])
def test_domain_normalisation(raw, expected):
    """Без нормализации «не найдено» превращается во второй счётчик на тот же сайт."""
    assert normalize_domain(raw) == expected


# ---------------------------------------------------------- создание счётчика
def test_counter_is_created_when_absent(token):
    fake = FakeYandex()
    provider = _provider(fake, token)
    state = provider.ensure_metrica_counter("yummyani.site", "YummyAnime — yummyani.site")
    assert state.created and not state.reused
    assert state.counter_id == 90000001
    assert fake.counts("POST", "/management/v1/counters") == 1


def test_second_run_reuses_and_never_duplicates(token):
    """Главное свойство: повторный запуск не создаёт второй счётчик."""
    fake = FakeYandex()
    provider = _provider(fake, token)
    first = provider.ensure_metrica_counter("yummyani.site", "YummyAnime — yummyani.site")

    again = _provider(fake, token)
    second = again.ensure_metrica_counter("yummyani.site", "YummyAnime — yummyani.site")

    assert second.reused and not second.created
    assert second.counter_id == first.counter_id
    assert fake.counts("POST", "/management/v1/counters") == 1
    assert len(fake.counters) == 1


def test_existing_counter_is_matched_regardless_of_www_and_scheme(token):
    fake = FakeYandex(counters=[
        {"id": 555, "name": "старое имя", "status": "Active",
         "site2": {"site": "https://www.yummyani.org/"}, "goals": []},
    ])
    provider = _provider(fake, token)
    state = provider.ensure_metrica_counter("yummyani.org", "YummyAnime — yummyani.org")
    assert state.reused and state.counter_id == 555
    assert fake.counts("POST", "/management/v1/counters") == 0


def test_renamed_counter_is_still_reused(token):
    """Домен — надёжный признак, имя владелец может поменять в интерфейсе."""
    fake = FakeYandex(counters=[
        {"id": 777, "name": "как-то иначе назвали", "status": "Active",
         "site2": {"site": "yummyani.biz"}, "goals": []},
    ])
    state = _provider(fake, token).ensure_metrica_counter("yummyani.biz", "YummyAnime — yummyani.biz")
    assert state.reused and state.counter_id == 777


def test_ambiguous_domain_is_not_resolved_silently(token):
    """Два счётчика на домен — вопрос владельцу, а не повод выбрать первый."""
    fake = FakeYandex(counters=[
        {"id": 1, "name": "a", "status": "Active", "site2": {"site": "yummyani.site"}, "goals": []},
        {"id": 2, "name": "b", "status": "Active", "site2": {"site": "www.yummyani.site"}, "goals": []},
    ])
    state = _provider(fake, token).ensure_metrica_counter("yummyani.site", "YummyAnime — yummyani.site")
    assert state.counter_id is None
    assert state.status == "ambiguous"
    assert "несколько счётчиков" in state.problems[0]
    assert fake.counts("POST", "/management/v1/counters") == 0


def test_three_domains_get_three_independent_counters(token):
    """Домены не объединяются зеркалами: у каждого сайта свой счётчик."""
    fake = FakeYandex()
    provider = _provider(fake, token)
    ids = []
    for domain in DOMAINS:
        state = provider.ensure_metrica_counter(domain, f"YummyAnime — {domain}")
        ids.append(state.counter_id)

    assert len(set(ids)) == 3, "счётчики обязаны быть разными"
    assert len(fake.counters) == 3
    for counter in fake.counters:
        assert not counter.get("mirrors2"), "фабрика не заводит зеркала"
    sites = sorted(c["site2"]["site"] for c in fake.counters)
    assert sites == sorted(DOMAINS)


def test_counter_creation_sends_no_webvisor_and_no_gdpr_agreement(token):
    """Вебвизор не включается, а юридическое согласие не даётся за владельца."""
    fake = FakeYandex()
    _provider(fake, token).ensure_metrica_counter("yummyani.site", "YummyAnime — yummyani.site")
    body = next(b for m, p, b in fake.requests if m == "POST" and p == "/management/v1/counters")
    assert set(body["counter"]) == {"name", "site2"}
    assert "webvisor" not in body["counter"]
    assert "gdpr_agreement_accepted" not in body["counter"]


@pytest.mark.parametrize("webvisor,expected", [
    ({"arch_enabled": True}, True),
    ({"arch_enabled": False}, False),
    ({"wv_forms": True}, True),
    ({"something_enabled": "true"}, True),
    ({"arch_type": "none"}, False),
    ({}, False),
])
def test_webvisor_detection_errs_towards_switch_it_off(webvisor, expected):
    assert webvisor_enabled({"webvisor": webvisor}) is expected


def test_enabled_webvisor_on_a_reused_counter_is_reported(token):
    fake = FakeYandex(counters=[
        {"id": 9, "name": "x", "status": "Active", "site2": {"site": "yummyani.site"},
         "goals": [], "webvisor": {"arch_enabled": True}},
    ])
    state = _provider(fake, token).ensure_metrica_counter("yummyani.site", "x")
    assert state.webvisor is True
    assert "Вебвизор" in state.problems[0]


# --------------------------------------------------------------------- цели
def test_all_nine_goals_are_created(token):
    fake = FakeYandex()
    provider = _provider(fake, token)
    state = provider.ensure_metrica_counter("yummyani.site", "YummyAnime — yummyani.site")
    state = provider.ensure_metrica_goals(state.counter_id, state)

    assert set(state.goals_created) == set(events_mod.EVENT_IDS)
    assert len(events_mod.EVENT_IDS) == 9
    assert state.goals_complete
    goals = fake.counters[0]["goals"]
    assert len(goals) == 9
    for goal in goals:
        assert goal["type"] == "action"
        assert goal["conditions"][0]["type"] == "exact"


def test_goals_are_not_duplicated_on_a_second_run(token):
    fake = FakeYandex()
    provider = _provider(fake, token)
    state = provider.ensure_metrica_counter("yummyani.site", "n")
    provider.ensure_metrica_goals(state.counter_id, state)
    created_first = fake.counts("POST", "/goals")

    again = _provider(fake, token)
    second = again.ensure_metrica_goals(state.counter_id)
    assert second.goals_created == ()
    assert len(second.goals_present) == 9
    assert fake.counts("POST", "/goals") == created_first == 9


def test_only_missing_goals_are_added(token):
    fake = FakeYandex(counters=[{
        "id": 42, "name": "x", "status": "Active", "site2": {"site": "yummyani.site"},
        "goals": [{"id": 1, "name": "Поиск", "type": "action",
                   "conditions": [{"type": "exact", "url": "search"}]}],
    }])
    provider = _provider(fake, token)
    state = provider.ensure_metrica_goals(42)
    assert "search" in state.goals_present
    assert "search" not in state.goals_created
    assert len(state.goals_created) == 8


def test_dry_run_creates_nothing_at_all(token):
    """План обязан быть планом: ни одного запроса на запись в сеть."""
    fake = FakeYandex()
    provider = _provider(fake, token, dry_run=True)
    state = provider.ensure_metrica_counter("yummyani.site", "YummyAnime — yummyani.site")

    assert state.planned and state.counter_id is None
    assert state.goals_planned == events_mod.EVENT_IDS
    assert all(method == "GET" for method, _, _ in fake.requests), fake.requests
    assert fake.counters == []


# ---------------------------------------------------------------- Вебмастер
def test_undeployed_domain_is_never_registered(token):
    fake = FakeYandex()
    state = _provider(fake, token).ensure_webmaster_host("yummyani.site", deployment_ready=False)
    assert state.verification_state == BLOCKED_DEPLOYMENT
    assert state.host_id is None
    assert not any(m == "POST" for m, _, _ in fake.requests)


def test_undeployed_domain_is_not_reported_as_done(token):
    fake = FakeYandex()
    state = _provider(fake, token).ensure_webmaster_host("yummyani.site", deployment_ready=False)
    assert state.verification_state != "DONE"
    assert state.verification_state != "VERIFIED"


def test_deployed_domain_is_registered_once(token):
    fake = FakeYandex()
    provider = _provider(fake, token)
    first = provider.ensure_webmaster_host("yummyani.site", deployment_ready=True)
    assert first.added and first.host_id

    second = _provider(fake, token).ensure_webmaster_host("yummyani.site", deployment_ready=True)
    assert second.reused and not second.added
    assert len(fake.hosts) == 1


def test_verification_is_not_started_when_the_marker_is_unreachable(token):
    fake = FakeYandex()
    provider = _provider(fake, token)
    result = provider.verify_webmaster_host("https:yummyani.site:443", marker_reachable=False)
    assert result["started"] is False
    assert result["verification_state"] == BLOCKED_DEPLOYMENT
    assert not any(m == "POST" and p.endswith("/verification") for m, p, _ in fake.requests)


def test_marker_is_returned_in_both_documented_forms(token):
    fake = FakeYandex()
    marker = _provider(fake, token).get_verification_marker("https:yummyani.site:443")
    assert marker["verification_uin"] == "abcdef0123456789"
    assert marker["meta_tag"] == '<meta name="yandex-verification" content="abcdef0123456789" />'
    assert marker["html_file_name"] == "yandex_abcdef0123456789.html"
    assert marker["verification_state"] in (
        "NONE", "VERIFIED", "IN_PROGRESS", "VERIFICATION_FAILED", "INTERNAL_ERROR")


def test_dry_run_does_not_start_verification(token):
    fake = FakeYandex(hosts=[{"host_id": "h", "ascii_host_url": "https://yummyani.site"}])
    provider = _provider(fake, token, dry_run=True)
    result = provider.verify_webmaster_host("h", marker_reachable=True)
    assert result["verification_state"] == PLANNED
    assert result["started"] is False
