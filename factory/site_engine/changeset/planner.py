"""Планирование и сухой прогон.

Сухой прогон использует ТОТ ЖЕ планировщик, что и применение. Отдельная
«облегчённая проверка» проверяла бы не то, что потом выполнится, и создавала
бы худший вид уверенности — подтверждённую не тем.

Содержимое заявки — данные, а не программа. Ни команда оболочки, ни путь к
файлу, ни адрес, ни SQL из неё не исполняются: разрешены только простые
значения в объявленных полях.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from . import adapter as A
from . import model as M
from .registry_client import RegistryClient, RegistryUnavailable
from .store import ChangeSetError, канон, хэш

#: Признаки того, что в значение пытаются протащить исполняемое или адрес.
ОПАСНЫЕ_ОБРАЗЦЫ = (
    (re.compile(r"\.\./|\.\.\\"), "путь вверх по дереву"),
    (re.compile(r"^\s*/|^[a-zA-Z]:\\"), "абсолютный путь"),
    (re.compile(r"[;&|`$]|\$\(|\bsudo\b|\brm\s+-rf\b"), "команда оболочки"),
    (re.compile(r"(?i)\b(union\s+select|drop\s+table|delete\s+from|"
                r"insert\s+into|--\s|/\*)"), "внедрение SQL"),
    (re.compile(r"(?i)^(https?|ftp|file|gopher|data)://"), "внешний адрес"),
    (re.compile(r"(?i)\b(169\.254\.169\.254|metadata\.google|localhost:\d+)"),
     "обращение к служебному адресу"),
    (re.compile(r"<\s*script|javascript:"), "исполняемая вставка"),
)

#: Глубина и размер заявки ограничены: вложенность без предела — это способ
#: занять память на разборе.
МАКС_ГЛУБИНА = 4
МАКС_КЛЮЧЕЙ = 64
МАКС_ДЛИНА_ЗНАЧЕНИЯ = 4096


def проверить_содержимое(значение: Any, *, глубина: int = 0,
                         путь: str = "requested_change") -> None:
    if глубина > МАКС_ГЛУБИНА:
        raise ChangeSetError("PAYLOAD_TOO_DEEP",
                             f"{путь}: вложенность глубже {МАКС_ГЛУБИНА}")
    if isinstance(значение, dict):
        if len(значение) > МАКС_КЛЮЧЕЙ:
            raise ChangeSetError("PAYLOAD_TOO_LARGE",
                                 f"{путь}: более {МАКС_КЛЮЧЕЙ} ключей")
        for k, v in значение.items():
            if not isinstance(k, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", k):
                raise ChangeSetError("PAYLOAD_KEY_INVALID",
                                     f"{путь}: недопустимый ключ {k!r}")
            проверить_содержимое(v, глубина=глубина + 1, путь=f"{путь}.{k}")
        return
    if isinstance(значение, list):
        if len(значение) > МАКС_КЛЮЧЕЙ:
            raise ChangeSetError("PAYLOAD_TOO_LARGE", f"{путь}: слишком длинный список")
        for i, v in enumerate(значение):
            проверить_содержимое(v, глубина=глубина + 1, путь=f"{путь}[{i}]")
        return
    if значение is None or isinstance(значение, (bool, int, float)):
        return
    if not isinstance(значение, str):
        raise ChangeSetError("PAYLOAD_TYPE_INVALID",
                             f"{путь}: тип {type(значение).__name__} не разрешён")
    if len(значение) > МАКС_ДЛИНА_ЗНАЧЕНИЯ:
        raise ChangeSetError("PAYLOAD_TOO_LARGE", f"{путь}: значение длиннее предела")
    for образец, что in ОПАСНЫЕ_ОБРАЗЦЫ:
        if образец.search(значение):
            raise ChangeSetError("PAYLOAD_REJECTED",
                                 f"{путь}: обнаружено — {что}")


def классифицировать_риск(набор: dict[str, Any], план: dict[str, Any],
                          окружения: set[str]) -> str:
    """Класс риска по последствиям, а не по намерению."""
    if окружения - {"test"}:
        if окружения & {"production"}:
            return M.RISK_HIGH
        return M.RISK_MEDIUM
    if len(набор["target_site_ids"]) > 1:
        return M.RISK_MEDIUM
    return M.RISK_LOW


def построить_планы(набор: dict[str, Any], планы: dict[str, dict]) -> tuple[dict, dict]:
    """План проверки и план отката — из того же материала, что и применение."""
    проверка = {
        "method": "observe_and_compare_fingerprint",
        "targets": {s: {"expected_fingerprint": p["expected_fingerprint"]}
                    for s, p in планы.items()},
        "postconditions": ["наблюдаемый отпечаток равен ожидаемому",
                           "ресурс существует"],
        # Код возврата исполнителя намеренно не входит в доказательства.
        "evidence": ["observed_state", "observed_fingerprint"],
    }
    откат = {
        "method": "restore_before_state",
        "targets": {s: {"before_fingerprint": p["before_fingerprint"]}
                    for s, p in планы.items()},
        "idempotent": True,
        "verify_after": True,
    }
    return проверка, откат


def спланировать(набор: dict[str, Any], *, реестр: RegistryClient | None = None,
                 адаптер: A.TargetAdapter | None = None) -> dict[str, Any]:
    """Полная валидация и построение плана. Ни одного эффекта."""
    рт = набор["resource_type"]
    оп = набор["operation_type"]

    if оп in M.НЕОБРАТИМЫЕ_ОПЕРАЦИИ:
        raise ChangeSetError(
            "IRREVERSIBLE_OPERATION",
            f"операция {оп} необратима; в этой версии такие изменения "
            f"не выполняются, поскольку их откат не доказан", 422)
    if оп not in M.ОПЕРАЦИИ:
        raise ChangeSetError("OPERATION_UNKNOWN",
                             f"операция {оп} не объявлена", 422)

    проверить_содержимое(набор.get("requested_change") or {})

    ад = адаптер or A.получить(рт)
    возможности = ад.capabilities()
    владелец = M.ЕДИНСТВЕННЫЙ_ПИСАТЕЛЬ.get(рт)
    if владелец and возможности.get("owner_service") != владелец:
        raise ChangeSetError(
            "OWNERSHIP_MISMATCH",
            f"ресурс {рт} принадлежит {владелец}, а адаптер объявляет "
            f"{возможности.get('owner_service')}", 409)
    if оп not in возможности.get("operations", ()):
        raise ChangeSetError("OPERATION_UNSUPPORTED",
                             f"адаптер не поддерживает {оп}", 422)

    рк = реестр or RegistryClient()
    try:
        версия_реестра = рк.версия()
        известные = {с["site_id"]: с for с in рк.сайты()}
    except RegistryUnavailable as e:
        raise ChangeSetError("REGISTRY_UNAVAILABLE",
                             f"реестр недоступен: {e}", 503) from e

    окружения: set[str] = set()
    планы: dict[str, dict] = {}
    отпечатки: dict[str, str] = {}
    for site_id in набор["target_site_ids"]:
        сайт = известные.get(site_id)
        if сайт is None:
            raise ChangeSetError(
                "SITE_ID_UNKNOWN",
                f"site_id {site_id!r} реестру неизвестен; домен "
                f"идентификатором не является", 422)
        if сайт.get("lifecycle_state") not in ("ACTIVE", "DRAFT"):
            raise ChangeSetError(
                "LIFECYCLE_FORBIDDEN",
                f"{site_id}: состояние {сайт.get('lifecycle_state')} "
                f"не допускает изменений", 409)
        окружения.add(сайт.get("environment") or "UNKNOWN")
        наблюдаемое = ад.observe(site_id=site_id, resource_id=набор["resource_id"])
        план = ад.plan(site_id=site_id, resource_id=набор["resource_id"],
                       operation=оп,
                       requested_change=набор.get("requested_change") or {},
                       observed=наблюдаемое)
        if not план.get("reversible", False):
            raise ChangeSetError("IRREVERSIBLE_PLAN",
                                 f"{site_id}: план необратим", 422)
        планы[site_id] = план
        отпечатки[site_id] = наблюдаемое["fingerprint"]

    риск = классифицировать_риск(набор, планы, окружения)
    проверка, откат = построить_планы(набор, планы)

    # plan_hash покрывает всё, что определяет смысл изменения. Его совпадение
    # — единственное основание считать, что применяется то же самое, что
    # одобрили.
    plan_hash = хэш({
        "schema_version": M.SCHEMA_VERSION,
        "resource_type": рт, "resource_id": набор["resource_id"],
        "operation_type": оп,
        "targets": {s: {"diff": планы[s]["diff"],
                        "before_fingerprint": планы[s]["before_fingerprint"],
                        "expected_fingerprint": планы[s]["expected_fingerprint"]}
                    for s in sorted(планы)},
        "base_registry_version": версия_реестра,
        "risk_class": риск,
    })
    for s in планы:
        планы[s]["plan_hash"] = plan_hash

    return {
        "plan_hash": plan_hash,
        "base_registry_version": версия_реестра,
        "expected_resource_fingerprint": хэш(
            {s: планы[s]["expected_fingerprint"] for s in sorted(планы)}),
        "observed_fingerprints": отпечатки,
        "environments": sorted(окружения),
        "risk_class": риск,
        "per_site_plan": планы,
        "verification_plan": проверка,
        "rollback_plan": откат,
        "empty": all(p["empty"] for p in планы.values()),
    }


def сухой_прогон(план: dict[str, Any], *,
                 адаптер: A.TargetAdapter | None = None,
                 resource_type: str = "") -> dict[str, Any]:
    """Прогнать план без единого эффекта и посчитать, что изменилось бы."""
    ад = адаптер or A.получить(resource_type)
    итог = {}
    эффектов = 0
    for site_id, p in план["per_site_plan"].items():
        r = ад.dry_run(site_id=site_id, plan=p)
        эффектов += int(r.get("effects", 0))
        итог[site_id] = r
    return {"per_site": итог, "effects": эффектов,
            "plan_hash": план["plan_hash"],
            "applicable": all(r.get("applicable") for r in итог.values())}


def обнаружить_дрейф(набор: dict[str, Any], *,
                     реестр: RegistryClient | None = None,
                     адаптер: A.TargetAdapter | None = None) -> dict[str, Any]:
    """Повторная проверка непосредственно перед применением.

    План, построенный десять минут назад, описывает мир десятиминутной
    давности. Применять его без повторной сверки — значит рассчитывать, что
    за это время никто ничего не трогал.
    """
    расхождения = []
    рк = реестр or RegistryClient()
    try:
        версия = рк.версия()
    except RegistryUnavailable as e:
        raise ChangeSetError("REGISTRY_UNAVAILABLE", str(e), 503) from e
    if набор.get("base_registry_version") is not None \
            and версия != набор["base_registry_version"]:
        расхождения.append({
            "what": "base_registry_version",
            "expected": набор["base_registry_version"], "actual": версия})

    ад = адаптер or A.получить(набор["resource_type"])
    планы = (набор.get("dry_run_result") or {}).get("per_site_plan") or {}
    for site_id, p in планы.items():
        текущее = ад.observe(site_id=site_id, resource_id=набор["resource_id"])
        if текущее["fingerprint"] not in (p["before_fingerprint"],
                                          p["expected_fingerprint"]):
            расхождения.append({
                "what": "resource_fingerprint", "site_id": site_id,
                "expected": p["before_fingerprint"],
                "actual": текущее["fingerprint"]})
    return {"stale": bool(расхождения), "drift": расхождения}
