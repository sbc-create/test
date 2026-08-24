"""REQ-ANALYTICS-REPAIR: повторный боевой прогон чинит настройку и ничего не плодит.

Прогон, который предстоит выполнить на сервере, здесь проигрывается целиком —
через настоящую команду `analytics apply`, на поддельной Метрике и на копии
реестра. Проверяется то, ради чего он и запускается:

* счётчики не создаются заново, а находятся по домену;
* цели не дублируются;
* запись сессий выключается через ``code_options.visor`` и подтверждается;
* в реестр попадают counter_id и все девять числовых goal_id;
* второй запуск подряд не делает ни одной записи.

Боевые идентификаторы взяты настоящие: если реестр разойдётся с ними, тест
покраснеет раньше, чем это увидит Метрика.
"""
from __future__ import annotations

import json
import shutil
import urllib.request

import pytest

from factory.analytics import events as events_mod
from factory.analytics import registry
from factory.analytics.credentials import OAuthToken
from factory.analytics.transport import RateLimiter, YandexApiClient
from factory.analytics.yandex import VISOR_OPTION, YandexAnalyticsProvider
from factory.paths import PATHS
from factory.redaction import forget_secrets

TOKEN_VALUE = "y0_AgAAAABrepairTESTtoken0123456789"

LIVE = {
    "yummyani.site": 111881037,
    "yummyani.org": 111881038,
    "yummyani.biz": 111881039,
}


@pytest.fixture(autouse=True)
def _clean():
    yield
    forget_secrets()


class Account:
    """Аккаунт Метрики в том состоянии, в каком его оставил первый прогон.

    Три счётчика, девять целей на каждом, запись сессий включена.
    """

    def __init__(self):
        self.counters = [
            {
                "id": counter_id,
                "name": f"YummyAnime — {domain}",
                "status": "Active",
                "site2": {"site": domain},
                "code_options": {"async": True, "visor": True, "clickmap": True},
                "webvisor": {"arch_enabled": True},
                "goals": [
                    {"id": counter_id * 10 + index, "name": event.goal_name, "type": "action",
                     "conditions": [{"type": "exact", "url": event.id}]}
                    for index, event in enumerate(events_mod.EVENTS)
                ],
            }
            for domain, counter_id in LIVE.items()
        ]
        self.requests: list[tuple[str, str, dict | None]] = []

    def _by_id(self, counter_id: int) -> dict | None:
        return next((c for c in self.counters if c["id"] == counter_id), None)

    def __call__(self, request: urllib.request.Request, timeout: float):
        method = request.get_method()
        path = request.full_url.split("?", 1)[0].split(".net", 1)[1]
        body = json.loads(request.data.decode("utf-8")) if request.data else None
        self.requests.append((method, path, body))

        if body and "counter" in body and "webvisor" in body["counter"]:
            return 400, b'{"message":"path: counter.webvisor.arch_enabled"}'
        if method == "GET" and path == "/management/v1/counters":
            return 200, json.dumps({"rows": len(self.counters),
                                    "counters": self.counters}).encode()
        if method == "GET" and path.startswith("/management/v1/counter/"):
            counter = self._by_id(int(path.split("/")[4]))
            return (200, json.dumps({"counter": counter}).encode()) if counter else (404, b"{}")
        if method == "PUT" and path.startswith("/management/v1/counter/"):
            counter = self._by_id(int(path.split("/")[4]))
            counter["code_options"] = {**counter["code_options"],
                                       **(body["counter"].get("code_options") or {})}
            return 200, json.dumps({"counter": counter}).encode()
        if method == "POST":
            raise AssertionError(f"повторный прогон не должен ничего создавать: POST {path}")
        return 404, b'{"message":"unmapped"}'

    def writes(self) -> list[str]:
        return [f"{m} {p}" for m, p, _ in self.requests if m in {"POST", "PUT"}]


@pytest.fixture
def repo(tmp_path):
    """Копия реестра и схемы: боевой файл тест не трогает."""
    root = tmp_path / "repo"
    (root / "config").mkdir(parents=True)
    (root / "schemas").mkdir()
    shutil.copy(PATHS.root / registry.REGISTRY_PATH, root / registry.REGISTRY_PATH)
    shutil.copy(PATHS.root / registry.SCHEMA_PATH, root / registry.SCHEMA_PATH)
    return root


