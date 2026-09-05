"""Живой транспорт Content API CDNVideoHub для направления Lords.

Здесь только обращение к источнику и превращение ответа в записи каталога.
Решение «что изменилось» принимает `content_api.plan_sync`, и оно намеренно
осталось там: план не должен зависеть от того, пришли данные по сети или из
кэша.

Пути, параметры, лимиты и соответствие полей берутся из
`knowledge/cdnvideohub/content-api.yaml`. Зашитых адресов в этом файле нет —
расхождение с контрактом обязано быть видно как отказ, а не подстройка.

Свойства, которые здесь важнее скорости:

* пустой или частичный ответ никогда не удаляет каталог — это отказ источника,
  а не сообщение «каталог опустел»;
* последний удачный ответ сохраняется целиком и переживает неудачный запуск;
* просроченный кэш отдаётся только явно, со статусом STALE, и вызывающий обязан
  этот статус увидеть;
* запись атомарна: каталог либо прежний, либо новый, промежуточного состояния
  на диске не существует.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from factory.lords.content_api import Contract, load_contract

FRESH = "FRESH"
STALE = "STALE"
BLOCKED_SOURCE = "BLOCKED_SOURCE"

#: Обход прекращается, даже если источник продолжает обещать следующую страницу.
#: Без этого испорченный курсор превращает синхронизацию в бесконечный цикл.
#: Предохранитель от зациклившейся пагинации. Это наша операционная настройка,
#: а не факт об API: провайдер число страниц не ограничивает, и в замороженном
#: контракте ему поэтому не место.
#:
#: Значение берётся с запасом над измеренным каталогом. Замер 2026-08-30:
#: источник отдаёт 53 115 записей — 532 страницы по сто. Прежние 200 страниц
#: при размере 24 обрезали витрину ровно на 4800 записях, и обрыв ничем себя не
#: выдавал: поле `stopped_by` заполнялось, но его никто не читал.
DEFAULT_MAX_PAGES = 2000


class SourceError(RuntimeError):
    """Источник не ответил так, чтобы ответу можно было доверять."""

    def __init__(self, message: str, *, status: int | None = None, kind: str = "network"):
        super().__init__(message)
        self.status = status
        self.kind = kind


# ---------------------------------------------------------------------------
# Чтение контракта
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Endpoint:
    path: str
    method: str = "GET"


@dataclass(frozen=True)
class LiveContract:
    """Разобранный контракт. Всё, что нужно транспорту, и ничего сверх того."""

    base_url: str
    auth_header: str
    auth_prefix: str
    accept: str
    endpoints: dict[str, Endpoint]
    cursor_param: str
    size_param: str
    default_size: int
    max_size: int
    items_field: str
    next_cursor_field: str
    has_more_field: str
    total_field: str
    max_pages: int
    refuse_repeated_cursor: bool
    timeout_ms: int
    max_retries: int
    backoff_base_ms: int
    backoff_max_ms: int
    max_retry_after_ms: int
    retry_on_status: tuple[int, ...]
    min_interval_ms: int
    cache_ttl_ms: int
    sections: dict[str, dict]
    title_mapping: dict[str, Any]
    aggregator_priority: tuple[str, ...]
    external_id_aliases: dict[str, list[str]]
    #: Раздел `filters` контракта. До 2026-09-02 он не читался вовсе, и
    #: объявленный там `updated_since` пролежал неиспользованным: каждый цикл
    #: забирал все 53 180 записей за 10 мин 42 с ради полусотни изменившихся.
    filters: dict[str, str] = field(default_factory=dict)

    @property
    def updated_since_param(self) -> str | None:
        """Имя параметра «изменения с отметки времени», если контракт его знает.

        Имя берётся только из контракта. Догадка здесь опаснее отсутствия:
        неизвестный параметр источник молча игнорирует и отдаёт полный каталог,
        то есть ошибка в имени выглядит как исправная работа.
        """
        return self.filters.get("updated_since") or None

    @classmethod
    def from_contract(cls, contract: Contract) -> LiveContract:
        problems = contract.problems()
        if problems:
            raise SourceError(f"контракт непригоден: {'; '.join(problems)}", kind="contract")
        raw = contract.raw
        pagination = raw.get("pagination") or {}
        limits = raw.get("limits") or {}
        auth = raw.get("auth") or {}
        mapping = raw.get("mapping") or {}
        title = mapping.get("title") or {}
        endpoints = {
            name: Endpoint(path=str(spec["path"]), method=str(spec.get("method", "GET")))
            for name, spec in (raw.get("endpoints") or {}).items()
            if isinstance(spec, dict) and spec.get("path")
        }
        if "titles" not in endpoints:
            raise SourceError("в контракте нет endpoint titles", kind="contract")
        return cls(
            base_url=str(raw["base_url"]),
            auth_header=str(auth.get("header", "Authorization")),
            auth_prefix=str(auth.get("value_prefix", "Bearer ")),
            accept=str(auth.get("accept", "application/json")),
            endpoints=endpoints,
            cursor_param=str(pagination.get("cursor_param", "cursor")),
            size_param=str(pagination.get("size_param", "limit")),
            default_size=int(pagination.get("default_size", 24)),
            max_size=int(pagination.get("max_size", 100)),
            items_field=str(pagination.get("items_field", "items")),
            next_cursor_field=str(pagination.get("next_cursor_field", "next_cursor")),
            has_more_field=str(pagination.get("has_more_field", "has_more")),
            total_field=str(pagination.get("total_field", "total")),
            max_pages=int(pagination.get("max_pages", DEFAULT_MAX_PAGES)),
            refuse_repeated_cursor=bool(pagination.get("refuse_repeated_cursor", True)),
            timeout_ms=int(limits.get("timeout_ms", 30000)),
            max_retries=int(limits.get("max_retries", 5)),
            backoff_base_ms=int(limits.get("backoff_base_ms", 1000)),
            backoff_max_ms=int(limits.get("backoff_max_ms", 30000)),
            max_retry_after_ms=int(limits.get("max_retry_after_ms", 5000)),
            retry_on_status=tuple(limits.get("retry_on_status", (429, 500, 502, 503, 504))),
            min_interval_ms=int(limits.get("min_interval_ms", 250)),
            cache_ttl_ms=int(limits.get("cache_ttl_ms", 3600000)),
            sections=dict(raw.get("sections") or {}),
            title_mapping=title,
            aggregator_priority=tuple(title.get("playback_aggregator_priority", ("kp",))),
            external_id_aliases={
                key: list(value)
                for key, value in (mapping.get("external_ids") or {}).items()
            },
            filters={
                str(key): str(value)
                for key, value in (raw.get("filters") or {}).items()
                if value
            },
        )

    def url(self, name: str, **kwargs: str) -> str:
        endpoint = self.endpoints.get(name)
        if endpoint is None:
            raise SourceError(f"в контракте нет endpoint {name}", kind="contract")
        path = endpoint.path
        for key, value in kwargs.items():
            path = path.replace("{" + key + "}", urllib.parse.quote(str(value), safe=""))
        return urllib.parse.urljoin(self.base_url, path)


# ---------------------------------------------------------------------------
# Транспорт
# ---------------------------------------------------------------------------
@dataclass
class Fetcher:
    """HTTP-обёртка: таймаут, ограничение частоты, повторы с выдержкой.

    `opener` подменяется в тестах: сеть в тестах не нужна и запрещена.
    """

    contract: LiveContract
    token: str
    opener: Callable[[urllib.request.Request, float], Any] | None = None
    sleep: Callable[[float], None] = time.sleep
    monotonic: Callable[[], float] = time.monotonic
    _last_request_at: float = field(default=0.0, init=False)
    requests_made: int = field(default=0, init=False)
    retries_made: int = field(default=0, init=False)

    def _throttle(self) -> None:
        if self.contract.min_interval_ms <= 0:
            return
        wait = (self.contract.min_interval_ms / 1000) - (self.monotonic() - self._last_request_at)
        if wait > 0:
            self.sleep(wait)

    def _open(self, url: str) -> tuple[int, bytes, dict]:
        request = urllib.request.Request(url, method="GET")
        request.add_header(self.contract.auth_header, f"{self.contract.auth_prefix}{self.token}")
        request.add_header("Accept", self.contract.accept)
        opener = self.opener or _default_opener
        return opener(request, self.contract.timeout_ms / 1000)

    def _retry_after_ms(self, headers: dict) -> int | None:
        raw = headers.get("Retry-After") or headers.get("retry-after")
        if raw is None:
            return None
        try:
            seconds = float(raw)
        except (TypeError, ValueError):
            return None
        if seconds < 0:
            return None
        return min(int(seconds * 1000), self.contract.max_retry_after_ms)

    def get_json(self, url: str) -> dict:
        attempt = 0
        while True:
            self._throttle()
            self._last_request_at = self.monotonic()
            self.requests_made += 1
            try:
                status, body, headers = self._open(url)
            except TimeoutError as error:
                status, body, headers = None, b"", {}
                failure = SourceError(f"таймаут запроса: {error}", kind="timeout")
            except OSError as error:
                status, body, headers = None, b"", {}
                failure = SourceError(f"сетевой отказ: {error}", kind="network")
            else:
                failure = None

            if failure is None and status == 200:
                try:
                    payload = json.loads(body.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as error:
                    raise SourceError(f"ответ не является JSON: {error}", kind="payload") from None
                if not isinstance(payload, dict):
                    raise SourceError("ответ верхнего уровня не объект", kind="payload")
                return payload

            retryable = failure is not None or status in self.contract.retry_on_status
            if not retryable:
                # 401/403/404 повторять бессмысленно: ответ не изменится.
                raise SourceError(f"источник ответил {status}", status=status, kind="http")

            if attempt >= self.contract.max_retries:
                if failure is not None:
                    raise failure
                raise SourceError(
                    f"источник отвечает {status} после {attempt} повторов",
                    status=status, kind="http",
                )

            delay_ms = self._retry_after_ms(headers) if status == 429 else None
            if delay_ms is None:
                delay_ms = min(
                    self.contract.backoff_base_ms * (2 ** attempt),
                    self.contract.backoff_max_ms,
                )
            attempt += 1
            self.retries_made += 1
            self.sleep(delay_ms / 1000)


def _default_opener(request: urllib.request.Request, timeout: float) -> tuple[int, bytes, dict]:
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return response.status, response.read(), dict(response.headers)
    except urllib.error.HTTPError as error:
        return error.code, error.read(), dict(error.headers or {})


# ---------------------------------------------------------------------------
# Обход страниц
# ---------------------------------------------------------------------------
@dataclass
class PageWalk:
    items: list[dict]
    pages: int
    total: int | None
    stopped_by: str


def walk_pages(fetcher: Fetcher, base_url: str, params: dict[str, str] | None = None) -> PageWalk:
    """Полный обход курсорной пагинации с защитой от зацикливания."""
    contract = fetcher.contract
    collected: list[dict] = []
    seen_cursors: set[str] = set()
    cursor: str | None = None
    pages = 0
    total: int | None = None
    stopped_by = "has_more"

    while True:
        query = dict(params or {})
        # Просим столько, сколько контракт разрешает. Прежде здесь стоял
        # `min(default_size, max_size)` — то есть двадцать четыре при
        # разрешённой сотне: вчетверо больше запросов ради вчетверо меньших
        # данных, и предел страниц исчерпывался вчетверо быстрее.
        query[contract.size_param] = str(contract.max_size)
        if cursor:
            query[contract.cursor_param] = cursor
        url = f"{base_url}?{urllib.parse.urlencode(query)}"
        payload = fetcher.get_json(url)
        pages += 1

        items = payload.get(contract.items_field)
        if items is None:
            raise SourceError(
                f"в ответе нет поля «{contract.items_field}» — ответ не соответствует контракту",
                kind="payload",
            )
        if not isinstance(items, list):
            raise SourceError(f"поле «{contract.items_field}» не список", kind="payload")
        collected.extend(item for item in items if isinstance(item, dict))

        if total is None and isinstance(payload.get(contract.total_field), int):
            total = payload[contract.total_field]

        has_more = bool(payload.get(contract.has_more_field))
        next_cursor = payload.get(contract.next_cursor_field)
        next_cursor = str(next_cursor).strip() if next_cursor else ""

        if not has_more or not next_cursor:
            # Источник, обещающий продолжение без курсора, зациклил бы обход.
            stopped_by = "has_more" if not has_more else "cursor_absent"
            break
        if contract.refuse_repeated_cursor and next_cursor in seen_cursors:
            raise SourceError(
                f"источник повторил курсор на странице {pages} — пагинация зациклена",
                kind="pagination",
            )
        seen_cursors.add(next_cursor)
        if pages >= contract.max_pages:
            # Предел страниц — защита от зациклившегося источника, а не признак
            # конца каталога. Молчаливый обрыв однажды оставил витрину с 4800
            # записями из 53 115, и ни один гейт об этом не сказал: поле
            # `stopped_by` заполнялось, но никто его не читал.
            raise SourceError(
                f"обрыв каталога: пройден предел в {contract.max_pages} страниц, "
                f"а источник обещает продолжение. Собрано {len(collected)} записей; "
                "публиковать неполный каталог как полный нельзя",
                kind="catalog_truncation",
            )
        cursor = next_cursor

    return PageWalk(items=collected, pages=pages, total=total, stopped_by=stopped_by)


# ---------------------------------------------------------------------------
# Нормализация
# ---------------------------------------------------------------------------
def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _pick_external(ids: dict | None, aliases: list[str]) -> str | None:
    if not isinstance(ids, dict):
        return None
    for alias in aliases:
        value = ids.get(alias)
        if value not in (None, ""):
            return str(value).strip() or None
    return None


def normalize_title(raw: dict, contract: LiveContract) -> dict | None:
    """Запись каталога из ответа источника. Ничего не додумывает.

    Возвращает None, если у записи нет устойчивого идентификатора: без него
    дедупликация и идемпотентность невозможны, а выдумывать ключ нельзя.
    """
    external_id = _text(raw.get("id"))
    name = _text(raw.get("name"))
    if not external_id or not name:
        return None

    external_ids = raw.get("external_ids") if isinstance(raw.get("external_ids"), dict) else {}
    resolved: dict[str, str] = {}
    for key, aliases in contract.external_id_aliases.items():
        found = _pick_external(external_ids, aliases)
        if found:
            resolved[key] = found

    # Плеер адресуется агрегатором, а не внутренним id источника.
    aggregator = None
    playback_id = None
    # imdb в этом отображении отсутствует намеренно: правило PC-2 контракта
    # плеера запрещает IMDb в роли playback identifier. Поставщик по нему поток
    # отдаёт, и 645 карточек из-за этого остаются без видео — но снимать запрет
    # вправе только владелец контракта.
    aggregator_by_key = {"kinopoisk": "kp", "myanimelist": "mali", "mydramalist": "mdl"}
    for key in ("kinopoisk", "myanimelist", "mydramalist"):
        code = aggregator_by_key[key]
        if code in contract.aggregator_priority and resolved.get(key):
            aggregator, playback_id = code, resolved[key]
            break

    is_series = raw.get("is_series")
    raw_type = _text(raw.get("type"))
    if is_series is None and raw_type:
        is_series = raw_type.lower() in {"series", "tv", "show"}

    year = raw.get("year")
    year = int(year) if isinstance(year, int) else None

    return {
        "external_id": external_id,
        "name": name,
        "type": raw_type,
        "is_series": bool(is_series) if is_series is not None else None,
        "year": year,
        "poster_url": _text(raw.get("poster_url")),
        "licensed": raw.get("licensed") if isinstance(raw.get("licensed"), bool) else None,
        "tags": [t for t in (raw.get("tags") or []) if isinstance(t, str)],
        "kinopoisk_rating": raw.get("kinopoisk_rating"),
        "imdb_rating": raw.get("imdb_rating"),
        "external_ids": resolved,
        "playback": (
            {"aggregator": aggregator, "title_id": playback_id}
            if aggregator and playback_id else None
        ),
        "created_at": _text(raw.get("created_at")),
        "updated_at": _text(raw.get("updated_at")),
    }


def normalize_all(items: list[dict], contract: LiveContract) -> tuple[list[dict], list[dict]]:
    """Нормализованные записи и отброшенные, с причиной отбрасывания."""
    good: list[dict] = []
    rejected: list[dict] = []
    for raw in items:
        normalized = normalize_title(raw, contract)
        if normalized is None:
            rejected.append({"reason": "нет id или name", "fields": sorted(raw)[:12]})
        else:
            good.append(normalized)
    return good, rejected


# ---------------------------------------------------------------------------
# Кэш последнего удачного ответа
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CacheEntry:
    fetched_at_ms: int
    items: list[dict]
    source: str
    #: Отметка для следующего инкрементального запроса. None у кэшей, записанных
    #: до появления инкрементального режима, — такой кэш обновляется полностью
    #: один раз и после этого отметку получает.
    mark: str | None = None
    #: Когда каталог в последний раз собирался полным обходом. Инкрементальный
    #: ответ не сообщает об удалённых записях, поэтому полный обход обязан
    #: повторяться, а не заменяться приращениями навсегда.
    base_full_at_ms: int = 0

    def age_ms(self, now_ms: int) -> int:
        return max(0, now_ms - self.fetched_at_ms)

    def is_fresh(self, now_ms: int, ttl_ms: int) -> bool:
        return self.age_ms(now_ms) < ttl_ms


def cache_path(root: Path, site_id: str) -> Path:
    return Path(root) / "lords" / "catalog-cache" / f"{site_id}.json"


def read_cache(path: Path) -> CacheEntry | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    items = payload.get("items")
    if not isinstance(items, list):
        return None
    mark = payload.get("mark")
    return CacheEntry(
        fetched_at_ms=int(payload.get("fetched_at_ms", 0)),
        items=[i for i in items if isinstance(i, dict)],
        source=str(payload.get("source", "unknown")),
        mark=str(mark) if isinstance(mark, str) and mark.strip() else None,
        base_full_at_ms=int(payload.get("base_full_at_ms", 0) or 0),
    )


def write_atomic(path: Path, payload: dict) -> None:
    """Запись через временный файл и rename.

    rename в пределах одной файловой системы атомарен, поэтому читатель видит
    либо прежний файл целиком, либо новый целиком. Прямая запись оставила бы
    каталог наполовину переписанным, если процесс прервут.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def write_cache(
    path: Path,
    items: list[dict],
    *,
    now_ms: int,
    source: str,
    mark: str | None = None,
    base_full_at_ms: int | None = None,
) -> None:
    payload: dict = {"fetched_at_ms": now_ms, "source": source, "items": items}
    if mark:
        payload["mark"] = mark
    payload["base_full_at_ms"] = int(base_full_at_ms if base_full_at_ms is not None else now_ms)
    write_atomic(path, payload)


