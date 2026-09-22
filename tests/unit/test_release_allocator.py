"""Allocator: new site identifiers are derived from registries, never guessed.

Every test here fixes one way the allocator could invent a value. The point of
the module is that `zona-02`, `nova-zona-02.service` and a port are *conclusions*
drawn from four independent sources, and that the allocator refuses when the
sources do not support a conclusion.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.release_orchestrator.allocator import (
    AllocationError,
    NOVA_PORT_BAND,
    allocate,
    collect_claims,
)


# ---------------------------------------------------------------------------
# Fixtures: a miniature of the live fleet
# ---------------------------------------------------------------------------
def _profile(site_id: str, domain: str, family: str) -> dict:
    return {"schema_version": "1.0", "site_id": site_id, "domains": [domain], "family": family}


@pytest.fixture()
def fleet(tmp_path: Path) -> dict:
    profiles = tmp_path / "config" / "site-profiles"
    profiles.mkdir(parents=True)
    for site_id, domain, family in (
        ("lords-01", "lordfilm47.space", "lords"),
        ("zona-01", "zonafilm.space", "zona"),
        ("animedia-01", "animedia.icu", "animedia"),
        ("animedia-02", "animedia.space", "animedia"),
    ):
        (profiles / f"{site_id}.json").write_text(
            json.dumps(_profile(site_id, domain, family)), encoding="utf-8"
        )

    registry = tmp_path / "config" / "release-registry.json"
    registry.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "registry_id": "test",
                "sites": [
                    {"site_id": "lords-01", "domain": "lordfilm47.space",
                     "site_family": "lords", "service_name": "lords-nova-01.service"},
                    {"site_id": "zona-01", "domain": "zonafilm.space",
                     "site_family": "zona", "service_name": "nova-zona-01.service"},
                    {"site_id": "animedia-01", "domain": "animedia.icu",
                     "site_family": "animedia", "service_name": "nova-animedia-01.service"},
                    {"site_id": "animedia-02", "domain": "animedia.space",
                     "site_family": "animedia", "service_name": "nova-animedia-02.service"},
                ],
            }
        ),
        encoding="utf-8",
    )

    runtime = tmp_path / "lords-runtime-registry.json"
    runtime.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "sites": {
                    "lords-01": {"site_id": "lords-01", "family": "lords", "port": 9110,
                                 "unit": "lords-nova-01.service"},
                    "zona-01": {"site_id": "zona-01", "family": "zona", "port": 9120,
                                "unit": "nova-zona-01.service"},
                    "animedia-01": {"site_id": "animedia-01", "family": "animedia", "port": 9121,
                                    "unit": "nova-animedia-01.service"},
                    "animedia-02": {"site_id": "animedia-02", "family": "animedia", "port": 9122,
                                    "unit": "nova-animedia-02.service"},
                },
            }
        ),
        encoding="utf-8",
    )

    units = tmp_path / "systemd"
    units.mkdir()
    (units / "lords-nova-01.service").write_text(
        "[Service]\nExecStart=/usr/bin/python3 /srv/lords/.frontend/lords-frontend.py --port 9110\n",
        encoding="utf-8",
    )
    (units / "nova-zona-01.service").write_text(
        "[Service]\nExecStart=/usr/bin/python3 /srv/lords/.frontend/lords-frontend.py --port 9120\n",
        encoding="utf-8",
    )
    (units / "nova-animedia-01.service").write_text(
        "[Service]\nExecStart=/usr/bin/python3 /srv/lords/.frontend/lords-frontend.py --port 9121\n",
        encoding="utf-8",
    )
    (units / "nova-animedia-02.service").write_text(
        "[Service]\nExecStart=/usr/bin/python3 /srv/lords/.frontend/lords-frontend.py --port 9122\n",
        encoding="utf-8",
    )
    return {
        "profiles_dir": profiles,
        "registry_path": registry,
        "runtime_registry_path": runtime,
        "unit_dir": units,
    }


def _allocate(fleet: dict, family: str = "zona", *, listening=frozenset()):
    return allocate(family, listening_ports=listening, **fleet)


# ---------------------------------------------------------------------------
# site_id
# ---------------------------------------------------------------------------
def test_site_id_is_next_free_ordinal_in_family(fleet):
    assert _allocate(fleet).site_id == "zona-02"


def test_site_id_skips_an_ordinal_claimed_by_any_single_source(fleet, tmp_path):
    """One source claiming zona-02 is enough to move on. Sources are unioned."""
    runtime = json.loads(fleet["runtime_registry_path"].read_text())
    runtime["sites"]["zona-02"] = {"site_id": "zona-02", "family": "zona", "port": 9123,
                                   "unit": "nova-zona-02.service"}
    fleet["runtime_registry_path"].write_text(json.dumps(runtime), encoding="utf-8")
    assert _allocate(fleet).site_id == "zona-03"


def test_unknown_family_is_refused_not_invented(fleet):
    with pytest.raises(AllocationError) as excinfo:
        _allocate(fleet, family="novaflix")
    assert "novaflix" in str(excinfo.value)


# ---------------------------------------------------------------------------
# service_name
# ---------------------------------------------------------------------------
def test_service_name_follows_the_family_pattern_actually_on_disk(fleet):
    assert _allocate(fleet).service_name == "nova-zona-02.service"


def test_service_name_pattern_is_read_from_the_family_not_assumed(fleet):
    """lords uses `lords-nova-01.service`; the allocator must not force `nova-`."""
    assert _allocate(fleet, family="lords").service_name == "lords-nova-02.service"


def test_sources_disagreeing_about_a_family_unit_is_refused_not_resolved(fleet):
    """The live fleet has exactly this drift: the ops overlay names a legacy unit
    (`zona-01.service`, the old static site on another port) while the dispatcher
    registry and the installed unit name `nova-zona-01.service`. Silently taking
    either one would have a new site inherit the wrong naming scheme."""
    registry = json.loads(fleet["registry_path"].read_text())
    for entry in registry["sites"]:
        if entry["site_id"] == "zona-01":
            entry["service_name"] = "zona-01.service"
    fleet["registry_path"].write_text(json.dumps(registry), encoding="utf-8")
    with pytest.raises(AllocationError) as excinfo:
        _allocate(fleet)
    message = str(excinfo.value)
    assert "zona-01.service" in message and "nova-zona-01.service" in message


def test_an_explicit_source_resolves_the_drift_without_guessing(fleet):
    registry = json.loads(fleet["registry_path"].read_text())
    for entry in registry["sites"]:
        if entry["site_id"] == "zona-01":
            entry["service_name"] = "zona-01.service"
    fleet["registry_path"].write_text(json.dumps(registry), encoding="utf-8")
    allocation = allocate("zona", listening_ports=frozenset(),
                          service_name_source="runtime_registry", **fleet)
    assert allocation.service_name == "nova-zona-02.service"
    assert allocation.evidence["service_name_source"] == "runtime_registry"
    assert allocation.evidence["service_name_drift"]["zona-01"] == {
        "release_registry": "zona-01.service",
        "runtime_registry": "nova-zona-01.service",
    }


def test_an_explicit_source_that_does_not_know_the_family_is_refused(fleet):
    with pytest.raises(AllocationError) as excinfo:
        allocate("zona", listening_ports=frozenset(),
                 service_name_source="nonexistent_source", **fleet)
    assert "nonexistent_source" in str(excinfo.value)


def test_service_name_collision_with_an_existing_unit_is_refused(fleet):
    (fleet["unit_dir"] / "nova-zona-02.service").write_text("[Service]\n", encoding="utf-8")
    with pytest.raises(AllocationError) as excinfo:
        _allocate(fleet)
    assert "nova-zona-02.service" in str(excinfo.value)


# ---------------------------------------------------------------------------
# port
# ---------------------------------------------------------------------------
def test_port_is_next_free_at_or_above_the_family_base(fleet):
    """zona base is 9120; 9121 is animedia's, so the first free slot is 9123."""
    assert _allocate(fleet).port == 9123


