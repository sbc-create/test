"""Рендерер Lords: настоящие HTML-страницы, а не описание страниц.

Модуль превращает manifest, профиль и каталог в набор готовых документов —
ровно тех, что отдаёт сайт. План (`factory.lords.plan`) остаётся отдельным
слоем и отвечает на вопрос «какие поверхности существуют и кто их индексирует»;
рендерер отвечает на вопрос «как они выглядят». Подменять второе первым нельзя:
план невозможно открыть в браузере и невозможно проверить визуально.

Свойства, которые здесь удерживаются:

* ни одного внешнего запроса — ни шрифта, ни скрипта, ни изображения;
* тип контента в состоянии, отличном от `enabled`, не создаёт ни страницы, ни
  ссылки, ни записи в sitemap; обращение к его адресу даёт 404, а не пустой 200;
* пока домен не передан, canonical не выдумывается, sitemap не получает ни
  одного адреса, а каждая страница несёт `noindex, nofollow`;
* значения секретов в разметку не попадают: плеер знает только своё состояние.
"""

from __future__ import annotations

import html
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from factory.lords import content_types as ct
from factory.lords import fixtures as fx
from factory.lords import plan as plan_mod
from factory.lords import player as player_mod
from factory.lords import theme as theme_mod

#: Состояния canonical. Пишутся и в разметку, и в отчёт: «canonical нет» и
#: «canonical ведёт на себя» — разные факты, и путать их нельзя.
CANONICAL_ABSENT = "absent_no_domain"
CANONICAL_SELF = "self"

TYPE_LABELS = {
    fx.MOVIES: "Фильм",
    fx.SERIES: "Сериал",
    fx.ANIMATION: "Мультфильм",
    fx.ANIME: "Аниме",
    fx.DORAMA: "Дорама",
}

#: Раздел → тип контента, который он показывает.
SECTION_TYPE = {
    "movies_index": fx.MOVIES,
    "series_index": fx.SERIES,
    "animation_index": fx.ANIMATION,
    "anime_index": fx.ANIME,
    "dorama_index": fx.DORAMA,
}

#: Подписи разделов для навигации. Профиль даёт текст только своим разделам,
#: но пункт меню нужен всем: без подписи ссылка нечитаема.
SECTION_LABELS = {
    "home": "Главная",
    "catalog_index": "Каталог",
    "movies_index": "Фильмы",
    "series_index": "Сериалы",
    "animation_index": "Мультфильмы",
    "anime_index": "Аниме",
    "dorama_index": "Дорамы",
    "collections_index": "Подборки",
    "new_index": "Новое",
    "schedule": "Расписание",
    "genres_index": "Жанры",
    "years_index": "Годы",
    "countries_index": "Страны",
    "search": "Поиск",
}

SORTS = (
    ("recent", "Сначала новые"),
    ("old", "Сначала старые"),
    ("name", "По названию"),
    ("long", "По длительности"),
)


def escape(value) -> str:
    return html.escape(str(value), quote=True)


@dataclass(frozen=True)
class Page:
    path: str
    body: str
    content_type: str = "text/html; charset=utf-8"
    indexable: bool = False
    status: int = 200


@dataclass
class RenderedSite:
    site_id: str
    profile: str
    brand: str
    pages: dict = field(default_factory=dict)
    not_found: Page | None = None
    plan: plan_mod.SitePlan | None = None
    report: dict = field(default_factory=dict)

    def paths(self) -> list:
        return sorted(self.pages)

    def html_paths(self) -> list:
        return sorted(p for p, page in self.pages.items() if page.content_type.startswith("text/html"))


# ---------------------------------------------------------------------------
# Постеры: локальные нейтральные заглушки, сгенерированные из слага
# ---------------------------------------------------------------------------
def poster_svg(title: fx.Title) -> str:
    """Заглушка постера. Ни одного чужого изображения и ни одного запроса наружу.

    Цвет выводится из слага, поэтому одна и та же запись всегда выглядит
    одинаково, а соседние карточки отличаются. Палитра приглушённая: заглушка
    обязана читаться как заглушка, а не как обложка.
    """
    seed = sum(ord(c) * (i + 1) for i, c in enumerate(title.slug))
    hue = seed % 360
    initials = "".join(word[0] for word in title.name.split()[:2]).upper()
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 600" '
        f'role="img" aria-label="Заглушка постера: {escape(title.name)}">'
        f'<rect width="400" height="600" fill="hsl({hue} 14% 21%)"/>'
        f'<rect y="430" width="400" height="170" fill="hsl({hue} 16% 16%)"/>'
        f'<circle cx="200" cy="250" r="96" fill="none" stroke="hsl({hue} 22% 38%)" stroke-width="3"/>'
        f'<text x="200" y="278" text-anchor="middle" font-size="86" font-weight="700" '
        f'fill="hsl({hue} 20% 62%)" font-family="system-ui, sans-serif">{escape(initials)}</text>'
        '<text x="200" y="500" text-anchor="middle" font-size="26" fill="hsl(0 0% 72%)" '
        'font-family="system-ui, sans-serif">FIXTURE</text>'
        '<text x="200" y="536" text-anchor="middle" font-size="19" fill="hsl(0 0% 55%)" '
        'font-family="system-ui, sans-serif">тестовая заглушка</text>'
        "</svg>"
    )


# ---------------------------------------------------------------------------
# Каркас документа
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Meta:
    title: str
    description: str
    h1: str
    page_type: str = "category"
    indexable: bool = False
    breadcrumbs: tuple = ()
    poster: str = ""
    jsonld: tuple = ()
    #: Ставить ли canonical на себя. Выключается там, где устойчивого адреса
    #: нет: выдача поиска зависит от запроса, и канонизировать её нечем.
    canonical_self: bool = True


def _nav_items(sections: list, current: str) -> str:
    out = []
    for section, path in sections:
        label = SECTION_LABELS.get(section, section)
        aria = ' aria-current="page"' if path == current else ""
        out.append(f'<li><a href="{escape(path)}"{aria}>{escape(label)}</a></li>')
    return "".join(out)


def _breadcrumbs(trail: tuple) -> str:
    if not trail:
        return ""
    items = []
    for index, (label, href) in enumerate(trail):
        last = index == len(trail) - 1
        inner = escape(label) if last or not href else f'<a href="{escape(href)}">{escape(label)}</a>'
        items.append(f"<li>{inner}</li>")
    return (
        '<nav class="breadcrumbs" aria-label="Хлебные крошки"><ol>'
        + "".join(items)
        + "</ol></nav>"
    )


def _breadcrumb_jsonld(trail: tuple) -> dict | None:
    if len(trail) < 2:
        return None
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": label,
             **({"item": href} if href else {})}
            for i, (label, href) in enumerate(trail)
        ],
    }


