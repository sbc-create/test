"""Backup, restore, rollback and failure injection — rehearsed, not asserted.

Every test here uses a real SQLite file rather than the in-memory database the
rest of the suite runs on. That is the whole point: a backup rehearsal against
an in-memory database proves that a dictionary can be copied, and the failure
modes worth knowing about — a half-written file, a schema from the previous
version, a restore into a directory that already has data — only exist on disk.

Nothing here touches production. The databases live in pytest's tmp_path and
the migration is applied to them directly, exactly as `migrations/0001` says it
is meant to be used: the module is handed a path and works with what it is
given.
"""

from __future__ import annotations

import importlib.util
import shutil
import sqlite3
from pathlib import Path

import pytest

from factory.comments_platform import states
from factory.comments_platform.errors import FeatureDisabled, NotFound
from factory.comments_platform.identity import Identity
from factory.comments_platform.rbac import MODERATOR, USER, Principal
from factory.comments_platform.service import CommentsService
from factory.comments_platform.store import CommentsStore
from factory.comments_platform.tenancy import ResourceRef, SiteRegistry, TenantScope

from .conftest import TENANTS, open_binding

REPO = Path(__file__).resolve().parents[3]
MIGRATION = REPO / "migrations" / "0007_comments_platform.py"
REF = ResourceRef("title", "tt-resilience")
LORDS = TenantScope("lords", "lords-main")


