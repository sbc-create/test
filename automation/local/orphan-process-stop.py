#!/usr/bin/env python3
"""Остановка процессов-сирот витрин по ИМЕННОМУ списку, со сверкой перед каждым.

Зачем отдельно от переписи. Перепись (`orphan-process-audit.py`) даёт основание,
а остановка — действие, и у действия свои требования:

* **именной список.** Останавливается только то, что названо в `--pid`:
  «останови всё, что инструмент счёл сиротой» — это доверие измерению, которое
  уже один раз ошиблось (первая версия переписи записала в сироты половину
  боевых витрин, потому что считала порт по `/proc/<pid>/fd`, а он читается не
  для всех процессов);
* **сверка перед каждым шагом.** Перед сигналом снова читаются командная строка,
  порт и cgroup. Если процесс не тот, что был в переписи, — отказ: номера
  переиспользуются, и остановить можно не то;
* **отказ при малейшем сомнении.** Порт в конфигурации nginx, принадлежность
  `*.service`, чужой владелец — отказ без вариантов;
* **по одному, с проверкой между шагами.** После каждого — пауза и измерение
  памяти; публичные страницы проверяются отдельным инструментом до и после.

Без `--confirm` ничего не посылается: печатается план.

    python3 automation/local/orphan-process-stop.py --pid 123 --pid 456
    python3 automation/local/orphan-process-stop.py --pid 123 --confirm
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import re
import signal
import sys
import time
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[1].parent
ПЕРЕПИСЬ = Path(__file__).resolve().parent / "orphan-process-audit.py"
ПРОЦ = Path("/proc")
ПАУЗА = 2.0


def _перепись():
    спец = importlib.util.spec_from_file_location("orphan_process_audit", ПЕРЕПИСЬ)
    м = importlib.util.module_from_spec(спец)
    sys.modules["orphan_process_audit"] = м
    спец.loader.exec_module(м)
    return м


def _память() -> int:
    текст = (ПРОЦ / "meminfo").read_text()
    return int(re.search(r"MemAvailable:\s+(\d+)", текст).group(1)) // 1024


def _жив(pid: int) -> bool:
    """Жив ли процесс. Зомби — не жив, хотя каталог `/proc/<pid>` ещё есть.

    Сироты, подобранные init, исчезают сразу, поэтому на хосте это незаметно.
    Но процесс, чей родитель ещё не вызвал `wait`, остаётся записью в состоянии
    `Z`, и проверка «каталог существует» объявляла бы остановленный процесс
    «висящим». Поймано проверкой остановки 2026-10-11: память уже освобождена,
    а инструмент сообщал об отказе.
    """
    место = ПРОЦ / str(pid)
    if not место.exists():
        return False
    try:
        состояние = (место / "status").read_text()
    except OSError:
        return False
    return _поле_состояния(состояние, "State") != "Z"


def _поле_состояния(текст: str, имя: str) -> str:
    м = re.search(rf"^{имя}:\s+(\S+)", текст, re.M)
    return м.group(1) if м else ""


def проверить(pid: int, м, объявленные: dict[int, list[str]]) -> tuple[bool, str]:
    """Можно ли останавливать ИМЕННО этот процесс сейчас."""
    загрузка = float((ПРОЦ / "uptime").read_text().split()[0])
    п = м.процесс(pid, загрузка)
    if not п:
        return False, "процесса нет или это не сервер витрины"
    if п["uid"] != os.getuid():
        return False, f"владелец uid {п['uid']}, не наш: останавливать не вправе"
    if п["port"] in объявленные:
        return False, (f"порт {п['port']} объявлен в nginx "
                       f"({', '.join(объявленные[п['port']])}): обслуживает сеть")
    if re.search(r"\.service$", п["cgroup"]):
        return False, f"процесс принадлежит службе {п['cgroup']}"
    if "/srv/" in п["cmd"] and "/releases/" in п["cmd"] and п["port"] in объявленные:
        return False, "выпуск из /srv на объявленном порту"
    return True, (f"сирота: порт {п['port']} вне nginx, вне службы, "
                  f"возраст {п['age_h']} ч, RSS {п['rss_mib']} МиБ")


def главное(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description="остановка процессов-сирот витрин")
    р.add_argument("--pid", type=int, action="append", required=True,
                   help="номер процесса; можно повторять")
    р.add_argument("--confirm", action="store_true",
                   help="без него сигналы не посылаются")
    а = р.parse_args(аргв)

    м = _перепись()
    объявленные = м.порты_nginx()
    было = _память()
    print(f"MemAvailable до: {было} МиБ; порог редактора 2048 МиБ")
    остановлено, отказано, освобождено = [], [], 0

    for pid in а.pid:
        можно, причина = проверить(pid, м, объявленные)
        if not можно:
            print(f"   [отказ] {pid}: {причина}")
            отказано.append((pid, причина))
            continue
        rss = м.процесс(pid, float((ПРОЦ / "uptime").read_text().split()[0]))["rss_mib"]
        if not а.confirm:
            print(f"   [план ] {pid}: {причина}")
            continue
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError as сбой:
            print(f"   [сбой ] {pid}: {сбой}")
            отказано.append((pid, str(сбой)))
            continue
        # Ждём ухода; SIGKILL не посылается: процесс, не ответивший на TERM,
        # разбирается отдельно, а не добивается заодно.
        ушёл = False
        for _ in range(10):
            time.sleep(ПАУЗА / 2)
            if not _жив(pid):
                ушёл = True
                break
        if ушёл:
            освобождено += rss
            остановлено.append(pid)
            print(f"   [стоп ] {pid}: остановлен, RSS был {rss} МиБ, "
                  f"MemAvailable {_память()} МиБ")
        else:
            print(f"   [висит] {pid}: не ответил на TERM за 10 с — оставляю, "
                  "разбирать отдельно")
            отказано.append((pid, "не ответил на SIGTERM"))
        time.sleep(ПАУЗА)

    стало = _память()
    print(f"\nостановлено: {len(остановлено)} {остановлено or ''}")
    print(f"отказов: {len(отказано)}")
    for pid, причина in отказано:
        print(f"   {pid}: {причина}")
    if а.confirm:
        print(f"MemAvailable {было} → {стало} МиБ (+{стало - было}); "
              f"сумма RSS остановленных {освобождено} МиБ; порог редактора "
              f"2048 МиБ — {'хватает' if стало >= 2048 else 'НЕ хватает'}")
    else:
        print("сигналы не посылались: это план. Для исполнения — --confirm")
    return 0 if not отказано else 1


if __name__ == "__main__":
    sys.exit(главное())
