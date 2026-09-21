"""Адаптер AniList — официальный публичный GraphQL, без ключа.

Контракт подтверждён живым ответом 2026-09-21 (Этап A):

* endpoint ``POST https://graphql.anilist.co``;
* ``Media.averageScore`` — взвешенная средняя, шкала 0–100 (86 для id=1);
* ``Media.stats.scoreDistribution`` — ключи 10..100 шагом 10, ``amount``
  по каждому; сумма ``amount`` и есть число оценивших;
* ``Media.idMal`` — ключ сопоставления с нашим каталогом;
* сервер сам объявляет лимит заголовком ``X-RateLimit-Limit: 30``.

``popularity`` и ``favourites`` считают пользователей списка, а не голоса,
и в оценку не превращаются ни при каких условиях: у популярного тайтла
эти числа больше числа оценок в разы, и подстановка одного вместо другого
даёт правдоподобный, но неверный «вес» рейтинга.
"""

from __future__ import annotations

import json
from typing import Any

from factory.ratings.adapters.base import AdapterError
from factory.unified_ratings import ADAPTER_VERSION_ANILIST
from factory.unified_ratings.adapters.base import Capabilities, HealthState, SourceFetch
from factory.unified_ratings.http_client import HttpClient, build_client
from factory.unified_ratings.sources import ANILIST

SOURCE_KEY = "anilist"
ENDPOINT = "https://graphql.anilist.co"

MEDIA_FIELDS = """
  id
  idMal
  title { romaji english native }
  synonyms
  format
  status
  episodes
  season
  seasonYear
  startDate { year month day }
  averageScore
  meanScore
  popularity
  favourites
  updatedAt
  siteUrl
  stats { scoreDistribution { score amount } }
"""

#: Пакетный запрос по нашим внешним ID (AniList id).
BATCH_BY_ID_QUERY = (
    "query ($ids: [Int], $perPage: Int) { "
    "Page(page: 1, perPage: $perPage) { "
    "pageInfo { total perPage currentPage hasNextPage } "
    "media(id_in: $ids, type: ANIME) {" + MEDIA_FIELDS + "} } }"
)

#: Пакетный запрос по MAL ID — основной путь сопоставления с каталогом.
BATCH_BY_MAL_QUERY = (
    "query ($malIds: [Int], $perPage: Int) { "
    "Page(page: 1, perPage: $perPage) { "
    "pageInfo { total perPage currentPage hasNextPage } "
    "media(idMal_in: $malIds, type: ANIME) {" + MEDIA_FIELDS + "} } }"
)

MAX_BATCH = 25


