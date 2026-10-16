#!/usr/bin/env python3
"""Идёт ли ПРЯМО СЕЙЧАС редакционный запуск `editor-run.sh`. Только чтение.

Зачем отдельный инструмент и чем он отличается от `editor-run-audit.py`. Аудит
отвечает на вопрос «был ли запуск в названном окне и что он сделал» — по двум
журналам, то есть ПОСЛЕ факта. Здесь нужен другой ответ: можно ли сейчас
безопасно перезапустить `site-factory-mcp.service`, не оборвав публикацию на
середине. «Был запуск» и «запуск идёт» — разные утверждения.

ПОПРАВКА К МОЕЙ ЖЕ ПРЕЖНЕЙ ПРОВЕРКЕ. Я считала активность по времени
изменения файла блокировки `var/editor-runs/run.lock` и сообщила «активная
публикация с 16:35:00Z», когда та уже завершилась в 16:52:04Z. Мера была не та:
обёртка открывает этот файл строкой `exec 9>"$STATE/run.lock"` при КАЖДОМ
срабатывании таймера — каждые пять минут, в том числе когда лёгкая проверка
`editor-gate` сразу отказывает и модель не запускается. То есть свежая отметка
времени у `run.lock` доказывает лишь то, что обёртка открывала файл, а не то,
что внутри кто-то работает. Тот же класс ошибки, что я правлю в чужих
проверках: признак, общий для «работает» и «не работает», предъявлен как
различающий.

Признаки здесь независимые, и каждый измеряет именно удержание работы:

* **захват блокировки.** Обёртка держит `flock` на `run.lock` всё время
  запуска. Проверка пробует взять ту же блокировку неблокирующе и сразу
  отпускает: взялась — запуска нет, не взялась — кто-то держит. Файл
  открывается только на чтение, поэтому ни содержимое, ни длина не меняются
  (`flock(2)` не требует доступа на запись);
* **последняя запись в `runs.jsonl`.** У завершённого запуска есть
  `finished_at`; запись без него означает запуск, который ещё идёт или умер, не
  дописав итог;
* **каталог запуска без итоговых файлов** — тот же признак со стороны
  файловой системы;
* **процесс обёртки в `/proc`** — по строке запуска, без обращения к systemd
  (журнал этой службы учётной записи сессии недоступен).

Вывод — одно из трёх: `RUNNING` (перезапуск MCP ждёт), `IDLE` (окно открыто) и
`UNKNOWN` (признаки противоречат друг другу; тогда перезапуск тоже ждёт, потому
что неизвестность не равна отсутствию работы).

    python3 automation/local/editor-run-state.py            # человекочитаемо
    python3 automation/local/editor-run-state.py --json     # для сценариев
"""
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import json
import os
import pathlib

СОСТОЯНИЕ = pathlib.Path("/home/claude/wt-portable-site-cell-01/var/editor-runs")
БЛОКИРОВКА = СОСТОЯНИЕ / "run.lock"
ЖУРНАЛ = СОСТОЯНИЕ / "runs.jsonl"
#: Строка запуска обёртки, по которой её процесс отличим от чужих.
ОБЁРТКА = "editor-run.sh"


