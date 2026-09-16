"""Карта страниц витрины: что существует, кому принадлежит и чем наполнено.

Карта **выводится из собранного сайта**, а не пишется рядом с ним. Написанная
руками карта расходится с кодом через одну правку и после этого вредна: она
выглядит документацией, а описывает прошлое. Здесь источник — те же документы,
которые отдаёт рендерер, поэтому расхождение невозможно по устройству.

Карта отвечает на четыре вопроса, которые владелец задаёт о разделе:

* существует ли он у этой витрины и по какому адресу;
* индексируется ли он ей или держится навигацией с ``noindex``;
* из чего он состоит — блоки, карточки, наличие плеера;
* сколько он весит.

Разделы, выключенные профилем, в карту не попадают вовсе: выключенный тип не
создаёт ни маршрута, ни пункта меню, и присутствие такой строки в карте
означало бы обещание адреса, которого нет.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Surface:
    """Одна поверхность витрины в том виде, в каком её отдаёт рендерер."""

    path: str
    indexable: bool
    title: str
    h1: str
    blocks: tuple[str, ...]
    cards: int
    has_player: bool
    weight_kb: float

    def as_dict(self) -> dict:
        return {
            "path": self.path,
            "indexable": self.indexable,
            "title": self.title,
            "h1": self.h1,
            "blocks": list(self.blocks),
            "cards": self.cards,
            "has_player": self.has_player,
            "weight_kb": self.weight_kb,
        }


@dataclass
class PageMap:
    """Карта одной витрины."""

    site: str
    profile: str
    surfaces: list[Surface] = field(default_factory=list)

    @property
    def indexable(self) -> list[Surface]:
        return [s for s in self.surfaces if s.indexable]

    def as_dict(self) -> dict:
        return {
            "site": self.site,
            "profile": self.profile,
            "surfaces_total": len(self.surfaces),
            "surfaces_indexable": len(self.indexable),
            "surfaces": [s.as_dict() for s in self.surfaces],
        }


#: Страницы произведений и постранично разбитые списки в карту не разворачиваются:
#: их сотни, они однотипны, и карта превратилась бы в выгрузку каталога. Вместо
#: каждой из них остаётся один представитель — образец вида.
#:
#: Свёртка идёт в два шага, и порядок важен: `/collections/northern-set/page/2/`
#: несёт и слаг, и номер страницы. Сначала снимается номер, потом слаг — иначе
#: карта расписала бы по строке на каждую подборку.
_SLUG_SECTIONS = ("title", "genres", "years", "countries", "collections")


def _family(path: str) -> str:
    """Имя семейства однотипных адресов, если адрес в него входит."""
    base, page_suffix = path, ""
    found_page = re.match(r"^(?P<base>.*/)page/\d+/$", path)
    if found_page:
        base = found_page.group("base")
        page_suffix = "page/{n}/"
    parts = base.strip("/").split("/")
    if len(parts) >= 2 and parts[0] in _SLUG_SECTIONS:
        base = f"/{parts[0]}/{{slug}}/"
    return base + page_suffix


def _text(html: str, tag: str) -> str:
    found = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", html, re.S)
    return re.sub(r"<[^>]+>", "", found.group(1)).strip() if found else ""


def build(site) -> PageMap:
    """Собрать карту по результату ``render_site``."""
    page_map = PageMap(site=site.site_id, profile=site.profile)
    seen: set[str] = set()
    for path, page in sorted(site.pages.items()):
        if page.raw is not None or not page.content_type.startswith("text/html"):
            continue
        family = _family(path)
        if family in seen:
            continue
        seen.add(family)
        html = page.body
        page_map.surfaces.append(Surface(
            path=family,
            indexable=page.indexable,
            title=_text(html, "title"),
            h1=_text(html, "h1"),
            blocks=tuple(dict.fromkeys(re.findall(r'data-block="([^"]+)"', html))),
            cards=len(re.findall(r'<article class="card"', html)),
            has_player=bool(re.search(r'class="player__frame"', html)),
            weight_kb=round(len(html.encode("utf-8")) / 1024, 1),
        ))
    return page_map


def render_markdown(maps: list[PageMap], catalog: str = "") -> str:
    """Карта в виде, пригодном для чтения владельцем."""
    lines = ["# Карта страниц направления Lords", ""]
    lines.append(
        "Таблицы построены из собранных документов "
        "(`python3 -m factory.templates.pagemap --write`). "
        "Однотипные адреса свёрнуты в один образец: `/title/{slug}/` вместо "
        "пятидесяти страниц произведений.")
    if catalog:
        lines += ["", f"Каталог, на котором построена карта: **{catalog}**. "
                      "Набор поверхностей от него зависит: раздел короче одной "
                      "страницы не даёт адреса пагинации."]
    lines.append("")
    for page_map in maps:
        lines += [
            f"## {page_map.site} — профиль `{page_map.profile}`", "",
            f"Поверхностей: {len(page_map.surfaces)}, "
            f"из них индексируется: {len(page_map.indexable)}.", "",
            "| Адрес | Индекс | H1 | Блоки | Карточек | Плеер | КБ |",
            "|---|---|---|---|---|---|---|",
        ]
        for s in page_map.surfaces:
            blocks = ", ".join(s.blocks) if s.blocks else "—"
            lines.append(
                f"| `{s.path}` | {'да' if s.indexable else 'нет'} | {s.h1 or '—'} | "
                f"{blocks} | {s.cards or '—'} | {'да' if s.has_player else '—'} | "
                f"{s.weight_kb} |")
        lines.append("")
    return "\n".join(lines)


def render_json(maps: list[PageMap]) -> str:
    return json.dumps([m.as_dict() for m in maps], ensure_ascii=False, indent=2) + "\n"


#: Витрины направления, по которым строится карта. Тот же перечень, что в
#: собранном документе: карта, покрывающая не то, что обещает её заголовок,
#: вводит в заблуждение точнее, чем её отсутствие.
SITES = ("lords-01", "lords-02", "lords-03", "lords-04")

#: Снимок боевого каталога там, где его держат сценарии этой полосы. Значение
#: живёт в точке входа, а не в библиотеке: библиотека получает путь параметром.
DEFAULT_SNAPSHOT = "/srv/site-factory/repo/var/lords/lords/catalog-cache/lords-02.json"
DEFAULT_DETAIL_CACHE = "/srv/site-factory/repo/var/lords/detail-cache"

MARKDOWN_OUT = "docs/templates/PAGE-MAP-lords.md"
JSON_OUT = "artifacts/evidence/templates/page-map-lords.json"


def _catalog(snapshot, limit: int, detail_cache=None):
    """Каталог для построения карты и его описание одной строкой.

    Набор поверхностей зависит от объёма каталога, и это не мелочь. В фикстуре
    62 записи; у мультфильмов их восемь, то есть меньше страницы, и адрес
    `/animation/page/{n}/` не появляется вовсе. Первая редакция этого модуля
    строила карту по фикстуре и утверждала в докстроке, что на живом каталоге
    перечень адресов вышел бы тем же. Это неверно: собранный документ содержал
    пять адресов пагинации, которых фикстура не даёт.

    Карта, не называющая свой каталог, вводит в заблуждение точнее, чем её
    отсутствие: пять недостающих разделов выглядят как удалённые.
    """
    import json
    from pathlib import Path

    from factory.lords import fixtures as fx

    if snapshot is None:
        catalog = fx.build_catalog()
        return catalog, f"фикстура, {len(catalog.titles)} записей"

    from factory.lords import live_catalog

    # Путь приходит параметром намеренно: этот модуль входит в состав
    # артефакта, и знать в нём чужой рабочий каталог — значит связать выпуск
    # шаблонов с раскладкой машины, на которой он однажды собирался.
    snapshot = Path(snapshot)
    if not snapshot.is_file():
        catalog = fx.build_catalog()
        return catalog, (f"фикстура, {len(catalog.titles)} записей "
                         f"(снимка {snapshot} нет)")
    raw = json.loads(snapshot.read_text(encoding="utf-8"))
    entries = (raw["items"] if isinstance(raw, dict) else raw)[:limit]

    # Обогащение обязательно, и это не украшение. Списочный ответ поставщика не
    # несёт ни стран, ни жанров, ни длительности: у первых 4 000 записей страна
    # отсутствует **полностью**, и карта, построенная без обогащения, не имеет
    # раздела стран вовсе. Она описывала бы витрину беднее, чем та есть, — и
    # выглядела бы при этом достоверной.
    обогащено = 0
    if detail_cache is not None:
        from factory.lords import detail_enrichment

        details, broken = detail_enrichment.load_cached_details(detail_cache)
        # `merge_detail` возвращает новую запись и не правит на месте: правило
        # «detail добавляет, но не отнимает» проще соблюсти, ничего не меняя.
        # Отбросить возвращённое — значит собрать карту по необогащённым
        # записям и не заметить этого: она выйдет достоверной на вид и беднее
        # витрины на целый раздел.
        entries, обогащено = detail_enrichment.merge_cached(entries, details)
        описание_битых = f", битых файлов кэша {len(broken)}" if broken else ""
    else:
        описание_битых = ""

    catalog = live_catalog.catalog_from_live(entries)
    описание = f"срез боевого каталога, {len(catalog.titles)} записей"
    if detail_cache is not None:
        описание += f", обогащено {обогащено}{описание_битых}"
    return catalog, описание


def build_all(sites=SITES, snapshot=None, limit: int = 4000, detail_cache=None):
    """Карты всех витрин направления. Возвращает карты и описание каталога."""
    import yaml

    from factory.lords import render as render_mod
    from factory.paths import PATHS

    catalog, описание = _catalog(snapshot, limit, detail_cache)
    maps = []
    for site_id in sites:
        package = yaml.safe_load(
            PATHS.site_package(site_id).read_text(encoding="utf-8"))
        site = render_mod.render_site(package, catalog=catalog, environ={})
        maps.append(build(site))
    return maps, описание


def main(argv=None) -> int:
    """Собрать карту страниц.

    Точки входа у этого модуля не было вовсе. Документ
    `docs/templates/PAGE-MAP-lords.md` собрали однажды руками, и разойтись с
    кодом он мог молча: никто не мог его пересобрать, не зная, как именно.
    Документ, который нельзя перепроверить, со временем становится описанием
    того, чего нет.
    """
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description="карта страниц направления Lords")
    parser.add_argument("--write", action="store_true",
                        help="записать документ и запись свидетельства")
    parser.add_argument("--snapshot", default=DEFAULT_SNAPSHOT,
                        help="снимок боевого каталога; пусто — строить по фикстуре")
    parser.add_argument("--limit", type=int, default=4000,
                        help="сколько записей боевого каталога брать")
    parser.add_argument("--detail-cache", default=DEFAULT_DETAIL_CACHE,
                        help="кэш обогащения; без него карта беднее витрины")
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parents[2]
    maps, описание = build_all(snapshot=args.snapshot or None, limit=args.limit,
                               detail_cache=args.detail_cache or None)
    markdown = render_markdown(maps, описание)
    if args.write:
        (root / MARKDOWN_OUT).write_text(markdown, encoding="utf-8")
        target = root / JSON_OUT
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_json(maps), encoding="utf-8")
        print(f"{MARKDOWN_OUT}\n{JSON_OUT}")
    else:
        print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
