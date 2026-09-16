"""Сквозная трассировка: Admin → Control API → задание → витрина.

Журнал отвечает, что произошло с запросом в одном месте. Метрики отвечают, что
происходит вообще. Трассировка отвечает на третий вопрос, который до сих пор
оставался без ответа: *где именно* ушло время и на каком звене всё сломалось,
когда звеньев несколько и они в разных процессах.

Контекст переносится в формате W3C Trace Context (`traceparent`), а не в
собственном: заголовок стандартный, его понимают внешние сборщики, и когда
здесь появится настоящий OpenTelemetry, менять придётся хранилище, а не
разметку кода.

Три решения объяснены отдельно, потому что они ограничивают возможности:

* **Отрезки пишутся в файл, а не в отдельную службу.** Новой инфраструктуры
  итерация не вводит. Файл читается тем же процессом, что его пишет, и этого
  достаточно для вопроса «покажи путь запроса X». Общий сбор с нескольких
  хостов — задача многосерверной схемы, вынесенной в отдельный backlog.
* **Выборка асимметрична.** Успешные чтения — по доле, а всё изменяющее и всё
  с ошибкой — целиком. Выборка, одинаковая для успеха и отказа, теряет ровно
  те следы, ради которых трассировку и заводят.
* **Значения не пишутся, пишутся имена.** Атрибут `site_id` полезен, значение
  настройки — нет: след запроса не должен становиться вторым местом, где лежат
  данные, и уж точно не местом, где лежат секреты.
"""
from __future__ import annotations

import json
import os
import random
import re
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from factory.audit import redact_obj

# Заголовок переноса контекста и его формат: версия-trace-span-флаги.
TRACEPARENT = "traceparent"
_TP_RE = re.compile(r"^00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$")

FLAG_SAMPLED = 0x01

# Доля выборки для успешных чтений. Изменяющие операции и ошибки пишутся всегда.
DEFAULT_READ_SAMPLE = 0.1

# Сколько следов хранится. Трассировка — диагностика недавнего, а не архив:
# бесконечное хранение превращает каталог в свалку, где нужный след не найти.
DEFAULT_RETENTION_SECONDS = 7 * 24 * 3600

# Атрибуты, которые разрешено записывать. Список закрытый: свободный набор
# однажды принесёт в след значение настройки или заголовок с токеном.
ALLOWED_ATTRS = frozenset({
    "site_id", "action", "scope", "operation", "method", "path_template",
    "status", "error_code", "job_id", "stage", "actor_token", "environment",
    "outcome", "count", "degraded", "limit_key", "contract_state",
})


def _hex(n: int) -> str:
    return "%0*x" % (n, random.getrandbits(n * 4))


@dataclass(frozen=True)
class TraceContext:
    trace_id: str
    span_id: str
    sampled: bool

    def header(self) -> str:
        флаги = "01" if self.sampled else "00"
        return f"00-{self.trace_id}-{self.span_id}-{флаги}"

    def child(self) -> TraceContext:
        return TraceContext(self.trace_id, _hex(16), self.sampled)


def parse_traceparent(value: str | None) -> TraceContext | None:
    """Разбор входящего контекста.

    Негодный заголовок игнорируется, а не отвергается: чужая ошибка в разметке
    не повод отказать в обслуживании. Начинается новый след, и это видно по
    отсутствию родителя.
    """
    if not value:
        return None
    совпадение = _TP_RE.match(str(value).strip().lower())
    if not совпадение:
        return None
    trace_id, span_id, флаги = совпадение.groups()
    if trace_id == "0" * 32 or span_id == "0" * 16:
        return None
    return TraceContext(trace_id, span_id, bool(int(флаги, 16) & FLAG_SAMPLED))


def new_context(*, sampled: bool = True) -> TraceContext:
    return TraceContext(_hex(32), _hex(16), sampled)


@dataclass
class Span:
    trace_id: str
    span_id: str
    parent_id: str | None
    name: str
    service: str
    started: float
    ended: float = 0.0
    attrs: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        return round((self.ended - self.started) * 1000.0, 2)

    def as_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_id": self.parent_id,
            "name": self.name,
            "service": self.service,
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.started)),
            "duration_ms": self.duration_ms,
            "attrs": self.attrs,
            "events": self.events,
        }


