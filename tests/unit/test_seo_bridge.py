"""Мост CORE → SEO: что уходит, что не уходит и что честно отсутствует.

Главные проверки здесь отрицательные. Мост опасен не тем, что чего-то не
передаст, а тем, что передаст лишнее либо выдаст отсутствие источника за
пустое значение.
"""

from __future__ import annotations

import datetime as dt
import json

import pytest

from factory.site_engine import seo_bridge as b

СЕЙЧАС = dt.datetime(2026, 9, 8, 12, 0, tzinfo=dt.timezone.utc)


def _запись(**ещё):
    з = {"external_id": "4417", "name": "Тишина", "year": 2026,
         "type": "anime", "is_series": True, "tags": ["16+"],
         "kinopoisk_rating": 7.8, "licensed": True,
         "playback": {"aggregator": "kp", "title_id": "stream-9911"},
         "poster_url": "https://cdn.example/poster-abc.jpg",
         "external_ids": {"myanimelist": "4417"}, "updated_at": "2026-09-01"}
    з.update(ещё)
    return з


# --- что не уходит --------------------------------------------------------------------

def test_запрещённые_значения_в_пакет_не_попадают():
    r = b.export_record(_запись(), site_id="s1")
    текст = json.dumps(r, ensure_ascii=False)
    for значение in ("stream-9911", "cdn.example", "poster-abc.jpg"):
        assert значение not in текст, значение


def test_имена_снятых_полей_остаются_а_значения_нет():
    """Потребителю важно знать, что поле было и снято намеренно, а не
    отсутствовало у источника."""
    r = b.export_record(_запись(), site_id="s1")
    assert r["droppedFieldNames"] == ["licensed", "playback", "poster_url"]


def test_подделка_ловится_по_значению_а_не_по_имени():
    """Проверка по именам поймала бы саму запись о снятии и молчала бы о
    настоящей утечке."""
    подделка = _запись(name="https://cdn.example/poster-abc.jpg")
    with pytest.raises(b.BridgeRefusal, match="значения запрещённых полей"):
        b.export_record(подделка, site_id="s1")


def test_запись_без_устойчивого_идентификатора_не_уходит():
    with pytest.raises(b.BridgeRefusal, match="без устойчивого идентификатора"):
        b.export_record(_запись(external_id=""), site_id="s1")


# --- честное отсутствие -------------------------------------------------------------------

def test_все_пятнадцать_полей_в_ответе_всегда():
    """Поле, выпавшее из ответа, читается как «про него не спрашивали»."""
    r = b.export_record(_запись(), site_id="s1")
    assert [f["key"] for f in r["descriptive"]] == list(b.DESCRIPTIVE_FIELDS)
    assert len(r["descriptive"]) == 15


def test_отсутствие_источника_отличается_от_пустого_значения():
    """Пустое поле в успешном ответе читается как «источник проверен, данных
    нет», а верное здесь — «источника не существует»."""
    r = b.export_record(_запись(), site_id="s1")
    поля = {f["key"]: f for f in r["descriptive"]}
    assert поля["synopsis"]["state"] == b.FieldState.MISSING_NO_SOURCE
    assert "отсутствие источника" in поля["synopsis"]["reason"]
    assert поля["year"]["state"] == b.FieldState.PRESENT


def test_запись_без_года_отличается_от_поля_без_источника():
    r = b.export_record(_запись(year=None), site_id="s1")
    поля = {f["key"]: f for f in r["descriptive"]}
    assert поля["year"]["state"] == b.FieldState.ABSENT
    assert поля["genres"]["state"] == b.FieldState.MISSING_NO_SOURCE


def test_перечень_отдаваемого_совпадает_с_измеренным():
    assert b.SUPPLIED_FIELDS == {"year", "ageRating"}
    assert len(set(b.DESCRIPTIVE_FIELDS) - b.SUPPLIED_FIELDS) == 13


# --- оценка ---------------------------------------------------------------------------------

