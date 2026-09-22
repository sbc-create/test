#!/usr/bin/env python3
"""Общее ядро отрисовки шаблонных пакетов Lords: карточки, блоки, маршруты.

## Граница ответственности

Ядро владеет тем, что не должно различаться между шаблонами и не может быть
отдано пакету без риска: экранирование, скелет документа, канонический адрес,
политика индексации, порядок заголовков, честное поведение при нехватке данных
и механика интерактивных компонентов. Пакет владеет композицией — какие блоки,
в каком порядке, какой грамматикой карточек, с какими токенами и по какой
стратегии собирается каждый маршрут.

Пакет НЕ содержит разметки. Он объявляет блоки, а строит их ядро. Иначе
пятьдесят пакетов стали бы пятьюдесятью копиями одного DOM с разными
переменными — ровно тем, что запрещено.

## Что здесь принадлежит ядру, а что витрине

Маршрутизация (какой адрес какой странице соответствует), выбор данных,
канонический адрес, индексация и коды ответа принадлежат ядру витрины и
проверяются на живых доменах. Пакет владеет ПРЕДСТАВЛЕНИЕМ маршрута: что видно
на каталоге, как устроена страница тайтла, чем отличается сезон от эпизода.
Ровно эту часть здесь и можно проверить честно, и ровно она объявляется
проверенной — не больше.

## Честность при нехватке данных

Фикстура несёт то, что есть в источнике, и явно отмечает, чего в нём нет.
Названий серий нет ни у одной записи — страница эпизода обязана обходиться
номером. Оценка показывается только с источником. Блок, которому нечего
показать, не рисует пустую рамку: он скрывается или честно меняет подпись.
"""

from __future__ import annotations

import html
import json
import pathlib

#: Ширины, на которых пакет обязан оставаться годным. Совпадают с матрицей
#: приёмки: проверять на других значит проверять не то, что принимается.
ТОЧКИ = (320, 390, 768, 1024, 1440, 1920)

#: Сколько карточек на странице каталога. Пагинация настоящая: адреса ведут на
#: соседние страницы, а не подставляют одинаковый список.
НА_СТРАНИЦЕ = 24


def э(значение) -> str:
    """Экранирование. Единственная точка: пакет до разметки не допущен."""
    return html.escape("" if значение is None else str(значение), quote=True)


# --- общие представления полей ----------------------------------------------

def _постер(запись: dict) -> str | None:
    return запись.get("poster_local") or запись.get("poster")


def подпись_мета(запись: dict, полей: int = 3) -> str:
    """Год, вид и число сезонов — то, что подтверждено записью."""
    части = []
    if запись.get("year"):
        части.append(str(запись["year"]))
    if запись.get("kind"):
        части.append(str(запись["kind"]))
    сезонов = запись.get("seasons_count")
    if сезонов:
        окончание = "" if сезонов == 1 else ("а" if сезонов < 5 else "ов")
        части.append(f"{сезонов} сезон{окончание}")
    return " · ".join(части[:полей])


def оценка_html(запись: dict, класс: str = "k__r") -> str:
    """Оценка рисуется только вместе с источником.

    Источник не украшение: число без него — утверждение, за которое никто не
    отвечает. Поэтому подпись содержит имя источника, а полное происхождение
    (провайдер, число голосов, дата получения) уходит в `title`.
    """
    оценки = запись.get("ratings") or {}
    for имя in ("imdb", "kp", "kinopoisk"):
        тело = оценки.get(имя)
        if not тело:
            continue
        подпись = {"imdb": "IMDb", "kp": "КП", "kinopoisk": "КП"}[имя]
        голоса = f", голосов {тело['votes']}" if тело.get("votes") else ""
        происхождение = f"{подпись} {тело['value']} из 10{голоса}; " \
                        f"источник {тело.get('provider') or имя}"
        return (f'<span class="{э(класс)}" title="{э(происхождение)}">'
                f'<span class="k__rs">{э(подпись)}</span>'
                f'<span class="k__rv">{э(тело["value"])}</span></span>')
    return ""


def жанры_html(запись: dict, предел: int = 3, класс: str = "k__g") -> str:
    жанры = (запись.get("genres") or [])[:предел]
    if not жанры:
        return ""
    внутри = "".join(f'<span class="k__gi">{э(ж)}</span>' for ж in жанры)
    return f'<span class="{э(класс)}">{внутри}</span>'


def _данные(запись: dict) -> str:
    """Атрибуты для фильтра, сортировки и поиска: разметка сама себе индекс."""
    оценки = запись.get("ratings") or {}
    первая = next((т["value"] for т in оценки.values() if т.get("value")), "")
    return (
        f' data-t="{э((запись.get("title") or "").lower())}"'
        f' data-y="{э(запись.get("year") or "")}"'
        f' data-k="{э(запись.get("kind") or "")}"'
        f' data-g="{э("|".join(запись.get("genres") or []))}"'
        f' data-c="{э("|".join(запись.get("countries") or []))}"'
        f' data-r="{э(первая)}"'
        f' data-a="{э((запись.get("published_at") or "")[:10])}"'
    )


def _медиа(запись: dict, ширина: int, высота: int, класс: str = "k__img") -> str:
    постер = _постер(запись)
    if not постер:
        # Чужую картинку сюда ставить нельзя: пустое место честнее подмены.
        return '<span class="k__none" aria-hidden="true"></span>'
    return (f'<img class="{э(класс)}" src="{э(постер)}" alt="" loading="lazy" '
            f'decoding="async" width="{ширина}" height="{высота}">')


# --- карточки ---------------------------------------------------------------

def карточка_постер(запись: dict) -> str:
    год = f'<span class="k__y">{э(запись["year"])}</span>' if запись.get("year") else ""
    return (
        f'<a class="k k--poster" href="{э(запись["url"])}"{_данные(запись)}>'
        f'<span class="k__p">{_медиа(запись, 200, 300)}{оценка_html(запись, "k__badge")}</span>'
        f'<span class="k__cap"><span class="k__t">{э(запись["title"])}</span>{год}</span>'
        f"</a>"
    )


def карточка_компакт(запись: dict) -> str:
    """Строка-карточка: миниатюра слева, подпись и метаданные друг под другом.

    Совмещение подписи и даты в один ряд отбирало у подписи ширину и обрезало
    обязательную дату — на живой витрине это стоило отдельного разбора.
    """
    дата = ""
    if запись.get("published_at") and not запись.get("published_at_estimated"):
        дата = (f'<time class="k__d" datetime="{э(запись["published_at"])}">'
                f'{э(str(запись["published_at"])[:10])}</time>')
    вид = f'<span class="k__k">{э(запись["kind"])}</span>' if запись.get("kind") else ""
    return (
        f'<a class="k k--compact" href="{э(запись["url"])}"{_данные(запись)}>'
        f'<span class="k__p">{_медиа(запись, 64, 96)}</span>'
        f'<span class="k__cap"><span class="k__t">{э(запись["title"])}</span></span>'
        f'<span class="k__meta">{вид}{дата}</span>'
        f"</a>"
    )


