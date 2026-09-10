#!/usr/bin/env python3
"""Шесть теневых циклов с полной сверкой current против shadow."""
from __future__ import annotations

import datetime as dt, json, random, resource, sqlite3, subprocess, sys, time
import urllib.error, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import canonical, ingest, readmodel, store

КОРЕНЬ = Path("/srv/site-factory/yummy-content")
БАЗА = КОРЕНЬ / "state/yummy-content.sqlite3"
ПРОЕКЦИЯ = Path("/srv/lords/.frontend/yummy-site-catalog.json")
КАТАЛОГ = "/srv/site-factory/repo/var/lords/lords/catalog-cache/lords-01.json"
КОНТЕЙНЕР = "yummyani-staging-pg-site-1"
ЖУРНАЛ = КОРЕНЬ / "state/shadow-cycles.jsonl"
ЦИКЛОВ, ПАУЗА = 6, 300


def сейчас() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def бд_витрины() -> dict:
    q = ('SELECT \'Title\',count(*) FROM "Title" UNION ALL '
         'SELECT \'PublicTitleRoute\',count(*) FROM "PublicTitleRoute" UNION ALL '
         'SELECT \'EditorialPost\',count(*) FROM "EditorialPost";')
    р = subprocess.run(["docker", "exec", "-i", КОНТЕЙНЕР, "sh", "-lc",
                        'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -qtA -F"|" -f -'],
                       input=q, capture_output=True, text=True, timeout=120)
    return {ч[0]: int(ч[1]) for ч in
            (с.split("|") for с in р.stdout.splitlines()) if len(ч) == 2}


def код(путь: str) -> int:
    """Конечный код ПОСЛЕ переходов. 308 в Python 3.10 не проходится сам,
    поэтому редирект отрабатывается вручную — иначе 308 сойдёт за отказ."""
    for _ in range(5):
        зпр = urllib.request.Request("http://127.0.0.1:3101" + путь,
                                     headers={"Host": "yummyani.site",
                                              "User-Agent": "shadow/1.0"})
        try:
            with urllib.request.urlopen(зпр, timeout=20) as о:
                return о.status
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308):
                место = e.headers.get("Location") or ""
                путь = место if место.startswith("/") else место.split("://")[-1][len("yummyani.site"):]
                continue
            return e.code
        except Exception:
            return 0
    return 0


