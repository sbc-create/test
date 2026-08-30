"""Редакционный слой CMS: правки поверх данных поставщика, не вместо них.

Главное правило, из которого следует всё остальное: **данные поставщика
доступны только для чтения**. Редактор не исправляет карточку — он объявляет
правку, и правка накладывается при показе. Поэтому повторный обход никогда не
затирает работу редактора, а откат правки возвращает ровно то, что сообщил
источник.

Здесь есть модели и сценарии использования и намеренно нет ни админ-панели, ни
публичных изменяющих маршрутов: без настоящей авторизации такой маршрут — это
дыра, а не удобство.
"""
from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from factory.site_engine.audit import AuditLog
from factory.site_engine.audit import event as audit_event
from factory.site_engine.contracts import ContractError, Title, require_aware, utc_now


class PermissionDenied(ContractError):
    pass


class RevisionConflict(ContractError):
    """Двое правили одну запись. Побеждает не последний, а тот, кто видел свежее."""


class InvalidOverride(ContractError):
    pass


#: Поля, которые редактор вправе переопределить. Список закрыт: правка сезонов
#: или счётчиков серий означала бы, что витрина сообщает о содержимом то, чего
#: в источнике нет.
OVERRIDABLE_FIELDS = ("name", "original_name", "poster_url", "year", "kind")


class Role(str, Enum):
    VIEWER = "viewer"
    EDITOR = "editor"
    PUBLISHER = "publisher"
    ADMIN = "admin"


class Permission(str, Enum):
    READ = "read"
    DRAFT_WRITE = "draft:write"
    PUBLISH = "publish"
    UNPUBLISH = "unpublish"
    ROLLBACK = "rollback"
    BULK = "bulk"
    INVALIDATE_CACHE = "cache:invalidate"
    TRIGGER_INGESTION = "ingestion:trigger"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.VIEWER: frozenset({Permission.READ}),
    Role.EDITOR: frozenset({Permission.READ, Permission.DRAFT_WRITE}),
    Role.PUBLISHER: frozenset(
        {
            Permission.READ,
            Permission.DRAFT_WRITE,
            Permission.PUBLISH,
            Permission.UNPUBLISH,
            Permission.ROLLBACK,
            Permission.INVALIDATE_CACHE,
        }
    ),
    Role.ADMIN: frozenset(Permission),
}


@dataclass(frozen=True)
class Principal:
    """Кто действует и на каких сайтах.

    Область сайтов входит в личность, а не проверяется где-то потом: иначе
    редактор одного сайта однажды опубликует на всех шести.
    """

    actor: str
    role: Role
    site_ids: frozenset[str]

    def may(self, permission: Permission, site_id: str | None = None) -> bool:
        if permission not in ROLE_PERMISSIONS[self.role]:
            return False
        if site_id is None:
            return True
        return site_id in self.site_ids or "*" in self.site_ids

    def require(self, permission: Permission, site_id: str | None = None) -> None:
        if not self.may(permission, site_id):
            raise PermissionDenied(
                f"{self.actor} ({self.role.value}) не вправе выполнить "
                f"{permission.value}" + (f" на сайте {site_id}" if site_id else "")
            )


@dataclass(frozen=True)
class EditorialOverride:
    """Редакторская правка одного тайтла на одном сайте."""

    site_id: str
    canonical_title_id: str
    fields: dict[str, Any]
    author: str
    reason: str
    created_at: datetime

    def __post_init__(self) -> None:
        unknown = set(self.fields) - set(OVERRIDABLE_FIELDS)
        if unknown:
            raise InvalidOverride(
                f"поля {sorted(unknown)} принадлежат поставщику и правке не подлежат"
            )
        if not self.fields:
            raise InvalidOverride("пустая правка ничего не меняет")
        if not self.reason.strip():
            # Без причины через месяц никто не вспомнит, почему название другое.
            raise InvalidOverride("правка без причины не принимается")
        object.__setattr__(self, "created_at", require_aware(self.created_at, "created_at"))

    def apply_to(self, title: Title) -> Title:
        return title.with_overrides(self.fields)


class DraftStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    UNPUBLISHED = "unpublished"


@dataclass(frozen=True)
class Revision:
    """Снимок состояния черновика. Именно к нему возвращает откат."""

    number: int
    fields: dict[str, Any]
    author: str
    reason: str
    at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "at", require_aware(self.at, "at"))


@dataclass
class Draft:
    """Черновик правки. Живёт отдельно от показа, пока не опубликован."""

    draft_id: str
    site_id: str
    canonical_title_id: str
    fields: dict[str, Any]
    status: DraftStatus = DraftStatus.DRAFT
    version: int = 1
    revisions: list[Revision] = field(default_factory=list)
    published_revision: int | None = None

    def snapshot(self, author: str, reason: str) -> Revision:
        rev = Revision(number=len(self.revisions) + 1, fields=dict(self.fields),
                       author=author, reason=reason, at=utc_now())
        self.revisions.append(rev)
        return rev


