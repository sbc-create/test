"""Проверка publisher_id: имя параметра провайдера и два признака.

Измерено 2026-10-05 на lordserials22.info: SDK провайдера запрашивает плейлист
адресом

    https://plapi.cdnvideohub.com/api/v1/player/sv/playlist?pub=10238&aggr=cvh&id=…

то есть идентификатор издателя уходит параметром `pub`, а не `publisher_id`.
Первая версия проверки искала только длинное имя, не находила ничего и
отвечала «в запросах провайдера: нет» — то есть выдавала дефект измерителя за
факт о витрине. Поэтому выражение закреплено тестом.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ИНСТРУМЕНТ = КОРЕНЬ / "automation" / "local" / "publisher-id-check.py"


def _модуль():
    спец = importlib.util.spec_from_file_location("publisher_id_check",
                                                  ИНСТРУМЕНТ)
    модуль = importlib.util.module_from_spec(спец)
    try:
        спец.loader.exec_module(модуль)
    except ImportError as ош:
        pytest.skip(f"инструмент не импортируется здесь: {ош}")
    return модуль


ЗАПРОСЫ_ПРОВАЙДЕРА = [
    ("https://plapi.cdnvideohub.com/api/v1/player/sv/playlist"
     "?pub=10238&aggr=cvh&id=01a10655-0e15-724f-9494-9606ea9db04f", "10238"),
    ("https://plapi.cdnvideohub.com/api/v1/player/sv/playlist"
     "?pub=10374&aggr=cvh&id=deadbeef", "10374"),
    ("https://example.test/init?publisher_id=10261&x=1", "10261"),
    ("https://example.test/init?publisherId=10252", "10252"),
    ("https://example.test/init?pub-id=10332", "10332"),
]


@pytest.mark.parametrize("url,ожидание", ЗАПРОСЫ_ПРОВАЙДЕРА)
def test_идентификатор_вынимается_из_запроса(url, ожидание):
    м = _модуль()
    assert м.ИЗ_ЗАПРОСА.findall(url) == [ожидание], url


def test_посторонние_числа_не_считаются_издателем():
    """Иначе проверка называла бы издателем размер кадра или метку времени."""
    м = _модуль()
    for url in (
        "https://poster.cdnvideohub.com/01a0fb75-a6d7-7b11-b021-6770a5e24759.webp",
        "https://player.cdnvideohub.com/s2/v2.31.11/frame/index.js",
        "https://example.test/x?width=10238",
        "https://example.test/x?t=1762345678",
    ):
        assert м.ИЗ_ЗАПРОСА.findall(url) == [], url


def test_проверка_смотрит_оба_признака_и_воспроизведение():
    """Совпадение идентификаторов без растущего времени ничего не значит."""
    текст = ИНСТРУМЕНТ.read_text(encoding="utf-8")
    assert "data-publisher-id" in текст, "вход витрины не читается"
    assert "ИЗ_ЗАПРОСА" in текст, "что ушло провайдеру — не читается"
    assert "currentTime" in текст and "воспроизведение ИДЁТ" in текст, (
        "проверка не подтверждает воспроизведение")
    # Обход теневых корней обязателен: плеер VK держит <video> в shadow DOM.
    assert "shadowRoot" in текст


def test_формы_адреса_совпадают_с_проверенной_таблицей():
    """Зашитый `/title/` не нашёл бы карточку у Yummy: там `/anime/<slug>`."""
    м = _модуль()
    from factory.qwen import registry

    формы = {ф.split("{", 1)[0] for ф in registry.ФОРМА_АДРЕСА.values()}
    for префикс in м.ПРЕФИКСЫ:
        assert префикс in формы, (
            f"{префикс} нет среди проверенных форм {sorted(формы)}")
