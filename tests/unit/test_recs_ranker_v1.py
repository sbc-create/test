"""Обязательные проверки рекомендаций (REC-001 … REC-016).

Витрина обещает посетителю просмотр. Всё остальное — свежесть, оценка,
упоминание у соседа — лишь порядок внутри того, что действительно играет.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from factory.recs import events as ev
from factory.recs import shelves as sh
from factory.recs.editorial import Editorial
from factory.recs.model import ItemFeatures, merge_duplicates
from factory.recs.ranker import ALGORITHM_VERSION, rank, rating_confidence, score_item
from factory.recs.store import CarouselStore, ShelfRejected

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)


def item(cid, **kw):
    base = {
        "content_id": cid, "title": f"Тайтл {cid}", "content_type": "movie",
        "poster": f"https://poster/{cid}.webp", "playback_state": True,
        "added_at": NOW - timedelta(days=5), "genres": ("драма",),
    }
    base.update(kw)
    return ItemFeatures(**base)


def playable_pool(n=14, **kw):
    return [item(f"c{i}", genres=(f"жанр{i % 5}",), **kw) for i in range(n)]


class TestREC001FreshWithoutPlaybackIsExcluded:
    def test_fresh_but_unplayable_never_reaches_the_carousel(self):
        pool = playable_pool(12)
        pool.append(item("новьё", added_at=NOW, playback_state=False))
        ranked = rank(pool, now=NOW, limit=18)
        assert "новьё" not in [s.item.content_id for s in ranked]

    def test_unchecked_playback_is_also_kept_out_of_the_shop_window(self):
        # Карусель обещает просмотр. «Не проверяли» — не обещание.
        ranked = rank([item("x", playback_state=None)], now=NOW)
        assert ranked == []


class TestREC002ProviderFailureKeepsLastKnownGood:
    def test_a_failed_rebuild_leaves_the_working_shelf_in_place(self):
        store = CarouselStore()
        good = [type("S", (), {"item": i, "score": 1.0})() for i in playable_pool(12)]
        store.publish("d", sh.MONTHLY_POPULAR, good,
                      algorithm_version=ALGORITHM_VERSION, now=NOW)
        with pytest.raises(ShelfRejected):
            store.publish("d", sh.MONTHLY_POPULAR, good[:3],
                          algorithm_version=ALGORITHM_VERSION, now=NOW)
        assert len(store.serve("d", sh.MONTHLY_POPULAR).items) == 12
        assert store.rejections


class TestREC003DuplicateSlugResolvesToPlayableStableId:
    def test_the_playable_copy_wins_and_the_id_stays_one(self):
        a = item("stable", playback_state=None, poster=None)
        b = item("stable", playback_state=True)
        merged = merge_duplicates([a, b])
        assert len(merged) == 1
        assert merged[0].playback_state is True
        assert merged[0].poster


class TestREC004RatingWithoutVotesHasLowConfidence:
    def test_a_lone_ten_loses_to_a_confirmed_eight(self):
        loud = item("loud", kp_rating=10.0, kp_votes=None)
        solid = item("solid", kp_rating=7.9, kp_votes=50000)
        assert rating_confidence(solid) > rating_confidence(loud)


class TestREC005MissingRatingIsHiddenNotZero:
    def test_absent_rating_is_not_a_zero_signal(self):
        assert rating_confidence(item("no")) is None

    def test_a_record_without_ratings_is_not_pushed_to_the_bottom(self):
        # Вес отсутствующего сигнала перераспределяется: незнание не наказание.
        rated = score_item(item("r", kp_rating=6.0, kp_votes=10), NOW)
        unrated = score_item(item("u"), NOW)
        assert unrated.score > 0
        assert unrated.signals["rating_confidence"] is None
        assert abs(unrated.score - rated.score) < 0.5


class TestREC006GenreDiversityIsEnforced:
    def test_no_three_identical_genres_in_a_row(self):
        pool = [item(f"g{i}", genres=("боевик",)) for i in range(6)]
        pool += [item(f"o{i}", genres=("комедия",)) for i in range(6)]
        ranked = rank(pool, now=NOW, limit=12)
        top = [s.item.genres[0] for s in ranked]
        for i in range(len(top) - 2):
            assert not (top[i] == top[i + 1] == top[i + 2]), top

    def test_one_item_per_franchise(self):
        pool = [item(f"f{i}", franchise_id="сага") for i in range(5)]
        pool += playable_pool(10)
        ranked = rank(pool, now=NOW, limit=12)
        saga = [s for s in ranked if s.item.franchise_id == "сага"]
        assert len(saga) <= 1


class TestREC007ExpiredEditorialPinIsRemoved:
    def test_a_pin_stops_working_when_it_expires(self):
        pool = playable_pool(12)
        pinned = item("гвоздь", added_at=NOW - timedelta(days=900))
        pool.append(pinned)
        fresh = Editorial.from_documents([{
            "action": "pin", "content_id": "гвоздь", "position": 1,
            "expires_at": (NOW + timedelta(days=1)).isoformat(),
        }])
        stale = Editorial.from_documents([{
            "action": "pin", "content_id": "гвоздь", "position": 1,
            "expires_at": (NOW - timedelta(days=1)).isoformat(),
        }])
        assert rank(pool, now=NOW, limit=12, editorial=fresh)[0].item.content_id == "гвоздь"
        assert rank(pool, now=NOW, limit=12, editorial=stale)[0].item.content_id != "гвоздь"


class TestREC008ReferenceMentionCannotOverrideMissingPlayback:
    def test_being_on_a_neighbours_shop_window_does_not_grant_a_place(self):
        loud = item("сосед", playback_state=False, reference_mentions=(
            {"seen_at": NOW.isoformat(), "position": 1},))
        assert rank([loud] + playable_pool(11), now=NOW) != []
        assert "сосед" not in [s.item.content_id for s in rank([loud] + playable_pool(11), now=NOW)]

    def test_an_editorial_pin_cannot_resurrect_an_unplayable_record(self):
        pool = playable_pool(12) + [item("мертвец", playback_state=False)]
        pinned = Editorial.from_documents([
            {"action": "pin", "content_id": "мертвец", "position": 1}])
        ranked = rank(pool, now=NOW, limit=12, editorial=pinned)
        assert "мертвец" not in [s.item.content_id for s in ranked]
        assert any(r["action"] == "pin_skipped" for r in pinned.audit_log)


class TestREC009RankingIsDeterministic:
    def test_the_same_input_and_version_give_the_same_order(self):
        pool = playable_pool(16)
        first = [s.item.content_id for s in rank(list(pool), now=NOW, limit=12)]
        second = [s.item.content_id for s in rank(list(reversed(pool)), now=NOW, limit=12)]
        assert first == second

    def test_ties_are_broken_by_a_stable_identifier(self):
        pool = [item("бета"), item("альфа")]
        pool = [p.with_(genres=("одно",)) for p in pool]
        order = [s.item.content_id for s in rank(pool, now=NOW, limit=2)]
        assert order == sorted(order)


class TestREC010NewPlayableItemEntersCandidatesQuickly:
    def test_an_item_added_minutes_ago_is_already_a_candidate(self):
        pool = playable_pool(12)
        pool.append(item("свежак", added_at=NOW - timedelta(minutes=14)))
        ranked = rank(pool, now=NOW, limit=18)
        assert "свежак" in [s.item.content_id for s in ranked]

    def test_it_also_reaches_the_latest_added_shelf(self):
        pool = playable_pool(12)
        pool.append(item("свежак", added_at=NOW - timedelta(minutes=10)))
        shelf = sh.build_shelf(sh.LATEST_ADDED, pool, now=NOW, limit=12)
        assert shelf.items[0].item.content_id == "свежак"


class TestREC011RefreshCannotExposeAPartialCarousel:
    def test_a_short_shelf_is_refused(self):
        store = CarouselStore()
        few = [type("S", (), {"item": i, "score": 1.0})() for i in playable_pool(4)]
        with pytest.raises(ShelfRejected):
            store.publish("d", "c", few, algorithm_version=ALGORITHM_VERSION, now=NOW)
        assert store.serve("d", "c") is None

    def test_a_shelf_with_an_unplayable_card_is_refused(self):
        store = CarouselStore()
        pool = playable_pool(11) + [item("плохой", playback_state=False)]
        wrapped = [type("S", (), {"item": i, "score": 1.0})() for i in pool]
        with pytest.raises(ShelfRejected):
            store.publish("d", "c", wrapped, algorithm_version=ALGORITHM_VERSION, now=NOW)


class TestREC012ProviderOutageServesLastValidCarousel:
    def test_the_visitor_keeps_seeing_yesterdays_working_shelf(self):
        store = CarouselStore()
        good = [type("S", (), {"item": i, "score": 1.0})() for i in playable_pool(12)]
        store.publish("d", "c", good, algorithm_version=ALGORITHM_VERSION, now=NOW)
        with pytest.raises(ShelfRejected):
            store.publish("d", "c", [], algorithm_version=ALGORITHM_VERSION, now=NOW)
        served = store.serve("d", "c")
        assert served is not None and len(served.items) == 12


class TestREC013DuplicateSignalsMergeIntoOneItem:
    def test_counters_add_up_instead_of_splitting_the_record(self):
        a = item("один", events_30d=100)
        b = item("один", events_30d=50)
        merged = merge_duplicates([a, b])
        assert len(merged) == 1
        assert merged[0].events_30d == 150

    def test_the_carousel_never_shows_the_same_id_twice(self):
        pool = [item("повтор"), item("повтор")] + playable_pool(11)
        ids = [s.item.content_id for s in rank(pool, now=NOW, limit=13)]
        assert len(ids) == len(set(ids))


class TestREC014DomainProfileExcludesForeignDirection:
    def test_a_dorama_stays_out_of_an_anime_domain(self):
        pool = playable_pool(11) + [item("дорама", direction="dorama")]
        ranked = rank(pool, now=NOW, limit=12, profile_directions=("anime",))
        assert "дорама" not in [s.item.content_id for s in ranked]

    def test_a_record_not_allowed_on_this_domain_is_excluded(self):
        pool = playable_pool(11) + [item("чужой", domain_eligibility=("other.tld",))]
        ranked = rank(pool, now=NOW, limit=12, domain="ours.tld")
        assert "чужой" not in [s.item.content_id for s in ranked]


class TestREC015ImpressionStoresEverythingNeeded:
    def test_every_required_field_is_recorded(self):
        ranked = rank(playable_pool(12), now=NOW, limit=6)
        impressions = ev.build_impressions(
            sh.MONTHLY_POPULAR, "ours.tld", ranked, request_id="req-1",
            session_id="ses-1", algorithm_version=ALGORITHM_VERSION, now=NOW)
        assert len(impressions) == 6
        for field in ev.REQUIRED_IMPRESSION_FIELDS:
            assert field in impressions[0].as_dict()
        assert [i.position for i in impressions] == [1, 2, 3, 4, 5, 6]


class TestREC016PlayAttributesToTheRightRecommendation:
    def test_a_play_is_tied_to_the_shelf_and_position_that_produced_it(self):
        log = ev.EventLog()
        ranked = rank(playable_pool(12), now=NOW, limit=6)
        log.record_impressions(ev.build_impressions(
            sh.MONTHLY_POPULAR, "ours.tld", ranked, request_id="req-9",
            session_id="ses-9", algorithm_version=ALGORITHM_VERSION, now=NOW))
        target = ranked[2].item.content_id
        event = log.record(ev.PLAY_START, request_id="req-9", session_id="ses-9",
                           domain="ours.tld", content_id=target, now=NOW)
        assert event.shelf_id == sh.MONTHLY_POPULAR
        assert event.position == 3
        assert event.algorithm_version == ALGORITHM_VERSION

    def test_success_is_measured_by_play_not_by_click(self):
        assert ev.SUCCESS_EVENTS == (ev.PLAY_START, ev.PLAY_30S)
        assert ev.CARD_CLICK not in ev.SUCCESS_EVENTS

    def test_an_event_without_a_matching_impression_is_not_misattributed(self):
        log = ev.EventLog()
        event = log.record(ev.PLAY_START, request_id="нет", session_id="s",
                           domain="d", content_id="c", now=NOW)
        assert event.shelf_id is None and event.position is None
