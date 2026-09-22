#!/usr/bin/env python3
"""Выборка боевого снимка Zona для локального стенда.

Зачем. Полный снимок zona-01 — 53 573 записи и 78 МБ подробностей: витрина
поднимается на нём минутами, и прогнать шесть ширин на десятке страниц
дважды за ночь на нём нельзя. Выдуманные данные при этом проверяли бы не ту
витрину: у настоящих записей длинные названия, отсутствующие постеры, пустые
описания и оценки трёх источников.

Поэтому здесь берётся подмножество НАСТОЯЩЕГО снимка, а не синтетика. Отбор
детерминированный и объявленный:

* все слаги недельного снимка «Высоких оценок недели» — иначе главная
  останется без лент и без слайдера;
* самые свежие по `published_at` — ими живут «Новое в каталоге» и `/new/`;
* записи без постера, с пустой датой и без оценок — ради честных краёв;
* по несколько записей каждого вида, чтобы разделы не пустовали.

Ничего не пишется в production: выход — в указанный каталог.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ИСТОЧНИК = Path("/srv/lords/.frontend")


def загрузить(путь: Path):
    return json.loads(путь.read_text(encoding="utf-8"))


def отобрать(каталог: dict, подробности: dict, weekly: dict | None,
             сколько: int) -> list:
    items = каталог["items"]
    по_слагу = {з["slug"]: з for з in items}
    отобрано: dict = {}

    def взять(з) -> None:
        if з and з["slug"] not in отобрано:
            отобрано[з["slug"]] = з

    # 1. Недельные полки — без них у главной нет ни лент, ни слайдера.
    for полка in ((weekly or {}).get("shelves") or {}).values():
        for slug in полка:
            взять(по_слагу.get(slug))

    # 2. Самые свежие: ими живут «Новое в каталоге» и /new/.
    свежие = sorted(items, key=lambda з: з.get("published_at") or "", reverse=True)
    for з in свежие[: max(0, сколько // 2)]:
        взять(з)

    # 3. Честные края: без постера, без даты, без оценок.
    без_постера = [з for з in items if not (з.get("poster") or "").strip()][:20]
    без_даты = [з for з in items if not (з.get("published_at") or "").strip()][:20]
    без_оценки = [з for з in items
                  if not (подробности.get(з["slug"]) or {}).get("ratings_by_source")][:20]
    длинные = sorted(items, key=lambda з: -len(з.get("title") or ""))[:20]
    for набор in (без_постера, без_даты, без_оценки, длинные):
        for з in набор:
            взять(з)

    # 4. Виды: ни один раздел не должен оказаться пустым.
    for вид in ("Фильм", "Сериал", "Мультфильм"):
        свои = [з for з in свежие if з.get("kind") == вид][:120]
        for з in свои:
            взять(з)

    # 5. Добор до размера — по свежести, чтобы порядок был воспроизводим.
    for з in свежие:
        if len(отобрано) >= сколько:
            break
        взять(з)
    return list(отобрано.values())


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--site", default="zona-01")
    р.add_argument("--out", required=True, help="каталог для выборки")
    р.add_argument("--count", type=int, default=1500)
    а = р.parse_args()

    каталог = загрузить(ИСТОЧНИК / f"{а.site}-catalog.json")
    подробности = загрузить(ИСТОЧНИК / f"{а.site}-details.json")["details"]
    недельный_путь = ИСТОЧНИК / f"{а.site}-popular-weekly.json"
    weekly = загрузить(недельный_путь) if недельный_путь.is_file() else None

    записи = отобрать(каталог, подробности, weekly, а.count)
    слаги = {з["slug"] for з in записи}

    выход = Path(а.out)
    выход.mkdir(parents=True, exist_ok=True)
    (выход / f"{а.site}-catalog.json").write_text(json.dumps({
        **{k: v for k, v in каталог.items() if k != "items"},
        "count": len(записи), "items": записи,
    }, ensure_ascii=False), encoding="utf-8")
    (выход / f"{а.site}-details.json").write_text(json.dumps({
        "schema": "nova.details.sidecar/2.0.0", "site": а.site,
        "source": "sampled-from-production-snapshot",
        "details_total": len(слаги), "items_total": len(записи),
        "details": {s: подробности[s] for s in слаги if s in подробности},
    }, ensure_ascii=False), encoding="utf-8")
    if weekly:
        # Полки урезаются до отобранных слагов: ссылка на запись, которой нет в
        # выборке, молча пропадает из полки и подменяет причину пустоты.
        полки = {k: [s for s in v if s in слаги]
                 for k, v in (weekly.get("shelves") or {}).items()}
        (выход / f"{а.site}-popular-weekly.json").write_text(
            json.dumps({**weekly, "shelves": полки}, ensure_ascii=False),
            encoding="utf-8")
    # Конфигурация плеера копируется как есть: без неё стенд считает видео
    # недоступным, и на снимках пропадает кнопка «Смотреть» — то есть витрина
    # выглядит беднее, чем она есть.
    плеер = ИСТОЧНИК / f"player-{а.site}.json"
    if плеер.is_file():
        (выход / плеер.name).write_text(плеер.read_text(encoding="utf-8"),
                                        encoding="utf-8")
    print(json.dumps({
        "site": а.site, "items": len(записи), "player_config": плеер.is_file(),
        "details": sum(1 for s in слаги if s in подробности),
        "shelves": {k: len(v) for k, v in
                    ((weekly or {}).get("shelves") or {}).items()},
        "out": str(выход),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
