"""REQ-LORDS-LIVE: живой каталог CDNVideoHub без боевых секретов.

Весь набор работает против поддельного источника, воспроизводящего контракт из
`knowledge/cdnvideohub/content-api.yaml`: несколько страниц, повторяющиеся
записи, фильмы и сериалы, 429 с Retry-After, 500, таймаут, пустой и частичный
ответ, испорченная пагинация. Боевой токен здесь не нужен и не используется —
проверяется поведение адаптера, а не доступность провайдера.

Главное свойство, которое проверяется настойчивее прочих: отказ источника не
должен превращаться в пустой каталог. Пустой ответ, обрыв сети и 500 обязаны
оставить прежние данные на месте.
"""

from __future__ import annotations

import json
import urllib.request

import pytest

from factory.lords import content_api, content_live
from factory.paths import PATHS

CONTRACT = PATHS.root / "knowledge/cdnvideohub/content-api.yaml"


# ---------------------------------------------------------------------------
# Поддельный источник
# ---------------------------------------------------------------------------
def title(external_id: str, *, name: str | None = None, kind: str = "movie",
          year: int = 2020, kp: str | None = None) -> dict:
    return {
        "id": external_id,
        "name": name or f"Тайтл {external_id}",
        "type": kind,
        "is_series": kind == "series",
        "year": year,
        "poster_url": f"https://poster.cdnvideohub.com/{external_id}.jpg",
        "licensed": True,
        "tags": ["anime"] if kind == "animation" else [],
        "external_ids": {"kp": kp or f"kp-{external_id}"},
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-02T00:00:00Z",
    }


class FakeApi:
    """Источник, отвечающий по контракту. Сеть не используется."""

    def __init__(self, pages: list[dict], *, failures: list[tuple[int, dict]] | None = None):
        self.pages = pages
        self.failures = list(failures or [])
        self.calls: list[str] = []
        self.slept: list[float] = []

    def opener(self, request: urllib.request.Request, timeout: float):
        url = request.full_url
        self.calls.append(url)

        assert request.get_header("Authorization", "").startswith("Bearer "), (
            "запрос ушёл без заголовка авторизации"
        )

        if self.failures:
            status, headers = self.failures.pop(0)
            if status == 0:
                raise TimeoutError("источник не ответил вовремя")
            if status == -1:
                raise OSError("соединение разорвано")
            return status, b'{"error":"transient"}', headers

        cursor = ""
        if "cursor=" in url:
            cursor = url.split("cursor=", 1)[1].split("&", 1)[0]
        index = 0
        if cursor:
            index = next(
                (n for n, page in enumerate(self.pages)
                 if str(page.get("_cursor", "")) == cursor),
                0,
            )
        page = dict(self.pages[index])
        page.pop("_cursor", None)
        return 200, json.dumps(page).encode("utf-8"), {}

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)


def page(items: list[dict], *, next_cursor: str | None = None, cursor: str | None = None,
         total: int | None = None) -> dict:
    payload: dict = {
        "items": items,
        "has_more": bool(next_cursor),
        "next_cursor": next_cursor,
    }
    if total is not None:
        payload["total"] = total
    if cursor is not None:
        payload["_cursor"] = cursor
    return payload


@pytest.fixture(scope="module")
def contract() -> content_live.LiveContract:
    return content_live.load_live_contract()


def make_fetcher(api: FakeApi, contract: content_live.LiveContract) -> content_live.Fetcher:
    return content_live.Fetcher(
        contract=contract,
        token="test-token-not-a-real-credential",
        opener=api.opener,
        sleep=api.sleep,
        monotonic=lambda: 0.0,
    )


# ---------------------------------------------------------------------------
# Контракт
# ---------------------------------------------------------------------------
class TestContract:
    def test_the_frozen_contract_parses(self, contract):
        assert contract.base_url.startswith("https://")
        assert "titles" in contract.endpoints

    def test_the_base_url_is_not_the_obsolete_one(self, contract):
        raw = content_api.load_contract().raw
        for obsolete in raw.get("obsolete_base_urls", []):
            assert contract.base_url != obsolete

    def test_urls_are_built_from_the_contract_not_hardcoded(self, contract):
        url = contract.url("episodes", id="abc", season="2")
        assert url.startswith(contract.base_url)
        assert "abc" in url and "2" in url

    def test_a_half_filled_contract_is_refused(self, tmp_path):
        path = tmp_path / "c.yaml"
        path.write_text("status: provided\nbase_url: https://x.invalid/\n", encoding="utf-8")
        with pytest.raises(content_live.SourceError):
            content_live.load_live_contract(path)


