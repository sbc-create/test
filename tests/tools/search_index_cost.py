"""Стоимость самого указателя, без сети и без отрисовки страницы.

Замер по HTTP отвечает на вопрос «сколько ждёт посетитель». Этот — на вопрос
«сколько из этого стоит поиск». Без второго нельзя сказать, во что упирается
цель: в указатель, в отрисовку ответа или в транспорт.
"""
from __future__ import annotations

import json
import random
import statistics
import sys
import time

sys.path.insert(0, "/home/claude/wt-prod-25")

from factory.lords import search_index as si

РЕЛИЗ = "/srv/lords/lords-03/current"
КАТАЛОГ = "/srv/site-factory/repo/var/lords/lords/catalog-cache/lords-01.json"

with open(КАТАЛОГ, encoding="utf-8") as файл:
    каталог = json.load(файл)
записи = каталог["items"] if isinstance(каталог, dict) else каталог
индекс = si.load(f"{РЕЛИЗ}/search-index.json")
print(f"записей в каталоге: {len(записи)}; в указателе: {индекс.get('size')}; "
      f"кусков: {len(индекс.get('postings') or {})}")

if индекс.get("size") != len(записи):
    print("ВНИМАНИЕ: размеры разошлись — замер пойдёт только по кандидатам")

случай = random.Random(20260907)
имена = [str(з.get("name") or "").strip() for з in записи if з.get("name")]


def префиксы(длина, сколько):
    итог = []
    while len(итог) < сколько:
        имя = случай.choice(имена)
        if len(имя) >= длина:
            итог.append(имя[:длина])
    return итог


for длина in (2, 3, 4, 6, 10):
    запросы = префиксы(длина, 60)
    отбор, сколько_кандидатов = [], []
    for q in запросы:
        н = time.monotonic()
        к = si.кандидаты(индекс, q)
        отбор.append((time.monotonic() - н) * 1000)
        сколько_кандидатов.append(len(к))
    отбор.sort()
    p95 = отбор[min(len(отбор) - 1, int(len(отбор) * 0.95))]
    print(f"  префикс {длина:2}: отбор p50={statistics.median(отбор):6.1f} "
          f"p95={p95:6.1f} мс | кандидатов в среднем "
          f"{statistics.mean(сколько_кандидатов):7.0f}, максимум {max(сколько_кандидатов)}")
