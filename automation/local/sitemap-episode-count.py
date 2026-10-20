"""Сколько адресов серий объявляет каждый домен — по ВСЕМ частям карты.

Только чтение. Моя прежняя оценка смотрела лишь первый файл `episodes.xml` и
потому занизила разрыв: у yummyani.biz серии разбиты на три файла.
"""
import re
import urllib.error
import urllib.request

АГЕНТ = "factory-episode-count"


def добыть(адрес, таймаут=150):
    з = urllib.request.Request(адрес, headers={"User-Agent": АГЕНТ})
    try:
        with urllib.request.urlopen(з, timeout=таймаут) as о:
            return о.status, о.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as ош:
        return ош.code, ""
    except (urllib.error.URLError, OSError, TimeoutError) as ош:
        return 0, f"{type(ош).__name__}"


for домен in ("yummyani.site", "yummyani.biz", "yummyani7.site"):
    код, индекс = добыть(f"https://{домен}/sitemap.xml")
    части = re.findall(r"<loc>([^<]+)</loc>", индекс)
    серии = [ч for ч in части if "episode" in ч]
    сезоны = [ч for ч in части if "season" in ч]
    всего_серий = 0
    адреса = set()
    for ч in серии:
        к, тело = добыть(ч)
        n = len(re.findall(r"<loc>", тело))
        всего_серий += n
        адреса |= set(re.findall(r"<loc>https?://[^/]+(/anime/[^<]+)</loc>", тело))
        print(f"   {домен:16} {ч.rsplit('/', 1)[-1]:18} код {к} адресов {n}")
    всего_сезонов = 0
    for ч in сезоны:
        к, тело = добыть(ч)
        всего_сезонов += len(re.findall(r"<loc>", тело))
    print(f"{домен:16} частей серий {len(серии)}  адресов серий {всего_серий}"
          f"  уникальных путей {len(адреса)}  сезонов {всего_сезонов}\n")
    globals().setdefault("наборы", {})[домен] = адреса

наборы = globals()["наборы"]
если_есть = наборы.get("yummyani.biz", set()) - наборы.get("yummyani.site", set())
print(f"серий, которые есть у yummyani.biz и НЕТ в карте yummyani.site:"
      f" {len(если_есть)}")
