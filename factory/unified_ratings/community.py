"""Пользовательские оценки 1–10 в единой модели.

Голоса пишет существующий проверенный ledger ``CommunityVotesService``
(Stage 05–08, живой 1% canary): идемпотентность, история событий,
антифрод, kill switch и восстановление агрегата уже проверены на нём.
Второй путь записи означал бы второй набор инвариантов и две разные
правды о том, сколько у тайтла голосов.

Здесь добавлено то, чего в ledger нет:

* ``title_id`` определяется сервером по паре (tenant, subject) из
  ``unified_title_tenant_map``. Клиент его не передаёт и передать не
  может — иначе голос с одной площадки ушёл бы тайтлу другой;
* агрегат с распределением 1–10 и контрольной суммой;
* сетевой агрегат по одному явному правилу, а не молчаливым сложением.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from factory.unified_ratings.scale import validate_community_score
from factory.unified_ratings.store import UnifiedStore
from factory.unified_ratings.titles import TitleRegistry, utc_now

DIMENSION_OVERALL = "overall"
STATUS_ACCEPTED = "ACCEPTED"

#: Правило сетевого агрегата. Одно, названное, и другого нет.
#:
#: Один активный голос участника на тайтл во всей сети. Если участник
#: проголосовал на двух площадках, учитывается последний по времени
#: изменения. Простое сложение площадочных агрегатов дало бы такому
#: участнику два голоса и незаметно завысило бы сетевое среднее.
NETWORK_RULE = "one_active_vote_per_actor_per_title__latest_wins/v1"


class VoteRejected(ValueError):
    """Голос отклонён до записи. Не техническая ошибка, а отказ по правилу."""

    status = 400


class UnknownSubject(VoteRejected):
    status = 404


@dataclass(frozen=True)
class AggregateView:
    scope_kind: str
    scope_id: str
    title_id: str
    vote_count: int
    vote_sum: int
    average: str | None
    distribution: dict[str, int]
    checksum: str
    recomputed_at: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "scope_kind": self.scope_kind,
            "scope_id": self.scope_id,
            "title_id": self.title_id,
            "vote_count": self.vote_count,
            "vote_sum": self.vote_sum,
            # Отсутствие голосов — не ноль. Ноль в этом поле означал бы,
            # что зрители поставили тайтлу нулевую оценку.
            "average": self.average,
            "distribution": self.distribution,
            "checksum": self.checksum,
            "recomputed_at": self.recomputed_at,
            "rule": NETWORK_RULE if self.scope_kind == "network" else "tenant_ledger/v1",
        }


def checksum_for(
    *, scope_kind: str, scope_id: str, title_id: str, vote_count: int, vote_sum: int,
    distribution: dict[str, int]
) -> str:
    material = json.dumps(
        {
            "scope_kind": scope_kind,
            "scope_id": scope_id,
            "title_id": title_id,
            "vote_count": vote_count,
            "vote_sum": vote_sum,
            "distribution": {str(k): int(v) for k, v in sorted(distribution.items())},
            "rule": NETWORK_RULE if scope_kind == "network" else "tenant_ledger/v1",
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _average(vote_sum: int, vote_count: int) -> str | None:
    if vote_count <= 0:
        return None
    from decimal import ROUND_HALF_UP, Decimal

    value = Decimal(vote_sum) / Decimal(vote_count)
    return f"{value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}"


class CommunityRatings:
    """Приём и чтение пользовательских оценок 1–10."""

    def __init__(
        self,
        store: UnifiedStore,
        votes_service: Any,
        *,
        registry: TitleRegistry | None = None,
    ) -> None:
        self.store = store
        self.votes = votes_service
        self.registry = registry or TitleRegistry(store)

    # ------------------------------------------------------------------
    # запись
    # ------------------------------------------------------------------

    def _resolve(self, tenant_id: str, subject_id: str) -> str:
        title_id = self.registry.resolve_subject(tenant_id, subject_id)
        if title_id is None:
            raise UnknownSubject(
                f"на площадке {tenant_id} нет тайтла с subject_id={subject_id}"
            )
        return title_id

    def submit(
        self,
        *,
        tenant_id: str,
        subject_id: str,
        actor_id: str,
        score: Any,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Поставить или изменить оценку.

        ``score`` проверяется до обращения к ledger: значение из интерфейса
        сервером не принимается на веру, и 8.5, "8", 0 или 11 не доходят до
        записи ни при какой реализации клиента.
        """
        if not idempotency_key:
            raise VoteRejected("требуется idempotency key")
        title_id = self._resolve(tenant_id, subject_id)
        try:
            clean = validate_community_score(score)
        except ValueError as exc:
            raise VoteRejected(str(exc)) from None

        response = self.votes.put_vote(
            idempotency_key=idempotency_key,
            rating_space_id=tenant_id,
            subject_id=subject_id,
            actor_id=actor_id,
            score=clean,
        )
        aggregate = self.rebuild(tenant_id=tenant_id, title_id=title_id)
        return {
            "title_id": title_id,
            "tenant_id": tenant_id,
            "your_score": clean,
            "scale": "1-10",
            "ledger": response,
            "aggregate": aggregate.as_dict(),
        }

    def retract(
        self, *, tenant_id: str, subject_id: str, actor_id: str, idempotency_key: str
    ) -> dict[str, Any]:
        """Отозвать оценку. Голос выходит из агрегата, история остаётся."""
        if not idempotency_key:
            raise VoteRejected("требуется idempotency key")
        title_id = self._resolve(tenant_id, subject_id)
        response = self.votes.delete_vote(
            idempotency_key=idempotency_key,
            rating_space_id=tenant_id,
            subject_id=subject_id,
            actor_id=actor_id,
        )
        aggregate = self.rebuild(tenant_id=tenant_id, title_id=title_id)
        return {
            "title_id": title_id,
            "tenant_id": tenant_id,
            "your_score": None,
            "ledger": response,
            "aggregate": aggregate.as_dict(),
        }

    # ------------------------------------------------------------------
    # чтение
    # ------------------------------------------------------------------

    def my_vote(self, *, tenant_id: str, subject_id: str, actor_id: str) -> int | None:
        row = self.votes.store.conn.execute(
            """SELECT score, status FROM community_votes
               WHERE rating_space_id=? AND subject_id=? AND actor_id=? AND dimension=?""",
            (tenant_id, subject_id, actor_id, DIMENSION_OVERALL),
        ).fetchone()
        if row is None or row["status"] != STATUS_ACCEPTED:
            return None
        return int(row["score"])

    def summary(self, *, tenant_id: str, subject_id: str, actor_id: str | None = None) -> dict[str, Any]:
        title_id = self._resolve(tenant_id, subject_id)
        aggregate = self.get_aggregate(scope_kind="tenant", scope_id=tenant_id, title_id=title_id)
        return {
            "title_id": title_id,
            "tenant_id": tenant_id,
            "scale": "1-10",
            "aggregate": None if aggregate is None else aggregate.as_dict(),
            "your_score": (
                None if actor_id is None
                else self.my_vote(tenant_id=tenant_id, subject_id=subject_id, actor_id=actor_id)
            ),
        }

    # ------------------------------------------------------------------
    # агрегат
    # ------------------------------------------------------------------

    def _ledger_rows(self, *, tenant_id: str | None, title_id: str) -> list[dict[str, Any]]:
        """Активные голоса по тайтлу. Источник истины — ledger, не агрегат."""
        subjects = self.store.query(
            "SELECT tenant_id, subject_id FROM unified_title_tenant_map WHERE title_id=?"
            + (" AND tenant_id=?" if tenant_id else ""),
            (title_id, tenant_id) if tenant_id else (title_id,),
        )
        rows: list[dict[str, Any]] = []
        for sub in subjects:
            found = self.votes.store.conn.execute(
                """SELECT actor_id, score, updated_at FROM community_votes
                   WHERE rating_space_id=? AND subject_id=? AND dimension=? AND status=?""",
                (sub["tenant_id"], sub["subject_id"], DIMENSION_OVERALL, STATUS_ACCEPTED),
            ).fetchall()
            for row in found:
                rows.append(
                    {
                        "tenant_id": sub["tenant_id"],
                        "actor_id": row["actor_id"],
                        "score": int(row["score"]),
                        "updated_at": row["updated_at"],
                    }
                )
        return rows

    def rebuild(self, *, tenant_id: str | None, title_id: str) -> AggregateView:
        """Пересчитать агрегат из ledger и записать его."""
        if tenant_id is None:
            return self.rebuild_network(title_id=title_id)
        rows = self._ledger_rows(tenant_id=tenant_id, title_id=title_id)
        return self._write_aggregate(
            scope_kind="tenant", scope_id=tenant_id, title_id=title_id, rows=rows
        )

    def rebuild_network(self, *, title_id: str) -> AggregateView:
        """Сетевой агрегат по правилу NETWORK_RULE."""
        rows = self._ledger_rows(tenant_id=None, title_id=title_id)
        latest: dict[str, dict[str, Any]] = {}
        for row in rows:
            previous = latest.get(row["actor_id"])
            if previous is None or str(row["updated_at"]) > str(previous["updated_at"]):
                latest[row["actor_id"]] = row
        return self._write_aggregate(
            scope_kind="network", scope_id="", title_id=title_id, rows=list(latest.values())
        )

    def _write_aggregate(
        self, *, scope_kind: str, scope_id: str, title_id: str, rows: list[dict[str, Any]]
    ) -> AggregateView:
        distribution = {str(i): 0 for i in range(1, 11)}
        vote_sum = 0
        for row in rows:
            score = int(row["score"])
            if score < 1 or score > 10:
                # Ledger не может содержать такого значения; если содержит,
                # это повреждение данных, и оно не должно молча попасть в
                # среднее.
                raise ValueError(
                    f"ledger содержит оценку вне 1–10: {score} ({title_id}/{scope_id})"
                )
            distribution[str(score)] += 1
            vote_sum += score
        vote_count = len(rows)
        checksum = checksum_for(
            scope_kind=scope_kind,
            scope_id=scope_id,
            title_id=title_id,
            vote_count=vote_count,
            vote_sum=vote_sum,
            distribution=distribution,
        )
        now = utc_now()
        with self.store.write_tx() as conn:
            conn.execute(
                """INSERT INTO unified_user_aggregates(
                       scope_kind, scope_id, title_id, dimension, vote_sum, vote_count,
                       average_score, distribution_json, checksum, aggregate_version,
                       recomputed_at)
                   VALUES (?,?,?,?,?,?,?,?,?,1,?)
                   ON CONFLICT(scope_kind, scope_id, title_id, dimension) DO UPDATE SET
                       vote_sum=excluded.vote_sum,
                       vote_count=excluded.vote_count,
                       average_score=excluded.average_score,
                       distribution_json=excluded.distribution_json,
                       checksum=excluded.checksum,
                       aggregate_version=unified_user_aggregates.aggregate_version+1,
                       recomputed_at=excluded.recomputed_at""",
                (
                    scope_kind,
                    scope_id,
                    title_id,
                    DIMENSION_OVERALL,
                    vote_sum,
                    vote_count,
                    _average(vote_sum, vote_count),
                    json.dumps(distribution, ensure_ascii=False),
                    checksum,
                    now,
                ),
            )
        return AggregateView(
            scope_kind=scope_kind,
            scope_id=scope_id,
            title_id=title_id,
            vote_count=vote_count,
            vote_sum=vote_sum,
            average=_average(vote_sum, vote_count),
            distribution=distribution,
            checksum=checksum,
            recomputed_at=now,
        )

    def get_aggregate(
        self, *, scope_kind: str, scope_id: str, title_id: str
    ) -> AggregateView | None:
        row = self.store.query_one(
            """SELECT * FROM unified_user_aggregates
               WHERE scope_kind=? AND scope_id=? AND title_id=? AND dimension=?""",
            (scope_kind, scope_id, title_id, DIMENSION_OVERALL),
        )
        if row is None:
            return None
        return AggregateView(
            scope_kind=row["scope_kind"],
            scope_id=row["scope_id"],
            title_id=row["title_id"],
            vote_count=int(row["vote_count"]),
            vote_sum=int(row["vote_sum"]),
            average=row["average_score"],
            distribution=json.loads(row["distribution_json"] or "{}"),
            checksum=row["checksum"],
            recomputed_at=row["recomputed_at"],
        )

    def verify_aggregate(self, *, scope_kind: str, scope_id: str, title_id: str) -> dict[str, Any]:
        """Сверить записанный агрегат с пересчётом из ledger."""
        stored = self.get_aggregate(scope_kind=scope_kind, scope_id=scope_id, title_id=title_id)
        rows = self._ledger_rows(
            tenant_id=scope_id if scope_kind == "tenant" else None, title_id=title_id
        )
        if scope_kind == "network":
            latest: dict[str, dict[str, Any]] = {}
            for row in rows:
                previous = latest.get(row["actor_id"])
                if previous is None or str(row["updated_at"]) > str(previous["updated_at"]):
                    latest[row["actor_id"]] = row
            rows = list(latest.values())
        distribution = {str(i): 0 for i in range(1, 11)}
        vote_sum = 0
        for row in rows:
            distribution[str(int(row["score"]))] += 1
            vote_sum += int(row["score"])
        expected = checksum_for(
            scope_kind=scope_kind,
            scope_id=scope_id,
            title_id=title_id,
            vote_count=len(rows),
            vote_sum=vote_sum,
            distribution=distribution,
        )
        return {
            "match": stored is not None and stored.checksum == expected,
            "stored_checksum": None if stored is None else stored.checksum,
            "recomputed_checksum": expected,
            "ledger_vote_count": len(rows),
            "stored_vote_count": None if stored is None else stored.vote_count,
        }
