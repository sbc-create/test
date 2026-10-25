#!/usr/bin/env python3
"""Доля отброшенных публичных запросов по витринам сети.

ПОВОД ИЗМЕРЕННЫЙ, 25.10 (MOD-175): `animedia.icu` отдаёт 503 на половину
публичных запросов, при здоровом узле и чистом nginx, тогда как её сестра на
том же стеке не падает ни разу. Два раза за сутки этот отказ едва не
превратился у меня в ложный вывод о содержимом страницы.

Если так ведёт себя одна витрина, нужно знать, не так ли ведут себя другие:
отброшенный запрос — это и потерянный посетитель, и причина поисковику
сократить обход. Отдельной меры доступности по сети у фабрики не было.

ЧТО ИНСТРУМЕНТ РАЗЛИЧАЕТ, и почему не считает всё «ошибкой»:
  отдано        — код 200;
  отброшено     — 5xx и 429, то есть витрина жива, но запрос не обслужен;
  не отвечает   — соединения нет вовсе (DNS, TCP, таймаут);
  закрыта       — витрина закрыта от обхода решением, её не судим.
Доля считается от ОТПРАВЛЕННЫХ запросов и печатается рядом с их числом:
доля без знаменателя скрывает, что замер был коротким.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import time
from collections import Counter

АГЕНТ = "factory-public-availability-sweep"

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
РЕЕСТР = КОРЕНЬ / "config" / "active-domains.json"


def домены() -> list[dict]:
    д = json.loads(РЕЕСТР.read_text(encoding="utf-8"))
    сп = д.get("domains") or д
    сп = list(сп.values()) if isinstance(сп, dict) else сп
    return [з for з in сп if isinstance(з, dict) and з.get("domain")]


def код(url: str, таймаут: int) -> str:
    try:
        г = subprocess.run(
            ["curl", "-A", АГЕНТ, "-sS", "-o", "/dev/null", "-w", "%{http_code}",
             "--max-time", str(таймаут), url],
            capture_output=True, text=True, timeout=таймаут + 10)
    except subprocess.TimeoutExpired:
        return "таймаут"
    if г.returncode != 0:
        return "нет соединения"
    return г.stdout.strip() or "нет кода"


def главное(argv: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--requests", type=int, default=6,
                   help="запросов на витрину (чередуются главная и карточка)")
    р.add_argument("--timeout", type=int, default=20)
    р.add_argument("--pause", type=float, default=0.7)
    р.add_argument("--json", type=pathlib.Path)
    р.add_argument("--max-dropped-share", type=float, default=0.05)
    а = р.parse_args(argv)

    строки = []
    print(f"{'витрина':24} {'послано':>8} {'отдано':>7} {'отброшено':>10}"
          f" {'нет связи':>10}  коды")
    всего_посл = всего_отбр = 0
    плохие = []
    for з in sorted(домены(), key=lambda x: x["domain"]):
        домен = з["domain"]
        режим = str(з.get("indexing") or з.get("indexability") or "").lower()
        if режим in ("closed", "закрыта"):
            print(f"{домен:24} {'—':>8} {'—':>7} {'—':>10} {'—':>10}"
                  "  закрыта решением, не судим")
            строки.append({"домен": домен, "закрыта": True})
            continue
        коды = Counter()
        for н in range(а.requests):
            путь = "/" if н % 2 == 0 else "/title/"
            коды[код(f"https://{домен}{путь}", а.timeout)] += 1
            time.sleep(а.pause)
        послано = sum(коды.values())
        отдано = коды.get("200", 0) + коды.get("301", 0) + коды.get("404", 0)
        отброшено = sum(в for к, в in коды.items()
                        if к.isdigit() and (к.startswith("5") or к == "429"))
        нет_связи = sum(в for к, в in коды.items() if not к.isdigit())
        всего_посл += послано
        всего_отбр += отброшено
        доля = отброшено / послано if послано else 0.0
        if доля > а.max_dropped_share:
            плохие.append((домен, отброшено, послано, доля))
        print(f"{домен:24} {послано:8} {отдано:7} {отброшено:10}"
              f" {нет_связи:10}  {dict(коды.most_common())}")
        строки.append({"домен": домен, "послано": послано, "отдано": отдано,
                       "отброшено": отброшено, "нет_связи": нет_связи,
                       "коды": dict(коды)})
    print()
    доля_сети = (всего_отбр / всего_посл) if всего_посл else 0.0
    print(f"послано запросов {всего_посл}; отброшено {всего_отбр}"
          f" ({доля_сети:.1%})")
    if а.json:
        а.json.parent.mkdir(parents=True, exist_ok=True)
        а.json.write_text(json.dumps(строки, ensure_ascii=False, indent=1),
                          encoding="utf-8")
        print(f"подробности: {а.json}")
    if плохие:
        print()
        print(f"ВЫВОД: витрин с долей отброшенных выше"
              f" {а.max_dropped_share:.0%}: {len(плохие)}")
        for домен, о, п_, д in sorted(плохие, key=lambda x: -x[3]):
            print(f"   {домен:24} {о} из {п_} ({д:.0%})")
        print("   отброшенный запрос — это и потерянный посетитель, и причина"
              " поисковику сократить обход")
        return 1
    print("ВЫВОД: витрин с заметной долей отброшенных запросов нет")
    return 0


if __name__ == "__main__":
    sys.exit(главное())
