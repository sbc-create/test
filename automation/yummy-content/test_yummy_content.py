"""Обязательные проверки контентного контура Yummy."""
from __future__ import annotations

import datetime as dt
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import canonical, ingest, readmodel, store

БАЗА = Path("/srv/site-factory/yummy-content/state/yummy-content.sqlite3")


@pytest.fixture(scope="module")
def соед() -> sqlite3.Connection:
    if not БАЗА.exists():
        pytest.skip("контур не собран: запустите build.py")
    c = sqlite3.connect(БАЗА)
    c.row_factory = sqlite3.Row
    return c


@pytest.fixture()
def пустая(tmp_path) -> sqlite3.Connection:
    return store.открыть(tmp_path / "t.sqlite3")


def _запись(ид: str, имя: str, **kw) -> dict:
    з = {"external_id": ид, "name": имя, "type": "tv", "is_series": True,
         "year": 2026, "poster_url": "/p.webp", "created_at": "2026-09-01T00:00:00Z",
         "updated_at": "2026-09-01T00:00:00Z", "external_ids": {}, }
    з.update(kw)
    return з


def _маршрут(ид: str, слаг: str, canonical_=True) -> dict:
    return {"providerTitleId": ид, "slug": слаг, "canonical": canonical_}


# --- 1. все карточки ведут на существующую сущность -------------------------

def test_1_каждая_карточка_разрешается(соед):
    """Ни одна карточка проекции не ведёт в никуда."""
    for имя, п in (("актуальное", readmodel.актуальное(соед, предел=50)),
                   ("новые-серии", readmodel.новые_серии(соед)),
                   ("сейчас-выходит", readmodel.сейчас_выходит(соед))):
        for к in п["items"]:
            assert к["entityId"], f"{имя}: карточка без entity_id"
            assert к["canonicalPath"], f"{имя}: карточка без canonical_path"
            р = readmodel.разрешить_адрес(соед, к["entityId"])
            assert р["outcome"] == "RESOLVED", f"{имя}: {к['entityId']} не разрешён"
            assert р["canonicalPath"] == к["canonicalPath"]


def test_2_адреса_отвечают_200(соед):
    """Карточки открывают существующую страницу на живом приложении."""
    п = readmodel.актуальное(соед, предел=12)
    if not п["items"]:
        pytest.skip("контур пуст")
    for к in п["items"]:
        зпр = urllib.request.Request(
            "http://127.0.0.1:3101" + к["canonicalPath"],
            headers={"Host": "yummyani.site", "User-Agent": "content-test/1.0"})
        try:
            with urllib.request.urlopen(зпр, timeout=20) as о:
                код = о.status
        except urllib.error.HTTPError as e:
            код = e.code
        assert код == 200, f"{к['canonicalPath']} -> HTTP {код}"


# --- 3. повторный импорт не создаёт дублей ----------------------------------

def test_3_повторный_импорт_идемпотентен(пустая):
    записи = [_запись("e1", "Первое"), _запись("e2", "Второе")]
    маршруты = [_маршрут("e1", "pervoe"), _маршрут("e2", "vtoroe")]
    a = ingest.импорт_сущностей(пустая, записи, маршруты)
    b = ingest.импорт_сущностей(пустая, записи, маршруты)
    n = пустая.execute("SELECT count(*) c FROM entity").fetchone()["c"]
    assert a["new"] == 2 and b["new"] == 0
    assert n == 2, f"после повторного импорта {n} строк вместо 2"
    первый = пустая.execute(
        "SELECT first_seen_at FROM entity WHERE entity_id='e1'").fetchone()[0]
    ingest.импорт_сущностей(пустая, записи, маршруты)
    второй = пустая.execute(
        "SELECT first_seen_at FROM entity WHERE entity_id='e1'").fetchone()[0]
    assert первый == второй, "событие появления переписано повторным импортом"


# --- 4. новая серия появляется ровно один раз -------------------------------

def test_4_серия_ровно_один_раз(пустая):
    ingest.импорт_сущностей(пустая, [_запись("e1", "Первое")],
                            [_маршрут("e1", "pervoe")])
    событие = {"entity_id": "e1", "season": 1, "episode": 5, "voice": "AniLibria",
               "source_event_at": "2026-09-09T10:00:00Z", "source": "provider"}
    a = ingest.импорт_серий(пустая, [событие])
    b = ingest.импорт_серий(пустая, [событие])
    n = пустая.execute("SELECT count(*) c FROM episode_event").fetchone()["c"]
    assert a["added"] == 1 and b["added"] == 0 and b["duplicates"] == 1
    assert n == 1, f"серия записана {n} раз"
    другая_озвучка = dict(событие, voice="Studio Band")
    ingest.импорт_серий(пустая, [другая_озвучка])
    assert пустая.execute("SELECT count(*) c FROM episode_event"
                          ).fetchone()["c"] == 2, "другая озвучка — другое событие"


