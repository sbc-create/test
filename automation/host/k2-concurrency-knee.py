#!/usr/bin/env python3
"""Со скольки одновременных запросов витрина перестаёт укладываться в 30 с.

Зачем. Публичный 504 означает только, что nginx не дождался ответа за
`proxy_read_timeout 30s`. Журналы узла закрыты правами, а собранные владельцем
записи об инциденте показывают ДЕСЯТКИ одновременных запросов страницы
произведения, у всех — `BrokenPipeError` на записи ответа: клиент (nginx) уже
ушёл. Это признак не однопоточности, а насыщения: все потоки заняты, каждый
отвечает дольше предела.

Инструмент измеряет именно это: одна и та же страница запрашивается с разной
одновременностью, печатаются медиана, p95 и максимум. Нагрузка маленькая и
короткая — несколько десятков запросов, — а ответ даёт точку, после которой
предел nginx перестаёт выполняться.

Запуск на узле:  k2-concurrency-knee.py <site_id> [путь] [1,4,8,16]
"""
from __future__ import annotations

import json
import statistics
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ОПИСЬ = Path("/home/k2deploy/stage/MANIFEST.json")
ПРЕДЕЛ_NGINX = 30.0


def порт(site: str) -> int:
    опись = json.loads(ОПИСЬ.read_text(encoding="utf-8"))
    ячейка = (опись.get("cells") or {}).get(site) or {}
    return int(ячейка["port"])


def запрос(адрес: str) -> float:
    t = time.monotonic()
    subprocess.run(["curl", "-sS", "-o", "/dev/null", "--max-time", "90", адрес],
                   capture_output=True)
    return time.monotonic() - t


def главная(аргв: list[str]) -> int:
    if not аргв:
        print("нужен site_id", file=sys.stderr)
        return 2
    site = аргв[0]
    путь = аргв[1] if len(аргв) > 1 else "/"
    ступени = [int(с) for с in (аргв[2] if len(аргв) > 2 else "1,4,8,16").split(",")]
    п = порт(site)
    адрес = f"http://127.0.0.1:{п}{путь}"
    print(f"{site}: {адрес}; предел nginx {ПРЕДЕЛ_NGINX:.0f} с")
    for n in ступени:
        with ThreadPoolExecutor(max_workers=n) as пул:
            времена = sorted(пул.map(lambda _: запрос(адрес), range(n)))
        p95 = времена[max(0, int(len(времена) * 0.95) - 1)]
        метка = "ПРЕВЫШЕН" if времена[-1] > ПРЕДЕЛ_NGINX else "в пределе"
        print(f"  одновременно {n:3}: медиана {statistics.median(времена):6.2f} с, "
              f"p95 {p95:6.2f} с, максимум {времена[-1]:6.2f} с — {метка}")
        time.sleep(2)
    return 0


if __name__ == "__main__":
    sys.exit(главная(sys.argv[1:]))
