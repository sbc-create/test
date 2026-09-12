"""Событие-исправление числовых утверждений: audit.claim.erratum.v1.

Журнал только дополняется. Исправление — это НОВАЯ запись со ссылкой на
прежнюю, а не правка прежней: журнал, который можно поправить, перестаёт быть
свидетельством и становится черновиком.

Почему нужен claim_namespace
----------------------------

Утверждение может быть сделано не в теле события, а в документе, на который
событие ссылается. Исправлять «поле события», которого в событии нет, —
значит писать в журнал неправду об исходной записи. Поэтому erratum обязан
назвать, ГДЕ живёт исправляемое утверждение, и путь проверяется по этому
документу, а не по догадке.

Два исхода и никакой середины
-----------------------------

CORRECTED означает «правильное значение известно» и требует его.
WITHDRAWN_UNVERIFIED означает «значение не подтверждено» и запрещает любое
числовое замещение: подставить ноль или «примерно столько же» — значит выдать
неизвестное за измеренное, а это хуже отсутствия числа.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

ТИП = "audit.claim.erratum.v1"
СХЕМА = "fleet-audit-erratum/1.0.0"

ИСПРАВЛЕНО = "CORRECTED"
ОТОЗВАНО = "WITHDRAWN_UNVERIFIED"
ИСХОДЫ = (ИСПРАВЛЕНО, ОТОЗВАНО)

ОБЯЗАТЕЛЬНЫЕ = ("source_event_id", "source_ledger_seq", "source_event_type",
                "subject_producer", "correction_actor", "correction_authority",
                "reason_code", "claim_namespace", "claim_corrections")

#: Коды причин. Перечень закрыт: свободный текст в причине означает, что
#: по журналу нельзя посчитать, сколько исправлений какого рода было.
ПРИЧИНЫ = ("RECOMPUTED_FROM_PINNED_EVIDENCE", "EVIDENCE_INSUFFICIENT",
           "UNIT_MISMATCH", "SOURCE_DATA_LOST")


class ErratumError(RuntimeError):
    def __init__(self, код: str, детали: str, статус: int = 422):
        super().__init__(детали)
        self.error_code, self.detail, self.status = код, детали, статус


def _по_пути(документ: Any, путь: str) -> tuple[bool, Any]:
    """Найти значение по JSON-указателю вида /a/b. Возвращает (есть, значение)."""
    текущее = документ
    for кусок in [к for к in путь.split("/") if к]:
        if isinstance(текущее, dict) and кусок in текущее:
            текущее = текущее[кусок]
        elif isinstance(текущее, list) and кусок.isdigit() and int(кусок) < len(текущее):
            текущее = текущее[int(кусок)]
        else:
            return False, None
    return True, текущее


def проверить(событие: dict[str, Any], *, документ_пространства: Any,
              исходное: dict[str, Any] | None,
              уже_есть: bool = False) -> dict[str, Any]:
    """Полная проверка erratum до записи. Возвращает разбор исправлений."""
    нет = [п for п in ОБЯЗАТЕЛЬНЫЕ if not событие.get(п)]
    if нет:
        raise ErratumError("ERRATUM_FIELDS_MISSING", f"не заданы поля: {нет}")
    if событие.get("reason_code") not in ПРИЧИНЫ:
        raise ErratumError("ERRATUM_REASON_UNKNOWN",
                           f"код причины {событие.get('reason_code')!r} не объявлен")

    # Исходное событие обязано существовать: исправление несуществующего —
    # это утверждение о том, чего не было.
    if исходное is None:
        raise ErratumError("ERRATUM_SOURCE_NOT_FOUND",
                           f"исходное событие {событие['source_event_id']} "
                           f"журналу неизвестно", 404)
    if исходное.get("ledger_seq") != событие.get("source_ledger_seq"):
        raise ErratumError("ERRATUM_SOURCE_SEQ_MISMATCH",
                           "source_ledger_seq не совпадает с записью")
    if исходное.get("event_type") != событие.get("source_event_type"):
        raise ErratumError("ERRATUM_SOURCE_TYPE_MISMATCH",
                           "source_event_type не совпадает с записью")
    if исходное.get("producer_service") != событие.get("subject_producer"):
        raise ErratumError("ERRATUM_SUBJECT_MISMATCH",
                           "subject_producer не совпадает с производителем "
                           "исходного события")
    if событие.get("event_id") == событие.get("source_event_id"):
        raise ErratumError("ERRATUM_SELF_REFERENCE",
                           "событие не исправляет само себя")
    # Цепочка исправлений: исправлять исправление — путь к кольцу, в котором
    # действующего значения нет ни у одной записи.
    if исходное.get("event_type") == ТИП:
        raise ErratumError("ERRATUM_CHAIN_FORBIDDEN",
                           "исправление исправления не выполняется: исправьте "
                           "исходное утверждение новой записью")
    # Актор исправления не выдаёт себя за производителя исходной записи.
    if событие.get("correction_actor") == событие.get("subject_producer"):
        raise ErratumError("ERRATUM_PRODUCER_IMPERSONATION",
                           "исправляющий не может объявлять себя автором "
                           "исправляемого утверждения")

    исправления = событие.get("claim_corrections") or []
    if not isinstance(исправления, list) or not исправления:
        raise ErratumError("ERRATUM_NO_CORRECTIONS", "нет ни одного исправления")
    разобрано = []
    пути = set()
    for и in исправления:
        путь = и.get("path")
        исход = и.get("disposition")
        if not путь or not str(путь).startswith("/"):
            raise ErratumError("ERRATUM_CLAIM_PATH_INVALID",
                               f"путь {путь!r} не является JSON-указателем")
        if путь in пути:
            raise ErratumError("ERRATUM_CLAIM_PATH_DUPLICATE",
                               f"путь {путь} исправляется дважды")
        пути.add(путь)
        if исход not in ИСХОДЫ:
            raise ErratumError("ERRATUM_DISPOSITION_UNKNOWN",
                               f"исход {исход!r} не объявлен")
        есть, значение = _по_пути(документ_пространства, путь)
        if not есть:
            raise ErratumError(
                "ERRATUM_CLAIM_PATH_UNKNOWN",
                f"утверждения {путь} нет в объявленном пространстве "
                f"{событие['claim_namespace'].get('ref')}")
        if "previous_value" in и and и["previous_value"] != значение:
            raise ErratumError(
                "ERRATUM_PREVIOUS_MISMATCH",
                f"{путь}: заявленное прежнее значение не совпадает с "
                f"закреплённым доказательством")
        замена = и.get("replacement_value", None)
        if исход == ИСПРАВЛЕНО and замена is None:
            raise ErratumError("ERRATUM_REPLACEMENT_REQUIRED",
                               f"{путь}: CORRECTED требует значения замены")
        if исход == ОТОЗВАНО and замена is not None:
            raise ErratumError(
                "ERRATUM_REPLACEMENT_FORBIDDEN",
                f"{путь}: отозванное как неподтверждённое не заменяется "
                f"числом — иначе неизвестное выдаётся за измеренное")
        разобрано.append({"path": путь, "previous_value": значение,
                          "disposition": исход, "replacement_value": замена})

    return {"corrections": разобрано, "idempotent_replay": уже_есть}


def ключ_идемпотентности(событие: dict[str, Any]) -> str:
    """Из содержания, а не из времени: повтор обязан дать тот же ключ."""
    основа = {"source_event_id": событие.get("source_event_id"),
              "corrections": sorted(
                  [(и.get("path"), и.get("disposition"),
                    и.get("replacement_value"))
                   for и in (событие.get("claim_corrections") or [])],
                  key=lambda x: x[0] or "")}
    сырое = json.dumps(основа, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"))
    return "erratum:" + hashlib.sha256(сырое.encode("utf-8")).hexdigest()[:32]


def действующее(исходные_утверждения: dict[str, Any],
                errata: list[dict[str, Any]]) -> dict[str, Any]:
    """Проекция: что считать действующим после всех исправлений.

    Проекция — представление над журналом, а не второй источник истины: она
    строится из записей каждый раз заново и ничего не хранит от себя.
    """
    итог = {}
    for путь, значение in исходные_утверждения.items():
        итог[путь] = {"original_value": значение,
                      "disposition": "AS_REPORTED",
                      "effective_value": значение,
                      "erratum_event_id": None, "reason_code": None}
    for e in errata:
        for и in (e.get("claim_corrections") or []):
            путь = и["path"]
            узел = итог.setdefault(путь, {"original_value": None})
            узел["disposition"] = и["disposition"]
            узел["effective_value"] = (и.get("replacement_value")
                                       if и["disposition"] == ИСПРАВЛЕНО else None)
            узел["erratum_event_id"] = e.get("event_id")
            узел["source_event_id"] = e.get("source_event_id")
            узел["reason_code"] = e.get("reason_code")
            узел["evidence_refs"] = e.get("evidence_refs")
    return итог
