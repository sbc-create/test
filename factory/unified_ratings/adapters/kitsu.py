"""Адаптер Kitsu — официальный публичный JSON:API, без ключа. Резервный источник.

Контракт подтверждён живыми ответами 2026-09-21 (Этап A):

* ``GET /api/edge/anime/{id}`` — ``attributes.averageRating`` строкой,
  шкала 0–100 (``"82.27"`` для id=1);
* ``attributes.ratingFrequencies`` — ключи 2..20; это оценка 1–10 с шагом
  0.5, умноженная на два, а сумма значений — число оценивших;
* ``attributes.userCount`` — число пользователей с тайтлом в библиотеке.
  Оно заметно больше числа оценивших и числом голосов не является;
* ``GET /api/edge/mappings?filter[externalSite]=myanimelist/anime&
  filter[externalId]=<csv>&include=item`` — точное сопоставление с нашим
  каталогом по MAL ID, пакетом, вместе с самими тайтлами.

Лимит источник в заголовках не объявляет, поэтому cap выбран заведомо
низким: неизвестный лимит — повод идти медленнее, а не быстрее.
"""

from __future__ import annotations

import urllib.parse
from typing import Any

from factory.ratings.adapters.base import AdapterError
from factory.unified_ratings import ADAPTER_VERSION_KITSU
from factory.unified_ratings.adapters.base import Capabilities, HealthState, SourceFetch
from factory.unified_ratings.http_client import HttpClient, build_client
from factory.unified_ratings.sources import KITSU

SOURCE_KEY = "kitsu"
BASE = "https://kitsu.io/api/edge"
MAL_SITE = "myanimelist/anime"
MAX_BATCH = 20

_HEADERS = {"Accept": "application/vnd.api+json"}


