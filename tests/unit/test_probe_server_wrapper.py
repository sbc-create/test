"""Обёртка пробного сервера: два сторожа, и ни один не заменяет другого.

Повод измерен 11 октября. Редактор простоял 07:09-15:55 с 101 отказом шлюза по
памяти: в системе накопились 13 пробных копий витрин без хозяина (около
2,8 ГБ), и `MemAvailable` держался на 958 МиБ при пороге редактора 2048 МиБ.
Копии подняты не инструментами фабрики — все они гасят потомков в `finally`, —
а напрямую из оболочек вызова инструментов.

Почему сторожей два, а не один — это вывод из разбора, а не перестраховка:

* у сироты `224855` родительская оболочка была ЖИВА, и сторож «умри вместе с
  родителем» её бы не тронул. Нужен предел жизни;
* а предел жизни не поможет, если оболочку закрыли через минуту, а предел
  стоит полчаса: до него сервер будет жить бесхозным. Нужен PDEATHSIG.

Оба проверены на деле, а не по наличию кода: предел — кодом выхода 124 с
названной причиной, PDEATHSIG — убийством обёртки через SIGKILL, при котором
никакой `finally` выполниться не может.
"""
from __future__ import annotations

import importlib.util
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
СЦЕНАРИЙ = КОРЕНЬ / "automation" / "local" / "probe-server.py"

ВЕЧНЫЙ = ("import time\n"
          "print('сервер пошёл', flush=True)\n"
          "while True: time.sleep(0.1)\n")


def _модуль():
    спец = importlib.util.spec_from_file_location("probe_server", СЦЕНАРИЙ)
    м = importlib.util.module_from_spec(спец)
    sys.modules["probe_server"] = м
    спец.loader.exec_module(м)
    return м


