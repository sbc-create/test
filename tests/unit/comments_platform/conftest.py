"""Shared fixtures.

Every test gets its own SQLite file in a tmp_path. No test touches a shared
database, a production path or `var/`: an isolation suite that shares state
between cases cannot prove isolation of anything.
"""

from __future__ import annotations

import hashlib

import pytest

from factory.comments_platform import flags as flags_module
from factory.comments_platform.identity import Identity, IdentityResolver, InMemorySecretResolver
from factory.comments_platform.rbac import MODERATOR, TENANT_ADMIN, USER, Principal
from factory.comments_platform.service import CommentsService
from factory.comments_platform.store import CommentsStore
from factory.comments_platform.tenancy import (
    ResourceRef,
    SiteBinding,
    SiteRegistry,
    TenantScope,
)

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


@pytest.fixture
def gates_open(monkeypatch):
    """Raise the compiled ceilings for one test.

    The platform ships with every gate pinned at 0 and unraisable from the
    environment, which is what makes the dark default trustworthy — and also
    what makes the read and write paths untestable without an explicit,
    visible escape hatch. Monkeypatching the ceiling is that hatch: it exists
    only inside a test process, it names itself in the test that uses it, and
    it cannot be reached from a deployment, a unit file or a config row.

    A test that does *not* request this fixture is asserting behaviour under
    the shipped defaults, which is why most of them do not.
    """
    for name in (
        "CEILING_READ_ENABLED", "CEILING_WRITE_ENABLED",
        "CEILING_PUBLICATION_ENABLED", "CEILING_SSR_ENABLED",
    ):
        monkeypatch.setattr(flags_module, name, 1)
    monkeypatch.setattr(flags_module, "CEILING_ROLLOUT_PERCENT", 100)
    flags_module.KillSwitch.release_global()
    yield
    flags_module.KillSwitch.release_global()


def open_binding(tenant: str, site: str, **over) -> SiteBinding:
    """A site row with reading and writing switched on, for service tests."""
    defaults = {
        "read_enabled": 1,
        "write_enabled": 1,
        "publication_enabled": 1,
        "moderation_mode": "post",
    }
    defaults.update(over)
    return make_binding(tenant, site, **defaults)


@pytest.fixture
def open_registry() -> SiteRegistry:
    return SiteRegistry([open_binding(t, s) for t, s in TENANTS])


@pytest.fixture
def service(store, open_registry, gates_open) -> CommentsService:
    return CommentsService(store, open_registry, artifact_hash="test-artifact")


@pytest.fixture
def identities(secrets_resolver, scopes) -> dict[str, Identity]:
    """One guest identity per tenant, derived exactly as the resolver would."""
    resolver = IdentityResolver(secrets_resolver, None)
    return {
        tenant: resolver.resolve(
            scope, {"guest_token": f"token-for-{tenant}-{'x' * 20}", "remote_addr": "203.0.113.5"}
        )
        for tenant, scope in scopes.items()
    }


@pytest.fixture
def users(scopes, identities) -> dict[str, Principal]:
    return {
        tenant: Principal(subject_id=identities[tenant].subject_id, role=USER, scope=scope)
        for tenant, scope in scopes.items()
    }


@pytest.fixture
def moderators(scopes) -> dict[str, Principal]:
    return {
        tenant: Principal(subject_id=f"mod-{tenant}", role=MODERATOR, scope=scope)
        for tenant, scope in scopes.items()
    }


@pytest.fixture
def admins(scopes) -> dict[str, Principal]:
    return {
        tenant: Principal(subject_id=f"admin-{tenant}", role=TENANT_ADMIN, scope=scope)
        for tenant, scope in scopes.items()
    }


REF = ResourceRef("title", "tt-0001")
