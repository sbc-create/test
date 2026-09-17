"""Tests for the site/domain authority adapter over sites/*/package.yaml."""
from __future__ import annotations

from pathlib import Path

from seo_operator.site_authority import KnownSite, SiteAuthority, load_site_authority

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class TestLoadsFromFactoryPackages:
    def test_known_real_site_resolves(self):
        authority = load_site_authority(REPO_ROOT)
        known = authority.resolve("lords-01", "lordfilm47.space")
        assert known is not None
        assert known.site_id == "lords-01"
        assert known.domain == "lordfilm47.space"

    def test_source_name_is_factory_site_packages(self):
        authority = load_site_authority(REPO_ROOT)
        assert authority.source_name == "factory-site-packages"

    def test_sites_without_a_confirmed_domain_are_not_resolvable(self):
        # sites/animedia-preview/package.yaml has no domain set.
        authority = load_site_authority(REPO_ROOT)
        assert "animedia-preview" not in authority.known_site_ids()


class TestFailsClosedOnUnknownSiteOrDomain:
    def setup_method(self):
        self.authority = SiteAuthority(
            (KnownSite(site_id="lords-01", domain="lordfilm47.space", ready=False),)
        )

    def test_unknown_site_id_is_none(self):
        assert self.authority.resolve("no-such-site", "lordfilm47.space") is None

    def test_known_site_wrong_domain_is_none(self):
        """A right site_id with a wrong domain is not a half-match — it fails closed."""
        assert self.authority.resolve("lords-01", "example.com") is None

    def test_empty_domain_is_none(self):
        assert self.authority.resolve("lords-01", "") is None

    def test_known_site_id_and_domain_resolve(self):
        known = self.authority.resolve("lords-01", "lordfilm47.space")
        assert known is not None
        assert known.ready is False
