"""Read-only контракт состояния индексации для потребителей.

Потребители — SEO и Templates. Оба **читают**. Метода, меняющего состояние,
здесь нет и появиться не может: команды ``OPEN`` и ``CLOSE`` живут в
:mod:`factory.site_engine.audit.indexing` и требуют разрешения владельца.

Контракт отвечает на вопросы, которые потребителю нужно различать, а не
сваливать в один «не открыт»:

* сайт **зарегистрирован и закрыт** — решение принято, оно отрицательное;
* сайт **не зарегистрирован** — решения не принимали, по умолчанию закрыт;
* **провайдер недоступен** — ответа нет вовсе, и это не повод менять живое
  состояние; берётся подтверждённый снимок, а релиз блокируется.

Разница между первым и третьим — та самая, из-за которой закрывалась живая
витрина: недоступность реестра принимали за решение закрыть.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from factory.site_engine.audit.indexing import (
    CLOSED,
    СХЕМА_СОСТОЯНИЯ,
)
from factory.site_engine.audit.indexing import (
    снимок as _снимок,
)
from factory.site_engine.audit.indexing import (
    состояние as _состояние,
)

#: Версия самого контракта. Отличается от версии состояния: схема данных может
#: остаться прежней, а форма ответа — измениться.
ВЕРСИЯ_КОНТРАКТА = "fleet-indexing-read/1.0.0"

ЗДОРОВ = "HEALTHY"
НЕДОСТУПЕН = "UNAVAILABLE"
ПОВРЕЖДЁН = "CORRUPT"

LKG_НЕ_НУЖЕН = "NOT_USED"
LKG_ПРИМЕНЁН = "SERVING_LAST_KNOWN_GOOD"
LKG_ОТСУТСТВУЕТ = "NONE_AVAILABLE"
LKG_ПОВРЕЖДЁН = "REJECTED_CORRUPT"


class ContractError(RuntimeError):
    """Запрос к контракту невозможно выполнить."""


class UnknownSite(ContractError):
    """Такого site_id нет в реестре. Это не «закрыт», это «не знаем такого»."""


@dataclass(frozen=True)
class Ответ:
    """Детерминированный ответ контракта."""

    contract_version: str
    schema_version: str
    provider_health: str
    lkg_status: str
    snapshot_digest: str | None
    taken_at: str | None
    sites: list[dict[str, Any]] = field(default_factory=list)
    release_blocked: bool = False
    blockers: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        """Сериализация детерминирована: одинаковый ответ — одинаковые байты."""
        return json.dumps(
            {
                "contract_version": self.contract_version,
                "schema_version": self.schema_version,
                "provider_health": self.provider_health,
                "lkg_status": self.lkg_status,
                "snapshot_digest": self.snapshot_digest,
                "taken_at": self.taken_at,
                "release_blocked": self.release_blocked,
                "blockers": sorted(self.blockers),
                "sites": sorted(self.sites, key=lambda s: s["site_id"]),
            },
            ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        )


def _поля(строка: dict[str, Any], домены: dict[str, str] | None = None) -> dict[str, Any]:
    """Ровно те поля, которые объявлены контрактом, и ни одного лишнего.

    ``domain`` — **производное** значение из Site Registry, а не ключ. Ключ —
    ``site_id``: домен меняется, идентификатор нет. Потребителю домен нужен,
    чтобы сопоставить решение с витриной, и отдать его удобнее, чем заставлять
    каждого потребителя ходить в реестр отдельно.

    ``last_known_good_revision`` равна текущей, пока провайдер здоров: снимок
    подтверждён тем, что он прочитан у источника. При отдаче подтверждённого
    снимка она остаётся той, что была на момент подтверждения.
    """
    return {
        "site_id": строка["site_id"],
        "domain": (домены or {}).get(строка["site_id"]),
        "desired_state": строка["desired_state"],
        "revision": строка["revision"],
        "last_known_good_revision": строка["revision"],
        "updated_at": строка.get("updated_at"),
        "source_event_id": строка.get("event_id"),
        "approval_ref": строка.get("approval_id"),
        "reason": строка.get("reason"),
        "snapshot_digest": строка.get("snapshot_digest"),
        "schema_version": строка.get("schema_version") or СХЕМА_СОСТОЯНИЯ,
        "registered": bool(строка.get("registered", True)),
    }


def прочитать(
    соед: sqlite3.Connection | None, *, last_known_good: Ответ | None = None,
    домены: dict[str, str] | None = None,
) -> Ответ:
    """Снимок всего флота. ``None`` вместо соединения означает недоступность.

    Три исхода, и все три названы явно. Пустая матрица не выдаётся за «всё
    закрыто»: «закрыть всё» — тоже изменение, и принимать его за отсутствие
    ответа нельзя.
    """
    if соед is None:
        if last_known_good is None:
            return Ответ(
                contract_version=ВЕРСИЯ_КОНТРАКТА, schema_version=СХЕМА_СОСТОЯНИЯ,
                provider_health=НЕДОСТУПЕН, lkg_status=LKG_ОТСУТСТВУЕТ,
                snapshot_digest=None, taken_at=None, sites=[],
                release_blocked=True,
                blockers=["провайдер недоступен и подтверждённого снимка нет"],
            )
        return Ответ(
            contract_version=ВЕРСИЯ_КОНТРАКТА,
            schema_version=last_known_good.schema_version,
            provider_health=НЕДОСТУПЕН, lkg_status=LKG_ПРИМЕНЁН,
            snapshot_digest=last_known_good.snapshot_digest,
            taken_at=last_known_good.taken_at, sites=list(last_known_good.sites),
            release_blocked=True,
            blockers=["провайдер недоступен: отдаётся подтверждённый снимок"],
        )

    try:
        сн = _снимок(соед)
    except sqlite3.Error as ошибка:
        if last_known_good is None:
            return Ответ(
                contract_version=ВЕРСИЯ_КОНТРАКТА, schema_version=СХЕМА_СОСТОЯНИЯ,
                provider_health=ПОВРЕЖДЁН, lkg_status=LKG_ОТСУТСТВУЕТ,
                snapshot_digest=None, taken_at=None, sites=[],
                release_blocked=True, blockers=[f"состояние повреждено: {ошибка}"],
            )
        return Ответ(
            contract_version=ВЕРСИЯ_КОНТРАКТА,
            schema_version=last_known_good.schema_version,
            provider_health=ПОВРЕЖДЁН, lkg_status=LKG_ПРИМЕНЁН,
            snapshot_digest=last_known_good.snapshot_digest,
            taken_at=last_known_good.taken_at, sites=list(last_known_good.sites),
            release_blocked=True, blockers=[f"состояние повреждено: {ошибка}"],
        )

    return Ответ(
        contract_version=ВЕРСИЯ_КОНТРАКТА, schema_version=сн["schema_version"],
        provider_health=ЗДОРОВ, lkg_status=LKG_НЕ_НУЖЕН,
        snapshot_digest=сн["snapshot_digest"], taken_at=сн["taken_at"],
        sites=[_поля(с, домены) for с in сн["sites"]],
    )


def прочитать_сайт(
    соед: sqlite3.Connection, site_id: str, *, известные_сайты=None,
    домены: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Состояние одного сайта.

    ``известные_сайты`` — реестр. Если он передан и сайта в нём нет, это
    ошибка, а не ``CLOSED``: «не знаем такого» и «решили не индексировать» —
    разные ответы, и путать их нельзя.
    """
    if известные_сайты is not None and site_id not in известные_сайты:
        raise UnknownSite(
            f"site_id {site_id!r} отсутствует в Site Registry; "
            "это не то же самое, что закрытый сайт"
        )
    return _поля(_состояние(соед, site_id), домены)