# ---------------------------------------------------------------------------
# Инкрементальное обновление
# ---------------------------------------------------------------------------
#: Насколько отметка сдвигается в прошлое относительно начала удачного обхода.
#: Обход длится минуты, часы источника и наши могут расходиться, а запись,
#: изменённая ровно во время обхода, обязана попасть в следующий ответ.
#: Перекрытие даёт повторы, а повтор при слиянии по идентификатору безвреден;
#: пропуск — нет.
DEFAULT_MARK_OVERLAP_MS = 15 * 60 * 1000

#: Как часто каталог обязан пересобираться полным обходом. Инкрементальный ответ
#: сообщает только об изменившихся записях и ничего — об исчезнувших, поэтому
#: без полного обхода удалённое осталось бы на витрине навсегда.
DEFAULT_FULL_REFRESH_AFTER_MS = 6 * 60 * 60 * 1000


def format_mark(now_ms: int, *, overlap_ms: int = DEFAULT_MARK_OVERLAP_MS) -> str:
    """Отметка времени для `updated_since` в формате, который принял источник."""
    seconds = max(0, (now_ms - max(0, overlap_ms))) // 1000
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(seconds))


def merge_items(base: list[dict], fresh: list[dict]) -> tuple[list[dict], int, int]:
    """Слияние приращения с каталогом по `external_id`.

    Возвращает каталог, число заменённых и число добавленных записей. Порядок
    прежних записей сохраняется, новые дописываются в конец: перестановка
    каталога сдвинула бы разбиение на страницы, а с ним и адреса.

    Слияние, а не замена, — здесь главное. Инкрементальный ответ содержит
    полсотни записей из пятидесяти трёх тысяч; замена оставила бы от каталога
    полсотни.
    """
    index = {}
    merged = list(base)
    for position, item in enumerate(merged):
        key = item.get("external_id")
        if key:
            index[key] = position
    replaced = 0
    added = 0
    for item in fresh:
        key = item.get("external_id")
        if not key:
            continue
        position = index.get(key)
        if position is None:
            index[key] = len(merged)
            merged.append(item)
            added += 1
        else:
            merged[position] = item
            replaced += 1
    return merged, replaced, added


