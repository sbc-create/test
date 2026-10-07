#!/usr/bin/env python3
"""Сторож доступности: пишет ТОЛЬКО отклонения, с временем. Только чтение.

    python3 automation/local/availability-watch.py --minutes 120 \\
        --log var/availability-watch.log <домен> [<домен> …]

Зачем. Отказ, который виден раз в двадцать замеров, нельзя ни подтвердить, ни
опровергнуть разовой проверкой. Измерено 2026-10-06 на zonafilm.cc:
`/collections/` дважды ответила 504 внутри последовательных проверок, а в
тридцати прямых замерах и в замере холодной отрисовки (3.6 с) — ни разу.
Сторож не исправляет и не угадывает причину: он фиксирует, КОГДА отклонение
случилось, чтобы причину можно было искать по времени в журналах служб.

Пишется только отклонение (код не 200 или время свыше порога) и одна итоговая
строка. Ровные круги в журнал не попадают: журнал, в котором девяносто девять
строк «всё хорошо», скрывает сотую.
"""
from __future__ import annotations

import argparse
import datetime
import pathlib
import subprocess
import sys
import time

ПУТИ_ПО_УМОЛЧАНИЮ = "/,/catalog/,/collections/,/new/"


def сейчас() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def замер(домен: str, путь: str, таймаут: int) -> tuple[str, float]:
    г = subprocess.run(
        ["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code} %{time_total}",
         "--max-time", str(таймаут), f"https://{домен}{путь}"],
        capture_output=True, text=True)
    части = (г.stdout or "").split()
    код = части[0] if части else "0"
    сек = float(части[1]) if len(части) > 1 else -1.0
    return код, сек


def главная(argv: list[str]) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("domains", nargs="+")
    р.add_argument("--paths", default=ПУТИ_ПО_УМОЛЧАНИЮ)
    р.add_argument("--minutes", type=float, default=60.0)
    р.add_argument("--every", type=float, default=120.0, help="пауза между кругами, с")
    р.add_argument("--slow", type=float, default=10.0, help="порог «медленно», с")
    р.add_argument("--timeout", type=int, default=90)
    р.add_argument("--log", default="")
    о = р.parse_args(argv[1:])

    пути = [п.strip() for п in о.paths.split(",") if п.strip()]
    журнал = pathlib.Path(о.log) if о.log else None
    if журнал:
        журнал.parent.mkdir(parents=True, exist_ok=True)

    def записать(строка: str) -> None:
        print(строка, flush=True)
        if журнал:
            with журнал.open("a", encoding="utf-8") as ф:
                ф.write(строка + "\n")

    записать(f"{сейчас()} сторож начат: домен {len(о.domains)}, путей {len(пути)}, "
             f"круг раз в {о.every:.0f} с, срок {о.minutes:.0f} мин")
    край = time.time() + о.minutes * 60
    кругов = отклонений = замеров = 0
    while time.time() < край:
        кругов += 1
        for домен in о.domains:
            for путь in пути:
                код, сек = замер(домен, путь, о.timeout)
                замеров += 1
                if код != "200":
                    отклонений += 1
                    записать(f"{сейчас()} ОТКЛОНЕНИЕ {домен}{путь} код {код} "
                             f"{сек:.2f}s (круг {кругов})")
                elif сек >= о.slow:
                    отклонений += 1
                    записать(f"{сейчас()} МЕДЛЕННО  {домен}{путь} код 200 "
                             f"{сек:.2f}s (круг {кругов})")
        if time.time() < край:
            time.sleep(о.every)
    записать(f"{сейчас()} сторож закончен: кругов {кругов}, замеров {замеров}, "
             f"отклонений {отклонений}")
    return 0


if __name__ == "__main__":
    raise SystemExit(главная(sys.argv))
