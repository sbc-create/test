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

import datetime as _dt
import html
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

from factory.analytics import client_codegen as analytics_codegen
from factory.analytics import snippet as analytics_snippet
from factory.lords import content_types as ct
from factory.lords import fixtures as fx
from factory.lords import icons
from factory.lords import pagination as pagination_mod
from factory.lords import plan as plan_mod
from factory.lords import player as player_mod
from factory.lords import recommend as recommend_mod
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

#: Тип контента → заголовок раздела на главной.
#:
#: В карточке и в фактах тип называется в единственном числе — там он описывает
#: одну запись. Заголовок раздела называет набор, и «Фильм» над рядом из
#: двенадцати фильмов читается как технический ярлык, а не как название полки.
TYPE_SECTION_LABELS = {
    fx.MOVIES: "Фильмы",
    fx.SERIES: "Сериалы",
    fx.ANIMATION: "Мультфильмы",
    fx.ANIME: "Аниме",
    fx.DORAMA: "Дорамы",
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
    #: Двоичное тело для документов, которые не являются текстом (иконка).
    #: Когда оно задано, на диск и в ответ идёт именно оно, а `body` остаётся
    #: человекочитаемым описанием — по нему видно, что за файл, в отчётах.
    raw: bytes | None = None

    @property
    def payload(self) -> bytes:
        return self.raw if self.raw is not None else self.body.encode("utf-8")


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
    # Счётчик встраивается ровно здесь и только через snippet.analytics_script_tag:
    # тот возвращает пустую строку, если сбор невозможен (нет counter_id, аналитика
    # выключена, окружение не production, пуст allowed_hosts). Пустая строка означает
    # «тега нет», а не «тег есть, но молчит», поэтому отсутствие настройки не может
    # превратиться в счётчик соседнего домена.
    analytics_script = ctx.get("analytics_script") or ""
    if analytics_script:
        head.append(analytics_script)
    head.append('<link rel="stylesheet" href="/assets/site.css">')
    # Раньше здесь стоял серый прямоугольник в data-URI: заглушка, которая
    # занимала место иконки и потому выглядела как решение. Настоящие файлы
    # рисуются из токенов темы и лежат в корне сайта.
    head.append('<link rel="icon" href="/favicon.ico" sizes="32x32">')
    head.append('<link rel="icon" href="/favicon.svg" type="image/svg+xml">')
    head.append('<link rel="manifest" href="/manifest.webmanifest">')
    head.append(f'<meta name="theme-color" content="{escape(ctx["tokens"]["accent"])}">')

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
        # Полоса про тестовый стенд принадлежит стенду. На живом каталоге она
        # сообщала посетителю, что названия и постеры выдуманы, — под настоящими
        # записями провайдера. Витрина от этого выглядела незаконченной ровно там,
        # где она уже была готова.
        + ('<div class="preview-banner"><p><strong>Тестовый стенд.</strong> '
           "Каталог синтетический (fixture/test), названия и постеры выдуманы, "
           "индексация закрыта.</p></div>" if ctx.get("fixture_catalog") else "")
        +
        '<header class="site-header"><div class="header-row">'
        f'<a class="brand" href="/"><span class="brand__mark">{mark}</span>'
        # Рядом с именем сайта стоял его внутренний идентификатор —
        # `lords-01`. Посетителю он ничего не сообщает, а страницу
        # заставляет выглядеть служебной сборкой.
        f'<span class="brand__name">{escape(ctx["brand"])}</span></a>'
        '<button class="nav-toggle" type="button" aria-expanded="false" '
        'aria-controls="site-nav">Меню</button>'
        '<nav class="site-nav" id="site-nav" aria-label="Основная навигация"><ul>'
        + _nav_items(ctx["nav"], ctx.get("_path", ""))
        + "</ul></nav>"
        + _header_search(ctx)
        + "</div></header>"
    )


def _header_search(ctx: dict) -> str:
    """Форма поиска в шапке — кроме главной, где она уже стоит в первом экране.

    Измерено 2026-09-02 на живом lordfilm47.space: две видимые формы поиска на
    всех трёх ширинах, обе с action=/search/ и классом header-search. Соседние
    витрины того же семейства показывали одну — расхождение шло от профиля:
    `lords-general` держит `hero_search` в `home_blocks`, а форма в шапке
    рисовалась безусловно.

    Убирается именно вторая по счёту, а не первая попавшаяся: форма в первом
    экране заметнее и стоит там намеренно, форма в шапке есть на всех
    остальных страницах и никуда не девается.
    """
    if "hero_search" in (ctx.get("home_blocks") or ()) and ctx.get("_path", "/") == "/":
        return ""
    return (
        '<form class="header-search" role="search" action="/search/" method="get">'
        '<label class="visually-hidden" for="q">Поиск по каталогу</label>'
        '<input id="q" name="q" type="search" placeholder="Название из каталога" '
        'autocomplete="off">'
        "<button type=\"submit\">Найти</button></form>"
    )


#: Контактный адрес всех витрин. Подтверждён владельцем.
#: Используется только как адрес для связи: правообладателем владелец его не
#: называл, и подставлять его туда нельзя.
CONTACT_EMAIL = "sbc.claude@yandex.ru"

#: Чем каждая витрина отличается от соседних. Текст пишется для читателя, а не
#: для поисковой системы: одинаковый подвал на шести сайтах не сообщает ничего
#: ни человеку, ни роботу, а перестановка синонимов — тем более.
SITE_BLURBS: dict[str, str] = {
    "lordfilm47.space":
        "Общая витрина: фильмы и сериалы в одном каталоге. Подборки собраны по "
        "жанрам, годам и странам, чтобы можно было начать с чего угодно — с "
        "конкретного названия, с настроения или просто с года выпуска.",
    "lordserial33.biz":
        "Витрина сериалов: сезоны, серии и даты выхода. У каждого сериала видно, "
        "сколько серий уже доступно и сколько заявлено, а разделы построены так, "
        "чтобы вернуться к начатому и не искать номер серии заново.",
    "1lordserials1.online":
        "Витрина подборок: что посмотреть, когда конкретного названия в голове "
        "нет. Разделы собраны вокруг выбора — по жанру, по году, по стране, — а "
        "не вокруг алфавита.",
}

