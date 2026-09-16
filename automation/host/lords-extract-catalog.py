#!/usr/bin/env python3
"""Собирает каталог витрины из её же отрисованных страниц.

Зачем
-----

Новый интерфейс нужен на публичном адресе быстро, а полный рендер каталога
занимает около трёх часов. Данные при этом уже есть: они лежат в отрисованных
страницах текущего релиза. Здесь они извлекаются в один JSON, и новый frontend
строится поверх существующего снимка содержимого, не дожидаясь обновления.

Что берётся
-----------

Ровно то, что действительно есть в разметке карточки: slug, название, год,
вид (фильм/сериал) и постер. Жанры, страны, возраст, КП и IMDb в текущем
снимке ПУСТЫ — `ld+json` отдаёт `genre: []` и пустую страну. Поэтому они не
извлекаются и не выдумываются: карточка покажет то, что измерено, а
отсутствующее останется отсутствующим.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Блок карточки берётся целиком, а поля — внутри него.
#
# Одним выражением с необязательной группой постера это не делается: `.*?`
# перескакивает через <img> и группа остаётся пустой. Первый прогон так и
# собрал 52612 тайтлов, из них 52612 «без постера» — то есть ни одного.
КАРТОЧКА = re.compile(r'<article[^>]*class="card"[^>]*data-slug="[^"]+".*?</article>', re.S)
СЛАГ = re.compile(r'data-slug="([^"]+)"')
ПОСТЕР = re.compile(r'<img src="([^"]+)"')
НАЗВАНИЕ = re.compile(r'<a class="card__title"[^>]*>([^<]+)</a>')
МЕТА = re.compile(r'<span class="card__meta">([^<]*)</span>')


def извлечь(корень: Path) -> dict[str, dict]:
    каталог: dict[str, dict] = {}
    страниц = 0
    for стр in корень.rglob("index.html"):
        try:
            текст = стр.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        страниц += 1
        for блок in КАРТОЧКА.findall(текст):
            сл = СЛАГ.search(блок)
            наз = НАЗВАНИЕ.search(блок)
            if not сл or not наз or сл.group(1) in каталог:
                continue
            пост = ПОСТЕР.search(блок)
            мета = МЕТА.search(блок)
            вид, _, год = (мета.group(1).strip() if мета else "").partition("·")
            каталог[сл.group(1)] = {
                "slug": сл.group(1),
                "title": наз.group(1).strip(),
                "poster": пост.group(1) if пост else None,
                "kind": вид.strip() or None,
                "year": int(год.strip()) if год.strip().isdigit() else None,
                "url": f"/title/{сл.group(1)}/",
            }
    print(f"[каталог] страниц просмотрено: {страниц}, тайтлов собрано: {len(каталог)}",
          file=sys.stderr)
    return каталог


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--site-root", required=True, help="каталог site текущего релиза")
    р.add_argument("--out", required=True)
    args = р.parse_args()

    каталог = извлечь(Path(args.site_root))
    if not каталог:
        print("каталог пуст: разметка карточки не совпала", file=sys.stderr)
        return 1
    без_постера = sum(1 for з in каталог.values() if not з["poster"])
    сведение = {
        "version": 1,
        "count": len(каталог),
        "without_poster": без_постера,
        "fields_present": ["slug", "title", "poster", "kind", "year", "url"],
        "fields_absent": ["genres", "countries", "age_rating", "kp", "imdb"],
        "absent_reason": ("в текущем снимке содержимого эти поля пусты "
                          "(ld+json отдаёт genre: [] и пустую страну); "
                          "выдумывать их запрещено"),
        "items": sorted(каталог.values(), key=lambda з: (-(з["year"] or 0), з["title"])),
    }
    Path(args.out).write_text(json.dumps(сведение, ensure_ascii=False), encoding="utf-8")
    print(f"[каталог] записано: {args.out} ({len(каталог)} тайтлов, "
          f"без постера {без_постера})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