def карточка_редакционная(запись: dict) -> str:
    подзаголовок = " · ".join(
        str(x) for x in (запись.get("kind"), запись.get("year")) if x)
    строка = f'<span class="k__sub">{э(подзаголовок)}</span>' if подзаголовок else ""
    return (
        f'<a class="k k--editorial" href="{э(запись["url"])}"{_данные(запись)}>'
        f'<span class="k__p">{_медиа(запись, 200, 300)}</span>'
        f'<span class="k__cap"><span class="k__t">{э(запись["title"])}</span>{строка}'
        f'{жанры_html(запись, 2)}</span>'
        f"</a>"
    )


def карточка_богатая(запись: dict) -> str:
    """Постер, оценка с источником и жанры — всё, что подтверждено записью."""
    подпись = " · ".join(str(x) for x in (запись.get("year"), запись.get("kind")) if x)
    return (
        f'<a class="k k--rich" href="{э(запись["url"])}"{_данные(запись)}>'
        f'<span class="k__p">{_медиа(запись, 200, 300)}</span>'
        f'<span class="k__cap"><span class="k__t">{э(запись["title"])}</span>'
        f'<span class="k__sub">{э(подпись)}</span>'
        f'<span class="k__row">{оценка_html(запись)}{жанры_html(запись, 2)}</span>'
        f'</span></a>'
    )


def карточка_строка(запись: dict) -> str:
    """Строка перечня: заголовок, год, жанры и оценка в колонках."""
    жанры = ", ".join((запись.get("genres") or [])[:2])
    return (
        f'<a class="k k--row" href="{э(запись["url"])}"{_данные(запись)}>'
        f'<span class="k__t">{э(запись["title"])}</span>'
        f'<span class="k__c1">{э(запись.get("year") or "—")}</span>'
        f'<span class="k__c2">{э(запись.get("kind") or "—")}</span>'
        f'<span class="k__c3">{э(жанры or "—")}</span>'
        f'<span class="k__c4">{оценка_html(запись) or "—"}</span>'
        f"</a>"
    )


def карточка_плитка(запись: dict) -> str:
    """Текстовая плитка без изображения: для индексов и досок."""
    год = f'<span class="k__y">{э(запись["year"])}</span>' if запись.get("year") else ""
    return (
        f'<a class="k k--tile" href="{э(запись["url"])}"{_данные(запись)}>'
        f'<span class="k__cap"><span class="k__t">{э(запись["title"])}</span>{год}</span>'
        f"</a>"
    )


def карточка_ранг(запись: dict, номер: int = 0) -> str:
    """Карточка с рангом. Номер — позиция в списке, а не оценка."""
    подпись = " · ".join(str(x) for x in (запись.get("kind"), запись.get("year")) if x)
    строка = f'<span class="k__sub">{э(подпись)}</span>' if подпись else ""
    return (
        f'<a class="k k--ranked" href="{э(запись["url"])}"{_данные(запись)}>'
        f'<span class="k__n" aria-hidden="true">{номер}</span>'
        f'<span class="k__cap"><span class="k__t">{э(запись["title"])}</span>{строка}</span>'
        f'{оценка_html(запись)}</a>'
    )


КАРТОЧКИ = {
    "poster": карточка_постер,
    "compact": карточка_компакт,
    "editorial": карточка_редакционная,
    "tile": карточка_плитка,
    "rich": карточка_богатая,
    "row": карточка_строка,
}


# --- блоки ------------------------------------------------------------------

def _сетка(записи: list[dict], грамматика: str, класс: str) -> str:
    строитель = КАРТОЧКИ[грамматика]
    карточки = "".join(строитель(з) for з in записи)
    return f'<div class="g g--{э(грамматика)} {э(класс)}">{карточки}</div>'


def _срез(вид: dict, настройка: dict, по_умолчанию: int = 12) -> list[dict]:
    """Записи блока.

    Обычно блок показывает записи своего маршрута. Но на пустой выдаче и на
    404 показывать «из каталога» записи маршрута нечего — их там ноль, и блок
    молча исчезал бы, оставляя страницу без выхода. Поэтому блок может явно
    объявить источником весь каталог.
    """
    источник = (вид["catalog_items"] if настройка.get("источник") == "catalog"
                else вид["items"])
    записи = источник[настройка.get("сдвиг", 0):]
    return без_хвоста(записи[: настройка.get("максимум", по_умолчанию)],
                      настройка.get("колонки"), настройка.get("минимум", 1),
                      настройка.get("тип", "grid"))


def без_хвоста(записи: list[dict], колонки: list[int] | None,
               минимум: int, тип: str = "grid") -> list[dict]:
    """Отрезает столько, чтобы в последнем ряду не осталась одна карточка.

    Данные не всегда дают ровно столько записей, сколько просит композиция:
    у жанра их может оказаться семь при сетке в три колонки. Тогда честнее
    показать шесть, чем оставить в конце сетки дыру шириной в две колонки.
    Ниже объявленного минимума блок не опускается — он просто исчезает, и это
    решает вызывающий.
    """
    if not колонки or len(записи) <= минимум:
        return записи
    добавка = 3 if тип == "mosaic" else 0
    сколько = len(записи)
    while сколько > минимум:
        if not any(к >= 3 and (сколько + добавка) % к == 1 for к in колонки):
            break
        сколько -= 1
    return записи[:сколько]


def блок_герой(вид: dict, настройка: dict) -> str:
    записи = вид["items"][: настройка.get("максимум", 1)]
    if not записи:
        return ""
    первая = записи[0]
    подпись = " · ".join(str(x) for x in (первая.get("kind"), первая.get("year")) if x)
    жанры = ", ".join((первая.get("genres") or [])[:3])
    описание = (первая.get("short_description") or первая.get("description") or "")[:220]
    return (
        f'<section class="sec hero"><div class="hero__media">'
        f'{_медиа(первая, 200, 300, "hero__img")}</div>'
        f'<div class="hero__body"><p class="hero__eyebrow">{э(настройка["заголовок"])}</p>'
        f'<h2 class="hero__t">{э(первая["title"])}</h2>'
        f'<p class="hero__sub">{э(подпись)}{" · " + э(жанры) if жанры else ""}</p>'
        + (f'<p class="hero__d">{э(описание)}</p>' if описание else "")
        + (f'<p class="hero__meta">{оценка}</p>'
           if (оценка := оценка_html(первая, "hero__r")) else "")
        + f'<a class="hero__cta" href="{э(первая["url"])}">Смотреть</a></div></section>'
    )


