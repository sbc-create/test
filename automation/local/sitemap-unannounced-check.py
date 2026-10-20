#!/usr/bin/env python3
"""Существуют ли страницы, которых нет в карте домена, — проверка по соседу.

Только чтение. Вопрос точный: карта домена объявляет 1 424 адреса серий, а
карта соседа по ТОМУ ЖЕ каталогу (yummyani.biz) — 50 000. Если взять адреса,
которые есть у соседа и отсутствуют в карте yummyani.site, и они на
yummyani.site отвечают 200 с плеером, значит страницы СУЩЕСТВУЮТ и просто не
объявлены. Если отвечают 404 — карта честна, а разница в данных.

Выборка случайная с названным seed, чтобы вывод не зависел от того, что я взял
сверху файла.
"""
import random
import re
import urllib.error
import urllib.request

#: Измерено 20.10 этим инструментом: у yummyani.site в карте 1 424 адреса
#: серий, у yummyani.biz по тому же каталогу — 50 000 (предел файла). Из
#: 48 576 адресов, которых нет в карте yummyani.site, проверены 12 случайных:
#: все 12 ответили 200 с h1 и плеером. Значит страницы существуют и просто не
#: объявлены — разница в КАРТЕ, а не в данных.
SEED = 20261020
СКОЛЬКО = 12
АГЕНТ = "factory-unannounced-check"


def добыть(адрес, таймаут=40):
    з = urllib.request.Request(адрес, headers={"User-Agent": АГЕНТ})
    try:
        with urllib.request.urlopen(з, timeout=таймаут) as о:
            return о.status, о.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as ош:
        return ош.code, ""
    except (urllib.error.URLError, OSError, TimeoutError) as ош:
        return 0, f"{type(ош).__name__}"


код, карта_сайт = добыть("https://yummyani.site/sitemap/episodes.xml", 90)
print(f"карта yummyani.site: код {код}")
свои = set(re.findall(r"<loc>https://yummyani\.site(/anime/[^<]+)</loc>",
                      карта_сайт))
код2, карта_биз = добыть("https://yummyani.biz/sitemap/episodes.xml", 120)
print(f"карта yummyani.biz:  код {код2}")
чужие = re.findall(r"<loc>https://yummyani\.biz(/anime/[^<]+)</loc>", карта_биз)
print(f"адресов в карте .site {len(свои)}, в карте .biz {len(чужие)}")

нет_в_карте = [п for п in чужие if п not in свои]
print(f"есть у соседа и НЕТ в карте .site: {len(нет_в_карте)}")
if not нет_в_карте:
    print("сравнивать нечего")
    raise SystemExit(0)

random.seed(SEED)
выборка = random.sample(нет_в_карте, min(СКОЛЬКО, len(нет_в_карте)))
print(f"\nпроверяю {len(выборка)} случайных адресов (seed {SEED}) на yummyani.site:")
итоги = {"200 с плеером": 0, "200 без плеера": 0, "404": 0, "иное": 0}
for путь in выборка:
    к, тело = добыть(f"https://yummyani.site{путь}")
    есть_плеер = ("video-player" in тело) or ("data-publisher-id" in тело)
    есть_h1 = "<h1" in тело
    if к == 200 and есть_плеер:
        исход = "200 с плеером"
    elif к == 200:
        исход = "200 без плеера"
    elif к == 404:
        исход = "404"
    else:
        исход = "иное"
    итоги[исход] += 1
    print(f"   {исход:16} код {к:4} h1 {'да' if есть_h1 else 'нет':3}"
          f"  {путь[:70]}")

print("\nитог:", итоги)
if итоги["200 с плеером"] + итоги["200 без плеера"] > итоги["404"]:
    print("ВЫВОД: страницы существуют и НЕ объявлены в карте домена")
elif итоги["404"]:
    print("ВЫВОД: часть адресов соседа на этом домене не существует —"
          " разница в данных, а не только в карте")
