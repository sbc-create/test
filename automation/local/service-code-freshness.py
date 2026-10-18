#!/usr/bin/env python3
"""Исполняет ли служба тот код, который лежит на диске. Только чтение.

    python3 automation/local/service-code-freshness.py
    python3 automation/local/service-code-freshness.py --unit site-factory-mcp.service

Зачем. «Код доставлен» и «служба его исполняет» — разные утверждения, и за один
день 18.10 разница всплыла дважды:

* сборщик аналитики (`analytics-cabinet`) исполняет одно рабочее дерево, а
  правка второго прохода по 429 лежала в другом — правка была написана и
  проверена, но не работала;
* служба `site-factory-mcp` запущена 2026-10-12 17:42Z и держит код того
  момента, тогда как исправление сборки накладки записано 2026-10-18 20:39Z.
  Проверка `editorial-fix-installed.py` поэтому отвечала «правка НЕ
  подтверждена», и публикации на семи витринах оставались на паузе.

Оба раза признак один: **время запуска процесса раньше времени правки файлов,
которые он исполняет**. Инструмент считает именно это и ничего не предполагает
о причине.

Как считается:

  ЧТО ИСПОЛНЯЕТ   `ExecStart` юнита: путь скрипта или `-m <модуль>` плюс
                  `WorkingDirectory` — отсюда дерево кода;
  КОГДА ЗАПУЩЕН   поле 22 `/proc/<pid>/stat` (ядро), а не вывод `systemctl`:
                  `systemctl` вне профиля сессии;
  КОГДА ПРАВЛЕН   самый свежий mtime среди `*.py` того дерева кода.

Чего инструмент НЕ делает: не перезапускает службы и не советует это молча.
Перезапуск — действие владельца, и у него есть цена: прерванная партия
редактора или оборванный сбор. Инструмент называет расхождение, решение
остаётся за владельцем.
"""
from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import re
import sys

ЮНИТЫ = pathlib.Path("/etc/systemd/system")
ПРОЦЕССЫ = pathlib.Path("/proc")
#: Службы, чей код ведёт фабрика. Перечень закрытый: служба, которой здесь
#: нет, называется аргументом — расширять список по своей инициативе нельзя.
НАШИ = ("site-factory-mcp.service", "analytics-cabinet.service",
        "seo-tech-run.service", "seo-tech-publish.service",
        "editor-run.service")
ТИК = 100.0


def строки_юнита(имя: str) -> dict[str, str]:
    путь = ЮНИТЫ / имя
    итог: dict[str, str] = {}
    try:
        текст = путь.read_text(encoding="utf-8")
    except OSError:
        return итог
    for строка in текст.splitlines():
        строка = строка.strip()
        for ключ in ("ExecStart", "WorkingDirectory"):
            if строка.startswith(ключ + "=") and ключ not in итог:
                итог[ключ] = строка.split("=", 1)[1].strip()
    return итог


def дерево_кода(поля: dict[str, str]) -> pathlib.Path | None:
    """Каталог, в котором лежит исполняемый код службы."""
    exec_start = поля.get("ExecStart", "")
    рабочий = поля.get("WorkingDirectory", "")
    м = re.search(r"-m\s+([A-Za-z0-9_.]+)", exec_start)
    if м and рабочий:
        # Модуль ищется в рабочем каталоге: пакет верхнего уровня.
        верх = м.group(1).split(".")[0]
        путь = pathlib.Path(рабочий) / верх
        return путь if путь.is_dir() else pathlib.Path(рабочий)
    for кусок in exec_start.split():
        if кусок.endswith((".py", ".sh")) and кусок.startswith("/"):
            п = pathlib.Path(кусок)
            return п.parent if п.is_file() else None
    return pathlib.Path(рабочий) if рабочий else None


def свежесть_дерева(каталог: pathlib.Path) -> tuple[dt.datetime | None, str]:
    """Самый свежий mtime среди `*.py` и `*.sh` дерева и имя этого файла.

    Оболочечные скрипты считаются наравне: у части служб `ExecStart` — именно
    `.sh`, и правка в нём так же не доедет до живущего процесса.
    """
    новейший: tuple[float, str] = (0.0, "")
    for путь in list(каталог.rglob("*.py")) + list(каталог.rglob("*.sh")):
        if "__pycache__" in путь.parts:
            continue
        try:
            м = путь.stat().st_mtime
        except OSError:
            continue
        if м > новейший[0]:
            новейший = (м, str(путь))
    if not новейший[1]:
        return (None, "")
    return (dt.datetime.fromtimestamp(новейший[0], dt.timezone.utc),
            новейший[1])


