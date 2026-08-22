"""
Управление главной: порядок блоков, витрины, пины, freshness.

Любая перестановка — эксперимент со snapshot и rollback. Главная страница
даёт самый большой blast radius на сайте, поэтому она же жёстче всех ограничена.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from .calendar import CalendarEntry, Status

STANDARD_MODULES = [
    "hero", "new_releases", "coming_soon", "ongoing", "popular",
    "editorial_picks", "collections", "continue_watching",
]


@dataclass
class ModuleSpec:
    id: str
    position: int
    freshness_window_days: int | None = None
    max_items: int = 12
    pinned_items: list[str] = field(default_factory=list)
    pin_expires: dict[str, str] = field(default_factory=dict)   # item_id -> ISO date
    source_status: list[str] = field(default_factory=list)


@dataclass
class HomepagePlan:
    site_id: str
    modules: list[ModuleSpec]
    experiment_id: str | None = None

    def order(self) -> list[str]:
        return [m.id for m in sorted(self.modules, key=lambda m: m.position)]


@dataclass
class FreshnessIssue:
    module_id: str
    item_id: str
    problem: str
    action: str


def audit_freshness(plan: HomepagePlan, entries: dict[str, CalendarEntry],
                    today: date | None = None) -> list[FreshnessIssue]:
    """Ищет на главной просроченные обещания: истёкшие пины, отменённые и вышедшие анонсы."""
    today = today or date.today()
    issues: list[FreshnessIssue] = []

    for module in plan.modules:
        for item_id in module.pinned_items:
            expires = module.pin_expires.get(item_id)
            if not expires:
                issues.append(FreshnessIssue(
                    module.id, item_id, "Пин без даты истечения",
                    "Задать pin_expires — бессрочный пин замораживает главную."))
                continue
            if date.fromisoformat(expires) < today:
                issues.append(FreshnessIssue(
                    module.id, item_id, f"Пин истёк {expires}", "Снять пин"))

            entry = entries.get(item_id)
            if entry is None:
                continue
            if entry.status is Status.CANCELLED:
                issues.append(FreshnessIssue(
                    module.id, item_id, "Материал отменён", "Немедленно снять и обновить статус"))
            elif entry.status is Status.EXPIRED:
                issues.append(FreshnessIssue(
                    module.id, item_id, "Анонс просрочен без подтверждения выхода",
                    "Снять с витрины, пометить перенос"))
            elif entry.status is Status.POSTPONED:
                issues.append(FreshnessIssue(
                    module.id, item_id, "Релиз перенесён", "Обновить формулировку даты, не удалять молча"))
            elif module.id == "coming_soon" and entry.status is Status.RELEASED:
                issues.append(FreshnessIssue(
                    module.id, item_id, "Материал уже вышел, но остаётся в «Скоро»",
                    "Перевести в «Новинки» и обновить доступность просмотра"))

        if module.freshness_window_days:
            module_entries = [e for e in entries.values() if e.external_id in module.pinned_items]
            cutoff = today - timedelta(days=module.freshness_window_days)
            for e in module_entries:
                if e.release_date and date.fromisoformat(e.release_date) < cutoff:
                    issues.append(FreshnessIssue(
                        module.id, e.external_id,
                        f"Вне окна свежести ({module.freshness_window_days} дн.)",
                        "Ротировать блок"))
    return issues


def reorder(plan: HomepagePlan, new_order: list[str], experiment_id: str) -> tuple[HomepagePlan, dict, dict]:
    """
    Возвращает (новый план, before_snapshot, rollback_payload).
    Rollback формируется ДО применения — это условие GR-006.
    """
    known = {m.id for m in plan.modules}
    unknown = [m for m in new_order if m not in known]
    if unknown:
        raise ValueError(f"Неизвестные модули: {unknown}")
    if set(new_order) != known:
        raise ValueError("Новый порядок должен содержать ровно те же модули.")

    before = {"site_id": plan.site_id, "module_order": plan.order()}
    rollback = {
        "executable": True,
        "kind": "homepage_reorder",
        "site_id": plan.site_id,
        "restore_order": plan.order(),
        "experiment_id": experiment_id,
    }
    new_modules = []
    for idx, mid in enumerate(new_order):
        m = next(m for m in plan.modules if m.id == mid)
        new_modules.append(ModuleSpec(
            id=m.id, position=idx, freshness_window_days=m.freshness_window_days,
            max_items=m.max_items, pinned_items=list(m.pinned_items),
            pin_expires=dict(m.pin_expires), source_status=list(m.source_status)))

    return HomepagePlan(plan.site_id, new_modules, experiment_id), before, rollback


def default_plan(site_id: str) -> HomepagePlan:
    return HomepagePlan(site_id, [
        ModuleSpec("hero", 0, max_items=1),
        ModuleSpec("new_releases", 1, freshness_window_days=30, source_status=["released"]),
        ModuleSpec("coming_soon", 2, freshness_window_days=60, source_status=["announced", "undated"]),
        ModuleSpec("ongoing", 3, source_status=["released"]),
        ModuleSpec("popular", 4),
        ModuleSpec("editorial_picks", 5, freshness_window_days=14),
        ModuleSpec("collections", 6),
    ])
