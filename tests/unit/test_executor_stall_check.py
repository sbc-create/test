"""REQ-EXEC-STALL: «исполнитель работает» и «работа движется» — разное.

Два измеренных провала, которые не видны ни в одном отчёте:

* выпускающий кружит на одной задаче. Измерено 2026-10-18: T175 — 356
  одинаковых решений «ожидание» подряд с 16.10 14:18Z по 17.10 21:02Z, то есть
  31 час цикла на задаче, которая не может сдвинуться; T145 — 29 подряд;
* готовая задача есть, а прогонов нет. Это НЕ то же, что «нет задач»: при
  пустой очереди простой законен, при непустой — нет.

Здесь проверяется ровно то, от чего зависит смысл вывода: счёт идёт по ПОДРЯД
идущим одинаковым решениям (иначе редкие ожидания сложатся в ложную находку),
пустая очередь находкой не считается, непрочитанная очередь называется
«НЕ ИЗМЕРЕНО», а причина простоя не называется вовсе — журналы её не знают.
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

ПУТЬ = (Path(__file__).resolve().parents[2] / "automation" / "local"
        / "executor-stall-check.py")


def _модуль():
    имя = "executor_stall_check"
    спец = importlib.util.spec_from_file_location(имя, ПУТЬ)
    м = importlib.util.module_from_spec(спец)
    sys.modules[имя] = м
    спец.loader.exec_module(м)
    return м


МОД = _модуль()


def _стенд(monkeypatch, tmp_path: Path, выпуски: list, прогоны: list,
           задачи: list | None = None, беда: str = "") -> None:
    (tmp_path / "publish.jsonl").write_text(
        "".join(json.dumps(з, ensure_ascii=False) + "\n" for з in выпуски),
        encoding="utf-8")
    (tmp_path / "runs.jsonl").write_text(
        "".join(json.dumps(з, ensure_ascii=False) + "\n" for з in прогоны),
        encoding="utf-8")
    monkeypatch.setattr(МОД, "ЖУРНАЛЫ", tmp_path)
    monkeypatch.setattr(МОД, "очередь",
                        lambda ветка, путь: (задачи or [], беда, "стенд"))


def _прогон(monkeypatch, tmp_path, выпуски, прогоны, задачи=None, беда="",
            аргв=()) -> tuple[int, str]:
    _стенд(monkeypatch, tmp_path, выпуски, прогоны, задачи, беда)
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        код = МОД.главная(list(аргв))
    return код, буфер.getvalue()


def _ожидание(задача: str, когда: str, причина: str = "ветка не равна живому"):
    return {"at": когда, "task_id": задача, "outcome": "waiting",
            "reason": причина}


def test_кружение_называется_с_числом_и_сроком(monkeypatch, tmp_path):
    выпуски = [_ожидание("T175", f"2026-10-16T{10 + i // 60:02d}:{i % 60:02d}:00Z")
               for i in range(25)]
    код, вывод = _прогон(monkeypatch, tmp_path, выпуски, [], аргв=("--repeats", "20"))
    assert код == 1
    assert "T175: 25 раз «waiting»" in вывод
    assert "2026-10-16T10:00:00Z" in вывод


def test_счёт_только_подряд(monkeypatch, tmp_path):
    """Иначе редкие ожидания за неделю сложатся в ложную находку.

    Двадцать ожиданий по задаче, но между ними другое решение: кружения нет,
    потому что задача ДВИГАЛАСЬ.
    """
    выпуски = []
    for i in range(20):
        выпуски.append(_ожидание("T1", f"2026-10-16T10:{i:02d}:00Z"))
        выпуски.append({"at": f"2026-10-16T10:{i:02d}:30Z", "task_id": "T1",
                        "outcome": "live_verified", "reason": "выпущено"})
    код, вывод = _прогон(monkeypatch, tmp_path, выпуски, [],
                         аргв=("--repeats", "20"))
    assert "КРУЖЕНИЕ НА ОДНОЙ ЗАДАЧЕ (порог 20 повторов подряд): 0" in вывод


def test_разная_причина_обнуляет_счёт(monkeypatch, tmp_path):
    выпуски = ([_ожидание("T1", f"2026-10-16T10:{i:02d}:00Z", "причина А")
                for i in range(15)]
               + [_ожидание("T1", f"2026-10-16T11:{i:02d}:00Z", "причина Б")
                  for i in range(15)])
    код, вывод = _прогон(monkeypatch, tmp_path, выпуски, [],
                         аргв=("--repeats", "20"))
    assert "): 0" in вывод, "две разные причины по 15 — это не 30 подряд"


def test_пустая_очередь_не_находка(monkeypatch, tmp_path):
    """Простой при пустой очереди законен, и так и печатается."""
    код, вывод = _прогон(monkeypatch, tmp_path, [], [
        {"task_id": "T1", "verdict": "VERIFIED",
         "started_at": "2026-10-10T10:00:00Z",
         "finished_at": "2026-10-10T10:05:00Z"}],
        задачи=[{"id": "T1", "status": "live_verified"}],
        аргв=("--now", "2026-10-18T15:00:00Z"))
    assert код == 0
    assert "простой при пустой очереди законен" in вывод


def test_готовая_задача_при_давнем_прогоне_это_находка(monkeypatch, tmp_path):
    код, вывод = _прогон(monkeypatch, tmp_path, [], [
        {"task_id": "T1", "verdict": "VERIFIED",
         "started_at": "2026-10-18T10:00:00Z",
         "finished_at": "2026-10-18T10:05:00Z"}],
        задачи=[{"id": "T9", "status": "queued"},
                {"id": "T8", "status": "queued"}],
        аргв=("--now", "2026-10-18T15:00:00Z", "--idle-minutes", "60"))
    assert код == 1
    assert "ГОТОВЫХ ЗАДАЧ 2" in вывод
    assert "295 мин назад" in вывод
    assert "T9" in вывод


def test_готовая_задача_в_пределах_порога_не_находка(monkeypatch, tmp_path):
    код, вывод = _прогон(monkeypatch, tmp_path, [], [
        {"task_id": "T1", "verdict": "VERIFIED",
         "started_at": "2026-10-18T14:30:00Z",
         "finished_at": "2026-10-18T14:40:00Z"}],
        задачи=[{"id": "T9", "status": "queued"}],
        аргв=("--now", "2026-10-18T15:00:00Z", "--idle-minutes", "60"))
    assert код == 0
    assert "в пределах порога" in вывод


def test_ни_одного_прогона_при_готовых_задачах(monkeypatch, tmp_path):
    код, вывод = _прогон(monkeypatch, tmp_path,
                         [_ожидание("T1", "2026-10-18T10:00:00Z")], [],
                         задачи=[{"id": "T9", "status": "queued"}],
                         аргв=("--now", "2026-10-18T15:00:00Z"))
    assert код == 1
    assert "прогонов в журнале нет" in вывод


def test_непрочитанная_очередь_это_не_отсутствие_задач(monkeypatch, tmp_path):
    """«Не измерено» вместо «готовых нет» — то же правило, что и везде."""
    код, вывод = _прогон(monkeypatch, tmp_path, [], [
        {"task_id": "T1", "verdict": "VERIFIED",
         "started_at": "2026-10-18T10:00:00Z",
         "finished_at": "2026-10-18T10:05:00Z"}],
        беда="git show не удался",
        аргв=("--now", "2026-10-18T15:00:00Z"))
    assert "НЕ ИЗМЕРЕНО" in вывод
    assert "не «готовых нет»" in вывод


def test_без_журналов_это_отказ(monkeypatch, tmp_path):
    код, _ = _прогон(monkeypatch, tmp_path, [], [])
    assert код == 2


def test_причина_простоя_не_называется():
    тело = ПУТЬ.read_text(encoding="utf-8")
    assert "Причина простоя здесь НЕ называется" in тело
    assert "упал ли" in тело and "ждёт внешнего действия" in тело


def test_очередь_читается_из_живого_файла_а_не_из_ветки(monkeypatch, tmp_path):
    """Разница измерена 18.10 19:30Z и она меняет вывод.

    В ветке `origin/claude/nova-publish-memory-01` было 188 задач и 11
    `queued`, в живом файле — 277 задач и `queued` ровно одна. Линия SEO
    коммитит локально и пушит позже, поэтому проверка по ветке отвечала на
    вопрос о прошлом состоянии и показывала одиннадцать готовых задач там, где
    их нет.
    """
    живой = tmp_path / "seo-tech-queue.json"
    живой.write_text(json.dumps({"tasks": [{"id": "T1", "status": "queued"}]}),
                     encoding="utf-8")
    monkeypatch.setattr(МОД, "ОЧЕРЕДЬ_ЖИВАЯ", живой)
    задачи, беда, откуда = МОД.очередь("origin/нет-такой-ветки",
                                       "config/seo-tech-queue.json")
    assert беда == "" and len(задачи) == 1
    assert "живой файл" in откуда


def test_без_живого_файла_источник_назван(monkeypatch, tmp_path):
    """Запас из ветки допустим, но вывод обязан сказать, что он отстаёт."""
    monkeypatch.setattr(МОД, "ОЧЕРЕДЬ_ЖИВАЯ", tmp_path / "нет.json")
    monkeypatch.setattr(МОД.subprocess, "run",
                        lambda *а, **к: type("Г", (), {
                            "returncode": 0,
                            "stdout": json.dumps({"tasks": []}),
                            "stderr": ""})())
    задачи, беда, откуда = МОД.очередь("origin/ветка", "config/q.json")
    assert беда == "" and задачи == []
    assert "состояние может отставать" in откуда
