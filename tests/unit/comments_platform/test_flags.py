"""Flags: off by default, lowerable from outside, never raisable from outside."""

from __future__ import annotations

import hashlib

import pytest

from factory.comments_platform import flags
from factory.comments_platform.tenancy import SiteBinding, TenantScope

CHECKSUM = hashlib.sha256(b"artifact").hexdigest()


def binding(tenant="lords", site="lords-main", **over) -> SiteBinding:
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


@pytest.fixture(autouse=True)
def _clean_switches(monkeypatch):
    flags.KillSwitch.release_global()
    for name in (
        "COMMENTS_READ_ENABLED", "COMMENTS_WRITE_ENABLED", "COMMENTS_PUBLICATION_ENABLED",
        "COMMENTS_ROLLOUT_PERCENT", "COMMENTS_SSR_ENABLED", "COMMENTS_KILL_SWITCH",
    ):
        monkeypatch.delenv(name, raising=False)
    yield
    flags.KillSwitch.release_global()


class TestSafeDefaults:
    def test_everything_is_off_for_a_fresh_site(self):
        effective = flags.FlagResolver().resolve(binding())
        assert effective.read_enabled == 0
        assert effective.write_enabled == 0
        assert effective.publication_enabled == 0
        assert effective.rollout_percent == 0
        assert effective.ssr_enabled == 0
        assert not effective.reads_allowed
        assert not effective.writes_allowed

    def test_assert_dark_passes_on_defaults(self):
        flags.assert_dark(flags.FlagResolver().resolve(binding()))


class TestCeilingsCannotBeRaised:
    @pytest.mark.parametrize(
        "env,attr",
        [
            ("COMMENTS_READ_ENABLED", "read_enabled"),
            ("COMMENTS_WRITE_ENABLED", "write_enabled"),
            ("COMMENTS_PUBLICATION_ENABLED", "publication_enabled"),
            ("COMMENTS_SSR_ENABLED", "ssr_enabled"),
        ],
    )
    def test_environment_cannot_light_a_gate(self, monkeypatch, env, attr):
        monkeypatch.setenv(env, "1")
        effective = flags.FlagResolver().resolve(binding())
        assert getattr(effective, attr) == 0, f"{env} escaped its ceiling"

    def test_environment_cannot_raise_rollout(self, monkeypatch):
        monkeypatch.setenv("COMMENTS_ROLLOUT_PERCENT", "100")
        assert flags.FlagResolver().resolve(binding()).rollout_percent == 0

    def test_configuration_cannot_light_a_gate_past_the_ceiling(self):
        """Even a site row claiming publication stays dark in this stage."""
        effective = flags.FlagResolver().resolve(
            binding(read_enabled=1, write_enabled=1, publication_enabled=1, rollout_percent=100)
        )
        assert effective.read_enabled == 0
        assert effective.write_enabled == 0
        assert effective.publication_enabled == 0
        assert effective.rollout_percent == 0

    def test_garbage_environment_value_is_ignored(self, monkeypatch):
        monkeypatch.setenv("COMMENTS_READ_ENABLED", "yes-please")
        assert flags.FlagResolver().resolve(binding()).read_enabled == 0

    def test_negative_environment_value_cannot_go_below_zero(self, monkeypatch):
        monkeypatch.setenv("COMMENTS_READ_ENABLED", "-5")
        assert flags.FlagResolver().resolve(binding()).read_enabled == 0


class TestOverridesOnlyLower:
    def test_operator_override_cannot_raise(self):
        resolver = flags.FlagResolver()
        resolver.set_site_override(TenantScope("lords", "lords-main"), read_enabled=1)
        assert resolver.resolve(binding()).read_enabled == 0

    def test_operator_override_lowers_independently_per_site(self):
        resolver = flags.FlagResolver()
        resolver.set_site_override(TenantScope("lords", "lords-main"), kill_switch=1)
        lords = resolver.resolve(binding("lords", "lords-main"))
        zona = resolver.resolve(binding("zona", "zona-main"))
        assert lords.kill_switch_site == 1
        assert zona.kill_switch_site == 0, "one tenant's incident darkened another"


class TestKillSwitch:
    def test_global_switch_stops_reads_and_writes_everywhere(self):
        flags.KillSwitch.engage_global()
        effective = flags.FlagResolver().resolve(binding())
        assert effective.any_kill_switch
        assert not effective.writes_allowed
        assert not effective.reads_allowed

    def test_environment_may_engage_the_switch(self, monkeypatch):
        """Opposite direction to feature flags: safety may be raised, not lowered."""
        monkeypatch.setenv("COMMENTS_KILL_SWITCH", "1")
        assert flags.FlagResolver().resolve(binding()).kill_switch_global == 1

    def test_switch_state_is_read_fresh_not_cached(self):
        resolver = flags.FlagResolver()
        assert resolver.resolve(binding()).kill_switch_global == 0
        flags.KillSwitch.engage_global()
        assert resolver.resolve(binding()).kill_switch_global == 1
        flags.KillSwitch.release_global()
        assert resolver.resolve(binding()).kill_switch_global == 0


class TestSsrFollowsPublication:
    def test_ssr_mode_alone_does_not_render_comments(self):
        effective = flags.FlagResolver().resolve(binding(seo_mode="ssr_first_page"))
        assert effective.ssr_enabled == 0, "SSR published comments without publication"


class TestForbiddenCapabilities:
    @pytest.mark.parametrize("name", sorted(flags.PERMANENTLY_FORBIDDEN))
    def test_forbidden_capability_is_recognised(self, name):
        assert flags.forbidden_capability(name)

    def test_shadow_ban_is_forbidden(self):
        assert "ADMIN_SHADOW_BAN" in flags.PERMANENTLY_FORBIDDEN

    def test_comments_may_never_affect_ratings(self):
        assert "COMMENTS_AFFECT_RATINGS" in flags.PERMANENTLY_FORBIDDEN


class TestAssertDark:
    def test_assert_dark_raises_if_a_gate_is_lit(self):
        lit = flags.EffectiveFlags(
            tenant_id="lords", site_id="lords-main", read_enabled=1, write_enabled=0,
            publication_enabled=0, rollout_percent=0, ssr_enabled=0,
            seo_mode="user_initiated", moderation_mode="pre",
            kill_switch_global=0, kill_switch_site=0,
        )
        with pytest.raises(RuntimeError):
            flags.assert_dark(lit)