def _document(ctx: dict, meta: Meta, body: str) -> str:
    """Полный HTML-документ. Всё встроено, ничего не подгружается извне."""
    brand = ctx["brand"]
    lang = ctx["language"]
    full_title = meta.title if meta.title.endswith(brand) else f"{meta.title} — {brand}"

    head = [
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{escape(full_title)}</title>",
        f'<meta name="description" content="{escape(meta.description)}">',
    ]
    # Canonical и индексация — разные вопросы, и решаются они порознь.
    # Canonical говорит, какой адрес считать основным; он осмыслен, как только
    # известен домен, и не зависит от того, пускаем ли мы туда поисковик.
    # Индексацию закрывает `noindex`, и на стенде он стоит всегда: каталог
    # синтетический, а показывать поисковику тестовые записи нельзя ни при каких
    # настройках профиля.
    if ctx["canonical_base"] and meta.canonical_self:
        head.append(
            f'<link rel="canonical" href="{escape(ctx["canonical_base"] + meta_path(ctx))}">'
        )
    if not (meta.indexable and ctx["indexing_enabled"]):
        head.append('<meta name="robots" content="noindex, nofollow">')
    head.append(f'<meta name="lords-canonical-state" content="{escape(ctx["canonical_state"])}">')
    head += [
        f'<meta property="og:type" content="{"video.movie" if meta.page_type == "title" else "website"}">',
        f'<meta property="og:site_name" content="{escape(brand)}">',
        f'<meta property="og:title" content="{escape(full_title)}">',
        f'<meta property="og:description" content="{escape(meta.description)}">',
        f'<meta property="og:locale" content="{escape("ru_RU" if lang == "ru" else lang)}">',
    ]
    if meta.poster:
        head.append(f'<meta property="og:image" content="{escape(meta.poster)}">')
    head.append('<meta name="lords-data-source" content="fixture/test">')
    head.append('<link rel="stylesheet" href="/assets/site.css">')
    head.append(
        '<link rel="icon" href="data:image/svg+xml,'
        "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E"
        "%3Crect width='16' height='16' rx='3' fill='%23888'/%3E%3C/svg%3E\">"
    )

    blocks = list(meta.jsonld)
    crumbs = _breadcrumb_jsonld(meta.breadcrumbs)
    if crumbs:
        blocks.append(crumbs)
    for block in blocks:
        payload = json.dumps(block, ensure_ascii=False, separators=(",", ":"))
        head.append(f'<script type="application/ld+json">{payload}</script>')

    return (
        f'<!doctype html><html lang="{escape(lang)}"><head>'
        + "".join(head)
        + "</head><body>"
        + _header(ctx, meta)
        + '<main id="content"><div class="container">'
        + _breadcrumbs(meta.breadcrumbs)
        + body
        + "</div></main>"
        + _footer(ctx)
        + '<script src="/assets/app.js" defer></script>'
        + "</body></html>"
    )


def meta_path(ctx: dict) -> str:
    return ctx.get("_path", "/")


def _header(ctx: dict, meta: Meta) -> str:
    mark = escape(ctx["mark"])
    return (
        '<a class="visually-hidden" href="#content">Перейти к содержимому</a>'
        '<div class="preview-banner"><p><strong>Тестовый стенд.</strong> '
        "Каталог синтетический (fixture/test), названия и постеры выдуманы, "
        "индексация закрыта.</p></div>"
        '<header class="site-header"><div class="header-row">'
        f'<a class="brand" href="/"><span class="brand__mark">{mark}</span>'
        f'<span class="brand__name">{escape(ctx["brand"])}</span>'
        f'<span class="brand__kind">{escape(ctx["site_id"])}</span></a>'
        '<button class="nav-toggle" type="button" aria-expanded="false" '
        'aria-controls="site-nav">Меню</button>'
        '<nav class="site-nav" id="site-nav" aria-label="Основная навигация"><ul>'
        + _nav_items(ctx["nav"], ctx.get("_path", ""))
        + "</ul></nav>"
        '<form class="header-search" role="search" action="/search/" method="get">'
        '<label class="visually-hidden" for="q">Поиск по каталогу</label>'
        '<input id="q" name="q" type="search" placeholder="Название из каталога" '
        'autocomplete="off">'
        "<button type=\"submit\">Найти</button></form>"
        "</div></header>"
    )


def _footer(ctx: dict) -> str:
    links = "".join(
        f'<li><a href="{escape(path)}">{escape(SECTION_LABELS.get(section, section))}</a></li>'
        for section, path in ctx["nav"]
    )
    return (
        '<footer class="site-footer"><div class="container">'
        f"<ul>{links}</ul>"
        f"<p>{escape(ctx['brand'])} · {escape(ctx['site_id'])} · профиль "
        f"{escape(ctx['profile'])}.</p>"
        "<p>Стенд собран фабрикой из синтетических данных. Каталог не описывает "
        "существующие произведения, оценок и сведений о правообладателях не "
        "содержит и в поисковые системы не отдаётся.</p>"
        "<p>Правовые документы появятся вместе с владельцем и доменом: "
        "выдумывать реквизиты стенд не станет.</p>"
        "</div></footer>"
    )


# ---------------------------------------------------------------------------
# Карточки и списки
# ---------------------------------------------------------------------------
def _card(title: fx.Title) -> str:
    seasons = (
        f'<span class="card__seasons">{title.episode_count} сер.</span>'
        if title.episodic else ""
    )
    meta = f"{TYPE_LABELS.get(title.content_type, title.content_type)} · {title.year} · {title.country}"
    return (
        f'<article class="card" data-slug="{escape(title.slug)}">'
        f'<a class="card__poster" href="{escape(title.path)}" tabindex="-1" aria-hidden="true">'
        f'<img src="{escape(title.poster_path)}" alt="" loading="lazy" width="400" height="600">'
        '<span class="card__badge">fixture</span>'
        f"{seasons}</a>"
        '<div class="card__body">'
        f'<a class="card__title" href="{escape(title.path)}">{escape(title.name)}</a>'
        f'<span class="card__meta">{escape(meta)}</span>'
        f'<span class="card__meta">{escape(", ".join(title.genres))}</span>'
        "</div></article>"
    )


def _grid(titles) -> str:
    if not titles:
        return (
            '<p class="empty">По выбранным условиям в тестовом каталоге ничего нет. '
            "Стенд показывает пустой результат честно и не подставляет чужие записи.</p>"
        )
    return '<div class="grid" id="grid">' + "".join(_card(t) for t in titles) + "</div>"


