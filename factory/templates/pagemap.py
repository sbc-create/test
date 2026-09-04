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


def render_markdown(maps: list[PageMap]) -> str:
    """Карта в виде, пригодном для чтения владельцем."""
    lines = ["# Карта страниц направления Lords", ""]
    lines.append(
        "Таблицы построены из собранных документов (`factory/templates/pagemap.py`). "
        "Однотипные адреса свёрнуты в один образец: `/title/{slug}/` вместо "
        "пятидесяти страниц произведений.")
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
