"""AMD Online: границы robots, разбор, безопасность, сопоставление.

Живой сети здесь нет: каждая страница подставляется фиктивным opener.
Тест проверяет наше поведение, а не доступность чужого сайта.
"""

from __future__ import annotations

import io
import json
import urllib.error

import pytest

from factory.ratings.adapters.base import AdapterError
from factory.unified_ratings.adapters.amd_online import (
    AmdKillSwitch,
    AmdOnlineAdapter,
    robots_allows,
)
from factory.unified_ratings.amd_ingest import AmdIngestor, TitleIndex, _facts_from_fetch
from factory.unified_ratings.matching import MatchStatus, match_by_facts
from factory.unified_ratings.titles import CanonicalTitle

TITLE_URL = "https://amd.online/1413-boevoj-kontinent.html"

PAGE = """
<html><h1>Боевой континент 2</h1>
<div class="amd-sub">Douluo Dalu II</div>
<a href="https://amd.online/anime/god/2023/">2023</a>
<a href="https://amd.online/anime/tip/ona/">ONA</a>
<a href="https://amd.online/anime/ghanr/ekshen/">экшен</a>
<a href="https://amd.online/anime/sezon_goda/leto-2023/">Лето 2023</a>
<div class="multirating-itog-rateval">9.4</div>
<div class="multirating-itog-votes">(16958)</div>
<div data-area="story" title="Сюжет"><span class="multirating-item-rateval-num">9.4</span></div>
<div data-area="actors" title="Персонажи"><span class="multirating-item-rateval-num">9.5</span></div>
<div data-area="graph" title="Рисовка"><span class="multirating-item-rateval-num">9.6</span></div>
<div data-area="sound" title="Озвучка"><span class="multirating-item-rateval-num">9.2</span></div>
<p>Статус: онгоинг</p></html>
"""

SECTION = """
<html>
<a href="https://amd.online/1413-boevoj-kontinent.html">A</a>
<a href="https://amd.online/1723-vtoroj.html">B</a>
<a href="https://amd.online/1413-boevoj-kontinent.html">дубль</a>
<a href="https://amd.online/ongoingi/page/2/">2</a>
<a href="https://amd.online/ongoingi/page/21/">21</a>
</html>
"""

SITEMAP = """<?xml version="1.0"?><urlset>
<url><loc>https://amd.online/1413-boevoj-kontinent.html</loc></url>
<url><loc>https://amd.online/1723-vtoroj.html</loc></url>
<url><loc>https://amd.online/1413-boevoj-kontinent.html</loc></url>
<url><loc>https://amd.online/ongoingi/</loc></url>
</urlset>"""


class Fake(io.BytesIO):
    def __init__(self, body: str, status: int = 200) -> None:
        super().__init__(body.encode())
        self.status = status
        self.headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()
        return False


def adapter_for(pages: dict[str, str], *, errors: dict[str, int] | None = None) -> AmdOnlineAdapter:
    errors = errors or {}
    calls: list[str] = []

    def _open(req, timeout):  # noqa: ARG001
        url = req.full_url
        calls.append(url)
        if url in errors:
            raise urllib.error.HTTPError(url, errors[url], "e", {}, io.BytesIO(b""))
        return Fake(pages.get(url, "<html></html>"))

    adapter = AmdOnlineAdapter(opener=_open, sleeper=lambda _s: None, min_interval=0, jitter=0)
    adapter.calls = calls  # type: ignore[attr-defined]
    return adapter


# ---------------------------------------------------------------------------
# robots
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "allowed"),
    [
        ("https://amd.online/ongoingi/", True),
        ("https://amd.online/1413-x.html", True),
        ("https://amd.online/ongoingi/page/2/", False),
        ("https://amd.online/ongoingi/page/21/", False),
        ("https://amd.online/user/somebody/", False),
        ("https://amd.online/mylists/", False),
        ("https://amd.online/?do=search", False),
        ("https://amd.online/engine/go.php", False),
        ("https://evil.example/amd", False),
    ],
)
def test_robots_rules_are_enforced_before_any_request(url, allowed):
    assert robots_allows(url) is allowed


def test_pagination_is_never_fetched_even_when_advertised():
    adapter = adapter_for({"https://amd.online/ongoingi/": SECTION})
    found = adapter.discover_ongoing_urls()
    assert found["max_page_advertised"] == 21
    assert found["pagination_fetched"] is False
    assert not any("/page/" in u for u in adapter.calls)


