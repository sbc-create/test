"""HTTP-клиент источников: лимиты, таймаут, ограниченный backoff.

Повторов конечное число, и это число задано до первого запроса. Бесконечный
retry с экспоненциальной задержкой выглядит как устойчивость, а ведёт себя
как медленный отказ: задача не падает, очередь не движется, источник видит
непрекращающийся поток запросов и ставит нас в постоянный rate limit.

Клиент не умеет обходить ограничения источника. 401/403 и требование ключа
гасят источник целиком (``hard_circuit``), а не превращаются в попытку
зайти другим путём.
"""

from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from factory.ratings.adapters.base import AdapterError
from factory.ratings.rate_limit import RateLimiter

#: Заголовки, значение которых не попадает ни в лог, ни в evidence.
_SECRET_HEADERS = {"authorization", "cookie", "simkl-api-key", "x-api-key", "proxy-authorization"}


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in headers.items():
        out[key] = "[REDACTED]" if key.lower() in _SECRET_HEADERS else value
    return out


@dataclass
class HttpResponse:
    status: int
    headers: dict[str, str]
    body: bytes

    def json(self) -> Any:
        try:
            return json.loads(self.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AdapterError("SCHEMA_DRIFT", f"ответ не JSON: {exc}", hard_circuit=True) from exc


@dataclass
class HttpClient:
    """Клиент одного источника. Один экземпляр — один бюджет запросов."""

    user_agent: str
    rate_limiter: RateLimiter
    timeout: float = 20.0
    max_retries: int = 3
    #: верхняя граница одной паузы; защищает от Retry-After в сутки
    max_backoff_seconds: float = 60.0
    opener: Callable | None = None
    sleeper: Callable[[float], None] = time.sleep
    #: счётчики для журнала импорта
    requests: int = 0
    retries: int = 0
    rate_limited: int = 0
    last_headers_redacted: dict[str, str] = field(default_factory=dict)

    def request(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
    ) -> HttpResponse:
        hdrs = {"User-Agent": self.user_agent, **(headers or {})}
        self.last_headers_redacted = redact_headers(hdrs)
        attempt = 0
        while True:
            self.rate_limiter.wait()
            self.requests += 1
            req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
            open_fn = self.opener or (
                lambda r, timeout: urllib.request.urlopen(r, timeout=timeout)  # noqa: S310
            )
            try:
                with open_fn(req, self.timeout) as resp:
                    return HttpResponse(
                        status=getattr(resp, "status", 200),
                        headers=dict(resp.headers.items()),
                        body=resp.read(),
                    )
            except urllib.error.HTTPError as exc:
                decision = self._classify(exc, attempt)
                if decision is None:
                    raise
                if decision == "raise":
                    raise self._error_for(exc) from exc
                attempt += 1
                self.retries += 1
                self.sleeper(self._backoff(exc, attempt))
            except (TimeoutError, urllib.error.URLError) as exc:
                attempt += 1
                if attempt > self.max_retries:
                    raise AdapterError(
                        "TIMEOUT", f"{type(exc).__name__}: {exc}", retryable=False
                    ) from exc
                self.retries += 1
                self.sleeper(self._backoff(None, attempt))

    def _classify(self, exc: urllib.error.HTTPError, attempt: int) -> str:
        code = exc.code
        if code in (401, 403):
            return "raise"
        if code == 412:
            # Simkl отвечает 412 на отсутствующий client_id. Повторять
            # нечего: ключ от повторов не появится.
            return "raise"
        if code == 429:
            self.rate_limited += 1
            return "raise" if attempt >= self.max_retries else "retry"
        if 500 <= code < 600:
            return "raise" if attempt >= self.max_retries else "retry"
        return "raise"

    def _error_for(self, exc: urllib.error.HTTPError) -> AdapterError:
        code = exc.code
        if code in (401, 403):
            return AdapterError("AUTH_REJECTED", f"HTTP {code}", hard_circuit=True)
        if code == 412:
            return AdapterError(
                "CREDENTIAL_REQUIRED",
                f"HTTP {code}: источник требует ключ приложения",
                hard_circuit=True,
            )
        if code == 429:
            return AdapterError(
                "RATE_LIMITED",
                "HTTP 429: бюджет повторов исчерпан",
                retryable=False,
                retry_after=_retry_after(exc),
            )
        if 500 <= code < 600:
            return AdapterError("UPSTREAM_5XX", f"HTTP {code} после повторов", retryable=False)
        return AdapterError("HTTP_ERROR", f"HTTP {code}", retryable=False)

    def _backoff(self, exc: urllib.error.HTTPError | None, attempt: int) -> float:
        retry_after = _retry_after(exc) if exc is not None else None
        if retry_after is not None:
            return min(retry_after, self.max_backoff_seconds)
        jitter = random.uniform(0, 0.5)  # noqa: S311  (задержка, не криптография)
        return min((2**attempt) + jitter, self.max_backoff_seconds)

    def usage(self) -> dict[str, Any]:
        return {
            "requests": self.requests,
            "retries": self.retries,
            "rate_limited": self.rate_limited,
            **self.rate_limiter.usage(),
        }


def _retry_after(exc: urllib.error.HTTPError | None) -> float | None:
    if exc is None or not exc.headers:
        return None
    raw = exc.headers.get("Retry-After")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def build_client(source, *, timeout: float = 20.0, opener: Callable | None = None) -> HttpClient:
    """Клиент с лимитами из реестра источника. Мягче объявленных — нельзя."""
    return HttpClient(
        user_agent=(
            "site-factory-unified-ratings/1.0 "
            "(+https://github.com/site-factory; ratings ingestion; contact: operator)"
        ),
        rate_limiter=RateLimiter(
            max_rps=source.max_rps,
            max_per_minute=source.max_requests_per_minute,
        ),
        timeout=timeout,
        opener=opener,
    )
