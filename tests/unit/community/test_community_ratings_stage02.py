"""COMMUNITY-RATINGS-02 — migration, permission, backfill, public-read gates."""

from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from factory.community.admin_ui import render_admin_list_html, require_read_scope
from factory.community.backfill import backfill_display_projections, replay_backfill
from factory.community.comments_foundation import assert_comments_dark
from factory.community.formulas import YummyPublic, build_yummy_prior
from factory.community.readmodel import get_title_ratings
from factory.community.ssr import render_title_block
from decimal import Decimal

ROOT = Path(__file__).resolve().parents[3]
MIG = ROOT / "migrations" / "0006_community_production.py"
PROD = Path("/srv/site-factory/repo/var/ratings/ratings.sqlite")


def _load_m6():
    spec = spec_from_file_location("m6_prod", MIG)
    mod = module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


class Stage02MigrationTests(unittest.TestCase):
    def test_migration_idempotent_on_clone(self) -> None:
        m6 = _load_m6()
        with tempfile.TemporaryDirectory() as td:
            clone = Path(td) / "c.sqlite"
            # minimal base with schema_migrations
            c = sqlite3.connect(str(clone))
            c.execute(
                "CREATE TABLE schema_migrations(version TEXT PRIMARY KEY, description TEXT, applied_at TEXT)"
            )
            c.commit()
            c.close()
            r1 = m6.apply_path(str(clone))
            r2 = m6.apply_path(str(clone))
            self.assertTrue(r1["first_apply"])
            self.assertFalse(r2["first_apply"])
            self.assertFalse(r1["destructive"])


class Stage02PermissionAndBackfillTests(unittest.TestCase):
    def test_prod_native_ledger_empty_and_amd_not_active(self) -> None:
        if not PROD.is_file():
            self.skipTest("no prod db")
        c = sqlite3.connect(f"file:{PROD}?mode=ro", uri=True)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM community_votes").fetchone()[0], 0)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM rating_vote_current").fetchone()[0], 0)
        self.assertEqual(
            c.execute(
                "SELECT COUNT(*) FROM community_display_projection WHERE source_key='amd_online' AND active=1"
            ).fetchone()[0],
            0,
        )
        self.assertEqual(c.execute("SELECT COUNT(*) FROM community_comments").fetchone()[0], 0)
        c.close()

    def test_double_count_gate(self) -> None:
        prior, prov = build_yummy_prior(
            animedia_native=None,
            shikimori=Decimal("7.1"),
            animedia_embeds_shikimori=False,
        )
        self.assertEqual(prov.get("double_counted_source_count"), 0)
        pub = YummyPublic(0, 0, prior, m=10)
        self.assertEqual(pub.displayed_vote_count(), 0)
        self.assertIsNotNone(pub.public_score)

    def test_admin_rbac(self) -> None:
        with self.assertRaises(PermissionError):
            require_read_scope([])
        html = render_admin_list_html(scopes={"read"})
        self.assertIn("read-only", html.lower())
        self.assertNotIn("name=\"score\"", html)

    def test_comments_dark(self) -> None:
        assert_comments_dark()

    def test_ssr_no_empty_shell_and_no_zero(self) -> None:
        view = get_title_ratings(rating_space_id="animedia", subject_id="definitely-missing-id")
        self.assertEqual(render_title_block(view), "")
        self.assertTrue(view["native"]["absent"])
        self.assertNotEqual(view["native"].get("score"), "0")
        self.assertFalse(view.get("aggregate_rating_schema_org"))


class Stage02PublicWriteDisabled(unittest.TestCase):
    def test_flags(self) -> None:
        if not PROD.is_file():
            self.skipTest("no prod db")
        c = sqlite3.connect(f"file:{PROD}?mode=ro", uri=True)
        flags = dict(c.execute("SELECT flag, value FROM community_feature_flags"))
        c.close()
        self.assertEqual(flags.get("RATINGS_NATIVE_WRITE_ANIMEDIA"), 0)
        self.assertEqual(flags.get("RATINGS_NATIVE_WRITE_YUMMY"), 0)
        self.assertEqual(flags.get("COMMENTS_PUBLICATION_ENABLED"), 0)


if __name__ == "__main__":
    unittest.main()
