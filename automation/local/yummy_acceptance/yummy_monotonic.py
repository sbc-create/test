"""Монотонность состава части карты: второе чтение обязано быть надмножеством первого.

python3 yummy_monotonic.py <домен> <префикс частей, напр. episodes> [интервал_с=3600] [снимок.xml ...]
Сравнивается ОБЪЕДИНЕНИЕ всех частей индекса с этим префиксом (episodes.xml, episodes-2.xml, …):
части режутся по 50 000, и адрес, переехавший в соседнюю часть, потерей не является.
Без снимков читает части, ждёт интервал и читает снова; со снимками сравнивает их с текущим чтением.
Код 0 — надмножество; 1 — адреса выпали (печатает, по каким работам); 2 — не измерено.
"""
import collections, re, sys, time, urllib.request

D, PART = sys.argv[1], sys.argv[2]
WAIT = int(sys.argv[3]) if len(sys.argv) > 3 else 3600
UA = {"User-Agent": "sf-seo-audit/1.0"}

def get(u):
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=120).read().decode()

def read():
    idx = get(f"https://{D}/sitemap.xml")
    parts = [u for u in re.findall(r"<loc>([^<]+)</loc>", idx) if re.search(rf"/{re.escape(PART)}(-\d+)?\.xml$", u)]
    if not parts:
        raise RuntimeError(f"в индексе нет частей {PART}*.xml")
    out = set()
    for u in parts:
        out |= set(re.findall(r"<loc>([^<]+)</loc>", get(u)))
    return out

try:
    if len(sys.argv) > 4:
        a = set()
        for f in sys.argv[4:]:
            a |= set(re.findall(r"<loc>([^<]+)</loc>", open(f).read()))
    else:
        a = read(); time.sleep(WAIT)
    b = read()
except Exception as e:  # noqa: BLE001
    print(f"НЕ ИЗМЕРЕНО: {type(e).__name__}: {e}"); sys.exit(2)
lost, added = a - b, b - a
work = lambda s: collections.Counter(u.split("/anime/")[1].split("/")[0] for u in s if "/anime/" in u)
print(f"{D} {PART}: было {len(a)}, стало {len(b)}, выпало {len(lost)}, добавилось {len(added)}")
if lost:
    print("выпали по работам:", work(lost).most_common(10)); sys.exit(1)
print("надмножество: да"); sys.exit(0)