# ---------------------------------------------------------------------------
# Синхронизация
# ---------------------------------------------------------------------------
@dataclass
class SyncOutcome:
    status: str
    reason: str
    items: list[dict]
    pages: int = 0
    rejected: list[dict] = field(default_factory=list)
    stopped_by: str = ""
    cache_age_ms: int | None = None
    requests_made: int = 0
    retries_made: int = 0
    #: "full" или "incremental" — каким обходом получен этот каталог.
    mode: str = "full"
    #: Сколько записей приращение заменило и сколько добавило. Для полного
    #: обхода не заполняется: там изменилось всё или ничего.
    replaced: int = 0
    added: int = 0
    #: Почему выбран полный обход вместо инкрементального. Пусто, если выбора
    #: не было или он не менялся.
    mode_reason: str = ""

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "reason": self.reason,
            "item_count": len(self.items),
            "pages": self.pages,
            "rejected": self.rejected[:20],
            "rejected_count": len(self.rejected),
            "stopped_by": self.stopped_by,
            "cache_age_ms": self.cache_age_ms,
            "requests_made": self.requests_made,
            "retries_made": self.retries_made,
            "mode": self.mode,
            "replaced": self.replaced,
            "added": self.added,
            "mode_reason": self.mode_reason,
        }


def _decide_mode(
    *,
    contract: LiveContract,
    cached: CacheEntry | None,
    incremental: bool,
    now_ms: int,
    full_refresh_after_ms: int,
) -> tuple[str, str]:
    """Полный обход или приращение. При любом сомнении — полный.

    Полный обход дороже, но никогда не бывает неправ. Приращение допускается
    только когда все условия выполнены разом, и каждый отказ называется вслух:
    молчаливый откат к полному обходу выглядел бы как исправная работа.
    """
    if not incremental:
        return "full", "инкрементальный режим не запрошен"
    if not contract.updated_since_param:
        return "full", "контракт не объявляет параметр updated_since"
    if cached is None:
        return "full", "кэша нет — приращение не к чему прибавлять"
    if not cached.items:
        return "full", "кэш пуст — приращение не к чему прибавлять"
    if not cached.mark:
        return "full", "в кэше нет отметки времени прошлой загрузки"
    if cached.base_full_at_ms <= 0:
        return "full", "неизвестно, когда каталог собирался полностью"
    age = now_ms - cached.base_full_at_ms
    if age >= full_refresh_after_ms:
        return "full", (
            f"с последнего полного обхода прошло {age // 60000} мин — "
            "пора сверить исчезнувшие записи"
        )
    if age < 0:
        return "full", "отметка полного обхода из будущего — доверять ей нельзя"
    return "incremental", ""


