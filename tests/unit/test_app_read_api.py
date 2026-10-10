"""Читающее API каталога для клиента приложения: контракт и отказы.

Повод — передача от сессии `ott-app-sandbox` (файл
`docs/handoff/2026-10-11-architect-app-read-api.md`): приложению нужен один
источник целиком — поиск, карточка, сезоны, серии, источник видео, — а
документированного JSON API у витрин не было. Витрины отдают страницы; трогать
их рантайм ради чтения каталога нельзя (он закреплён, и в нём живёт плеер).

Здесь сторожится ровно то, что обещано разработчику:

* форма ответов и форма ошибок (код + `{"error":{"code","message"}}`);
* курсор и предел страницы;
* сезоны и серии строятся ИЗ ЧИСЕЛ снимка, а не выдумываются;
* `/sources` отдаёт пустой список с НАЗВАННОЙ причиной: прямого потока у
  фабрики нет, и подменять его догадкой запрещено;
* отсутствующие поля остаются отсутствующими (`rating: null`), а не нулями.

Снимок здесь синтетический: боевые данные в проверках не нужны, а зависеть от
них значит сделать проверку непредсказуемой.
"""
from __future__ import annotations

import importlib.util
import json
import socket
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
СЦЕНАРИЙ = КОРЕНЬ / "automation" / "host" / "app-read-api.py"


def _модуль():
    спец = importlib.util.spec_from_file_location("app_read_api", СЦЕНАРИЙ)
    м = importlib.util.module_from_spec(спец)
    sys.modules["app_read_api"] = м
    спец.loader.exec_module(м)
    return м


