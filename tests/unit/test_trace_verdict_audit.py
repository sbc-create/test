"""Сторож следов с двумя вердиктами: проверяется ИСПОЛНЕНИЕМ на стенде.

Главное требование к этому сторожу — он обязан ПАДАТЬ на противоречии и
молчать на согласии. Инструмент, который на подложном противоречии возвращает
0, доверия не несёт (D205), поэтому ни один из этих случаев не выводится из
другого: каждый кладёт свой след и смотрит код возврата.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ИНСТРУМЕНТ = (Path(__file__).resolve().parents[2] / "automation" / "local"
              / "trace-verdict-audit.py")


def _след(каталог: Path, имя: str, *, верх: str, низ: str | None,
          операция: str = "deliver", этап: str = "live_verified") -> None:
    запись: dict[str, object] = {
        "request_id": имя, "site_id": "проба-01", "operation": операция,
        "dry_run": False, "status": верх,
        "finished_at": "2026-10-13T00:00:00+00:00",
    }
    if низ is not None:
        запись["outcome"] = {"status": низ, "stage": этап, "steps": {}}
    (каталог / f"{имя}.json").write_text(
        json.dumps(запись, ensure_ascii=False), encoding="utf-8")


def _прогон(каталог: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ИНСТРУМЕНТ), "--follow", str(каталог)],
        capture_output=True, text=True, timeout=120)


def test_противоречие_валит_прогон(tmp_path):
    """Верхний `failed` при применённом нижнем исходе — находка, а не шум."""
    _след(tmp_path, "проба-01-data-aaa", верх="failed", низ="delivered")
    г = _прогон(tmp_path)
    assert г.returncode == 1, г.stdout + г.stderr
    assert "ПРОТИВОРЕЧАТ: 1" in г.stdout, г.stdout
    # Называется и запись, и обе половины вердикта: без них находку не проверить.
    assert "проба-01-data-aaa.json" in г.stdout
    assert "верх failed, низ delivered" in г.stdout


def test_согласие_не_валит_прогон(tmp_path):
    """Обратная сторона: иначе сторож падал бы всегда и ничего не различал."""
    _след(tmp_path, "проба-01-data-bbb", верх="ok", низ="delivered")
    _след(tmp_path, "проба-01-code-ccc", верх="ok", низ="activated",
          операция="activate", этап="activated")
    г = _прогон(tmp_path)
    assert г.returncode == 0, г.stdout + г.stderr
    assert "ПРОТИВОРЕЧАТ: 0" in г.stdout, г.stdout


def test_настоящий_провал_не_объявляется_противоречием(tmp_path):
    """Откат отработал без исключения, но выпуска не было.

    `failed/rolled-back` и `failed/candidate-failed` — согласованные вердикты:
    нижний исход НЕ входит в применённые. Объявить их противоречием значило бы
    выдать правильную запись за дефект, и тогда настоящие четыре потерялись бы
    в шуме.
    """
    _след(tmp_path, "проба-01-data-ddd", верх="failed", низ="rolled-back",
          этап="rolled_back")
    _след(tmp_path, "проба-01-data-eee", верх="failed", низ="candidate-failed",
          этап="failed")
    г = _прогон(tmp_path)
    assert г.returncode == 0, г.stdout + г.stderr
    assert "ПРОТИВОРЕЧАТ: 0" in г.stdout, г.stdout


def test_отказ_исключением_не_зовётся_пробелом(tmp_path):
    """`rejected` без `outcome` — устройство исполнителя, а не недостача.

    Пока эти записи считались «без вердикта», вывод звал читателя искать
    пропажу там, где её нет: 43 записи из 651 на живых следах.
    """
    _след(tmp_path, "проба-01-code-fff", верх="rejected", низ=None,
          операция="activate")
    г = _прогон(tmp_path)
    assert г.returncode == 0, г.stdout + г.stderr
    assert "отказ исключением 1" in г.stdout, г.stdout
    assert "без вердикта 0" in г.stdout, г.stdout


def test_запись_без_верхнего_вердикта_называется(tmp_path):
    """Непредусмотренная форма записи не проглатывается молча."""
    (tmp_path / "проба-01-data-ggg.json").write_text(
        json.dumps({"site_id": "проба-01", "operation": "deliver",
                    "outcome": {"status": "delivered", "stage": "live_verified"}},
                   ensure_ascii=False), encoding="utf-8")
    г = _прогон(tmp_path)
    assert "без вердикта 1" in г.stdout, г.stdout
    assert "проба-01-data-ggg.json" in г.stdout, г.stdout


def test_каталога_следов_нет_это_не_измерено(tmp_path):
    """Отсутствие следов — предел измерения, и он не выдаётся за успех."""
    г = _прогон(tmp_path / "нет-такого")
    assert г.returncode == 2, г.stdout + г.stderr
    assert "НЕ ИЗМЕРЕНО" in г.stdout, г.stdout


def test_набор_исходов_сверяется_с_живым_кодом():
    """Копия набора в инструменте не должна тихо отстать от источника.

    Набор `ПРИМЕНЁННЫЕ_ИСХОДЫ` уже пополнялся — именно поэтому четыре старых
    следа и противоречат себе. Копия, отставшая от кода, повторила бы ту же
    ошибку на новом витке, поэтому инструмент читает живой набор и расхождение
    печатает отдельной строкой.
    """
    текст = ИНСТРУМЕНТ.read_text(encoding="utf-8")
    assert "набор_из_источника" in текст
    assert "РАСХОЖДЕНИЕ копии набора с живым кодом" in текст
    assert "дальше считается по ЖИВОМУ набору" in текст
