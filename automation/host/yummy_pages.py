"""Страницы /new/, /collections/ и /schedule/ в собственном интерфейсе Yummy.

Почему так, а не своим каркасом
-------------------------------

У приложения витрины этих маршрутов нет — оно отвечает 404. Рисовать их
универсальной тёмной оболочкой уже пробовали: получилась не витрина Yummy, а
перекрашенный Lords. Поэтому здесь страница собирается из ЕЁ ЖЕ частей:
`<head>` со ссылкой на её таблицу стилей, её `<header>`, её `<footer>` и её
собственные классы карточек (`portal-catalog-tile`, `poster-slot--catalog`,
`portal-section-bar`). Ничего не перекрашивается и не изобретается.

Откуда данные
-------------

Из полезной нагрузки самой витрины. Главная отдаёт разделы «Новые серии»,
«Появилось видео», «Сейчас выходят», «Анонсы» и сезонную подборку; каталог
отдаёт плитки с рейтингом, постером, типом и годом. Ничего не выдумывается: в
разделе показывается ровно то, что витрина уже показывает у себя.

Честное пустое состояние
------------------------

Если данных для раздела нет, страница отвечает 200 и показывает оформленное
пустое состояние. Выдуманные даты и подставные карточки запрещены: пустое
состояние честнее придуманного расписания.
"""

from __future__ import annotations

import html
import re

# Плитка витрины в полезной нагрузке: href, рейтинг, постер, подпись, тип, год.
ПЛИТКА = re.compile(
    r'portal-catalog-tile.{0,120}?\\"href\\":\\"(?P<href>/anime/[^\\"]+)\\"'
    r'.{0,900}?portal-catalog-rating-value\\",\\"children\\":\\"(?P<rating>[^\\"]*)\\"'
    r'.{0,900}?\\"alt\\":\\"(?P<alt>[^\\"]*)\\".{0,400}?\\"src\\":\\"(?P<src>[^\\"]+)\\"'
    r'.{0,900}?portal-catalog-caption\\",\\"children\\":\\"(?P<name>[^\\"]+)\\"',
    re.S)

#: Карточка в лентах главной: там разметка другая — ссылка, постер и подпись.
ЛЕНТА = re.compile(
    r'\\"href\\":\\"(?P<href>/anime/[^\\"]+)\\".{0,600}?'
    r'\\"alt\\":\\"Постер аниме «(?P<name>[^»]+)»\\"'
    r'(?:.{0,300}?\\"src\\":\\"(?P<src>[^\\"]+)\\")?',
    re.S)


#: Идентификатор тайтла в адресе: «/anime/<слаг>--<uuid>». Постер витрины
#: лежит по «/poster/<uuid>.webp» — проверено запросом, отвечает 200.
#: Это не догадка об адресе, а тот же идентификатор, которым витрина сама
#: называет тайтл; у адресов без uuid постер не подставляется.
UUID_В_АДРЕСЕ = re.compile(
    r"--([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$")


def постер_по_адресу(href: str) -> str | None:
    м = UUID_В_АДРЕСЕ.search(href or "")
    return f"/poster/{м.group(1)}.webp" if м else None


def плитки_каталога(payload: str, предел: int = 60) -> list[dict]:
    итог, видели = [], set()
    for м in ПЛИТКА.finditer(payload):
        href = м.group("href")
        if href in видели:
            continue
        видели.add(href)
        итог.append({"href": href, "name": м.group("name"),
                     "src": м.group("src"), "alt": м.group("alt"),
                     "rating": м.group("rating") or None})
        if len(итог) >= предел:
            break
    return итог


#: Заголовки лент главной. Нужны, чтобы ограничить раздел СЛЕДУЮЩИМ
#: заголовком, а не окном фиксированной длины.
ЗАГОЛОВКИ_ЛЕНТ = ("Новые серии", "Актуальное", "Появилось видео", "Сейчас выходят",
                  "Аниме летнего сезона", "Новые серии и обновления", "Новости",
                  "Новое на сайте", "Анонсы")


def раздел_главной(payload: str, заголовок: str, предел: int = 24) -> list[dict]:
    """Элементы одного раздела главной — строго до следующего заголовка.

    Окно фиксированной длины здесь не годится: разделы идут подряд, и
    двадцать четыре тысячи знаков перетекали в соседние. Из-за этого «Анонсы»
    и «Сейчас выходят» возвращали один и тот же набор, а страницы
    /collections/ и /schedule/ совпадали на сто процентов.
    """
    i = payload.find(f'\\"{заголовок}\\"')
    if i < 0:
        i = payload.find(заголовок)
    if i < 0:
        return []
    конец = len(payload)
    for другой in ЗАГОЛОВКИ_ЛЕНТ:
        if другой == заголовок:
            continue
        for образец in (f'\\"{другой}\\"', другой):
            j = payload.find(образец, i + len(заголовок))
            if j > i:
                конец = min(конец, j)
                break
    кусок = payload[i:конец]
    итог, видели = [], set()
    for м in ЛЕНТА.finditer(кусок):
        href = м.group("href")
        if href in видели:
            continue
        видели.add(href)
        итог.append({"href": href, "name": м.group("name"),
                     "src": м.group("src") or постер_по_адресу(href),
                     "alt": f'Постер аниме «{м.group("name")}»',
                     "rating": None})
        if len(итог) >= предел:
            break
    return итог