def сохранить_lkg(ответ: Ответ, путь: Path) -> Path:
    """Сохранить подтверждённый снимок. Это кеш чтения, а не источник решений."""
    цель = Path(путь)
    цель.parent.mkdir(parents=True, exist_ok=True)
    цель.write_text(ответ.to_json() + "\n", encoding="utf-8")
    return цель


def загрузить_lkg(путь: Path) -> Ответ:
    """Прочитать подтверждённый снимок. Повреждённый не применяется."""
    текст = Path(путь).read_text(encoding="utf-8")
    if not текст.strip():
        raise ContractError("подтверждённый снимок пуст")
    try:
        д = json.loads(текст)
    except ValueError as ошибка:
        raise ContractError(f"подтверждённый снимок не разбирается — {ошибка}") from ошибка
    if д.get("contract_version") != ВЕРСИЯ_КОНТРАКТА:
        raise ContractError(
            f"чужая версия контракта {д.get('contract_version')!r}: "
            "читать снимок по правилам другой версии нельзя"
        )
    if not д.get("snapshot_digest"):
        raise ContractError("в снимке нет отпечатка: подтвердить его нечем")
    return Ответ(
        contract_version=д["contract_version"], schema_version=д["schema_version"],
        provider_health=д["provider_health"], lkg_status=д["lkg_status"],
        snapshot_digest=д["snapshot_digest"], taken_at=д.get("taken_at"),
        sites=д.get("sites") or [],
        release_blocked=bool(д.get("release_blocked")),
        blockers=list(д.get("blockers") or []),
    )


def состояние_для_потребителя(ответ: Ответ, site_id: str) -> str:
    """Удобство для потребителя: ``OPEN`` или ``CLOSED`` по ответу контракта."""
    for с in ответ.sites:
        if с["site_id"] == site_id:
            return с["desired_state"]
    return CLOSED
