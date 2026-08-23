"""REQ-ANALYTICS-OPERATOR: SEO-оператор получает данные, а не выдумывает нули.

Проверяется главное свойство ежедневного сбора: отсутствующий показатель
попадает в отчёт как «не измерено» с причиной. Отчёт, в котором «0 визитов» и
«счётчика ещё нет» выглядят одинаково, хуже отсутствующего отчёта.
"""
from __future__ import annotations

import json

import pytest

from factory.errors import BlockedAnalyticsAccess
from seo_operator import analytics_collect
from seo_operator.datasources.base import UnavailableSourceError
from seo_operator.datasources.live import YandexMetrika, YandexWebmaster, probe_all

PLANNED_ENTRY = {
    "domain": "yummyani.site",
    "counter_id": None,
    "goals": [],
    "webmaster": {"host_id": None},
}
LIVE_ENTRY = {
    "domain": "yummyani.site",
    "counter_id": 90000001,
    "goals": ["search"],
    "webmaster": {"host_id": "https:yummyani.site:443"},
}


class StubProvider:
    """Провайдер, отвечающий заранее заданным способом."""

    def __init__(self, *, metrika=None, webmaster=None, fail=None):
        self._metrika = metrika or {}
        self._webmaster = webmaster or {}
        self._fail = fail

    def get_metrica_report(self, counter_id, **kwargs):
        if self._fail:
            raise self._fail
        return {"totals": [11, 22, 1.7, 90.0, 30.0], "data": [{"dimensions": [], "metrics": [1]}],
                "sampled": False, "sample_share": 1.0, **self._metrika}

    def list_goal_ids(self, counter_id):
        if self._fail:
            raise self._fail
        return {"search": 101}

    def get_webmaster_report(self, host_id, resource, params=None):
        if self._fail:
            raise self._fail
        return {"resource": resource, "host_id": host_id, "payload": self._webmaster}


def test_missing_counter_produces_not_measured_not_zero():
    collection = analytics_collect.collect_domain(
        StubProvider(), PLANNED_ENTRY, date1="7daysAgo", date2="yesterday")
    payload = collection.as_dict()

    assert payload["measured_count"] == 0
    for item in payload["measurements"]:
        assert item["measured"] is False
        assert item["value"] == analytics_collect.NOT_MEASURED
        assert item["value"] != 0
        assert item["reason"], f"{item['key']} не назвал причину"


def test_all_thirteen_groups_of_the_brief_are_present():
    keys = {m["key"] for m in analytics_collect.collect_domain(
        StubProvider(), PLANNED_ENTRY, date1="a", date2="b").as_dict()["measurements"]}
    assert keys == {
        "visitors", "visits", "page_depth", "avg_visit_duration", "bounce_rate",
        "traffic_sources", "search_engines", "landing_pages", "popular_pages",
        "goal_reaches", "pages_in_search", "excluded_pages", "external_links",
        "technical_issues",
    }


def test_measured_values_carry_the_sampling_flag():
    """40% сессий и 100% сессий — разные утверждения, отчёт обязан их различать."""
    collection = analytics_collect.collect_domain(
        StubProvider(), LIVE_ENTRY, date1="a", date2="b")
    measured = [m for m in collection.as_dict()["measurements"] if m["measured"]]
    assert measured
    metrika = [m for m in measured if m["key"] == "visits"][0]
    assert metrika["sampled"] is False
    assert metrika["sample_share"] == 1.0


def test_api_failure_becomes_not_measured_with_the_reason():
    failure = BlockedAnalyticsAccess("Метрика ответила HTTP 503")
    collection = analytics_collect.collect_domain(
        StubProvider(fail=failure), LIVE_ENTRY, date1="a", date2="b")
    payload = collection.as_dict()
    assert payload["measured_count"] == 0
    assert all("503" in m["reason"] for m in payload["measurements"]
               if m["key"] in {"visitors", "visits"})


def test_collect_summary_says_how_much_was_not_measured():
    report = analytics_collect.collect(provider=StubProvider())
    summary = report["summary"]
    assert summary["total"] == summary["measured"] + summary["not_measured"]
    assert "не измерены" in summary["note"]
    assert report["read_only"] is True


def test_collect_writes_an_artifact(tmp_path):
    report = analytics_collect.collect(provider=StubProvider(), artifacts_dir=tmp_path)
    path = tmp_path / report["artifact"].rsplit("/", 1)[-1]
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["read_only"] is True


