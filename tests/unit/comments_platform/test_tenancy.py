"""Tenant resolution must be un-spoofable and un-ambiguous."""

from __future__ import annotations

import hashlib

import pytest

from factory.comments_platform.errors import (
    BadRequest,
    CrossTenantDenied,
    NotFound,
    ValidationFailed,
)
from factory.comments_platform.tenancy import (
    ALLOWED_TENANTS,
    ResourceRef,
    SiteBinding,
    SiteRegistry,
    TenantScope,
    reject_client_supplied_scope,
)

CHECKSUM = hashlib.sha256(b"artifact").hexdigest()


def binding(tenant: str = "lords", site: str = "lords-main", **over) -> SiteBinding:
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


class TestScope:
    def test_scope_rejects_unknown_tenant(self):
        with pytest.raises(ValidationFailed):
            TenantScope("notatenant", "site")

    def test_scope_rejects_shell_unsafe_identifiers(self):
        for bad in ("../lords", "lords/main", "Lords", "lords main", "", "a" * 80):
            with pytest.raises(ValidationFailed):
                TenantScope(bad, "site")

    def test_assert_owns_raises_cross_tenant_for_foreign_row(self):
        scope = TenantScope("lords", "lords-main")
        with pytest.raises(CrossTenantDenied) as exc:
            scope.assert_owns("zona", "zona-main")
        # 404 on the wire: a probe must not learn the object exists elsewhere.
        assert exc.value.http_status == 404
        assert exc.value.code == "NotFound"

    def test_assert_owns_catches_same_tenant_other_site(self):
        scope = TenantScope("lords", "lords-main")
        with pytest.raises(CrossTenantDenied):
            scope.assert_owns("lords", "lords-staging")

    def test_all_four_tenants_are_allowed(self):
        assert set(ALLOWED_TENANTS) == {"lords", "zona", "animedia", "yummy"}


class TestClientSuppliedScope:
    @pytest.mark.parametrize(
        "payload",
        [
            {"tenant_id": "zona"},
            {"site_id": "zona-main"},
            {"TENANT_ID": "zona"},
            {"X-Tenant-Id": "zona"},
            {"body": "hi", "tenant": "zona"},
        ],
    )
    def test_any_client_named_scope_is_refused(self, payload):
        with pytest.raises(BadRequest):
            reject_client_supplied_scope(payload)

    def test_ordinary_payload_passes(self):
        reject_client_supplied_scope({"body": "hello", "parent_id": "c1"})
        reject_client_supplied_scope(None)


class TestSiteBinding:
    @pytest.mark.parametrize("floating", ["latest", "main", "HEAD", "", "stable", "current"])
    def test_floating_versions_are_refused(self, floating):
        with pytest.raises(ValidationFailed):
            binding(module_version=floating)

    def test_checksum_must_be_sha256(self):
        with pytest.raises(ValidationFailed):
            binding(artifact_checksum="deadbeef")

    def test_wildcard_origin_is_refused(self):
        with pytest.raises(ValidationFailed):
            binding(allowed_origins=("https://*.example",))

    def test_origin_must_carry_a_scheme(self):
        with pytest.raises(ValidationFailed):
            binding(allowed_origins=("lords.example",))

    def test_host_with_port_is_refused(self):
        with pytest.raises(ValidationFailed):
            binding(hosts=("lords.example:8080",))

    def test_public_config_leaks_no_secrets_or_internals(self):
        cfg = binding().to_public_config()
        flat = repr(cfg).lower()
        for forbidden in ("tenant_id", "checksum", "secret", "token", "credential", "hosts"):
            assert forbidden not in flat, f"{forbidden} reached the browser config"

    def test_defaults_are_dark(self):
        b = binding()
        assert b.read_enabled == 0
        assert b.write_enabled == 0
        assert b.publication_enabled == 0
        assert b.rollout_percent == 0
        assert b.seo_mode == "user_initiated"


class TestRegistry:
    def test_host_resolves_to_its_own_site(self):
        reg = SiteRegistry([binding(), binding("zona", "zona-main")])
        assert reg.resolve_host("zona-main.example").tenant_id == "zona"

    @pytest.mark.parametrize(
        "given", ["LORDS-MAIN.EXAMPLE", "lords-main.example.", "lords-main.example:443"]
    )
    def test_host_normalisation(self, given):
        reg = SiteRegistry([binding()])
        assert reg.resolve_host(given).site_id == "lords-main"

    def test_unknown_host_is_not_found_and_names_no_site(self):
        reg = SiteRegistry([binding()])
        with pytest.raises(NotFound) as exc:
            reg.resolve_host("attacker.example")
        assert "lords" not in exc.value.to_public("rid")["error"]["message"]

    def test_two_sites_may_not_share_a_host(self):
        with pytest.raises(ValidationFailed):
            SiteRegistry([binding(), binding("zona", "zona-main", hosts=("lords-main.example",))])

    def test_duplicate_site_key_is_refused(self):
        with pytest.raises(ValidationFailed):
            SiteRegistry([binding(), binding(hosts=("other.example",))])

    def test_origin_matching_is_exact(self):
        reg = SiteRegistry([binding()])
        b = reg.get("lords", "lords-main")
        assert reg.origin_allowed(b, "https://lords-main.example")
        assert not reg.origin_allowed(b, "https://lords-main.example.evil.test")
        assert not reg.origin_allowed(b, "https://evil.test")
        assert not reg.origin_allowed(b, "null")
        assert not reg.origin_allowed(b, None)
        assert not reg.origin_allowed(b, "http://lords-main.example")


class TestResourceRef:
    def test_thread_key_is_content_not_url(self):
        ref = ResourceRef("title", "tt-0001")
        assert ref.canonical_content_id == "tt-0001"
        # Same content id under a renamed site keeps the same thread key.
        assert ResourceRef("title", "tt-0001") == ref

    def test_unknown_resource_type_is_refused(self):
        with pytest.raises(ValidationFailed):
            ResourceRef("comment_on_a_comment", "tt-0001")
