"""Shikimori GraphQL adapter — официальный API, не REST v1/v2.

Контракт (подтверждён live probe 2026-09-19):

* endpoint: POST https://shikimori.io/api/graphql
* ``animes(ids: String, limit: Int)`` — ids = CSV строка, batch до 50
* поля: id, malId, name, russian, score, scoresStats{score,count}, updatedAt, url
* ``score`` — оценка Shikimori (НЕ оценка MAL)
* ``malId`` — идентификатор crosswalk, не оценка
* vote_count = sum(scoresStats.count)
* лимиты API: 5 rps / 90 rpm; наш cap: RATINGS_MAX_RPS / RATINGS_MAX_REQUESTS_PER_MINUTE
"""

from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.request
from typing import Any, Callable

from factory.ratings import ADAPTER_VERSION_SHIKIMORI
from factory.ratings.adapters.base import AdapterError, FetchResult
from factory.ratings.rate_limit import RateLimiter
from factory.ratings.secrets import redact_headers, resolve_shikimori_token

SOURCE_KEY = "shikimori"

ANIME_FIELDS = (
    "id malId name russian score "
    "scoresStats { score count } "
    "updatedAt url"
)

BATCH_QUERY = (
    "query ($ids: String, $limit: Int) { "
    "animes(ids: $ids, limit: $limit) { " + ANIME_FIELDS + " } }"
)

REQUIRED_FIELDS = {
    "id",
    "malId",
    "name",
    "russian",
    "score",
    "scoresStats",
    "updatedAt",
    "url",
}


def vote_count_from_stats(stats: list | None) -> int | None:
    if not stats:
        return None
    total = 0
    for row in stats:
        if not isinstance(row, dict):
            continue
        c = row.get("count")
        if isinstance(c, bool) or not isinstance(c, int):
            return None
        total += c
    return total


def distribution_from_stats(stats: list | None) -> dict[str, int] | None:
    if not stats:
        return None
    out: dict[str, int] = {}
    for row in stats:
        if not isinstance(row, dict):
            continue
        s, c = row.get("score"), row.get("count")
        if not isinstance(s, int) or not isinstance(c, int) or isinstance(c, bool):
            return None
        out[str(s)] = c
    return out or None


def normalize_score(raw: Any) -> float | None:
    """NULL/0/пустое → None. Ноль у Shikimori = «ещё не оценили», не оценка 0.0."""
    if raw is None or isinstance(raw, bool):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    if value > 10:
        return None
    return value


