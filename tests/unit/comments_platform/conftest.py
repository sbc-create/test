"""Shared fixtures.

Every test gets its own SQLite file in a tmp_path. No test touches a shared
database, a production path or `var/`: an isolation suite that shares state
between cases cannot prove isolation of anything.
"""

from __future__ import annotations

import hashlib

import pytest

from factory.comments_platform.identity import InMemorySecretResolver
from factory.comments_platform.store import CommentsStore
from factory.comments_platform.tenancy import SiteBinding, SiteRegistry, TenantScope

CHECKSUM = hashlib.sha256(b"comments-platform-mvp").hexdigest()

TENANTS = (
    ("lords", "lords-main"),
    ("zona", "zona-main"),
    ("animedia", "animedia-main"),
    ("yummy", "yummy-main"),
)


def make_binding(tenant: str, site: str, **over) -> SiteBinding:
    kwargs = {
        "tenant_id": tenant,
        "site_id": site,
        "hosts": (f"{site}.example",),
        "allowed_origins": (f"https://{site}.example",),
        "module_version": "0.1.0-mvp",
        "artifact_checksum": CHECKSUM,
    }
    kwargs.update(over)
    return SiteBinding(**kwargs)


@pytest.fixture
def registry() -> SiteRegistry:
    return SiteRegistry([make_binding(t, s) for t, s in TENANTS])


@pytest.fixture
def scopes() -> dict[str, TenantScope]:
    return {tenant: TenantScope(tenant, site) for tenant, site in TENANTS}


@pytest.fixture
def store(scopes) -> CommentsStore:
    # In memory on purpose. A file database on this host costs about a second
    # per schema creation in fsync alone, which would put the suite at several
    # minutes and quietly discourage running it. The backup/restore rehearsal
    # uses a real file, because there the file is the thing under test.
    st = CommentsStore(":memory:")
    st.create_schema()
    for scope in scopes.values():
        st.upsert_site(
            scope, module_version="0.1.0-mvp", artifact_checksum=CHECKSUM, moderation_mode="pre"
        )
        st.upsert_policy(scope, policy_version="v1")
    st._conn.commit()
    yield st
    st.close()


@pytest.fixture
def secrets_resolver() -> InMemorySecretResolver:
    return InMemorySecretResolver()