# ---------------------------------------------------------------------------
# Обход страниц
# ---------------------------------------------------------------------------
class TestPagination:
    def test_every_page_is_walked(self, contract):
        api = FakeApi([
            page([title("a"), title("b")], next_cursor="c2"),
            page([title("c")], cursor="c2", next_cursor="c3"),
            page([title("d")], cursor="c3"),
        ])
        walk = content_live.walk_pages(make_fetcher(api, contract), contract.url("titles"))
        assert [i["id"] for i in walk.items] == ["a", "b", "c", "d"]
        assert walk.pages == 3
        assert walk.stopped_by == "has_more"

    def test_a_repeated_cursor_stops_the_walk(self, contract):
        """Испорченная пагинация не должна крутиться вечно."""
        api = FakeApi([
            page([title("a")], next_cursor="loop"),
            page([title("b")], cursor="loop", next_cursor="loop"),
        ])
        with pytest.raises(content_live.SourceError, match="зациклена"):
            content_live.walk_pages(make_fetcher(api, contract), contract.url("titles"))

    def test_has_more_without_a_cursor_ends_the_walk(self, contract):
        api = FakeApi([{"items": [title("a")], "has_more": True, "next_cursor": None}])
        walk = content_live.walk_pages(make_fetcher(api, contract), contract.url("titles"))
        assert walk.stopped_by == "cursor_absent"
        assert len(walk.items) == 1

    def test_a_response_without_items_is_refused(self, contract):
        api = FakeApi([{"has_more": False}])
        with pytest.raises(content_live.SourceError, match="items"):
            content_live.walk_pages(make_fetcher(api, contract), contract.url("titles"))

    def test_the_page_cap_is_honoured(self, contract, monkeypatch):
        looping = [page([title(f"x{n}")], cursor=f"c{n}", next_cursor=f"c{n + 1}")
                   for n in range(50)]
        api = FakeApi(looping)
        small = dataclass_replace(contract, max_pages=5)
        walk = content_live.walk_pages(make_fetcher(api, small), small.url("titles"))
        assert walk.pages == 5
        assert walk.stopped_by == "max_pages"

    def test_the_limit_never_exceeds_the_contract_maximum(self, contract):
        api = FakeApi([page([title("a")])])
        content_live.walk_pages(make_fetcher(api, contract), contract.url("titles"))
        limit = int(api.calls[0].split("limit=")[1].split("&")[0])
        assert limit <= contract.max_size


def dataclass_replace(contract, **changes):
    import dataclasses
    return dataclasses.replace(contract, **changes)


# ---------------------------------------------------------------------------
# Отказы источника
# ---------------------------------------------------------------------------
class TestRetries:
    def test_429_is_retried_and_respects_retry_after(self, contract):
        api = FakeApi([page([title("a")])], failures=[(429, {"Retry-After": "2"})])
        fetcher = make_fetcher(api, contract)
        walk = content_live.walk_pages(fetcher, contract.url("titles"))
        assert len(walk.items) == 1
        assert fetcher.retries_made == 1
        assert api.slept, "повтор произошёл без паузы"
        assert max(api.slept) <= contract.max_retry_after_ms / 1000

    def test_500_is_retried(self, contract):
        api = FakeApi([page([title("a")])], failures=[(500, {}), (503, {})])
        fetcher = make_fetcher(api, contract)
        walk = content_live.walk_pages(fetcher, contract.url("titles"))
        assert len(walk.items) == 1
        assert fetcher.retries_made == 2

    def test_a_timeout_is_retried(self, contract):
        api = FakeApi([page([title("a")])], failures=[(0, {})])
        fetcher = make_fetcher(api, contract)
        assert len(content_live.walk_pages(fetcher, contract.url("titles")).items) == 1

    def test_401_is_not_retried(self, contract):
        """Ответ не изменится от повтора, а лимит потратится."""
        api = FakeApi([page([title("a")])], failures=[(401, {})])
        fetcher = make_fetcher(api, contract)
        with pytest.raises(content_live.SourceError) as excinfo:
            content_live.walk_pages(fetcher, contract.url("titles"))
        assert excinfo.value.status == 401
        assert fetcher.retries_made == 0

    def test_retries_are_bounded(self, contract):
        api = FakeApi([page([title("a")])],
                      failures=[(500, {})] * (contract.max_retries + 5))
        fetcher = make_fetcher(api, contract)
        with pytest.raises(content_live.SourceError):
            content_live.walk_pages(fetcher, contract.url("titles"))
        assert fetcher.retries_made == contract.max_retries

    def test_backoff_grows(self, contract):
        """Паузы между попытками растут.

        В `slept` попадают и паузы ограничения частоты, и выдержка повторов;
        различаются они величиной, поэтому первые отфильтровываются.
        """
        api = FakeApi([page([title("a")])], failures=[(500, {}), (500, {}), (500, {})])
        content_live.walk_pages(make_fetcher(api, contract), contract.url("titles"))

        throttle = contract.min_interval_ms / 1000
        backoff = [s for s in api.slept if s > throttle]
        assert len(backoff) == 3, f"ожидалось три выдержки, получено {backoff}"
        assert backoff == sorted(backoff), f"выдержка не растёт: {backoff}"
        assert backoff[0] < backoff[-1], "выдержка постоянна"
        assert max(backoff) <= contract.backoff_max_ms / 1000

    def test_throttling_paces_requests(self, contract):
        """Между запросами к источнику есть пауза."""
        api = FakeApi([
            page([title("a")], next_cursor="c2"),
            page([title("b")], cursor="c2"),
        ])
        content_live.walk_pages(make_fetcher(api, contract), contract.url("titles"))
        throttle = contract.min_interval_ms / 1000
        assert any(abs(s - throttle) < 1e-9 for s in api.slept), api.slept


