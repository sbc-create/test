#!/usr/bin/env python3
"""Фокусная проверка отзыва токенов Control API.

Предъявляет прежние значения по маршруту КАЖДОЙ области, которой они
обладали. Опознание в Control API предшествует и разбору маршрута, и проверке
прав: нераспознанный токен получает 401 до того, как обработчик что-либо
сделает, поэтому проверка изменяющих маршрутов безопасна — мутации не
происходит.

Значения не печатаются никогда: наружу идут только отпечатки и коды ответов.
"""
from __future__ import annotations

import hashlib
import json
import sys
import urllib.error
import urllib.request

БАЗА = "http://127.0.0.1:8790"
САЙТ = "demo-books"            # окружение non-production, DRAFT

#: Область → маршрут, которым она пользуется.
МАРШРУТЫ = {
    "read": ("GET", "/api/v1/playback-policy"),
    "audit:read": ("GET", "/api/v1/metrics"),
    "jobs:write": ("POST", f"/api/v1/sites/{САЙТ}/jobs"),
    "config:write": ("PATCH", f"/api/v1/sites/{САЙТ}/settings"),
    "cache:write": ("POST", f"/api/v1/sites/{САЙТ}/cache/invalidate"),
}


def отпечаток(значение: str) -> str:
    return hashlib.sha256(значение.encode()).hexdigest()[:12]


def проба(метод: str, путь: str, токен: str) -> tuple[int, str]:
    зпр = urllib.request.Request(
        БАЗА + путь, method=метод,
        data=b"{}" if метод in ("POST", "PATCH") else None,
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + токен})
    try:
        with urllib.request.urlopen(зпр, timeout=10) as о:
            return о.status, "ПРИНЯТ"
    except urllib.error.HTTPError as ош:
        return ош.code, {401: "ОТКАЗ-неопознан", 403: "ОТКАЗ-нет-прав",
                         404: "маршрута нет"}.get(ош.code, "иной")
    except Exception as ош:
        return 0, type(ош).__name__


def проверить(значения: dict[str, list[str]]) -> dict:
    """значения: отпечаток → перечень прежних областей (сам токен во входе)."""
    итог, принято = [], 0
    for токен, области in значения.items():
        for область in области:
            метод, путь = МАРШРУТЫ[область]
            код, исход = проба(метод, путь, токен)
            принято += 1 if исход == "ПРИНЯТ" else 0
            итог.append({"fingerprint": отпечаток(токен), "scope": область,
                         "route": f"{метод} {путь}", "status": код,
                         "outcome": исход})
    return {"checks": итог, "accepted": принято,
            "all_refused": принято == 0}


if __name__ == "__main__":
    # Вход: путь к файлу вида `токен=области|токен=области` (прежние значения).
    источник = sys.argv[1]
    вход = {}
    for кусок in open(источник, encoding="utf-8").read().strip().split("|"):
        т, _, о = кусок.strip().partition("=")
        if т.strip():
            вход[т.strip()] = [x.strip() for x in о.split(",") if x.strip()]
    результат = проверить(вход)
    print(json.dumps(результат, ensure_ascii=False, indent=1))
    sys.exit(0 if результат["all_refused"] else 4)