def test_a_disallowed_url_raises_instead_of_being_fetched():
    adapter = adapter_for({})
    with pytest.raises(AdapterError) as exc:
        adapter.fetch_page("https://amd.online/ongoingi/page/3/")
    assert exc.value.code == "ROBOTS_DISALLOWED"
    assert adapter.calls == []


# ---------------------------------------------------------------------------
# перечисление
# ---------------------------------------------------------------------------


def test_section_links_are_deduplicated():
    adapter = adapter_for({"https://amd.online/ongoingi/": SECTION})
    urls = adapter.discover_ongoing_urls()["first_page_urls"]
    assert len(urls) == len(set(urls)) == 2


def test_sitemap_yields_only_title_pages_without_duplicates():
    adapter = adapter_for({"https://amd.online/news_pages.xml": SITEMAP})
    urls = adapter.discover_title_urls()
    assert urls == [
        "https://amd.online/1413-boevoj-kontinent.html",
        "https://amd.online/1723-vtoroj.html",
    ]


def test_cache_prevents_refetching_in_one_run():
    adapter = adapter_for({TITLE_URL: PAGE})
    adapter.fetch_page(TITLE_URL)
    adapter.fetch_page(TITLE_URL)
    assert len(adapter.calls) == 1


# ---------------------------------------------------------------------------
# разбор
# ---------------------------------------------------------------------------


def test_title_page_is_parsed_completely():
    adapter = adapter_for({TITLE_URL: PAGE})
    fetch = adapter.parse_title(TITLE_URL, adapter.fetch_page(TITLE_URL))
    assert fetch.external_id == "1413"
    assert fetch.raw_score == "9.4"
    assert fetch.vote_count == 16958
    assert fetch.year == 2023
    assert fetch.kind == "ONA"
    payload = fetch.raw_payload
    assert payload["title_ru"] == "Боевой континент 2"
    assert payload["title_original"] == "Douluo Dalu II"
    assert payload["is_ongoing"] is True
    assert payload["genres"] == ["экшен"]
    assert payload["season"] == "Лето 2023"
    assert payload["html_sha256"]
    assert payload["access_method"] == "PUBLIC_HTML"


def test_every_component_keeps_its_own_label():
    adapter = adapter_for({TITLE_URL: PAGE})
    components = adapter.parse_title(TITLE_URL, PAGE).raw_payload["components"]
    assert {k: v["label"] for k, v in components.items()} == {
        "story": "Сюжет", "actors": "Персонажи", "graph": "Рисовка", "sound": "Озвучка",
    }
    assert components["graph"]["raw"] == "9.6"


def test_an_unlabelled_number_is_not_taken_as_a_component():
    page = PAGE.replace('data-area="graph" title="Рисовка"', 'data-area="graph" title="Что-то"')
    adapter = adapter_for({TITLE_URL: page})
    components = adapter.parse_title(TITLE_URL, page).raw_payload["components"]
    assert "graph" not in components, "число без своей подписи в оценку не идёт"


def test_a_page_without_a_rating_is_not_found_not_zero():
    page = PAGE.replace('<div class="multirating-itog-rateval">9.4</div>', "")
    adapter = adapter_for({TITLE_URL: page})
    fetch = adapter.parse_title(TITLE_URL, page)
    assert fetch.found is False
    assert fetch.raw_score is None


def test_a_broken_vote_count_is_unknown_not_guessed():
    page = PAGE.replace("(16958)", "(много)")
    adapter = adapter_for({TITLE_URL: page})
    assert adapter.parse_title(TITLE_URL, page).vote_count is None


def test_dom_drift_stops_the_source():
    adapter = adapter_for({TITLE_URL: "<html><body>совсем другое</body></html>"})
    with pytest.raises(AdapterError) as exc:
        adapter.parse_title(TITLE_URL, "<html><body>совсем другое</body></html>")
    assert exc.value.code == "DOM_DRIFT"
    assert adapter.kill_switch.active is True


# ---------------------------------------------------------------------------
# безопасность
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("code", [403, 429])
def test_refusal_kills_the_source_immediately(code):
    adapter = adapter_for({}, errors={TITLE_URL: code})
    with pytest.raises(AdapterError) as exc:
        adapter.fetch_page(TITLE_URL)
    assert exc.value.code == "SOURCE_REFUSED"
    assert exc.value.hard_circuit is True
    assert adapter.kill_switch.active is True
    assert len(adapter.calls) == 1, "отказ не повторяют"


def test_repeated_5xx_stops_the_source_after_bounded_retries():
    adapter = adapter_for({}, errors={TITLE_URL: 503})
    with pytest.raises(AdapterError) as exc:
        adapter.fetch_page(TITLE_URL)
    assert exc.value.code == "UPSTREAM_5XX"
    assert adapter.kill_switch.active is True
    assert len(adapter.calls) == adapter.max_retries + 1