def блок_сетка(вид: dict, настройка: dict) -> str:
    записи = _срез(вид, настройка)
    if len(записи) < настройка.get("минимум", 1):
        return ""  # Блок скрывается, а не рисует пустые ячейки.
    return (
        f'<section class="sec"><h2 class="sec__t">{э(настройка["заголовок"])}</h2>'
        f'{_сетка(записи, настройка["грамматика"], настройка.get("класс", ""))}</section>'
    )


def блок_лента(вид: dict, настройка: dict) -> str:
    """Лента по дате добавления. Без доказанной даты запись в ленту не идёт."""
    свежие = [з for з in вид["items"]
              if з.get("published_at") and not з.get("published_at_estimated")]
    свежие.sort(key=lambda з: з["published_at"], reverse=True)
    записи = без_хвоста(свежие[: настройка.get("максимум", 8)],
                        настройка.get("колонки"), настройка.get("минимум", 1))
    if len(записи) < настройка.get("минимум", 1):
        return ""
    return (
        f'<section class="sec"><h2 class="sec__t">{э(настройка["заголовок"])}</h2>'
        f'{_сетка(записи, настройка.get("грамматика", "compact"), настройка.get("класс", ""))}'
        f"</section>"
    )


def блок_таксономия(вид: dict, настройка: dict) -> str:
    """Навигация по тому, что в данных есть: виды, жанры, годы, страны."""
    источник = настройка.get("источник", "kinds")
    значения = (вид["taxonomies"].get(источник) or [])[: настройка.get("максимум", 12)]
    if not значения:
        return ""
    основа = {"kinds": "/catalog/?kind=", "genres": "/genre/", "years": "/year/",
              "countries": "/country/"}[источник]
    ссылки = "".join(
        f'<a class="chip" href="{э(основа)}{э(з["slug"])}{"" if источник == "kinds" else "/"}">'
        f'{э(з["name"])}<span class="chip__n">{з["count"]}</span></a>'
        for з in значения)
    return (
        f'<section class="sec"><h2 class="sec__t">{э(настройка["заголовок"])}</h2>'
        f'<nav class="chips {э(настройка.get("класс", ""))}" '
        f'aria-label="{э(настройка["заголовок"])}">{ссылки}</nav></section>'
    )


def блок_текст(вид: dict, настройка: dict) -> str:
    return (
        f'<section class="sec sec--about"><h2 class="sec__t">{э(настройка["заголовок"])}</h2>'
        f'<p class="about__p">{э(настройка["текст"])}</p></section>'
    )


def блок_ранжированный(вид: dict, настройка: dict) -> str:
    """Нумерованный список. Номер — позиция, а не оценка."""
    записи = _срез(вид, настройка, 10)
    if len(записи) < настройка.get("минимум", 3):
        return ""
    карточки = "".join(карточка_ранг(з, i) for i, з in enumerate(записи, 1))
    return (
        f'<section class="sec"><h2 class="sec__t">{э(настройка["заголовок"])}</h2>'
        f'<ol class="g g--ranked {э(настройка.get("класс", ""))}">{карточки}</ol></section>'
    )


def блок_доска(вид: dict, настройка: dict) -> str:
    """Колонки по группам данных: вид или жанр. Пустая колонка невозможна."""
    поле = настройка.get("по", "kind")
    группы: dict[str, list[dict]] = {}
    for з in вид["items"]:
        значения = з.get(поле) if поле != "kind" else [з.get("kind")]
        for значение in (значения or []):
            if значение:
                группы.setdefault(значение, []).append(з)
    годные = [(и, зз) for и, зз in группы.items()
              if len(зз) >= настройка.get("минимум_в_группе", 2)]
    годные.sort(key=lambda п: -len(п[1]))
    годные = годные[: настройка.get("колонок", 4)]
    if len(годные) < настройка.get("минимум", 2):
        return ""
    предел = настройка.get("максимум_в_группе", 5)
    строитель = КАРТОЧКИ[настройка.get("грамматика", "tile")]
    столбцы = "".join(
        f'<div class="board__col"><h3 class="board__t">{э(имя)}</h3>'
        f'<div class="board__items">{"".join(строитель(з) for з in зз[:предел])}</div></div>'
        for имя, зз in годные)
    return (
        f'<section class="sec"><h2 class="sec__t">{э(настройка["заголовок"])}</h2>'
        f'<div class="board {э(настройка.get("класс", ""))}">{столбцы}</div></section>'
    )


def блок_мозаика(вид: dict, настройка: dict) -> str:
    """Мозаика с объявленными пролётами: первая карточка крупнее остальных."""
    записи = _срез(вид, настройка, 7)
    if len(записи) < настройка.get("минимум", 4):
        return ""
    строитель = КАРТОЧКИ[настройка.get("грамматика", "poster")]
    первая = строитель(записи[0]).replace('class="k ', 'class="k k--lead ', 1)
    прочие = "".join(строитель(з) for з in записи[1:])
    return (
        f'<section class="sec"><h2 class="sec__t">{э(настройка["заголовок"])}</h2>'
        f'<div class="g g--{э(настройка.get("грамматика", "poster"))} mosaic '
        f'{э(настройка.get("класс", ""))}">{первая}{прочие}</div></section>'
    )


def блок_индекс(вид: dict, настройка: dict) -> str:
    """Текстовый индекс по первой букве. Навигация вместо витрины."""
    буквы: dict[str, int] = {}
    for з in вид["items"]:
        название = (з.get("title") or "").strip()
        if название:
            буквы[название[0].upper()] = буквы.get(название[0].upper(), 0) + 1
    if len(буквы) < настройка.get("минимум", 4):
        return ""
    ссылки = "".join(
        f'<a class="chip idx__l" href="/letter/{э(б)}/">{э(б)}'
        f'<span class="idx__n">{n}</span></a>' for б, n in sorted(буквы.items()))
    return (
        f'<section class="sec"><h2 class="sec__t">{э(настройка["заголовок"])}</h2>'
        f'<nav class="chips idx {э(настройка.get("класс", ""))}" '
        f'aria-label="{э(настройка["заголовок"])}">{ссылки}</nav></section>'
    )