# ---------------------------------------------------------------------------
# Нормализация и дедупликация
# ---------------------------------------------------------------------------
class TestNormalisation:
    def test_a_record_without_an_id_is_rejected_not_invented(self, contract):
        good, rejected = content_live.normalize_all(
            [title("a"), {"name": "без id"}], contract
        )
        assert [i["external_id"] for i in good] == ["a"]
        assert len(rejected) == 1

    def test_types_are_normalised(self, contract):
        good, _ = content_live.normalize_all(
            [title("m", kind="movie"), title("s", kind="series")], contract
        )
        by_id = {i["external_id"]: i for i in good}
        assert by_id["m"]["is_series"] is False
        assert by_id["s"]["is_series"] is True

    def test_the_playback_pair_comes_from_external_ids(self, contract):
        good, _ = content_live.normalize_all([title("a", kp="12345")], contract)
        assert good[0]["playback"] == {"aggregator": "kp", "title_id": "12345"}

    def test_a_title_without_external_ids_has_no_playback_pair(self, contract):
        raw = title("a")
        raw["external_ids"] = {}
        good, _ = content_live.normalize_all([raw], contract)
        assert good[0]["playback"] is None

    def test_duplicates_are_collapsed_by_stable_id(self, contract):
        good, _ = content_live.normalize_all(
            [title("a"), title("a"), title("b")], contract
        )
        plan = content_api.plan_sync({}, good)
        assert sorted(plan.created) == ["a", "b"]
        assert plan.duplicates == ["a"]


# ---------------------------------------------------------------------------
# Кэш и устаревание
# ---------------------------------------------------------------------------
class TestCacheAndStale:
    def test_a_successful_run_writes_the_cache(self, contract, tmp_path):
        api = FakeApi([page([title("a"), title("b")])])
        cache = tmp_path / "c.json"
        outcome = content_live.fetch_catalog(
            contract=contract, fetcher=make_fetcher(api, contract),
            cache_file=cache, now_ms=1_000_000,
        )
        assert outcome.status == content_live.FRESH
        assert cache.is_file()
        assert len(content_live.read_cache(cache).items) == 2

    def test_an_unreachable_source_falls_back_to_last_known_good(self, contract, tmp_path):
        cache = tmp_path / "c.json"
        content_live.write_cache(cache, [
            content_live.normalize_title(title("old"), contract)
        ], now_ms=0, source="live")

        api = FakeApi([page([])], failures=[(-1, {})] * 20)
        outcome = content_live.fetch_catalog(
            contract=contract, fetcher=make_fetcher(api, contract),
            cache_file=cache, now_ms=5_000,
        )
        assert outcome.status == content_live.STALE
        assert [i["external_id"] for i in outcome.items] == ["old"]
        assert outcome.cache_age_ms == 5_000

    def test_an_empty_response_never_empties_the_catalog(self, contract, tmp_path):
        """Пустой ответ — отказ источника, а не «каталог опустел»."""
        cache = tmp_path / "c.json"
        content_live.write_cache(cache, [
            content_live.normalize_title(title("keep"), contract)
        ], now_ms=0, source="live")

        api = FakeApi([page([])])
        outcome = content_live.fetch_catalog(
            contract=contract, fetcher=make_fetcher(api, contract),
            cache_file=cache, now_ms=1_000,
        )
        assert outcome.status == content_live.STALE
        assert [i["external_id"] for i in outcome.items] == ["keep"]
        # Кэш не перезаписан пустотой.
        assert [i["external_id"] for i in content_live.read_cache(cache).items] == ["keep"]

    def test_an_empty_response_without_a_cache_blocks_instead_of_publishing_nothing(
        self, contract, tmp_path
    ):
        api = FakeApi([page([])])
        outcome = content_live.fetch_catalog(
            contract=contract, fetcher=make_fetcher(api, contract),
            cache_file=tmp_path / "absent.json", now_ms=1_000,
        )
        assert outcome.status == content_live.BLOCKED_SOURCE
        assert outcome.items == []

    def test_stale_can_be_refused(self, contract, tmp_path):
        cache = tmp_path / "c.json"
        content_live.write_cache(cache, [
            content_live.normalize_title(title("old"), contract)
        ], now_ms=0, source="live")
        api = FakeApi([page([])], failures=[(-1, {})] * 20)
        outcome = content_live.fetch_catalog(
            contract=contract, fetcher=make_fetcher(api, contract),
            cache_file=cache, now_ms=1_000, allow_stale=False,
        )
        assert outcome.status == content_live.BLOCKED_SOURCE

    def test_ttl_marks_an_old_cache_as_not_fresh(self, contract, tmp_path):
        cache = tmp_path / "c.json"
        content_live.write_cache(cache, [], now_ms=0, source="live")
        entry = content_live.read_cache(cache)
        assert entry.is_fresh(contract.cache_ttl_ms - 1, contract.cache_ttl_ms)
        assert not entry.is_fresh(contract.cache_ttl_ms + 1, contract.cache_ttl_ms)

    def test_the_write_is_atomic(self, contract, tmp_path):
        """Промежуточного состояния на диске не существует."""
        target = tmp_path / "catalog.json"
        content_live.write_atomic(target, {"items": [1, 2, 3]})
        assert json.loads(target.read_text(encoding="utf-8"))["items"] == [1, 2, 3]
        leftovers = [p.name for p in tmp_path.iterdir() if p.name.startswith(".")]
        assert leftovers == [], f"остался временный файл: {leftovers}"


