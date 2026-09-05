"""Control API v1 — безопасные операции записи над массивом сайтов.

Читающая часть (app.py) отвечает на вопрос «что сейчас». Этот модуль отвечает на
вопрос «измени вот это» — и потому устроен строже. Каждая запись проходит один и
тот же конвейер: включённость → аутентификация → право → лимит частоты →
валидация → идемпотентность → блокировка сайта → сверка версии → применение →
аудит. Пропустить ступень нельзя: конвейер один на все маршруты.

Три решения, которые стоит объяснить, потому что они ограничивают возможности:

1. Запись включается отдельным флагом, а не вместе с чтением. Открытое чтение —
   это утечка; открытая запись — это чужой контроль над витриной. Разные риски
   заслуживают разных выключателей, иначе включивший чтение однажды обнаружит,
   что включил и запись.

2. Меняются только обратимые настройки, принадлежащие ядру. Домены, канонический
   хост, тип сайта и флаги индексации отклоняются намеренно: их правка через
   вызов API — не управление, а авария с большим радиусом, которую замечают
   через недели по падению трафика. Такие изменения проходят через ревью и
   выкладку, где у них есть автор и откат.

3. Инвалидация кэша ставится заданием в очередь, а не ходит в Redis напрямую.
   Управляющий слой не должен иметь доступа к данным витрин: тогда его ошибка
   останется ошибкой планирования, а не порчей чужого состояния.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from factory import audit, locks, queue
from factory.site_engine.api import compat, content_health, reasons
from factory.site_engine.api.app import ApiResponse, error
from factory.site_engine.api.idempotency import (
    CONFLICT,
    IN_PROGRESS,
    REPLAY,
    IdempotencyStore,
    fingerprint,
)
from factory.site_engine.api.metrics import Metrics, status_class
from factory.site_engine.api.ratelimit import SharedRateLimiter
from factory.site_engine.api.tracing import (
    TRACEPARENT,
    Tracer,
    new_context,
    parse_traceparent,
    path_template,
)
from factory.site_engine.settings_contract import (
    REFUSED_SETTINGS,
    SAFE_SETTINGS,
    config_version,
    profile_path,
)

API_VERSION = "v1"

# Право на чтение отделено от права на запись, а запись — по областям. Один
# токен для всего означает, что задача «дай Qwen перезапускать индексацию»
# незаметно выдаёт и право переписать конфигурацию.
SCOPE_READ = "read"
SCOPE_JOBS = "jobs:write"
SCOPE_CONFIG = "config:write"
SCOPE_CACHE = "cache:write"
SCOPE_AUDIT = "audit:read"
#: Разбор спорных записей. Отдельно от config:write намеренно: редактор,
#: решающий вопрос о виде произведения, не должен получать право менять
#: настройки витрины — это разные роли и разный радиус ошибки.
SCOPE_REVIEW = "review:write"
#: Управление людьми. Самое опасное право в системе: оно позволяет выдать
#: любое другое. Поэтому оно есть только у роли admin и никогда не входит в
#: набор по умолчанию.
SCOPE_OPERATORS = "operators:write"
#: Заведение новых витрин. Отдельно от config:write: право менять настройки
#: существующей витрины и право создать новую — разные по последствиям. Первое
#: обратимо откатом, второе занимает домен и место на площадке.
SCOPE_SITES = "sites:create"
KNOWN_SCOPES = frozenset(
    {
        SCOPE_READ,
        SCOPE_JOBS,
        SCOPE_CONFIG,
        SCOPE_CACHE,
        SCOPE_AUDIT,
        SCOPE_REVIEW,
        SCOPE_OPERATORS,
        SCOPE_SITES,
    }
)

# Действия, которые разрешено ставить в очередь. Список закрытый: очередь
# исполняет то, что в ней лежит, поэтому свободное поле action означало бы
# выполнение произвольного действия по HTTP.
ALLOWED_JOB_ACTIONS = frozenset({"reindex", "refresh", "enrich", "verify"})
ALLOWED_ENVIRONMENTS = frozenset({"staging", "production"})

SITE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
# Ключ кэша — идентификатор, а не адрес. Управляющий слой сам ключи не
# запрашивает, но кладёт их в очередь исполнителю, и тот может обойтись с
# похожим на URL значением как с адресом. Проще не пропускать такое сюда,
# чем полагаться на осторожность каждого будущего исполнителя.
CACHE_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
MAX_BODY_KEYS = 32


class ControlDenied(Exception):
    """Отказ на ступени конвейера. Несёт код и статус, чтобы ответ был точным."""

    def __init__(self, status: int, code: str, message: str, **extra: Any) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.extra = extra


@dataclass(frozen=True)
class Principal:
    """Кто обращается. Токен наружу не отдаётся — только его идентификатор."""

    token_id: str
    scopes: frozenset[str]
    label: str = ""

    def require(self, scope: str) -> None:
        if scope not in self.scopes:
            raise ControlDenied(
                403,
                "forbidden",
                f"нет права {scope}",
                required_scope=scope,
                granted_scopes=sorted(self.scopes),
            )


def _актор(principal) -> str:
    """Кто действует. У Principal нет поля name — было бы всегда «operator».

    Различие существенное: запрет утверждать собственное решение и запись в
    журнал опираются на действующее лицо. Одно имя на всех превращает и то и
    другое в формальность.
    """
    метка = getattr(principal, "label", "") or ""
    return метка or f"token:{getattr(principal, 'token_id', 'unknown')}"


def writes_enabled(env: dict[str, str] | None = None) -> bool:
    """Запись выключена по умолчанию и включается отдельно от чтения."""
    env = env if env is not None else {}
    return str(env.get("SITE_ENGINE_CONTROL_WRITES", "")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _token_id(token: str) -> str:
    """Устойчивый идентификатор токена для журналов. Сам токен не хранится."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:12]


def principals_from_env(env: dict[str, str] | None = None) -> dict[str, Principal]:
    """Разбор SITE_ENGINE_CONTROL_TOKENS вида `токен=области|токен=области`.

    Разделитель — «=», а не «:»: имена областей сами содержат двоеточие
    (jobs:write), и разбор по первому двоеточию разорвал бы их пополам.

    Пустая переменная означает «никому ничего»: отсутствие настройки не должно
    молча превращаться в открытый доступ.
    """
    env = env if env is not None else {}
    raw = str(env.get("SITE_ENGINE_CONTROL_TOKENS", "")).strip()
    principals: dict[str, Principal] = {}
    if not raw:
        return principals
    for chunk in raw.split("|"):
        chunk = chunk.strip()
        if not chunk or "=" not in chunk:
            continue
        token, _, scope_part = chunk.partition("=")
        token = token.strip()
        if not token:
            continue
        scopes = {s.strip() for s in scope_part.split(",") if s.strip()}
        unknown = scopes - KNOWN_SCOPES
        if unknown:
            # Опечатка в области права — это тихо выданное не то право.
            raise ValueError(f"неизвестные области: {sorted(unknown)}")
        principals[token] = Principal(token_id=_token_id(token), scopes=frozenset(scopes))
    return principals


def _validate_settings(changes: dict[str, Any]) -> list[str]:
    """Все нарушения сразу, а не первое. Отказ по одному полю за запрос
    превращает исправление конфигурации в переписку из пяти раундов."""
    problems: list[str] = []
    for key, value in changes.items():
        if key in REFUSED_SETTINGS:
            problems.append(f"{key}: отклонено намеренно — {REFUSED_SETTINGS[key]}")
            continue
        rule = SAFE_SETTINGS.get(key)
        if rule is None:
            problems.append(f"{key}: не входит в список изменяемых настроек")
            continue
        expected = rule["type"]
        if expected is int and isinstance(value, bool):
            problems.append(f"{key}: ожидалось число, получено логическое значение")
            continue
        if not isinstance(value, expected):
            problems.append(f"{key}: ожидался тип {expected.__name__}")
            continue
        if expected is int:
            if not (rule["min"] <= value <= rule["max"]):
                problems.append(
                    f"{key}: допустимо от {rule['min']} до {rule['max']}, получено {value}"
                )
        elif expected is dict:
            vtype = rule["value_type"]
            for sub_key, sub_value in value.items():
                if not isinstance(sub_key, str) or not sub_key:
                    problems.append(f"{key}: имя вложенного ключа должно быть непустой строкой")
                    continue
                if vtype is int and isinstance(sub_value, bool):
                    problems.append(f"{key}.{sub_key}: ожидалось число")
                    continue
                if not isinstance(sub_value, vtype):
                    problems.append(f"{key}.{sub_key}: ожидался тип {vtype.__name__}")
                    continue
                if vtype is int and not (rule["min"] <= sub_value <= rule["max"]):
                    problems.append(
                        f"{key}.{sub_key}: допустимо от {rule['min']} до {rule['max']}, получено {sub_value}"
                    )
    return problems


def _diff(before: dict[str, Any], changes: dict[str, Any]) -> dict[str, Any]:
    """Что именно изменится. Возвращается и в dry-run, и в аудит, чтобы запись в
    журнале отвечала на вопрос «что стало другим», а не только «кто-то менял»."""
    out: dict[str, Any] = {}
    for key, value in changes.items():
        old = before.get(key)
        if isinstance(value, dict) and isinstance(old, dict):
            merged = {**old, **value}
            if merged != old:
                out[key] = {"before": old, "after": merged}
        elif old != value:
            out[key] = {"before": old, "after": value}
    return out


