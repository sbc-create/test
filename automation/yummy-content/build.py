#!/usr/bin/env python3
"""Сборка контентного контура Yummy из настоящих источников.

Источники — те же, что у витрины: каталог поставщика и таблица маршрутов
самой витрины. Пишет в собственное хранилище; боевые базы только читаются.
"""
from __future__ import annotations

import argparse, json, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ingest, store

КАТАЛОГ = "/srv/site-factory/repo/var/lords/lords/catalog-cache/lords-01.json"
БАЗА = "/srv/site-factory/yummy-content/state/yummy-content.sqlite3"
КОНТЕЙНЕР = "yummyani-staging-pg-site-1"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--db", default=БАЗА)
    p.add_argument("--catalog", default=КАТАЛОГ)
    p.add_argument("--container", default=КОНТЕЙНЕР)
    a = p.parse_args()

    t0 = time.time()
    соед = store.открыть(a.db)
    маршруты = ingest.маршруты_витрины(a.container)
    записи = ingest.каталог_поставщика(a.catalog)
    print(f"источники: маршрутов {len(маршруты)}, записей каталога {len(записи)}")
    итог = ingest.импорт_сущностей(соед, записи, маршруты)
    print("импорт:", json.dumps(итог, ensure_ascii=False))
    n = соед.execute("SELECT count(*) c FROM entity").fetchone()["c"]
    r = соед.execute("SELECT count(*) c FROM external_rating WHERE status='OK'"
                     ).fetchone()["c"]
    print(f"сущностей {n}, внешних рейтингов со значением {r}, "
          f"за {time.time() - t0:.1f} с")
    return 0


if __name__ == "__main__":
    sys.exit(main())
