"""
Накопление доказанного опыта.

Под self-learning понимается feedback loop на данных, а не изменение весов модели:
эксперимент -> результат -> кандидат в паттерн -> подтверждение -> playbook.
Неудачи не стираются: FAILED_PATTERNS так же ценны, как успехи.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .. import config
from ..experiments.evaluator import Evaluation
from ..experiments.registry import Experiment


@dataclass
class ApplicabilityScope:
    """Явные границы. Без них успех одной страницы обобщается на портфель — и ломает его."""
    site_types: list[str] = field(default_factory=list)
    page_types: list[str] = field(default_factory=list)
    query_intents: list[str] = field(default_factory=list)
    traffic_band: str = "unknown"          # low | medium | high

    def is_explicit(self) -> bool:
        return bool(self.page_types and self.query_intents and self.traffic_band != "unknown")


@dataclass
class Pattern:
    id: str
    statement: str
    evidence_experiments: list[str]
    scope: ApplicabilityScope
    observed_lift_pct: float
    confidence: float
    status: str = "candidate"              # candidate | active | retired
    reproductions: int = 0
    created_at: str = field(default_factory=lambda: date.today().isoformat())
    retired_reason: str | None = None


PROMOTION_CRITERIA = [
    "experiment_data_matured",
    "guardrails_cleared",
    "confounders_considered",
    "reproduced_or_sufficient_evidence",
    "applicability_scope_explicit",
    "rollback_was_possible",
    "protected_rules_unchanged",
]


def promotion_check(pattern: Pattern, exp: Experiment, ev: Evaluation,
                    protected_drift: list[str]) -> tuple[bool, dict[str, bool]]:
    checks = {
        "experiment_data_matured": ev.decision != "inconclusive" or bool(ev.lift_pct),
        "guardrails_cleared": not ev.guardrail_breaches,
        "confounders_considered": ev.confidence >= 0.6 or not ev.confounders,
        "reproduced_or_sufficient_evidence": pattern.reproductions >= 1 or ev.confidence >= 0.8,
        "applicability_scope_explicit": pattern.scope.is_explicit(),
        "rollback_was_possible": bool(exp.rollback_payload and exp.rollback_payload.get("executable")),
        "protected_rules_unchanged": not protected_drift,
    }
    return all(checks.values()), checks


class LearningRegistry:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or (config.repo_root() / "seo" / "learning")
        self.root.mkdir(parents=True, exist_ok=True)
        self.patterns_path = self.root / "PATTERN_REGISTRY.yaml"
        self.failed_path = self.root / "FAILED_PATTERNS.yaml"
        self.changelog_path = self.root / "CHANGELOG.md"

    def _load(self, path: Path, key: str) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return data.get(key) or []

    def _save(self, path: Path, key: str, items: list[dict[str, Any]]) -> None:
        path.write_text(
            yaml.safe_dump({"version": 1, "updated_at": date.today().isoformat(), key: items},
                           allow_unicode=True, sort_keys=False),
            encoding="utf-8")

    def patterns(self) -> list[dict[str, Any]]:
        return self._load(self.patterns_path, "patterns")

    def failed(self) -> list[dict[str, Any]]:
        return self._load(self.failed_path, "failed_patterns")

    def add_candidate(self, pattern: Pattern) -> None:
        items = self.patterns()
        if any(p["id"] == pattern.id for p in items):
            return
        d = asdict(pattern)
        d["scope"] = asdict(pattern.scope)
        items.append(d)
        self._save(self.patterns_path, "patterns", items)
        self._log(f"candidate `{pattern.id}` добавлен: {pattern.statement}")

    def activate(self, pattern_id: str, checks: dict[str, bool]) -> bool:
        if not all(checks.values()):
            return False
        items = self.patterns()
        for p in items:
            if p["id"] == pattern_id:
                p["status"] = "active"
                p["promoted_at"] = date.today().isoformat()
                p["promotion_checks"] = checks
                self._save(self.patterns_path, "patterns", items)
                self._log(f"pattern `{pattern_id}` активирован.")
                return True
        return False

    def record_failure(self, pattern_id: str, statement: str, reason: str,
                       experiments: list[str], scope: ApplicabilityScope) -> None:
        """Провалы не удаляются — это защита от повторения той же ошибки."""
        items = self.failed()
        items.append({
            "id": pattern_id, "statement": statement, "reason": reason,
            "evidence_experiments": experiments, "scope": asdict(scope),
            "recorded_at": date.today().isoformat(),
        })
        self._save(self.failed_path, "failed_patterns", items)
        self._log(f"failed pattern `{pattern_id}`: {reason}")

    def is_known_failure(self, statement: str, page_type: str | None = None) -> str | None:
        """Перед новым экспериментом проверяем, не пробовали ли мы это и не провалились ли."""
        for f in self.failed():
            if f["statement"].strip().lower() == statement.strip().lower():
                scope_types = (f.get("scope") or {}).get("page_types") or []
                if page_type is None or not scope_types or page_type in scope_types:
                    return f["reason"]
        return None

    def _log(self, message: str) -> None:
        header = "# Learning changelog\n\n" if not self.changelog_path.exists() else ""
        with self.changelog_path.open("a", encoding="utf-8") as fh:
            fh.write(f"{header}- {datetime.now(timezone.utc):%Y-%m-%d %H:%M} — {message}\n")


def backtest(pattern: Pattern, historical: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Проверка паттерна на исторических экспериментах вне обучающего набора.
    Возвращает долю подтверждений и вывод о переносимости.
    """
    in_scope = [h for h in historical
                if (not pattern.scope.page_types or h.get("page_type") in pattern.scope.page_types)
                and (not pattern.scope.query_intents or h.get("intent") in pattern.scope.query_intents)]
    out_of_sample = [h for h in in_scope if h["experiment_id"] not in pattern.evidence_experiments]

    if not out_of_sample:
        return {"verdict": "insufficient_data", "checked": 0,
                "note": "Нет исторических случаев вне обучающего набора."}

    confirmed = sum(1 for h in out_of_sample if h.get("lift_pct", 0) >= 5)
    contradicted = sum(1 for h in out_of_sample if h.get("lift_pct", 0) <= -5)
    rate = confirmed / len(out_of_sample)

    if rate >= 0.7 and contradicted == 0:
        verdict = "holds"
    elif contradicted > confirmed:
        verdict = "contradicted"
    else:
        verdict = "unstable"

    return {"verdict": verdict, "checked": len(out_of_sample), "confirmed": confirmed,
            "contradicted": contradicted, "confirm_rate": round(rate, 3)}
