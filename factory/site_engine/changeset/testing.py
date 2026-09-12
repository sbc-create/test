"""Оснастка испытаний контура изменений.

Лежит в пакете рядом с тестовым адаптером, а не в каталоге тестов: репозиторий
собирает тесты в режиме importlib, и модуль из каталога тестов оттуда не
импортируется. Модуль ничего не делает при импорте и в рабочем пути не
используется.
"""
from __future__ import annotations

import uuid
from typing import Any

from . import store as S
from .fake_adapter import FakeAdapter
from .registry_client import RegistryUnavailable

РЕСУРС = FakeAdapter.resource_type

#: Идентификаторы заведомо не совпадают ни с одним настоящим: совпадение
#: однажды привело бы к тому, что испытание изменило что-то у живого сайта.
САЙТЫ: dict[str, dict[str, Any]] = {
    "test-alpha-0001": {"site_id": "test-alpha-0001", "environment": "test",
                        "lifecycle_state": "ACTIVE"},
    "test-beta-0002": {"site_id": "test-beta-0002", "environment": "test",
                       "lifecycle_state": "ACTIVE"},
    "test-gamma-0003": {"site_id": "test-gamma-0003", "environment": "test",
                        "lifecycle_state": "ACTIVE"},
    "test-prod-0004": {"site_id": "test-prod-0004", "environment": "production",
                       "lifecycle_state": "ACTIVE"},
    "test-retired-0005": {"site_id": "test-retired-0005", "environment": "test",
                          "lifecycle_state": "RETIRED"},
}


class FakeRegistry:
    """Реестр испытаний: отвечает как versioned API, ничего не читая извне."""

    def __init__(self, версия: int = 100, сайты: dict | None = None):
        self._версия = версия
        self._сайты = dict(сайты or САЙТЫ)
        self.недоступен = False

    def версия(self) -> int:
        if self.недоступен:
            raise RegistryUnavailable("реестр недоступен (испытание)")
        return self._версия

    def сдвинуть_версию(self, на: int = 1) -> int:
        self._версия += на
        return self._версия

    def сайт(self, site_id: str) -> dict | None:
        return self._сайты.get(site_id)

    def сайты(self) -> list[dict]:
        if self.недоступен:
            raise RegistryUnavailable("реестр недоступен (испытание)")
        return list(self._сайты.values())


def заявка(**kw) -> dict[str, Any]:
    д = {
        "resource_type": РЕСУРС,
        "resource_id": "res-1",
        "operation_type": "update",
        "target_site_ids": ["test-alpha-0001"],
        "requested_change": {"title": "новое значение"},
        "idempotency_key": "k-" + uuid.uuid4().hex[:12],
        "correlation_id": "corr-" + uuid.uuid4().hex[:8],
    }
    д.update(kw)
    return д


def создать(соед, **kw) -> str:
    return S.создать(соед, заявка(**kw), producer_service="templates",
                     actor_id="service:templates",
                     actor_type="SERVICE")["changeset_id"]


def довести_до_одобрения(соед, двигатель, cid: str, *,
                         срок: str = "2099-01-01T00:00:00Z") -> None:
    двигатель.валидировать(cid, actor_id="service:control-plane",
                           служба="control-plane")
    двигатель.запросить_одобрение(cid, actor_id="service:templates",
                                  служба="templates", expires_at=срок)
    двигатель.одобрить(cid, approver_id="human:owner", служба="human_owner",
                       actor_type="HUMAN", expires_at=срок)