class KitsuAdapter:
    source_key = SOURCE_KEY
    adapter_version = ADAPTER_VERSION_KITSU

    def __init__(self, client: HttpClient | None = None, *, base: str = BASE) -> None:
        self.base = base.rstrip("/")
        self.client = client or build_client(KITSU)

    # ------------------------------------------------------------------

    def capabilities(self) -> Capabilities:
        return Capabilities(
            source_key=SOURCE_KEY,
            supports_batch=True,
            max_batch_size=MAX_BATCH,
            supports_vote_count=True,
            supports_user_count=True,
            supports_distribution=True,
            supports_source_side_incremental=False,
            incremental_mode=(
                "локальный checkpoint по нашей очереди тайтлов; сортировка по "
                "updatedAt источником поддерживается, но охватывает весь "
                "каталог Kitsu, а не наш"
            ),
            external_id_space="kitsu_anime_id; сопоставление через mappings/myanimelist",
            requires_credential=False,
        )

    # ------------------------------------------------------------------

    def _get(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        url = f"{self.base}{path}?{urllib.parse.urlencode(params)}"
        resp = self.client.request(url, headers=_HEADERS)
        data = resp.json()
        if not isinstance(data, dict):
            raise AdapterError("SCHEMA_DRIFT", "ответ Kitsu не объект", hard_circuit=True)
        if data.get("errors"):
            messages = "; ".join(
                str(e.get("detail") or e.get("title") or e)
                for e in data["errors"]
                if isinstance(e, dict)
            )
            raise AdapterError("API_ERROR", messages, retryable=False)
        return data

    # ------------------------------------------------------------------

    def fetch_by_external_ids(self, external_ids: list[str]) -> dict[str, SourceFetch]:
        """Пакетная выборка по собственным идентификаторам Kitsu."""
        requested = [str(i).strip() for i in external_ids if str(i).strip()]
        out: dict[str, SourceFetch] = {}
        for start in range(0, len(requested), MAX_BATCH):
            chunk = requested[start : start + MAX_BATCH]
            data = self._get(
                "/anime",
                {"filter[id]": ",".join(chunk), "page[limit]": str(len(chunk))},
            )
            rows = data.get("data")
            if not isinstance(rows, list):
                raise AdapterError("SCHEMA_DRIFT", "data не список", hard_circuit=True)
            by_id = {str(r.get("id")): r for r in rows if isinstance(r, dict)}
            for raw in chunk:
                row = by_id.get(raw)
                out[raw] = (
                    _to_fetch(row, requested_key=raw)
                    if row
                    else SourceFetch(
                        source_key=SOURCE_KEY, external_id=raw, found=False, error="NOT_FOUND"
                    )
                )
        return out

    def fetch_by_mal_ids(self, mal_ids: list[str]) -> dict[str, SourceFetch]:
        """Точное сопоставление по MAL ID через официальные mappings.

        Ключи результата — запрошенные MAL ID. Kitsu возвращает найденные
        соответствия в своём порядке и не упоминает отсутствующие, поэтому
        сопоставление по позиции дало бы сдвиг на первом же пропуске.
        """
        requested = [str(i).strip() for i in mal_ids if str(i).strip()]
        out: dict[str, SourceFetch] = {}
        for start in range(0, len(requested), MAX_BATCH):
            chunk = requested[start : start + MAX_BATCH]
            data = self._get(
                "/mappings",
                {
                    "filter[externalSite]": MAL_SITE,
                    "filter[externalId]": ",".join(chunk),
                    "include": "item",
                    "page[limit]": str(min(MAX_BATCH, len(chunk))),
                },
            )
            mappings = data.get("data") or []
            included = data.get("included") or []
            items_by_id = {
                str(i.get("id")): i
                for i in included
                if isinstance(i, dict) and i.get("type") == "anime"
            }
            mal_to_item: dict[str, dict[str, Any]] = {}
            for mapping in mappings:
                if not isinstance(mapping, dict):
                    continue
                attrs = mapping.get("attributes") or {}
                if attrs.get("externalSite") != MAL_SITE:
                    continue
                mal_id = str(attrs.get("externalId") or "")
                ref = ((mapping.get("relationships") or {}).get("item") or {}).get("data") or {}
                item = items_by_id.get(str(ref.get("id")))
                if mal_id and item is not None:
                    mal_to_item[mal_id] = item

            for raw in chunk:
                item = mal_to_item.get(raw)
                if item is None:
                    out[raw] = SourceFetch(
                        source_key=SOURCE_KEY,
                        external_id=raw,
                        found=False,
                        error="NOT_FOUND: нет соответствия myanimelist/anime",
                    )
                    continue
                fetch = _to_fetch(item, requested_key=str(item.get("id")))
                out[raw] = fetch
        return out

    # ------------------------------------------------------------------

    def health(self) -> dict[str, Any]:
        try:
            data = self._get("/anime", {"filter[id]": "1", "page[limit]": "1"})
        except AdapterError as exc:
            return {
                "source_key": SOURCE_KEY,
                "state": HealthState.BLOCKED if exc.hard_circuit else HealthState.DEGRADED,
                "error": str(exc),
            }
        rows = data.get("data") or []
        return {
            "source_key": SOURCE_KEY,
            "state": HealthState.HEALTHY if rows else HealthState.DEGRADED,
            "usage": self.client.usage(),
        }


def vote_count_from_frequencies(freq: Any) -> int | None:
    """Сумма ``ratingFrequencies``. Значения приходят строками."""
    if not isinstance(freq, dict) or not freq:
        return None
    total = 0
    for value in freq.values():
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            count = value
        elif isinstance(value, str) and value.strip().isdigit():
            count = int(value)
        else:
            return None
        if count < 0:
            return None
        total += count
    return total


def distribution_map(freq: Any) -> dict[str, int] | None:
    """Распределение в терминах источника: ключи 2..20 (шкала 1–10 × 2)."""
    if not isinstance(freq, dict) or not freq:
        return None
    out: dict[str, int] = {}
    for key, value in freq.items():
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            out[str(key)] = value
        elif isinstance(value, str) and value.strip().isdigit():
            out[str(key)] = int(value)
        else:
            return None
    return out or None


def _year(start_date: Any) -> int | None:
    if isinstance(start_date, str) and len(start_date) >= 4 and start_date[:4].isdigit():
        return int(start_date[:4])
    return None


def _to_fetch(row: dict[str, Any], *, requested_key: str) -> SourceFetch:
    attrs = row.get("attributes") or {}
    freq = attrs.get("ratingFrequencies")
    titles = attrs.get("titles") or {}
    abbreviated = attrs.get("abbreviatedTitles")
    payload = {
        "id": row.get("id"),
        "canonicalTitle": attrs.get("canonicalTitle"),
        "titles": titles,
        "abbreviatedTitles": abbreviated if isinstance(abbreviated, list) else [],
        "subtype": attrs.get("subtype"),
        "status": attrs.get("status"),
        "episodeCount": attrs.get("episodeCount"),
        "startDate": attrs.get("startDate"),
        "averageRating": attrs.get("averageRating"),
        "ratingFrequencies": freq,
        "userCount": attrs.get("userCount"),
        "updatedAt": attrs.get("updatedAt"),
        "slug": attrs.get("slug"),
        # Ранги — место в списке, а не оценка; хранятся помеченными.
        "_ratingRank_is_not_a_rating": attrs.get("ratingRank"),
        "_popularityRank_is_not_a_rating": attrs.get("popularityRank"),
        "_favoritesCount_is_not_a_rating": attrs.get("favoritesCount"),
    }
    user_count = attrs.get("userCount")
    episodes = attrs.get("episodeCount")
    return SourceFetch(
        source_key=SOURCE_KEY,
        external_id=str(row.get("id") or requested_key),
        found=attrs.get("averageRating") not in (None, ""),
        raw_score=attrs.get("averageRating"),
        vote_count=vote_count_from_frequencies(freq),
        user_count=user_count if isinstance(user_count, int) and not isinstance(user_count, bool) else None,
        score_distribution=distribution_map(freq),
        source_rating_date=str(attrs.get("startDate") or ""),
        source_updated_at=str(attrs.get("updatedAt") or ""),
        provenance_url=f"https://kitsu.io/anime/{attrs.get('slug') or row.get('id')}",
        titles={
            "canonical": str(attrs.get("canonicalTitle") or ""),
            "en": str(titles.get("en") or ""),
            "en_jp": str(titles.get("en_jp") or ""),
            "ja_jp": str(titles.get("ja_jp") or ""),
        },
        year=_year(attrs.get("startDate")),
        kind=str(attrs.get("subtype") or ""),
        episodes=episodes if isinstance(episodes, int) and not isinstance(episodes, bool) else None,
        raw_payload=payload,
    )
