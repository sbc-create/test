"""Конвейер сбора внешних оценок: прогон, сопоставление, снимок.

Прогон всегда описан в ``unified_import_runs``, даже если он упал на
первом запросе. Незаписанный прогон — это сбор, которого по данным не
было, и повторный запуск начинает его заново с того же места.

Один и тот же ответ источника не создаёт новую версию. Сравнение идёт по
``content_hash`` — хешу только тех полей, которые составляют оценку
(значение, число голосов, распределение). Время ответа в хеш не входит,
иначе ежедневная проверка неизменившегося тайтла порождала бы по версии
в день и через год истории было бы невозможно найти реальное изменение.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from factory.ratings.adapters.base import AdapterError
from factory.unified_ratings import MODULE_VERSION
from factory.unified_ratings.adapters.base import SourceFetch
from factory.unified_ratings.matching import (
    MatchDecision,
    MatchStatus,
    QuarantineReason,
    TitleFacts,
    disagreements,
)
from factory.unified_ratings.metrics import MetricsRecorder
from factory.unified_ratings.scale import ScoreState, normalize
from factory.unified_ratings.sources import SourceDefinition, SourceStatus
from factory.unified_ratings.store import UnifiedStore
from factory.unified_ratings.titles import CanonicalTitle, TitleRegistry, utc_now

#: Идентификаторы источника → пространство идентификаторов нашего каталога.
ID_SPACE_BY_SOURCE = {
    "anilist": "myanimelist",
    "kitsu": "myanimelist",
    "shikimori": "myanimelist",
    "provider_feed_imdb": "imdb",
    "provider_feed_kinopoisk": "kinopoisk",
    "simkl": "myanimelist",
}


@dataclass
class RunCounters:
    requested: int = 0
    received: int = 0
    exact_match: int = 0
    pending_match: int = 0
    rejected: int = 0
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    failed: int = 0
    rate_limited: int = 0
    retries: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass
class IngestionResult:
    run_id: str
    source_key: str
    status: str
    counters: RunCounters
    cursor_out: str = ""
    next_checkpoint: str = ""
    error: str = ""
    review_items: list[dict[str, Any]] = field(default_factory=list)
    samples: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "source_key": self.source_key,
            "status": self.status,
            "counters": self.counters.as_dict(),
            "cursor_out": self.cursor_out,
            "next_checkpoint": self.next_checkpoint,
            "error": self.error,
            "review_items": self.review_items,
            "samples": self.samples,
        }


class IngestionRefused(RuntimeError):
    """Сбор не запускается. Причина — не техническая ошибка, а запрет."""


class Ingestor:
    """Сбор оценок одного источника в единую модель."""

    def __init__(
        self,
        store: UnifiedStore,
        source: SourceDefinition,
        adapter: Any,
        *,
        dry_run: bool = True,
    ) -> None:
        self.store = store
        self.source = source
        self.adapter = adapter
        self.dry_run = dry_run
        self.registry = TitleRegistry(store)

    # ------------------------------------------------------------------
    # прогон
    # ------------------------------------------------------------------

    def run(
        self,
        titles: list[CanonicalTitle],
        *,
        stage: str = "",
        run_id: str | None = None,
        cursor_in: str = "",
    ) -> IngestionResult:
        if self.source.status not in (SourceStatus.READY, SourceStatus.FEED_ONLY):
            raise IngestionRefused(
                f"{self.source.source_key}: статус {self.source.status.value} — "
                f"{self.source.blocker or 'сбор не разрешён'}"
            )

        run_id = run_id or f"{self.source.source_key}-{uuid.uuid4().hex[:12]}"
        counters = RunCounters(requested=len(titles))
        metrics = MetricsRecorder(self.store, run_id=run_id)
        started = datetime.now(timezone.utc)
        self._open_run(run_id, stage, cursor_in, counters)

        result = IngestionResult(run_id=run_id, source_key=self.source.source_key,
                                 status="RUNNING", counters=counters)
        id_space = ID_SPACE_BY_SOURCE.get(self.source.source_key, "")
        lookup = {
            str(t.external_ids.get(id_space)): t
            for t in titles
            if t.external_ids.get(id_space)
        }
        counters.requested = len(lookup)

        if not lookup:
            result.status = "NOTHING_TO_DO"
            self._close_run(run_id, result, started)
            metrics.unmeasured(
                "source_requests",
                "ни у одного тайтла нет идентификатора нужного пространства",
                labels={"source": self.source.source_key},
            )
            return result

        try:
            fetched = self._fetch(list(lookup.keys()))
        except AdapterError as exc:
            counters.failed = len(lookup)
            if exc.code == "RATE_LIMITED":
                counters.rate_limited = 1
            result.status = "FAILED"
            result.error = f"{exc.code}: {exc.message}"
            self._close_run(run_id, result, started)
            metrics.record("source_errors", 1, labels={"source": self.source.source_key,
                                                       "code": exc.code})
            return result

        counters.retries = getattr(getattr(self.adapter, "client", None), "retries", 0) or 0
        counters.rate_limited = getattr(getattr(self.adapter, "client", None), "rate_limited", 0) or 0

        for key, fetch in fetched.items():
            title = lookup.get(key)
            if title is None:
                continue
            if not fetch.found and fetch.error:
                counters.failed += 1
                continue
            counters.received += 1
            outcome = self._ingest_one(title, fetch, run_id=run_id, id_space=id_space)
            self._apply_outcome(counters, result, outcome)

        result.status = "OK" if not counters.failed else "PARTIAL"
        result.cursor_out = max(lookup.keys(), key=_sort_key) if lookup else cursor_in
        result.next_checkpoint = result.cursor_out
        self._close_run(run_id, result, started)

        metrics.record("source_requests", getattr(getattr(self.adapter, "client", None), "requests", 0) or 0,
                       labels={"source": self.source.source_key})
        metrics.record("imported", counters.inserted, labels={"source": self.source.source_key})
        metrics.record("updated", counters.updated, labels={"source": self.source.source_key})
        metrics.record("unchanged", counters.unchanged, labels={"source": self.source.source_key})
        metrics.record("rejected", counters.rejected, labels={"source": self.source.source_key})
        metrics.record("pending_review", counters.pending_match, labels={"source": self.source.source_key})
        metrics.record("source_rate_limits", counters.rate_limited, labels={"source": self.source.source_key})
        elapsed_ms = (datetime.now(timezone.utc) - started).total_seconds() * 1000
        metrics.record("ingestion_latency_ms", elapsed_ms, labels={"source": self.source.source_key})
        return result

    # ------------------------------------------------------------------

    def _fetch(self, external_ids: list[str]) -> dict[str, SourceFetch]:
        """Выбрать путь получения: через MAL-кросволк, если адаптер умеет."""
        by_mal = getattr(self.adapter, "fetch_by_mal_ids", None)
        if by_mal is not None and ID_SPACE_BY_SOURCE.get(self.source.source_key) == "myanimelist":
            return by_mal(external_ids)
        return self.adapter.fetch_by_external_ids(external_ids)

    # ------------------------------------------------------------------

    def _ingest_one(
        self, title: CanonicalTitle, fetch: SourceFetch, *, run_id: str, id_space: str
    ) -> dict[str, Any]:
        decision = self._decide(title, fetch, id_space=id_space)
        if decision.status in (MatchStatus.PENDING, MatchStatus.CONFLICT):
            self._queue_review(title, decision, run_id=run_id)
            self._write_link(title, fetch, decision)
            return {"kind": "review", "decision": decision, "title": title, "fetch": fetch}
        if decision.status is MatchStatus.REJECTED:
            return {"kind": "rejected", "decision": decision, "title": title, "fetch": fetch}

        self._write_link(title, fetch, decision)
        normalized = normalize(fetch.raw_score, self.source.scale)
        stored = self._store_snapshot(title, fetch, normalized, run_id=run_id)
        return {
            "kind": stored,
            "decision": decision,
            "title": title,
            "fetch": fetch,
            "normalized": normalized,
        }

    def _decide(self, title: CanonicalTitle, fetch: SourceFetch, *, id_space: str) -> MatchDecision:
        """Проверить связь, полученную по точному идентификатору.

        Кандидат здесь ровно один: запрос шёл по нашему внешнему ID. Но
        «ответ пришёл» и «ответ про тот же тайтл» — разные утверждения, и
        второе проверяется фактами, а не фактом ответа.
        """
        from factory.unified_ratings.matching import MatchMethod

        our_id = str(title.external_ids.get(id_space) or "")
        their = TitleFacts(
            title_id=fetch.external_id,
            title_ru=fetch.titles.get("russian", "") or fetch.titles.get("ru", ""),
            title_original=(
                fetch.titles.get("romaji")
                or fetch.titles.get("canonical")
                or fetch.titles.get("name")
                or fetch.titles.get("main")
                or ""
            ),
            alt_titles=tuple(v for k, v in fetch.titles.items() if v and k not in ("russian", "ru")),
            year=fetch.year,
            kind=fetch.kind,
            episode_count=fetch.episodes,
            external_ids={id_space: our_id} if our_id else {},
        )
        problems = disagreements(title.facts(), their)
        if problems:
            return MatchDecision(
                status=MatchStatus.CONFLICT,
                method=MatchMethod.EXACT_EXTERNAL_ID,
                confidence=0.0,
                external_id=fetch.external_id,
                reasons=tuple(problems),
                detail=(
                    f"{id_space}={our_id} совпал, но факты расходятся: "
                    + ", ".join(r.value for r in problems)
                ),
                candidates=(
                    {
                        "external_id": fetch.external_id,
                        "titles": fetch.titles,
                        "year": fetch.year,
                        "kind": fetch.kind,
                        "episodes": fetch.episodes,
                    },
                ),
            )
        return MatchDecision(
            status=MatchStatus.EXACT,
            method=MatchMethod.EXACT_EXTERNAL_ID,
            confidence=1.0,
            external_id=fetch.external_id,
            detail=f"{id_space}={our_id}",
        )

    # ------------------------------------------------------------------

    def _write_link(
        self, title: CanonicalTitle, fetch: SourceFetch, decision: MatchDecision
    ) -> None:
        if self.dry_run:
            return
        now = utc_now()
        with self.store.write_tx() as conn:
            conn.execute(
                """INSERT INTO unified_source_links(
                       title_id, source_key, external_id, source_url, match_method,
                       confidence, status, verified_by, verified_at, evidence_json,
                       created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(title_id, source_key) DO UPDATE SET
                       external_id=excluded.external_id,
                       source_url=excluded.source_url,
                       match_method=excluded.match_method,
                       confidence=excluded.confidence,
                       status=excluded.status,
                       evidence_json=excluded.evidence_json,
                       updated_at=excluded.updated_at""",
                (
                    title.title_id,
                    self.source.source_key,
                    decision.external_id or fetch.external_id,
                    fetch.provenance_url,
                    decision.method.value,
                    decision.confidence,
                    decision.status.value,
                    "" if decision.status is not MatchStatus.EXACT else "automatic:exact_external_id",
                    now if decision.status is MatchStatus.EXACT else "",
                    json.dumps(decision.as_dict(), ensure_ascii=False),
                    now,
                    now,
                ),
            )

    def _queue_review(
        self, title: CanonicalTitle, decision: MatchDecision, *, run_id: str
    ) -> None:
        if self.dry_run:
            return
        reason = (
            decision.reasons[0].value
            if decision.reasons
            else QuarantineReason.INSUFFICIENT_CONFIDENCE.value
        )
        with self.store.write_tx() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO unified_review_queue(
                       title_id, source_key, reason_code, candidates_json, detail,
                       status, created_at, run_id)
                   VALUES (?,?,?,?,?,'PENDING',?,?)""",
                (
                    title.title_id,
                    self.source.source_key,
                    reason,
                    json.dumps(list(decision.candidates), ensure_ascii=False),
                    decision.detail,
                    utc_now(),
                    run_id,
                ),
            )

    # ------------------------------------------------------------------

    def _store_snapshot(
        self, title: CanonicalTitle, fetch: SourceFetch, normalized, *, run_id: str
    ) -> str:
        """Записать снимок. Неизменившееся содержимое новой версии не создаёт."""
        content_hash = fetch.content_hash()
        current = self.store.query_one(
            "SELECT * FROM unified_external_current WHERE title_id=? AND source_key=?",
            (title.title_id, self.source.source_key),
        )
        now = utc_now()

        if current is not None and current["content_hash"] == content_hash:
            if not self.dry_run:
                with self.store.write_tx() as conn:
                    conn.execute(
                        """UPDATE unified_external_current
                           SET last_checked_at=?, unchanged_streak=unchanged_streak+1
                           WHERE title_id=? AND source_key=?""",
                        (now, title.title_id, self.source.source_key),
                    )
            return "unchanged"

        validation_state = normalized.state.value
        rejection_reason = "" if normalized.state is ScoreState.OK else normalized.reason
        if self.dry_run:
            return "inserted" if current is None else "updated"

        provenance = {
            "source": self.source.source_key,
            "access_method": self.source.access_method.value,
            "legal_basis": self.source.legal_basis,
            "adapter_version": self.source.adapter_version,
            "module_version": MODULE_VERSION,
            "provenance_url": fetch.provenance_url,
            "source_updated_at": fetch.source_updated_at,
            "measures": self.source.scale.measures,
            "raw_field": self.source.scale.raw_field,
            "distribution": fetch.score_distribution,
        }
        with self.store.write_tx() as conn:
            cursor = conn.execute(
                """INSERT INTO unified_external_snapshots(
                       title_id, source_key, external_id, raw_score,
                       source_scale_min, source_scale_max, normalization_formula,
                       normalized_score, vote_count, user_count, source_rating_date,
                       fetched_at, source_updated_at, adapter_version,
                       raw_payload_sha256, content_hash, validation_state,
                       rejection_reason, provenance_json, prev_snapshot_id, run_id)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    title.title_id,
                    self.source.source_key,
                    fetch.external_id,
                    None if fetch.raw_score is None else str(fetch.raw_score),
                    str(self.source.scale.source_scale_min),
                    str(self.source.scale.source_scale_max),
                    self.source.scale.formula.value,
                    None if normalized.normalized is None else str(normalized.normalized),
                    fetch.vote_count,
                    fetch.user_count,
                    fetch.source_rating_date,
                    now,
                    fetch.source_updated_at,
                    self.source.adapter_version,
                    fetch.payload_sha256(),
                    content_hash,
                    validation_state,
                    rejection_reason,
                    json.dumps(provenance, ensure_ascii=False),
                    current["snapshot_id"] if current is not None else None,
                    run_id,
                ),
            )
            snapshot_id = cursor.lastrowid
            conn.execute(
                """INSERT INTO unified_external_current(
                       title_id, source_key, snapshot_id, raw_score, source_scale_max,
                       normalized_score, vote_count, user_count, content_hash,
                       validation_state, fetched_at, last_checked_at, unchanged_streak,
                       provenance_url, adapter_version)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0,?,?)
                   ON CONFLICT(title_id, source_key) DO UPDATE SET
                       snapshot_id=excluded.snapshot_id,
                       raw_score=excluded.raw_score,
                       source_scale_max=excluded.source_scale_max,
                       normalized_score=excluded.normalized_score,
                       vote_count=excluded.vote_count,
                       user_count=excluded.user_count,
                       content_hash=excluded.content_hash,
                       validation_state=excluded.validation_state,
                       fetched_at=excluded.fetched_at,
                       last_checked_at=excluded.last_checked_at,
                       unchanged_streak=0,
                       provenance_url=excluded.provenance_url,
                       adapter_version=excluded.adapter_version""",
                (
                    title.title_id,
                    self.source.source_key,
                    snapshot_id,
                    None if fetch.raw_score is None else str(fetch.raw_score),
                    str(self.source.scale.source_scale_max),
                    None if normalized.normalized is None else str(normalized.normalized),
                    fetch.vote_count,
                    fetch.user_count,
                    content_hash,
                    validation_state,
                    now,
                    now,
                    fetch.provenance_url,
                    self.source.adapter_version,
                ),
            )
        return "inserted" if current is None else "updated"

    # ------------------------------------------------------------------

    def _apply_outcome(
        self, counters: RunCounters, result: IngestionResult, outcome: dict[str, Any]
    ) -> None:
        kind = outcome["kind"]
        decision: MatchDecision = outcome["decision"]
        title: CanonicalTitle = outcome["title"]
        fetch: SourceFetch = outcome["fetch"]

        if kind == "review":
            counters.pending_match += 1
            result.review_items.append(
                {
                    "title_id": title.title_id,
                    "title_ru": title.title_ru,
                    "source": self.source.source_key,
                    "external_id": fetch.external_id,
                    **decision.as_dict(),
                }
            )
            return
        if kind == "rejected":
            counters.rejected += 1
            return

        counters.exact_match += 1
        if kind == "inserted":
            counters.inserted += 1
        elif kind == "updated":
            counters.updated += 1
        elif kind == "unchanged":
            counters.unchanged += 1

        normalized = outcome.get("normalized")
        if normalized is not None and normalized.state is not ScoreState.OK:
            counters.rejected += 1
        if len(result.samples) < 25:
            result.samples.append(
                {
                    "title_id": title.title_id,
                    "title_ru": title.title_ru,
                    "year": title.release_year,
                    "source": self.source.source_key,
                    "external_id": fetch.external_id,
                    "raw_score": None if fetch.raw_score is None else str(fetch.raw_score),
                    "source_scale": self.source.scale.scale_label,
                    "formula": self.source.scale.formula.value,
                    "normalized": None if normalized is None else normalized.as_dict().get("normalized"),
                    "display": None if normalized is None else normalized.display(),
                    "vote_count": fetch.vote_count,
                    "user_count": fetch.user_count,
                    "state": None if normalized is None else normalized.state.value,
                    "outcome": kind,
                    "provenance_url": fetch.provenance_url,
                }
            )

    # ------------------------------------------------------------------
    # журнал прогонов
    # ------------------------------------------------------------------

    def _open_run(self, run_id: str, stage: str, cursor_in: str, counters: RunCounters) -> None:
        with self.store.write_tx() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO unified_import_runs(
                       run_id, source_key, stage, started_at, status, dry_run,
                       cursor_in, requested, code_version, adapter_version)
                   VALUES (?,?,?,?,'RUNNING',?,?,?,?,?)""",
                (
                    run_id,
                    self.source.source_key,
                    stage,
                    utc_now(),
                    1 if self.dry_run else 0,
                    cursor_in,
                    counters.requested,
                    MODULE_VERSION,
                    self.source.adapter_version,
                ),
            )

    def _close_run(self, run_id: str, result: IngestionResult, started: datetime) -> None:
        c = result.counters
        with self.store.write_tx() as conn:
            conn.execute(
                """UPDATE unified_import_runs SET
                       finished_at=?, status=?, cursor_out=?, next_checkpoint=?,
                       requested=?, received=?, exact_match=?, pending_match=?, rejected=?,
                       inserted=?, updated=?, unchanged=?, failed=?, rate_limited=?,
                       retries=?, notes=?
                   WHERE run_id=?""",
                (
                    utc_now(),
                    result.status,
                    result.cursor_out,
                    result.next_checkpoint,
                    c.requested,
                    c.received,
                    c.exact_match,
                    c.pending_match,
                    c.rejected,
                    c.inserted,
                    c.updated,
                    c.unchanged,
                    c.failed,
                    c.rate_limited,
                    c.retries,
                    result.error,
                    run_id,
                ),
            )


def _sort_key(value: str) -> tuple[int, str]:
    return (0, value.zfill(12)) if value.isdigit() else (1, value)
