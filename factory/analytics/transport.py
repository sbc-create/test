"""HTTP-транспорт к API Яндекса: таймауты, лимит частоты, повторы и аудит.

Отдельный слой нужен затем, чтобы провайдер занимался смыслом операций, а не
сетью, и чтобы правила «сколько ждать», «сколько повторять» и «что писать в
журнал» существовали в одном месте, а не в двенадцати.

Свойства, которые модуль обязан удержать:

* значение токена подставляется в заголовок в момент отправки и нигде не
  сохраняется: ни в объекте запроса, ни в журнале, ни в тексте исключения;
* ``429`` и временные ``5xx`` повторяются с экспоненциальной задержкой,
  ``401``/``403``/``404``/``409`` — не повторяются никогда;
* в режиме плана (``dry_run``) любой запрос, меняющий состояние, не уходит в
  сеть вообще: он возвращается как запланированный;
* каждый вызов попадает в audit trail — метод, путь, HTTP-статус, была ли
  мутация. Тело ответа в журнал не пишется.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from factory import audit
from factory.analytics.credentials import OAuthToken
from factory.errors import BlockedAnalyticsAccess, TransientError
from factory.redaction import redact
from factory.retry import RetryPolicy, run_with_retry

#: Значение по умолчанию: сеть отвечает быстро или не отвечает вовсе.
DEFAULT_TIMEOUT = 20.0

#: Минимальный интервал между запросами к одному сервису. Документированного
#: числового лимита для Management API в выжимке контракта нет, поэтому фабрика
#: сама держит скромный темп: превысить неизвестный лимит проще, чем узнать его.
DEFAULT_MIN_INTERVAL = 0.25

#: Повторяемые ответы. 429 — явная просьба подождать, 5xx — сбой на той стороне.
RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})

#: Ответы, которые повторять бессмысленно и вредно: они не изменятся сами, а
#: повтор POST рискует создать дубль.
TERMINAL_STATUSES = frozenset({400, 401, 403, 404, 405, 409, 422})

#: Методы, меняющие состояние на стороне Яндекса.
MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

RETRY_POLICY = RetryPolicy(max_attempts=5, base_delay=1.0, max_delay=30.0)


@dataclass(frozen=True)
class ApiResponse:
    """Ответ API. Тело хранится разобранным; сырой текст — только усечённый и отредактированный."""

    status: int
    payload: Any
    method: str
    path: str
    #: Заполняется только для неуспешных ответов и только после редакции.
    error_text: str = ""
    #: Запрос не отправлялся: план показывает, что было бы сделано.
    planned: bool = False

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "method": self.method,
            "path": self.path,
            "ok": self.ok,
            "planned": self.planned,
            "error": self.error_text or None,
        }


@dataclass
class RateLimiter:
    """Простейший ограничитель: не чаще одного запроса в ``min_interval`` секунд."""

    min_interval: float = DEFAULT_MIN_INTERVAL
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic
    #: `None`, а не `0.0`: «запросов ещё не было» и «первый запрос случился в
    #: нулевой момент» — разные состояния, и проверка на истинность их путает.
    _last: float | None = field(default=None, repr=False)

    def wait(self) -> None:
        if self.min_interval <= 0:
            return
        if self._last is not None:
            elapsed = self.clock() - self._last
            if elapsed < self.min_interval:
                self.sleep(self.min_interval - elapsed)
        self._last = self.clock()


class ApiError(TransientError):
    """Временный отказ API: 429 или 5xx. Повторяется транспортом."""


def _decode(raw: bytes) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


class YandexApiClient:
    """Клиент одного сервиса Яндекса (Метрика или Вебмастер).

    ``opener`` подменяется в тестах: боевой сети в unit-тестах нет и не должно
    быть, а поведение при 401/403/429/5xx проверяется именно здесь.
    """

    def __init__(
        self,
        base_url: str,
        token: OAuthToken,
        *,
        service: str,
        timeout: float = DEFAULT_TIMEOUT,
        dry_run: bool = True,
        rate_limiter: RateLimiter | None = None,
        retry_policy: RetryPolicy = RETRY_POLICY,
        sleep: Callable[[float], None] = time.sleep,
        opener: Callable[[urllib.request.Request, float], tuple[int, bytes]] | None = None,
        job_id: str = "analytics",
        site_id: str = "-",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.service = service
        self._token = token
        self.timeout = timeout
        #: План по умолчанию. Запись включается явно и только вызывающим.
        self.dry_run = dry_run
        self.rate_limiter = rate_limiter or RateLimiter()
        self.retry_policy = retry_policy
        self._sleep = sleep
        self._opener = opener or self._urlopen
        self.job_id = job_id
        self.site_id = site_id
        #: Счётчики для отчёта: сколько запросов ушло и сколько было отложено.
        self.calls: list[dict] = []

    # ------------------------------------------------------------------ сеть
    @staticmethod
    def _urlopen(request: urllib.request.Request, timeout: float) -> tuple[int, bytes]:
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
                return response.status, response.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()

    def _url(self, path: str, params: dict | None) -> str:
        url = f"{self.base_url}{path}"
        if params:
            clean = {k: v for k, v in params.items() if v is not None}
            if clean:
                url = f"{url}?{urllib.parse.urlencode(clean, doseq=True)}"
        return url

    # ------------------------------------------------------------- запросы
    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        body: dict | None = None,
        allow_statuses: frozenset[int] = frozenset(),
    ) -> ApiResponse:
        """Выполняет запрос. Мутация в режиме плана не отправляется.

        ``allow_statuses`` — коды, которые вызывающий считает нормальным
        ответом (например ``409 HOST_ALREADY_ADDED`` — это идемпотентность,
        а не ошибка).
        """
        method = method.upper()
        mutating = method in MUTATING_METHODS

        if mutating and self.dry_run:
            self.calls.append({"method": method, "path": path, "planned": True})
            return ApiResponse(0, None, method, path, planned=True)

        def attempt() -> ApiResponse:
            self.rate_limiter.wait()
            data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
            request = urllib.request.Request(  # noqa: S310 — базовый URL из замороженного контракта
                self._url(path, params),
                data=data,
                method=method,
                headers={
                    # Единственное место, где значение токена покидает OAuthToken.
                    "Authorization": self._token.authorization_header(),
                    "Accept": "application/json",
                    **({"Content-Type": "application/json"} if data is not None else {}),
                },
            )
            try:
                status, raw = self._opener(request, self.timeout)
            except OSError as exc:
                # Сетевой сбой — временная ошибка среды, её ретраит factory.retry.
                raise ApiError(
                    f"{self.service}: сеть недоступна ({exc.__class__.__name__})",
                    field=f"analytics.{self.service}",
                    blocks_stage="VALIDATING",
                ) from None

            payload = _decode(raw)
            if status in RETRYABLE_STATUSES and status not in allow_statuses:
                raise ApiError(
                    f"{self.service}: HTTP {status}",
                    field=f"analytics.{self.service}",
                    blocks_stage="VALIDATING",
                )
            error_text = "" if 200 <= status < 300 else redact(self._error_of(payload, raw))
            return ApiResponse(status, payload, method, path, error_text=error_text)

        try:
            response = run_with_retry(attempt, policy=self.retry_policy, sleep=self._sleep)
        except ApiError as exc:
            self._audit(method, path, None, mutating, str(exc))
            raise BlockedAnalyticsAccess(
                f"{exc.reason}. Повторы исчерпаны — фабрика не продолжает с выдуманными данными.",
                field=f"analytics.{self.service}",
                required_input="Доступный API Яндекса или снятый лимит частоты",
                blocks_stage="VALIDATING",
            ) from None

        self.calls.append({"method": method, "path": path, "status": response.status})
        self._audit(method, path, response.status, mutating, response.error_text)

        if not response.ok and response.status not in allow_statuses:
            raise BlockedAnalyticsAccess(
                self._explain(response),
                field=f"analytics.{self.service}",
                required_input=self._required_input(response.status),
                blocks_stage="VALIDATING",
            )
        return response

    def get(self, path: str, **kwargs) -> ApiResponse:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> ApiResponse:
        return self.request("POST", path, **kwargs)

    # ------------------------------------------------------- диагностика
    @staticmethod
    def _error_of(payload: Any, raw: bytes) -> str:
        """Сообщение об ошибке из тела ответа. Тело целиком в отчёт не идёт."""
        if isinstance(payload, dict):
            for key in ("message", "error_message", "error_type", "code"):
                if payload.get(key):
                    return str(payload[key])[:300]
            errors = payload.get("errors")
            if isinstance(errors, list) and errors:
                return str(errors[0])[:300]
        return raw[:200].decode("utf-8", "replace") if raw else ""

    def _explain(self, response: ApiResponse) -> str:
        known = {
            401: "токен не принят (истёк, отозван или неверен)",
            403: "у токена нет прав на эту операцию",
            404: "ресурс не найден",
            409: "конфликт: объект уже существует",
            422: "запрос отвергнут как некорректный",
        }
        detail = known.get(response.status, "неожиданный ответ")
        suffix = f": {response.error_text}" if response.error_text else ""
        return f"{self.service} ответил HTTP {response.status} — {detail}{suffix}"

    @staticmethod
    def _required_input(status: int) -> str:
        if status == 401:
            return "Действующий OAuth-токен в файле секрета (нужна ротация)"
        if status == 403:
            return "Токен с правами на управление счётчиками Метрики и сайтами Вебмастера"
        return "Работающий API Яндекса; входные данные операции проверить по контракту"

    def _audit(self, method: str, path: str, status: int | None, mutation: bool, detail: str) -> None:
        audit.record(
            job_id=self.job_id,
            site_id=self.site_id,
            environment="staging",
            action=f"analytics.{self.service}.{method.lower()}",
            # В журнал идёт путь без query: query может нести идентификаторы.
            target=f"{self.base_url}{path}",
            exit_code=status,
            mutation=mutation,
            # Тело ответа не журналируется: в журнале нужен факт вызова и его исход.
            extra={"detail": redact(detail)[:500]} if detail else None,
        )