def блок_разворот(вид: dict, настройка: dict) -> str:
    """Асимметричный разворот: одна крупная запись слева, список справа."""
    записи = _срез(вид, настройка, 7)
    if len(записи) < настройка.get("минимум", 4):
        return ""
    ведущая, прочие = записи[0], записи[1:]
    строитель = КАРТОЧКИ[настройка.get("грамматика", "compact")]
    подпись = " · ".join(str(x) for x in (ведущая.get("kind"), ведущая.get("year")) if x)
    return (
        f'<section class="sec split {э(настройка.get("класс", ""))}">'
        f'<h2 class="sec__t">{э(настройка["заголовок"])}</h2>'
        f'<div class="split__in">'
        f'<a class="split__lead" href="{э(ведущая["url"])}"{_данные(ведущая)}>'
        f'<span class="split__media">{_медиа(ведущая, 200, 300, "split__img")}</span>'
        f'<span class="split__cap"><span class="k__t">{э(ведущая["title"])}</span>'
        f'<span class="k__sub">{э(подпись)}</span>{оценка_html(ведущая)}</span></a>'
        f'<div class="split__list">{"".join(строитель(з) for з in прочие)}</div>'
        f"</div></section>"
    )


def блок_полоса(вид: dict, настройка: dict) -> str:
    """Настоящая прокручиваемая полоса.

    Стрелки здесь НЕ рисуются. Их добавляет ядро интерактивности и только
    тогда, когда прокручивать действительно есть что. Нарисованная стрелка,
    которая ничего не делает, — обман, и в разметке её быть не должно.
    Без скриптов полоса остаётся годной: это обычная прокрутка пальцем и
    колесом, с доступом с клавиатуры через сами карточки.
    """
    записи = _срез(вид, настройка, 14)
    if len(записи) < настройка.get("минимум", 3):
        return ""
    строитель = КАРТОЧКИ[настройка.get("грамматика", "poster")]
    карточки = "".join(строитель(з) for з in записи)
    подпись = э(настройка["заголовок"])
    return (
        f'<section class="sec rail" data-lx="rail">'
        f'<div class="rail__hd"><h2 class="sec__t">{подпись}</h2>'
        f'<div class="rail__nav" data-lx-nav hidden></div></div>'
        f'<div class="rail__track {э(настройка.get("класс", ""))}" data-lx-track '
        f'tabindex="0" role="group" aria-label="{подпись}: прокручиваемая полоса">'
        f'{карточки}</div></section>'
    )


def блок_фильтры(вид: dict, настройка: dict) -> str:
    """Панель фильтров и сортировки, которая действительно фильтрует.

    Значения берутся из показанных записей, поэтому фильтр не может дать
    пустоту «из-за опечатки в списке». Состояние объявляется через
    `aria-pressed`, а изменившееся число результатов — через живую область.
    """
    поле = настройка.get("источник", "genres")
    счёт: dict[str, int] = {}
    for з in вид["items"]:
        значения = з.get(поле) if поле != "kinds" else [з.get("kind")]
        for значение in (значения or []):
            if значение:
                счёт[значение] = счёт.get(значение, 0) + 1
    значения = sorted(счёт.items(), key=lambda п: (-п[1], п[0]))[: настройка.get("максимум", 8)]
    if len(значения) < 2:
        return ""
    ключ = {"genres": "g", "countries": "c", "kinds": "k"}[поле]
    кнопки = "".join(
        f'<button class="chip chip--f" type="button" data-lx-filter="{э(ключ)}" '
        f'data-value="{э(имя)}" aria-pressed="false">{э(имя)}'
        f'<span class="chip__n">{n}</span></button>' for имя, n in значения)
    сортировка = (
        '<label class="tools__sort"><span class="tools__lb">Сортировка</span>'
        '<select class="tools__sel" data-lx-sort>'
        '<option value="default">по каталогу</option>'
        '<option value="year">по году</option>'
        '<option value="title">по названию</option>'
        '<option value="rating">по оценке</option>'
        '<option value="added">по дате добавления</option></select></label>'
    ) if настройка.get("сортировка", True) else ""
    return (
        f'<section class="sec tools" data-lx="tools">'
        f'<h2 class="sec__t">{э(настройка["заголовок"])}</h2>'
        f'<div class="tools__in"><div class="chips tools__chips">{кнопки}'
        f'<button class="chip chip--r" type="button" data-lx-reset hidden>Сбросить</button>'
        f'</div>{сортировка}</div>'
        f'<p class="tools__live" data-lx-live role="status" aria-live="polite">'
        f'Показано {len(вид["items"])}</p></section>'
    )


