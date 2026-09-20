"""Ratings isolation — comments must not mutate votes / aggregates."""

from __future__ import annotations

import uuid

from factory.community.comments.flags import comments_dark_flags
from factory.community.comments.service import CommentsService
from factory.community.comments_foundation import comments_cannot_mutate_rating
from factory.community.identity_v1 import mint_identity_id
from factory.community.rollout import load_flags
from factory.community.service import CommunityVotesService
from factory.community.store import CommunityStore


def test_comments_do_not_mutate_votes(tmp_path):
    store = CommunityStore(tmp_path / "iso.sqlite")
    votes = CommunityVotesService(store)
    comments = CommentsService(store)
    subject = f"nova:00000000-iso-{uuid.uuid4().hex[:8]}"
    actor = f"canary-iso-{uuid.uuid4().hex[:8]}"
    votes.put_vote(
        idempotency_key=f"k-{uuid.uuid4().hex}",
        rating_space_id="yummy",
        subject_id=subject,
        actor_id=actor,
        score=8,
    )
    before = store.get_aggregate(rating_space_id="yummy", subject_id=subject)
    probe = comments.vote_aggregate_unchanged_probe(
        rating_space_id="yummy", subject_id=subject
    )
    assert probe["vote_sum"] == before["vote_sum"]
    assert probe["vote_count"] == before["vote_count"]

    comments.create(
        site_space="yummy",
        title_id=subject,
        identity_id=mint_identity_id(),
        body="Комментарий не должен менять агрегат оценок.",
        bypass_write_flag_for_tests=True,
    )
    after = store.get_aggregate(rating_space_id="yummy", subject_id=subject)
    assert after["vote_sum"] == before["vote_sum"]
    assert after["vote_count"] == before["vote_count"]
    assert after["aggregate_version"] == before["aggregate_version"]

    vote = store.get_vote(
        rating_space_id="yummy", subject_id=subject, actor_id=actor
    )
    assert vote is not None and vote["score"] == 8
    store.close()


def test_ratings_rollout_percent_untouched():
    # Must not be altered by comments work — stage ceiling remains 1.
    flags = load_flags()
    assert flags.PUBLIC_WRITE_MAX_PERCENT == 1
    assert flags.PUBLIC_WRITE_ROLLOUT_PERCENT <= 1


def test_dark_publication_counters():
    f = comments_dark_flags()
    assert f["PRODUCTION_COMMENTS_INSERTED"] == 0
    assert f["EXTERNAL_COMMENTS_REPUBLISHED"] == 0
    assert f["FAKE_COMMENTS_INSERTED"] == 0
    assert f["COMMENTS_OR_REACTIONS_AFFECT_RATING"] == 0
    inv = comments_cannot_mutate_rating()
    assert inv["comments_affect_rating"] is False
    assert inv["delete_comment_deletes_vote"] is False


def test_spoiler_flag_set(tmp_path):
    store = CommunityStore(tmp_path / "spoiler.sqlite")
    svc = CommentsService(store)
    out = svc.create(
        site_space="yummy",
        title_id="t-spoiler",
        identity_id=mint_identity_id(),
        body="В финале главный герой погибает — спойлер.",
        bypass_write_flag_for_tests=True,
    )
    assert out["comment"]["spoiler"] in (1, True)
    store.close()
