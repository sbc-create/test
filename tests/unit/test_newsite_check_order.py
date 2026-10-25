"""Вызов проверки вписывается ПЕРЕД блоком подсчёта, иначе сторож врёт.

Измерено 25.10 на пробном сайте `probe-inherit-01`, созданном штатным
генератором (`factory cell newsite --template lords-anime`): прогон
`checks/run.sh` дал «checks-all-ran FAIL — объявлено проверок: 14,
исполнилось: 13». Причина не в проверках: `expected` считается как число строк
`^check `, а `ran` наращивает сама обёртка `check`, и вызов, добавленный
генератором ПОСЛЕ блока сравнения, попадает в `expected`, но исполняется
позже. Сторож падал у КАЖДОГО нового сайта этого семейства, а напечатанная им
причина («обёртка называется иначе») к делу не относилась — то есть отказ ещё
и уводил разбор в сторону.

Вписыватель здесь ОДИН на всех, кто добавляет проверки: две независимые
вставки повторили бы и ошибку порядка — так и вышло (доступность серий и
публичная почта писались по отдельности).
"""
from __future__ import annotations

import pathlib
import re
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(КОРЕНЬ))

from factory.cell import newsite  # noqa: E402

КАНОН = КОРЕНЬ / "factory" / "cell" / "site_checks" / "run.sh"


def строки_проверок(текст: str) -> list[int]:
    return [i for i, с in enumerate(текст.splitlines()) if re.match(r"^(check|step) ", с)]


def номер_подсчёта(текст: str) -> int:
    строки = текст.splitlines()
    return next(i for i, с in enumerate(строки) if '"$ran" -ne "$expected"' in с)


def test_канон_сам_считает_верно() -> None:
    """Исходный бегунок обязан быть согласован: иначе сравнивать не с чем."""
    текст = КАНОН.read_text(encoding="utf-8")
    assert строки_проверок(текст), "в каноне нет ни одной строки check"
    assert max(строки_проверок(текст)) < номер_подсчёта(текст)


def test_вписанная_проверка_стоит_до_подсчёта(tmp_path) -> None:
    бегунок = tmp_path / "run.sh"
    бегунок.write_text(КАНОН.read_text(encoding="utf-8"), encoding="utf-8")
    изменён = newsite._вписать_проверку(
        бегунок, 'check "episode-availability" python3 checks/episode_availability.py',
        "episode_availability.py")
    текст = бегунок.read_text(encoding="utf-8")
    assert изменён
    assert "episode_availability.py" in текст
    assert max(строки_проверок(текст)) < номер_подсчёта(текст), (
        "вызов снова оказался после блока подсчёта — сторож checks-all-ran "
        "будет падать у каждого нового сайта")


def test_две_вставки_подряд_не_ломают_порядок(tmp_path) -> None:
    """Доступность серий и публичная почта вписываются по отдельности."""
    бегунок = tmp_path / "run.sh"
    бегунок.write_text(КАНОН.read_text(encoding="utf-8"), encoding="utf-8")
    newsite._вписать_проверку(
        бегунок, 'check "episode-availability" python3 checks/episode_availability.py',
        "episode_availability.py")
    newsite._вписать_проверку(
        бегунок, 'check "своя-проверка"        python3 checks/своя.py', "checks/своя.py")
    текст = бегунок.read_text(encoding="utf-8")
    assert len(строки_проверок(текст)) == 15
    assert max(строки_проверок(текст)) < номер_подсчёта(текст)


def test_повторная_вставка_не_дублирует(tmp_path) -> None:
    бегунок = tmp_path / "run.sh"
    бегунок.write_text(КАНОН.read_text(encoding="utf-8"), encoding="utf-8")
    строка = 'check "episode-availability" python3 checks/episode_availability.py'
    assert newsite._вписать_проверку(бегунок, строка, "episode_availability.py") is True
    assert newsite._вписать_проверку(бегунок, строка, "episode_availability.py") is False
    assert бегунок.read_text(encoding="utf-8").count("episode_availability.py") == 1


def test_бегунок_без_блока_подсчёта_обслуживается_прежним_путём(tmp_path) -> None:
    """Сравнивать «объявлено против исполнилось» там некому — вставка до выхода."""
    бегунок = tmp_path / "run.sh"
    бегунок.write_text('#!/usr/bin/env bash\nfail=0\n\nexit "$fail"\n', encoding="utf-8")
    assert newsite._вписать_проверку(бегунок, 'check "x" python3 x.py', "x.py") is True
    текст = бегунок.read_text(encoding="utf-8")
    assert текст.index('check "x"') < текст.index('exit "$fail"')


def test_отсутствующий_бегунок_не_роняет_создание(tmp_path) -> None:
    assert newsite._вписать_проверку(tmp_path / "нет.sh", 'check "x" python3 x.py', "x.py") is False


def test_вписыватель_один(tmp_path) -> None:
    """Самодельных вставок в модуле больше нет: иначе ошибка порядка вернётся."""
    текст = (КОРЕНЬ / "factory" / "cell" / "newsite.py").read_text(encoding="utf-8")
    assert текст.count('replace(\'\\nexit "$fail"\'') <= 1, (
        "в модуле снова несколько самодельных вставок в run.sh")
    assert текст.count("def _вписать_проверку") == 1