def test_оценка_без_шкалы_не_объявляет_шкалу():
    """7,8 из десяти и 7,8 из ста — разные утверждения."""
    r = b.export_record(_запись(), site_id="s1")
    assert r["rating"]["ratingState"] == "RATED"
    assert r["rating"]["scaleMax"] is None
    assert r["rating"]["votesCount"] is None
    assert "выпускать нечем" in r["rating"]["reason"]


def test_отсутствие_оценки_не_ноль():
    r = b.export_record(_запись(kinopoisk_rating=None, imdb_rating=None),
                        site_id="s1")
    assert r["rating"]["ratingState"] == "UNRATED"
    assert r["rating"]["value"] is None


def test_нечисловая_оценка_не_превращается_в_число():
    r = b.export_record(_запись(kinopoisk_rating="очень хорошо"), site_id="s1")
    assert r["rating"]["ratingState"] == "UNKNOWN"
    assert r["rating"]["value"] is None


# --- постраничность ---------------------------------------------------------------------------

def _много(n):
    return [_запись(external_id=f"{i:05d}") for i in range(n)]


def test_обход_страниц_не_теряет_записей():
    записи = _много(250)
    собрано = []
    смещение = 0
    while True:
        стр = b.export_page(записи, site_id="s1", offset=смещение, limit=100,
                            now=СЕЙЧАС)
        собрано += [r["contentId"] for r in стр["records"]]
        if not стр["hasMore"]:
            break
        смещение += стр["limit"]
    assert len(собрано) == 250
    assert len(set(собрано)) == 250


def test_порядок_задан_идентификатором_а_не_источником():
    """Порядок источника меняется при перестроении кэша, и постраничный обход
    тогда теряет записи между страницами."""
    записи = _много(50)
    прямо = b.export_page(записи, site_id="s1", limit=50, now=СЕЙЧАС)
    вперемешку = b.export_page(list(reversed(записи)), site_id="s1", limit=50,
                               now=СЕЙЧАС)
    assert прямо["digest"] == вперемешку["digest"]


def test_отпечаток_не_зависит_от_времени_сборки():
    """Время сборки говорит о нашем прогоне, а не о данных."""
    записи = _много(10)
    a = b.export_page(записи, site_id="s1", now=СЕЙЧАС)
    c = b.export_page(записи, site_id="s1",
                      now=СЕЙЧАС + dt.timedelta(days=3))
    assert a["digest"] == c["digest"]
    assert a["generatedAt"] != c["generatedAt"]


@pytest.mark.parametrize("плохое", [-1, "10", True, 0.5])
def test_негодное_смещение_отвергается(плохое):
    with pytest.raises(b.BridgeRefusal):
        b.export_page(_много(5), site_id="s1", offset=плохое)


def test_предел_страницы_ограничен():
    with pytest.raises(b.BridgeRefusal, match="от 1 до"):
        b.export_page(_много(5), site_id="s1", limit=b.MAX_PAGE + 1)


def test_пакет_без_витрины_не_собирается():
    """Пакет без витрины нельзя проверить на принадлежность."""
    with pytest.raises(b.BridgeRefusal, match="витрина не названа"):
        b.export_page(_много(5), site_id="")


def test_витрина_проставлена_в_каждой_записи():
    стр = b.export_page(_много(5), site_id="yummyani-site", now=СЕЙЧАС)
    assert all(r["siteId"] == "yummyani-site" for r in стр["records"])


# --- согласование версий ------------------------------------------------------------------------

def test_младшая_версия_потребителя_совместима():
    assert b.handshake("core-seo-bridge/1.7.0")["compatible"]


def test_чужая_старшая_версия_несовместима():
    итог = b.handshake("core-seo-bridge/2.0.0")
    assert not итог["compatible"]
    assert "угадывать" in итог["reason"]


def test_чужая_схема_несовместима():
    assert not b.handshake("совсем-другое/1.0.0")["compatible"]


def test_согласование_называет_что_отдаётся_а_что_нет():
    """Несовместимость обязана обнаруживаться до работы: на середине половина
    пакета уже разобрана чужими правилами."""
    итог = b.handshake(b.BRIDGE_SCHEMA)
    assert len(итог["descriptiveFields"]) == 15
    assert итог["suppliedFields"] == ["ageRating", "year"]
