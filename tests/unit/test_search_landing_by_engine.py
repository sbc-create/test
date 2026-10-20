"""Показатель «входы по странице И поисковой системе».

Зачем он есть. `search_landing_pages` знает страницу, `daily_search` знает
поисковик, и ни один не знает обоих. Измерено 2026-10-20: у lordserials22.info
Google дал +603 визита за неделю, Яндекс потерял 23, а `/title/akademiya-vedm/`
упал с 56 входов до 10 — в каком из каналов, сказать было нечем.

Проверяется:

* показатель запрашивается с тремя измерениями и метрикой визитов;
* в значение попадают только строки органики: иначе прямые заходы и переходы
  по ссылкам сложились бы в «поиск»;
* предел строк объявлен в `top_n`, потому что страница вне предела — это
  «вне первых N», а не ноль;
* отказ источника даёт «не измерено» с причиной, а не пустой список;
* подписи показателей берутся ПО КЛЮЧУ, а не по номеру в кортеже — вставка
  нового показателя в середину переставляла бы подписи уже собираемым.
"""
from __future__ import annotations

import pytest

from factory.errors import FactoryError
from seo_operator import analytics_collect

КЛЮЧ = "search_landing_by_engine"


def _строка(источник, поисковик, путь, визиты):
    return {"dimensions": [{"id": источник, "name": источник},
                           {"id": поисковик, "name": поисковик.title()},
                           {"name": путь}],
            "metrics": [визиты]}


class Источник:
    """Провайдер, который помнит, о чём его спросили."""

    def __init__(self, строки=None, падать=False):
        self.строки = строки if строки is not None else []
        self.падать = падать
        self.запросы = []

    def get_metrica_report(self, counter_id, **кв):
        self.запросы.append(кв)
        if set(кв.get("dimensions") or []) == {
                "ym:s:lastsignTrafficSource",
                "ym:s:lastsignSearchEngineRoot",
                "ym:s:startURLPath"}:
            if self.падать:
                raise FactoryError("429 от источника: повторы исчерпаны")
            return {"data": self.строки, "sampled": False, "sample_share": 1.0}
        return {"data": [], "sampled": False, "sample_share": 1.0}


def _собрать(источник):
    return {и.key: и for и in analytics_collect._metrika_daily_and_search(
        источник, 1, "7daysAgo", "yesterday")}


def test_показатель_собирается():
    и = _собрать(Источник([_строка("organic", "yandex", "/title/a/", 56.0)]))[КЛЮЧ]
    assert и.measured is True
    assert и.value == [_строка("organic", "yandex", "/title/a/", 56.0)]


def test_запрошены_три_измерения_и_визиты():
    источник = Источник([])
    _собрать(источник)
    нужный = [з for з in источник.запросы
              if "ym:s:startURLPath" in (з.get("dimensions") or [])
              and "ym:s:lastsignSearchEngineRoot" in (з.get("dimensions") or [])]
    assert len(нужный) == 1
    assert нужный[0]["metrics"] == ["ym:s:visits"]


def test_неорганика_в_значение_не_попадает():
    """Отрицательный контроль: прямые заходы — не поиск."""
    строки = [_строка("organic", "yandex", "/title/a/", 10.0),
              _строка("direct", "none", "/title/a/", 99.0),
              _строка("referral", "none", "/title/b/", 7.0)]
    и = _собрать(Источник(строки))[КЛЮЧ]
    assert len(и.value) == 1
    assert и.value[0]["dimensions"][0]["id"] == "organic"


def test_предел_строк_объявлен():
    и = _собрать(Источник([]))[КЛЮЧ]
    assert и.top_n == analytics_collect.ВХОДОВ_ПО_ПОИСКОВИКУ
    assert и.top_n >= 1000


def test_отказ_источника_даёт_не_измерено_а_не_пустоту():
    и = _собрать(Источник(падать=True))[КЛЮЧ]
    assert и.measured is False
    assert и.value in (None, analytics_collect.NOT_MEASURED)
    assert "429" in и.reason


def test_источник_показателя_назван():
    и = _собрать(Источник([]))[КЛЮЧ]
    for часть in ("ym:s:visits", "lastsignSearchEngineRoot", "startURLPath"):
        assert часть in и.source


# --- подписи по ключу, а не по номеру ----------------------------------------

@pytest.mark.parametrize("ключ", ("daily_users", "search_landing_pages",
                                  "daily_search", "daily_traffic_profile",
                                  КЛЮЧ))
def test_подпись_берётся_по_ключу(ключ):
    заголовок, источник = analytics_collect._мета(ключ)
    assert заголовок and источник


def test_подписи_не_перепутаны_между_показателями():
    """Ровно та ошибка, которую ловит обращение по ключу: вставка показателя
    в середину кортежа молча переставляла подписи уже собираемым."""
    собрано = _собрать(Источник([]))
    for ключ, и in собрано.items():
        if ключ in analytics_collect.ЭКСТРА_ПО_КЛЮЧУ:
            assert и.title == analytics_collect.ЭКСТРА_ПО_КЛЮЧУ[ключ][0]
            assert и.source == analytics_collect.ЭКСТРА_ПО_КЛЮЧУ[ключ][1]
