"""Какая выдача расходится с перебором и почему.

Опыт с порогом дал одинаковые 29 из 30 при любом пороге, включая нулевой, —
то есть при нынешнем поведении. Значит расхождение существует само по себе, а
порог его не создаёт. Здесь оно называется поимённо.
"""
from __future__ import annotations

import json
import random
import sys

sys.path.insert(0, "/home/claude/wt-prod-25")

from factory.lords import search as search_mod
from factory.lords import search_index as si

КАТАЛОГ = "/srv/site-factory/repo/var/lords/lords/catalog-cache/lords-01.json"
ПРЕДЕЛ_ВЫДАЧИ = 20

with open(КАТАЛОГ, encoding="utf-8") as файл:
    сырьё = json.load(файл)
записи = сырьё["items"] if isinstance(сырьё, dict) else сырьё
индекс = si.build(записи)


def эталон(query: str):
    варианты = search_mod._variants(query)
    if not варианты or max(len(в) for в in варианты) < search_mod.MIN_QUERY:
        return []
    оценённые = []
    for позиция, запись in enumerate(записи):
        лучшее = 0
        for форма in search_mod._forms(запись):
            for вариант in варианты:
                лучшее = max(лучшее, search_mod._score(форма, вариант))
        if лучшее:
            оценённые.append((лучшее, search_mod.normalize(запись.get("name") or ""),
                              позиция, запись))
    оценённые.sort(key=lambda с: (-с[0], с[1], с[2]))
    return оценённые[:ПРЕДЕЛ_ВЫДАЧИ]


случай = random.Random(20260907)
имена = [str(з.get("name") or "").strip() for з in записи if з.get("name")]
запросы = []
for длина in (4, 6, 10):
    пока = 0
    while пока < 8:
        имя = случай.choice(имена)
        if len(имя) >= длина:
            запросы.append(имя[:длина])
            пока += 1
запросы += ["матрца", "матирца", "матрицца", "vfnhbwf", "ведмак", "ведььмак"]

for q in запросы:
    ожидаемое = эталон(q)
    полученное = si.search(индекс, записи, q, limit=ПРЕДЕЛ_ВЫДАЧИ)
    if [з.get("external_id") for _, _, _, з in ожидаемое] == \
            [з.get("external_id") for з in полученное]:
        continue
    print(f"РАСХОЖДЕНИЕ на запросе {q!r}")
    кандидаты = si.кандидаты(индекс, q)
    print(f"  кандидатов отобрано: {len(кандидаты)} (предел {si.ПРЕДЕЛ_КАНДИДАТОВ})")
    множество = set(кандидаты)
    print(f"\n  {'#':>2} {'оценка':>6} {'в кандидатах':>13}  название")
    for н, (оценка, _, позиция, запись) in enumerate(ожидаемое, 1):
        print(f"  {н:2} {оценка:6} {str(позиция in множество):>13}  "
              f"{str(запись.get('name'))[:46]}")
    получено_имена = [str(з.get("name"))[:46] for з in полученное]
    print(f"\n  выдача указателя: {получено_имена[:6]}")
    break
else:
    print("расхождений нет")
