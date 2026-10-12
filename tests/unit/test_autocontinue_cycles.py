"""Приёмка двух циклов: инструмент обязан отличать доказательство от похожего.

Критерий владельца легко изобразить: два прогона в следе — и «автопродолжение
работает». Поэтому здесь проверяется, что инструмент НЕ принимает похожее за
доказательство: ручной запуск, повтор той же задачи, отсутствие вердикта и
отсутствие отметок времени он обязан называть расхождением по отдельности.

И отдельно — что отсутствие следов даёт «не измерено» (код 2), а не
«не подтверждено»: это разные утверждения, и путать их нельзя.
"""
from __future__ import annotations

import importlib.util
import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
ИСТОЧНИК = КОРЕНЬ / "automation" / "local" / "autocontinue-cycles.py"


def _модуль():
    спец = importlib.util.spec_from_file_location("cycles", ИСТОЧНИК)
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


@pytest.fixture(scope="module")
def м():
    return _модуль()


def прогон_записи(**поля):
    основа = {"trigger": "systemd-timer", "verdict": "VERIFIED",
              "started_at": "2026-10-12T17:00:00Z",
              "finished_at": "2026-10-12T17:10:00Z"}
    return {**основа, **поля}


def след(tmp_path: Path, записи: list[dict]) -> Path:
    путь = tmp_path / "runs.jsonl"
    путь.write_text("".join(json.dumps(з, ensure_ascii=False) + "\n"
                            for з in записи), encoding="utf-8")
    return путь


def прогон(м, путь: Path, вид: str = "tech"):
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        код = м.главное(["--kind", вид, "--runs", str(путь)])
    return код, буфер.getvalue()


def test_два_цикла_по_таймеру_с_разными_задачами_это_проход(м, tmp_path):
    путь = след(tmp_path, [prognoz := прогон_записи(task_id="T001"),
                           прогон_записи(task_id="T002")])
    assert prognoz["task_id"] == "T001"
    код, вывод = прогон(м, путь)
    assert код == 0, вывод
    assert "два цикла подряд подтверждены" in вывод


def test_ручной_запуск_это_расхождение(м, tmp_path):
    """«Подряд без ручной команды» — главное в критерии."""
    путь = след(tmp_path, [прогон_записи(task_id="T001"),
                           прогон_записи(task_id="T002", trigger="manual")])
    код, вывод = прогон(м, путь)
    assert код == 1
    assert "запущены таймером" in вывод
    assert "'manual'" in вывод


def test_одна_и_та_же_задача_дважды_это_расхождение(м, tmp_path):
    """Два прогона одной задачи доказывают повтор, а не продолжение."""
    путь = след(tmp_path, [прогон_записи(task_id="T001"),
                           прогон_записи(task_id="T001")])
    код, вывод = прогон(м, путь)
    assert код == 1
    assert "задачи разные" in вывод
    assert "пересечение 1" in вывод


def test_отсутствие_вердикта_это_расхождение(м, tmp_path):
    """Код завершения процесса выполнения не подтверждает."""
    путь = след(tmp_path, [прогон_записи(task_id="T001"),
                           прогон_записи(task_id="T002", verdict="INCOMPLETE")])
    код, вывод = прогон(м, путь)
    assert код == 1
    assert "вердикт проверяющего шага" in вывод


def test_отсутствие_отметок_времени_это_расхождение(м, tmp_path):
    путь = след(tmp_path, [прогон_записи(task_id="T001"),
                           прогон_записи(task_id="T002", finished_at=None)])
    код, вывод = прогон(м, путь)
    assert код == 1
    assert "отметки времени" in вывод


def test_задача_без_имени_доказательством_не_считается(м, tmp_path):
    """Пустая задача — нечего сравнивать, а значит и нечего утверждать."""
    путь = след(tmp_path, [прогон_записи(), прогон_записи()])
    код, вывод = прогон(м, путь)
    assert код == 1
    assert "задачи разные" in вывод


def test_один_прогон_это_не_измерено(м, tmp_path):
    """Один цикл доказывает запуск, а не продолжение."""
    путь = след(tmp_path, [прогон_записи(task_id="T001")])
    assert м.главное(["--kind", "tech", "--runs", str(путь)]) == 2


def test_нет_следа_это_не_измерено(м, tmp_path):
    assert м.главное(["--kind", "tech", "--runs", str(tmp_path / "нет")]) == 2


def test_битые_строки_следа_не_роняют(м, tmp_path):
    путь = tmp_path / "runs.jsonl"
    путь.write_text(json.dumps(прогон_записи(task_id="T001")) + "\nне json\n"
                    + json.dumps(прогон_записи(task_id="T002")) + "\n",
                    encoding="utf-8")
    код, вывод = прогон(м, путь)
    assert код == 0, вывод


def test_редакционный_вид_опознаёт_задачу_адресами(м, tmp_path):
    """У редакции нет task_id: задача — множество опубликованных адресов."""
    первый = прогон_записи(self_report={"urls": ["https://a/1"]},
                           verified_complete=True)
    второй = прогон_записи(self_report={"urls": ["https://a/2"]},
                           verified_complete=True)
    код, вывод = прогон(м, след(tmp_path, [первый, второй]), вид="editor")
    assert код == 0, вывод
    assert "пересечение 0" in вывод


def test_редакционный_вердикт_берётся_у_проверки_а_не_у_прогона(м, tmp_path):
    """`verdict` рядом пишет сам прогон; считает `verified_complete`."""
    первый = прогон_записи(self_report={"urls": ["https://a/1"]},
                           verified_complete=True)
    второй = прогон_записи(self_report={"urls": ["https://a/2"]},
                           verdict="COMPLETE", verified_complete=False)
    код, вывод = прогон(м, след(tmp_path, [первый, второй]), вид="editor")
    assert код == 1
    assert "НЕ ПОДТВЕРЖДЁН" in вывод