def живой(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:  # pragma: no cover
        return True
    try:
        return Path(f"/proc/{pid}/stat").read_text().split()[2] != "Z"
    except OSError:
        return False


# --- разбор аргументов ----------------------------------------------------

def test_без_команды_отказ():
    м = _модуль()
    assert м.главное([]) == 2


def test_нулевой_предел_отвергается():
    """Сервер без предела — это и есть сирота, ради которой всё написано."""
    м = _модуль()
    assert м.главное(["--ttl", "0", "--", "sleep", "1"]) == 2
    assert м.главное(["--ttl", "-5", "--", "sleep", "1"]) == 2


@pytest.mark.parametrize("команда,ожидалось", [
    (["python3", "src/x.py", "--port", "9190"], "9190"),
    (["python3", "src/x.py", "-p", "8080"], "8080"),
    (["python3", "src/x.py", "--port=7000"], "7000"),
    (["python3", "src/x.py"], ""),
])
def test_порт_вынимается_из_команды(команда, ожидалось):
    """Порт нужен в записке: по нему сверяют сервер с конфигурацией nginx."""
    м = _модуль()
    assert м.порт_из_команды(команда) == ожидалось


# --- сторож «предел жизни» ------------------------------------------------

def test_предел_жизни_гасит_и_даёт_код_124():
    начало = time.monotonic()
    итог = subprocess.run(
        [sys.executable, str(СЦЕНАРИЙ), "--ttl", "2", "--",
         sys.executable, "-c", ВЕЧНЫЙ],
        capture_output=True, text=True, timeout=60)
    прошло = time.monotonic() - начало
    assert итог.returncode == 124, итог.stderr
    assert 1.5 <= прошло <= 20, прошло
    assert "исчерпан предел жизни" in итог.stderr


def test_сервер_завершившийся_сам_отдаёт_свой_код():
    """Предел не должен подменять исход команды, когда она закончилась сама."""
    итог = subprocess.run(
        [sys.executable, str(СЦЕНАРИЙ), "--ttl", "60", "--",
         sys.executable, "-c", "import sys; sys.exit(3)"],
        capture_output=True, text=True, timeout=60)
    assert итог.returncode == 3, итог.stderr


def test_успешная_команда_проходит():
    итог = subprocess.run(
        [sys.executable, str(СЦЕНАРИЙ), "--ttl", "60", "--",
         sys.executable, "-c", "print('ок')"],
        capture_output=True, text=True, timeout=60)
    assert итог.returncode == 0, итог.stderr


# --- сторож «умри с родителем» -------------------------------------------

def test_смерть_обёртки_убивает_сервер():
    """Обёртку убивают SIGKILL: никакой finally выполниться не может.

    Это главный опыт файла. Сторож здесь — свойство ядра (PR_SET_PDEATHSIG), а
    не обещание обработчика, и проверять его надо именно так.
    """
    обёртка = subprocess.Popen(
        [sys.executable, str(СЦЕНАРИЙ), "--ttl", "600", "--",
         sys.executable, "-c", ВЕЧНЫЙ],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    записки = КОРЕНЬ / "var" / "probe-servers"
    сервер_pid = None
    for _ in range(60):
        time.sleep(0.2)
        мои = [п for п in записки.glob("*.json")
               if json.loads(п.read_text(encoding="utf-8")).get("обёртка_pid")
               == обёртка.pid]
        if мои:
            сервер_pid = json.loads(мои[0].read_text(encoding="utf-8"))["pid"]
            break
    assert сервер_pid, "записка о процессе не появилась"
    assert живой(сервер_pid)

    обёртка.kill()
    обёртка.wait(timeout=10)
    for _ in range(40):
        time.sleep(0.25)
        if not живой(сервер_pid):
            break
    жив = живой(сервер_pid)
    if жив:  # pragma: no cover - уборка, чтобы опыт не оставил сироту
        os.kill(сервер_pid, signal.SIGKILL)
    assert not жив, "сервер пережил обёртку — сторож не работает"


def test_записка_появляется_до_готовности_сервера():
    """Записка пишется сразу после запуска, а не после проверки готовности.

    Иначе прерывание между запуском и проверкой оставляет живой процесс, о
    котором никто не знает — ровно так и набрались 13 копий.
    """
    м = _модуль()
    источник = СЦЕНАРИЙ.read_text(encoding="utf-8")
    запуск = источник.index("процесс = subprocess.Popen(команда")
    запись = источник.index("путь = записка(процесс.pid")
    ожидание = источник.index("процесс.wait(timeout=1.0)")
    assert запуск < запись < ожидание
    assert hasattr(м, "записка")


def test_записка_убирается_за_собой(tmp_path, monkeypatch):
    м = _модуль()
    monkeypatch.setattr(м, "ЗАПИСКИ", tmp_path)
    код = м.главное(["--ttl", "30", "--", sys.executable, "-c", "pass"])
    assert код == 0
    assert list(tmp_path.glob("*.json")) == []


def test_записка_называет_порт_и_команду(tmp_path, monkeypatch):
    м = _модуль()
    monkeypatch.setattr(м, "ЗАПИСКИ", tmp_path)
    путь = м.записка(12345, "9190", ["python3", "x.py", "--port", "9190"], 900)
    д = json.loads(путь.read_text(encoding="utf-8"))
    assert д["pid"] == 12345
    assert д["порт"] == "9190"
    assert д["ttl_сек"] == 900
    assert д["обёртка_pid"] == os.getpid()
    assert "рабочий_каталог" in д


def test_сторож_ядра_ставится_обоим():
    """И обёртке, и серверу: иначе цепочка рвётся на середине.

    Если PDEATHSIG стоит только серверу, то смерть ОБОЛОЧКИ убьёт обёртку
    (у неё сторожа нет), а сервер останется — его родитель жив... точнее,
    только что умер, и тогда сработает его собственный сторож. Но если
    сторож стоит только обёртке, сервер переживёт обоих.
    """
    источник = СЦЕНАРИЙ.read_text(encoding="utf-8")
    # В теле обёртки — до запуска ребёнка.
    assert источник.index("умереть_с_родителем()") < источник.index(
        "процесс = subprocess.Popen(команда")
    # И внутри preexec_fn ребёнка.
    в_ребёнке = источник[источник.index("def в_ребёнке"):
                         источник.index("процесс = subprocess.Popen(команда")]
    assert "умереть_с_родителем()" in в_ребёнке
    assert "os.setpgrp()" in в_ребёнке


def test_отсутствие_prctl_называется_а_не_молчит(monkeypatch, capsys):
    """Сторож, который не встал, обязан сказать об этом."""
    м = _модуль()

    def нет_libc(*_а, **_к):
        raise OSError("нет libc")

    monkeypatch.setattr(м.ctypes, "CDLL", нет_libc)
    м.умереть_с_родителем()
    assert "сторож «умри с родителем» НЕ поставлен" in capsys.readouterr().err


def test_мёртвые_записки_убираются_на_входе(tmp_path, monkeypatch, capsys):
    """Записку убирает finally, но SIGKILL его не даёт — и записка начинает врать.

    Мёртвая запись о живом процессе хуже отсутствия записи: по ней принимают
    решения. Проверено на деле — после опыта с SIGKILL в каталоге осталось
    две таких записки.
    """
    м = _модуль()
    monkeypatch.setattr(м, "ЗАПИСКИ", tmp_path)
    # Заведомо мёртвый pid: берём свой дочерний процесс и дожидаемся конца.
    мёртвый = subprocess.run([sys.executable, "-c", "pass"])
    мёртвый_pid = 999999
    (tmp_path / f"{мёртвый_pid}.json").write_text("{}", encoding="utf-8")
    (tmp_path / f"{os.getpid()}.json").write_text("{}", encoding="utf-8")
    (tmp_path / "не-число.json").write_text("{}", encoding="utf-8")

    убрано = м.убрать_мёртвые_записки()
    assert мёртвый_pid in убрано
    assert not (tmp_path / f"{мёртвый_pid}.json").exists()
    # Записка о ЖИВОМ процессе остаётся, иначе уборка съедает нужное.
    assert (tmp_path / f"{os.getpid()}.json").exists()
    # Файл не по формату не ломает уборку и не удаляется наугад.
    assert (tmp_path / "не-число.json").exists()
    assert мёртвый.returncode == 0


def test_уборка_зовётся_из_запуска():
    источник = СЦЕНАРИЙ.read_text(encoding="utf-8")
    assert "убрать_мёртвые_записки()" in источник
    assert источник.index("убрать_мёртвые_записки()") < источник.index(
        "процесс = subprocess.Popen(команда")