DEFAULT_BLURB = (
    "Каталог фильмов и сериалов с поиском по жанрам, годам и странам."
)


def _footer(ctx: dict) -> str:
    links = "".join(
        f'<li><a href="{escape(path)}">{escape(SECTION_LABELS.get(section, section))}</a></li>'
        for section, path in ctx["nav"]
    )
    domain = str(ctx.get("domain") or "")
    blurb = SITE_BLURBS.get(domain, DEFAULT_BLURB)
    year = _dt.date.today().year
    contact = escape(CONTACT_EMAIL)
    return (
        '<footer class="site-footer"><div class="container">'
        f"<ul>{links}</ul>"
        # Идентификатор сайта и имя профиля сборки — внутренняя
        # классификация фабрики; в подвале публичного сайта им не место.
        f"<p>{escape(ctx['brand'])}</p>"
        f"<p>{escape(blurb)}</p>"
        + ("<p>Каталог демонстрационный: перечисленные в нём произведения не "
           "существуют, оценок и сведений о правообладателях он не содержит и в "
           "поисковые системы не отдаётся.</p>"
           if ctx.get("fixture_catalog") else
           "<p>Каталог формируется из данных CDNVideoHub. Сайт не хранит "
           "видеофайлы и не является их источником.</p>")
        + f'<p>Связаться: <a href="mailto:{contact}">{contact}</a></p>'
        # Правообладатель и юридические документы владельцем не заданы. Пустое
        # место здесь честнее выдуманных реквизитов.
        f"<p>© {year} {escape(ctx['brand'])}</p>"
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
    # Источник списка не отдаёт страну, а год бывает неизвестен. Склейка через
    # разделитель без проверки давала «Фильм · 2003 · » и «Фильм ·  · » —
    # разделитель повисал там, где значения просто нет.
    meta = " · ".join(
        str(part) for part in (
            TYPE_LABELS.get(title.content_type, title.content_type),
            title.year or "",
            title.country,
        ) if part
    )
    # Подпись говорит, откуда карточка, а не повторяет слово «fixture» над
    # живыми данными: на публичных доменах это была прямая неправда.
    badge = '<span class="card__badge">каталог</span>' if title.fixture else ""
    return (
        f'<article class="card" data-slug="{escape(title.slug)}">'
        f'<a class="card__poster" href="{escape(title.path)}" tabindex="-1" aria-hidden="true">'
        f'<img src="{escape(title.poster_src)}" alt="" loading="lazy" width="400" height="600">'
        f"{badge}"
        f"{_card_rating(title)}"
        f"{seasons}</a>"
        '<div class="card__body">'
        f'<a class="card__title" href="{escape(title.path)}">{escape(title.name)}</a>'
        f'<span class="card__meta">{escape(meta)}</span>'
        f'<span class="card__meta">{escape(", ".join(title.genres))}</span>'
        "</div></article>"
    )



def _card_rating(title) -> str:
    """Оценка на карточке: одно число с подписью источника.

    Разметка оценок на странице произведения существовала давно, но ни одного
    правила оформления для неё не было: в таблице стилей слово «rating» не
    встречалось ни разу. Подписи и число шли подряд без промежутка и терялись
    среди прочего текста — владелец справедливо считал, что оценок нет.

    На карточке показывается одна оценка, а не обе: две мелкие подписи под
    обложкой спорят друг с другом. Кинопоиск идёт первым как более знакомый
    здешнему зрителю; если его нет — IMDb.
    """
    for label, raw in (("Кинопоиск", getattr(title, "kinopoisk_rating", None)),
                       ("IMDb", getattr(title, "imdb_rating", None))):
        value = _format_rating(raw)
        if value is not None:
            return (
                f'<span class="card__rating" title="{escape(label)}">'
                f'<span class="card__rating-source">{escape(label)}</span>'
                f'<span class="card__rating-value">{escape(value)}</span>'
                "</span>"
            )
    return ""



def _carousel_card(scored, position: int, shelf_id: str) -> str:
    """Одна карточка карусели.

    Показывается то, что подтверждено источником: название, год, тип, жанр и
    оценка с подписью. Ничего из этого не додумывается — отсутствующее поле
    просто не рисуется, а не заменяется прочерком или нулём.
    """
    item = scored.item
    if not item.path:
        return ""
    meta = " · ".join(str(part) for part in (
        TYPE_LABELS.get(item.content_type, item.content_type),
        item.release_date.year if item.release_date else "",
        item.genres[0] if item.genres else "",
    ) if part)
    rating = ""
    for label, value in (("Кинопоиск", item.kp_rating), ("IMDb", item.imdb_rating)):
        shown = _format_rating(value)
        if shown is not None:
            rating = (f'<span class="rail__rating"><span class="rail__rating-source">'
                      f'{escape(label)}</span><span class="rail__rating-value">'
                      f'{escape(shown)}</span></span>')
            break
    # Адрес берётся у записи каталога. Собирать его из идентификатора нельзя:
    # идентификатор — это UUID поставщика, страницы по такому адресу нет, и
    # каждая карточка карусели вела в 404. Приёмка выкладки это и поймала.
    path = item.path
    return (
        f'<li class="rail__item" role="listitem">'
        f'<a class="rail__link" href="{escape(path)}"'
        f' data-shelf="{escape(shelf_id)}" data-position="{position}"'
        f' data-content-id="{escape(item.content_id)}">'
        f'<span class="rail__poster">'
        f'<img src="{escape(item.poster or "")}" alt="" loading="lazy" decoding="async"'
        f' width="400" height="600">{rating}</span>'
        f'<span class="rail__title">{escape(item.title)}</span>'
        f'<span class="rail__meta">{escape(meta)}</span>'
        "</a></li>"
    )


def _carousel(ctx, shelf, heading: str) -> str:
    """Верхняя карусель.

    Полка приходит от ранжировщика, а не собирается здесь руками: правила
    допуска, разнообразия и порядка живут в одном месте и одинаковы для всех
    доменов.

    Разметка — список внутри горизонтально прокручиваемой области. Стрелки
    добавляются только как удобство: прокрутка работает колесом, свайпом и
    клавиатурой и без них, поэтому отключённый JavaScript ничего не ломает.
    """
    if shelf is None or len(shelf) < 4:
        return ""
    cards = "".join(_carousel_card(s, i + 1, shelf.shelf_id)
                    for i, s in enumerate(shelf.items))
    return (
        '<section class="section section--rail" aria-labelledby="rail-heading"'
        f' data-shelf="{escape(shelf.shelf_id)}"'
        f' data-algorithm="{escape(shelf.algorithm_version)}">'
        '<div class="section__head">'
        f'<h2 id="rail-heading">{escape(heading)}</h2>'
        '<div class="rail__nav">'
        '<button class="rail__arrow" type="button" data-rail-prev'
        ' aria-label="Предыдущие">‹</button>'
        '<button class="rail__arrow" type="button" data-rail-next'
        ' aria-label="Следующие">›</button>'
        "</div></div>"
        '<ul class="rail" role="list" tabindex="0" aria-label="Подборка">'
        + cards + "</ul></section>"
    )


def _grid(titles) -> str:
    if not titles:
        return (
            '<p class="empty">По выбранным условиям в каталоге ничего нет. '
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


def _facets(catalog: fx.Catalog, kinds, *, show_type: bool, row: bool = False,
            with_counts: bool = True) -> str:
    """Панель фильтров и сортировки. Работает поверх встроенного набора данных.

    `row` включает раскладку в строку — она нужна там, где фасеты стоят над
    списком: пять полей в колонку отодвигают первую карточку за сгиб, и раздел
    выглядит пустым, хотя в нём полсотни записей.

    `with_counts=False` убирает числа из подписей фильтров. Числа считаются по
    всему разделу, поэтому одна добавленная запись меняла подпись `2026 (1842)`
    на `2026 (1843)` — и меняла её на **каждой** странице раздела. Измерено
    2026-09-03: после перехода на разбиение по годам одна запись всё равно
    перерисовывала 9266 страниц из 9717, и дифф показал, что расходятся ровно
    эти счётчики. Числа остаются там, где они полезны и где страница и так
    меняется от любой правки, — на первой странице раздела.
    """
    types = [(k, TYPE_LABELS[k]) for k in kinds if catalog.of_type(k)]
    подпись = (lambda label, count: f"{label} ({count})") if with_counts else (
        lambda label, count: str(label))
    genres = [(slug, подпись(label, count)) for slug, label, count in catalog.genres(kinds)]
    years = [(str(y), подпись(y, c)) for y, c in catalog.years(kinds)]
    countries = [(slug, подпись(label, count)) for slug, label, count in catalog.countries(kinds)]

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


#: Выше этого размера полный набор в разметку не встраивается.
#: Причина в цене: на стенде в 62 тайтла набор стоил килобайты, на живом
#: каталоге в 4800 — полтора мегабайта на КАЖДОЙ странице списка, при том что
#: карточек на ней по-прежнему 24. Страница списка начинала весить как весь
#: каталог, и первым это замечал посетитель с телефона.
#: Фильтрация при этом не пропадает: фасеты жанров, годов и стран — обычные
#: ссылки на серверные разделы, а клиентский сценарий сам отступает, когда
#: `#listing-data` в разметке нет.
DATASET_MAX_TITLES = 200


def _dataset(titles) -> str:
    """Набор списка для клиентской фильтрации — пока он того стоит.

    Пагинация на сервере отдаёт одну страницу, и фильтровать её содержимое было
    бы обманом: пользователь увидел бы «ничего не найдено» там, где запись есть
    на третьей странице. Поэтому список фильтруется по полному набору — но
    только пока этот набор дёшево отдать целиком. Дальше фильтрация переходит
    к серверным разделам, а не превращается в мегабайт на каждой странице.
    """
    if len(titles) > DATASET_MAX_TITLES:
        return ""
    payload = [
        {
            "slug": t.slug, "name": t.name, "type": t.content_type,
            "typeLabel": TYPE_LABELS.get(t.content_type, t.content_type),
            "year": t.year, "country": t.country, "countrySlug": t.country_slug,
            "genres": list(t.genre_slugs), "genreLabels": list(t.genres),
            "runtime": t.runtime_min, "episodes": t.episode_count,
            "path": t.path, "poster": t.poster_src,
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
    """Порядок витрины: сначала свежие годы. Для каталога это верный порядок."""
    return sorted(titles, key=lambda t: (-t.year, t.name, t.slug))


def _by_arrival(titles) -> list:
    """Порядок ленты поступлений: сначала то, что появилось у источника позже.

    Общий порядок каталога тут не подходит: он сортирует по году выпуска, и
    фильм 2026 года, добавленный полгода назад, всегда обгонял бы вчерашнее
    поступление 2019-го. Блок при этом называется «Последние добавления», и
    посетитель справедливо ждёт от него другого.

    Записи без отметки времени не всплывают наверх: отсутствие даты — это не
    «только что», а «источник не сказал».
    """
    return sorted(
        titles,
        key=lambda t: (getattr(t, "created_at", "") or "", -t.year, t.name, t.slug),
        reverse=True,
    )


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
    # Разбиение по блокам годов ограничивает правку одним годом: добавленная
    # запись 2026-го трогает 82 страницы вместо 2216. Договор и цена перехода —
    # adr/0007-pagination-by-year-blocks.md. Пока владелец не согласился на
    # однократную смену состава страниц, поведение прежнее.
    страницы = pagination_mod.разбить(
        items, per_page, по_годам=bool(ctx.get("pagination_by_year")))
    pages_count = len(страницы)
    out = []
    position = ctx["facet_position"]
    # Два варианта панели: с числами для первой страницы раздела и без чисел
    # для остальных. Числа считаются по всему разделу и потому связывают все
    # страницы между собой — с ними инкрементальная публикация невозможна.
    facets = (
        _facets(catalog, kinds, show_type=show_type, row=position != "sidebar")
        if (show_facets and items) else ""
    )
    facets_deep = (
        _facets(catalog, kinds, show_type=show_type, row=position != "sidebar",
                with_counts=False)
        if (show_facets and items) else ""
    )

    for number in range(1, pages_count + 1):
        chunk = страницы[number - 1]
        path = base if number == 1 else f"{base}page/{number}/"
        heading = h1 if number == 1 else f"{h1} — страница {number}"
        title = section_title if number == 1 else f"{section_title} — страница {number}"
        desc = description if number == 1 else f"{description} Страница {number}."
        lede = f'<p class="lede">{escape(intro)}</p>' if intro and number == 1 else ""
        grid = _grid(chunk) + _pagination(base, number, pages_count)
        # Общее число записей — та же связность: оно меняется от любой правки
        # каталога и стоит на каждой странице. Остаётся на первой, где читатель
        # его и ищет.
        счётчик = (f'<p class="count">Записей в разделе: {len(items)}.</p>'
                   if number == 1 else "")
        body_top = f'<h1>{escape(heading)}</h1>{lede}{счётчик}{extra_top}'
        панель = facets if number == 1 else facets_deep
        if not панель:
            inner = body_top + grid
        elif position == "sidebar":
            inner = body_top + f'<div class="listing">{панель}<div>{grid}</div></div>'
        else:  # top / hero / none — фасеты стоят над списком
            inner = body_top + панель + grid
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



def _is_watchable(title) -> bool:
    """Можно ли на этой записи что-то посмотреть.

    Прежде здесь проверялось наличие пары «агрегатор + идентификатор». Она есть
    у всех записей каталога, включая те, для которых поток ещё не завели, — то
    есть условие было истинным всегда, и отбор ничего не отбирал. На первый
    экран выходили самые свежие поступления, а у них потока чаще всего нет:
    посетитель открывал первые карточки подряд и не видел видео ни на одной.

    Теперь учитывается ответ источника. Подтверждённое «пусто» исключает
    запись с первого экрана; неизвестность — нет.
    """
    if not (getattr(title, "playback", None) or {}).get("title_id"):
        return False
    return getattr(title, "playable", None) is not False


def _watchable_first(titles, limit: int) -> list:
    """Лента поступлений, ведущая туда, где есть что смотреть.

    Порядок по времени поступления сам по себе даёт плохую витрину: у только
    что заведённых записей контракт воспроизведения чаще всего ещё не создан.
    Из двенадцати последних поступлений его имели четыре — посетитель кликал
    первые карточки и в двух случаях из трёх попадал на страницу без видео.
    Покрытие каталога при этом оставалось прежним, около 86%: средняя цифра
    скрывала то, что видел человек.

    Поэтому лента показывает последние поступления среди тех, что можно
    смотреть. Записи без видео из каталога никуда не деваются — у них есть
    страница, описание и место в разделах; они просто не занимают собой первый
    экран. Если смотреть нечего нигде, лента остаётся непустой: пустой блок
    хуже блока с записями без видео.
    """
    ordered = _by_arrival(titles)
    watchable = [t for t in ordered if _is_watchable(t)]
    if len(watchable) >= limit:
        return watchable[:limit]
    rest = [t for t in ordered if not _is_watchable(t)]
    return (watchable + rest)[:limit]


def _home(ctx, catalog: fx.Catalog, kinds, section) -> Page:
    text = ctx["texts"].get("home") or {}
    blocks = ctx["home_blocks"]
    pool = catalog.of_types(kinds)
    latest = _watchable_first(pool, ctx["home_items"])
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
        if block == "top_carousel":
            # Полка собирается ранжировщиком из записей каталога: правила
            # допуска и разнообразия живут в одном месте и одинаковы для всех
            # доменов. Вручную сюда ничего не подставляется.
            parts.append(_carousel(
                ctx,
                recommend_mod.carousel_shelf(
                    catalog.of_types(kinds), domain=ctx.get("domain") or None),
                ctx.get("carousel_heading") or "Новинки"))
        elif block == "latest_grid":
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
                    f"<h2>{escape(TYPE_SECTION_LABELS.get(kind, TYPE_LABELS[kind]))}</h2>{more}</div>"
                    + _grid(row) + "</section>"
                )
        elif block == "top_rated":
            parts.append(_top_rated(ctx, pool))
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
            # Оговорка про тестовый каталог верна только для стенда. На живом
            # каталоге она сообщала посетителю, что за записями не стоят
            # реальные произведения, — под настоящими записями провайдера.
            note = (
                "Подборки на стенде собраны по формальным признакам тестового "
                "каталога — длительности, числу сезонов, названию. Редакционного "
                "отбора здесь нет и быть не может: за записями не стоят реальные "
                "произведения."
                if ctx.get("fixture_catalog") else
                "Подборки собраны по формальным признакам каталога — году, типу, "
                "длительности и числу сезонов. Состав обновляется вместе с каталогом."
            )
            parts.append(
                '<section class="section"><h2>Как собран список</h2>'
                f'<p class="lede">{escape(note)}</p></section>'
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
        '<section class="section"><h2>Сезоны в каталоге</h2>'
        '<p class="lede">Здесь перечислены многосерийные записи и число серий в '
        "последнем сезоне. Дат выхода источник не сообщает, поэтому порядок "
        "показа не является календарём премьер.</p>"
        '<ol class="season">' + "".join(rows) + "</ol></section>"
    )



def _best_rating(title) -> float | None:
    """Наибольшая из подтверждённых оценок записи.

    Оценки нет — возвращается None, а не ноль: запись без оценки не должна
    занимать последнее место в рейтинге, ей там нечего делать.
    """
    values = [
        v for v in (getattr(title, "kinopoisk_rating", None),
                    getattr(title, "imdb_rating", None))
        if isinstance(v, int | float)
    ]
    return max(values) if values else None


def _top_rated(ctx, pool) -> str:
    """Полка «высокие оценки».

    Сортируется только по тому, что действительно пришло от источника. Записи
    без оценки в полку не попадают: подставить им среднее значило бы показать
    посетителю оценку, которой никто не ставил.
    """
    rated = [(t, _best_rating(t)) for t in pool]
    rated = [(t, r) for t, r in rated if r is not None]
    if len(rated) < 4:
        return ""
    rated.sort(key=lambda pair: (-pair[1], pair[0].name))
    row = [t for t, _ in rated[:ctx["row_items"]]]
    return (
        '<section class="section"><div class="section__head">'
        "<h2>Высокие оценки</h2></div>" + _grid(row) + "</section>"
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
            '<section class="seasons"><h2>О фильме</h2>'
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
        + ('<p class="comments__note">На стенде комментарии выключены: писать не о чем — '
           "запись синтетическая, а публиковать чужие тексты стенд не станет. "
           "Форма показана, чтобы блок занимал своё место в раскладке.</p>"
           if ctx.get("fixture_catalog") else
           '<p class="comments__note">Комментарии скоро откроются.</p>')
        +
        "<form><label class=\"visually-hidden\" for=\"comment\">Текст комментария</label>"
        '<textarea id="comment" disabled placeholder="Комментарии пока закрыты">'
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



def _player_block(ctx, title, name: str) -> str:
    """Плеер тайтла: настоящий там, где источник дал чем его адресовать.

    Источник сообщает пару «агрегатор + идентификатор тайтла» только для части
    каталога. Там, где она есть и Publisher ID известен, страница получает тот
    же `<video-player>`, что отдавал прежний сборщик. Там, где её нет, —
    нейтральное состояние: отсутствие видео у одного тайтла не повод объяснять
    посетителю устройство нашей сборки.
    """
    playback = getattr(title, "playback", None) or {}
    aggregator = str(playback.get("aggregator") or "").strip()
    title_id = str(playback.get("title_id") or "").strip()
    publisher_id = ctx.get("publisher_id")

    # Источник может подтвердить, что играть нечего: на запрос плейлиста он
    # отвечает «пусто». Ставить в этом случае кадр плеера — значит показывать
    # посетителю чёрный прямоугольник, который никогда не запустится.
    #
    # Условие намеренно проверяет именно False, а не ложность: `None` означает
    # «не проверяли», и такая запись плеер сохраняет. Ни один тайтл, который
    # играл, не может лишиться плеера из-за сетевой ошибки при проверке.
    confirmed_silent = getattr(title, "playable", None) is False

    if aggregator and title_id and publisher_id and not confirmed_silent:
        try:
            return player_mod.render_live(
                publisher_id=str(publisher_id),
                aggregator=aggregator,
                title_id=title_id,
                title_name=name,
                # Идентификатор элемента у каждого тайтла свой: общий склеил бы
                # два плеера на соседних страницах в один.
                ident=f"player-{title.slug}",
                season=1,
                episode=1,
            )
        except player_mod.PlayerContractError:
            # Контракт нарушен — это наша проблема, а не посетителя.
            pass
    return player_mod.render(
        player_mod.PlayerState(available=False, status="", message=""),
        title_name=name,
    )




#: Разумные границы шкалы оценок. Значение вне них — не оценка: чаще всего это
#: внешний идентификатор, случайно попавший в поле балла. Оба числа, и отличить
#: их можно только по величине.
RATING_MIN = 0.1
RATING_MAX = 10.0


def _format_rating(value) -> str | None:
    """Оценка в виде, понятном читателю, или ничего.

    По-русски дробная часть отделяется запятой. Точка здесь выглядит как
    машинный вывод, а три знака после неё — как техническая утечка: источник
    присылает `7.282`, читателю нужно `7,3`.
    """
    shown = _shown_rating(value)
    if shown is None or not (RATING_MIN <= shown <= RATING_MAX):
        return None
    return f"{shown:.1f}".replace(".", ",")


def _shown_rating(value) -> float | None:
    """Оценка, которую можно показать, или ничего.

    Ноль не показывается. Сейчас источник для отсутствующей оценки присылает
    `null` — нулей в каталоге нет ни одного, — но ноль в шкале «от одного до
    десяти» почти всегда означает «оценки нет», а не «оценили на ноль».
    Показать 0.0 с подписью «Кинопоиск» значило бы приписать источнику
    суждение, которого он не высказывал.
    """
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value) if value > 0 else None


def _ratings_block(title) -> str:
    """Оценки с подписью источника.

    Число без подписи ничего не значит: 7.8 у Кинопоиска и 7.8 у IMDb — разные
    утверждения разных источников. Отсутствующая оценка скрывается, а не
    показывается нулём: ноль здесь означал бы «оценили на ноль».
    """
    pairs = (
        # «КП» узнают не все; на странице произведения место есть, и источник
        # называется полностью.
        ("Кинопоиск", getattr(title, "kinopoisk_rating", None)),
        ("IMDb", getattr(title, "imdb_rating", None)),
    )
    shown = [
        f'<li class="rating"><span class="rating__source">{escape(label)}</span>'
        f'<span class="rating__value">{escape(text)}</span></li>'
        for label, text in (
            (label, _format_rating(value)) for label, value in pairs)
        if text is not None
    ]
    if not shown:
        return ""
    return '<ul class="ratings">' + "".join(shown) + "</ul>"



#: Рекомендуемая длина описания в выдаче: короче обрывается смысл, длиннее —
#: обрезает поисковик.
DESCRIPTION_TARGET_MIN = 70
# Запас против экранирования: кавычки-ёлочки и амперсанд в атрибуте
# разрастаются, и обрезка ровно по 180 давала на выходе до 198 знаков.
DESCRIPTION_TARGET_MAX = 168


def _trim_at_word(text: str, limit: int) -> str:
    """Обрезка по границе слова, без многоточия посреди слова."""
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(" ,;:—-")
    return cut + "…"


def _title_description(title, template: str) -> str:
    """Описание страницы произведения из подтверждённых сведений.

    Шаблон подставлял одно название и на коротком названии давал полсотни
    знаков — в выдаче это выглядит обрывком. Ничего не выдумывая, описание
    можно собрать из того, что источник уже сообщил.

    Сначала берётся синопсис поставщика: он уникален, правдив и отвечает на
    вопрос «про что это». Если синопсиса нет, собирается справка из полей —
    тип, год, страна, жанры, — и она честно остаётся справкой, а не
    притворяется пересказом сюжета. Пустые поля просто не упоминаются.
    """
    name = title.name
    summary = " ".join((getattr(title, "summary", "") or "").split())
    if len(summary) >= DESCRIPTION_TARGET_MIN:
        return _trim_at_word(summary, DESCRIPTION_TARGET_MAX)

    facts = []
    kind = TYPE_LABELS.get(title.content_type)
    if kind:
        facts.append(kind.lower())
    if getattr(title, "year", None):
        facts.append(f"{title.year} года")
    if getattr(title, "country", None):
        facts.append(str(title.country))
    genres = [g for g in (getattr(title, "genres", ()) or ()) if g][:3]

    parts = [f"{name} — " + " ".join(facts) if facts else name]
    if genres:
        parts.append("жанр: " + ", ".join(genres))
    base = str(template or "{name}").format(name=name)
    tail = base.split(":", 1)[1].strip() if ":" in base else ""
    if tail:
        parts.append(tail.rstrip("."))
    if summary:
        parts.append(summary)
    text = ". ".join(part for part in parts if part).strip()
    if not text.endswith("."):
        text += "."
    return _trim_at_word(text, DESCRIPTION_TARGET_MAX)



def _human_date(value) -> str:
    """Дата в привычном виде: 21.11.2024.

    Источник отдаёт ISO-8601, и он же попадал на страницу: «2024-11-21» читается
    как запись из журнала, а не как дата выхода. Если известен только год, год и
    остаётся — придумывать день и месяц нельзя.
    """
    text = str(value or "").strip()
    if not text:
        return ""
    head = text.split("T", 1)[0]
    parts = head.split("-")
    if len(parts) == 3 and all(p.isdigit() for p in parts):
        year, month, day = parts
        return f"{int(day):02d}.{int(month):02d}.{year}"
    if len(parts) == 1 and parts[0].isdigit() and len(parts[0]) == 4:
        return parts[0]
    return text


def _title_page(ctx, catalog: fx.Catalog, title: fx.Title, kinds, indexable: bool) -> Page:
    tpl = ctx["title_page"]
    name = title.name
    page_title = str(tpl.get("title_template", "{name}")).format(name=name)
    description = _title_description(title, str(tpl.get("description_template", "{name}")))
    h1 = str(tpl.get("h1_template", "{name}")).format(name=name)

    # Длительность в ноль минут — это не длительность, а её отсутствие: списочный
    # ответ источника хронометража не даёт вовсе.
    duration = ""
    if title.runtime_min:
        duration = f"{title.runtime_min} мин"
    if title.episodic:
        duration = (duration + " · " if duration else "") + f"серий {title.episode_count}"

    def _join(values) -> str:
        """Список имён в строку. Длинный состав режется: страница не афиша."""
        names = [str(v).strip() for v in (values or []) if str(v).strip()]
        if len(names) > 8:
            return ", ".join(names[:8]) + f" и ещё {len(names) - 8}"
        return ", ".join(names)

    facts = [
        ("Оригинальное название", title.original_name),
        ("Тип", TYPE_LABELS.get(title.content_type, title.content_type)),
        ("Год", str(title.year) if title.year else ""),
        ("Дата выхода", _human_date(getattr(title, "premiere_date", ""))),
        ("Страна", title.country),
        ("Режиссёр", _join(getattr(title, "directors", ()))),
        ("В ролях", _join(getattr(title, "actors", ()))),
        ("Озвучки", _join(getattr(title, "voices", ()))),
        ("Сезонов", str(getattr(title, "seasons_count", 0) or "") ),
        # У фикстуры это настоящие жанры. У живого каталога — теги источника:
        # они описывают запись, но жанрами не являются, и называть их жанрами
        # значило бы написать на странице фильма «Жанры: NR».
        ("Жанры" if title.fixture else "Теги", ", ".join(title.genres)),
        ("Студия", title.studio),
        ("Возрастная отметка", title.age_rating),
        ("Длительность", duration),
    ]
    # Пустая строка — это «источник не сказал». Заголовок без значения выглядит
    # как потерянные данные, поэтому такие пары не печатаются вовсе.
    facts_html = "".join(
        f"<dt>{escape(label)}</dt><dd>{escape(value)}</dd>"
        for label, value in facts if value
    )

    head = (
        f'<div class="title-head"><div class="title-head__poster">'
        f'<img src="{escape(title.poster_src)}" alt="Постер: {escape(name)}" '
        'width="400" height="600"></div><div>'
        f"<h1>{escape(h1)}</h1>"
        f'<p class="lede">{escape(title.summary)}</p>'
        + _ratings_block(title)
        + f'<dl class="facts">{facts_html}</dl></div></div>'
    )

    body = (
        head
        + _player_block(ctx, title, name)
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
        indexable=indexable, breadcrumbs=trail, poster=title.poster_src,
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
        f'{len(items)} записям каталога.</p>'
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



def _icon_pages(ctx) -> list[Page]:
    """`/favicon.ico`, `/favicon.svg`, `/icon-32.png` и манифест.

    Все три домена отдавали на эти адреса 404. Иконка рисуется из токенов темы,
    поэтому она меняется вместе с оформлением и не может от него отстать.
    """
    accent = ctx["tokens"]["accent"]
    glyph = ctx["tokens"].get("accent_text", "#0d0d0d")
    brand = ctx["brand"]
    manifest = json.dumps(
        {
            "name": brand,
            "short_name": brand,
            "start_url": "/",
            "display": "standalone",
            "background_color": ctx["tokens"]["bg"],
            "theme_color": accent,
            "icons": [
                {"src": "/icon-32.png", "sizes": "32x32", "type": "image/png"},
                {"src": "/favicon.svg", "sizes": "any", "type": "image/svg+xml"},
            ],
        },
        ensure_ascii=False,
        indent=2,
    )
    return [
        Page(path="/favicon.ico", body="[иконка сайта, ICO]",
             content_type="image/x-icon", raw=icons.favicon_ico(accent, glyph)),
        Page(path="/icon-32.png", body="[иконка сайта, PNG 32x32]",
             content_type="image/png", raw=icons.favicon_png(accent, glyph)),
        Page(path="/favicon.svg", body=icons.favicon_svg(accent, glyph),
             content_type="image/svg+xml"),
        Page(path="/manifest.webmanifest", body=manifest + "\n",
             content_type="application/manifest+json; charset=utf-8"),
    ]


def _sitemap(ctx, indexable_paths) -> Page:
    """sitemap.xml. Без домена в нём не может быть ни одного адреса.

    Адрес в sitemap абсолютен по спецификации. Придумать хост — значит указать
    поисковику на чужой или несуществующий сайт, поэтому карта остаётся
    синтаксически корректной, но пустой, и прямо говорит почему.
    """
    urls = []
    if ctx["domain"] and ctx["indexing_enabled"]:
        urls = [f"  <url><loc>https://{ctx['domain']}{path}</loc></url>" for path in indexable_paths]
        note = ""
    elif not ctx["domain"]:
        note = (
            "  <!-- Адресов нет: домен не передан, а абсолютный URL без домена "
            "невозможен. Карта заполнится вместе с доменом. -->\n"
        )
    else:
        # Прежде здесь стояла отговорка про отсутствующий домен, хотя домен
        # был на месте. Карта молчит по другой причине, и называть надо её:
        # звать поисковик на страницы, которые владелец закрыл от индексации,
        # значит спорить с его же решением.
        note = (
            "  <!-- Адресов нет: индексация выключена в пакете сайта. "
            "Карта заполнится вместе с её включением. -->\n"
        )
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + note + ("\n".join(urls) + "\n" if urls else "")
        + "</urlset>\n"
    )
    return Page(path="/sitemap.xml", body=body, content_type="application/xml; charset=utf-8")


#: Адрес клиента аналитики. Один на весь модуль: тег в разметке и страница
#: ассета обязаны совпадать, а две независимые строки однажды разойдутся.
ANALYTICS_ASSET_PATH = analytics_snippet.ANALYTICS_SCRIPT_URL

APP_JS = """/* Lords — поведение интерфейса. Ни одного внешнего запроса. */
(function () {
  "use strict";

  // Стрелки карусели. Полка прокручивается колесом, свайпом и клавиатурой и
  // без них — это добавка для мыши, а не условие работоспособности.
  Array.prototype.forEach.call(document.querySelectorAll(".section--rail"), function (section) {
    var rail = section.querySelector(".rail");
    if (!rail) { return; }
    function step(direction) {
      var card = rail.querySelector(".rail__item");
      var width = card ? card.getBoundingClientRect().width + 12 : rail.clientWidth / 2;
      rail.scrollBy({ left: direction * width * 2, behavior: "smooth" });
    }
    var prev = section.querySelector("[data-rail-prev]");
    var next = section.querySelector("[data-rail-next]");
    if (prev) { prev.addEventListener("click", function () { step(-1); }); }
    if (next) { next.addEventListener("click", function () { step(1); }); }
    rail.addEventListener("keydown", function (event) {
      if (event.key === "ArrowRight") { step(1); event.preventDefault(); }
      if (event.key === "ArrowLeft") { step(-1); event.preventDefault(); }
    });
  });
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
      + seasons + "</a>"
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
        : "Введите название: поиск идёт по " + items.length + " записям каталога.";
    }
    if (query === "" && counter) { grid.innerHTML = ""; return; }

    var total = Math.max(1, Math.ceil(list.length / PER_PAGE));
    if (page > total) { page = total; }
    var slice = list.slice((page - 1) * PER_PAGE, page * PER_PAGE);
    grid.innerHTML = slice.length
      ? slice.map(card).join("")
      : '<p class="empty">По выбранным условиям в каталоге ничего нет.</p>';
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



#: Внутренние идентификаторы стенда: `lords-01`, `lords-02`, …
_TECHNICAL_ID = re.compile(r"^lords[-_]?\d+$", re.IGNORECASE)


def _brand_name(package: dict, profile: dict, domain: str) -> str:
    """Имя сайта, которое видит посетитель.

    Раньше здесь стояла метка профиля — «Lords General», «Lords New»,
    «Lords Curated». Это названия шаблонов сборки, а не сайтов: посетитель
    читал в заголовке вкладки внутреннюю классификацию стенда.

    Имя берётся из пакета, если владелец его задал. Технический идентификатор
    именем не считается. Дальше идёт домен — он принадлежит владельцу и не
    выдуман, а придумывать сайту название за владельца нельзя: имя бренда
    задаёт он, и до тех пор домен честнее любой выдумки.
    """
    declared = str((package.get("brand") or {}).get("name") or "").strip()
    if declared and not _TECHNICAL_ID.match(declared) and declared != package.get("site_id"):
        return declared
    if domain:
        return domain
    return str(profile.get("label") or package.get("site_id") or "")


def _context(package: dict, profile: dict, site_plan, player_state,
             publisher_id: str | None = None, fixture_catalog: bool = True) -> dict:
    layout = theme_mod.layout_of(profile)
    domain = str(package.get("domain") or "").strip()
    brand = _brand_name(package, profile, domain)
    nav = [
        (page.section, page.path)
        for page in site_plan.pages
        if page.in_menu and page.section != "home"
    ]
    return {
        "site_id": str(package.get("site_id", "")),
        "profile": site_plan.profile,
        "brand": brand,
        "tokens": theme_mod.tokens_of(profile),
        "carousel_heading": str(layout.get("carousel_heading") or "Новинки"),
        "mark": "".join(word[0] for word in brand.split()[:2]).upper() or "L",
        "language": str(package.get("language") or "ru"),
        "domain": domain,
        "indexing_enabled": bool(package.get("seo_indexing_enabled", False)),
        "canonical_base": f"https://{domain}" if domain else "",
        "canonical_state": CANONICAL_SELF if domain else CANONICAL_ABSENT,
        # allowed_hosts по умолчанию — собственный домен пакета и ничей больше:
        # три домена Lords обслуживаются одним рендерером, и общий список сразу
        # означал бы, что счётчик одного сайта уезжает на два соседних.
        "analytics_script": analytics_snippet.analytics_script_tag(
            counter_id=(package.get("analytics") or {}).get("counter_id"),
            allowed_hosts=list((package.get("analytics") or {}).get("allowed_hosts") or ([domain] if domain else [])),
            environment=str(package.get("environment") or "staging"),
            enabled=bool((package.get("analytics") or {}).get("enabled")),
            # Разрешение владельца на сбор с этого публичного домена. Отдельно
            # от `environment`: объявление сайта production требует правовых
            # сведений, а счётчик разрешён сам по себе.
            collection_authorized=bool((package.get("analytics") or {}).get("collection_authorized")),
        ),
        "nav": [("home", "/")] + nav,
        "per_page": int(((package.get("seo") or {}).get("items_per_page")) or 24),
        # Выключено по умолчанию: включение меняет состав страниц один раз и
        # требует согласия владельца (adr/0007).
        "pagination_by_year": bool(((package.get("seo") or {}).get("pagination_by_year"))),
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
        # Раскладка одна, а подписи разные: часть текстов честна только про стенд.
        "fixture_catalog": fixture_catalog,
        # Публичный атрибут элемента плеера. Подставляется на сервере в момент
        # ответа и в общий JS-бандл не попадает.
        "publisher_id": publisher_id,
        "comments_enabled": bool((package.get("comments") or {}).get("enabled")),
    }


def render_site(
    package: dict,
    *,
    catalog: fx.Catalog | None = None,
    root: Path | None = None,
    environ: dict | None = None,
    publisher_id: str | None = None,
    only_title_slugs: frozenset[str] | None = None,
) -> RenderedSite:
    """Полный сайт одного пакета: страницы, ассеты и отчёт о сборке.

    `catalog=None` — это не «пустой сайт», а отсутствие источника данных: в этом
    случае все типы находятся в состоянии `blocked_credentials`, разделов не
    возникает, и рендерер честно отдаёт сайт без каталога вместо витрины с
    выдуманным содержимым.

    `only_title_slugs` ограничивает отрисовку страниц произведений названными.
    По умолчанию (`None`) поведение прежнее — отрисовываются все. Ограничение
    нужно быстрому пути: страниц произведений 53 116, и на них уходит почти всё
    время сборки, тогда как выход одной серии меняет одну такую страницу.

    В ограниченном режиме карта сайта **не** пересобирается: она строится по
    списку отрисованных страниц, а он в этом режиме заведомо неполон. Карта
    остаётся прежней — что верно, пока произведения не появляются и не исчезают.
    Появление и исчезновение произведения требует полного цикла.
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
    fixture_catalog = (
        all(getattr(t, "fixture", True) for t in catalog.titles) if catalog.titles else True
    )
    ctx = _context(package, profile, site_plan, player_state, publisher_id, fixture_catalog)

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
                description=f"Произведения жанра «{label}» в каталоге.",
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
                description=f"Произведения {year} года в каталоге.",
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
                description=f"Произведения страны «{label}» в каталоге.",
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
        if only_title_slugs is not None and title.slug not in only_title_slugs:
            continue
        add(_title_page(ctx, catalog, title, kinds, indexable=owns_titles))

    # Поиск и служебные документы
    if "search" in by_section:
        add(_search_page(ctx, catalog, kinds))
    indexable_paths = sorted(p for p, page in site.pages.items() if page.indexable)
    for icon_page in _icon_pages(ctx):
        add(icon_page)
    add(_robots(ctx))
    # Карта сайта строится по списку отрисованного. В ограниченном режиме этот
    # список неполон, и пересборка выбросила бы из карты все неотрисованные
    # страницы. Прежняя карта остаётся верной, пока состав произведений не
    # менялся; изменение состава — повод для полного цикла, а не для быстрого.
    if only_title_slugs is None:
        add(_sitemap(ctx, indexable_paths))
    site.not_found = _not_found(ctx)

    # Ассеты
    add(Page(path="/assets/site.css", body=theme_mod.stylesheet(profile),
             content_type="text/css; charset=utf-8"))
    add(Page(path="/assets/app.js", body=APP_JS,
             content_type="text/javascript; charset=utf-8"))
    # Клиент аналитики выкладывается ровно тогда, когда на страницах есть тег,
    # который на него ссылается. Без этого тег указывал на несуществующий файл:
    # счётчик верный, тег единственный, разрешение выдано — и ни одного
    # обращения к Метрике, потому что `/assets/analytics.js` отдавал 404.
    if ctx.get("analytics_script"):
        add(Page(path=ANALYTICS_ASSET_PATH, body=analytics_codegen.render_js(),
                 content_type="text/javascript; charset=utf-8"))
    for title in pool:
        # Заглушка нужна лишь тем, у кого нет собственного постера. Раньше
        # страница создавалась каждому, и на живом каталоге это давало почти
        # пять тысяч ненужных SVG рядом с настоящими картинками источника.
        if title.poster_src == title.poster_path:
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
