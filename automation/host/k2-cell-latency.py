#!/usr/bin/env python3
"""Задержка и вес восьми витрин НА УЗЛЕ — для разбора зависаний 504.

Зачем. Публичный 504 означает только одно: nginx не получил ответ за
`proxy_read_timeout 30s`. Чей это предел — сети, nginx или самой витрины —
снаружи не видно. Инструмент измеряет локально, в обход nginx: время ответа
каждой ячейки на её порту, её RSS, время старта процесса и свободную память
узла. Этого достаточно, чтобы отличить «витрина думает дольше 30 с» от
«витрина отвечает мгновенно, а ждал кто-то другой».

Главная выбрана намеренно: это самая тяжёлая сборка (лента и полки), и именно
на ней измерен публичный 504.

Запуск на узле:  k2-cell-latency.py [site_id ...]
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ОПИСЬ = Path("/home/k2deploy/stage/MANIFEST.json")


def витрины() -> dict[str, dict]:
    опись = json.loads(ОПИСЬ.read_text(encoding="utf-8"))
    return опись.get("cells") or {}


def память() -> dict[str, int]:
    итог = {}
    for строка in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
        ключ, _, хвост = строка.partition(":")
        if ключ in ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree"):
            итог[ключ] = int(хвост.split()[0]) // 1024
    return итог


def процесс(порт: int) -> dict:
    """RSS и время старта процесса, слушающего порт. Пусто — не нашли."""
    try:
        вывод = subprocess.run(["ss", "-ltnp", f"sport = :{порт}"],
                               capture_output=True, text=True, timeout=20).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    pid = None
    for часть in вывод.replace(",", " ").split():
        if часть.startswith("pid="):
            pid = часть[4:]
            break
    if not pid:
        return {}
    try:
        статус = Path(f"/proc/{pid}/status").read_text(encoding="utf-8")
        rss = next((int(с.split()[1]) // 1024 for с in статус.splitlines()
                    if с.startswith("VmRSS")), None)
        возраст = time.time() - Path(f"/proc/{pid}").stat().st_mtime
    except (OSError, ValueError):
        return {"pid": pid}
    return {"pid": pid, "rss_mib": rss, "возраст_с": int(возраст)}


def замер(порт: int, путь: str, повторов: int = 3) -> list[float]:
    времена = []
    for _ in range(повторов):
        t = time.monotonic()
        subprocess.run(["curl", "-sS", "-o", "/dev/null", "--max-time", "60",
                        f"http://127.0.0.1:{порт}{путь}"],
                       capture_output=True)
        времена.append(round(time.monotonic() - t, 3))
    return времена


def главная(аргв: list[str]) -> int:
    пары = витрины()
    цели = аргв or sorted(пары)
    м = память()
    print(f"узел: память всего {м.get('MemTotal')} МиБ, доступно "
          f"{м.get('MemAvailable')} МиБ, swap {м.get('SwapTotal')} МиБ")
    for site in цели:
        з = пары.get(site) or {}
        порт = з.get("port") or з.get("http_port")
        if not порт:
            print(f"{site}: порта в описи нет")
            continue
        п = процесс(int(порт))
        главн = замер(int(порт), "/")
        здоров = замер(int(порт), "/healthz", повторов=1)
        print(f"{site} порт {порт}: главная {главн} с, healthz {здоров} с, "
              f"rss {п.get('rss_mib')} МиБ, процесс живёт "
              f"{п.get('возраст_с')} с")
    return 0


if __name__ == "__main__":
    sys.exit(главная(sys.argv[1:]))
