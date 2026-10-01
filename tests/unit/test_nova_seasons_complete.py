"""Проверки состава сезонов ДО публикации снимка.

Производитель строит `seasons` из detail API, а плеер посетителя ходит в
плейлист, и два конца одного источника расходятся. Здесь закреплены оба
случая, измеренные 2026-09-29, и три формы номеров, которые старый контракт
описать не мог: спецвыпуск №0, пропуски и номера выше прежнего `eps`.

Сеть в проверке запрещена: ответ провайдера подставляется. Проверяется НАША
часть — как из ответа получается состав сезонов, который уйдёт на витрины.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
ИНСТРУМЕНТ = КОРЕНЬ / "automation" / "host" / "nova-seasons-complete.py"


def загрузить(имя: str, путь: Path):
    спец = importlib.util.spec_from_file_location(имя, путь)
    м = importlib.util.module_from_spec(спец)
    sys.modules[имя] = м
    спец.loader.exec_module(м)
    return м


nsc = загрузить("_nsc", ИНСТРУМЕНТ)
es = nsc.правила()


def дорожки(по_сезонам: dict, префикс: str = "id"):
    return {"items": [{"season": с, "episode": э, "cvhId": f"{префикс}-{с}-{э}",
                       "vkId": "v"} for с, ном in по_сезонам.items() for э in ном]}


# --- случай boec-baki: сезоны потеряны -------------------------------------

BAKI_СНИМОК = [{"n": 1, "eps": 24, "avail": 24}, {"n": 2, "eps": 24, "avail": 0}]
BAKI_ПЛЕЙЛИСТ = {1: set(range(1, 25)), 2: set(range(1, 27)), 3: set(range(1, 13)),
                 5: set(range(1, 25)), 6: set(range(1, 14)), 7: set(range(1, 28)),
                 8: set(range(1, 14)), 9: set(range(1, 13))}


def test_потерянные_сезоны_дополняются():
    деталь = {"seasons": [dict(с) for с in BAKI_СНИМОК]}
    ответ = дорожки(BAKI_ПЛЕЙЛИСТ)
    es.согласовать(деталь, es.серии_по_сезонам(ответ), "t",
                   es.опознание_по_сезонам(ответ), None)
    assert [с["n"] for с in деталь["seasons"]] == [1, 2, 3, 5, 6, 7, 8, 9]
    восьмой = [с for с in деталь["seasons"] if с["n"] == 8][0]
    assert восьмой["eps"] == 13 and восьмой["from"] == "player"


def test_номера_выше_прежнего_eps_попадают_в_состав():
    """У второго сезона объявлено 24 серии, у провайдера 26."""
    деталь = {"seasons": [dict(с) for с in BAKI_СНИМОК]}
    ответ = дорожки(BAKI_ПЛЕЙЛИСТ)
    es.согласовать(деталь, es.серии_по_сезонам(ответ), "t",
                   es.опознание_по_сезонам(ответ), None)
    второй = [с for с in деталь["seasons"] if с["n"] == 2][0]
    assert второй["nums"][-1] == 26 and второй["eps"] == 24, (
        "состав сезона ведёт конвейер, но играющая серия обязана быть в перечне")


# --- случай avatar-korolya-2: сдвиг нумерации -------------------------------

AVATAR_СНИМОК = [{"n": 1, "eps": 12, "avail": 12}, {"n": 2, "eps": 12, "avail": 12},
                 {"n": 3, "eps": 17, "avail": 17}, {"n": 4, "eps": 3, "avail": 0}]
AVATAR_ПЛЕЙЛИСТ = {1: set(range(1, 13)), 2: set(range(1, 13)), 3: set(range(1, 13)),
                   4: set(range(1, 13)), 5: set(range(1, 18))}


def test_сдвиг_нумерации_не_создаёт_двойника():
    деталь = {"seasons": [dict(с) for с in AVATAR_СНИМОК]}
    ответ = дорожки(AVATAR_ПЛЕЙЛИСТ)
    assert es.нумерация_сходится(деталь, es.серии_по_сезонам(ответ),
                                 es.опознание_по_сезонам(ответ), None) is False
    es.согласовать(деталь, es.серии_по_сезонам(ответ), "t",
                   es.опознание_по_сезонам(ответ), None)
    assert [с["n"] for с in деталь["seasons"]] == [1, 2, 3, 4]


def test_сдвиг_опознаётся_по_идентификаторам_а_не_по_счёту():
    """Число серий у сезонов совпадает — решают идентификаторы дорожек."""
    деталь = {"seasons": [{"n": 3, "eps": 12, "avail": 12}]}
    ответ = дорожки({3: set(range(1, 13)), 7: set(range(1, 13))})
    помним = {"3": [f"id-7-{n}" for n in range(1, 9)]}   # эти дорожки были 3-м
    assert es.нумерация_сходится(деталь, es.серии_по_сезонам(ответ),
                                 es.опознание_по_сезонам(ответ), помним) is False


# --- формы номеров, которые старый контракт не описывал ---------------------

def test_спецвыпуск_ноль_доходит_до_снимка():
    деталь = {"seasons": [{"n": 1, "eps": 6, "avail": 1}]}
    ответ = дорожки({1: {0}})
    es.согласовать(деталь, es.серии_по_сезонам(ответ), "t",
                   es.опознание_по_сезонам(ответ), None)
    assert деталь["seasons"][0]["nums"] == [0]


def test_пропуск_в_нумерации_сохраняется():
    деталь = {"seasons": [{"n": 2, "eps": 21, "avail": 21}]}
    ответ = дорожки({2: set(range(2, 23))})
    es.согласовать(деталь, es.серии_по_сезонам(ответ), "t",
                   es.опознание_по_сезонам(ответ), None)
    assert деталь["seasons"][0]["nums"][0] == 2


def test_отказ_провайдера_не_меняет_состав():
    """Сетевая ошибка не имеет права обнулить рабочий состав сезонов."""
    деталь = {"seasons": [dict(с) for с in BAKI_СНИМОК]}
    было = json.dumps(деталь, sort_keys=True)
    es.согласовать(деталь, {}, "t", {}, None)
    assert json.dumps(деталь, sort_keys=True) == было


# --- отбор и порядок кандидатов ---------------------------------------------

def test_кандидаты_в_том_же_порядке_что_у_витрины():
    деталь = {"id": "01a0e27f-8175-7115-8972-83cce31b15d3",
              "sources": [{"provider": "kp", "source_id": "4750468",
                           "availability_status": "available"}]}
    assert nsc.кандидаты(деталь)[0] == ("kp", "4750468")
    assert ("cvh", деталь["id"]) in nsc.кандидаты(деталь)


def test_без_apply_снимок_не_пишется(tmp_path, monkeypatch):
    снимок = tmp_path / "s-details.json"
    снимок.write_text(json.dumps(
        {"details": {"a": {"id": "a", "sources": [
            {"provider": "kp", "source_id": "414679",
             "availability_status": "available"}],
            "seasons": [dict(с) for с in BAKI_СНИМОК]}}}),
        encoding="utf-8")
    было = снимок.read_bytes()
    monkeypatch.setattr(es, "_плейлист", lambda *а, **к: дорожки(BAKI_ПЛЕЙЛИСТ))
    monkeypatch.setattr(nsc.time, "sleep", lambda _: None)
    nsc.main(["--snapshot", str(снимок), "--publisher", "1", "--origin", "x.test",
              "--limit", "5"])
    assert снимок.read_bytes() == было


def test_с_apply_снимок_дополняется(tmp_path, monkeypatch):
    снимок = tmp_path / "s-details.json"
    снимок.write_text(json.dumps(
        {"details": {"a": {"id": "a", "sources": [
            {"provider": "kp", "source_id": "414679",
             "availability_status": "available"}],
            "seasons": [dict(с) for с in BAKI_СНИМОК]}}}),
        encoding="utf-8")
    monkeypatch.setattr(es, "_плейлист", lambda *а, **к: дорожки(BAKI_ПЛЕЙЛИСТ))
    monkeypatch.setattr(nsc.time, "sleep", lambda _: None)
    nsc.main(["--snapshot", str(снимок), "--publisher", "1", "--origin", "x.test",
              "--limit", "5", "--apply"])
    д = json.loads(снимок.read_text(encoding="utf-8"))["details"]["a"]
    assert [с["n"] for с in д["seasons"]] == [1, 2, 3, 5, 6, 7, 8, 9]
