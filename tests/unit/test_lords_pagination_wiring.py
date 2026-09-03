"""Проводка разбиения по годам: выключено по умолчанию, включается пакетом.

Сама функция разбиения проверена в `test_lords_pagination_blocks.py`. Здесь
проверяется, что её вообще зовут и что переключатель делает то, что обещает:
правка, которую нельзя включить, ничем не отличается от несделанной.

Договор: adr/0007-pagination-by-year-blocks.md.
"""
from __future__ import annotations

import copy
import re

import yaml

from factory.lords import fixtures as fx
from factory.lords import render
from factory.paths import PATHS

SITE = "lords-01"


def пакет(*, по_годам: bool | None = None) -> dict:
    p = yaml.safe_load(PATHS.site_package(SITE).read_text(encoding="utf-8"))
    if по_годам is not None:
        p = copy.deepcopy(p)
        p.setdefault("seo", {})["pagination_by_year"] = по_годам
    return p


def карточки(body: str) -> list[str]:
    return re.findall(r'href="(/title/[^"]+)"', body)


def первая_страница_списка(site) -> str | None:
    for path in sorted(site.pages):
        if path.endswith("page/2/"):
            return path[: -len("page/2/")]
    return None


def test_по_умолчанию_разбиение_прежнее():
    обычный = render.render_site(пакет(), catalog=fx.build_catalog())
    выключенный = render.render_site(пакет(по_годам=False), catalog=fx.build_catalog())
    assert sorted(обычный.pages) == sorted(выключенный.pages)
    for path in обычный.pages:
        assert обычный.pages[path].body == выключенный.pages[path].body, path


def test_включение_меняет_состав_страниц_и_добавляет_адреса():
    """Ни один прежний адрес не исчезает, но новые появляются.

    Я сперва записал в договор, что адреса не меняются вовсе. Эта проверка
    показала обратное: каждый год начинается с новой страницы, последняя
    страница года неполна, и общее число страниц растёт — на фикстурном
    каталоге прибавилось 110 адресов. Договор исправлен по этой проверке,
    а не наоборот.
    """
    было = render.render_site(пакет(по_годам=False), catalog=fx.build_catalog())
    стало = render.render_site(пакет(по_годам=True), catalog=fx.build_catalog())

    исчезли = set(было.pages) - set(стало.pages)
    assert not исчезли, sorted(исчезли)[:10]

    появились = set(стало.pages) - set(было.pages)
    assert появились, "переключатель ничего не изменил"
    assert all("page/" in path for path in появились), sorted(появились)[:10]

    база = первая_страница_списка(было)
    if база is not None:
        assert карточки(было.pages[база].body) != карточки(стало.pages[база].body)


def test_на_странице_только_один_год():
    site = render.render_site(пакет(по_годам=True), catalog=fx.build_catalog())
    каталог = {t.slug: t.year for t in fx.build_catalog().titles}
    for path, page in site.pages.items():
        if "page/" not in path:
            continue
        годы = {
            каталог.get(m.rsplit("/", 2)[-2])
            for m in карточки(page.body)
        }
        годы.discard(None)
        assert len(годы) <= 1, (path, годы)
