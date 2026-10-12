"""Молчащие проверки в run.sh ячеек: находка не должна зависеть от удачи.

Случай 12.10 нашёлся на полном прогоне одной ячейки. Инструмент существует,
чтобы следующий такой случай назывался сразу и по всем ячейкам. Поэтому здесь
проверяется различение трёх состояний, которые легко слить в одно: молчащая
проверка прямо сейчас, отсутствие защиты от следующей и исправность.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
ИСТОЧНИК = КОРЕНЬ / "automation" / "local" / "run-sh-guard-audit.py"


def _модуль():
    спец = importlib.util.spec_from_file_location("run_sh_guard_audit",
                                                  ИСТОЧНИК)
    м = importlib.util.module_from_spec(спец)
    sys.modules["run_sh_guard_audit"] = м
    спец.loader.exec_module(м)
    return м


ау = _модуль()

С_ОБЁРТКОЙ_STEP = """#!/usr/bin/env bash
step() { "$@"; }
step "первая" python3 checks/один.py
step "вторая" python3 checks/два.py
"""

ОСИРОТЕВШАЯ = С_ОБЁРТКОЙ_STEP + 'check "крошки" python3 checks/крошки.py\n'

СО_СТОРОЖЕМ = С_ОБЁРТКОЙ_STEP + '''
if [ "$ran" -ne "$expected" ]; then
  say "checks-all-ran" "FAIL"
fi
'''


def _ячейка(tmp_path: Path, имя: str, текст: str) -> None:
    (tmp_path / имя / "checks").mkdir(parents=True)
    (tmp_path / имя / "checks" / "run.sh").write_text(текст, encoding="utf-8")


def test_осиротевший_вызов_находится():
    итог = ау.разобрать(ОСИРОТЕВШАЯ)
    assert итог["определены"] == ["step"]
    assert итог["осиротевшие"] == {"check": 1}, итог


def test_совпадающая_обёртка_осиротевшей_не_считается():
    """Обратная сторона: иначе инструмент ругался бы на все 21 ячейку."""
    итог = ау.разобрать(С_ОБЁРТКОЙ_STEP)
    assert итог["осиротевшие"] == {}, итог
    assert итог["вызовы"] == {"check": 0, "step": 2}


def test_сторож_различается_от_его_отсутствия():
    assert ау.разобрать(СО_СТОРОЖЕМ)["сторож"] is True
    assert ау.разобрать(С_ОБЁРТКОЙ_STEP)["сторож"] is False


def test_молчащая_проверка_это_код_1(tmp_path, capsys):
    _ячейка(tmp_path, "ячейка-а", ОСИРОТЕВШАЯ)
    код = ау.главное(["--repos", str(tmp_path)])
    вывод = capsys.readouterr().out
    assert код == 1, вывод
    assert "эти проверки молчат" in вывод
    assert "молчащие проверки прямо сейчас: 1" in вывод


def test_отсутствие_сторожа_это_отдельный_код(tmp_path, capsys):
    """Ячейка без сторожа сегодня исправна — но защиты у неё нет.

    Слить это с молчащей проверкой значило бы либо поднять ложную тревогу,
    либо скрыть настоящую: коды возврата различаются намеренно.
    """
    _ячейка(tmp_path, "ячейка-б", С_ОБЁРТКОЙ_STEP)
    код = ау.главное(["--repos", str(tmp_path)])
    вывод = capsys.readouterr().out
    assert код == 3, вывод
    assert "молчащие проверки прямо сейчас: 0" in вывод
    assert "без сторожа счёта" in вывод


def test_со_сторожем_и_без_сирот_это_ноль(tmp_path, capsys):
    _ячейка(tmp_path, "ячейка-в", СО_СТОРОЖЕМ)
    код = ау.главное(["--repos", str(tmp_path)])
    assert код == 0, capsys.readouterr().out


def test_ни_одного_run_sh_это_предел_измерения(tmp_path, capsys):
    """Пустая выборка не «всё исправно»: мерить было нечего."""
    (tmp_path / "пусто").mkdir()
    код = ау.главное(["--repos", str(tmp_path)])
    вывод = capsys.readouterr()
    assert код == 2, вывод.out
    assert "предел измерения" in вывод.err


def test_нет_каталога_это_отказ(tmp_path, capsys):
    код = ау.главное(["--repos", str(tmp_path / "такого-нет")])
    assert код == 2
    assert "каталога рабочих копий нет" in capsys.readouterr().err