@pytest.fixture
def provider(monkeypatch):
    account = Account()
    token = OAuthToken(TOKEN_VALUE, "тест")

    def build(args):
        instance = YandexAnalyticsProvider(token=token, dry_run=not args.confirm_writes)
        instance._metrika = YandexApiClient(
            "https://api-metrika.yandex.net", token, service="metrika",
            dry_run=not args.confirm_writes, opener=account,
            rate_limiter=RateLimiter(min_interval=0), sleep=lambda _s: None)
        return instance

    from factory.analytics import cli as analytics_cli

    monkeypatch.setattr(analytics_cli, "_provider", build)
    return account


class Args:
    def __init__(self, **kwargs):
        self.site = None
        self.domain = None
        self.confirm_writes = False
        self.json = False
        self.__dict__.update(kwargs)


@pytest.fixture
def scoped_registry(repo, monkeypatch):
    """Реестр команды указывает во временную копию."""
    real_load, real_save, real_upsert = registry.load, registry.save, registry.upsert
    monkeypatch.setattr(registry, "load", lambda root=None: real_load(root or repo))
    monkeypatch.setattr(registry, "save", lambda data, root=None: real_save(data, root or repo))
    monkeypatch.setattr(registry, "upsert", lambda entry, root=None: real_upsert(entry, root or repo))
    from factory.analytics import cli as analytics_cli

    monkeypatch.setattr(analytics_cli, "registry", registry)
    return repo


def test_repair_run_disables_the_visor_without_creating_anything(
    provider, scoped_registry, monkeypatch, capsys
):
    from factory.analytics import cli as analytics_cli

    exit_code = analytics_cli.cmd_apply(Args(confirm_writes=True, json=True))
    capsys.readouterr()

    assert exit_code == 0, "прогон обязан завершиться без блокеров"
    assert all(w.startswith("PUT ") for w in provider.writes()), provider.writes()
    assert len(provider.writes()) == 3, "по одному PUT на счётчик — не больше"
    for counter in provider.counters:
        assert counter["code_options"][VISOR_OPTION] is False
        # Остальные настройки кода счётчика не тронуты.
        assert counter["code_options"]["clickmap"] is True
        assert counter["code_options"]["async"] is True
        assert len(counter["goals"]) == 9


def test_repair_run_records_counter_ids_and_twenty_seven_goal_ids(
    provider, scoped_registry, monkeypatch, capsys
):
    from factory.analytics import cli as analytics_cli

    analytics_cli.cmd_apply(Args(confirm_writes=True, json=True))
    capsys.readouterr()

    data = registry.load()
    total = 0
    for entry in data["properties"]:
        assert entry["counter_id"] == LIVE[entry["domain"]]
        assert entry["counter_state"] == "reused"
        assert entry["webvisor"] is False
        assert set(entry["goal_ids"]) == set(events_mod.EVENT_IDS)
        assert all(isinstance(v, int) for v in entry["goal_ids"].values())
        assert not any("сесси" in p for p in entry["problems"])
        total += len(entry["goal_ids"])
    assert total == 27, f"ожидалось 27 идентификаторов целей, получено {total}"


def test_a_second_repair_run_writes_nothing(provider, scoped_registry, monkeypatch, capsys):
    from factory.analytics import cli as analytics_cli

    analytics_cli.cmd_apply(Args(confirm_writes=True, json=True))
    writes_after_first = len(provider.writes())
    analytics_cli.cmd_apply(Args(confirm_writes=True, json=True))
    capsys.readouterr()

    assert len(provider.writes()) == writes_after_first, (
        "второй прогон подряд не должен слать ни одного запроса на запись"
    )


def test_dry_run_writes_nothing_at_all(provider, scoped_registry, monkeypatch, capsys):
    from factory.analytics import cli as analytics_cli

    analytics_cli.cmd_apply(Args(confirm_writes=False, json=True))
    capsys.readouterr()
    assert provider.writes() == []
    assert all(entry["counter_id"] == LIVE[entry["domain"]]
               for entry in registry.load()["properties"])


def test_a_counter_that_does_not_match_the_registry_stops_the_run(
    provider, scoped_registry, monkeypatch, capsys
):
    """Подмена счётчика — это остановка, а не «принято к сведению»."""
    from factory.analytics import cli as analytics_cli

    provider.counters[0]["id"] = 999999999
    exit_code = analytics_cli.cmd_apply(Args(confirm_writes=True, json=True))
    output = capsys.readouterr().out

    assert exit_code == 2
    assert "BLOCKED_ANALYTICS_ACCESS" in output
    assert "не подменяет счётчик молча" in output
