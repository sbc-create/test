"""Наблюдаемость Integration Provisioner.

Метрики собираются из того, что уже записано: наборов изменений, действий у
провайдера и связей. Отдельного счётчика «на всякий случай» здесь нет —
он немедленно разошёлся бы с состоянием и врал бы убедительнее, чем молчание.

В журнал аудита эти показатели НЕ пишутся. Сердцебиение и глубина очереди —
не события жизненного цикла; попав в журнал, они утопили бы в себе то
немногое, ради чего журнал существует.

Застрявшим считается набор, который слишком долго держится в незавершённом
состоянии. Именно «слишком долго», а не «не завершён»: незавершённый прямо
сейчас — норма, а незавершённый час — повод вмешаться.
"""
from __future__ import annotations

import datetime as _d
import json
from dataclasses import dataclass, field
from typing import Any

#: Сколько набор вправе оставаться в рабочем состоянии до тревоги.
ПРЕДЕЛ_ЗАСТРЕВАНИЯ_СЕК = 900.0
#: Доля неудачных обращений к провайдеру, выше которой поднимается тревога.
ПРЕДЕЛ_ДОЛИ_ОШИБОК = 0.25

РАБОЧИЕ_СОСТОЯНИЯ = ("PROPOSED", "VALIDATING", "VALIDATED", "AWAITING_APPROVAL",
                     "APPROVED", "APPLYING", "VERIFYING")
ТРЕВОЖНЫЕ_СОСТОЯНИЯ = ("APPLY_FAILED", "VERIFY_FAILED",
                       "MANUAL_INTERVENTION_REQUIRED", "VALIDATION_FAILED")


def _время(строка: str | None) -> _d.datetime | None:
    if not строка:
        return None
    try:
        return _d.datetime.fromisoformat(строка.replace("Z", "+00:00"))
    except ValueError:
        return None


@dataclass
class Показатели:
    ready: bool
    heartbeat_at: str
    onboarding_sites: int = 0
    links_total: int = 0
    links_by_lifecycle: dict[str, int] = field(default_factory=dict)
    provider_actions_total: int = 0
    provider_actions_in_flight: int = 0
    provider_error_rate: float = 0.0
    duplicate_effects: int = 0
    dlq_depth: int = 0
    changesets_in_flight: int = 0
    changesets_failed: int = 0
    stuck_changesets: list[str] = field(default_factory=list)
    stage_durations_sec: dict[str, float] = field(default_factory=dict)
    alerts: list[dict[str, Any]] = field(default_factory=list)

    def в_json(self) -> str:
        return json.dumps(self.__dict__, ensure_ascii=False, indent=1)


def собрать(*, связи, соед_наборов, сейчас: _d.datetime | None = None) -> Показатели:
    сейчас = сейчас or _d.datetime.now(_d.timezone.utc)
    п = Показатели(ready=True,
                   heartbeat_at=сейчас.isoformat().replace("+00:00", "Z"))

    строки = связи.соед.execute(
        "SELECT site_id, lifecycle FROM resource_link").fetchall()
    п.links_total = len(строки)
    п.onboarding_sites = len({с["site_id"] for с in строки})
    for с in строки:
        п.links_by_lifecycle[с["lifecycle"]] = \
            п.links_by_lifecycle.get(с["lifecycle"], 0) + 1

    действия = связи.соед.execute(
        "SELECT state, external_id, COUNT(*) c FROM provider_action "
        "GROUP BY state, external_id").fetchall()
    всего = sum(д["c"] for д in действия)
    неудач = sum(д["c"] for д in действия if д["state"] == "FAILED")
    п.provider_actions_total = всего
    п.provider_actions_in_flight = sum(
        д["c"] for д in действия if д["state"] == "STARTED")
    п.provider_error_rate = round(неудач / всего, 4) if всего else 0.0

    # Дубль эффекта: один внешний объект, созданный более чем одним успешным
    # действием. Ноль здесь — не украшение отчёта, а условие исправности.
    дубли = связи.соед.execute(
        "SELECT external_id, COUNT(*) c FROM provider_action "
        "WHERE state='SUCCEEDED' AND external_id IS NOT NULL "
        "GROUP BY external_id HAVING c > 1").fetchall()
    п.duplicate_effects = sum(д["c"] - 1 for д in дубли)
    п.dlq_depth = связи.глубина_dlq

    наборы = соед_наборов.execute(
        "SELECT changeset_id, status, created_at, updated_at FROM changeset"
    ).fetchall()
    п.changesets_in_flight = sum(1 for н in наборы
                                 if н["status"] in РАБОЧИЕ_СОСТОЯНИЯ)
    п.changesets_failed = sum(1 for н in наборы
                              if н["status"] in ТРЕВОЖНЫЕ_СОСТОЯНИЯ)
    for н in наборы:
        начало, конец = _время(н["created_at"]), _время(н["updated_at"])
        if начало and конец:
            п.stage_durations_sec[н["changeset_id"]] = round(
                (конец - начало).total_seconds(), 3)
        if н["status"] in РАБОЧИЕ_СОСТОЯНИЯ and конец:
            простой = (сейчас - конец).total_seconds()
            if простой > ПРЕДЕЛ_ЗАСТРЕВАНИЯ_СЕК:
                п.stuck_changesets.append(н["changeset_id"])

    # --- тревоги ----------------------------------------------------------
    if п.stuck_changesets:
        п.alerts.append({"code": "CHANGESET_STUCK", "severity": "P1",
                         "detail": f"наборов без движения дольше "
                                   f"{int(ПРЕДЕЛ_ЗАСТРЕВАНИЯ_СЕК)}с: "
                                   f"{len(п.stuck_changesets)}"})
    if п.changesets_failed:
        п.alerts.append({"code": "CHANGESET_FAILED", "severity": "P1",
                         "detail": f"наборов в состоянии отказа: "
                                   f"{п.changesets_failed}"})
    if п.dlq_depth:
        п.alerts.append({"code": "PROVIDER_DLQ_NON_EMPTY", "severity": "P2",
                         "detail": f"в очереди разбора {п.dlq_depth}"})
    if п.duplicate_effects:
        п.alerts.append({"code": "DUPLICATE_PROVIDER_EFFECT", "severity": "P0",
                         "detail": f"дублей внешних объектов: "
                                   f"{п.duplicate_effects}"})
    if п.provider_error_rate > ПРЕДЕЛ_ДОЛИ_ОШИБОК:
        п.alerts.append({"code": "PROVIDER_ERROR_RATE", "severity": "P2",
                         "detail": f"доля отказов {п.provider_error_rate}"})
    if п.provider_actions_in_flight:
        п.alerts.append({"code": "PROVIDER_ACTIONS_IN_FLIGHT", "severity": "P3",
                         "detail": f"начатых и неподтверждённых действий: "
                                   f"{п.provider_actions_in_flight}; они "
                                   f"подлежат сверке"})
    п.ready = not any(а["severity"] in ("P0", "P1") for а in п.alerts)
    return п
