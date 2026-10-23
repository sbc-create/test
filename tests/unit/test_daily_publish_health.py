"""Четыре исхода суточной публикации различимы, и перечень витрин — свой.

Повод измеренный, 23.10: `var/lords/daily-state/last-publish.json` не читал
никто, в нём лежал traceback с `[Errno 28] No space left on device`, и
тринадцать витрин остались на каталоге от 22.10. Обнаружилось случайно.

Проверяется ПОВЕДЕНИЕ на подготовленных каталогах: инструмент запускается с
`--state`, `--frontend` и `--backups`, указывающими в tmp_path. Структурная
проверка «в коде есть слово ENOSPC» прошла бы и на инструменте, который
печатает его всегда.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ИНСТРУМЕНТ = КОРЕНЬ / "automation" / "local" / "daily-publish-health.py"

TRACEBACK_ENOSPC = """Traceback (most recent call last):
  File "nova-catalog-publish.py", line 595, in _выполнить
    shutil.copy2(путь, копия)
OSError: [Errno 28] No space left on device: '/srv/lords/.frontend/lords-06-details.json' -> '/x/lords-06-details.json.before.daily-20261023T033423Z'
"""

TRACEBACK_ДРУГОЙ = """Traceback (most recent call last):
  File "nova-catalog-publish.py", line 400, in выполнить
    raise RuntimeError("снимок поставщика не разбирается")
RuntimeError: снимок поставщика не разбирается
"""


def подготовить(tmp_path, отчёт: str, витрины: dict[str, float],
                копии: dict[str, int] | None = None) -> dict[str, str]:
    состояние = tmp_path / "daily-state"
    состояние.mkdir()
    (состояние / "last-publish.json").write_text(отчёт, encoding="utf-8")
    фронт = tmp_path / "frontend"
    фронт.mkdir()
    import os
    for имя, когда in витрины.items():
        ф = фронт / f"{имя}-catalog.json"
        ф.write_text("{}", encoding="utf-8")
        os.utime(ф, (когда, когда))
    копии_к = tmp_path / "backups"
    копии_к.mkdir()
    for имя, размер in (копии or {}).items():
        (копии_к / имя).write_bytes(b"x" * размер)
    return {"state": str(состояние), "frontend": str(фронт),
            "backups": str(копии_к)}


def запуск(пути: dict[str, str]) -> tuple[int, dict]:
    г = subprocess.run(
        [sys.executable, str(ИНСТРУМЕНТ), "--state", пути["state"],
         "--frontend", пути["frontend"], "--backups", пути["backups"], "--json"],
        capture_output=True, text=True, timeout=120)
    return г.returncode, json.loads(г.stdout)


def test_enospc_называется_отдельно(tmp_path):
    """ENOSPC — не «какая-то ошибка»: причина снаружи кода, и действие другое."""
    пути = подготовить(tmp_path, TRACEBACK_ENOSPC, {"lords-01": 1.0e9})
    код, итог = запуск(пути)
    assert итог["исход"] == "ПРОГОН УПАЛ", итог
    assert "ENOSPC" in итог["почему"], итог["почему"]
    assert код == 1


def test_другая_ошибка_не_называется_местом(tmp_path):
    """Контроль: падение не из-за места не должно печатать ENOSPC."""
    пути = подготовить(tmp_path, TRACEBACK_ДРУГОЙ, {"lords-01": 1.0e9})
    код, итог = запуск(пути)
    assert итог["исход"] == "ПРОГОН УПАЛ", итог
    assert "ENOSPC" not in итог["почему"], итог["почему"]
    assert "снимок поставщика" in итог["почему"]
    assert код == 1


def test_отчёт_есть_а_витрины_старые_это_отдельный_исход(tmp_path):
    """«Прогон прошёл» и «витрины обновились» — разные факты."""
    пути = подготовить(tmp_path, json.dumps({"ok": True}),
                       {"lords-01": 1.0e9, "lords-02": 1.0e9})
    код, итог = запуск(пути)
    assert итог["исход"] == "ПРОГОН ПРОШЁЛ, ВИТРИНЫ СТАРЫЕ", итог
    assert set(итог["отставших"]) == {"lords-01", "lords-02"}, итог
    assert код == 1


def test_исправно_когда_витрины_не_старше_прогона(tmp_path):
    """Контроль исхода «исправно»: иначе инструмент всегда находил бы беду."""
    import time
    сейчас = time.time()
    пути = подготовить(tmp_path, json.dumps({"ok": True}),
                       {"lords-01": сейчас, "lords-02": сейчас})
    код, итог = запуск(пути)
    assert итог["исход"] == "ИСПРАВНО", итог
    assert итог["отставших"] == []
    assert код == 0


def test_нет_состояния_это_не_исправно(tmp_path):
    """Отсутствие файла — третий исход, а не успех."""
    пути = подготовить(tmp_path, json.dumps({"ok": True}), {})
    pathlib.Path(пути["state"], "last-publish.json").unlink()
    код, итог = запуск(пути)
    assert итог["исход"] == "НЕ ИЗМЕРЕНО", итог
    assert "last-publish.json" in итог["почему"]
    assert код == 2


def test_чужие_витрины_не_считаются_своими(tmp_path):
    """Перечень витрин — из копий издателя, иначе в него попадают соседи.

    23.10 первая редакция насчитала 14 витрин, включив `animego-04`, который
    этот издатель не публикует: его файлы в том же каталоге пишет другой
    таймер, а копий у него нет.
    """
    import time
    сейчас = time.time()
    пути = подготовить(
        tmp_path, json.dumps({"ok": True}),
        {"lords-01": сейчас, "animego-04": сейчас, "yummy-07": сейчас},
        копии={"lords-01-catalog.json.before.daily-20261023T033423Z": 10})
    код, итог = запуск(пути)
    assert [в["витрина"] for в in итог["витрины"]] == ["lords-01"], итог
    assert итог["копии"]["суточных_прогонов"] == 1, итог


def test_без_копий_перечень_назван_приблизительным(tmp_path):
    """Когда отличить своё от чужого не на чем, это говорится вслух."""
    import time
    сейчас = time.time()
    пути = подготовить(tmp_path, json.dumps({"ok": True}),
                       {"lords-01": сейчас, "animego-04": сейчас})
    код, итог = запуск(пути)
    assert "ПЕРЕЧЕНЬ ВЗЯТ ИЗ КАТАЛОГА ВИТРИН" in итог["перечень_витрин_откуда"]
    assert len(итог["витрины"]) == 2, итог
