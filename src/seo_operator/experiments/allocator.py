"""
Аллокатор: решает, можно ли запустить эксперимент и на какой когорте.

Главное ограничение — не менять одинаково все 15-20 сайтов одновременно.
Второе — не сталкивать два своих сайта на одном интенте.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Iterable

from .. import config
from .registry import Experiment, ExperimentRegistry


@dataclass(frozen=True)
class AllocationDecision:
    allowed: bool
    reason: str
    cohort: list[str]
    holdout: list[str]
    share: float


def _bucket(url: str, salt: str) -> float:
    h = hashlib.sha256(f"{salt}:{url}".encode("utf-8")).digest()
    return int.from_bytes(h[:4], "big") / 2**32


def split_cohort(urls: Iterable[str], share: float, salt: str,
                 holdout_share: float = 0.0) -> tuple[list[str], list[str]]:
    """
    Стабильное детерминированное разбиение: одна и та же страница всегда
    попадает в ту же группу при том же salt — без этого повторный запуск
    перемешивает когорты и портит измерение.
    """
    treatment: list[str] = []
    holdout: list[str] = []
    for u in urls:
        b = _bucket(u, salt)
        if b < share:
            treatment.append(u)
        elif b < share + holdout_share:
            holdout.append(u)
    return treatment, holdout


class Allocator:
    def __init__(self, registry: ExperimentRegistry) -> None:
        self.registry = registry
        self.policy = config.experiment_policy()["allocation"]

    def can_start(self, site_id: str, page_type: str | None,
                  intent: str | None = None) -> AllocationDecision:
        site = config.get_site(site_id)

        if self.registry.store.open_incidents(site_id):
            return AllocationDecision(False, "На сайте открыт инцидент — эксперименты заморожены.", [], [], 0.0)

        active = self.registry.active(site_id)
        site_limit = min(site.experiment_limit, self.policy["max_concurrent_per_site"])
        if len(active) >= site_limit:
            return AllocationDecision(
                False, f"Достигнут лимит одновременных экспериментов на сайте ({site_limit}).", [], [], 0.0)

        if page_type:
            same_type = [e for e in active if e.page_type == page_type]
            if len(same_type) >= self.policy["max_concurrent_per_page_type"]:
                return AllocationDecision(
                    False, f"Лимит экспериментов на тип страниц '{page_type}' исчерпан.", [], [], 0.0)

        portfolio_active = self.registry.active()
        if len(portfolio_active) >= self.policy["max_concurrent_portfolio"]:
            return AllocationDecision(False, "Достигнут портфельный лимит экспериментов.", [], [], 0.0)

        if intent and self.policy.get("forbid_intra_portfolio_competition_same_intent"):
            competing = [e for e in portfolio_active
                         if e.query_cohort == intent and e.site_id != site_id]
            if competing:
                return AllocationDecision(
                    False,
                    f"Интент '{intent}' уже под экспериментом на {competing[0].site_id} — "
                    "два сайта портфеля не конкурируют без отдельного решения.",
                    [], [], 0.0)

        return AllocationDecision(True, "Слот доступен.", [], [], self.policy["default_cohort_share"])

    def allocate(self, site_id: str, urls: list[str], page_type: str | None = None,
                 intent: str | None = None, salt: str | None = None) -> AllocationDecision:
        base = self.can_start(site_id, page_type, intent)
        if not base.allowed:
            return base
        share = self.policy["default_cohort_share"]
        holdout_share = share if self.policy.get("holdout_required_when_possible") else 0.0
        salt = salt or f"{site_id}:{page_type}:{intent}"
        treatment, holdout = split_cohort(urls, share, salt, holdout_share)

        if not treatment:
            return AllocationDecision(False, "Когорта пуста при заданной доле.", [], [], share)
        if holdout_share and not holdout:
            return AllocationDecision(
                False,
                "Holdout не сформирован — при малой выборке эффект неотличим от шума.",
                treatment, [], share)
        return AllocationDecision(True, "Когорта и holdout сформированы.", treatment, holdout, share)

    def rollout_step(self, current_share: float) -> float | None:
        """Следующий шаг раскатки после зрелого положительного результата."""
        steps = config.experiment_policy()["rollout"]["step_shares"]
        for s in steps:
            if s > current_share + 1e-9:
                return s
        return None
