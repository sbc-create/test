"""REQ-LORDS-ENRICHMENT: обогащение добавляет и никогда не отнимает.

Списочный ответ CDNVideoHub не содержит того, из чего состоит страница фильма:
описания, страны, настоящих жанров, хронометража, съёмочной группы, сезонов.
Всё это отдаёт detail — по одному запросу на запись, то есть четыре тысячи
восемьсот запросов на пересборку, если делать это в лоб.

Отсюда проверяются два свойства. Бюджет: за прогон уходит ограниченное число
запросов, остальное берётся из кэша и переживает пересборку. И неотнимание:
пустой ответ не затирает заполненное поле, отказ источника оставляет запись
прежней, а `playback` не трогается вовсе — плеер уже однажды исчез со всех
страниц из-за обновления каталога, и повторять это через обогащение нельзя.
"""

from __future__ import annotations

from pathlib import Path

from factory.lords import detail_enrichment as de


class FakeContract:
    def url(self, name, **kwargs):
        assert name == "title_detail"
        return f"https://example.invalid/titles/{kwargs['id']}"


class FakeFetcher:
    def __init__(self, responses, fail_for=()):
        self.responses = responses
        self.fail_for = set(fail_for)
        self.calls = []

    def get_json(self, url):
        external_id = url.rsplit("/", 1)[-1]
        self.calls.append(external_id)
        if external_id in self.fail_for:
            raise RuntimeError("источник недоступен")
        return dict(self.responses[external_id])


def item(external_id, **over):
    base = {
        "external_id": external_id, "name": f"Тайтл {external_id}", "type": "movie",
        "is_series": False, "year": 2020, "poster_url": None, "tags": [],
        "kinopoisk_rating": None, "imdb_rating": None, "external_ids": {},
        "playback": {"aggregator": "kp", "title_id": "777"},
        "created_at": None, "updated_at": None,
    }
    base.update(over)
    return base


DETAIL = {
    "description": "Настоящее описание из источника.",
    "original_name": "Original", "countries": ["Великобритания"],
    "genres": ["драма"], "duration": 43, "premiere_date": "2002-05-13",
    "crew": [{"role": "actor", "person_name": "Питер Фёрт"}],
    "seasons_count": 10,
}


class TestNothingIsLost:
    def test_playback_is_never_touched(self):
        """Плеер уже исчезал со всех страниц. Через обогащение — не должен."""
        src = item("a")
        merged = de.merge_detail(src, {**DETAIL, "playback": None})
        assert merged["playback"] == src["playback"]

    def test_empty_detail_field_does_not_erase_a_filled_one(self):
        src = item("a", description="Было описание", countries=["Франция"])
        merged = de.merge_detail(src, {"description": "", "countries": []})
        assert merged["description"] == "Было описание"
        assert merged["countries"] == ["Франция"]

    def test_detail_fills_what_the_list_did_not_have(self):
        merged = de.merge_detail(item("a"), DETAIL)
        assert merged["description"] == "Настоящее описание из источника."
        assert merged["countries"] == ["Великобритания"]
        assert merged["duration"] == 43

    def test_a_source_failure_leaves_the_record_as_it_was(self, tmp_path: Path):
        items = [item("a", description="Прежнее описание")]
        cache = de.DetailCache(tmp_path)
        out, report = de.enrich_items(
            items, fetcher=FakeFetcher({}, fail_for=["a"]), contract=FakeContract(),
            cache=cache, order=["a"])
        assert report.failed == 1
        assert out[0]["description"] == "Прежнее описание"
        assert out[0]["playback"] == items[0]["playback"]


class TestTheBudgetIsRespected:
    def test_no_more_network_calls_than_the_budget(self, tmp_path: Path):
        items = [item(str(i)) for i in range(20)]
        fetcher = FakeFetcher({str(i): DETAIL for i in range(20)})
        out, report = de.enrich_items(
            items, fetcher=fetcher, contract=FakeContract(),
            cache=de.DetailCache(tmp_path), budget=5)
        assert len(fetcher.calls) == 5, f"ушло {len(fetcher.calls)} запросов вместо пяти"
        assert report.fetched == 5

    def test_a_second_run_uses_the_cache_and_spends_nothing(self, tmp_path: Path):
        items = [item(str(i)) for i in range(5)]
        cache = de.DetailCache(tmp_path)
        responses = {str(i): DETAIL for i in range(5)}
        de.enrich_items(items, fetcher=FakeFetcher(responses), contract=FakeContract(),
                        cache=cache, budget=5)
        second = FakeFetcher(responses)
        out, report = de.enrich_items(items, fetcher=second, contract=FakeContract(),
                                      cache=cache, budget=5)
        assert second.calls == [], "повторный прогон снова пошёл в сеть"
        assert report.from_cache == 5
        assert out[0]["description"] == DETAIL["description"]

    def test_coverage_grows_between_runs(self, tmp_path: Path):
        """Бюджет не мешает покрытию: оно набирается прогонами, а не заново."""
        items = [item(str(i)) for i in range(10)]
        cache = de.DetailCache(tmp_path)
        responses = {str(i): DETAIL for i in range(10)}
        first, _ = de.enrich_items(items, fetcher=FakeFetcher(responses),
                                   contract=FakeContract(), cache=cache, budget=4)
        covered_first = sum(1 for i in first if i.get("description"))
        second, _ = de.enrich_items(first, fetcher=FakeFetcher(responses),
                                    contract=FakeContract(), cache=cache, budget=4)
        covered_second = sum(1 for i in second if i.get("description"))
        assert covered_first == 4
        assert covered_second > covered_first, "покрытие не выросло на втором прогоне"


class TestFailuresDoNotEatTheBudget:
    def test_a_failed_record_is_not_retried_immediately(self, tmp_path: Path):
        items = [item("a"), item("b")]
        cache = de.DetailCache(tmp_path)
        de.enrich_items(items, fetcher=FakeFetcher({"b": DETAIL}, fail_for=["a"]),
                        contract=FakeContract(), cache=cache, budget=5)
        again = FakeFetcher({"b": DETAIL}, fail_for=["a"])
        _, report = de.enrich_items(items, fetcher=again, contract=FakeContract(),
                                    cache=cache, budget=5)
        assert "a" not in again.calls, (
            "отказавшая запись перезапрашивается каждый прогон и съедает бюджет"
        )
        assert report.skipped_negative == 1

    def test_a_negative_entry_expires(self, tmp_path: Path):
        clock = {"t": 1000.0}
        cache = de.DetailCache(tmp_path, negative_ttl=100, now=lambda: clock["t"])
        cache.put("a", None, error="boom")
        assert cache.get("a")[0] == "negative"
        clock["t"] += 200
        assert cache.get("a")[0] == "miss", "отказ запомнен навсегда"
