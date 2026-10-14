"""Перезакрепление исходника ячейки: причина обязательна, прежняя сумма хранится.

Зачем инструмент и зачем проверка. `pins.lock.json` закрепляет заимствованные
исходники по sha256, и проверка выпуска `pins-match-sources` валит сборку при
расхождении — иначе закрепление было бы записью о намерении. Но расхождение
бывает РЕШЁННЫМ: партия K2 несёт исправления интерфейса, сделанные в ячейках,
потому что решение D212а оставило семейный рантайм на отдельный выпуск (тот же
файл исполняют 17 действующих витрин).

Измерено 2026-10-14: из-за расхождения каждая сборка восьми витрин падала с
12:10, и зелёного прогона CI у партии не было ни одного. Опасность правки
очевидна — переписать сумму молча значит снять проверку тем же движением,
которым она охраняется. Поэтому у инструмента три свойства, и они проверяются:

* причина обязательна и содержательна (короткая отметка не принимается);
* прежняя сумма сохраняется в `base_sha256`, а происхождение перестаёт
  называться `git`;
* новых записей в замок инструмент не добавляет — это другая операция.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
СЦЕНАРИЙ = КОРЕНЬ / "automation" / "local" / "relock-cell-source.py"
ПРИЧИНА = ("D212а: исправления интерфейса партии живут в ячейке, семейный "
           "рантайм обновляется отдельным выпуском")


def _модуль():
    спец = importlib.util.spec_from_file_location("relock_cell_source", СЦЕНАРИЙ)
    м = importlib.util.module_from_spec(спец)
    sys.modules[спец.name] = м
    спец.loader.exec_module(м)
    return м


def _ячейка(tmp_path: Path, *, закреплено: str | None, содержимое: bytes) -> Path:
    основа = tmp_path / "cells"
    ячейка = основа / "site-x"
    (ячейка / "src").mkdir(parents=True)
    (ячейка / "src" / "runtime.py").write_bytes(содержимое)
    замок = {"schema_version": 1, "site_id": "site-x",
             "files": {"runtime.py": {"bytes": 1, "verified_against": "git",
                                      "repo_path": "automation/host/runtime.py"}}}
    if закреплено:
        замок["files"]["runtime.py"]["sha256"] = закреплено
    (ячейка / "pins.lock.json").write_text(json.dumps(замок, ensure_ascii=False),
                                           encoding="utf-8")
    return основа


def test_замок_приводится_к_факту_и_помнит_прежнюю_сумму(tmp_path: Path):
    м = _модуль()
    основа = _ячейка(tmp_path, закреплено="a" * 64, содержимое=b"new code")
    отчёт = м.перезакрепить("site-x", "runtime.py", ПРИЧИНА, apply=True, основа=основа)
    assert отчёт["итог"].startswith("замок приведён к факту")
    запись = json.loads((основа / "site-x" / "pins.lock.json").read_text(
        encoding="utf-8"))["files"]["runtime.py"]
    assert запись["sha256"] == hashlib.sha256(b"new code").hexdigest()
    assert запись["base_sha256"] == "a" * 64, "прежняя сумма потеряна"
    assert запись["verified_against"] != "git", (
        "происхождение по-прежнему называется git, хотя файл разошёлся с ним")
    assert запись["note"] == ПРИЧИНА
    assert запись["repo_path"] == "automation/host/runtime.py", "путь источника потерян"


def test_сухой_прогон_ничего_не_пишет(tmp_path: Path):
    м = _модуль()
    основа = _ячейка(tmp_path, закреплено="a" * 64, содержимое=b"new code")
    было = (основа / "site-x" / "pins.lock.json").read_text(encoding="utf-8")
    отчёт = м.перезакрепить("site-x", "runtime.py", ПРИЧИНА, apply=False, основа=основа)
    assert отчёт["итог"].startswith("сухой прогон")
    assert (основа / "site-x" / "pins.lock.json").read_text(encoding="utf-8") == было


def test_совпадающий_замок_не_переписывается(tmp_path: Path):
    """Идемпотентность: повторный запуск не плодит base_sha256 от самого себя."""
    м = _модуль()
    сумма = hashlib.sha256(b"same code").hexdigest()
    основа = _ячейка(tmp_path, закреплено=сумма, содержимое=b"same code")
    отчёт = м.перезакрепить("site-x", "runtime.py", ПРИЧИНА, apply=True, основа=основа)
    assert отчёт["итог"].startswith("менять нечего")
    запись = json.loads((основа / "site-x" / "pins.lock.json").read_text(
        encoding="utf-8"))["files"]["runtime.py"]
    assert "base_sha256" not in запись


def test_незакреплённый_файл_не_добавляется(tmp_path: Path):
    """Добавить в замок новую запись — другая операция, и инструмент это говорит.

    Файл в стенде существует намеренно: иначе отказ пришёл бы раньше, от
    проверки наличия, и проверка утверждала бы про замок, не дойдя до него.
    """
    м = _модуль()
    основа = _ячейка(tmp_path, закреплено="a" * 64, содержимое=b"code")
    (основа / "site-x" / "src" / "storonniy.py").write_bytes(b"other code")
    with pytest.raises(м.Отказ, match="в замке не закреплён"):
        м.перезакрепить("site-x", "storonniy.py", ПРИЧИНА, apply=True, основа=основа)


def test_отсутствующий_файл_называется_отдельной_причиной(tmp_path: Path):
    """«Нет файла» и «нет записи в замке» — разные отказы, и путать их нельзя."""
    м = _модуль()
    основа = _ячейка(tmp_path, закреплено="a" * 64, содержимое=b"code")
    with pytest.raises(м.Отказ, match="перезакреплять нечего"):
        м.перезакрепить("site-x", "net-takogo.py", ПРИЧИНА, apply=True, основа=основа)


def test_короткая_причина_не_принимается():
    """Отметка вместо причины — отказ: через месяц её нельзя будет прочитать."""
    г = subprocess.run([sys.executable, str(СЦЕНАРИЙ), "--site", "site-x",
                        "--file", "runtime.py", "--reason", "надо", "--apply"],
                       capture_output=True, text=True, timeout=120, cwd=str(КОРЕНЬ))
    assert г.returncode == 2, г.stdout + г.stderr
    assert "причина" in (г.stderr or "")


def test_без_причины_инструмент_не_запускается():
    г = subprocess.run([sys.executable, str(СЦЕНАРИЙ), "--site", "site-x",
                        "--file", "runtime.py", "--apply"],
                       capture_output=True, text=True, timeout=120, cwd=str(КОРЕНЬ))
    assert г.returncode != 0
    assert "--reason" in (г.stderr or "")