def test_4b_время_выхода_не_подменяется_пересборкой(пустая):
    ingest.импорт_сущностей(пустая, [_запись("e1", "Первое")],
                            [_маршрут("e1", "pervoe")])
    ingest.импорт_серий(пустая, [{"entity_id": "e1", "season": 1, "episode": 1,
                                  "source_event_at": "2026-09-01T08:00:00Z",
                                  "published_at": "2026-09-10T14:00:00Z",
                                  "source": "provider"}])
    с = readmodel.новые_серии(пустая)["items"][0]
    assert с["sourceEventAt"] == "2026-09-01T08:00:00Z"
    assert с["sourceEventAt"] != с["publishedAt"]


# --- 5. завершённый не попадает в «сейчас выходит» --------------------------

def test_5_только_подтверждённый_показ(пустая):
    ingest.импорт_сущностей(
        пустая, [_запись("e1", "Идёт"), _запись("e2", "Завершён"),
                 _запись("e3", "Неподтверждён")],
        [_маршрут("e1", "idet"), _маршрут("e2", "zavershen"),
         _маршрут("e3", "nepodtverzhden")])
    пустая.execute("UPDATE entity SET airing_status='CONFIRMED_ONGOING', "
                   "airing_source='provider:detail' WHERE entity_id='e1'")
    пустая.execute("UPDATE entity SET airing_status='CONFIRMED_COMPLETED' "
                   "WHERE entity_id='e2'")
    пустая.commit()
    ид = [к["entityId"] for к in readmodel.сейчас_выходит(пустая)["items"]]
    assert ид == ["e1"], f"в «сейчас выходит» попали {ид}"


# --- 6. «актуальное» воспроизводимо -----------------------------------------

def test_6_актуальное_воспроизводимо(пустая):
    ingest.импорт_сущностей(пустая, [_запись(f"e{i}", f"Т{i}") for i in range(5)],
                            [_маршрут(f"e{i}", f"t{i}") for i in range(5)])
    т = dt.datetime(2026, 9, 10, tzinfo=dt.timezone.utc)
    a = readmodel.актуальное(пустая, сейчас=т)
    b = readmodel.актуальное(пустая, сейчас=т)
    assert [к["entityId"] for к in a["items"]] == [к["entityId"] for к in b["items"]]
    assert a["formula"]["weights"]["freshness"] == readmodel.ВЕС_СВЕЖЕСТИ
    for к in a["items"]:
        assert "scoreParts" in к, "балл без разложения невоспроизводим"


def test_6b_малое_число_голосов_не_поднимает(пустая):
    """Три голоса с десяткой не обгоняют тысячу голосов с восьмёркой."""
    мало = readmodel.сглаженный_рейтинг(10.0, 3, 10.0)
    много = readmodel.сглаженный_рейтинг(8.0, 1000, 10.0)
    assert мало < много, f"{мало} >= {много}: защиты от малой выборки нет"
    неизвестно = readmodel.сглаженный_рейтинг(10.0, None, 10.0)
    assert неизвестно < много, "неизвестные голоса считаются достаточными"


# --- 7. рейтинги источников не смешиваются ----------------------------------

def test_7_рейтинги_раздельны(пустая):
    ingest.импорт_сущностей(
        пустая,
        [_запись("e1", "Т", kinopoisk_rating=7.9, imdb_rating=6.1,
                 external_ids={"kinopoisk": "123", "imdb": "tt9"})],
        [_маршрут("e1", "t")])
    п = readmodel.внешние_рейтинги(пустая, "e1")
    по = {р["provider"]: р for р in п["providers"]}
    assert по["kp"]["value"] == 7.9 and по["imdb"]["value"] == 6.1
    assert по["kp"]["externalId"] == "123" and по["imdb"]["externalId"] == "tt9"
    for р in п["providers"]:
        assert р["scale"], "значение без шкалы"


def test_7b_отсутствие_рейтинга_не_ноль(пустая):
    ingest.импорт_сущностей(пустая, [_запись("e1", "Т")], [_маршрут("e1", "t")])
    по = {р["provider"]: р for р in
          readmodel.внешние_рейтинги(пустая, "e1")["providers"]}
    assert по["kp"]["status"] == "ABSENT" and по["kp"]["value"] is None


