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
    # Ключ задан: без него служба теперь не отдаёт данные вовсе, и проверки
    # контракта шли бы на 401. Отсутствие ключа проверяется отдельно.
    м.Обработчик.ключ = "app-key-probe-1"
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


КЛЮЧ = "app-key-probe-1"


def гет(база: str, путь: str, заголовки: dict | None = None):
    """Запрос с ключом по умолчанию: без него служба отвечает 401 на всё."""
    заг = {"X-App-Key": КЛЮЧ}
    заг.update(заголовки or {})
    запрос = urllib.request.Request(база + путь, headers=заг)
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
    assert тело["ready"] is True and тело["keyConfigured"] is True
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
    assert тело["reason"] == "NO_SOURCE_CONTRACT_RELEASED"
    assert тело["embed"]["kind"] == "provider-web-component"
    assert тело["embed"]["providerRefs"][0]["sourceId"] == "555"


def test_без_ссылок_провайдера_причина_та_же(служба):
    """Код причины один и явный: дело не в «не вышло», а в отсутствии договора."""
    _, база = служба
    _, тело, _ = гет(база, f"/api/app/v1/episodes/{ФИЛЬМ}:movie/sources")
    assert тело["sources"] == []
    assert тело["reason"] == "NO_SOURCE_CONTRACT_RELEASED"
    assert тело["embed"]["providerRefs"] == []


def test_перечень_для_главной_по_дате_добавления(служба):
    """Форма запрошена клиентом (уточнение 002): страница с курсором и жанром."""
    _, база = служба
    код, тело, _ = гет(база, "/api/app/v1/titles?sort=added&limit=1")
    assert код == 200, тело
    assert тело["total"] == 2
    assert тело["nextCursor"] == "1"
    assert "added" in тело["rule"], "правило ряда обязано быть названо"
    # Порядок — по дате добавления: сериал добавлен позже фильма.
    assert тело["items"][0]["contentId"] == СЕРИАЛ


def test_перечень_сужается_жанром(служба):
    _, база = служба
    код, тело, _ = гет(база, "/api/app/v1/titles?genre="
                       + urllib.parse.quote("драма"))
    assert код == 200
    assert [и["contentId"] for и in тело["items"]] == [СЕРИАЛ]
    assert тело["genre"] == "драма"


def test_непонятный_порядок_отвергается(служба):
    """Порядков, которых у снимка нет, служба не изображает."""
    _, база = служба
    код, тело, _ = гет(база, "/api/app/v1/titles?sort=popular")
    assert код == 400 and тело["error"]["code"] == "bad_request"


def test_источники_фильма_в_форме_клиента(служба):
    """`episodes/movie/sources?contentId=…` — форма из задания клиента."""
    _, база = служба
    код, тело, _ = гет(база, f"/api/app/v1/episodes/movie/sources?contentId={ФИЛЬМ}")
    assert код == 200, тело
    assert тело["sources"] == []
    assert тело["reason"] == "NO_SOURCE_CONTRACT_RELEASED"


def test_источники_фильма_без_contentId_отказ(служба):
    _, база = служба
    код, тело, _ = гет(база, "/api/app/v1/episodes/movie/sources")
    assert код == 400 and "contentId" in тело["error"]["message"]


def test_неизвестный_маршрут_404(служба):
    _, база = служба
    код, тело, _ = гет(база, "/api/app/v1/nothing")
    assert код == 404 and тело["error"]["code"] == "not_found"


def test_без_заголовка_ключа_данные_не_отдаются(служба):
    """Ключ обязателен всегда: доступ без него — не «удобство», а дыра."""
    _, база = служба
    код, тело, _ = гет(база, f"/api/app/v1/titles/{СЕРИАЛ}", {"X-App-Key": ""})
    assert код == 401 and тело["error"]["code"] == "unauthorized"


def test_неверный_ключ_отвергается(служба):
    _, база = служба
    код, тело, _ = гет(база, f"/api/app/v1/titles/{СЕРИАЛ}",
                       {"X-App-Key": "app-key-probe-2"})
    assert код == 401 and тело["error"]["code"] == "unauthorized"


