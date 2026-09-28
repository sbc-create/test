"""Динамические сообщения объявляются экранным диктором.

Число найденного, «ничего не нашлось» и «указатель загружается» появляются
после загрузки страницы. Без живой области диктор их не произносит: для него
страница не изменилась, тогда как зрячий читатель видит изменение сразу.

Проверено измерением до правки: живых областей на витрине было ноль, при том
что сообщения писались в элемент на каждом запросе.
"""
from __future__ import annotations

import pathlib
import re

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ИСХОДНИК = КОРЕНЬ / "factory" / "lords" / "render.py"


@pytest.fixture(scope="module")
def исходник() -> str:
    return ИСХОДНИК.read_text("utf-8")


class TestЖиваяОбласть:
    def test_каждое_объявление_счётчика_живое(self, исходник):
        объявления = re.findall(r'<p class="count" id="search-count"[^>]*', исходник)
        assert объявления, "элемент сообщений поиска не найден"
        немые = [о for о in объявления if 'aria-live' not in о]
        assert немые == [], f"объявление без живой области: {немые[:1]}"

    def test_роль_указана(self, исходник):
        объявления = re.findall(r'<p class="count" id="search-count"[^>]*', исходник)
        assert all('role="status"' in о for о in объявления)

    def test_вежливый_режим(self, исходник):
        """`assertive` прерывает чтение; для счётчика результатов это грубо."""
        assert 'aria-live="assertive"' not in исходник

    def test_сообщения_пишутся_именно_в_этот_элемент(self, исходник):
        assert 'getElementById("search-count")' in исходник
