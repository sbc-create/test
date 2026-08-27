"""Плеер стоит там, где действительно есть что играть.

Заказчик открыл несколько тайтлов подряд и не увидел видео ни на одном. Причина
оказалась не в разметке: пара «агрегатор + идентификатор» есть у всех записей
каталога, в том числе у тех, для которых поток ещё не завели, — и отбор
«ведущих» записей, проверявший наличие этой пары, пропускал всех. На главную
выходили самые свежие поступления, а у них потока чаще всего нет.

Главное правило этих тестов: подтверждённое «пусто» имеет последствия,
неизвестность — нет. Ни один тайтл, который играл, не должен лишиться плеера
из-за того, что проверка не состоялась.
"""
from __future__ import annotations

import io

import pytest

from factory.lords import live_catalog as lc
from factory.lords import playability, render


class _Response(io.BytesIO):
    def __init__(self, status: int, body: bytes = b""):
        super().__init__(body)
        self.status = status

    def getcode(self):
        return self.status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def _opener(status, body=b"x"):
    return lambda request, timeout=None: _Response(status, body)


PB = {"aggregator": "kp", "title_id": "404915"}


class TestProbeReadsTheSource:
    def test_a_playlist_with_content_means_playable(self):
        assert playability.probe_one(PB, "1", opener=_opener(200, b"[]")) is True

    def test_an_empty_answer_means_nothing_to_play(self):
        assert playability.probe_one(PB, "1", opener=_opener(204)) is False

    def test_a_200_with_no_body_is_not_playable(self):
        assert playability.probe_one(PB, "1", opener=_opener(200, b"")) is False

    def test_a_network_failure_is_unknown_not_silent(self):
        # Именно здесь ломался бы контракт: сетевая ошибка не смеет снимать
        # плеер с записи, которая играет.
        def boom(request, timeout=None):
            raise OSError("сеть недоступна")

        assert playability.probe_one(PB, "1", opener=boom) is None

    def test_an_unexpected_status_is_unknown(self):
        assert playability.probe_one(PB, "1", opener=_opener(500)) is None

    @pytest.mark.parametrize("broken", [{}, {"aggregator": "kp"}, {"title_id": "1"}])
    def test_an_incomplete_contract_is_unknown(self, broken):
        assert playability.probe_one(broken, "1", opener=_opener(204)) is None

    def test_without_a_publisher_nothing_is_declared_silent(self):
        assert playability.probe_one(PB, "", opener=_opener(204)) is None


class TestCacheRemembersWithDifferentPatience:
    def test_a_confirmation_is_remembered_for_a_long_time(self):
        cache = playability.PlayabilityCache()
        now = 1000.0
        cache.put("kp:1", True, now=now)
        assert cache.get("kp:1", now=now + playability.OK_TTL_SECONDS - 1) is True

    def test_a_refusal_expires_quickly(self):
        # У свежего поступления поток появляется в ближайшие часы: держать
        # запись «немой» сутки значило бы прятать её дольше, чем нужно.
        cache = playability.PlayabilityCache()
        now = 1000.0
        cache.put("kp:2", False, now=now)
        assert cache.get("kp:2", now=now + playability.SILENT_TTL_SECONDS - 1) is False
        assert cache.get("kp:2", now=now + playability.SILENT_TTL_SECONDS + 1) is None

    def test_an_unknown_key_is_unknown(self):
        assert playability.PlayabilityCache().get("kp:нет") is None

    def test_the_cache_survives_a_round_trip(self, tmp_path):
        path = tmp_path / "playability.json"
        cache = playability.PlayabilityCache(path)
        cache.put("kp:3", True)
        cache.save()
        assert playability.PlayabilityCache(path).get("kp:3") is True

    def test_a_corrupt_cache_file_does_not_break_the_build(self, tmp_path):
        path = tmp_path / "playability.json"
        path.write_text("{не json", encoding="utf-8")
        assert len(playability.PlayabilityCache(path)) == 0