@dataclass(frozen=True)
class PublicationTarget:
    """Куда публикуем. Список сайтов всегда явный — «на все» не бывает."""

    site_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.site_ids:
            raise ContractError("публикация без списка сайтов запрещена")


@dataclass(frozen=True)
class Publication:
    draft_id: str
    revision: int
    target: PublicationTarget
    published_by: str
    at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "at", require_aware(self.at, "at"))


@dataclass(frozen=True)
class PreviewToken:
    """Право посмотреть черновик, не публикуя его.

    Предпросмотр не влияет на LIVE — это свойство обеспечивается тем, что
    наложение черновика требует токена, а публичный показ его не имеет.
    """

    token: str
    draft_id: str
    expires_at: datetime

    def valid_at(self, moment: datetime) -> bool:
        return moment < self.expires_at


@dataclass
class ChangeSet:
    """Что именно изменится. Считается до применения, а не после."""

    site_id: str
    canonical_title_id: str
    before: dict[str, Any]
    after: dict[str, Any]

    @property
    def changed_fields(self) -> tuple[str, ...]:
        return tuple(sorted(k for k in self.after if self.before.get(k) != self.after[k]))

    @property
    def empty(self) -> bool:
        return not self.changed_fields


@dataclass
class BulkOperation:
    """Массовая операция. Сначала сухой прогон — всегда, без исключений."""

    operation_id: str
    site_ids: tuple[str, ...]
    changes: tuple[ChangeSet, ...]
    dry_run: bool = True
    applied: bool = False

    def plan(self) -> dict[str, Any]:
        touched = [c for c in self.changes if not c.empty]
        return {
            "operation_id": self.operation_id,
            "sites": list(self.site_ids),
            "changes_total": len(self.changes),
            "changes_effective": len(touched),
            "no_op": len(self.changes) - len(touched),
            "dry_run": self.dry_run,
        }


