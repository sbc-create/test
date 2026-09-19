"""AnimeMedia source stub — UNVERIFIED_DISABLED.

Наши домены animedia.icu / animedia.space НЕ являются внешним источником
рейтингов. Импорт оценок с собственных витрин запрещён (циклическая provenance).

До включения нужны: canonical origin, владелец, API/feed, право хранения,
атрибуция, rate limits, стабильные external IDs, vote-count contract.
"""

from __future__ import annotations

from typing import Any

from factory.ratings import ADAPTER_VERSION_ANIMEMEDIA
from factory.ratings.adapters.base import AdapterError, FetchResult

SOURCE_KEY = "animemedia"
SOURCE_STATE = "UNVERIFIED_DISABLED"


class AnimeMediaAdapter:
    source_key = SOURCE_KEY
    adapter_version = ADAPTER_VERSION_ANIMEMEDIA
    state = SOURCE_STATE

    def fetch_by_ids(self, external_ids: list[str]) -> dict[str, FetchResult]:
        raise AdapterError(
            "SOURCE_UNVERIFIED_DISABLED",
            "AnimeMedia source is UNVERIFIED_DISABLED: canonical origin, "
            "ownership, API/feed, attribution and rate limits are not confirmed. "
            "Our animedia.icu/space sites must not be used as rating sources.",
            retryable=False,
            hard_circuit=True,
        )

    def check_schema(self) -> dict[str, Any]:
        return {
            "adapter_version": self.adapter_version,
            "state": SOURCE_STATE,
            "enabled": False,
            "blocker": (
                "exact canonical origin, data owner, documented API/feed or owned "
                "upstream, storage rights, attribution, rate limits, stable external "
                "IDs and vote-count contract are required before enablement"
            ),
            "forbidden": [
                "guess provider/domain",
                "bypass Cloudflare/CAPTCHA",
                "substitute MAL/AniList by guess",
                "use our own sites as external source",
                "HTML scrape without owner permission",
                "copy reference visual scores",
            ],
        }