def дополнить_постерами(элементы: list[dict], каталог: list[dict]) -> list[dict]:
    """Постеры для лент берутся из каталога по адресу тайтла.

    В лентах главной постер лежит не рядом со ссылкой, и по одному только
    адресу его выводит не всегда: часть адресов без идентификатора. Каталог
    той же витрины отдаёт `src` явно — здесь эти два источника сводятся по
    href. Ничего не подставляется наугад: нет совпадения — остаётся заглушка.
    """
    по_адресу = {з["href"]: з.get("src") for з in каталог if з.get("src")}
    for з in элементы:
        if not з.get("src"):
            з["src"] = по_адресу.get(з["href"])
    return элементы


#: Единственный контракт адресов: сущность → канонический путь.
#:
#: Компоненты не собирают адрес сами. В данных витрины ссылка приходит и в
#: виде «/anime/<слаг>», и в виде «/anime/<слаг>--<uuid>»; второй отвечает
#: постоянным редиректом на первый. Публиковать в блоке адрес, который сначала
#: редиректит, значит гонять посетителя и краулер через лишний переход и
#: показывать в разметке не тот URL, что в canonical страницы.
ХВОСТ_UUID = re.compile(
    r"--[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def канонический_путь(href: str) -> str | None:
    """Канонический адрес сущности или None, если адрес непригоден.

    None означает «в блоке не публикуем»: сущность без разрешённого
    канонического пути показывать нельзя.
    """
    if not href or not href.startswith("/anime/"):
        return None
    путь = href.split("?", 1)[0].split("#", 1)[0].rstrip("/")
    путь = ХВОСТ_UUID.sub("", путь)
    хвост = путь[len("/anime/"):]
    return путь if хвост else None


def карточка(з: dict) -> str:
    """Плитка ровно теми классами, которыми её рисует сама витрина."""
    рейтинг = ""
    if з.get("rating"):
        рейтинг = (
            '<span class="portal-catalog-rating"><span class="portal-catalog-rating-info">'
            '<svg class="portal-catalog-star" width="14" height="14" viewBox="0 0 24 24" '
            'aria-hidden="true"><path fill="currentColor" d="M12 2.6l2.7 6.3 6.8.6-5.2 4.5 '
            '1.6 6.6L12 17.2 6.1 20.6l1.6-6.6L2.5 9.5l6.8-.6z"></path></svg>'
            f'<span class="portal-catalog-rating-value">{html.escape(з["rating"])}</span>'
            '</span></span>')
    if з.get("src"):
        # Реальное изображение: с размерами и осмысленным alt.
        постер = (f'<img alt="{html.escape(з.get("alt") or з["name"])}" loading="lazy" '
                  f'width="230" height="322" decoding="async" '
                  f'src="{html.escape(з["src"])}">')
    else:
        # Заглушка только при настоящем отсутствии изображения.
        постер = ('<span class="poster-slot-skeleton" aria-label="Нет постера">'
                  'Нет постера</span>')
    адрес = канонический_путь(з.get("href"))
    if not адрес:
        # Без канонического пути сущность в блоке не публикуется.
        return ""
    return (
        f'<article class="portal-catalog-tile" data-entity="{html.escape(адрес)}">'
        f'<a class="portal-catalog-image" href="{html.escape(адрес)}">{рейтинг}'
        f'<div class="poster-slot poster-slot--catalog">{постер}</div></a>'
        f'<div class="portal-catalog-info">'
        f'<a class="portal-catalog-caption" href="{html.escape(адрес)}">'
        f'{html.escape(з["name"])}</a></div></article>')


def секция(заголовок: str, подпись: str, элементы: list[dict]) -> str:
    if not элементы:
        return (f'<div class="portal-section-bar">{html.escape(заголовок)}</div>'
                f'<p class="portal-empty">{html.escape(подпись)}</p>')
    плитки = "".join(карточка(з) for з in элементы)
    return (f'<div class="portal-section-bar">{html.escape(заголовок)}</div>'
            f'<div class="portal-catalog-tiles">{плитки}</div>')


ПУСТО_СТИЛЬ = (
    "<style>.portal-empty{margin:12px 0 28px;padding:22px;border-radius:14px;"
    "border:1px dashed currentColor;opacity:.7;font-size:15px;line-height:1.5}"
    ".portal-page-lead{margin:4px 0 18px;opacity:.8;font-size:15px}</style>")


ГОЛОВА_ТИТУЛ = re.compile(r"<title\b[^>]*>.*?</title>", re.S | re.I)
ГОЛОВА_ОПИСАНИЕ = re.compile(
    r'<meta\s+(?:name="description"|property="og:(?:title|description|type|site_name)")'
    r'[^>]*>', re.I)


def собрать(оболочка: dict, заголовок: str, лид: str, тело: str,
            вариант: dict | None = None, имя_сайта: str = "YummyAnime") -> bytes:
    """Страница из головы, шапки и подвала самой витрины.

    Профиль домена меняет акцентные токены, плотность сетки и объявляет себя
    в разметке: три витрины одной семьи не должны отдавать одинаковый DOM.
    """
    в = вариант or {}
    токены = ""
    if в:
        токены = (
            "<style>:root{--sf-accent:" + в.get("акцент", "#ff5c8a") + ";"
            "--sf-accent-2:" + в.get("акцент2", "#ffb347") + "}"
            ".portal-catalog-tiles{grid-template-columns:"
            + в.get("плотность", "repeat(auto-fill,minmax(150px,1fr))") + "}"
            ".portal-section-bar{border-left:4px solid var(--sf-accent);padding-left:10px}"
            ".sf-rank{display:inline-block;margin-right:6px;font-weight:800;"
            "color:var(--sf-accent)}"
            ".sf-rates{display:inline-flex;gap:6px;flex-wrap:wrap}"
            ".sf-rate{font-size:12px;opacity:.85}.sf-rate small{opacity:.7}"
            ".sf-tabs{display:flex;gap:8px;margin:8px 0 14px}"
            ".sf-tabs a{padding:6px 12px;border:1px solid var(--sf-accent);"
            "border-radius:8px;font-size:13px}"
            ".sf-tabs a[aria-current]{background:var(--sf-accent);color:#fff}</style>")
    мета = ""
    if в:
        мета = (f'<meta name="site-factory-variant-id" content="{html.escape(в.get("variant_id",""))}">'
                f'<meta name="site-factory-variant-version" content="{html.escape(в.get("variant_version",""))}">')
    # Заголовок страницы — свой, а не унаследованный от оболочки.
    #
    # Оболочка берётся у страницы каталога вместе с её <title>, и раздел
    # «Расписание выходов» уходил наружу под заголовком «Каталог с
    # редакционной навигацией». Заголовок и H1 обязаны говорить об одной
    # странице: расхождение видит и посетитель во вкладке, и поисковик.
    голова = ГОЛОВА_ТИТУЛ.sub(
        f"<title>{html.escape(заголовок)} · {html.escape(имя_сайта)}</title>",
        оболочка["head"], count=1)
    описание = html.escape(лид[:300])
    голова = ГОЛОВА_ОПИСАНИЕ.sub("", голова)
    сводка = (f'<meta name="description" content="{описание}">'
              f'<meta property="og:title" content="{html.escape(заголовок)}">'
              f'<meta property="og:description" content="{описание}">'
              f'<meta property="og:type" content="website">')
    if в.get("title"):
        сводка += f'<meta property="og:site_name" content="{html.escape(в["title"])}">'
    return (
        "<!DOCTYPE html><html lang=\"ru\">"
        + голова.replace("</head>", ПУСТО_СТИЛЬ + токены + мета + сводка + "</head>", 1)
        + f'<body data-variant="{html.escape(в.get("variant_id", ""))}">' + оболочка["header"]
        + '<main id="main-content" class="portal-container min-h-dvh min-w-0 flex-1">'
        + f"<h1 class=\"portal-section-bar\">{html.escape(заголовок)}</h1>"
        + f"<p class=\"portal-page-lead\">{html.escape(лид)}</p>"
        + тело + "</main>" + оболочка["footer"] + "</body></html>"
    ).encode("utf-8")


ГОЛОВА = re.compile(r"<head\b.*?</head>", re.S | re.I)
ШАПКА = re.compile(r"<header\b.*?</header>", re.S | re.I)
ПОДВАЛ = re.compile(r"<footer\b.*?</footer>", re.S | re.I)


def разобрать_оболочку(html_витрины: str) -> dict | None:
    г = ГОЛОВА.search(html_витрины)
    ш = ШАПКА.search(html_витрины)
    п = ПОДВАЛ.search(html_витрины)
    if not (г and ш and п):
        return None
    голова = г.group(0)
    # Заголовок страницы заменяется ниже вызывающим кодом; скрипты приложения
    # не переносятся: страница статическая и гидратация ей не нужна.
    голова = re.sub(r"<script\b.*?</script>", "", голова, flags=re.S | re.I)
    return {"head": голова, "header": ш.group(0), "footer": п.group(0)}
