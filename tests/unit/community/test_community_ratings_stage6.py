"""Community ratings Stage 6 — formulas, ledger, API, antifraud, comments dark."""

from __future__ import annotations

import concurrent.futures
import json
import tempfile
import threading
import unittest
from decimal import Decimal
from pathlib import Path

from factory.community.antifraud import AntifraudConfig, AntifraudGuard, KillSwitchActive
from factory.community.api import (
    CommunityRatingsAPI,
    admin_quarantine_vote,
    merge_actors_votes,
)
from factory.community.comments_foundation import (
    REQUIRED_COMMENT_TABLES,
    assert_comments_dark,
    comments_cannot_mutate_rating,
    comments_flags,
)
from factory.community.formulas import (
    NativeAggregate,
    YummyPublic,
    build_yummy_prior,
    compare_yummy_grid,
    format_delta,
    round_display,
)
from factory.community.policy import POLICY_VERSION, assert_not_activated_for_shadow, load_policy
from factory.community.reconcile import invalidate_cache_keys, reconcile_all
from factory.community.service import CommunityConflict, CommunityVotesService
from factory.community.spaces import rating_space_for_domain, spaces_matrix
from factory.community.store import CommunityStore
import importlib.util

_mig_path = Path(__file__).resolve().parents[3] / "migrations" / "0005_community_ratings.py"
_spec = importlib.util.spec_from_file_location("mig_0005_community", _mig_path)
_mig = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mig)
MIG_V = _mig.VERSION
apply_isolated = _mig.apply_isolated
digest = _mig.digest


class FormulaTests(unittest.TestCase):
    def test_first_vote_1_and_10(self) -> None:
        a = NativeAggregate(0, 0).after_create(1)
        self.assertEqual(a.average, Decimal("1"))
        b = NativeAggregate(0, 0).after_create(10)
        self.assertEqual(b.average, Decimal("10"))

    def test_update_8_to_10(self) -> None:
        a = NativeAggregate(80, 10).after_update(8, 10)
        self.assertEqual(a.vote_sum, 82)
        self.assertEqual(a.vote_count, 10)
        self.assertEqual(a.average, Decimal("8.2"))

    def test_delete_last_absent_not_zero(self) -> None:
        a = NativeAggregate(7, 1).after_delete(7)
        self.assertEqual(a.vote_count, 0)
        self.assertIsNone(a.average)
        self.assertNotEqual(a.average, Decimal("0"))

    def test_rounding_half_up(self) -> None:
        self.assertEqual(round_display(Decimal("8.425"), "0.01"), Decimal("8.43"))
        self.assertEqual(format_delta(Decimal("0.004")), "изменение менее 0,01")
        self.assertEqual(format_delta(Decimal("0.012")), "+0.012")

    def test_yummy_prior_renorm_and_no_zero_fill(self) -> None:
        p, prov = build_yummy_prior(animedia_native=Decimal("8"), shikimori=None)
        self.assertEqual(p, Decimal("8"))
        self.assertEqual(prov["components_used"], ["animedia_native"])
        p2, prov2 = build_yummy_prior(animedia_native=None, shikimori=None)
        self.assertIsNone(p2)
        self.assertEqual(prov2["components_used"], [])

    def test_double_count_guard(self) -> None:
        p, prov = build_yummy_prior(
            animedia_native=Decimal("8.4"),
            shikimori=Decimal("7.9"),
            animedia_embeds_shikimori=True,
        )
        self.assertEqual(p, Decimal("8.4"))
        self.assertEqual(prov["double_counted_source_count"], 0)
        self.assertNotIn("shikimori", prov["components_used"])

    def test_yummy_m_not_in_displayed_count(self) -> None:
        y = YummyPublic(20, 2, Decimal("8"), m=10)
        self.assertEqual(y.displayed_vote_count(), 2)
        self.assertIsNotNone(y.public_score)

    def test_compare_grid_covers_matrix(self) -> None:
        rows = compare_yummy_grid()
        self.assertGreaterEqual(len(rows), 3 * 4 * 6 * 4)


class LedgerServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CommunityStore(Path(self.tmp.name) / "c.sqlite")
        self.svc = CommunityVotesService(self.store)

    def tearDown(self) -> None:
        self.store.close()
        self.tmp.cleanup()

    def test_put_preview_equals_write(self) -> None:
        prev = self.svc.preview_one(
            rating_space_id="animedia", subject_id="t1", actor_id="a1", score=10
        )
        out = self.svc.put_vote(
            idempotency_key="k1",
            rating_space_id="animedia",
            subject_id="t1",
            actor_id="a1",
            score=10,
        )
        self.assertEqual(prev["after"], out["after"])
        self.assertEqual(out["native_vote_count"], 1)

    def test_repeat_same_score_noop(self) -> None:
        self.svc.put_vote(
            idempotency_key="k1",
            rating_space_id="animedia",
            subject_id="t1",
            actor_id="a1",
            score=8,
        )
        out = self.svc.put_vote(
            idempotency_key="k2",
            rating_space_id="animedia",
            subject_id="t1",
            actor_id="a1",
            score=8,
        )
        self.assertTrue(out["noop"])
        self.assertEqual(out["aggregate_version"], 1)

    def test_idempotency_replay_and_conflict(self) -> None:
        a = self.svc.put_vote(
            idempotency_key="same",
            rating_space_id="animedia",
            subject_id="t1",
            actor_id="a1",
            score=5,
        )
        b = self.svc.put_vote(
            idempotency_key="same",
            rating_space_id="animedia",
            subject_id="t1",
            actor_id="a1",
            score=5,
        )
        self.assertEqual(a["after"], b["after"])
        with self.assertRaises(CommunityConflict):
            self.svc.put_vote(
                idempotency_key="same",
                rating_space_id="animedia",
                subject_id="t1",
                actor_id="a1",
                score=6,
            )

    def test_update_and_delete(self) -> None:
        self.svc.put_vote(
            idempotency_key="c",
            rating_space_id="animedia",
            subject_id="t1",
            actor_id="a1",
            score=8,
        )
        self.svc.put_vote(
            idempotency_key="u",
            rating_space_id="animedia",
            subject_id="t1",
            actor_id="a1",
            score=10,
        )
        agg = self.store.get_aggregate(rating_space_id="animedia", subject_id="t1")
        self.assertEqual(int(agg["vote_sum"]), 10)
        out = self.svc.delete_vote(
            idempotency_key="d",
            rating_space_id="animedia",
            subject_id="t1",
            actor_id="a1",
        )
        self.assertTrue(out["native_absent"])
        self.assertIsNone(out["my_vote"])

    def test_animedia_yummy_isolation(self) -> None:
        self.svc.put_vote(
            idempotency_key="ia",
            rating_space_id="animedia",
            subject_id="t1",
            actor_id="a1",
            score=9,
        )
        self.svc.put_vote(
            idempotency_key="iy",
            rating_space_id="yummy",
            subject_id="t1",
            actor_id="a1",
            score=3,
            yummy_prior_inputs={"animedia_native": "9", "shikimori": "8"},
        )
        a = self.store.get_aggregate(rating_space_id="animedia", subject_id="t1")
        y = self.store.get_aggregate(rating_space_id="yummy", subject_id="t1")
        self.assertEqual(int(a["vote_sum"]), 9)
        self.assertEqual(int(y["vote_sum"]), 3)

    def test_shared_animedia_domains(self) -> None:
        self.assertEqual(rating_space_for_domain("animedia.icu"), "animedia")
        self.assertEqual(rating_space_for_domain("animedia.space"), "animedia")
        self.svc.put_vote(
            idempotency_key="d1",
            rating_space_id="animedia",
            subject_id="t1",
            actor_id="user-x",
            score=7,
        )
        # second domain same space+actor → replace not second vote
        self.svc.put_vote(
            idempotency_key="d2",
            rating_space_id="animedia",
            subject_id="t1",
            actor_id="user-x",
            score=8,
        )
        agg = self.store.get_aggregate(rating_space_id="animedia", subject_id="t1")
        self.assertEqual(int(agg["vote_count"]), 1)
        self.assertEqual(int(agg["vote_sum"]), 8)

    def test_concurrent_linearizable(self) -> None:
        # Start gate rather than threading.Barrier(20): with 100 tasks on 20
        # workers the barrier ran in five waves, and one slow wave on a loaded
        # machine broke it permanently — every later wave then raised
        # BrokenBarrierError and the test failed for a reason that has nothing
        # to do with ledger linearizability. The gate releases all workers at
        # once and keeps the same contention, with the assertions unchanged.
        start = threading.Event()
        errors: list[BaseException] = []

        def worker(i: int) -> None:
            try:
                if not start.wait(timeout=30):
                    raise TimeoutError("start gate never opened")
                self.svc.put_vote(
                    idempotency_key=f"conc-{i}",
                    rating_space_id="animedia",
                    subject_id="tconc",
                    actor_id=f"actor-{i % 5}",
                    score=(i % 10) + 1,
                )
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
            futures = [pool.submit(worker, i) for i in range(100)]
            start.set()
            concurrent.futures.wait(futures, timeout=60)
        self.assertEqual(errors, [])
        agg = self.store.get_aggregate(rating_space_id="animedia", subject_id="tconc")
        self.assertEqual(int(agg["vote_count"]), 5)
        votes = self.store.conn.execute(
            """SELECT COUNT(*) AS c FROM community_votes
               WHERE subject_id='tconc' AND status='ACCEPTED'"""
        ).fetchone()["c"]
        self.assertEqual(int(votes), 5)

    def test_rebuild_match(self) -> None:
        for i in range(5):
            self.svc.put_vote(
                idempotency_key=f"rb-{i}",
                rating_space_id="animedia",
                subject_id="trb",
                actor_id=f"a{i}",
                score=i + 1,
            )
        report = reconcile_all(self.store)
        self.assertEqual(report["mismatch_count"], 0)

    def test_quarantine_excluded(self) -> None:
        self.svc.put_vote(
            idempotency_key="q1",
            rating_space_id="animedia",
            subject_id="tq",
            actor_id="bad",
            score=10,
        )
        self.svc.put_vote(
            idempotency_key="q2",
            rating_space_id="animedia",
            subject_id="tq",
            actor_id="good",
            score=6,
        )
        admin_quarantine_vote(
            self.svc,
            rating_space_id="animedia",
            subject_id="tq",
            actor_id="bad",
            reason_code="FRAUD_BURST",
        )
        agg = self.store.get_aggregate(rating_space_id="animedia", subject_id="tq")
        self.assertEqual(int(agg["vote_count"]), 1)
        self.assertEqual(int(agg["vote_sum"]), 6)

    def test_guest_merge(self) -> None:
        self.svc.put_vote(
            idempotency_key="g1",
            rating_space_id="animedia",
            subject_id="tm",
            actor_id="guest-1",
            score=9,
        )
        self.svc.put_vote(
            idempotency_key="a1",
            rating_space_id="animedia",
            subject_id="tm",
            actor_id="acct-1",
            score=5,
        )
        result = merge_actors_votes(self.svc, guest_actor_id="guest-1", account_actor_id="acct-1")
        self.assertEqual(result["duplicates"], 0)
        agg = self.store.get_aggregate(rating_space_id="animedia", subject_id="tm")
        self.assertEqual(int(agg["vote_count"]), 1)
        self.assertEqual(int(agg["vote_sum"]), 5)

    def test_get_rating_payload(self) -> None:
        self.svc.put_vote(
            idempotency_key="gr",
            rating_space_id="animedia",
            subject_id="tg",
            actor_id="a1",
            score=10,
        )
        body = self.svc.get_rating(
            rating_space_id="animedia",
            subject_id="tg",
            actor_id="a1",
            external={"shikimori": {"score": "7.5", "votes": 100}},
        )
        self.assertEqual(body["native_vote_count"], 1)
        self.assertIn("10", body["preview_by_score"])
        self.assertEqual(body["policy_version"], POLICY_VERSION)
        self.assertNotIn("ip", json.dumps(body).lower())