def test_captcha_page_stops_the_source():
    adapter = adapter_for({TITLE_URL: "<html>Проверка браузера, captcha</html>"})
    with pytest.raises(AdapterError) as exc:
        adapter.fetch_page(TITLE_URL)
    assert exc.value.code == "CAPTCHA_SUSPECTED"
    assert adapter.kill_switch.active is True


def test_kill_switch_blocks_every_later_request():
    adapter = adapter_for({TITLE_URL: PAGE})
    adapter.kill_switch.trip("остановлено вручную")
    with pytest.raises(AdapterError) as exc:
        adapter.fetch_page(TITLE_URL)
    assert exc.value.code == "SOURCE_KILLED"
    assert adapter.calls == []


def test_health_reports_the_kill_switch():
    adapter = adapter_for({})
    adapter.kill_switch = AmdKillSwitch(active=True, reason="HTTP 429")
    assert adapter.health()["state"] == "BLOCKED"


def test_the_adapter_never_sends_credentials():
    source = __import__("pathlib").Path(
        __import__("factory.unified_ratings.adapters.amd_online", fromlist=["x"]).__file__
    ).read_text(encoding="utf-8")
    for forbidden in ("Cookie", "Authorization", "proxy", "captcha_solver"):
        assert forbidden not in source


# ---------------------------------------------------------------------------
# сопоставление
# ---------------------------------------------------------------------------


@pytest.fixture
def index(store, registry) -> TitleIndex:
    registry.upsert_many(
        [
            CanonicalTitle(title_id="nova:a", title_ru="Боевой континент 2",
                           release_year=2023, content_kind="tv"),
            CanonicalTitle(title_id="nova:film", title_ru="Один и тот же",
                           release_year=2020, content_kind="movie"),
            CanonicalTitle(title_id="nova:serial", title_ru="Один и тот же",
                           release_year=2020, content_kind="tv"),
            CanonicalTitle(title_id="nova:dup1", title_ru="Двойник",
                           release_year=2021, content_kind="tv"),
            CanonicalTitle(title_id="nova:dup2", title_ru="Двойник",
                           release_year=2021, content_kind="tv"),
        ]
    )
    return TitleIndex.build(registry)


def fetch_for(adapter, page: str):
    return adapter.parse_title(TITLE_URL, page)


def test_exact_name_year_and_kind_are_accepted(index):
    adapter = adapter_for({TITLE_URL: PAGE})
    fetch = fetch_for(adapter, PAGE)
    decision = match_by_facts(_facts_from_fetch(fetch), index.candidates_for(fetch))
    assert decision.status is MatchStatus.REVIEWED
    assert decision.external_id == "nova:a"


def test_a_year_apart_is_not_accepted(index):
    page = PAGE.replace("/god/2023/", "/god/2015/").replace(">2023<", ">2015<")
    adapter = adapter_for({TITLE_URL: page})
    fetch = fetch_for(adapter, page)
    decision = match_by_facts(_facts_from_fetch(fetch), index.candidates_for(fetch))
    assert decision.status is MatchStatus.PENDING


def test_two_identical_candidates_go_to_review(index):
    page = PAGE.replace("Боевой континент 2", "Двойник").replace("/god/2023/", "/god/2021/")
    page = page.replace(">2023<", ">2021<")
    adapter = adapter_for({TITLE_URL: page})
    fetch = fetch_for(adapter, page)
    decision = match_by_facts(_facts_from_fetch(fetch), index.candidates_for(fetch))
    assert decision.status is MatchStatus.PENDING
    assert decision.reasons[0].value == "MULTIPLE_EQUAL_CANDIDATES"


def test_a_similar_name_alone_never_matches(index):
    page = PAGE.replace("Боевой континент 2", "Боевой континент 3")
    adapter = adapter_for({TITLE_URL: page})
    fetch = fetch_for(adapter, page)
    decision = match_by_facts(_facts_from_fetch(fetch), index.candidates_for(fetch))
    assert decision.status is MatchStatus.REJECTED


