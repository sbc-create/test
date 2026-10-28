"""Отчёты разбора поведения zonafilm.cc (ANALYSIS_ORDER, 28.10).

Отчёт, который отвечает на гипотезу, обязан видеть хвост, а не первые 20 строк:
именно первые 20 строк и скрыли карточки на дашборде. Неполные сутки
сравниваются с теми же часами вчера, поэтому разбивка по часам — с датой.
Суточные срезы — поштучно по дням: недельное окно Метрика уже отклоняла.
"""
from __future__ import annotations

import datetime as dt

from factory.errors import BlockedAnalyticsAccess
from seo_operator import analytics_collect

from tests.unit.test_yandex_analytics_operator import LIVE_ENTRY, StubProvider

ZONA_CC = {**LIVE_ENTRY, "domain": "zonafilm.cc"}
DAILY = ("pages_with_params", "internal_search", "referer_to_page", "pages_by_device",
         "exit_pages", "landings_by_source")
# 29.10 05:00Z = 08:00 МСК: последние полные сутки по часам счётчика — 28.10 и 27.10.
NOW = dt.datetime(2026, 10, 29, 5, 0, tzinfo=dt.timezone.utc)
DAYS = ("2026-10-28", "2026-10-27")
KEYS = tuple(f"{k}@{d}" for d in DAYS for k in DAILY) + ("device_hour", "control_visits")


class Recorder(StubProvider):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.calls = []

    def get_metrica_report(self, counter_id, **kwargs):
        self.calls.append(kwargs)
        return {**super().get_metrica_report(counter_id, **kwargs), "total_rows": 3}


def _reports(provider):
    return {m.key: m.as_dict() for m in analytics_collect._behavior_reports(provider, 1, now=NOW)}


def _by_key(provider, entry):
    payload = analytics_collect.collect_domain(provider, entry, date1="7daysAgo", date2="yesterday").as_dict()
    return {m["key"]: m for m in payload["measurements"]}


def test_behavior_reports_present_for_listed_zona_domains_only():
    for domain in ("zonafilm.cc", "zonafilm.space", "zonafilm12.site"):
        entry = {**LIVE_ENTRY, "domain": domain}
        assert any(k.startswith("pages_with_params@") for k in _by_key(Recorder(), entry)), domain
    assert not any(k.startswith(("pages_with_params", "device_hour", "control_visits"))
                   for k in _by_key(Recorder(), LIVE_ENTRY))


def test_last_full_days_are_taken_in_the_counter_timezone():
    # 23:30Z 28.10 — уже 02:30 МСК 29.10: вчера по счётчику — 28.10, а не 27.10.
    assert analytics_collect._behavior_dates(dt.datetime(2026, 10, 28, 23, 30, tzinfo=dt.timezone.utc)) == list(DAYS)
    assert analytics_collect._behavior_dates(NOW) == list(DAYS)


def test_every_report_sees_the_tail_not_the_first_twenty_rows():
    by_key = _reports(Recorder())
    assert set(by_key) == set(KEYS)
    for key in KEYS:
        assert by_key[key]["top_n"] == analytics_collect.BEHAVIOR_LIMIT > 20, key
        assert by_key[key]["total_rows"] == 3, key


def test_daily_reports_are_one_day_each_never_a_week():
    p = Recorder()
    _reports(p)
    daily = [c for c in p.calls if c["date1"] in DAYS]
    assert len(daily) == len(DAILY) * len(DAYS)
    assert all(c["date1"] == c["date2"] for c in daily)


def test_internal_search_is_filtered_to_the_search_path():
    p = Recorder()
    _reports(p)
    calls = [c for c in p.calls if c.get("filters") == "ym:pv:URLPath=='/search/'"]
    assert len(calls) == len(DAYS) and all(c["dimensions"] == ["ym:pv:URL"] for c in calls)


def test_device_hour_compares_the_same_hours_of_yesterday_and_today():
    p = Recorder()
    by_key = _reports(p)
    call = next(c for c in p.calls if c["dimensions"] == ["ym:s:date", "ym:s:hour", "ym:s:deviceCategory", "ym:s:isRobot"])
    assert (call["date1"], call["date2"]) == ("yesterday", "today")
    assert "ym:s:pageviews" in call["metrics"]
    assert "отсечка" in by_key["device_hour"]["title"]


def test_control_visits_are_selected_by_their_label_and_kept_apart():
    p = Recorder()
    _reports(p)
    call = next(c for c in p.calls if "ym:s:UTMSource" in c["dimensions"])
    assert call["filters"] == f"ym:s:UTMSource=='{analytics_collect.CONTROL_UTM_SOURCE}'"
    assert "ym:s:isRobot" in call["dimensions"] and call["date2"] == "today"


def test_failure_is_not_measured_with_the_api_reason():
    by_key = _reports(StubProvider(fail=BlockedAnalyticsAccess("Query is too complicated")))
    for key in KEYS:
        assert by_key[key]["measured"] is False and "too complicated" in by_key[key]["reason"], key


def test_recent_popular_queries_ask_for_explicit_last_seven_days():
    """Без дат Вебмастер отдал 30.09–06.10 у всех хостов (27–28.10): окно задаётся явно."""
    seen = []

    class P(StubProvider):
        def get_webmaster_report(self, host_id, resource, params=None):
            seen.append(params)
            return super().get_webmaster_report(host_id, resource, params)

    m = analytics_collect._popular_queries_recent(P(), "h", now=NOW).as_dict()
    assert m["measured"] and m["key"] == "popular_queries_recent"
    assert seen[0]["date_from"] == "2026-10-22T00:00:00+03:00" and seen[0]["date_to"] == "2026-10-28T23:59:59+03:00"
    assert seen[0]["query_indicator"] == analytics_collect.QUERY_INDICATORS


def test_recent_popular_queries_failure_keeps_the_default_request():
    by_key = {m["key"]: m for m in analytics_collect.collect_domain(
        StubProvider(fail=BlockedAnalyticsAccess("bad date")), LIVE_ENTRY, date1="a", date2="b").as_dict()["measurements"]}
    assert by_key["popular_queries_recent"]["measured"] is False and "bad date" in by_key["popular_queries_recent"]["reason"]
    assert "popular_queries" in by_key