def _pagination(base: str, page: int, pages: int) -> str:
    if pages <= 1:
        return ""
    def href(n: int) -> str:
        return base if n == 1 else f"{base}page/{n}/"
    items = []
    if page > 1:
        items.append(f'<li><a rel="prev" href="{escape(href(page - 1))}">Назад</a></li>')
    for n in range(1, pages + 1):
        if n == page:
            items.append(f'<li><span aria-current="page">{n}</span></li>')
        else:
            items.append(f'<li><a href="{escape(href(n))}">{n}</a></li>')
    if page < pages:
        items.append(f'<li><a rel="next" href="{escape(href(page + 1))}">Вперёд</a></li>')
    return (
        '<nav class="pagination" aria-label="Страницы списка"><ul>'
        + "".join(items) + "</ul></nav>"
    )


def _options(pairs, name: str) -> str:
    body = "".join(f'<option value="{escape(v)}">{escape(label)}</option>' for v, label in pairs)
    return f'<option value="">{escape(name)}</option>{body}'


def _facets(catalog: fx.Catalog, kinds, *, show_type: bool, row: bool = False) -> str:
    """Панель фильтров и сортировки. Работает поверх встроенного набора данных.

    `row` включает раскладку в строку — она нужна там, где фасеты стоят над
    списком: пять полей в колонку отодвигают первую карточку за сгиб, и раздел
    выглядит пустым, хотя в нём полсотни записей.
    """
    types = [(k, TYPE_LABELS[k]) for k in kinds if catalog.of_type(k)]
    genres = [(slug, f"{label} ({count})") for slug, label, count in catalog.genres(kinds)]
    years = [(str(y), f"{y} ({c})") for y, c in catalog.years(kinds)]
    countries = [(slug, f"{label} ({count})") for slug, label, count in catalog.countries(kinds)]

    type_block = ""
    if show_type and len(types) > 1:
        type_block = (
            '<fieldset><legend>Тип</legend>'
            f'<select id="f-type" data-facet="type">{_options(types, "Любой тип")}</select>'
            "</fieldset>"
        )
    css = "facets facets--row" if row else "facets"
    return (
        f'<form class="{css}" id="facets" aria-label="Фильтры и сортировка">'
        "<h2>Фильтры</h2>"
        + type_block
        + '<fieldset><legend>Жанр</legend>'
        f'<select id="f-genre" data-facet="genre">{_options(genres, "Любой жанр")}</select>'
        "</fieldset>"
        '<fieldset><legend>Год</legend>'
        f'<select id="f-year" data-facet="year">{_options(years, "Любой год")}</select>'
        "</fieldset>"
        '<fieldset><legend>Страна</legend>'
        f'<select id="f-country" data-facet="country">{_options(countries, "Любая страна")}</select>'
        "</fieldset>"
        '<fieldset><legend>Сортировка</legend>'
        f'<select id="f-sort" data-facet="sort">{_options(SORTS[1:], SORTS[0][1])}</select>'
        "</fieldset>"
        '<button class="facets__reset" type="reset">Сбросить</button>'
        "</form>"
    )


def _dataset(titles) -> str:
    """Полный набор списка для клиентской фильтрации.

    Пагинация на сервере отдаёт одну страницу, и фильтровать её содержимое было
    бы обманом: пользователь увидел бы «ничего не найдено» там, где запись есть
    на третьей странице. Поэтому список фильтруется по полному набору, а
    серверная разбивка остаётся тем, что видно без JavaScript.
    """
    payload = [
        {
            "slug": t.slug, "name": t.name, "type": t.content_type,
            "typeLabel": TYPE_LABELS.get(t.content_type, t.content_type),
            "year": t.year, "country": t.country, "countrySlug": t.country_slug,
            "genres": list(t.genre_slugs), "genreLabels": list(t.genres),
            "runtime": t.runtime_min, "episodes": t.episode_count,
            "path": t.path, "poster": t.poster_path,
        }
        for t in titles
    ]
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    # `</script>` внутри данных закрыл бы тег раньше времени.
    body = body.replace("<", "\\u003c")
    return f'<script type="application/json" id="listing-data">{body}</script>'


# ---------------------------------------------------------------------------
# Страницы списков
# ---------------------------------------------------------------------------
def _sorted(titles) -> list:
    return sorted(titles, key=lambda t: (-t.year, t.name, t.slug))


def _listing_pages(
    ctx,
    *,
    base: str,
    titles,
    catalog: fx.Catalog,
    kinds,
    section_title: str,
    h1: str,
    description: str,
    intro: str,
    indexable: bool,
    trail,
    page_type: str = "category",
    show_type: bool = True,
    show_facets: bool = True,
    extra_top: str = "",
) -> list:
    """Список с фасетами, сортировкой и пагинацией. Одна функция на все разделы."""
    items = _sorted(titles)
    per_page = ctx["per_page"]
    pages_count = max(1, math.ceil(len(items) / per_page)) if items else 1
    out = []
    position = ctx["facet_position"]
    facets = (
        _facets(catalog, kinds, show_type=show_type, row=position != "sidebar")
        if (show_facets and items) else ""
    )

    for number in range(1, pages_count + 1):
        chunk = items[(number - 1) * per_page: number * per_page]
        path = base if number == 1 else f"{base}page/{number}/"
        heading = h1 if number == 1 else f"{h1} — страница {number}"
        title = section_title if number == 1 else f"{section_title} — страница {number}"
        desc = description if number == 1 else f"{description} Страница {number}."
        lede = f'<p class="lede">{escape(intro)}</p>' if intro and number == 1 else ""
        grid = _grid(chunk) + _pagination(base, number, pages_count)
        body_top = (
            f'<h1>{escape(heading)}</h1>{lede}'
            f'<p class="count">Записей в разделе: {len(items)}.</p>{extra_top}'
        )
        if not facets:
            inner = body_top + grid
        elif position == "sidebar":
            inner = body_top + f'<div class="listing">{facets}<div>{grid}</div></div>'
        else:  # top / hero / none — фасеты стоят над списком
            inner = body_top + facets + grid
        inner += _dataset(items)

        page_trail = trail if number == 1 else trail + ((f"Страница {number}", ""),)
        jsonld = ({
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": title,
            "description": desc,
            "inLanguage": ctx["language"],
            "isPartOf": {"@type": "WebSite", "name": ctx["brand"]},
        },)
        meta = Meta(
            title=title, description=desc, h1=heading, page_type=page_type,
            # Индексируется только первая страница владельца: страницы 2..N —
            # то же содержимое в другой нарезке.
            indexable=indexable and number == 1,
            breadcrumbs=page_trail, jsonld=jsonld,
        )
        out.append(_page(ctx, path, meta, inner))
    return out


def _page(ctx, path: str, meta: Meta, body: str) -> Page:
    local = dict(ctx)
    local["_path"] = path
    return Page(path=path, body=_document(local, meta, body), indexable=meta.indexable)