def _сейчас() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def блокировка_занята() -> tuple[bool | None, str]:
    """True — кто-то держит `flock`; False — свободна; None — не измерить."""
    if not БЛОКИРОВКА.is_file():
        return None, f"файла блокировки нет: {БЛОКИРОВКА}"
    фд = None
    try:
        фд = os.open(БЛОКИРОВКА, os.O_RDONLY)
    except OSError as сбой:
        return None, f"файл блокировки не открыть на чтение: {сбой}"
    try:
        fcntl.flock(фд, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return True, "блокировка удерживается другим процессом"
    except OSError as сбой:
        return None, f"flock не выполнить: {сбой}"
    else:
        fcntl.flock(фд, fcntl.LOCK_UN)
        return False, "блокировка свободна"
    finally:
        os.close(фд)


def последняя_запись() -> dict:
    if not ЖУРНАЛ.is_file():
        return {"есть": False, "причина": f"журнала нет: {ЖУРНАЛ}"}
    строки = [с for с in ЖУРНАЛ.read_text(encoding="utf-8").splitlines()
              if с.strip()]
    if not строки:
        return {"есть": False, "причина": "журнал пуст"}
    try:
        д = json.loads(строки[-1])
    except json.JSONDecodeError as сбой:
        return {"есть": False, "причина": f"последняя строка не JSON: {сбой}"}
    return {
        "есть": True,
        "run_id": д.get("run_id"),
        "started_at": д.get("started_at"),
        "finished_at": д.get("finished_at"),
        "verdict": д.get("verdict"),
        "завершена": bool(д.get("finished_at")),
    }


def каталоги_без_итога() -> list[str]:
    """Запуски, у которых есть рабочий каталог, но нет файлов итога.

    Где лежит итог — измерено, а не предположено: обёртка пишет
    `$STATE/$RUN_ID.run.json` и `$STATE/$RUN_ID.verify.json` РЯДОМ с каталогом
    `run-$RUN_ID`, а не внутри него (внутри — рабочие файлы запуска: выгрузки
    страниц, черновики). Первая версия этой функции искала итог внутри
    каталога и объявила «без итога» все 168 запусков, включая завершённые, —
    то есть признак, общий для всех, снова оказался предъявлен как
    различающий. Теперь ищется ровно там, где файл создаётся.
    """
    если = []
    for к in sorted(СОСТОЯНИЕ.glob("run-*")):
        if not к.is_dir():
            continue
        ид = к.name[len("run-"):]
        итоги = [СОСТОЯНИЕ / f"{ид}.run.json", СОСТОЯНИЕ / f"{ид}.verify.json"]
        if not any(ф.is_file() for ф in итоги):
            если.append(к.name)
    return если


def процессы_обёртки() -> list[dict]:
    найдено = []
    корень = pathlib.Path("/proc")
    for п in корень.iterdir():
        if not п.name.isdigit():
            continue
        try:
            строка = (п / "cmdline").read_bytes().decode("utf-8", "replace")
        except OSError:
            continue
        if ОБЁРТКА in строка:
            найдено.append({"pid": int(п.name),
                            "cmdline": строка.replace("\x00", " ").strip()})
    return найдено


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--json", action="store_true", help="машинный вывод")
    опции = р.parse_args(аргв)

    занята, пояснение = блокировка_занята()
    запись = последняя_запись()
    без_итога = каталоги_без_итога()
    процессы = процессы_обёртки()

    # Решение принимается по захвату блокировки: это единственный признак,
    # который обёртка удерживает ровно на время работы. Остальные — проверка
    # на согласованность; расхождение даёт UNKNOWN, а не тихий выбор.
    признаки_за_работу = [
        занята is True,
        запись.get("есть") and not запись.get("завершена"),
        bool(процессы),
    ]
    if занята is None:
        состояние = "UNKNOWN"
    elif занята:
        состояние = "RUNNING"
    elif any(признаки_за_работу):
        состояние = "UNKNOWN"
    else:
        состояние = "IDLE"

    итог = {
        "measured_at": _сейчас(),
        "state": состояние,
        "lock_held": занята,
        "lock_note": пояснение,
        "lock_mtime": (dt.datetime.fromtimestamp(БЛОКИРОВКА.stat().st_mtime,
                                                 dt.timezone.utc)
                       .strftime("%Y-%m-%dT%H:%M:%SZ")
                       if БЛОКИРОВКА.is_file() else None),
        "last_record": запись,
        "run_dirs_without_result": без_итога,
        "wrapper_processes": процессы,
        "mcp_restart_allowed": состояние == "IDLE",
    }
    if опции.json:
        print(json.dumps(итог, ensure_ascii=False, indent=1))
        return 0 if состояние == "IDLE" else 1

    print(f"состояние editor-run.sh: {состояние}")
    print(f"  блокировка: {пояснение}")
    print(f"  отметка времени файла блокировки: {итог['lock_mtime']} "
          "(доказательством работы НЕ является: обёртка открывает файл каждые "
          "5 минут)")
    if запись.get("есть"):
        print(f"  последний запуск: {запись['run_id']} "
              f"{запись['started_at']} → {запись['finished_at']} "
              f"{запись['verdict']}")
    else:
        print(f"  журнал: {запись.get('причина')}")
    print(f"  каталогов без итоговых файлов: {len(без_итога)}"
          + (f" ({', '.join(без_итога[-3:])})" if без_итога else ""))
    print(f"  процессов обёртки: {len(процессы)}")
    print("  перезапуск site-factory-mcp: "
          + ("разрешён" if состояние == "IDLE" else "ждать"))
    return 0 if состояние == "IDLE" else 1


if __name__ == "__main__":
    raise SystemExit(главное())
