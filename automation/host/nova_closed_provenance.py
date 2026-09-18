#!/usr/bin/env python3
"""Точная provenance-карта закрытых nova-витрин.

source_commit — HEAD профильного worktree (откуда взяты профиль/семейство).
runtime_commit — HEAD worktree, чей automation/host/lords-frontend.py лежит
в /srv/lords/.frontend (общий рантайм на все семейства).

Подменять source_commit значением runtime_commit нельзя: это скрывает, из
какого профильного дерева собрана витрина.
"""

from __future__ import annotations

from typing import TypedDict


class ClosedSiteProvenance(TypedDict):
    site: str
    domain: str
    family: str
    profile: str
    source_commit: str
    runtime_commit: str
    design_version: str
    source_repo: str
    runtime_repo: str


LORDS_COMMIT = "69d56ce2bfab987fa722ce15379a844bb5a2835c"
ANIMEDIA_COMMIT = "b023bd50cced8d281cb3814a75bf72b429afee0b"
ZONA_COMMIT = "a10e68b2350a020a2f7d5efe28cd98ef2fc89edd"

REPO_LORDS = "/home/claude/wt-lords-integration-canary-01"
REPO_ANIMEDIA = "/home/claude/wt-animedia-finalization-01"
REPO_ZONA = "/home/claude/wt-zona-finalization-01"

# Общий lords-frontend.py обслуживает все семейства. Его байты сейчас совпадают
# с Lords/Animedia worktree; Zona worktree держит более старую копию и не
# должна перезаписывать общий рантайм при выкладке только профиля Zona.
RUNTIME_COMMIT = LORDS_COMMIT
RUNTIME_REPO = REPO_LORDS

CLOSED_SITES: tuple[ClosedSiteProvenance, ...] = (
    {
        "site": "lords-02",
        "domain": "lordserial33.biz",
        "family": "lords",
        "profile": "lords-new",
        "source_commit": LORDS_COMMIT,
        "runtime_commit": RUNTIME_COMMIT,
        "design_version": "1.1.0",
        "source_repo": REPO_LORDS,
        "runtime_repo": RUNTIME_REPO,
    },
    {
        "site": "animedia-01",
        "domain": "animedia.icu",
        "family": "animedia",
        "profile": "animedia-general",
        "source_commit": ANIMEDIA_COMMIT,
        "runtime_commit": RUNTIME_COMMIT,
        "design_version": "1.2.0",
        "source_repo": REPO_ANIMEDIA,
        "runtime_repo": RUNTIME_REPO,
    },
    {
        "site": "animedia-02",
        "domain": "animedia.space",
        "family": "animedia",
        "profile": "animedia-general",
        "source_commit": ANIMEDIA_COMMIT,
        "runtime_commit": RUNTIME_COMMIT,
        "design_version": "1.2.0",
        "source_repo": REPO_ANIMEDIA,
        "runtime_repo": RUNTIME_REPO,
    },
    {
        "site": "zona-01",
        "domain": "zonafilm.space",
        "family": "zona",
        "profile": "zona-general",
        "source_commit": ZONA_COMMIT,
        "runtime_commit": RUNTIME_COMMIT,
        "design_version": "1.2.0",
        "source_repo": REPO_ZONA,
        "runtime_repo": RUNTIME_REPO,
    },
)


def by_domain() -> dict[str, ClosedSiteProvenance]:
    return {row["domain"]: row for row in CLOSED_SITES}


def by_site() -> dict[str, ClosedSiteProvenance]:
    return {row["site"]: row for row in CLOSED_SITES}


def build_manifest(
    *,
    family: str,
    design_version: str,
    source_commit: str,
    runtime_commit: str,
    build_id: str,
    artifact_sha256: str,
    profile: str,
    built_at: str,
) -> dict:
    """Манифест витрины: source и runtime разделены явно."""
    return {
        "schema_version": 1,
        "template_family": family,
        "design_version": design_version,
        "source_commit": source_commit,
        "runtime_commit": runtime_commit,
        "build_id": build_id,
        "artifact_sha256": artifact_sha256,
        "profile": profile,
        "built_at": built_at,
    }
