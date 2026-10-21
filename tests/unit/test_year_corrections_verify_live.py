"""Проверка поправок года ДО и ПОСЛЕ выпуска: по снимку витрины и по странице.

Одна команда на оба состояния — до выпуска она обязана честно говорить «НЕ
применены», после выпуска «применены». Без этого «выпустили» и «работает»
сливаются в одно слово.

Отрицательные контроли, названные заранее:

* **признак на странице обязан РАЗЛИЧАТЬ.** Первая версия искала само число
  года в теле страницы и дала «год есть» у 13 записей из 15 ДО всякого
  выпуска: четырёхзначное число встречается на странице где угодно. Теперь
  проверяется ссылка фасета `/catalog/?year=N`, и обязательно ОТСУТСТВИЕ
  прежней — одного наличия новой мало;
* **контрольная запись с поправкой — отказ прохода целиком** (код 2): если
  правка задела запись, год которой сверка подтвердила верным, остальное уже
  неважно;
* **частичное применение успехом не считается** и печатается отдельной
  строкой: «применены ЧАСТИЧНО — разбирать поимённо».
"""
from __future__ import annotations

import importlib.util
import json
import pathlib

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_с = importlib.util.spec_from_file_location(
    "year_corrections_verify_live",
    КОРЕНЬ / "automation/local/year-corrections-verify-live.py")
ИНСТР = importlib.util.module_from_spec(_с)
_с.loader.exec_module(ИНСТР)

ИД = "01918cd7-61fd-75e3-8410-67fe2f763a0d"


def _поправки(tmp_path, **п) -> pathlib.Path:
    з = {
        "id": ИД, "slug_at_measure": "rukovodstvo-soten-demonov-4",
        "source_id": "57995",
        "source_url": "https://shikimori.io/animes/57995",
        "measured_at": "2026-10-20T13:39:06Z",
        "matching": "external_id_from_record+title_verified",
        "year_provider": 2020, "year_source": 2024,
    }
    з.update(п)
    ф = tmp_path / "corrections.json"
    ф.write_text(json.dumps({"schema_version": 1, "corrections": [з]}),
                 encoding="utf-8")
    return ф


def _витрина(tmp_path, запись: dict, *, контроль_год_источник: str = "provider"):
    каталог = tmp_path / "data"
    каталог.mkdir(exist_ok=True)
    подробности = {"rukovodstvo-soten-demonov-4": запись}
    for слаг in ИНСТР.КОНТРОЛЬ:
        подробности[слаг] = {"id": f"ид-{слаг}", "year": 2024, "type": "tv",
                             "year_source": контроль_год_источник}
    (каталог / "animedia-01-details.json").write_text(
        json.dumps({"catalog_built_at": "2026-10-21T03:15:26Z",
                    "details": подробности}), encoding="utf-8")
    return str(каталог)


def _подготовить(monkeypatch, tmp_path, запись, *, поправки=None,
                 контроль_год_источник="provider"):
    monkeypatch.setattr(ИНСТР, "ПОПРАВКИ", поправки or _поправки(tmp_path))
    monkeypatch.setitem(
        ИНСТР.ВИТРИНЫ, "animedia-01",
        (_витрина(tmp_path, запись,
                  контроль_год_источник=контроль_год_источник),
         "animedia.icu"))


# --- снимок витрины -------------------------------------------------------------

def test_до_выпуска_честно_не_применено(monkeypatch, tmp_path, capsys):
    _подготовить(monkeypatch, tmp_path,
                 {"id": ИД, "year": 2020, "type": "tv"})
    код = ИНСТР.главное(["--site", "animedia-01"])
    вывод = capsys.readouterr().out
    assert код == 1
    assert "НЕ ПРИМЕНЕНО" in вывод
    assert "поправки НЕ применены — это состояние ДО выпуска" in вывод


def test_после_выпуска_применено(monkeypatch, tmp_path, capsys):
    _подготовить(monkeypatch, tmp_path,
                 {"id": ИД, "year": 2024, "type": "tv",
                  "year_source": "https://shikimori.io/animes/57995 (2026-10-20)"})
    код = ИНСТР.главное(["--site", "animedia-01"])
    вывод = capsys.readouterr().out
    assert код == 0
    assert "все поправки применены" in вывод


