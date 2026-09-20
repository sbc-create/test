"""Unit tests for COMMUNITY-COMMENTS-01 source policy."""

from __future__ import annotations

from pathlib import Path

import pytest

from factory.community.comments_research.policy import (
    assert_source_allowed_for_http,
    is_collectable,
    load_policy,
    sources_by_class,
)

ROOT = Path(__file__).resolve().parents[3]


def test_policy_loads_and_has_required_fields():
    policy = load_policy(str(ROOT))
    assert policy["storage_mode_default"] == "DERIVED_ONLY"
    assert policy["raw_user_identities_stored"] == 0
    required = {
        "source_name",
        "base_url",
        "exact_endpoint_or_feed",
        "content_category",
        "language",
        "access_method",
        "official_api",
        "public_html",
        "robots_status",
        "terms_checked",
        "authentication_required",
        "rate_limit",
        "raw_storage_allowed",
        "derived_analysis_allowed",
        "attribution_required",
        "redistribution_allowed",
        "pii_risk",
        "copyright_risk",
        "policy_class",
        "reason",
        "checked_at",
    }
    for src in policy["sources"]:
        missing = required - set(src)
        assert not missing, f"{src.get('source_name')}: missing {missing}"


def test_blocked_scrapers_are_blocked():
    blocked = {s["source_name"] for s in sources_by_class(ROOT, "BLOCKED")}
    assert "Letterboxd" in blocked
    assert "Kinopoisk" in blocked
    assert "IMDb" in blocked


def test_anilist_is_allowed_api():
    allowed = sources_by_class(ROOT, "ALLOWED_API")
    names = {s["source_name"] for s in allowed}
    assert "AniList Reviews GraphQL" in names
    anilist = next(s for s in allowed if s["source_name"] == "AniList Reviews GraphQL")
    assert anilist["derived_analysis_allowed"] is True
    assert anilist["raw_storage_allowed"] is False
    assert is_collectable(anilist)


def test_blocked_source_raises():
    with pytest.raises(PermissionError):
        assert_source_allowed_for_http(ROOT, "Letterboxd")
