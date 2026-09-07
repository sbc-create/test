#!/usr/bin/env python3
"""Предпросмотр продукта на настоящих данных.

Зачем не фикстура
-----------------

Фикстура ровная: у каждой записи есть год, жанр, страна, длительность и постер.
Боевой каталог рваный — у 2 746 записей нет года, у 86 % нет описания, у 78 %
нет жанров, у половины нет ни одной оценки. Витрина, безупречная на ровных
данных, на рваных показывает пустые подписи и мёртвые отступы. Показывать
владельцу предпросмотр на фикстуре значит показывать не тот продукт.

Поэтому предпросмотр собирается из разрешённого снимка каталога, слитого с
обогащением. Снимок читается только на чтение; ни одна боевая вещь не
трогается.

Об источнике снимка
-------------------

Снимок хранится по идентификатору витрины, и у витрин этого этапа своего
снимка нет — они никогда не ходили к источнику. Берётся снимок соседней
витрины того же поставщика: содержимое каталога у него общее, а
принадлежность снимка записывается в отчёт, чтобы никто не принял
предпросмотр за приёмку этой витрины.

Чего этот предпросмотр не значит
--------------------------------

Он не production и не приёмка боевой витрины. У витрин нет ни домена, ни
окружения, ни разрешения владельца; предпросмотр показывает, как выглядит и
работает шаблон на настоящих данных, — и только это.

Запуск:
    .venv/bin/python scripts/build_product_preview.py --product zona-cinema
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

LIVE_ROOT = Path("/srv/site-factory/repo/var/lords")
CATALOG_CACHE = LIVE_ROOT / "lords" / "catalog-cache"
DETAIL_CACHE = LIVE_ROOT / "detail-cache"

#: Витрина, чей снимок берётся за источник содержимого. Поставщик и каталог у
#: неё те же; принадлежность записывается в отчёт предпросмотра.
SNAPSHOT_SITE = "lords-02"

OUT_ROOT = ROOT / "var" / "product-preview"

#: Продукт → пакет. Соответствие снято `scripts/product_map.py` из манифестов.
PRODUCTS = {
    "zona-cinema": "zona-cinema-preview",
    "animedia-portal": "animedia-preview",
}

#: Витрины на движке DLE. Они собираются штатной командой фабрики, а не
#: рендерером Lords: у них другой движок, другой источник и другие маршруты.
#: Предпросмотр здесь только раскладывает готовую сборку под общий стенд.
DLE_PRODUCTS = {"basis-video": "pilot-local"}


def load_catalog(limit: int | None) -> tuple[list[dict], dict]:
    source = CATALOG_CACHE / f"{SNAPSHOT_SITE}.json"
    if not source.is_file():
        raise SystemExit(f"BLOCKED: снимка каталога нет — {source}")
    raw = json.loads(source.read_text(encoding="utf-8"))
    items = raw["items"] if isinstance(raw, dict) else raw

    details, broken = enrich_mod.load_cached_details(DETAIL_CACHE)
    if broken:
        print(f"кэш обогащения: пропущено битых файлов {len(broken)}: "
              f"{', '.join(broken[:5])}")

    # Обогащение обязательно: списочный ответ не несёт ни описаний, ни жанров,
    # ни стран, ни длительности. Без него витрина выглядит пустее, чем есть.
    merged = [
        enrich_mod.merge_detail(item, details[item["external_id"]])
        if item.get("external_id") in details else item
        for item in items
    ]
    if limit:
        merged = merged[:limit]
    return merged, {"snapshot_site": SNAPSHOT_SITE, "records": len(merged),
                    "enriched": len(details), "source": raw.get("source")
                    if isinstance(raw, dict) else None}


def build(product: str, *, titles: int, limit: int | None) -> dict:
    package_name = PRODUCTS.get(product)
    if package_name is None:
        raise SystemExit(f"неизвестный продукт: {product}")

    started = time.perf_counter()
    items, provenance = load_catalog(limit)
    catalog = live_mod.catalog_from_live(items)
    package, _ = preview_mod._package(package_name)

    # Страницы произведений отрисовываются выборкой равным шагом, а не с
    # начала: начало каталога — самые свежие записи, они заполнены лучше
    # хвоста, и первые N завысили бы любую оценку полноты.
    slugs: frozenset[str] = frozenset()
    if titles > 0:
        ordered = sorted(t.slug for t in catalog.titles)
        step = max(1, len(ordered) // titles)
        slugs = frozenset(ordered[::step][:titles])

    site = render_mod.render_site(
        package, catalog=catalog, environ={},
        # Publisher ID — заглушка предпросмотра. Настоящее значение живёт в
        # области секретов, недоступно этой полосе и выводу не подлежит.
        publisher_id="1", only_title_slugs=slugs)

    directory = OUT_ROOT / product
    serve_mod.clear_directory(directory)
    result = serve_mod.export(site, directory)

    report = {
        "product": product,
        "package": package_name,
        "theme": (package.get("tenant") or {}).get("theme"),
        "profile": (package.get("tenant") or {}).get("seo_profile"),
        "documents": len(site.pages),
        "title_pages": len(slugs),
        "files": len(result["files"]),
        "root": str(directory),
        "seconds": round(time.perf_counter() - started, 1),
        "data_provenance": provenance,
        "not_acceptance": ("предпросмотр на настоящих данных; домена, окружения и "
                           "разрешения владельца у витрины нет, приёмкой не является"),
    }
    (directory / "preview-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def latest_build(site: str) -> Path | None:
    """Последняя сборка витрины DLE. Берётся именно последняя, а не любая."""
    root = ROOT / "var" / "build" / site
    if not root.is_dir():
        return None
    builds = [p for p in root.iterdir() if (p / "public" / "index.html").is_file()]
    if not builds:
        return None
    return max(builds, key=lambda p: p.stat().st_mtime)


def place_dle(product: str) -> dict:
    """Готовая сборка DLE — под общий стенд предпросмотра.

    Пересборка здесь не делается намеренно: витрина собирается штатной
    командой фабрики (`python3 -m factory build --site …`), и подменять её
    своей сборкой значило бы показывать владельцу не тот артефакт, который
    уйдёт в выкладку.
    """
    site = DLE_PRODUCTS[product]
    build = latest_build(site)
    if build is None:
        raise SystemExit(
            f"BLOCKED: сборки витрины {site} нет — сначала "
            f"`python3 -m factory build --site {site}`")

    import shutil

    directory = OUT_ROOT / product
    if directory.exists():
        shutil.rmtree(directory)
    shutil.copytree(build / "public", directory)

    manifest = build / "build-manifest.json"
    report = {
        "product": product,
        "package": site,
        "engine": "dle20",
        "build_id": build.name,
        "documents": sum(1 for _ in directory.rglob("*.html")),
        "files": sum(1 for p in directory.rglob("*") if p.is_file()),
        "root": str(directory),
        "build_manifest": (json.loads(manifest.read_text(encoding="utf-8"))
                           if manifest.is_file() else None),
        "data_provenance": {"source": "fixture", "note":
                            "синтетический набор витрины; боевыми данными не является"},
        "not_acceptance": ("предпросмотр на синтетических данных; приёмкой витрины "
                           "не является ни при каких условиях"),
    }
    (directory / "preview-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product", required=True,
                        choices=sorted(set(PRODUCTS) | set(DLE_PRODUCTS)))
    parser.add_argument("--titles", type=int, default=40)
    parser.add_argument("--limit", type=int, default=None,
                        help="ограничить каталог (для быстрых прогонов)")
    args = parser.parse_args()

    if args.product in DLE_PRODUCTS:
        report = place_dle(args.product)
        print(f"{report['product']}: пакет {report['package']}, движок {report['engine']}, "
              f"сборка {report['build_id']}")
        print(f"  документов {report['documents']}, файлов {report['files']}")
        print(f"  {report['root']}")
        return 0

    report = build(args.product, titles=args.titles, limit=args.limit)
    print(f"{report['product']}: пакет {report['package']}, тема {report['theme']}")
    print(f"  записей {report['data_provenance']['records']}, "
          f"обогащено {report['data_provenance']['enriched']}, "
          f"снимок витрины {report['data_provenance']['snapshot_site']}")
    print(f"  документов {report['documents']}, страниц произведений "
          f"{report['title_pages']}, собрано за {report['seconds']} с")
    print(f"  {report['root']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