# ---------------------------------------------------------------------------
# Главная
# ---------------------------------------------------------------------------
def _chips(pairs) -> str:
    return '<ul class="chips">' + "".join(
        f'<li><a href="{escape(href)}">{escape(label)}'
        f'<span class="chips__count">{count}</span></a></li>'
        for label, href, count in pairs
    ) + "</ul>"


def _home(ctx, catalog: fx.Catalog, kinds, section) -> Page:
    text = ctx["texts"].get("home") or {}
    blocks = ctx["home_blocks"]
    pool = catalog.of_types(kinds)
    latest = _sorted(pool)[:ctx["home_items"]]
    parts = []

    hero_kind = ctx["hero"]
    hero_body = f'<h1>{escape(text.get("h1") or SECTION_LABELS["home"])}</h1>'
    hero_body += f'<p class="lede">{escape(text.get("intro", ""))}</p>'
    if "hero_search" in blocks:
        hero_body += (
            '<form class="header-search" role="search" action="/search/" method="get">'
            '<label class="visually-hidden" for="hero-q">Поиск по каталогу</label>'
            '<input id="hero-q" name="q" type="search" placeholder="Название из каталога">'
            "<button type=\"submit\">Найти</button></form>"
        )
    if "hero_facets" in blocks:
        hero_body += _chips([
            (label, f"/genres/{slug}/", count) for slug, label, count in catalog.genres(kinds)[:8]
        ])
    parts.append(f'<section class="hero hero--{escape(hero_kind)}">{hero_body}</section>')

    for block in blocks:
        if block == "latest_grid":
            parts.append(
                '<section class="section"><div class="section__head">'
                "<h2>Последние добавления</h2>"
                f'<a class="section__more" href="{escape(ctx["catalog_path"])}">Весь каталог</a>'
                "</div>" + _grid(latest) + "</section>"
            )
        elif block == "type_rows":
            for kind in kinds:
                row = _sorted(catalog.of_type(kind))[:ctx["row_items"]]
                if not row:
                    continue
                href = ctx["type_paths"].get(kind)
                more = f'<a class="section__more" href="{escape(href)}">Все</a>' if href else ""
                parts.append(
                    '<section class="section"><div class="section__head">'
                    f"<h2>{escape(TYPE_LABELS[kind])}</h2>{more}</div>"
                    + _grid(row) + "</section>"
                )
        elif block == "genre_chips":
            parts.append(
                '<section class="section"><h2>Жанры</h2>'
                + _chips([(label, f"/genres/{slug}/", count)
                          for slug, label, count in catalog.genres(kinds)])
                + "</section>"
            )
        elif block == "year_grid":
            parts.append(
                '<section class="section"><h2>Годы выпуска</h2>'
                + _chips([(str(year), f"/years/{year}/", count)
                          for year, count in catalog.years(kinds)])
                + "</section>"
            )
        elif block == "country_grid":
            parts.append(
                '<section class="section"><h2>Страны</h2>'
                + _chips([(label, f"/countries/{slug}/", count)
                          for slug, label, count in catalog.countries(kinds)])
                + "</section>"
            )
        elif block == "calendar" and ctx["show_calendar"]:
            parts.append(_calendar(catalog, kinds))
        elif block == "fresh_episodes":
            episodic = [t for t in _sorted(pool) if t.episodic][:ctx["row_items"]]
            if episodic:
                parts.append(
                    '<section class="section"><div class="section__head">'
                    "<h2>Продолжающиеся истории</h2></div>" + _grid(episodic) + "</section>"
                )
        elif block == "collection_cards" and ctx["show_collection_cards"]:
            parts.append(_collection_cards(ctx, catalog))
        elif block == "editor_note":
            parts.append(
                '<section class="section"><h2>Как собран список</h2>'
                '<p class="lede">Подборки на стенде собраны по формальным признакам '
                "тестового каталога — длительности, числу сезонов, названию. "
                "Редакционного отбора здесь нет и быть не может: за записями не "
                "стоят реальные произведения.</p></section>"
            )

    jsonld = ({
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": ctx["brand"],
        "description": text.get("description", ""),
        "inLanguage": ctx["language"],
    },)
    meta = Meta(
        title=text.get("title") or ctx["brand"],
        description=text.get("description", ""),
        h1=text.get("h1") or ctx["brand"],
        page_type="home",
        indexable=bool(section and section.indexable),
        breadcrumbs=(),
        jsonld=jsonld,
    )
    return _page(ctx, "/", meta, "".join(parts))


def _calendar(catalog: fx.Catalog, kinds) -> str:
    """Календарь серий стенда. Даты условные и подписаны как условные.

    Реальных дат выхода у выдуманных записей нет; выдавать вымысел за расписание
    премьер нельзя, поэтому строка календаря говорит о порядке, а не о дате.
    """
    rows = []
    for title in _sorted([t for t in catalog.of_types(kinds) if t.episodic])[:8]:
        last = title.seasons[-1]
        rows.append(
            f'<li class="episode"><span><a href="{escape(title.path)}">'
            f"{escape(title.name)}</a></span>"
            f"<span>сезон {last.number}, серий {len(last.episodes)}</span></li>"
        )
    if not rows:
        return ""
    return (
        '<section class="section"><h2>Что продолжается</h2>'
        '<p class="lede">Порядок выхода серий на стенде условный: дат премьер у '
        "синтетических записей нет и не будет выдумано.</p>"
        '<ol class="season">' + "".join(rows) + "</ol></section>"
    )


def _collection_cards(ctx, catalog: fx.Catalog) -> str:
    cards = []
    for col in catalog.collections:
        cards.append(
            '<article class="card"><div class="card__body">'
            f'<a class="card__title" href="{escape(col.path)}">{escape(col.name)}</a>'
            f'<span class="card__meta">{len(col.title_slugs)} записей</span>'
            f'<span class="card__meta">{escape(col.summary)}</span>'
            "</div></article>"
        )
    return (
        '<section class="section"><div class="section__head"><h2>Подборки</h2>'
        '<a class="section__more" href="/collections/">Все подборки</a></div>'
        '<div class="grid">' + "".join(cards) + "</div></section>"
    )


# ---------------------------------------------------------------------------
# Страница произведения
# ---------------------------------------------------------------------------
def _seasons_block(title: fx.Title) -> str:
    if not title.episodic:
        return (
            '<section class="seasons"><h2>Структура</h2>'
            '<p class="lede">У полнометражной записи сезонов нет: страница ведёт '
            "к одному просмотру, а не к списку серий.</p></section>"
        )
    blocks = []
    for season in title.seasons:
        episodes = "".join(
            f'<li class="episode"><span>{escape(episode.name)}</span>'
            f"<span>{episode.runtime_min} мин</span></li>"
            for episode in season.episodes
        )
        opened = " open" if season.number == 1 else ""
        blocks.append(
            f'<details class="season"{opened}><summary>Сезон {season.number} · '
            f"{len(season.episodes)} серий</summary><ol>{episodes}</ol></details>"
        )
    return (
        '<section class="seasons"><h2>Сезоны и серии</h2>'
        + "".join(blocks) + "</section>"
    )