def test_запись_без_id_в_снимке_называется(monkeypatch, tmp_path, capsys):
    _подготовить(monkeypatch, tmp_path, {"id": "другой", "year": 2020})
    ИНСТР.главное(["--site", "animedia-01"])
    assert "НЕ НАЙДЕНА" in capsys.readouterr().out


def test_поправка_вида_учитывается(monkeypatch, tmp_path, capsys):
    _подготовить(monkeypatch, tmp_path,
                 {"id": ИД, "year": 2024, "type": "tv", "year_source": "u"},
                 поправки=_поправки(tmp_path, year_source=None,
                                    year_provider=None,
                                    type_provider="tv", type_source="movie"))
    код = ИНСТР.главное(["--site", "animedia-01"])
    assert код == 1, capsys.readouterr().out


# --- отрицательный контроль -----------------------------------------------------

def test_поправка_на_контрольной_записи_это_отказ(monkeypatch, tmp_path, capsys):
    _подготовить(monkeypatch, tmp_path,
                 {"id": ИД, "year": 2024, "type": "tv", "year_source": "u"},
                 контроль_год_источник="https://shikimori.io/animes/1 (x)")
    код = ИНСТР.главное(["--site", "animedia-01"])
    вывод = capsys.readouterr().out
    assert код == 2
    assert "ПРОВАЛ: контрольной записи поставлена поправка" in вывод


# --- признак на странице --------------------------------------------------------

def test_прежняя_ссылка_года_перечёркивает_новую(monkeypatch, tmp_path):
    """Главный контроль: наличия новой ссылки МАЛО, пока есть прежняя."""
    _подготовить(monkeypatch, tmp_path,
                 {"id": ИД, "year": 2024, "type": "tv", "year_source": "u"})
    тело = '<a href="/catalog/?year=2024">2024</a><a href="/catalog/?year=2020">2020</a>'
    итог = ИНСТР.разобрать("animedia-01", сеть=True, загрузчик=lambda url: тело)
    (строка,) = итог["записи"]
    assert строка["ссылка_нового_года"] is True
    assert строка["ссылка_прежнего_года"] is True
    assert строка["страница"] == "НЕ ПРИМЕНЕНО"


def test_страница_ок_когда_прежней_ссылки_нет(monkeypatch, tmp_path):
    _подготовить(monkeypatch, tmp_path,
                 {"id": ИД, "year": 2024, "type": "tv", "year_source": "u"})
    тело = '<a href="/catalog/?year=2024">2024</a>'
    итог = ИНСТР.разобрать("animedia-01", сеть=True, загрузчик=lambda url: тело)
    assert итог["записи"][0]["страница"] == "ок"


def test_страница_не_измерена_когда_нет_ни_той_ни_другой(monkeypatch, tmp_path):
    _подготовить(monkeypatch, tmp_path,
                 {"id": ИД, "year": 2024, "type": "tv", "year_source": "u"})
    итог = ИНСТР.разобрать("animedia-01", сеть=True, загрузчик=lambda url: "<html>")
    assert итог["записи"][0]["страница"] == "не измерено"


def test_основание_признака_страницы_названо():
    текст = " ".join(
        pathlib.Path(ИНСТР.__file__).read_text(encoding="utf-8").split())
    assert "13 записей из 15" in текст
    assert "не отвечает вовсе" in текст


# --- пределы --------------------------------------------------------------------

def test_незнакомая_витрина_отвергается(capsys):
    assert ИНСТР.главное(["--site", "нет-такой"]) == 2
    assert "нет в перечне" in capsys.readouterr().out


def test_нет_снимка_это_не_измерено(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(ИНСТР, "ПОПРАВКИ", _поправки(tmp_path))
    monkeypatch.setitem(ИНСТР.ВИТРИНЫ, "animedia-01",
                        (str(tmp_path / "пусто"), "animedia.icu"))
    assert ИНСТР.главное(["--site", "animedia-01"]) == 2
    assert "НЕ ИЗМЕРЕНО" in capsys.readouterr().out
