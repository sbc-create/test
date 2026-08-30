"""REQ-SEO-TOPVISOR: источник позиций не выдумывает данные и не молчит о возрасте.

Topvisor — система измерения. Ошибка измерения дороже отсутствия измерения:
пустой ответ, нарисованный отчётом как «0 запросов в TOP-10», хуже честного
«источник недоступен». Поэтому проверяется ровно то, что отличает измерение
от выдумки: отказ вместо пустоты, явная пометка устаревших данных, отсутствие
дублей и полное отсутствие секрета в любом выходе.
"""
from __future__ import annotations

import json

import pytest

from seo_operator.datasources.base import SourceStatus, UnavailableSourceError
from seo_operator.datasources.topvisor import (
    DEFAULT_TTL_SECONDS,
    TopvisorCache,
    TopvisorSource,
    healthcheck,
)

SIX_DOMAINS = (
    "yummyani.site",
    "yummyani.org",
    "yummyani.biz",
    "lordfilm47.space",
    "lordserial33.biz",
    "1lordserials1.online",
)


def _projects(*pairs):
    return [{"id": pid, "site": domain} for pid, domain in pairs]


class _FakeClient:
    """Минимальный двойник клиента: отдаёт проекты или падает."""

    def __init__(self, projects=None, error=None):
        self._projects = projects or []
        self._error = error
        self.calls = 0

    def projects(self):
        self.calls += 1
        if self._error:
            raise self._error
        return self._projects


# --------------------------------------------------------------- probe

def test_probe_without_credential_is_not_available(tmp_path):
    source = TopvisorSource(cache_path=tmp_path / "c.json", credential_check=lambda: (False, "нет доступа к каталогу"))
    availability = source.probe()
    assert availability.status is SourceStatus.MISSING_CREDENTIALS
    assert "нет доступа" in availability.detail
    assert not availability.usable


def test_fetch_without_credential_raises_instead_of_returning_empty(tmp_path):
    source = TopvisorSource(cache_path=tmp_path / "c.json", credential_check=lambda: (False, "нет доступа"))
    with pytest.raises(UnavailableSourceError):
        source.fetch("yummyani.site")


# --------------------------------------------------------------- dedup

def test_duplicate_project_ids_collapse_to_one(tmp_path):
    client = _FakeClient(_projects((1, "yummyani.site"), (1, "yummyani.site")))
    source = TopvisorSource(
        cache_path=tmp_path / "c.json",
        credential_check=lambda: (True, "ok"),
        client_factory=lambda: client,
    )
    snapshot = source.snapshot()
    assert len(snapshot["projects"]) == 1


def test_projects_without_an_id_do_not_collapse_into_one(tmp_path):
    """Отсутствующий идентификатор — не признак одинаковости.

    Дедупликация шла по `id`, и записи без него получали общий ключ `None`.
    Два разных проекта схлопывались в один, а вместе со вторым исчезал его
    домен — молча, без единой пометки. Для модуля, написанного ради того,
    чтобы отсутствие данных нельзя было спутать с нулём, это худший вид потери.
    """
    client = _FakeClient([{"site": "yummyani.site"}, {"site": "yummyani.org"}])
    source = TopvisorSource(
        cache_path=tmp_path / "c.json",
        credential_check=lambda: (True, "ok"),
        client_factory=lambda: client,
    )
    domains = {p["domain"] for p in source.snapshot()["projects"]}
    assert domains == {"yummyani.site", "yummyani.org"}


def test_two_projects_on_one_domain_are_reported_not_silently_merged(tmp_path):
    client = _FakeClient(_projects((1, "yummyani.site"), (2, "yummyani.site")))
    source = TopvisorSource(
        cache_path=tmp_path / "c.json",
        credential_check=lambda: (True, "ok"),
        client_factory=lambda: client,
    )
    snapshot = source.snapshot()
    assert "yummyani.site" in snapshot["duplicate_domains"]


# --------------------------------------------------------------- TTL

def test_fresh_cache_is_served_without_calling_the_api(tmp_path):
    client = _FakeClient(_projects((1, "yummyani.site")))
    path = tmp_path / "c.json"
    source = TopvisorSource(path, credential_check=lambda: (True, "ok"), client_factory=lambda: client, now=lambda: 1000.0)
    source.snapshot()
    assert client.calls == 1
    source.snapshot()
    assert client.calls == 1, "свежий кэш не должен ходить в API"


