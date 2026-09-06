"""Выдача контракта через Site View API.

Без этой выдачи контракт существовал только в виде кода: собрать его у себя
было можно, получить у работающего движка — нельзя. А потребитель обязан
читать контракт у движка, иначе у контракта два источника, и они разъедутся на
первой же правке любого из них.

Проверки идут на подставном корне с маленькими наборами: настоящий каталог —
пятьдесят три тысячи записей, и проверка, которая его читает, перестаёт быть
быстрой, а быстрая проверка — та, которую запускают.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.site_engine.api import seo_bindings as api

ИСТОЧНИКИ = """
version: "1.0.0"
sites:
  demo-lords:
    producer: computed-routes
    catalog: var/catalog.json
  demo-declared:
    producer: declared-routes
    routes: var/routes.json
    catalog: var/catalog.json
  demo-broken:
    producer: несуществующий
    catalog: var/catalog.json
"""


def запись(pid: str, name: str, **kwargs) -> dict:
    основа = {
        "external_id": pid, "name": name, "type": "tv", "is_series": True,
        "tags": [], "year": 2026,
        "playback": {"aggregator": "kp", "title_id": "1"},
        "external_ids": {"kp": "1"},
    }
    основа.update(kwargs)
    return основа


@pytest.fixture
def корень(tmp_path: Path) -> Path:
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "seo-binding-sources.yaml").write_text(
        ИСТОЧНИКИ, encoding="utf-8")
    (tmp_path / "var").mkdir()
    каталог = [запись(f"p-{i:03d}", f"Работа {i:03d}") for i in range(12)]
    каталог.append(запись("p-conf", "Конфликт", type="movie", tags=["ona"]))
    (tmp_path / "var" / "catalog.json").write_text(
        json.dumps({"items": каталог, "fetched_at_ms": 1788000000000}),
        encoding="utf-8")
    (tmp_path / "var" / "routes.json").write_text(json.dumps({
        "siteId": "demo-declared", "fetchedAt": "2026-09-06T05:00:00+00:00",
        "source": "container:test", "items": [
            {"slug": f"rabota-{i:03d}", "providerTitleId": f"p-{i:03d}",
             "canonical": True} for i in range(12)
        ] + [{"slug": "konflikt", "providerTitleId": "p-conf",
              "canonical": True}]}), encoding="utf-8")
    return tmp_path


# --- перечень витрин ---------------------------------------------------------

def test_перечень_витрин_называет_производителя(корень):
    каталог = api.каталог_витрин(корень)
    assert каталог["contract"] == "seo-route-binding/1.0.0"
    имена = {s["siteId"]: s["producer"] for s in каталог["sites"]}
    assert имена["demo-lords"] == "computed-routes"
    assert имена["demo-declared"] == "declared-routes"


def test_витрина_вне_настройки_получает_отказ(корень):
    with pytest.raises(api.BindingSourceUnknown, match="не описана"):
        api.страница(корень, "нет-такой")


def test_неизвестный_производитель_получает_отказ(корень):
    """Список производителей закрыт: новый — это адаптер, а не строка."""
    with pytest.raises(api.BindingSourceUnknown, match="неизвестен"):
        api.страница(корень, "demo-broken")


# --- страницы ----------------------------------------------------------------

def test_выдача_постраничная(корень):
    первая = api.страница(корень, "demo-declared", offset=0, limit=5)
    assert первая["returned"] == 5
    assert первая["hasMore"] is True
    вторая = api.страница(корень, "demo-declared", offset=5, limit=5)
    assert вторая["returned"] == 5
    assert {b["contentId"] for b in первая["bindings"]} \
        & {b["contentId"] for b in вторая["bindings"]} == set()


def test_последняя_страница_не_обещает_продолжения(корень):
    полная = api.страница(корень, "demo-declared", limit=500)
    последняя = api.страница(корень, "demo-declared",
                             offset=полная["records"] - 2, limit=500)
    assert последняя["hasMore"] is False


def test_отпечаток_считается_по_всему_набору_а_не_по_странице(корень):
    """Иначе он перестал бы отвечать на вопрос «изменились ли данные»."""
    первая = api.страница(корень, "demo-declared", offset=0, limit=2)
    вторая = api.страница(корень, "demo-declared", offset=6, limit=2)
    assert первая["digest"] == вторая["digest"]
    assert первая["records"] == вторая["records"]


def test_предел_страницы_проверяется(корень):
    for плохой in (0, -1, 501, "много", True):
        with pytest.raises(ValueError, match="limit"):
            api.страница(корень, "demo-declared", limit=плохой)


def test_смещение_проверяется(корень):
    with pytest.raises(ValueError, match="offset"):
        api.страница(корень, "demo-declared", offset=-1)


def test_смещение_за_концом_даёт_пустую_страницу_а_не_ошибку(корень):
    итог = api.страница(корень, "demo-declared", offset=10_000, limit=10)
    assert итог["returned"] == 0
    assert итог["hasMore"] is False
    assert итог["records"] > 0


# --- отбор по состоянию ------------------------------------------------------

def test_очередь_разбора_получается_одним_запросом(корень):
    итог = api.страница(корень, "demo-declared", binding_state="KIND_UNRESOLVED")
    assert итог["returned"] >= 1
    assert all(b["bindingState"] == "KIND_UNRESOLVED" for b in итог["bindings"])
    assert итог["filter"] == {"bindingState": "KIND_UNRESOLVED"}
    # Сводка по всему набору остаётся полной, а не сужается фильтром.
    assert итог["byBindingState"].get("BOUND", 0) > 0


def test_отбор_не_меняет_отпечаток_и_счёт_набора(корень):
    без = api.страница(корень, "demo-declared", limit=1)
    с_отбором = api.страница(корень, "demo-declared", limit=1,
                             binding_state="BOUND")
    assert без["digest"] == с_отбором["digest"]
    assert без["records"] == с_отбором["records"]


# --- содержимое --------------------------------------------------------------

def test_страница_несёт_версию_контракта_и_происхождение(корень):
    итог = api.страница(корень, "demo-declared", limit=1)
    assert итог["schemaVersion"] == "seo-route-binding/1.0.0"
    assert итог["contractVersion"] == "1.0.0"
    assert итог["provenance"]
    assert итог["snapshotAt"]


def test_оба_производителя_отдают_один_контракт(корень):
    объявленный = api.страница(корень, "demo-declared", limit=1)
    вычисленный = api.страница(корень, "demo-lords", limit=1)
    assert объявленный["schemaVersion"] == вычисленный["schemaVersion"]
    поля = set(объявленный["bindings"][0]) ^ set(вычисленный["bindings"][0])
    assert not поля, f"состав полей разошёлся: {поля}"


def test_конфликтная_запись_разметки_не_получает(корень):
    итог = api.страница(корень, "demo-declared", limit=500,
                        binding_state="KIND_UNRESOLVED")
    for b in итог["bindings"]:
        assert b["schemaType"] == ""
        assert b["contentKind"] == "UNKNOWN"


def test_секретов_в_выдаче_нет(корень):
    сырьё = json.dumps(api.страница(корень, "demo-declared", limit=500),
                       ensure_ascii=False).lower()
    for запрещённое in ("token", "secret", "password", "m3u8", "aggregator",
                        "title_id", "postgres"):
        assert запрещённое not in сырьё, запрещённое
