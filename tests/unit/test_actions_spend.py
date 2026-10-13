"""Инструмент расхода Actions: считает минуты и различает исходы.

Проверяется не «считает правильно», а четыре вида подмены, каждая из которых
уже случилась 13.10 при первом замере:

* **свойство выбранного пути за действительность** — перечень репозиториев
  брался из `users/<логин>/repos`, который отдаёт только ОТКРЫТЫЕ. Из
  двадцати шести нашёлся один, и «расход 0 минут» был свойством запроса;
* **ноль за неизмеренное** — минуты брались из поля `billable`, а этому
  токену оно отдаёт 0 даже у прогона, шедшего четыре с половиной минуты
  (38326615302). Теперь минуты реконструируются по заданиям, а недоступные
  задания дают None, а не ноль;
* **бесплатные минуты за расход квоты** — открытые репозитории квоту не
  тратят, и смешивать их с закрытыми нельзя: фабрика лежит в открытом
  `sbc-create/test`, её 276 минут за 48 ч в бюджет не входят;
* **выдуманный бюджет** — размер бюджета API не отдаёт (нужно право `user`),
  и подставлять число тарифа за владельца нельзя: без `--budget` норма и
  прогноз не печатаются, а печатается названный предел.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
ИСТОЧНИК = КОРЕНЬ / "automation" / "local" / "actions-spend.py"


def _модуль():
    спец = importlib.util.spec_from_file_location("actions_spend", ИСТОЧНИК)
    м = importlib.util.module_from_spec(спец)
    sys.modules["actions_spend"] = м
    спец.loader.exec_module(м)
    return м


@pytest.fixture(scope="module")
def рс():
    return _модуль()


def _задание(начало: str, конец: str, раннер: str | None = "GitHub Actions 1") -> dict:
    return {"started_at": начало, "completed_at": конец, "runner_name": раннер}


def test_минуты_округляются_вверх_по_каждому_заданию(рс, monkeypatch):
    """GitHub списывает за каждое задание, округляя вверх до минуты."""
    monkeypatch.setattr(рс, "api", lambda п, предел=180: {"jobs": [
        _задание("2026-10-13T00:00:00Z", "2026-10-13T00:00:10Z"),   # 10 с → 1
        _задание("2026-10-13T00:00:00Z", "2026-10-13T00:04:04Z"),   # 244 с → 5
    ]})
    минут, посчитано = рс.минуты("репо", 1)
    assert минут == 6, "округление вверх по заданиям не выполнено"
    assert посчитано == 2


def test_задание_без_раннера_не_стоит_ничего(рс, monkeypatch):
    """Пропущенное по `if` задание раннера не занимало."""
    monkeypatch.setattr(рс, "api", lambda п, предел=180: {"jobs": [
        _задание("2026-10-13T00:00:00Z", "2026-10-13T00:00:00Z", раннер=None),
        _задание("2026-10-13T00:00:00Z", "2026-10-13T00:02:00Z"),
    ]})
    минут, посчитано = рс.минуты("репо", 1)
    assert минут == 2
    assert посчитано == 1


def test_недоступные_задания_это_не_ноль(рс, monkeypatch):
    """Главная подмена: «не измерено» не должно выглядеть как «ничего»."""
    monkeypatch.setattr(рс, "api", lambda п, предел=180: None)
    минут, посчитано = рс.минуты("репо", 1)
    assert минут is None, "недоступные задания превратились в ноль минут"
    assert посчитано == 0


def test_перечень_репозиториев_включает_закрытые(рс, monkeypatch):
    """Прежний путь отдавал только открытые, и расход выглядел нулевым."""
    вызовы = []

    def поддельный(путь, предел=180):
        вызовы.append(путь)
        if путь.startswith("user/repos"):
            return [{"name": "закрытый", "private": True},
                    {"name": "открытый", "private": False}]
        return None

    monkeypatch.setattr(рс, "api", поддельный)
    итог = рс.репозитории_с_закрытостью()
    assert ("закрытый", True) in итог
    assert ("открытый", False) in итог
    assert any(в.startswith("user/repos") for в in вызовы), (
        "перечень должен идти через /user/repos: users/<логин>/repos закрытые "
        "репозитории не отдаёт")


def test_только_текст_не_считает_код_документацией(рс):
    assert рс.только_текст(["docs/a.md", "README.md"]) is True
    assert рс.только_текст(["docs/a.md", "factory/code.py"]) is False
    assert рс.только_текст(["adr/0001.md"]) is True
    assert рс.только_текст([]) is False, "пустой перечень не документация"


def test_без_бюджета_норма_и_прогноз_не_печатаются(рс, monkeypatch, capsys):
    """Выдуманный бюджет хуже отсутствующего: печатается предел."""
    monkeypatch.setattr(рс, "гх", lambda *а, предел=60: (0, ""))
    monkeypatch.setattr(рс, "репозитории_с_закрытостью",
                        lambda: [("репо", True)])
    monkeypatch.setattr(рс, "прогоны", lambda р, с: [])
    код = рс.главная(["--hours", "48"])
    вывод = capsys.readouterr().out
    assert код == 2 or "ПРЕДЕЛ" in вывод
    assert "мин/месяц" not in вывод, "норма посчитана без бюджета"


def test_открытые_и_закрытые_считаются_раздельно(рс, monkeypatch, capsys):
    """Минуты открытого репозитория квоту не тратят."""
    сейчас = dt.datetime.now(dt.timezone.utc)
    создан = (сейчас - dt.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    прогон = {"id": 1, "name": "CI", "event": "push", "status": "completed",
              "conclusion": "success", "head_sha": "a" * 40,
              "head_branch": "main", "created_at": создан}

    monkeypatch.setattr(рс, "гх", lambda *а, предел=60: (0, ""))
    monkeypatch.setattr(рс, "репозитории_с_закрытостью",
                        lambda: [("закрытый", True), ("открытый", False)])
    monkeypatch.setattr(рс, "прогоны", lambda р, с: [dict(прогон)])
    monkeypatch.setattr(рс, "минуты", lambda р, и: (10, 1))
    monkeypatch.setattr(рс, "_конец_заданий", lambda р, и: None)
    код = рс.главная(["--hours", "48", "--no-files", "--budget", "2000"])
    вывод = capsys.readouterr().out
    assert код == 0
    assert "открытые (бесплатно, квоту не тратят)" in вывод
    # Квота = только закрытый репозиторий: 10 мин за 48 ч = 5 мин/сутки.
    assert "10 мин за окно" in вывод, вывод
    assert "66.7 мин/сутки" in вывод, "норма из бюджета не посчитана"


def test_вытесненным_считается_только_перекрытый_прогон(рс, monkeypatch, capsys):
    """Если прежний успел закончиться, отмена ничего не сэкономила бы."""
    сейчас = dt.datetime.now(dt.timezone.utc)

    def создан(минут_назад: int) -> str:
        return (сейчас - dt.timedelta(minutes=минут_назад)).strftime(
            "%Y-%m-%dT%H:%M:%SZ")

    прогоны = [
        {"id": 1, "name": "CI", "event": "push", "status": "completed",
         "conclusion": "success", "head_sha": "a" * 40, "head_branch": "раб",
         "created_at": создан(60)},
        {"id": 2, "name": "CI", "event": "push", "status": "completed",
         "conclusion": "success", "head_sha": "b" * 40, "head_branch": "раб",
         "created_at": создан(50)},
    ]
    # Первый закончился ЧЕРЕЗ 20 минут, то есть позже создания второго.
    концы = {1: сейчас - dt.timedelta(minutes=40), 2: None}
    monkeypatch.setattr(рс, "гх", lambda *а, предел=60: (0, ""))
    monkeypatch.setattr(рс, "репозитории_с_закрытостью", lambda: [("р", True)])
    monkeypatch.setattr(рс, "прогоны", lambda р, с: [dict(п) for п in прогоны])
    monkeypatch.setattr(рс, "минуты", lambda р, и: (7, 1))
    monkeypatch.setattr(рс, "_конец_заданий", lambda р, и: концы[и])
    рс.главная(["--hours", "48", "--no-files"])
    вывод = capsys.readouterr().out
    assert "ВЫТЕСНЕННЫЕ ПРОГОНЫ" in вывод
    assert "прогонов 1" in вывод, "вытесненным должен быть ровно первый"


def test_успевший_закончиться_прогон_вытесненным_не_считается(рс, monkeypatch, capsys):
    сейчас = dt.datetime.now(dt.timezone.utc)

    def создан(минут_назад: int) -> str:
        return (сейчас - dt.timedelta(minutes=минут_назад)).strftime(
            "%Y-%m-%dT%H:%M:%SZ")

    прогоны = [
        {"id": 1, "name": "CI", "event": "push", "status": "completed",
         "conclusion": "success", "head_sha": "a" * 40, "head_branch": "раб",
         "created_at": создан(60)},
        {"id": 2, "name": "CI", "event": "push", "status": "completed",
         "conclusion": "success", "head_sha": "b" * 40, "head_branch": "раб",
         "created_at": создан(50)},
    ]
    # Первый закончился ДО создания второго: отменять было нечего.
    концы = {1: сейчас - dt.timedelta(minutes=55), 2: None}
    monkeypatch.setattr(рс, "гх", lambda *а, предел=60: (0, ""))
    monkeypatch.setattr(рс, "репозитории_с_закрытостью", lambda: [("р", True)])
    monkeypatch.setattr(рс, "прогоны", lambda р, с: [dict(п) for п in прогоны])
    monkeypatch.setattr(рс, "минуты", lambda р, и: (7, 1))
    monkeypatch.setattr(рс, "_конец_заданий", lambda р, и: концы[и])
    рс.главная(["--hours", "48", "--no-files"])
    вывод = capsys.readouterr().out
    assert "прогонов 0, минут 0" in вывод, (
        "прогон, успевший закончиться, записан в вытесненные — экономия была "
        "бы завышена")


def test_json_вывод_разбирается(рс, monkeypatch, capsys):
    monkeypatch.setattr(рс, "гх", lambda *а, предел=60: (0, ""))
    monkeypatch.setattr(рс, "репозитории_с_закрытостью", lambda: [("р", True)])
    сейчас = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=5)
    monkeypatch.setattr(рс, "прогоны", lambda р, с: [{
        "id": 1, "name": "CI", "event": "push", "status": "completed",
        "conclusion": "success", "head_sha": "a" * 40, "head_branch": "main",
        "created_at": сейчас.strftime("%Y-%m-%dT%H:%M:%SZ")}])
    monkeypatch.setattr(рс, "минуты", lambda р, и: (3, 1))
    monkeypatch.setattr(рс, "_конец_заданий", lambda р, и: None)
    рс.главная(["--hours", "48", "--no-files", "--json"])
    d = json.loads(capsys.readouterr().out)
    assert d["прогонов"] == 1
    assert d["минут_всего"] == 3
    assert "вытесненные_прогоны" in d
    assert "квота" in d and d["квота"]["предел"]
