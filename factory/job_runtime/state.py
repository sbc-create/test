"""State machine конвейера с персистентным состоянием.

Состояние живёт на диске (`var/state/<job_id>.json`), а не в контексте модели:
worker обязан продолжать с последнего подтверждённого checkpoint после restart.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from factory.errors import ALL_STATES, FAILURE_STATES
from factory.paths import PATHS

#: Разрешённые переходы. Любой другой переход — ошибка программиста, а не «предупреждение».
TRANSITIONS: dict[str, set[str]] = {
    "RECEIVED": {"VALIDATING", "QUARANTINED"},
    "VALIDATING": {"READY", *FAILURE_STATES},
    "READY": {"BUILDING", *FAILURE_STATES},
    "BUILDING": {"BUILT", *FAILURE_STATES},
    "BUILT": {"STAGING_DEPLOY", "AUTHORIZATION_CHECK", *FAILURE_STATES},
    "STAGING_DEPLOY": {"STAGING_QA", *FAILURE_STATES},
    "STAGING_QA": {"AUTHORIZATION_CHECK", "DONE", *FAILURE_STATES},
    "AUTHORIZATION_CHECK": {"PRODUCTION_DEPLOY", *FAILURE_STATES},
    "PRODUCTION_DEPLOY": {"PRODUCTION_SMOKE", *FAILURE_STATES},
    "PRODUCTION_SMOKE": {"MONITORING", "ROLLED_BACK", *FAILURE_STATES},
    "MONITORING": {"DONE", *FAILURE_STATES},
    "DONE": set(),
    # Из терминальных отказов job возвращается только новым запуском после исправления входа.
    **{state: {"RECEIVED", "QUARANTINED"} for state in FAILURE_STATES},
}


class IllegalTransition(RuntimeError):
    def __init__(self, current: str, target: str) -> None:
        super().__init__(f"Недопустимый переход {current} → {target}")
        self.current = current
        self.target = target


@dataclass
class JobState:
    job_id: str
    site_id: str
    environment: str
    status: str = "RECEIVED"
    requested_action: str = "create"
    attempts: int = 0
    checkpoint: str | None = None
    build_id: str | None = None
    release_id: str | None = None
    base_url: str | None = None
    history: list[dict] = field(default_factory=list)
    blockers: list[dict] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    # ------------------------------------------------------------------ хранение
    @staticmethod
    def path_for(job_id: str) -> Path:
        PATHS.state.mkdir(parents=True, exist_ok=True)
        return PATHS.state / f"{job_id}.json"

    @classmethod
    def load(cls, job_id: str) -> JobState | None:
        path = cls.path_for(job_id)
        if not path.exists():
            return None
        return cls(**json.loads(path.read_text(encoding="utf-8")))

    @classmethod
    def load_or_create(cls, job_id: str, site_id: str, environment: str, requested_action: str = "create") -> JobState:
        existing = cls.load(job_id)
        if existing:
            return existing
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        state = cls(job_id=job_id, site_id=site_id, environment=environment,
                    requested_action=requested_action, created_at=now, updated_at=now)
        state.save()
        return state

    def save(self) -> None:
        self.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        path = self.path_for(self.job_id)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.__dict__, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)   # атомарная запись: падение между write и replace не рвёт состояние

    # ------------------------------------------------------------------ переходы
    def can_transition(self, target: str) -> bool:
        return target in TRANSITIONS.get(self.status, set())

    def transition(self, target: str, *, detail: str = "", blockers: list[dict] | None = None) -> JobState:
        if target not in ALL_STATES:
            raise ValueError(f"Неизвестный статус: {target}")
        if not self.can_transition(target):
            raise IllegalTransition(self.status, target)
        self.history.append({
            "from": self.status, "to": target, "detail": detail,
            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })
        self.status = target
        if blockers is not None:
            self.blockers = blockers
        self.save()
        return self

    def checkpoint_at(self, name: str) -> None:
        self.checkpoint = name
        self.save()

    @property
    def terminal(self) -> bool:
        return self.status in ("DONE", *FAILURE_STATES)

    def as_dict(self) -> dict:
        return dict(self.__dict__)


def all_jobs() -> list[JobState]:
    if not PATHS.state.exists():
        return []
    jobs = []
    for path in sorted(PATHS.state.glob("*.json")):
        try:
            jobs.append(JobState(**json.loads(path.read_text(encoding="utf-8"))))
        except (json.JSONDecodeError, TypeError):
            continue
    return jobs