def процесс_юнита(exec_start: str) -> tuple[int | None, dt.datetime | None]:
    """pid и время запуска по `/proc`, без `systemctl`."""
    м = re.search(r"-m\s+([A-Za-z0-9_.]+)", exec_start)
    признак = м.group(1) if м else ""
    if not признак:
        куски = [к for к in exec_start.split() if к.endswith((".py", ".sh"))]
        признак = куски[0] if куски else ""
    if not признак:
        return (None, None)
    try:
        загрузка = float((ПРОЦЕССЫ / "uptime").read_text().split()[0])
    except OSError:
        return (None, None)
    старт_системы = dt.datetime.now(dt.timezone.utc) - dt.timedelta(
        seconds=загрузка)
    мой = str(pathlib.Path.cwd())
    for каталог in ПРОЦЕССЫ.iterdir():
        if not каталог.name.isdigit():
            continue
        try:
            cmd = (каталог / "cmdline").read_bytes().replace(
                b"\0", b" ").decode("utf-8", "replace")
        except OSError:
            continue
        if признак not in cmd or "python3 -c" in cmd:
            continue
        try:
            # Свои же процессы отбрасываются: они лишь упоминают признак.
            if str((каталог / "cwd").resolve()) == мой:
                continue
            поля = (каталог / "stat").read_text().rsplit(") ", 1)[1].split()
            начало = старт_системы + dt.timedelta(
                seconds=float(поля[19]) / ТИК)
        except (OSError, IndexError, ValueError):
            continue
        return (int(каталог.name), начало)
    return (None, None)


def по_таймеру(имя: str) -> bool:
    """Есть ли у службы свой таймер.

    Служба по таймеру новый код подхватывает сама на следующем запуске:
    процесс между запусками не живёт. Поэтому «процесс не найден» у неё —
    нормальное состояние, а не пробел измерения, и путать эти два случая
    нельзя: иначе четыре строки из пяти выглядят как непроверенные.
    """
    основа = имя[:-len(".service")] if имя.endswith(".service") else имя
    return (ЮНИТЫ / f"{основа}.timer").is_file()


def главная(аргв=None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--unit", action="append", default=[])
    а = р.parse_args(аргв)
    юниты = а.unit or list(НАШИ)

    находок = 0
    не_измерено = 0
    print(f"{'служба':30} {'pid':8} {'запущен':17} {'код правлен':17} вывод")
    for имя in юниты:
        поля = строки_юнита(имя)
        if not поля.get("ExecStart"):
            print(f"{имя:30} {'—':8} {'юнит не прочитан':17} {'—':17} "
                  f"НЕ ИЗМЕРЕНО")
            не_измерено += 1
            continue
        каталог = дерево_кода(поля)
        pid, запуск = процесс_юнита(поля["ExecStart"])
        правлен, файл = (свежесть_дерева(каталог) if каталог and каталог.is_dir()
                         else (None, ""))
        if запуск is None and по_таймеру(имя):
            вывод = ("по таймеру: процесс между запусками не живёт, новый код "
                     "подхватится на следующем запуске")
        elif запуск is None:
            вывод = "процесс не найден — служба не запущена либо признак другой"
            не_измерено += 1
        elif правлен is None:
            вывод = f"код не найден ({каталог}) — НЕ ИЗМЕРЕНО"
            не_измерено += 1
        elif правлен > запуск:
            вывод = (f"ИСПОЛНЯЕТ СТАРЫЙ КОД: правка новее запуска на "
                     f"{(правлен - запуск).total_seconds() / 3600:.1f} ч")
            находок += 1
        else:
            вывод = "код не новее запуска"
        print(f"{имя:30} {str(pid or '—'):8} "
              f"{(запуск.strftime('%m-%d %H:%M') + 'Z') if запуск else '—':17} "
              f"{(правлен.strftime('%m-%d %H:%M') + 'Z') if правлен else '—':17} "
              f"{вывод}")
        if правлен and запуск and правлен > запуск and файл:
            print(f"{'':30} {'':8} самый свежий файл: {файл}")

    print(f"\nслужб с устаревшим кодом: {находок}; не измерено: {не_измерено}")
    print("Перезапуск инструмент не делает и молча не советует: у него есть "
          "цена (прерванная партия редактора, оборванный сбор), и решение "
          "остаётся за владельцем.")
    return 1 if находок else 0


if __name__ == "__main__":
    raise SystemExit(главная())
