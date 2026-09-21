"""Собственные страницы витрины Yummy: /new/, /collections/, /schedule/, /top/.

Почему не своим каркасом
------------------------

У приложения витрины этих маршрутов нет — оно отвечает 404. Рисовать их
универсальной тёмной оболочкой уже пробовали: получилась не витрина Yummy, а
перекрашенный Lords. Поэтому страница собирается из ЕЁ ЖЕ частей: `<head>` со
ссылкой на её таблицу стилей, её `<header>`, её `<footer>` и её собственные
классы карточек (`portal-catalog-tile`, `poster-slot--catalog`,
`portal-section-bar`). Ничего не перекрашивается и не изобретается.

Откуда данные
-------------

Из контура чтения — того же, на котором стоит `/__contract` и `/top/`.

Раньше данные добывались разбором полезной нагрузки приложения регулярными
выражениями, и это сломалось молча: приложение сменило порядок полей в
разметке плитки (`src` перед `alt`) и перестало печатать рейтинг у части
карточек. Разбор начал возвращать ноль, и наружу это вышло не ошибкой, а
пустыми разделами, плитками без постеров и секцией «Высокие оценки», которая
уверяла, что оценок нет, — при 437 подтверждённых оценках в контуре.

Чинить выражение было бы лечением симптома. Документ приложения приходит
потоком, и его текстовый порядок не совпадает с порядком на экране: между
заголовком раздела и следующим заголовком лежат чужие карточки и служебные
скрипты. Измерено на живом приложении: «Новое на сайте» давало 80 карточек
вместо 18, «Анонсы» — 2 вместо 12. Извлечение «по тексту между заголовками»
— догадка, а не чтение, и надёжным оно не станет.

Контур, напротив, отдаёт объявленный адрес, постер, год, вид и дату у каждой
записи. Ничего не выдумывается и здесь: показывается ровно то, что в контуре
есть, а чего в нём нет — того на странице нет.

Честное пустое состояние
------------------------

Поверхность без данных не рисуется вовсе — ни заголовка, ни рамки: пустое
место читается как поломка, а «пока пусто» в рамке — как работающий раздел
без данных. Страница, у которой не наполнилась ни одна поверхность, не
остаётся одним заголовком: она называет, каких поверхностей не хватило, и
куда уйти. Выдуманные даты и подставные карточки запрещены.
"""

from __future__ import annotations

import html
import re

