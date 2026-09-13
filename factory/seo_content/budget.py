"""Бюджет контура: отказ до эффекта, а не учёт после.

Владелец назвал потолок, но не назвал валюту:

    SEO_BUDGET_CAP=10000
    SEO_BUDGET_CURRENCY=UNSPECIFIED

Пока валюта не названа, потолок несопоставим с ценой: десять тысяч чего —
неизвестно. Поэтому платный вызов отклоняется не по превышению суммы, а по
самому факту неопределённости — до обращения, до расхода и до появления
строки в чужом счёте. Это единственный безопасный разбор пустого поля:
пустое поле не разрешение подставить значение по умолчанию.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

BUDGET_CAP = 10000
BUDGET_CURRENCY = "UNSPECIFIED"
PAID_PROVIDERS_ENABLED = False


class PaidCallRefused(RuntimeError):
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


#: Поставщики, обращение к которым стоит денег. Бесплатный локальный Qwen в
#: этот список не входит — но и он требует отдельного разрешения на живой
#: режим, потому что это другое решение.
ПЛАТНЫЕ = frozenset({"openai", "anthropic", "yandexgpt", "gigachat",
                     "deepl", "languagetool_premium", "copyscape",
                     "text_ru_premium", "qwen_cloud"})


@dataclass
class BudgetLedger:
    """Учёт попыток и расходов. Расход всегда ноль, пока валюта не названа."""

    cap: int = BUDGET_CAP
    currency: str = BUDGET_CURRENCY
    paid_enabled: bool = PAID_PROVIDERS_ENABLED
    spend: float = 0.0
    refused: list[dict[str, Any]] = field(default_factory=list)
    allowed_calls: int = 0

    def assert_call_allowed(self, *, provider: str,
                            estimated_cost: float | None) -> None:
        """Пропустить вызов или отказать. Отказ — до обращения."""
        платный = provider in ПЛАТНЫЕ or (estimated_cost or 0) > 0
        if not платный:
            self.allowed_calls += 1
            return
        причина = None
        if not self.paid_enabled:
            причина = ("PAID_PROVIDERS_DISABLED",
                       f"{provider}: платные поставщики выключены "
                       f"(PAID_PROVIDERS_ENABLED=NO)")
        elif self.currency == "UNSPECIFIED":
            причина = ("BUDGET_CURRENCY_UNSPECIFIED",
                       f"{provider}: потолок {self.cap} задан без валюты; "
                       f"сравнить цену с потолком нечем")
        elif estimated_cost is None:
            причина = ("COST_UNKNOWN",
                       f"{provider}: стоимость вызова неизвестна")
        elif self.spend + estimated_cost > self.cap:
            причина = ("BUDGET_EXCEEDED",
                       f"{provider}: {self.spend} + {estimated_cost} > "
                       f"{self.cap} {self.currency}")
        if причина:
            self.refused.append({"provider": provider, "code": причина[0],
                                 "detail": причина[1]})
            raise PaidCallRefused(*причина)
        self.spend += float(estimated_cost or 0)
        self.allowed_calls += 1

    def to_dict(self) -> dict[str, Any]:
        return {"SEO_BUDGET_CAP": self.cap,
                "SEO_BUDGET_CURRENCY": self.currency,
                "PAID_PROVIDERS_ENABLED": "YES" if self.paid_enabled else "NO",
                "PAID_SPEND": self.spend,
                "refused_calls": list(self.refused),
                "allowed_free_calls": self.allowed_calls}


@dataclass
class Estimate:
    """Оценка объёма работы контура. В токенах и вызовах, не в деньгах.

    Перевод в деньги здесь не делается намеренно: он требует валюты и
    прейскуранта, а ни того, ни другого нам не назвали. Число, умноженное на
    выдуманную ставку, выглядело бы как смета.
    """

    entities: int
    tokens_per_entity: int
    calls_per_entity: int = 1

    @property
    def total_calls(self) -> int:
        return self.entities * self.calls_per_entity

    @property
    def total_tokens(self) -> int:
        return self.entities * self.tokens_per_entity * self.calls_per_entity

    def to_dict(self) -> dict[str, Any]:
        return {"entities": self.entities,
                "tokens_per_entity": self.tokens_per_entity,
                "calls_per_entity": self.calls_per_entity,
                "total_calls": self.total_calls,
                "total_tokens": self.total_tokens,
                "money_estimate": "UNSPECIFIED",
                "money_estimate_reason": (
                    "валюта бюджета не названа и прейскурант не согласован; "
                    "перевод объёма в деньги был бы выдумкой")}


def estimate_catalog(entities: int, *, tokens_per_entity: int = 1400,
                     calls_per_entity: int = 1) -> Estimate:
    return Estimate(entities, tokens_per_entity, calls_per_entity)
