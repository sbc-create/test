"""Командная модель: опасное изменение — это команда, а не вызов функции.

Разница не в форме. У команды есть автор, причина, состояние, прежнее и новое
значение, ключ повторной подачи и ссылка на откат. У вызова функции нет ничего
из этого, и потому после инцидента остаётся только гадать, кто и зачем.

Повторная подача одной и той же команды не выполняет работу дважды: за это
отвечает ключ идемпотентности. Одновременная правка одного объекта из двух мест
не затирается молча: за это отвечает версия объекта.
"""
from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from factory.site_engine.access import AccessDenied, Permission, Principal, require
from factory.site_engine.contracts import ContractError, utc_now


class CommandState(str, Enum):
    DRAFT = "DRAFT"
    VALIDATING = "VALIDATING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    ROLLED_BACK = "ROLLED_BACK"


#: Из какого состояния в какое переход осмыслен. Список закрытый: «почти любое
#: в любое» — это отсутствие модели, а не гибкость.
ALLOWED_TRANSITIONS: dict[CommandState, frozenset[CommandState]] = {
    CommandState.DRAFT: frozenset({CommandState.VALIDATING, CommandState.CANCELLED}),
    CommandState.VALIDATING: frozenset({CommandState.QUEUED, CommandState.FAILED,
                                        CommandState.CANCELLED}),
    CommandState.QUEUED: frozenset({CommandState.RUNNING, CommandState.CANCELLED}),
    CommandState.RUNNING: frozenset({CommandState.SUCCEEDED, CommandState.FAILED}),
    CommandState.SUCCEEDED: frozenset({CommandState.ROLLED_BACK}),
    CommandState.FAILED: frozenset({CommandState.QUEUED}),
    CommandState.CANCELLED: frozenset(),
    CommandState.ROLLED_BACK: frozenset(),
}


class CommandKind(str, Enum):
    SITE_CREATE = "site.create"
    PROFILE_UPDATE = "profile.update"
    EDITORIAL_CREATE = "editorial.create"
    SHELF_UPDATE = "shelf.update"
    INGESTION_RUN = "ingestion.run"
    TITLE_REFRESH = "title.refresh"
    CANARY_RUN = "canary.run"
    RELEASE_PUBLISH = "release.publish"
    ROLLBACK_RUN = "rollback.run"
    CACHE_INVALIDATE = "cache.invalidate"


#: Право, без которого команду нельзя даже подать. Проверяется при подаче, а не
#: при исполнении: очередь не должна наполняться тем, что всё равно отклонят.
REQUIRED_PERMISSION: dict[CommandKind, Permission] = {
    CommandKind.SITE_CREATE: Permission.SITE_CREATE,
    CommandKind.PROFILE_UPDATE: Permission.PROFILE_WRITE,
    CommandKind.EDITORIAL_CREATE: Permission.EDITORIAL_WRITE,
    CommandKind.SHELF_UPDATE: Permission.SHELF_WRITE,
    CommandKind.INGESTION_RUN: Permission.INGESTION_RUN,
    CommandKind.TITLE_REFRESH: Permission.TITLE_REFRESH,
    CommandKind.CANARY_RUN: Permission.PUBLISH_CANARY,
    CommandKind.RELEASE_PUBLISH: Permission.PUBLISH_PRODUCTION,
    CommandKind.ROLLBACK_RUN: Permission.ROLLBACK_RUN,
    CommandKind.CACHE_INVALIDATE: Permission.CACHE_INVALIDATE,
}

#: Команды, которые нельзя выполнить «заодно с сохранением формы».
DANGEROUS = frozenset({
    CommandKind.RELEASE_PUBLISH,
    CommandKind.ROLLBACK_RUN,
    CommandKind.SITE_CREATE,
})


class CommandRejected(ContractError):
    """Команда не принята: право, состояние, версия или подтверждение."""


@dataclass
class Command:
    command_id: str
    kind: CommandKind
    actor: str
    site_id: str | None
    payload: dict[str, Any]
    idempotency_key: str
    state: CommandState = CommandState.DRAFT
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    reason: str = ""
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    rollback_reference: str | None = None
    expected_version: int | None = None
    history: tuple[tuple[str, str], ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "command_id": self.command_id,
            "kind": self.kind.value,
            "actor": self.actor,
            "site_id": self.site_id,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "reason": self.reason,
            "idempotency_key": self.idempotency_key,
            "expected_version": self.expected_version,
            "before": self.before,
            "after": self.after,
            "result": self.result,
            "rollback_reference": self.rollback_reference,
            "history": [{"state": s, "at": at} for s, at in self.history],
            # payload не отдаётся целиком: в нём может оказаться что угодно,
            # включая то, чего в ответе быть не должно.
            "payload_keys": sorted(self.payload),
        }


