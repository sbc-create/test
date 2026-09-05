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

API_VERSION = "v1"

# Право на чтение отделено от права на запись, а запись — по областям. Один
# токен для всего означает, что задача «дай Qwen перезапускать индексацию»
# незаметно выдаёт и право переписать конфигурацию.
SCOPE_READ = "read"
SCOPE_JOBS = "jobs:write"
SCOPE_CONFIG = "config:write"
SCOPE_CACHE = "cache:write"
SCOPE_AUDIT = "audit:read"
KNOWN_SCOPES = frozenset({SCOPE_READ, SCOPE_JOBS, SCOPE_CONFIG, SCOPE_CACHE, SCOPE_AUDIT})

# Действия, которые разрешено ставить в очередь. Список закрытый: очередь
# исполняет то, что в ней лежит, поэтому свободное поле action означало бы
# выполнение произвольного действия по HTTP.
ALLOWED_JOB_ACTIONS = frozenset({"reindex", "refresh", "enrich", "verify"})
ALLOWED_ENVIRONMENTS = frozenset({"staging", "production"})

# Обратимые настройки ядра: у каждой — проверка диапазона, а не только типа.
# Проверка типа пропускает keep_releases=0, после которого откатываться некуда.
SAFE_SETTINGS: dict[str, dict[str, Any]] = {
    "keep_releases": {"type": int, "min": 2, "max": 20},
    "cache_policy": {"type": dict, "value_type": int, "min": 0, "max": 86_400},
    "feature_flags": {"type": dict, "value_type": bool},
}

# Отклоняются намеренно — с указанием причины в ответе, чтобы вызывающий понял,
# что это правило, а не пробел в реализации.
REFUSED_SETTINGS: dict[str, str] = {
    "domains": "смена доменов требует выкладки и проверки сертификатов",
    "canonical_host": "смена канонического хоста меняет индексацию всего сайта",
    "site_type": "тип сайта определяет адаптеры и хранилище",
    "indexing_enabled": "отключение индексации замечают через недели по падению трафика",
    "seo_enabled": "SEO-слой принадлежит другому потоку и меняется через него",
    "locale": "локаль меняет весь отрендеренный контент",
    "timezone": "часовой пояс меняет расписания и отметки времени",
    "theme": "оформление принадлежит потоку шаблонов",
    "render_mode": "режим рендеринга меняется вместе с выкладкой",
}

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


def writes_enabled(env: dict[str, str] | None = None) -> bool:
    """Запись выключена по умолчанию и включается отдельно от чтения."""
    env = env if env is not None else {}
    return str(env.get("SITE_ENGINE_CONTROL_WRITES", "")).strip().lower() in {"1", "true", "yes", "on"}


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


def profile_path(site_id: str, root: Path) -> Path:
    return root / "config" / "site-profiles" / f"{site_id}.json"


def config_version(path: Path) -> str:
    """Версия конфигурации — хэш её содержимого.

    Хэш, а не отметка времени: время меняется при копировании файла, содержимое —
    только при правке. Сверка по времени пропустила бы конкурентную запись.
    """
    if not path.exists():
        return "absent"
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()[:32]


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
                problems.append(f"{key}: допустимо от {rule['min']} до {rule['max']}, получено {value}")
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

    def __init__(self, tracer, context, *, name: str, service: str,
                 method: str, path: str, started: float, now) -> None:
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
            self._context, None, self._name,
            {"method": self._method, "path_template": path_template(self._path),
             "status": status, "outcome": "ok" if status < 400 else "error"},
            self._started, float(self._now()), service=self._service)
        self._tracer.record(отрезок)


