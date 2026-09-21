"""Identity: no passwords, no raw IP, and no way to follow a guest between sites."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from factory.comments_platform.errors import Unauthenticated, ValidationFailed
from factory.comments_platform.identity import (
    GUEST_PREFIX,
    GuestIdentityProvider,
    IdentityResolver,
    InMemorySecretResolver,
    TenantLocalProfile,
    derive_network_hmac,
    derive_public_subject_id,
    privacy_notes,
)
from factory.comments_platform.tenancy import TenantScope

LORDS = TenantScope("lords", "lords-main")
ZONA = TenantScope("zona", "zona-main")
LORDS_SECOND_SITE = TenantScope("lords", "lords-staging")


class StaticUpstream:
    def __init__(self, subject: str | None) -> None:
        self.subject = subject

    def authenticated_subject(self, request_context):
        return self.subject


class TestNonCorrelation:
    def test_same_person_gets_unrelated_ids_on_two_tenants(self, secrets_resolver):
        upstream = "the-same-human-everywhere"
        lords_id = derive_public_subject_id(
            secrets_resolver, LORDS, upstream_subject=upstream, is_guest=False
        )
        zona_id = derive_public_subject_id(
            secrets_resolver, ZONA, upstream_subject=upstream, is_guest=False
        )
        assert lords_id != zona_id
        # And not merely different: neither contains the other or the input.
        assert upstream not in lords_id
        assert lords_id[2:] not in zona_id

    def test_two_sites_of_one_tenant_are_also_separated(self, secrets_resolver):
        upstream = "same-human"
        a = derive_public_subject_id(
            secrets_resolver, LORDS, upstream_subject=upstream, is_guest=False
        )
        b = derive_public_subject_id(
            secrets_resolver, LORDS_SECOND_SITE, upstream_subject=upstream, is_guest=False
        )
        assert a != b

    def test_derivation_is_stable_for_one_scope(self, secrets_resolver):
        args = {"upstream_subject": "human", "is_guest": False}
        first = derive_public_subject_id(secrets_resolver, LORDS, **args)
        second = derive_public_subject_id(secrets_resolver, LORDS, **args)
        assert first == second

    def test_without_the_other_tenants_key_correlation_is_not_computable(self):
        """Two deployments holding separate keys cannot join their user tables."""
        lords_only = InMemorySecretResolver()
        zona_only = InMemorySecretResolver()
        upstream = "human"
        a = derive_public_subject_id(lords_only, LORDS, upstream_subject=upstream, is_guest=False)
        b = derive_public_subject_id(zona_only, ZONA, upstream_subject=upstream, is_guest=False)
        assert a != b

    def test_empty_upstream_subject_is_refused(self, secrets_resolver):
        with pytest.raises(Unauthenticated):
            derive_public_subject_id(secrets_resolver, LORDS, upstream_subject="", is_guest=False)


class TestNetworkIdentifier:
    def test_raw_address_never_appears_in_the_output(self, secrets_resolver):
        value = derive_network_hmac(secrets_resolver, LORDS, remote_addr="203.0.113.7")
        assert "203.0.113" not in value
        assert value.startswith("n_")

    def test_rotates_between_epochs(self, secrets_resolver):
        day_one = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)
        day_two = day_one + timedelta(days=1)
        a = derive_network_hmac(secrets_resolver, LORDS, remote_addr="203.0.113.7", now=day_one)
        b = derive_network_hmac(secrets_resolver, LORDS, remote_addr="203.0.113.7", now=day_two)
        assert a != b, "a network identifier that never rotates is a durable tracker"

    def test_stable_within_one_epoch(self, secrets_resolver):
        morning = datetime(2026, 9, 21, 1, 0, tzinfo=timezone.utc)
        evening = datetime(2026, 9, 21, 23, 0, tzinfo=timezone.utc)
        a = derive_network_hmac(secrets_resolver, LORDS, remote_addr="203.0.113.7", now=morning)
        b = derive_network_hmac(secrets_resolver, LORDS, remote_addr="203.0.113.7", now=evening)
        assert a == b, "flood detection needs one epoch to be stable"

    def test_differs_between_tenants_for_one_address(self, secrets_resolver):
        now = datetime(2026, 9, 21, tzinfo=timezone.utc)
        a = derive_network_hmac(secrets_resolver, LORDS, remote_addr="203.0.113.7", now=now)
        b = derive_network_hmac(secrets_resolver, ZONA, remote_addr="203.0.113.7", now=now)
        assert a != b

    def test_missing_address_yields_empty_not_a_fabricated_value(self, secrets_resolver):
        assert derive_network_hmac(secrets_resolver, LORDS, remote_addr="") == ""


class TestGuests:
    def test_guest_token_is_random_not_a_fingerprint(self):
        tokens = {GuestIdentityProvider.issue_guest_token() for _ in range(50)}
        assert len(tokens) == 50

    def test_guest_id_is_marked_as_a_guest(self, secrets_resolver):
        provider = GuestIdentityProvider(secrets_resolver)
        identity = provider.identity_for_guest(LORDS, "a" * 32)
        assert identity.is_guest
        assert identity.subject_id.startswith(GUEST_PREFIX)

    def test_short_guest_token_is_refused(self, secrets_resolver):
        provider = GuestIdentityProvider(secrets_resolver)
        for bad in ("", "short"):
            with pytest.raises(ValidationFailed):
                provider.identity_for_guest(LORDS, bad)

    def test_same_guest_token_on_two_tenants_is_uncorrelatable(self, secrets_resolver):
        provider = GuestIdentityProvider(secrets_resolver)
        token = "b" * 32
        assert (
            provider.identity_for_guest(LORDS, token).subject_id
            != provider.identity_for_guest(ZONA, token).subject_id
        )


class TestResolver:
    def test_authenticated_subject_wins_over_guest_token(self, secrets_resolver):
        resolver = IdentityResolver(secrets_resolver, StaticUpstream("auth-subject"))
        identity = resolver.resolve(LORDS, {"guest_token": "c" * 32, "remote_addr": "203.0.113.1"})
        assert not identity.is_guest
        assert identity.subject_id.startswith("u_")

    def test_guest_path_when_no_upstream_subject(self, secrets_resolver):
        resolver = IdentityResolver(secrets_resolver, StaticUpstream(None))
        identity = resolver.resolve(LORDS, {"guest_token": "d" * 32})
        assert identity.is_guest

    def test_site_requiring_login_refuses_guests(self, secrets_resolver):
        resolver = IdentityResolver(secrets_resolver, StaticUpstream(None))
        with pytest.raises(Unauthenticated):
            resolver.resolve(LORDS, {"guest_token": "e" * 32}, allow_guests=False)

    def test_network_hmac_is_attached_but_the_address_is_not(self, secrets_resolver):
        resolver = IdentityResolver(secrets_resolver, StaticUpstream("auth"))
        identity = resolver.resolve(LORDS, {"remote_addr": "198.51.100.9"})
        assert identity.network_hmac
        assert "198.51.100" not in repr(identity)

    def test_display_name_is_bounded(self, secrets_resolver):
        resolver = IdentityResolver(secrets_resolver, StaticUpstream("auth"))
        identity = resolver.resolve(LORDS, {"display_name": "x" * 500})
        assert len(identity.display_name) <= 64


class TestProfilesAreLocal:
    def test_profile_key_includes_tenant_and_site(self):
        profile = TenantLocalProfile(scope=LORDS, subject_id="u_1", banned=True)
        assert profile.key() == ("lords", "lords-main", "u_1")

    def test_a_ban_is_a_property_of_one_site(self):
        lords_profile = TenantLocalProfile(scope=LORDS, subject_id="u_1", banned=True)
        zona_profile = TenantLocalProfile(scope=ZONA, subject_id="u_1", banned=False)
        assert lords_profile.banned and not zona_profile.banned
        assert lords_profile.key() != zona_profile.key()


class TestPrivacyStatement:
    def test_states_what_is_not_stored(self):
        notes = privacy_notes()
        assert notes["stores_passwords"] is False
        assert notes["stores_raw_ip"] is False
        assert notes["stores_email"] is False
        assert notes["network_retention_days"] <= 30

    def test_public_identity_dict_carries_no_network_value(self, secrets_resolver):
        resolver = IdentityResolver(secrets_resolver, StaticUpstream("auth"))
        identity = resolver.resolve(LORDS, {"remote_addr": "198.51.100.9"})
        assert "network" not in repr(identity.as_public_dict())
