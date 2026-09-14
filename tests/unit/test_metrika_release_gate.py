"""Ворота релиза: тег Метрики не должен исчезать из рендерера.

Эти ворота появились после того, как тег уже однажды пропал. Он был добавлен
в шаблоны, а следующая переработка шаблонов Zona и Animedia принесла два
новых `<head>` — и про вставку в них просто не вспомнили. Страницы при этом
продолжали отдаваться как ни в чём не бывало: пропажу было бы видно только по
отчёту Метрики через сутки.

Поэтому проверяется не «есть ли тег в шаблоне», а поведение единственной
точки отдачи ответа. Новый шаблон не может её обойти, а если кто-нибудь
уберёт саму вставку, упадут эти ворота, а не отчёт владельца через сутки.
"""
from __future__ import annotations

import importlib.util
import os
import pathlib
import sys

import pytest

РЕНДЕРЕР = pathlib.Path(__file__).resolve().parents[2] / "automation/host/lords-frontend.py"

#: Домен → счётчик. Источник — config/analytics.json и readback API Метрики.
#: Дубли здесь запрещены: один счётчик на двух доменах сливает две аудитории
#: в один отчёт, и заметить это можно только по чужому росту посещаемости.
КАРТА = {
    "lordfilm47.space": 112010269,
    "lordserial33.biz": 112010274,
    "1lordserials1.online": 112010277,
    "zonafilm.space": 112582938,
}

СТРАНИЦА = (b"<!doctype html><html><head><title>x</title></head>"
            b"<body>y</body></html>")


def _модуль(counter: str):
    """Загрузить рендерер с заданным счётчиком, не запуская сервер."""
    прежнее = os.environ.get("LORDS_METRIKA_COUNTER")
    os.environ["LORDS_METRIKA_COUNTER"] = counter
    try:
        spec = importlib.util.spec_from_file_location("_nova_gate", РЕНДЕРЕР)
        m = importlib.util.module_from_spec(spec)
        sys.modules["_nova_gate"] = m
        spec.loader.exec_module(m)
        return m
    finally:
        if прежнее is None:
            os.environ.pop("LORDS_METRIKA_COUNTER", None)
        else:
            os.environ["LORDS_METRIKA_COUNTER"] = прежнее


def test_вставка_живёт_в_отдаче_ответа_а_не_в_шаблоне():
    """Место вставки важнее самой вставки: шаблон её потеряет, отдача — нет."""
    текст = РЕНДЕРЕР.read_text(encoding="utf-8")
    assert "def со_счётчиком(" in текст, "функция вставки исчезла"
    вызов = текст.index("тело = со_счётчиком(тело, тип)")
    отдача = текст.index("def _отдать(")
    assert вызов > отдача, "вставка вызывается не из отдачи ответа"
    assert текст.count("тело = со_счётчиком(тело, тип)") == 1, (
        "вставок больше одной: двойная вставка даёт два счётчика на странице")


@pytest.mark.parametrize("домен,счётчик", sorted(КАРТА.items()))
def test_каждый_домен_получает_свой_счётчик(домен, счётчик):
    m = _модуль(str(счётчик))
    вышло = m.со_счётчиком(СТРАНИЦА, "text/html; charset=utf-8").decode("utf-8")
    assert f'ym({счётчик},"init"' in вышло, домен
    чужие = [c for c in КАРТА.values() if c != счётчик and f"ym({c}," in вышло]
    assert чужие == [], f"{домен}: на странице чужой счётчик {чужие}"


def test_счётчиков_на_домен_ровно_один():
    """Один счётчик на домен. Общий собрал бы визиты соседних витрин в один отчёт."""
    assert len(set(КАРТА.values())) == len(КАРТА)


@pytest.mark.parametrize("счётчик", sorted(КАРТА.values()))
def test_тег_ровно_один_раз(счётчик):
    m = _модуль(str(счётчик))
    вышло = m.со_счётчиком(СТРАНИЦА, "text/html; charset=utf-8")
    assert вышло.count(b"metrika/tag.js") == 1
    assert вышло.count(b'ym(%d,"init"' % счётчик) == 1


def test_повторная_отдача_не_добавляет_второй_тег():
    """Страница, прошедшая отдачу дважды, не получает двух счётчиков."""
    m = _модуль("112010269")
    один = m.со_счётчиком(СТРАНИЦА, "text/html; charset=utf-8")
    два = m.со_счётчиком(один, "text/html; charset=utf-8")
    assert один == два
    assert два.count(b"metrika/tag.js") == 1


def test_без_счётчика_тега_нет():
    """Пустое значение даёт страницу без тега, а не тег, который молчит."""
    m = _модуль("")
    вышло = m.со_счётчиком(СТРАНИЦА, "text/html; charset=utf-8")
    assert вышло == СТРАНИЦА
    assert b"mc.yandex" not in вышло


@pytest.mark.parametrize("мусор", ["", "  ", "abc", "112010269; rm -rf /",
                                   "0x1b", "-5", "112010269 112010274"])
def test_негодное_значение_не_попадает_на_страницу(мусор):
    """Счётчиком считается только число. Всё прочее даёт страницу без тега."""
    m = _модуль(мусор)
    вышло = m.со_счётчиком(СТРАНИЦА, "text/html; charset=utf-8")
    assert b"mc.yandex" not in вышло, f"на страницу попало {мусор!r}"


def test_не_html_не_размечается():
    m = _модуль("112010269")
    тело = b'{"a":1}'
    assert m.со_счётчиком(тело, "application/json") == тело


def test_инициализация_защёлкнута_от_повтора():
    """Защёлка стоит в самом теге: две вставки на одной странице дали бы
    два просмотра одного визита."""
    m = _модуль("112010269")
    тег = m.тег_метрики()
    assert "__sfMetrikaReady" in тег
    assert тег.count('"init"') == 1


def test_параметры_сбора_заданы_явно():
    """trackLinks и accurateTrackBounce — измеримое качество данных.
    Вебвизор выключен: реестр требует от него false."""
    тег = _модуль("112010269").тег_метрики()
    assert "trackLinks:true" in тег
    assert "accurateTrackBounce:true" in тег
    assert "webvisor:false" in тег


def test_тег_не_задерживает_отрисовку():
    assert "k.async=1" in _модуль("112010269").тег_метрики()
