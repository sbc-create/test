#!/usr/bin/env python3
"""Теневой прогон контура Yummy: собрать рядом, сверить, ничего не переключать.

Теневой прогон обязан доказывать три разные вещи, и все три проверяются здесь
отдельно:

1. контур собирается воспроизводимо и повторный прогон не плодит сущностей;
2. то, что он отдал бы витрине, разрешается в существующие страницы;
3. production при этом не изменился — ни файл проекции, ни базы витрин.

Третий пункт проверяется отпечатками ДО и ПОСЛЕ прогона. Утверждение
«я ничего не трогал» без такой сверки — это намерение, а не измерение.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import random
import sqlite3
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ingest, readmodel, store

КОРЕНЬ = Path("/srv/site-factory/yummy-content")
БАЗА = КОРЕНЬ / "state/yummy-content.sqlite3"
ПРОЕКЦИЯ = Path("/srv/lords/.frontend/yummy-site-catalog.json")
КАТАЛОГ = "/srv/site-factory/repo/var/lords/lords/catalog-cache/lords-01.json"
КОНТЕЙНЕР = "yummyani-staging-pg-site-1"
ВЫБОРКА = 40


def сейчас() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def отпечаток_файла(п: Path) -> dict:
    if not п.exists():
        return {"exists": False}
    b = п.read_bytes()
    return {"exists": True, "sha256": hashlib.sha256(b).hexdigest(),
            "size": len(b), "mtime": int(п.stat().st_mtime)}


def счётчики_витрины() -> dict:
    запрос = ('SELECT \'Title\', count(*) FROM "Title" UNION ALL '
              'SELECT \'PublicTitleRoute\', count(*) FROM "PublicTitleRoute" '
              'UNION ALL SELECT \'EditorialPost\', count(*) FROM "EditorialPost";')
    р = subprocess.run(
        ["docker", "exec", "-i", КОНТЕЙНЕР, "sh", "-lc",
         'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -qtA -F"|" -f -'],
        input=запрос, capture_output=True, text=True, timeout=120)
    итог = {}
    for строка in р.stdout.splitlines():
        ч = строка.split("|")
        if len(ч) == 2:
            итог[ч[0]] = int(ч[1])
    return итог


def код(путь: str) -> int:
    зпр = urllib.request.Request("http://127.0.0.1:3101" + путь,
                                 headers={"Host": "yummyani.site",
                                          "User-Agent": "shadow-run/1.0"})
    try:
        with urllib.request.urlopen(зпр, timeout=20) as о:
            return о.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


def main() -> int:
    отчёт: dict = {"startedAt": сейчас(), "mode": "shadow",
                   "productionSwitched": False}

    # --- ДО -----------------------------------------------------------------
    до = {"projection": отпечаток_файла(ПРОЕКЦИЯ), "db": счётчики_витрины()}
    отчёт["before"] = до
    print("до прогона: проекция sha %s, витрина %s" % (
        до["projection"].get("sha256", "—")[:12], до["db"]))

    # --- сборка -------------------------------------------------------------
    соед = store.открыть(БАЗА)
    маршруты = ingest.маршруты_витрины(КОНТЕЙНЕР)
    записи = ingest.каталог_поставщика(КАТАЛОГ)
    первый = ingest.импорт_сущностей(соед, записи, маршруты)
    второй = ingest.импорт_сущностей(соед, записи, маршруты)
    отчёт["import"] = {"first": первый, "second": второй}
    print("импорт: новых %s, повтор дал новых %s (идемпотентность)"
          % (первый.get("new"), второй.get("new")))

    n = соед.execute("SELECT count(*) c FROM entity").fetchone()["c"]
    отчёт["entities"] = n

    # --- сверка состава с нынешней проекцией --------------------------------
    живая = json.loads(ПРОЕКЦИЯ.read_text(encoding="utf-8"))
    слаги_живой = {(з.get("slug") or "").strip("/") for з in живая["items"]}
    слаги_тени = {р["slug"] for р in
                  соед.execute("SELECT slug FROM entity").fetchall()}
    отчёт["composition"] = {
        "liveProjection": len(слаги_живой), "shadow": len(слаги_тени),
        "onlyInLive": len(слаги_живой - слаги_тени),
        "onlyInShadow": len(слаги_тени - слаги_живой),
        "common": len(слаги_живой & слаги_тени)}
    print("состав: живая %d, тень %d, только в живой %d, только в тени %d"
          % (len(слаги_живой), len(слаги_тени),
             len(слаги_живой - слаги_тени), len(слаги_тени - слаги_живой)))

    # --- разрешимость адресов тени ------------------------------------------
    поверхность = readmodel.актуальное(соед, предел=200)
    все = [dict(р) for р in соед.execute(
        "SELECT entity_id, canonical_path FROM entity").fetchall()]
    random.seed(23)
    проба = random.sample(все, min(ВЫБОРКА, len(все)))
    коды: dict[int, int] = {}
    плохие = []
    for з in проба:
        c = код(з["canonical_path"])
        коды[c] = коды.get(c, 0) + 1
        if c != 200:
            плохие.append({"entityId": з["entity_id"],
                           "canonicalPath": з["canonical_path"], "http": c})
    отчёт["addressProbe"] = {"sampled": len(проба), "byCode": коды,
                             "bad": плохие[:10]}
    print("адреса: проверено %d, коды %s" % (len(проба), коды))

    # --- ПОСЛЕ --------------------------------------------------------------
    после = {"projection": отпечаток_файла(ПРОЕКЦИЯ), "db": счётчики_витрины()}
    отчёт["after"] = после
    проекция_цела = до["projection"] == после["projection"]
    база_цела = до["db"] == после["db"]
    отчёт["productionUnchanged"] = {"projectionFile": проекция_цела,
                                    "showcaseDb": база_цела}
    print("после прогона: проекция без изменений %s, базы витрины без изменений %s"
          % (проекция_цела, база_цела))

    отчёт["finishedAt"] = сейчас()
    отчёт["verdict"] = ("PASS" if проекция_цела and база_цела and not плохие
                        and второй.get("new") == 0 else "FAIL")
    (КОРЕНЬ / "state/shadow-report.json").write_text(
        json.dumps(отчёт, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nвердикт:", отчёт["verdict"])
    return 0 if отчёт["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
