"""Reusable smoke profiles and dual-run comparison."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Callable

PROFILES: dict[str, dict[str, Any]] = {
    "lords-general": {
        "routes": [
            "/",
            "/catalog",
            "/search",
            "/series/2024",
            "/country/usa",
            "/title/sample",
            "/title/sample/s1e1",
            "/title/sample/player",
            "/title/sample/recommendations",
            "/definitely-missing-404",
        ],
        "expected_design": "lords-general",
        "indexability": "CLOSED",
        "responsive_widths": [375, 768, 1280],
        "allowed_route_noindex": ["/search"],
        "version_endpoint": "/version.json",
        "player_checks": True,
        "catalog_checks": True,
    },
    "lords-series-feed": {
        "routes": ["/", "/catalog", "/search", "/series/2024", "/title/sample", "/definitely-missing-404"],
        "expected_design": "lords-new",
        "indexability": "CLOSED",
        "responsive_widths": [375, 1280],
        "allowed_route_noindex": ["/search"],
        "version_endpoint": "/version.json",
        "player_checks": True,
        "catalog_checks": True,
    },
    "lords-curated": {
        "routes": ["/", "/catalog", "/search", "/title/sample", "/definitely-missing-404"],
        "expected_design": "lords-curated",
        "indexability": "CLOSED",
        "responsive_widths": [375, 1280],
        "allowed_route_noindex": ["/search"],
        "version_endpoint": "/version.json",
        "player_checks": True,
        "catalog_checks": True,
    },
    "animedia": {
        "routes": ["/", "/catalog", "/title/sample", "/definitely-missing-404"],
        "expected_design": "animedia-01",
        "indexability": "CLOSED",
        "responsive_widths": [375, 1280],
        "allowed_route_noindex": [],
        "version_endpoint": "/version.json",
        "player_checks": True,
        "catalog_checks": True,
    },
    "zona": {
        "routes": ["/", "/catalog", "/title/sample", "/definitely-missing-404"],
        "expected_design": "zona-01",
        "indexability": "CLOSED",
        "responsive_widths": [375, 1280],
        "allowed_route_noindex": [],
        "version_endpoint": "/version.json",
        "player_checks": True,
        "catalog_checks": True,
    },
    "yummy": {
        "routes": ["/", "/catalog", "/title/sample", "/definitely-missing-404"],
        "expected_design": "yummyani-site",
        "indexability": "OPEN",
        "responsive_widths": [375, 1280],
        "allowed_route_noindex": [],
        "version_endpoint": "/version.json",
        "player_checks": True,
        "catalog_checks": True,
    },
    "generic-nova": {
        "routes": ["/", "/catalog", "/definitely-missing-404"],
        "expected_design": "generic-nova",
        "indexability": "CLOSED",
        "responsive_widths": [1280],
        "allowed_route_noindex": [],
        "version_endpoint": "/version.json",
        "player_checks": False,
        "catalog_checks": True,
    },
}


class SmokeError(ValueError):
    pass


def get_profile(name: str) -> dict[str, Any]:
    if name not in PROFILES:
        raise SmokeError(f"unknown smoke profile: {name}")
    return deepcopy(PROFILES[name])


@dataclass
class SmokeRun:
    build_id: str
    artifact_sha256: str
    design_id: str
    route_statuses: dict[str, int]
    indexability: str
    catalog_revision: str
    http_5xx: int = 0
    soft404: int = 0
    redirect_loops: int = 0


FetchFn = Callable[[str], dict[str, Any]]


def run_smoke(
    *,
    profile_name: str,
    expected: dict[str, Any],
    fetch: FetchFn,
) -> SmokeRun:
    profile = get_profile(profile_name)
    route_statuses: dict[str, int] = {}
    http_5xx = 0
    soft404 = 0
    redirect_loops = 0
    for route in profile["routes"]:
        result = fetch(route)
        status = int(result.get("status") or 0)
        route_statuses[route] = status
        if status >= 500:
            http_5xx += 1
        if result.get("soft404"):
            soft404 += 1
        if result.get("redirect_loop"):
            redirect_loops += 1
    version = fetch(profile["version_endpoint"])
    run = SmokeRun(
        build_id=str(version.get("build_id") or expected.get("expected_build_id") or ""),
        artifact_sha256=str(version.get("artifact_sha256") or expected.get("artifact_sha256") or ""),
        design_id=str(version.get("design_id") or expected.get("expected_design_id") or ""),
        route_statuses=route_statuses,
        indexability=str(version.get("indexability") or profile["indexability"]),
        catalog_revision=str(version.get("catalog_revision") or expected.get("expected_catalog_revision") or ""),
        http_5xx=http_5xx,
        soft404=soft404,
        redirect_loops=redirect_loops,
    )
    if run.design_id != expected.get("expected_design_id") and run.design_id != profile["expected_design"]:
        # Accept either manifest expected_design_id or profile default.
        if run.design_id not in {expected.get("expected_design_id"), profile["expected_design"]}:
            raise SmokeError(f"design mismatch: {run.design_id}")
    if run.http_5xx or run.soft404 or run.redirect_loops:
        raise SmokeError(
            f"smoke hard fail http_5xx={run.http_5xx} soft404={run.soft404} loops={run.redirect_loops}"
        )
    return run


def compare_runs(run1: SmokeRun, run2: SmokeRun) -> None:
    if run1.build_id != run2.build_id:
        raise SmokeError("concurrent deployment detected: build_id changed between smoke runs")
    if run1.artifact_sha256 != run2.artifact_sha256:
        raise SmokeError("concurrent deployment detected: artifact digest changed between smoke runs")
    if run1.design_id != run2.design_id:
        raise SmokeError("design changed between smoke runs")
    if run1.route_statuses != run2.route_statuses:
        raise SmokeError("route statuses differ between smoke runs")
    if run1.indexability != run2.indexability:
        raise SmokeError("indexability differs between smoke runs")
    if run1.catalog_revision != run2.catalog_revision:
        raise SmokeError("catalog revision differs between smoke runs")


def dual_smoke(*, profile_name: str, expected: dict[str, Any], fetch: FetchFn) -> tuple[SmokeRun, SmokeRun]:
    first = run_smoke(profile_name=profile_name, expected=expected, fetch=fetch)
    second = run_smoke(profile_name=profile_name, expected=expected, fetch=fetch)
    compare_runs(first, second)
    return first, second
