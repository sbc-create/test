"""Отчёты разбора поведения zonafilm.cc (ANALYSIS_ORDER, 28.10).

Отчёт, который отвечает на гипотезу, обязан видеть хвост, а не первые 20 строк:
именно первые 20 строк и скрыли карточки на дашборде. Неполные сутки
сравниваются с теми же часами вчера, поэтому разбивка по часам — с датой.
"""
from __future__ import annotations

from factory.errors import BlockedAnalyticsAccess
from seo_operator import analytics_collect

from tests.unit.test_yandex_analytics_operator import LIVE_ENTRY, StubProvider

ZONA_CC = {**LIVE_ENTRY, "domain": "zonafilm.cc"}
KEYS = ("pages_with_params", "referer_to_page", "exit_pages", "device_hour")


class Recorder(StubProvider):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.calls = []

    def get_metrica_report(self, counter_id, **kwargs):
        self.calls.append(kwargs)
        return {**super().get_metrica_report(counter_id, **kwargs), "total_rows": 3}


def _by_key(provider, entry):
    payload = analytics_collect.collect_domain(provider, entry, date1="7daysAgo", date2="yesterday").as_dict()
    return {m["key"]: m for m in payload["measurements"]}


def _call(provider, dims):
    return next(c for c in provider.calls if c.get("dimensions") == dims)


def test_behavior_reports_present_for_zonafilm_cc_only():
    assert all(k in _by_key(Recorder(), ZONA_CC) for k in KEYS)
    assert not any(k in _by_key(Recorder(), LIVE_ENTRY) for k in KEYS)


def test_behavior_reports_see_the_tail_not_the_first_twenty_rows():
    by_key = _by_key(Recorder(), ZONA_CC)
    for key in KEYS:
        assert by_key[key]["top_n"] == analytics_collect.BEHAVIOR_LIMIT > 20, key
        assert by_key[key]["total_rows"] == 3, key


def test_pageview_reports_cover_yesterday_not_a_week():
    p = Recorder()
    _by_key(p, ZONA_CC)
    for dims in (["ym:pv:URL"], ["ym:pv:referer", "ym:pv:URL"]):
        call = _call(p, dims)
        assert (call["date1"], call["date2"]) == ("yesterday", "yesterday"), dims
        assert call["limit"] == analytics_collect.BEHAVIOR_LIMIT


def test_device_hour_compares_the_same_hours_of_yesterday_and_today():
    p = Recorder()
    by_key = _by_key(p, ZONA_CC)
    call = _call(p, ["ym:s:date", "ym:s:hour", "ym:s:deviceCategory", "ym:s:isRobot"])
    assert (call["date1"], call["date2"]) == ("yesterday", "today")
    assert "ym:s:pageviews" in call["metrics"]
    assert "отсечка" in by_key["device_hour"]["title"]


def test_failure_is_not_measured_with_the_api_reason():
    by_key = _by_key(StubProvider(fail=BlockedAnalyticsAccess("Query is too complicated")), ZONA_CC)
    for key in KEYS:
        assert by_key[key]["measured"] is False and "too complicated" in by_key[key]["reason"], key
