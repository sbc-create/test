"""Community spaces and actor identity (Animedia shared, Yummy isolated)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ActorKind(str, Enum):
    ACCOUNT = "authenticated_account"
    SIGNED_GUEST = "signed_guest"
    MERGED = "merged_canonical"


@dataclass(frozen=True)
class BrandSite:
    brand_id: str
    site_id: str
    rating_space_id: str
    discussion_space_id: str
    domains: tuple[str, ...]


# Owner-confirmed: both Animedia domains share one rating space.
ANIMEDIA_SITES: tuple[BrandSite, ...] = (
    BrandSite(
        brand_id="animedia",
        site_id="animedia-01",
        rating_space_id="animedia",
        discussion_space_id="animedia",
        domains=("animedia.icu",),
    ),
    BrandSite(
        brand_id="animedia",
        site_id="animedia-02",
        rating_space_id="animedia",
        discussion_space_id="animedia",
        domains=("animedia.space",),
    ),
)

YUMMY_SITES: tuple[BrandSite, ...] = (
    BrandSite(
        brand_id="yummy",
        site_id="yummyani-site",
        rating_space_id="yummy",
        discussion_space_id="yummy",
        domains=("yummyani.site",),
    ),
    BrandSite(
        brand_id="yummy",
        site_id="yummyani-org",
        rating_space_id="yummy",
        discussion_space_id="yummy",
        domains=("yummyani.org",),
    ),
    BrandSite(
        brand_id="yummy",
        site_id="yummyani-biz",
        rating_space_id="yummy",
        discussion_space_id="yummy",
        domains=("yummyani.biz",),
    ),
)


def rating_space_for_site(site_id: str) -> str:
    for row in (*ANIMEDIA_SITES, *YUMMY_SITES):
        if row.site_id == site_id:
            return row.rating_space_id
    raise KeyError(f"unknown site_id={site_id}")


def rating_space_for_domain(domain: str) -> str:
    d = domain.lower().strip()
    for row in (*ANIMEDIA_SITES, *YUMMY_SITES):
        if d in row.domains:
            return row.rating_space_id
    raise KeyError(f"unknown domain={domain}")


@dataclass
class Actor:
    """Identity abstraction. IP/fingerprint are never actor_id."""

    actor_id: str
    kind: ActorKind
    account_id: str = ""
    site_profile_id: str = ""
    merged_into: str = ""

    def canonical_actor_id(self) -> str:
        return self.merged_into or self.actor_id

    def as_dict(self) -> dict[str, Any]:
        return {
            "actor_id": self.actor_id,
            "kind": self.kind.value,
            "account_id": self.account_id,
            "site_profile_id": self.site_profile_id,
            "merged_into": self.merged_into,
            "canonical_actor_id": self.canonical_actor_id(),
        }


def merge_guest_into_account(*, guest: Actor, account: Actor) -> Actor:
    """Guest-to-account merge → one canonical actor (account)."""
    if account.kind != ActorKind.ACCOUNT:
        raise ValueError("merge target must be authenticated_account")
    return Actor(
        actor_id=account.actor_id,
        kind=ActorKind.MERGED,
        account_id=account.account_id or account.actor_id,
        site_profile_id=account.site_profile_id,
        merged_into=account.actor_id,
    )


def spaces_matrix() -> dict[str, Any]:
    return {
        "animedia_shared_across_icu_space": True,
        "yummy_isolated": True,
        "yummy_cannot_mutate_animedia_native": True,
        "hostname_auto_merge_forbidden": True,
        "ip_is_not_identity": True,
        "device_fingerprint_is_not_proof": True,
        "sites": [s.__dict__ | {"domains": list(s.domains)} for s in (*ANIMEDIA_SITES, *YUMMY_SITES)],
    }
