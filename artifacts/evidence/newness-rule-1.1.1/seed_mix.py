#!/usr/bin/env python3
"""Засев представительной смеси: архив, свежее, будущее, без даты.

Доли взяты с боевого снимка lords-01: в окне по дате загрузки архив составлял
большинство. Если правило новинок сломается, это видно сразу — на полке
появятся карточки с годом из прошлого века.
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

КУДА = Path(sys.argv[1]); КУДА.mkdir(parents=True, exist_ok=True)
SITE = sys.argv[2] if len(sys.argv) > 2 else "lords-90"
ПОКОЛЕНИЕ = sys.argv[3] if len(sys.argv) > 3 else "mix-1"
СЕГОДНЯ = date.today()

записи, детали = [], {}

def добавить(slug, title, kind, тип, год, дней_назад, жанры, оценка=7.8, сезоны=()):
    з = {"slug": slug, "url": f"/title/{slug}/", "title": title, "kind": kind,
         "poster": f"https://img.example/{slug}.jpg", "original_title": title}
    if год is not None:
        з["year"] = год
    if дней_назад is not None:
        з["published_at"] = (СЕГОДНЯ - timedelta(days=дней_назад)).isoformat() + "T04:00:00Z"
    записи.append(з)
    детали[slug] = {"id": f"cvh-{slug}", "slug": slug, "genres": list(жанры), "type": тип,
                    "seasons": [dict(с) for с in сезоны], "countries": ["Россия"],
                    "description": f"Описание «{title}».", "imdb_rating": оценка,
                    "kinopoisk_rating": round(оценка - 0.3, 1), "playable": True,
                    "external_ids": {"kp": f"kp{abs(hash(slug)) % 100000}"}}

# 1. АРХИВ, загруженный сегодня — главная причина дефекта. 120 записей.
for i in range(120):
    год = 1955 + (i % 60)
    добавить(f"arh-{i:03d}", f"Архивный фильм {год} года", "Фильм", "movie",
             год, i % 3, ["драма"], 6.5 + (i % 30) / 10)

# 2. СВЕЖЕЕ, вышло в окне. 40 записей.
for i in range(40):
    год = СЕГОДНЯ.year if i % 2 else СЕГОДНЯ.year - 1
    добавить(f"nov-{i:03d}", f"Новинка {год} номер {i}", "Фильм", "movie",
             год, i % 25, ["боевик"], 7.0 + (i % 25) / 10)

# 3. СЕРИАЛЫ: старый продолжающийся и новый. 20 записей.
for i in range(10):
    добавить(f"ser-old-{i:02d}", f"Старый сериал {i}", "Сериал", "tv",
             2011 + (i % 5), i % 5, ["драма"], 8.0,
             сезоны=[{"n": s, "eps": 10, "avail": 10} for s in range(1, 9)])
for i in range(10):
    добавить(f"ser-new-{i:02d}", f"Новый сериал {i}", "Сериал", "tv",
             СЕГОДНЯ.year, i % 20, ["фантастика"], 8.2,
             сезоны=[{"n": 1, "eps": 8, "avail": 8}])

# 4. БУДУЩАЯ премьера. 8 записей.
for i in range(8):
    добавить(f"bud-{i:02d}", f"Премьера {СЕГОДНЯ.year + 1} номер {i}", "Фильм", "movie",
             СЕГОДНЯ.year + 1, i % 4, ["фантастика"], 0.0)

# 5. БЕЗ ГОДА, загружено сегодня. 12 записей.
for i in range(12):
    добавить(f"nog-{i:02d}", f"Без даты выхода {i}", "Фильм", "movie",
             None, i % 3, ["комедия"], 6.0)

# 6. Мультфильмы и аниме, чтобы разделы не были пустыми.
for i in range(20):
    добавить(f"mult-{i:02d}", f"Мультфильм {i}", "Мультфильм", "movie",
             СЕГОДНЯ.year - (i % 2), i % 10, ["мультфильм", "семейный"], 7.5)

# 7. Аниме и дорамы — иначе семейства Animedia и Yummy показывают пустой
#    каталог, и проверка новинок проходит ни на чём.
for i in range(20):
    год = СЕГОДНЯ.year if i % 2 else 1998 + (i % 20)
    добавить(f"anime-{i:02d}", f"Аниме {i}", "Сериал", "tv", год, i % 8,
             ["аниме", "фантастика"], 7.9,
             сезоны=[{"n": 1, "eps": 12, "avail": 12}])
for i in range(12):
    год = СЕГОДНЯ.year - (i % 2) if i % 3 else 2005 + (i % 10)
    добавить(f"dorama-{i:02d}", f"Дорама {i}", "Сериал", "tv", год, i % 6,
             ["дорама", "драма"], 7.6,
             сезоны=[{"n": 1, "eps": 16, "avail": 16}])

(КУДА / f"{SITE}-catalog.json").write_text(json.dumps(
    {"revision": ПОКОЛЕНИЕ, "built_at": SITE, "items": записи}, ensure_ascii=False),
    encoding="utf-8")
(КУДА / f"{SITE}-details.json").write_text(json.dumps(
    {"catalog_revision": ПОКОЛЕНИЕ, "source": "смесь приёмки",
     "details_total": len(детали), "details": детали}, ensure_ascii=False), encoding="utf-8")
print(json.dumps({"всего": len(записи), "архив": 120, "новинок": 40,
                  "сериалов": 20, "будущих": 8, "без_года": 12, "мультфильмов": 20, "аниме": 20, "дорам": 12},
                 ensure_ascii=False))
