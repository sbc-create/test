"""Интерфейс целевого адаптера.

Адаптер — единственное место, где контур изменений соприкасается с реальным
ресурсом. Ни планировщик, ни исполнитель не знают, что находится за ним:
шаблон, каталог, SEO-поле или внешний провайдер.

Два метода различаются намеренно и не взаимозаменяемы:

* `observe` отвечает, что СЕЙЧАС наблюдается у ресурса;
* `verify` сравнивает наблюдаемое с ожидаемым.

Код возврата исполнителя доказательством успеха не является: адаптер может
отчитаться об успехе и не изменить ничего. Поэтому проверка всегда читает
состояние заново.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


class AdapterError(RuntimeError):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.error_code, self.detail = code, detail


@runtime_checkable
class TargetAdapter(Protocol):
    """Контракт адаптера ресурса."""

    #: Имя службы-владельца ресурса. Должно совпадать с матрицей владения:
    #: адаптер, объявивший чужого владельца, применять нельзя.
    owner_service: str

    def capabilities(self) -> dict[str, Any]:
        """Что адаптер умеет: типы ресурсов, операции, обратимость."""

    def plan(self, *, site_id: str, resource_id: str, operation: str,
             requested_change: dict[str, Any],
             observed: dict[str, Any]) -> dict[str, Any]:
        """Детерминированный план: diff, ожидаемое состояние, обратимость.

        Детерминированность обязательна: plan_hash связывает одобрение с
        планом, и план, меняющийся от запуска к запуску, сделал бы это
        связывание бессмысленным.
        """

    def dry_run(self, *, site_id: str, plan: dict[str, Any]) -> dict[str, Any]:
        """Прогон плана без единого эффекта."""

    def apply(self, *, site_id: str, plan: dict[str, Any],
              fencing_token: int) -> dict[str, Any]:
        """Применить план. Обязан быть идемпотентным по plan_hash."""

    def observe(self, *, site_id: str, resource_id: str) -> dict[str, Any]:
        """Фактически наблюдаемое состояние и его отпечаток."""

    def verify(self, *, site_id: str, plan: dict[str, Any],
               observed: dict[str, Any]) -> dict[str, Any]:
        """Сошлось ли наблюдаемое с ожидаемым; что именно разошлось."""

    def rollback(self, *, site_id: str, plan: dict[str, Any],
                 before_fingerprint: str, fencing_token: int) -> dict[str, Any]:
        """Вернуть ресурс к состоянию до применения. Идемпотентно."""


#: Реестр доступных адаптеров. Реальные адаптеры Templates, Content, SEO и
#: провайдеров в этой версии НЕ подключены намеренно: сначала доказывается
#: механизм, потом к нему подводят то, что способно что-то испортить.
РЕЕСТР: dict[str, TargetAdapter] = {}


def зарегистрировать(имя: str, адаптер: TargetAdapter) -> None:
    if имя in РЕЕСТР:
        raise AdapterError("ADAPTER_DUPLICATE", f"адаптер {имя} уже зарегистрирован")
    РЕЕСТР[имя] = адаптер


def получить(resource_type: str) -> TargetAdapter:
    а = РЕЕСТР.get(resource_type)
    if а is None:
        raise AdapterError("ADAPTER_UNKNOWN",
                           f"для ресурса {resource_type} адаптер не подключён")
    return а
