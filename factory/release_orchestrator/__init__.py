"""Site Factory Release Orchestrator.

After one owner approval, validates, builds, deploys, restarts, verifies, and
rolls back sites sequentially (concurrency=1). Service names, domains, and
handlers come only from the Core release registry + site-profiles.
"""

from __future__ import annotations

__all__ = [
    "SCHEMA_VERSION",
    "STAGE",
    "TARGET_BRANCH",
    "TARGET_WORKTREE",
]

SCHEMA_VERSION = "1.0.0"
STAGE = "SITE-FACTORY-RELEASE-ORCHESTRATOR-01"
TARGET_BRANCH = "cursor/site-factory-release-orchestrator-01"
TARGET_WORKTREE = "/home/claude/wt-site-factory-release-orchestrator-01"
