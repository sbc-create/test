"""IMDb и Кинопоиск — только из договорного фида поставщика.

Адаптер не ходит в сеть и не может: обращение к imdb.com и kinopoisk.ru
запрещено решением владельца от 2026-09-06. Значения читаются из того же
каталожного снимка, который уже загружен для сайта, и сохраняются в
единой модели с provenance «фид поставщика», а не «IMDb».

Разница существенна для отчётности: мы показываем не оценку, которую сами
измерили у IMDb, а число, которое нам передал поставщик по договору. Если
поставщик задержал обновление, устареет именно наше значение, и по
``source_updated_at`` это видно.
"""

from __future__ import annotations

from typing import Any

from factory.unified_ratings import ADAPTER_VERSION_PROVIDER_FEED
from factory.unified_ratings.adapters.base import Capabilities, HealthState, SourceFetch

SOURCE_IMDB = "provider_feed_imdb"
SOURCE_KINOPOISK = "provider_feed_kinopoisk"

_FIELD = {
    SOURCE_IMDB: "imdb_rating",
    SOURCE_KINOPOISK: "kinopoisk_rating",
}
_ID_FIELD = {
    SOURCE_IMDB: "imdb",
    SOURCE_KINOPOISK: "kinopoisk",
}


class ProviderFeedAdapter:
    """Читает оценки из уже загруженных элементов каталога.

    ``items_by_external_id`` — наш каталог, а не ответ внешней площадки,
    поэтому сетевого клиента у адаптера нет вовсе.
    """

    adapter_version = ADAPTER_VERSION_PROVIDER_FEED

    def __init__(self, source_key: str, items_by_external_id: dict[str, dict[str, Any]]) -> None:
        if source_key not in _FIELD:
            raise ValueError(f"источник фида не поддерживается: {source_key}")
        self.source_key = source_key
        self.items = items_by_external_id

    def capabilities(self) -> Capabilities:
        return Capabilities(
            source_key=self.source_key,
            supports_batch=True,
            max_batch_size=len(self.items) or 1,
            supports_vote_count=False,
            supports_user_count=False,
            supports_distribution=False,
            supports_source_side_incremental=True,
            incremental_mode="обновление наступает при обновлении каталожного снимка",
            external_id_space=_ID_FIELD[self.source_key],
            requires_credential=False,
        )

    def fetch_by_external_ids(self, external_ids: list[str]) -> dict[str, SourceFetch]:
        field = _FIELD[self.source_key]
        id_field = _ID_FIELD[self.source_key]
        out: dict[str, SourceFetch] = {}
        for raw in [str(i).strip() for i in external_ids if str(i).strip()]:
            item = self.items.get(raw)
            if item is None:
                out[raw] = SourceFetch(
                    source_key=self.source_key,
                    external_id=raw,
                    found=False,
                    error="NOT_IN_FEED",
                )
                continue
            value = item.get(field)
            external_ids_map = item.get("external_ids") or {}
            out[raw] = SourceFetch(
                source_key=self.source_key,
                external_id=str(external_ids_map.get(id_field) or raw),
                # Идентификатор объявлен самим фидом в external_ids: это и
                # есть подтверждение того, к какому тайтлу относится оценка.
                crosswalk_ids={
                    k: str(v) for k, v in external_ids_map.items() if v not in (None, "")
                },
                found=value not in (None, ""),
                raw_score=value,
                vote_count=None,
                source_updated_at=str(item.get("updated_at") or ""),
                provenance_url="",
                titles={"ru": str(item.get("name") or "")},
                year=item.get("year") if isinstance(item.get("year"), int) else None,
                kind=str(item.get("type") or ""),
                raw_payload={
                    field: value,
                    "external_ids": external_ids_map,
                    "updated_at": item.get("updated_at"),
                    "_delivery": "договорный фид поставщика; прямой сбор с площадки запрещён",
                },
            )
        return out

    def health(self) -> dict[str, Any]:
        measured = sum(1 for i in self.items.values() if i.get(_FIELD[self.source_key]) not in (None, ""))
        return {
            "source_key": self.source_key,
            "state": HealthState.HEALTHY if self.items else HealthState.UNMEASURED,
            "feed_items": len(self.items),
            "items_with_value": measured,
            "network_calls_made": 0,
        }