def test_7c_оценка_пользователя_отдельно(пустая):
    ingest.импорт_сущностей(пустая, [_запись("e1", "Т", kinopoisk_rating=7.9)],
                            [_маршрут("e1", "t")])
    assert readmodel.поставить_оценку(пустая, "u1", "e1", 9)["ok"]
    assert readmodel.поставить_оценку(пустая, "u1", "e1", 4)["ok"]  # изменение
    а = readmodel.пользовательский_рейтинг(пустая, "e1", "u1")
    assert а["aggregate"]["count"] == 1, "изменение оценки создало вторую строку"
    assert а["mine"]["value"] == 4
    внеш = {р["provider"]: р for р in
            readmodel.внешние_рейтинги(пустая, "e1")["providers"]}
    assert внеш["kp"]["value"] == 7.9
    плохо = readmodel.поставить_оценку(пустая, "u1", "e1", 99)
    assert not плохо["ok"] and плохо["error"] == "VALUE_OUT_OF_RANGE"


# --- 8. остановка импорта обнаруживается ------------------------------------

def test_8_пустой_импорт_не_затирает_и_виден(пустая):
    ingest.импорт_сущностей(пустая, [_запись("e1", "Т")], [_маршрут("e1", "t")])
    итог = ingest.импорт_сущностей(пустая, [], [_маршрут("e1", "t")])
    assert итог["skipped"] == "EMPTY_SOURCE"
    assert пустая.execute("SELECT count(*) c FROM entity").fetchone()["c"] == 1
    dlq = пустая.execute("SELECT error_code, reason FROM dead_letter").fetchall()
    assert dlq and dlq[0]["error_code"] == "EMPTY_SOURCE"
    сост = пустая.execute("SELECT error_code, attempts FROM import_state "
                          "WHERE stream='entities'").fetchone()
    assert сост["error_code"] == "EMPTY_SOURCE" and сост["attempts"] >= 1


def test_8b_обвал_источника_отклоняется(пустая):
    записи = [_запись(f"e{i}", f"Т{i}") for i in range(20)]
    маршруты = [_маршрут(f"e{i}", f"t{i}") for i in range(20)]
    ingest.импорт_сущностей(пустая, записи, маршруты)
    итог = ingest.импорт_сущностей(пустая, записи[:5], маршруты)
    assert итог["skipped"] == "SOURCE_SHRINK"
    assert пустая.execute("SELECT count(*) c FROM entity").fetchone()["c"] == 20


# --- 9. запись без объявленного адреса не публикуется -----------------------

def test_9_без_маршрута_не_публикуется(пустая):
    итог = ingest.импорт_сущностей(
        пустая, [_запись("e1", "Есть"), _запись("e2", "Нет адреса")],
        [_маршрут("e1", "est")])
    assert итог["rejected"] == 1
    assert пустая.execute("SELECT count(*) c FROM entity").fetchone()["c"] == 1


def test_9b_только_псевдоним_не_публикуется(пустая):
    итог = ingest.импорт_сущностей(пустая, [_запись("e1", "Т")],
                                   [_маршрут("e1", "alias", canonical_=False)])
    assert итог["rejected"] == 1
    assert пустая.execute("SELECT count(*) c FROM entity").fetchone()["c"] == 0


# --- 10. новости: дедупликация и обязательные поля --------------------------

def test_10_новость_дедуплицируется(пустая):
    т = "2026-09-10T10:00:00Z"
    for _ in range(2):
        пустая.execute(
            "INSERT INTO editorial_post(post_id, type, source, source_key, "
            "title, summary, canonical_path, provenance, published_at, "
            "updated_at, status) VALUES(?,?,?,?,?,?,?,?,?,?,'published') "
            "ON CONFLICT(source, source_key) DO UPDATE SET updated_at=excluded.updated_at",
            ("p1", "news", "editorial-cli", "k1", "Заголовок", "Кратко",
             "/news/zagolovok/", "editorial:cli", т, т))
    пустая.commit()
    п = readmodel.новости(пустая)
    assert len(п["items"]) == 1, "повторная подача создала вторую новость"
    н = п["items"][0]
    for поле in ("postId", "source", "title", "publishedAt", "updatedAt",
                 "canonicalPath", "provenance", "relatedEntityIds"):
        assert поле in н, f"в новости нет обязательного поля {поле}"
