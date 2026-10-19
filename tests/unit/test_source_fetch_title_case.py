"""REQ-SOURCE-TITLE-CASE: вариант статьи с приведённым регистром служебных слов.

Повод (линия SEO, 19.10): варианты статьи строятся из названия каталога
буквально, а Википедия различает регистр всех букв, кроме первой. Каталог
1lordserials1.online даёт «007: Road to A Million»; проверено 19.10 06:30Z:

    en.wikipedia.org/wiki/007:_Road_to_A_Million  → 404
    en.wikipedia.org/wiki/007:_Road_to_a_Million  → 200, tt19049680 в статье

Приведение только ДОБАВЛЯЕТ вариант: личность по-прежнему подтверждается IMDb
ID в статье, поэтому лишний вариант стоит одного запроса и подменить
произведение не может.

Границы правила проверяются отдельно: начало названия и начало сегмента после
знака («Hey Arnold! The Movie») остаются с большой буквы — там и Википедия
пишет с большой.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_путь = КОРЕНЬ / "automation/local/source_fetch.py"
_спец = importlib.util.spec_from_file_location("source_fetch_title_case", _путь)
СФ = importlib.util.module_from_spec(_спец)
_спец.loader.exec_module(СФ)

СТАТЬЯ = ('<div class="mw-content-ltr mw-parser-output"><p>Пример.</p></div>'
          '<a href="https://www.imdb.com/title/tt19049680/">IMDb</a>')


@pytest.mark.parametrize("было,стало", [
    ("007: Road to A Million", "007: Road to a Million"),
    ("Everlasting God Of Sword", "Everlasting God of Sword"),
    ("Choujigen Game Neptune The Animation OVA",
     "Choujigen Game Neptune the Animation OVA"),
    # Начало названия — не служебное положение.
    ("The Movie", "The Movie"),
    # После знака сегмент начинается заново: Википедия тоже пишет с большой.
    ("Hey Arnold! The Movie", "Hey Arnold! The Movie"),
    ("101 Dalmatians: The Series", "101 Dalmatians: The Series"),
    ("Jigoku Sensei Nube: The Movie", "Jigoku Sensei Nube: The Movie"),
    # Уже строчные — без изменений.
    ("Road to a Million", "Road to a Million"),
    # Пустое и однословное.
    ("", ""),
    ("Naruto", "Naruto"),
])
def test_приведение_регистра(было, стало):
    assert СФ.регистр_служебных(было) == стало


def test_приведённый_вариант_пробуется_после_литерального(monkeypatch):
    """Литеральный вариант остаётся первым: прежнее поведение не меняется."""
    обращения = []

    def подделка(lang, title, **_):
        обращения.append(f"{lang}:{title}")
        если_тот = title == "007: Road to a Million"
        return (200 if если_тот else 404), (СТАТЬЯ if если_тот else ""), \
               f"https://{lang}.wikipedia.org/wiki/{title}"

    monkeypatch.setattr(СФ, "_wiki_article", подделка)
    итог = СФ.film("19049680", "", "007: Road to A Million", "2023", "tv")
    assert итог["ok"] is True
    assert итог["url"].endswith("007: Road to a Million")
    assert обращения[0] == "en:007: Road to A Million", обращения
    assert "en:007: Road to a Million" in обращения


def test_без_изменений_лишних_запросов_нет(monkeypatch):
    """Если приведение ничего не меняет, вторая база не добавляется."""
    обращения = []

    def подделка(lang, title, **_):
        обращения.append(title)
        return 404, "", f"https://{lang}.wikipedia.org/wiki/{title}"

    monkeypatch.setattr(СФ, "_wiki_article", подделка)
    СФ.film("19049680", "", "Naruto", "2002", "tv")
    # три английских суффикса для сериала и ни одного повтора
    assert len(обращения) == 3, обращения
    assert len(set(обращения)) == 3


def test_отрицательный_контроль_ни_один_вариант_не_подошёл(monkeypatch):
    monkeypatch.setattr(
        СФ, "_wiki_article",
        lambda lang, title, **_: (404, "", f"https://{lang}.wikipedia.org/wiki/{title}"))
    итог = СФ.film("19049680", "Имя", "Name Of Thing", "2023", "tv")
    assert итог["ok"] is False
    адреса = [з["url"] for з in итог["tried"]]
    assert any("Name_Of_Thing" in а or "Name Of Thing" in а for а in адреса)
    assert any("Name of Thing" in а or "Name_of_Thing" in а for а in адреса)


def test_чужая_статья_по_приведённому_варианту_не_принимается(monkeypatch):
    """Главная защита остаётся на месте: вариант без нужного IMDb отвергается."""
    monkeypatch.setattr(
        СФ, "_wiki_article",
        lambda lang, title, **_: (200, '<a href="/title/tt0000001/">IMDb</a>',
                                  f"https://{lang}.wikipedia.org/wiki/{title}"))
    assert СФ.film("19049680", "Имя", "Name Of Thing", "2023", "tv")["ok"] is False
