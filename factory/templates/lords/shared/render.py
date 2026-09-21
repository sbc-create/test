#!/usr/bin/env python3
"""Общее ядро отрисовки шаблонных пакетов Lords.

## Граница ответственности

Ядро владеет тем, что не должно различаться между шаблонами и не может быть
отдано пакету без риска: экранирование, скелет документа, канонический адрес,
политика индексации, порядок заголовков и честное поведение при нехватке
данных. Пакет владеет композицией — какие блоки, в каком порядке, какой
грамматикой карточек и с какими токенами.

Из этого следует правило, которое здесь и закреплено: пакет НЕ содержит
разметки. Он объявляет блоки, а строит их ядро. Иначе пятьдесят пакетов стали
бы пятьюдесятью копиями одного DOM с разными переменными — ровно тем, что
запрещено.

## Честность при нехватке данных

Фикстура несёт только то, что есть в каталоге: slug, title, url, year, kind,
poster, published_at. Рейтингов, жанров, стран и описаний там нет. Блок,
которому нечего показать, не рисует пустую рамку: он либо скрывается, либо
честно меняет подпись. Поэтому `минимум` у блока — не украшение, а условие
его появления.
"""

from __future__ import annotations

import html
import json
import pathlib

#: Ширины, на которых пакет обязан оставаться годным. Совпадают с матрицей
#: приёмки: проверять на других значит проверять не то, что принимается.
ТОЧКИ = (320, 390, 768, 1024, 1440, 1920)


def э(значение) -> str:
    """Экранирование. Единственная точка: пакет до разметки не допущен."""
    return html.escape("" if значение is None else str(значение), quote=True)


# --- карточки ---------------------------------------------------------------

def карточка_постер(запись: dict) -> str:
    постер = запись.get("poster")
    медиа = (
        f'<img class="k__img" src="{э(постер)}" alt="" loading="lazy" '
        f'width="200" height="300">'
        if постер else '<span class="k__none" aria-hidden="true"></span>'
    )
    год = f'<span class="k__y">{э(запись["year"])}</span>' if запись.get("year") else ""
    return (
        f'<a class="k k--poster" href="{э(запись["url"])}" title="{э(запись["title"])}">'
        f'<span class="k__p">{медиа}</span>'
        f'<span class="k__cap"><span class="k__t">{э(запись["title"])}</span>{год}</span>'
        f"</a>"
    )


def карточка_компакт(запись: dict) -> str:
    """Строка-карточка: миниатюра слева, подпись и метаданные справа.

    Дата стоит отдельной строкой, а не в одном ряду с подписью: именно
    совмещение их в ряд и приводило к обрезанию обязательной даты.
    """
    постер = запись.get("poster")
    медиа = (
        f'<img class="k__img" src="{э(постер)}" alt="" loading="lazy" width="64" height="96">'
        if постер else '<span class="k__none" aria-hidden="true"></span>'
    )
    дата = ""
    if запись.get("published_at") and not запись.get("published_at_estimated"):
        дата = f'<time class="k__d" datetime="{э(запись["published_at"])}">' \
               f'{э(str(запись["published_at"])[:10])}</time>'
    вид = f'<span class="k__k">{э(запись["kind"])}</span>' if запись.get("kind") else ""
    return (
        f'<a class="k k--compact" href="{э(запись["url"])}" title="{э(запись["title"])}">'
        f'<span class="k__p">{медиа}</span>'
        f'<span class="k__cap"><span class="k__t">{э(запись["title"])}</span>'
        f'<span class="k__meta">{вид}{дата}</span></span>'
        f"</a>"
    )


def карточка_редакционная(запись: dict) -> str:
    постер = запись.get("poster")
    медиа = (
        f'<img class="k__img" src="{э(постер)}" alt="" loading="lazy" width="200" height="300">'
        if постер else '<span class="k__none" aria-hidden="true"></span>'
    )
    подзаголовок = " · ".join(
        str(x) for x in (запись.get("kind"), запись.get("year")) if x
    )
    строка = f'<span class="k__sub">{э(подзаголовок)}</span>' if подзаголовок else ""
    return (
        f'<a class="k k--editorial" href="{э(запись["url"])}" title="{э(запись["title"])}">'
        f'<span class="k__p">{медиа}</span>'
        f'<span class="k__cap"><span class="k__t">{э(запись["title"])}</span>{строка}</span>'
        f"</a>"
    )