class TestAnnotateSpendsItsBudgetOnTheShopWindow:
    def _items(self, n):
        return [
            {"external_id": f"e{i}", "name": f"Запись {i}",
             "created_at": f"2026-08-{(n - i) % 28 + 1:02d}T00:00:00Z",
             "playback": {"aggregator": "kp", "title_id": str(i)}}
            for i in range(n)
        ]

    def test_the_newest_arrivals_are_checked_first(self):
        # Записи без потока сосредоточены среди свежих поступлений, и именно
        # они стоят на первом экране.
        items = self._items(10)
        seen = []

        def probe(playback, publisher, referer=""):
            seen.append(playback["title_id"])
            return True

        playability.annotate(items, "1", budget=3, probe=probe, workers=1)
        newest = [i["playback"]["title_id"] for i in
                  sorted(items, key=lambda i: i["created_at"], reverse=True)[:3]]
        assert seen == newest

    def test_records_beyond_the_budget_stay_unknown_not_silent(self):
        items = self._items(10)
        playability.annotate(items, "1", budget=2,
                             probe=lambda *a, **k: True, workers=1)
        assert sum(1 for i in items if i["playable"] is True) == 2
        assert sum(1 for i in items if i["playable"] is None) == 8

    def test_without_a_publisher_every_record_stays_unknown(self):
        items = self._items(4)
        report = playability.annotate(items, None, budget=10)
        assert all(i["playable"] is None for i in items)
        assert report["unknown"] == 4

    def test_a_cached_answer_is_not_requested_again(self):
        items = self._items(3)
        cache = playability.PlayabilityCache()
        for item in items:
            cache.put(playability.cache_key(item["playback"]), True)
        calls = []
        report = playability.annotate(
            items, "1", budget=10, cache=cache,
            probe=lambda *a, **k: calls.append(1), workers=1)
        assert calls == []
        assert report["cached"] == 3


class TestTheShopWindowLeadsWithWhatPlays:
    def _title(self, name, playable):
        return lc.title_from_item({
            "external_id": name, "name": name, "type": "movie", "is_series": False,
            "year": 2020, "tags": [], "external_ids": {}, "created_at": None,
            "updated_at": None, "playable": playable,
            "playback": {"aggregator": "kp", "title_id": "1"},
        })

    def test_a_confirmed_silent_record_does_not_lead(self):
        assert render._is_watchable(self._title("молчит", False)) is False

    def test_an_unchecked_record_still_leads(self):
        # Неизвестность не наказывается: иначе первая же сетевая ошибка
        # опустошила бы главную.
        assert render._is_watchable(self._title("неизвестно", None)) is True

    def test_a_confirmed_playable_record_leads(self):
        assert render._is_watchable(self._title("играет", True)) is True

    def test_a_record_without_any_contract_does_not_lead(self):
        title = lc.title_from_item({
            "external_id": "x", "name": "x", "type": "movie", "is_series": False,
            "year": 2020, "tags": [], "external_ids": {}, "playback": None,
            "created_at": None, "updated_at": None,
        })
        assert render._is_watchable(title) is False


class TestTheFrozenPlayerNeverDisappearsByAccident:
    def _ctx(self):
        return {"publisher_id": "10238"}

    def test_a_confirmed_silent_title_gets_no_dead_frame(self):
        title = TestTheShopWindowLeadsWithWhatPlays()._title("молчит", False)
        html = render._player_block(self._ctx(), title, "Молчит")
        assert "<video-player" not in html

    @pytest.mark.parametrize("playable", [True, None])
    def test_anything_not_confirmed_silent_keeps_its_player(self, playable):
        # Условие обязано проверять именно False. Если оно когда-нибудь станет
        # проверять ложность, `None` начнёт снимать плееры — и каталог
        # замолчит целиком при первом же сбое проверки.
        title = TestTheShopWindowLeadsWithWhatPlays()._title("играет", playable)
        html = render._player_block(self._ctx(), title, "Играет")
        assert "<video-player" in html
