"""Заработавшие страницы: якорь — не отдельный адрес, визиты складываются.

Повод измеренный, 23.10. В посадочных страницах из поиска встречаются пути
вида `/title/…/#watch`. Якорь браузер на сервер не отправляет, то есть это та
же страница. Моя первая версия считала такой путь отдельным адресом, и у него
canonical оказывался «не свой» ПО ПОСТРОЕНИЮ: три из шести «изъянов» первого
прогона были именно этим, и я чуть не записала их как дефекты витрин.

Проверяется чистая функция отбора посадочных: ни сети, ни браузера.
"""
from __future__ import annotations

import importlib.util
import pathlib

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ПУТЬ = КОРЕНЬ / "automation" / "local" / "earning-pages-health.py"

_с = importlib.util.spec_from_file_location("earning_pages_health", ПУТЬ)
МОДУЛЬ = importlib.util.module_from_spec(_с)
assert _с.loader is not None
_с.loader.exec_module(МОДУЛЬ)


def _мера(строки: list[tuple[str, float]]) -> dict:
    return {
        "domain": "fixture-one.test",
        "measurements": [{
            "key": "daily_search_landing_pages", "measured": True,
            "value": [
                {"dimensions": [{"name": "2026-10-20"}, {"name": путь}],
                 "metrics": [визиты, визиты]}
                for путь, визиты in строки
            ],
        }],
    }


def test_якорь_складывается_со_страницей():
    сч = МОДУЛЬ.посадочные(_мера([
        ("/title/x/", 100.0),
        ("/title/x/#watch", 38.0),
        ("/title/y/", 7.0),
    ]))
    assert сч["/title/x/"] == 138.0, dict(сч)
    assert "/title/x/#watch" not in сч
    assert сч["/title/y/"] == 7.0


def test_параметры_тоже_отбрасываются():
    """Метрика пишет и `?utm=…`: это та же страница, а не вторая."""
    сч = МОДУЛЬ.посадочные(_мера([
        ("/title/x/", 10.0),
        ("/title/x/?utm_source=ya", 5.0),
    ]))
    assert сч == {"/title/x/": 15.0}, dict(сч)


def test_полный_адрес_приводится_к_пути():
    сч = МОДУЛЬ.посадочные(_мера([
        ("https://fixture-one.test/title/x/", 4.0),
    ]))
    assert сч == {"/title/x/": 4.0}, dict(сч)


def test_без_меры_набор_пуст_а_не_выдуман():
    """Нет меры — нет набора. Выдумывать адреса для проверки нельзя."""
    assert МОДУЛЬ.посадочные({"domain": "x", "measurements": []}) == {}
