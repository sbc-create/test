"""REQ-LORDS-DURATION: длительности нет — значит, поля нет.

Найдено на боевой витрине `lordserial33.biz`: страница произведения несёт в
разметке `"duration": "PTNoneM"`. Так выглядит `f"PT{title.runtime_min}M"`,
когда источник длительности не назвал.

`PTNoneM` — не длительность и не её отсутствие: это строка, которую поисковая
система разберёт как ошибку разметки, а человек прочитает как сбой. Ноль
подошёл бы ещё меньше: он означал бы фильм нулевой длины.

Правило то же, что и для оценок: отсутствие числа не превращается ни в ноль,
ни в правдоподобную строку. Поля просто нет.
"""

from __future__ import annotations

import json
import re

import pytest

from factory.lords import render


class ЗаписьБезДлительности:
    """Минимальная запись: обогащение не дошло, длительности нет."""

    def __init__(self, runtime_min=None, episodic=False):
        self.runtime_min = runtime_min
        self.episodic = episodic
        self.name = "Проверочное произведение"
        self.original_name = ""
        self.summary = "Описание"
        self.genres = ("драма",)
        self.country = "Россия"
        self.studio = ""
        self.year = 2020
        self.seasons = ()
        self.episode_count = 0
        self.slug = "proverochnoe"
        self.kind = "MOVIE"


def _разметка(текст: str) -> list[dict]:
    из = []
    for кусок in re.findall(
            r'<script type="application/ld\+json">(.*?)</script>', текст, re.S):
        try:
            из.append(json.loads(кусок))
        except ValueError:
            pytest.fail(f"разметка не разбирается: {кусок[:200]}")
    return из


def test_pt_none_m_не_встречается_в_исходниках():
    """Прямая проверка формулы: она и порождала PTNoneM на витрине."""
    исходник = (render.__file__)
    with open(исходник, encoding="utf-8") as ф:
        текст = ф.read()
    assert 'f"PT{title.runtime_min}M"' not in текст, (
        "длительность подставляется без проверки: при отсутствующем значении "
        "на страницу уходит PTNoneM — измерено на lordserial33.biz")


def test_поле_длительности_отсутствует_когда_нет_числа():
    сущность = render._schema_duration(ЗаписьБезДлительности())
    assert сущность == {}, "у произведения без длительности поле не появляется"


def test_поле_длительности_есть_когда_число_есть():
    сущность = render._schema_duration(ЗаписьБезДлительности(runtime_min=97))
    assert сущность == {"duration": "PT97M"}


def test_ноль_не_выдаётся_за_длительность():
    # Ноль минут — это не фильм, а отсутствие данных, названное числом.
    assert render._schema_duration(ЗаписьБезДлительности(runtime_min=0)) == {}


def test_отрицательное_и_нечисловое_значение_не_попадают_в_разметку():
    for значение in (-5, "сорок", float("nan")):
        assert render._schema_duration(ЗаписьБезДлительности(runtime_min=значение)) == {}


def test_у_сериала_длительности_серии_вместо_общей_нет():
    сущность = render._schema_duration(ЗаписьБезДлительности(runtime_min=45, episodic=True))
    assert сущность == {}, (
        "у сериала duration описывал бы одну серию, а стоял бы у сериала целиком")