def fetch_catalog(
    *,
    contract: LiveContract,
    fetcher: Fetcher,
    cache_file: Path,
    now_ms: int,
    params: dict[str, str] | None = None,
    allow_stale: bool = True,
    incremental: bool = False,
    full_refresh_after_ms: int = DEFAULT_FULL_REFRESH_AFTER_MS,
    mark_overlap_ms: int = DEFAULT_MARK_OVERLAP_MS,
) -> SyncOutcome:
    """Живой каталог: сеть, при отказе — последний удачный ответ.

    Отказ источника никогда не превращается в пустой каталог. Если сети нет, а
    кэш есть — отдаётся кэш со статусом STALE, и вызывающий обязан этот статус
    учесть. Если нет ни того, ни другого — BLOCKED_SOURCE и ноль изменений.

    При `incremental=True` и выполненных условиях (см. `_decide_mode`) у
    источника запрашиваются только записи, изменившиеся с отметки прошлой
    удачной загрузки, и ответ **сливается** с кэшем. Разница в цене измерена
    2026-09-02: полный обход — 53 180 записей за 10 мин 42 с, приращение за
    сутки — 51 запись за 0,4 с.

    Пустой ответ в двух режимах означает противоположное. В полном обходе пустой
    каталог — отказ источника: каталог из пятидесяти тысяч записей не пустеет.
    В приращении пустой ответ — самый обычный случай: с прошлого раза ничего не
    менялось. Различать их обязательно, иначе тихий час источника либо сотрёт
    витрину, либо навсегда останется «отказом».
    """
    cached = read_cache(cache_file)
    mode, mode_reason = _decide_mode(
        contract=contract,
        cached=cached,
        incremental=incremental,
        now_ms=now_ms,
        full_refresh_after_ms=full_refresh_after_ms,
    )

    # Отметка берётся до запроса: всё, что изменится во время обхода, обязано
    # попасть в следующий ответ, а не потеряться между двумя загрузками.
    next_mark = format_mark(now_ms, overlap_ms=mark_overlap_ms)

    query = dict(params or {})
    if mode == "incremental":
        query[contract.updated_since_param] = cached.mark

    def _fallback(reason: str, pages: int = 0, rejected: list[dict] | None = None,
                  stopped_by: str = "") -> SyncOutcome:
        if cached and allow_stale:
            return SyncOutcome(
                status=STALE,
                reason=f"{reason}; отдан последний удачный ответ",
                items=cached.items,
                pages=pages,
                rejected=rejected or [],
                stopped_by=stopped_by,
                cache_age_ms=cached.age_ms(now_ms),
                requests_made=fetcher.requests_made,
                retries_made=fetcher.retries_made,
                mode=mode,
                mode_reason=mode_reason,
            )
        return SyncOutcome(
            status=BLOCKED_SOURCE,
            reason=f"{reason}, кэша нет — каталог не трогаем",
            items=[],
            pages=pages,
            rejected=rejected or [],
            stopped_by=stopped_by,
            requests_made=fetcher.requests_made,
            retries_made=fetcher.retries_made,
            mode=mode,
            mode_reason=mode_reason,
        )

    try:
        walk = walk_pages(fetcher, contract.url("titles"), query)
    except SourceError as error:
        return _fallback(f"источник недоступен ({error})")

    items, rejected = normalize_all(walk.items, contract)

    if mode == "incremental":
        # Здесь пустой ответ законен и означает «ничего не изменилось».
        merged, replaced, added = merge_items(cached.items, items)
        if len(merged) < len(cached.items):
            # Недостижимо при слиянии по построению. Проверка стоит здесь
            # потому, что цена ошибки — стёртый каталог, а не лишняя строка.
            return _fallback(
                "слияние уменьшило каталог — приращение отвергнуто",
                pages=walk.pages, rejected=rejected, stopped_by=walk.stopped_by,
            )
        write_cache(
            cache_file, merged,
            now_ms=now_ms, source="live-incremental",
            mark=next_mark, base_full_at_ms=cached.base_full_at_ms,
        )
        return SyncOutcome(
            status=FRESH,
            reason=(
                f"приращение с {cached.mark}: изменено {replaced}, добавлено {added}, "
                f"каталог {len(merged)} записей за {walk.pages} страниц"
            ),
            items=merged,
            pages=walk.pages,
            rejected=rejected,
            stopped_by=walk.stopped_by,
            cache_age_ms=0,
            requests_made=fetcher.requests_made,
            retries_made=fetcher.retries_made,
            mode="incremental",
            replaced=replaced,
            added=added,
        )

    if not items:
        # Пустой ответ — это отказ источника, а не «каталог опустел».
        return _fallback(
            "источник вернул пустой каталог",
            pages=walk.pages, rejected=rejected, stopped_by=walk.stopped_by,
        )

    write_cache(
        cache_file, items,
        now_ms=now_ms, source="live", mark=next_mark, base_full_at_ms=now_ms,
    )
    return SyncOutcome(
        status=FRESH,
        reason=f"получено {len(items)} записей за {walk.pages} страниц",
        items=items,
        pages=walk.pages,
        rejected=rejected,
        stopped_by=walk.stopped_by,
        cache_age_ms=0,
        requests_made=fetcher.requests_made,
        retries_made=fetcher.retries_made,
        mode="full",
        mode_reason=mode_reason,
    )