def карточка_ранг(запись: dict, номер: int = 0) -> str:
    """Карточка с рангом. Номер — позиция в списке, а не оценка.

    Оценок в источнике нет, и подставлять их нельзя. Ранг честно означает
    «столько-то по порядку в этом списке» и больше ничего.
    """
    подпись = " · ".join(str(x) for x in (запись.get("kind"), запись.get("year")) if x)
    строка = f'<span class="k__sub">{э(подпись)}</span>' if подпись else ""
    return (
        f'<a class="k k--ranked" href="{э(запись["url"])}" title="{э(запись["title"])}">'
        f'<span class="k__n" aria-hidden="true">{номер}</span>'
        f'<span class="k__cap"><span class="k__t">{э(запись["title"])}</span>{строка}</span>'
        f"</a>"
    )


def карточка_плитка(запись: dict) -> str:
    """Текстовая плитка без изображения: для индексов и досок."""
    год = f'<span class="k__y">{э(запись["year"])}</span>' if запись.get("year") else ""
    return (
        f'<a class="k k--tile" href="{э(запись["url"])}" title="{э(запись["title"])}">'
        f'<span class="k__cap"><span class="k__t">{э(запись["title"])}</span>{год}</span>'
        f"</a>"
    )


КАРТОЧКИ = {
    "poster": карточка_постер,
    "compact": карточка_компакт,
    "editorial": карточка_редакционная,
    "tile": карточка_плитка,
}


# --- блоки ------------------------------------------------------------------

def _сетка(записи: list[dict], грамматика: str, класс: str) -> str:
    строитель = КАРТОЧКИ[грамматика]
    карточки = "".join(строитель(з) for з in записи)
    return f'<div class="g g--{э(грамматика)} {э(класс)}">{карточки}</div>'


def блок_герой(данные: dict, настройка: dict) -> str:
    записи = данные["items"][: настройка.get("максимум", 1)]
    if not записи:
        return ""
    первая = записи[0]
    постер = первая.get("poster")
    медиа = (
        f'<img class="hero__img" src="{э(постер)}" alt="" width="200" height="300">'
        if постер else '<span class="k__none" aria-hidden="true"></span>'
    )
    подпись = " · ".join(str(x) for x in (первая.get("kind"), первая.get("year")) if x)
    return (
        f'<section class="sec hero"><div class="hero__media">{медиа}</div>'
        f'<div class="hero__body"><p class="hero__eyebrow">{э(настройка["заголовок"])}</p>'
        f'<h2 class="hero__t">{э(первая["title"])}</h2>'
        f'<p class="hero__sub">{э(подпись)}</p>'
        f'<a class="hero__cta" href="{э(первая["url"])}">Смотреть</a></div></section>'
    )


def блок_сетка(данные: dict, настройка: dict) -> str:
    записи = данные["items"][настройка.get("сдвиг", 0):][: настройка.get("максимум", 12)]
    if len(записи) < настройка.get("минимум", 1):
        return ""  # Блок скрывается, а не рисует пустые ячейки.
    return (
        f'<section class="sec"><h2 class="sec__t">{э(настройка["заголовок"])}</h2>'
        f'{_сетка(записи, настройка["грамматика"], настройка.get("класс", ""))}</section>'
    )


def блок_лента(данные: dict, настройка: dict) -> str:
    """Лента по дате добавления. Без доказанной даты запись в ленту не идёт."""
    свежие = [
        з for з in данные["items"]
        if з.get("published_at") and not з.get("published_at_estimated")
    ]
    свежие.sort(key=lambda з: з["published_at"], reverse=True)
    записи = свежие[: настройка.get("максимум", 8)]
    if len(записи) < настройка.get("минимум", 1):
        return ""
    return (
        f'<section class="sec"><h2 class="sec__t">{э(настройка["заголовок"])}</h2>'
        f'{_сетка(записи, настройка.get("грамматика", "compact"), настройка.get("класс", ""))}'
        f"</section>"
    )


def блок_таксономия(данные: dict, настройка: dict) -> str:
    """Навигация по тому, что в данных ЕСТЬ: виды и годы. Жанров в каталоге нет."""
    вид = настройка.get("источник", "kinds")
    значения = данные.get(вид) or []
    if not значения:
        return ""
    ссылки = "".join(
        f'<a class="chip" href="/{э(вид)}/{э(з)}/">{э(з)}</a>' for з in значения[:12]
    )
    return (
        f'<section class="sec"><h2 class="sec__t">{э(настройка["заголовок"])}</h2>'
        f'<nav class="chips">{ссылки}</nav></section>'
    )


