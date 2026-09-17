"""Builds and validates the ``approved_relevant_manifest`` contract.

This module performs no network call and no Topvisor mutation. It only
assembles and validates a versioned, digested record of query relevance
decisions. An entry is :attr:`ManifestEntry.sync_eligible` only when its
relevance decision is APPROVED_RELEVANT, it carries evidence, and its site
is ready (rights confirmed, production authorized, not a stand domain) —
and even then nothing here calls Topvisor. Importing into Topvisor is a
separate, explicitly authorized step this module does not implement.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from seo_operator.frequency_policy import FrequencyBand
from seo_operator.priority import QueryClass
from seo_operator.relevance import RelevanceDecision, RelevanceVerdict
from seo_operator.site_authority import SiteAuthority

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "schemas" / "approved-relevant-manifest.schema.json"

EVIDENCE_KINDS = frozenset(
    {
        "query_observation",
        "rank_observation",
        "search_index_observation",
        "indexability_observation",
        "manual_review",
    }
)


class ManifestError(RuntimeError):
    """A manifest entry or document cannot be built, or fails validation."""


def normalize_query(query: str) -> str:
    """Lowercase, trimmed, whitespace-collapsed form used for ownership matching."""
    return " ".join(query.strip().lower().split())


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def compute_digest(document: dict) -> str:
    """sha256 hex digest over `document` with its own `digest` field removed."""
    payload = {k: v for k, v in document.items() if k != "digest"}
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EvidenceRef:
    kind: str
    ref: str
    summary: str
    checked_at: str

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ManifestEntry:
    site_id: str
    domain: str
    site_ready: bool
    query: str
    normalized_query: str
    taxonomy_id: str
    intent: QueryClass
    cluster: str
    frequency_band: FrequencyBand
    frequency_measurement: dict
    target_url: str
    relevance_decision: RelevanceDecision
    evidence: tuple[EvidenceRef, ...]
    approved_by: str
    approved_at: str
    created_at: str
    expires_at: str | None = None

    @property
    def sync_eligible(self) -> bool:
        """Only an APPROVED_RELEVANT, evidenced entry on a ready site is sync-eligible.

        This module never acts on that eligibility — it only computes it, so a
        later, separately authorized sync step has something honest to filter on.
        """
        return (
            self.relevance_decision.verdict is RelevanceVerdict.APPROVED_RELEVANT
            and len(self.evidence) > 0
            and self.site_ready
        )

    def as_dict(self) -> dict:
        return {
            "site_id": self.site_id,
            "domain": self.domain,
            "site_ready": self.site_ready,
            "query": self.query,
            "normalized_query": self.normalized_query,
            "taxonomy_id": self.taxonomy_id,
            "intent": self.intent.value,
            "cluster": self.cluster,
            "frequency_band": self.frequency_band.value,
            "frequency_measurement": self.frequency_measurement,
            "target_url": self.target_url,
            "relevance_decision": {
                "verdict": self.relevance_decision.verdict.value,
                "reason": self.relevance_decision.reason,
                "policy_revision": self.relevance_decision.policy_revision,
                "decided_at": self.relevance_decision.decided_at,
            },
            "evidence": [e.as_dict() for e in self.evidence],
            "owner": {"approved_by": self.approved_by, "approved_at": self.approved_at},
            "created_at": self.created_at,
            "expires_at": self.expires_at,
        }


def build_entry(
    *,
    site_id: str,
    domain: str,
    query: str,
    taxonomy_id: str,
    intent: QueryClass,
    cluster: str,
    frequency_band: FrequencyBand,
    frequency_measurement: dict,
    target_url: str,
    relevance_decision: RelevanceDecision,
    evidence: tuple[EvidenceRef, ...],
    approved_by: str,
    approved_at: str,
    created_at: str,
    site_authority: SiteAuthority,
    expires_at: str | None = None,
) -> ManifestEntry:
    """Assemble one manifest entry. Fails closed on an unknown site or domain."""
    known = site_authority.resolve(site_id, domain)
    if known is None:
        raise ManifestError(
            f"BLOCKED_INPUT: site_id={site_id!r} domain={domain!r} is not a known "
            f"(site_id, domain) pair in {site_authority.source_name}"
        )
    for item in evidence:
        if item.kind not in EVIDENCE_KINDS:
            raise ManifestError(f"unknown evidence kind {item.kind!r}")
    if not isinstance(relevance_decision, RelevanceDecision):
        raise ManifestError(
            "relevance_decision must come from seo_operator.relevance.decide_relevance, "
            f"got {type(relevance_decision).__name__}"
        )
    return ManifestEntry(
        site_id=site_id,
        domain=domain,
        site_ready=known.ready,
        query=query,
        normalized_query=normalize_query(query),
        taxonomy_id=taxonomy_id,
        intent=intent,
        cluster=cluster,
        frequency_band=frequency_band,
        frequency_measurement=frequency_measurement,
        target_url=target_url,
        relevance_decision=relevance_decision,
        evidence=tuple(evidence),
        approved_by=approved_by,
        approved_at=approved_at,
        created_at=created_at,
        expires_at=expires_at,
    )


def _sort_key(entry_dict: dict) -> tuple:
    return (entry_dict["site_id"], entry_dict["normalized_query"], entry_dict["target_url"])


def build_manifest(
    entries: list[ManifestEntry],
    *,
    manifest_id: str,
    version: int,
    revision: int,
    generated_at: str,
    site_authority: SiteAuthority,
    band_policy_revision: int,
    note: str = "",
) -> dict:
    """Assemble the manifest document. Entry order never affects the digest."""
    entry_dicts = sorted((e.as_dict() for e in entries), key=_sort_key)
    document: dict[str, Any] = {
        "manifest_id": manifest_id,
        "version": version,
        "revision": revision,
        "generated_at": generated_at,
        "site_authority_source": site_authority.source_name,
        "band_policy_revision": band_policy_revision,
        "entries": entry_dicts,
    }
    if note:
        document["note"] = note
    document["digest"] = compute_digest(document)
    return document


def validate_manifest(data: dict) -> list[str]:
    """Validate a manifest document against the schema and its own digest.

    Pure dry-run validation: reads the schema file, hashes the document, and
    returns problems. Never touches the network or Topvisor.
    """
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    problems = [
        f"{'/'.join(str(p) for p in e.path) or '(root)'}: {e.message}"
        for e in sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    ]
    expected = compute_digest(data)
    if data.get("digest") != expected:
        problems.append(f"digest mismatch: stored {data.get('digest')!r}, recomputed {expected!r}")
    return problems


def sync_eligible_entries(data: dict) -> list[dict]:
    """Entries eligible for a FUTURE, separately authorized Topvisor sync.

    Nothing in this module calls that sync; this only computes the filter it
    would use.
    """
    return [
        e
        for e in data.get("entries", [])
        if e.get("relevance_decision", {}).get("verdict") == "APPROVED_RELEVANT"
        and e.get("evidence")
        and e.get("site_ready") is True
    ]
