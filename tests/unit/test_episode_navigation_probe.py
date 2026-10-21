"""Переход со страницы серии на следующую: две ловушки, обе уже сработавшие.

Ловушка первая — форма адреса. Хвостовой слэш у Lords, Zona и Animedia
(`/season-1/episode-2/`) не подходил под выражение, и проход печатал
«НЕ ИЗМЕРЕНО» у четырёх витрин из пяти: молчал там, где серии есть.

Ловушка вторая — предмет проверки. У произведения с ОДНОЙ серией «следующей» нет
по определению, и проход объявил дефектом исправную витрину, выбрав такую
работу. Теперь односерийные исключаются до измерения.

Ссылка на себя переходом не считается: страница, ссылающаяся сама на себя,
никуда не ведёт.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_с = importlib.util.spec_from_file_location(
    "episode_navigation_probe",
    КОРЕНЬ / "automation/local/episode-navigation-probe.py")
ИНС = importlib.util.module_from_spec(_с)
_с.loader.exec_module(ИНС)


@pytest.mark.parametrize("адрес", [
    "/title/a/season-1/episode-2",
    "/title/a/season-1/episode-2/",
    "/anime/a/season/1/episode/2",
    "/anime/a/season/1/episode/2/",
])
def test_обе_формы_адреса_и_хвостовой_слэш(адрес):
    найдено = ИНС.серии_на(f'<a href="{адрес}">серия</a>')
    assert len(найдено) == 1, адрес
    _, работа, сезон, номер = найдено[0]
    assert работа in ("/title/a", "/anime/a")
    assert (сезон, номер) == (1, 2)


def test_одиночные_кавычки_тоже_читаются():
    assert len(ИНС.серии_на("<a href='/title/a/season-1/episode-3/'>с</a>")) == 1


@pytest.fixture()
def сеть(monkeypatch):
    таблица: dict[str, str] = {}
    monkeypatch.setattr(ИНС, "достать",
                        lambda адрес, таймаут=40: таблица.get(адрес))
    return таблица


def _витрина(сеть, серий: int, ссылки_со_страницы: int | None = None,
             назад: bool = True):
    """Витрина с одной работой, у которой `серий` серий."""
    сеть["https://x.test/"] = '<a href="/title/a/">A</a>'
    карточка = "".join(
        f'<a href="/title/a/season-1/episode-{н}/">{н}</a>'
        for н in range(1, серий + 1))
    сеть["https://x.test/title/a/"] = карточка
    сколько = серий if ссылки_со_страницы is None else ссылки_со_страницы
    страница = "".join(
        f'<a href="/title/a/season-1/episode-{н}/">{н}</a>'
        for н in range(1, сколько + 1))
    if назад:
        страница += '<a href="/title/a/">назад</a>'
    сеть["https://x.test/title/a/season-1/episode-1"] = страница
    сеть["https://x.test/title/a/season-1/episode-1/"] = страница


def test_переход_на_соседнюю_серию_находится(сеть):
    _витрина(сеть, серий=3)
    итог = ИНС.проверить("x.test")
    assert итог["на_соседнюю_серию"] == 1
    assert итог["на_другие_серии_той_же_работы"] == 2
    assert итог["возврат_к_произведению"] is True
    assert итог["замечания"] == []


def test_односерийное_произведение_дефектом_не_объявляется(сеть):
    """Та самая ложная находка: «следующей» нет по определению."""
    _витрина(сеть, серий=1)
    итог = ИНС.проверить("x.test")
    assert "НЕ ИЗМЕРЕНО" in итог["замечания"][0]
    assert итог["односерийных_встречено"] == 1
    # И это НЕ утверждение о дефекте витрины.
    assert "смотреть дальше" not in " ".join(итог["замечания"])


def test_только_своя_серия_это_находка(сеть):
    """Страница ссылается лишь на себя — идти некуда."""
    _витрина(сеть, серий=3, ссылки_со_страницы=1)
    итог = ИНС.проверить("x.test")
    assert итог["на_другие_серии_той_же_работы"] == 0
    assert any("смотреть дальше" in з for з in итог["замечания"])


def test_есть_другие_но_нет_соседней(сеть):
    """Список серий есть, «следующая» не названа — это слабее, но не ок."""
    сеть["https://x.test/"] = '<a href="/title/a/">A</a>'
    сеть["https://x.test/title/a/"] = (
        '<a href="/title/a/season-1/episode-1/">1</a>'
        '<a href="/title/a/season-1/episode-5/">5</a>')
    страница = ('<a href="/title/a/season-1/episode-1/">1</a>'
                '<a href="/title/a/season-1/episode-5/">5</a>'
                '<a href="/title/a/">назад</a>')
    сеть["https://x.test/title/a/season-1/episode-1"] = страница
    сеть["https://x.test/title/a/season-1/episode-1/"] = страница
    итог = ИНС.проверить("x.test")
    assert итог["на_соседнюю_серию"] == 0
    assert итог["на_другие_серии_той_же_работы"] == 1
    assert any("соседней среди них нет" in з for з in итог["замечания"])


def test_нет_возврата_к_произведению_это_замечание(сеть):
    _витрина(сеть, серий=3, назад=False)
    итог = ИНС.проверить("x.test")
    assert итог["возврат_к_произведению"] is False
    assert any("назад на карточку" in з for з in итог["замечания"])


def test_чужая_работа_переходом_не_считается(сеть):
    """Ссылка на серию ДРУГОГО произведения — не «смотреть дальше»."""
    сеть["https://x.test/"] = '<a href="/title/a/">A</a>'
    сеть["https://x.test/title/a/"] = (
        '<a href="/title/a/season-1/episode-1/">1</a>'
        '<a href="/title/a/season-1/episode-2/">2</a>')
    страница = ('<a href="/title/a/season-1/episode-1/">я</a>'
                '<a href="/title/b/season-1/episode-9/">чужая</a>'
                '<a href="/title/a/">назад</a>')
    сеть["https://x.test/title/a/season-1/episode-1"] = страница
    сеть["https://x.test/title/a/season-1/episode-1/"] = страница
    итог = ИНС.проверить("x.test")
    assert итог["всего_ссылок_на_серии"] == 2
    assert итог["на_другие_серии_той_же_работы"] == 0


def test_непрочитанная_главная_это_не_измерено(сеть):
    итог = ИНС.проверить("x.test")
    assert "НЕ ИЗМЕРЕНО" in итог["замечания"][0]
