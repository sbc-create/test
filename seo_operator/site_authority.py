"""Site/domain authority for the frequency & relevance policy layer.

There are, today, two disjoint site registries in this repository:

* ``config/portfolio.json`` (``schemas/portfolio-registry.schema.json``) — an
  owner-maintained editorial registry. On this branch it is empty (see its own
  ``note`` field): it describes a future set of sites, not the six that
  already have Topvisor projects.
* ``sites/*/package.yaml``, read through :mod:`seo_operator.factory_bridge` —
  the factory's own site packages. That module's docstring states plainly
  that this is "the single source of truth for which sites exist" from the
  operator's point of view, and that ``config/portfolio.json`` is deliberately
  never inferred from it.

This is the disjoint-authority gap noted in
``docs/seo-operator/frequency-taxonomy-policy.md``: neither registry currently
lists the same sites the other does (``config/site-profiles/yummyani-*.json``
has no matching ``sites/yummyani-*/package.yaml`` on this branch, for
example). Resolving that gap is an owner decision outside this task's scope.

This module does not add a third registry. It binds to the one
``factory_bridge`` already names as authoritative, so this policy layer does
not silently disagree with the rest of the operator about which sites exist.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from seo_operator.factory_bridge import READY, discover_packages, readiness

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Recorded in the manifest's ``site_authority_source`` field so a reader can
#: see, without re-deriving it, which registry was consulted.
SOURCE_NAME = "factory-site-packages"


@dataclass(frozen=True)
class KnownSite:
    site_id: str
    domain: str
    ready: bool


class SiteAuthority:
    """Resolves (site_id, domain) pairs against ``sites/*/package.yaml``."""

    def __init__(self, sites: tuple[KnownSite, ...]) -> None:
        self._by_site_id: dict[str, KnownSite] = {s.site_id: s for s in sites}

    @property
    def source_name(self) -> str:
        return SOURCE_NAME

    def known_site_ids(self) -> frozenset[str]:
        return frozenset(self._by_site_id)

    def resolve(self, site_id: str, domain: str) -> KnownSite | None:
        """Return the known site iff both the id and its domain match. Else None.

        A right site_id with a wrong domain is refused the same as an unknown
        site_id: half-matching input is not a discount on the identity check.
        """
        site = self._by_site_id.get(site_id)
        if site is None:
            return None
        if site.domain != (domain or "").strip().lower():
            return None
        return site


def load_site_authority(root: Path | None = None) -> SiteAuthority:
    root = Path(root or REPO_ROOT)
    sites: list[KnownSite] = []
    for package in discover_packages(root):
        # `.get(key, "")` only falls back when the key is absent. A package
        # with `domain: null` in its YAML has the key present with value
        # None, and `str(None)` is the non-empty string "none" — exactly the
        # kind of false-positive identity this authority must not produce.
        site_id = str(package.get("site_id") or "").strip()
        domain = str(package.get("domain") or "").strip().lower()
        if not site_id or not domain:
            # A package without both a site_id and a domain is not a
            # resolvable identity; it is simply absent from this authority,
            # not present-with-an-empty-domain.
            continue
        sites.append(KnownSite(site_id=site_id, domain=domain, ready=readiness(package) == READY))
    return SiteAuthority(tuple(sites))