def _comments_block(ctx, title: fx.Title) -> str:
    if not ctx["comments_enabled"]:
        return ""
    return (
        '<section class="comments" aria-labelledby="comments-heading">'
        '<h2 id="comments-heading">Комментарии</h2>'
        '<p class="comments__note">На стенде комментарии выключены: писать не о чем — '
        "запись синтетическая, а публиковать чужие тексты стенд не станет. "
        "Форма показана, чтобы блок занимал своё место в раскладке.</p>"
        "<form><label class=\"visually-hidden\" for=\"comment\">Текст комментария</label>"
        '<textarea id="comment" disabled placeholder="Отправка выключена на стенде">'
        "</textarea>"
        '<button type="button" disabled>Отправить</button></form>'
        "</section>"
    )


def _related(catalog: fx.Catalog, title: fx.Title, kinds, limit: int) -> str:
    """Похожее — только по признакам самой записи, без сторонних источников."""
    pool = [t for t in catalog.of_types(kinds) if t.slug != title.slug]
    def score(other: fx.Title) -> tuple:
        shared = len(set(other.genre_slugs) & set(title.genre_slugs))
        same_type = other.content_type == title.content_type
        return (-shared, not same_type, abs(other.year - title.year), other.slug)
    picks = sorted(pool, key=score)[:limit]
    if not picks:
        return ""
    return (
        '<section class="section"><div class="section__head"><h2>Похожее</h2></div>'
        + _grid(picks) + "</section>"
    )


def _title_page(ctx, catalog: fx.Catalog, title: fx.Title, kinds, indexable: bool) -> Page:
    tpl = ctx["title_page"]
    name = title.name
    page_title = str(tpl.get("title_template", "{name}")).format(name=name)
    description = str(tpl.get("description_template", "{name}")).format(name=name)
    h1 = str(tpl.get("h1_template", "{name}")).format(name=name)

    facts = [
        ("Оригинальное название", title.original_name),
        ("Тип", TYPE_LABELS.get(title.content_type, title.content_type)),
        ("Год", str(title.year)),
        ("Страна", title.country),
        ("Жанры", ", ".join(title.genres)),
        ("Студия", title.studio),
        ("Возрастная отметка", title.age_rating),
        (
            "Длительность",
            f"{title.runtime_min} мин"
            + (f" · серий {title.episode_count}" if title.episodic else ""),
        ),
        ("Происхождение данных", f"{title.source} — синтетическая запись стенда"),
    ]
    facts_html = "".join(
        f"<dt>{escape(label)}</dt><dd>{escape(value)}</dd>" for label, value in facts
    )

    head = (
        f'<div class="title-head"><div class="title-head__poster">'
        f'<img src="{escape(title.poster_path)}" alt="Заглушка постера: {escape(name)}" '
        'width="400" height="600"></div><div>'
        f"<h1>{escape(h1)}</h1>"
        f'<p class="lede">{escape(title.summary)}</p>'
        f'<dl class="facts">{facts_html}</dl></div></div>'
    )

    body = (
        head
        + player_mod.render(ctx["player_state"], title_name=name)
        + _seasons_block(title)
        + '<section class="section"><h2>О карточке</h2>'
        + f'<p class="lede">{escape(tpl.get("intro", ""))}</p></section>'
        + _related(catalog, title, kinds, ctx["row_items"])
        + _comments_block(ctx, title)
    )

    schema_type = "Movie" if not title.episodic else "TVSeries"
    entity = {
        "@context": "https://schema.org",
        "@type": schema_type,
        "name": name,
        "alternateName": title.original_name,
        "description": title.summary,
        "inLanguage": ctx["language"],
        "genre": list(title.genres),
        "countryOfOrigin": {"@type": "Country", "name": title.country},
        "productionCompany": {"@type": "Organization", "name": title.studio},
        "copyrightYear": title.year,
    }
    if title.episodic:
        entity["numberOfSeasons"] = len(title.seasons)
        entity["numberOfEpisodes"] = title.episode_count
    else:
        entity["duration"] = f"PT{title.runtime_min}M"

    trail = (
        ("Главная", "/"),
        (SECTION_LABELS["catalog_index"], ctx["catalog_path"]),
        (name, ""),
    )
    meta = Meta(
        title=page_title, description=description, h1=h1, page_type="title",
        indexable=indexable, breadcrumbs=trail, poster=title.poster_path,
        jsonld=(entity,),
    )
    return _page(ctx, title.path, meta, body)


# ---------------------------------------------------------------------------
# Поиск, служебные документы и 404
# ---------------------------------------------------------------------------
def _search_page(ctx, catalog: fx.Catalog, kinds) -> Page:
    text = ctx["texts"].get("search") or {}
    items = _sorted(catalog.of_types(kinds))
    body = (
        f'<h1>{escape(text.get("h1", "Поиск"))}</h1>'
        f'<p class="lede">{escape(text.get("intro", ""))}</p>'
        '<form class="header-search" role="search" action="/search/" method="get">'
        '<label class="visually-hidden" for="search-q">Строка поиска</label>'
        '<input id="search-q" name="q" type="search" placeholder="Название из каталога" '
        'autocomplete="off">'
        "<button type=\"submit\">Найти</button></form>"
        '<p class="count" id="search-count">Введите название: поиск идёт по '
        f'{len(items)} записям тестового каталога.</p>'
        '<div class="grid" id="grid"></div>'
        + _dataset(items)
    )
    meta = Meta(
        title=text.get("title", "Поиск"),
        description=text.get("description", "Поиск по каталогу."),
        h1=text.get("h1", "Поиск"),
        page_type="search",
        # Выдача поиска не индексируется никогда: содержимое зависит от запроса.
        indexable=False,
        breadcrumbs=(("Главная", "/"), ("Поиск", "")),
        # И канонизировать её нечем: устойчивого адреса у результата нет.
        canonical_self=False,
    )
    return _page(ctx, "/search/", meta, body)


def _not_found(ctx) -> Page:
    body = (
        "<h1>Страница не найдена</h1>"
        '<p class="lede">Такого адреса на сайте нет. Возможные причины: раздел '
        "выключен в настройках сайта, запись отсутствует в каталоге или адрес "
        "набран с ошибкой.</p>"
        '<p><a href="/">Вернуться на главную</a></p>'
    )
    meta = Meta(
        title="Страница не найдена", description="Запрошенного адреса на сайте нет.",
        h1="Страница не найдена", page_type="not_found", indexable=False,
    )
    page = _page(ctx, "/404.html", meta, body)
    return Page(path=page.path, body=page.body, indexable=False, status=404)


