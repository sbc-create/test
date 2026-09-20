"""COMMUNITY-COMMENTS-01 research corpus — DERIVED_ONLY language/structure analysis.

Never republishes external comments. Never inserts into production comment tables.
Default storage is digests/labels/templates only (STORAGE_MODE=DERIVED_ONLY).
"""

from __future__ import annotations

__all__ = [
    "POLICY_PATH",
    "STORAGE_MODE_DEFAULT",
]

STORAGE_MODE_DEFAULT = "DERIVED_ONLY"
POLICY_PATH = "docs/community_comments/SOURCE_POLICY_V1.json"