def test_ненастроенный_ключ_закрывает_данные_и_виден_в_готовности(служба):
    """Отсутствие настройки — это НЕ разрешение.

    Прежняя версия при пустом ключе отвечала всем, и служба, выложенная
    наружу до появления файла ключа, отдавала бы каталог кому угодно, причём
    выглядело бы это исправной работой.
    """
    м, база = служба
    м.Обработчик.ключ = ""
    try:
        код, тело, _ = гет(база, "/healthz")
        assert код == 503, тело
        assert тело["ok"] is False and тело["ready"] is False
        assert тело["keyConfigured"] is False
        assert "не задан" in тело["reason"]
        код, тело, _ = гет(база, f"/api/app/v1/titles/{СЕРИАЛ}")
        assert код == 401, тело
        assert "не настроен" in тело["error"]["message"]
    finally:
        м.Обработчик.ключ = КЛЮЧ


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


# --- состояние внутри отданного наружу префикса ------------------------------
#
# Живой случай 2026-10-10. Разработчик приложения спросил
# https://animedia.icu/api/app/v1/healthz и получил 308 на тот же путь со
# слешем, а затем 404 — страницу «не найдено» самой витрины. Служба тут ни при
# чём: маршрута не было вовсе. Но и после установки этот адрес не ответил бы:
# состояние жило только в `/healthz`, который наружу не отдаётся — в
# конфигурации витрины `location = /healthz` уже занят ею самой.
#
# Поэтому состояние отвечает и внутри префикса. Это единственный адрес, которым
# клиент приложения может отличить «служба работает» от «маршрута нет».


def test_состояние_отвечает_внутри_префикса(служба):
    _, база = служба
    код, тело, _ = гет(база, "/api/app/v1/healthz")
    assert код == 200, тело
    assert тело["ready"] is True and тело["keyConfigured"] is True
    assert тело["catalogRevision"] == "r-1"


def test_состояние_внутри_префикса_не_требует_ключа(служба):
    """Иначе «нет доступа» и «нет службы» снова сливаются в один ответ."""
    _, база = служба
    код, тело, _ = гет(база, "/api/app/v1/healthz", {"X-App-Key": ""})
    assert код == 200, тело
    assert тело["keyConfigured"] is True


def test_состояние_внутри_префикса_без_ключа_на_сервере(служба):
    м, база = служба
    м.Обработчик.ключ = ""
    try:
        код, тело, _ = гет(база, "/api/app/v1/healthz")
        assert код == 503, тело
        assert тело["ready"] is False and тело["keyConfigured"] is False
    finally:
        м.Обработчик.ключ = КЛЮЧ


def test_хвостовой_слеш_не_ломает_маршрут(служба):
    """Клиент мог запомнить перенаправление витрины на путь со слешем."""
    _, база = служба
    for путь in ("/api/app/v1/healthz/", f"/api/app/v1/titles/{СЕРИАЛ}/"):
        код, _тело, _ = гет(база, путь)
        assert код == 200, путь


def test_состояние_не_несёт_данных_каталога(служба):
    """Он отвечает без ключа, поэтому в теле не должно быть самих записей."""
    _, база = служба
    _, тело, _ = гет(база, "/api/app/v1/healthz")
    assert "items" not in тело and "titles" in тело
    assert isinstance(тело["titles"], int), "число записей — не сами записи"


# --- процентное кодирование в пути ------------------------------------------
#
# Наблюдение приложения 2026-10-11, воспроизведено на публичном адресе:
# `/api/app/v1/seasons/<id>%3As1/episodes` отдавал 404, а тот же путь с
# двоеточием — 200. Кодировать двоеточие в сегменте пути законно и равнозначно
# самому двоеточию (RFC 3986 §2.2, §6.2.2.2), поэтому служба обязана принимать
# обе формы: иначе любой клиент, который кодирует путь целиком (а это обычное
# поведение библиотек), получает 404 на исправный идентификатор.
#
# Раскрытие идёт по СЕГМЕНТАМ: `%2F` не должен превращаться в разделитель и
# делить сегмент на два — это подмена маршрута.


