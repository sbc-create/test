"""Согласование доступности: что оно пишет и, главное, чего НЕ пишет.

Требование владельца разделено здесь на три разных исхода, которые раньше
выглядели одинаково:

  подтверждённое отсутствие потока — провайдер ответил, дорожек в сезоне нет;
  временная ошибка запроса         — провайдер не ответил вовсе;
  устаревшие или непроверенные     — сезона в ответе не было.

«Не заменяй последнее известное рабочее состояние нулём из-за таймаута» —
это не пожелание, а самый дорогой из возможных промахов: он снимает со
страницы серии, которые играются.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
МОДУЛЬ = КОРЕНЬ / "automation" / "host" / "episode_sync.py"


def загрузить():
    спец = importlib.util.spec_from_file_location("_episode_sync", МОДУЛЬ)
    м = importlib.util.module_from_spec(спец)
    sys.modules["_episode_sync"] = м
    спец.loader.exec_module(м)
    return м


es = загрузить()


class Подробности:
    def __init__(self, путь: Path, записи: dict) -> None:
        self.path = str(путь)
        self.записи = записи
        путь.write_text(json.dumps({"details": записи}, ensure_ascii=False),
                        encoding="utf-8")
        self.mtime = путь.stat().st_mtime


class Рантайм:
    """Минимальный двойник витрины: только то, чем пользуется согласование."""

    def __init__(self, подробности, *, publisher="10238", mode="provider-id") -> None:
        self.ПЛЕЕР = {"publisher_id": publisher, "source_mode": mode}

        class Обработчик:
            pass

        Обработчик.подробности = подробности
        self.Обработчик = Обработчик

    @staticmethod
    def кандидаты_источника(деталь):
        return [("cvh", деталь.get("id") or "x")]


def дорожка(сезон: int, эпизод: int) -> dict:
    return {"season": сезон, "episode": эпизод, "cvhId": "c1", "vkId": "v1"}


# --- разбор ответа провайдера ------------------------------------------------

def test_ноль_настоящий_номер_серии():
    """У «Скоттов» это единственная дорожка записи."""
    assert es.серии_по_сезонам({"items": [дорожка(1, 0)]}) == {1: {0}}


def test_заготовка_без_потока_дорожкой_не_считается():
    """Пустая позиция означает «озвучка заявлена», а не «включается»."""
    ответ = {"items": [{"season": 1, "episode": 3, "cvhId": "", "vkId": ""}]}
    assert es.серии_по_сезонам(ответ) == {}


def test_пропуски_сохраняются_как_есть():
    ответ = {"items": [дорожка(2, 2), дорожка(2, 5), дорожка(2, 6)]}
    assert es.серии_по_сезонам(ответ) == {2: {2, 5, 6}}


# --- что записывается в снимок ----------------------------------------------

def test_перечень_записывается_с_отметкой_времени():
    деталь = {"seasons": [{"n": 1, "eps": 6, "avail": 1}]}
    assert es.согласовать(деталь, {1: {0}}, "2026-09-28T21:00:00Z") is True
    сезон = деталь["seasons"][0]
    assert сезон["nums"] == [0] and сезон["nums_at"] == "2026-09-28T21:00:00Z"
    # `avail` принадлежит суточному конвейеру и отсюда не правится: иначе
    # согласование спорило бы с доставкой каждый день.
    assert сезон["avail"] == 1


def test_сезон_которого_в_ответе_нет_не_трогается():
    """Расхождение нумерации или неполный ответ — не доказательство отсутствия."""
    деталь = {"seasons": [{"n": 1, "eps": 6, "avail": 3, "nums": [1, 2, 3]},
                          {"n": 2, "eps": 4, "avail": 4}]}
    es.согласовать(деталь, {1: {1, 2, 3, 4}}, "t")
    assert деталь["seasons"][1] == {"n": 2, "eps": 4, "avail": 4}


def test_пустой_ответ_по_сезону_ничего_не_снимает():
    деталь = {"seasons": [{"n": 1, "eps": 6, "avail": 3, "nums": [1, 2, 3]}]}
    assert es.согласовать(деталь, {1: set()}, "t") is False
    assert деталь["seasons"][0]["nums"] == [1, 2, 3]


def test_подтверждённое_сокращение_записывается():
    """Метод отдаёт список целиком, поэтому непустой ответ — полное описание."""
    деталь = {"seasons": [{"n": 1, "eps": 6, "avail": 5, "nums": [1, 2, 3, 4, 5]}]}
    assert es.согласовать(деталь, {1: {1, 2}}, "t") is True
    assert деталь["seasons"][0]["nums"] == [1, 2]


# --- проход: временная ошибка не портит данные -------------------------------

def test_отказ_запроса_не_меняет_снимок(tmp_path, monkeypatch):
    записи = {"skotty": {"id": "a", "seasons": [{"n": 1, "eps": 6, "avail": 1}]}}
    п = Подробности(tmp_path / "d.json", записи)
    monkeypatch.setattr(es, "_плейлист", lambda *а, **к: None)
    monkeypatch.setattr(es.time, "sleep", lambda _: None)
    итог = es.Согласование(Рантайм(п), домен="x.test",
                           каталог_позиции=tmp_path / "ring.json").проход(п)
    assert итог["согласовано"] == 0 and итог["записано"] is False
    assert итог["отказов_запроса"] >= 1
    assert "nums" not in записи["skotty"]["seasons"][0]


def test_успешный_проход_пишет_файл_и_позицию(tmp_path, monkeypatch):
    записи = {"skotty": {"id": "a", "seasons": [{"n": 1, "eps": 6, "avail": 1}]}}
    п = Подробности(tmp_path / "d.json", записи)
    monkeypatch.setattr(es, "_плейлист",
                        lambda *а, **к: {"items": [дорожка(1, 0)]})
    monkeypatch.setattr(es.time, "sleep", lambda _: None)
    кольцо = tmp_path / "ring.json"
    итог = es.Согласование(Рантайм(п), домен="x.test",
                           каталог_позиции=кольцо).проход(п)
    assert итог["согласовано"] == 1 and итог["записано"] is True
    на_диске = json.loads((tmp_path / "d.json").read_text(encoding="utf-8"))
    assert на_диске["details"]["skotty"]["seasons"][0]["nums"] == [0]
    assert json.loads(кольцо.read_text(encoding="utf-8"))["после"] == "skotty"


def test_свежая_доставка_не_затирается(tmp_path, monkeypatch):
    """Конвейер положил новый снимок, пока шёл проход, — запись отменяется."""
    записи = {"a": {"id": "a", "seasons": [{"n": 1, "eps": 2, "avail": 0}]}}
    п = Подробности(tmp_path / "d.json", записи)
    п.mtime = 0.0                       # как будто читали задолго до доставки
    monkeypatch.setattr(es, "_плейлист",
                        lambda *а, **к: {"items": [дорожка(1, 1)]})
    monkeypatch.setattr(es.time, "sleep", lambda _: None)
    итог = es.Согласование(Рантайм(п), домен="x.test",
                           каталог_позиции=tmp_path / "ring.json").проход(п)
    assert итог["записано"] is False


# --- очередь -----------------------------------------------------------------

def test_очередь_начинается_с_полного_недобора():
    записи = {
        "растущий": {"seasons": [{"n": 1, "eps": 9, "avail": 3}]},
        "полный": {"seasons": [{"n": 1, "eps": 9, "avail": 0}]},
        "прочий": {"seasons": [{"n": 1, "eps": 9, "avail": 9}]},
    }
    assert es.очередь(записи) == ["полный", "растущий", "прочий"]


def test_в_очередь_попадают_и_записи_с_полным_avail():
    """У «Скоттов» ложным было само обещание, а не его величина."""
    assert "прочий" in es.очередь(
        {"прочий": {"seasons": [{"n": 1, "eps": 9, "avail": 9}]}})


# --- условия запуска ---------------------------------------------------------

@pytest.mark.parametrize("окружение,плеер", [
    ({}, {"publisher_id": "10238", "source_mode": "provider-id"}),
    ({"LORDS_SITE_HOST": "x.test"}, {"publisher_id": "", "source_mode": "provider-id"}),
    ({"LORDS_SITE_HOST": "x.test"}, {"publisher_id": "10238", "source_mode": "external-ids"}),
])
def test_поток_не_заводится_без_условий(tmp_path, monkeypatch, окружение, плеер):
    """Чужой Origin, отсутствующий publisher и режим одного ключа — отказ."""
    for имя in ("LORDS_SITE_HOST", "ANIMEDIA_SITE_HOST", "ANIMEGO_SITE_HOST"):
        monkeypatch.delenv(имя, raising=False)
    for к, в in окружение.items():
        monkeypatch.setenv(к, в)
    п = Подробности(tmp_path / "d.json", {})
    р = Рантайм(п)
    р.ПЛЕЕР = плеер
    assert es.запустить(р) is False


# --- срочные -----------------------------------------------------------------

def test_срочные_спрашиваются_первыми_и_не_двигают_круг(tmp_path, monkeypatch):
    """Суточная доставка каждый раз возвращает снимок без `nums`.

    Запись, на которую владелец уже пожаловался, обязана выправиться в первые
    минуты после доставки, а не когда до неё дойдёт обход двадцати тысяч
    сериалов. При этом позицию круга срочные не двигают: иначе каждый проход
    начинался бы заново и хвост каталога не спрашивался бы никогда.
    """
    записи = {
        "aaa": {"id": "aaa", "seasons": [{"n": 1, "eps": 2, "avail": 0}]},
        "skotty": {"id": "s", "seasons": [{"n": 1, "eps": 6, "avail": 1}]},
    }
    п = Подробности(tmp_path / "d.json", записи)
    monkeypatch.setenv("LORDS_AVAIL_URGENT", "skotty")
    monkeypatch.setattr(es, "ЗА_ПРОХОД", 1)
    monkeypatch.setattr(es, "_плейлист", lambda *а, **к: {"items": [дорожка(1, 0)]})
    monkeypatch.setattr(es.time, "sleep", lambda _: None)
    итог = es.Согласование(Рантайм(п), домен="x.test",
                           каталог_позиции=tmp_path / "ring.json").проход(п)
    assert записи["skotty"]["seasons"][0]["nums"] == [0], "срочную не спросили"
    assert итог["позиция"] == "aaa", "срочная сдвинула круг — хвост не будет обойдён"


def test_срочные_не_названы_ничего_не_меняют(tmp_path, monkeypatch):
    monkeypatch.delenv("LORDS_AVAIL_URGENT", raising=False)
    assert es.срочные() == []