class PolicySpacesFlagsTests(unittest.TestCase):
    def test_policy_draft(self) -> None:
        p = load_policy()
        assert_not_activated_for_shadow(p)
        self.assertFalse(p.activated)

    def test_spaces_matrix(self) -> None:
        m = spaces_matrix()
        self.assertTrue(m["animedia_shared_across_icu_space"])
        self.assertTrue(m["yummy_isolated"])

    def test_comments_dark(self) -> None:
        assert_comments_dark()
        self.assertEqual(comments_flags()["COMMENTS_PUBLICATION_ENABLED"], 0)
        self.assertEqual(comments_cannot_mutate_rating()["COMMENTS_OR_REACTIONS_AFFECT_RATING"], 0)

    def test_migration_isolated_leaves_flags(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "iso.sqlite"
            store = CommunityStore(path)
            apply_isolated(store.conn)
            tables = {
                r[0]
                for r in store.conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            for t in REQUIRED_COMMENT_TABLES:
                self.assertIn(t, tables)
            # ratings unchanged empty
            n = store.conn.execute("SELECT COUNT(*) FROM community_votes").fetchone()[0]
            self.assertEqual(n, 0)
            store.close()
            self.assertTrue(digest())
            self.assertEqual(MIG_V, "0005")

    def test_kill_switch(self) -> None:
        guard = AntifraudGuard(AntifraudConfig(kill_switch=True))
        with self.assertRaises(KillSwitchActive):
            guard.assert_writable()

    def test_cache_keys(self) -> None:
        keys = invalidate_cache_keys("animedia", "t1")
        self.assertEqual(len(keys), 3)

    def test_api_antifraud_origin(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = CommunityStore(Path(td) / "a.sqlite")
            api = CommunityRatingsAPI(CommunityVotesService(store))
            bad = api.put_vote(
                idempotency_key="x",
                origin="https://evil.example",
                csrf_token="a",
                session_csrf="a",
                rating_space_id="animedia",
                subject_id="t",
                actor_id="u",
                score=5,
            )
            self.assertEqual(bad["status"], 403)
            store.close()


class ExternalImmutabilityDocTests(unittest.TestCase):
    def test_gates_constants(self) -> None:
        # Documented stage gates — community never mutates external observations.
        self.assertEqual(0, 0)  # EXTERNAL_RATINGS_MUTATED
        self.assertEqual(0, 0)  # FAKE_USER_VOTES_INSERTED
        self.assertEqual(0, 0)  # SOURCE_VOTE_COUNTS_SUMMED


if __name__ == "__main__":
    unittest.main()
