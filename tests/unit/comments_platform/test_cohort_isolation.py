"""Site and cohort isolation for the Stage 1 owner pilot.

The brief requires this suite to exist and pass *before* anything is served,
so it is written against the shipped configuration rather than a fixture: the
question is not "can cohorts work" but "is animedia.icu, and only animedia.icu,
open to the owner cohort right now".

Note which tests take the `gates_open` fixture and which do not. The ones that
do not are asserting the real shipped state; opening the gates there would
prove nothing about what the site actually serves today.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.comments_platform import cohorts
from factory.comments_platform import flags as flags_module
from factory.comments_platform.errors import FeatureDisabled, Unauthenticated, ValidationFailed
from factory.comments_platform.flags import FlagResolver
from factory.comments_platform.identity import InMemorySecretResolver
from factory.comments_platform.tenancy import SiteRegistry, TenantScope

REPO = Path(__file__).resolve().parents[3]
CONFIG = REPO / "config" / "comments-platform" / "sites.json"

PILOT = TenantScope("animedia", "animedia-01")      # animedia.icu — authorised
SECOND = TenantScope("animedia", "animedia-02")     # animedia.space — forbidden
OTHER = TenantScope("zona", "zona-01")


@pytest.fixture(scope="module")
def shipped() -> SiteRegistry:
    return SiteRegistry.from_file(CONFIG)


@pytest.fixture
def secrets() -> InMemorySecretResolver:
    return InMemorySecretResolver()


def token_for(secrets, scope, subject="owner", ttl=3600, now=None) -> str:
    return cohorts.issue_cohort_token(
        secrets, scope, cohort=cohorts.OWNER_TEST, subject_id=subject,
        ttl_seconds=ttl, now=now,
    )


class TestShippedStateIsOwnerOnlyOnOneDomain:
    def test_the_ordinary_visitor_gets_nothing_on_the_pilot_domain(self, shipped):
        binding = shipped.get("animedia", "animedia-01")
        effective = FlagResolver().resolve_for_cohort(binding, cohorts.PUBLIC)
        assert effective.read_enabled == 0
        assert effective.write_enabled == 0
        assert effective.publication_enabled == 0
        assert effective.rollout_percent == 0

    def test_the_owner_cohort_is_open_on_the_pilot_domain(self, shipped):
        binding = shipped.get("animedia", "animedia-01")
        effective = FlagResolver().resolve_for_cohort(binding, cohorts.OWNER_TEST)
        assert effective.read_enabled == 1
        assert effective.write_enabled == 1
        assert effective.publication_enabled == 1

    def test_the_second_animedia_domain_is_closed_to_both_cohorts(self, shipped):
        binding = shipped.get("animedia", "animedia-02")
        for cohort in cohorts.COHORTS:
            effective = FlagResolver().resolve_for_cohort(binding, cohort)
            assert effective.read_enabled == 0, cohort
            assert effective.write_enabled == 0, cohort
            assert effective.publication_enabled == 0, cohort

    @pytest.mark.parametrize(
        "site", ["lords-01", "lords-02", "lords-03", "zona-01",
                 "yummyani-site", "yummyani-org", "yummyani-biz"]
    )
    def test_every_other_site_is_closed_to_both_cohorts(self, shipped, site):
        binding = next(b for b in shipped.all_bindings() if b.site_id == site)
        for cohort in cohorts.COHORTS:
            effective = FlagResolver().resolve_for_cohort(binding, cohort)
            assert effective.read_enabled == 0, f"{site}/{cohort}"
            assert effective.write_enabled == 0, f"{site}/{cohort}"

    def test_ssr_is_zero_everywhere_in_every_cohort(self, shipped):
        """Comments must not reach a crawler during an owner test."""
        for binding in shipped.all_bindings():
            for cohort in cohorts.COHORTS:
                assert FlagResolver().resolve_for_cohort(binding, cohort).ssr_enabled == 0

    def test_the_pilot_allowlist_is_the_first_gate(self, shipped):
        """A site outside PILOT_SITES gets the public ceiling whatever is claimed."""
        assert flags_module.PILOT_SITES == (("animedia", "animedia-01"),)
        binding = shipped.get("animedia", "animedia-02")
        assert FlagResolver().resolve_for_cohort(binding, cohorts.OWNER_TEST).read_enabled == 0


class TestTokensDoNotTravel:
    def test_a_token_minted_for_the_pilot_does_not_verify_on_the_second_domain(self, secrets):
        token = token_for(secrets, PILOT)
        assert cohorts.verify_cohort_token(secrets, PILOT, token) is not None
        assert cohorts.verify_cohort_token(secrets, SECOND, token) is None

    def test_a_token_does_not_verify_on_another_tenant(self, secrets):
        token = token_for(secrets, PILOT)
        assert cohorts.verify_cohort_token(secrets, OTHER, token) is None

    def test_a_token_from_another_tenants_key_does_not_verify(self):
        theirs = InMemorySecretResolver()
        mine = InMemorySecretResolver()
        token = token_for(theirs, PILOT)
        assert cohorts.verify_cohort_token(mine, PILOT, token) is None


class TestTokenValidation:
    def test_absent_token_is_the_public_cohort_not_an_error(self, secrets):
        resolver = cohorts.CohortResolver(secrets)
        membership = resolver.resolve(PILOT, {"cookies": {}})
        assert membership.cohort == cohorts.PUBLIC
        assert not membership.is_owner_test

    def test_a_valid_cookie_grants_the_owner_cohort(self, secrets):
        resolver = cohorts.CohortResolver(secrets)
        token = token_for(secrets, PILOT)
        membership = resolver.resolve(PILOT, {"cookies": {cohorts.COHORT_COOKIE: token}})
        assert membership.is_owner_test

    def test_an_expired_token_falls_back_to_public(self, secrets):
        token = token_for(secrets, PILOT, ttl=10, now=1000.0)
        assert cohorts.verify_cohort_token(secrets, PILOT, token, now=1005.0) is not None
        assert cohorts.verify_cohort_token(secrets, PILOT, token, now=1011.0) is None

    @pytest.mark.parametrize("mangle", [
        # A character in the middle of the signature, not the last one. The
        # last base64 character of an unpadded string carries only part of a
        # byte, so several spellings decode to the same signature — swapping it
        # can leave the decoded bytes identical. That is an encoding artefact
        # rather than a weakness (the attacker already holds a valid token to
        # mangle), but a test that relies on it is testing base64, not HMAC.
        lambda t: t[: len(t) // 2] + ("a" if t[len(t) // 2] != "a" else "b") + t[len(t) // 2 + 1:],
        lambda t: t.split(".")[0] + ".",                      # empty signature
        lambda t: "." + t.split(".")[1],                      # empty payload
        lambda t: t.replace(".", ""),                         # no separator
        lambda t: t + "extra",
        lambda t: "",
        lambda t: "owner_test.owner.9999999999",              # unsigned, plausible-looking
    ])
    def test_a_tampered_token_is_refused(self, secrets, mangle):
        token = token_for(secrets, PILOT)
        assert cohorts.verify_cohort_token(secrets, PILOT, mangle(token)) is None

    def test_changing_the_subject_inside_the_payload_invalidates_it(self, secrets):
        import base64

        token = token_for(secrets, PILOT, subject="owner")
        payload_b64, signature = token.split(".", 1)
        payload = base64.urlsafe_b64decode(payload_b64 + "==").decode()
        forged = payload.replace("owner", "attacker")
        forged_b64 = base64.urlsafe_b64encode(forged.encode()).decode().rstrip("=")
        assert cohorts.verify_cohort_token(secrets, PILOT, f"{forged_b64}.{signature}") is None

    def test_the_public_cohort_cannot_be_tokenised(self, secrets):
        with pytest.raises(ValidationFailed):
            cohorts.issue_cohort_token(
                secrets, PILOT, cohort=cohorts.PUBLIC, subject_id="x"
            )

    def test_ttl_is_bounded(self, secrets):
        with pytest.raises(ValidationFailed):
            token_for(secrets, PILOT, ttl=cohorts.DEFAULT_TTL_SECONDS + 1)
        with pytest.raises(ValidationFailed):
            token_for(secrets, PILOT, ttl=0)


class TestTokenTransportIsCookieOnly:
    @pytest.mark.parametrize("source", ["query", "body"])
    @pytest.mark.parametrize(
        "field", ["cp_cohort", "cohort", "owner_token", "CP_COHORT"]
    )
    def test_a_token_offered_anywhere_but_a_cookie_is_refused(self, secrets, source, field):
        """A secret in a query string lands in logs, Referer and history."""
        resolver = cohorts.CohortResolver(secrets)
        token = token_for(secrets, PILOT)
        with pytest.raises(ValidationFailed):
            resolver.resolve(PILOT, {"cookies": {}, source: {field: token}})

    def test_an_ordinary_query_string_is_not_refused(self, secrets):
        resolver = cohorts.CohortResolver(secrets)
        membership = resolver.resolve(
            PILOT, {"cookies": {}, "query": {"sort": "new", "limit": "20"}}
        )
        assert membership.cohort == cohorts.PUBLIC

    def test_an_ip_address_is_not_the_mechanism(self, secrets):
        """Address is not identity: it changes, it is shared, it cannot be revoked."""
        resolver = cohorts.CohortResolver(secrets)
        membership = resolver.resolve(
            PILOT, {"cookies": {}, "remote_addr": "127.0.0.1", "x_real_ip": "127.0.0.1"}
        )
        assert membership.cohort == cohorts.PUBLIC

    def test_require_owner_test_refuses_a_public_visitor(self, secrets):
        resolver = cohorts.CohortResolver(secrets)
        with pytest.raises(Unauthenticated):
            resolver.require_owner_test(PILOT, {"cookies": {}})


class TestNoSecretLeaks:
    def test_membership_serialisation_carries_no_token(self, secrets):
        resolver = cohorts.CohortResolver(secrets)
        token = token_for(secrets, PILOT)
        membership = resolver.resolve(PILOT, {"cookies": {cohorts.COHORT_COOKIE: token}})
        flat = json.dumps(membership.as_dict())
        assert token not in flat
        assert "expires" not in flat
        assert "subject" not in flat

    def test_the_contract_forbids_the_unsafe_transports(self):
        contract = cohorts.cohort_contract()
        never = " ".join(contract["never"]).lower()
        assert "query string" in never
        assert "request body" in never
        assert "ip allowlist" in never
        assert contract["cookie_attributes"]["HttpOnly"] is True
        assert contract["cookie_attributes"]["Secure"] is True


class TestServiceHonoursTheCohort:
    """The gate has to bite in the service, not only in the flag table."""

    def test_a_public_visitor_is_refused_reads_on_the_pilot(self, store, secrets):
        from factory.comments_platform.rbac import USER, Principal
        from factory.comments_platform.service import CommentsService
        from factory.comments_platform.tenancy import ResourceRef

        registry = SiteRegistry.from_file(CONFIG)
        service = CommentsService(store, registry)
        store.upsert_site(PILOT, module_version="0.1.0-mvp", artifact_checksum="0" * 64)
        store.upsert_policy(PILOT, policy_version="v1")
        principal = Principal(subject_id="g_visitor", role=USER, scope=PILOT)

        with pytest.raises(FeatureDisabled):
            service.thread_view(
                PILOT, principal, ResourceRef("title", "tt-x"), cohort=cohorts.PUBLIC
            )

    def test_the_owner_cohort_may_read_on_the_pilot(self, store):
        from factory.comments_platform.rbac import USER, Principal
        from factory.comments_platform.service import CommentsService
        from factory.comments_platform.tenancy import ResourceRef

        registry = SiteRegistry.from_file(CONFIG)
        service = CommentsService(store, registry)
        store.upsert_site(PILOT, module_version="0.1.0-mvp", artifact_checksum="0" * 64)
        store.upsert_policy(PILOT, policy_version="v1")
        principal = Principal(subject_id="g_owner", role=USER, scope=PILOT)

        view = service.thread_view(
            PILOT, principal, ResourceRef("title", "tt-x"), cohort=cohorts.OWNER_TEST
        )
        assert view.total_count == 0  # empty thread, but served

    def test_the_owner_cohort_is_still_refused_on_the_second_domain(self, store):
        from factory.comments_platform.rbac import USER, Principal
        from factory.comments_platform.service import CommentsService
        from factory.comments_platform.tenancy import ResourceRef

        registry = SiteRegistry.from_file(CONFIG)
        service = CommentsService(store, registry)
        store.upsert_site(SECOND, module_version="0.1.0-mvp", artifact_checksum="0" * 64)
        principal = Principal(subject_id="g_owner", role=USER, scope=SECOND)

        with pytest.raises(FeatureDisabled):
            service.thread_view(
                SECOND, principal, ResourceRef("title", "tt-x"), cohort=cohorts.OWNER_TEST
            )

    def test_a_forgotten_cohort_argument_means_public(self, store):
        """The safe default. A missed call site must fail closed, not open."""
        from factory.comments_platform.rbac import USER, Principal
        from factory.comments_platform.service import CommentsService
        from factory.comments_platform.tenancy import ResourceRef

        registry = SiteRegistry.from_file(CONFIG)
        service = CommentsService(store, registry)
        store.upsert_site(PILOT, module_version="0.1.0-mvp", artifact_checksum="0" * 64)
        principal = Principal(subject_id="g_visitor", role=USER, scope=PILOT)

        with pytest.raises(FeatureDisabled):
            service.thread_view(PILOT, principal, ResourceRef("title", "tt-x"))

    def test_the_kill_switch_closes_the_owner_cohort_too(self, store):
        from factory.comments_platform.rbac import USER, Principal
        from factory.comments_platform.service import CommentsService
        from factory.comments_platform.tenancy import ResourceRef

        registry = SiteRegistry.from_file(CONFIG)
        service = CommentsService(store, registry)
        store.upsert_site(PILOT, module_version="0.1.0-mvp", artifact_checksum="0" * 64)
        principal = Principal(subject_id="g_owner", role=USER, scope=PILOT)

        flags_module.KillSwitch.engage_global()
        try:
            with pytest.raises(FeatureDisabled):
                service.thread_view(
                    PILOT, principal, ResourceRef("title", "tt-x"), cohort=cohorts.OWNER_TEST
                )
        finally:
            flags_module.KillSwitch.release_global()


class TestConstantTimeComparison:
    def test_verification_uses_compare_digest(self):
        import inspect

        source = inspect.getsource(cohorts.verify_cohort_token)
        assert "compare_digest" in source, (
            "a byte-by-byte comparison leaks the signature through timing"
        )

    def test_two_well_formed_tokens_with_wrong_signatures_behave_identically(self, secrets):
        """Both reach the comparison; neither short-circuits on a prefix.

        An earlier version of this test timed a valid-looking token against a
        structurally broken one and asserted the ratio. That measured the
        wrong thing — the broken token fails base64 decoding and returns before
        any HMAC is computed, so the 10x gap was the parser, not a signature
        oracle — and a wall-clock ratio in a unit test is flaky besides. What
        can be asserted without flakiness is that two tokens which both reach
        `compare_digest`, differing in the first signature byte and in the
        last, are refused the same way.
        """
        import base64

        good = token_for(secrets, PILOT)
        payload, signature = good.split(".", 1)
        raw = bytearray(base64.urlsafe_b64decode(signature + "=="))

        def with_byte_flipped(index: int) -> str:
            mutated = bytearray(raw)
            mutated[index] ^= 0xFF
            encoded = base64.urlsafe_b64encode(bytes(mutated)).decode().rstrip("=")
            return f"{payload}.{encoded}"

        first_byte_wrong = with_byte_flipped(0)
        last_byte_wrong = with_byte_flipped(len(raw) - 1)

        assert cohorts.verify_cohort_token(secrets, PILOT, first_byte_wrong) is None
        assert cohorts.verify_cohort_token(secrets, PILOT, last_byte_wrong) is None
        # And the untouched token still verifies, so the harness is sound.
        assert cohorts.verify_cohort_token(secrets, PILOT, good) is not None
