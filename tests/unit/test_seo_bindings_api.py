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


# --- адрес страницы ----------------------------------------------------------
#
# У потребителя на входе адреса, а контракт отдаёт связи по маршрутам страниц
# произведений. Разбирать вложенный адрес на своей стороне значит зашивать
# форму адресов витрины в потребителя — ровно та догадка, ради запрета которой
# контракт и написан.

def test_адрес_произведения_разрешается_в_связь(корень):
    итог = api.разрешить(корень, "demo-declared", "/anime/rabota-003/")
    assert итог["resolved"] is True
    assert итог["pageType"] == "title"
    assert итог["inheritsFrom"] == ""
    assert итог["binding"]["contentId"] == "p-003"
    assert итог["schemaVersion"] == "seo-route-binding/1.0.0"


@pytest.mark.parametrize("путь, тип", [
    ("/anime/rabota-003/season/1", "season"),
    ("/anime/rabota-003/season/2/episode/7", "episode"),
])
def test_вложенный_адрес_наследует_связь_произведения(корень, путь, тип):
    итог = api.разрешить(корень, "demo-declared", путь)
    assert итог["resolved"] is True
    assert итог["pageType"] == тип
    assert итог["inheritsFrom"] == "/anime/rabota-003/"
    assert итог["binding"]["contentId"] == "p-003"


def test_право_обещать_просмотр_наследуется_вместе_со_связью(корень):
    """Поток принадлежит произведению, а не отдельной странице сезона."""
    страница = api.разрешить(корень, "demo-declared", "/anime/rabota-003/")
    серия = api.разрешить(корень, "demo-declared",
                          "/anime/rabota-003/season/1/episode/4")
    assert серия["binding"]["mayPromisePlayback"] \
        == страница["binding"]["mayPromisePlayback"]


def test_вложенный_адрес_конфликтного_вида_права_не_получает(корень):
    """Наследуется связь целиком, включая запрет — а не одно лишь разрешение."""
    итог = api.разрешить(корень, "demo-declared", "/anime/konflikt/season/1")
    assert итог["binding"]["bindingState"] == "KIND_UNRESOLVED"
    assert итог["binding"]["schemaType"] == ""


@pytest.mark.parametrize("путь", [
    "/catalog", "/", "/anime/", "/anime/rabota-003/season",
    "/anime/rabota-003/season/1/episode", "/anime/rabota-003/kadry",
])
def test_чужой_адрес_отказывается_явно_а_не_угадывается(корень, путь):
    итог = api.разрешить(корень, "demo-declared", путь)
    assert итог["resolved"] is False
    assert итог["pageType"] == ""
    assert итог["reason"]
    assert "binding" not in итог


def test_адрес_без_маршрута_не_выдумывает_связь(корень):
    итог = api.разрешить(корень, "demo-declared", "/anime/net-takogo/")
    assert итог["resolved"] is False
    assert итог["pageType"] == "title"
    assert "маршрута нет" in итог["reason"]


def test_у_вычисляемых_адресов_вложенных_страниц_нет(корень):
    """Витрины Lords адресуют сезон и серию иначе; догадка здесь запрещена."""
    assert api.разрешить(корень, "demo-lords",
                         "/title/rabota-003/season/1")["resolved"] is False


def test_разрешение_у_неизвестного_производителя_отказывает(корень):
    """Отказ тот же, что и у выдачи: иначе один и тот же изъян настройки даёт
    потребителю 404 в одном месте и поломку сервера в другом."""
    with pytest.raises(api.BindingSourceUnknown, match="неизвестен"):
        api.разрешить(корень, "demo-broken", "/title/x/")


# --- кэш выгрузки ------------------------------------------------------------

def test_повторная_выгрузка_берётся_из_кэша(корень):
    первая = api.выгрузка(корень, "demo-declared")
    assert api.выгрузка(корень, "demo-declared") is первая


def test_правка_источника_кэш_обесценивает(корень):
    """Ключом было время правки, и проверка поймала это редким падением: две
    правки внутри одного тика дают одну отметку, и кэш отдаёт вчерашнее."""
    до = api.выгрузка(корень, "demo-declared")["records"]
    снимок = json.loads((корень / "var" / "routes.json").read_text("utf-8"))
    снимок["items"].append({"slug": "novyj", "providerTitleId": "p-001",
                            "canonical": True})
    (корень / "var" / "routes.json").write_text(json.dumps(снимок),
                                                encoding="utf-8")
    assert api.выгрузка(корень, "demo-declared")["records"] == до + 1


def test_правка_того_же_объёма_кэш_тоже_обесценивает(корень):
    """Отпечаток по содержимому, а не по размеру и времени: подмена слага на
    равный по длине не меняет ни того, ни другого."""
    было = api.выгрузка(корень, "demo-declared")
    снимок = json.loads((корень / "var" / "routes.json").read_text("utf-8"))
    снимок["items"][0]["slug"] = "rabota-XXX"
    (корень / "var" / "routes.json").write_text(json.dumps(снимок),
                                                encoding="utf-8")
    стало = api.выгрузка(корень, "demo-declared")
    assert стало["records"] == было["records"]
    assert стало["digest"] != было["digest"]
