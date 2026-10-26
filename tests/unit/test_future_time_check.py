"""Отметка времени позже текущей — ошибка записи (26.10.2026: пять таких за вечер)."""
from __future__ import annotations

import datetime as dt
import importlib.util
from pathlib import Path

ПУТЬ = Path(__file__).resolve().parents[2] / "automation" / "local" / "future-time-check.py"
спец = importlib.util.spec_from_file_location("future_time_check", ПУТЬ)
м = importlib.util.module_from_spec(спец)
спец.loader.exec_module(м)

СЕЙЧАС = dt.datetime(2026, 10, 26, 21, 10, 36, tzinfo=dt.timezone.utc)


def test_отметка_из_будущего_найдена():
    найдено = м.из_будущего(["Проверка 26.10 ~21:12Z: 404"], СЕЙЧАС)
    assert [о for о, _ in найдено] == ["~21:12Z"]


def test_измеренные_и_прошлые_отметки_не_ошибка():
    строки = ["окно 21:09–21:10Z", "сборка 17:53Z", "публикация 21:10:36Z", "в пределах минуты 21:11Z"]
    assert м.из_будущего(строки, СЕЙЧАС) == []


def test_время_без_z_и_годы_не_разбираются():
    assert м.из_будущего(["в 22:00 МСК", "2026-10-26", "счёт 23:59"], СЕЙЧАС) == []
