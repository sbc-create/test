#!/usr/bin/env python3
"""Засев проверочного экземпляра: каталог и подробности.

Данные синтетические и живут только в каталоге проверки. Ни один живой снимок
не читается и не пишется.
"""
import json
import sys
from pathlib import Path

КУДА = Path(sys.argv[1])
ПОКОЛЕНИЕ = sys.argv[2] if len(sys.argv) > 2 else "rev-1"
ДОБАВКА = json.loads(sys.argv[3]) if len(sys.argv) > 3 else []

КУДА.mkdir(parents=True, exist_ok=True)
ЖАНРЫ_КИНО = ["боевик", "драма", "комедия", "триллер", "фантастика"]
записи, детали = [], {}

def добавить(slug, title, kind, тип, жанры, год, оценка, дата, сезоны=(), играет=True):
    записи.append({
        "slug": slug, "url": f"/title/{slug}/", "title": title, "kind": kind,
        "year": год, "poster": f"https://img.example/{slug}.jpg",
        "published_at": дата, "original_title": title,
    })
    детали[slug] = {
        "id": f"cvh-{slug}", "slug": slug, "genres": list(жанры), "type": тип,
        "seasons": [dict(с) for с in сезоны],
        "countries": ["Россия"], "description": f"Описание для «{title}».",
        "imdb_rating": оценка, "kinopoisk_rating": round(оценка - 0.3, 1),
        "playable": играет,
        "external_ids": {"kp": f"kp{abs(hash(slug)) % 100000}"} if играет else {},
    }

for i in range(120):
    д = f"2026-09-{(i % 26) + 1:02d}T04:00:00Z" if i < 60 else f"2026-07-{(i % 28) + 1:02d}T04:00:00Z"
    добавить(f"kino-{i:03d}", f"Фильм номер {i}", "Фильм", "movie",
             [ЖАНРЫ_КИНО[i % 5]], 2018 + (i % 9), round(4.5 + (i % 55) / 10, 1), д)
for i in range(60):
    д = f"2026-09-{(i % 26) + 1:02d}T05:00:00Z" if i < 30 else f"2026-08-{(i % 28) + 1:02d}T05:00:00Z"
    добавить(f"serial-{i:03d}", f"Сериал номер {i}", "Сериал", "tv",
             ["драма", ЖАНРЫ_КИНО[i % 5]], 2019 + (i % 8), round(5.0 + (i % 50) / 10, 1), д,
             сезоны=[{"n": 1, "eps": 12, "avail": 8 if i % 3 else 12}])
for i in range(25):
    добавить(f"anime-{i:03d}", f"Аниме номер {i}", "Сериал", "tv",
             ["аниме", "сенен"], 2020 + (i % 6), round(6.0 + (i % 40) / 10, 1),
             f"2026-09-{(i % 26) + 1:02d}T06:00:00Z",
             сезоны=[{"n": 1, "eps": 24, "avail": 24}])
for i in range(20):
    добавить(f"dorama-{i:03d}", f"Дорама номер {i}", "Сериал", "tv",
             ["дорама", "драма"], 2021 + (i % 5), round(6.5 + (i % 35) / 10, 1),
             f"2026-09-{(i % 26) + 1:02d}T07:00:00Z",
             сезоны=[{"n": 1, "eps": 16, "avail": 16}])
for i in range(15):
    добавить(f"mult-{i:03d}", f"Мультфильм номер {i}", "Мультфильм", "movie",
             ["мультфильм", "семейный"], 2019 + (i % 7), round(6.0 + (i % 30) / 10, 1),
             f"2026-09-{(i % 26) + 1:02d}T08:00:00Z")

for доп in ДОБАВКА:
    добавить(доп["slug"], доп["title"], доп["kind"], доп["type"], доп["genres"],
             доп.get("year", 2026), доп.get("rating", 8.5), доп["published_at"],
             сезоны=доп.get("seasons", ()), играет=доп.get("playable", True))

site = "lords-90"
(КУДА / f"{site}-catalog.json").write_text(json.dumps({
    "revision": ПОКОЛЕНИЕ, "built_at": "2026-09-26T03:30:00+00:00", "items": записи,
}, ensure_ascii=False), encoding="utf-8")
(КУДА / f"{site}-details.json").write_text(json.dumps({
    "catalog_revision": ПОКОЛЕНИЕ, "catalog_built_at": "2026-09-26T03:30:00+00:00",
    "source": "проверочный засев", "details_total": len(детали), "details": детали,
}, ensure_ascii=False), encoding="utf-8")
print(json.dumps({"записей": len(записи), "поколение": ПОКОЛЕНИЕ}, ensure_ascii=False))
