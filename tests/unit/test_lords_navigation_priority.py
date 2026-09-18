"""Порядок навигации и фасета «Тип» обязан следовать `navigation.primary` пакета.

`navigation.primary` — обязательное поле схемы пакета
(`schemas/site-package.schema.json`), уже наполненное каждым сайтом Lords
осмысленным порядком. Владелец `animedia-preview` заявил порядок явно —
Аниме, Сериалы, Фильмы, Мультфильмы (`sites/animedia-preview/package.yaml`,
комментарий «Аниме первым: витрина заведена ради него») — и тот же
generic-контракт уже отдаёт это поле как единственный источник шапки в другом
blueprint (`factory/render.py:217`). `factory/lords/render.py` эту часть
контракта не читал вовсе: и шапка (`_context()`), и фасет «Тип» на
`/catalog/` (`kinds = ct.active_types(...)`) шли фиксированным порядком
`blueprints/lords/blueprint.yaml`/`content_types.CONTENT_TYPES`, одинаковым
для всех профилей Lords — «Фильмы» и «Сериалы» обгоняли «Аниме» в шапке и в
фасете одной и той же витрины, наперекор её собственному пакету.

Передано владельцем общего слоя как CORE-HANDOFF
(`artifacts/evidence/templates/animedia-portal/finalization-01/
CORE-HANDOFF-nav-order.md`, коммит `b023bd5`, origin/
claude/animedia-template-finalization-01). Починка здесь не вводит новое поле
профиля (`layout.type_priority` из хендоффа) — она дочитывает уже
обязательное поле пакета, которое ни разу не тронуто этой веткой ни у одного
сайта.

Раздел, не упомянутый в `navigation.primary` (Каталог, Подборки, Новое,
Расписание, Жанры, Годы, Страны, Поиск), остаётся на своём текущем месте:
`navigation.primary` — короткий, курируемый список, а не полный состав
меню, и полная замена состава сломала бы кросс-сайтовую noindex-навигацию
(`blueprints/lords/blueprint.yaml`: «остальные сайты держат раздел как
навигацию с noindex»).
"""

from __future__ import annotations

import re

from factory.lords import fixtures as fx
from factory.lords import preview as preview_mod
from factory.lords import render as render_mod


def _site(site_id: str):
    package, _ = preview_mod._package(site_id)
    catalog = fx.build_catalog()
    return render_mod.render_site(package, catalog=catalog, environ={})


def _nav_urls(body: str) -> list[str]:
    nav = re.search(r'<nav class="site-nav".*?</nav>', body, re.S).group(0)
    return re.findall(r'<a href="([^"]+)"', nav)


def _facet_type_urls(body: str) -> list[str]:
    block = re.search(r'<legend>Тип</legend>(.*?)</ul>', body, re.S).group(1)
    return re.findall(r'href="([^"]+)"', block)


class TestNavigationOrderFollowsPackageContract:
    """`animedia-preview` объявляет Аниме первым — шапка обязана его слушать."""

    def test_header_nav_follows_navigation_primary_order(self):
        site = _site("animedia-preview")
        urls = _nav_urls(site.pages["/"].body)
        declared = ["/anime/", "/series/", "/movies/", "/animation/"]
        present = [u for u in urls if u in declared]
        assert present == declared, (
            f"шапка витрины показывает {present}, а package.yaml.navigation.primary "
            f"заявляет {declared}"
        )

    def test_catalog_type_facet_follows_navigation_primary_order(self):
        site = _site("animedia-preview")
        urls = _facet_type_urls(site.pages["/catalog/"].body)
        declared = ["/anime/", "/series/", "/movies/", "/animation/"]
        assert urls == declared, (
            f"фасет «Тип» на /catalog/ отдаёт {urls}, а тот же пакет заявляет {declared} "
            "в шапке — одна витрина не вправе противоречить себе на соседних экранах"
        )

    def test_sections_absent_from_navigation_primary_keep_their_position(self):
        """Каталог/Подборки/Новое/… не входят в navigation.primary — их место не меняется."""
        site = _site("animedia-preview")
        urls = _nav_urls(site.pages["/"].body)
        structural = [u for u in urls if u not in
                      {"/", "/anime/", "/series/", "/movies/", "/animation/"}]
        assert structural == [
            "/catalog/", "/collections/", "/new/", "/schedule/",
            "/genres/", "/years/", "/countries/", "/search/",
        ]


class TestNavigationOrderStaysBackwardCompatible:
    """Профили, чей navigation.primary уже совпадает с порядком блюпринта, не меняются."""

    def test_lords_01_header_nav_is_unchanged(self):
        site = _site("lords-01")
        urls = _nav_urls(site.pages["/"].body)
        assert urls == [
            "/", "/catalog/", "/movies/", "/series/", "/animation/", "/collections/",
            "/new/", "/schedule/", "/genres/", "/years/", "/countries/", "/search/",
        ]

    def test_zona_cinema_preview_header_nav_is_unchanged(self):
        # content_types.collections: false у этого пакета — /collections/ не входит в план.
        site = _site("zona-cinema-preview")
        urls = _nav_urls(site.pages["/"].body)
        assert urls == [
            "/", "/catalog/", "/movies/", "/series/", "/animation/",
            "/new/", "/schedule/", "/genres/", "/years/", "/countries/", "/search/",
        ]
