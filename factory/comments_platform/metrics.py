"""Observability.

Every metric is labelled by tenant, site, module version and operation, so
"comments are slow" can be narrowed to "writes on animedia-02 since version
0.1.1" rather than remaining an impression. No metric carries user text, a
subject id, a network identifier or a token: a metrics backend is a second
datastore with different retention and usually wider access, and a comment body
that reaches it has escaped every moderation state that governs the first copy.

One counter is different in kind from the rest. `cross_tenant_attempts` is not
a performance signal — any confirmed cross-tenant *disclosure* is a P0 and
blocks rollout outright, and this counter is how that becomes observable rather
than hypothetical. A non-zero value is not automatically a breach: a refused
probe increments it too, which is the system working. What must never happen is
a refusal count of zero alongside a served response.
"""

from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from . import MODULE_VERSION
from .tenancy import TenantScope

# Label names permitted on any metric. An allowlist, not a denylist: a new call
# site that passes `body=` simply has it dropped rather than leaking it.
ALLOWED_LABELS = frozenset(
    {"tenant_id", "site_id", "version", "operation", "outcome", "code", "state", "reason_class"}
)

# Values that must never appear as a label value, whatever the label name.
# Checked by a test against real service traffic, not trusted to review.
FORBIDDEN_LABEL_SUBSTRINGS = ("@", "http://", "https://")

COUNTERS = (
    "api_requests_total",
    "api_errors_total",
    "read_success_total",
    "write_success_total",
    "moderation_outcomes_total",
    "idempotency_conflicts_total",
    "duplicates_rejected_total",
    "rate_limited_total",
    "widget_load_total",
    "widget_ready_total",
    "widget_error_total",
    "hydration_mismatch_total",
    "ssr_render_total",
    "ssr_timeout_total",
    "ssr_cache_hit_total",
    "js_error_free_sessions_total",
    "queue_depth",
    "kill_switch_engaged",
    "cross_tenant_attempts_total",
)

HISTOGRAMS = ("api_latency_ms", "ssr_latency_ms", "widget_ready_ms")


def _clean_labels(scope: TenantScope, extra: Mapping[str, Any] | None) -> dict[str, str]:
    labels = {
        "tenant_id": scope.tenant_id,
        "site_id": scope.site_id,
        "version": MODULE_VERSION,
    }
    for key, value in (extra or {}).items():
        if key not in ALLOWED_LABELS:
            continue
        text = str(value)
        # Bound the cardinality and the content. A label is a dimension, not a
        # message: long free text here both leaks and explodes the series count.
        if len(text) > 40:
            continue
        if any(bad in text for bad in FORBIDDEN_LABEL_SUBSTRINGS):
            continue
        labels[key] = text
    return labels


@dataclass
class Metrics:
    """An in-process sink.

    Deliberately not a client for any particular backend: the platform records
    what happened, and whatever the host site already runs scrapes or forwards
    it. That keeps a metrics outage from becoming a comments outage.
    """

    counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = field(
        default_factory=lambda: defaultdict(float)
    )
    observations: dict[tuple[str, tuple[tuple[str, str], ...]], list[float]] = field(
        default_factory=lambda: defaultdict(list)
    )

    def increment(
        self, name: str, scope: TenantScope, *, value: float = 1.0, **labels: Any
    ) -> None:
        if name not in COUNTERS:
            raise ValueError(f"unknown counter {name!r}")
        key = (name, tuple(sorted(_clean_labels(scope, labels).items())))
        self.counters[key] += value

    def observe(self, name: str, scope: TenantScope, value: float, **labels: Any) -> None:
        if name not in HISTOGRAMS:
            raise ValueError(f"unknown histogram {name!r}")
        key = (name, tuple(sorted(_clean_labels(scope, labels).items())))
        self.observations[key].append(float(value))

    def gauge(self, name: str, scope: TenantScope, value: float, **labels: Any) -> None:
        if name not in COUNTERS:
            raise ValueError(f"unknown gauge {name!r}")
        key = (name, tuple(sorted(_clean_labels(scope, labels).items())))
        self.counters[key] = float(value)

    def value(self, name: str, scope: TenantScope, **labels: Any) -> float:
        key = (name, tuple(sorted(_clean_labels(scope, labels).items())))
        return self.counters.get(key, 0.0)

    def series(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for (name, labels), value in sorted(self.counters.items()):
            out.append({"metric": name, "labels": dict(labels), "value": value})
        for (name, labels), values in sorted(self.observations.items()):
            out.append(
                {
                    "metric": name,
                    "labels": dict(labels),
                    "count": len(values),
                    "sum": sum(values),
                    "p50": _percentile(values, 50),
                    "p95": _percentile(values, 95),
                }
            )
        return out

    def scope_totals(self, scope: TenantScope) -> dict[str, float]:
        """Everything recorded for one site. Used by the per-tenant dashboard."""
        totals: dict[str, float] = defaultdict(float)
        for (name, labels), value in self.counters.items():
            as_dict = dict(labels)
            if as_dict.get("tenant_id") == scope.tenant_id and as_dict.get("site_id") == scope.site_id:
                totals[name] += value
        return dict(totals)


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((pct / 100.0) * (len(ordered) - 1))))
    return ordered[index]


class Timer:
    """`with Timer(metrics, 'api_latency_ms', scope, operation='create'):`"""

    def __init__(self, metrics: Metrics, name: str, scope: TenantScope, **labels: Any) -> None:
        self._metrics = metrics
        self._name = name
        self._scope = scope
        self._labels = labels
        self._started = 0.0

    def __enter__(self) -> Timer:
        self._started = time.perf_counter()
        return self

    def __exit__(self, *exc: Any) -> None:
        elapsed_ms = (time.perf_counter() - self._started) * 1000.0
        self._metrics.observe(self._name, self._scope, elapsed_ms, **self._labels)


def observability_contract() -> dict[str, Any]:
    return {
        "schema_version": "COMMENTS_OBSERVABILITY_V1",
        "counters": list(COUNTERS),
        "histograms": list(HISTOGRAMS),
        "labels": sorted(ALLOWED_LABELS),
        "always_labelled_by": ["tenant_id", "site_id", "version"],
        "never_in_metrics": [
            "comment text", "subject ids", "network identifiers", "tokens", "email", "raw IP",
        ],
        "p0_signal": {
            "metric": "cross_tenant_attempts_total",
            "rule": (
                "a confirmed cross-tenant disclosure is P0 and blocks rollout; "
                "a refused probe also increments this counter, and that is the "
                "system working"
            ),
        },
    }
