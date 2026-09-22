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
    #: источник ответил «такого тайтла у меня нет» — обычный исход
    not_found: int = 0
    #: источник не ответил или ответил ошибкой — это отказ
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
        write_batch_size: int = 250,
    ) -> None:
        self.store = store
        self.source = source
        self.adapter = adapter
        self.dry_run = dry_run
        self.write_batch_size = max(1, write_batch_size)
        self.registry = TitleRegistry(store)
        #: текущие значения по произведениям пакета; читаются одним
        #: запросом вместо одного запроса на произведение
        self._current: dict[tuple[str, str], Any] = {}
        self._claimed_in_batch: dict[str, str] = {}

    def _load_current_cache(self, title_ids: list[str]) -> None:
        self._current = {}
        # Заявки, сделанные внутри текущей транзакции: запрос к БД их ещё
        # не видит, а конфликт двух произведений одного пакета за один
        # внешний идентификатор так же реален, как и конфликт с уже
        # записанным.
        self._claimed_in_batch = {}
        for start in range(0, len(title_ids), 400):
            chunk = title_ids[start : start + 400]
            marks = ",".join("?" * len(chunk))
            for row in self.store.query(
                f"SELECT * FROM unified_external_current"
                f" WHERE source_key=? AND title_id IN ({marks})",
                (self.source.source_key, *chunk),
            ):
                self._current[(row["title_id"], row["source_key"])] = row

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
        # Один внешний идентификатор может быть у нескольких наших
        # произведений. Словарь «идентификатор → произведение» терял бы
        # всех, кроме последнего: ни снимка, ни записи в очереди, ни следа
        # в журнале — самая тихая из возможных потерь данных.
        lookup: dict[str, list[CanonicalTitle]] = {}
        for title in titles:
            external = title.external_ids.get(id_space)
            if external:
                lookup.setdefault(str(external), []).append(title)
        counters.requested = sum(len(v) for v in lookup.values())

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

        usable: list[tuple[CanonicalTitle, SourceFetch]] = []
        for key, fetch in fetched.items():
            claimants = lookup.get(key) or []
            for title in claimants:
                if not fetch.found and fetch.error:
                    # Отсутствие тайтла у источника — не отказ источника.
                    # Пока эти исходы считались вместе, один не найденный
                    # тайтл ронял ворота всего источника.
                    if fetch.error.startswith("NOT_FOUND") or fetch.error == "NOT_IN_FEED":
                        counters.not_found += 1
                    else:
                        counters.failed += 1
                    continue
                counters.received += 1
                usable.append((title, fetch))

        # Запись идёт пакетами в одной транзакции на пакет. Отдельная
        # транзакция на произведение означала бы для полного каталога
        # девяносто тысяч блокировок записи на базе, к которой подключён
        # живой gateway, — и медленно, и недружелюбно к соседям.
        for start in range(0, len(usable), self.write_batch_size):
            chunk = usable[start : start + self.write_batch_size]
            self._load_current_cache([t.title_id for t, _ in chunk])
            if self.dry_run:
                for title, fetch in chunk:
                    self._apply_outcome(
                        counters,
                        result,
                        self._ingest_one(None, title, fetch, run_id=run_id, id_space=id_space),
                    )
                continue
            with self.store.write_tx() as conn:
                outcomes = [
                    self._ingest_one(conn, title, fetch, run_id=run_id, id_space=id_space)
                    for title, fetch in chunk
                ]
            for outcome in outcomes:
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
        self, conn, title: CanonicalTitle, fetch: SourceFetch, *, run_id: str, id_space: str
    ) -> dict[str, Any]:
        decision = self._decide(title, fetch, id_space=id_space)
        if decision.status is MatchStatus.EXACT:
            decision = self._check_exclusive_claim(title, fetch, decision)
        if decision.status in (MatchStatus.PENDING, MatchStatus.CONFLICT):
            self._queue_review(conn, title, decision, run_id=run_id)
            self._write_link(conn, title, fetch, decision)
            return {"kind": "review", "decision": decision, "title": title, "fetch": fetch}
        if decision.status is MatchStatus.REJECTED:
            return {"kind": "rejected", "decision": decision, "title": title, "fetch": fetch}

        self._write_link(conn, title, fetch, decision)
        normalized = normalize(fetch.raw_score, self.source.scale)
        stored = self._store_snapshot(conn, title, fetch, normalized, run_id=run_id)
        return {
            "kind": stored,
            "decision": decision,
            "title": title,
            "fetch": fetch,
            "normalized": normalized,
        }

    def _check_exclusive_claim(
        self, title: CanonicalTitle, fetch: SourceFetch, decision: MatchDecision
    ) -> MatchDecision:
        """Один внешний идентификатор — одно произведение.

        В каталоге встречаются две записи с одним и тем же MAL ID: части
        одного релиза, дубль или ошибка импорта. Принять обе значило бы
        показать одну и ту же внешнюю оценку как оценку двух разных
        произведений. Схема это запрещает уникальным индексом, но падать
        на нём нельзя: конфликт двух каталожных записей — обычное
        состояние данных, и разбирать его должен человек, а не аварийный
        останов посреди прохода.
        """
        from factory.unified_ratings.matching import MatchMethod

        external_id = decision.external_id or fetch.external_id
        holder = self._claimed_in_batch.get(external_id)
        if holder is None:
            row = self.store.query_one(
                "SELECT title_id FROM unified_source_links"
                " WHERE source_key=? AND external_id=? AND status IN ('exact','reviewed')",
                (self.source.source_key, external_id),
            )
            holder = row["title_id"] if row is not None else None
        if holder is None or holder == title.title_id:
            self._claimed_in_batch[external_id] = title.title_id
            return decision
        row = {"title_id": holder}
        return MatchDecision(
            status=MatchStatus.CONFLICT,
            method=MatchMethod.EXACT_EXTERNAL_ID,
            confidence=0.0,
            external_id=external_id,
            reasons=(QuarantineReason.EXTERNAL_ID_CONFLICT,),
            detail=(
                f"{self.source.source_key}:{external_id} уже закреплён за "
                f"{row['title_id']}; два наших произведения претендуют на одну "
                "запись источника"
            ),
            candidates=(
                {"external_id": external_id, "held_by_title_id": row["title_id"]},
                {"external_id": external_id, "claimed_by_title_id": title.title_id},
            ),
        )

    def _decide(self, title: CanonicalTitle, fetch: SourceFetch, *, id_space: str) -> MatchDecision:
        """Проверить связь, полученную по точному идентификатору.

        Кандидат здесь ровно один: запрос шёл по нашему внешнему ID. Но
        «ответ пришёл» и «ответ про тот же тайтл» — разные утверждения, и
        второе проверяется фактами, а не фактом ответа.
        """
        from factory.unified_ratings.matching import MatchMethod

        our_id = str(title.external_ids.get(id_space) or "")
        # Идентификаторы «их» стороны берутся из того, что объявил сам
        # источник. Подставить сюда наш же идентификатор означало бы
        # сравнить его с собой: такая проверка не падает никогда и потому
        # не проверяет ничего.
        their_ids = {k: str(v) for k, v in fetch.crosswalk_ids.items() if v}
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
            external_ids=their_ids,
        )
        problems = disagreements(title.facts(), their)
        unconfirmed = bool(our_id) and id_space not in their_ids
        if unconfirmed:
            # Источник не подтвердил, про какой тайтл ответ. Это не отказ,
            # но и не точное сопоставление: связь принимается только когда
            # идентификатор подтверждён обеими сторонами.
            problems.append(QuarantineReason.INSUFFICIENT_CONFIDENCE)
        if problems:
            detail = (
                f"источник не подтвердил {id_space}={our_id} в своём ответе"
                if unconfirmed and len(problems) == 1
                else (
                    f"{id_space}={our_id} совпал, но факты расходятся: "
                    + ", ".join(r.value for r in problems)
                )
            )
            return MatchDecision(
                status=MatchStatus.CONFLICT,
                method=MatchMethod.EXACT_EXTERNAL_ID,
                confidence=0.0,
                external_id=fetch.external_id,
                reasons=tuple(problems),
                detail=detail,
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
        self, conn, title: CanonicalTitle, fetch: SourceFetch, decision: MatchDecision
    ) -> None:
        if self.dry_run or conn is None:
            return
        now = utc_now()
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
        self, conn, title: CanonicalTitle, decision: MatchDecision, *, run_id: str
    ) -> None:
        if self.dry_run or conn is None:
            return
        reason = (
            decision.reasons[0].value
            if decision.reasons
            else QuarantineReason.INSUFFICIENT_CONFIDENCE.value
        )
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
        self, conn, title: CanonicalTitle, fetch: SourceFetch, normalized, *, run_id: str
    ) -> str:
        """Записать снимок. Неизменившееся содержимое новой версии не создаёт."""
        content_hash = fetch.content_hash()
        current = self._current.get((title.title_id, self.source.source_key))
        now = utc_now()

        if current is not None and current["content_hash"] == content_hash:
            if not self.dry_run and conn is not None:
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
                       inserted=?, updated=?, unchanged=?, not_found=?, failed=?,
                       rate_limited=?, retries=?, notes=?
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
                    c.not_found,
                    c.failed,
                    c.rate_limited,
                    c.retries,
                    result.error,
                    run_id,
                ),
            )


def _sort_key(value: str) -> tuple[int, str]:
    return (0, value.zfill(12)) if value.isdigit() else (1, value)
