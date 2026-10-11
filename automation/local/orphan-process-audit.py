#!/usr/bin/env python3
"""Перепись процессов витрин: кто обслуживает сеть, а кто остался от проб.

Только чтение `/proc` и конфигураций nginx. Ничего не останавливает и не
меняет: инструмент даёт ОСНОВАНИЕ для решения, а решение — отдельный шаг.

Почему именно так считается
---------------------------

Первая попытка этой переписи 2026-10-11 определяла порт процесса по его
сокетам (`/proc/<pid>/fd` + `/proc/net/tcp`) и записала в сироты ПОЛОВИНУ
боевых витрин: каталог `fd` читается не для всех процессов, и «порт не найден»
было истолковано как «порт не слушается». Это ровно та ошибка, из-за которой
можно остановить работающий сайт.

Поэтому признак строится на двух независимых источниках, каждый из которых
читается для любого процесса:

* **порт из командной строки** (`--port N`) — эти серверы всегда получают его
  аргументом; сверяется с портами, объявленными в конфигурации nginx;
* **cgroup**: боевая витрина живёт в своём `*.service`, проба — в сеансовой
  области (`session-*.scope`) или вообще без юнита.

Сиротой считается процесс, у которого порт НЕ объявлен в nginx **и** который не
принадлежит службе. Несовпадение двух признаков — не вывод, а повод разбираться
руками: такой процесс помечается `спорно` и в список на остановку не попадает.

    python3 automation/local/orphan-process-audit.py            # перепись
    python3 automation/local/orphan-process-audit.py --json     # машинный вид
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ПРОЦ = Path("/proc")
NGINX = Path("/etc/nginx")
ТАКТ = 100.0


def порты_nginx() -> dict[int, list[str]]:
    """Порт петли → файлы конфигурации, где он объявлен."""
    итог: dict[int, list[str]] = {}
    if not NGINX.is_dir():
        return итог
    for путь in NGINX.rglob("*"):
        if not путь.is_file():
            continue
        try:
            текст = путь.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for м in re.finditer(r"127\.0\.0\.1:(\d+)", текст):
            итог.setdefault(int(м.group(1)), []).append(путь.name)
    return итог


def _поле(текст: str, имя: str, по_умолчанию: str = "") -> str:
    м = re.search(rf"^{имя}:\s+(\S+)", текст, re.M)
    return м.group(1) if м else по_умолчанию


def процесс(pid: int, загрузка: float) -> dict | None:
    место = ПРОЦ / str(pid)
    try:
        команда = (место / "cmdline").read_bytes().decode("utf-8", "replace")
        состояние = (место / "status").read_text()
        стат = (место / "stat").read_text().rsplit(") ", 1)[1].split()
    except (OSError, IndexError):
        return None
    if "--port" not in команда:
        return None
    части = команда.split("\0")
    порт = None
    for i, ч in enumerate(части):
        if ч == "--port" and i + 1 < len(части):
            порт = int(части[i + 1]) if части[i + 1].isdigit() else None
    try:
        группа = (место / "cgroup").read_text().strip().rsplit("/", 1)[-1]
    except OSError:
        группа = ""
    return {
        "pid": pid,
        "ppid": int(_поле(состояние, "PPid", "0")),
        "uid": int(_поле(состояние, "Uid", "0")),
        "rss_mib": int(_поле(состояние, "VmRSS", "0").rstrip()) // 1024
        if _поле(состояние, "VmRSS") else 0,
        "age_h": round((загрузка - float(стат[19]) / ТАКТ) / 3600, 1),
        "port": порт,
        "cgroup": группа,
        "cmd": команда.replace("\0", " ").strip(),
    }


def собрать() -> tuple[list[dict], dict[int, list[str]]]:
    объявленные = порты_nginx()
    загрузка = float((ПРОЦ / "uptime").read_text().split()[0])
    найдено = []
    for запись in ПРОЦ.iterdir():
        if not запись.name.isdigit():
            continue
        п = процесс(int(запись.name), загрузка)
        if not п:
            continue
        в_nginx = п["port"] in объявленные
        служба = bool(re.search(r"\.service$", п["cgroup"]))
        if в_nginx and служба:
            п["вид"] = "обслуживает"
        elif not в_nginx and not служба:
            п["вид"] = "сирота"
        else:
            # Признаки расходятся: это не вывод, а повод смотреть руками.
            п["вид"] = "спорно"
        п["in_nginx"] = в_nginx
        п["service"] = служба
        найдено.append(п)
    return sorted(найдено, key=lambda п: (п["вид"], -п["rss_mib"])), объявленные


def главное(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description="перепись процессов витрин")
    р.add_argument("--json", action="store_true")
    а = р.parse_args(аргв)
    процессы, объявленные = собрать()
    память = (ПРОЦ / "meminfo").read_text()
    доступно = int(_поле(память, "MemAvailable")) // 1024
    своп = int(_поле(память, "SwapTotal")) // 1024
    сироты = [п for п in процессы if п["вид"] == "сирота"]
    спорные = [п for п in процессы if п["вид"] == "спорно"]
    свод = {
        "mem_available_mib": доступно,
        "swap_total_mib": своп,
        "editor_threshold_mib": 2048,
        "editor_can_start": доступно >= 2048,
        "orphan_count": len(сироты),
        "orphan_rss_mib": sum(п["rss_mib"] for п in сироты),
        "disputed_count": len(спорные),
        "processes": процессы,
    }
    if а.json:
        print(json.dumps(свод, ensure_ascii=False, indent=2))
        return 0
    print(f"{'pid':>8} {'вид':12} {'RSS':>6} {'порт':>6} {'в nginx':>8} "
          f"{'служба':>7} {'возраст':>8}  команда")
    for п in процессы:
        print(f"{п['pid']:>8} {п['вид']:12} {п['rss_mib']:>6} "
              f"{str(п['port'] or '—'):>6} {'да' if п['in_nginx'] else 'нет':>8} "
              f"{'да' if п['service'] else 'нет':>7} {п['age_h']:>7} ч  "
              f"{п['cmd'][:78]}")
    print(f"\nMemAvailable {доступно} МиБ, swap {своп} МиБ; порог редактора "
          f"2048 МиБ — {'хватает' if доступно >= 2048 else 'НЕ хватает'}")
    print(f"сирот: {len(сироты)}, их память: {свод['orphan_rss_mib']} МиБ; "
          f"спорных: {len(спорные)}")
    if спорные:
        print("спорные в список на остановку НЕ входят — разбирать руками:")
        for п in спорные:
            print(f"   {п['pid']} порт {п['port']} в nginx "
                  f"{'да' if п['in_nginx'] else 'нет'}, служба "
                  f"{'да' if п['service'] else 'нет'}: {п['cmd'][:70]}")
    return 0


if __name__ == "__main__":
    sys.exit(главное())
