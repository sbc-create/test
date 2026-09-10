"""Прокси витрины Yummy обязан переносить заголовки ответа, а не один тип.

Дефект `YUMMY-PROXY-DROPS-LOCATION-45`.

Приложение витрины canonical-редирект отдаёт правильно:

    GET /anime/dara-iz-reyvy--019efa52-db2d-7ef0-ac9f-29bda090bcd8
    308 Permanent Redirect
    location: /anime/dara-iz-reyvy

Прокси переносил наверх только `Content-Type`. Заголовок `Location` терялся, и
наружу уходил 308 без адреса перехода и с типом `application/octet-stream`:
браузер такой ответ показать не может, а краулер видит битую ссылку. Снаружи
это выглядело как «карточки строят нерабочие адреса `slug--UUID`», хотя
адреса были верны, а ломал их посредник.

Здесь закрепляется перенос заголовков, а не поведение приложения.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import re
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
ФРОНТ = КОРЕНЬ / "automation" / "host" / "yummy-frontend.py"


def _исходник() -> str:
    return ФРОНТ.read_text(encoding="utf-8")


class TestПереносЗаголовков:
    def test_location_переносится(self):
        т = _исходник()
        assert "Location" in т or "location" in т, (
            "прокси не упоминает Location: canonical-редирект потеряется")

    def test_переносится_не_только_тип(self):
        """Явный список переносимых заголовков, а не один Content-Type."""
        т = _исходник()
        assert "ПЕРЕНОСИМЫЕ" in т, (
            "нет списка переносимых заголовков ответа")

    def test_список_включает_ключевые(self):
        т = _исходник()
        начало = т.index("ПЕРЕНОСИМЫЕ")
        кусок = т[начало:начало + 600].lower()
        for имя in ("location", "cache-control", "content-language"):
            assert имя in кусок, f"заголовок {имя} не переносится"

    def test_тип_не_подменяется_на_octet_stream(self):
        """У редиректа тела нет, и выдумывать ему тип нельзя."""
        т = _исходник()
        assert "application/octet-stream" not in т or "не подменяется" in т, (
            "octet-stream остаётся значением по умолчанию для ответов без тела")


class TestКанонические:
    """Контракт адресов: карточки ведут на canonical, а не на slug--UUID."""

    ХВОСТ_UUID = re.compile(
        r"--[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

    def test_канонический_путь_есть_в_модуле_страниц(self):
        м = (КОРЕНЬ / "automation" / "host" / "yummy_pages.py").read_text(encoding="utf-8")
        assert "канонический_путь" in м, (
            "нет единого преобразования адреса к каноническому виду")

    def test_карточка_не_печатает_uuid_хвост(self):
        """Плитка обязана вести на canonical, даже если в данных пришёл uuid."""
        м = (КОРЕНЬ / "automation" / "host" / "yummy_pages.py").read_text(encoding="utf-8")
        начало = м.index("def карточка")
        тело = м[начало:м.index("\ndef ", начало + 10)]
        assert "канонический_путь" in тело, (
            "карточка собирает ссылку сама, минуя канонический контракт")
