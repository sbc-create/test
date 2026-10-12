"""Снимок живого режима индексации: что считается сохранением, а что нет.

Задание владельца требует сохранять режим индексации каждого сайта, и
подтвердить это обещанием нельзя: в истории хозяйства пересоздание контейнера
уже один раз поставило `yummyani.site` в `NOINDEX` (P0). Поэтому здесь
проверяется не «снимок делается», а три различения, на которых такое
подтверждение ломается: изменение против тишины, недоступный домен против
сохранённого режима, заголовок против мета-тега.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
ИСТОЧНИК = КОРЕНЬ / "automation" / "local" / "indexing-live-snapshot.py"

ОТКРЫТ = {"код": "200", "x_robots_tag": "index, follow",
          "meta_robots": "index, follow",
          "canonical": "https://проба.test/"}


def _модуль():
    спец = importlib.util.spec_from_file_location("indexing_live_snapshot",
                                                  ИСТОЧНИК)
    м = importlib.util.module_from_spec(спец)
    sys.modules["indexing_live_snapshot"] = м
    спец.loader.exec_module(м)
    return м


сн = _модуль()


def _стенд(monkeypatch, состояния: dict, домены=("проба.test",)):
    monkeypatch.setattr(сн, "живые_домены", lambda: list(домены))
    monkeypatch.setattr(сн, "снять",
                        lambda домен, предел: состояния[домен])


def test_снимок_и_сверка_без_изменений(monkeypatch, tmp_path, capsys):
    _стенд(monkeypatch, {"проба.test": dict(ОТКРЫТ)})
    assert сн.главное(["--snapshot", "--store", str(tmp_path)]) == 0
    capsys.readouterr()
    код = сн.главное(["--compare", "--store", str(tmp_path)])
    вывод = capsys.readouterr().out
    assert код == 0, вывод
    assert "режим не изменился" in вывод
    assert "изменений: 0" in вывод


def test_смена_заголовка_называется_и_меняет_код(monkeypatch, tmp_path, capsys):
    """Главный исход, ради которого инструмент и нужен."""
    состояние = {"проба.test": dict(ОТКРЫТ)}
    _стенд(monkeypatch, состояние)
    сн.главное(["--snapshot", "--store", str(tmp_path)])
    capsys.readouterr()

    состояние["проба.test"] = dict(ОТКРЫТ, x_robots_tag="noindex, nofollow")
    код = сн.главное(["--compare", "--store", str(tmp_path)])
    вывод = capsys.readouterr().out
    assert код == 1, вывод
    assert "ИЗМЕНИЛОСЬ" in вывод
    assert "x_robots_tag" in вывод
    assert "noindex" in вывод
    assert "изменений: 1" in вывод


def test_заголовок_и_мета_различаются(monkeypatch, tmp_path, capsys):
    """Они могут расходиться, и тогда важно какое именно изменилось.

    У пяти витрин Yummy заголовка нет вовсе — измерено 12.10, — значит режим
    там держится только на мета-теге, и правка разметки перевернёт его без
    всякого nginx. Одно общее поле скрыло бы эту разницу.
    """
    состояние = {"проба.test": dict(ОТКРЫТ, x_robots_tag="")}
    _стенд(monkeypatch, состояние)
    сн.главное(["--snapshot", "--store", str(tmp_path)])
    capsys.readouterr()

    состояние["проба.test"] = dict(ОТКРЫТ, x_robots_tag="",
                                   meta_robots="noindex")
    сн.главное(["--compare", "--store", str(tmp_path)])
    вывод = capsys.readouterr().out
    assert "meta_robots" in вывод
    assert "x_robots_tag" not in вывод.split("ИЗМЕНИЛОСЬ")[1]


def test_недоступный_домен_сохранением_не_считается(monkeypatch, tmp_path,
                                                     capsys):
    """Отказ связи — факт о замере, а не о витрине.

    Склеить его с «режим сохранён» значило бы подтвердить то, чего не видели.
    """
    состояние = {"проба.test": dict(ОТКРЫТ)}
    _стенд(monkeypatch, состояние)
    сн.главное(["--snapshot", "--store", str(tmp_path)])
    capsys.readouterr()

    состояние["проба.test"] = {"ошибка": "TimeoutError: read timed out"}
    код = сн.главное(["--compare", "--store", str(tmp_path)])
    вывод = capsys.readouterr()
    assert код == 2, вывод.out
    assert "НЕ ИЗМЕРЕНО" in вывод.out
    assert "режим не изменился" not in вывод.out
    assert "НЕ утверждается" in вывод.err


def test_без_снимка_сверка_отказывает(monkeypatch, tmp_path, capsys):
    _стенд(monkeypatch, {"проба.test": dict(ОТКРЫТ)})
    код = сн.главное(["--compare", "--store", str(tmp_path)])
    вывод = capsys.readouterr()
    assert код == 2
    assert "сверять не с чем" in вывод.err
    assert "чего мы не знаем" in вывод.err


def test_снимок_с_недоступным_доменом_честен(monkeypatch, tmp_path, capsys):
    """Снимок, в котором домен не снят, не должен выглядеть полным."""
    _стенд(monkeypatch, {"проба.test": {"ошибка": "URLError: нет связи"}})
    код = сн.главное(["--snapshot", "--store", str(tmp_path)])
    вывод = capsys.readouterr().out
    assert код == 2, вывод
    assert "не снято 1" in вывод
    assert "НЕ ИЗМЕРЕНО" in вывод


def test_новый_домен_изменением_режима_не_считается(monkeypatch, tmp_path,
                                                     capsys):
    """Домен, которого в снимке не было, — не «режим сломан»."""
    состояние = {"проба.test": dict(ОТКРЫТ)}
    _стенд(monkeypatch, состояние)
    сн.главное(["--snapshot", "--store", str(tmp_path)])
    capsys.readouterr()

    состояние["новый.test"] = dict(ОТКРЫТ)
    _стенд(monkeypatch, состояние, домены=("проба.test", "новый.test"))
    код = сн.главное(["--compare", "--store", str(tmp_path)])
    вывод = capsys.readouterr().out
    assert код == 0, вывод
    assert "новый домен" in вывод


def test_нужен_ровно_один_режим(capsys):
    assert сн.главное([]) == 2
    assert "ровно один" in capsys.readouterr().err


def test_живой_снимок_существует():
    """Снимок до операций владельца должен лежать в репозитории."""
    файл = сн.СНИМКИ / "latest.json"
    if not файл.is_file():
        import pytest
        pytest.skip("живой снимок ещё не снят")
    д = json.loads(файл.read_text(encoding="utf-8"))
    assert д, "снимок пуст"
    закрытые = sorted(
        домен for домен, з in д.items()
        if "noindex" in (з.get("x_robots_tag", "")
                         + " " + з.get("meta_robots", "")).lower())
    assert not закрытые, (
        f"в снимке есть закрытые от обхода домены: {закрытые}. "
        "Снимок снят ДО операций владельца, и закрытый домен в нём означал "
        "бы, что режим уже потерян.")