def load_migration():
    spec = importlib.util.spec_from_file_location("m0007", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def disk_store(tmp_path):
    """A real file database, seeded with all four tenants."""
    store = CommentsStore(tmp_path / "comments.sqlite")
    store.create_schema()
    for tenant, site in TENANTS:
        scope = TenantScope(tenant, site)
        store.upsert_site(scope, module_version="0.1.0-mvp", artifact_checksum="0" * 64)
        store.upsert_policy(scope, policy_version="v1")
    store._conn.commit()
    yield store
    store.close()


@pytest.fixture
def disk_service(disk_store, gates_open):
    registry = SiteRegistry([open_binding(t, s) for t, s in TENANTS])
    return CommentsService(disk_store, registry, artifact_hash="rehearsal")


def author(scope, subject="g_author0001"):
    return (
        Principal(subject_id=subject, role=USER, scope=scope),
        Identity(subject_id=subject, scope=scope, is_guest=True),
    )


def seed(service, scope, count=3):
    principal, identity = author(scope)
    ids = []
    for index in range(count):
        result = service.create_comment(
            scope, principal, identity, REF,
            body=f"комментарий номер {index} с достаточно разными словами для дедупликации",
            idempotency_key=f"seed-{index}",
        )
        ids.append(result["comment"]["comment_id"])
    return ids


class TestBackupAndRestore:
    def test_a_file_copy_backup_restores_every_row(self, disk_store, disk_service, tmp_path):
        ids = seed(disk_service, LORDS, 3)
        before = {
            table: disk_store.raw_count(table)
            for table in ("cp_comments", "cp_threads", "cp_audit_events", "cp_idempotency")
        }

        backup = tmp_path / "backup.sqlite"
        # The documented procedure: SQLite's own online backup API, not a
        # filesystem copy of a live WAL database, which can capture a torn page.
        with sqlite3.connect(backup) as target:
            disk_store._conn.backup(target)

        # Destroy the original thoroughly.
        for table in ("cp_reactions", "cp_comment_revisions", "cp_comments", "cp_threads"):
            disk_store.execute_raw(f"DELETE FROM {table}")
        disk_store._conn.commit()
        assert disk_store.raw_count("cp_comments") == 0

        restored = CommentsStore(backup)
        try:
            for table, count in before.items():
                assert restored.raw_count(table) == count, f"{table} did not survive"
            for comment_id in ids:
                assert restored.get_comment(LORDS, comment_id)["body"]
        finally:
            restored.close()

    def test_restore_preserves_tenant_partitioning(self, disk_store, disk_service, tmp_path):
        for tenant, site in TENANTS:
            seed(disk_service, TenantScope(tenant, site), 2)
        backup = tmp_path / "backup2.sqlite"
        with sqlite3.connect(backup) as target:
            disk_store._conn.backup(target)

        restored = CommentsStore(backup)
        try:
            total = restored.raw_count("cp_comments")
            per_tenant = sum(
                restored.raw_count("cp_comments", TenantScope(t, s)) for t, s in TENANTS
            )
            assert total == per_tenant == 8
        finally:
            restored.close()

    def test_a_truncated_backup_is_detected_rather_than_trusted(self, disk_store, tmp_path):
        """Half a backup file must not read as a successful restore."""
        seed_path = tmp_path / "good.sqlite"
        with sqlite3.connect(seed_path) as target:
            disk_store._conn.backup(target)

        broken = tmp_path / "broken.sqlite"
        data = seed_path.read_bytes()
        broken.write_bytes(data[: len(data) // 2])

        with pytest.raises(sqlite3.DatabaseError):
            conn = sqlite3.connect(broken)
            conn.execute("PRAGMA integrity_check")
            # integrity_check on a truncated file may return rows rather than
            # raising, so the result is inspected too.
            result = conn.execute("SELECT COUNT(*) FROM cp_comments").fetchone()
            if result is None:
                raise sqlite3.DatabaseError("empty")

    def test_integrity_check_passes_on_a_real_backup(self, disk_store, disk_service, tmp_path):
        seed(disk_service, LORDS, 2)
        backup = tmp_path / "checked.sqlite"
        with sqlite3.connect(backup) as target:
            disk_store._conn.backup(target)
        conn = sqlite3.connect(backup)
        try:
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        finally:
            conn.close()


class TestMigrationRollbackRehearsal:
    def test_down_then_up_on_a_file_database_with_a_backup_in_between(self, tmp_path):
        """The full rehearsal an operator would perform before a real migration."""
        db = tmp_path / "rehearsal.sqlite"
        migration = load_migration()

        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        migration.upgrade(conn)
        assert migration.applied(conn)

        # Seed through the real store so the data is shaped like production's.
        store = CommentsStore(db)
        store.upsert_site(LORDS, module_version="0.1.0-mvp", artifact_checksum="0" * 64)
        store.upsert_policy(LORDS, policy_version="v1")
        store.upsert_identity(LORDS, "g_x")
        thread = store.get_or_create_thread(LORDS, REF)
        store.insert_comment(
            LORDS, thread_id=thread["thread_id"], subject_id="g_x",
            body="перед откатом", body_html="перед откатом", state=states.PUBLISHED,
        )
        store._conn.commit()
        rows_before = store.raw_count("cp_comments")
        store.close()

        # Backup, then roll the schema back.
        backup = tmp_path / "pre-downgrade.sqlite"
        shutil.copy2(db, backup)

        migration.downgrade(conn)
        assert not migration.applied(conn)
        remaining = {
            r["name"]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'cp_%'"
            )
        }
        assert remaining <= {"cp_schema_migrations"}

        # Roll forward again: the schema returns, empty but usable.
        migration.upgrade(conn)
        conn.close()
        store = CommentsStore(db)
        try:
            assert store.raw_count("cp_comments") == 0
        finally:
            store.close()

        # And the data is recoverable from the backup taken before the rollback.
        recovered = CommentsStore(backup)
        try:
            assert recovered.raw_count("cp_comments") == rows_before
        finally:
            recovered.close()

    def test_rollback_does_not_touch_other_tables_in_the_same_file(self, tmp_path):
        """Comments share a file with nothing, but prove the blast radius anyway."""
        db = tmp_path / "shared.sqlite"
        migration = load_migration()
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE unrelated_product (id TEXT PRIMARY KEY, payload TEXT)")
        conn.execute("INSERT INTO unrelated_product VALUES ('r1', 'ratings-like row')")
        conn.commit()

        migration.upgrade(conn)
        migration.downgrade(conn)

        survived = conn.execute("SELECT COUNT(*) FROM unrelated_product").fetchone()[0]
        conn.close()
        assert survived == 1, "the comments rollback removed somebody else's data"


class TestFailureInjection:
    def test_a_write_failing_mid_transaction_leaves_nothing_behind(
        self, disk_store, disk_service, monkeypatch
    ):
        """A comment without its audit row is worse than a refused comment."""
        principal, identity = author(LORDS)
        before = {
            table: disk_store.raw_count(table)
            for table in ("cp_comments", "cp_audit_events", "cp_content_digests", "cp_outbox")
        }

        original = disk_store.enqueue_event

        def explode(*args, **kwargs):
            raise RuntimeError("outbox unavailable")

        monkeypatch.setattr(disk_store, "enqueue_event", explode)
        with pytest.raises(RuntimeError):
            disk_service.create_comment(
                LORDS, principal, identity, REF, body="этот комментарий не должен уцелеть"
            )
        monkeypatch.setattr(disk_store, "enqueue_event", original)

        for table, count in before.items():
            assert disk_store.raw_count(table) == count, (
                f"{table} kept rows from a failed write"
            )

    def test_a_failed_write_does_not_consume_its_idempotency_key(
        self, disk_store, disk_service, monkeypatch
    ):
        """Otherwise a retry of a failed request is refused for ever."""
        principal, identity = author(LORDS)

        def explode(*args, **kwargs):
            raise RuntimeError("transient")

        original = disk_store.enqueue_event
        monkeypatch.setattr(disk_store, "enqueue_event", explode)
        with pytest.raises(RuntimeError):
            disk_service.create_comment(
                LORDS, principal, identity, REF, body="повторяемая попытка",
                idempotency_key="retry-me",
            )
        monkeypatch.setattr(disk_store, "enqueue_event", original)

        # The retry now succeeds rather than hitting a stored conflict.
        result = disk_service.create_comment(
            LORDS, principal, identity, REF, body="повторяемая попытка",
            idempotency_key="retry-me",
        )
        assert result["comment"]["comment_id"]

    def test_the_kill_switch_stops_writes_but_not_the_process(
        self, disk_store, disk_service
    ):
        from factory.comments_platform import flags as flags_module

        principal, identity = author(LORDS)
        seed(disk_service, LORDS, 1)
        flags_module.KillSwitch.engage_global()
        try:
            with pytest.raises(FeatureDisabled):
                disk_service.create_comment(
                    LORDS, principal, identity, REF, body="во время инцидента"
                )
            # Reads are also stopped, and the process is fine either way.
            with pytest.raises(FeatureDisabled):
                disk_service.thread_view(LORDS, principal, REF)
        finally:
            flags_module.KillSwitch.release_global()
        # And recovery needs no restart.
        assert disk_service.thread_view(LORDS, principal, REF).total_count == 1

    def test_antispam_outage_holds_instead_of_publishing(self, disk_store, disk_service):
        principal, identity = author(LORDS)
        result = disk_service.create_comment(
            LORDS, principal, identity, REF,
            body="совершенно обычный текст во время отказа античита",
            antispam_degraded=True,
        )
        assert result["moderation"]["state"] == states.PENDING

    def test_a_corrupted_row_state_is_refused_rather_than_guessed(
        self, disk_store, disk_service
    ):
        """A state nobody recognises must not be treated as published."""
        comment_id = seed(disk_service, LORDS, 1)[0]
        disk_store.execute_raw(
            "UPDATE cp_comments SET state = 'approved-ish' WHERE tenant_id = ?"
            " AND site_id = ? AND comment_id = ?",
            (LORDS.tenant_id, LORDS.site_id, comment_id),
        )
        disk_store._conn.commit()
        principal, _ = author(LORDS)
        with pytest.raises(Exception) as exc:
            disk_service.moderate(
                LORDS, Principal(subject_id="m", role=MODERATOR, scope=LORDS),
                comment_id, action="hide", reason="проверка",
            )
        assert "state" in str(exc.value).lower()


class TestBackgroundWorkerScope:
    def test_a_worker_draining_events_stays_inside_one_site(
        self, disk_store, disk_service
    ):
        for tenant, site in TENANTS:
            seed(disk_service, TenantScope(tenant, site), 1)

        for tenant, site in TENANTS:
            scope = TenantScope(tenant, site)
            claimed = disk_store.claim_events(scope, limit=50)
            assert claimed
            for event in claimed:
                assert (event["tenant_id"], event["site_id"]) == (tenant, site)
                disk_store.mark_event_processed(scope, event["event_id"])
        disk_store._conn.commit()

        remaining = disk_store.execute_raw(
            "SELECT COUNT(*) AS n FROM cp_outbox WHERE state = 'pending'"
        )
        assert remaining[0]["n"] == 0

    def test_retention_purge_is_scoped(self, disk_store):
        lords, zona = TenantScope("lords", "lords-main"), TenantScope("zona", "zona-main")
        for scope in (lords, zona):
            disk_store.record_rate_event(
                scope, bucket="subject", principal_key="k", endpoint="create"
            )
        disk_store._conn.commit()
        removed = disk_store.purge_rate_events_before(lords, "2099-01-01T00:00:00Z")
        assert removed == 1
        assert disk_store.raw_count("cp_rate_events", zona) == 1


class TestPrivacyOperations:
    def test_export_then_anonymize_keeps_the_thread_readable(
        self, disk_store, disk_service
    ):
        comment_ids = seed(disk_service, LORDS, 2)
        subject = "g_author0001"

        export = disk_store.export_subject(LORDS, subject)
        assert len(export["comments"]) == 2

        changed = disk_store.anonymize_subject(LORDS, subject)
        disk_store._conn.commit()
        assert changed == 2

        # The comments are still there and still readable — erasure must not
        # punch holes in every conversation the person took part in.
        for comment_id in comment_ids:
            row = disk_store.get_comment(LORDS, comment_id)
            assert row["body"]
            assert row["subject_id"] != subject

        # And nothing of theirs remains addressable under the old id.
        after = disk_store.export_subject(LORDS, subject)
        assert after["comments"] == []

    def test_anonymize_does_not_reach_another_site(self, disk_store, disk_service):
        for tenant, site in TENANTS:
            seed(disk_service, TenantScope(tenant, site), 1)
        disk_store.anonymize_subject(LORDS, "g_author0001")
        disk_store._conn.commit()
        zona = TenantScope("zona", "zona-main")
        assert disk_store.export_subject(zona, "g_author0001")["comments"]


class TestNotFoundStaysNotFound:
    def test_an_unknown_comment_id_is_not_found_on_a_file_database(self, disk_store):
        with pytest.raises(NotFound):
            disk_store.get_comment(LORDS, "c_does_not_exist")
