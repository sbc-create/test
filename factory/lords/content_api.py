"""Адаптер Content API CDNVideoHub для направления Lords.

Адаптер управляется описанием контракта, а не зашитыми адресами: пути, разбивка
на страницы и соответствие полей берутся из `knowledge/cdnvideohub/content-api.yaml`.
Пока контракт не передан или не переданы учётные данные, адаптер честно отвечает
статусом и не подбирает адреса самостоятельно.

Что работает без токена: разбор и проверка контракта, план синхронизации,
идемпотентность, защита от дублей, политика устаревших данных и запись
доказательств. Не работает ровно одно — живой запрос.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from factory.paths import PATHS

BLOCKED_CREDENTIALS = "BLOCKED_INPUT_CDNVIDEOHUB_CREDENTIALS"
BLOCKED_CONTRACT = "BLOCKED_INPUT_CDNVIDEOHUB_CONTRACT"
READY = "READY"

CONTRACT_REF = "knowledge/cdnvideohub/content-api.yaml"

#: Обязательные разделы переданного контракта. Отсутствие любого означает, что
#: контракт передан наполовину, а половина контракта хуже его отсутствия:
#: недостающее пришлось бы додумывать.
REQUIRED_CONTRACT_SECTIONS = ("base_url", "auth", "endpoints", "pagination", "mapping")

#: Доля прежнего каталога, ниже которой ответ считается частичным. Удаление по
#: такому ответу запрещено: пустой или короткий ответ — это отказ источника, а
#: не сообщение «каталог опустел».
MIN_RESPONSE_FRACTION = 0.5


@dataclass(frozen=True)
class Contract:
    status: str
    raw: dict = field(default_factory=dict)

    @property
    def provided(self) -> bool:
        return self.status == "provided"

    def problems(self) -> list[str]:
        if not self.provided:
            return [f"контракт не передан (status: {self.status})"]
        return [f"в контракте нет раздела «{s}»" for s in REQUIRED_CONTRACT_SECTIONS
                if not self.raw.get(s)]


@dataclass(frozen=True)
class Readiness:
    status: str
    reason: str

    @property
    def ready(self) -> bool:
        return self.status == READY


def load_contract(path: Path | str | None = None) -> Contract:
    target = Path(path) if path else PATHS.root / CONTRACT_REF
    if not target.exists():
        return Contract(status="missing")
    data = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    return Contract(status=str(data.get("status", "not_provided")), raw=data)


def readiness(contract: Contract, *, token_present: bool, publisher_id_present: bool) -> Readiness:
    """Можно ли обращаться к источнику. Порядок проверок — от общего к частному."""
    problems = contract.problems()
    if problems:
        return Readiness(BLOCKED_CONTRACT, "; ".join(problems))
    missing = [name for name, present in
               (("api-token", token_present), ("publisher-id", publisher_id_present))
               if not present]
    if missing:
        return Readiness(BLOCKED_CREDENTIALS, f"не переданы секреты: {', '.join(missing)}")
    return Readiness(READY, "контракт передан, секреты доступны")


# --------------------------------------------------------------------------
# План синхронизации
# --------------------------------------------------------------------------
@dataclass
class SyncPlan:
    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    duplicates: list[str] = field(default_factory=list)
    missing_key: list[dict] = field(default_factory=list)
    deletions_refused: str | None = None
    stale: list[str] = field(default_factory=list)

    @property
    def changes(self) -> int:
        return len(self.created) + len(self.updated)

    def as_dict(self) -> dict:
        return {
            "created": sorted(self.created),
            "updated": sorted(self.updated),
            "unchanged": sorted(self.unchanged),
            "duplicates": sorted(self.duplicates),
            "missing_key": self.missing_key,
            "deletions_refused": self.deletions_refused,
            "stale": sorted(self.stale),
            "counts": {
                "created": len(self.created),
                "updated": len(self.updated),
                "unchanged": len(self.unchanged),
                "duplicates": len(self.duplicates),
                "missing_key": len(self.missing_key),
                "stale": len(self.stale),
            },
        }


def _key(item: dict) -> str | None:
    value = item.get("external_id")
    return str(value) if value not in (None, "") else None


def plan_sync(existing: dict[str, dict], incoming: list[dict]) -> SyncPlan:
    """План изменений каталога по ответу источника.

    Идемпотентность обеспечивается сравнением содержимого: повторный тот же
    ответ даёт нулевое число изменений, а не повторную запись. Дубли внутри
    ответа отбрасываются по ключу — первым выигрывает первый пришедший, потому
    что порядок ответа задаёт источник, а не мы.

    Удаление не планируется никогда. Пустой или частичный ответ — это отказ
    источника, и трактовать его как «каталог опустел» значит стереть каталог
    из-за сетевой ошибки.
    """
    plan = SyncPlan()
    seen: set[str] = set()

    for item in incoming:
        key = _key(item)
        if key is None:
            plan.missing_key.append({"reason": "нет external_id", "item_fields": sorted(item)})
            continue
        if key in seen:
            plan.duplicates.append(key)
            continue
        seen.add(key)

        current = existing.get(key)
        if current is None:
            plan.created.append(key)
        elif current != item:
            plan.updated.append(key)
        else:
            plan.unchanged.append(key)

    # Записи, которых не было в ответе. Они не удаляются — только помечаются.
    plan.stale = [key for key in existing if key not in seen]

    if existing and (not seen or len(seen) < len(existing) * MIN_RESPONSE_FRACTION):
        plan.deletions_refused = (
            f"ответ содержит {len(seen)} записей против {len(existing)} в каталоге — "
            "это частичный ответ источника, удаление по нему запрещено"
        )
    elif plan.stale:
        plan.deletions_refused = (
            f"{len(plan.stale)} записей отсутствуют в ответе; удаление не планируется, "
            "снятие с публикации выполняет отдельное решение оператора"
        )
    return plan


def dry_run(
    package: dict,
    incoming: list[dict] | None = None,
    existing: dict[str, dict] | None = None,
    *,
    contract_path: Path | str | None = None,
    token_present: bool = False,
    publisher_id_present: bool = False,
) -> dict:
    """Сухой прогон синхронизации. Ничего не записывает и ничего не запрашивает.

    Возвращает отчёт, пригодный как доказательство: команда, статус готовности,
    причина и план изменений. Значения секретов в отчёт не попадают — только
    факт их наличия.
    """
    contract = load_contract(contract_path)
    state = readiness(contract, token_present=token_present,
                      publisher_id_present=publisher_id_present)
    plan = plan_sync(existing or {}, incoming or [])
    return {
        "site_id": package.get("site_id"),
        "contract_ref": CONTRACT_REF,
        "contract_status": contract.status,
        "readiness": state.status,
        "reason": state.reason,
        "live_request_performed": False,
        "secrets_present": {
            "api-token": bool(token_present),
            "publisher-id": bool(publisher_id_present),
        },
        "plan": plan.as_dict(),
    }
