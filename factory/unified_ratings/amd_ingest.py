"""Сбор AMD Online: перечисление, сопоставление, запись.

Отдельный модуль, потому что у этого источника нет общего с нами
идентификатора: сопоставление идёт по названию, году и типу, а не по
ключу, и правила приёма здесь строже, чем у остальных источников.

Порядок обхода — сначала онгоинги с первой страницы раздела, затем
остальной каталог из sitemap, начиная с новых. Пагинация раздела закрыта
robots.txt сайта и не обходится; что раздел ею не исчерпывается,
записано в отчёт, а не замолчано.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from factory.ratings.adapters.base import AdapterError
from factory.unified_ratings.adapters.amd_online import AmdOnlineAdapter
from factory.unified_ratings.adapters.base import SourceFetch
from factory.unified_ratings.matching import (
    MatchStatus,
    TitleFacts,
    match_by_facts,
    normalize_title,
)
from factory.unified_ratings.scale import ScoreState, normalize
from factory.unified_ratings.sources import AMD_ONLINE
from factory.unified_ratings.store import UnifiedStore
from factory.unified_ratings.titles import TitleRegistry, utc_now

SOURCE_KEY = "amd_online"


@dataclass
class AmdRunCounters:
    section_pages_fetched: int = 0
    pagination_pages_advertised: int = 0
    ongoing_urls_found: int = 0
    sitemap_urls_found: int = 0
    title_pages_fetched: int = 0
    with_main_score: int = 0
    with_vote_count: int = 0
    dimensions_found: int = 0
    exact_matches: int = 0
    sent_to_review: int = 0
    unmatched: int = 0
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    failed: int = 0
    stopped_reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class TitleIndex:
    """Индекс каталога по нормализованному названию.

    Строится один раз: пятьдесят тысяч тайтлов на каждую карточку AMD —
    это часы вместо минут.
    """

    by_name: dict[str, list[TitleFacts]] = field(default_factory=dict)

    @classmethod
    def build(cls, registry: TitleRegistry) -> TitleIndex:
        index = cls()
        rows = registry.store.query(
            "SELECT title_id, title_ru, title_original, alt_titles_json,"
            " release_year, content_kind, episode_count, external_ids_json FROM unified_titles"
        )
        for row in rows:
            facts = TitleFacts(
                title_id=row["title_id"],
                title_ru=row["title_ru"],
                title_original=row["title_original"],
                alt_titles=tuple(json.loads(row["alt_titles_json"] or "[]")),
                year=row["release_year"],
                kind=row["content_kind"],
                episode_count=row["episode_count"],
                external_ids=json.loads(row["external_ids_json"] or "{}"),
            )
            for name in facts.all_titles:
                key = normalize_title(name)
                if key:
                    index.by_name.setdefault(key, []).append(facts)
        return index

    def candidates_for(self, fetch: SourceFetch) -> list[TitleFacts]:
        seen: dict[str, TitleFacts] = {}
        for name in fetch.titles.values():
            for facts in self.by_name.get(normalize_title(name), []):
                seen[facts.title_id] = facts
        return list(seen.values())


def _facts_from_fetch(fetch: SourceFetch) -> TitleFacts:
    payload = fetch.raw_payload
    # Тип у AMD на карточке не подписан отдельным полем, поэтому он
    # остаётся неизвестным, а не угадывается: неизвестный тип не
    # конфликтует ни с чем и проверку типа просто не проводит.
    return TitleFacts(
        title_id=fetch.external_id,
        title_ru=payload.get("title_ru", ""),
        title_original=payload.get("title_original", ""),
        year=fetch.year,
        kind="",
    )


class AmdIngestor:
    def __init__(
        self,
        store: UnifiedStore,
        adapter: AmdOnlineAdapter | None = None,
        *,
        dry_run: bool = True,
    ) -> None:
        self.store = store
        self.adapter = adapter or AmdOnlineAdapter()
        self.dry_run = dry_run
        self.registry = TitleRegistry(store)

    # ------------------------------------------------------------------

    def discover(self, *, include_catalog: bool = True) -> dict[str, Any]:
        section = self.adapter.discover_ongoing_urls()
        urls = list(section["first_page_urls"])
        sitemap_urls: list[str] = []
        if include_catalog:
            sitemap_urls = self.adapter.discover_title_urls()
            known = set(urls)
            urls.extend(u for u in sitemap_urls if u not in known)
        return {
            "section": section,
            "sitemap_urls": len(sitemap_urls),
            "ordered_urls": urls,
        }

    # ------------------------------------------------------------------

    def run(
        self,
        urls: list[str],
        *,
        index: TitleIndex,
        counters: AmdRunCounters | None = None,
        progress_every: int = 25,
        on_progress: Any = None,
    ) -> AmdRunCounters:
        counters = counters or AmdRunCounters()
        for position, url in enumerate(urls, start=1):
            try:
                html_text = self.adapter.fetch_page(url, use_cache=False)
                fetch = self.adapter.parse_title(url, html_text)
            except AdapterError as exc:
                if exc.hard_circuit:
                    counters.stopped_reason = f"{exc.code}: {exc.message}"
                    break
                counters.failed += 1
                continue

            counters.title_pages_fetched += 1
            if fetch.raw_score is not None:
                counters.with_main_score += 1
            if fetch.vote_count is not None:
                counters.with_vote_count += 1
            counters.dimensions_found += len(fetch.raw_payload.get("components") or {})

            decision = match_by_facts(_facts_from_fetch(fetch), index.candidates_for(fetch))
            if decision.status is MatchStatus.REVIEWED:
                counters.exact_matches += 1
                outcome = self._store(fetch, decision.external_id, decision)
                setattr(counters, outcome, getattr(counters, outcome) + 1)
            elif decision.status is MatchStatus.PENDING:
                counters.sent_to_review += 1
                self._queue_review(fetch, decision)
            else:
                counters.unmatched += 1

            if on_progress and position % progress_every == 0:
                on_progress(position, len(urls), counters)
        return counters

    # ------------------------------------------------------------------

    def _store(self, fetch: SourceFetch, title_id: str, decision) -> str:
        """Записать значение. Возвращает ``inserted``/``updated``/``unchanged``."""
        normalized = normalize(fetch.raw_score, AMD_ONLINE.scale)
        content_hash = fetch.content_hash()
        current = self.store.query_one(
            "SELECT * FROM unified_external_current WHERE title_id=? AND source_key=?",
            (title_id, SOURCE_KEY),
        )
        if current is not None and current["content_hash"] == content_hash:
            if not self.dry_run:
                with self.store.write_tx() as conn:
                    conn.execute(
                        "UPDATE unified_external_current SET last_checked_at=?,"
                        " unchanged_streak=unchanged_streak+1"
                        " WHERE title_id=? AND source_key=?",
                        (utc_now(), title_id, SOURCE_KEY),
                    )
            return "unchanged"
        if self.dry_run:
            return "inserted" if current is None else "updated"

        now = utc_now()
        provenance = {
            "source": SOURCE_KEY,
            "access_method": AMD_ONLINE.access_method.value,
            "access_label": "AMD_ONLINE_PUBLIC_HTML",
            "legal_basis": AMD_ONLINE.legal_basis,
            "adapter_version": self.adapter.adapter_version,
            "provenance_url": fetch.provenance_url,
            "html_sha256": fetch.raw_payload.get("html_sha256"),
            "match_basis": decision.detail,
            "match_confidence": decision.confidence,
            "raw_score": fetch.raw_score,
            "raw_votes": fetch.vote_count,
        }
        with self.store.write_tx() as conn:
            cursor = conn.execute(
                """INSERT INTO unified_external_snapshots(
                       title_id, source_key, external_id, raw_score, source_scale_min,
                       source_scale_max, normalization_formula, normalized_score, vote_count,
                       user_count, source_rating_date, fetched_at, source_updated_at,
                       adapter_version, raw_payload_sha256, content_hash, validation_state,
                       rejection_reason, provenance_json, prev_snapshot_id, run_id)
                   VALUES (?,?,?,?,?,?,?,?,?,NULL,'',?,'',?,?,?,?,?,?,?,'amd')""",
                (
                    title_id, SOURCE_KEY, fetch.external_id,
                    None if fetch.raw_score is None else str(fetch.raw_score),
                    str(AMD_ONLINE.scale.source_scale_min),
                    str(AMD_ONLINE.scale.source_scale_max),
                    AMD_ONLINE.scale.formula.value,
                    None if normalized.normalized is None else str(normalized.normalized),
                    fetch.vote_count, now, self.adapter.adapter_version,
                    fetch.payload_sha256(), content_hash, normalized.state.value,
                    "" if normalized.state is ScoreState.OK else normalized.reason,
                    json.dumps(provenance, ensure_ascii=False),
                    current["snapshot_id"] if current is not None else None,
                ),
            )
            snapshot_id = cursor.lastrowid
            conn.execute(
                """INSERT INTO unified_external_current(
                       title_id, source_key, snapshot_id, raw_score, source_scale_max,
                       normalized_score, vote_count, user_count, content_hash,
                       validation_state, fetched_at, last_checked_at, unchanged_streak,
                       provenance_url, adapter_version)
                   VALUES (?,?,?,?,?,?,?,NULL,?,?,?,?,0,?,?)
                   ON CONFLICT(title_id, source_key) DO UPDATE SET
                       snapshot_id=excluded.snapshot_id, raw_score=excluded.raw_score,
                       normalized_score=excluded.normalized_score,
                       vote_count=excluded.vote_count, content_hash=excluded.content_hash,
                       validation_state=excluded.validation_state,
                       fetched_at=excluded.fetched_at, last_checked_at=excluded.last_checked_at,
                       unchanged_streak=0, provenance_url=excluded.provenance_url,
                       adapter_version=excluded.adapter_version""",
                (
                    title_id, SOURCE_KEY, snapshot_id,
                    None if fetch.raw_score is None else str(fetch.raw_score),
                    str(AMD_ONLINE.scale.source_scale_max),
                    None if normalized.normalized is None else str(normalized.normalized),
                    fetch.vote_count, content_hash, normalized.state.value,
                    now, now, fetch.provenance_url, self.adapter.adapter_version,
                ),
            )
            conn.execute(
                """INSERT INTO unified_source_links(
                       title_id, source_key, external_id, source_url, match_method,
                       confidence, status, verified_by, verified_at, evidence_json,
                       created_at, updated_at)
                   VALUES (?,?,?,?,?,?,'reviewed','automatic:title_year_kind',?,?,?,?)
                   ON CONFLICT(title_id, source_key) DO UPDATE SET
                       external_id=excluded.external_id, confidence=excluded.confidence,
                       status=excluded.status, updated_at=excluded.updated_at""",
                (
                    title_id, SOURCE_KEY, fetch.external_id, fetch.provenance_url,
                    decision.method.value, decision.confidence, now,
                    json.dumps(decision.as_dict(), ensure_ascii=False), now, now,
                ),
            )
            # Покритериальные оценки — отдельными измерениями. В общую
            # оценку произведения они не входят и в сводную не попадают.
            for area, comp in (fetch.raw_payload.get("components") or {}).items():
                comp_norm = normalize(comp["raw"], AMD_ONLINE.scale)
                conn.execute(
                    """INSERT INTO unified_source_dimensions(
                           title_id, source_key, dimension, label, raw_value,
                           source_scale_max, normalized_value, validation_state,
                           fetched_at, adapter_version)
                       VALUES (?,?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(title_id, source_key, dimension) DO UPDATE SET
                           raw_value=excluded.raw_value,
                           normalized_value=excluded.normalized_value,
                           validation_state=excluded.validation_state,
                           fetched_at=excluded.fetched_at""",
                    (
                        title_id, SOURCE_KEY, area, comp["label"], comp["raw"],
                        str(AMD_ONLINE.scale.source_scale_max),
                        None if comp_norm.normalized is None else str(comp_norm.normalized),
                        comp_norm.state.value, now, self.adapter.adapter_version,
                    ),
                )
        return "inserted" if current is None else "updated"

    def _queue_review(self, fetch: SourceFetch, decision) -> None:
        if self.dry_run:
            return
        reason = decision.reasons[0].value if decision.reasons else "INSUFFICIENT_CONFIDENCE"
        with self.store.write_tx() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO unified_review_queue(
                       title_id, source_key, reason_code, candidates_json, detail,
                       status, created_at, run_id)
                   VALUES (?,?,?,?,?,'PENDING',?,'amd')""",
                (
                    f"amd:{fetch.external_id}", SOURCE_KEY, reason,
                    json.dumps(list(decision.candidates), ensure_ascii=False),
                    f"{fetch.raw_payload.get('title_ru','')} — {decision.detail}",
                    utc_now(),
                ),
            )


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