def test_expired_cache_is_refetched(tmp_path):
    client = _FakeClient(_projects((1, "yummyani.site")))
    path = tmp_path / "c.json"
    clock = {"t": 1000.0}
    source = TopvisorSource(path, credential_check=lambda: (True, "ok"), client_factory=lambda: client, now=lambda: clock["t"])
    source.snapshot()
    clock["t"] += DEFAULT_TTL_SECONDS + 1
    source.snapshot()
    assert client.calls == 2


# ------------------------------------------------- last-known-good

def test_failed_refetch_returns_last_known_good_marked_stale(tmp_path):
    path = tmp_path / "c.json"
    clock = {"t": 1000.0}
    good = TopvisorSource(path, credential_check=lambda: (True, "ok"),
                          client_factory=lambda: _FakeClient(_projects((1, "yummyani.site"))),
                          now=lambda: clock["t"])
    good.snapshot()

    clock["t"] += DEFAULT_TTL_SECONDS + 60
    broken = TopvisorSource(path, credential_check=lambda: (True, "ok"),
                            client_factory=lambda: _FakeClient(error=RuntimeError("API 500")),
                            now=lambda: clock["t"])
    snapshot = broken.snapshot()

    assert snapshot["stale"] is True, "устаревшие данные обязаны быть помечены"
    assert snapshot["age_seconds"] >= DEFAULT_TTL_SECONDS
    assert snapshot["projects"], "last-known-good не должен теряться"
    assert "API 500" in snapshot["refresh_error"]


def test_no_cache_and_failed_fetch_raises_rather_than_inventing(tmp_path):
    source = TopvisorSource(tmp_path / "c.json", credential_check=lambda: (True, "ok"),
                            client_factory=lambda: _FakeClient(error=RuntimeError("API 500")))
    with pytest.raises(UnavailableSourceError):
        source.snapshot()


# --------------------------------------------------------------- healthcheck

def test_healthcheck_names_domains_without_a_project(tmp_path):
    client = _FakeClient(_projects((1, "yummyani.site"), (2, "yummyani.org")))
    source = TopvisorSource(tmp_path / "c.json", credential_check=lambda: (True, "ok"),
                            client_factory=lambda: client)
    report = healthcheck(source)
    assert report["matched"] == 2
    assert report["expected"] == len(SIX_DOMAINS)
    assert "lordfilm47.space" in report["missing_domains"]
    assert report["status"] == "INCOMPLETE"


def test_healthcheck_is_connected_only_when_all_six_are_read(tmp_path):
    client = _FakeClient(_projects(*[(i + 1, d) for i, d in enumerate(SIX_DOMAINS)]))
    source = TopvisorSource(tmp_path / "c.json", credential_check=lambda: (True, "ok"),
                            client_factory=lambda: client)
    report = healthcheck(source)
    assert report["status"] == "CONNECTED"
    assert report["missing_domains"] == []


def test_healthcheck_without_credential_is_blocked_not_connected(tmp_path):
    source = TopvisorSource(tmp_path / "c.json", credential_check=lambda: (False, "нет доступа к каталогу"))
    report = healthcheck(source)
    assert report["status"] == "BLOCKED_CREDENTIAL"
    assert report["matched"] == 0


# --------------------------------------------------------------- secrets

def test_no_secret_material_reaches_cache_or_healthcheck(tmp_path):
    path = tmp_path / "c.json"
    client = _FakeClient(_projects((1, "yummyani.site")))
    source = TopvisorSource(path, credential_check=lambda: (True, "ok"), client_factory=lambda: client)
    report = healthcheck(source)
    written = path.read_text(encoding="utf-8")
    for forbidden in ("api_key", "Authorization", "user_id"):
        assert forbidden not in written
        assert forbidden not in json.dumps(report, ensure_ascii=False)


def test_cache_survives_a_corrupted_file(tmp_path):
    """Битый кэш — не причина упасть и не причина выдумать данные."""
    path = tmp_path / "c.json"
    path.write_text("{не json", encoding="utf-8")
    cache = TopvisorCache(path, ttl_seconds=DEFAULT_TTL_SECONDS)
    assert cache.read() is None