def enabled_sections(items: list[dict], contract: LiveContract) -> dict[str, dict]:
    """Какие разделы можно публиковать.

    Раздел включается только при подтверждённой возможности источника и наличии
    материалов: пустой раздел, отвечающий 200, — это обещание, которого сайт не
    выполняет.
    """
    result: dict[str, dict] = {}
    for name, spec in contract.sections.items():
        if spec.get("supported") is False:
            result[name] = {"enabled": False, "reason": spec.get("reason", "не поддержан источником")}
            continue
        minimum = int(spec.get("min_items", 1))
        value = spec.get("filter_value")
        field_name = spec.get("requires_filter")
        if field_name == "type":
            matched = [i for i in items if (i.get("type") or "").lower() == str(value).lower()]
        elif field_name == "direction":
            matched = [i for i in items if str(value).lower() in
                       [t.lower() for t in (i.get("tags") or [])]]
        else:
            matched = list(items)
        if len(matched) >= minimum:
            result[name] = {"enabled": True, "count": len(matched)}
        else:
            result[name] = {
                "enabled": False,
                "count": len(matched),
                "reason": f"материалов {len(matched)}, минимум {minimum}",
            }
    return result


def load_live_contract(path: Path | str | None = None) -> LiveContract:
    return LiveContract.from_contract(load_contract(path))
