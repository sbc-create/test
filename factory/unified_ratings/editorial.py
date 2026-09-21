"""Редакционная оценка 1–10 — наша собственная, защищённая RBAC.

Редакционная оценка не пишется в таблицы пользовательских голосов и не
участвует в их агрегате. В интерфейсе она называется «Наша оценка» и
никогда — IMDb, Кинопоиском, AniList или оценкой зрителей: подпись здесь
не оформление, а утверждение об источнике числа.

Audit обязателен и пишется в той же транзакции, что и сама оценка.
Запись, сделанная отдельным вызовом «после», теряется ровно тогда, когда
она нужна — при сбое между двумя записями.

Массовое изменение требует предварительного preview: список того, что
именно изменится, с прежними значениями. Пакетная операция без него —
единственный способ переписать сотню оценок, не заметив ошибки в фильтре.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

from factory.unified_ratings.scale import validate_community_score
from factory.unified_ratings.store import UnifiedStore
from factory.unified_ratings.titles import TitleRegistry, utc_now

#: Роли, которым разрешено ставить редакционную оценку.
EDITORIAL_ROLES: frozenset[str] = frozenset({"editor_in_chief", "content_editor"})

#: Роли, которым разрешено только читать историю.
READONLY_ROLES: frozenset[str] = frozenset({"editorial_auditor"})

SCOPE_GLOBAL = "global"
SCOPE_TENANT = "tenant"

STATUS_ACTIVE = "ACTIVE"
STATUS_WITHDRAWN = "WITHDRAWN"

#: Выше этого числа изменение считается массовым и требует preview.
BULK_THRESHOLD = 5


class EditorialDenied(PermissionError):
    status = 403


class EditorialRejected(ValueError):
    status = 400


@dataclass(frozen=True)
class Principal:
    """Кто выполняет действие. Роль приходит из системы прав, не из запроса."""

    actor_id: str
    role: str

    @property
    def may_write(self) -> bool:
        return self.role in EDITORIAL_ROLES

    @property
    def may_read(self) -> bool:
        return self.role in EDITORIAL_ROLES or self.role in READONLY_ROLES


@dataclass(frozen=True)
class EditorialRating:
    title_id: str
    scope_kind: str
    scope_id: str
    score: int | None
    status: str
    author_id: str
    author_role: str
    rationale: str
    created_at: str
    updated_at: str
    withdrawn_at: str
    revision: int

    @property
    def active(self) -> bool:
        return self.status == STATUS_ACTIVE and self.score is not None

    def as_dict(self) -> dict[str, Any]:
        return {
            "title_id": self.title_id,
            "scope": {"kind": self.scope_kind, "id": self.scope_id},
            "score": self.score if self.active else None,
            "scale": "1-10",
            "label": "Наша оценка",
            "status": self.status,
            "author_id": self.author_id,
            "author_role": self.author_role,
            "rationale": self.rationale,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "withdrawn_at": self.withdrawn_at,
            "revision": self.revision,
        }


class EditorialRatings:
    def __init__(self, store: UnifiedStore, *, registry: TitleRegistry | None = None) -> None:
        self.store = store
        self.registry = registry or TitleRegistry(store)

    # ------------------------------------------------------------------

    def _require_write(self, principal: Principal) -> None:
        if not principal.may_write:
            raise EditorialDenied(
                f"роль {principal.role!r} не может ставить редакционную оценку; "
                f"разрешены: {', '.join(sorted(EDITORIAL_ROLES))}"
            )

    def _require_read(self, principal: Principal) -> None:
        if not principal.may_read:
            raise EditorialDenied(f"роль {principal.role!r} не может читать редакционную историю")

    def _require_title(self, title_id: str) -> None:
        if not self.registry.exists(title_id):
            raise EditorialRejected(f"канонический тайтл не найден: {title_id}")

    @staticmethod
    def _normalize_scope(scope_kind: str, scope_id: str) -> tuple[str, str]:
        if scope_kind not in (SCOPE_GLOBAL, SCOPE_TENANT):
            raise EditorialRejected(f"область должна быть global или tenant, получено: {scope_kind}")
        if scope_kind == SCOPE_GLOBAL:
            return SCOPE_GLOBAL, ""
        if not scope_id:
            raise EditorialRejected("для области tenant требуется идентификатор площадки")
        return SCOPE_TENANT, scope_id

    # ------------------------------------------------------------------

    def get(
        self, *, title_id: str, scope_kind: str = SCOPE_GLOBAL, scope_id: str = ""
    ) -> EditorialRating | None:
        scope_kind, scope_id = self._normalize_scope(scope_kind, scope_id)
        row = self.store.query_one(
            """SELECT * FROM unified_editorial_ratings
               WHERE title_id=? AND scope_kind=? AND scope_id=?""",
            (title_id, scope_kind, scope_id),
        )
        return None if row is None else _row_to_rating(row)

    def effective(self, *, title_id: str, tenant_id: str = "") -> EditorialRating | None:
        """Оценка площадки, иначе глобальная. Порядок явный и один."""
        if tenant_id:
            tenant_rating = self.get(title_id=title_id, scope_kind=SCOPE_TENANT, scope_id=tenant_id)
            if tenant_rating is not None and tenant_rating.active:
                return tenant_rating
        global_rating = self.get(title_id=title_id, scope_kind=SCOPE_GLOBAL)
        return global_rating if global_rating is not None and global_rating.active else None

    # ------------------------------------------------------------------

    def set_score(
        self,
        principal: Principal,
        *,
        title_id: str,
        score: Any,
        rationale: str,
        scope_kind: str = SCOPE_GLOBAL,
        scope_id: str = "",
        batch_id: str = "",
    ) -> EditorialRating:
        self._require_write(principal)
        self._require_title(title_id)
        scope_kind, scope_id = self._normalize_scope(scope_kind, scope_id)
        try:
            clean = validate_community_score(score)
        except ValueError as exc:
            raise EditorialRejected(str(exc)) from None
        if not rationale.strip():
            raise EditorialRejected("редакционная оценка требует основания")

        existing = self.get(title_id=title_id, scope_kind=scope_kind, scope_id=scope_id)
        now = utc_now()
        action = "SET" if existing is None else ("RESTORE" if existing.status == STATUS_WITHDRAWN else "UPDATE")
        old_score = existing.score if existing is not None else None
        revision = 1 if existing is None else existing.revision + 1
        created_at = existing.created_at if existing is not None else now

        with self.store.write_tx() as conn:
            conn.execute(
                """INSERT INTO unified_editorial_ratings(
                       title_id, scope_kind, scope_id, score, status, author_id, author_role,
                       rationale, created_at, updated_at, withdrawn_at, revision)
                   VALUES (?,?,?,?,?,?,?,?,?,?,'',?)
                   ON CONFLICT(title_id, scope_kind, scope_id) DO UPDATE SET
                       score=excluded.score, status=excluded.status,
                       author_id=excluded.author_id, author_role=excluded.author_role,
                       rationale=excluded.rationale, updated_at=excluded.updated_at,
                       withdrawn_at='', revision=excluded.revision""",
                (
                    title_id, scope_kind, scope_id, clean, STATUS_ACTIVE,
                    principal.actor_id, principal.role, rationale, created_at, now, revision,
                ),
            )
            _write_audit(
                conn,
                title_id=title_id,
                scope_kind=scope_kind,
                scope_id=scope_id,
                action=action,
                old_score=old_score,
                new_score=clean,
                principal=principal,
                rationale=rationale,
                batch_id=batch_id,
                created_at=now,
            )
        result = self.get(title_id=title_id, scope_kind=scope_kind, scope_id=scope_id)
        assert result is not None
        return result

    def withdraw(
        self,
        principal: Principal,
        *,
        title_id: str,
        rationale: str,
        scope_kind: str = SCOPE_GLOBAL,
        scope_id: str = "",
        batch_id: str = "",
    ) -> EditorialRating:
        """Снять оценку. Значение уходит из показа, история остаётся."""
        self._require_write(principal)
        scope_kind, scope_id = self._normalize_scope(scope_kind, scope_id)
        existing = self.get(title_id=title_id, scope_kind=scope_kind, scope_id=scope_id)
        if existing is None:
            raise EditorialRejected(f"нечего снимать: у {title_id} нет редакционной оценки")
        if not rationale.strip():
            raise EditorialRejected("снятие редакционной оценки требует основания")
        now = utc_now()
        with self.store.write_tx() as conn:
            conn.execute(
                """UPDATE unified_editorial_ratings
                   SET status=?, withdrawn_at=?, updated_at=?, revision=?,
                       author_id=?, author_role=?, rationale=?
                   WHERE title_id=? AND scope_kind=? AND scope_id=?""",
                (
                    STATUS_WITHDRAWN, now, now, existing.revision + 1,
                    principal.actor_id, principal.role, rationale,
                    title_id, scope_kind, scope_id,
                ),
            )
            _write_audit(
                conn,
                title_id=title_id,
                scope_kind=scope_kind,
                scope_id=scope_id,
                action="WITHDRAW",
                old_score=existing.score,
                new_score=None,
                principal=principal,
                rationale=rationale,
                batch_id=batch_id,
                created_at=now,
            )
        result = self.get(title_id=title_id, scope_kind=scope_kind, scope_id=scope_id)
        assert result is not None
        return result

    # ------------------------------------------------------------------
    # массовое изменение
    # ------------------------------------------------------------------

    def preview_bulk(
        self,
        principal: Principal,
        changes: list[dict[str, Any]],
        *,
        scope_kind: str = SCOPE_GLOBAL,
        scope_id: str = "",
    ) -> dict[str, Any]:
        """Что именно изменится. Без этого пакет не применяется."""
        self._require_write(principal)
        scope_kind, scope_id = self._normalize_scope(scope_kind, scope_id)
        rows: list[dict[str, Any]] = []
        problems: list[str] = []
        for change in changes:
            title_id = str(change.get("title_id") or "")
            try:
                score = validate_community_score(change.get("score"))
            except ValueError as exc:
                problems.append(f"{title_id}: {exc}")
                continue
            if not self.registry.exists(title_id):
                problems.append(f"{title_id}: канонический тайтл не найден")
                continue
            existing = self.get(title_id=title_id, scope_kind=scope_kind, scope_id=scope_id)
            rows.append(
                {
                    "title_id": title_id,
                    "old_score": existing.score if existing and existing.active else None,
                    "new_score": score,
                    "changes": (existing.score if existing and existing.active else None) != score,
                }
            )
        preview_id = f"bulk-{uuid.uuid4().hex[:12]}"
        return {
            "preview_id": preview_id,
            "scope": {"kind": scope_kind, "id": scope_id},
            "count": len(rows),
            "changing": sum(1 for r in rows if r["changes"]),
            "rows": rows,
            "problems": problems,
            "applicable": not problems,
        }

    def apply_bulk(
        self,
        principal: Principal,
        changes: list[dict[str, Any]],
        *,
        preview: dict[str, Any],
        rationale: str,
        scope_kind: str = SCOPE_GLOBAL,
        scope_id: str = "",
    ) -> dict[str, Any]:
        self._require_write(principal)
        if len(changes) > BULK_THRESHOLD and not preview:
            raise EditorialRejected(
                f"изменение {len(changes)} оценок требует preview (порог {BULK_THRESHOLD})"
            )
        if not preview or not preview.get("applicable"):
            raise EditorialRejected("preview отсутствует или содержит неустранённые проблемы")
        previewed = {r["title_id"]: r["new_score"] for r in preview.get("rows", [])}
        requested = {str(c.get("title_id")): c.get("score") for c in changes}
        if previewed != requested:
            # Набор изменился между preview и применением — применять
            # нечего: подтверждали не это.
            raise EditorialRejected("набор изменений не совпадает с показанным в preview")

        batch_id = preview["preview_id"]
        applied = []
        for title_id, score in requested.items():
            applied.append(
                self.set_score(
                    principal,
                    title_id=title_id,
                    score=score,
                    rationale=rationale,
                    scope_kind=scope_kind,
                    scope_id=scope_id,
                    batch_id=batch_id,
                ).as_dict()
            )
        return {"batch_id": batch_id, "applied": len(applied), "rows": applied}

    # ------------------------------------------------------------------
    # история
    # ------------------------------------------------------------------

    def history(
        self, principal: Principal, *, title_id: str | None = None, limit: int = 500
    ) -> list[dict[str, Any]]:
        self._require_read(principal)
        if title_id:
            rows = self.store.query(
                "SELECT * FROM unified_editorial_audit WHERE title_id=? ORDER BY audit_id DESC LIMIT ?",
                (title_id, limit),
            )
        else:
            rows = self.store.query(
                "SELECT * FROM unified_editorial_audit ORDER BY audit_id DESC LIMIT ?", (limit,)
            )
        return [dict(r) for r in rows]

    def export_history(self, principal: Principal) -> str:
        """Полный экспорт истории в JSON Lines."""
        self._require_read(principal)
        rows = self.store.query("SELECT * FROM unified_editorial_audit ORDER BY audit_id")
        return "\n".join(json.dumps(dict(r), ensure_ascii=False, sort_keys=True) for r in rows)


def _write_audit(
    conn,
    *,
    title_id: str,
    scope_kind: str,
    scope_id: str,
    action: str,
    old_score: int | None,
    new_score: int | None,
    principal: Principal,
    rationale: str,
    batch_id: str,
    created_at: str,
) -> None:
    conn.execute(
        """INSERT INTO unified_editorial_audit(
               title_id, scope_kind, scope_id, action, old_score, new_score,
               actor_id, actor_role, rationale, batch_id, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            title_id, scope_kind, scope_id, action, old_score, new_score,
            principal.actor_id, principal.role, rationale, batch_id, created_at,
        ),
    )


def _row_to_rating(row: Any) -> EditorialRating:
    return EditorialRating(
        title_id=row["title_id"],
        scope_kind=row["scope_kind"],
        scope_id=row["scope_id"],
        score=row["score"],
        status=row["status"],
        author_id=row["author_id"],
        author_role=row["author_role"],
        rationale=row["rationale"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        withdrawn_at=row["withdrawn_at"],
        revision=int(row["revision"]),
    )
