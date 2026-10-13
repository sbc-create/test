"""Карта имён ячейки: `--check` обязан падать на расхождении.

Зачем карта существует. У ячейки пять имён, и у 20 из 21 каталог рабочей копии,
учётная запись и суффикс unit совпадают. Ровно поэтому единственное исключение
(`lords-03`: каталог `1lordserials1-online`, учётная запись
`site-1lordserials1-online`) — ловушка: соглашение, верное в 20 случаях из 21,
не выглядит имеющим исключение. Измерено 13.10: вывод с именем учётной записи
увёл поиск рабочей копии в несуществующий каталог.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
ИНСТРУМЕНТ = КОРЕНЬ / "automation" / "local" / "cell-name-map.py"


def _паспорт(путь: Path, *, учётка: str) -> None:
    путь.write_text(json.dumps({"version": 1, "cells": [{
        "site_id": "проба-01",
        "domain": "проба.localhost.test",
        "status": "live",
        "repo": {"kind": "remote", "path": "var/site-repos/проба-копия"},
        "runtime": {"unit": "nova-проба-копия.service", "account": учётка,
                    "app_dir": "/srv/проба/app", "port": 9999},
    }]}, ensure_ascii=False), encoding="utf-8")


def _прогон(tmp_path: Path, *, учётка: str, check: bool):
    паспорт = tmp_path / "site-cells.json"
    _паспорт(паспорт, учётка=учётка)
    арг = [sys.executable, str(ИНСТРУМЕНТ), "--registry", str(паспорт)]
    if check:
        арг.append("--check")
    return subprocess.run(арг, capture_output=True, text=True, timeout=120,
                          cwd=str(КОРЕНЬ))


def test_расхождение_имён_валит_check(tmp_path):
    г = _прогон(tmp_path, учётка="site-проба-копия", check=True)
    assert г.returncode == 1, г.stdout + г.stderr
    assert "ИМЕНА РАЗНЫЕ" in г.stdout, г.stdout
    # Называются ОБА имени: без них расхождение нечем проверить.
    assert "проба-копия" in г.stdout and "site-проба-копия" in г.stdout


def test_согласованные_имена_не_валят_check(tmp_path):
    """Обратная сторона: иначе `--check` падал бы на любом паспорте."""
    г = _прогон(tmp_path, учётка="проба-копия", check=True)
    assert г.returncode == 0, г.stdout + г.stderr
    assert "имена ячеек согласованы между собой" in г.stdout, г.stdout


def test_без_флага_check_расхождение_не_валит_прогон(tmp_path):
    """Карта — прежде всего справка; код возврата меняет только `--check`."""
    г = _прогон(tmp_path, учётка="site-проба-копия", check=False)
    assert г.returncode == 0, г.stdout + г.stderr
    assert "ИМЕНА РАЗНЫЕ" in г.stdout


def test_имена_не_приводятся_к_одному_виду(tmp_path):
    """Инструмент только читает: переименование — вход владельца."""
    г = _прогон(tmp_path, учётка="site-проба-копия", check=False)
    assert "НЕ приводятся к одному виду" in г.stdout, г.stdout
    # Паспорт не тронут.
    d = json.loads((tmp_path / "site-cells.json").read_text(encoding="utf-8"))
    assert d["cells"][0]["runtime"]["account"] == "site-проба-копия"


def test_паспорта_нет_это_не_измерено(tmp_path):
    г = subprocess.run(
        [sys.executable, str(ИНСТРУМЕНТ), "--registry", str(tmp_path / "нет.json")],
        capture_output=True, text=True, timeout=120, cwd=str(КОРЕНЬ))
    assert г.returncode == 2, г.stdout + г.stderr
    assert "НЕ ИЗМЕРЕНО" in г.stdout, г.stdout
