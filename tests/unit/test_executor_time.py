"""REQ-EXEC-TIME: время работы исполнителя считается по журналам прогонов.

«Исполнитель простаивал» обычно выводят из промежутков между коммитами. Это не
доказательство: коммит появляется в конце работы, а не во время неё. Поэтому
инструмент считает по записям прогонов, где у каждого есть начало и конец, и
НЕ называет простоем остаток календарного времени — журнал не знает, была ли в
тот момент готовая задача.

Измерено 2026-10-18 за 14–18.10: 204 прогона, 16,2 ч занятости из 192 ч
календаря, вердикты VERIFIED 131 / INCOMPLETE 73, решений о выпуске 722, из
них 599 «ожидание» — и 545 из этих 599 приходятся на одну задачу T175.
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

ПУТЬ = (Path(__file__).resolve().parents[2] / "automation" / "local"
        / "executor-time.py")


def _модуль():
    имя = "executor_time"
    спец = importlib.util.spec_from_file_location(имя, ПУТЬ)
    м = importlib.util.module_from_spec(спец)
    sys.modules[имя] = м
    спец.loader.exec_module(м)
    return м


МОД = _модуль()


def _журналы(monkeypatch, tmp_path: Path, прогоны: list, выпуски: list) -> None:
    (tmp_path / "runs.jsonl").write_text(
        "\n".join(json.dumps(з, ensure_ascii=False) for з in прогоны) + "\n",
        encoding="utf-8")
    (tmp_path / "publish.jsonl").write_text(
        "\n".join(json.dumps(з, ensure_ascii=False) for з in выпуски) + "\n",
        encoding="utf-8")
    monkeypatch.setattr(МОД, "КОРЕНЬ", tmp_path)


def _прогон(monkeypatch, tmp_path, прогоны, выпуски, с="2026-10-14",
            по="2026-10-15") -> tuple[int, str]:
    _журналы(monkeypatch, tmp_path, прогоны, выпуски)
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        код = МОД.главная(["--from", с, "--to", по])
    return код, буфер.getvalue()


def test_занятость_считается_по_началу_и_концу(monkeypatch, tmp_path):
    код, вывод = _прогон(monkeypatch, tmp_path, [
        {"task_id": "T1", "verdict": "VERIFIED",
         "started_at": "2026-10-14T10:00:00Z",
         "finished_at": "2026-10-14T10:30:00Z"},
        {"task_id": "T2", "verdict": "INCOMPLETE",
         "started_at": "2026-10-14T11:00:00Z",
         "finished_at": "2026-10-14T11:30:00Z"},
    ], [])
    assert код == 0
    assert "1.0 ч" in вывод
    assert "VERIFIED:1" in вывод and "INCOMPLETE:1" in вывод


def test_прогон_без_конца_не_добавляет_времени(monkeypatch, tmp_path):
    """Незакрытая запись — пробел журнала, а не бесконечная работа."""
    код, вывод = _прогон(monkeypatch, tmp_path, [
        {"task_id": "T1", "verdict": "VERIFIED",
         "started_at": "2026-10-14T10:00:00Z", "finished_at": None},
    ], [])
    assert "0.0 ч" in вывод


def test_день_без_записей_называется_а_не_считается_нулём(monkeypatch, tmp_path):
    код, вывод = _прогон(monkeypatch, tmp_path, [
        {"task_id": "T1", "verdict": "VERIFIED",
         "started_at": "2026-10-15T10:00:00Z",
         "finished_at": "2026-10-15T10:06:00Z"},
    ], [])
    assert "2026-10-14" in вывод and "нет записей" in вывод


def test_остаток_времени_не_называется_простоем(monkeypatch, tmp_path):
    """Главное свойство вывода: отличать нечем — значит не утверждать."""
    код, вывод = _прогон(monkeypatch, tmp_path, [
        {"task_id": "T1", "verdict": "VERIFIED",
         "started_at": "2026-10-14T10:00:00Z",
         "finished_at": "2026-10-14T10:06:00Z"},
    ], [])
    assert "НЕ называется простоем" in вывод
    assert "не ждал ли исполнитель внешнего действия" in вывод
    assert "простой" not in вывод.split("НЕ называется простоем")[0].lower()


def test_исходы_выпусков_считаются_по_суткам(monkeypatch, tmp_path):
    код, вывод = _прогон(monkeypatch, tmp_path, [
        {"task_id": "T1", "verdict": "VERIFIED",
         "started_at": "2026-10-14T10:00:00Z",
         "finished_at": "2026-10-14T10:06:00Z"},
    ], [
        {"at": "2026-10-14T10:05:00Z", "task_id": "T1",
         "outcome": "live_verified"},
        {"at": "2026-10-14T10:07:00Z", "task_id": "T175", "outcome": "waiting"},
        {"at": "2026-10-14T10:09:00Z", "task_id": "T175", "outcome": "waiting"},
    ])
    assert "'waiting': 2" in вывод and "'live_verified': 1" in вывод


def test_пустой_журнал_прогонов_это_отказ(monkeypatch, tmp_path):
    код, _ = _прогон(monkeypatch, tmp_path, [], [])
    assert код == 2, "нечего считать — это не «ноль работы»"


def test_промежутки_между_коммитами_не_источник(monkeypatch, tmp_path):
    тело = ПУТЬ.read_text(encoding="utf-8")
    assert "промежутк" in тело.lower()
    assert "runs.jsonl" in тело and "publish.jsonl" in тело
    assert "git log" not in тело, (
        "время работы не выводится из истории коммитов")
