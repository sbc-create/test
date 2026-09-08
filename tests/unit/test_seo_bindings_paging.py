"""Постраничная выдача связей: числа из строки запроса.

Handoff 043 сообщал, что выдача отвергает `offset`. Проверка исполнением
показала, что не работает и `limit`: строка запроса приносит числа строками,
прикладная функция требует целых, а границы, приводящей одно к другому, не
было. Потребитель мог взять только первую страницу.
"""

from __future__ import annotations

import pytest

from factory.site_engine.api.control import ControlDenied, _целое


def test_строка_приводится_к_целому():
    """`?limit=50&offset=100` приносит строки, а не числа."""
    assert _целое("100", "offset") == 100
    assert isinstance(_целое("100", "offset"), int)


def test_целое_проходит_как_есть():
    assert _целое(50, "limit") == 50


def test_пробелы_не_мешают():
    assert _целое(" 100 ", "offset") == 100


@pytest.mark.parametrize("плохое", ["abc", "", None, "1.5", []])
def test_нечисло_отвергается_а_не_подменяется_умолчанием(плохое):
    """Умолчание означало бы, что `?offset=abc` тихо вернёт первую страницу:
    вызывающий получит ответ на вопрос, которого не задавал, и решит, что
    записей больше нет."""
    with pytest.raises(ControlDenied) as отказ:
        _целое(плохое, "offset")
    assert отказ.value.status == 400
    assert отказ.value.code == "invalid_paging"


def test_булево_целым_не_считается():
    """`True` в Python равен единице, и `?offset=true` дало бы смещение 1."""
    with pytest.raises(ControlDenied, match="не булево"):
        _целое(True, "offset")


def test_отрицательное_приводится_и_отвергается_прикладной_функцией():
    """Граница приводит тип, а правило остаётся у прикладной функции: два
    места для одной проверки разошлись бы."""
    assert _целое("-5", "offset") == -5
    from factory.site_engine.api import seo_bindings
    import inspect
    assert "offset < 0" in inspect.getsource(seo_bindings.страница)