class ClientOperation:
    """Операция, начатая внешним слоем поверх Control API.

    Существует, чтобы панель не импортировала внутренности пакета `api`.
    Панель получает управляющий объект внедрением и работает только через его
    открытую поверхность: иначе граница между слоями держится на договорённости,
    а не на устройстве кода, и первый же прямой импорт её отменяет.
    """

    def __init__(
        self,
        tracer,
        context,
        *,
        name: str,
        service: str,
        method: str,
        path: str,
        started: float,
        now,
    ) -> None:
        self._tracer = tracer
        self._context = context
        self._name = name
        self._service = service
        self._method = method.upper()
        self._path = path
        self._started = started
        self._now = now

    @property
    def headers(self) -> dict[str, str]:
        """Заголовки для передачи в Control API. Продолжают тот же след."""
        return {TRACEPARENT: self._context.header()}

    def finish(self, status: int) -> None:
        if not self._context.sampled:
            return
        отрезок = _завершённый_отрезок(
            self._context,
            None,
            self._name,
            {
                "method": self._method,
                "path_template": path_template(self._path),
                "status": status,
                "outcome": "ok" if status < 400 else "error",
            },
            self._started,
            float(self._now()),
            service=self._service,
        )
        self._tracer.record(отрезок)


def _завершённый_отрезок(
    контекст, родитель, имя, атрибуты, начало, конец, service: str = "control-api"
):
    """Готовый отрезок для записи после ответа."""
    from factory.site_engine.api.tracing import Span, sanitize_attrs

    отрезок = Span(
        trace_id=контекст.trace_id,
        span_id=контекст.span_id,
        parent_id=родитель.span_id if родитель is not None else None,
        name=имя,
        service=service,
        started=начало,
        attrs=sanitize_attrs(атрибуты),
    )
    отрезок.ended = конец
    return отрезок