@pytest.mark.parametrize("кодировка", ["%3A", "%3a"])
def test_серии_по_закодированному_двоеточию(служба, кодировка):
    _, база = служба
    сезон = f"{СЕРИАЛ}:s1".replace(":", кодировка)
    код, тело, _ = гет(база, f"/api/app/v1/seasons/{сезон}/episodes")
    assert код == 200, тело
    assert isinstance(тело, list) and тело, тело
    assert тело[0]["seasonId"] == f"{СЕРИАЛ}:s1", (
        "в ответе идентификатор остаётся в своей, незакодированной форме")


@pytest.mark.parametrize("кодировка", ["%3A", "%3a"])
def test_источники_серии_по_закодированному_двоеточию(служба, кодировка):
    _, база = служба
    серия = f"{СЕРИАЛ}:s1:e1".replace(":", кодировка)
    код, тело, _ = гет(база, f"/api/app/v1/episodes/{серия}/sources")
    assert код == 200, тело
    assert тело["reason"] == "NO_SOURCE_CONTRACT_RELEASED"


def test_обе_формы_дают_один_ответ(служба):
    _, база = служба
    прямо = гет(база, f"/api/app/v1/seasons/{СЕРИАЛ}:s1/episodes")[1]
    кодом = гет(база, f"/api/app/v1/seasons/{СЕРИАЛ}%3As1/episodes")[1]
    assert прямо == кодом, "формы адреса обязаны быть равнозначны"


def test_закодированный_разделитель_не_делит_сегмент(служба):
    """`%2F` — не разделитель: иначе один сегмент стал бы двумя."""
    _, база = служба
    код, тело, _ = гет(база, f"/api/app/v1/titles%2F{СЕРИАЛ}")
    assert код == 400, тело
    assert "разделитель" in тело["error"]["message"]


def test_обычные_пути_не_изменились(служба):
    _, база = служба
    for путь, ожидание in (
            (f"/api/app/v1/titles/{СЕРИАЛ}", 200),
            ("/api/app/v1/healthz", 200),
            ("/api/app/v1/нет-такого", 404)):
        код, _тело, _ = гет(база, urllib.parse.quote(путь))
        assert код == ожидание, путь


# --- «Где смотреть»: titles/{id}/offers ------------------------------------
#
# Сценарии согласованы с приложением (Кинатека, docs/API_CONTRACT.md в
# ott-app-sandbox): подтверждено, нет сведений, устарело, другой регион, ошибка
# и повтор. Предложения здесь — ТЕСТОВЫЕ записи синтетического снимка; на боевом
# хосте хранилища нет, и ответ там — unknown.

def _записать_предложения(каталог: Path, записи, источник=None, сырое: str | None = None):
    путь = каталог / "proba-01-offers.json"
    if сырое is not None:
        путь.write_text(сырое, encoding="utf-8")
    else:
        путь.write_text(json.dumps({"source": источник or {"id": "probe", "name": "проверочный источник"},
                                    "generatedAt": "2026-10-13T09:00:00Z", "offers": записи},
                                   ensure_ascii=False), encoding="utf-8")
    return путь


def _предложение(**поля):
    import datetime as _dt
    сейчас = _dt.datetime.now(_dt.timezone.utc)
    з = {"contentId": ФИЛЬМ, "serviceId": "svc", "serviceName": "Сервис", "region": "RU",
         "url": "https://svc.example/film/123", "kind": "SUBSCRIPTION", "source": "проверочный фид",
         "checkedAt": (сейчас - _dt.timedelta(days=2)).isoformat().replace("+00:00", "Z")}
    з.update(поля)
    return з


@pytest.fixture()
def служба_с_предложениями(служба, снимок):
    м, база = служба
    м.Обработчик.предложения = м.ХранилищеПредложений(снимок / "proba-01-offers.json")
    try:
        yield м, база, снимок
    finally:
        м.Обработчик.предложения = None


def test_предложения_без_источника_unknown_а_не_нигде(служба_с_предложениями):
    _, база, _ = служба_с_предложениями
    код, тело, _ = гет(база, f"/api/app/v1/titles/{ФИЛЬМ}/offers?region=RU")
    assert код == 200
    assert тело["status"] == "unknown" and тело["reason"] == "NO_AVAILABILITY_SOURCE"
    assert тело["offers"] == [] and тело["staleOffers"] == [] and тело["source"] is None