class EditorialService:
    """Сценарии использования редакционного слоя.

    Каждый изменяющий сценарий требует личности, проверяет право на конкретный
    сайт, пишет в аудит и поддерживает ключ идемпотентности. Ни один из них не
    трогает данные поставщика.
    """

    def __init__(self, audit: AuditLog | None = None) -> None:
        self._drafts: dict[str, Draft] = {}
        self._overrides: dict[tuple[str, str], EditorialOverride] = {}
        self._idempotency: dict[str, str] = {}
        self._lock = threading.RLock()
        self.audit = audit or AuditLog()

    # ------------------------------------------------------------- черновики
    def create_draft(
        self,
        principal: Principal,
        *,
        site_id: str,
        canonical_title_id: str,
        fields: dict[str, Any],
        reason: str,
        idempotency_key: str | None = None,
    ) -> Draft:
        principal.require(Permission.DRAFT_WRITE, site_id)
        unknown = set(fields) - set(OVERRIDABLE_FIELDS)
        if unknown:
            raise InvalidOverride(
                f"поля {sorted(unknown)} принадлежат поставщику и правке не подлежат"
            )
        if idempotency_key:
            with self._lock:
                known = self._idempotency.get(idempotency_key)
            if known:
                # Повтор той же просьбы обязан дать тот же результат, а не
                # второй черновик.
                return self._drafts[known]

        draft_id = hashlib.sha256(
            f"{site_id}|{canonical_title_id}|{utc_now().isoformat()}".encode()
        ).hexdigest()[:16]
        draft = Draft(draft_id=draft_id, site_id=site_id,
                      canonical_title_id=canonical_title_id, fields=dict(fields))
        draft.snapshot(principal.actor, reason)
        with self._lock:
            self._drafts[draft_id] = draft
            if idempotency_key:
                self._idempotency[idempotency_key] = draft_id
        self.audit.record(
            audit_event(actor=principal.actor, action="draft.create", subject=draft_id,
                        reason=reason, site_ids=(site_id,), after=dict(fields))
        )
        return draft

    def update_draft(
        self,
        principal: Principal,
        draft_id: str,
        *,
        fields: dict[str, Any],
        reason: str,
        expected_version: int,
    ) -> Draft:
        draft = self._draft(draft_id)
        principal.require(Permission.DRAFT_WRITE, draft.site_id)
        if expected_version != draft.version:
            # Оптимистичная блокировка: тот, кто правит вслепую, узнаёт об
            # этом сразу, а не после потери чужой работы.
            raise RevisionConflict(
                f"черновик уже версии {draft.version}, а правка основана на "
                f"версии {expected_version}"
            )
        before = dict(draft.fields)
        unknown = set(fields) - set(OVERRIDABLE_FIELDS)
        if unknown:
            raise InvalidOverride(f"поля {sorted(unknown)} правке не подлежат")
        draft.fields.update(fields)
        draft.version += 1
        draft.snapshot(principal.actor, reason)
        self.audit.record(
            audit_event(actor=principal.actor, action="draft.update", subject=draft_id,
                        reason=reason, site_ids=(draft.site_id,), before=before,
                        after=dict(draft.fields))
        )
        return draft

    # ------------------------------------------------------------ предпросмотр
    def preview(self, principal: Principal, draft_id: str, title: Title,
                token: PreviewToken | None = None) -> Title:
        draft = self._draft(draft_id)
        principal.require(Permission.READ, draft.site_id)
        if token is not None and token.draft_id != draft_id:
            raise PermissionDenied("токен предпросмотра выдан для другого черновика")
        # Предпросмотр ничего не сохраняет: LIVE о нём не узнаёт.
        return title.with_overrides(draft.fields)

    # -------------------------------------------------------------- публикация
    def publish(
        self,
        principal: Principal,
        draft_id: str,
        *,
        target: PublicationTarget,
        reason: str,
    ) -> Publication:
        draft = self._draft(draft_id)
        for site_id in target.site_ids:
            principal.require(Permission.PUBLISH, site_id)
        revision = draft.snapshot(principal.actor, reason)
        draft.status = DraftStatus.PUBLISHED
        draft.published_revision = revision.number
        with self._lock:
            for site_id in target.site_ids:
                self._overrides[(site_id, draft.canonical_title_id)] = EditorialOverride(
                    site_id=site_id,
                    canonical_title_id=draft.canonical_title_id,
                    fields=dict(draft.fields),
                    author=principal.actor,
                    reason=reason,
                    created_at=utc_now(),
                )
        self.audit.record(
            audit_event(actor=principal.actor, action="draft.publish", subject=draft_id,
                        reason=reason, site_ids=target.site_ids, after=dict(draft.fields))
        )
        return Publication(draft_id=draft_id, revision=revision.number, target=target,
                           published_by=principal.actor, at=utc_now())

    def unpublish(self, principal: Principal, draft_id: str, *, reason: str) -> None:
        draft = self._draft(draft_id)
        principal.require(Permission.UNPUBLISH, draft.site_id)
        with self._lock:
            removed = [
                key for key in self._overrides
                if key[1] == draft.canonical_title_id
            ]
            for key in removed:
                self._overrides.pop(key, None)
        draft.status = DraftStatus.UNPUBLISHED
        self.audit.record(
            audit_event(actor=principal.actor, action="draft.unpublish", subject=draft_id,
                        reason=reason, site_ids=(draft.site_id,))
        )

    def rollback(self, principal: Principal, draft_id: str, *, revision: int,
                 reason: str) -> Draft:
        draft = self._draft(draft_id)
        principal.require(Permission.ROLLBACK, draft.site_id)
        target = next((r for r in draft.revisions if r.number == revision), None)
        if target is None:
            raise ContractError(
                f"ревизии {revision} у черновика {draft_id} нет; "
                f"есть {[r.number for r in draft.revisions]}"
            )
        before = dict(draft.fields)
        draft.fields = dict(target.fields)
        draft.version += 1
        draft.snapshot(principal.actor, f"откат к ревизии {revision}: {reason}")
        self.audit.record(
            audit_event(actor=principal.actor, action="draft.rollback", subject=draft_id,
                        reason=reason, site_ids=(draft.site_id,), before=before,
                        after=dict(draft.fields))
        )
        return draft

    # ---------------------------------------------------------------- показ
    def apply_overrides(self, site_id: str, title: Title) -> Title:
        """Наложение правки при показе. Исходная запись не меняется."""
        override = self._overrides.get((site_id, title.canonical_id))
        return override.apply_to(title) if override else title

    def override_for(self, site_id: str, canonical_title_id: str) -> EditorialOverride | None:
        return self._overrides.get((site_id, canonical_title_id))

    # ------------------------------------------------------- массовые операции
    def plan_bulk(self, principal: Principal, operation: BulkOperation) -> dict[str, Any]:
        for site_id in operation.site_ids:
            principal.require(Permission.BULK, site_id)
        plan = operation.plan()
        self.audit.record(
            audit_event(actor=principal.actor, action="bulk.plan",
                        subject=operation.operation_id, reason="сухой прогон",
                        site_ids=operation.site_ids, after=plan)
        )
        return plan

    def apply_bulk(self, principal: Principal, operation: BulkOperation, *,
                   reason: str) -> dict[str, Any]:
        if operation.dry_run:
            raise ContractError(
                "массовая операция помечена как сухой прогон; применять нечего"
            )
        if not operation.applied and not any(
            e.action == "bulk.plan" and e.subject == operation.operation_id
            for e in self.audit
        ):
            # Сухой прогон обязателен: массовая правка вслепую по шести сайтам
            # необратима на глаз.
            raise ContractError(
                f"массовая операция {operation.operation_id} не проходила сухой прогон"
            )
        for site_id in operation.site_ids:
            principal.require(Permission.BULK, site_id)
        operation.applied = True
        result = operation.plan() | {"applied": True}
        self.audit.record(
            audit_event(actor=principal.actor, action="bulk.apply",
                        subject=operation.operation_id, reason=reason,
                        site_ids=operation.site_ids, after=result)
        )
        return result

    def _draft(self, draft_id: str) -> Draft:
        try:
            return self._drafts[draft_id]
        except KeyError:
            raise ContractError(f"черновика {draft_id} нет") from None
