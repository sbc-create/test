"""Страница, индексируемая несколькими витринами, обязана различаться на каждой.

Три сайта Lords работают на одном каталоге. От дублей их спасает владение
разделами: каждый путь индексирует ровно один сайт, остальные держат его как
навигацию. Единственное исключение — главная: она своя у каждой витрины и
индексируется всеми тремя.

Поэтому именно главная — единственная точка, где кросс-доменный дубль возможен
физически. Одинаковые title, description или H1 на трёх индексируемых главных
означали бы три страницы, конкурирующие друг с другом по одним запросам.

Тест не заменяет проверку владения: он сторожит то, что владение не покрывает.
"""
from __future__ import annotations

import collections
import functools
import re

import yaml

from factory.lords import fixtures as fx
from factory.lords import render
from factory.paths import PATHS

SITES = ("lords-01", "lords-02", "lords-03")
TITLE = re.compile(r"<title>([^<]*)</title>")
DESCRIPTION = re.compile(r'<meta name="description" content="([^"]*)"')
H1 = re.compile(r"<h1[^>]*>([^<]*)</h1>")


def package(site_id: str) -> dict:
    return yaml.safe_load(PATHS.site_package(site_id).read_text(encoding="utf-8"))


@functools.lru_cache(maxsize=1)
def _indexable_meta() -> dict[str, dict[str, tuple[str, str, str]]]:
    """`{путь: {site_id: (title, description, h1)}}` только для индексируемых страниц.

    Рендер трёх витрин — заметная работа, а обоим тестам нужен один и тот же
    результат. Кэш держит её однократной: набор тестов не место для лишней
    нагрузки, от которой начинают мигать чужие проверки по таймингу.
    """
    out: dict[str, dict[str, tuple[str, str, str]]] = collections.defaultdict(dict)
    for site_id in SITES:
        site = render.render_site(package(site_id), catalog=fx.build_catalog())
        for path, page in site.pages.items():
            if not page.indexable:
                continue
            body = page.body
            out[path][site_id] = (
                (TITLE.search(body) or [None, ""])[1] if TITLE.search(body) else "",
                (DESCRIPTION.search(body) or [None, ""])[1] if DESCRIPTION.search(body) else "",
                (H1.search(body) or [None, ""])[1] if H1.search(body) else "",
            )
    return out


def test_ownership_leaves_exactly_one_multi_indexed_path():
    """Опора теста ниже: без неё он зеленел бы, ничего не проверив.

    Если владение разделами когда-нибудь перестанет разводить сайты, здесь
    появятся новые пути — и это само по себе повод разобраться раньше, чем
    дубли дойдут до выдачи.
    """
    shared = {p: v for p, v in _indexable_meta().items() if len(v) > 1}
    assert set(shared) == {"/"}, f"индексируется несколькими сайтами: {sorted(shared)}"


def test_pages_indexed_by_several_sites_differ_in_title_description_and_h1():
    for path, per_site in _indexable_meta().items():
        if len(per_site) < 2:
            continue
        for position, field in enumerate(("title", "description", "H1")):
            values = [meta[position] for meta in per_site.values()]
            assert len(set(values)) == len(values), (
                f"{path}: {field} совпадает у витрин {sorted(per_site)} — {values[0]!r}"
            )