def блок_текст(данные: dict, настройка: dict) -> str:
    return (
        f'<section class="sec sec--about"><h2 class="sec__t">{э(настройка["заголовок"])}</h2>'
        f'<p class="about__p">{э(настройка["текст"])}</p></section>'
    )


def блок_ранжированный(данные: dict, настройка: dict) -> str:
    """Нумерованный список. Номер — позиция, а не оценка.

    Оценок в источнике нет. Назвать позицию в списке рейтингом значило бы
    выдумать величину, которой не существует, поэтому подпись блока обязана
    говорить о порядке, а не о качестве.
    """
    записи = данные["items"][настройка.get("сдвиг", 0):][: настройка.get("максимум", 10)]
    if len(записи) < настройка.get("минимум", 3):
        return ""
    карточки = "".join(карточка_ранг(з, i) for i, з in enumerate(записи, 1))
    класс = настройка.get("класс", "")
    return (
        f'<section class="sec"><h2 class="sec__t">{э(настройка["заголовок"])}</h2>'
        f'<ol class="g g--ranked {э(класс)}">{карточки}</ol></section>'
    )


def блок_доска(данные: dict, настройка: dict) -> str:
    """Колонки по видам: каждая группа — свой столбец с собственным заголовком.

    Группы берутся из данных, а не назначаются: вид есть в каталоге, и пустая
    колонка невозможна по построению.
    """
    по_видам: dict[str, list[dict]] = {}
    for з in данные["items"]:
        вид = з.get("kind")
        if вид:
            по_видам.setdefault(вид, []).append(з)
    группы = [(в, зз) for в, зз in по_видам.items()
              if len(зз) >= настройка.get("минимум_в_группе", 2)]
    if len(группы) < настройка.get("минимум", 2):
        return ""
    предел = настройка.get("максимум_в_группе", 5)
    грамматика = настройка.get("грамматика", "tile")
    строитель = КАРТОЧКИ[грамматика]
    столбцы = "".join(
        f'<div class="board__col"><h3 class="board__t">{э(вид)}</h3>'
        f'<div class="board__items">{"".join(строитель(з) for з in зз[:предел])}</div></div>'
        for вид, зз in группы
    )
    return (
        f'<section class="sec"><h2 class="sec__t">{э(настройка["заголовок"])}</h2>'
        f'<div class="board {э(настройка.get("класс", ""))}">{столбцы}</div></section>'
    )


def блок_мозаика(данные: dict, настройка: dict) -> str:
    """Мозаика с объявленными пролётами: первая карточка крупнее остальных.

    Пролёты объявлены классом, а не вычисляются на лету: масонри с прыгающими
    высотами даёт разный макет при одинаковых данных, и сравнивать снимки
    становится нечем.
    """
    записи = данные["items"][настройка.get("сдвиг", 0):][: настройка.get("максимум", 7)]
    if len(записи) < настройка.get("минимум", 4):
        return ""
    грамматика = настройка.get("грамматика", "poster")
    строитель = КАРТОЧКИ[грамматика]
    первая = строитель(записи[0]).replace('class="k ', 'class="k k--lead ', 1)
    прочие = "".join(строитель(з) for з in записи[1:])
    return (
        f'<section class="sec"><h2 class="sec__t">{э(настройка["заголовок"])}</h2>'
        f'<div class="g g--{э(грамматика)} mosaic {э(настройка.get("класс", ""))}">'
        f'{первая}{прочие}</div></section>'
    )


def блок_индекс(данные: dict, настройка: dict) -> str:
    """Текстовый индекс по первой букве. Навигация вместо витрины."""
    буквы: dict[str, int] = {}
    for з in данные["items"]:
        название = (з.get("title") or "").strip()
        if название:
            буквы[название[0].upper()] = буквы.get(название[0].upper(), 0) + 1
    if len(буквы) < настройка.get("минимум", 4):
        return ""
    ссылки = "".join(
        f'<a class="chip idx__l" href="/letter/{э(б)}/">{э(б)}'
        f'<span class="idx__n">{n}</span></a>'
        for б, n in sorted(буквы.items())
    )
    return (
        f'<section class="sec"><h2 class="sec__t">{э(настройка["заголовок"])}</h2>'
        f'<nav class="chips idx {э(настройка.get("класс", ""))}">{ссылки}</nav></section>'
    )


