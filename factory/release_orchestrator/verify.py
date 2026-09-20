"""Live runtime verification against manifest/registry expectations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


class VerifyError(ValueError):
    pass


Fetch = Callable[[str], dict[str, Any]]


@dataclass
class RuntimeObservation:
    http_status: int = 0
    build_id: str = ""
    source_commit: str = ""
    artifact_sha256: str = ""
    template_family: str = ""
    profile: str = ""
    design_id: str = ""
    domain: str = ""
    catalog_revision: str = ""
    details_revision: str = ""
    catalog_details_skew: int = 0
    player_ok: bool = False
    robots: str = ""
    meta_robots: str = ""
    x_robots_tag: str = ""
    canonical: str = ""
    sitemap: str = ""
    extras: dict[str, Any] = field(default_factory=dict)


def observe(fetch: Fetch, *, version_path: str = "/version.json", home_path: str = "/") -> RuntimeObservation:
    version = fetch(version_path)
    home = fetch(home_path)
    robots = fetch("/robots.txt")
    sitemap = fetch("/sitemap.xml")
    catalog_rev = str(version.get("catalog_revision") or "")
    details_rev = str(version.get("details_revision") or "")
    skew = 0 if catalog_rev == details_rev or not catalog_rev or not details_rev else 1
    return RuntimeObservation(
        http_status=int(home.get("status") or version.get("status") or 0),
        build_id=str(version.get("build_id") or ""),
        source_commit=str(version.get("source_commit") or ""),
        artifact_sha256=str(version.get("artifact_sha256") or ""),
        template_family=str(version.get("template_family") or ""),
        profile=str(version.get("profile") or ""),
        design_id=str(version.get("design_id") or home.get("data_design") or ""),
        domain=str(version.get("domain") or ""),
        catalog_revision=catalog_rev,
        details_revision=details_rev,
        catalog_details_skew=skew,
        player_ok=bool(version.get("player_ok", True)),
        robots=str(robots.get("body") or ""),
        meta_robots=str(home.get("meta_robots") or ""),
        x_robots_tag=str(home.get("x_robots_tag") or ""),
        canonical=str(home.get("canonical") or ""),
        sitemap=str(sitemap.get("status") or ""),
    )


def assert_matches_expected(obs: RuntimeObservation, expected: dict[str, Any]) -> None:
    checks = {
        "build_id": (obs.build_id, expected.get("expected_build_id")),
        "source_commit": (obs.source_commit, expected.get("source_head")),
        "artifact_sha256": (obs.artifact_sha256, expected.get("artifact_sha256")),
        "design_id": (obs.design_id, expected.get("expected_design_id")),
        "domain": (obs.domain, expected.get("domain")),
        "catalog_revision": (obs.catalog_revision, expected.get("expected_catalog_revision")),
        "details_revision": (obs.details_revision, expected.get("expected_details_revision")),
        "profile": (obs.profile, expected.get("template_profile")),
    }
    failures = []
    for name, (actual, want) in checks.items():
        if want is not None and str(actual) != str(want):
            failures.append(f"{name}: actual={actual!r} expected={want!r}")
    if obs.http_status and obs.http_status >= 500:
        failures.append(f"http_status={obs.http_status}")
    if obs.catalog_details_skew:
        failures.append("catalog_details_skew=1")
    if failures:
        raise VerifyError("; ".join(failures))
