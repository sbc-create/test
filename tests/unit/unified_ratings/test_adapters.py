"""Адаптеры: таймаут, rate limit, ограниченный retry, разбор контракта.

Живой сети здесь нет. Каждый ответ источника подставляется фиктивным
opener, поэтому тест проверяет наше поведение, а не доступность чужого
сервера.
"""

from __future__ import annotations

import io
import json
import urllib.error

import pytest

from factory.ratings.adapters.base import AdapterError
from factory.ratings.rate_limit import RateLimiter
from factory.unified_ratings.adapters.anilist import (
    AniListAdapter,
    distribution_map,
    vote_count_from_distribution,
)
from factory.unified_ratings.adapters.kitsu import KitsuAdapter, vote_count_from_frequencies
from factory.unified_ratings.adapters.provider_feed import ProviderFeedAdapter
from factory.unified_ratings.adapters.simkl import SimklAdapter
from factory.unified_ratings.http_client import HttpClient, redact_headers


class FakeResponse(io.BytesIO):
    def __init__(self, payload: bytes, status: int = 200, headers: dict | None = None) -> None:
        super().__init__(payload)
        self.status = status
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
        return False


def json_opener(payload: dict, *, headers: dict | None = None):
    def _open(req, timeout):  # noqa: ARG001
        return FakeResponse(json.dumps(payload).encode(), headers=headers or {})

    return _open


def error_opener(code: int, *, headers: dict | None = None, body: bytes = b"{}"):
    calls = {"n": 0}

    def _open(req, timeout):  # noqa: ARG001
        calls["n"] += 1
        raise urllib.error.HTTPError(req.full_url, code, "err", headers or {}, io.BytesIO(body))

    _open.calls = calls  # type: ignore[attr-defined]
    return _open


def client(opener, *, max_retries: int = 3) -> HttpClient:
    sleeps: list[float] = []
    http = HttpClient(
        user_agent="test",
        rate_limiter=RateLimiter(max_rps=1000.0, max_per_minute=100000),
        timeout=1.0,
        max_retries=max_retries,
        opener=opener,
        sleeper=sleeps.append,
    )
    http.sleeps = sleeps  # type: ignore[attr-defined]
    return http


# ---------------------------------------------------------------------------
# таймаут
# ---------------------------------------------------------------------------


def test_timeout_is_retried_a_bounded_number_of_times():
    calls = {"n": 0}

    def _open(req, timeout):  # noqa: ARG001
        calls["n"] += 1
        raise TimeoutError("read timed out")

    http = client(_open, max_retries=3)
    with pytest.raises(AdapterError) as exc:
        http.request("https://example.test/x")
    assert exc.value.code == "TIMEOUT"
    assert calls["n"] == 4, "одна попытка плюс ровно три повтора"


def test_retry_never_runs_forever():
    http = client(error_opener(503), max_retries=2)
    with pytest.raises(AdapterError):
        http.request("https://example.test/x")
    assert http.retries == 2


def test_backoff_is_capped():
    opener = error_opener(429, headers={"Retry-After": "86400"})
    http = client(opener, max_retries=2)
    with pytest.raises(AdapterError):
        http.request("https://example.test/x")
    assert all(delay <= http.max_backoff_seconds for delay in http.sleeps)


# ---------------------------------------------------------------------------
# rate limit
# ---------------------------------------------------------------------------


def test_rate_limited_response_is_counted_and_reported():
    http = client(error_opener(429, headers={"Retry-After": "5"}), max_retries=1)
    with pytest.raises(AdapterError) as exc:
        http.request("https://example.test/x")
    assert exc.value.code == "RATE_LIMITED"
    assert exc.value.retry_after == 5.0
    assert http.rate_limited >= 1


def test_rate_limiter_respects_the_minute_budget():
    now = {"t": 0.0}
    slept: list[float] = []
    limiter = RateLimiter(
        max_rps=1000.0,
        max_per_minute=3,
        clock=lambda: now["t"],
        sleeper=lambda d: (slept.append(d), now.__setitem__("t", now["t"] + d)),
    )
    for _ in range(4):
        limiter.wait()
    assert slept, "четвёртый запрос в минутном бюджете из трёх обязан подождать"


def test_our_caps_are_not_looser_than_the_documented_limits():
    from factory.unified_ratings.sources import ANILIST, KITSU, SHIKIMORI

    # AniList сам объявил 30 запросов в минуту заголовком.
    assert ANILIST.max_requests_per_minute <= 30
    # Shikimori документирует 5 rps / 90 rpm.
    assert SHIKIMORI.max_rps <= 5.0
    assert SHIKIMORI.max_requests_per_minute <= 90
    # Kitsu лимит не объявляет — cap выбран консервативно.
    assert KITSU.max_requests_per_minute <= 30


# ---------------------------------------------------------------------------
# авторизация и ключи
# ---------------------------------------------------------------------------


