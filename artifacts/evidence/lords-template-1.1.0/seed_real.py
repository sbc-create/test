#!/usr/bin/env python3
"""Засев проверочного экземпляра НАСТОЯЩИМИ идентификаторами источника.

Синтетический каталог годится для отбора, раскладки и подборок, но проверить
воспроизведение на нём нельзя: у выдуманной записи у провайдера ничего нет.
Здесь берётся небольшая выборка из живого снимка — только публичные
метаданные каталога (название, год, вид, идентификаторы источника, сезоны).
Секретов в снимке нет; настройка плеера сюда не копируется и не печатается.

Живые файлы открываются ТОЛЬКО на чтение.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ЖИВОЙ_КАТАЛОГ = Path("/srv/lordfilm47-space/data/lords-01-catalog.json")
ЖИВЫЕ_ПОДРОБНОСТИ = Path("/srv/lordfilm47-space/data/lords-01-details.json")

КУДА = Path(sys.argv[1])
SITE = sys.argv[2] if len(sys.argv) > 2 else "lords-90"
СКОЛЬКО = int(sys.argv[3]) if len(sys.argv) > 3 else 120
ПОКОЛЕНИЕ = sys.argv[4] if len(sys.argv) > 4 else "real-1"

каталог = json.loads(ЖИВОЙ_КАТАЛОГ.read_text(encoding="utf-8"))
подробности = json.loads(ЖИВЫЕ_ПОДРОБНОСТИ.read_text(encoding="utf-8"))["details"]

# Берём записи, у которых источник действительно есть: иначе плеер честно
# скажет «источник не передан», и проверять будет нечего.
сериалы, фильмы = [], []
for з in каталог["items"]:
    д = подробности.get(з["slug"])
    if not д:
        continue
    есть_источник = bool(д.get("sources")) or bool(д.get("external_ids"))
    if not есть_источник or not д.get("playable"):
        continue
    доступно = sum(int(с.get("avail") or 0) for с in (д.get("seasons") or []))
    if доступно >= 2 and len(сериалы) < 12:
        сериалы.append(з)
    elif not д.get("seasons") and len(фильмы) < СКОЛЬКО - 12:
        фильмы.append(з)
    if len(сериалы) >= 12 and len(фильмы) >= СКОЛЬКО - 12:
        break

выбор = сериалы + фильмы
записи = [dict(з) for з in выбор]
детали = {з["slug"]: подробности[з["slug"]] for з in выбор}

КУДА.mkdir(parents=True, exist_ok=True)
(КУДА / f"{SITE}-catalog.json").write_text(json.dumps({
    "revision": ПОКОЛЕНИЕ, "built_at": каталог.get("built_at", ""), "items": записи,
}, ensure_ascii=False), encoding="utf-8")
(КУДА / f"{SITE}-details.json").write_text(json.dumps({
    "catalog_revision": ПОКОЛЕНИЕ, "source": "выборка живого снимка (только чтение)",
    "details_total": len(детали), "details": детали,
}, ensure_ascii=False), encoding="utf-8")
print(json.dumps({"записей": len(записи), "сериалов": len(сериалы),
                  "поколение": ПОКОЛЕНИЕ,
                  "пример_сериала": сериалы[0]["slug"] if сериалы else None},
                 ensure_ascii=False))