class Tracer:
    """Запись отрезков в файл с выборкой и очисткой."""

    def __init__(
        self,
        state_dir: Path | str,
        *,
        service: str = "control-api",
        read_sample: float = DEFAULT_READ_SAMPLE,
        now=time.time,
        retention_seconds: float = DEFAULT_RETENTION_SECONDS,
    ) -> None:
        self._dir = Path(state_dir) / "trace"
        self._service = service
        self._read_sample = max(0.0, min(1.0, read_sample))
        self._now = now
        self._retention = retention_seconds
        self._lock = threading.Lock()

    # ---- выборка --------------------------------------------------------

    def should_sample(self, *, mutating: bool, failed: bool,
                      inherited: bool | None = None) -> bool:
        """Решение о записи следа.

        Унаследованное решение уважается: если вызывающий уже решил писать
        след, обрывать его на середине бессмысленно — получится половина пути.
        """
        if inherited is not None and inherited:
            return True
        if mutating or failed:
            return True
        return random.random() < self._read_sample

    # ---- запись ---------------------------------------------------------

    def _path(self, trace_id: str) -> Path:
        # По файлу на след: искать путь запроса по идентификатору проще, чем
        # вычитывать общий журнал, а параллельная запись не сталкивается.
        return self._dir / f"{trace_id}.jsonl"

    def record(self, span: Span) -> None:
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            строка = json.dumps(span.as_dict(), ensure_ascii=False)
            with self._lock, self._path(span.trace_id).open("a", encoding="utf-8") as fh:
                fh.write(строка + "\n")
        except OSError:
            # Невозможность записать след не должна ронять обслуживание:
            # диагностика важна, но не важнее самой работы.
            pass

    @contextmanager
    def span(self, name: str, context: TraceContext, *, parent_id: str | None = None,
             attrs: dict[str, Any] | None = None, service: str | None = None):
        """Отрезок работы. Записывается по выходу, в том числе при исключении."""
        отрезок = Span(
            trace_id=context.trace_id,
            span_id=context.span_id,
            parent_id=parent_id,
            name=name,
            service=service or self._service,
            started=float(self._now()),
            attrs=sanitize_attrs(attrs or {}),
        )
        try:
            yield отрезок
        except Exception as exc:  # noqa: BLE001
            отрезок.attrs["outcome"] = "exception"
            отрезок.events.append({"type": "exception", "class": type(exc).__name__})
            отрезок.ended = float(self._now())
            if context.sampled:
                self.record(отрезок)
            raise
        else:
            отрезок.ended = float(self._now())
            if context.sampled:
                self.record(отрезок)

    # ---- чтение ---------------------------------------------------------

    def read_trace(self, trace_id: str) -> list[dict[str, Any]]:
        """Все отрезки следа в порядке начала.

        Это и есть ответ на вопрос «покажи путь запроса X»: без него отрезки
        существуют, а восстановить по ним цепочку нельзя.
        """
        if not re.match(r"^[0-9a-f]{32}$", str(trace_id).lower()):
            return []
        путь = self._path(str(trace_id).lower())
        if not путь.is_file():
            return []
        отрезки = []
        try:
            for строка in путь.read_text(encoding="utf-8").splitlines():
                строка = строка.strip()
                if строка:
                    отрезки.append(json.loads(строка))
        except (OSError, json.JSONDecodeError):
            return отрезки
        отрезки.sort(key=lambda s: (s.get("started_at", ""), s.get("span_id", "")))
        return отрезки

    def cleanup(self) -> int:
        """Удалить следы старше срока хранения."""
        if not self._dir.is_dir():
            return 0
        # Сравнивается время изменения файла, поэтому и порог берётся от
        # настоящего времени: подставленные часы сравнивались бы с реальным
        # mtime и не удаляли бы ничего.
        порог = time.time() - self._retention
        убрано = 0
        for путь in self._dir.glob("*.jsonl"):
            try:
                if путь.stat().st_mtime < порог:
                    путь.unlink(missing_ok=True)
                    убрано += 1
            except OSError:
                continue
        return убрано


def sanitize_attrs(attrs: dict[str, Any]) -> dict[str, Any]:
    """Оставить разрешённые атрибуты и вычистить возможные секреты.

    Двойная защита: список разрешённых имён и та же чистка, что у журнала
    аудита. Первое отсекает случайное, второе — то, что попало в разрешённое
    поле по недосмотру.
    """
    отобранные = {k: v for k, v in attrs.items() if k in ALLOWED_ATTRS}
    очищенные = redact_obj(отобранные)
    return очищенные if isinstance(очищенные, dict) else {}


def path_template(path: str) -> str:
    """Путь без идентификаторов: `/api/v1/sites/{siteId}/jobs`.

    В атрибут следа идёт шаблон, а не конкретный путь. Иначе имена отрезков
    размножаются по числу витрин, и сравнить «сколько занимает постановка
    задания» становится невозможно.
    """
    части = [p for p in str(path).strip("/").split("/") if p]
    вывод: list[str] = []
    for i, часть in enumerate(части):
        если_после = части[i - 1] if i else ""
        if если_после == "sites" and i >= 3:
            вывод.append("{siteId}")
        elif если_после == "titles":
            вывод.append("{titleId}")
        elif если_после == "jobs" and i >= 3:
            вывод.append("{jobId}")
        elif если_после == "compatibility" and i >= 3:
            вывод.append("{siteId}")
        else:
            вывод.append(часть)
    return "/" + "/".join(вывод)


def tracer_from_env(root: Path | str, env: dict[str, str] | None = None,
                    *, service: str = "control-api") -> Tracer:
    env = env if env is not None else dict(os.environ)
    доля = env.get("SITE_ENGINE_TRACE_SAMPLE", "")
    try:
        значение = float(доля) if доля else DEFAULT_READ_SAMPLE
    except ValueError:
        значение = DEFAULT_READ_SAMPLE
    return Tracer(Path(root) / "var" / "state", service=service, read_sample=значение)