def test_auth_rejection_opens_the_circuit_instead_of_retrying():
    opener = error_opener(403)
    http = client(opener, max_retries=3)
    with pytest.raises(AdapterError) as exc:
        http.request("https://example.test/x")
    assert exc.value.code == "AUTH_REJECTED"
    assert exc.value.hard_circuit is True
    assert opener.calls["n"] == 1, "403 не повторяют: доступ от повторов не появится"


def test_missing_credential_is_not_retried():
    opener = error_opener(412)
    http = client(opener, max_retries=3)
    with pytest.raises(AdapterError) as exc:
        http.request("https://example.test/x")
    assert exc.value.code == "CREDENTIAL_REQUIRED"
    assert opener.calls["n"] == 1


def test_secrets_are_redacted_from_recorded_headers():
    redacted = redact_headers(
        {"Authorization": "Bearer abc123", "simkl-api-key": "key-xyz", "Accept": "application/json"}
    )
    assert redacted["Authorization"] == "[REDACTED]"
    assert redacted["simkl-api-key"] == "[REDACTED]"
    assert redacted["Accept"] == "application/json"
    assert "abc123" not in json.dumps(redacted)
    assert "key-xyz" not in json.dumps(redacted)


# ---------------------------------------------------------------------------
# Simkl без ключа
# ---------------------------------------------------------------------------


def test_simkl_refuses_before_making_a_network_call():
    calls = {"n": 0}

    def _open(req, timeout):  # noqa: ARG001
        calls["n"] += 1
        raise AssertionError("сетевой запрос без ключа выполняться не должен")

    adapter = SimklAdapter(client(_open), client_id=None)
    with pytest.raises(AdapterError) as exc:
        adapter.fetch_by_external_ids(["1"])
    assert exc.value.code == "CREDENTIAL_REQUIRED"
    assert calls["n"] == 0


def test_simkl_health_reports_the_blocker_without_touching_the_network():
    adapter = SimklAdapter(client(lambda req, timeout: None), client_id=None)
    health = adapter.health()
    assert health["state"] == "BLOCKED"
    assert health["network_calls_made"] == 0
    assert "client_id" in health["blocker"]


# ---------------------------------------------------------------------------
# разбор контрактов
# ---------------------------------------------------------------------------


ANILIST_MEDIA = {
    "id": 1,
    "idMal": 1,
    "title": {"romaji": "Cowboy Bebop", "english": "Cowboy Bebop", "native": "カウボーイビバップ"},
    "synonyms": [],
    "format": "TV",
    "status": "FINISHED",
    "episodes": 26,
    "season": "SPRING",
    "seasonYear": 1998,
    "startDate": {"year": 1998, "month": 4, "day": 3},
    "averageScore": 86,
    "meanScore": 86,
    "popularity": 468649,
    "favourites": 32225,
    "updatedAt": 1790024451,
    "siteUrl": "https://anilist.co/anime/1",
    "stats": {"scoreDistribution": [{"score": 80, "amount": 10}, {"score": 90, "amount": 15}]},
}


def test_anilist_parses_score_votes_and_provenance():
    opener = json_opener({"data": {"Page": {"media": [ANILIST_MEDIA]}}})
    adapter = AniListAdapter(client(opener))
    result = adapter.fetch_by_mal_ids(["1"])["1"]
    assert result.found is True
    assert result.raw_score == 86
    assert result.vote_count == 25
    assert result.provenance_url == "https://anilist.co/anime/1"
    assert result.year == 1998
    assert result.kind == "TV"


def test_anilist_popularity_is_never_taken_as_a_score():
    opener = json_opener({"data": {"Page": {"media": [ANILIST_MEDIA]}}})
    result = AniListAdapter(client(opener)).fetch_by_mal_ids(["1"])["1"]
    assert result.raw_score != ANILIST_MEDIA["popularity"]
    assert result.vote_count != ANILIST_MEDIA["popularity"]
    assert result.raw_payload["_popularity_is_not_a_rating"] == 468649


def test_anilist_missing_media_is_not_found_not_zero():
    opener = json_opener({"data": {"Page": {"media": []}}})
    result = AniListAdapter(client(opener)).fetch_by_mal_ids(["999"])["999"]
    assert result.found is False
    assert result.raw_score is None
    assert result.error == "NOT_FOUND"


def test_anilist_graphql_errors_surface():
    opener = json_opener({"errors": [{"message": "Too Many Requests"}]})
    with pytest.raises(AdapterError) as exc:
        AniListAdapter(client(opener)).fetch_by_mal_ids(["1"])
    assert exc.value.code == "GRAPHQL_ERROR"


def test_partial_distribution_makes_the_vote_count_unknown():
    assert vote_count_from_distribution([{"score": 80, "amount": "many"}]) is None
    assert vote_count_from_distribution([{"score": 80, "amount": 5}]) == 5
    assert vote_count_from_distribution([]) is None
    assert distribution_map([{"score": 80, "amount": 5}]) == {"80": 5}