#: Идентификатор тайтла в хвосте адреса: «/anime/<слаг>--<uuid>».
#:
#: Приложение печатает в своих лентах именно эту форму, а она отвечает
#: постоянным редиректом на короткую. Публиковать её в блоке значит гонять
#: посетителя и краулер через лишний переход и показывать в разметке не тот
#: URL, что в canonical страницы.
ХВОСТ_UUID = re.compile(
    r"--[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def канонический_путь(href: str | None) -> str | None:
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


#: Вид произведения: контур говорит машинным словом, витрина — человеческим.
#: Неизвестное значение не переводится и не печатается: выдумывать подпись
#: под незнакомый код нельзя.
ВИДЫ = {"SERIES": "Сериал", "MOVIE": "Фильм", "OVA": "OVA", "ONA": "ONA",
        "SPECIAL": "Спецвыпуск"}


def _звезда() -> str:
    return ('<svg class="portal-catalog-star" width="14" height="14" '
            'viewBox="0 0 24 24" aria-hidden="true">'
            '<path fill="currentColor" d="M12 2.6l2.7 6.3 6.8.6-5.2 4.5 '
            '1.6 6.6L12 17.2 6.1 20.6l1.6-6.6L2.5 9.5l6.8-.6z"></path></svg>')


def карточка(э: dict) -> str:
    """Плитка ровно теми классами, которыми её рисует само приложение.

    Принимается словарь контура: `canonical_path`, `title`, `poster`, `year`,
    `kind`, необязательные `rating` и `caption`. Отдельного словаря «для
    разметки» нет намеренно: два написания одного поля однажды разойдутся.

    Счётчик просмотров приложения (`portal-catalog-icons`) здесь не рисуется:
    контур просмотров не отдаёт, а печатать ноль значило бы объявить
    измеренным то, чего никто не измерял.
    """
    адрес = канонический_путь(э.get("canonical_path"))
    if not адрес:
        return ""
    название = (э.get("title") or "").strip()
    рейтинг = ""
    if э.get("rating"):
        # Значок оценки — компонент приложения: звезда и число. Но число без
        # источника запрещено: разные шкалы, сведённые в одно безымянное
        # значение, невозможно ни сверить, ни оспорить. Источник и шкала
        # приходят отдельным полем и попадают в доступное имя значка, а
        # видимой строкой — в сведения карточки ниже.
        подпись = (f'Оценка {э["rating_source"]}: {э["rating"]}'
                   if э.get("rating_source") else f'Оценка {э["rating"]}')
        рейтинг = (
            f'<span class="portal-catalog-rating" title="{html.escape(подпись)}" '
            f'aria-label="{html.escape(подпись)}">'
            '<span class="portal-catalog-rating-info">' + _звезда()
            + f'<span class="portal-catalog-rating-value">'
              f'{html.escape(str(э["rating"]))}</span></span></span>')
    if э.get("poster"):
        # Настоящее изображение: с размерами приложения и осмысленным alt.
        постер = (f'<img alt="Постер аниме «{html.escape(название)}»" '
                  f'loading="lazy" width="230" height="322" decoding="async" '
                  f'style="color:transparent" src="{html.escape(э["poster"])}">')
    else:
        # Заглушка только при настоящем отсутствии изображения. Подставлять
        # сюда общий /poster/<слаг>.webp нельзя: он отвечает 200 на любой
        # адрес и отдаёт svg-заглушку, то есть прячет отсутствие данных.
        постер = ('<span class="poster-slot-skeleton" aria-label="Нет постера">'
                  'Нет постера</span>')
    сведения = [f'<a class="portal-catalog-caption" href="{html.escape(адрес)}">'
                f'{html.escape(название)}</a>']
    вид = ВИДЫ.get(э.get("kind") or "")
    год = э.get("year")
    if вид or год:
        части = ""
        if вид:
            части += f"<span>{html.escape(вид)}</span>"
        if год:
            части += f'<span class="portal-catalog-year">{html.escape(str(год))}</span>'
        сведения.append(f'<div class="portal-catalog-type">{части}</div>')
    строки = []
    if э.get("rating_source"):
        # Видимая строка называет источник и шкалу — не повторяя число:
        # оно уже стоит в значке, а два одинаковых числа рядом читаются как
        # две разные оценки.
        строки.append(f'Оценка: {э["rating_source"]}')
    if э.get("caption"):
        строки.append(str(э["caption"]))
    if строки:
        сведения.append(f'<div class="portal-catalog-meta">'
                        f'{html.escape(" · ".join(строки))}</div>')
    return (
        f'<article class="portal-catalog-tile" data-entity="{html.escape(адрес)}">'
        f'<a class="portal-catalog-image" href="{html.escape(адрес)}">{рейтинг}'
        f'<div class="poster-slot poster-slot--catalog">{постер}</div></a>'
        f'<div class="portal-catalog-info">{"".join(сведения)}</div></article>')


def секция(заголовок: str, подпись: str, элементы: list[dict]) -> str:
    """Раздел страницы. Пустой — не рисуется вовсе.

    `подпись` объясняет критерий попадания в раздел: без него читатель не
    отличит «здесь свежее» от «здесь любимое редакцией», а раздел без
    объявленного критерия невозможно ни проверить, ни оспорить.
    """
    плитки = [т for т in (карточка(з) for з in элементы) if т]
    if not плитки:
        return ""
    подпись_html = (f'<p class="portal-page-lead">{html.escape(подпись)}</p>'
                    if подпись else "")
    return (f'<div class="portal-section-bar">{html.escape(заголовок)}</div>'
            f'{подпись_html}<div class="portal-catalog-tiles">'
            + "".join(плитки) + "</div>")


def нечего_показать(раздел: str, поверхности: list[str]) -> str:
    """Объяснение для страницы, у которой не наполнилась ни одна поверхность.

    Страница из одного заголовка читается как поломка. Здесь называются
    поверхности контракта, которых не хватило, — машинными именами, теми же,
    что отдаёт `/__contract`: тогда сказанное на странице можно сверить с
    числом, а не поверить на слово.
    """
    имена = ", ".join(html.escape(п) for п in поверхности)
    return ('<p class="portal-empty">'
            f'Раздел «{html.escape(раздел)}» строится на поверхностях контура: '
            f'{имена}. Сейчас ни одна из них не содержит записей, поэтому '
            'показывать нечего — подменять раздел общим каталогом запрещено. '
            'Число записей в каждой поверхности отвечает '
            '<a href="/__contract">/__contract</a>; каталог целиком — '
            '<a href="/catalog">/catalog</a>.</p>')


ПОЛЕ_ЗАПРОСА = re.compile(r'(<input\b[^>]*\bname="q"[^>]*>)', re.I)
ЗНАЧЕНИЕ_ПОЛЯ = re.compile(r'\svalue="[^"]*"', re.I)


def подставить_запрос(оболочка: dict, запрос: str) -> dict:
    """Введённый запрос остаётся в поле поиска и на собственной странице.

    Шапка копируется у страницы каталога, а там поле пустое. Страница
    результатов с пустым полем стирает то, что человек набрал: он не видит,
    на какой вопрос получил ответ, и не может исправить одну букву.

    Правится только СВОЯ копия шапки: страница статическая, дерева React на
    ней нет, и атрибут никому не мешает.
    """
    if not запрос:
        return оболочка

    def заменить(м: re.Match) -> str:
        тег = ЗНАЧЕНИЕ_ПОЛЯ.sub("", м.group(1))
        закрытие = "/>" if тег.rstrip().endswith("/>") else ">"
        тело = тег.rstrip()[:-len(закрытие)].rstrip()
        return f'{тело} value="{html.escape(запрос, quote=True)}"{закрытие}'
    новая = dict(оболочка)
    новая["header"] = ПОЛЕ_ЗАПРОСА.sub(заменить, оболочка["header"])
    return новая


def возраст_данных(свод: dict) -> str:
    """Строка о пополнении контура. Неизвестность называется неизвестностью."""
    if not свод.get("known"):
        return ('<p class="portal-page-lead">Момент последнего пополнения '
                'контура неизвестен: состояние импорта не объявлено.</p>')
    момент = html.escape(str(свод.get("last_success") or "неизвестен"))
    хвост = ""
    if свод.get("source_count"):
        хвост = f', записей в источнике {int(свод["source_count"])}'
    return (f'<p class="portal-page-lead">Контур пополнялся последний раз '
            f'{момент}{хвост}. Всё, что показано ниже, — на этот момент.</p>')


#: Маршруты, которые витрина отдаёт своими страницами. Ссылки первого экрана
#: строятся только из них: пункт, ведущий в 404, хуже отсутствующего.
МАРШРУТЫ = (("/new/", "Новинки"), ("/top/", "Топ-100"),
            ("/collections/", "Подборки"), ("/schedule/", "Расписание"))


def первый_экран(в: dict, активный: str = "") -> str:
    """Композиция первого экрана — часть профиля домена, а не украшение.

    Три витрины одной семьи не должны открываться одинаково. Каталожная
    начинает поиском, событийная — рядом разделов, редакционная — вступлением
    и крупной сеткой. Ничего, кроме существующих маршрутов и формы поиска
    самой витрины, здесь не появляется: выдумывать фильтры, счётчики и
    подборки запрещено.
    """
    вид = в.get("первый_экран") or "витрина"
    порядок = в.get("нав_порядок") or [а for а, _ in МАРШРУТЫ]
    по_адресу = dict(МАРШРУТЫ)
    пункты = [(а, по_адресу[а]) for а in порядок if а in по_адресу]
    ряд = "".join(
        f'<a href="{html.escape(а)}"'
        + (' aria-current="page"' if а.rstrip("/") == активный.rstrip("/") else "")
        + f">{html.escape(п)}</a>" for а, п in пункты)
    ряд = f'<nav class="sf-tabs" aria-label="Разделы витрины">{ряд}</nav>'
    if вид == "поиск":
        return (
            '<form class="sf-find" action="/search" method="get" role="search">'
            '<label class="sr-only" for="sf-q">Найти аниме по названию</label>'
            '<input id="sf-q" name="q" placeholder="Найти аниме по названию" '
            'autocomplete="off"><button type="submit">Найти</button></form>' + ряд)
    if вид == "лента":
        return ряд
    # Редакционная витрина открывается лидом — но ряд разделов нужен и ей.
    #
    # Голова и шапка копируются у приложения без скриптов: страница
    # статическая, гидратация ей не нужна. Значит, и выпадающий список
    # «Аниме» на ней не откроется, а три из четырёх разделов витрины живут
    # именно в нём. Без этого ряда с собственной страницы некуда уйти.
    return ряд


ГОЛОВА_ТИТУЛ = re.compile(r"<title\b[^>]*>.*?</title>", re.S | re.I)
ГОЛОВА_РОБОТЫ = re.compile(r'<meta\s+name="robots"[^>]*>', re.I)
ГОЛОВА_ОПИСАНИЕ = re.compile(
    r'<meta\s+(?:name="description"|property="og:(?:title|description|type|site_name)")'
    r'[^>]*>', re.I)

ПУСТО_СТИЛЬ = (
    "<style>.portal-empty{margin:12px 0 28px;padding:22px;border-radius:14px;"
    "border:1px dashed currentColor;opacity:.7;font-size:15px;line-height:1.5}"
    ".portal-page-lead{margin:4px 0 18px;opacity:.8;font-size:15px}"
    ".portal-catalog-meta{margin-top:2px;font-size:12px;opacity:.7}</style>")


def собрать(оболочка: dict, заголовок: str, лид: str, тело: str,
            вариант: dict | None = None, имя_сайта: str = "YummyAnime",
            активный: str = "") -> bytes:
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
            ".sf-tabs a[aria-current]{background:var(--sf-accent);color:#fff}"
            ".sf-find{display:flex;gap:8px;margin:6px 0 12px;max-width:560px}"
            ".sf-find input{flex:1 1 auto;min-width:0;padding:9px 12px;border-radius:9px;"
            "border:1px solid color-mix(in srgb,currentColor 25%,transparent);"
            "background:transparent;color:inherit;font:inherit}"
            ".sf-find button{padding:9px 16px;border-radius:9px;border:0;cursor:pointer;"
            "background:var(--sf-accent);color:#fff;font:inherit}"
            ".sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}"
            "</style>")
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
    # Голова копируется у витрины вместе с её мета-тегом robots. Страница
    # наша, дерева React на ней нет, и тег приводится к строгому значению
    # здесь же — второй тег рядом с первым был бы конфликтом директив.
    голова = ГОЛОВА_РОБОТЫ.sub("", голова)
    сводка = (f'<meta name="description" content="{описание}">'
              f'<meta property="og:title" content="{html.escape(заголовок)}">'
              f'<meta property="og:description" content="{описание}">'
              f'<meta property="og:type" content="website">')
    if в.get("title"):
        сводка += f'<meta property="og:site_name" content="{html.escape(в["title"])}">'
    return (
        # `data-sf-own` — признак собственной страницы витрины. Только на
        # ней посредник объявляет версию: в чужую разметку он не пишет
        # ничего, иначе ломается восстановление страницы React.
        "<!DOCTYPE html><html data-sf-own=\"1\" lang=\"ru\">"
        + голова.replace("</head>", ПУСТО_СТИЛЬ + токены + мета + сводка + "</head>", 1)
        + f'<body data-variant="{html.escape(в.get("variant_id", ""))}">' + оболочка["header"]
        + '<main id="main-content" class="portal-container min-h-dvh min-w-0 flex-1">'
        + f"<h1 class=\"portal-section-bar\">{html.escape(заголовок)}</h1>"
        + f"<p class=\"portal-page-lead\">{html.escape(лид)}</p>"
        + первый_экран(в, активный) + тело + "</main>" + оболочка["footer"] + "</body></html>"
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
