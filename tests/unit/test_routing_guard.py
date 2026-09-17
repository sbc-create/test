"""REQ-TRANSPORT-ROUTING: транспорт обслуживает всё, что описано.

Отдельный файл, потому что проверка межслойная: сверка описания вызывает
ControlApi напрямую и потому не заметила бы, что транспорт отправляет маршрут
не в тот слой. Ровно это и произошло с /api/v1/metrics.
"""
from pathlib import Path

from factory.site_engine.api.openapi import ЗАПИСЬ
from factory.site_engine.api.server import _CONTROL_GET_PREFIXES, _is_control_path


def test_каждый_управляющий_маршрут_уходит_в_управляющий_слой():
    for path, node in ЗАПИСЬ.items():
        конкретный = path.replace("{siteId}", "s1").replace("{jobId}", "j1")
        метод = node["method"].upper()
        assert _is_control_path(метод, конкретный), f"{метод} {path} ушёл бы в чтение"


def test_читающие_маршруты_не_перехватываются():
    for path in ("/api/v1/health", "/api/v1/sites", "/api/v1/sites/s1",
                 "/api/v1/sites/s1/titles", "/api/v1/ingestion/status"):
        assert not _is_control_path("GET", path), f"{path} перехвачен управляющим слоем"


def test_перечень_префиксов_не_ведётся_руками():
    """Список из таблицы, а не из литерала: иначе он отстаёт молча."""
    источник = Path("factory/site_engine/api/server.py").read_text(encoding="utf-8")
    assert "_control_get_prefixes()" in источник
    assert "/api/v1/metrics" in _CONTROL_GET_PREFIXES
    assert "/api/v1/audit" in _CONTROL_GET_PREFIXES