@pytest.fixture()
def снимок(tmp_path):
    """Снимок той же формы, что у витрины: каталог плюс боковые подробности."""
    (tmp_path / "proba-01-catalog.json").write_text(json.dumps({
        "schema": "nova-catalog/2.0.0", "site": "proba-01", "revision": "r-1",
        "builtAt": "2026-10-10T11:46:13Z", "count": 2,
        "items": [
            {"slug": "severnyy-marshrut", "title": "Северный маршрут",
             "kind": "Сериал", "year": 2024, "url": "/title/severnyy-marshrut/",
             "poster": "https://poster.example/северный.webp",
             "published_at": "2026-10-01T10:00:00Z"},
            {"slug": "tihiy-film", "title": "Тихий маршрут", "kind": "Фильм",
             "year": 2019, "url": "/title/tihiy-film/",
             "poster": "https://poster.example/tihiy.webp",
             "published_at": "2026-09-01T10:00:00Z"},
        ],
    }, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "proba-01-details.json").write_text(json.dumps({
        "schema": "nova.details.sidecar/2.0.0", "site": "proba-01",
        "catalog_revision": "r-1",
        "details": {
            "severnyy-marshrut": {
                "id": "01915145-2c16-7ba4-8353-42b73d657fdc",
                "name": "Северный маршрут", "original_name": "North Route",
                "type": "tv", "year": 2024, "genres": ["драма"],
                "description": "Описание из снимка.",
                "poster_url": "https://poster.example/северный.webp",
                "external_ids": {"kinopoisk": "1234", "imdb": ""},
                "ratings_by_source": {"kinopoisk": 7.4},
                "playable": True,
                "seasons": [{"n": 1, "eps": 10, "avail": 7},
                            {"n": 0, "eps": 2, "avail": 2}],
                "sources": [{"provider": "kp", "source_id": "555",
                             "player_id": None,
                             "availability_status": "available"}],
            },
            "tihiy-film": {
                "id": "01915145-0000-7000-8000-000000000002",
                "name": "Тихий маршрут", "type": "movie", "year": 2019,
                "genres": [], "seasons": [], "sources": [],
            },
        },
    }, ensure_ascii=False), encoding="utf-8")
    return tmp_path


@pytest.fixture()
def служба(снимок):
    м = _модуль()
    м.Обработчик.каталог = м.Каталог("proba-01", снимок)
    м.Обработчик.ключ = ""
    м.Обработчик.счётчик = {}
    гнездо = socket.socket()
    гнездо.bind(("127.0.0.1", 0))
    порт = гнездо.getsockname()[1]
    гнездо.close()
    сервер = ThreadingHTTPServer(("127.0.0.1", порт), м.Обработчик)
    поток = threading.Thread(target=сервер.serve_forever, daemon=True)
    поток.start()
    try:
        yield м, f"http://127.0.0.1:{порт}"
    finally:
        сервер.shutdown()
        сервер.server_close()


def гет(база: str, путь: str, заголовки: dict | None = None):
    запрос = urllib.request.Request(база + путь, headers=заголовки or {})
    try:
        with urllib.request.urlopen(запрос, timeout=20) as о:
            return о.status, json.loads(о.read()), dict(о.headers)
    except urllib.error.HTTPError as ош:
        return ош.code, json.loads(ош.read()), dict(ош.headers)


СЕРИАЛ = "01915145-2c16-7ba4-8353-42b73d657fdc"
ФИЛЬМ = "01915145-0000-7000-8000-000000000002"


def test_состояние_называет_поколение(служба):
    _, база = служба
    код, тело, _ = гет(база, "/healthz")
    assert код == 200
    assert тело["titles"] == 2
    assert тело["catalogRevision"] == "r-1"
    assert тело["catalogBuiltAt"] == "2026-10-10T11:46:13Z"


def test_поиск_по_русскому_и_оригинальному(служба):
    _, база = служба
    for запрос in ("северный", "north"):
        код, тело, _ = гет(база, "/api/app/v1/search?q=" + urllib.parse.quote(запрос))
        assert код == 200, тело
        assert [и["contentId"] for и in тело["items"]] == [СЕРИАЛ], запрос


def test_поиск_курсором_и_пределом(служба):
    _, база = служба
    код, тело, _ = гет(база, "/api/app/v1/search?q=" + urllib.parse.quote("маршрут") + "&limit=1")
    assert код == 200
    assert len(тело["items"]) == 1
    assert тело["total"] == 2
    assert тело["nextCursor"] == "1"
    код, вторая, _ = гет(база, "/api/app/v1/search?q=" + urllib.parse.quote("маршрут")
                         + "&limit=1&cursor=1")
    assert вторая["nextCursor"] is None
    assert вторая["items"][0]["contentId"] != тело["items"][0]["contentId"]


def test_короткий_запрос_отвергается_с_формой_ошибки(служба):
    _, база = служба
    код, тело, _ = гет(база, "/api/app/v1/search?q=a")
    assert код == 400
    assert тело["error"]["code"] == "bad_request"
    assert "message" in тело["error"]


def test_карточка_отдаёт_только_имеющееся(служба):
    _, база = служба
    код, тело, _ = гет(база, f"/api/app/v1/titles/{СЕРИАЛ}")
    assert код == 200
    assert тело["titleRu"] == "Северный маршрут"
    assert тело["originalTitle"] == "North Route"
    assert тело["type"] == "SERIES"
    assert тело["rating"] == {"value": 7.4, "scale": 10, "source": "kinopoisk"}
    assert тело["artwork"]["posterUrl"].endswith(".webp")
    assert {"namespace": "kinopoisk", "value": "1234"} in тело["externalIds"]
    # Пустой внешний id не превращается в запись: отсутствующее отсутствует.
    assert all(и["value"] for и in тело["externalIds"])
    assert тело["addedAt"] == "2026-10-01"
    # Внутренние поля наружу не уходят.
    assert not [к for к in тело if к.startswith("_")]


def test_отсутствующая_оценка_остаётся_пустой(служба):
    """Ноль вместо отсутствующей оценки — выдумка, и её здесь быть не должно."""
    _, база = служба
    _, тело, _ = гет(база, f"/api/app/v1/titles/{ФИЛЬМ}")
    assert тело["rating"] is None
    assert тело["type"] == "MOVIE"


def test_нет_тайтла_404(служба):
    _, база = служба
    код, тело, _ = гет(база, f"/api/app/v1/titles/{urllib.parse.quote('нет')}")
    assert код == 404 and тело["error"]["code"] == "not_found"


def test_сезоны_из_чисел_снимка(служба):
    _, база = служба
    код, тело, _ = гет(база, f"/api/app/v1/titles/{СЕРИАЛ}/seasons")
    assert код == 200
    номера = {с["number"]: с for с in тело}
    assert номера[1]["episodeCount"] == 10 and номера[1]["availableCount"] == 7
    assert номера[1]["isSpecial"] is False
    # Нулевой сезон — спецвыпуски, и он назван именно так.
    assert номера[0]["isSpecial"] is True


def test_серии_отмечают_доступность(служба):
    _, база = служба
    код, тело, _ = гет(база, f"/api/app/v1/seasons/{СЕРИАЛ}:s1/episodes")
    assert код == 200
    assert len(тело) == 10
    assert [э["available"] for э in тело] == [True] * 7 + [False] * 3
    assert тело[0]["displayNumber"] == "1" and тело[0]["order"] == 1001
    assert тело[0]["episodeId"] == f"{СЕРИАЛ}:s1:e1"


def test_нет_сезона_404(служба):
    _, база = служба
    код, тело, _ = гет(база, f"/api/app/v1/seasons/{СЕРИАЛ}:s9/episodes")
    assert код == 404 and тело["error"]["code"] == "not_found"


def test_источник_видео_пуст_и_причина_названа(служба):
    """Главное обещание: прямого потока нет, и это сказано машинно.

    Выдать вместо него адрес страницы или кадр провайдера значило бы подсунуть
    нативному плееру то, что он не умеет, и выдать блокер за решение.
    """
    _, база = служба
    код, тело, _ = гет(база, f"/api/app/v1/episodes/{СЕРИАЛ}:s1:e1/sources")
    assert код == 200
    assert тело["sources"] == []
    assert тело["reason"] == "NO_SOURCE"
    assert тело["embed"]["kind"] == "provider-web-component"
    assert тело["embed"]["providerRefs"][0]["sourceId"] == "555"


def test_без_источников_причина_другая(служба):
    _, база = служба
    _, тело, _ = гет(база, f"/api/app/v1/episodes/{ФИЛЬМ}:movie/sources")
    assert тело["sources"] == [] and тело["reason"] == "NOT_RELEASED"


def test_неизвестный_маршрут_404(служба):
    _, база = служба
    код, тело, _ = гет(база, "/api/app/v1/nothing")
    assert код == 404 and тело["error"]["code"] == "not_found"


def test_ключ_клиента_когда_задан_обязателен(служба):
    м, база = служба
    м.Обработчик.ключ = "app-key-probe-1"
    try:
        код, тело, _ = гет(база, f"/api/app/v1/titles/{СЕРИАЛ}")
        assert код == 401 and тело["error"]["code"] == "unauthorized"
        код, тело, _ = гет(база, f"/api/app/v1/titles/{СЕРИАЛ}",
                           {"X-App-Key": "app-key-probe-1"})
        assert код == 200 and тело["contentId"] == СЕРИАЛ
    finally:
        м.Обработчик.ключ = ""


def test_предел_частоты_отвечает_429_с_retry_after(служба):
    м, база = служба
    м.ПРЕДЕЛ_ЗАПРОСОВ_В_МИНУТУ = 3
    try:
        коды = [гет(база, f"/api/app/v1/titles/{urllib.parse.quote('нет')}")[0] for _ in range(5)]
        assert 429 in коды, коды
        код, тело, заголовки = гет(база, f"/api/app/v1/titles/{urllib.parse.quote('нет')}")
        assert код == 429 and тело["error"]["code"] == "rate_limited"
        assert заголовки.get("Retry-After") == "60"
    finally:
        м.ПРЕДЕЛ_ЗАПРОСОВ_В_МИНУТУ = 120
        м.Обработчик.счётчик = {}
