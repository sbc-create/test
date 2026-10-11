#!/usr/bin/env python3
"""Быстрая сверка доступности сети: код главной по каждому домену.

Нужна там, где полная приёмка слишком долгая, а знать «до» и «после» надо
обязательно: например, перед остановкой процессов на хосте и сразу после.
Проверяет ровно одно — отвечает ли главная, — и не притворяется приёмкой:
качество страниц проверяет `public-acceptance.py`.

    python3 automation/local/quick-availability.py            # все домены сети
    python3 automation/local/quick-availability.py a.site b.site
"""
from __future__ import annotations

import concurrent.futures
import sys
import urllib.error
import urllib.request

ДОМЕНЫ = (
    "animedia.icu", "animedia.space", "animeg0.site", "an1mego.site",
    "an1meg0.site", "lordfilm47.space", "lordserial33.biz",
    "lordserials22.info", "1lordserials1.online", "zonafilm.cc",
    "zonafilm.space", "zonafilm12.site", "yummyani.site", "yummyani.org",
    "yummyani.biz", "yummyani7.site", "yummyani7.info",
)
ТАЙМАУТ = 20


def проверить(домен: str) -> tuple[str, str]:
    зап = urllib.request.Request(f"https://{домен}/",
                                 headers={"User-Agent": "quick-availability"})
    try:
        with urllib.request.urlopen(зап, timeout=ТАЙМАУТ) as о:
            return домен, str(о.status)
    except urllib.error.HTTPError as сбой:
        return домен, str(сбой.code)
    except Exception as сбой:  # сеть, TLS, таймаут — всё это «не ответил»
        return домен, f"нет ответа: {type(сбой).__name__}"


def главное(аргв: list[str] | None = None) -> int:
    домены = tuple(аргв) if аргв else ДОМЕНЫ
    с_проблемой = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as пул:
        for домен, итог in пул.map(проверить, домены):
            print(f"   {домен:24} {итог}")
            if итог != "200":
                с_проблемой.append((домен, итог))
    print(f"\nдоменов {len(домены)}, отвечают 200: "
          f"{len(домены) - len(с_проблемой)}, не 200: {len(с_проблемой)}")
    for домен, итог in с_проблемой:
        print(f"   {домен}: {итог}")
    return 0 if not с_проблемой else 1


if __name__ == "__main__":
    sys.exit(главное(sys.argv[1:] or None))