def test_предложения_подтверждённое_со_всеми_полями(служба_с_предложениями):
    _, база, каталог = служба_с_предложениями
    _записать_предложения(каталог, [_предложение(androidPackage="example.svc")])
    код, тело, _ = гет(база, f"/api/app/v1/titles/{ФИЛЬМ}/offers?region=ru")
    assert код == 200 and тело["status"] == "confirmed" and тело["region"] == "RU"
    п = тело["offers"][0]
    assert {"contentId", "serviceId", "serviceName", "region", "url", "kind", "source", "checkedAt"} <= set(п)
    assert п["androidPackage"] == "example.svc" and тело["source"]["id"] == "probe"


def test_предложения_устаревшие_отдельно_и_не_как_подтверждённые(служба_с_предложениями):
    _, база, каталог = служба_с_предложениями
    _записать_предложения(каталог, [_предложение(checkedAt="2026-01-01T00:00:00Z")])
    _, тело, _ = гет(база, f"/api/app/v1/titles/{ФИЛЬМ}/offers?region=RU")
    assert тело["status"] == "stale" and тело["offers"] == [] and len(тело["staleOffers"]) == 1


def test_предложения_только_другой_регион(служба_с_предложениями):
    _, база, каталог = служба_с_предложениями
    _записать_предложения(каталог, [_предложение(region="KZ")])
    _, тело, _ = гет(база, f"/api/app/v1/titles/{ФИЛЬМ}/offers?region=RU")
    assert тело["status"] == "other_region" and тело["offers"][0]["region"] == "KZ"


def test_предложения_поиск_неполные_и_выдуманные_условия_отбрасываются(служба_с_предложениями):
    _, база, каталог = служба_с_предложениями
    _записать_предложения(каталог, [
        _предложение(url="https://svc.example/search?q=film"),        # поиск — не доказательство
        _предложение(serviceId="b", url="https://svc.example/"),       # главная сервиса
        _предложение(serviceId="c", url="http://svc.example/film/1"),  # не https
        _предложение(serviceId="d", source=""),                       # без источника
        _предложение(serviceId="e", checkedAt="вчера"),               # время не читается
        _предложение(serviceId="f", region="Russia"),                 # регион не ISO
        _предложение(serviceId="g", kind="LEASE"),                     # неизвестные условия → null
        _предложение(contentId=СЕРИАЛ, serviceId="h"),                # другое произведение
    ])
    _, тело, _ = гет(база, f"/api/app/v1/titles/{ФИЛЬМ}/offers?region=RU")
    assert [п["serviceId"] for п in тело["offers"]] == ["g"]
    assert тело["offers"][0]["kind"] is None and тело["dropped"] == 6


def test_предложения_ошибка_хранилища_503_и_повтор_после_исправления(служба_с_предложениями):
    _, база, каталог = служба_с_предложениями
    путь = _записать_предложения(каталог, None, сырое="{битый json")
    код, тело, заг = гет(база, f"/api/app/v1/titles/{ФИЛЬМ}/offers?region=RU")
    assert код == 503 and тело["error"]["code"] == "offers_unavailable" and заг.get("Retry-After") == "60"
    import os as _os, time as _time
    _записать_предложения(каталог, [_предложение()])
    _os.utime(путь, (_time.time() + 5, _time.time() + 5))   # другая метка — хранилище перечитывается
    код, тело, _ = гет(база, f"/api/app/v1/titles/{ФИЛЬМ}/offers?region=RU")
    assert код == 200 and тело["status"] == "confirmed"


def test_предложения_отказы_маршрута(служба_с_предложениями):
    _, база, _ = служба_с_предложениями
    assert гет(база, f"/api/app/v1/titles/{ФИЛЬМ}/offers")[0] == 400                    # нет региона
    assert гет(база, f"/api/app/v1/titles/{ФИЛЬМ}/offers?region=RUS")[0] == 400
    assert гет(база, "/api/app/v1/titles/no-such-title/offers?region=RU")[0] == 404
    assert гет(база, f"/api/app/v1/titles/{ФИЛЬМ}/offers?region=RU", {"X-App-Key": "wrong-key"})[0] == 401