def блок_разворот(данные: dict, настройка: dict) -> str:
    """Асимметричный разворот: одна крупная запись слева, список справа."""
    записи = данные["items"][настройка.get("сдвиг", 0):][: настройка.get("максимум", 7)]
    if len(записи) < настройка.get("минимум", 4):
        return ""
    ведущая, прочие = записи[0], записи[1:]
    грамматика = настройка.get("грамматика", "compact")
    строитель = КАРТОЧКИ[грамматика]
    постер = ведущая.get("poster")
    медиа = (
        f'<img class="split__img" src="{э(постер)}" alt="" loading="lazy" width="200" height="300">'
        if постер else '<span class="k__none" aria-hidden="true"></span>'
    )
    подпись = " · ".join(str(x) for x in (ведущая.get("kind"), ведущая.get("year")) if x)
    return (
        f'<section class="sec split {э(настройка.get("класс", ""))}">'
        f'<h2 class="sec__t">{э(настройка["заголовок"])}</h2>'
        f'<div class="split__in">'
        f'<a class="split__lead" href="{э(ведущая["url"])}" title="{э(ведущая["title"])}">'
        f'<span class="split__media">{медиа}</span>'
        f'<span class="split__cap"><span class="k__t">{э(ведущая["title"])}</span>'
        f'<span class="k__sub">{э(подпись)}</span></span></a>'
        f'<div class="split__list">{"".join(строитель(з) for з in прочие)}</div>'
        f"</div></section>"
    )


БЛОКИ = {
    "hero": блок_герой,
    "grid": блок_сетка,
    "feed": блок_лента,
    "taxonomy": блок_таксономия,
    "about": блок_текст,
    "ranked": блок_ранжированный,
    "board": блок_доска,
    "mosaic": блок_мозаика,
    "index": блок_индекс,
    "split": блок_разворот,
}


# --- страница ---------------------------------------------------------------

СКЕЛЕТ = """<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<link rel="canonical" href="https://{домен}/">
<title>{титул}</title>
<style>{стили}</style></head>
<body data-template="{template_id}" data-design="{slug}">
<header class="hd"><a class="hd__brand" href="/">{бренд}</a>
<nav class="hd__nav">{навигация}</nav>
<form class="hd__s" role="search"><input class="hd__i" type="search" aria-label="Поиск"
 placeholder="Поиск"></form></header>
<main class="wrap">{тело}</main>
<footer class="ft"><p class="ft__p">{подвал}</p></footer>
</body></html>"""


def собрать_стили(пакет: pathlib.Path, ядро: pathlib.Path) -> str:
    части = [(ядро / "core.css").read_text(encoding="utf-8")]
    for имя in ("tokens.css", "layout.css", "components.css"):
        файл = пакет / имя
        if файл.is_file():
            части.append(файл.read_text(encoding="utf-8"))
    return "\n".join(части)


def отрисовать(пакет_каталог: pathlib.Path, фикстура: dict,
               ядро: pathlib.Path | None = None) -> str:
    ядро = ядро or pathlib.Path(__file__).resolve().parent
    манифест = json.loads((пакет_каталог / "template.json").read_text(encoding="utf-8"))

    тело = []
    for блок in манифест["home_block_order"]:
        строитель = БЛОКИ.get(блок["тип"])
        if строитель is None:
            raise ValueError(f"{манифест['template_id']}: неизвестный блок {блок['тип']!r}")
        тело.append(строитель(фикстура, блок))

    навигация = "".join(
        f'<a class="hd__l" href="{э(п["url"])}">{э(п["подпись"])}</a>'
        for п in манифест["navigation"]
    )
    return СКЕЛЕТ.format(
        домен=э(манифест.get("preview_domain", "lords.example")),
        титул=э(манифест["title"]),
        стили=собрать_стили(пакет_каталог, ядро),
        template_id=э(манифест["template_id"]),
        slug=э(манифест["slug"]),
        бренд=э(манифест["brand"]),
        навигация=навигация,
        тело="".join(тело),
        подвал=э(манифест["footer"]),
    )