def _завершённый_отрезок(контекст, родитель, имя, атрибуты, начало, конец,
                         service: str = "control-api"):
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
        self._idempotency = idempotency if idempotency is not None else IdempotencyStore(
            состояние, now=now)
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

    def begin_client_operation(self, method: str, path: str, *, service: str,
                               mutating: bool) -> ClientOperation:
        """Начать операцию внешнего слоя.

        Возвращается объект с заголовками для последующих вызовов и способом
        закрыть отрезок. Внешнему слою не нужно знать ни формата контекста, ни
        устройства трассировщика.
        """
        контекст = new_context(
            sampled=self._tracer.should_sample(mutating=mutating, failed=False))
        return ClientOperation(self._tracer, контекст, name=f"{service}.request",
                               service=service, method=method, path=path,
                               started=float(self._now()), now=self._now)

    def principal_for(self, token: str) -> Principal | None:
        """Права токена — для вызывающих внутри процесса.

        Нужен админке, чтобы не показывать кнопки, которых всё равно не
        позволит конвейер. Показ и запрет — разные вещи: запрет остаётся здесь.
        """
        return self._principals.get(token)

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
        correlation_id = str(headers.get("x-correlation-id") or "").strip() or self._new_correlation_id()
        # Контекст следа продолжается, если пришёл, и начинается, если нет.
        родитель = parse_traceparent(headers.get(TRACEPARENT))
        изменяющий = method.upper() in {"POST", "PATCH", "PUT", "DELETE"}
        if родитель is not None:
            контекст = родитель.child()
        else:
            контекст = new_context(
                sampled=self._tracer.should_sample(mutating=изменяющий, failed=False))
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
                    ControlDenied(409, "idempotency_key_reused",
                                  "ключ идемпотентности уже использован для другого запроса"),
                    method, path, headers, correlation_id)
            if заявка.state == IN_PROGRESS:
                # Первый запрос ещё выполняется. Ждать значит удваивать таймаут
                # вместо ответа; выполнить второй раз — нарушить идемпотентность.
                return self._deny(
                    ControlDenied(409, "request_in_flight",
                                  "запрос с этим ключом уже выполняется",
                                  holder=заявка.holder,
                                  age_seconds=round(заявка.age_seconds, 1)),
                    method, path, headers, correlation_id)

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
        self._metrics.inc("site_engine_control_requests_total",
                          method=method.upper(), status=status_class(response.status))
        # Идентификатор запроса возвращается всегда, включая отказы: без него
        # вызывающий не может найти свой запрос в журнале и приносит скриншот.
        payload = response.body if isinstance(response.body, dict) else {"result": response.body}
        payload = {**payload, "correlationId": correlation_id,
                   "traceparent": контекст.header()}
        # Отрезок записывается после ответа: до него неизвестны ни код, ни
        # причина отказа, а след без них отвечает «что-то произошло».
        # Поле error принадлежит оболочке ошибок и обязано быть объектом.
        # Но тело может прийти от любого обработчика, и чужая форма не
        # должна ронять запись следа — диагностика не вправе ломать работу.
        сырое = payload.get("error") if isinstance(payload, dict) else None
        ошибка = сырое.get("code", "") if isinstance(сырое, dict) else ""
        if контекст.sampled or response.status >= 400:
            отрезок = _завершённый_отрезок(
                контекст, родитель, "control.request",
                {"method": method.upper(), "path_template": path_template(path),
                 "status": response.status, "error_code": ошибка,
                 "outcome": "ok" if response.status < 400 else "error"},
                self._request_started, float(self._now()))
            self._tracer.record(отрезок)
        return ApiResponse(status=response.status, body=payload)

    def _idempotency_key(self, method: str, path: str, body: dict[str, Any],
                         headers: dict[str, str]) -> tuple[str | None, str]:
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
            raise ControlDenied(400, "invalid_idempotency_key",
                                "ключ идемпотентности недопустим")
        return ключ, fingerprint(method.upper(), path, body)

    def _deny(self, denied: ControlDenied, method: str, path: str,
              headers: dict[str, str], correlation_id: str) -> ApiResponse:
        self._audit_refusal(denied, method, path, headers, correlation_id)
        self._metrics.inc("site_engine_control_refusals_total", code=denied.code)
        self._metrics.inc("site_engine_control_requests_total",
                          method=method.upper(), status=status_class(denied.status))
        ответ = error(denied.status, denied.code, denied.message, **denied.extra)
        # Ранние отказы возвращаются мимо общего хвоста handle(), поэтому след
        # пишется здесь. Без этого конфликт ключа и запрос в работе — то есть
        # ровно те случаи, ради которых трассировку заводят, — следа не имели.
        контекст = getattr(self, "_trace_context", None)
        if контекст is not None:
            отрезок = _завершённый_отрезок(
                контекст, None, "control.request",
                {"method": method.upper(), "path_template": path_template(path),
                 "status": denied.status, "error_code": denied.code, "outcome": "error"},
                getattr(self, "_request_started", float(self._now())), float(self._now()))
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
        self._rate_limit(principal, site_for_limit, f"{method}:{operation}")

        if method == "GET" and rest[:1] == ["content-health"]:
            principal.require(SCOPE_READ)
            return self._content_health(rest[1] if len(rest) > 1 else None, body)
        if method == "GET" and rest == ["reasons"]:
            principal.require(SCOPE_READ)
            return ApiResponse(status=200, body=reasons.catalogue())
        if method == "GET" and len(rest) == 2 and rest[0] == "traces":
            principal.require(SCOPE_AUDIT)
            return self._trace(rest[1])
        if method == "GET" and rest[:1] == ["compatibility"]:
            principal.require(SCOPE_READ)
            return self._compatibility(rest[1] if len(rest) > 1 else None)
        if method == "GET" and rest == ["metrics"]:
            principal.require(SCOPE_READ)
            return self._metrics_response()
        if method == "GET" and rest[:1] == ["audit"]:
            principal.require(SCOPE_AUDIT)
            return self._audit_trail(body, headers)
        if method == "GET" and len(rest) == 2 and rest[0] == "jobs":
            principal.require(SCOPE_READ)
            return self._job_status(rest[1])
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

    def _rate_limit(self, principal: Principal, site_id: str, operation: str) -> None:
        """Списать разрешение по иерархии ключей.

        Ключи раздельные: среда, витрина, действующее лицо, операция. Общего
        счётчика на весь массив здесь нет намеренно — один шумный сайт не
        должен упирать в предел остальные.
        """
        решение = self._limiter.check({
            "environment": self._env.get("SITE_ENGINE_ENVIRONMENT", "local"),
            "site": site_id,
            "actor": principal.token_id,
            # Витрина входит в ключ операции: без неё шум по одной витрине
            # выбирал бы операционное ведро сразу для всех остальных.
            "operation": f"{principal.token_id}:{site_id or '-'}:{operation}" if operation else "",
        })
        if решение.degraded:
            # Тихий переход в запасной режим не должен остаться незамеченным:
            # предел в нём строже, и вызывающий обязан узнать причину отказов.
            self._metrics.inc("site_engine_ratelimit_degraded_total")
        if not решение.allowed:
            self._metrics.inc("site_engine_control_refusals_total", code="rate_limited")
            raise ControlDenied(429, "rate_limited",
                                "превышен предел частоты",
                                **решение.as_error_extra())

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
                400, "invalid_action", "недопустимое действие",
                allowed=sorted(ALLOWED_JOB_ACTIONS),
            )
        if environment not in ALLOWED_ENVIRONMENTS:
            raise ControlDenied(400, "invalid_environment", "недопустимая среда",
                                allowed=sorted(ALLOWED_ENVIRONMENTS))

        if dry_run:
            return ApiResponse(
                status=200,
                body={
                    "dryRun": True,
                    "wouldEnqueue": {"siteId": site_id, "action": action, "environment": environment},
                    "siteLocked": locks.is_locked(site_id, environment),
                },
            )

        try:
            with locks.site_lock(site_id, environment, timeout=2.0):
                item = queue.enqueue(site_id, action=action, environment=environment,
                                     traceparent=self._trace_context.header())
        except locks.LockBusy as exc:
            raise ControlDenied(409, "site_busy", "по сайту уже идёт операция") from exc
        except FileExistsError as exc:
            raise ControlDenied(409, "job_exists", "такое задание уже в очереди") from exc

        audit.record(
            job_id=item.job_id, site_id=site_id, environment=environment,
            action=f"control.job.{action}", target="queue", mutation=True, exit_code=0,
            extra={"correlation_id": correlation_id, "actor_token": principal.token_id,
                   "trace_id": self._trace_context.trace_id},
        )
        return ApiResponse(status=202, body={"job": item.as_dict(), "status": "queued"})

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
        if not isinstance(changes, dict) or not changes:
            raise ControlDenied(400, "invalid_body", "нужен непустой объект changes")
        if len(changes) > MAX_BODY_KEYS:
            raise ControlDenied(400, "too_many_changes", f"не более {MAX_BODY_KEYS} настроек за запрос")
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
                409, "version_conflict", "конфигурация изменилась с момента чтения",
                expected_version=expected, current_version=current_version,
            )

        before = json.loads(target.read_text(encoding="utf-8"))
        diff = _diff(before, changes)
        dry_run = bool(body.get("dryRun"))

        if dry_run:
            return ApiResponse(
                status=200,
                body={"dryRun": True, "currentVersion": current_version, "diff": diff,
                      "noop": not diff},
            )

        if not diff:
            return ApiResponse(status=200, body={"applied": False, "noop": True,
                                                 "version": current_version, "diff": {}})

        after = dict(before)
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
                    raise ControlDenied(409, "version_conflict",
                                        "конфигурация изменилась во время применения")
                tmp = target.with_suffix(".json.tmp")
                tmp.write_text(json.dumps(after, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
                tmp.replace(target)
        except locks.LockBusy as exc:
            raise ControlDenied(409, "site_busy", "по сайту уже идёт операция") from exc
        except OSError as exc:
            # Каталог профилей может быть намеренно закрыт на запись. Падение с
            # 500 выглядело бы как поломка службы; на деле это её граница прав,
            # и оператору полезнее увидеть причину, чем внутреннюю ошибку.
            raise ControlDenied(
                503, "config_read_only",
                "настройки витрин недоступны для записи этой службе",
                reason=exc.strerror or "",
            ) from exc

        new_version = config_version(target)
        audit.record(
            job_id=correlation_id, site_id=site_id, environment="staging",
            action="control.settings.patch", target=str(target.relative_to(self._root)),
            mutation=True, exit_code=0,
            extra={"correlation_id": correlation_id, "actor_token": principal.token_id,
                   "trace_id": self._trace_context.trace_id,
                   "diff": diff, "version_before": current_version, "version_after": new_version},
        )
        return ApiResponse(status=200, body={"applied": True, "diff": diff,
                                                   "previousVersion": current_version,
                                                   "version": new_version})

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
            raise ControlDenied(400, "invalid_scope", "недопустимая область инвалидации",
                                allowed=sorted(allowed_scopes))
        keys = body.get("keys") or []
        if not isinstance(keys, list) or any(not isinstance(k, str) or not k for k in keys):
            raise ControlDenied(400, "invalid_keys", "keys должен быть списком непустых строк")
        негодные = [k for k in keys if not CACHE_KEY_RE.match(k)]
        if негодные:
            raise ControlDenied(
                400, "invalid_keys",
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
            item = queue.enqueue(site_id, action="invalidate", environment="staging",
                                 job_id=job_id, traceparent=self._trace_context.header())
        except FileExistsError as exc:
            raise ControlDenied(409, "job_exists",
                                "такая инвалидация уже запланирована") from exc
        audit.record(
            job_id=item.job_id, site_id=site_id, environment="staging",
            action="control.cache.invalidate", target=scope, mutation=True, exit_code=0,
            extra={"correlation_id": correlation_id, "actor_token": principal.token_id,
                   "trace_id": self._trace_context.trace_id, "keys": keys},
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
                compat.STATE_INCOMPATIBLE, compat.ENGINE_CONTRACT, None,
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
                409, "incompatible_contract",
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
        детали = content_health.проблемные(self._root, site_id, code=код, limit=предел, env=self._env)
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
            raise ControlDenied(404, "trace_not_found",
                                "след не найден: возможно, запрос не попал в выборку")
        return ApiResponse(status=200, body={
            "traceId": trace_id,
            "spans": отрезки,
            "total": len(отрезки),
            "durationMs": round(sum(s.get("duration_ms", 0) for s in отрезки), 2),
        })

    def _compatibility(self, site_id: str | None) -> ApiResponse:
        if site_id is not None:
            self._check_site_id(site_id)
            return ApiResponse(status=200,
                               body={"siteId": site_id,
                                     **self._compatibility_of(site_id).as_dict()})
        directory = self._root / "config" / "site-profiles"
        rows = []
        for path in sorted(directory.glob("*.json")) if directory.is_dir() else []:
            raw = self._load_profile_raw(path.stem)
            state = self._compatibility_of(path.stem)
            rows.append({"siteId": path.stem,
                         "siteType": (raw or {}).get("site_type"),
                         **state.as_dict()})
        by_state: dict[str, int] = {}
        for row in rows:
            by_state[row["state"]] = by_state.get(row["state"], 0) + 1
        return ApiResponse(status=200, body={
            "engine": compat.ENGINE_CONTRACT,
            "sites": rows,
            "total": len(rows),
            "byState": by_state,
            "manageable": sum(1 for r in rows if r["manageable"]),
        })

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
        for name, source in self._gauges.items():
            try:
                gauges[name] = source()
            except Exception:  # noqa: BLE001
                continue
        text = self._metrics.render(gauges)
        return ApiResponse(status=200, body={"prometheus": text,
                                             "counters": self._metrics.snapshot()})

    def _audit_trail(self, body: dict[str, Any], headers: dict[str, str]) -> ApiResponse:
        limit = body.get("limit", 50)
        if not isinstance(limit, int) or isinstance(limit, bool) or not (1 <= limit <= 500):
            raise ControlDenied(400, "invalid_limit", "limit — целое от 1 до 500")
        site_id = body.get("siteId")
        entries = audit.read_all()
        if site_id:
            entries = [e for e in entries if e.get("site_id") == site_id]
        return ApiResponse(status=200, body={"entries": entries[-limit:], "total": len(entries)})

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
                job_id=correlation_id, site_id="-", environment="-",
                action=f"control.denied.{denied.code}", target=f"{method} {path}",
                mutation=False, exit_code=denied.status,
                extra={"correlation_id": correlation_id,
                       "actor_token": _token_id(token) if token else "anonymous"},
            )
        except Exception:
            # Невозможность записать отказ не должна превращать отказ в сбой.
            pass