def test_collection_never_writes_to_yandex():
    """Сборщик обязан быть read-only: ни одного метода записи он не вызывает."""
    class Tripwire(StubProvider):
        def ensure_metrica_counter(self, *a, **k):
            raise AssertionError("сборщик попытался создать счётчик")

        def ensure_metrica_goals(self, *a, **k):
            raise AssertionError("сборщик попытался создать цель")

        def ensure_webmaster_host(self, *a, **k):
            raise AssertionError("сборщик попытался зарегистрировать сайт")

        def verify_webmaster_host(self, *a, **k):
            raise AssertionError("сборщик попытался подтвердить права")

    analytics_collect.collect(provider=Tripwire())


# --------------------------------------------------------------- источники
def test_yandex_sources_require_a_path_not_a_value():
    """В окружении лежит путь к файлу, а не сам токен."""
    for source in (YandexMetrika(), YandexWebmaster()):
        assert source.required_env == ()


@pytest.mark.parametrize("variable", [
    "YANDEX_OAUTH_TOKEN", "YANDEX_METRIKA_TOKEN", "YANDEX_WEBMASTER_TOKEN",
])
def test_token_value_in_the_environment_makes_the_source_unusable(monkeypatch, variable):
    monkeypatch.setenv(variable, "y0_AgAAAABleakedTHROUGHenvironment12")
    availability = YandexMetrika().probe()
    assert not availability.usable
    assert "переменной окружения" in availability.detail


def test_fetch_without_a_counter_refuses_instead_of_returning_zero(monkeypatch, tmp_path):
    source = YandexMetrika()
    monkeypatch.setattr(source, "probe", lambda: _available())
    with pytest.raises(UnavailableSourceError, match="counter_id"):
        source.fetch("yummyani.site")


def test_webmaster_fetch_without_a_host_refuses(monkeypatch):
    source = YandexWebmaster()
    monkeypatch.setattr(source, "probe", lambda: _available())
    with pytest.raises(UnavailableSourceError, match="host_id"):
        source.fetch("yummyani.site")


def _available():
    from seo_operator.datasources.base import Availability, SourceStatus

    return Availability(SourceStatus.AVAILABLE, "тест")


def test_probe_reports_the_true_reason_today():
    """Источник, до которого нет доступа, обязан назвать причину, а не молчать."""
    probes = probe_all()
    for name in ("yandex_metrika", "yandex_webmaster"):
        availability = probes[name]
        assert availability.detail, f"{name} не назвал причину"
        if not availability.usable:
            assert "секрет" in availability.detail or "токен" in availability.detail


def test_data_source_registry_names_only_a_path_variable():
    from seo_operator.registry import load_data_sources

    sources = {s["name"]: s for s in load_data_sources()["sources"]}
    for name in ("yandex_metrika", "yandex_webmaster"):
        assert sources[name]["required_env"] == ["YANDEX_OAUTH_TOKEN_FILE"]


def test_daily_timer_is_not_enabled_yet():
    """Расписание готово, но выключено: сайтов ещё нет, отчёт был бы пустым."""
    from factory.paths import PATHS

    installer = (PATHS.automation / "host" / "install-units.sh").read_text(encoding="utf-8")
    enabled_block = installer.split("for timer in", 1)[1].split("done", 1)[0]
    assert "site-factory-analytics-collect.timer" not in enabled_block
    assert "site-factory-analytics-collect.timer" in installer, "таймер должен быть упомянут"
    assert "НЕ включены намеренно" in installer


def test_apply_unit_has_no_timer():
    """Создание счётчиков — разовое действие человека, а не расписание."""
    from factory.paths import PATHS

    units = PATHS.automation / "host" / "systemd"
    assert (units / "site-factory-analytics-apply.service").exists()
    assert not (units / "site-factory-analytics-apply.timer").exists()


def test_units_take_the_secret_through_systemd_credentials():
    from factory.paths import PATHS

    units = PATHS.automation / "host" / "systemd"
    for name in ("site-factory-analytics-apply.service",
                 "site-factory-analytics-collect.service"):
        text = (units / name).read_text(encoding="utf-8")
        assert "LoadCredential=yandex_oauth:" in text, name
        assert "YANDEX_OAUTH_TOKEN_FILE=%d/yandex_oauth" in text, name
        # Значение токена не появляется ни в Environment=, ни в EnvironmentFile.
        assert "YANDEX_OAUTH_TOKEN=" not in text, name


def test_collect_unit_cannot_write():
    from factory.paths import PATHS

    text = (PATHS.automation / "host" / "systemd"
            / "site-factory-analytics-collect.service").read_text(encoding="utf-8")
    # Проверяется исполняемая строка, а не комментарий: комментарий имеет право
    # объяснять, чего в unit'е нет.
    exec_lines = [line for line in text.splitlines() if line.startswith("ExecStart=")]
    assert exec_lines, "у unit'а нет ExecStart"
    for line in exec_lines:
        assert "--confirm-writes" not in line
        assert "--verify" not in line
        assert "analytics-collect" in line
