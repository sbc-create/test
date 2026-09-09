"""Согласие производителя и потребителя об адресе — на всех маршрутах.

Проверка на 71 записи очереди показывает, что механизм работает. Она не
показывает, что он работает везде: приведение адреса объявлено версией
(`core-route-normalization/1.0.0` у нас, `seo-route-normalization/1.0.0` у
потребителя), и расхождение двух приведений выглядело бы не ошибкой, а
страницей, которой нет в снимке. Поэтому ключ сверяется на каждом маршруте
всех шести витрин.

Сверяется то, что потребитель действительно делает: берёт canonicalUrl,
приводит путь и вырезает ключ произведения объявленными префиксами. Результат
обязан совпасть с routeKey, который записал производитель.
"""
import json, pathlib, sys, collections

SEO = "/home/claude/wt-seo-kind-34"
CORE = "/home/claude/wt-core-ident-35"
sys.path.insert(0, SEO)
from seo_engine.binding import route_resolution as rr

префиксы = {}
for f in sorted((pathlib.Path(CORE) / "config/site-profiles").glob("*.json")):
    d = json.loads(f.read_text())
    префиксы[d["site_id"]] = tuple(
        d.get("seo_profile", {}).get("title_prefixes") or ())

итог, всего_расхождений = {}, 0
for путь in sorted(pathlib.Path("/home/claude/ident-35-artifacts/snapshots"
                                ).glob("route-snapshot-*.json")):
    снимок = json.loads(путь.read_text())
    витрина = снимок["siteId"]
    пр = префиксы.get(витрина, ())
    расхождения, пустые, ключи = [], 0, collections.Counter()
    for з in снимок["records"]:
        ключи[з["routeKey"]] += 1
        адрес = з.get("canonicalUrl") or ""
        if not адрес:
            пустые += 1          # COLLISION-записи адреса не имеют — так и надо
            continue
        ключ, _ = rr.work_key(rr.normalize_path(адрес), пр)
        if ключ != з["routeKey"]:
            расхождения.append({"routeKey": з["routeKey"],
                                "canonicalUrl": адрес, "consumerKey": ключ})
    дубли = [к for к, n in ключи.items() if n > 1]
    всего_расхождений += len(расхождения)
    итог[витрина] = {"records": len(снимок["records"]),
                     "prefixes": list(пр),
                     "keyMismatches": len(расхождения),
                     "duplicateRouteKeys": len(дубли),
                     "recordsWithoutUrl": пустые,
                     "examples": расхождения[:3]}
    print(f"{витрина:<16} записей {len(снимок['records']):>6}  "
          f"расхождений ключа {len(расхождения):>4}  "
          f"дублей ключа {len(дубли):>4}  без адреса {пустые:>5}")

print(f"\nвсего расхождений производителя и потребителя: {всего_расхождений}")
(pathlib.Path(CORE) / "reports/CORE-UNIFIED-IDENTITY-PROVENANCE-35/"
 "SCALE-ROUTE-AGREEMENT.json").write_text(json.dumps(
    {"producerNormalization": "core-route-normalization/1.0.0",
     "consumerNormalization": rr.NORMALIZATION_VERSION,
     "totalMismatches": всего_расхождений, "bySite": итог},
    ensure_ascii=False, indent=1), encoding="utf-8")
sys.exit(0 if всего_расхождений == 0 else 1)
