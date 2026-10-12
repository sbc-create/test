"""Почему нет жанров: три разных случая, которые нельзя смешивать.

Повод. SEO-сессия сообщила: у новых записей пустые жанры — «правка у
производителя снимка». Измерение показало, что производитель тут не при чём:

* 2 277 записей ни разу не спрашивали у detail API (файла в кэше нет) — это
  незакрытое покрытие, и закрывает его добор;
* 17 записей спрашивали, и источник жанров НЕ ОТДАЛ — добор не поможет, а
  выдумывать жанры запрещено;
* третий случай — жанры в кэше есть, а на витрине нет — был бы потерей при
  сборке, и его надо видеть отдельно. На 11.10 таких ноль.

Проверка качества, которая считает все три случая одним, будет падать каждый
день после каждой партии новых записей и ничего этим не сообщать. Поэтому
различение измеряется, а не описывается словами.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
СЦЕНАРИЙ = КОРЕНЬ / "automation" / "local" / "genre-coverage-audit.py"


def _модуль():
    спец = importlib.util.spec_from_file_location("genre_coverage_audit", СЦЕНАРИЙ)
    м = importlib.util.module_from_spec(спец)
    sys.modules["genre_coverage_audit"] = м
    спец.loader.exec_module(м)
    return м


@pytest.fixture()
def стенд(tmp_path):
    м = _модуль()
    кэш = tmp_path / "detail-cache"
    кэш.mkdir()
    м.КЭШ = кэш
    подробности = {
        # с жанрами — в счёт не идёт
        "с-жанрами": {"id": "id-1", "genres": ["комедия"]},
        # не спрашивали: файла в кэше нет
        "не-спрошен": {"id": "id-2", "genres": []},
        # спрашивали, источник жанров не отдал
        "пусто-у-источника": {"id": "id-3", "genres": None},
        # жанры в кэше есть, а на витрине нет — потеря при сборке
        "расхождение": {"id": "id-4", "genres": []},
    }
    (кэш / "id-3.json").write_text(
        json.dumps({"detail": {"name": "Без жанров", "genres": []}}),
        encoding="utf-8")
    (кэш / "id-4.json").write_text(
        json.dumps({"detail": {"name": "С жанрами", "genres": ["драма"]}}),
        encoding="utf-8")
    return м, подробности


def test_три_случая_различаются(стенд):
    м, подробности = стенд
    итог = м.разобрать(подробности)
    assert итог["всего"] == 4
    assert итог["без_жанров"] == 3
    assert итог["не_спрошены"] == ["не-спрошен"]
    assert итог["пусто_у_источника"] == ["пусто-у-источника"]
    assert итог["расхождение_кэш_витрина"] == ["расхождение"]


def test_запись_с_жанрами_не_попадает_в_счёт(стенд):
    м, подробности = стенд
    итог = м.разобрать(подробности)
    for ключ in ("не_спрошены", "пусто_у_источника", "расхождение_кэш_витрина"):
        assert "с-жанрами" not in итог[ключ]


def test_пустой_список_и_None_считаются_одинаково(стенд):
    """`genres: []` и `genres: None` — одно и то же отсутствие."""
    м, _ = стенд
    итог = м.разобрать({"пусто": {"id": "нет", "genres": []},
                        "нет_поля": {"id": "нет2"}})
    assert итог["без_жанров"] == 2
    assert sorted(итог["не_спрошены"]) == ["нет_поля", "пусто"]


def test_нечитаемый_кэш_не_путается_с_отсутствием(стенд):
    м, подробности = стенд
    (м.КЭШ / "id-5.json").write_text("{битый json", encoding="utf-8")
    итог = м.разобрать({"битый": {"id": "id-5", "genres": []}})
    assert итог["не_спрошены"] == [], "битый файл — это не «не спрашивали»"
    assert итог["расхождение_кэш_витрина"] == ["битый"]


def test_расхождение_даёт_ненулевой_код(стенд, capsys, monkeypatch, tmp_path):
    """Потеря при сборке обязана быть видна кодом выхода, а не только текстом."""
    м, подробности = стенд
    файл = tmp_path / "details.json"
    файл.write_text(json.dumps({"details": подробности}), encoding="utf-8")
    monkeypatch.setitem(м.ВИТРИНЫ, "animedia-01", файл)
    m_отчёт = tmp_path / "нет-отчёта.json"
    m_отчёт.unlink(missing_ok=True)
    м.ОТЧЁТ_ДОБОРА = m_отчёт
    код = м.главное(["--site", "animedia-01"])
    вывод = capsys.readouterr().out
    assert код == 1, вывод
    assert "потеря при сборке" in вывод


def test_без_расхождений_код_ноль(стенд, capsys, monkeypatch, tmp_path):
    м, подробности = стенд
    подробности.pop("расхождение")
    файл = tmp_path / "details.json"
    файл.write_text(json.dumps({"details": подробности}), encoding="utf-8")
    monkeypatch.setitem(м.ВИТРИНЫ, "animedia-01", файл)
    м.ОТЧЁТ_ДОБОРА = tmp_path / "нет.json"
    assert м.главное(["--site", "animedia-01"]) == 0
    вывод = capsys.readouterr().out
    assert "не спрошены у источника:      1" in вывод
    assert "источник жанров не отдал:     1" in вывод


def test_срок_закрытия_покрытия_считается_из_отчёта(стенд, capsys, monkeypatch,
                                                    tmp_path):
    """Вместо «когда-нибудь доберётся» — число суток из бюджета прогона.

    Отчёт описывает ТОТ ЖЕ каталог, что и витрина: `titles` совпадает с числом
    записей стенда. Это условие в стенде раньше не соблюдалось, и тест
    проходил на несогласованном мире — отчёт обходил 62652 записи при одной
    записи у витрины.
    """
    м, подробности = стенд
    файл = tmp_path / "details.json"
    файл.write_text(json.dumps({"details": {"с-жанрами": подробности["с-жанрами"]}}),
                    encoding="utf-8")
    monkeypatch.setitem(м.ВИТРИНЫ, "animedia-01", файл)
    отчёт = tmp_path / "detail-backfill-report.json"
    отчёт.write_text(json.dumps({
        "budget": 500, "requests_made": 2700, "finished_at": "2026-10-11T03:53:21Z",
        "before": {"titles": 1, "cached": 0},
        "after": {"titles": 1, "cached": 0}}), encoding="utf-8")
    м.ОТЧЁТ_ДОБОРА = отчёт
    assert м.главное(["--site", "animedia-01"]) == 0
    вывод = capsys.readouterr().out
    assert "НЕ в кэше 1" in вывод
    assert "~1 сут" in вывод


def test_чужой_отчёт_добора_не_выдаётся_за_план_этой_витрины(
        стенд, capsys, monkeypatch, tmp_path):
    """Отчёт про другой каталог не даёт витрине срока закрытия.

    Измерено 12.10: у animedia-01 8552 записи, отчёт добора обходит 62652, и
    инструмент печатал её «~5 сут» как свой. Это приписывание чужого плана
    работ, и читается оно как обещание.
    """
    м, подробности = стенд
    файл = tmp_path / "details.json"
    файл.write_text(json.dumps({"details": {"с-жанрами": подробности["с-жанрами"]}}),
                    encoding="utf-8")
    monkeypatch.setitem(м.ВИТРИНЫ, "animedia-01", файл)
    отчёт = tmp_path / "detail-backfill-report.json"
    отчёт.write_text(json.dumps({
        "budget": 500, "requests_made": 2700, "finished_at": "2026-10-11T03:53:21Z",
        "before": {"titles": 62652, "cached": 59875},
        "after": {"titles": 62652, "cached": 60375}}), encoding="utf-8")
    м.ОТЧЁТ_ДОБОРА = отчёт
    assert м.главное(["--site", "animedia-01"]) == 0
    вывод = capsys.readouterr().out
    assert "ДРУГОЙ каталог" in вывод
    assert "сут" not in вывод.split("ДРУГОЙ каталог")[0].split("в кэше")[-1]


def test_пустой_источник_назван_незакрываемым(стенд, capsys, monkeypatch,
                                              tmp_path):
    """17 записей lords-02 добором не закроются: источник для них пуст.

    Смешивать их с «не спрошены» нельзя: первое закрывается ожиданием,
    второе — никогда, и решение по ним принимает человек.
    """
    м, подробности = стенд
    файл = tmp_path / "details.json"
    файл.write_text(json.dumps({"details": {
        "пусто-у-источника": подробности["пусто-у-источника"]}}),
        encoding="utf-8")
    monkeypatch.setitem(м.ВИТРИНЫ, "lords-02", файл)
    отчёт = tmp_path / "detail-backfill-report.json"
    отчёт.write_text(json.dumps({
        "budget": 500, "requests_made": 2700, "finished_at": "2026-10-11T03:53:21Z",
        "before": {"titles": 1, "cached": 1},
        "after": {"titles": 1, "cached": 1}}), encoding="utf-8")
    м.ОТЧЁТ_ДОБОРА = отчёт
    assert м.главное(["--site", "lords-02"]) == 0
    вывод = capsys.readouterr().out
    assert "НЕ закроются никогда" in вывод