def _robots(ctx) -> Page:
    """robots.txt стенда. Пока индексация закрыта — закрыт весь сайт целиком."""
    if ctx["indexing_enabled"] and ctx["domain"]:  # pragma: no cover - требует домена
        lines = ["User-agent: *", "Allow: /", f"Sitemap: https://{ctx['domain']}/sitemap.xml"]
    else:
        lines = [
            "# Стенд закрыт от индексации: домен не передан, данные синтетические.",
            "User-agent: *",
            "Disallow: /",
        ]
    return Page(path="/robots.txt", body="\n".join(lines) + "\n",
                content_type="text/plain; charset=utf-8")


def _sitemap(ctx, indexable_paths) -> Page:
    """sitemap.xml. Без домена в нём не может быть ни одного адреса.

    Адрес в sitemap абсолютен по спецификации. Придумать хост — значит указать
    поисковику на чужой или несуществующий сайт, поэтому карта остаётся
    синтаксически корректной, но пустой, и прямо говорит почему.
    """
    urls = []
    if ctx["domain"] and ctx["indexing_enabled"]:  # pragma: no cover - требует домена
        urls = [f"  <url><loc>https://{ctx['domain']}{path}</loc></url>" for path in indexable_paths]
        note = ""
    else:
        note = (
            "  <!-- Адресов нет: домен не передан, а абсолютный URL без домена "
            "невозможен. Карта заполнится вместе с доменом. -->\n"
        )
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + note + ("\n".join(urls) + "\n" if urls else "")
        + "</urlset>\n"
    )
    return Page(path="/sitemap.xml", body=body, content_type="application/xml; charset=utf-8")


APP_JS = """/* Lords — поведение интерфейса. Ни одного внешнего запроса. */
(function () {
  "use strict";
  var toggle = document.querySelector(".nav-toggle");
  var nav = document.getElementById("site-nav");
  if (toggle && nav) {
    toggle.addEventListener("click", function () {
      var open = nav.getAttribute("data-open") === "true";
      nav.setAttribute("data-open", open ? "false" : "true");
      toggle.setAttribute("aria-expanded", open ? "false" : "true");
    });
  }

  var node = document.getElementById("listing-data");
  var grid = document.getElementById("grid");
  if (!node || !grid) { return; }
  var items = [];
  try { items = JSON.parse(node.textContent); } catch (e) { return; }

  var PER_PAGE = 24;
  var page = 1;

  function card(item) {
    var seasons = item.episodes ? '<span class="card__seasons">' + item.episodes + ' сер.</span>' : "";
    return '<article class="card" data-slug="' + item.slug + '">'
      + '<a class="card__poster" href="' + item.path + '" tabindex="-1" aria-hidden="true">'
      + '<img src="' + item.poster + '" alt="" loading="lazy" width="400" height="600">'
      + '<span class="card__badge">fixture</span>' + seasons + "</a>"
      + '<div class="card__body"><a class="card__title" href="' + item.path + '">'
      + item.name + "</a>"
      + '<span class="card__meta">' + item.typeLabel + " · " + item.year + " · " + item.country + "</span>"
      + '<span class="card__meta">' + item.genreLabels.join(", ") + "</span></div></article>";
  }

  function value(id) {
    var el = document.getElementById(id);
    return el ? el.value : "";
  }

  function apply(reset) {
    if (reset) { page = 1; }
    var type = value("f-type"), genre = value("f-genre");
    var year = value("f-year"), country = value("f-country"), sort = value("f-sort");
    var query = (value("search-q") || "").trim().toLowerCase();
    var list = items.filter(function (item) {
      if (type && item.type !== type) { return false; }
      if (genre && item.genres.indexOf(genre) === -1) { return false; }
      if (year && String(item.year) !== year) { return false; }
      if (country && item.countrySlug !== country) { return false; }
      if (query && item.name.toLowerCase().indexOf(query) === -1) { return false; }
      return true;
    });
    list.sort(function (a, b) {
      if (sort === "name") { return a.name.localeCompare(b.name, "ru"); }
      if (sort === "old") { return a.year - b.year || a.name.localeCompare(b.name, "ru"); }
      if (sort === "long") { return b.runtime - a.runtime; }
      return b.year - a.year || a.name.localeCompare(b.name, "ru");
    });

    var counter = document.getElementById("search-count");
    if (counter) {
      counter.textContent = query
        ? "Найдено записей: " + list.length + "."
        : "Введите название: поиск идёт по " + items.length + " записям тестового каталога.";
    }
    if (query === "" && counter) { grid.innerHTML = ""; return; }

    var total = Math.max(1, Math.ceil(list.length / PER_PAGE));
    if (page > total) { page = total; }
    var slice = list.slice((page - 1) * PER_PAGE, page * PER_PAGE);
    grid.innerHTML = slice.length
      ? slice.map(card).join("")
      : '<p class="empty">По выбранным условиям в тестовом каталоге ничего нет.</p>';
    grid.setAttribute("data-total", String(list.length));
    grid.setAttribute("data-page", String(page));
    renderPager(total);
  }

  function renderPager(total) {
    var pager = document.querySelector(".pagination");
    if (!pager) { return; }
    if (total <= 1) { pager.innerHTML = ""; return; }
    var html = "<ul>";
    for (var n = 1; n <= total; n += 1) {
      html += n === page
        ? '<li><span aria-current="page">' + n + "</span></li>"
        : '<li><a href="#grid" data-page="' + n + '">' + n + "</a></li>";
    }
    pager.innerHTML = html + "</ul>";
  }

  document.addEventListener("change", function (event) {
    if (event.target.closest && event.target.closest("#facets")) { apply(true); }
  });
  document.addEventListener("reset", function (event) {
    if (event.target.id === "facets") { window.setTimeout(function () { apply(true); }, 0); }
  });
  document.addEventListener("click", function (event) {
    var link = event.target.closest && event.target.closest(".pagination a[data-page]");
    if (!link) { return; }
    event.preventDefault();
    page = parseInt(link.getAttribute("data-page"), 10) || 1;
    apply(false);
  });

  var search = document.getElementById("search-q");
  if (search) {
    var params = new URLSearchParams(window.location.search);
    var q = params.get("q");
    if (q) { search.value = q; }
    search.addEventListener("input", function () { apply(true); });
    var form = search.closest("form");
    if (form) { form.addEventListener("submit", function (e) { e.preventDefault(); apply(true); }); }
    apply(true);
  }
})();
"""


