"""Маршруты выдачи связей на уровне Control API.

Сам контракт проверяется отдельно; здесь проверяется то, что видит
потребитель через HTTP: право читать, коды отказов и то, что изъян настройки
не превращается в поломку сервера. Ступень, которую никто не проверяет,
однажды окажется пропущенной, и узнают об этом по последствиям.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.site_engine.api import seo_bindings as api
from factory.site_engine.api.control import ControlApi

ЧИТАТЕЛЬ = "reader-token"
СРЕДА = {"SITE_ENGINE_CONTROL_TOKENS": f"{ЧИТАТЕЛЬ}=read"}
ДОСТУП = {"Authorization": f"Bearer {ЧИТАТЕЛЬ}"}
ВИТРИНА = "demo-declared"

ИСТОЧНИКИ = """
version: "1.0.0"
sites:
  demo-declared:
    producer: declared-routes
    routes: var/routes.json
    catalog: var/catalog.json
  demo-broken:
    producer: несуществующий
    catalog: var/catalog.json
"""


@pytest.fixture
def песочница(tmp_path: Path) -> Path:
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "seo-binding-sources.yaml").write_text(
        ИСТОЧНИКИ, encoding="utf-8")
    (tmp_path / "var").mkdir()
    каталог = [{"external_id": "p-001", "name": "Работа", "type": "tv",
                "is_series": True, "tags": [], "year": 2026,
                "playback": {"aggregator": "kp", "title_id": "1"},
                "external_ids": {"kp": "1"}}]
    (tmp_path / "var" / "catalog.json").write_text(
        json.dumps({"items": каталог, "fetched_at_ms": 1788000000000}),
        encoding="utf-8")
    (tmp_path / "var" / "routes.json").write_text(json.dumps({
        "siteId": ВИТРИНА, "fetchedAt": "2026-09-06T05:00:00+00:00",
        "source": "container:test",
        "items": [{"slug": "rabota", "providerTitleId": "p-001",
                   "canonical": True}]}), encoding="utf-8")
    return tmp_path


def клиент(песочница: Path) -> ControlApi:
    return ControlApi(root=песочница, env=СРЕДА)


# --- доступ ------------------------------------------------------------------

@pytest.mark.parametrize("путь", [
    "/api/v1/seo-bindings",
    f"/api/v1/seo-bindings/{ВИТРИНА}",
    f"/api/v1/seo-bindings/{ВИТРИНА}/resolve",
])
def test_без_ключа_связи_не_отдаются(песочница, путь):
    assert клиент(песочница).handle("GET", путь).status == 401


def test_чтения_достаточно_права_на_чтение(песочница):
    r = клиент(песочница).handle("GET", f"/api/v1/seo-bindings/{ВИТРИНА}",
                                 body={"limit": 1}, headers=ДОСТУП)
    assert r.status == 200
    assert r.body["schemaVersion"] == "seo-route-binding/1.0.0"


# --- разрешение адреса -------------------------------------------------------

def test_адрес_разрешается_и_несёт_связь(песочница):
    r = клиент(песочница).handle(
        "GET", f"/api/v1/seo-bindings/{ВИТРИНА}/resolve",
        body={"path": "/anime/rabota/"}, headers=ДОСТУП)
    assert r.status == 200
    assert r.body["resolved"] is True
    assert r.body["binding"]["contentId"] == "p-001"


def test_вложенный_адрес_наследует_связь(песочница):
    r = клиент(песочница).handle(
        "GET", f"/api/v1/seo-bindings/{ВИТРИНА}/resolve",
        body={"path": "/anime/rabota/season/1/episode/3"}, headers=ДОСТУП)
    assert r.status == 200
    assert r.body["pageType"] == "episode"
    assert r.body["inheritsFrom"] == "/anime/rabota/"


def test_чужой_адрес_даёт_явный_отказ_а_не_ошибку(песочница):
    """Отказ по существу — это ответ, а не сбой: страница просто не наша."""
    r = клиент(песочница).handle(
        "GET", f"/api/v1/seo-bindings/{ВИТРИНА}/resolve",
        body={"path": "/catalog"}, headers=ДОСТУП)
    assert r.status == 200
    assert r.body["resolved"] is False
    assert r.body["reason"]


@pytest.mark.parametrize("тело", [
    {}, {"path": ""}, {"path": "anime/rabota/"}, {"path": 7}, {"path": None},
])
def test_адрес_проверяется_до_сборки(песочница, тело):
    r = клиент(песочница).handle(
        "GET", f"/api/v1/seo-bindings/{ВИТРИНА}/resolve",
        body=тело, headers=ДОСТУП)
    assert r.status == 400
    assert r.body["error"]["code"] == "invalid_path"


# --- изъяны настройки --------------------------------------------------------

def test_витрина_вне_настройки_даёт_404(песочница):
    r = клиент(песочница).handle("GET", "/api/v1/seo-bindings/net-takoj",
                                 body={"path": "/anime/x/"}, headers=ДОСТУП)
    assert r.status == 404
    assert r.body["error"]["code"] == "binding_source_unknown"


def test_негодный_идентификатор_отсекается_до_чтения_настройки(песочница):
    """Форма идентификатора проверяется раньше источников: до файлов доходит
    только то, что вообще может быть именем витрины."""
    r = клиент(песочница).handle("GET", "/api/v1/seo-bindings/нет-такой",
                                 body={"path": "/anime/x/"}, headers=ДОСТУП)
    assert r.status == 400
    assert r.body["error"]["code"] == "invalid_site_id"


def test_неизвестный_производитель_даёт_404_а_не_500(песочница):
    """Один и тот же изъян настройки должен отвечать одинаково на обоих
    маршрутах: иначе он выглядит поломкой сервера там, где он — «нет такого»."""
    для_выдачи = клиент(песочница).handle(
        "GET", "/api/v1/seo-bindings/demo-broken", body={"limit": 1},
        headers=ДОСТУП)
    для_адреса = клиент(песочница).handle(
        "GET", "/api/v1/seo-bindings/demo-broken/resolve",
        body={"path": "/anime/x/"}, headers=ДОСТУП)
    assert для_выдачи.status == для_адреса.status == 404
    assert для_выдачи.body["error"]["code"] \
        == для_адреса.body["error"]["code"] == "binding_source_unknown"


# --- перечень витрин ---------------------------------------------------------

def test_перечень_называет_витрины_и_способ_адресации(песочница):
    r = клиент(песочница).handle("GET", "/api/v1/seo-bindings", headers=ДОСТУП)
    assert r.status == 200
    имена = {s["siteId"]: s["producer"] for s in r.body["sites"]}
    assert имена[ВИТРИНА] == "declared-routes"


# --- объявление возможностей -------------------------------------------------

def test_движок_объявляет_все_маршруты_контракта(песочница):
    """Потребитель обязан узнать возможность у движка, а не вывести её из
    номера версии: вывод из версии — догадка, ради запрета которой контракт и
    написан. Объявлялся один маршрут из трёх."""
    from factory.site_engine.api import openapi

    r = клиент(песочница).handle("GET", "/api/v1/compatibility", headers=ДОСТУП)
    объявлен = next(c for c in r.body["contracts"]
                    if c["name"] == "seo-route-binding")
    описаны = {п for п in openapi.spec()["paths"]
               if п.startswith("/api/v1/seo-bindings")}
    assert set(объявлен["endpoints"]) == описаны, \
        "объявление движка разошлось с описанием API"


def test_объявленные_производители_совпадают_с_существующими(песочница):
    from factory.site_engine import adapters

    r = клиент(песочница).handle("GET", "/api/v1/compatibility", headers=ДОСТУП)
    объявлен = next(c for c in r.body["contracts"]
                    if c["name"] == "seo-route-binding")
    assert tuple(объявлен["producers"]) == adapters.PRODUCERS


# --- незавершённая установка не выглядит измеренным нулём --------------------
#
# Код берётся из каталога релиза, а настройка и данные — из корня состояния,
# и это разные места. Релиз с маршрутами контракта, выложенный в корень без
# config/seo-binding-sources.yaml, поднимается полностью исправным и отдаёт
# пустой перечень. Выкладка, выглядящая успешной при неработающей
# возможности, — худший вид отказа: о нём узнают от потребителя и позже.

def test_отсутствие_настройки_отличимо_от_нуля_витрин(tmp_path):
    """«Настройки нет» и «настройка описывает ноль витрин» выглядят одинаково —
    пустым перечнем. Схлопывать первое во второе значит выдавать незнание за
    измеренный ноль."""
    (tmp_path / "config").mkdir()
    без = api.каталог_витрин(tmp_path)
    assert без["sites"] == []
    assert без["sourcesConfigured"] is False
    assert без["reason"]

    (tmp_path / "config" / "seo-binding-sources.yaml").write_text(
        'version: "1.0.0"\nsites: {}\n', encoding="utf-8")
    пусто = api.каталог_витрин(tmp_path)
    assert пусто["sites"] == []
    assert пусто["sourcesConfigured"] is True
    assert "reason" not in пусто, "осознанный ноль причины не требует"


def test_перечень_витрин_объявляет_настроенность_и_при_наличии(песочница):
    assert api.каталог_витрин(песочница)["sourcesConfigured"] is True


def test_протокол_запуска_называет_отсутствие_настройки(tmp_path):
    """Иначе выкладка выглядит исправной, а контракт молчит."""
    from factory.site_engine.api import startup

    проверки = startup.check_seo_binding_sources(tmp_path)
    имена = {c.name: c for c in проверки}
    assert имена["seo-bindings.sources"].status == startup.DEGRADED
    assert "пустым перечнем" in имена["seo-bindings.sources"].detail


def test_протокол_запуска_называет_недостающие_входы(песочница):
    """Настройка на месте, а файла каталога нет — тоже молчаливая пустота."""
    from factory.site_engine.api import startup

    (песочница / "var" / "catalog.json").unlink()
    имена = {c.name: c for c in startup.check_seo_binding_sources(песочница)}
    assert имена["seo-bindings.inputs"].status == startup.DEGRADED
    assert "demo-declared:catalog" in имена["seo-bindings.inputs"].detail


def test_отсутствие_связей_не_мешает_службе_подняться(tmp_path):
    """Корень без витрин со связями — законное состояние: ограничение, а не
    фатальная ошибка. Ворота, роняющие запуск, заменяют один отказ другим."""
    from factory.site_engine.api import startup

    for c in startup.check_seo_binding_sources(tmp_path):
        assert c.status != startup.FATAL


def test_протокол_запуска_называет_пустые_перечни(песочница, monkeypatch):
    """Оба перечня fail-closed: без настройки пусты, и это верно. Но пустой
    перечень тих — связи собираются, записи отдаются, и каждая приходит без
    идентификаторов и без права обещать просмотр. Отказ, о котором никто не
    сказал, выглядит работой."""
    from factory.site_engine import seo_binding
    from factory.site_engine.api import startup

    monkeypatch.setattr(seo_binding, "ID_NAMESPACES", ())
    monkeypatch.setattr(seo_binding, "PLAYBACK_AUTHORISED", frozenset())
    имена = {c.name: c for c in startup.check_seo_binding_sources(песочница)}
    assert имена["seo-bindings.namespaces"].status == startup.DEGRADED
    assert имена["seo-bindings.playback"].status == startup.DEGRADED


def test_заполненные_перечни_ограничением_не_объявляются(песочница):
    from factory.site_engine.api import startup

    имена = {c.name for c in startup.check_seo_binding_sources(песочница)}
    assert "seo-bindings.namespaces" not in имена
    assert "seo-bindings.playback" not in имена


def test_ворота_сообщают_обо_всех_пробелах_сразу(tmp_path, monkeypatch):
    """Ворота, останавливающиеся на первом ограничении, заставляют чинить по
    одному и выкатывать трижды — каждый раз узнавая о следующем уже после
    выкладки."""
    from factory.site_engine import seo_binding
    from factory.site_engine.api import startup

    monkeypatch.setattr(seo_binding, "ID_NAMESPACES", ())
    monkeypatch.setattr(seo_binding, "PLAYBACK_AUTHORISED", frozenset())
    имена = {c.name for c in startup.check_seo_binding_sources(tmp_path)}
    assert имена == {"seo-bindings.sources", "seo-bindings.namespaces",
                     "seo-bindings.playback"}
