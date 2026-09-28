"""Метрики управляющего слоя.

Журнал отвечает на вопрос «что произошло с этим запросом», метрики — на вопрос
«что происходит вообще». Второй вопрос задают, когда разбирать журнал построчно
уже поздно.

Счётчики живут в памяти процесса и обнуляются при перезапуске. Это записано
прямо, потому что определяет способ их чтения: смысл имеет скорость роста, а не
абсолютное значение. Хранилище с историей — задача системы сбора, а не службы.

Метки выбраны так, чтобы число рядов оставалось малым: метод, класс кода ответа
и код отказа. Метки с идентификатором витрины или пути сюда не попадают —
на массиве сайтов это превращает несколько рядов в тысячи.
"""
from __future__ import annotations

import threading
from typing import Any

# Порядок важен только для читаемости вывода.
_HELP = {
    "site_engine_control_requests_total": (
        "counter", "Запросы к управляющему слою по методу и классу ответа"),
    "site_engine_control_refusals_total": (
        "counter", "Отказы управляющего слоя по коду причины"),
    "site_engine_queue_items": (
        "gauge", "Заданий в очереди по стадиям"),
    "site_engine_sites": (
        "gauge", "Витрин под управлением"),
    "site_engine_admin_sessions": (
        "gauge", "Открытых сессий админки"),
    "site_engine_playback_identifiers_allowed": (
        "gauge", "Идентификаторы, которыми разрешено адресовать плеер (1 — разрешён)"),
    "site_engine_playback_identifier_flags": (
        "gauge", "Состояние флагов идентификаторов вне основы контракта"),
}


def _labels(pairs: dict[str, str]) -> str:
    if not pairs:
        return ""
    inner = ",".join(f'{k}="{_escape(v)}"' for k, v in sorted(pairs.items()))
    return "{" + inner + "}"


def _escape(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


class Metrics:
    """Счётчики процесса. Потокобезопасны: сервер многопоточный."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], int] = {}

    def inc(self, name: str, amount: int = 1, **labels: str) -> None:
        key = (name, tuple(sorted((k, str(v)) for k, v in labels.items())))
        with self._lock:
            self._counters[key] = self._counters.get(key, 0) + amount

    def value(self, name: str, **labels: str) -> int:
        key = (name, tuple(sorted((k, str(v)) for k, v in labels.items())))
        with self._lock:
            return self._counters.get(key, 0)

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return {f"{n}{_labels(dict(lb))}": v for (n, lb), v in self._counters.items()}

    def render(self, gauges: dict[str, list[tuple[dict[str, str], Any]]] | None = None) -> str:
        """Текстовый формат Prometheus.

        Собственная отрисовка, а не библиотека: формат прост, а зависимость
        обновляется по своему расписанию и тянет за собой реестр процесса.
        """
        lines: list[str] = []
        seen: set[str] = set()
        with self._lock:
            counters = dict(self._counters)
        buckets: dict[str, list[tuple[dict[str, str], Any]]] = {}
        for (name, labels), value in counters.items():
            buckets.setdefault(name, []).append((dict(labels), value))
        for name, rows in (gauges or {}).items():
            buckets.setdefault(name, []).extend(rows)
        for name in sorted(buckets):
            kind, help_text = _HELP.get(name, ("untyped", ""))
            if name not in seen:
                if help_text:
                    lines.append(f"# HELP {name} {help_text}")
                lines.append(f"# TYPE {name} {kind}")
                seen.add(name)
            for labels, value in sorted(buckets[name], key=lambda r: _labels(r[0])):
                lines.append(f"{name}{_labels(labels)} {value}")
        return "\n".join(lines) + "\n"


def status_class(status: int) -> str:
    """Класс ответа вместо точного кода: 2xx, 4xx, 5xx.

    Точный код держат журнал и счётчик отказов; в метрике по методу он дал бы
    вчетверо больше рядов без нового смысла.
    """
    return f"{status // 100}xx"