# ---------------------------------------------------------------------------
# Сборка сайта
# ---------------------------------------------------------------------------
def _index_page(ctx, *, path, section, pairs, trail_label, indexable) -> Page:
    """Индекс фасета: набор значений, за каждым из которых стоят произведения."""
    text = ctx["texts"].get(section) or {}
    title = text.get("title") or SECTION_LABELS.get(section, section)
    h1 = text.get("h1") or title
    lede = f'<p class="lede">{escape(text.get("intro", ""))}</p>' if text.get("intro") else ""
    body = (
        f"<h1>{escape(h1)}</h1>{lede}"
        f'<p class="count">Значений с непустым списком: {len(pairs)}.</p>'
        + _chips(pairs)
    )
    meta = Meta(
        title=title,
        description=text.get("description", f"{title} каталога."),
        h1=h1, page_type="category", indexable=indexable,
        breadcrumbs=(("Главная", "/"), (trail_label, "")),
    )
    return _page(ctx, path, meta, body)


def _collections_index(ctx, catalog: fx.Catalog, indexable: bool) -> Page:
    text = ctx["texts"].get("collections_index") or {}
    title = text.get("title") or SECTION_LABELS["collections_index"]
    cards = "".join(
        '<article class="card"><div class="card__body">'
        f'<a class="card__title" href="{escape(col.path)}">{escape(col.name)}</a>'
        f'<span class="card__meta">{len(col.title_slugs)} записей</span>'
        f'<span class="card__meta">{escape(col.summary)}</span></div></article>'
        for col in catalog.collections
    )
    body = (
        f'<h1>{escape(text.get("h1") or title)}</h1>'
        f'<p class="lede">{escape(text.get("intro", ""))}</p>'
        f'<p class="count">Подборок: {len(catalog.collections)}.</p>'
        f'<div class="grid">{cards}</div>'
    )
    meta = Meta(
        title=title, description=text.get("description", ""), h1=text.get("h1") or title,
        page_type="collection", indexable=indexable,
        breadcrumbs=(("Главная", "/"), (title, "")),
    )
    return _page(ctx, "/collections/", meta, body)


def _schedule_page(ctx, catalog: fx.Catalog, kinds, indexable: bool) -> Page:
    text = ctx["texts"].get("schedule") or {}
    title = text.get("title") or SECTION_LABELS["schedule"]
    body = (
        f'<h1>{escape(text.get("h1") or title)}</h1>'
        f'<p class="lede">{escape(text.get("intro", ""))}</p>'
        + (_calendar(catalog, kinds) or '<p class="empty">Многосерийных записей нет.</p>')
    )
    meta = Meta(
        title=title, description=text.get("description", ""), h1=text.get("h1") or title,
        page_type="category", indexable=indexable,
        breadcrumbs=(("Главная", "/"), (title, "")),
    )
    return _page(ctx, "/schedule/", meta, body)


def _context(package: dict, profile: dict, site_plan, player_state) -> dict:
    layout = theme_mod.layout_of(profile)
    brand = str(profile.get("label") or package.get("site_id"))
    domain = str(package.get("domain") or "").strip()
    nav = [
        (page.section, page.path)
        for page in site_plan.pages
        if page.in_menu and page.section != "home"
    ]
    return {
        "site_id": str(package.get("site_id", "")),
        "profile": site_plan.profile,
        "brand": brand,
        "mark": "".join(word[0] for word in brand.split()[:2]).upper() or "L",
        "language": str(package.get("language") or "ru"),
        "domain": domain,
        "indexing_enabled": bool(package.get("seo_indexing_enabled", False)),
        "canonical_base": f"https://{domain}" if domain else "",
        "canonical_state": CANONICAL_SELF if domain else CANONICAL_ABSENT,
        "nav": [("home", "/")] + nav,
        "per_page": int(((package.get("seo") or {}).get("items_per_page")) or 24),
        "home_items": 12,
        "row_items": 6,
        "facet_position": str(layout.get("facet_position")),
        "hero": str(layout.get("hero")),
        "home_blocks": list(layout.get("home_blocks") or []),
        "show_calendar": bool(layout.get("show_calendar")),
        "show_collection_cards": bool(layout.get("show_collection_cards")),
        "texts": profile.get("sections") or {},
        "title_page": profile.get("title_page") or {
            "title_template": "{name}", "h1_template": "{name}",
            "description_template": "{name}", "intro": "",
        },
        "catalog_path": "/catalog/",
        "type_paths": {
            fx.MOVIES: "/movies/", fx.SERIES: "/series/", fx.ANIMATION: "/animation/",
            fx.ANIME: "/anime/", fx.DORAMA: "/dorama/",
        },
        "player_state": player_state,
        "comments_enabled": bool((package.get("comments") or {}).get("enabled")),
    }