class ControlApi:
    """Записывающая часть Control API v1."""

    def __init__(
        self,
        *,
        root: Path | str = ".",
        env: dict[str, str] | None = None,
        now: Any = time.time,
        metrics: Metrics | None = None,
        limiter: SharedRateLimiter | None = None,
        idempotency: IdempotencyStore | None = None,
        tracer: Tracer | None = None,
    ) -> None:
        self._root = Path(root).resolve()
        self._env = env if env is not None else {}
        self._now = now
        self._principals = principals_from_env(self._env)
        self._metrics = metrics if metrics is not None else Metrics()
        состояние = self._root / "var" / "state"
        # Ограничение и идемпотентность живут в общем каталоге состояния, а не
        # в памяти: при двух экземплярах Control API предел в памяти оказался бы
        # вдвое выше объявленного, а повтор после таймаута создал бы второе
        # задание.
        self._limiter = limiter if limiter is not None else SharedRateLimiter(состояние, now=now)
        self._idempotency = (
            idempotency if idempotency is not None else IdempotencyStore(состояние, now=now)
        )
        self._tracer = tracer if tracer is not None else Tracer(состояние, now=now)
        # Показатели, которые считает не этот модуль: их поставщик регистрирует
        # себя сам. Иначе управляющий слой начал бы знать про админку.
        self._gauges: dict[str, Any] = {}

    @property
    def tracer(self) -> Tracer:
        return self._tracer

    @property
    def metrics(self) -> Metrics:
        return self._metrics

    def register_gauge(self, name: str, source: Any) -> None:
        """Источник показателя, вычисляемый в момент опроса."""
        self._gauges[name] = source

    def begin_client_operation(
        self, method: str, path: str, *, service: str, mutating: bool
    ) -> ClientOperation:
        """Начать операцию внешнего слоя.

        Возвращается объект с заголовками для последующих вызовов и способом
        закрыть отрезок. Внешнему слою не нужно знать ни формата контекста, ни
        устройства трассировщика.
        """
        контекст = new_context(sampled=self._tracer.should_sample(mutating=mutating, failed=False))
        return ClientOperation(
            self._tracer,
            контекст,
            name=f"{service}.request",
            service=service,
            method=method,
            path=path,
            started=float(self._now()),
            now=self._now,
        )

    def principal_for(self, token: str) -> Principal | None:
        """Права токена — для вызывающих внутри процесса.

        Нужен админке, чтобы не показывать кнопки, которых всё равно не
        позволит конвейер. Показ и запрет — разные вещи: запрет остаётся здесь.
        """
        return self._principals.get(token)

    def mint_session_principal(self, *, label: str, scopes) -> str:
        """Временный принципал для сессии оператора.

        Права оператора задаются его ролями, а не выданным заранее токеном. Но
        второй путь аутентификации заводить нельзя: он неизбежно разойдётся с
        первым. Поэтому здесь рождается обычный принципал — просто с временем
        жизни сессии и без записи в настройках.

        Значение живёт только в памяти процесса, наружу не отдаётся и
        уничтожается вместе с сессией.
        """
        import secrets as _secrets

        токен = _secrets.token_urlsafe(32)
        self._principals[токен] = Principal(
            token_id=hashlib.sha256(токен.encode("utf-8")).hexdigest()[:12],
            scopes=frozenset(scopes),
            label=label,
        )
        return токен

    def update_session_principal(self, token: str, *, scopes) -> None:
        """Права сессии обязаны следовать за ролями, а не за моментом входа."""
        прежний = self._principals.get(token)
        if прежний is None:
            return
        self._principals[token] = Principal(
            token_id=прежний.token_id, scopes=frozenset(scopes), label=прежний.label
        )

    def drop_session_principal(self, token: str) -> None:
        if token:
            self._principals.pop(token, None)

    # ---- конвейер -------------------------------------------------------

    def handle(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> ApiResponse:
        headers = {str(k).lower(): v for k, v in (headers or {}).items()}
        correlation_id = (
            str(headers.get("x-correlation-id") or "").strip() or self._new_correlation_id()
        )
        # Контекст следа продолжается, если пришёл, и начинается, если нет.
        родитель = parse_traceparent(headers.get(TRACEPARENT))
        изменяющий = method.upper() in {"POST", "PATCH", "PUT", "DELETE"}
        if родитель is not None:
            контекст = родитель.child()
        else:
            контекст = new_context(
                sampled=self._tracer.should_sample(mutating=изменяющий, failed=False)
            )
        self._trace_context = контекст
        self._request_started = float(self._now())
        try:
            ключ, отпечаток = self._idempotency_key(method, path, body or {}, headers)
        except ControlDenied as denied:
            # Разбор ключа стоит до конвейера, поэтому его отказ надо перехватить
            # здесь: иначе недопустимый ключ вылетает исключением наружу вместо
            # ответа 400. Найдено проверкой несколькими процессами.
            return self._deny(denied, method, path, headers, correlation_id)
        if ключ:
            заявка = self._idempotency.reserve(ключ, отпечаток)
            if заявка.state == REPLAY:
                тело = dict(заявка.stored.get("body") or {})
                тело["idempotentReplay"] = True
                тело["correlationId"] = correlation_id
                return ApiResponse(status=int(заявка.stored.get("status", 200)), body=тело)
            if заявка.state == CONFLICT:
                return self._deny(
                    ControlDenied(
                        409,
                        "idempotency_key_reused",
                        "ключ идемпотентности уже использован для другого запроса",
                    ),
                    method,
                    path,
                    headers,
                    correlation_id,
                )
            if заявка.state == IN_PROGRESS:
                # Первый запрос ещё выполняется. Ждать значит удваивать таймаут
                # вместо ответа; выполнить второй раз — нарушить идемпотентность.
                return self._deny(
                    ControlDenied(
                        409,
                        "request_in_flight",
                        "запрос с этим ключом уже выполняется",
                        holder=заявка.holder,
                        age_seconds=round(заявка.age_seconds, 1),
                    ),
                    method,
                    path,
                    headers,
                    correlation_id,
                )

        try:
            response = self._route(method.upper(), path, body or {}, headers, correlation_id)
            if ключ:
                if 200 <= response.status < 300:
                    self._idempotency.commit(ключ, отпечаток, response.status, response.body)
                else:
                    # Отказ не запоминается: исправленный повтор с тем же ключом
                    # должен получить возможность выполниться.
                    self._idempotency.release(ключ)
        except ControlDenied as denied:
            if ключ:
                self._idempotency.release(ключ)
            self._audit_refusal(denied, method, path, headers, correlation_id)
            response = error(denied.status, denied.code, denied.message, **denied.extra)
            self._metrics.inc("site_engine_control_refusals_total", code=denied.code)
        self._metrics.inc(
            "site_engine_control_requests_total",
            method=method.upper(),
            status=status_class(response.status),
        )
        # Идентификатор запроса возвращается всегда, включая отказы: без него
        # вызывающий не может найти свой запрос в журнале и приносит скриншот.
        payload = response.body if isinstance(response.body, dict) else {"result": response.body}
        payload = {**payload, "correlationId": correlation_id, "traceparent": контекст.header()}
        # Отрезок записывается после ответа: до него неизвестны ни код, ни
        # причина отказа, а след без них отвечает «что-то произошло».
        # Поле error принадлежит оболочке ошибок и обязано быть объектом.
        # Но тело может прийти от любого обработчика, и чужая форма не
        # должна ронять запись следа — диагностика не вправе ломать работу.
        сырое = payload.get("error") if isinstance(payload, dict) else None
        ошибка = сырое.get("code", "") if isinstance(сырое, dict) else ""
        if контекст.sampled or response.status >= 400:
            отрезок = _завершённый_отрезок(
                контекст,
                родитель,
                "control.request",
                {
                    "method": method.upper(),
                    "path_template": path_template(path),
                    "status": response.status,
                    "error_code": ошибка,
                    "outcome": "ok" if response.status < 400 else "error",
                },
                self._request_started,
                float(self._now()),
            )
            self._tracer.record(отрезок)
        return ApiResponse(status=response.status, body=payload)

    def _idempotency_key(
        self, method: str, path: str, body: dict[str, Any], headers: dict[str, str]
    ) -> tuple[str | None, str]:
        """Ключ применим только к изменяющим запросам без dryRun.

        Пробный запуск ничего не меняет, поэтому занимать под него ключ значит
        запретить последующее боевое применение с тем же ключом.
        """
        if method.upper() not in {"POST", "PATCH", "PUT", "DELETE"}:
            return None, ""
        if body.get("dryRun"):
            return None, ""
        ключ = str(headers.get("idempotency-key") or "").strip()
        if not ключ:
            return None, ""
        if len(ключ) > 128 or not re.match(r"^[A-Za-z0-9_.:-]+$", ключ):
            raise ControlDenied(400, "invalid_idempotency_key", "ключ идемпотентности недопустим")
        return ключ, fingerprint(method.upper(), path, body)

    def _deny(
        self,
        denied: ControlDenied,
        method: str,
        path: str,
        headers: dict[str, str],
        correlation_id: str,
    ) -> ApiResponse:
        self._audit_refusal(denied, method, path, headers, correlation_id)
        self._metrics.inc("site_engine_control_refusals_total", code=denied.code)
        self._metrics.inc(
            "site_engine_control_requests_total",
            method=method.upper(),
            status=status_class(denied.status),
        )
        ответ = error(denied.status, denied.code, denied.message, **denied.extra)
        # Ранние отказы возвращаются мимо общего хвоста handle(), поэтому след
        # пишется здесь. Без этого конфликт ключа и запрос в работе — то есть
        # ровно те случаи, ради которых трассировку заводят, — следа не имели.
        контекст = getattr(self, "_trace_context", None)
        if контекст is not None:
            отрезок = _завершённый_отрезок(
                контекст,
                None,
                "control.request",
                {
                    "method": method.upper(),
                    "path_template": path_template(path),
                    "status": denied.status,
                    "error_code": denied.code,
                    "outcome": "error",
                },
                getattr(self, "_request_started", float(self._now())),
                float(self._now()),
            )
            self._tracer.record(отрезок)
        тело = {**ответ.body, "correlationId": correlation_id}
        if контекст is not None:
            тело["traceparent"] = контекст.header()
        return ApiResponse(status=ответ.status, body=тело)

    def _new_correlation_id(self) -> str:
        seed = f"{self._now()}:{id(self)}"
        return "cid-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]

    def _route(
        self,
        method: str,
        path: str,
        body: dict[str, Any],
        headers: dict[str, str],
        correlation_id: str,
    ) -> ApiResponse:
        parts = [p for p in path.strip("/").split("/") if p]
        if parts[:2] != ["api", API_VERSION]:
            raise ControlDenied(404, "not_found", "маршрут не найден")
        rest = parts[2:]

        # Запись выключена — маршрут не существует. Отвечать 403 значит
        # подтверждать, что здесь есть что включать.
        mutating = method in {"POST", "PATCH", "PUT", "DELETE"}
        if mutating and not writes_enabled(self._env):
            raise ControlDenied(404, "not_found", "маршрут не найден")

        principal = self._authenticate(headers)
        # Витрина и операция извлекаются до списания разрешения: без них
        # предел был бы общим на действующее лицо, и одна витрина упирала бы
        # в него остальные.
        site_for_limit = rest[1] if rest[:1] == ["sites"] and len(rest) >= 2 else ""
        operation = "/".join(rest[2:]) if len(rest) > 2 else (rest[0] if rest else "")
        self._rate_limit(
            principal, site_for_limit, f"{method}:{operation}", mutating=mutating
        )

        if method == "GET" and rest[:1] == ["content-health"]:
            principal.require(SCOPE_READ)
            return self._content_health(rest[1] if len(rest) > 1 else None, body)
        if method == "GET" and rest == ["reasons"]:
            principal.require(SCOPE_READ)
            return ApiResponse(status=200, body=reasons.catalogue())
        if method == "GET" and rest == ["playback-policy"]:
            principal.require(SCOPE_READ)
            return self._playback_policy()
        if rest[:1] == ["review-queue"]:
            return self._review_route(method, rest[1:], body, principal, headers, correlation_id)
        if method == "GET" and rest == ["overview"]:
            principal.require(SCOPE_READ)
            from factory.site_engine.api import overview as overview_mod

            return ApiResponse(status=200, body=overview_mod.сводка(self._root, env=self._env))
        if method == "GET" and rest == ["jobs"]:
            principal.require(SCOPE_READ)
            from factory.site_engine.api import ops_view

            return ApiResponse(
                status=200,
                body=ops_view.jobs(
                    self._root,
                    site_id=self._опция(body, "siteId"),
                    state=self._опция(body, "state"),
                    offset=self._целое(body, "offset", 0, 0, 10**6),
                    limit=self._целое(body, "limit", 50, 1, 200),
                ),
            )
        if method == "GET" and rest == ["sites-status"]:
            principal.require(SCOPE_READ)
            from factory.site_engine.api import ops_view

            return ApiResponse(status=200, body=ops_view.sites(self._root, env=self._env))
        if rest[:1] == ["content"]:
            return self._content_route(method, rest[1:], body, principal)
        if rest[:1] == ["operators"]:
            return self._operators_route(method, rest[1:], body, principal, headers, correlation_id)
        if method == "GET" and len(rest) == 2 and rest[0] == "traces":
            principal.require(SCOPE_AUDIT)
            return self._trace(rest[1])
        if method == "GET" and rest[:1] == ["compatibility"]:
            principal.require(SCOPE_READ)
            return self._compatibility(rest[1] if len(rest) > 1 else None)
        if method == "GET" and rest == ["metrics"]:
            principal.require(SCOPE_READ)
            return self._metrics_response()
        if rest[:1] == ["site-requests"]:
            return self._site_requests(method, rest[1:], body, principal, correlation_id)
        if method == "GET" and len(rest) == 2 and rest[0] == "join-keys":
            principal.require(SCOPE_READ)
            from factory.site_engine.api import join_keys as _ключи

            self._check_site_id(rest[1])
            try:
                return ApiResponse(
                    status=200,
                    body=_ключи.join_keys(
                        self._root,
                        rest[1],
                        env=self._env,
                        offset=self._целое(body, "offset", 0, 0, 10**6),
                        limit=self._целое(body, "limit", 500, 1, 5000),
                    ),
                )
            except _ключи.JoinKeyError as ошибка:
                raise ControlDenied(404, "site_not_found", str(ошибка)) from ошибка
        if method == "GET" and rest == ["scorecard"]:
            principal.require(SCOPE_READ)
            from factory.site_engine.api import readiness

            return ApiResponse(status=200, body=readiness.scorecard(self._root, self._env))
        if method == "GET" and rest == ["rating-sources"]:
            principal.require(SCOPE_READ)
            from factory.site_engine import rating_sources

            try:
                return ApiResponse(status=200, body=rating_sources.resolve(self._root).as_dict())
            except rating_sources.RatingSourceError as ошибка:
                # Противоречивый реестр — не «почти работает»: он молча
                # открывает то, что закрыто решением владельца.
                raise ControlDenied(500, "rating_registry_invalid", str(ошибка)) from ошибка
        if method == "GET" and rest == ["alerts"]:
            principal.require(SCOPE_READ)
            from factory.site_engine.api import readiness

            return ApiResponse(status=200, body=readiness.alerts())
        if method == "GET" and rest == ["state-inventory"]:
            principal.require(SCOPE_AUDIT)
            from factory.site_engine.api import readiness

            return ApiResponse(status=200, body=readiness.state_inventory(self._root))
        if method == "POST" and rest == ["state-backup"]:
            principal.require(SCOPE_AUDIT)
            from factory.site_engine.api import readiness

            итог = readiness.state_backup(
                self._root, verify=body.get("verify", True) is not False
            )
            audit.record(
                job_id=correlation_id,
                site_id="",
                environment="staging",
                action="control.state.backup",
                target=str(итог["backup"]),
                mutation=True,
                exit_code=0 if итог["verified"] else 1,
                extra={
                    "correlation_id": correlation_id,
                    "actor": _актор(principal),
                    "verified": итог["verified"],
                },
            )
            return ApiResponse(status=200, body=итог)
        if method == "GET" and rest == ["releases"]:
            principal.require(SCOPE_READ)
            from factory.site_engine.api import program_view

            return ApiResponse(status=200, body=program_view.releases(self._root, self._env))
        if method == "GET" and rest == ["incidents"]:
            principal.require(SCOPE_READ)
            from factory.site_engine.api import program_view

            return ApiResponse(status=200, body=program_view.incidents(self._root, self._env))
        if method == "GET" and rest[:1] == ["audit"]:
            principal.require(SCOPE_AUDIT)
            return self._audit_trail(body, headers)
        if method == "GET" and len(rest) == 2 and rest[0] == "jobs":
            principal.require(SCOPE_READ)
            # Сначала результат: очередь знает только «где лежит файл», а
            # оператору нужно, чем задание кончилось и какие проверки не
            # прошли. Пока задание в очереди, результата ещё нет — тогда
            # отвечает очередь.
            результат = self._job_result(rest[1])
            if результат is not None:
                return результат
            return self._job_status(rest[1])
        # Отдельный префикс, а не /api/v1/sites/{id}/status: транспорт
        # определяет управляющие маршруты по префиксу из описания, и запись
        # под sites/ перехватывала читающий /api/v1/sites/{id}. Поймано
        # проверкой границ маршрутизации.
        if method == "GET" and len(rest) == 2 and rest[0] == "site-status":
            principal.require(SCOPE_READ)
            from factory.site_engine.api import ops_view

            try:
                return ApiResponse(
                    status=200, body=ops_view.site_status(self._root, rest[1], env=self._env)
                )
            except ops_view.OpsError as ошибка:
                raise ControlDenied(404, "site_not_found", str(ошибка)) from ошибка
        # Чтение настроек — отдельный префикс, не GET на пути записи:
        # управляющие маршруты транспорт различает по префиксу из описания, и
        # второй метод на том же пути в описании не помещается.
        if method == "GET" and len(rest) == 2 and rest[0] == "settings":
            principal.require(SCOPE_READ)
            return self._settings_view(rest[1], principal)
        if method == "POST" and len(rest) == 3 and rest[0] == "settings" and rest[2] == "rollback":
            principal.require(SCOPE_CONFIG)
            return self._settings_rollback(principal, rest[1], body, headers, correlation_id)
        if rest[:1] == ["sites"] and len(rest) >= 3:
            site_id = rest[1]
            self._check_site_id(site_id)
            tail = rest[2:]
            if method == "POST" and tail == ["jobs"]:
                principal.require(SCOPE_JOBS)
                return self._start_job(principal, site_id, body, headers, correlation_id)
            if method == "PATCH" and tail == ["settings"]:
                principal.require(SCOPE_CONFIG)
                return self._patch_settings(principal, site_id, body, headers, correlation_id)
            if method == "POST" and tail == ["cache", "invalidate"]:
                principal.require(SCOPE_CACHE)
                return self._invalidate_cache(principal, site_id, body, headers, correlation_id)
        raise ControlDenied(404, "not_found", "маршрут не найден")

    def _authenticate(self, headers: dict[str, str]) -> Principal:
        raw = str(headers.get("authorization") or "").strip()
        if not raw.lower().startswith("bearer "):
            raise ControlDenied(401, "unauthorized", "нужен заголовок Authorization: Bearer")
        token = raw[7:].strip()
        principal = self._principals.get(token)
        if principal is None:
            raise ControlDenied(401, "unauthorized", "токен не распознан")
        return principal

    def _rate_limit(
        self, principal: Principal, site_id: str, operation: str, *, mutating: bool = True
    ) -> None:
        """Списать разрешение по иерархии ключей.

        Ключи раздельные: среда, витрина, действующее лицо, операция. Общего
        счётчика на весь массив здесь нет намеренно — один шумный сайт не
        должен упирать в предел остальные.
        """
        решение = self._limiter.check(
            {
                "environment": self._env.get("SITE_ENGINE_ENVIRONMENT", "local"),
                "site": site_id,
                # Чтение и запись считаются в разные вёдра: ограничивать надо
                # то, что меняет состояние.
                ("actor" if mutating else "actor_read"): principal.token_id,
                # Витрина входит в ключ операции: без неё шум по одной витрине
                # выбирал бы операционное ведро сразу для всех остальных.
                ("operation" if mutating else "operation_read"): (
                    f"{principal.token_id}:{site_id or '-'}:{operation}" if operation else ""
                ),
            }
        )
        if решение.degraded:
            # Тихий переход в запасной режим не должен остаться незамеченным:
            # предел в нём строже, и вызывающий обязан узнать причину отказов.
            self._metrics.inc("site_engine_ratelimit_degraded_total")
        if not решение.allowed:
            self._metrics.inc("site_engine_control_refusals_total", code="rate_limited")
            raise ControlDenied(
                429, "rate_limited", "превышен предел частоты", **решение.as_error_extra()
            )

    def _check_site_id(self, site_id: str) -> None:
        if not SITE_ID_RE.match(site_id):
            raise ControlDenied(400, "invalid_site_id", "недопустимый идентификатор сайта")
        if not profile_path(site_id, self._root).exists():
            raise ControlDenied(404, "site_not_found", f"сайта {site_id} нет")

    # ---- операции -------------------------------------------------------

    def _start_job(
        self,
        principal: Principal,
        site_id: str,
        body: dict[str, Any],
        headers: dict[str, str],
        correlation_id: str,
    ) -> ApiResponse:
        self._require_manageable(site_id)
        action = str(body.get("action") or "").strip()
        environment = str(body.get("environment") or "staging").strip()
        dry_run = bool(body.get("dryRun"))
        if action not in ALLOWED_JOB_ACTIONS:
            raise ControlDenied(
                400,
                "invalid_action",
                "недопустимое действие",
                allowed=sorted(ALLOWED_JOB_ACTIONS),
            )
        if environment not in ALLOWED_ENVIRONMENTS:
            raise ControlDenied(
                400,
                "invalid_environment",
                "недопустимая среда",
                allowed=sorted(ALLOWED_ENVIRONMENTS),
            )

        if dry_run:
            return ApiResponse(
                status=200,
                body={
                    "dryRun": True,
                    "wouldEnqueue": {
                        "siteId": site_id,
                        "action": action,
                        "environment": environment,
                    },
                    "siteLocked": locks.is_locked(site_id, environment),
                },
            )

        try:
            with locks.site_lock(site_id, environment, timeout=2.0):
                item = queue.enqueue(
                    site_id,
                    action=action,
                    environment=environment,
                    traceparent=self._trace_context.header(),
                )
        except locks.LockBusy as exc:
            raise ControlDenied(409, "site_busy", "по сайту уже идёт операция") from exc
        except FileExistsError as exc:
            raise ControlDenied(409, "job_exists", "такое задание уже в очереди") from exc

        audit.record(
            job_id=item.job_id,
            site_id=site_id,
            environment=environment,
            action=f"control.job.{action}",
            target="queue",
            mutation=True,
            exit_code=0,
            extra={
                "correlation_id": correlation_id,
                "actor_token": principal.token_id,
                "trace_id": self._trace_context.trace_id,
            },
        )
        return ApiResponse(status=202, body={"job": item.as_dict(), "status": "queued"})

    def _job_result(self, job_id: str) -> ApiResponse | None:
        """Результат задания, если он записан. Очередь его не содержит."""
        from factory.site_engine.api import ops_view

        try:
            return ApiResponse(status=200, body=ops_view.job(self._root, job_id))
        except ops_view.OpsError:
            return None

    def _job_status(self, job_id: str) -> ApiResponse:
        if not re.match(r"^[A-Za-z0-9_.:-]{1,128}$", job_id):
            raise ControlDenied(400, "invalid_job_id", "недопустимый идентификатор задания")
        for stage in queue.STAGES:
            candidate = queue.stage_dir(stage) / f"{job_id}.json"
            if candidate.exists():
                data = json.loads(candidate.read_text(encoding="utf-8"))
                return ApiResponse(
                    status=200,
                    body={
                        "jobId": job_id,
                        "stage": stage,
                        "terminal": stage in {"done", "failed", "quarantine"},
                        "attempts": queue.attempts_of(candidate),
                        "job": data,
                    },
                )
        raise ControlDenied(404, "job_not_found", f"задания {job_id} нет")

    def _site_requests(
        self,
        method: str,
        tail: list[str],
        body: dict[str, Any],
        principal: Principal,
        correlation_id: str,
    ) -> ApiResponse:
        """Заявки на новую витрину. Мастер, сухой прогон — и ни одной мутации."""
        from factory.site_engine import site_plan, site_provision, site_request

        склад = site_request.SiteRequestStore(self._root)
        try:
            if method == "POST" and not tail:
                principal.require(SCOPE_SITES)
                заявка = склад.create(
                    str(body.get("siteId") or ""),
                    actor=_актор(principal),
                    now=self._время(),
                )
                self._audit_site_request("create", заявка, _актор(principal), correlation_id)
                return ApiResponse(status=201, body=заявка.as_dict())
            if method == "GET" and not tail:
                principal.require(SCOPE_READ)
                return ApiResponse(
                    status=200, body={"items": [з.as_dict() for з in склад.list()]}
                )
            if method == "GET" and len(tail) == 1:
                principal.require(SCOPE_READ)
                заявка = склад.get(tail[0])
                тело = заявка.as_dict()
                # План по требованию в том же ответе. Экран мастера показывает
                # заявку и план вместе; двумя запросами он тратил вдвое больше
                # разрешений частоты и на восьмом шаге упирался в предел —
                # страница при этом молча оказывалась пустой.
                if body.get("withPlan"):
                    тело["plan"] = site_plan.план(заявка, self._root, self._env)
                return ApiResponse(status=200, body=тело)
            if method == "GET" and tail[1:] == ["plan"]:
                principal.require(SCOPE_READ)
                заявка = склад.get(tail[0])
                return ApiResponse(
                    status=200, body=site_plan.план(заявка, self._root, self._env)
                )
            if method == "POST" and tail[1:] == ["approve"]:
                principal.require(SCOPE_SITES)
                заявка = site_provision.approve(
                    склад,
                    tail[0],
                    str(body.get("planHash") or ""),
                    self._root,
                    actor=_актор(principal),
                )
                self._audit_site_request("approve", заявка, _актор(principal), correlation_id)
                return ApiResponse(status=200, body=заявка.as_dict())
            if method == "POST" and tail[1:] == ["provision"]:
                principal.require(SCOPE_SITES)
                итог = site_provision.provision(
                    склад,
                    tail[0],
                    self._root,
                    actor=_актор(principal),
                    correlation_id=correlation_id,
                    now=self._время(),
                )
                return ApiResponse(status=200, body=итог)
            if method == "GET" and tail[1:] == ["verification"]:
                principal.require(SCOPE_READ)
                return ApiResponse(
                    status=200, body=site_provision.verification(склад, tail[0], self._root)
                )
            if method == "POST" and tail[1:] == ["publish"]:
                principal.require(SCOPE_SITES)
                return ApiResponse(
                    status=200, body=site_provision.publish(склад, tail[0], self._root)
                )
            if method == "POST" and tail[1:] == ["rollback"]:
                principal.require(SCOPE_SITES)
                итог = site_provision.rollback(
                    склад,
                    tail[0],
                    self._root,
                    actor=_актор(principal),
                    correlation_id=correlation_id,
                )
                return ApiResponse(status=200, body=итог)
            if method == "PATCH" and len(tail) == 1:
                principal.require(SCOPE_SITES)
                заявка = склад.answer(
                    tail[0], str(body.get("step") or ""), body.get("answers") or {}
                )
                self._audit_site_request(
                    f"answer.{body.get('step')}", заявка, _актор(principal), correlation_id
                )
                return ApiResponse(status=200, body=заявка.as_dict())
        except site_request.SiteRequestError as ошибка:
            raise ControlDenied(
                ошибка.status, ошибка.code, ошибка.message, field=ошибка.field
            ) from ошибка
        except site_provision.ProvisionError as ошибка:
            raise ControlDenied(
                ошибка.status, ошибка.code, ошибка.message, **ошибка.extra
            ) from ошибка
        raise ControlDenied(404, "not_found", "маршрут не найден")

    def _время(self) -> str:
        """Отметка времени создания заявки. Фиксируется один раз: план обязан
        быть детерминированным, а часы в момент показа плана меняются."""
        import time

        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def _audit_site_request(self, действие: str, заявка, актор: str, correlation_id: str) -> None:
        audit.record(
            job_id=correlation_id,
            site_id=заявка.site_id,
            environment="staging",
            action=f"control.site_request.{действие}",
            target=f"var/state/site-requests/{заявка.request_id}",
            mutation=True,
            exit_code=0,
            extra={
                "correlation_id": correlation_id,
                "actor": актор,
                "request_id": заявка.request_id,
                "next_step": заявка.next_step,
            },
        )

    def _settings_view(self, site_id: str, principal: Principal) -> ApiResponse:
        """Схема, значения, версия, ссылки на секреты и готовый откат."""
        from factory.site_engine import settings_view

        self._check_site_id(site_id)
        try:
            тело = settings_view.представление(
                site_id, self._root, can_write=SCOPE_CONFIG in principal.scopes
            )
        except settings_view.SettingsViewError as ошибка:
            raise ControlDenied(404, "site_not_found", str(ошибка)) from ошибка
        return ApiResponse(status=200, body=тело)

    def _settings_rollback(
        self,
        principal: Principal,
        site_id: str,
        body: dict[str, Any],
        headers: dict[str, str],
        correlation_id: str,
    ) -> ApiResponse:
        """Вернуть прежние значения последнего изменения настроек.

        Откат идёт тем же путём, что и обычное изменение: те же проверки, та же
        сверка версии, та же запись в журнал. Отдельный путь записи «только для
        отката» обошёл бы проверки ровно там, где ошибиться дороже всего.
        """
        from factory.site_engine import settings_view

        self._check_site_id(site_id)
        путь = profile_path(site_id, self._root)
        версия = config_version(путь)
        план = settings_view.откат(site_id, self._root, версия=версия)
        if not план.get("available"):
            raise ControlDenied(
                409,
                "rollback_unavailable",
                str(план.get("reason") or "откатывать нечего"),
            )
        return self._patch_settings(
            principal,
            site_id,
            {
                "changes": план["changes"],
                "remove": план.get("remove") or [],
                "expectedVersion": версия,
                "dryRun": bool(body.get("dryRun")),
                "rollback": True,
            },
            headers,
            correlation_id,
        )

    def _patch_settings(
        self,
        principal: Principal,
        site_id: str,
        body: dict[str, Any],
        headers: dict[str, str],
        correlation_id: str,
    ) -> ApiResponse:
        self._require_manageable(site_id)
        changes = body.get("changes")
        # Удаление настройки — отдельное поле, а не changes[key] = null. Null в
        # словаре изменений неотличим от «поставить пустое значение», и разница
        # между «убрать поле» и «записать null» стоила бы одного молчаливого
        # расхождения профиля со схемой.
        убрать = body.get("remove") or []
        if not isinstance(убрать, list) or not all(isinstance(к, str) for к in убрать):
            raise ControlDenied(400, "invalid_body", "remove — список имён настроек")
        чужие = [к for к in убрать if к not in SAFE_SETTINGS]
        if чужие:
            raise ControlDenied(
                422,
                "invalid_settings",
                "настройки не приняты",
                problems=[f"{к}: не входит в список изменяемых настроек" for к in чужие],
            )
        if not isinstance(changes, dict) or (not changes and not убрать):
            raise ControlDenied(400, "invalid_body", "нужен непустой объект changes")
        changes = changes if isinstance(changes, dict) else {}
        if len(changes) > MAX_BODY_KEYS:
            raise ControlDenied(
                400, "too_many_changes", f"не более {MAX_BODY_KEYS} настроек за запрос"
            )
        problems = _validate_settings(changes)
        if problems:
            raise ControlDenied(422, "invalid_settings", "настройки не приняты", problems=problems)

        target = profile_path(site_id, self._root)
        current_version = config_version(target)
        expected = str(body.get("expectedVersion") or "").strip()
        if expected and expected != current_version:
            # Конкурентная правка. Применить поверх значило бы потерять чужое
            # изменение и не сообщить об этом ни одной из сторон.
            raise ControlDenied(
                409,
                "version_conflict",
                "конфигурация изменилась с момента чтения",
                expected_version=expected,
                current_version=current_version,
            )

        before = json.loads(target.read_text(encoding="utf-8"))
        diff = _diff(before, changes)
        for ключ in убрать:
            if ключ in before:
                diff[ключ] = {"before": before[ключ], "after": None, "removed": True}
        dry_run = bool(body.get("dryRun"))

        if dry_run:
            return ApiResponse(
                status=200,
                body={
                    "dryRun": True,
                    "currentVersion": current_version,
                    "diff": diff,
                    "noop": not diff,
                },
            )

        if not diff:
            return ApiResponse(
                status=200,
                body={"applied": False, "noop": True, "version": current_version, "diff": {}},
            )

        after = dict(before)
        for ключ in убрать:
            after.pop(ключ, None)
        for field_name, value in changes.items():
            if isinstance(value, dict) and isinstance(before.get(field_name), dict):
                after[field_name] = {**before[field_name], **value}
            else:
                after[field_name] = value

        try:
            with locks.site_lock(site_id, "staging", timeout=2.0):
                # Повторная сверка под блокировкой: между чтением версии и
                # захватом замка файл мог измениться.
                if config_version(target) != current_version:
                    raise ControlDenied(
                        409, "version_conflict", "конфигурация изменилась во время применения"
                    )
                tmp = target.with_suffix(".json.tmp")
                tmp.write_text(
                    json.dumps(after, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
                tmp.replace(target)
        except locks.LockBusy as exc:
            raise ControlDenied(409, "site_busy", "по сайту уже идёт операция") from exc
        except OSError as exc:
            # Каталог профилей может быть намеренно закрыт на запись. Падение с
            # 500 выглядело бы как поломка службы; на деле это её граница прав,
            # и оператору полезнее увидеть причину, чем внутреннюю ошибку.
            raise ControlDenied(
                503,
                "config_read_only",
                "настройки витрин недоступны для записи этой службе",
                reason=exc.strerror or "",
            ) from exc

        new_version = config_version(target)
        audit.record(
            job_id=correlation_id,
            site_id=site_id,
            environment="staging",
            action="control.settings.patch",
            target=str(target.relative_to(self._root)),
            mutation=True,
            exit_code=0,
            extra={
                "correlation_id": correlation_id,
                "actor_token": principal.token_id,
                "trace_id": self._trace_context.trace_id,
                "diff": diff,
                "version_before": current_version,
                "version_after": new_version,
            },
        )
        return ApiResponse(
            status=200,
            body={
                "applied": True,
                "diff": diff,
                "previousVersion": current_version,
                "version": new_version,
            },
        )

    def _invalidate_cache(
        self,
        principal: Principal,
        site_id: str,
        body: dict[str, Any],
        headers: dict[str, str],
        correlation_id: str,
    ) -> ApiResponse:
        self._require_manageable(site_id)
        scope = str(body.get("scope") or "").strip()
        allowed_scopes = {"homepage", "title", "shelves", "catalog"}
        if scope not in allowed_scopes:
            raise ControlDenied(
                400,
                "invalid_scope",
                "недопустимая область инвалидации",
                allowed=sorted(allowed_scopes),
            )
        keys = body.get("keys") or []
        if not isinstance(keys, list) or any(not isinstance(k, str) or not k for k in keys):
            raise ControlDenied(400, "invalid_keys", "keys должен быть списком непустых строк")
        негодные = [k for k in keys if not CACHE_KEY_RE.match(k)]
        if негодные:
            raise ControlDenied(
                400,
                "invalid_keys",
                "ключ кэша должен быть идентификатором, а не адресом",
                rejected=негодные[:5],
            )
        if len(keys) > 100:
            raise ControlDenied(400, "too_many_keys", "не более 100 ключей за запрос")
        if scope == "title" and not keys:
            # Пустой список при точечной области — это «сбрось всё» под видом
            # точечной операции. Такой запрос почти всегда ошибка вызывающего.
            raise ControlDenied(400, "keys_required", "для области title нужен непустой keys")

        plan = {"siteId": site_id, "scope": scope, "keys": keys}
        if bool(body.get("dryRun")):
            return ApiResponse(status=200, body={"dryRun": True, "wouldInvalidate": plan})

        job_id = f"{site_id}-cache-{scope}-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"
        try:
            item = queue.enqueue(
                site_id,
                action="invalidate",
                environment="staging",
                job_id=job_id,
                traceparent=self._trace_context.header(),
            )
        except FileExistsError as exc:
            raise ControlDenied(409, "job_exists", "такая инвалидация уже запланирована") from exc
        audit.record(
            job_id=item.job_id,
            site_id=site_id,
            environment="staging",
            action="control.cache.invalidate",
            target=scope,
            mutation=True,
            exit_code=0,
            extra={
                "correlation_id": correlation_id,
                "actor_token": principal.token_id,
                "trace_id": self._trace_context.trace_id,
                "keys": keys,
            },
        )
        return ApiResponse(status=202, body={"job": item.as_dict(), "invalidate": plan})

    def _load_profile_raw(self, site_id: str) -> dict[str, Any] | None:
        """Содержимое профиля или None, если прочитать не удалось.

        Отличать «не прочитан» от «пустой» обязательно: пустой словарь означает
        «контракт не объявлен», то есть управляемо по обратной совместимости.
        Нечитаемый профиль означает «состояние неизвестно» — управлять витриной
        в этом случае значит менять то, чего не видишь.
        """
        path = profile_path(site_id, self._root)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None

    def _compatibility_of(self, site_id: str) -> compat.Compatibility:
        raw = self._load_profile_raw(site_id)
        if raw is None:
            return compat.Compatibility(
                compat.STATE_INCOMPATIBLE,
                compat.ENGINE_CONTRACT,
                None,
                "профиль витрины не прочитан или не является объектом JSON",
            )
        return compat.evaluate(raw)

    def _require_manageable(self, site_id: str) -> None:
        """Витрину под чужим старшим контрактом менять нельзя.

        Правка конфигурации под контракт, которого движок не реализует, делает
        витрину хуже, а не лучше: настройка применится, а поведение окажется
        не тем, которого ждал автор профиля.
        """
        state = self._compatibility_of(site_id)
        if not state.manageable:
            raise ControlDenied(
                409,
                "incompatible_contract",
                "витрина несовместима с версией движка",
                **state.as_dict(),
            )

    def _content_health(self, site_id: str | None, body: dict[str, Any]) -> ApiResponse:
        """Покрытие воспроизведения и причины его отсутствия.

        Без витрины — сводка по массиву. С витриной — она же плюс проблемные
        карточки с указанием звена и способа устранения: диагноз без списка
        пострадавших не даёт оператору куда смотреть.
        """
        if site_id is None:
            return ApiResponse(status=200, body=content_health.сводка(self._root, env=self._env))
        self._check_site_id_soft(site_id)
        свод = content_health.сводка(self._root, site=site_id, env=self._env)
        код = body.get("reason")
        предел = body.get("limit", 50)
        if not isinstance(предел, int) or isinstance(предел, bool) or not (1 <= предел <= 500):
            raise ControlDenied(400, "invalid_limit", "limit — целое от 1 до 500")
        детали = content_health.проблемные(
            self._root, site_id, code=код, limit=предел, env=self._env
        )
        return ApiResponse(status=200, body={**свод, "problems": детали})

    def _check_site_id_soft(self, site_id: str) -> None:
        """Проверка идентификатора без требования профиля.

        Витрины Lords живут в кэше каталога, а не в config/site-profiles, и
        требовать профиль здесь значило бы закрыть диагностику именно там, где
        она нужнее всего.
        """
        if not SITE_ID_RE.match(site_id):
            raise ControlDenied(400, "invalid_site_id", "недопустимый идентификатор витрины")

    def _trace(self, trace_id: str) -> ApiResponse:
        """Путь запроса по его идентификатору.

        Отрезки без способа их собрать — это данные, которых никто не читает.
        Здесь они собираются в цепочку с длительностями по звеньям.
        """
        отрезки = self._tracer.read_trace(trace_id)
        if not отрезки:
            raise ControlDenied(
                404, "trace_not_found", "след не найден: возможно, запрос не попал в выборку"
            )
        return ApiResponse(
            status=200,
            body={
                "traceId": trace_id,
                "spans": отрезки,
                "total": len(отрезки),
                "durationMs": round(sum(s.get("duration_ms", 0) for s in отрезки), 2),
            },
        )

    def _compatibility(self, site_id: str | None) -> ApiResponse:
        if site_id is not None:
            self._check_site_id(site_id)
            return ApiResponse(
                status=200, body={"siteId": site_id, **self._compatibility_of(site_id).as_dict()}
            )
        directory = self._root / "config" / "site-profiles"
        rows = []
        for path in sorted(directory.glob("*.json")) if directory.is_dir() else []:
            raw = self._load_profile_raw(path.stem)
            state = self._compatibility_of(path.stem)
            rows.append(
                {"siteId": path.stem, "siteType": (raw or {}).get("site_type"), **state.as_dict()}
            )
        by_state: dict[str, int] = {}
        for row in rows:
            by_state[row["state"]] = by_state.get(row["state"], 0) + 1
        return ApiResponse(
            status=200,
            body={
                "engine": compat.ENGINE_CONTRACT,
                "sites": rows,
                "total": len(rows),
                "byState": by_state,
                "manageable": sum(1 for r in rows if r["manageable"]),
            },
        )

    # ------------------------------------------------------------------
    # Каталог
    # ------------------------------------------------------------------
    def _content_route(
        self, method: str, tail: list[str], body: dict[str, Any], principal
    ) -> ApiResponse:
        """Просмотр каталога. Отбор выполняется здесь, а не в браузере."""
        from factory.site_engine.api import content_browse

        principal.require(SCOPE_READ)
        try:
            if method == "GET" and not tail:
                return ApiResponse(
                    status=200,
                    body=content_browse.список(
                        self._root,
                        site_id=self._опция(body, "siteId"),
                        env=self._env,
                        q=self._опция(body, "q"),
                        kind=self._опция(body, "kind"),
                        reason=self._опция(body, "reason"),
                        sort=self._опция(body, "sort") or "externalId",
                        desc=bool(body.get("desc")),
                        offset=self._целое(body, "offset", 0, 0, 10**6),
                        limit=self._целое(
                            body, "limit", content_browse.DEFAULT_LIMIT, 1, content_browse.MAX_LIMIT
                        ),
                    ),
                )
            if method == "GET" and len(tail) == 2:
                return ApiResponse(
                    status=200,
                    body=content_browse.карточка(
                        self._root, site_id=tail[0], external_id=tail[1], env=self._env
                    ),
                )
        except content_browse.ContentError as ошибка:
            код = 404 if "нет" in str(ошибка) else 400
            raise ControlDenied(код, "content_error", str(ошибка)) from ошибка
        raise ControlDenied(404, "not_found", "маршрут не найден")

    # ------------------------------------------------------------------
    # Операторы
    # ------------------------------------------------------------------
    def _directory(self):
        from factory.site_engine.operators import OperatorDirectory

        return OperatorDirectory(self._root)

    def _operators_route(
        self,
        method: str,
        tail: list[str],
        body: dict[str, Any],
        principal,
        headers: dict[str, str],
        correlation_id: str,
    ) -> ApiResponse:
        """Каталог операторов.

        Чтение списка требует read: знать, кто имеет доступ, полезно всем, кто
        и так внутри. Любое изменение требует operators:write — права, которое
        позволяет выдать любое другое право, и потому есть только у admin.
        """
        from factory.site_engine.operators import OperatorError

        каталог = self._directory()
        актор = _актор(principal)
        актор_id = str(body.get("actorOperatorId") or "")
        try:
            if method == "GET" and not tail:
                principal.require(SCOPE_READ)
                return ApiResponse(
                    status=200,
                    body=каталог.list(
                        state=self._опция(body, "state"),
                        role=self._опция(body, "role"),
                        offset=self._целое(body, "offset", 0, 0, 100000),
                        limit=self._целое(body, "limit", 50, 1, 200),
                    ),
                )
            if method == "GET" and tail == ["invites"]:
                principal.require(SCOPE_OPERATORS)
                return ApiResponse(status=200, body={"items": каталог.list_invites()})
            if method == "GET" and tail == ["sessions"]:
                principal.require(SCOPE_OPERATORS)
                # Сессия отдаётся с адресом и ролями владельца. Один только
                # идентификатор оператора делает отзыв неосмысленным: решение
                # «отозвать эту сессию» принимают, зная чью, а сверять хэши
                # глазами по второму списку никто не станет.
                строки = каталог.list_sessions(
                    operator_id=self._опция(body, "operatorId"),
                    active_only=body.get("activeOnly", True) is not False,
                )
                for строка in строки:
                    try:
                        владелец = каталог.get(строка.get("operatorId", ""))
                    except OperatorError:
                        строка["email"] = ""
                        строка["roles"] = []
                        строка["ownerState"] = "UNKNOWN"
                        continue
                    строка["email"] = владелец.email
                    строка["roles"] = list(владелец.roles)
                    строка["ownerState"] = владелец.state
                return ApiResponse(status=200, body={"items": строки})
            if method == "POST" and tail == ["invites"]:
                principal.require(SCOPE_OPERATORS)
                приглашение, секрет = каталог.invite(
                    email=str(body.get("email") or ""),
                    roles=body.get("roles") or [],
                    created_by=актор,
                )
                self._audit_operators("invite", приглашение.email, актор, correlation_id)
                # Секрет возвращается ровно один раз и в журнал не попадает.
                return ApiResponse(status=201, body={**приглашение.as_dict(), "secret": секрет})
            if method == "POST" and len(tail) == 2 and tail[0] == "invites":
                principal.require(SCOPE_OPERATORS)
                if tail[1] == "accept":
                    оператор = каталог.accept_invite(
                        secret=str(body.get("secret") or ""),
                        password=str(body.get("password") or ""),
                    )
                    self._audit_operators("accept", оператор.email, оператор.email, correlation_id)
                    return ApiResponse(status=200, body=оператор.as_dict())
                итог = каталог.revoke_invite(tail[1], actor=актор)
                self._audit_operators("revoke_invite", итог.get("email", ""), актор, correlation_id)
                return ApiResponse(status=200, body=итог)
            # Проверяется РАНЬШЕ общей ветки из двух частей: иначе "sessions"
            # разбирается как идентификатор оператора, "revoke" — как неизвестное
            # действие, и маршрут отвечает «не найдено». Поймано проверкой
            # соответствия описания и обслуживаемых маршрутов.
            if method == "POST" and tail == ["sessions", "revoke"]:
                principal.require(SCOPE_OPERATORS)
                ок = каталог.revoke_session(str(body.get("sessionId") or ""), actor=актор)
                self._audit_operators(
                    "revoke_session", str(body.get("sessionId") or ""), актор, correlation_id
                )
                return ApiResponse(status=200 if ок else 404, body={"revoked": ок})
            if method == "POST" and len(tail) == 2:
                principal.require(SCOPE_OPERATORS)
                оператор_id, действие = tail
                if действие == "roles":
                    итог = каталог.set_roles(
                        оператор_id,
                        body.get("roles") or [],
                        actor_id=актор_id,
                        actor_roles=body.get("actorRoles") or [],
                    )
                elif действие == "block":
                    итог = каталог.block(
                        оператор_id, reason=str(body.get("reason") or ""), actor_id=актор_id
                    )
                elif действие == "unblock":
                    итог = каталог.unblock(оператор_id)
                elif действие == "delete":
                    итог = каталог.delete(оператор_id, actor_id=актор_id)
                elif действие == "revoke-sessions":
                    сколько = каталог.revoke_all_sessions(оператор_id, actor=актор)
                    self._audit_operators("revoke_sessions", оператор_id, актор, correlation_id)
                    return ApiResponse(status=200, body={"revoked": сколько})
                elif действие == "mfa-enroll":
                    return ApiResponse(status=200, body=каталог.start_mfa_enrollment(оператор_id))
                else:
                    raise ControlDenied(404, "not_found", "маршрут не найден")
                self._audit_operators(действие, итог.email, актор, correlation_id)
                return ApiResponse(status=200, body=итог.as_dict())
        except OperatorError as ошибка:
            текст = str(ошибка)
            код = 409 if ("последний" in текст or "уже" in текст or "нельзя" in текст) else 400
            raise ControlDenied(код, "operator_conflict", текст) from ошибка
        raise ControlDenied(404, "not_found", "маршрут не найден")

    def _audit_operators(self, действие: str, цель: str, актор: str, correlation_id: str) -> None:
        audit.record(
            job_id=f"operators-{действие}",
            site_id="",
            environment="control",
            action=f"operators_{действие}",
            target=цель,
            exit_code=0,
            output="",
            mutation=True,
            extra={"correlationId": correlation_id, "actor": актор},
        )

    # ------------------------------------------------------------------
    # Очередь разбора
    # ------------------------------------------------------------------
    def _review(self):
        from factory.site_engine.review_queue import ReviewQueue

        return ReviewQueue(self._root)

    def _review_route(
        self,
        method: str,
        tail: list[str],
        body: dict[str, Any],
        principal,
        headers: dict[str, str],
        correlation_id: str,
    ) -> ApiResponse:
        """Маршруты очереди. Чтение и решение разведены по правам.

        Решение — изменяющая операция, и она обязана нести версию записи:
        без неё два редактора перезапишут решение друг друга, и второй даже
        не узнает, что было первое.
        """
        from factory.site_engine.review_queue import ReviewError

        очередь = self._review()
        try:
            if method == "GET" and not tail:
                principal.require(SCOPE_READ)
                return ApiResponse(
                    status=200,
                    body=очередь.list(
                        state=self._опция(body, "state"),
                        site_id=self._опция(body, "siteId"),
                        conflict_code=self._опция(body, "conflictCode"),
                        query=self._опция(body, "q"),
                        offset=self._целое(body, "offset", 0, 0, 100000),
                        limit=self._целое(body, "limit", 50, 1, 200),
                    ),
                )
            if method == "GET" and len(tail) == 1:
                principal.require(SCOPE_READ)
                return ApiResponse(status=200, body=очередь.get(tail[0]).as_dict())
            if method == "GET" and len(tail) == 2 and tail[1] == "preview":
                principal.require(SCOPE_READ)
                return ApiResponse(status=200, body=очередь.preview(tail[0]))
            if method == "POST" and tail == ["batch"]:
                return self._review_batch(body, principal, headers, correlation_id)
            if method == "POST" and len(tail) == 2:
                principal.require(SCOPE_REVIEW)
                действие = tail[1]
                актор = _актор(principal)
                if действие in ("approve", "publish", "unpublish"):
                    вызов = {
                        "approve": очередь.approve,
                        "publish": очередь.publish,
                        "unpublish": очередь.unpublish,
                    }[действие]
                    если_версия = self._целое(body, "expectedVersion", None, 1, 10**9)
                    итог = (
                        вызов(
                            tail[0],
                            actor=актор,
                            expected_version=если_версия,
                            note=str(body.get("note") or ""),
                        )
                        if действие == "approve"
                        else вызов(tail[0], actor=актор, expected_version=если_версия)
                        if действие == "publish"
                        else вызов(tail[0], actor=актор, note=str(body.get("note") or ""))
                    )
                elif действие == "claim":
                    итог = очередь.claim(tail[0], actor=актор)
                elif действие == "decide":
                    итог = очередь.decide(
                        tail[0],
                        value=str(body.get("value") or ""),
                        actor=актор,
                        note=str(body.get("note") or ""),
                        expected_version=self._целое(body, "expectedVersion", None, 1, 10**9),
                        dismiss=bool(body.get("dismiss")),
                    )
                elif действие == "revert":
                    итог = очередь.revert(tail[0], actor=актор, note=str(body.get("note") or ""))
                else:
                    raise ControlDenied(404, "not_found", "маршрут не найден")
                self._audit_review(действие, итог, актор, correlation_id)
                return ApiResponse(status=200, body=итог.as_dict())
        except ReviewError as ошибка:
            # Конфликт версии и негодное значение — это 409 и 400, а не 500:
            # оператор обязан увидеть, что именно не так, а не «ошибку сервера».
            текст = str(ошибка)
            # Конфликт СОСТОЯНИЯ — это 409: запрос корректен, но запись сейчас
            # в другом состоянии. 400 сказал бы «вы прислали ерунду», и
            # оператор искал бы ошибку в своей форме.
            конфликт = any(
                слово in текст
                for слово in ("версия", "изменил", "нельзя", "только", "нечего", "уже")
            )
            код = 409 if конфликт else 400
            raise ControlDenied(код, "review_conflict", str(ошибка)) from ошибка
        raise ControlDenied(404, "not_found", "маршрут не найден")

    def _review_batch(
        self, body: dict[str, Any], principal, headers: dict[str, str], correlation_id: str
    ) -> ApiResponse:
        """Групповое действие. Сухой прогон доступен по чтению, изменение — нет."""
        режим = str(body.get("mode") or "dryRun")
        очередь = self._review()
        актор = _актор(principal)
        if режим == "dryRun":
            principal.require(SCOPE_READ)
            return ApiResponse(
                status=200,
                body=очередь.batch_preview(
                    conflict_code=str(body.get("conflictCode") or ""),
                    from_value=str(body.get("fromValue") or ""),
                    to_value=str(body.get("toValue") or ""),
                    site_id=self._опция(body, "siteId"),
                    sample=self._целое(body, "sample", 5, 0, 50),
                ),
            )
        principal.require(SCOPE_REVIEW)
        if режим == "apply":
            итог = очередь.batch_apply(
                conflict_code=str(body.get("conflictCode") or ""),
                from_value=str(body.get("fromValue") or ""),
                to_value=str(body.get("toValue") or ""),
                actor=актор,
                expected_fingerprint=str(body.get("expectedFingerprint") or ""),
                site_id=self._опция(body, "siteId"),
                note=str(body.get("note") or ""),
            )
        elif режим == "publish":
            итог = очередь.batch_publish(batch_id=str(body.get("batchId") or ""), actor=актор)
        elif режим == "revert":
            итог = очередь.batch_revert(batch_id=str(body.get("batchId") or ""), actor=актор)
        else:
            raise ControlDenied(400, "invalid_mode", "mode — dryRun, apply или revert")
        audit.record(
            job_id=f"review-batch-{итог.get('batchId', '')}",
            site_id=self._опция(body, "siteId"),
            environment="control",
            action=f"review_batch_{режим}",
            target="review-queue",
            exit_code=0,
            output=json.dumps(
                {k: v for k, v in итог.items() if k != "itemIds"}, ensure_ascii=False
            ),
            mutation=True,
            extra={"correlationId": correlation_id, "actor": актор},
        )
        return ApiResponse(status=200, body=итог)

    def _audit_review(self, действие: str, итог, актор: str, correlation_id: str) -> None:
        audit.record(
            job_id=f"review-{итог.item_id}",
            site_id=итог.site_id,
            environment="control",
            action=f"review_{действие}",
            target=итог.internal_entity_id,
            exit_code=0,
            output=f"{итог.state.value} {итог.decided_value}".strip(),
            mutation=True,
            extra={"correlationId": correlation_id, "actor": актор, "version": итог.version},
        )

    @staticmethod
    def _опция(body: dict[str, Any], имя: str) -> str:
        значение = body.get(имя)
        return str(значение).strip() if значение is not None else ""

    @staticmethod
    def _целое(body: dict[str, Any], имя: str, по_умолчанию, низ: int, верх: int):
        значение = body.get(имя, по_умолчанию)
        if значение is None:
            return по_умолчанию
        if not isinstance(значение, int) or isinstance(значение, bool):
            raise ControlDenied(400, "invalid_value", f"{имя} — целое число")
        if not (низ <= значение <= верх):
            raise ControlDenied(400, "invalid_value", f"{имя} — целое от {низ} до {верх}")
        return значение

    def _playback_policy(self) -> ApiResponse:
        """Действующий перечень идентификаторов и состояние флагов.

        Отдаётся отдельным маршрутом, потому что вопрос «почему у этой карточки
        нет видео» на массиве в пятьдесят тысяч записей чаще всего оказывается
        вопросом «что сейчас разрешено», и выяснять это чтением файлов на
        рабочем узле — самый долгий способ.
        """
        from factory.site_engine import playback_policy

        try:
            решение = playback_policy.resolve_cached(root=self._root)
        except playback_policy.PlaybackPolicyError as ошибка:
            # Противоречивая настройка — это состояние, о котором обязан узнать
            # оператор, а не отсутствующий маршрут.
            return ApiResponse(
                status=409,
                body={"error": {"code": "playback_policy_conflict", "message": str(ошибка)}},
            )
        тело = решение.as_dict()
        тело["flags"] = self._playback_flags()
        return ApiResponse(status=200, body=тело)

    def _playback_flags(self) -> list[dict[str, Any]]:
        """Флаги отдаются без содержимого записей авторизации.

        Наружу уходит только факт наличия разрешения и его статус: сами
        доказательства могут содержать переписку и реквизиты договора.
        """
        import yaml

        путь = self._root / "config" / "playback-identifiers.yaml"
        if not путь.exists():
            return []
        try:
            данные = yaml.safe_load(путь.read_text(encoding="utf-8")) or {}
        except Exception:  # noqa: BLE001
            return []
        поставщики = данные.get("providers")
        if not isinstance(поставщики, dict):
            return []
        строки: list[dict[str, Any]] = []
        for поставщик, описание in поставщики.items():
            записи = (описание or {}).get("identifiers")
            if not isinstance(записи, dict):
                continue
            for имя, запись in записи.items():
                if not isinstance(запись, dict):
                    continue
                авторизация = запись.get("authorization")
                строки.append(
                    {
                        "provider": поставщик,
                        "identifier": имя,
                        "enabled": bool(запись.get("enabled")),
                        "flag": запись.get("flag"),
                        "authorization": (
                            авторизация.get("status")
                            if isinstance(авторизация, dict)
                            else "baseline"
                        ),
                    }
                )
        return строки

    def _metrics_response(self) -> ApiResponse:
        """Показатели собираются в момент опроса, а не накапливаются.

        Очередь и состав витрин — состояние на диске: держать их копию в памяти
        значит однажды отдать устаревшую.
        """
        gauges: dict[str, list[tuple[dict[str, str], Any]]] = {}
        try:
            counts = queue.counts()
            gauges["site_engine_queue_items"] = [
                ({"stage": stage}, counts.get(stage, 0)) for stage in queue.STAGES
            ]
        except OSError:
            # Недоступная очередь не должна ронять опрос метрик: система сбора
            # получит остальные показатели и заметит пропажу этого.
            pass
        profiles = self._root / "config" / "site-profiles"
        if profiles.is_dir():
            gauges["site_engine_sites"] = [({}, len(list(profiles.glob("*.json"))))]
        try:
            from factory.site_engine import playback_policy

            решение = playback_policy.resolve_cached(root=self._root)
            gauges["site_engine_playback_identifiers_allowed"] = [
                ({"identifier": имя}, 1 if имя in решение.allowed else 0)
                for имя in sorted(set(решение.baseline) | set(решение.allowed))
            ]
            gauges["site_engine_playback_identifier_flags"] = [
                (
                    {
                        "identifier": строка["identifier"],
                        "authorization": str(строка["authorization"]),
                    },
                    1 if строка["enabled"] else 0,
                )
                for строка in self._playback_flags()
                if строка["flag"]
            ]
        except Exception:  # noqa: BLE001
            # Противоречивая настройка видна на своём маршруте; ронять опрос
            # метрик из-за неё значит потерять и все остальные показатели.
            pass
        for name, source in self._gauges.items():
            try:
                gauges[name] = source()
            except Exception:  # noqa: BLE001
                continue
        text = self._metrics.render(gauges)
        return ApiResponse(
            status=200, body={"prometheus": text, "counters": self._metrics.snapshot()}
        )

    #: Исходы, по которым можно отбирать. Замкнутый набор: «error» и «ошибка»
    #: как разные значения одного отбора однажды дадут два разных ответа на
    #: один вопрос.
    ИСХОДЫ = ("ok", "error")

    @staticmethod
    def _актор_записи(запись: dict[str, Any]) -> str:
        """Кто действовал. Панель кладёт имя в extra, ядро — в поле actor."""
        дополнительно = запись.get("extra") or {}
        return str(дополнительно.get("actor") or запись.get("actor") or "")

    def _audit_trail(self, body: dict[str, Any], headers: dict[str, str]) -> ApiResponse:
        """Журнал с отбором. Общее число не зависит от отбора — это разные числа.

        `total` отвечает «сколько записей есть», `matched` — «сколько подошло».
        Одно число на оба вопроса превращает пустой отбор в «записей нет».
        """
        limit = body.get("limit", 50)
        if not isinstance(limit, int) or isinstance(limit, bool) or not (1 <= limit <= 500):
            raise ControlDenied(400, "invalid_limit", "limit — целое от 1 до 500")
        offset = body.get("offset", 0)
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            raise ControlDenied(400, "invalid_offset", "offset — целое от 0")
        исход = str(body.get("result") or "").strip()
        if исход and исход not in self.ИСХОДЫ:
            raise ControlDenied(
                400,
                "invalid_result",
                f"result — одно из {', '.join(self.ИСХОДЫ)}",
                field="result",
            )

        site_id = self._опция(body, "siteId")
        актор = self._опция(body, "actor")
        действие = self._опция(body, "action")
        связь = self._опция(body, "correlationId")
        цель = self._опция(body, "target")
        с = self._опция(body, "since")
        по = self._опция(body, "until")

        все = audit.read_all()
        подошли = []
        for запись in все:
            if site_id and запись.get("site_id") != site_id:
                continue
            if актор and self._актор_записи(запись) != актор:
                continue
            # Действие отбирается по началу имени: «control.settings» обязано
            # находить и patch, и будущие control.settings.*. Точное совпадение
            # заставляло бы помнить полный список действий наизусть.
            if действие and not str(запись.get("action") or "").startswith(действие):
                continue
            if цель and цель not in str(запись.get("target") or ""):
                continue
            if связь and (запись.get("extra") or {}).get("correlation_id") != связь:
                continue
            код = запись.get("exit_code")
            if исход == "ok" and not (код == 0 or код is None):
                continue
            if исход == "error" and (код == 0 or код is None):
                continue
            отметка = str(запись.get("ts") or "")
            if с and отметка < с:
                continue
            if по and отметка > по:
                continue
            подошли.append(запись)

        окно = подошли[::-1][offset : offset + limit]
        return ApiResponse(
            status=200,
            body={
                "entries": окно,
                "matched": len(подошли),
                "total": len(все),
                "offset": offset,
                "limit": limit,
                "filters": {
                    k: v
                    for k, v in (
                        ("siteId", site_id),
                        ("actor", актор),
                        ("action", действие),
                        ("target", цель),
                        ("correlationId", связь),
                        ("result", исход),
                        ("since", с),
                        ("until", по),
                    )
                    if v
                },
            },
        )

    def _audit_refusal(
        self,
        denied: ControlDenied,
        method: str,
        path: str,
        headers: dict[str, str],
        correlation_id: str,
    ) -> None:
        """Отказы тоже попадают в журнал.

        Журнал, где видны только удачные операции, отвечает на вопрос «что
        изменилось», но не на вопрос «кто пытался». Второй вопрос задают ровно
        тогда, когда он уже важен.
        """
        if denied.status in {404} and denied.code == "not_found":
            return
        try:
            raw = str(headers.get("authorization") or "")
            token = raw[7:].strip() if raw.lower().startswith("bearer ") else ""
            audit.record(
                job_id=correlation_id,
                site_id="-",
                environment="-",
                action=f"control.denied.{denied.code}",
                target=f"{method} {path}",
                mutation=False,
                exit_code=denied.status,
                extra={
                    "correlation_id": correlation_id,
                    "actor_token": _token_id(token) if token else "anonymous",
                },
            )
        except Exception:
            # Невозможность записать отказ не должна превращать отказ в сбой.
            pass
