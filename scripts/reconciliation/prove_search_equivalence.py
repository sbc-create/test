#!/usr/bin/env python3
"""Доказывает, что указатель поиска не потерял ни одной записи.

Ускорение, которое молча вырезает записи из выдачи, — это не ускорение, а
порча выдачи: пользователь видит не «медленно», а «не найдено». Поэтому
отбор кандидатов проверяется не рассуждением, а сличением: выдача с
указателем сравнивается с выдачей полного перебора на широкой батарее
запросов, построенной из настоящих названий живого каталога.

Запросы берутся детерминированно (фиксированное зерно), чтобы прогон
повторялся, и по видам обращений, а не по удобству: целое название, префикс,
одно слово, транслитерация, чужая раскладка, опечатка, лишнее слово формы
издания и заведомо пустой запрос.

Запуск под общим замком тяжёлых работ:
    flock /home/claude/run-locks/site-factory-heavy-build.lock \\
        python3 scripts/reconciliation/prove_search_equivalence.py 150
"""

from __future__ import annotations

import importlib.util
import json
import os
import random
import resource
import sys
import time
from pathlib import Path

FRONTEND = Path("automation/host/lords-frontend.py")
CATALOG = Path("/srv/lords/.frontend/zona-01-catalog.json")
OUT = Path("artifacts/evidence/cursor-work-reconciliation-01/SEARCH_EQUIVALENCE.json")
ЗЕРНО = 20260921


def загрузить_модуль():
    spec = importlib.util.spec_from_file_location("lords_frontend_proof", FRONTEND)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"не удалось загрузить {FRONTEND}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["lords_frontend_proof"] = module
    spec.loader.exec_module(module)
    return module


def построить_запросы(модуль, items: list[dict], сколько: int) -> list[str]:
    рнд = random.Random(ЗЕРНО)
    образцы = рнд.sample(items, min(len(items), сколько))
    запросы: list[str] = []
    for з in образцы:
        title = (з.get("title") or "").strip()
        if not title:
            continue
        слова = title.split()
        вид = len(запросы) % 8
        if вид == 0:
            запросы.append(title)
        elif вид == 1:
            запросы.append(title[: max(4, len(title) // 2)])
        elif вид == 2:
            запросы.append(слова[0])
        elif вид == 3:
            запросы.append(модуль.транслит(title))
        elif вид == 4:
            # Чужая раскладка: латиница, набранная вместо кириллицы.
            обратно = {v: k for k, v in zip(
                "qwertyuiop[]asdfghjkl;'zxcvbnm,.`",
                "йцукенгшщзхъфывапролджэячсмитьбюё")}
            запросы.append("".join(обратно.get(ch, ch) for ch in title.lower()))
        elif вид == 5:
            испорченное = list(title)
            if len(испорченное) > 5:
                испорченное[len(испорченное) // 2] = "ы"
            запросы.append("".join(испорченное))
        elif вид == 6:
            запросы.append(f"{слова[0]} 1-3 сезон")
        else:
            запросы.append(" ".join(слова[:2]))
    запросы.extend(["zzznothing", "ыварпо", "", "   ", "the", "war", "2019"])
    # Стабильный порядок без повторов.
    видели: set[str] = set()
    итог: list[str] = []
    for q in запросы:
        if q not in видели:
            видели.add(q)
            итог.append(q)
    return итог


def выдача(данные, q: str) -> list[str]:
    return [з.get("slug") or з.get("url") for з in данные.искать(q)]


def main() -> int:
    сколько = int(sys.argv[1]) if len(sys.argv) > 1 else 150
    if not CATALOG.exists():
        print(f"каталог не найден: {CATALOG}", file=sys.stderr)
        return 1

    модуль = загрузить_модуль()
    данные = модуль.Данные(str(CATALOG))
    запросы = построить_запросы(модуль, данные.items, сколько)

    расхождения: list[dict[str, object]] = []
    кандидатов: list[int] = []
    переборов = 0
    быстрое_ms: list[float] = []
    медленное_ms: list[float] = []

    начало = time.perf_counter()
    for q in запросы:
        данные.указатель_включён = False
        t0 = time.perf_counter()
        эталон = выдача(данные, q)
        медленное_ms.append((time.perf_counter() - t0) * 1000)

        данные.указатель_включён = True
        t0 = time.perf_counter()
        быстро = выдача(данные, q)
        быстрое_ms.append((time.perf_counter() - t0) * 1000)

        статистика = dict(данные.статистика_поиска)
        if статистика.get("полный_перебор"):
            переборов += 1
        else:
            кандидатов.append(int(статистика.get("кандидатов") or 0))

        if быстро != эталон:
            потеряно = [s for s in эталон if s not in быстро]
            лишнее = [s for s in быстро if s not in эталон]
            расхождения.append({
                "запрос": q,
                "эталон": len(эталон),
                "указатель": len(быстро),
                "потеряно": потеряно[:10],
                "лишнее": лишнее[:10],
            })

    прошло = time.perf_counter() - начало
    быстрое_ms.sort()
    медленное_ms.sort()

    def p(значения: list[float], доля: float) -> float:
        if not значения:
            return 0.0
        return round(значения[min(len(значения) - 1, int(len(значения) * доля))], 1)

    отчёт = {
        "catalog": str(CATALOG),
        "revision": данные.revision,
        "items": len(данные.items),
        "QUERIES_COMPARED": len(запросы),
        "SEARCH_RESULT_MISMATCHES": len(расхождения),
        "расхождения": расхождения[:20],
        "полных_переборов": переборов,
        "кандидатов_медиана": (
            sorted(кандидатов)[len(кандидатов) // 2] if кандидатов else None),
        "кандидатов_максимум": max(кандидатов) if кандидатов else None,
        "доля_каталога_максимум": (
            round(max(кандидатов) / len(данные.items), 4) if кандидатов else None),
        "указатель_p50_ms": p(быстрое_ms, 0.5),
        "указатель_p95_ms": p(быстрое_ms, 0.95),
        "перебор_p50_ms": p(медленное_ms, 0.5),
        "перебор_p95_ms": p(медленное_ms, 0.95),
        "прогон_секунд": round(прошло, 1),
        "PEAK_RSS_MB": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1),
        "EQUIVALENCE_PASS": 1 if not расхождения else 0,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(отчёт, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    краткое = {k: v for k, v in отчёт.items() if k != "расхождения"}
    print(json.dumps(краткое, ensure_ascii=False, indent=2))
    print("->", OUT)
    return 0 if not расхождения else 1


if __name__ == "__main__":
    raise SystemExit(main())