class AniListAdapter:
    source_key = SOURCE_KEY
    adapter_version = ADAPTER_VERSION_ANILIST

    def __init__(self, client: HttpClient | None = None, *, endpoint: str = ENDPOINT) -> None:
        self.endpoint = endpoint
        self.client = client or build_client(ANILIST)
        self.last_rate_limit: dict[str, str] = {}

    # ------------------------------------------------------------------

    def capabilities(self) -> Capabilities:
        return Capabilities(
            source_key=SOURCE_KEY,
            supports_batch=True,
            max_batch_size=MAX_BATCH,
            supports_vote_count=True,
            supports_user_count=False,
            supports_distribution=True,
            supports_source_side_incremental=False,
            incremental_mode=(
                "локальный checkpoint по нашей очереди тайтлов; источник не "
                "отдаёт «что изменилось с момента X» для произвольного набора"
            ),
            external_id_space="anilist_media_id; сопоставление через idMal",
            requires_credential=False,
        )

    # ------------------------------------------------------------------

    def _post(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
        resp = self.client.request(
            self.endpoint,
            method="POST",
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            body=body,
        )
        self.last_rate_limit = {
            k: v for k, v in resp.headers.items() if k.lower().startswith("x-ratelimit")
        }
        data = resp.json()
        if not isinstance(data, dict):
            raise AdapterError("SCHEMA_DRIFT", "ответ AniList не объект", hard_circuit=True)
        if data.get("errors"):
            messages = "; ".join(
                str(e.get("message") or e) for e in data["errors"] if isinstance(e, dict)
            )
            raise AdapterError("GRAPHQL_ERROR", messages, retryable=False)
        return data

    # ------------------------------------------------------------------

    def fetch_by_external_ids(self, external_ids: list[str]) -> dict[str, SourceFetch]:
        return self._fetch(external_ids, by_mal=False)

    def fetch_by_mal_ids(self, mal_ids: list[str]) -> dict[str, SourceFetch]:
        """Сопоставление по MAL ID — точный внешний идентификатор.

        Ключи результата — запрошенные MAL ID, чтобы вызывающий код не
        сопоставлял ответы по порядку: AniList возвращает найденные медиа в
        своём порядке и молча пропускает отсутствующие.
        """
        return self._fetch(mal_ids, by_mal=True)

    def _fetch(self, ids: list[str], *, by_mal: bool) -> dict[str, SourceFetch]:
        requested = [str(i).strip() for i in ids if str(i).strip()]
        out: dict[str, SourceFetch] = {}
        for start in range(0, len(requested), MAX_BATCH):
            chunk = requested[start : start + MAX_BATCH]
            numeric: list[int] = []
            for raw in chunk:
                try:
                    numeric.append(int(raw))
                except ValueError:
                    out[raw] = SourceFetch(
                        source_key=SOURCE_KEY,
                        external_id=raw,
                        found=False,
                        error="INVALID_EXTERNAL_ID: AniList использует целые идентификаторы",
                    )
            if not numeric:
                continue
            query = BATCH_BY_MAL_QUERY if by_mal else BATCH_BY_ID_QUERY
            variables = (
                {"malIds": numeric, "perPage": len(numeric)}
                if by_mal
                else {"ids": numeric, "perPage": len(numeric)}
            )
            data = self._post(query, variables)
            page = (data.get("data") or {}).get("Page") or {}
            media = page.get("media")
            if not isinstance(media, list):
                raise AdapterError("SCHEMA_DRIFT", "Page.media не список", hard_circuit=True)

            by_key: dict[str, dict[str, Any]] = {}
            for row in media:
                if not isinstance(row, dict):
                    continue
                key = str(row.get("idMal") if by_mal else row.get("id") or "")
                if key and key != "None":
                    by_key[key] = row

            for raw in chunk:
                row = by_key.get(raw)
                if row is None:
                    out[raw] = SourceFetch(
                        source_key=SOURCE_KEY,
                        external_id=raw,
                        found=False,
                        error="NOT_FOUND",
                    )
                    continue
                out[raw] = _to_fetch(row, requested_key=raw)
        return out

    # ------------------------------------------------------------------

    def health(self) -> dict[str, Any]:
        try:
            data = self._post(
                "query { Media(id: 1, type: ANIME) { id averageScore } }", {}
            )
        except AdapterError as exc:
            return {
                "source_key": SOURCE_KEY,
                "state": HealthState.BLOCKED if exc.hard_circuit else HealthState.DEGRADED,
                "error": str(exc),
                "rate_limit_headers": self.last_rate_limit,
            }
        media = (data.get("data") or {}).get("Media") or {}
        return {
            "source_key": SOURCE_KEY,
            "state": HealthState.HEALTHY if media.get("id") else HealthState.DEGRADED,
            "probe_id": media.get("id"),
            "rate_limit_headers": self.last_rate_limit,
            "usage": self.client.usage(),
        }


def vote_count_from_distribution(dist: Any) -> int | None:
    """Сумма ``amount``. Любая нецелая запись делает сумму неизвестной.

    Частичная сумма хуже отсутствия: она выглядит как настоящее число
    голосов и тихо занижает вес источника в любом сводном показателе.
    """
    if not isinstance(dist, list) or not dist:
        return None
    total = 0
    for row in dist:
        if not isinstance(row, dict):
            return None
        amount = row.get("amount")
        if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
            return None
        total += amount
    return total


def distribution_map(dist: Any) -> dict[str, int] | None:
    """Распределение в терминах шкалы источника (0–100, шаг 10)."""
    if not isinstance(dist, list) or not dist:
        return None
    out: dict[str, int] = {}
    for row in dist:
        if not isinstance(row, dict):
            return None
        score, amount = row.get("score"), row.get("amount")
        if not isinstance(score, int) or isinstance(score, bool):
            return None
        if not isinstance(amount, int) or isinstance(amount, bool):
            return None
        out[str(score)] = amount
    return out or None


def _start_date(row: dict[str, Any]) -> str:
    start = row.get("startDate") or {}
    year, month, day = start.get("year"), start.get("month"), start.get("day")
    if not year:
        return ""
    if month and day:
        return f"{year:04d}-{month:02d}-{day:02d}"
    if month:
        return f"{year:04d}-{month:02d}"
    return f"{year:04d}"


def _to_fetch(row: dict[str, Any], *, requested_key: str) -> SourceFetch:
    stats = (row.get("stats") or {}).get("scoreDistribution")
    titles = row.get("title") or {}
    synonyms = row.get("synonyms")
    payload = {
        "id": row.get("id"),
        "idMal": row.get("idMal"),
        "title": titles,
        "synonyms": synonyms if isinstance(synonyms, list) else [],
        "format": row.get("format"),
        "status": row.get("status"),
        "episodes": row.get("episodes"),
        "season": row.get("season"),
        "seasonYear": row.get("seasonYear"),
        "startDate": row.get("startDate"),
        "averageScore": row.get("averageScore"),
        "meanScore": row.get("meanScore"),
        "updatedAt": row.get("updatedAt"),
        "siteUrl": row.get("siteUrl"),
        "stats": {"scoreDistribution": stats},
        # Явные пометки, чтобы поле не переехало в оценку при доработке.
        "_popularity_is_not_a_rating": row.get("popularity"),
        "_favourites_is_not_a_rating": row.get("favourites"),
    }
    updated = row.get("updatedAt")
    id_mal = row.get("idMal")
    return SourceFetch(
        source_key=SOURCE_KEY,
        external_id=requested_key,
        crosswalk_ids={"myanimelist": str(id_mal)} if id_mal not in (None, "") else {},
        found=row.get("averageScore") is not None,
        raw_score=row.get("averageScore"),
        vote_count=vote_count_from_distribution(stats),
        user_count=None,
        score_distribution=distribution_map(stats),
        source_rating_date=_start_date(row),
        source_updated_at=str(updated) if updated not in (None, "") else "",
        provenance_url=str(row.get("siteUrl") or ""),
        titles={
            "romaji": str(titles.get("romaji") or ""),
            "english": str(titles.get("english") or ""),
            "native": str(titles.get("native") or ""),
        },
        year=row.get("seasonYear") if isinstance(row.get("seasonYear"), int) else None,
        kind=str(row.get("format") or ""),
        episodes=row.get("episodes") if isinstance(row.get("episodes"), int) else None,
        raw_payload=payload,
    )
