"""
Единый справочник статусов (ТЗ §14).

Смысл этого модуля — сделать невозможным «тихое» враньё в отчёте.
Отсутствие данных обязано иметь имя: NOT_MEASURED или DATA_DELAY, но не 0.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class Status(str, Enum):
    READY = "READY"
    RUNNING = "RUNNING"
    BLOCKED_ACCESS = "BLOCKED_ACCESS"
    BLOCKED_SECRET = "BLOCKED_SECRET"
    BLOCKED_DEPLOYMENT = "BLOCKED_DEPLOYMENT"
    BLOCKED_RIGHTS = "BLOCKED_RIGHTS"
    BLOCKED_OWNER_DECISION = "BLOCKED_OWNER_DECISION"
    DATA_DELAY = "DATA_DELAY"
    NOT_MEASURED = "NOT_MEASURED"
    INCONCLUSIVE = "INCONCLUSIVE"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


BLOCKED_STATUSES = frozenset({
    Status.BLOCKED_ACCESS, Status.BLOCKED_SECRET, Status.BLOCKED_DEPLOYMENT,
    Status.BLOCKED_RIGHTS, Status.BLOCKED_OWNER_DECISION,
})

# Статусы, при которых число публиковать нельзя ни в каком виде.
NO_VALUE_STATUSES = frozenset({
    Status.NOT_MEASURED, Status.DATA_DELAY, Status.INCONCLUSIVE,
    Status.FAILED, *BLOCKED_STATUSES,
})

# Разделитель разрядов в отчётах. Неразрывный пробел выбран намеренно:
# число не разрывается переносом строки. Константа вынесена, чтобы разделитель
# нельзя было изменить случайной правкой невидимого символа в строке.
THOUSANDS_SEPARATOR = " "

RU_LABEL = {
    Status.READY: "готово",
    Status.RUNNING: "выполняется",
    Status.BLOCKED_ACCESS: "нет доступа",
    Status.BLOCKED_SECRET: "нет секрета в Secret Hub",
    Status.BLOCKED_DEPLOYMENT: "нет выкладки или отката",
    Status.BLOCKED_RIGHTS: "нет подтверждённых прав",
    Status.BLOCKED_OWNER_DECISION: "нужно решение владельца",
    Status.DATA_DELAY: "данные задерживаются",
    Status.NOT_MEASURED: "не измерено",
    Status.INCONCLUSIVE: "данных недостаточно",
    Status.FAILED: "ошибка",
    Status.ROLLED_BACK: "откачено",
}


class ExperimentOutcome(str, Enum):
    """ТЗ §5, шаг 7. Отдельно от Status: это исход гипотезы, а не состояние джоба."""

    WIN = "WIN"
    LOSS = "LOSS"
    NEUTRAL = "NEUTRAL"
    INCONCLUSIVE = "INCONCLUSIVE"
    INVALIDATED = "INVALIDATED"
    ROLLED_BACK = "ROLLED_BACK"


class Confidence(str, Enum):
    """ТЗ §5, шаг 3. Каждый вывод обязан нести уровень уверенности."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass(frozen=True)
class Measurement:
    """
    Значение показателя вместе с происхождением. Отчёт печатает только Measurement:
    каждое число несёт источник, период, время обновления и статус качества (ТЗ §10).

    Конструктор запрещает две ошибки по построению: значение при статусе
    «не измерено» и отсутствие значения при статусе READY.
    """

    metric: str
    value: float | int | None
    status: Status
    source: str
    period: str
    as_of: str
    note: str = ""
    unit: str = ""

    def __post_init__(self) -> None:
        if self.status in NO_VALUE_STATUSES and self.value is not None:
            raise ValueError(
                f"{self.metric}: статус {self.status.value} несовместим со значением "
                f"{self.value!r} — отсутствие данных не заменяется числом.")
        if self.status is Status.READY and self.value is None:
            raise ValueError(f"{self.metric}: статус READY требует значения.")

    @property
    def measured(self) -> bool:
        return self.status is Status.READY and self.value is not None

    def render(self) -> str:
        """Единственный разрешённый способ показать показатель человеку."""
        if not self.measured:
            detail = f" ({self.note})" if self.note else ""
            return f"{self.status.value}{detail}"
        if isinstance(self.value, (int, float)) and abs(self.value) >= 1000:
            shown = f"{self.value:,.0f}".replace(",", THOUSANDS_SEPARATOR)
        else:
            shown = str(self.value)
        unit = f" {self.unit}" if self.unit else ""
        return f"{shown}{unit} [{self.source}, {self.period}, обновлено {self.as_of}]"

    def to_dict(self) -> dict[str, Any]:
        return {"metric": self.metric, "value": self.value, "status": self.status.value,
                "source": self.source, "period": self.period, "as_of": self.as_of,
                "note": self.note, "unit": self.unit}


def measured(metric: str, value: float | int, source: str, period: str,
             as_of: str, unit: str = "", note: str = "") -> Measurement:
    return Measurement(metric=metric, value=value, status=Status.READY, source=source,
                       period=period, as_of=as_of, unit=unit, note=note)


def not_measured(metric: str, reason: str, source: str = "n/a") -> Measurement:
    return Measurement(metric=metric, value=None, status=Status.NOT_MEASURED,
                       source=source, period="n/a", as_of="n/a", note=reason)


def data_delay(metric: str, reason: str, source: str, expected_by: str) -> Measurement:
    return Measurement(metric=metric, value=None, status=Status.DATA_DELAY,
                       source=source, period="n/a", as_of=expected_by, note=reason)


def inconclusive(metric: str, reason: str, source: str = "n/a") -> Measurement:
    return Measurement(metric=metric, value=None, status=Status.INCONCLUSIVE,
                       source=source, period="n/a", as_of="n/a", note=reason)


def blocked(metric: str, status: Status, reason: str) -> Measurement:
    if status not in BLOCKED_STATUSES:
        raise ValueError(f"{status} не является BLOCKED_*")
    return Measurement(metric=metric, value=None, status=status,
                       source="n/a", period="n/a", as_of="n/a", note=reason)