def блок_перечень(вид: dict, настройка: dict) -> str:
    """Тело каталога: сетка выбранной грамматики и настоящая пагинация.

    Пагинация серверная: соседняя страница — это другой адрес и другой набор
    записей. Кнопка, которая никуда не ведёт, в разметке не появляется —
    на первой странице нет «назад», на последней нет «вперёд».
    """
    записи = вид["items"]
    страница = вид.get("page", 1)
    на_странице = вид.get("per_page") or настройка.get("на_странице", НА_СТРАНИЦЕ)
    всего = вид.get("total", len(записи))
    страниц = max(1, -(-всего // на_странице))
    if not записи:
        return (
            f'<section class="sec empty"><h2 class="sec__t">{э(настройка["заголовок"])}</h2>'
            f'<p class="empty__p">{э(настройка.get("пусто", "Записей нет."))}</p></section>'
        )
    грамматика = настройка.get("грамматика", "poster")
    тело = (_сетка(записи, грамматика, настройка.get("класс", ""))
            if грамматика != "row" else _таблица(записи, настройка))
    навигация = _пагинация(вид, страница, страниц)
    return (
        f'<section class="sec listing" data-lx="listing">'
        f'<h2 class="sec__t">{э(настройка["заголовок"])}</h2>'
        f'{тело}'
        f'<p class="listing__none" data-lx-none hidden role="status">'
        f'Под выбранные условия не подошла ни одна запись.</p>'
        f'{навигация}</section>'
    )


def _таблица(записи: list[dict], настройка: dict) -> str:
    шапка = ('<div class="g__hd" aria-hidden="true"><span>Название</span>'
             '<span>Год</span><span>Тип</span><span>Жанры</span><span>Оценка</span></div>')
    строки = "".join(карточка_строка(з) for з in записи)
    return f'<div class="g g--row {э(настройка.get("класс", ""))}">{шапка}{строки}</div>'


def _пагинация(вид: dict, страница: int, страниц: int) -> str:
    if страниц < 2:
        return ""
    основа = вид.get("base_url", "/catalog/")
    def адрес(n: int) -> str:
        return основа if n == 1 else f"{основа}?page={n}"
    части = []
    if страница > 1:
        части.append(f'<a class="pg__l pg__prev" href="{э(адрес(страница - 1))}" '
                     f'rel="prev">Назад</a>')
    for n in range(1, страниц + 1):
        if n == страница:
            части.append(f'<span class="pg__l pg__now" aria-current="page">{n}</span>')
        else:
            части.append(f'<a class="pg__l" href="{э(адрес(n))}">{n}</a>')
    if страница < страниц:
        части.append(f'<a class="pg__l pg__next" href="{э(адрес(страница + 1))}" '
                     f'rel="next">Вперёд</a>')
    return (f'<nav class="pg" aria-label="Страницы каталога">{"".join(части)}</nav>')


def блок_поиск(вид: dict, настройка: dict) -> str:
    """Страница поиска: запрос, число результатов и честная пустая выдача."""
    запрос = вид.get("query", "")
    записи = вид["items"]
    поле = (
        f'<form class="srch" action="/search/" method="get" role="search">'
        f'<label class="srch__lb" for="q">Поиск по каталогу</label>'
        f'<input class="srch__i" id="q" name="q" type="search" value="{э(запрос)}" '
        f'data-lx-search placeholder="Название">'
        f'<button class="srch__b" type="submit">Найти</button></form>'
    )
    if not записи:
        return (
            f'<section class="sec empty"><h1 class="sec__t">Ничего не найдено</h1>{поле}'
            f'<p class="empty__p">По запросу «{э(запрос)}» в каталоге нет ни одной записи. '
            f'Проверьте написание или откройте <a class="lnk" href="/catalog/">каталог</a>.</p>'
            f'</section>'
        )
    return (
        f'<section class="sec" data-lx="listing"><h1 class="sec__t">'
        f'Найдено {len(записи)} по запросу «{э(запрос)}»</h1>{поле}'
        f'{_сетка(записи, настройка.get("грамматика", "compact"), настройка.get("класс", ""))}'
        f'<p class="listing__none" data-lx-none hidden role="status">'
        f'Под выбранные условия не подошла ни одна запись.</p></section>'
    )


# --- страница тайтла --------------------------------------------------------

def блок_карточка_тайтла(вид: dict, настройка: dict) -> str:
    """Шапка страницы фильма или сериала.

    Показывается ровно то, что есть в записи. Нет описания — нет блока
    описания, а не «Описание отсутствует» в рамке на пол-экрана. Длинное
    описание сворачивается настоящим раскрытием с `aria-expanded`, а не
    обрезается насовсем.
    """
    з = вид["entity"]
    факты = []
    if з.get("year"):
        факты.append(("Год", str(з["year"])))
    if з.get("kind"):
        факты.append(("Тип", з["kind"]))
    if з.get("countries"):
        факты.append(("Страна", ", ".join(з["countries"][:3])))
    if з.get("genres"):
        факты.append(("Жанры", ", ".join(з["genres"][:4])))
    if з.get("seasons"):
        серий = sum(с["eps"] or 0 for с in з["seasons"])
        факты.append(("Сезоны", f"{len(з['seasons'])}, серий {серий}"))
    if з.get("duration"):
        факты.append(("Длительность", f"{з['duration']} мин"))
    if з.get("original_name"):
        факты.append(("Оригинал", з["original_name"]))
    таблица = "".join(
        f'<div class="ft__r"><dt class="ft__k">{э(к)}</dt><dd class="ft__v">{э(v)}</dd></div>'
        for к, v in факты)

    описание = з.get("description") or ""
    длинное = len(описание) > 320
    тело_описания = ""
    if описание:
        тело_описания = (
            f'<div class="ttl__d{" ttl__d--cut" if длинное else ""}"'
            + (' data-lx-more id="ttl-d"' if длинное else "")
            + f'><p class="ttl__p">{э(описание)}</p></div>'
        )
        if длинное:
            тело_описания += (
                '<button class="ttl__more" type="button" data-lx-more-btn '
                'aria-expanded="false" aria-controls="ttl-d">Читать полностью</button>')

    смотреть = ""
    if з.get("playable"):
        цель = (f'{з["url"]}season-1/episode-1/' if з.get("seasons") else f'{з["url"]}watch/')
        смотреть = f'<a class="ttl__cta" href="{э(цель)}">Смотреть</a>'

    классы = ("sec ttl " + (настройка.get("класс") or "")).strip()
    подпись = " · ".join(str(x) for x in (з.get("year"), з.get("kind")) if x)
    оценка = оценка_html(з, "ttl__rating")
    return (
        f'<section class="{э(классы)}">'
        f'<div class="ttl__media">{_медиа(з, 300, 450, "ttl__img")}</div>'
        f'<div class="ttl__body"><h1 class="ttl__t">{э(з["title"])}</h1>'
        + (f'<p class="ttl__sub">{э(подпись)}</p>' if подпись else "")
        + (f'<p class="ttl__r">{оценка}</p>' if оценка else "")
        + смотреть + тело_описания
        + (f'<dl class="ttl__facts">{таблица}</dl>' if таблица else "")
        + '</div></section>'
    )


def блок_сезоны(вид: dict, настройка: dict) -> str:
    """Сезоны и серии сериала.

    Названий серий в источнике нет ни у одной записи. Поэтому серия честно
    названа номером, а рядом стоит то, что источник подтверждает: сколько
    серий в сезоне и сколько из них доступно. Выдумать заголовок серии было бы
    проще всего — и это была бы ровно та ложь, которую запрещает контракт.
    """
    з = вид["entity"]
    сезоны = з.get("seasons") or []
    if not сезоны:
        return ""
    активный = вид.get("season") or сезоны[0]["n"]
    вкладки, панели = [], []
    for с in сезоны:
        выбран = с["n"] == активный
        вкладки.append(
            f'<button class="tabs__t" type="button" role="tab" '
            f'id="s{с["n"]}-tab" aria-controls="s{с["n"]}" '
            f'aria-selected="{"true" if выбран else "false"}" '
            f'tabindex="{"0" if выбран else "-1"}">Сезон {с["n"]}</button>')
        серий = с["eps"] or 0
        доступно = с["avail"] if с["avail"] is not None else серий
        эпизоды = "".join(
            f'<a class="eps__e{"" if n <= доступно else " eps__e--soon"}" '
            f'href="{э(з["url"])}season-{с["n"]}/episode-{n}/">'
            f'<span class="eps__n">{n}</span>'
            f'<span class="eps__l">серия</span>'
            f'{"" if n <= доступно else "<span class=eps__s>скоро</span>"}</a>'
            for n in range(1, серий + 1))
        итог = (f'{серий} серий, доступно {доступно}' if серий else 'состав сезона не указан')
        панели.append(
            f'<div class="tabs__p" role="tabpanel" id="s{с["n"]}" '
            f'aria-labelledby="s{с["n"]}-tab"{"" if выбран else " hidden"}>'
            f'<p class="eps__sum">{э(итог)}</p>'
            f'<div class="eps">{эпизоды}</div></div>')
    return (
        f'<section class="sec seasons" data-lx="tabs">'
        f'<h2 class="sec__t">{э(настройка.get("заголовок", "Сезоны и серии"))}</h2>'
        f'<div class="tabs__l" role="tablist" aria-label="Сезоны">{"".join(вкладки)}</div>'
        f'{"".join(панели)}</section>'
    )


def блок_плеер(вид: dict, настройка: dict) -> str:
    """Место плеера.

    Пакет владеет рамкой: пропорция, положение, поведение при нажатии и
    отсутствие сдвига макета. Сам источник воспроизведения подключает ядро
    витрины по своему контракту — публикатор и адрес провайдера лежат вне
    пакета и вне репозитория. Автозапуска нет: кадр загружается только после
    действия человека, поэтому до нажатия тяжёлых кадров на странице ноль.
    """
    з = вид["entity"]
    сезон = вид.get("season")
    серия = вид.get("episode")
    подпись = з["title"]
    if сезон and серия:
        подпись = f'{з["title"]} — сезон {сезон}, серия {серия}'
    return (
        f'<section class="sec player" data-lx="player">'
        f'<h2 class="sec__t">{э(настройка.get("заголовок", "Просмотр"))}</h2>'
        f'<div class="player__box" data-player-host data-title="{э(з["slug"])}"'
        f'{f" data-season={сезон} data-episode={серия}" if сезон and серия else ""}>'
        f'<button class="player__go" type="button" data-lx-play '
        f'aria-label="Включить просмотр: {э(подпись)}">'
        f'<span class="player__ico" aria-hidden="true">▶</span>'
        f'<span class="player__lb">Включить просмотр</span></button>'
        f'<p class="player__note" data-lx-state>Источник воспроизведения подключает '
        f'ядро витрины после нажатия. Автозапуска нет.</p></div></section>'
    )


def блок_рекомендации(вид: dict, настройка: dict) -> str:
    """Похожее — только по связям, которые есть в записи.

    Первый источник — `recommendation_ids` самой записи. Если её связи ведут
    за пределы выборки, берётся второй настоящий признак — общий жанр, и
    подпись честно меняется на «Из того же жанра». Чего здесь нет и быть не
    может, так это «похожего на наш вкус»: подборка без основания — выдумка,
    даже если выглядит уместно.
    """
    з = вид["entity"]
    свои = вид["by_slug"]
    заголовок = настройка.get("заголовок", "Похожее")
    записи = [свои[s] for s in (з.get("recommendations") or []) if s in свои]
    if len(записи) < настройка.get("минимум", 3):
        жанры = set(з.get("genres") or [])
        if жанры:
            записи = [д for д in вид["catalog_items"]
                      if д["slug"] != з["slug"] and жанры & set(д.get("genres") or [])]
            заголовок = "Из того же жанра"
        else:
            записи = []
    записи = записи[: настройка.get("максимум", 8)]
    if len(записи) < настройка.get("минимум", 3):
        return ""
    подвид = dict(вид, items=записи)
    строитель = блок_полоса if настройка.get("полосой") else блок_сетка
    return строитель(подвид, dict(настройка, заголовок=заголовок, сдвиг=0,
                                  источник="route", максимум=len(записи), минимум=1))


def блок_крошки(вид: dict, настройка: dict) -> str:
    крошки = вид.get("crumbs") or []
    if len(крошки) < 2:
        return ""
    части = []
    for i, (подпись, адрес) in enumerate(крошки):
        последняя = i == len(крошки) - 1
        внутри = (f'<span aria-current="page">{э(подпись)}</span>' if последняя
                  else f'<a class="bc__a" href="{э(адрес)}">{э(подпись)}</a>')
        части.append(f'<li class="bc__i">{внутри}</li>')
    return (f'<nav class="bc" aria-label="Хлебные крошки"><ol class="bc__l">'
            f'{"".join(части)}</ol></nav>')


def блок_не_найдено(вид: dict, настройка: dict) -> str:
    return (
        f'<section class="sec nf"><h1 class="nf__t">Страница не найдена</h1>'
        f'<p class="nf__p">Такого адреса в каталоге нет. Возможно, запись убрали '
        f'или адрес набран с опечаткой.</p>'
        f'<form class="srch" action="/search/" method="get" role="search">'
        f'<label class="srch__lb" for="q404">Поиск по каталогу</label>'
        f'<input class="srch__i" id="q404" name="q" type="search" placeholder="Название">'
        f'<button class="srch__b" type="submit">Найти</button></form>'
        f'<p class="nf__l"><a class="lnk" href="/">На главную</a> · '
        f'<a class="lnk" href="/catalog/">Каталог</a></p></section>'
    )


def блок_заголовок(вид: dict, настройка: dict) -> str:
    """Заголовок раздела: h1 маршрута и, если есть, счётчик записей."""
    счёт = вид.get("total")
    подпись = f'<span class="ph__n">{счёт}</span>' if счёт else ""
    описание = вид.get("lead")
    return (
        f'<header class="ph"><h1 class="ph__t">{э(вид.get("h1") or настройка.get("заголовок", ""))}'
        f'{подпись}</h1>'
        + (f'<p class="ph__d">{э(описание)}</p>' if описание else "")
        + '</header>'
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
    "rail": блок_полоса,
    "filters": блок_фильтры,
    "listing": блок_перечень,
    "search": блок_поиск,
    "title": блок_карточка_тайтла,
    "seasons": блок_сезоны,
    "player": блок_плеер,
    "similar": блок_рекомендации,
    "crumbs": блок_крошки,
    "notfound": блок_не_найдено,
    "pagehead": блок_заголовок,
}


# --- виды маршрутов ---------------------------------------------------------

def _по_слагу(фикстура: dict) -> dict:
    return {з["slug"]: з for з in фикстура["items"]}


def вид_маршрута(фикстура: dict, маршрут: str, параметры: dict | None = None,
                 на_странице: int = НА_СТРАНИЦЕ) -> dict:
    """Данные одного маршрута: что показывать, под каким заголовком, где мы.

    Выбор данных — работа ядра витрины; здесь он воспроизведён на фикстуре,
    чтобы представление маршрута можно было проверить, не трогая витрину.
    """
    параметры = параметры or {}
    записи = фикстура["items"]
    по_слагу = _по_слагу(фикстура)
    общее = {
        "catalog_items": записи,
        "per_page": на_странице,
        "taxonomies": фикстура["taxonomies"],
        "collections": фикстура["collections"],
        "by_slug": по_слагу,
        "route": маршрут,
        "crumbs": [("Главная", "/")],
        "base_url": "/catalog/",
        "page": int(параметры.get("page", 1)),
    }

    def страница(подмножество: list[dict], основа: str, заголовок: str,
                 крошки: list, ведущее: str | None = None) -> dict:
        н = int(параметры.get("page", 1))
        начало = (н - 1) * на_странице
        return dict(общее, items=подмножество[начало:начало + на_странице],
                    total=len(подмножество), page=н, base_url=основа,
                    h1=заголовок, crumbs=крошки, lead=ведущее,
                    per_page=на_странице, all_items=подмножество)

    if маршрут == "home":
        return dict(общее, items=записи, total=len(записи), h1=None)

    if маршрут == "catalog":
        return страница(записи, "/catalog/", "Каталог",
                        [("Главная", "/"), ("Каталог", "/catalog/")])

    if маршрут == "new":
        свежие = sorted(
            [з for з in записи if з.get("published_at") and not з.get("published_at_estimated")],
            key=lambda з: з["published_at"], reverse=True)
        return страница(свежие, "/new/", "Новинки",
                        [("Главная", "/"), ("Новинки", "/new/")],
                        "Порядок — по дате добавления в каталог витрины.")

    if маршрут in ("search", "search_empty"):
        запрос = параметры.get("q")
        if запрос is None:
            запрос = (фикстура["search"]["queries"][0]["q"]
                      if маршрут == "search" and фикстура["search"]["queries"]
                      else фикстура["search"]["empty_query"])
        найдено = [з for з in записи if запрос.lower() in (з.get("title") or "").lower()]
        вид = страница(найдено, "/search/", f"Поиск: {запрос}",
                       [("Главная", "/"), ("Поиск", "/search/")])
        вид["query"] = запрос
        return вид

    if маршрут in ("genre", "year", "country"):
        поле = {"genre": "genres", "year": "years", "country": "countries"}[маршрут]
        значения = фикстура["taxonomies"][поле]
        ключ = параметры.get("value") or (значения[0]["name"] if значения else "")
        if маршрут == "year":
            подмножество = [з for з in записи if str(з.get("year")) == str(ключ)]
            подпись, корень = f"Год {ключ}", "/year/"
        else:
            подмножество = [з for з in записи if ключ in (з.get(поле) or [])]
            подпись = ключ[:1].upper() + ключ[1:]
            корень = "/genre/" if маршрут == "genre" else "/country/"
        слаг = next((з["slug"] for з in значения if з["name"] == str(ключ)), str(ключ))
        разделы = {"genre": "Жанры", "year": "Годы", "country": "Страны"}[маршрут]
        return страница(подмножество, f"{корень}{слаг}/", подпись,
                        [("Главная", "/"), (разделы, корень), (подпись, f"{корень}{слаг}/")])

    if маршрут == "collection":
        подборки = фикстура["collections"]
        ключ = параметры.get("value") or (подборки[0]["key"] if подборки else "")
        подборка = next((п for п in подборки if п["key"] == ключ), None)
        состав = [по_слагу[s] for s in (подборка["slugs"] if подборка else []) if s in по_слагу]
        return страница(состав, f"/collections/{ключ}/",
                        подборка["title"] if подборка else "Подборка",
                        [("Главная", "/"), ("Подборки", "/collections/"),
                         (подборка["title"] if подборка else "Подборка", f"/collections/{ключ}/")],
                        f"Состав подборки: {подборка['provenance']}." if подборка else None)

    if маршрут in ("title_movie", "title_series", "season", "episode", "episode_player"):
        slug = параметры.get("slug")
        if not slug:
            сериалы = [з for з in записи if з.get("seasons")]
            фильмы = [з for з in записи if not з.get("seasons")]
            выбор = сериалы if маршрут != "title_movie" else фильмы
            slug = (выбор or записи)[0]["slug"]
        сущность = по_слагу[slug]
        крошки = [("Главная", "/"), ("Каталог", "/catalog/"),
                  (сущность["title"], сущность["url"])]
        вид = dict(общее, items=записи, entity=сущность, total=None,
                   h1=сущность["title"], crumbs=крошки)
        if маршрут in ("season", "episode", "episode_player"):
            сезон = int(параметры.get("season") or (сущность["seasons"][0]["n"]
                                                    if сущность.get("seasons") else 1))
            вид["season"] = сезон
            крошки.append((f"Сезон {сезон}", f'{сущность["url"]}season-{сезон}/'))
        if маршрут in ("episode", "episode_player"):
            серия = int(параметры.get("episode") or 1)
            вид["episode"] = серия
            вид["h1"] = f'{сущность["title"]} — сезон {вид["season"]}, серия {серия}'
            крошки.append((f"Серия {серия}",
                           f'{сущность["url"]}season-{вид["season"]}/episode-{серия}/'))
        return вид

    if маршрут == "notfound":
        return dict(общее, items=записи[:12], total=None, h1="Страница не найдена",
                    crumbs=[])

    raise ValueError(f"неизвестный маршрут {маршрут!r}")


# --- страница ---------------------------------------------------------------

СКЕЛЕТ = """<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<link rel="canonical" href="https://{домен}{канон}">
<title>{титул}</title>
<style>{стили}</style></head>
<body data-template="{template_id}" data-design="{slug}" data-route="{маршрут}">
<a class="skip" href="#main">К содержанию</a>
<header class="hd" role="banner"><a class="hd__brand" href="/">{бренд}</a>
<nav class="hd__nav" aria-label="Основная навигация">{навигация}</nav>
<form class="hd__s" action="/search/" method="get" role="search">
<label class="hd__lb" for="hq">Поиск</label>
<input class="hd__i" id="hq" name="q" type="search" placeholder="Поиск"></form></header>
<main class="wrap" id="main" role="main">{тело}</main>
<footer class="ft" role="contentinfo"><p class="ft__p">{подвал}</p></footer>
<script>{скрипт}</script>
</body></html>"""

#: Заголовок документа и канонический адрес маршрута — ядро, а не пакет.
ТИТУЛЫ = {
    "home": "{бренд} — каталог фильмов и сериалов",
    "catalog": "Каталог — {бренд}",
    "new": "Новинки — {бренд}",
    "search": "Поиск: {q} — {бренд}",
    "search_empty": "Поиск: {q} — {бренд}",
    "genre": "{h1} — {бренд}",
    "year": "{h1} — {бренд}",
    "country": "{h1} — {бренд}",
    "collection": "{h1} — {бренд}",
    "title_movie": "{h1} — смотреть онлайн — {бренд}",
    "title_series": "{h1} — смотреть онлайн — {бренд}",
    "season": "{h1} — {бренд}",
    "episode": "{h1} — {бренд}",
    "episode_player": "{h1} — {бренд}",
    "notfound": "Страница не найдена — {бренд}",
}


def канонический(вид: dict, маршрут: str) -> str:
    если_тайтл = вид.get("entity")
    if маршрут in ("title_movie", "title_series"):
        return если_тайтл["url"]
    if маршрут == "season":
        return f'{если_тайтл["url"]}season-{вид["season"]}/'
    if маршрут in ("episode", "episode_player"):
        return f'{если_тайтл["url"]}season-{вид["season"]}/episode-{вид["episode"]}/'
    if маршрут in ("search", "search_empty"):
        return "/search/"
    основа = вид.get("base_url", "/")
    return основа if вид.get("page", 1) == 1 else f'{основа}?page={вид["page"]}'


def собрать_стили(пакет: pathlib.Path, ядро: pathlib.Path) -> str:
    части = [(ядро / "core.css").read_text(encoding="utf-8")]
    for имя in ("tokens.css", "layout.css", "components.css"):
        файл = пакет / имя
        if файл.is_file():
            части.append(файл.read_text(encoding="utf-8"))
    return "\n".join(части)


def состав_маршрута(манифест: dict, маршрут: str) -> list[dict]:
    """Состав маршрута объявляет пакет; ядро лишь берёт объявленное."""
    if маршрут == "home":
        return манифест["home_block_order"]
    маршруты = манифест.get("routes") or {}
    if маршрут in маршруты:
        return маршруты[маршрут]
    raise ValueError(f'{манифест["template_id"]}: маршрут {маршрут} не объявлен')


def _страница_маршрута(блоки: list[dict], фикстура: dict) -> int:
    """Размер страницы пагинации: объявленный пакетом и согласованный с итогом.

    Проверять только первую страницу мало: последняя получает остаток, и
    именно там появляется одинокая карточка. Поэтому размер подбирается так,
    чтобы ни одна страница перечня не оставила в последнем ряду одну.
    """
    перечень = next((б for б in блоки if б["тип"] == "listing"), None)
    if not перечень:
        return НА_СТРАНИЦЕ
    объявлено = перечень.get("на_странице", НА_СТРАНИЦЕ)
    колонки = [к for к in (перечень.get("колонки") or []) if к >= 3]
    всего = len(фикстура["items"])
    if not колонки:
        return объявлено
    def годен(размер: int) -> bool:
        остаток = всего % размер or размер
        return not any(размер % к == 1 or остаток % к == 1 for к in колонки)
    for шаг in range(0, 9):
        for размер in (объявлено + шаг, объявлено - шаг):
            if размер >= 12 and годен(размер):
                return размер
    return объявлено


def _один_h1(разметка: str) -> str:
    """На странице обязан быть ровно один h1.

    Композиция главной принадлежит пакету, и требовать от него отдельного
    заголовка страницы значит навязать всем пятидесяти одинаковую шапку.
    Поэтому правило соблюдается ядром: если ни один блок не дал h1, им
    становится заголовок первого блока — тот, что человек и читает первым.
    """
    if "<h1" in разметка:
        return разметка
    for метка in ('<h2 class="hero__t">', '<h2 class="sec__t">'):
        if метка not in разметка:
            continue
        место = разметка.index(метка)
        конец = разметка.index("</h2>", место)
        повышенный = (метка.replace("<h2", "<h1") + разметка[место + len(метка):конец]
                      + "</h1>")
        # Внутри повышенной секции подзаголовки обязаны подняться вместе с ней.
        # Иначе h1 оказывается прямо над h3 — пропуск уровня, который создаёт
        # само это правило, а ловит проверка доступности. Уже ловила.
        начало_секции = разметка.rfind("<section", 0, место)
        конец_секции = разметка.find("</section>", конец)
        голова = разметка[:место]
        хвост = разметка[конец + len("</h2>"):]
        if начало_секции != -1 and конец_секции != -1:
            внутри = разметка[конец + len("</h2>"):конец_секции]
            хвост = (внутри.replace("<h3 ", "<h2 ").replace("</h3>", "</h2>")
                     + разметка[конец_секции:])
        return голова + повышенный + хвост
    return разметка


def отрисовать(пакет_каталог: pathlib.Path, фикстура: dict,
               ядро: pathlib.Path | None = None, маршрут: str = "home",
               параметры: dict | None = None) -> str:
    ядро = ядро or pathlib.Path(__file__).resolve().parent
    манифест = json.loads((пакет_каталог / "template.json").read_text(encoding="utf-8"))
    блоки = состав_маршрута(манифест, маршрут)
    вид = вид_маршрута(фикстура, маршрут, параметры,
                       на_странице=_страница_маршрута(блоки, фикстура))

    тело = []
    for блок in блоки:
        строитель = БЛОКИ.get(блок["тип"])
        if строитель is None:
            raise ValueError(f"{манифест['template_id']}: неизвестный блок {блок['тип']!r}")
        тело.append(строитель(вид, блок))
    разметка = _один_h1("".join(тело))

    навигация = "".join(
        f'<a class="hd__l" href="{э(п["url"])}">{э(п["подпись"])}</a>'
        for п in манифест["navigation"])
    заготовка = ТИТУЛЫ[маршрут]
    титул = заготовка.format(бренд=манифест["brand"], h1=вид.get("h1") or манифест["title"],
                             q=вид.get("query", ""))
    return СКЕЛЕТ.format(
        домен=э(манифест.get("preview_domain", "lords.example")),
        канон=э(канонический(вид, маршрут)),
        титул=э(титул),
        стили=собрать_стили(пакет_каталог, ядро),
        template_id=э(манифест["template_id"]),
        slug=э(манифест["slug"]),
        маршрут=э(маршрут),
        бренд=э(манифест["brand"]),
        навигация=навигация,
        тело=разметка,
        подвал=э(манифест["footer"]),
        скрипт=(ядро / "core.js").read_text(encoding="utf-8"),
    )