def test_port_skips_a_listening_socket_even_when_no_registry_claims_it(fleet):
    assert _allocate(fleet, listening=frozenset({9123})).port == 9124


def test_port_skips_a_port_only_visible_in_a_unit_file(fleet):
    (fleet["unit_dir"] / "unrelated-thing.service").write_text(
        "[Service]\nExecStart=/usr/bin/python3 /opt/x.py --port 9123\n", encoding="utf-8"
    )
    assert _allocate(fleet).port == 9124


def test_exhausted_band_is_refused_not_wrapped(fleet):
    taken = frozenset(range(NOVA_PORT_BAND[0], NOVA_PORT_BAND[1] + 1))
    with pytest.raises(AllocationError) as excinfo:
        _allocate(fleet, listening=taken)
    assert "band" in str(excinfo.value).lower()


# ---------------------------------------------------------------------------
# evidence
# ---------------------------------------------------------------------------
def test_allocation_records_every_source_it_consulted(fleet):
    allocation = _allocate(fleet)
    sources = allocation.evidence["sources"]
    assert set(sources) == {
        "site_profiles", "release_registry", "runtime_registry", "systemd_units", "listening_ports"
    }
    # Each identifier must name the sources that could have contradicted it.
    assert allocation.evidence["site_id_claims"]["zona"] == ["zona-01"]
    assert 9120 in allocation.evidence["claimed_ports"]


def test_collect_claims_unions_all_sources(fleet):
    claims = collect_claims(listening_ports=frozenset({9999}), **fleet)
    assert "zona-01" in claims.site_ids
    assert "nova-zona-01.service" in claims.service_names
    assert {9110, 9120, 9121, 9999} <= claims.ports


# ---------------------------------------------------------------------------
# domain safety: the allocator must never hand out an identifier already bound
# to a different domain, because that is how one site overwrites another.
# ---------------------------------------------------------------------------
def test_domain_already_registered_is_refused(fleet):
    with pytest.raises(AllocationError) as excinfo:
        allocate("zona", domain="zonafilm.space", listening_ports=frozenset(), **fleet)
    assert "zonafilm.space" in str(excinfo.value)


def test_fresh_domain_is_accepted_and_recorded(fleet):
    allocation = allocate("zona", domain="zonafilm.cc", listening_ports=frozenset(), **fleet)
    assert allocation.domain == "zonafilm.cc"
    assert allocation.site_id == "zona-02"
