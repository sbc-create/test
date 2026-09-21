"""Реестр канонических тайтлов и их связь с площадками.

Канонический тайтл описывает то, что знаем мы: каталожный снимок и
существующие сопоставления. Названия, годы и типы из внешних источников
сюда не переносятся — источник оценок не является источником каталога, и
запись «год взят у AniList» через месяц неотличима от «год наш».
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from factory.unified_ratings.matching import TitleFacts
from factory.unified_ratings.store import UnifiedStore

CATALOG_PROVIDER = "nova"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class CanonicalTitle:
    title_id: str
    content_kind: str = "UNKNOWN"
    title_ru: str = ""
    title_original: str = ""
    alt_titles: list[str] = field(default_factory=list)
    release_year: int | None = None
    season_number: int | None = None
    episode_count: int | None = None
    external_ids: dict[str, str] = field(default_factory=dict)
    catalog_source: str = ""
    catalog_revision: str = ""

    def facts(self) -> TitleFacts:
        return TitleFacts(
            title_id=self.title_id,
            title_ru=self.title_ru,
            title_original=self.title_original,
            alt_titles=tuple(self.alt_titles),
            year=self.release_year,
            kind=self.content_kind,
            season_number=self.season_number,
            episode_count=self.episode_count,
            external_ids=dict(self.external_ids),
        )


def from_catalog_item(item: dict[str, Any], *, provider: str = CATALOG_PROVIDER) -> CanonicalTitle | None:
    external_id = str(item.get("external_id") or item.get("id") or "").strip()
    if not external_id:
        return None
    raw_ids = item.get("external_ids") or {}
    external_ids = {str(k): str(v) for k, v in raw_ids.items() if v not in (None, "")}
    # Каталог встречается в двух записях одного и того же пространства.
    if "myanimelist" not in external_ids and external_ids.get("mal"):
        external_ids["myanimelist"] = external_ids["mal"]

    year = item.get("year")
    episodes = item.get("episodes_count")
    kind = str(item.get("type") or "").strip().lower()
    if not kind:
        kind = "tv" if item.get("is_series") else "UNKNOWN"

    return CanonicalTitle(
        title_id=f"{provider}:{external_id}",
        content_kind=kind,
        title_ru=str(item.get("name") or ""),
        title_original=str(item.get("original_name") or ""),
        alt_titles=[str(t) for t in (item.get("alt_names") or []) if t],
        release_year=year if isinstance(year, int) and not isinstance(year, bool) else None,
        season_number=None,
        episode_count=(
            episodes if isinstance(episodes, int) and not isinstance(episodes, bool) and episodes > 0 else None
        ),
        external_ids=external_ids,
        catalog_source=provider,
        catalog_revision=str(item.get("updated_at") or ""),
    )


def load_catalog_items(path: Path | str) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    items = data.get("items") if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise ValueError(f"каталог {path} не содержит списка items")
    return items


class TitleRegistry:
    def __init__(self, store: UnifiedStore) -> None:
        self.store = store

    # ------------------------------------------------------------------

    def upsert(self, title: CanonicalTitle) -> str:
        """Записать канонический тайтл. Возвращает 'inserted'|'updated'|'unchanged'."""
        now = utc_now()
        existing = self.store.query_one(
            "SELECT * FROM unified_titles WHERE title_id = ?", (title.title_id,)
        )
        payload = _payload(title)
        if existing is None:
            with self.store.write_tx() as conn:
                conn.execute(
                    """INSERT INTO unified_titles(
                           title_id, content_kind, title_ru, title_original, alt_titles_json,
                           release_year, season_number, episode_count, external_ids_json,
                           catalog_source, catalog_revision, created_at, updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (title.title_id, *payload, now, now),
                )
            return "inserted"

        current = (
            existing["content_kind"],
            existing["title_ru"],
            existing["title_original"],
            existing["alt_titles_json"],
            existing["release_year"],
            existing["season_number"],
            existing["episode_count"],
            existing["external_ids_json"],
            existing["catalog_source"],
            existing["catalog_revision"],
        )
        if current == payload:
            return "unchanged"
        with self.store.write_tx() as conn:
            conn.execute(
                """UPDATE unified_titles SET
                       content_kind=?, title_ru=?, title_original=?, alt_titles_json=?,
                       release_year=?, season_number=?, episode_count=?, external_ids_json=?,
                       catalog_source=?, catalog_revision=?, updated_at=?
                   WHERE title_id=?""",
                (*payload, now, title.title_id),
            )
        return "updated"

    def upsert_many(self, titles: list[CanonicalTitle], *, batch_size: int = 500) -> dict[str, int]:
        """Пакетная запись каталога.

        Отдельная транзакция на тайтл превращает загрузку каталога из
        пятидесяти тысяч записей в пятьдесят тысяч блокировок записи на
        базе, к которой подключён работающий gateway. Пакет держит
        блокировку коротко и отпускает её между пакетами.
        """
        counts = {"inserted": 0, "updated": 0, "unchanged": 0}
        now = utc_now()
        for start in range(0, len(titles), batch_size):
            chunk = titles[start : start + batch_size]
            existing = self._existing_rows([t.title_id for t in chunk])
            with self.store.write_tx() as conn:
                for title in chunk:
                    payload = _payload(title)
                    current = existing.get(title.title_id)
                    if current is None:
                        conn.execute(
                            """INSERT INTO unified_titles(
                                   title_id, content_kind, title_ru, title_original,
                                   alt_titles_json, release_year, season_number, episode_count,
                                   external_ids_json, catalog_source, catalog_revision,
                                   created_at, updated_at)
                               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (title.title_id, *payload, now, now),
                        )
                        counts["inserted"] += 1
                    elif current == payload:
                        counts["unchanged"] += 1
                    else:
                        conn.execute(
                            """UPDATE unified_titles SET
                                   content_kind=?, title_ru=?, title_original=?,
                                   alt_titles_json=?, release_year=?, season_number=?,
                                   episode_count=?, external_ids_json=?, catalog_source=?,
                                   catalog_revision=?, updated_at=?
                               WHERE title_id=?""",
                            (*payload, now, title.title_id),
                        )
                        counts["updated"] += 1
        return counts

    def _existing_rows(self, title_ids: list[str]) -> dict[str, tuple]:
        if not title_ids:
            return {}
        placeholders = ",".join("?" * len(title_ids))
        rows = self.store.query(
            f"SELECT * FROM unified_titles WHERE title_id IN ({placeholders})", tuple(title_ids)
        )
        return {
            row["title_id"]: (
                row["content_kind"],
                row["title_ru"],
                row["title_original"],
                row["alt_titles_json"],
                row["release_year"],
                row["season_number"],
                row["episode_count"],
                row["external_ids_json"],
                row["catalog_source"],
                row["catalog_revision"],
            )
            for row in rows
        }

    # ------------------------------------------------------------------

    def get(self, title_id: str) -> CanonicalTitle | None:
        row = self.store.query_one("SELECT * FROM unified_titles WHERE title_id = ?", (title_id,))
        return None if row is None else _row_to_title(row)

    def exists(self, title_id: str) -> bool:
        return self.store.query_one(
            "SELECT 1 FROM unified_titles WHERE title_id = ?", (title_id,)
        ) is not None

    def with_external_id(self, id_space: str, limit: int | None = None) -> list[CanonicalTitle]:
        """Тайтлы, у которых есть идентификатор нужного пространства."""
        rows = self.store.query(
            "SELECT * FROM unified_titles WHERE json_extract(external_ids_json, ?) IS NOT NULL"
            " ORDER BY title_id",
            (f"$.{id_space}",),
        )
        titles = [_row_to_title(r) for r in rows]
        return titles if limit is None else titles[:limit]

    # ------------------------------------------------------------------

    def map_tenant_subject(
        self, *, tenant_id: str, subject_id: str, title_id: str, profile_id: str = ""
    ) -> None:
        """Связать subject площадки с каноническим тайтлом.

        Голос приходит с сайта с ``subject_id``; ``title_id`` берётся из
        этой таблицы, а не из запроса. Иначе клиент, подставив чужой
        ``title_id``, проголосовал бы за тайтл другой площадки.
        """
        if not self.exists(title_id):
            raise KeyError(f"канонический тайтл не найден: {title_id}")
        with self.store.write_tx() as conn:
            conn.execute(
                """INSERT INTO unified_title_tenant_map(
                       tenant_id, subject_id, title_id, profile_id, created_at)
                   VALUES (?,?,?,?,?)
                   ON CONFLICT(tenant_id, subject_id) DO UPDATE SET
                       title_id=excluded.title_id, profile_id=excluded.profile_id""",
                (tenant_id, subject_id, title_id, profile_id, utc_now()),
            )

    def resolve_subject(self, tenant_id: str, subject_id: str) -> str | None:
        row = self.store.query_one(
            "SELECT title_id FROM unified_title_tenant_map WHERE tenant_id=? AND subject_id=?",
            (tenant_id, subject_id),
        )
        return None if row is None else row["title_id"]

    def tenants_for(self, title_id: str) -> list[str]:
        return [
            r["tenant_id"]
            for r in self.store.query(
                "SELECT DISTINCT tenant_id FROM unified_title_tenant_map WHERE title_id=?"
                " ORDER BY tenant_id",
                (title_id,),
            )
        ]


def _payload(title: CanonicalTitle) -> tuple:
    """Поля тайтла в порядке колонок. Один порядок на запись и на сравнение."""
    return (
        title.content_kind,
        title.title_ru,
        title.title_original,
        json.dumps(title.alt_titles, ensure_ascii=False),
        title.release_year,
        title.season_number,
        title.episode_count,
        json.dumps(title.external_ids, ensure_ascii=False, sort_keys=True),
        title.catalog_source,
        title.catalog_revision,
    )


def _row_to_title(row: Any) -> CanonicalTitle:
    return CanonicalTitle(
        title_id=row["title_id"],
        content_kind=row["content_kind"],
        title_ru=row["title_ru"],
        title_original=row["title_original"],
        alt_titles=json.loads(row["alt_titles_json"] or "[]"),
        release_year=row["release_year"],
        season_number=row["season_number"],
        episode_count=row["episode_count"],
        external_ids=json.loads(row["external_ids_json"] or "{}"),
        catalog_source=row["catalog_source"],
        catalog_revision=row["catalog_revision"],
    )
