"""Логический карантин множеств событий журнала.

Журнал только на добавление: ошибочно записанное нельзя убрать, и убирать его
нельзя даже тогда, когда очень хочется — иначе свойство, ради которого журнал
существует, держалось бы на честном слове. Поэтому загрязнение исправляется
не удалением, а НОВЫМ событием, которое объявляет прежние непригодными для
рабочих решений.

Разделение поверхностей:

* raw feed показывает всё, включая ошибку системы, и помечает её статусом;
* operational projection исключает карантинные события из рабочих решений.

Список идентификаторов хранится в манифесте доказательств, а не в теле
события: payload с шестьюдесятью идентификаторами перестал бы читаться, а хэш
манифеста связывает событие со списком не слабее, чем прямое вложение.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from . import ledger_store as store

#: Причина, по которой множество событий признано непригодным.
ПРИЧИНА_HARNESS = "TEST_HARNESS_CONTAMINATION"

#: Типы событий, порождаемые только испытательной обвязкой. Признак точный:
#: ни один рабочий контур таких событий не подаёт, поэтому классификация не
#: требует догадок о содержимом.
ТИПЫ_ОБВЯЗКИ = ("test.observed.v1", "test.outage.v1")

СОБЫТИЕ_КАРАНТИН = "audit.event_set.quarantined.v1"
СОБЫТИЕ_ОТМЕНА = "audit.event_set.quarantine_revoked.v1"


class ClassificationError(RuntimeError):
    """Событие невозможно отнести к тестовым доказательно."""


def найти_кандидатов(соед: sqlite3.Connection) -> list[dict[str, Any]]:
    """Собрать события обвязки вместе с признаками, по которым они опознаны."""
    места = ",".join("?" * len(ТИПЫ_ОБВЯЗКИ))
    строки = [dict(r) for r in соед.execute(
        f"SELECT * FROM ledger_event WHERE event_type IN ({места}) "
        "ORDER BY ledger_seq", ТИПЫ_ОБВЯЗКИ)]
    for с in строки:
        с["classification_reason"] = (
            f"event_type={с['event_type']} порождается только испытательной "
            f"обвязкой; producer={с['producer_service']}, scope={с['scope']}, "
            f"site_id={с['site_id']!r}, resource_id={с['resource_id']!r}")
    return строки


def проверить_однозначность(соед: sqlite3.Connection,
                            кандидаты: list[dict[str, Any]]) -> dict[str, Any]:
    """Убедиться, что в набор не попало ничего настоящего.

    Проверяется не «похоже на тестовое», а отсутствие признаков настоящего:
    события реестра, действия над сайтом, ссылки на production-ресурс.
    """
    спорные = []
    for с in кандидаты:
        причины = []
        if с["producer_service"] != "architect":
            причины.append(f"производитель {с['producer_service']}")
        if с["site_id"]:
            причины.append(f"ссылается на сайт {с['site_id']}")
        if с["resource_id"]:
            причины.append(f"ссылается на ресурс {с['resource_id']}")
        if (с["environment"] or "").lower() in ("production", "prod"):
            причины.append("окружение production")
        if с["event_type"].startswith("registry."):
            причины.append("событие реестра")
        if причины:
            спорные.append({"ledger_seq": с["ledger_seq"],
                            "event_id": с["event_id"], "причины": причины})
    реестровых = sum(1 for с in кандидаты
                     if с["producer_service"] == "registry")
    return {"candidates": len(кандидаты), "ambiguous": len(спорные),
            "ambiguous_detail": спорные, "registry_events": реестровых,
            "production_events": sum(
                1 for с in кандидаты
                if (с["environment"] or "").lower().startswith("prod"))}


def собрать_манифест(кандидаты: list[dict[str, Any]], путь: Path, *,
                     причина: str, prompt_id: str, prompt_rev: str,
                     source_commit: str) -> dict[str, Any]:
    """Записать манифест доказательств и вернуть его хэш."""
    поля = ("event_id", "ledger_seq", "event_type", "producer_service",
            "actor_id", "actor_type", "authority", "environment", "run_id",
            "correlation_id", "action_id", "occurred_at", "received_at",
            "payload_hash", "classification_reason")
    манифест = {
        "manifest_version": "fleet-audit-quarantine-manifest/1.0.0",
        "reason": причина, "owner": "ARCHITECT",
        "decision_authority": "AUTHORIZE",
        "prompt_id": prompt_id, "prompt_rev": prompt_rev,
        "source_commit": source_commit,
        "classified_at": store.сейчас(),
        "event_count": len(кандидаты),
        "first_ledger_seq": min(с["ledger_seq"] for с in кандидаты),
        "last_ledger_seq": max(с["ledger_seq"] for с in кандидаты),
        "events": [{k: с[k] for k in поля} for с in кандидаты],
    }
    путь.parent.mkdir(parents=True, exist_ok=True)
    # Канонический JSON: хэш манифеста обязан зависеть от содержимого, а не от
    # порядка ключей и отступов при записи.
    тело = json.dumps(манифест, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")
    путь.write_bytes(тело)
    return {"manifest": манифест, "path": str(путь),
            "sha256": hashlib.sha256(тело).hexdigest(), "size": len(тело)}


def прочитать_решения(соед: sqlite3.Connection) -> dict[int, str]:
    """Какие позиции журнала сейчас в карантине.

    Читается из самого журнала: решения о карантине — такие же события, как
    все прочие, и отменяются тоже событием. Отдельной таблицы решений нет
    намеренно — она стала бы состоянием, которое можно поправить руками.
    """
    в_карантине: dict[int, str] = {}
    for р in соед.execute(
            "SELECT event_id, event_type, summary, evidence_refs FROM "
            "ledger_event WHERE event_type IN (?, ?) ORDER BY ledger_seq",
            (СОБЫТИЕ_КАРАНТИН, СОБЫТИЕ_ОТМЕНА)):
        ссылки = json.loads(р["evidence_refs"] or "[]")
        for сс in ссылки:
            путь = Path(сс.get("uri", ""))
            if not путь.is_file():
                raise ClassificationError(
                    f"манифест карантина недоступен: {путь}")
            тело = путь.read_bytes()
            факт = hashlib.sha256(тело).hexdigest()
            if сс.get("checksum") and факт != сс["checksum"]:
                # Манифест, не совпавший с хэшем, не применяется: иначе
                # подменённый файл менял бы состав карантина молча.
                raise ClassificationError(
                    f"манифест {путь} не совпал с контрольной суммой")
            данные = json.loads(тело.decode("utf-8"))
            for е in данные["events"]:
                if р["event_type"] == СОБЫТИЕ_КАРАНТИН:
                    в_карантине[int(е["ledger_seq"])] = р["event_id"]
                else:
                    в_карантине.pop(int(е["ledger_seq"]), None)
    return в_карантине
