"""Пул шаблонов: free → reserved → assigned.

Шаблон — исчерпаемый ресурс. Пока он выдавался «по договорённости», два заказа,
поданных в одну минуту, получали один и тот же профиль, и расходились они уже
на живых доменах. Поэтому выдача здесь атомарна, а не аккуратна.

Три свойства, каждое из которых проверяется тестом:

* **Атомарность.** Два одновременных резервирования получают разные
  `template_id`. Обеспечивается блокировкой журнала, а не порядком строк.
* **Идемпотентность.** Повтор того же заказа (`order_id`) возвращает прежнее
  резервирование и не расходует второй шаблон. Повторный запуск onboarding —
  штатное событие, а не авария.
* **Необратимость назначения.** Назначенный шаблон выбывает из свободного пула
  и сам по себе не возвращается. Исходники при этом остаются на месте: шаблон
  назначен сайту, а не израсходован.

Снятие зависшего резерва существует, но требует явного подтверждения: тихий
автоматический возврат «зависшего» резерва однажды отдал бы второму заказу
шаблон, по которому первый уже собрал релиз.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from factory.cell import ledger
from factory.paths import PATHS

SCHEMA_VERSION = "1.0"
POOL_PATH = "config/template-pool.json"

FREE = "free"
RESERVED = "reserved"
ASSIGNED = "assigned"
STATUSES = (FREE, RESERVED, ASSIGNED)


class TemplateError(RuntimeError):
    pass


class PoolExhausted(TemplateError):
    """Свободных шаблонов нет.

    Отдельный тип: это не ошибка ввода и не сбой — это исчерпанный ресурс,
    и ответ на него — пополнить пул, а не повторить заказ.
    """


class NotReserved(TemplateError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def pool_path() -> Path:
    return PATHS.root / POOL_PATH


@dataclass(frozen=True)
class Reservation:
    template_id: str
    order_id: str
    site_id: str
    domain: str
    status: str
    reserved_at: str
    assigned_at: str | None = None

    @property
    def is_assigned(self) -> bool:
        return self.status == ASSIGNED


def _entries(pool: dict[str, Any]) -> list[dict[str, Any]]:
    templates = pool.get("templates")
    if not isinstance(templates, list):
        raise TemplateError("в пуле шаблонов нет списка templates")
    return templates


def _reservation(entry: dict[str, Any]) -> Reservation:
    holder = entry.get("assignment") or {}
    return Reservation(
        template_id=entry["template_id"],
        order_id=holder.get("order_id", ""),
        site_id=holder.get("site_id", ""),
        domain=holder.get("domain", ""),
        status=entry["status"],
        reserved_at=holder.get("reserved_at", ""),
        assigned_at=holder.get("assigned_at"),
    )


def load(path: Path | None = None) -> dict[str, Any]:
    return ledger.read(path or pool_path())


def free_templates(path: Path | None = None) -> tuple[str, ...]:
    pool = load(path)
    return tuple(e["template_id"] for e in _entries(pool) if e["status"] == FREE)


def find_by_order(order_id: str, path: Path | None = None) -> Reservation | None:
    """Резервирование по заказу. Основа идемпотентности: сначала смотрим, не
    выдавали ли мы уже шаблон этому заказу."""
    for entry in _entries(load(path)):
        holder = entry.get("assignment") or {}
        if holder.get("order_id") == order_id:
            return _reservation(entry)
    return None


def find_by_site(site_id: str, path: Path | None = None) -> Reservation | None:
    for entry in _entries(load(path)):
        holder = entry.get("assignment") or {}
        if holder.get("site_id") == site_id:
            return _reservation(entry)
    return None


def reserve(*, order_id: str, site_id: str, domain: str, family: str | None = None,
            template_id: str | None = None, path: Path | None = None) -> Reservation:
    """Зарезервировать один шаблон за заказом.

    Повтор того же `order_id` возвращает прежнее резервирование — второй шаблон
    не расходуется и второй проект не заводится.
    """
    if not order_id or not site_id or not domain:
        raise TemplateError("резервирование требует order_id, site_id и domain")
    target = path or pool_path()
    result: dict[str, Any] = {}

    def change(pool: dict[str, Any]) -> dict[str, Any]:
        entries = _entries(pool)
        for entry in entries:
            holder = entry.get("assignment") or {}
            if holder.get("order_id") == order_id:
                # Тот же заказ. Возвращаем то же самое и ничего не расходуем.
                result["entry"] = entry
                return pool
        # Другой сайт с тем же site_id уже держит шаблон — повторный onboarding
        # того же сайта под новым номером заказа не должен забрать второй.
        for entry in entries:
            holder = entry.get("assignment") or {}
            if holder.get("site_id") == site_id:
                raise TemplateError(
                    f"за сайтом {site_id} уже закреплён шаблон "
                    f"{entry['template_id']} (заказ {holder.get('order_id')}); "
                    "второй шаблон одному сайту не выдаётся"
                )
        candidates = [e for e in entries if e["status"] == FREE]
        if family:
            candidates = [e for e in candidates if e.get("family") == family]
        if template_id:
            candidates = [e for e in candidates if e["template_id"] == template_id]
            if not candidates:
                raise TemplateError(
                    f"шаблон {template_id} не свободен или отсутствует в пуле"
                )
        if not candidates:
            raise PoolExhausted(
                "свободных шаблонов нет"
                + (f" в семействе {family}" if family else "")
            )
        # Порядок детерминирован: при равных условиях два прогона фабрики
        # выдают один и тот же шаблон, и отчёт воспроизводится.
        chosen = sorted(candidates, key=lambda e: e["template_id"])[0]
        chosen["status"] = RESERVED
        chosen["assignment"] = {
            "order_id": order_id,
            "site_id": site_id,
            "domain": domain,
            "reserved_at": utc_now(),
            "assigned_at": None,
        }
        result["entry"] = chosen
        return pool

    ledger.mutate(target, change)
    return _reservation(result["entry"])


def assign(*, order_id: str, path: Path | None = None) -> Reservation:
    """Перевести резерв в назначение. После этого шаблон принадлежит сайту."""
    target = path or pool_path()
    result: dict[str, Any] = {}

    def change(pool: dict[str, Any]) -> dict[str, Any]:
        for entry in _entries(pool):
            holder = entry.get("assignment") or {}
            if holder.get("order_id") != order_id:
                continue
            if entry["status"] == ASSIGNED:
                result["entry"] = entry
                return pool
            if entry["status"] != RESERVED:
                raise NotReserved(
                    f"шаблон {entry['template_id']} в состоянии {entry['status']}: "
                    "назначать можно только зарезервированный"
                )
            entry["status"] = ASSIGNED
            holder["assigned_at"] = utc_now()
            entry["assignment"] = holder
            result["entry"] = entry
            return pool
        raise NotReserved(f"по заказу {order_id} резервирования нет")

    ledger.mutate(target, change)
    return _reservation(result["entry"])


def release_reservation(*, order_id: str, confirmed_no_pending: bool,
                        reason: str, path: Path | None = None) -> Reservation:
    """Снять зависший резерв.

    Требует явного подтверждения, что незавершённых действий по заказу нет.
    Назначенный шаблон не снимается здесь ни при каких условиях: у
    опубликованного сайта шаблон не отзывается сам.
    """
    if not confirmed_no_pending:
        raise TemplateError(
            "снятие резерва требует подтверждения, что незавершённых действий "
            "по заказу нет: иначе второй заказ получит шаблон, по которому "
            "первый уже собрал релиз"
        )
    if not reason.strip():
        raise TemplateError("снятие резерва без причины не принимается")
    target = path or pool_path()
    result: dict[str, Any] = {}

    def change(pool: dict[str, Any]) -> dict[str, Any]:
        for entry in _entries(pool):
            holder = entry.get("assignment") or {}
            if holder.get("order_id") != order_id:
                continue
            if entry["status"] == ASSIGNED:
                raise TemplateError(
                    f"шаблон {entry['template_id']} назначен сайту "
                    f"{holder.get('site_id')}; назначение не снимается снятием резерва"
                )
            before = _reservation(entry)
            entry["status"] = FREE
            entry["assignment"] = None
            history = entry.setdefault("history", [])
            history.append({
                "event": "reservation_released",
                "order_id": order_id,
                "site_id": before.site_id,
                "reason": reason,
                "at": utc_now(),
            })
            result["entry"] = {**entry, "assignment": {
                "order_id": order_id, "site_id": before.site_id,
                "domain": before.domain, "reserved_at": before.reserved_at,
                "assigned_at": None,
            }}
            return pool
        raise NotReserved(f"по заказу {order_id} резервирования нет")

    ledger.mutate(target, change)
    entry = dict(result["entry"])
    entry["status"] = FREE
    return _reservation(entry)
