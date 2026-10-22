"""Монотонность состава части карты: второе чтение обязано быть надмножеством первого.

python3 yummy_monotonic.py <домен> <часть, напр. episodes.xml> [интервал_с=3600] [предыдущий_снимок.xml]
Без снимка читает часть, ждёт интервал и читает снова; со снимком сравнивает его с текущим чтением.
Код 0 — надмножество; 1 — адреса выпали (печатает, по каким работам); 2 — не измерено.
"""
import collections, re, sys, time, urllib.request

D, PART = sys.argv[1], sys.argv[2]
WAIT = int(sys.argv[3]) if len(sys.argv) > 3 else 3600
UA = {"User-Agent": "sf-seo-audit/1.0"}

def read():
    b = urllib.request.urlopen(urllib.request.Request(f"https://{D}/sitemap/{PART}", headers=UA), timeout=120).read().decode()
    return set(re.findall(r"<loc>([^<]+)</loc>", b))

try:
    if len(sys.argv) > 4:
        a = set(re.findall(r"<loc>([^<]+)</loc>", open(sys.argv[4]).read()))
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
