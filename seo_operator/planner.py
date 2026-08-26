"""
Goal Planner — самостоятельная постановка целей (ТЗ §5, шаг 4).

priority = expected_traffic_gain × confidence × strategic_fit
           ÷ (effort × risk × time_to_result)

Отдельно от формулы здесь решается вторая, более важная задача: не дать очереди
выродиться в поток дешёвой косметики. Балансировка по категориям — обязательный
этап, а не опция, потому что формула сама по себе всегда предпочтёт правку title
исправлению технического долга.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from typing import Any, Iterable, Sequence

from .statuses import Confidence, Status

CONFIDENCE_WEIGHT = {Confidence.LOW: 0.3, Confidence.MEDIUM: 0.65, Confidence.HIGH: 1.0}


class Category(str, Enum):
    TECHNICAL_HEALTH = "technical_health"
    EXISTING_PAGES = "existing_pages"
    NEW_DEMAND = "new_demand"
    CONTENT = "content"
    INTERNAL_LINKING = "internal_linking"
    CTR = "ctr"
    PORTFOLIO_SCALING = "portfolio_scaling"


# Минимальная доля очереди на категорию (ТЗ §5, шаг 4: очередь балансируется).
# Сумма < 1: остаток распределяется по приоритету.
MIN_SHARE = {
    Category.TECHNICAL_HEALTH: 0.20,
    Category.EXISTING_PAGES: 0.15,
    Category.NEW_DEMAND: 0.10,
    Category.CONTENT: 0.10,
    Category.INTERNAL_LINKING: 0.05,
    Category.CTR: 0.05,
}


class IncompleteTask(ValueError):
    """Задача без baseline, критериев или срока оценки в очередь не попадает."""


@dataclass
class Task:
    task_id: str
    site_id: str
    category: Category
    problem: str                       # исходная проблема или возможность
    hypothesis: str
    urls: list[str]
    cluster: str | None
    baseline: dict[str, Any]
    expected_traffic_gain: float       # уников/сут, оценка
    confidence: Confidence
    strategic_fit: float               # 0.5..1.5
    effort: float                      # человеко-часы, >0
    risk: float                        # 1..10
    time_to_result_days: int           # >0
    success_criterion: str
    failure_criterion: str
    stop_criterion: str
    rollback_plan: str
    evaluate_after: str
    requires_manual_approval: bool = False
    priority: float = 0.0
    rationale: str = ""

    def validate(self) -> None:
        missing = [name for name, value in (
            ("problem", self.problem), ("hypothesis", self.hypothesis),
            ("success_criterion", self.success_criterion),
            ("failure_criterion", self.failure_criterion),
            ("stop_criterion", self.stop_criterion),
            ("rollback_plan", self.rollback_plan)) if not (value or "").strip()]
        if missing:
            raise IncompleteTask(f"{self.task_id}: не заданы {missing}")
        if not self.baseline:
            raise IncompleteTask(f"{self.task_id}: пустой baseline")
        if not self.urls:
            raise IncompleteTask(f"{self.task_id}: не указан ни один URL")
        if self.effort <= 0 or self.risk <= 0 or self.time_to_result_days <= 0:
            raise IncompleteTask(
                f"{self.task_id}: effort/risk/time_to_result должны быть больше нуля "
                "— иначе приоритет уходит в бесконечность")
        try:
            date.fromisoformat(self.evaluate_after)
        except ValueError as exc:
            raise IncompleteTask(f"{self.task_id}: evaluate_after не дата") from exc


def compute_priority(task: Task) -> float:
    """
    Формула ТЗ §5. Время переводится в недели, чтобы срок в 1 и 7 дней
    не различались на порядок и не выдавливали всё остальное из очереди.
    """
    task.validate()
    gain = max(0.0, task.expected_traffic_gain)
    conf = CONFIDENCE_WEIGHT[task.confidence]
    fit = min(1.5, max(0.5, task.strategic_fit))
    weeks = max(0.5, task.time_to_result_days / 7.0)
    denominator = task.effort * task.risk * weeks
    return round(gain * conf * fit / denominator, 4)


def prioritize(tasks: Sequence[Task]) -> list[Task]:
    for t in tasks:
        t.priority = compute_priority(t)
        t.rationale = (f"gain={t.expected_traffic_gain:.0f} × conf={CONFIDENCE_WEIGHT[t.confidence]} "
                       f"× fit={t.strategic_fit} ÷ (effort={t.effort} × risk={t.risk} "
                       f"× {t.time_to_result_days/7:.1f}нед)")
    return sorted(tasks, key=lambda t: -t.priority)


@dataclass
class Queue:
    selected: list[Task]
    deferred: list[Task]
    balance: dict[str, int]
    warnings: list[str] = field(default_factory=list)


def build_queue(tasks: Sequence[Task], capacity: int,
                min_share: dict[Category, float] | None = None) -> Queue:
    """
    Формирует очередь на период с соблюдением минимальных долей по категориям.

    Сначала каждая категория получает свою квоту (лучшие задачи внутри категории),
    затем остаток заполняется по общему приоритету. Так техдолг не вытесняется
    косметикой, даже если у косметики приоритет выше.
    """
    if capacity <= 0:
        return Queue(selected=[], deferred=list(tasks), balance={}, warnings=["Нулевая ёмкость."])

    min_share = min_share or MIN_SHARE
    ranked = prioritize(tasks)
    by_category: dict[Category, list[Task]] = defaultdict(list)
    for t in ranked:
        by_category[t.category].append(t)

    selected: list[Task] = []
    warnings: list[str] = []
    taken: set[str] = set()

    for category, share in sorted(min_share.items(), key=lambda kv: -kv[1]):
        quota = int(math.floor(capacity * share))
        if quota == 0:
            continue
        available = by_category.get(category, [])
        if not available:
            warnings.append(
                f"Категория '{category.value}' зарезервировала {quota} мест, но задач нет — "
                "это пробел в диагностике, а не свободная ёмкость.")
            continue
        for t in available[:quota]:
            selected.append(t)
            taken.add(t.task_id)

    for t in ranked:
        if len(selected) >= capacity:
            break
        if t.task_id not in taken:
            selected.append(t)
            taken.add(t.task_id)

    selected = sorted(selected, key=lambda t: -t.priority)[:capacity]
    taken = {t.task_id for t in selected}
    deferred = [t for t in ranked if t.task_id not in taken]

    balance = Counter(t.category.value for t in selected)

    cosmetic = sum(1 for t in selected
                   if t.category in (Category.CTR, Category.EXISTING_PAGES) and t.effort <= 1)
    if selected and cosmetic / len(selected) > 0.6:
        warnings.append(
            f"{cosmetic} из {len(selected)} задач — мелкие правки. Очередь смещена "
            "в косметику: проверьте, не пропущены ли технические проблемы.")

    if not any(t.category is Category.TECHNICAL_HEALTH for t in selected):
        warnings.append("В очереди нет ни одной задачи технического здоровья.")

    return Queue(selected=selected, deferred=deferred, balance=dict(balance), warnings=warnings)


def new_task_id(site_id: str, seq: int, today: date | None = None) -> str:
    today = today or date.today()
    return f"TASK-{today:%Y%m%d}-{site_id}-{seq:03d}"


def default_evaluate_after(time_to_result_days: int, today: date | None = None,
                           data_lag_days: int = 3) -> str:
    """
    Дата повторной оценки с запасом на задержку данных: оценивать ровно в срок
    эффекта значит смотреть на неполные дни.
    """
    today = today or date.today()
    return (today + timedelta(days=time_to_result_days + data_lag_days)).isoformat()
