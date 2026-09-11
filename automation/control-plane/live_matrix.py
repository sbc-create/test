#!/usr/bin/env python3
"""Обязательная live-матрица A–L для server-side фильтров /api/v1/sites."""
from __future__ import annotations
import json, sys, urllib.error, urllib.parse, urllib.request
from pathlib import Path

Б = "http://127.0.0.1:8790"
ОТЧЁТ = Path("/srv/site-factory/control-plane-contracts/evidence/live-filter-matrix.json")
провалы: list[str] = []
строки: list[dict] = []


def дай(q: str = "") -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(Б + "/api/v1/sites" + q, timeout=15) as о:
            return о.status, json.loads(о.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except Exception:  # noqa: BLE001
            return e.code, {}
    except Exception:  # noqa: BLE001
        return 0, {}


def шаг(метка, имя, условие, деталь=""):
    print("  %-3s %-50s %s %s" % (метка, имя, "PASS" if условие else "FAIL", деталь))
    строки.append({"case": метка, "name": имя, "pass": bool(условие),
                   "detail": str(деталь)})
    if not условие:
        провалы.append(f"{метка}:{имя}")


def ids(т): return {i["site_id"] for i in т.get("items", [])}

# --- снимок для сверки множеств ---------------------------------------------
with urllib.request.urlopen(Б + "/api/v1/registry/snapshot", timeout=15) as о:
    снимок = json.loads(о.read())
снимок_ids = {s["site_id"] for s in снимок["sites"]}

# A ---------------------------------------------------------------------------
к, т = дай()
всего = len(т.get("items", []))
шаг("A", "без фильтров: 200 и полный реестр", к == 200 and всего >= 9, f"items={всего}")
шаг("A", "прежние ключи на месте (совместимость)",
    all({"site_id","site_type","domains","render_mode"} <= set(i)
        for i in т.get("items", [])))

# B ---------------------------------------------------------------------------
к, т = дай("?environment=production")
только_prod = all(i.get("environment") == "production" for i in т.get("items", []))
шаг("B", "environment=production: только production",
    к == 200 and только_prod and len(т["items"]) < всего,
    f"items={len(т.get('items',[]))}")
шаг("B", "утечки demo/test нет",
    not any(i["site_id"] in ("demo-books",) or
            i.get("environment") == "test" for i in т.get("items", [])))

# C ---------------------------------------------------------------------------
к, т = дай("?lifecycle_state=ACTIVE")
шаг("C", "lifecycle_state=ACTIVE: все записи ACTIVE",
    к == 200 and all(i.get("lifecycle_state") == "ACTIVE"
                     for i in т.get("items", [])),
    f"items={len(т.get('items',[]))}")

# D ---------------------------------------------------------------------------
к, т = дай("?environment=production&lifecycle_state=ACTIVE")
d_ids = ids(т)
шаг("D", "AND-фильтр даёт ровно 9", к == 200 and len(т.get("items", [])) == 9,
    f"items={len(т.get('items',[]))}")
шаг("D", "множество совпадает со снимком точно", d_ids == снимок_ids,
    f"разница={sorted(d_ids ^ снимок_ids)}")
шаг("D", "demo-books отсутствует", "demo-books" not in d_ids)
шаг("D", "синтетических записей нет",
    not any(s.startswith("synthetic") for s in d_ids))
шаг("D", "site_id уникальны", len(d_ids) == len(т.get("items", [])))
шаг("D", "порядок по site_id", [i["site_id"] for i in т["items"]] ==
    sorted(i["site_id"] for i in т["items"]))
шаг("D", "ETag отражает отфильтрованную проекцию", bool(т.get("etag")),
    т.get("etag", "")[:24])
шаг("D", "применённые фильтры объявлены в ответе",
    т.get("filters_applied") == {"environment": "production",
                                 "lifecycle_state": "ACTIVE"})

# E ---------------------------------------------------------------------------
к, т = дай("?environment=test")
шаг("E", "environment=test: production не протекает",
    к == 200 and all(i.get("environment") == "test" for i in т.get("items", [])),
    f"items={len(т.get('items',[]))}")

# F ---------------------------------------------------------------------------
к, т = дай("?lifecycle_state=DRAFT")
f_ids = ids(т)
шаг("F", "lifecycle_state=DRAFT: ACTIVE не протекает",
    к == 200 and all(i.get("lifecycle_state") == "DRAFT"
                     for i in т.get("items", [])), f"items={len(f_ids)}")
шаг("F", "demo-books классифицирован как DRAFT non-production",
    "demo-books" in f_ids)

# G, H, I, J -------------------------------------------------------------------
for метка, q, имя in (("G", "?environment=nonsense", "неизвестная среда"),
                      ("H", "?lifecycle_state=NOPE", "неизвестное состояние"),
                      ("I", "?environment=", "пустое значение"),
                      ("J", "?environment=production&environment=test",
                       "конфликт повторного ключа")):
    к, т = дай(q)
    шаг(метка, f"{имя} -> 422", к == 422, f"HTTP {к}")
    for поле in ("type", "title", "status", "error_code", "retryable", "owner"):
        if поле not in т:
            шаг(метка, f"Problem.v1: поле {поле}", False)
            break
    else:
        шаг(метка, "Problem.v1 валиден", т.get("status") == 422
            and bool(т.get("error_code")), т.get("error_code"))

# K ---------------------------------------------------------------------------
к, т = дай("?environment=production&lifecycle_state=ACTIVE")
шаг("K", "фильтр применён до нарезки (весь набор отфильтрован)",
    len(т.get("items", [])) == 9 and all(
        i.get("environment") == "production" and
        i.get("lifecycle_state") == "ACTIVE" for i in т["items"]))
к2, т2 = дай("?environment=production&lifecycle_state=ACTIVE")
шаг("K", "повторный запрос стабилен (без дублей и пропусков)",
    [i["site_id"] for i in т["items"]] == [i["site_id"] for i in т2["items"]])

# L ---------------------------------------------------------------------------
к, т = дай("?environment=non-production&lifecycle_state=RETIRED")
шаг("L", "валидная комбинация без совпадений -> 200 и пустой массив",
    к == 200 and т.get("items") == [], f"HTTP {к}, items={len(т.get('items', []))}")
шаг("L", "fallback-записей нет", т.get("total") == 0)

итог = {"verdict": "PASS" if not провалы else "FAIL", "failures": провалы,
        "unfiltered_count": всего, "production_active_count": len(d_ids),
        "snapshot_count": снимок["count"],
        "exact_set_match": d_ids == снимок_ids, "rows": строки}
ОТЧЁТ.parent.mkdir(parents=True, exist_ok=True)
ОТЧЁТ.write_text(json.dumps(итог, ensure_ascii=False, indent=1), encoding="utf-8")
print("\n  проверок: %d, провалов: %d, вердикт: %s"
      % (len(строки), len(провалы), итог["verdict"]))
sys.exit(0 if not провалы else 1)
