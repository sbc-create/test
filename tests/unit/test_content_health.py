"""REQ-CONTENT-HEALTH: покрытие воспроизведения видно и объяснено.

Проверяется не наличие чисел, а их пригодность: знаменатель честный, причины
разложены по кодам, устаревание проекции заметно, а список проблемных карточек
называет звено и способ устранения.
"""
import json
import time

import pytest

from factory.site_engine.api import content_health as ch


@pytest.fixture
def корень(tmp_path):
    d = tmp_path / "var" / "lords" / "lords" / "catalog-cache"
    d.mkdir(parents=True)
    items = [
        {"external_id": "a", "name": "С дескриптором", "is_series": False, "year": 2026,
         "created_at": "2026-09-01T00:00:00Z",
         "external_ids": {"kinopoisk": "1"}, "playback": {"aggregator": "kp", "title_id": "1"}},
        {"external_id": "b", "name": "Только IMDb", "is_series": False, "year": 2026,
         "created_at": "2026-09-01T00:00:00Z",
         "external_ids": {"imdb": "2"}, "playback": None},
        {"external_id": "c", "name": "Без идентификаторов", "is_series": True, "year": 2026,
         "created_at": "2026-08-01T00:00:00Z",
         "external_ids": {}, "playback": None},
        {"external_id": "d", "name": "Поставщик пуст", "is_series": False, "year": 2025,
         "created_at": "2026-07-01T00:00:00Z",
         "external_ids": {"kinopoisk": "9"}, "playback": {"aggregator": "kp", "title_id": "9"}},
    ]
    (d / "lords-01.json").write_text(json.dumps({"items": items}, ensure_ascii=False),
                                     encoding="utf-8")
    (tmp_path / "var" / "lords" / "playability.json").write_text(
        json.dumps({"kp:9": {"playable": False, "checked_at": 1}}), encoding="utf-8")
    return tmp_path


def test_знаменатель_честный(корень):
    d = ch.сводка(корень)
    assert d["fleet"]["total"] == 4
    assert d["fleet"]["playable"] == 1
    assert d["fleet"]["coverage"] == pytest.approx(0.25)


def test_причины_разложены_по_кодам(корень):
    r = ch.сводка(корень)["fleet"]["reasons"]
    assert r["OK"] == 1
    assert r["UNSUPPORTED_AGGREGATOR"] == 1, "запись только с IMDb при узком списке"
    assert r["MISSING_PROVIDER_ID"] == 1
    assert r["PROVIDER_NOT_PLAYABLE"] == 1


def test_расширение_списка_агрегаторов_видно_в_покрытии(корень):
    узкий = ch.сводка(корень, supported=("kp",))
    широкий = ch.сводка(корень, supported=("kp", "imdb"))
    assert узкий["fleet"]["reasons"].get("UNSUPPORTED_AGGREGATOR") == 1
    # При широком списке запись всё равно без дескриптора в кэше: покрытие
    # меняется только после переработки проекции, и это должно быть видно.
    assert широкий["fleet"]["total"] == узкий["fleet"]["total"]


def test_устаревшая_проекция_заметна(корень):
    import os
    файл = корень / "var" / "lords" / "lords" / "catalog-cache" / "lords-01.json"
    старое = time.time() - ch.FRESHNESS_SLO_SECONDS - 60
    os.utime(файл, (старое, старое))
    s = ch.сводка(корень)["sites"]["lords-01"]
    assert s["projectionStale"] is True
    assert s["projectionAgeSeconds"] > ch.FRESHNESS_SLO_SECONDS


def test_свежая_проекция_не_помечается(корень):
    s = ch.сводка(корень)["sites"]["lords-01"]
    assert s["projectionStale"] is False


def test_разбивка_по_типу_и_месяцу(корень):
    s = ch.сводка(корень)["sites"]["lords-01"]
    assert "movie" in s["byType"] and "series" in s["byType"]
    assert any(m.startswith("2026-") for m in s["recentMonths"])


def test_проблемные_называют_звено_и_устранение(корень):
    d = ch.проблемные(корень, "lords-01")
    assert d["total"] == 3, "три карточки без воспроизведения"
    for row in d["items"]:
        assert row["reason"] != "OK"
        assert row["stage"], "не указано звено"
        assert row["remediation"], "не сказано, что делать"
        assert row["public"], "нет безопасного сообщения"
        assert isinstance(row["terminal"], bool)


def test_фильтр_по_коду(корень):
    d = ch.проблемные(корень, "lords-01", code="MISSING_PROVIDER_ID")
    assert d["total"] == 1
    assert d["items"][0]["name"] == "Без идентификаторов"


def test_предел_соблюдается(корень):
    d = ch.проблемные(корень, "lords-01", limit=1)
    assert len(d["items"]) == 1


def test_неизвестная_витрина_не_роняет(корень):
    d = ch.проблемные(корень, "нет-такой")
    assert "error" in d


def test_повреждённый_кэш_не_роняет_сводку(корень):
    файл = корень / "var" / "lords" / "lords" / "catalog-cache" / "lords-01.json"
    файл.write_text("{битый", encoding="utf-8")
    d = ch.сводка(корень)
    assert "error" in d["sites"]["lords-01"], "повреждение обязано быть названо"
    assert d["fleet"]["total"] == 0


def test_отсутствие_каталога_не_роняет(tmp_path):
    d = ch.сводка(tmp_path)
    assert "error" in d


def test_версия_классификации_указана(корень):
    assert ch.сводка(корень)["reasonVersion"]
    assert ch.проблемные(корень, "lords-01")["reasonVersion"]
