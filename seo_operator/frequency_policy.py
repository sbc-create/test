"""Versioned HF/MF/LF frequency-band policy.

Boundaries live in a versioned JSON document (default:
``config/frequency-band-policy.json``, schema
``schemas/frequency-band-policy.schema.json``), never as numbers embedded in
code. Changing a boundary means writing a new revision with a recomputed
digest; nothing here mutates a revision in place.

A volume measurement that is missing, or older than the policy's freshness
window, always classifies as :class:`FrequencyBand.UNKNOWN` — never as ``0``
and never as whatever band the last known value happened to be.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "schemas" / "frequency-band-policy.schema.json"
DEFAULT_POLICY_PATH = REPO_ROOT / "config" / "frequency-band-policy.json"


class PolicyError(RuntimeError):
    """A policy document fails schema validation or internal consistency checks."""


class FrequencyBand(str, Enum):
    HF = "HF"
    MF = "MF"
    LF = "LF"
    UNKNOWN = "UNKNOWN"


class Freshness(str, Enum):
    FRESH = "FRESH"
    STALE = "STALE"
    MISSING = "MISSING"


def _canonical(value: Any) -> str:
    """Stable JSON form: key order and whitespace never affect the digest."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def compute_digest(document: dict) -> str:
    """sha256 hex digest over `document` with its own `digest` field removed."""
    payload = {k: v for k, v in document.items() if k != "digest"}
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class BandBoundary:
    name: FrequencyBand
    min_monthly_volume: int
    max_monthly_volume: int | None  # None marks the open-ended top band (HF)


@dataclass(frozen=True)
class FrequencyPolicy:
    policy_id: str
    revision: int
    supersedes_revision: int | None
    digest: str
    effective_from: str
    region: str
    searchers: tuple[str, ...]
    freshness_max_age_days: int
    bands: tuple[BandBoundary, ...]
    note: str = ""

    def band_for(self, volume: int) -> FrequencyBand:
        for boundary in self.bands:
            upper_ok = boundary.max_monthly_volume is None or volume < boundary.max_monthly_volume
            if boundary.min_monthly_volume <= volume and upper_ok:
                return boundary.name
        raise PolicyError(
            f"volume {volume} is not covered by any band in policy "
            f"{self.policy_id} rev {self.revision}"
        )


@dataclass(frozen=True)
class VolumeMeasurement:
    """A single monthly-volume reading.

    ``value`` is ``None`` when the source did not return a number — that is
    never conflated with a measured ``0``. ``source``, ``region`` and
    ``searcher`` are always recorded, even when ``value`` is ``None``, so a
    failed measurement still says who was asked and for what.
    """

    value: int | None
    source: str
    measured_at: str | None  # RFC 3339; None only when value is also None
    region: str
    searcher: str


def _validate_schema(data: dict) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    if errors:
        detail = "; ".join(
            f"{'/'.join(str(p) for p in e.path) or '(root)'}: {e.message}" for e in errors[:5]
        )
        raise PolicyError(f"frequency-band-policy schema violation: {detail}")


def _bands_from_data(raw_bands: list[dict]) -> tuple[BandBoundary, ...]:
    return tuple(
        BandBoundary(FrequencyBand(b["name"]), b["min_monthly_volume"], b.get("max_monthly_volume"))
        for b in raw_bands
    )


def check_bands_are_contiguous(bands: tuple[BandBoundary, ...]) -> None:
    """LF/MF/HF must tile [0, +inf) with no gap and no overlap.

    This is enforced in code, not left to convention, because a gap between
    bands would silently make some volumes unclassifiable and an overlap would
    make the classification order-dependent.
    """
    names = {b.name for b in bands}
    if names != {FrequencyBand.LF, FrequencyBand.MF, FrequencyBand.HF}:
        raise PolicyError(
            f"policy must define exactly LF, MF and HF bands, got {sorted(n.value for n in names)}"
        )
    ordered = sorted(bands, key=lambda b: b.min_monthly_volume)
    if ordered[0].min_monthly_volume != 0:
        raise PolicyError("bands must start at 0")
    for left, right in zip(ordered, ordered[1:], strict=False):
        if left.max_monthly_volume is None:
            raise PolicyError(f"band {left.name.value} is open-ended but is not the highest band")
        if left.max_monthly_volume != right.min_monthly_volume:
            raise PolicyError(
                f"gap or overlap between {left.name.value} (< {left.max_monthly_volume}) and "
                f"{right.name.value} (>= {right.min_monthly_volume})"
            )
    if ordered[-1].max_monthly_volume is not None:
        raise PolicyError("the highest band must be open-ended (max_monthly_volume: null)")


def load_policy(path: Path | None = None) -> FrequencyPolicy:
    path = Path(path or DEFAULT_POLICY_PATH)
    if not path.exists():
        raise PolicyError(f"policy file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    _validate_schema(data)
    expected_digest = compute_digest(data)
    if data.get("digest") != expected_digest:
        raise PolicyError(
            f"{path}: stored digest {data.get('digest')!r} does not match recomputed "
            f"{expected_digest!r} — the file was edited without regenerating its digest"
        )
    bands = _bands_from_data(data["bands"])
    check_bands_are_contiguous(bands)
    return FrequencyPolicy(
        policy_id=data["policy_id"],
        revision=data["revision"],
        supersedes_revision=data.get("supersedes_revision"),
        digest=data["digest"],
        effective_from=data["effective_from"],
        region=data["region"],
        searchers=tuple(data["searchers"]),
        freshness_max_age_days=data["freshness_max_age_days"],
        bands=bands,
        note=data.get("note", ""),
    )


def classify_frequency(
    measurement: VolumeMeasurement,
    policy: FrequencyPolicy,
    *,
    now: datetime,
) -> tuple[FrequencyBand, Freshness, str]:
    """Classify one volume measurement. Missing or stale data always yields UNKNOWN."""
    if measurement.value is None:
        return (
            FrequencyBand.UNKNOWN,
            Freshness.MISSING,
            f"no volume measurement on record (source: {measurement.source})",
        )
    if measurement.measured_at is None:
        raise PolicyError("a measurement carrying a value must also record when it was measured")

    measured_at = datetime.fromisoformat(measurement.measured_at)
    if measured_at.tzinfo is None:
        measured_at = measured_at.replace(tzinfo=timezone.utc)
    reference = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    age_days = (reference - measured_at).total_seconds() / 86400

    if age_days > policy.freshness_max_age_days:
        return (
            FrequencyBand.UNKNOWN,
            Freshness.STALE,
            f"measurement is {age_days:.0f} days old, past the "
            f"{policy.freshness_max_age_days}-day freshness limit "
            f"of policy revision {policy.revision}",
        )

    band = policy.band_for(measurement.value)
    return (
        band,
        Freshness.FRESH,
        f"{measurement.value} monthly volume falls in {band.value} per policy "
        f"{policy.policy_id} revision {policy.revision}",
    )


def measurement_to_dict(measurement: VolumeMeasurement, freshness: Freshness) -> dict:
    """Shape a measurement + its freshness verdict for the manifest contract."""
    return {
        "value": measurement.value,
        "source": measurement.source,
        "measured_at": measurement.measured_at,
        "region": measurement.region,
        "searcher": measurement.searcher,
        "freshness": freshness.value,
    }
