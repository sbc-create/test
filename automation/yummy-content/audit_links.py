"""Сколько карточек нынешней проекции ведут в никуда — и почему."""
import collections, json, pathlib, sys, urllib.error, urllib.request
sys.path.insert(0, "/srv/site-factory/yummy-content")
from canonical import Резолвер, маршруты_из_базы, путь_по_слагу, Исход

маршруты = маршруты_из_базы("yummyani-staging-pg-site-1")
р = Резолвер(маршруты)
print("таблица маршрутов витрины: %d записей" % р.всего)

кат = json.loads(pathlib.Path(
    "/srv/lords/.frontend/yummy-site-catalog.json").read_text(encoding="utf-8"))
items = кат["items"]
print("nova-каталог (то, что видит шаблон): %d записей\n" % len(items))

# В нынешнем каталоге идентификатора произведения НЕТ вовсе — только слаг.
слаг_к_ид = {м["slug"]: м["providerTitleId"] for м in маршруты}
исходы = collections.Counter()
примеры = collections.defaultdict(list)
for з in items:
    слаг = (з.get("slug") or "").strip("/")
    ид = слаг_к_ид.get(слаг)
    ссылка = р.разрешить(ид or "")
    исходы[ссылка.outcome] += 1
    if len(примеры[ссылка.outcome]) < 3:
        примеры[ссылка.outcome].append((з.get("url"), слаг))

print("=== разрешимость записей нынешней проекции ===")
for и, n in исходы.most_common():
    print("  %-22s %5d  (%.1f%%)" % (и.value, n, 100.0 * n / len(items)))
    for url, слаг in примеры[и]:
        print("        url=%s slug=%s" % (url, слаг))

def код(путь: str) -> int:
    зпр = urllib.request.Request("http://127.0.0.1:3101" + путь,
                                 headers={"Host": "yummyani.site",
                                          "User-Agent": "content-probe/1.0"})
    try:
        with urllib.request.urlopen(зпр, timeout=15) as о:
            return о.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0

print("\n=== фактические ответы приложения ===")
import random
random.seed(11)
проба = random.sample(items, 25)
плохих = 0
for з in проба:
    старый = з.get("url") or ""
    новый = путь_по_слагу((з.get("slug") or ""))
    c1, c2 = код(старый), код(новый)
    if c1 != 200:
        плохих += 1
    if плохих <= 5 and c1 != 200:
        print("  как в каталоге %-3s -> %-46s" % (c1, старый))
        print("  по контракту   %-3s -> %s" % (c2, новый))
print("  из 25 проб: битых по нынешнему url — %d" % плохих)
