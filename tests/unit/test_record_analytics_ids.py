"""Перенос идентификаторов из отчётов служб в реестр: проверяется поведение.

Инструмент существует, чтобы двенадцать многозначных чисел не переносились
глазами. Значит, интересны случаи, в которых перенос руками и ошибается: нет
отчёта, отчёт испорчен, два проекта на один домен, повторный запуск, и — главное
— соблазн выдать «объект создан» за «работает на сайте».
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
ИНСТРУМЕНТ = КОРЕНЬ / "automation" / "host" / "record-analytics-ids.py"

СПИСОК_ПРОЕКТОВ = """Доступ к Topvisor: подтверждён
  проектов в аккаунте        : 2
    #777 a.test — A — первый
    #888 b.test — B — второй
"""


def загрузить(корень: Path):
    спец = importlib.util.spec_from_file_location("record_ids", ИНСТРУМЕНТ)
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    м.КОРЕНЬ = корень
    м.РЕЕСТР = корень / "config" / "site-cells.json"
    м.ОТЧЁТЫ_МЕТРИКИ = корень / "var" / "analytics"
    # Переопределяется ИМЕННО то имя, которое читает инструмент. Раньше здесь
    # стояло `ОТЧЁТ_TOPVISOR`, а инструмент давно читает кортеж `ОТЧЁТЫ_TOPVISOR`
    # (двух отчётов: до применения плана и после). Присваивание несуществующему
    # имени молча создавало новый атрибут, тест уходил на НАСТОЯЩИЕ файлы
    # репозитория и перестал проверять перенос Topvisor вовсе — падение пришло
    # только тогда, когда в настоящем отчёте не нашлось домена `a.test`.
    # Поэтому имя сверяется, а не присваивается наугад.
    assert hasattr(м, "ОТЧЁТЫ_TOPVISOR"), (
        "инструмент переименовал источник отчётов Topvisor — стенд его больше "
        "не подменяет и проверял бы настоящие файлы репозитория")
    м.ОТЧЁТЫ_TOPVISOR = (корень / "var" / "topvisor" / "check-after-connect.txt",
                         корень / "var" / "topvisor" / "check-latest.txt")
    return м


@pytest.fixture()
def стенд(tmp_path: Path) -> Path:
    (tmp_path / "config").mkdir()
    (tmp_path / "var" / "analytics").mkdir(parents=True)
    (tmp_path / "var" / "topvisor").mkdir(parents=True)
    (tmp_path / "config" / "site-cells.json").write_text(json.dumps({
        "schema_version": 1,
        "cells": [{"site_id": "a", "domain": "a.test"}, {"site_id": "b", "domain": "b.test"},
                  {"site_id": "c", "domain": "c.test"}],
    }, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "var" / "analytics" / "connect-a.test.json").write_text(json.dumps({
        "dry_run": False,
        "results": [{"domain": "a.test", "counter_id": 101, "api_site": "a.test",
                     "status": "Active"}],
    }, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "var" / "topvisor" / "check-latest.txt").write_text(
        СПИСОК_ПРОЕКТОВ, encoding="utf-8")
    return tmp_path


def ячейки(корень: Path) -> dict[str, dict]:
    данные = json.loads((корень / "config" / "site-cells.json").read_text(encoding="utf-8"))
    return {c["domain"]: c for c in данные["cells"]}


def test_без_apply_ничего_не_пишет(стенд):
    м = загрузить(стенд)
    assert м.main([]) == 0
    assert ячейки(стенд)["a.test"].get("analytics") is None


def test_apply_пишет_только_прочитанное(стенд):
    м = загрузить(стенд)
    assert м.main(["--apply"]) == 0
    блоки = ячейки(стенд)
    a = блоки["a.test"]["analytics"]
    assert a["metrika_counter_id"] == 101
    assert a["topvisor_project_id"] == 777
    # У b.test есть проект и нет отчёта Метрики — счётчик не выдумывается.
    b = блоки["b.test"]["analytics"]
    assert b["topvisor_project_id"] == 888
    assert "metrika_counter_id" not in b
    # У c.test нет ни того, ни другого — блок не появляется вовсе.
    assert блоки["c.test"].get("analytics") is None


def test_созданное_не_выдаётся_за_работающее(стенд):
    """Главное свойство: отчёт о создании объекта не доказывает работу на сайте."""
    м = загрузить(стенд)
    м.main(["--apply"])
    a = ячейки(стенд)["a.test"]["analytics"]
    assert a["metrika_verified_at"] is None, "отправка события не подтверждалась"
    assert a["metrika_data_seen_at"] is None, "визит в статистике не подтверждался"
    assert "не подтверждены" in a["note"]


def test_повторный_запуск_ничего_не_меняет(стенд, capsys):
    м = загрузить(стенд)
    м.main(["--apply"])
    до = (стенд / "config" / "site-cells.json").read_text(encoding="utf-8")
    м.main(["--apply"])
    после = (стенд / "config" / "site-cells.json").read_text(encoding="utf-8")
    assert до == после, "повторный перенос переписал реестр"
    assert "ячеек с изменениями: 0" in capsys.readouterr().out


def test_дубль_проекта_не_меняет_выбор(стенд):
    """Два проекта на домен — решение владельца; берём первый и не молчим."""
    (стенд / "var" / "topvisor" / "check-latest.txt").write_text(
        СПИСОК_ПРОЕКТОВ + "    #999 a.test — A — дубль\n", encoding="utf-8")
    м = загрузить(стенд)
    м.main(["--apply"])
    assert ячейки(стенд)["a.test"]["analytics"]["topvisor_project_id"] == 777


def test_испорченный_отчёт_не_ломает_перенос(стенд):
    (стенд / "var" / "analytics" / "connect-a.test.json").write_text(
        "не json", encoding="utf-8")
    м = загрузить(стенд)
    assert м.main(["--apply"]) == 0
    a = ячейки(стенд)["a.test"]["analytics"]
    assert "metrika_counter_id" not in a, "счётчик взят из нечитаемого отчёта"
    assert a["topvisor_project_id"] == 777


def test_отсутствие_домена_счётчика_названо(стенд):
    """Без api_site соответствие домену не проверено — и это сказано вслух."""
    (стенд / "var" / "analytics" / "connect-a.test.json").write_text(json.dumps({
        "results": [{"domain": "a.test", "counter_id": 101, "status": "Active"}],
    }, ensure_ascii=False), encoding="utf-8")
    м = загрузить(стенд)
    м.main(["--apply"])
    note = ячейки(стенд)["a.test"]["analytics"]["note"]
    assert "домен счётчика в отчёте отсутствует" in note