def _identifier(kind: CommandKind, actor: str, key: str) -> str:
    return hashlib.sha256(f"{kind.value}|{actor}|{key}".encode()).hexdigest()[:16]


class CommandLog:
    """Журнал команд с ключом идемпотентности и проверкой версии."""

    def __init__(self) -> None:
        self._by_id: dict[str, Command] = {}
        self._by_key: dict[str, str] = {}
        self._versions: dict[str, int] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------ подача
    def submit(
        self,
        *,
        kind: CommandKind,
        principal: Principal,
        site_id: str | None,
        payload: dict[str, Any],
        idempotency_key: str,
        reason: str = "",
        expected_version: int | None = None,
        confirmed: bool = False,
    ) -> tuple[Command, bool]:
        """Возвращает команду и признак «это повтор, работа уже была принята»."""
        if not idempotency_key:
            raise CommandRejected("команда без ключа идемпотентности не принимается")
        try:
            require(principal, REQUIRED_PERMISSION[kind], site_id)
        except AccessDenied as отказ:
            raise CommandRejected(str(отказ)) from отказ
        if kind in DANGEROUS and not confirmed:
            raise CommandRejected(
                f"{kind.value}: требуется отдельное подтверждение, а не сохранение формы"
            )

        with self._lock:
            прежний_id = self._by_key.get(idempotency_key)
            if прежний_id is not None:
                return self._by_id[прежний_id], True

            субъект = f"{kind.value}:{site_id or '-'}"
            текущая = self._versions.get(субъект, 0)
            if expected_version is not None and expected_version != текущая:
                raise CommandRejected(
                    f"версия объекта {текущая}, команда рассчитана на {expected_version}: "
                    "объект изменили, пока команда готовилась"
                )

            команда = Command(
                command_id=_identifier(kind, principal.principal_id, idempotency_key),
                kind=kind,
                actor=principal.principal_id,
                site_id=site_id,
                payload=dict(payload),
                idempotency_key=idempotency_key,
                reason=reason,
                expected_version=expected_version,
            )
            команда.history = (("DRAFT", команда.created_at.isoformat()),)
            self._by_id[команда.command_id] = команда
            self._by_key[idempotency_key] = команда.command_id
            return команда, False

    # ------------------------------------------------------------------ переход
    def transition(
        self,
        command_id: str,
        state: CommandState,
        *,
        result: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        rollback_reference: str | None = None,
    ) -> Command:
        with self._lock:
            команда = self._by_id.get(command_id)
            if команда is None:
                raise CommandRejected(f"команды {command_id} нет")
            if state not in ALLOWED_TRANSITIONS[команда.state]:
                raise CommandRejected(
                    f"переход {команда.state.value} → {state.value} не предусмотрен"
                )
            команда.state = state
            команда.updated_at = utc_now()
            команда.history = команда.history + ((state.value, команда.updated_at.isoformat()),)
            if result is not None:
                команда.result = result
            if after is not None:
                команда.after = after
            if rollback_reference is not None:
                команда.rollback_reference = rollback_reference
            if state is CommandState.SUCCEEDED:
                субъект = f"{команда.kind.value}:{команда.site_id or '-'}"
                self._versions[субъект] = self._versions.get(субъект, 0) + 1
            return команда

    # ------------------------------------------------------------------ чтение
    def get(self, command_id: str) -> Command | None:
        with self._lock:
            return self._by_id.get(command_id)

    def version_of(self, kind: CommandKind, site_id: str | None) -> int:
        with self._lock:
            return self._versions.get(f"{kind.value}:{site_id or '-'}", 0)

    def __iter__(self) -> Iterator[Command]:
        with self._lock:
            return iter(list(self._by_id.values()))

    def __len__(self) -> int:
        return len(self._by_id)

    def as_list(self) -> list[dict[str, Any]]:
        return [c.as_dict() for c in sorted(self, key=lambda c: c.created_at)]


def payload_digest(payload: dict[str, Any]) -> str:
    """Отпечаток содержания команды — для ключа идемпотентности по умолчанию."""
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