def цикл(n: int) -> dict:
    t0 = time.time()
    м: dict = {"cycle": n, "at": сейчас()}
    до_ф = ПРОЕКЦИЯ.read_bytes() if ПРОЕКЦИЯ.exists() else b""
    до_бд = бд_витрины()

    соед = store.открыть(БАЗА)
    маршруты = ingest.маршруты_витрины(КОНТЕЙНЕР)
    записи = ingest.каталог_поставщика(КАТАЛОГ)

    # 4. идемпотентность: двукратный replay
    a = ingest.импорт_сущностей(соед, записи, маршруты)
    b = ingest.импорт_сущностей(соед, записи, маршруты)
    м["idempotent"] = {"firstNew": a.get("new"), "secondNew": b.get("new"),
                       "ok": b.get("new") == 0}

    # 1. количество сущностей и маршрутов
    n_ent = соед.execute("SELECT count(*) c FROM entity").fetchone()["c"]
    живая = json.loads(ПРОЕКЦИЯ.read_text(encoding="utf-8"))
    м["counts"] = {"routes": len(маршруты), "shadowEntities": n_ent,
                   "liveProjection": len(живая["items"]),
                   "sourceCatalog": len(записи)}

    # 9. причины отклонений с группировкой
    рез = canonical.Резолвер(маршруты)
    группы: dict[str, int] = {}
    for з in записи:
        и = рез.разрешить(str(з.get("external_id") or "")).outcome.value
        группы[и] = группы.get(и, 0) + 1
    м["rejectionCodes"] = группы

    # 2 + 3. разрешение и конечный код после переходов
    все = [dict(р) for р in соед.execute(
        "SELECT entity_id, canonical_path FROM entity").fetchall()]
    random.seed(100 + n)
    проба = random.sample(все, min(30, len(все)))
    коды: dict[str, int] = {}
    плохие = []
    for з in проба:
        нераз = readmodel.разрешить_адрес(соед, з["entity_id"])
        c = код(з["canonical_path"])
        коды[str(c)] = коды.get(str(c), 0) + 1
        if c != 200 or нераз["outcome"] != "RESOLVED":
            плохие.append({"entityId": з["entity_id"],
                           "path": з["canonical_path"], "http": c})
    м["addresses"] = {"sampled": len(проба), "byFinalCode": коды,
                      "terminal404": коды.get("404", 0), "bad": плохие[:5]}

    # 6. покрытие рейтингов по провайдерам
    м["ratings"] = {р["provider"]: {"ok": р["ok"], "absent": р["absent"]}
                    for р in соед.execute(
        "SELECT provider, sum(status='OK') ok, sum(status='ABSENT') absent "
        "FROM external_rating GROUP BY provider").fetchall()}

    # 7. новости и анонсы
    м["editorial"] = {t: len(readmodel.новости(соед, t)["items"])
                      for t in ("news", "announcement")}

    # 8. все восемь поверхностей
    об = все[0]["entity_id"] if все else ""
    м["surfaces"] = {
        "актуальное": len(readmodel.актуальное(соед, предел=24)["items"]),
        "новые-серии": len(readmodel.новые_серии(соед)["items"]),
        "сейчас-выходит": len(readmodel.сейчас_выходит(соед)["items"]),
        "новости": м["editorial"]["news"],
        "анонсы": м["editorial"]["announcement"],
        "внешние-рейтинги": len(readmodel.внешние_рейтинги(соед, об)["providers"]),
        "пользовательские-рейтинги":
            readmodel.пользовательский_рейтинг(соед, об)["aggregate"]["count"],
        "resolver": readmodel.разрешить_адрес(соед, об)["outcome"]}

    # 5. искусственная ошибка: DLQ, checkpoint, восстановление
    пусто = ingest.импорт_сущностей(соед, [], маршруты)
    после_сбоя = соед.execute("SELECT count(*) c FROM entity").fetchone()["c"]
    dlq = соед.execute("SELECT error_code, attempts FROM dead_letter "
                       "ORDER BY id DESC LIMIT 1").fetchone()
    вост = ingest.импорт_сущностей(соед, записи, маршруты)
    чек = соед.execute("SELECT checksum, last_success, error_code FROM "
                       "import_state WHERE stream='entities'").fetchone()
    м["faultInjection"] = {
        "emptySkipped": пусто.get("skipped"), "keptEntities": после_сбоя,
        "dlqCode": dlq["error_code"] if dlq else None,
        "dlqAttempts": dlq["attempts"] if dlq else None,
        "recovered": вост.get("new") == 0 and после_сбоя == n_ent,
        "checkpointCleared": чек["error_code"] is None,
        "checkpoint": чек["checksum"][:12] if чек["checksum"] else None}

    # 10. время, память, неизменность production
    после_ф = ПРОЕКЦИЯ.read_bytes() if ПРОЕКЦИЯ.exists() else b""
    м["production"] = {"projectionUnchanged": до_ф == после_ф,
                       "showcaseDbBefore": до_бд, "showcaseDbAfter": бд_витрины()}
    м["production"]["showcaseDbUnchanged"] = (
        м["production"]["showcaseDbBefore"] == м["production"]["showcaseDbAfter"])
    м["perf"] = {"seconds": round(time.time() - t0, 2),
                 "maxRssMb": round(
                     resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)}
    м["verdict"] = ("PASS" if м["idempotent"]["ok"]
                    and м["addresses"]["terminal404"] == 0 and not плохие
                    and м["production"]["projectionUnchanged"]
                    and м["production"]["showcaseDbUnchanged"]
                    and м["faultInjection"]["recovered"] else "FAIL")
    return м


def main() -> int:
    ЖУРНАЛ.parent.mkdir(parents=True, exist_ok=True)
    for i in range(1, ЦИКЛОВ + 1):
        м = цикл(i)
        with ЖУРНАЛ.open("a", encoding="utf-8") as f:
            f.write(json.dumps(м, ensure_ascii=False) + "\n")
        print("цикл %d: %s за %.1f с, сущностей %d, 404 %d, prod без изменений %s"
              % (i, м["verdict"], м["perf"]["seconds"],
                 м["counts"]["shadowEntities"], м["addresses"]["terminal404"],
                 м["production"]["projectionUnchanged"]
                 and м["production"]["showcaseDbUnchanged"]), flush=True)
        if i < ЦИКЛОВ:
            time.sleep(ПАУЗА)
    return 0


if __name__ == "__main__":
    sys.exit(main())
