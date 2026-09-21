"""Migration 0007: reversible, and scoped on every table it creates."""

from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest

from factory.comments_platform import schema

REPO_ROOT = Path(__file__).resolve().parents[3]
MIGRATION_PATH = REPO_ROOT / "migrations" / "0007_comments_platform.py"


def load_migration():
    spec = importlib.util.spec_from_file_location("m0007", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def conn():
    # In memory: this suite tests DDL semantics, and a file database costs a
    # second per case in fsync on this host for no added coverage.
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    yield connection
    connection.close()


def table_names(connection) -> set[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'cp_%'"
    ).fetchall()
    return {r["name"] for r in rows}


class TestReversibility:
    def test_upgrade_creates_every_declared_table(self, conn):
        migration = load_migration()
        migration.upgrade(conn)
        present = table_names(conn)
        for table in schema.TABLES:
            assert table in present, f"{table} was declared but not created"

    def test_applied_reports_truthfully(self, conn):
        migration = load_migration()
        assert migration.applied(conn) is False
        migration.upgrade(conn)
        assert migration.applied(conn) is True
        migration.downgrade(conn)
        assert migration.applied(conn) is False

    def test_downgrade_removes_everything_it_created(self, conn):
        migration = load_migration()
        before = table_names(conn)
        migration.upgrade(conn)
        migration.downgrade(conn)
        after = table_names(conn)
        leftover = after - before - {"cp_schema_migrations"}
        assert not leftover, f"downgrade left {sorted(leftover)} behind"

    def test_upgrade_is_idempotent(self, conn):
        migration = load_migration()
        migration.upgrade(conn)
        migration.upgrade(conn)  # must not raise
        assert migration.applied(conn)

    def test_downgrade_then_upgrade_restores_a_working_schema(self, conn):
        migration = load_migration()
        migration.upgrade(conn)
        migration.downgrade(conn)
        migration.upgrade(conn)
        for table in schema.TABLES:
            conn.execute(f"SELECT COUNT(*) FROM {table}")


class TestTenantScopingIsStructural:
    """Every table this module owns must carry the tenant pair.

    Walking the live schema rather than reading the DDL means a table added
    later without scoping fails here, rather than being caught by whoever
    happens to review that diff.
    """

    @pytest.mark.parametrize("table", schema.TABLES)
    def test_table_carries_tenant_and_site(self, conn, table):
        migration = load_migration()
        migration.upgrade(conn)
        columns = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        assert "tenant_id" in columns, f"{table} has no tenant_id"
        assert "site_id" in columns, f"{table} has no site_id"

    @pytest.mark.parametrize("table", schema.TABLES)
    def test_primary_key_leads_with_the_tenant_pair(self, conn, table):
        migration = load_migration()
        migration.upgrade(conn)
        rows = list(conn.execute(f"PRAGMA table_info({table})"))
        pk = [r["name"] for r in sorted(rows, key=lambda r: r["pk"]) if r["pk"]]
        assert pk[:2] == ["tenant_id", "site_id"], f"{table} primary key is {pk}"

    def test_declared_table_list_matches_reality(self, conn):
        migration = load_migration()
        migration.upgrade(conn)
        actual = table_names(conn) - set(schema.UNSCOPED_TABLES)
        assert actual == set(schema.TABLES), (
            f"declared {sorted(set(schema.TABLES))} but schema has {sorted(actual)}"
        )


class TestCompositeForeignKeys:
    def test_a_comment_cannot_reference_another_tenants_thread(self, conn):
        """The database, not the application, refuses this."""
        migration = load_migration()
        migration.upgrade(conn)
        now = "2026-09-21T00:00:00Z"
        for tenant, site in (("lords", "lords-main"), ("zona", "zona-main")):
            conn.execute(
                "INSERT INTO cp_sites(tenant_id, site_id, module_version, artifact_checksum,"
                " created_at, updated_at) VALUES (?,?,'v','x',?,?)",
                (tenant, site, now, now),
            )
            conn.execute(
                "INSERT INTO cp_identities(tenant_id, site_id, subject_id, created_at, updated_at)"
                " VALUES (?,?,'u_1',?,?)",
                (tenant, site, now, now),
            )
        conn.execute(
            "INSERT INTO cp_threads(tenant_id, site_id, thread_id, resource_type,"
            " canonical_content_id, created_at, updated_at)"
            " VALUES ('zona','zona-main','th_z','title','tt-1',?,?)",
            (now, now),
        )
        conn.commit()

        with pytest.raises(sqlite3.IntegrityError):
            # A lords comment pointing at the zona thread id.
            conn.execute(
                "INSERT INTO cp_comments(tenant_id, site_id, comment_id, thread_id, subject_id,"
                " body, body_html, state, created_at, updated_at, seq)"
                " VALUES ('lords','lords-main','c_1','th_z','u_1','x','x','pending',?,?,1)",
                (now, now),
            )
            conn.commit()

    def test_foreign_keys_are_actually_enforced_on_this_connection(self, conn):
        migration = load_migration()
        migration.upgrade(conn)
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
