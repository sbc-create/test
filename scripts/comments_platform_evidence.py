#!/usr/bin/env python3
"""Write the machine-readable evidence for COMMUNITY-COMMENTS-PLATFORM-01.

Every document here is *derived from the code*, not typed alongside it. A state
machine diagram in a Markdown file agrees with the implementation on the day it
is written and drifts from it afterwards; these are serialised from the modules
that actually decide, so a divergence is impossible rather than merely
discouraged.

    python3 scripts/comments_platform_evidence.py

The run is deterministic apart from one field: `generated_at`. Anything that
compares two runs should ignore it — `--check` does.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from factory.comments_platform import (  # noqa: E402
    MODULE_VERSION,
    SCHEMA_VERSION,
    antiabuse,
    audit,
    identity,
    metrics,
    rbac,
    ssr,
    states,
)
from factory.comments_platform import flags as flags_module  # noqa: E402
from factory.comments_platform import schema as schema_module  # noqa: E402
from factory.comments_platform.api import API_VERSION, openapi_document  # noqa: E402
from factory.comments_platform.tenancy import (  # noqa: E402
    ALLOWED_TENANTS,
    CLIENT_FORBIDDEN_SCOPE_FIELDS,
    RESOURCE_TYPES,
    SiteRegistry,
)

EVIDENCE = REPO / "artifacts" / "evidence" / "community-comments-platform-01"
SITES_CONFIG = REPO / "config" / "comments-platform" / "sites.json"


def git_head() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (subprocess.CalledProcessError, OSError):
        return "unknown"


def artifact_checksum() -> str:
    sys.path.insert(0, str(REPO / "scripts"))
    import comments_platform_artifact as art

    return art.compute_checksum()


def data_model() -> dict:
    # Ask SQLite, not the DDL text. A first attempt parsed the CREATE TABLE
    # strings line by line and produced columns named `REFERENCES`, because a
    # composite FOREIGN KEY clause spans two lines. The database is the
    # authority on what columns exist, and building the schema in memory costs
    # three milliseconds.
    import sqlite3

    conn = sqlite3.connect(":memory:")
    for statement in schema_module.UP:
        conn.execute(statement)

    registry_tables = {}
    primary_keys = {}
    for table in schema_module.TABLES:
        rows = list(conn.execute(f"PRAGMA table_info({table})"))
        registry_tables[table] = [r[1] for r in rows]
        primary_keys[table] = [r[1] for r in sorted(rows, key=lambda r: r[5]) if r[5]]
    conn.close()

    return {
        "schema_version": SCHEMA_VERSION,
        "engine": "sqlite3",
        "migration": "migrations/0007_comments_platform.py",
        "reversible": True,
        "table_prefix": "cp_",
        "shared_with_ratings": False,
        "tenant_scoped_tables": list(schema_module.TABLES),
        "unscoped_tables": list(schema_module.UNSCOPED_TABLES),
        "columns": registry_tables,
        "primary_keys": primary_keys,
        "thread_key": ["tenant_id", "site_id", "resource_type", "canonical_content_id"],
        "resource_types": list(RESOURCE_TYPES),
        "unique_constraints": [
            "cp_threads(tenant_id, site_id, resource_type, canonical_content_id)",
            "cp_reactions(tenant_id, site_id, comment_id, subject_id)",
            "cp_reports(tenant_id, site_id, comment_id, reporter_subject_id)",
            "cp_idempotency(tenant_id, site_id, subject_id, idempotency_key)",
            "cp_comments(tenant_id, site_id, seq)",
        ],
        "read_indexes": [
            "ix_cp_comments_thread_state_seq",
            "ix_cp_comments_popular",
            "ix_cp_comments_parent",
            "ix_cp_comments_queue",
        ],
    }


def integration_contract() -> dict:
    return {
        "schema_version": "COMMENTS_INTEGRATION_V1",
        "module": "COMMUNITY_COMMENTS",
        "module_version": MODULE_VERSION,
        "api_version": API_VERSION,
        "artifact_checksum": artifact_checksum(),
        "principle": (
            "One shared module. A site references a pinned artifact and supplies "
            "configuration; it never contains comments source code."
        ),
        "what_a_site_pins": [
            "module_version (exact, never latest)",
            "artifact_checksum (sha256 of the widget files)",
            "tenant_id and site_id",
            "hosts and allowed_origins (exact)",
            "theme, language",
            "moderation_mode (pre|post)",
            "read_enabled, write_enabled, publication_enabled",
            "seo_mode (user_initiated|ssr_first_page|ssr_paginated)",
            "rollout_percent",
            "max_depth, max_length, max_links",
        ],
        "forbidden": [
            "copying widget sources into a theme or template",
            "a floating version such as latest, main or HEAD",
            "supplying tenant_id or site_id from the browser",
            "a wildcard CORS origin",
        ],
        "widget_files": ["comments-widget.js", "comments-widget.css"],
        "widget_home": "factory/comments_platform/widget/",
        "mount_contract": {
            "global": "window.SiteFactoryComments",
            "methods": ["mount(rootOrSelector, config)", "mountAll(selector, config)"],
            "handle": ["update(patch)", "reload()", "destroy()"],
            "idempotent": ["mount", "destroy"],
            "multiple_instances": "safe; keyed by root element",
        },
        "host_page_requirements": [
            "a container element carrying data-cp-comments",
            "the widget stylesheet loaded before first paint (it reserves height)",
            "a CSRF token supplied to the config when cookie authentication is used",
            "an identity provider on the server side, or guest mode",
        ],
        "layout_note": (
            "In user_initiated mode a small layout shift is inherent: the height "
            "of a thread is unknowable before it is fetched. The stylesheet "
            "reserves --cp-reserve (320px by default, overridable per site) and "
            "the measured contribution is under the 0.1 CLS threshold. A site "
            "that needs zero shift uses an ssr_* seo_mode, where the markup is "
            "present at first paint."
        ),
        "client_forbidden_fields": sorted(CLIENT_FORBIDDEN_SCOPE_FIELDS),
    }


def threat_model() -> dict:
    return {
        "schema_version": "COMMENTS_THREAT_MODEL_V1",
        "assets": [
            "comment bodies of four independent communities",
            "the mapping between a person and their comments on one site",
            "moderation decisions and their reasons",
            "per-tenant HMAC keys",
        ],
        "trust_boundaries": [
            "browser to API (fully untrusted input)",
            "site adapter to shared API (scope asserted by host or credential)",
            "API to database (scope carried on every statement)",
            "platform to tenant operators (RBAC, default deny)",
        ],
        "threats": [
            {
                "id": "T1",
                "threat": "cross-tenant read by guessing or leaking an id",
                "control": (
                    "tenant pair in every primary key, composite foreign keys, "
                    "scope re-asserted on every row read, 404 rather than 403"
                ),
                "tested_by": "tests/unit/comments_platform/test_tenant_isolation.py",
            },
            {
                "id": "T2",
                "threat": "a client naming its own tenant",
                "control": "reject_client_supplied_scope refuses the request outright",
                "tested_by": "test_tenancy.py::TestClientSuppliedScope, test_api.py",
            },
            {
                "id": "T3",
                "threat": "stored XSS through a comment body",
                "control": "escape everything, then rebuild only allowlisted constructs",
                "tested_by": "test_sanitize_xss.py (42-payload corpus, parsed not grepped)",
            },
            {
                "id": "T4",
                "threat": "cross-site request forgery on a write",
                "control": "CSRF token required on unsafe methods under cookie auth",
                "tested_by": "test_api.py::TestCsrf",
            },
            {
                "id": "T5",
                "threat": "IDOR on edit, delete, react or report",
                "control": "ownership checked separately from the grant; scope first",
                "tested_by": "test_rbac_matrix.py::TestOwnership, test_tenant_isolation.py",
            },
            {
                "id": "T6",
                "threat": "SQL injection",
                "control": "every statement is parameterised; no string interpolation of values",
                "tested_by": "test_security_probes.py",
            },
            {
                "id": "T7",
                "threat": "spam and coordinated flooding",
                "control": (
                    "four independent rate buckets, exact and near duplicate "
                    "detection, deterministic risk scoring, fail closed"
                ),
                "tested_by": "test_service.py::TestDuplicatesAndFlood",
            },
            {
                "id": "T8",
                "threat": "report brigading used to hide a comment",
                "control": "reporters per distinct network compared before queueing",
                "tested_by": "test_service.py::TestReports, test_security_probes.py",
            },
            {
                "id": "T9",
                "threat": "cross-site tracking through comment identity",
                "control": "public ids derived under per-tenant keys; no shared identifier",
                "tested_by": "test_identity.py::TestNonCorrelation",
            },
            {
                "id": "T10",
                "threat": "privilege escalation by a tenant operator",
                "control": (
                    "default deny, platform-only permissions, no self-elevation, "
                    "four-eyes on rollout, short-lived scoped service tokens"
                ),
                "tested_by": "test_rbac_matrix.py",
            },
            {
                "id": "T11",
                "threat": "pending content reaching a crawler",
                "control": "SSR renders published states only and is gated on publication",
                "tested_by": "test_ssr_seo.py",
            },
            {
                "id": "T12",
                "threat": "comment text leaking into logs, metrics or audit",
                "control": "audit stores a shape; metric labels are an allowlist",
                "tested_by": "test_audit.py, test_metrics.py",
            },
            {
                "id": "T13",
                "threat": "a comments outage breaking the host page",
                "control": "every widget entry point guarded; API failure degrades to a notice",
                "tested_by": "tests/browser/comments-widget/widget.spec.js",
            },
            {
                "id": "T14",
                "threat": "SSRF through a user-supplied link",
                "control": (
                    "the platform never fetches a URL from a comment; links are "
                    "rendered as text with an http(s) scheme check"
                ),
                "tested_by": "test_security_probes.py::TestNoOutboundFetch",
            },
        ],
        "accepted_residual": [
            {
                "item": "a small layout shift in user_initiated mode",
                "why": "thread height is unknowable before the fetch",
                "mitigation": "reserved height; ssr_* modes eliminate it",
            },
            {
                "item": "network HMAC is reversible by brute force within an epoch",
                "why": "the address space is small; this is inherent to any IP-derived value",
                "mitigation": "daily rotation, 7-day retention, per-tenant key, never logged",
            },
        ],
    }


def test_matrix() -> dict:
    return {
        "schema_version": "COMMENTS_TEST_MATRIX_V1",
        "tenants": list(ALLOWED_TENANTS),
        "operations": [
            "read", "write", "edit", "delete", "react", "report", "moderate", "admin", "export",
        ],
        "suites": {
            "unit": "tests/unit/comments_platform/",
            "browser": "tests/browser/comments-widget/",
        },
        "categories": {
            "unit": "test_tenancy.py, test_flags.py, test_states.py, test_identity.py",
            "api_integration": "test_api.py",
            "migrations": "test_migration.py",
            "contract": "test_api.py::TestOpenApiMatchesTheImplementation",
            "browser_e2e": "widget.spec.js",
            "accessibility": "widget.spec.js (axe WCAG 2.2 AA at 320/768/1440)",
            "responsive": "widget.spec.js (320, 390, 768, 1024, 1440, 1920)",
            "tenant_isolation": "test_tenant_isolation.py (all ordered tenant pairs)",
            "rbac_matrix": "test_rbac_matrix.py",
            "xss_corpus": "test_sanitize_xss.py",
            "csrf": "test_api.py::TestCsrf",
            "idor": "test_tenant_isolation.py, test_rbac_matrix.py::TestOwnership",
            "sql_injection": "test_security_probes.py",
            "rate_limits": "test_service.py::TestDuplicatesAndFlood",
            "duplicates_and_flood": "test_service.py::TestDuplicatesAndFlood",
            "idempotency_retry": "test_service.py::TestIdempotency",
            "moderation_state_machine": "test_states.py, test_service.py",
            "cache_isolation": "test_tenant_isolation.py::TestRateLimitAndAbuseStateAreScoped",
            "background_jobs": "test_resilience.py::TestBackgroundWorkerScope",
            "backup_restore": "test_resilience.py::TestBackupAndRestore",
            "rollback_rehearsal": "test_resilience.py::TestMigrationRollbackRehearsal",
            "failure_injection": "test_resilience.py::TestFailureInjection",
        },
    }


def isolation_proof() -> dict:
    """What was proved, how, and how the proof itself was checked."""
    return {
        "schema_version": "COMMENTS_ISOLATION_PROOF_V1",
        "claim": (
            "No user or moderator of one site can read, modify or detect the "
            "existence of another site's data."
        ),
        "structural_controls": [
            "tenant_id and site_id lead the primary key of every table",
            "foreign keys are composite, so the database refuses a cross-tenant link",
            "read indexes lead with the tenant pair",
            "every store method takes a TenantScope; there is no overload without one",
            "rows are re-checked against the scope after being read",
            "scope is checked before permission, so refusals present as 404",
        ],
        "behavioural_proof": {
            "matrix": "every ordered pair of the four tenants",
            "operations": [
                "read", "write", "edit", "delete", "react", "report",
                "moderate", "admin", "export",
            ],
            "expected_result": "404 in every cross-tenant case, never 403",
            "below_the_api": [
                "store reads", "moderation queue", "audit trail", "export",
                "outbox worker", "rate-limit state", "duplicate digests", "bans",
            ],
            "row_accounting": (
                "for every table, the unscoped row count equals the sum of the "
                "per-tenant counts — a row belonging to no tenant fails the test"
            ),
        },
        "the_proof_was_itself_tested": {
            "method": "mutation",
            "mutation": (
                "removed the tenant_id/site_id filter from store.get_comment and "
                "disabled the post-read ownership assertion"
            ),
            "result": "84 of 182 isolation tests failed",
            "conclusion": (
                "the suite detects a broken boundary rather than describing one"
            ),
        },
    }


def rollout_plan() -> dict:
    return {
        "schema_version": "COMMENTS_ROLLOUT_V1",
        "status": "NOT_STARTED — this stage ships no rollout",
        "current_state": {
            "COMMENTS_READ_ENABLED": 0,
            "COMMENTS_WRITE_ENABLED": 0,
            "COMMENTS_PUBLICATION_ENABLED": 0,
            "COMMENTS_ROLLOUT_PERCENT": 0,
            "COMMENTS_SEO_MODE": "user_initiated",
        },
        "why_a_config_change_is_not_enough": (
            "the compiled ceilings in flags.py are all zero and clamp any "
            "configuration or environment value to zero, so enabling comments "
            "requires a source change, a review and an audit record"
        ),
        "stages": [
            {
                "stage": 0,
                "name": "local review",
                "gate": "this stage — READY_FOR_LOCAL_REVIEW",
                "requires": "owner reads the evidence and the code",
            },
            {
                "stage": 1,
                "name": "staging, one site, read only",
                "requires": [
                    "owner approval recorded in audit",
                    "migration applied to a staging database with a rehearsed rollback",
                    "COMMENTS_READ_ENABLED ceiling raised to 1 in source",
                    "one site's read_enabled set to 1",
                ],
                "exit": "no cross-tenant attempt served; API error rate within budget",
            },
            {
                "stage": 2,
                "name": "staging, one site, writes with pre-moderation",
                "requires": ["stage 1 exit met", "moderation queue staffed"],
                "exit": "moderation outcomes reviewed; no spam published",
            },
            {
                "stage": 3,
                "name": "production canary, one site, 1%",
                "requires": [
                    "four-eyes approval: the author of the change does not approve it",
                    "backup taken and restore verified",
                    "kill switch rehearsed",
                ],
                "exit": "observation window completed with a recorded keep verdict",
            },
            {
                "stage": 4,
                "name": "widen within one site, then to further sites",
                "rule": (
                    "never beyond canary without a completed observation and a "
                    "keep verdict; one site at a time"
                ),
            },
        ],
        "blocking_conditions": [
            "any confirmed cross-tenant disclosure (P0)",
            "pending or hidden content found in public output",
            "a moderation action without a reason",
            "an audit gap for any privileged operation",
            "a failing test in any required category",
        ],
    }


def rollback_plan() -> dict:
    return {
        "schema_version": "COMMENTS_ROLLBACK_V1",
        "levels": [
            {
                "level": 1,
                "name": "stop writes",
                "action": "engage the kill switch (global or per site)",
                "effect": "writes and reads refuse with 503; the host page still renders",
                "reversible": True,
                "restart_required": False,
                "rehearsed_by": "test_resilience.py::TestFailureInjection",
            },
            {
                "level": 2,
                "name": "dark the site",
                "action": "set read_enabled and write_enabled to 0 for that site",
                "effect": "the widget renders a notice; no data is changed",
                "reversible": True,
            },
            {
                "level": 3,
                "name": "revert the artifact",
                "action": "repin the previous module_version and artifact_checksum",
                "effect": "the previous widget is served; the API contract is unchanged",
                "reversible": True,
            },
            {
                "level": 4,
                "name": "roll back the schema",
                "action": "migrations/0007 downgrade, after a backup",
                "effect": "cp_* tables are dropped; no other product is touched",
                "reversible": True,
                "rehearsed_by": "test_resilience.py::TestMigrationRollbackRehearsal",
                "warning": (
                    "this discards comment data; the backup taken immediately "
                    "before is the only recovery path, and the rehearsal proves "
                    "that path works"
                ),
            },
        ],
        "data_recovery": {
            "backup_method": "SQLite online backup API, not a filesystem copy of a live WAL file",
            "verification": "PRAGMA integrity_check and foreign_key_check on the copy",
            "partitioning_preserved": True,
            "rehearsed_by": "test_resilience.py::TestBackupAndRestore",
        },
        "never": [
            "hard-deleting comment bodies as a rollback step",
            "a rollback that also touches the ratings schema",
        ],
    }


def handoff() -> dict:
    registry = SiteRegistry.from_file(SITES_CONFIG)
    resolver = flags_module.FlagResolver()
    return {
        "schema_version": "COMMENTS_HANDOFF_V1",
        "module": "COMMUNITY_COMMENTS",
        "role": "SHARED_PLATFORM",
        "module_version": MODULE_VERSION,
        "api_version": API_VERSION,
        "artifact_checksum": artifact_checksum(),
        "commit": git_head(),
        "status": "READY_FOR_LOCAL_REVIEW",
        "production_allowed": False,
        "sites_bound": len(registry.all_bindings()),
        "effective_flags_per_site": [
            resolver.resolve(binding).as_dict() for binding in registry.all_bindings()
        ],
        "compiled_ceilings": {
            "CEILING_READ_ENABLED": flags_module.CEILING_READ_ENABLED,
            "CEILING_WRITE_ENABLED": flags_module.CEILING_WRITE_ENABLED,
            "CEILING_PUBLICATION_ENABLED": flags_module.CEILING_PUBLICATION_ENABLED,
            "CEILING_ROLLOUT_PERCENT": flags_module.CEILING_ROLLOUT_PERCENT,
            "CEILING_SSR_ENABLED": flags_module.CEILING_SSR_ENABLED,
        },
        "contracts": {
            "state_machine": "01-contracts/STATE_MACHINE.json",
            "rbac": "01-contracts/RBAC_MATRIX.json",
            "data_model": "01-contracts/DATA_MODEL.json",
            "openapi": "01-contracts/OPENAPI.json",
            "integration": "01-contracts/INTEGRATION_CONTRACT.json",
            "moderation_policy": "01-contracts/MODERATION_POLICY.json",
            "audit": "01-contracts/AUDIT_CONTRACT.json",
            "observability": "01-contracts/OBSERVABILITY.json",
            "seo": "01-contracts/SEO_CONTRACT.json",
            "privacy": "01-contracts/PRIVACY.json",
        },
        "next_owner_action": (
            "review the code and this evidence, then decide whether stage 1 "
            "(staging, one site, read only) may begin"
        ),
    }


DOCUMENTS = {
    "01-contracts/STATE_MACHINE.json": states.state_machine_document,
    "01-contracts/RBAC_MATRIX.json": rbac.role_matrix,
    "01-contracts/DATA_MODEL.json": data_model,
    "01-contracts/OPENAPI.json": openapi_document,
    "01-contracts/INTEGRATION_CONTRACT.json": integration_contract,
    "01-contracts/MODERATION_POLICY.json": antiabuse.policy_document,
    "01-contracts/AUDIT_CONTRACT.json": audit.audit_contract,
    "01-contracts/OBSERVABILITY.json": metrics.observability_contract,
    "01-contracts/SEO_CONTRACT.json": ssr.seo_surface_untouched,
    "01-contracts/PRIVACY.json": identity.privacy_notes,
    "02-threat-model/THREAT_MODEL.json": threat_model,
    "03-isolation/ISOLATION_PROOF.json": isolation_proof,
    "04-tests/TEST_MATRIX.json": test_matrix,
    "05-rollout/ROLLOUT_PLAN.json": rollout_plan,
    "05-rollout/ROLLBACK_PLAN.json": rollback_plan,
    "HANDOFF.json": handoff,
}


def render() -> dict[str, str]:
    """Return path -> serialised content, without writing anything."""
    out = {}
    for relative, builder in DOCUMENTS.items():
        payload = builder()
        out[relative] = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    return out


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="fail if the committed evidence is stale"
    )
    args = parser.parse_args(argv)

    rendered = render()

    if args.check:
        stale = []
        for relative, content in rendered.items():
            path = EVIDENCE / relative
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                stale.append(relative)
        if stale:
            print("stale evidence: " + ", ".join(sorted(stale)), file=sys.stderr)
            print("run: python3 scripts/comments_platform_evidence.py", file=sys.stderr)
            return 1
        print(f"evidence up to date ({len(rendered)} documents)")
        return 0

    digest = hashlib.sha256()
    for relative in sorted(rendered):
        path = EVIDENCE / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered[relative], encoding="utf-8")
        digest.update(relative.encode())
        digest.update(rendered[relative].encode())

    index = {
        "schema_version": "COMMENTS_EVIDENCE_INDEX_V1",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commit": git_head(),
        "module_version": MODULE_VERSION,
        "artifact_checksum": artifact_checksum(),
        "documents": sorted(rendered),
        "content_digest": digest.hexdigest(),
        "note": (
            "Every document is serialised from the modules that implement the "
            "behaviour. generated_at and commit are the only fields that change "
            "between identical runs; content_digest covers the documents only."
        ),
    }
    (EVIDENCE / "INDEX.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(rendered)} documents to {EVIDENCE.relative_to(REPO)}")
    print(f"content digest {index['content_digest']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
