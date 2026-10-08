"""REQ-ANALYTICS-OPERATOR: почему у домена нет данных Вебмастера — три разных ответа.

«host_id пуст» объясняется отсутствием сайта в аккаунте, неподтверждёнными
правами или ошибкой сопоставления; это разные действия, и смешивать их нельзя.
"""
from __future__ import annotations

from factory.errors import BlockedAnalyticsAccess
from seo_operator import webmaster_inventory as wi


class Provider:
    def __init__(self, hosts=None, states=None, fail=None):
        self.hosts, self.states, self.fail = hosts or [], states or {}, fail
        self.writes = 0

    def list_hosts(self):
        if self.fail:
            raise self.fail
        return self.hosts

    def get_verification_marker(self, host_id):
        return {"verification_state": self.states.get(host_id, "NONE")}

    def ensure_webmaster_host(self, *a, **k):
        self.writes += 1

    def verify_webmaster_host(self, *a, **k):
        self.writes += 1


def _entry(domain, host_id=None):
    return {"domain": domain, "webmaster": {"host_id": host_id}}


def test_four_states_are_told_apart():
    provider = Provider(
        hosts=[
            {"host_id": "https:a.example:443", "ascii_host_url": "https://a.example/"},
            {"host_id": "http:b.example:80", "ascii_host_url": "http://b.example/"},
            {"host_id": "https:c.example:443", "ascii_host_url": "https://c.example/"},
            {"host_id": "https:d.example:443", "ascii_host_url": "https://d.example/"},
        ],
        states={"https:a.example:443": "NONE", "https:c.example:443": "VERIFIED",
                "https:d.example:443": "VERIFIED"},
    )
    rows = wi.inventory(provider, [
        _entry("a.example"), _entry("b.example"), _entry("c.example"),
        _entry("d.example", "https:d.example:443"), _entry("e.example"),
    ])["domains"]
    states = {r["domain"]: r["state"] for r in rows}
    assert states == {
        "a.example": "IN_ACCOUNT_UNVERIFIED",
        "b.example": "MAPPING_MISMATCH",       # только http-хост
        "c.example": "MAPPING_MISMATCH",       # подтверждён, реестр не знает
        "d.example": "VERIFIED_MAPPED",
        "e.example": "NOT_IN_ACCOUNT",
    }
    assert provider.writes == 0


def test_no_token_is_blocked_access_not_empty_account():
    report = wi.inventory(Provider(fail=BlockedAnalyticsAccess("файл токена не найден")),
                          [_entry("a.example")])
    assert report["status"] == "BLOCKED_ACCESS"
    assert report["domains"] == []
