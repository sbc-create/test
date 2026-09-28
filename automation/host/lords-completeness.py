#!/usr/bin/env python3
"""Полнота витрины: все ли тайтлы публикуемых типов получили страницы.

Публикуемые типы берутся из плана сайта, а не угадываются по содержимому диска:
первая попытка выводила их из того, что уже лежит, и ошибалась — несколько аниме
на диске делали весь тип «публикуемым», после чего 497 законно отсутствующих
записей выглядели недостачей.
"""
import collections
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import yaml  # noqa: E402

from factory.lords import content_types as ct  # noqa: E402
from factory.lords import live_catalog  # noqa: E402
from factory.lords import plan as plan_mod  # noqa: E402
from factory.paths import PATHS  # noqa: E402

САЙТЫ = ("lords-01", "lords-02", "lords-03")
ВСЕГО = {"полно": 0, "неполно": 0}

for site in САЙТЫ:
    корень = os.path.realpath(f"/srv/lords/{site}/current") + "/site"
    каталог_страниц = f"{корень}/title"
    кэш = os.environ.get("LORDS_CACHE_DIR",
                        "/srv/site-factory/repo/var/lords/lords/catalog-cache")
    кэш = f"{кэш}/{site}.json"
    if not os.path.isdir(каталог_страниц):
        print(f"  {site}: страниц ещё нет")
        continue

    package = yaml.safe_load(PATHS.site_package(site).read_text(encoding="utf-8"))
    items = json.loads(Path(кэш).read_text(encoding="utf-8"))["items"]
    catalog = live_catalog.catalog_from_live(items)
    site_plan = plan_mod.build_plan(
        package,
        credentials_available=True,
        api_capabilities=catalog.capabilities(),
    )
    kinds = list(ct.active_types(site_plan.type_states))

    на_диске = set(os.listdir(каталог_страниц))
    по_слагу = {}
    for t in catalog.titles:
        по_слагу.setdefault(t.slug, t)

    ожидаемые = {s: t for s, t in по_слагу.items() if t.content_type in kinds}
    пропущены = [(s, t) for s, t in ожидаемые.items() if s not in на_диске]
    лишние = на_диске - set(ожидаемые)

    типы = collections.Counter(t.content_type for t in catalog.titles)
    исключено = sum(v for k, v in типы.items() if k not in kinds)
    столкновения = len(catalog.titles) - len(по_слагу)

    print(f"  {site} (релиз {os.path.basename(os.path.dirname(корень))}):")
    print(f"    записей в каталоге         {len(catalog.titles)}")
    print(f"    публикуемые типы           {kinds}")
    print(f"    исключено по типу          {исключено}  (так и задумано)")
    print(f"    потеряно на столкновениях  {столкновения}  (дефект slug)")
    print(f"    ожидалось страниц          {len(ожидаемые)}")
    print(f"    на диске                   {len(на_диске)}")
    if пропущены:
        print(f"    НЕ ХВАТАЕТ                 {len(пропущены)}")
        for s, t in пропущены[:3]:
            print(f"        {s} ({t.content_type})")
        ВСЕГО["неполно"] += 1
    else:
        print("    ИТОГ                       ПОЛНО")
        ВСЕГО["полно"] += 1
    if лишние:
        print(f"    на диске лишних            {len(лишние)}")

print()
print(f"  витрин полных: {ВСЕГО['полно']}, неполных: {ВСЕГО['неполно']}")
