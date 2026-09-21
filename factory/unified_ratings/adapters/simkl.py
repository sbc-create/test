"""Адаптер Simkl — официальный API, требующий client_id приложения.

Состояние на 2026-09-21: ключа нет. Живой Этап-A probe вернул
``HTTP 412 {"error":"client_id_failed"}``, и ни secret storage, ни
``inventory/`` такого ключа не содержат.

Адаптер написан целиком и заработает от одного внешнего действия — выдачи
``secret_ref: simkl_client_id``. До этого он не выполняет ни одного сетевого
запроса: без ключа запрос к источнику — это либо мусорный трафик, либо
попытка обойти требование источника, и первое неотличимо от второго со
стороны Simkl. Поэтому ``fetch_by_external_ids`` падает с
``CREDENTIAL_REQUIRED`` до обращения к сети, а не после отказа.

Контракт шкалы намеренно помечен ``verified=False``: пока живой ответ не
получен, «Simkl отдаёт 0–10» — это память, а не проверенный факт, и
нормализация вернёт CONTRACT_UNVERIFIED вместо числа.
"""

from __future__ import annotations

import os
import urllib.parse
from pathlib import Path
from typing import Any

from factory.ratings.adapters.base import AdapterError
from factory.ratings.secrets import load_secret_file
from factory.unified_ratings import ADAPTER_VERSION_SIMKL
from factory.unified_ratings.adapters.base import Capabilities, HealthState, SourceFetch
from factory.unified_ratings.http_client import HttpClient, build_client
from factory.unified_ratings.sources import SIMKL

SOURCE_KEY = "simkl"
BASE = "https://api.simkl.com"
MAX_BATCH = 1  # источник отдаёт по одному тайтлу на запрос

CREDENTIAL_NAME = "simkl_client_id"


def resolve_client_id() -> str | None:
    """Ключ из штатного secret storage. Значение никуда не логируется."""
    cred_dir = os.environ.get("CREDENTIALS_DIRECTORY")
    if cred_dir:
        path = Path(cred_dir) / os.environ.get("SIMKL_CLIENT_ID_CREDENTIAL", CREDENTIAL_NAME)
        if path.is_file():
            return load_secret_file(path)
    env_file = os.environ.get("SIMKL_CLIENT_ID_FILE")
    if env_file:
        return load_secret_file(env_file)
    return os.environ.get("SIMKL_CLIENT_ID") or None


class SimklAdapter:
    source_key = SOURCE_KEY
    adapter_version = ADAPTER_VERSION_SIMKL

    def __init__(
        self,
        client: HttpClient | None = None,
        *,
        base: str = BASE,
        client_id: str | None = None,
    ) -> None:
        self.base = base.rstrip("/")
        self.client = client or build_client(SIMKL)
        self._client_id = client_id if client_id is not None else resolve_client_id()

    @property
    def has_credential(self) -> bool:
        return bool(self._client_id)

    def capabilities(self) -> Capabilities:
        return Capabilities(
            source_key=SOURCE_KEY,
            supports_batch=False,
            max_batch_size=MAX_BATCH,
            supports_vote_count=True,
            supports_user_count=False,
            supports_distribution=False,
            supports_source_side_incremental=True,
            incremental_mode=(
                "источник документирует выборку изменений по дате; проверить "
                "это без ключа нельзя, поэтому режим не подтверждён"
            ),
            external_id_space="simkl_id; сопоставление через mal/anilist id",
            requires_credential=True,
        )

    def _require_credential(self) -> str:
        if not self._client_id:
            raise AdapterError(
                "CREDENTIAL_REQUIRED",
                (
                    "Simkl требует client_id приложения; в secret storage его нет. "
                    "Источник остаётся BLOCKED_SECRET: подставлять чужой или "
                    "выдуманный client_id и разбирать публичные страницы вместо "
                    "API запрещено."
                ),
                hard_circuit=True,
            )
        return self._client_id

    def _get(self, path: str, params: dict[str, str]) -> Any:
        client_id = self._require_credential()
        url = f"{self.base}{path}?{urllib.parse.urlencode(params)}"
        resp = self.client.request(
            url,
            headers={
                "Accept": "application/json",
                "simkl-api-key": client_id,
            },
        )
        return resp.json()

    def fetch_by_external_ids(self, external_ids: list[str]) -> dict[str, SourceFetch]:
        self._require_credential()
        out: dict[str, SourceFetch] = {}
        for raw in [str(i).strip() for i in external_ids if str(i).strip()]:
            data = self._get(f"/anime/{urllib.parse.quote(raw)}", {"extended": "full"})
            out[raw] = _to_fetch(data if isinstance(data, dict) else {}, requested_key=raw)
        return out

    def health(self) -> dict[str, Any]:
        if not self.has_credential:
            return {
                "source_key": SOURCE_KEY,
                "state": HealthState.BLOCKED,
                "reason": "CREDENTIAL_MISSING",
                "blocker": SIMKL.blocker,
                "network_calls_made": 0,
                "unblock_action": "выдать secret_ref simkl_client_id",
            }
        try:
            self._get("/anime/1", {"extended": "full"})
        except AdapterError as exc:
            return {"source_key": SOURCE_KEY, "state": HealthState.DEGRADED, "error": str(exc)}
        return {"source_key": SOURCE_KEY, "state": HealthState.HEALTHY}


def _to_fetch(data: dict[str, Any], *, requested_key: str) -> SourceFetch:
    ratings = (data.get("ratings") or {}).get("simkl") or {}
    ids = data.get("ids") or {}
    return SourceFetch(
        source_key=SOURCE_KEY,
        external_id=str(ids.get("simkl") or requested_key),
        found=ratings.get("rating") not in (None, ""),
        raw_score=ratings.get("rating"),
        vote_count=ratings.get("votes") if isinstance(ratings.get("votes"), int) else None,
        source_rating_date=str(data.get("first_aired") or ""),
        provenance_url=str(data.get("url") or ""),
        titles={"main": str(data.get("title") or "")},
        year=data.get("year") if isinstance(data.get("year"), int) else None,
        kind=str(data.get("type") or ""),
        raw_payload={"ids": ids, "ratings": data.get("ratings"), "title": data.get("title")},
    )
