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


ПРЕЖНИЕ_МАРШРУТЫ = ROOT / "data" / "lords" / "previous-routes.json"


def _потерявшие_адрес(catalog) -> list[tuple[str, str, str]]:
    """Сущности, у которых публичный адрес был и сменился.

    Прежний адрес для большинства сущностей выводится из названия; в файле
    лежит только невыводимое — суффиксные адреса и владельцы спорных адресов.
    Отсутствие файла означает, что закреплять ещё нечего, и страж молчит.
    """
    try:
        прежнее = json.loads(ПРЕЖНИЕ_МАРШРУТЫ.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    суффиксные = прежнее.get("suffixed", {})
    спорные = прежнее.get("contested_owner", {})

    сейчас = {t.external_id: t.slug for t in catalog.titles}
    прежний = {}
    for t in catalog.titles:
        естественный = live_mod.slugify(t.name) or t.external_id.lower()
        прежний[t.external_id] = суффиксные.get(t.external_id, естественный)

    владелец = {}
    for ид, с in прежний.items():
        владелец[с] = ид
    владелец.update(спорные)

    потеряли = []
    for ид, было in прежний.items():
        стало = сейчас.get(ид)
        if стало is not None and стало != было and владелец.get(было) == ид:
            потеряли.append((ид, было, стало))
    return потеряли


def _переезды(catalog, карта) -> tuple[dict, list]:
    """Старый адрес → новый, когда содержимое переехало.

    Адрес меняет владельца: прежде по нему отдавалась одна сущность, теперь
    он принадлежит другой. Если прежняя на этой витрине по-прежнему
    публикуется, читателя надо привести к ней — один переход, без цепочек.

    Считается ПО ВИТРИНЕ, а не по каталогу. Витрина публикует не все виды, и
    «кто отдавался по адресу» — это последняя ОТРИСОВАННАЯ запись с этим
    адресом, а не глобальный владелец: запись невыпускаемого вида страницы не
    получала и перекрыть ничего не могла.

    Второе значение — надгробия: адреса, чья прежняя сущность на этой витрине
    больше не публикуется. Их не прячем: адрес, ставший 404, должен быть
    назван с причиной.
    """
    try:
        прежнее = json.loads(ПРЕЖНИЕ_МАРШРУТЫ.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}, []
    суффиксные = прежнее.get("suffixed", {})

    собрано = set(карта.slugs if hasattr(карта, "slugs") else карта.слаги)

    отдавалось = {}
    новый = {}
    for t_ in catalog.titles:                       # порядок источника сохранён
        новый[t_.external_id] = t_.slug
        if t_.slug not in собрано:
            # Запись невыпускаемого вида страницы не получала и перекрыть
            # ничего не могла. Считать её владельцем адреса значило бы
            # объявить надгробием адрес, который на этой витрине жил.
            continue
        естественный = live_mod.slugify(t_.name) or t_.external_id.lower()
        старый = суффиксные.get(t_.external_id, естественный)
        отдавалось[старый] = t_                     # последний перекрывал прежних
    переезды, надгробия = {}, []
    for старый, владелец in sorted(отдавалось.items()):
        if старый in собрано:
            continue
        цель = новый.get(владелец.external_id)
        if цель and цель in собрано:
            переезды[f"/title/{старый}/"] = f"/title/{цель}/"
        else:
            надгробия.append({"path": f"/title/{старый}/",
                              "reason": "OWNER_NOT_PUBLISHED_ON_STOREFRONT",
                              "entity": владелец.external_id})
    return переезды, надгробия


def load_catalog(limit: int | None,
                 shuffle_seed: int | None = None) -> tuple[list[dict], dict]:
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
    merged, обогащено = enrich_mod.merge_cached(items, details)
    if limit:
        merged = merged[:limit]
    if shuffle_seed is not None:
        # Перестановка входа — проверка, а не режим сборки. Адрес не должен
        # зависеть от порядка строк в выгрузке, и единственный способ это
        # показать — собрать из тех же записей в другом порядке и сверить
        # отпечатки. Порядок задаётся зерном, чтобы проверка повторялась.
        import random as _random
        merged = list(merged)
        _random.Random(shuffle_seed).shuffle(merged)
    return merged, {"snapshot_site": SNAPSHOT_SITE, "records": len(merged),
                    "shuffle_seed": shuffle_seed,
                    # Число обогащённых записей, а не размер кэша: кэш может
                    # быть велик и не совпасть со срезом ни одной записью.
                    "enriched": обогащено, "source": raw.get("source")
                    if isinstance(raw, dict) else None}


#: Адрес карточки в разметке. Кавычки, плюс и скобки исключены: в виджете
#: поиска есть JS-шаблон `"/title/" + encodeURIComponent(...)`, и он ссылкой
#: страницы не является.
_ССЫЛКА = __import__("re").compile(r'href="(/title/[a-z0-9\-/]*)"')


def _карточные_цели(site) -> set[str]:
    """Все адреса карточек, которые отдаёт собранный сайт."""
    from factory.lords import urlmap as um
    цели = set()
    for страница in site.pages.values():
        тело = страница.body
        if isinstance(тело, bytes):
            тело = тело.decode("utf-8", "replace")
        for сырой in _ССЫЛКА.findall(тело):
            цели.add(um.нормализовать(сырой))
    return цели


def build(product: str, *, titles: int, limit: int | None,
          out_root: Path | None = None, shuffle_seed: int | None = None) -> dict:
    package_name = PRODUCTS.get(product)
    if package_name is None:
        raise SystemExit(f"неизвестный продукт: {product}")

    started = time.perf_counter()
    items, provenance = load_catalog(limit, shuffle_seed)
    catalog = live_mod.catalog_from_live(items)
    package, _ = preview_mod._package(package_name)

    # Страницы произведений отрисовываются выборкой равным шагом, а не с
    # начала: начало каталога — самые свежие записи, они заполнены лучше
    # хвоста, и первые N завысили бы любую оценку полноты.
    # `titles <= 0` означает «все», а не «ни одной».
    #
    # Прежде ноль давал пустое множество, и рендер отрисовывал нуль страниц
    # произведений, продолжая раскладывать карточки по всему каталогу. Для
    # раскладки витрины нужен именно полный набор: каталог опубликовал четыре
    # тысячи сущностей, и витрина обязана отдавать их все.
    slugs: frozenset[str] | None = None
    if titles > 0:
        ordered = sorted(t.slug for t in catalog.titles)
        step = max(1, len(ordered) // titles)
        slugs = frozenset(ordered[::step][:titles])

    site = render_mod.render_site(
        package, catalog=catalog, environ={},
        # Publisher ID — заглушка предпросмотра. Настоящее значение живёт в
        # области секретов, недоступно этой полосе и выводу не подлежит.
        publisher_id="1", only_title_slugs=slugs,
        # Списки следуют за отрисованными страницами. Прежде здесь карточки
        # брались из полного каталога, а страницы — из выборки: срез уходил в
        # раскладку витрины, и около четырёх тысяч карточек вели на девятнадцать
        # существующих адресов.
        restrict_cards_to_rendered=slugs is not None)

    # Карта маршрутов и паритет считаются ДО выгрузки: срез, который не
    # сходится сам с собой, не должен попасть на диск и быть принятым за
    # годный к раскладке.
    from factory.lords import urlmap as um
    отрисованные = {а[len("/title/"):].strip("/") for а in site.pages
                    if а.startswith("/title/") and а.count("/") == 3}
    карта = um.построить(отрисованные)
    цели = _карточные_цели(site)
    паритет = um.паритет(цели, карта)
    if not паритет.ок:
        raise SystemExit(
            f"срез не сходится сам с собой: {len(паритет.orphan_targets)} "
            f"карточек ведут на несуществующие адреса; пример: "
            f"{list(паритет.orphan_targets)[:3]}")
    # Страж устойчивости публичных адресов.
    #
    # Паритет карточек и страниц ничего не говорит о том, ЧЬЯ страница лежит
    # по адресу. Сущность, которая уже год публикуется по своему URL, не
    # должна его лишиться из-за того, что в каталог добавили запись с похожим
    # названием. Проверка идёт по закреплённым прежним адресам и падает до
    # выгрузки: подменённый адрес дешевле не собрать, чем потом искать.
    потеряли = _потерявшие_адрес(catalog)
    if потеряли:
        примеры = "; ".join(f"{и}: {было} -> {стало}"
                            for и, было, стало in потеряли[:3])
        raise SystemExit(
            f"публичный адрес сменился у {len(потеряли)} сущностей, которые его "
            f"занимали: {примеры}")

    переезды, надгробия = _переезды(catalog, карта)
    # Цепочек и петель не бывает по построению: цель переезда обязана быть
    # собранной страницей, а собранная страница переездом не является.
    петли = [а for а, ц in переезды.items() if ц in переезды or ц == а]
    if петли:
        raise SystemExit(f"переезды образуют цепочку: {петли[:3]}")

    # Ни один адрес витрины не исчезает молча.
    #
    # Страж выше проверяет назначение: не сменился ли адрес у сущности,
    # которая его занимала. Этого мало — витрина публикует не все виды, и
    # адрес может пропасть именно на ней, тогда как назначение в порядке.
    #
    # Надгробие — это адрес, который был живым и станет 404. Причина в записи
    # объясняет, ПОЧЕМУ так вышло, но не делает потерю приемлемой: принять её
    # должен человек, а не сборка. Поэтому любое надгробие останавливает
    # сборку, пока не перечислено в `data/lords/route-tombstones.json`.
    принятые = set()
    файл_надгробий = ROOT / "data" / "lords" / "route-tombstones.json"
    if файл_надгробий.is_file():
        try:
            принятые = {з["path"] for з in
                        json.loads(файл_надгробий.read_text(encoding="utf-8"))
                        .get("accepted", [])}
        except (ValueError, KeyError, TypeError):
            принятые = set()
    непринятые = [н for н in надгробия if н["path"] not in принятые]
    if непринятые:
        raise SystemExit(
            f"адреса станут 404 и это нигде не принято: {len(непринятые)}; "
            f"пример {непринятые[0]['path']} ({непринятые[0]['reason']}); "
            f"перечислите их в {файл_надгробий} вместе с причиной")

    карта_маршрутов = {
        "summary": {"version": карта.version, "routes": len(карта.routes),
                    "redirects": len(переезды), "tombstones": len(надгробия),
                    "route_map_sha256": карта.отпечаток,
                    "card_targets": len(цели),
                    "orphan_targets": len(паритет.orphan_targets),
                    "unreferenced_routes": len(паритет.unreferenced_routes)},
        "map": карта.в_словарь()}

    # Каталог назначения задаётся явно. Срез, из которого уже провизионированы
    # витрины, перезаписывать нельзя: кандидат обязан быть отдельным и
    # неизменяемым, иначе «собрать кандидата» означало бы стереть основание
    # действующего релиза.
    directory = (Path(out_root) if out_root else OUT_ROOT) / product
    if directory.exists() and (directory / "release-provisioned.marker").is_file():
        raise SystemExit(f"{directory}: срез уже провизионирован, перезапись "
                         f"запрещена")
    serve_mod.clear_directory(directory)
    result = serve_mod.export(site, directory)
    (directory / "redirects.json").write_text(
        json.dumps({"version": "lords-redirects/1.0.0", "moved": переезды,
                    "tombstones": надгробия}, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8")
    (directory / "route-map.json").write_text(
        json.dumps(карта_маршрутов["map"], ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8")

    report = {
        "product": product,
        "package": package_name,
        "theme": (package.get("tenant") or {}).get("theme"),
        "profile": (package.get("tenant") or {}).get("seo_profile"),
        "documents": len(site.pages),
        # Фактически отрисованные страницы, а не размер среза и не размер
        # каталога. Каталог из 4000 записей даёт 3868 страниц: часть записей
        # витрина не публикует. Отчёт, называющий 4000, завышает сам себя —
        # и именно такое число потом цитируют как проверенное.
        "title_pages": len(карта.routes),
        "route_map": карта_маршрутов["summary"],
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
    parser.add_argument("--titles", type=int, default=40,
                        help="сколько страниц произведений отрисовать; "
                             "0 и меньше означает «все»")
    parser.add_argument("--out", default=None,
                        help="корень выгрузки; по умолчанию var/product-preview")
    parser.add_argument("--limit", type=int, default=None,
                        help="ограничить каталог (для быстрых прогонов)")
    parser.add_argument("--shuffle-seed", type=int, default=None,
                        dest="shuffle_seed",
                        help="переставить входные записи заданным зерном; "
                             "проверка независимости адресов от порядка входа")
    args = parser.parse_args()

    if args.product in DLE_PRODUCTS:
        report = place_dle(args.product)
        print(f"{report['product']}: пакет {report['package']}, движок {report['engine']}, "
              f"сборка {report['build_id']}")
        print(f"  документов {report['documents']}, файлов {report['files']}")
        print(f"  {report['root']}")
        return 0

    report = build(args.product, titles=args.titles, limit=args.limit,
                   out_root=args.out, shuffle_seed=args.shuffle_seed)
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
