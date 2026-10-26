#!/usr/bin/env python3
"""Промежуточная оценка строк журнала изменений по Метрике (только чтение).

Для каждой строки: доля поисковых входов домена, пришедшая на затронутые
страницы, по поисковым системам раздельно, в окне 7 дней до изменения и
7 дней после. Доля, а не число, — чтобы общий ход домена (ряды сети волатильны,
MOD-169) не выдавался за эффект. Знак засчитывается, только если он одинаков
при сдвиге обоих окон на −2…+2 суток; иначе — «не определён». Для строк с
ожиданием по поведению — отказы и глубина органических визитов людей
(`daily_traffic_profile`, isRobot = People).

    python3 automation/local/ledger-interim-eval.py [--out путь.json]

Источник — artifacts/analytics/analytics-2026-10-*.json (каждая выгрузка —
7 дней; дни из разных выгрузок не суммируются, берётся последнее значение).
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import re
from collections import defaultdict
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]


def загрузить():
    входы: dict = {}      # (домен, дата, система, адрес) -> визиты
    профиль: dict = {}    # (домен, дата) -> [визиты, отказы*визиты, глубина*визиты]
    сырой_профиль: dict = {}
    for f in sorted(glob.glob(str(КОРЕНЬ / "artifacts/analytics/analytics-2026-10-*.json"))):
        try:
            d = json.load(open(f, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for dom in d.get("domains", []):
            for m in dom.get("measurements", []):
                if not m.get("measured") or not isinstance(m.get("value"), list):
                    continue
                if m["key"] == "daily_search_landing_pages":
                    for r in m["value"]:
                        ds = [x["name"] for x in r["dimensions"]]
                        входы[(dom["domain"], ds[0], ds[1], ds[2])] = r["metrics"][0]
                elif m["key"] == "daily_traffic_profile":
                    for r in m["value"]:
                        ds = r["dimensions"]
                        if len(ds) < 5 or len(r["metrics"]) < 3:
                            continue  # ранние выгрузки — без признака робота
                        if ds[1].get("id") != "organic" or ds[4].get("id") != "no":
                            continue
                        ключ = (dom["domain"], ds[0]["name"], ds[2].get("id"), ds[3].get("id"))
                        сырой_профиль[ключ] = r["metrics"]
    for (домен, дата, _, _), (в, отк, глуб, *_) in сырой_профиль.items():
        п = профиль.setdefault((домен, дата), [0.0, 0.0, 0.0])
        п[0] += в
        п[1] += в * отк
        п[2] += в * глуб
    return входы, профиль


def окно(начало: dt.date, дней: int = 7) -> list[str]:
    return [(начало + dt.timedelta(days=i)).isoformat() for i in range(дней)]


def доля(входы, домен, дни, отбор, система):
    всего = цель = 0.0
    дни_с_данными = set()
    for (д, дата, сист, адрес), в in входы.items():
        if д != домен or дата not in дни or (система and сист != система):
            continue
        дни_с_данными.add(дата)
        всего += в
        if отбор(адрес):
            цель += в
    return цель, всего, len(дни_с_данными)


def оценить_входы(входы, домены, изменение: dt.date, отбор):
    итог = {}
    for домен in домены:
        for система in ("Yandex", "Google"):
            строки = []
            for сдвиг in range(-2, 3):
                до = окно(изменение - dt.timedelta(days=7 - сдвиг))
                после = окно(изменение + dt.timedelta(days=1 + сдвиг))
                ц0, в0, н0 = доля(входы, домен, set(до), отбор, система)
                ц1, в1, н1 = доля(входы, домен, set(после), отбор, система)
                строки.append({"сдвиг": сдвиг, "до": [ц0, в0, н0], "после": [ц1, в1, н1]})
            база = строки[2]
            полные = [с for с in строки if с["до"][2] == 7 and с["после"][2] == 7]
            знаки = set()
            for с in полные:
                д0 = с["до"][0] / с["до"][1] if с["до"][1] else None
                д1 = с["после"][0] / с["после"][1] if с["после"][1] else None
                if д0 is not None and д1 is not None:
                    знаки.add((д1 > д0) - (д1 < д0))
            if not полные:
                вывод = "нет полных окон"
            elif база["до"][1] + база["после"][1] < 20:
                вывод = "мало данных"
            elif len(знаки) == 1:
                вывод = {1: "доля выросла", -1: "доля снизилась", 0: "без изменения"}[знаки.pop()]
            else:
                вывод = "знак не определён"
            итог[f"{домен}/{система}"] = {
                "цель_до": база["до"][0], "всего_до": база["до"][1],
                "цель_после": база["после"][0], "всего_после": база["после"][1],
                "полных_окон": len(полные), "вывод": вывод}
    return итог


def оценить_поведение(профиль, домены, изменение: dt.date):
    итог = {}
    for домен in домены:
        out = {}
        for имя, дни in (("до", окно(изменение - dt.timedelta(days=7))),
                         ("после", окно(изменение + dt.timedelta(days=1)))):
            в = отк = гл = 0.0
            н = 0
            for день in дни:
                п = профиль.get((домен, день))
                if п:
                    н += 1
                    в += п[0]; отк += п[1]; гл += п[2]
            out[имя] = {"визиты": в, "отказы_%": round(отк / в, 1) if в else None,
                        "глубина": round(гл / в, 2) if в else None, "дней": н}
        итог[домен] = out
    return итог


def тайтл_yummy(a):
    return bool(re.search(r"/anime/[^/?#]+/?$", a.split("?")[0]))


def сезон_серия_yummy(a):
    return "/season/" in a or "/episode/" in a


СТРОКИ = [
    {"строка": "B031", "дата": "2026-10-16", "домены": ["yummyani.biz", "yummyani.org", "yummyani.site"],
     "отбор": тайтл_yummy, "что": "доля поиска на страницах тайтла /anime/<slug>; yummyani.site — контроль"},
    {"строка": "B033", "дата": "2026-10-16", "домены": ["yummyani.biz", "yummyani.org", "yummyani.site"],
     "отбор": сезон_серия_yummy, "что": "доля поиска на сезонах и сериях; yummyani.site — контроль; B031 и B033 не разделяются"},
    {"строка": "T185–T189", "дата": "2026-10-17", "домены": ["zonafilm.space", "zonafilm.cc", "lordserial33.biz", "zonafilm12.site"],
     "отбор": lambda a: "genre" in a, "что": "доля поиска на разделах жанров", "поведение": True},
    {"строка": "T192–T199", "дата": "2026-10-18", "домены": ["zonafilm.space", "zonafilm12.site", "an1mego.site", "animeg0.site", "an1meg0.site", "animedia.icu"],
     "отбор": lambda a: "/title/" in a, "что": "доля поиска на тайтлах", "поведение": True},
    {"строка": "T208–T213", "дата": "2026-10-18", "домены": ["animedia.icu"],
     "отбор": lambda a: any(x in a for x in ("/collections", "/collection/", "/types/")), "что": "доля поиска на подборках и /types/"},
    {"строка": "T211, T214–T220", "дата": "2026-10-18", "домены": ["an1mego.site", "animeg0.site", "an1meg0.site", "animedia.icu"],
     "отбор": lambda a: any(x in a for x in ("/movies", "/series")), "что": "доля поиска на /movies/, /series/"},
    {"строка": "T160–T166 и редакционная чистка", "дата": "2026-10-16", "домены": ["an1mego.site", "animeg0.site", "an1meg0.site", "zonafilm.space", "lordserials22.info"],
     "отбор": None, "что": "отказы и глубина органики", "поведение": True},
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(КОРЕНЬ / "artifacts/evidence/ledger-interim-eval-20261026.json"))
    a = ap.parse_args()
    входы, профиль = загрузить()
    итог = []
    for с in СТРОКИ:
        дата = dt.date.fromisoformat(с["дата"])
        запись = {"строка": с["строка"], "изменение": с["дата"], "что": с["что"]}
        if с["отбор"]:
            запись["входы"] = оценить_входы(входы, с["домены"], дата, с["отбор"])
        if с.get("поведение"):
            запись["поведение"] = оценить_поведение(профиль, с["домены"], дата)
        итог.append(запись)
    Path(a.out).write_text(json.dumps(итог, ensure_ascii=False, indent=1), encoding="utf-8")
    for з in итог:
        print("==", з["строка"], "—", з["что"])
        for к, в in (з.get("входы") or {}).items():
            print(f"   {к}: {в['цель_до']:.0f}/{в['всего_до']:.0f} → {в['цель_после']:.0f}/{в['всего_после']:.0f}; "
                  f"полных окон {в['полных_окон']}; {в['вывод']}")
        for к, в in (з.get("поведение") or {}).items():
            print(f"   {к}: отказы {в['до']['отказы_%']} → {в['после']['отказы_%']}, глубина {в['до']['глубина']} → "
                  f"{в['после']['глубина']}, визиты {в['до']['визиты']:.0f} → {в['после']['визиты']:.0f} (дней {в['до']['дней']}/{в['после']['дней']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
