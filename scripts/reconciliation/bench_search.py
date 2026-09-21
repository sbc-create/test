#!/usr/bin/env python3
"""Измеряет, куда уходит время поиска витрины, на живом каталоге.

Дефект P0-SEARCH-FULL-SCAN известен по симптому: `/search/` отвечает ~8.4 s
против 0.39 s у `/catalog/`. Симптом не говорит, что именно дорого — перебор
записей или пересчёт форм названия на каждом запросе. Стенд разделяет эти два
предположения замером, а не рассуждением.

Запуск (под общим замком тяжёлых работ):
    flock /home/claude/run-locks/site-factory-heavy-build.lock \\
        python3 scripts/reconciliation/bench_search.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import resource
import statistics
import sys
import time
from pathlib import Path

FRONTEND = Path("automation/host/lords-frontend.py")
CATALOG = Path("/srv/lords/.frontend/zona-01-catalog.json")

#: Запросы подобраны по видам обращений, а не по удобству: точное название,
#: латиница вместо кириллицы, чужая раскладка, многословный запрос, запрос с
#: формой издания и заведомо пустой.
ЗАПРОСЫ = [
    "матрица",
    "matrix",
    "vfnhbwf",
    "звездные войны",
    "бункер 1-3 сезон",
    "наруто",
    "naruto",
    "чаша весны",
    "zzznothing",
    "плен",
]


def загрузить_модуль():
    spec = importlib.util.spec_from_file_location("lords_frontend", FRONTEND)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"не удалось загрузить {FRONTEND}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["lords_frontend"] = module
    spec.loader.exec_module(module)
    return module


def rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def замер(данные, запросы, повторов: int = 3) -> dict[str, object]:
    времена: list[float] = []
    по_запросу: dict[str, object] = {}
    найдено: dict[str, int] = {}
    for q in запросы:
        лучшее = None
        for _ in range(повторов):
            начало = time.perf_counter()
            итог = данные.искать(q)
            прошло = (time.perf_counter() - начало) * 1000
            лучшее = прошло if лучшее is None else min(лучшее, прошло)
        статистика = dict(getattr(данные, "статистика_поиска", {}) or {})
        по_запросу[q] = {
            "ms": round(лучшее or 0.0, 1),
            "кандидатов": статистика.get("кандидатов"),
            "полный_перебор": статистика.get("полный_перебор"),
        }
        найдено[q] = len(итог)
        времена.append(лучшее or 0.0)
    времена.sort()
    return {
        "p50_ms": round(statistics.median(времена), 1),
        "p95_ms": round(времена[min(len(времена) - 1, int(len(времена) * 0.95))], 1),
        "max_ms": round(времена[-1], 1),
        "по_запросу_ms": по_запросу,
        "найдено": найдено,
    }


def main() -> int:
    if not CATALOG.exists():
        print(f"каталог не найден: {CATALOG}", file=sys.stderr)
        return 1

    модуль = загрузить_модуль()
    rss_до = rss_mb()

    начало = time.perf_counter()
    данные = модуль.Данные(str(CATALOG))
    загрузка_ms = (time.perf_counter() - начало) * 1000
    rss_после = rss_mb()

    отчёт: dict[str, object] = {
        "catalog": str(CATALOG),
        "items": len(данные.items),
        "revision": данные.revision,
        "загрузка_ms": round(загрузка_ms, 1),
        "rss_до_загрузки_mb": round(rss_до, 1),
        "rss_после_загрузки_mb": round(rss_после, 1),
        "поиск": замер(данные, ЗАПРОСЫ),
    }
    отчёт["rss_пик_mb"] = round(rss_mb(), 1)

    print(json.dumps(отчёт, ensure_ascii=False, indent=2))
    out = os.environ.get("BENCH_OUT")
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(
            json.dumps(отчёт, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print("->", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
