"""REQ-SOURCE-IDENTITY: без IMDb ID статья Википедии не читается вовсе.

Сверка личности в `source_fetch.film` ищет в статье «tt<цифры>». При пустом
или нечисловом ID выражение вырождается в поиск «tt», не продолженного цифрой
— а такая подстрока есть почти в любой статье («Attack», «better», «Mitte»).
Ответ был бы «идентичность подтверждена» для ЛЮБОЙ открывшейся страницы, и
факты чужого произведения попали бы в редакционный текст как проверенные.

Измерено 2026-10-19: в каталоге animedia-01 IMDb ID есть у 2427 тайтлов из
8655 — у 72 % его нет, то есть путь не редкий. Запросов тоже жалко: за ночь
18–19.10 из 683 обращений к Википедии 522 вернули 404.

Отрицательные контроли обязательны: с настоящим ID работа идёт как прежде, и
несовпадающий ID по-прежнему статью отклоняет.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_путь = КОРЕНЬ / "automation/local/source_fetch.py"
_спец = importlib.util.spec_from_file_location("source_fetch_identity", _путь)
СФ = importlib.util.module_from_spec(_спец)
_спец.loader.exec_module(СФ)

#: Страница, в которой «tt» есть, но не как часть IMDb ID. Ровно та ловушка.
СТРАНИЦА_ЛОВУШКА = (
    '<div class="mw-content-ltr mw-parser-output"><p>Attack on Titan — другое '
    "произведение, и лучше его не путать.</p></div>"
)
СТРАНИЦА_С_ИД = (
    '<div class="mw-content-ltr mw-parser-output"><p>Пример статьи.</p></div>'
    '<a href="https://www.imdb.com/title/tt0491603/">IMDb</a>'
)


@pytest.fixture
def без_сети(monkeypatch):
    """Любое обращение к Википедии в этом тесте — отказ: его быть не должно."""
    def нельзя(*а, **кв):
        raise AssertionError("запрос к Википедии при пустом ID недопустим")
    monkeypatch.setattr(СФ, "_wiki_article", нельзя)


@pytest.mark.parametrize("пустой", ["", "tt", "  ", "-", "нет", "abc", "tt-"])
def test_без_ид_статья_не_читается(пустой, без_сети):
    итог = СФ.film(пустой, "Название", "Name", "2026", "tv")
    assert итог["ok"] is False
    assert "идентичность подтвердить нечем" in итог["reason"]
    assert итог["tried"] == []


def test_ловушка_tt_без_цифр_не_принимается(monkeypatch):
    """Прямое доказательство дефекта: без защиты эта страница была бы принята."""
    обращения = []

    def подделка(lang, title, **_):
        обращения.append((lang, title))
        return 200, СТРАНИЦА_ЛОВУШКА, f"https://{lang}.wikipedia.org/wiki/{title}"

    monkeypatch.setattr(СФ, "_wiki_article", подделка)
    итог = СФ.film("", "Название", "Name", "2026", "tv")
    assert итог["ok"] is False
    assert обращения == [], "страница не должна была запрашиваться вовсе"
    # И то же самое через само выражение сверки: без цифр оно ловит «Attack».
    import re
    assert re.search(r"tt(?!\d)", СТРАНИЦА_ЛОВУШКА), (
        "ловушка перестала быть ловушкой — проверка потеряла смысл")


def test_настоящий_ид_работает_как_прежде(monkeypatch):
    """Отрицательный контроль: защита не мешает обычной работе."""
    monkeypatch.setattr(
        СФ, "_wiki_article",
        lambda lang, title, **_: (200, СТРАНИЦА_С_ИД,
                             f"https://{lang}.wikipedia.org/wiki/{title}"))
    итог = СФ.film("491603", "Название", "Name", "2026", "tv")
    assert итог["ok"] is True
    assert итог["source_id"] == "src-wikipedia"
    assert "tt0491603" in итог["identity"]


def test_чужой_ид_статью_отклоняет(monkeypatch):
    """Отрицательный контроль второй: сверка по-прежнему отвергает несовпадение."""
    monkeypatch.setattr(
        СФ, "_wiki_article",
        lambda lang, title, **_: (200, СТРАНИЦА_С_ИД,
                             f"https://{lang}.wikipedia.org/wiki/{title}"))
    итог = СФ.film("1210166", "Название", "Name", "2026", "tv")
    assert итог["ok"] is False
    assert "среди вариантов нет" in итог["reason"]
    assert итог["tried"], "варианты должны были перебираться"


def test_продолжение_цифрами_не_совпадение(monkeypatch):
    """Правка линии SEO остаётся в силе: tt1210166 ≠ tt12101660."""
    страница = '<a href="https://www.imdb.com/title/tt12101660/">IMDb</a>'
    monkeypatch.setattr(
        СФ, "_wiki_article",
        lambda lang, title, **_: (200, страница,
                             f"https://{lang}.wikipedia.org/wiki/{title}"))
    assert СФ.film("1210166", "Название", "Name", "2026", "tv")["ok"] is False
