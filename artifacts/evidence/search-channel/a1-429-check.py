"""Приёмка задачи А1 плана недели: 429 Метрики у zonafilm12.site и zonafilm.space.

Критерий плана: «в выгрузке у обоих доменов `daily_search` измерен либо названа
причина с числом попыток». Проверяется по выгрузкам 19.10 и 20.10 — только
чтение.
"""
import json
import pathlib

БАЗА = pathlib.Path("/home/claude/wt-portable-site-cell-01/artifacts/analytics")
ДОМЕНЫ = ("zonafilm12.site", "zonafilm.space")


def проверить(файл):
    д = json.loads((БАЗА / файл).read_text(encoding="utf-8"))
    print(f"\n=== {файл} (собрано {д['collected_at']})")
    св = д.get("summary") or {}
    print(f"    измерено {св.get('measured')} из {св.get('total')}")
    пп = д.get("rate_limit_retry") or {}
    print(f"    повторный проход: включён {пп.get('enabled')},"
          f" пауза {пп.get('cooldown_s')} с, домены {пп.get('domains')}")
    for домен, итог in (пп.get("results") or {}).items():
        print(f"      {домен}: было {итог.get('before')} →"
              f" {итог.get('after')}, помогло {итог.get('helped')}")
    дом = {з.get("domain"): з for з in д["domains"]}
    for домен in ДОМЕНЫ:
        з = дом.get(домен)
        if з is None:
            print(f"    {домен:18} домена в выгрузке нет")
            continue
        м = {и["key"]: и for и in з["measurements"]}
        всего429 = [и["key"] for и in з["measurements"]
                    if not и.get("measured") and "429" in str(и.get("reason", ""))]
        ds = м.get("daily_search") or {}
        состояние = ("измерен" if ds.get("measured")
                     else f"НЕ ИЗМЕРЕН: {ds.get('reason')}")
        print(f"    {домен:18} измерено {з['measured_count']}/{з['total_count']},"
              f" daily_search {состояние}")
        if всего429:
            print(f"      показатели с 429: {всего429}")


for файл in ("analytics-2026-10-19.json", "analytics-2026-10-20.json"):
    проверить(файл)
