"""Сводка состояния сети считает РЕАЛЬНЫЕ визиты и не пишет недостачу закрытым.

Повод измеренный, 23.10. Цифры про цель лежат в четырёх разных местах, и
собирая их руками я дважды ошиблась за одну ночь: сначала назвала «людьми»
ряд, где отделены только роботы Метрики (класс 19), потом посчитала недостачу
витринам, закрытым от индексации решением (MOD-155). Сводка существует, чтобы
эти две ошибки нельзя было повторить незаметно.

Проверяется чистая функция `по_витрине`: ни сети, ни браузера.
"""
from __future__ import annotations

import importlib.util
import pathlib

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ПУТЬ = КОРЕНЬ / "automation" / "local" / "network-growth-state.py"

_с = importlib.util.spec_from_file_location("network_growth_state", ПУТЬ)
МОДУЛЬ = importlib.util.module_from_spec(_с)
assert _с.loader is not None
_с.loader.exec_module(МОДУЛЬ)
СЕГМ = МОДУЛЬ._сегменты()


def _профиль(дата: str, источник: str, браузер: str, робот: str,
             визиты: float) -> dict:
    return {
        "dimensions": [{"name": дата}, {"name": источник}, {"name": "PC"},
                       {"name": браузер}, {"name": робот}],
        "metrics": [визиты, 50.0, 1.2, 100.0],
    }


def _витрина(строки: list[dict], посадочные: list[str] | None = None) -> dict:
    меры = [{"key": "daily_traffic_profile", "measured": True,
             "value": строки}]
    if посадочные is not None:
        меры.append({
            "key": "daily_search_landing_pages", "measured": True,
            "value": [{"dimensions": [{"name": "2026-10-20"}, {"name": п}],
                       "metrics": [1.0, 1.0]} for п in посадочные],
        })
    return {"domain": "fixture-one.test", "measurements": меры}


def test_автоматизация_в_реальные_визиты_не_попадает():
    я = _витрина([
        _профиль("2026-10-20", "Search engine traffic", "Yandex Browser",
                 "People", 100.0),
        _профиль("2026-10-20", "Direct traffic", "HeadlessChrome", "People",
                 900.0),
        _профиль("2026-10-20", "Direct traffic", "Chrome Mobile", "Robots",
                 300.0),
    ])
    итог = МОДУЛЬ.по_витрине(я, СЕГМ)
    assert итог["реальные_в_сутки"] == 100.0, итог
    assert итог["поиск_доля"] == 100.0, итог
    assert итог["суток"] == 1


def test_доля_поиска_считается_от_реальных_а_не_от_всего():
    я = _витрина([
        _профиль("2026-10-20", "Search engine traffic", "Opera", "People",
                 30.0),
        _профиль("2026-10-20", "Direct traffic", "Opera", "People", 70.0),
        _профиль("2026-10-20", "Direct traffic", "HeadlessChrome", "People",
                 900.0),
    ])
    итог = МОДУЛЬ.по_витрине(я, СЕГМ)
    assert итог["реальные_в_сутки"] == 100.0
    assert итог["поиск_доля"] == 30.0


def test_без_профиля_суток_визиты_это_не_ноль_а_не_измерено():
    """Ноль и «не измерено» — разные утверждения, и путать их нельзя:
    по нулю пишут недостачу, по «не измерено» идут измерять."""
    я = {"domain": "fixture-one.test", "measurements": []}
    итог = МОДУЛЬ.по_витрине(я, СЕГМ)
    assert итог["реальные_в_сутки"] is None
    assert итог["поиск_доля"] is None
    assert итог["суток"] == 0


def test_страницы_с_визитами_считаются_по_разным_адресам():
    я = _витрина(
        [_профиль("2026-10-20", "Search engine traffic", "Opera", "People",
                  10.0)],
        посадочные=["/title/a/", "/title/a/?utm=1", "/title/b/"])
    итог = МОДУЛЬ.по_витрине(я, СЕГМ)
    # Параметры отбрасываются: это один и тот же адрес.
    assert итог["страниц_с_визитами"] == 2, итог
