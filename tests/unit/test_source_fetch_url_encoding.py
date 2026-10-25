"""Адрес источника с нелатинским названием обязан быть запрашиваемым.

Измерено 25.10: `source_fetch.py page https://ru.wikipedia.org/wiki/Правила_…`
падал с `UnicodeEncodeError: 'ascii' codec can't encode characters` внутри
http.client — то есть ЛЮБОЙ записанный источник с русским названием в адресе
этим путём прочитать было нельзя. Отказ при этом выглядел поломкой
инструмента, а не свойством адреса, и поэтому мог годами не исправляться:
редактор записывал такой источник при подготовке (путь `film` строит адрес
сам и кодирует его), а перечитать его при рецензии было нечем.

Проверка держит два края: нелатинский путь кодируется, а уже закодированный
адрес не кодируется ВТОРОЙ раз (иначе «%D0» стало бы «%25D0» и источник
подменился бы на несуществующий).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ПУТЬ = (Path(__file__).resolve().parents[2] / "automation" / "local"
        / "source_fetch.py")


def _модуль():
    спец = importlib.util.spec_from_file_location("source_fetch", ПУТЬ)
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


МОД = _модуль()


def test_кириллический_путь_кодируется():
    из = МОД.безопасный_адрес(
        "https://ru.wikipedia.org/wiki/Правила_совместной_жизни")
    assert из.startswith("https://ru.wikipedia.org/wiki/%D0%9F")
    из.encode("ascii")  # запрос обязан кодироваться в ASCII


def test_уже_закодированный_адрес_не_кодируется_повторно():
    было = "https://ru.wikipedia.org/wiki/%D0%9F%D1%80%D0%B0%D0%B2%D0%B8%D0%BB%D0%B0"
    assert МОД.безопасный_адрес(было) == было


def test_латинский_адрес_не_меняется():
    было = "https://en.wikipedia.org/wiki/So_Cold_the_River"
    assert МОД.безопасный_адрес(было) == было


def test_схема_и_хост_сохраняются():
    из = МОД.безопасный_адрес("https://shikimori.io/animes/61967")
    assert из == "https://shikimori.io/animes/61967"


def test_запрос_и_якорь_не_ломаются():
    из = МОД.безопасный_адрес(
        "https://example.org/путь?ключ=значение&b=2#раздел")
    из.encode("ascii")
    assert "?" in из and "&b=2" in из and "#" in из


def test_запрос_использует_безопасный_адрес():
    """Исправление обязано стоять на входе ЛЮБОГО запроса, а не в одном пути."""
    исходник = ПУТЬ.read_text(encoding="utf-8")
    начало = исходник.index("def _get(")
    тело = исходник[начало:начало + 700]
    assert "безопасный_адрес(url)" in тело, (
        "запрос идёт мимо кодирования: тогда один путь исправлен, а остальные"
        " падают на том же адресе")
