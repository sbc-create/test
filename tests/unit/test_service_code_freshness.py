"""REQ-OPS-SERVICE-CODE: «код доставлен» и «служба его исполняет» — разное.

За один день 18.10 разница всплыла дважды:

* сборщик аналитики исполняет одно рабочее дерево, а правка второго прохода по
  429 лежала в другом — правка была написана и проверена, но не работала;
* служба `site-factory-mcp` запущена 2026-10-12 17:42Z и держит код того
  момента, тогда как исправление сборки накладки записано 2026-10-18 20:39Z.
  Из-за этого публикации описаний на семи витринах Lords/Zona остались на
  паузе, хотя правка уже существовала.

Признак один: время запуска процесса раньше времени правки файлов, которые он
исполняет. Проверено на живой системе 18.10: `site-factory-mcp` — pid 1499831,
147 часов разницы; три службы по таймеру — не находка, они подхватят код на
следующем запуске.

Здесь закреплены различения, без которых вывод был бы ложным:

* служба ПО ТАЙМЕРУ между запусками не живёт, и «процесс не найден» у неё —
  нормальное состояние, а не пробел измерения;
* нечитаемый юнит — «НЕ ИЗМЕРЕНО», а не «код свежий»;
* инструмент ничего не перезапускает и не советует это молча.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

ПУТЬ = (Path(__file__).resolve().parents[2] / "automation" / "local"
        / "service-code-freshness.py")


def _модуль():
    имя = "service_code_freshness"
    спец = importlib.util.spec_from_file_location(имя, ПУТЬ)
    м = importlib.util.module_from_spec(спец)
    sys.modules[имя] = м
    спец.loader.exec_module(м)
    return м


МОД = _модуль()


def _юнит(tmp_path: Path, имя: str, *, exec_start: str, рабочий: str,
          таймер: bool = False) -> None:
    (tmp_path / имя).write_text(
        f"[Service]\nExecStart={exec_start}\nWorkingDirectory={рабочий}\n",
        encoding="utf-8")
    if таймер:
        основа = имя[:-len(".service")]
        (tmp_path / f"{основа}.timer").write_text("[Timer]\n", encoding="utf-8")


def _прогон(monkeypatch, tmp_path, *, юниты, процесс, свежесть, аргв):
    monkeypatch.setattr(МОД, "ЮНИТЫ", tmp_path)
    monkeypatch.setattr(МОД, "процесс_юнита", lambda e: процесс)
    monkeypatch.setattr(МОД, "свежесть_дерева", lambda к: свежесть)
    monkeypatch.setattr(МОД, "дерево_кода", lambda п: tmp_path)
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        код = МОД.главная(аргв)
    return код, буфер.getvalue()


ЗАПУСК = dt.datetime(2026, 10, 12, 17, 42, tzinfo=dt.timezone.utc)
ПРАВКА_ПОЗЖЕ = dt.datetime(2026, 10, 18, 20, 39, tzinfo=dt.timezone.utc)
ПРАВКА_РАНЬШЕ = dt.datetime(2026, 10, 10, 9, 0, tzinfo=dt.timezone.utc)


def test_служба_со_старым_кодом_это_находка(monkeypatch, tmp_path):
    _юнит(tmp_path, "a.service", exec_start="/usr/bin/python3 -m factory.qwen.mcp",
          рабочий=str(tmp_path))
    код, вывод = _прогон(monkeypatch, tmp_path, юниты=["a.service"],
                         процесс=(1499831, ЗАПУСК),
                         свежесть=(ПРАВКА_ПОЗЖЕ, str(tmp_path / "editorial.py")),
                         аргв=["--unit", "a.service"])
    assert код == 1
    assert "ИСПОЛНЯЕТ СТАРЫЙ КОД" in вывод
    часов = (ПРАВКА_ПОЗЖЕ - ЗАПУСК).total_seconds() / 3600
    assert f"{часов:.1f} ч" in вывод, (
        "разница печатается числом, а не словом «устарел»: по ней видно, "
        "сколько именно живёт старый код")
    assert "editorial.py" in вывод, "самый свежий файл обязан быть назван"


def test_код_не_новее_запуска_не_находка(monkeypatch, tmp_path):
    _юнит(tmp_path, "a.service", exec_start="/usr/bin/python3 -m factory.x",
          рабочий=str(tmp_path))
    код, вывод = _прогон(monkeypatch, tmp_path, юниты=["a.service"],
                         процесс=(42, ЗАПУСК),
                         свежесть=(ПРАВКА_РАНЬШЕ, str(tmp_path / "x.py")),
                         аргв=["--unit", "a.service"])
    assert код == 0
    assert "код не новее запуска" in вывод


def test_служба_по_таймеру_не_пробел(monkeypatch, tmp_path):
    """Между запусками процесса нет — это норма, а не непроверенность."""
    _юнит(tmp_path, "b.service", exec_start="/usr/bin/python3 -m factory.y",
          рабочий=str(tmp_path), таймер=True)
    код, вывод = _прогон(monkeypatch, tmp_path, юниты=["b.service"],
                         процесс=(None, None),
                         свежесть=(ПРАВКА_ПОЗЖЕ, str(tmp_path / "y.py")),
                         аргв=["--unit", "b.service"])
    assert код == 0
    assert "по таймеру" in вывод
    assert "не измерено: 0" in вывод


def test_служба_без_таймера_и_без_процесса_это_пробел(monkeypatch, tmp_path):
    _юнит(tmp_path, "c.service", exec_start="/usr/bin/python3 -m factory.z",
          рабочий=str(tmp_path))
    код, вывод = _прогон(monkeypatch, tmp_path, юниты=["c.service"],
                         процесс=(None, None),
                         свежесть=(ПРАВКА_ПОЗЖЕ, str(tmp_path / "z.py")),
                         аргв=["--unit", "c.service"])
    assert код == 0, "пробел измерения сам по себе не находка"
    assert "процесс не найден" in вывод
    assert "не измерено: 1" in вывод


def test_нечитаемый_юнит_это_не_свежий_код(monkeypatch, tmp_path):
    monkeypatch.setattr(МОД, "ЮНИТЫ", tmp_path)
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        код = МОД.главная(["--unit", "нет-такого.service"])
    вывод = буфер.getvalue()
    assert "НЕ ИЗМЕРЕНО" in вывод and "юнит не прочитан" in вывод
    assert код == 0


def test_оболочечные_скрипты_считаются(tmp_path):
    """У части служб ExecStart — `.sh`, и правка в нём так же не доедет."""
    (tmp_path / "run.sh").write_text("echo", encoding="utf-8")
    когда, файл = МОД.свежесть_дерева(tmp_path)
    assert когда is not None and файл.endswith("run.sh")


def test_инструмент_ничего_не_перезапускает():
    тело = ПУТЬ.read_text(encoding="utf-8")
    assert "systemctl" in тело, "упоминание в тексте — объяснение, а не вызов"
    assert "subprocess" not in тело, "перезапускать службы инструмент не вправе"
    assert "Перезапуск инструмент не делает" in тело
