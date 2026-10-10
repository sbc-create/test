#!/usr/bin/env python3
"""Наблюдение дрейфа памяти по ЦИКЛАМ ОБНОВЛЕНИЯ, а не по одному замеру.

Зачем. «Перезапустил — стало лучше» измерением не является: после перезапуска
RSS мал у любой витрины. Доказывает причину только связка «снимок перезаписан
тем же содержимым → витрина перечитала его → RSS подрос», повторённая несколько
циклов подряд.

Поэтому на каждом шаге пишутся обе стороны:

* память витрин (`showcase-memory-report.py`, тот же код, что в замере);
* отпечаток снимка каждой витрины: `mtime`, размер и sha256. Смена `mtime` при
  неизменных размере и хеше — это и есть лишняя перезапись, из-за которой
  читатель заново разбирает полмиллиона объектов.

Ничего не меняет: только чтение `/proc` и файлов данных.

    python3 automation/local/memory-drift-watch.py --minutes 45 --every 300
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
ЗАМЕР = КОРЕНЬ / "automation" / "local" / "showcase-memory-report.py"
ДАННЫЕ = Path("/srv")
КУСОК = 1024 * 1024


def _замер():
    спец = importlib.util.spec_from_file_location("showcase_memory_report", ЗАМЕР)
    м = importlib.util.module_from_spec(спец)
    sys.modules["showcase_memory_report"] = м
    спец.loader.exec_module(м)
    return м


def _сумма(путь: Path) -> str:
    х = hashlib.sha256()
    with путь.open("rb") as ф:
        while кусок := ф.read(КУСОК):
            х.update(кусок)
    return х.hexdigest()[:16]


def отпечатки(витрина: str) -> dict[str, dict]:
    """mtime, размер и хеш снимков витрины — по файлу."""
    итог: dict[str, dict] = {}
    каталог = ДАННЫЕ / витрина / "data"
    if not каталог.is_dir():
        return итог
    for файл in sorted(каталог.glob("*.json")):
        if "catalog" not in файл.name and "details" not in файл.name:
            continue
        try:
            с = файл.stat()
            итог[файл.name] = {"mtime": int(с.st_mtime), "size": с.st_size,
                               "sha": _сумма(файл)}
        except OSError as сбой:
            итог[файл.name] = {"error": str(сбой)}
    return итог


def шаг(м) -> dict:
    витрины = м.дрейф(м.собрать())
    return {
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "host": м.хост(),
        "showcases": {в["showcase"]: {"rss_mib": в["rss_mib"],
                                      "hwm_mib": в["hwm_mib"],
                                      "age_s": в["age_s"],
                                      "snapshot": отпечатки(в["showcase"])}
                      for в in витрины},
    }


def свод(шаги: list[dict]) -> list[str]:
    """Что именно доказали шаги: лишние перезаписи и прирост RSS."""
    строки: list[str] = []
    if len(шаги) < 2:
        return ["шагов меньше двух: выводить нечего"]
    имена = sorted(шаги[-1]["showcases"])
    строки.append(f"{'витрина':26} {'RSS нач':>8} {'RSS кон':>8} {'прирост':>8} "
                  f"{'перезаписей':>12} {'из них впустую':>15}")
    for имя in имена:
        первый = шаги[0]["showcases"].get(имя)
        последний = шаги[-1]["showcases"].get(имя)
        if not первый or not последний:
            continue  # витрина появилась или исчезла между шагами
        перезаписей = впустую = 0
        for файл, было in первый["snapshot"].items():
            прежний = было
            for ш in шаги[1:]:
                стало = (ш["showcases"].get(имя) or {}).get("snapshot", {}).get(файл)
                if not стало or "error" in стало or "error" in прежний:
                    continue
                if стало["mtime"] != прежний["mtime"]:
                    перезаписей += 1
                    if (стало["sha"] == прежний["sha"]
                            and стало["size"] == прежний["size"]):
                        впустую += 1
                прежний = стало
        строки.append(f"{имя[:26]:26} {первый['rss_mib']:8} "
                      f"{последний['rss_mib']:8} "
                      f"{последний['rss_mib'] - первый['rss_mib']:+8} "
                      f"{перезаписей:12} {впустую:15}")
    п, к = шаги[0]["host"], шаги[-1]["host"]
    строки.append(f"\nMemAvailable {п['mem_available_mib']} → "
                  f"{к['mem_available_mib']} МиБ; oom_kill "
                  f"{п['oom_kill_total']} → {к['oom_kill_total']}")
    if к["oom_kill_total"] != п["oom_kill_total"]:
        строки.append("ВНИМАНИЕ: за время наблюдения ядро убило процесс — "
                      "кого именно, видно только в /var/log/kern.log (root)")
    return строки


def главное(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description="наблюдение дрейфа памяти витрин")
    р.add_argument("--minutes", type=float, default=45.0)
    р.add_argument("--every", type=int, default=300, help="секунд между шагами")
    р.add_argument("--out", default="", help="файл JSONL; по умолчанию в artifacts/")
    а = р.parse_args(аргв)

    м = _замер()
    метка = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    файл = Path(а.out) if а.out else (
        КОРЕНЬ / "artifacts" / f"memory-drift-{метка}.jsonl")
    файл.parent.mkdir(parents=True, exist_ok=True)

    конец = time.monotonic() + а.minutes * 60
    шаги: list[dict] = []
    while True:
        ш = шаг(м)
        шаги.append(ш)
        with файл.open("a", encoding="utf-8") as ф:
            ф.write(json.dumps(ш, ensure_ascii=False) + "\n")
        print(f"шаг {len(шаги)}: {ш['at']}, MemAvailable "
              f"{ш['host']['mem_available_mib']} МиБ", flush=True)
        if time.monotonic() >= конец:
            break
        time.sleep(min(а.every, max(1, конец - time.monotonic())))

    print()
    for строка in свод(шаги):
        print(строка)
    print(f"\nшаги: {файл}")
    return 0


if __name__ == "__main__":
    sys.exit(главное())
