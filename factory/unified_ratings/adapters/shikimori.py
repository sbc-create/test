"""Shikimori в едином контракте — обёртка над уже разрешённым коннектором.

Новый адаптер не пишется намеренно. Разрешение владельца от 2026-09-19
выдано на существующий проверенный коннектор
``factory/ratings/adapters/shikimori.py``, прошедший Stage 1–5 на живых
данных; второй клиент к тому же API означал бы второй, не проверенный
способ доступа и удвоенную нагрузку на тот же лимит.

Обёртка приводит результат к ``SourceFetch`` и ничего не добавляет к
запросу.
"""

from __future__ import annotations

from typing import Any

from factory.ratings.adapters.base import AdapterError
from factory.ratings.adapters.shikimori import ShikimoriGraphQLAdapter
from factory.ratings.rate_limit import RateLimiter
from factory.unified_ratings import ADAPTER_VERSION_SHIKIMORI
from factory.unified_ratings.adapters.base import Capabilities, HealthState, SourceFetch
from factory.unified_ratings.sources import SHIKIMORI

SOURCE_KEY = "shikimori"
MAX_BATCH = 50


class ShikimoriUnifiedAdapter:
    source_key = SOURCE_KEY
    adapter_version = ADAPTER_VERSION_SHIKIMORI

    def __init__(self, inner: ShikimoriGraphQLAdapter | None = None) -> None:
        self.inner = inner or ShikimoriGraphQLAdapter(
            rate_limiter=RateLimiter(
                max_rps=SHIKIMORI.max_rps,
                max_per_minute=SHIKIMORI.max_requests_per_minute,
            ),
            batch_size=MAX_BATCH,
        )

    def capabilities(self) -> Capabilities:
        return Capabilities(
            source_key=SOURCE_KEY,
            supports_batch=True,
            max_batch_size=MAX_BATCH,
            supports_vote_count=True,
            supports_user_count=False,
            supports_distribution=True,
            supports_source_side_incremental=False,
            incremental_mode="локальный checkpoint по нашей очереди тайтлов",
            external_id_space="shikimori_id; malId — ключ сопоставления, не оценка",
            requires_credential=False,
        )

    def fetch_by_external_ids(self, external_ids: list[str]) -> dict[str, SourceFetch]:
        inner_results = self.inner.fetch_by_ids([str(i) for i in external_ids])
        out: dict[str, SourceFetch] = {}
        for key, res in inner_results.items():
            out[key] = SourceFetch(
                source_key=SOURCE_KEY,
                external_id=res.external_id or key,
                # Shikimori фильтрует по своему идентификатору, а спрашиваем
                # мы по MAL. Для большинства тайтлов это одно число, но
                # «обычно совпадает» — не основание: malId из ответа и есть
                # независимая проверка того, про какой тайтл он ответил.
                crosswalk_ids={"myanimelist": str(res.mal_id)} if res.mal_id else {},
                found=res.found,
                raw_score=res.raw_score,
                vote_count=res.vote_count,
                user_count=None,
                score_distribution=res.score_distribution,
                source_updated_at=res.source_updated_at,
                provenance_url=res.provenance_url,
                titles={"name": res.name, "russian": res.russian},
                raw_payload=dict(res.payload or {}),
                error=res.error,
            )
        return out

    def health(self) -> dict[str, Any]:
        try:
            probe = self.inner.check_schema()
        except AdapterError as exc:
            return {
                "source_key": SOURCE_KEY,
                "state": HealthState.BLOCKED if exc.hard_circuit else HealthState.DEGRADED,
                "error": str(exc),
            }
        return {"source_key": SOURCE_KEY, "state": HealthState.HEALTHY, "probe": probe}