def render_site(
    package: dict,
    *,
    catalog: fx.Catalog | None = None,
    root: Path | None = None,
    environ: dict | None = None,
) -> RenderedSite:
    """Полный сайт одного пакета: страницы, ассеты и отчёт о сборке.

    `catalog=None` — это не «пустой сайт», а отсутствие источника данных: в этом
    случае все типы находятся в состоянии `blocked_credentials`, разделов не
    возникает, и рендерер честно отдаёт сайт без каталога вместо витрины с
    выдуманным содержимым.
    """
    catalog = catalog if catalog is not None else fx.build_catalog()
    profiles = plan_mod.load_profiles(root)
    site_plan = plan_mod.build_plan(
        package,
        credentials_available=True,
        api_capabilities=catalog.capabilities(),
        root=root,
    )
    profile = profiles[site_plan.profile]
    player_state = player_mod.state(environ)
    ctx = _context(package, profile, site_plan, player_state)

    kinds = [k for k in ct.active_types(site_plan.type_states) if k in TYPE_LABELS]
    collections_on = site_plan.type_states["collections"].active
    by_section = {page.section: page for page in site_plan.pages}
    pool = catalog.of_types(kinds)

    site = RenderedSite(site_id=ctx["site_id"], profile=site_plan.profile,
                        brand=ctx["brand"], plan=site_plan)

    def add(page: Page) -> None:
        site.pages[page.path] = page

    def texts_of(section: str) -> dict:
        return ctx["texts"].get(section) or {}

    def listing(section, *, base, titles, subset, trail_label, show_type=True):
        entry = by_section.get(section)
        if entry is None:
            return
        text = texts_of(section)
        title = text.get("title") or SECTION_LABELS.get(section, section)
        for page in _listing_pages(
            ctx, base=base, titles=titles, catalog=catalog, kinds=subset,
            section_title=title, h1=text.get("h1") or title,
            description=text.get("description", f"{title} каталога."),
            intro=text.get("intro", ""), indexable=entry.indexable,
            trail=(("Главная", "/"), (trail_label, "")), show_type=show_type,
        ):
            add(page)

    # Главная
    add(_home(ctx, catalog, kinds, by_section.get("home")))

    # Каталог и разделы по типам
    listing("catalog_index", base="/catalog/", titles=pool, subset=kinds,
            trail_label=texts_of("catalog_index").get("title") or "Каталог")
    for section, kind in SECTION_TYPE.items():
        if kind not in kinds:
            continue
        listing(section, base=ctx["type_paths"][kind], titles=catalog.of_type(kind),
                subset=[kind], show_type=False,
                trail_label=texts_of(section).get("title") or SECTION_LABELS[section])

    # Новое
    listing("new_index", base="/new/", titles=pool, subset=kinds,
            trail_label=texts_of("new_index").get("title") or "Новое")

    # Расписание
    if "schedule" in by_section:
        add(_schedule_page(ctx, catalog, kinds, by_section["schedule"].indexable))

    # Фасеты: индексы и посадочные страницы
    facet_specs = (
        ("genres_index", "/genres/", "Жанры",
         [(label, f"/genres/{slug}/", count) for slug, label, count in catalog.genres(kinds)]),
        ("years_index", "/years/", "Годы выпуска",
         [(str(year), f"/years/{year}/", count) for year, count in catalog.years(kinds)]),
        ("countries_index", "/countries/", "Страны",
         [(label, f"/countries/{slug}/", count)
          for slug, label, count in catalog.countries(kinds)]),
    )
    for section, path, fallback, pairs in facet_specs:
        entry = by_section.get(section)
        if entry is None:
            continue
        add(_index_page(ctx, path=path, section=section, pairs=pairs,
                        trail_label=texts_of(section).get("title") or fallback,
                        indexable=entry.indexable))

    if "genres_index" in by_section:
        entry = by_section["genres_index"]
        for slug, label, _count in catalog.genres(kinds):
            picks = [t for t in pool if slug in t.genre_slugs]
            for page in _listing_pages(
                ctx, base=f"/genres/{slug}/", titles=picks, catalog=catalog, kinds=kinds,
                section_title=f"{label}", h1=f"Жанр: {label}",
                description=f"Произведения жанра «{label}» в тестовом каталоге.",
                intro="", indexable=entry.indexable,
                trail=(("Главная", "/"), ("Жанры", "/genres/"), (label, "")),
            ):
                add(page)

    if "years_index" in by_section:
        entry = by_section["years_index"]
        for year, _count in catalog.years(kinds):
            picks = [t for t in pool if t.year == year]
            for page in _listing_pages(
                ctx, base=f"/years/{year}/", titles=picks, catalog=catalog, kinds=kinds,
                section_title=f"{year} год", h1=f"Год выпуска: {year}",
                description=f"Произведения {year} года в тестовом каталоге.",
                intro="", indexable=entry.indexable,
                trail=(("Главная", "/"), ("Годы выпуска", "/years/"), (str(year), "")),
            ):
                add(page)

    if "countries_index" in by_section:
        entry = by_section["countries_index"]
        for slug, label, _count in catalog.countries(kinds):
            picks = [t for t in pool if t.country_slug == slug]
            for page in _listing_pages(
                ctx, base=f"/countries/{slug}/", titles=picks, catalog=catalog, kinds=kinds,
                section_title=label, h1=f"Страна производства: {label}",
                description=f"Произведения страны «{label}» в тестовом каталоге.",
                intro="", indexable=entry.indexable,
                trail=(("Главная", "/"), ("Страны", "/countries/"), (label, "")),
            ):
                add(page)

    # Подборки
    if collections_on and "collections_index" in by_section:
        entry = by_section["collections_index"]
        add(_collections_index(ctx, catalog, entry.indexable))
        for col in catalog.collections:
            picks = [t for t in (catalog.by_slug(s) for s in col.title_slugs)
                     if t is not None and t.content_type in kinds]
            for page in _listing_pages(
                ctx, base=col.path, titles=picks, catalog=catalog, kinds=kinds,
                section_title=col.name, h1=col.name, description=col.summary,
                intro=col.summary, indexable=entry.indexable,
                trail=(("Главная", "/"), ("Подборки", "/collections/"), (col.name, "")),
            ):
                add(page)

    # Страницы произведений
    owns_titles = bool(profile.get("owns_title_page"))
    for title in pool:
        add(_title_page(ctx, catalog, title, kinds, indexable=owns_titles))

    # Поиск и служебные документы
    if "search" in by_section:
        add(_search_page(ctx, catalog, kinds))
    indexable_paths = sorted(p for p, page in site.pages.items() if page.indexable)
    add(_robots(ctx))
    add(_sitemap(ctx, indexable_paths))
    site.not_found = _not_found(ctx)

    # Ассеты
    add(Page(path="/assets/site.css", body=theme_mod.stylesheet(profile),
             content_type="text/css; charset=utf-8"))
    add(Page(path="/assets/app.js", body=APP_JS,
             content_type="text/javascript; charset=utf-8"))
    for title in pool:
        add(Page(path=title.poster_path, body=poster_svg(title),
                 content_type="image/svg+xml; charset=utf-8"))

    site.report = {
        "site_id": ctx["site_id"],
        "profile": site_plan.profile,
        "brand": ctx["brand"],
        "data_source": fx.SOURCE,
        "pages": len(site.html_paths()),
        "assets": len(site.pages) - len(site.html_paths()),
        "indexable_pages": len(indexable_paths),
        "sitemap_urls": len(indexable_paths) if (ctx["domain"] and ctx["indexing_enabled"]) else 0,
        "canonical_state": ctx["canonical_state"],
        "canonical_base": ctx["canonical_base"],
        "robots": "Disallow: /" if not (ctx["domain"] and ctx["indexing_enabled"]) else "Allow",
        "content_types": {n: s.as_dict() for n, s in site_plan.type_states.items()},
        "active_types": kinds + (["collections"] if collections_on else []),
        "player": player_mod.contract_check(player_state),
        "blocked_inputs": _blocked_inputs(package, site_plan, player_state),
    }
    return site


def _blocked_inputs(package: dict, site_plan, player_state) -> list:
    """Что действительно перекрыто отсутствующими входными данными."""
    out = []
    if not package.get("domain"):
        out.append({"code": "BLOCKED_INPUT_DOMAIN",
                    "blocks": ["canonical", "sitemap", "indexing", "TLS", "Метрика", "Вебмастер"]})
    if not package.get("target_ref"):
        out.append({"code": "BLOCKED_INPUT_TARGET", "blocks": ["deploy", "rollback"]})
    if player_state.placeholder:
        out.append({"code": player_state.status,
                    "blocks": ["плеер", "проверка контракта плеера"]})
    blocked = sorted(
        name for name, state in site_plan.type_states.items()
        if state.state == ct.BLOCKED_CREDENTIALS
    )
    if blocked:
        out.append({"code": "BLOCKED_INPUT_CDNVIDEOHUB_CREDENTIALS",
                    "blocks": [f"тип контента {name}" for name in blocked]})
    return out