class ShikimoriGraphQLAdapter:
    source_key = SOURCE_KEY
    adapter_version = ADAPTER_VERSION_SHIKIMORI

    def __init__(
        self,
        *,
        url: str = "https://shikimori.io/api/graphql",
        user_agent: str = "site-factory-ratings/1.0 (+ratings-ingestion)",
        rate_limiter: RateLimiter | None = None,
        batch_size: int = 50,
        timeout: float = 30.0,
        max_retries: int = 3,
        opener: Callable | None = None,
        token: str | None = None,
        clock: Callable[[], float] | None = None,
        sleeper: Callable[[float], None] | None = None,
    ) -> None:
        self.url = url
        self.user_agent = user_agent
        self.rate_limiter = rate_limiter or RateLimiter(max_rps=2.0, max_per_minute=60)
        self.batch_size = min(50, max(1, batch_size))
        self.timeout = timeout
        self.max_retries = max_retries
        self.opener = opener
        self._token = token if token is not None else resolve_shikimori_token()
        self.clock = clock or time.monotonic
        self.sleeper = sleeper or time.sleep
        self.last_request_headers_redacted: dict[str, str] = {}

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": self.user_agent,
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        self.last_request_headers_redacted = redact_headers(headers)
        return headers

    def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        payload = json.dumps(body).encode("utf-8")
        attempt = 0
        while True:
            self.rate_limiter.wait()
            req = urllib.request.Request(
                self.url, data=payload, headers=self._headers(), method="POST"
            )
            open_fn = self.opener or (
                lambda r, timeout: urllib.request.urlopen(r, timeout=timeout)  # noqa: S310
            )
            try:
                with open_fn(req, self.timeout) as resp:
                    raw = resp.read()
                data = json.loads(raw.decode("utf-8"))
                if not isinstance(data, dict):
                    raise AdapterError("SCHEMA_DRIFT", "ответ не объект", hard_circuit=True)
                if data.get("errors"):
                    msg = "; ".join(
                        str(e.get("message") or e) for e in data["errors"] if isinstance(e, dict)
                    )
                    raise AdapterError("GRAPHQL_ERROR", msg, retryable=False)
                return data
            except AdapterError:
                raise
            except urllib.error.HTTPError as exc:
                attempt += 1
                if exc.code in (401, 403):
                    raise AdapterError(
                        "AUTH_REJECTED",
                        f"HTTP {exc.code}",
                        hard_circuit=True,
                    ) from exc
                if exc.code == 429:
                    retry_after = None
                    ra = exc.headers.get("Retry-After") if exc.headers else None
                    if ra:
                        try:
                            retry_after = float(ra)
                        except ValueError:
                            retry_after = None
                    if attempt > self.max_retries:
                        raise AdapterError(
                            "RATE_LIMITED",
                            "429 budget exhausted",
                            retryable=False,
                            retry_after=retry_after,
                        ) from exc
                    delay = retry_after if retry_after is not None else (2 ** attempt) + random.uniform(0, 0.5)
                    self.sleeper(delay)
                    continue
                if 500 <= exc.code < 600:
                    if attempt > self.max_retries:
                        raise AdapterError(
                            "UPSTREAM_5XX",
                            f"HTTP {exc.code} after retries",
                            retryable=False,
                        ) from exc
                    delay = (2 ** attempt) + random.uniform(0, 0.5)
                    self.sleeper(delay)
                    continue
                raise AdapterError("HTTP_ERROR", f"HTTP {exc.code}", retryable=False) from exc
            except (TimeoutError, urllib.error.URLError, TimeoutError) as exc:
                attempt += 1
                if attempt > self.max_retries:
                    raise AdapterError(
                        "TIMEOUT",
                        str(exc),
                        retryable=False,
                    ) from exc
                delay = (2 ** attempt) + random.uniform(0, 0.5)
                self.sleeper(delay)

    def fetch_by_ids(self, external_ids: list[str]) -> dict[str, FetchResult]:
        out: dict[str, FetchResult] = {}
        cleaned = [str(i).strip() for i in external_ids if str(i).strip()]
        for start in range(0, len(cleaned), self.batch_size):
            chunk = cleaned[start : start + self.batch_size]
            data = self._post(
                {
                    "query": BATCH_QUERY,
                    "variables": {"ids": ",".join(chunk), "limit": len(chunk)},
                }
            )
            animes = ((data.get("data") or {}).get("animes")) or []
            if not isinstance(animes, list):
                raise AdapterError("SCHEMA_DRIFT", "animes не список", hard_circuit=True)
            found_ids: set[str] = set()
            for row in animes:
                if not isinstance(row, dict):
                    continue
                eid = str(row.get("id") or "")
                if not eid:
                    continue
                found_ids.add(eid)
                # Also index by malId for crosswalk lookups when equal.
                mal = row.get("malId")
                mal_s = str(mal) if mal not in (None, "") else None
                score = normalize_score(row.get("score"))
                stats = row.get("scoresStats")
                votes = vote_count_from_stats(stats if isinstance(stats, list) else None)
                dist = distribution_from_stats(stats if isinstance(stats, list) else None)
                result = FetchResult(
                    external_id=eid,
                    found=score is not None,
                    raw_score=score,
                    vote_count=votes,
                    score_distribution=dist,
                    source_updated_at=str(row.get("updatedAt") or ""),
                    provenance_url=str(row.get("url") or ""),
                    name=str(row.get("name") or ""),
                    russian=str(row.get("russian") or ""),
                    mal_id=mal_s,
                    payload={
                        "id": eid,
                        "malId": mal_s,
                        "name": row.get("name"),
                        "russian": row.get("russian"),
                        "score": row.get("score"),
                        "scoresStats": stats,
                        "updatedAt": row.get("updatedAt"),
                        "url": row.get("url"),
                        # Явная пометка: score принадлежит Shikimori, не MAL.
                        "score_source": "shikimori",
                        "mal_id_is_not_score": True,
                    },
                )
                out[eid] = result
                if mal_s and mal_s != eid and mal_s in chunk:
                    out[mal_s] = result
            for requested in chunk:
                if requested not in out:
                    out[requested] = FetchResult(external_id=requested, found=False, error="NOT_FOUND")
        return out

    def check_schema(self) -> dict[str, Any]:
        """Bounded live/contract schema check (also works against fixtures via opener)."""
        # Introspection depth-limited: ask Anime field names only.
        data = self._post(
            {"query": "{ __type(name: \"Anime\") { fields { name } } }"}
        )
        fields = {
            f["name"]
            for f in (((data.get("data") or {}).get("__type") or {}).get("fields") or [])
            if isinstance(f, dict) and "name" in f
        }
        missing = sorted(REQUIRED_FIELDS - fields)
        if missing:
            raise AdapterError(
                "SCHEMA_DRIFT",
                f"Anime missing fields: {missing}",
                hard_circuit=True,
            )
        # Confirm batch CSV ids argument with a tiny probe if live.
        sample = self._post(
            {
                "query": BATCH_QUERY,
                "variables": {"ids": "1", "limit": 1},
            }
        )
        animes = ((sample.get("data") or {}).get("animes")) or []
        ok_sample = isinstance(animes, list)
        return {
            "adapter_version": self.adapter_version,
            "endpoint": self.url,
            "required_fields_present": True,
            "fields_checked": sorted(REQUIRED_FIELDS),
            "batch_ids_csv": True,
            "sample_ok": ok_sample,
            "request_headers_redacted": self.last_request_headers_redacted,
            "score_semantics": "shikimori_score_not_mal",
            "vote_count_from": "sum(scoresStats.count)",
            "documented_limits": {"rps": 5, "rpm": 90},
            "operational_cap": {
                "rps": self.rate_limiter.max_rps,
                "rpm": self.rate_limiter.max_per_minute,
            },
        }
