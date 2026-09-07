"""Опыт: меняет ли выдачу более строгий отбор кандидатов.

Задержка подсказки растёт с длиной запроса потому, что кандидатов становится
больше, а каждый оценивается целиком. Напрашивается порог по числу общих
кусков. Вопрос ровно один: изменится ли от этого выдача — совпадение со
сплошным перебором здесь охраняемое свойство, и оно защищает нечёткий поиск.

Опыт ничего не меняет в коде: отбор с порогом считается здесь же, рядом с
настоящим, и обе выдачи сверяются с перебором.

Эталон на запрос считается один раз и запоминается: перебор стоит секунды, и
пересчитывать его для каждого порога значит занимать процессор, который сейчас
нужен рендеру.
"""
from __future__ import annotations

import json
import random
import statistics
import sys
import time

sys.path.insert(0, "/home/claude/wt-prod-25")

from factory.lords import search as search_mod
from factory.lords import search_index as si

КАТАЛОГ = "/srv/site-factory/repo/var/lords/lords/catalog-cache/lords-01.json"
ПРЕДЕЛ_ВЫДАЧИ = 20

with open(КАТАЛОГ, encoding="utf-8") as файл:
    сырьё = json.load(файл)
записи = сырьё["items"] if isinstance(сырьё, dict) else сырьё
индекс = si.build(записи)
print(f"каталог {len(записи)} записей, кусков {len(индекс['postings'])}")

_память: dict[str, list[str]] = {}


def эталон(query: str) -> list[str]:
    if query in _память:
        return _память[query]
    варианты = search_mod._variants(query)
    if not варианты or max(len(в) for в in варианты) < search_mod.MIN_QUERY:
        _память[query] = []
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
    _память[query] = [з.get("external_id") for _, _, _, з in оценённые[:ПРЕДЕЛ_ВЫДАЧИ]]
    return _память[query]


def с_порогом(query: str, доля: float) -> tuple[list[str], int, float]:
    варианты = search_mod._variants(query)
    if not варианты or max(len(в) for в in варианты) < search_mod.MIN_QUERY:
        return [], 0, 0.0
    начало = time.monotonic()
    postings = индекс["postings"]
    счёт: dict[int, int] = {}
    всего_кусков = 0
    for вариант in варианты:
        куски = si.куски(вариант)
        всего_кусков = max(всего_кусков, len(куски))
        for кусок in куски:
            for позиция in postings.get(кусок, ()):
                счёт[позиция] = счёт.get(позиция, 0) + 1
    порог = max(1, int(всего_кусков * доля))
    отобранные = [п for п, c in счёт.items() if c >= порог]
    оценённые = []
    for позиция in отобранные:
        запись = записи[позиция]
        лучшее = 0
        for форма in search_mod._forms(запись):
            for вариант in варианты:
                лучшее = max(лучшее, search_mod._score(форма, вариант))
        if лучшее:
            оценённые.append((лучшее, search_mod.normalize(запись.get("name") or ""),
                              позиция, запись))
    оценённые.sort(key=lambda с: (-с[0], с[1], с[2]))
    мс = (time.monotonic() - начало) * 1000
    return ([з.get("external_id") for _, _, _, з in оценённые[:ПРЕДЕЛ_ВЫДАЧИ]],
            len(отобранные), мс)


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
нечёткие = ["матрца", "матирца", "матрицца", "vfnhbwf", "ведмак", "ведььмак"]
все = запросы + нечёткие

начало = time.monotonic()
for q in все:
    эталон(q)
print(f"эталоны посчитаны за {time.monotonic() - начало:.0f} с\n")

print(f"{'доля':>6} {'совпало':>12} {'кандидатов':>12} {'время поиска p95':>18}")
for доля in (0.0, 0.25, 0.34, 0.5):
    совпало, кандидатов, времена = 0, [], []
    for q in все:
        получено, сколько, мс = с_порогом(q, доля)
        кандидатов.append(сколько)
        времена.append(мс)
        if получено == эталон(q):
            совпало += 1
    времена.sort()
    p95 = времена[min(len(времена) - 1, int(len(времена) * 0.95))]
    print(f"{доля:6.2f} {совпало:9}/{len(все):<3} {statistics.mean(кандидатов):11.0f} "
          f"{p95:17.1f} мс")

print("\nнечёткие запросы при доле 0.34:")
for q in нечёткие:
    получено, сколько, _ = с_порогом(q, 0.34)
    метка = "совпало" if получено == эталон(q) else "РАЗОШЛОСЬ"
    print(f"  {q:12} эталон {len(эталон(q)):2}, порог {len(получено):2} "
          f"({сколько} кандидатов) — {метка}")
