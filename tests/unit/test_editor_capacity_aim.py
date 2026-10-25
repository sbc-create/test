"""Куда нацелена ёмкость редактора: мера печатает выбор, а не судит его.

Измерено 25.10: 96 % заходов редактора за 7 суток пришлись на работы, у
которых у источника НЕТ описания, тогда как их доля в каталоге 26 %. Это не
ошибка отбора — такие страницы показывают только шаблон фактов, и механизм в
`seo_operator/regular.py` выбирает их намеренно. Но источника там нет, поэтому
65 % всех заходов кончились отказом «нет источника», а 5 067 работ с готовой
завязкой не берутся вовсе.

Мера существует ровно для того, чтобы этот выбор перестал быть молчаливым.
Поэтому здесь закреплено: она НЕ называет ни одну цель правильной, считает
доли от числа ЗАХОДОВ (а не от числа отказов) и честно говорит «не измерено»,
когда заходов не было.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ПУТЬ = (Path(__file__).resolve().parents[2] / "automation" / "local"
        / "editor-capacity-aim.py")


def _модуль():
    спец = importlib.util.spec_from_file_location("editor_capacity_aim", ПУТЬ)
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


МОД = _модуль()


def _снимок(tmp_path, записи):
    к = tmp_path / "снимки"
    к.mkdir(exist_ok=True)
    (к / "animedia-01-details.json").write_text(
        json.dumps({"details": записи}, ensure_ascii=False), encoding="utf-8")
    return к


def test_длины_описаний_читаются_из_снимка(tmp_path):
    к = _снимок(tmp_path, {"a": {"description": "x" * 250},
                           "b": {"description": ""},
                           "c": {"description": "y" * 50}})
    длины = МОД.описания_каталога(к / "animedia-01-details.json")
    assert длины == {"a": 250, "b": 0, "c": 50}


def test_порог_завязки_назван_числом():
    """Порог — свойство меры, а не догадка в голове: он объявлен."""
    assert МОД.ПОРОГ_ЗАВЯЗКИ == 200


def test_доли_считаются_от_заходов_а_не_от_отказов(tmp_path, monkeypatch, capsys):
    к = _снимок(tmp_path, {"пусто1": {"description": ""},
                           "пусто2": {"description": ""},
                           "полная": {"description": "z" * 300}})
    monkeypatch.setattr(МОД, "слаги_наложения", lambda д: set())
    monkeypatch.setattr(МОД, "исходы_заданий", lambda в, д: [
        ("animedia.icu", "пусто1", "SOURCES_MISSING"),
        ("animedia.icu", "пусто2", "TEXT_WRITTEN"),
        ("animedia.icu", "полная", "TEXT_WRITTEN"),
    ])
    код = МОД.главное(["--family", "animedia", "--snapshots", str(к)])
    вывод = capsys.readouterr().out
    assert код == 0
    # два захода из трёх по пустым работам
    assert "по работам «пусто»: 2 (67%)" in вывод
    # отказ один, и он считается от числа ЗАХОДОВ, а не от числа отказов
    assert "отказов «нет источника» по пустым работам: 1 (33% всех заходов)" in вывод


def test_мера_не_называет_цель_правильной(tmp_path, monkeypatch, capsys):
    к = _снимок(tmp_path, {"пусто": {"description": ""}})
    monkeypatch.setattr(МОД, "слаги_наложения", lambda д: set())
    monkeypatch.setattr(МОД, "исходы_заданий", lambda в, д: [
        ("animedia.icu", "пусто", "SOURCES_MISSING")])
    МОД.главное(["--family", "animedia", "--snapshots", str(к)])
    вывод = capsys.readouterr().out
    assert "не ошибка отбора" in вывод
    assert "решение владельца" in вывод


def test_без_заходов_цель_не_измерена(tmp_path, monkeypatch, capsys):
    к = _снимок(tmp_path, {"a": {"description": "x" * 250}})
    monkeypatch.setattr(МОД, "слаги_наложения", lambda д: set())
    monkeypatch.setattr(МОД, "исходы_заданий", lambda в, д: [])
    код = МОД.главное(["--family", "animedia", "--snapshots", str(к)])
    assert код == 3
    assert "НЕ ИЗМЕРЕНА" in capsys.readouterr().out


def test_нет_снимка_это_не_измерено(tmp_path, capsys):
    код = МОД.главное(["--family", "animedia", "--snapshots", str(tmp_path / "нет")])
    assert код == 2
    assert "НЕ ИЗМЕРЕНО" in capsys.readouterr().err


def test_размещённое_вычитается_из_запаса(tmp_path, monkeypatch, capsys):
    к = _снимок(tmp_path, {"a": {"description": "x" * 300},
                           "b": {"description": "y" * 300}})
    monkeypatch.setattr(МОД, "слаги_наложения",
                        lambda д: {"a"} if д == "animedia.icu" else set())
    monkeypatch.setattr(МОД, "исходы_заданий", lambda в, д: [
        ("animedia.icu", "a", "TEXT_WRITTEN")])
    МОД.главное(["--family", "animedia", "--snapshots", str(к)])
    вывод = capsys.readouterr().out
    #: у .icu размещён один из двух, значит с завязкой без текста — один
    assert "animedia.icu" in вывод
    строка = [с for с in вывод.splitlines() if с.startswith("animedia.icu")][0]
    assert строка.split()[1] == "1" and строка.split()[2] == "1"