# ---------------------------------------------------------------------------
# Идемпотентность
# ---------------------------------------------------------------------------
class TestIdempotency:
    def test_the_same_response_twice_changes_nothing(self, contract):
        items, _ = content_live.normalize_all([title("a"), title("b")], contract)
        existing = {i["external_id"]: i for i in items}
        plan = content_api.plan_sync(existing, items)
        assert plan.changes == 0
        assert len(plan.unchanged) == 2

    def test_a_changed_field_is_an_update_not_a_duplicate(self, contract):
        first, _ = content_live.normalize_all([title("a", name="Было")], contract)
        second, _ = content_live.normalize_all([title("a", name="Стало")], contract)
        plan = content_api.plan_sync({i["external_id"]: i for i in first}, second)
        assert plan.updated == ["a"]
        assert plan.created == []

    def test_a_partial_response_refuses_deletions(self, contract):
        many, _ = content_live.normalize_all(
            [title(str(n)) for n in range(10)], contract
        )
        few, _ = content_live.normalize_all([title("0")], contract)
        plan = content_api.plan_sync({i["external_id"]: i for i in many}, few)
        assert plan.deletions_refused, "частичный ответ обязан запрещать удаление"
        assert len(plan.stale) == 9


# ---------------------------------------------------------------------------
# Разделы
# ---------------------------------------------------------------------------
class TestSections:
    def test_a_section_without_material_is_not_published(self, contract):
        items, _ = content_live.normalize_all([title("m", kind="movie")], contract)
        sections = content_live.enabled_sections(items, contract)
        assert sections["movies"]["enabled"] is True
        assert sections["series"]["enabled"] is False

    def test_collections_stay_off_because_the_source_has_no_endpoint(self, contract):
        sections = content_live.enabled_sections([], contract)
        assert sections["collections"]["enabled"] is False
        assert "endpoint" in sections["collections"]["reason"]


# ---------------------------------------------------------------------------
# Секреты
# ---------------------------------------------------------------------------
class TestSecrets:
    def test_the_token_is_sent_as_a_header_and_never_in_the_url(self, contract):
        api = FakeApi([page([title("a")])])
        content_live.walk_pages(make_fetcher(api, contract), contract.url("titles"))
        for url in api.calls:
            assert "test-token" not in url, f"токен попал в адрес: {url}"

    def test_the_outcome_report_carries_no_token(self, contract, tmp_path):
        api = FakeApi([page([title("a")])])
        outcome = content_live.fetch_catalog(
            contract=contract, fetcher=make_fetcher(api, contract),
            cache_file=tmp_path / "c.json", now_ms=1,
        )
        assert "test-token" not in json.dumps(outcome.as_dict(), ensure_ascii=False)

    def test_the_cache_file_carries_no_token(self, contract, tmp_path):
        cache = tmp_path / "c.json"
        api = FakeApi([page([title("a")])])
        content_live.fetch_catalog(
            contract=contract, fetcher=make_fetcher(api, contract),
            cache_file=cache, now_ms=1,
        )
        assert "test-token" not in cache.read_text(encoding="utf-8")

    def test_the_contract_forbids_the_token_in_the_browser(self):
        raw = content_api.load_contract().raw
        assert raw["auth"]["browser_forbidden"] is True
