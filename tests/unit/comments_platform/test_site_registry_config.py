"""The shipped site registry: real sites, pinned artifacts, every gate dark."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from factory.comments_platform import flags as flags_module
from factory.comments_platform.flags import FlagResolver, assert_dark
from factory.comments_platform.tenancy import ALLOWED_TENANTS, SiteRegistry

REPO = Path(__file__).resolve().parents[3]
CONFIG = REPO / "config" / "comments-platform" / "sites.json"
FLEET = REPO / "config" / "FLEET-REGISTRY.json"
WIDGET_DIR = REPO / "factory" / "comments_platform" / "widget"


@pytest.fixture(scope="module")
def raw() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def shipped_registry() -> SiteRegistry:
    return SiteRegistry.from_file(CONFIG)


class TestSitesAreReal:
    def test_every_site_and_domain_comes_from_the_fleet_registry(self, raw):
        """No invented hosts.

        The fleet registry is built from live release manifests and site
        packages, so it is the only place a domain may come from. A hostname
        that appears here and not there is a guess, and a guess in a CORS
        allowlist is a security defect.
        """
        fleet = json.loads(FLEET.read_text(encoding="utf-8"))["fleet"]
        known = {(e["family"], e["site_id"], e["domain"]) for e in fleet}
        for site in raw["sites"]:
            triple = (site["tenant_id"], site["site_id"], site["hosts"][0])
            assert triple in known, f"{triple} is not in config/FLEET-REGISTRY.json"

    def test_every_fleet_site_of_an_allowed_tenant_is_bound(self, raw):
        fleet = json.loads(FLEET.read_text(encoding="utf-8"))["fleet"]
        expected = {e["site_id"] for e in fleet if e["family"] in ALLOWED_TENANTS}
        actual = {s["site_id"] for s in raw["sites"]}
        assert actual == expected, f"missing {sorted(expected - actual)}"

    def test_tenants_are_the_four_allowed_families(self, raw):
        assert {s["tenant_id"] for s in raw["sites"]} == set(ALLOWED_TENANTS)

    def test_the_registry_loads_without_error(self, shipped_registry):
        assert len(shipped_registry.all_bindings()) == 9


class TestEveryGateIsDark:
    def test_only_the_authorised_pilot_site_may_carry_a_non_zero_gate(self, raw):
        """The config value is one of two keys, and only one site holds it.

        This test used to assert that every gate in the file was 0, which was
        true before Stage 1 and is no longer the invariant worth protecting.
        The real one is narrower and stronger: a value of 1 is permitted on
        exactly the site the owner authorised, and nowhere else. The public
        experience is protected by the cohort ceiling, asserted below.
        """
        authorised = {s for _, s in flags_module.PILOT_SITES}
        for site in raw["sites"]:
            for gate in ("read_enabled", "write_enabled", "publication_enabled"):
                if site[gate] != 0:
                    assert site["site_id"] in authorised, (
                        f"{site['site_id']}: {gate}={site[gate]} but the site is not in PILOT_SITES"
                    )
            # A public traffic dial is never opened by this stage, on any site.
            assert site["rollout_percent"] == 0, f"{site['site_id']}: rollout is not 0"
            # SSR would put comment text where a crawler reads it.
            assert site["seo_mode"] == "user_initiated"

    def test_the_second_animedia_domain_is_entirely_untouched(self, raw):
        """animedia.space shares a release with animedia.icu and must stay dark."""
        second = next(s for s in raw["sites"] if s["site_id"] == "animedia-02")
        for gate in ("read_enabled", "write_enabled", "publication_enabled", "rollout_percent"):
            assert second[gate] == 0, f"animedia-02: {gate} is {second[gate]}"

    def test_the_public_cohort_is_dark_on_every_site_including_the_pilot(
        self, shipped_registry
    ):
        """The property an ordinary visitor actually experiences."""
        resolver = FlagResolver()
        for binding in shipped_registry.all_bindings():
            assert_dark(resolver.resolve_for_cohort(binding, "public"))
            # And `resolve` without a cohort must mean the public one.
            assert_dark(resolver.resolve(binding))

    def test_the_owner_cohort_is_open_on_the_pilot_site_and_nowhere_else(
        self, shipped_registry
    ):
        resolver = FlagResolver()
        authorised = {s for _, s in flags_module.PILOT_SITES}
        for binding in shipped_registry.all_bindings():
            effective = resolver.resolve_for_cohort(binding, "owner_test")
            if binding.site_id in authorised:
                assert effective.read_enabled == 1
                assert effective.write_enabled == 1
                assert effective.publication_enabled == 1
            else:
                assert effective.read_enabled == 0, binding.site_id
                assert effective.write_enabled == 0, binding.site_id
                assert effective.publication_enabled == 0, binding.site_id
            # Never, on any site, in any cohort, in this stage.
            assert effective.ssr_enabled == 0
            assert effective.rollout_percent == 0

    def test_the_pilot_allowlist_names_exactly_the_authorised_domain(self, raw):
        assert flags_module.PILOT_SITES == (("animedia", "animedia-01"),)
        pilot = next(s for s in raw["sites"] if s["site_id"] == "animedia-01")
        assert pilot["hosts"] == ["animedia.icu"]

    def test_a_stray_one_in_the_config_would_still_resolve_dark(self, raw):
        """The cohort ceiling is the real gate for the public.

        If somebody edits this file to enable reading on all nine sites, the
        public ceiling in flags.py clamps every one of them back to zero. An
        ordinary visitor is protected by source, not by a config row somebody
        might edit in a hurry.
        """
        mutated = json.loads(json.dumps(raw))
        for site in mutated["sites"]:
            site["read_enabled"] = 1
            site["write_enabled"] = 1
            site["publication_enabled"] = 1
            site["rollout_percent"] = 100
        registry = SiteRegistry.from_mapping(mutated)
        resolver = FlagResolver()
        for binding in registry.all_bindings():
            effective = resolver.resolve_for_cohort(binding, "public")
            assert effective.read_enabled == 0, binding.site_id
            assert effective.write_enabled == 0, binding.site_id
            assert effective.publication_enabled == 0, binding.site_id
            assert effective.rollout_percent == 0, binding.site_id


class TestArtifactPinning:
    def test_no_site_uses_a_floating_version(self, raw):
        for site in raw["sites"]:
            assert site["module_version"] not in ("latest", "main", "HEAD", "", "stable")

    def test_every_checksum_is_a_sha256(self, raw):
        for site in raw["sites"]:
            checksum = site["artifact_checksum"]
            assert len(checksum) == 64
            assert all(c in "0123456789abcdef" for c in checksum)

    def test_all_sites_pin_the_same_artifact(self, raw):
        """One module, one build. Divergence here means somebody forked it."""
        assert len({s["artifact_checksum"] for s in raw["sites"]}) == 1
        assert len({s["module_version"] for s in raw["sites"]}) == 1

    def test_the_committed_checksum_matches_the_files_on_disk(self):
        result = subprocess.run(
            [sys.executable, "scripts/comments_platform_artifact.py", "--check"],
            cwd=REPO, capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr

    def test_changing_a_widget_byte_changes_the_digest(self, tmp_path):
        """The digest must actually depend on the content it claims to cover."""
        sys.path.insert(0, str(REPO / "scripts"))
        import comments_platform_artifact as artifact

        before = artifact.compute_checksum()
        target = WIDGET_DIR / "comments-widget.js"
        original = target.read_bytes()
        try:
            target.write_bytes(original + b"\n// a stray byte\n")
            assert artifact.compute_checksum() != before
        finally:
            target.write_bytes(original)
        assert artifact.compute_checksum() == before


class TestOriginsAreExact:
    def test_no_wildcard_or_http_origin(self, raw):
        for site in raw["sites"]:
            for origin in site["allowed_origins"]:
                assert "*" not in origin, f"{site['site_id']}: wildcard origin"
                assert origin.startswith("https://"), f"{site['site_id']}: {origin} is not https"
                assert not origin.endswith("/")

    def test_each_origin_matches_its_own_host(self, raw):
        for site in raw["sites"]:
            hosts = set(site["hosts"])
            for origin in site["allowed_origins"]:
                host = origin.split("://", 1)[1]
                assert host in hosts, f"{site['site_id']}: {origin} is not one of its hosts"

    def test_no_host_is_claimed_by_two_sites(self, shipped_registry):
        # SiteRegistry refuses this at construction; asserting it here states
        # why the shipped file is safe rather than leaving it implied.
        seen = set()
        for binding in shipped_registry.all_bindings():
            for host in binding.hosts:
                assert host not in seen
                seen.add(host)


class TestNoWidgetSourceInTenantTemplates:
    def test_the_widget_lives_in_exactly_one_place(self):
        """Copying the widget into a theme is the failure this module prevents."""
        copies = []
        for pattern in ("comments-widget.js", "comments-widget.css"):
            for path in REPO.rglob(pattern):
                if ".git" in path.parts or "node_modules" in path.parts:
                    continue
                if path.parent != WIDGET_DIR:
                    copies.append(str(path.relative_to(REPO)))
        assert not copies, f"widget copies found outside its home: {copies}"

    def test_no_theme_or_template_embeds_the_widget_global(self):
        offenders = []
        for directory in ("themes", "blueprints", "config/site-profiles"):
            root = REPO / directory
            if not root.exists():
                continue
            for path in root.rglob("*"):
                if not path.is_file() or path.suffix not in (".js", ".html", ".css", ".tsx", ".ts"):
                    continue
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                if "SiteFactoryComments" in text and "mount" not in text:
                    offenders.append(str(path.relative_to(REPO)))
        assert not offenders, f"widget internals referenced in templates: {offenders}"
