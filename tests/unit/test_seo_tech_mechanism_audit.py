"""Приёмка механизма автопродолжения: что считается пробелом, а что незнанием.

Инструмент проверяет чужой механизм (`seo_operator.tech_run` ведёт SEO-сессия),
и поэтому у него две обязанности, которые легко перепутать:

* назвать пробел, когда свойство НЕ держится — и не постесняться, даже если
  механизм чужой;
* не выдать за пробел то, что просто не измерялось. Следов прогонов может ещё
  не быть, и «файла нет» — факт о приёмке, а не о механизме.

Сеть и живое дерево не нужны: подставляется и дерево, и модуль.
"""
from __future__ import annotations

import importlib.util
import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
ИСТОЧНИК = КОРЕНЬ / "automation" / "local" / "seo-tech-mechanism-audit.py"

#: Подставной механизм, верный действующему во всём, кроме двух пробелов.
#: Просрочку захвата и предел попыток он соблюдает: иначе приёмка показала бы
#: четыре расхождения, и настоящие два потерялись бы среди придуманных.
МЕХАНИЗМ_С_ГОНКОЙ = '''
import datetime as dt
import json
from pathlib import Path

STALE_S = 2 * 3600
MAX_ATTEMPTS = 3


def _строки(state, имя):
    ф = Path(state) / имя
    if not ф.exists():
        return []
    return [json.loads(с) for с in ф.read_text(encoding="utf-8").splitlines()
            if с.strip()]


def task_state(state):
    итог = {}
    for р in _строки(state, "runs.jsonl"):
        з = итог.setdefault(р["task_id"], {"failures": 0})
        if р.get("verdict") == "VERIFIED":
            з["status"] = "verified"
        elif р.get("verdict") != "NO_TASK":
            з["failures"] += 1
    закрытые = {р["run_id"] for р in _строки(state, "runs.jsonl")}
    for к in _строки(state, "claims.jsonl"):
        if к["run_id"] not in закрытые:
            итог.setdefault(к["task_id"], {"failures": 0})["open_claim"] = к
    return итог


def next_task(задачи, state=None, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    сводка = task_state(state)
    for з in задачи:
        if з.get("status") != "queued":
            continue
        с = сводка.get(з["id"], {})
        if с.get("status") == "verified" or с.get("failures", 0) >= MAX_ATTEMPTS:
            continue
        захват = с.get("open_claim")
        if захват:
            возраст = (now - dt.datetime.fromisoformat(
                захват["at"].replace("Z", "+00:00"))).total_seconds()
            if возраст < STALE_S:
                continue
        # Пробел 1: задача отдаётся ДО записи захвата, поэтому второй прогон
        # получит её же. Ровно так ведёт себя действующий модуль.
        return з
    return None
'''

#: Тот же механизм, но с уборкой и с атомарным захватом.
МЕХАНИЗМ_ИСПРАВЛЕННЫЙ = МЕХАНИЗМ_С_ГОНКОЙ + '''

def prune_worktrees(state=None):
    return []


_выданные = set()


def next_task_atomic(задачи, state=None, now=None):
    return None
'''


def _модуль():
    спец = importlib.util.spec_from_file_location("audit", ИСТОЧНИК)
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


@pytest.fixture(scope="module")
def м():
    return _модуль()


def дерево(tmp_path: Path, механизм: str, *, задачи=None,
           следы: bool = False) -> Path:
    """Подставное дерево службы: модуль, очередь и, по просьбе, следы."""
    (tmp_path / "seo_operator").mkdir(parents=True, exist_ok=True)
    (tmp_path / "seo_operator" / "tech_run.py").write_text(механизм,
                                                           encoding="utf-8")
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    задачи = задачи if задачи is not None else [
        {"id": "T001", "status": "queued", "repo": "r1", "check": "checks/a.py"},
        {"id": "T002", "status": "queued", "repo": "r2", "check": "checks/b.py"}]
    (tmp_path / "config" / "seo-tech-queue.json").write_text(
        json.dumps({"tasks": задачи}, ensure_ascii=False), encoding="utf-8")
    состояние = tmp_path / "var" / "seo-tech"
    состояние.mkdir(parents=True, exist_ok=True)
    if следы:
        (состояние / "claims.jsonl").write_text("", encoding="utf-8")
        (состояние / "runs.jsonl").write_text("", encoding="utf-8")
    return tmp_path


def прогон(м, tmp_path: Path, дер: Path):
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        код = м.главное(["--tree", str(дер), "--stand", str(tmp_path / "стенд")])
    return код, буфер.getvalue()


