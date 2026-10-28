"""Главная «Кинатеки» с сервера: маршрут `config/{канал}` читающего API.

Передача 135 (`ott-app-sandbox`, контракт `kinateka-config/1`). Сторожится:

* каналы раздельны: указатель sandbox не отдаётся в production;
* «ничего не опубликовано» (`404 NO_CONFIG`) и «хранилище не читается» (503)
  не сливаются — клиент поступает по-разному;
* позиции подборок дополняются из ТЕКУЩЕГО снимка, исчезнувшие — в `missing`,
  порядок прочих сохраняется;
* тайтл с жанром не для общей главной не отдаётся, даже если он в ревизии;
* смена указателя (публикация, откат) видна без перезапуска;
* обновлённый витриной снимок перечитывается без перезапуска.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

import pytest

import importlib.util
from pathlib import Path

# Снимок, служба и запрос — общие с основным набором; импорт по пути, потому что
# pytest собирает тесты в режиме importlib и соседний файл не модуль пакета.
_спец = importlib.util.spec_from_file_location(
    "test_app_read_api_base", Path(__file__).with_name("test_app_read_api.py"))
_основа = importlib.util.module_from_spec(_спец)
_спец.loader.exec_module(_основа)
СЕРИАЛ, ФИЛЬМ, гет = _основа.СЕРИАЛ, _основа.ФИЛЬМ, _основа.гет
снимок, служба = _основа.снимок, _основа.служба


def ревизия(n: int, канал: str = "sandbox", состав=(СЕРИАЛ, "нет-такого", ФИЛЬМ)) -> dict:
    return {
        "schema": "kinateka-config/1", "channel": канал, "revision": n, "revisionId": f"r{n}-x",
        "appearance": {"accent": "#E3B26B"},
        "home": {"blocks": [{"id": "c1", "kind": "collection", "collectionId": "c1", "title": "Подборка"}]},
        "collections": [{"id": "c1", "title": "Подборка", "source": "редакция", "checkedAt": "2026-10-28T10:00:00Z",
                         "items": [{"contentId": ид, "reason": "причина", "source": "редакция",
                                    "checkedAt": "2026-10-28T10:00:00Z", "title": "старое имя"} for ид in состав]}],
    }


def опубликовать(корень, канал, док):
    (корень / "revisions").mkdir(parents=True, exist_ok=True)
    (корень / "revisions" / f"{док['revision']}.json").write_text(json.dumps(док, ensure_ascii=False), encoding="utf-8")
    указатель = корень / f"published-{канал}.json"
    указатель.write_text(json.dumps({"revision": док["revision"]}), encoding="utf-8")
    # Указатель переписывается в ту же наносекунду в быстрых проверках: метка обязана отличаться.
    ст = указатель.stat()
    os.utime(указатель, ns=(ст.st_atime_ns, ст.st_mtime_ns + док["revision"] * 1000))


@pytest.fixture()
def с_конфигурацией(служба, tmp_path):
    м, база = служба
    корень = tmp_path / "app-config"
    корень.mkdir()
    м.Обработчик.конфигурация = м.ХранилищеКонфигурации(корень)
    yield м, база, корень
    м.Обработчик.конфигурация = None


def test_без_публикации_NO_CONFIG(с_конфигурацией):
    _, база, _ = с_конфигурацией
    код, тело, _ = гет(база, "/api/app/v1/config/sandbox")
    assert код == 404 and тело["error"]["code"] == "NO_CONFIG"


def test_ключ_обязателен(с_конфигурацией):
    _, база, корень = с_конфигурацией
    опубликовать(корень, "sandbox", ревизия(1))
    код, _, _ = гет(база, "/api/app/v1/config/sandbox", {"X-App-Key": "wrong-key"})
    assert код == 401


def test_неизвестный_канал_не_читает_файлы(с_конфигурацией):
    _, база, _ = с_конфигурацией
    код, _, _ = гет(база, "/api/app/v1/config/..%2Fsecret")
    assert код in (400, 404)
    код, _, _ = гет(база, "/api/app/v1/config/staging")
    assert код == 404


def test_состав_из_текущего_снимка_и_missing(с_конфигурацией):
    _, база, корень = с_конфигурацией
    опубликовать(корень, "sandbox", ревизия(1))
    код, тело, заг = гет(база, "/api/app/v1/config/sandbox")
    assert код == 200, тело
    п = тело["collections"][0]
    assert [и["contentId"] for и in п["items"]] == [СЕРИАЛ, ФИЛЬМ]
    assert п["missing"] == ["нет-такого"]
    assert п["items"][0]["title"] == "Северный маршрут"      # имя из снимка, не из ревизии
    assert п["items"][0]["type"] == "series" and п["items"][1]["type"] == "movie"
    assert тело["catalogRevision"] == "r-1"
    assert заг["ETag"].startswith('"r1-x.')
    assert заг["Cache-Control"] == "max-age=60"
    запрос = urllib.request.Request(база + "/api/app/v1/config/sandbox",
                                    headers={"X-App-Key": _основа.КЛЮЧ, "If-None-Match": заг["ETag"]})
    with pytest.raises(urllib.error.HTTPError) as отказ:     # urllib считает 304 ошибкой
        urllib.request.urlopen(запрос, timeout=20)
    assert отказ.value.code == 304


def test_каналы_раздельны(с_конфигурацией):
    _, база, корень = с_конфигурацией
    опубликовать(корень, "sandbox", ревизия(1))
    код, тело, _ = гет(база, "/api/app/v1/config/production")
    assert код == 404 and тело["error"]["code"] == "NO_CONFIG"


def test_ревизия_чужого_канала_не_отдаётся(с_конфигурацией):
    _, база, корень = с_конфигурацией
    опубликовать(корень, "production", ревизия(1, канал="sandbox"))
    код, тело, _ = гет(база, "/api/app/v1/config/production")
    assert код == 503 and тело["error"]["code"] == "config_unavailable"


def test_публикация_и_откат_видны_без_перезапуска(с_конфигурацией):
    _, база, корень = с_конфигурацией
    опубликовать(корень, "sandbox", ревизия(1))
    опубликовать(корень, "sandbox", ревизия(2, состав=(ФИЛЬМ,)))
    _, тело, _ = гет(база, "/api/app/v1/config/sandbox")
    assert тело["revision"] == 2
    (корень / "published-sandbox.json").write_text(json.dumps({"revision": 1}), encoding="utf-8")
    ст = (корень / "published-sandbox.json").stat()
    os.utime(корень / "published-sandbox.json", ns=(ст.st_atime_ns, ст.st_mtime_ns + 7_000_000))
    _, тело, _ = гет(база, "/api/app/v1/config/sandbox")
    assert тело["revision"] == 1


def test_битый_указатель_это_503_а_не_NO_CONFIG(с_конфигурацией):
    _, база, корень = с_конфигурацией
    (корень / "published-sandbox.json").write_text("{не json", encoding="utf-8")
    код, тело, _ = гет(база, "/api/app/v1/config/sandbox")
    assert код == 503 and тело["error"]["code"] == "config_unavailable"


def test_жанр_не_для_общей_главной_не_отдаётся(с_конфигурацией, снимок):
    м, база, корень = с_конфигурацией
    подр = json.loads((снимок / "proba-01-details.json").read_text(encoding="utf-8"))
    подр["details"]["tihiy-film"]["genres"] = ["комедия", "Этти"]
    (снимок / "proba-01-details.json").write_text(json.dumps(подр, ensure_ascii=False), encoding="utf-8")
    м.Обработчик.каталог = м.Каталог("proba-01", снимок)
    опубликовать(корень, "sandbox", ревизия(1))
    _, тело, _ = гет(база, "/api/app/v1/config/sandbox")
    п = тело["collections"][0]
    assert [и["contentId"] for и in п["items"]] == [СЕРИАЛ]
    assert ФИЛЬМ in п["missing"]


def test_обновлённый_снимок_перечитывается_без_перезапуска(служба, снимок):
    м, база = служба
    обн = м.ОбновительСнимка("proba-01", снимок, интервал=0)
    м.Обработчик.обновитель = обн
    try:
        кат = json.loads((снимок / "proba-01-catalog.json").read_text(encoding="utf-8"))
        кат["revision"] = "r-2"
        (снимок / "proba-01-catalog.json").write_text(json.dumps(кат, ensure_ascii=False), encoding="utf-8")
        ст = (снимок / "proba-01-catalog.json").stat()
        os.utime(снимок / "proba-01-catalog.json", ns=(ст.st_atime_ns, ст.st_mtime_ns + 5_000_000))
        обн.сверить(ждать=True)
        _, тело, _ = гет(база, "/healthz")
        assert тело["catalogRevision"] == "r-2"
        assert тело["catalogReloadedAt"]
    finally:
        м.Обработчик.обновитель = None


def test_недописанный_снимок_оставляет_прежний(служба, снимок):
    м, база = служба
    обн = м.ОбновительСнимка("proba-01", снимок, интервал=0)
    (снимок / "proba-01-details.json").write_text("{обрыв", encoding="utf-8")
    обн.сверить(ждать=True)
    assert м.Обработчик.каталог.revision == "r-1"
    assert обн.ошибка and "перечитан" in обн.ошибка
