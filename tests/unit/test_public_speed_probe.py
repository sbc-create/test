"""REQ-PUBLIC-SPEED: первый ответ и последующие считаются раздельно.

Первый запрос к витрине после сброса памятки стоит дороже остальных — измерено
06.10 на zonafilm.cc: `/collections/` дважды ответила 504, а в двадцати прямых
замерах — 200 за 0.08–0.5 с. Смешивать их в одно «среднее время» нельзя: именно
первый запрос получает обход, и именно он падает.

Закрепляется:

* первый замер отдельно, медиана остальных отдельно;
* один повтор — медианы нет (None), а не «равна первому»;
* превышение считается по медиане и по весу, с порогами из аргументов;
* адрес не ответил — «не измерено» с причиной, а не ноль.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_путь = КОРЕНЬ / "automation/local/public-speed-probe.py"
_спец = importlib.util.spec_from_file_location("public_speed_probe", _путь)
ИНСТР = importlib.util.module_from_spec(_спец)
_спец.loader.exec_module(ИНСТР)


def _замеры(monkeypatch, последовательность):
    очередь = list(последовательность)

    def подделка(адрес, таймаут=30):
        return очередь.pop(0) if очередь else последовательность[-1]

    monkeypatch.setattr(ИНСТР, "замер", подделка)


def test_первый_замер_отдельно_от_медианы(monkeypatch):
    _замеры(monkeypatch, [
        {"ок": True, "код": "200", "ttfb": 2.0, "всего": 2.5, "байт": 100000},
        {"ок": True, "код": "200", "ttfb": 0.2, "всего": 0.3, "байт": 100000},
        {"ок": True, "код": "200", "ttfb": 0.3, "всего": 0.4, "байт": 100000},
    ])
    и = ИНСТР.опросить("https://a.test/", 3)
    assert и["измерено"] is True
    assert и["ttfb_первый"] == 2.0
    assert и["ttfb_медиана"] == 0.25
    assert и["мб"] == 0.1


def test_один_повтор_медианы_не_даёт(monkeypatch):
    _замеры(monkeypatch, [
        {"ок": True, "код": "200", "ttfb": 0.5, "всего": 0.6, "байт": 1048576}])
    и = ИНСТР.опросить("https://a.test/", 1)
    assert и["ttfb_первый"] == 0.5 and и["ttfb_медиана"] is None
    assert и["мб"] == 1.0


def test_не_ответил_не_измерено(monkeypatch):
    _замеры(monkeypatch, [{"ок": False, "почему": "curl код 28"}])
    и = ИНСТР.опросить("https://a.test/", 2)
    assert и["измерено"] is False and "28" in и["почему"]


def test_частичный_отказ_считается_по_удачным(monkeypatch):
    _замеры(monkeypatch, [
        {"ок": False, "почему": "curl код 28"},
        {"ок": True, "код": "200", "ttfb": 0.4, "всего": 0.5, "байт": 2048},
        {"ок": True, "код": "200", "ttfb": 0.6, "всего": 0.7, "байт": 2048},
    ])
    и = ИНСТР.опросить("https://a.test/", 3)
    assert и["измерено"] is True and и["замеров"] == 2
    assert и["ttfb_первый"] == 0.4 and и["ttfb_медиана"] == 0.6


def test_превышение_по_медиане(monkeypatch, capsys):
    _замеры(monkeypatch, [
        {"ок": True, "код": "200", "ttfb": 0.5, "всего": 0.6, "байт": 1000},
        {"ок": True, "код": "200", "ttfb": 2.0, "всего": 2.2, "байт": 1000},
        {"ок": True, "код": "200", "ttfb": 2.2, "всего": 2.4, "байт": 1000},
    ])
    код = ИНСТР.main(["--url", "https://a.test/", "--repeat", "3", "--ttfb", "1.5"])
    assert код == 1
    assert "превышение" in capsys.readouterr().out


def test_превышение_по_весу(monkeypatch, capsys):
    тяжёлый = {"ок": True, "код": "200", "ttfb": 0.1, "всего": 0.2,
               "байт": 5 * 1048576}
    _замеры(monkeypatch, [тяжёлый, тяжёлый, тяжёлый])
    assert ИНСТР.main(["--url", "https://a.test/", "--repeat", "3",
                       "--weight", "3"]) == 1
    assert "превышение" in capsys.readouterr().out


def test_в_пределах_порогов_код_0(monkeypatch, capsys):
    быстрый = {"ок": True, "код": "200", "ttfb": 0.2, "всего": 0.3, "байт": 1000}
    _замеры(monkeypatch, [быстрый, быстрый, быстрый])
    assert ИНСТР.main(["--url", "https://a.test/", "--repeat", "3"]) == 0
    вывод = capsys.readouterr().out
    assert "превышений 0" in вывод
    assert "Core Web Vitals здесь НЕ измеряются" in вывод


def test_без_адресов_код_2(capsys):
    assert ИНСТР.main([]) == 2
    assert "НЕ ИЗМЕРЕНО" in capsys.readouterr().out


def test_страницы_спроса_из_выгрузки(tmp_path):
    п = tmp_path / "cabinet.json"
    п.write_text(json.dumps({"domains": [{"domain": "a.test", "measurements": [
        {"key": "search_landing_pages", "measured": True, "value": [
            {"dimensions": [{"id": "organic"}, {"name": "/b"}], "metrics": [5]},
            {"dimensions": [{"id": "organic"}, {"name": "/a"}], "metrics": [50]}]}]}]}),
        encoding="utf-8")
    адреса, беда = ИНСТР.страницы_спроса(п, "a.test", 2)
    assert беда == ""
    assert адреса == ["https://a.test/a", "https://a.test/b"]


def test_нет_домена_в_выгрузке(tmp_path):
    п = tmp_path / "cabinet.json"
    п.write_text(json.dumps({"domains": []}), encoding="utf-8")
    адреса, беда = ИНСТР.страницы_спроса(п, "a.test", 2)
    assert адреса == [] and "нет" in беда