def test_гонка_захвата_называется_пробелом(м, tmp_path):
    """Главное требование владельца: одну задачу не берут дважды."""
    код, вывод = прогон(м, tmp_path, дерево(tmp_path, МЕХАНИЗМ_С_ГОНКОЙ))
    assert код == 1
    assert "не получают одну задачу" in вывод
    assert "не атомарны" in вывод


def test_отсутствие_уборки_называется_пробелом(м, tmp_path):
    код, вывод = прогон(м, tmp_path, дерево(tmp_path, МЕХАНИЗМ_С_ГОНКОЙ))
    assert код == 1
    assert "уборка брошенных копий" in вывод
    assert "копятся" in вывод


def test_наличие_уборки_пробелом_не_считается(м, tmp_path):
    _код, вывод = прогон(м, tmp_path, дерево(tmp_path, МЕХАНИЗМ_ИСПРАВЛЕННЫЙ))
    строка = [с for с in вывод.splitlines() if "уборка брошенных" in с]
    assert строка and строка[0].startswith("   [ок ]"), строка


def test_отсутствие_следов_это_не_измерено_а_не_пробел(м, tmp_path):
    """Файла следов ещё нет — это факт о приёмке, и в расхождения он не идёт."""
    _код, вывод = прогон(м, tmp_path, дерево(tmp_path, МЕХАНИЗМ_С_ГОНКОЙ))
    assert "файла ещё нет" in вывод
    # claims.jsonl, runs.jsonl и каталог копий — три незнания, ноль обвинений.
    assert "не измерено: 3" in вывод
    assert "в расхождения не идёт" in вывод
    # И ровно два расхождения: гонка и уборка. Остальное стенд соблюдает.
    assert "расхождений: 2" in вывод


def test_битая_строка_следа_это_пробел(м, tmp_path):
    дер = дерево(tmp_path, МЕХАНИЗМ_С_ГОНКОЙ, следы=True)
    (дер / "var" / "seo-tech" / "runs.jsonl").write_text(
        '{"run_id": "r1"}\nне json\n', encoding="utf-8")
    код, вывод = прогон(м, tmp_path, дер)
    assert код == 1
    assert "разбирается построчно" in вывод
    assert "строк битых 1" in вывод


def test_задача_без_проверки_это_пробел(м, tmp_path):
    """Задача без объявленной проверки делает вердикт невозможным (D203)."""
    дер = дерево(tmp_path, МЕХАНИЗМ_С_ГОНКОЙ, задачи=[
        {"id": "T001", "status": "queued", "repo": "r1"}])
    код, вывод = прогон(м, tmp_path, дер)
    assert код == 1
    assert "объявлена своя проверка" in вывод
    assert "T001" in вывод


def test_задача_не_в_очереди_проверки_не_требует(м, tmp_path):
    """Статус не queued — задача не берётся, и требовать от неё нечего."""
    дер = дерево(tmp_path, МЕХАНИЗМ_С_ГОНКОЙ, задачи=[
        {"id": "T001", "status": "queued", "repo": "r1", "check": "checks/a.py"},
        {"id": "B001", "status": "blocked", "repo": None}])
    _код, вывод = прогон(м, tmp_path, дер)
    строка = [с for с in вывод.splitlines() if "объявлена своя проверка" in с]
    assert строка and строка[0].startswith("   [ок ]"), строка


def test_повторяющиеся_идентификаторы_это_пробел(м, tmp_path):
    дер = дерево(tmp_path, МЕХАНИЗМ_С_ГОНКОЙ, задачи=[
        {"id": "T001", "status": "queued", "repo": "r1", "check": "c/a.py"},
        {"id": "T001", "status": "queued", "repo": "r2", "check": "c/b.py"}])
    код, вывод = прогон(м, tmp_path, дер)
    assert код == 1
    assert "не повторяются" in вывод


def test_нет_модуля_это_отдельный_исход(м, tmp_path):
    """Нечем проверять — код 2, а не «пробелов нет»."""
    пусто = tmp_path / "пусто"
    (пусто / "config").mkdir(parents=True)
    assert м.главное(["--tree", str(пусто)]) == 2


def test_непригодный_модуль_не_роняет_приёмку(м, tmp_path):
    дер = дерево(tmp_path, "import нет_такого_модуля\n")
    assert м.главное(["--tree", str(дер)]) == 2


def test_живое_состояние_не_трогается(м, tmp_path):
    """Подставные следы пишутся в стенд, а не в дерево службы."""
    дер = дерево(tmp_path, МЕХАНИЗМ_С_ГОНКОЙ, следы=True)
    следы = дер / "var" / "seo-tech" / "claims.jsonl"
    следы.write_text("", encoding="utf-8")
    прогон(м, tmp_path, дер)
    assert следы.read_text(encoding="utf-8") == "", "приёмка записала в живой след"
    assert (tmp_path / "стенд" / "claims.jsonl").exists()
