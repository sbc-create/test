"""Owner-readable comments postmod metrics (no secrets, no user texts)."""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CommentsMetrics:
    comments_created: int = 0
    preflight_rejected: int = 0
    published_unreviewed: int = 0
    qwen_approved: int = 0
    spoiler_collapsed: int = 0
    auto_hidden: int = 0
    held_for_review: int = 0
    qwen_errors: int = 0
    schema_mismatches: int = 0
    retries: int = 0
    dead_letter: int = 0
    admin_overrides: int = 0
    reports_submitted: int = 0
    edits: int = 0
    deletes: int = 0
    rate_limit_blocks: int = 0
    prompt_injection_detections: int = 0
    xss_blocks: int = 0
    _latencies_ms: list[float] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def observe_latency_ms(self, value: float) -> None:
        with self._lock:
            self._latencies_ms.append(float(value))
            if len(self._latencies_ms) > 5000:
                self._latencies_ms = self._latencies_ms[-2500:]

    def _percentile(self, p: float) -> float:
        data = sorted(self._latencies_ms)
        if not data:
            return 0.0
        idx = min(len(data) - 1, max(0, int(round((p / 100.0) * (len(data) - 1)))))
        return float(data[idx])

    def snapshot(
        self,
        *,
        queue_depth: int = 0,
        oldest_job_age_s: float = 0.0,
        kill_switch: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            return {
                "comments_created": self.comments_created,
                "preflight_rejected": self.preflight_rejected,
                "published_unreviewed": self.published_unreviewed,
                "qwen_approved": self.qwen_approved,
                "spoiler_collapsed": self.spoiler_collapsed,
                "auto_hidden": self.auto_hidden,
                "held_for_review": self.held_for_review,
                "qwen_errors": self.qwen_errors,
                "schema_mismatches": self.schema_mismatches,
                "moderation_latency_ms": {
                    "p50": self._percentile(50),
                    "p95": self._percentile(95),
                    "p99": self._percentile(99),
                    "samples": len(self._latencies_ms),
                },
                "queue_depth": queue_depth,
                "oldest_job_age_s": oldest_job_age_s,
                "retries": self.retries,
                "dead_letter_count": self.dead_letter,
                "admin_overrides": self.admin_overrides,
                "reports_submitted": self.reports_submitted,
                "edit_counts": self.edits,
                "delete_counts": self.deletes,
                "rate_limit_blocks": self.rate_limit_blocks,
                "prompt_injection_detections": self.prompt_injection_detections,
                "xss_blocks": self.xss_blocks,
                "kill_switch": kill_switch or {},
                "contains_user_text": 0,
                "contains_secrets": 0,
            }


_GLOBAL = CommentsMetrics()


def metrics() -> CommentsMetrics:
    return _GLOBAL
