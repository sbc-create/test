#!/usr/bin/env python3
"""Стенд поиска на снимке боевого каталога.

Зачем отдельный стенд. Указатель поиска отдаётся только там, где встроенного
набора нет, — на каталоге больше `DATASET_MAX_TITLES` записей. Фикстурный стенд
несёт шестьдесят две записи, и эта ветка на нём не отрисовывается вовсе: любая
проверка поиска на фикстуре доказывала бы работу другого кода.

Поэтому стенд собирается из настоящего снимка каталога. Снимок читается только
на чтение; ни одна боевая вещь при этом не трогается.

Страницы произведений не отрисовываются намеренно: их пятьдесят три тысячи, они
занимают часы и к поиску отношения не имеют. Остаются списки, разделы, страница
поиска и указатель — то, что проверяется.

Запуск:
    .venv/bin/python scripts/build_live_search_stand.py [--site lords-02]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from factory.lords import detail_enrichment as enrich_mod  # noqa: E402
from factory.lords import live_catalog as live_mod  # noqa: E402
from factory.lords import preview as preview_mod  # noqa: E402
from factory.lords import render as render_mod  # noqa: E402
from factory.lords import serve as serve_mod  # noqa: E402

CATALOG_CACHE = Path("/srv/site-factory/repo/var/lords/lords/catalog-cache")
DETAIL_CACHE = Path("/srv/site-factory/repo/var/lords/detail-cache")
OUT = ROOT / "var" / "live-search-stand"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", default="lords-02")
    parser.add_argument("--output", default=str(OUT))
    parser.add_argument("--titles", type=int, default=0,
                        help="сколько страниц произведений отрисовать (0 — ни одной)")
    args = parser.parse_args()

    source = CATALOG_CACHE / f"{args.site}.json"
    if not source.is_file():
        print(f"BLOCKED: снимка каталога нет — {source}", file=sys.stderr)
        return 1

    started = time.perf_counter()
    raw = json.loads(source.read_text(encoding="utf-8"))
    items = raw["items"] if isinstance(raw, dict) else raw

    # Обогащение обязательно, а не по желанию. Списочный ответ не несёт ни
    # описаний, ни жанров, ни стран, ни длительности — они приходят только из
    # detail. Стенд без обогащения показывает витрину, которой не существует:
    # указатель стран на нём пуст, хотя у 8 348 записей страна есть.
    details: dict[str, dict] = {}
    if DETAIL_CACHE.is_dir():
        for path in DETAIL_CACHE.glob("*.json"):
            try:
                entry = json.loads(path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001 — битый файл кэша не поле
                continue
            detail = entry.get("detail")
            if detail:
                details[detail.get("id") or path.stem] = detail
    merged = [
        enrich_mod.merge_detail(item, details[item["external_id"]])
        if item.get("external_id") in details else item
        for item in items
    ]
    catalog = live_mod.catalog_from_live(merged)
    package, _ = preview_mod._package(args.site)
    # Страницы произведений отрисовываются выборочно: их пятьдесят три тысячи,
    # и полная отрисовка занимает часы. Выборка идёт равным шагом по каталогу,
    # а не с начала: начало — самые свежие записи, они заполнены лучше хвоста,
    # и первые N завысили бы любую проверку полноты.
    slugs: frozenset[str] = frozenset()
    if args.titles > 0:
        ordered = sorted(t.slug for t in catalog.titles)
        step = max(1, len(ordered) // args.titles)
        slugs = frozenset(ordered[::step][:args.titles])
    # Publisher ID для стенда — заглушка предпросмотра, а не настоящее
    # значение: настоящее живёт в области секретов и этой полосе недоступно,
    # выводить его куда бы то ни было запрещено прямо.
    #
    # Без него плеер не собирается вовсе: все сорок страниц произведений
    # показывали «видео недоступно», и проверить состояния плеера было не на
    # чем. Это была слепота стенда, а не дефект витрины, но отличить одно от
    # другого удалось только пройдя по страницам глазами.
    site = render_mod.render_site(package, catalog=catalog, environ={},
                                  publisher_id="1", only_title_slugs=slugs)
    directory = Path(args.output)
    serve_mod.clear_directory(directory)
    result = serve_mod.export(site, directory)

    index = site.pages.get(render_mod.SEARCH_INDEX_PATH)
    print(f"{args.site}: записей {len(items)}, обогащено {len(details)}, "
          f"страниц произведений {len(slugs)}, "
          f"документов {len(site.pages)}, "
          f"собрано за {time.perf_counter() - started:.0f} с")
    if index is None:
        print("указатель поиска не отдан: проверьте seo.search_index в пакете")
    else:
        print(f"указатель поиска: {len(index.payload) / 1024 / 1024:.1f} МБ")
    print(f"выгружено файлов: {len(result['files'])} в {directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
