"""Отказ на одной витрине K2 не лишает каталога остальные.

Повод измеренный: 22.10 доставка отказала на `lords-10`, и остальные СЕМЬ
витрин не обрабатывались вовсе — сценарий выходил кодом 1 на первой неудаче,
хотя комплекты для остальных уже лежали рядом. Витрины независимы: у каждой
свой входящий каталог на узле и свои суммы.

Проверяется ПОВЕДЕНИЕ сценария, а не его текст: `ansible` подменяется заглушкой
в `PATH`, которая отказывает ровно одной витрине. Структурная проверка «в файле
нет `exit 1`» прошла бы и на сценарии, который молча глотает отказы.
"""
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
СЦЕНАРИЙ = КОРЕНЬ / "automation" / "local" / "k2-deliver-catalog.sh"

#: Имена переменных в заглушке ТОЛЬКО ASCII, как и в самом сценарии: bash не
#: принимает кириллические имена, и первая редакция этой заглушки печатала
#: «line 3: аргументы=…: No such file or directory», отчего отказали все три
#: витрины вместо одной. Та же ловушка ловила меня 21.10 на `/bin/sh`.
ЗАГЛУШКА = """#!/bin/bash
# Заглушка ansible: отказывает ровно той витрине, чьё имя лежит в FAIL_SITE.
args="$*"
if [ -n "$FAIL_SITE" ] && printf '%s' "$args" | grep -q "$FAIL_SITE"; then
  echo "fatal: [k2-zomro-01]: UNREACHABLE! => подменённая причина отказа" >&2
  exit 1
fi
case "$args" in
  *"-m raw"*) echo "k2-zomro-01 | CHANGED | rc=0 >>"; echo "rc=0" ;;
  *)          echo "k2-zomro-01 | CHANGED => ok" ;;
esac
exit 0
"""


@pytest.fixture
def стенд(tmp_path):
    """Дерево, из которого сценарий считает себя корнем копии."""
    (tmp_path / "automation" / "local").mkdir(parents=True)
    shutil.copy(СЦЕНАРИЙ, tmp_path / "automation" / "local" / СЦЕНАРИЙ.name)
    (tmp_path / "var" / "ansible").mkdir(parents=True)
    (tmp_path / "var" / "ansible" / "hosts.yml").write_text(
        "all:\n  children:\n    dle_staging:\n      hosts:\n"
        "        k2-zomro-01:\n          ansible_host: 127.0.0.1\n",
        encoding="utf-8")
    бин = tmp_path / "bin"
    бин.mkdir()
    заглушка = бин / "ansible"
    заглушка.write_text(ЗАГЛУШКА, encoding="utf-8")
    заглушка.chmod(0o755)
    комплект = tmp_path / "staging"
    комплект.mkdir()
    for site in ("s-1", "s-2", "s-3"):
        for kind in ("catalog", "details"):
            (комплект / f"{site}-{kind}.json").write_text(
                '{"items": []}', encoding="utf-8")
    return tmp_path


def запустить(стенд, отказать: str = "") -> subprocess.CompletedProcess:
    окружение = dict(os.environ)
    окружение["PATH"] = f"{стенд / 'bin'}:{окружение['PATH']}"
    окружение["FAIL_SITE"] = отказать
    return subprocess.run(
        ["bash", str(стенд / "automation" / "local" / СЦЕНАРИЙ.name),
         "--from-staging", str(стенд / "staging"), "s-1", "s-2", "s-3"],
        capture_output=True, text=True, env=окружение, timeout=120)


def test_отказ_одной_витрины_не_останавливает_остальные(стенд):
    г = запустить(стенд, отказать="s-2")
    assert "s-1: доставлено и сверено" in г.stdout, г.stdout
    assert "s-3: доставлено и сверено" in г.stdout, г.stdout
    assert "доставлено [s-1 s-3], отказ [s-2]" in г.stdout, г.stdout


def test_частичная_доставка_успехом_не_считается(стенд):
    """Код возврата ненулевой, иначе таймер отчитается об успехе."""
    г = запустить(стенд, отказать="s-2")
    assert г.returncode == 1, г.stdout


def test_причина_отказа_печатается_а_не_глотается(стенд):
    г = запустить(стенд, отказать="s-2")
    assert "UNREACHABLE" in г.stdout, (
        "вывод ansible снова уничтожается — ровно тот дефект, из-за которого"
        " четыре суточных отказа остались без причины")


def test_журнал_отказа_переживает_прогон(стенд):
    запустить(стенд, отказать="s-2")
    журнал = стенд / "var" / "k2-data" / "last-copy-failure.log"
    assert журнал.is_file(), "копия журнала отказа не сохранена"
    assert "UNREACHABLE" in журнал.read_text(encoding="utf-8")


def test_ящик_отказавшей_витрины_остаётся_для_разбора(стенд):
    запустить(стенд, отказать="s-2")
    ящик = стенд / "var" / "k2-data" / "deliver" / "s-2"
    assert ящик.is_dir(), "ящик отказавшей витрины убран — разбирать нечего"
    assert (ящик / "SHA256SUMS").is_file()


def test_ящики_доставленных_витрин_убраны(стенд):
    """Иначе рабочий каталог растёт на 115 МиБ за витрину."""
    запустить(стенд, отказать="s-2")
    основа = стенд / "var" / "k2-data" / "deliver"
    assert not (основа / "s-1").exists()
    assert not (основа / "s-3").exists()


def test_когда_всё_прошло_рабочий_каталог_убран_и_код_ноль(стенд):
    """Граница с другой стороны: без отказов поведение прежнее."""
    г = запустить(стенд)
    assert г.returncode == 0, г.stdout
    assert "доставлено [s-1 s-2 s-3], отказ []" in г.stdout, г.stdout
    assert not (стенд / "var" / "k2-data" / "deliver").exists()


def test_нехватка_файла_у_одной_витрины_тоже_не_валит_прогон(стенд):
    (стенд / "staging" / "s-2-details.json").unlink()
    г = запустить(стенд)
    assert г.returncode == 1
    assert "s-1: доставлено и сверено" in г.stdout, г.stdout
    assert "s-3: доставлено и сверено" in г.stdout, г.stdout
    assert "отказ [s-2]" in г.stdout, г.stdout