KITSU_ITEM = {
    "id": "1",
    "type": "anime",
    "attributes": {
        "canonicalTitle": "Cowboy Bebop",
        "titles": {"en": "Cowboy Bebop", "ja_jp": "カウボーイビバップ"},
        "subtype": "TV",
        "episodeCount": 26,
        "startDate": "1998-04-03",
        "averageRating": "82.27",
        "ratingFrequencies": {"16": "10", "20": "15"},
        "userCount": 162344,
        "updatedAt": "2026-09-21T18:44:35.125Z",
        "slug": "cowboy-bebop",
        "ratingRank": 200,
        "popularityRank": 44,
    },
}


def test_kitsu_distinguishes_voters_from_users():
    payload = {
        "data": [
            {
                "id": "64108",
                "attributes": {"externalSite": "myanimelist/anime", "externalId": "1"},
                "relationships": {"item": {"data": {"type": "anime", "id": "1"}}},
            }
        ],
        "included": [KITSU_ITEM],
    }
    result = KitsuAdapter(client(json_opener(payload))).fetch_by_mal_ids(["1"])["1"]
    assert result.raw_score == "82.27"
    assert result.vote_count == 25, "число оценивших — сумма ratingFrequencies"
    assert result.user_count == 162344, "userCount — это библиотеки, а не голоса"
    assert result.vote_count != result.user_count


def test_kitsu_rating_frequencies_reject_junk():
    assert vote_count_from_frequencies({"16": "10", "20": "nope"}) is None
    assert vote_count_from_frequencies({}) is None
    assert vote_count_from_frequencies({"16": 4, "20": 6}) == 10


def test_kitsu_unmapped_mal_id_is_not_found():
    payload = {"data": [], "included": []}
    result = KitsuAdapter(client(json_opener(payload))).fetch_by_mal_ids(["12345"])["12345"]
    assert result.found is False
    assert "NOT_FOUND" in result.error


# ---------------------------------------------------------------------------
# фид поставщика
# ---------------------------------------------------------------------------


def test_provider_feed_never_touches_the_network():
    items = {
        "0213338": {
            "name": "Ковбой Бибоп",
            "year": 1998,
            "imdb_rating": 8.9,
            "external_ids": {"imdb": "0213338"},
        }
    }
    adapter = ProviderFeedAdapter("provider_feed_imdb", items)
    result = adapter.fetch_by_external_ids(["0213338"])["0213338"]
    assert result.raw_score == 8.9
    assert adapter.health()["network_calls_made"] == 0
    assert "фид" in result.raw_payload["_delivery"]


def test_provider_feed_missing_value_is_not_found():
    items = {"x": {"name": "Без оценки", "external_ids": {"imdb": "x"}}}
    result = ProviderFeedAdapter("provider_feed_imdb", items).fetch_by_external_ids(["x"])["x"]
    assert result.found is False
    assert result.raw_score is None


# ---------------------------------------------------------------------------
# capabilities
# ---------------------------------------------------------------------------


def test_every_adapter_declares_its_capabilities():
    adapters = [
        AniListAdapter(client(json_opener({}))),
        KitsuAdapter(client(json_opener({}))),
        SimklAdapter(client(json_opener({})), client_id=None),
        ProviderFeedAdapter("provider_feed_imdb", {}),
    ]
    for adapter in adapters:
        caps = adapter.capabilities().as_dict()
        assert caps["source_key"]
        assert caps["incremental_mode"], "режим инкрементального сбора обязан быть назван"
        assert isinstance(caps["requires_credential"], bool)


# ---------------------------------------------------------------------------
# мусорный идентификатор не уносит соседей по пакету
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["-2680", "witcher-siren", "0", "-9999987899999", "1864094294"])
def test_invalid_external_ids_never_reach_the_source(bad):
    """Каталог содержит слаги и отрицательные числа в поле MAL ID."""
    from factory.unified_ratings.adapters.anilist import valid_external_id

    assert valid_external_id(bad) is None


@pytest.mark.parametrize("good", ["1", "5114", "64536"])
def test_plausible_ids_pass(good):
    from factory.unified_ratings.adapters.anilist import valid_external_id

    assert valid_external_id(good) == int(good)


def test_a_rejected_batch_is_split_instead_of_lost():
    """AniList отвечает 400 на весь запрос из-за одного идентификатора."""
    poison = "777777"
    calls = {"n": 0}

    def _open(req, timeout):  # noqa: ARG001
        calls["n"] += 1
        body = req.data.decode()
        if f"{poison}" in body:
            raise urllib.error.HTTPError(req.full_url, 400, "bad", {}, io.BytesIO(b"{}"))
        return FakeResponse(json.dumps({"data": {"Page": {"media": [ANILIST_MEDIA]}}}).encode())

    adapter = AniListAdapter(client(_open, max_retries=0))
    result = adapter.fetch_by_mal_ids(["1", poison])
    assert result["1"].found is True, "здоровый тайтл не должен теряться вместе с виновником"
    assert result[poison].found is False
    assert "REJECTED_BY_SOURCE" in result[poison].error
    assert calls["n"] >= 3, "пакет делился, а не отбрасывался целиком"