def test_a_film_is_not_matched_to_a_series(index, store):
    """Тип AMD учитывается: MOVIE против нашего tv — расхождение."""
    page = PAGE.replace("Боевой континент 2", "Один и тот же")
    page = page.replace("/god/2023/", "/god/2020/").replace(">2023<", ">2020<")
    page = page.replace('/tip/ona/">ONA', '/tip/film/">Фильм')
    adapter = adapter_for({TITLE_URL: page})
    fetch = fetch_for(adapter, page)
    from factory.unified_ratings.matching import TitleFacts

    theirs = TitleFacts(
        title_id=fetch.external_id, title_ru="Один и тот же", year=2020, kind="movie"
    )
    decision = match_by_facts(theirs, index.candidates_for(fetch))
    assert decision.status is MatchStatus.REVIEWED
    assert decision.external_id == "nova:film", "фильм связан с фильмом, не с сериалом"


# ---------------------------------------------------------------------------
# запись
# ---------------------------------------------------------------------------


def test_import_stores_score_votes_dimensions_and_provenance(store, index):
    adapter = adapter_for({TITLE_URL: PAGE})
    ingestor = AmdIngestor(store, adapter, dry_run=False)
    counters = ingestor.run([TITLE_URL], index=index)
    assert counters.exact_matches == 1
    assert counters.inserted == 1

    row = store.query_one("SELECT * FROM unified_external_current WHERE source_key='amd_online'")
    assert row["raw_score"] == "9.4"
    assert row["normalized_score"] == "9.4"
    assert row["vote_count"] == 16958
    assert row["validation_state"] == "OK"

    dims = store.query("SELECT * FROM unified_source_dimensions WHERE source_key='amd_online'")
    assert len(dims) == 4
    assert {d["dimension"] for d in dims} == {"story", "actors", "graph", "sound"}

    snapshot = store.query_one(
        "SELECT provenance_json FROM unified_external_snapshots WHERE source_key='amd_online'"
    )
    provenance = json.loads(snapshot["provenance_json"])
    assert provenance["access_label"] == "AMD_ONLINE_PUBLIC_HTML"
    assert provenance["html_sha256"]
    assert provenance["provenance_url"] == TITLE_URL


def test_reimport_of_unchanged_page_adds_no_duplicate(store, index):
    adapter = adapter_for({TITLE_URL: PAGE})
    ingestor = AmdIngestor(store, adapter, dry_run=False)
    ingestor.run([TITLE_URL], index=index)
    before = store.count("unified_external_snapshots")
    counters = ingestor.run([TITLE_URL], index=index)
    assert counters.unchanged == 1
    assert counters.inserted == 0
    assert store.count("unified_external_snapshots") == before


def test_a_changed_rating_creates_a_new_version(store, index):
    adapter = adapter_for({TITLE_URL: PAGE})
    AmdIngestor(store, adapter, dry_run=False).run([TITLE_URL], index=index)
    changed = PAGE.replace(">9.4</div>\n<div class=\"multirating-itog-votes\"", ">9.8</div>\n<div class=\"multirating-itog-votes\"")
    adapter2 = adapter_for({TITLE_URL: changed})
    counters = AmdIngestor(store, adapter2, dry_run=False).run([TITLE_URL], index=index)
    assert counters.updated == 1
    assert store.count("unified_external_snapshots") == 2


def test_dry_run_writes_nothing(store, index):
    adapter = adapter_for({TITLE_URL: PAGE})
    AmdIngestor(store, adapter, dry_run=True).run([TITLE_URL], index=index)
    assert store.count("unified_external_current") == 0
    assert store.count("unified_source_dimensions") == 0


def test_dimensions_do_not_enter_the_composite(store, index, seeded):
    """Оценка рисовки — не оценка произведения."""
    from factory.unified_ratings.composite import compute

    adapter = adapter_for({TITLE_URL: PAGE})
    AmdIngestor(store, adapter, dry_run=False).run([TITLE_URL], index=index)
    result = compute(store, title_id="nova:a")
    assert result.state == "SINGLE_SOURCE_ONLY", "один источник сводной оценкой не является"
    assert {c.source_key for c in result.sources_used} == {"amd_online"}


def test_a_dropped_connection_is_retried_then_treated_as_refusal():
    """RemoteDisconnected — OSError, а не URLError: ловить надо обе ветки."""
    import http.client

    calls = {"n": 0}

    def _open(req, timeout):  # noqa: ARG001
        calls["n"] += 1
        raise http.client.RemoteDisconnected("closed")

    adapter = AmdOnlineAdapter(opener=_open, sleeper=lambda _s: None, min_interval=0, jitter=0)
    with pytest.raises(AdapterError) as exc:
        adapter.fetch_page(TITLE_URL)
    assert exc.value.code == "CONNECTION_REFUSED"
    assert exc.value.hard_circuit is True
    assert calls["n"] == adapter.max_retries + 1, "повторы ограничены"
    assert adapter.kill_switch.active is True
    assert adapter.disconnects >= 1
