"""SEO-слой витрины: аналитика, canonical, структурированные данные, sitemap.

Отдельный модуль, а не правки по рендереру, и на то две причины.

Первая — та, из-за которой слой вообще появился. Тег Метрики уже однажды
исчез: он стоял в шаблонах, переработка шаблонов добавила два новых `<head>`,
и про них забыли. Забыть можно только то, о чём надо помнить. Здесь помнить
не о чем: слой вызывается из единственной точки отдачи ответа, и новый
шаблон её не минует.

Вторая — передача. Ветку шаблонов ведёт другая сессия, её финальный коммит
ещё не выдан, и патч по живому файлу конфликтовал бы с любой их правкой.
Отдельный файл плюс три вызова конфликтовать не с чем.

Ничего визуального слой не добавляет. Всё, что он вставляет, живёт в `<head>`
либо отдаётся отдельным адресом.
"""
from __future__ import annotations

import html as _html
import json
import os
import pathlib
import re
import tempfile
import xml.etree.ElementTree as ET
from typing import Any, Iterable

# ---------------------------------------------------------------------------
# Аналитика
# ---------------------------------------------------------------------------

#: Признак уже вставленного тега. По нему проверяется идемпотентность:
#: страница, прошедшая отдачу дважды, не должна получить два счётчика.
МЕТКА_МЕТРИКИ = "data-metrika-counter="


def тег_метрики(counter: str) -> str:
    """Официальный тег Метрики или пустая строка.

    Пустая строка означает «счётчика нет» и даёт страницу без тега, а не тег,
    который молчит: молчащий тег неотличим от работающего до первого отчёта.

    Загрузка асинхронная — аналитика не вправе задерживать отрисовку.
    Вебвизор выключен: реестр аналитики требует от него `false`, а включается
    он отдельным решением владельца.
    """
    counter = (counter or "").strip()
    if not counter.isdigit():
        return ""
    return (
        f'<script {МЕТКА_МЕТРИКИ}"{counter}">'
        "(function(){"
        "if(window.__sfMetrikaReady){return;}window.__sfMetrikaReady=1;"
        "(function(m,e,t,r,i,k,a){"
        "m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};"
        "m[i].l=1*new Date();"
        "for(var j=0;j<e.scripts.length;j++){if(e.scripts[j].src===r){return;}}"
        "k=e.createElement(t),a=e.getElementsByTagName(t)[0],"
        "k.async=1,k.src=r,a.parentNode.insertBefore(k,a)"
        '})(window,document,"script","https://mc.yandex.ru/metrika/tag.js","ym");'
        f'ym({counter},"init",{{trackLinks:true,accurateTrackBounce:true,webvisor:false}});'
        "})();"
        "</script>"
        f'<noscript><div><img src="https://mc.yandex.ru/watch/{counter}" '
        'style="position:absolute;left:-9999px" alt=""></div></noscript>'
    )


# ---------------------------------------------------------------------------
# Canonical
# ---------------------------------------------------------------------------

#: Параметры, которые не образуют отдельной канонической страницы. Сортировка
#: и метки рекламных кампаний меняют вид списка, но не его содержание.
НЕКАНОНИЧЕСКИЕ = frozenset({
    "sort", "order", "view", "per_page", "q", "utm_source", "utm_medium",
    "utm_campaign", "utm_term", "utm_content", "gclid", "yclid", "fbclid",
})


def канонический_путь(путь: str) -> str:
    """Путь без параметров, которые не создают отдельной страницы.

    Фильтр `kind` оставляется: `/catalog/?kind=Фильм` — это другой список, а
    не другой порядок того же списка. Сортировка убирается: она порождала бы
    у каждой страницы столько копий, сколько у неё способов упорядочивания.
    """
    основа, _, запрос = путь.partition("?")
    if not запрос:
        return основа
    оставить = []
    for пара in запрос.split("&"):
        имя = пара.split("=", 1)[0]
        if имя and имя not in НЕКАНОНИЧЕСКИЕ:
            оставить.append(пара)
    return основа + ("?" + "&".join(оставить) if оставить else "")


def тег_каноникал(хост: str, путь: str) -> str:
    """Абсолютный self-canonical. Только свой домен и только https."""
    if not хост:
        return ""
    return (f'<link rel="canonical" href="'
            f'{_html.escape("https://" + хост + канонический_путь(путь))}">')


# ---------------------------------------------------------------------------
# Структурированные данные
# ---------------------------------------------------------------------------

def _цепочка(хост: str, путь: str, titles: dict[str, str]) -> list[dict]:
    части = [ч for ч in канонический_путь(путь).split("?")[0].split("/") if ч]
    шаги, накопленный = [{"@type": "ListItem", "position": 1, "name": "Главная",
                          "item": f"https://{хост}/"}], ""
    for i, ч in enumerate(части, start=2):
        накопленный += f"/{ч}"
        шаги.append({"@type": "ListItem", "position": i,
                     "name": titles.get(ч, ч),
                     "item": f"https://{хост}{накопленный}/"})
    return шаги


def уже_есть_типы(тело: bytes) -> set[str]:
    """Типы schema.org, которые страница объявила сама."""
    текст = тело.decode("utf-8", errors="replace")
    return set(re.findall(r'"@type"\s*:\s*"([A-Za-z]+)"', текст))


def схема(хост: str, путь: str, имя_сайта: str, *,
          сущность: dict[str, Any] | None = None,
          поиск: str = "", крошки: dict[str, str] | None = None,
          кроме: set[str] | None = None) -> str:
    """JSON-LD только из того, что известно наверняка.

    Ни рейтингов, ни числа голосов, ни актёров, ни дат, которых нет в данных:
    выдуманная разметка — это заявка поисковику на сведения, которых не
    существует, и отвечать за неё придётся домену.

    `SearchAction` добавляется только когда адрес поиска передан явно: объявить
    неработающий контракт поиска хуже, чем не объявлять никакого.
    """
    if not хост:
        return ""
    занято = кроме or set()
    блоки: list[dict[str, Any]] = []
    сайт: dict[str, Any] = {
        "@context": "https://schema.org", "@type": "WebSite",
        "name": имя_сайта, "url": f"https://{хост}/",
    }
    if поиск:
        сайт["potentialAction"] = {
            "@type": "SearchAction",
            "target": {"@type": "EntryPoint",
                       "urlTemplate": f"https://{хост}{поиск}"},
            "query-input": "required name=search_term_string",
        }
    if "WebSite" not in занято:
        блоки.append(сайт)
    цепь = _цепочка(хост, путь, крошки or {})
    if len(цепь) > 1 and "BreadcrumbList" not in занято:
        блоки.append({"@context": "https://schema.org",
                      "@type": "BreadcrumbList", "itemListElement": цепь})
    if сущность and not ({"Movie", "TVSeries", "CreativeWork"} & занято):
        блоки.append(_сущность(хост, сущность))
    if not блоки:
        return ""
    return "".join(
        '<script type="application/ld+json">'
        + json.dumps(б, ensure_ascii=False, separators=(",", ":"))
        + "</script>" for б in блоки)


#: Вид каталога → тип schema.org. Мультфильм намеренно отображается в Movie:
#: отдельного типа для него в словаре нет, а выдумывать свой — значит отдать
#: разметку, которую никто не прочтёт.
ТИПЫ = {"Фильм": "Movie", "Мультфильм": "Movie", "Сериал": "TVSeries"}


def _сущность(хост: str, з: dict[str, Any]) -> dict[str, Any]:
    вид = ТИПЫ.get(str(з.get("kind") or ""), "CreativeWork")
    из: dict[str, Any] = {"@context": "https://schema.org", "@type": вид,
                          "name": з.get("title")}
    if з.get("url"):
        из["url"] = f"https://{хост}{з['url']}"
    elif з.get("slug"):
        из["url"] = f"https://{хост}/title/{з['slug']}/"
    # Год — только если он есть в каталоге. `datePublished` требует даты, а
    # год датой не является; поэтому отдаётся именно год копирайта.
    if з.get("year"):
        из["copyrightYear"] = int(з["year"])
    if з.get("poster"):
        из["image"] = з["poster"]
    return {к: v for к, v in из.items() if v not in (None, "", [])}


# ---------------------------------------------------------------------------
# Единая точка обогащения
# ---------------------------------------------------------------------------

def обогатить(тело: bytes, тип: str, *, хост: str = "", путь: str = "/",
              counter: str = "", имя_сайта: str = "",
              сущность: dict[str, Any] | None = None,
              поиск: str = "", крошки: dict[str, str] | None = None,
              код: int = 200) -> bytes:
    """Дополнить HTML-ответ SEO-разметкой. Вызывается из отдачи ответа.

    На ответах, которые не 200, canonical и схема не ставятся: канонический
    адрес у страницы, которой нет, — это указание поисковику считать ошибку
    содержимым. Тег аналитики ставится всегда: просмотр четырёхсотой страницы
    такой же факт, как и любой другой, и терять его незачем.
    """
    if "text/html" not in тип or b"</head>" not in тело:
        return тело
    вставка = ""
    if МЕТКА_МЕТРИКИ.encode("utf-8") not in тело:
        вставка += тег_метрики(counter)
    if код == 200:
        if b'rel="canonical"' not in тело:
            вставка += тег_каноникал(хост, путь)
        # Проверка по типам, а не по факту наличия разметки. Шаблон тайтла уже
        # отдаёт `Movie`, и грубая проверка «есть ли ld+json» оставляла такую
        # страницу вовсе без `WebSite` и хлебных крошек — то есть добавляла
        # ровно там, где и без того было, и молчала там, где не было.
        есть = уже_есть_типы(тело)
        вставка += схема(хост, путь, имя_сайта, сущность=сущность,
                         поиск=поиск, крошки=крошки, кроме=есть)
    if not вставка:
        return тело
    return тело.replace(b"</head>", вставка.encode("utf-8") + b"</head>", 1)


# ---------------------------------------------------------------------------
# Sitemap
# ---------------------------------------------------------------------------

#: Предел протокола — 50 000 URL на файл. Берём с запасом: каталог растёт
#: между сборками, и упереться в предел на публикации хуже, чем иметь на один
#: файл больше.
ПРЕДЕЛ_URL = 45_000

SM_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"


def _урл(родитель: ET.Element, адрес: str, lastmod: str = "") -> None:
    у = ET.SubElement(родитель, "url")
    ET.SubElement(у, "loc").text = адрес
    # `lastmod` ставится только когда дата известна. Подставленная «сегодня»
    # сообщает поисковику, что весь каталог обновился сегодня, — и обесценивает
    # поле у всех остальных страниц заодно.
    if lastmod:
        ET.SubElement(у, "lastmod").text = lastmod


def построить_sitemap(хост: str, страницы: Iterable[dict[str, Any]],
                      разделы: Iterable[str] = ()) -> list[tuple[str, bytes]]:
    """Вернуть список `(имя файла, содержимое)`: индекс и его части.

    Дубли убираются по адресу, чужие домены невозможны по построению: адрес
    собирается из переданного хоста, а не берётся из данных.
    """
    адреса: list[tuple[str, str]] = []
    видели: set[str] = set()
    for р in разделы:
        а = f"https://{хост}{р}"
        if а not in видели:
            видели.add(а)
            адреса.append((а, ""))
    for с in страницы:
        путь = с.get("url") or (f"/title/{с['slug']}/" if с.get("slug") else "")
        if not путь:
            continue
        а = f"https://{хост}{путь}"
        if а in видели:
            continue
        видели.add(а)
        адреса.append((а, str(с.get("lastmod") or "")))

    файлы: list[tuple[str, bytes]] = []
    части = [адреса[i:i + ПРЕДЕЛ_URL] for i in range(0, len(адреса), ПРЕДЕЛ_URL)] or [[]]
    for н, часть in enumerate(части, start=1):
        корень = ET.Element("urlset", xmlns=SM_NS)
        for а, lm in часть:
            _урл(корень, а, lm)
        файлы.append((f"sitemap-{н}.xml",
                      ET.tostring(корень, encoding="utf-8", xml_declaration=True)))
    индекс = ET.Element("sitemapindex", xmlns=SM_NS)
    for имя, _ in файлы:
        s = ET.SubElement(индекс, "sitemap")
        ET.SubElement(s, "loc").text = f"https://{хост}/{имя}"
    файлы.append(("sitemap.xml",
                  ET.tostring(индекс, encoding="utf-8", xml_declaration=True)))
    return файлы


def записать_атомарно(каталог: str | os.PathLike[str],
                      файлы: list[tuple[str, bytes]]) -> dict[str, Any]:
    """Записать набор целиком или не записать ничего.

    Частично обновлённый sitemap хуже устаревшего: индекс уже ссылается на
    части, которых ещё нет, и поисковик получает набор ошибок вместо карты.
    """
    цель = pathlib.Path(каталог)
    цель.mkdir(parents=True, exist_ok=True)
    временные: list[pathlib.Path] = []
    try:
        for имя, данные in файлы:
            fd, врем = tempfile.mkstemp(dir=цель, prefix=f".{имя}.", suffix=".tmp")
            with os.fdopen(fd, "wb") as f:
                f.write(данные)
            временные.append(pathlib.Path(врем))
        for (имя, _), врем in zip(файлы, временные):
            os.replace(врем, цель / имя)
    except BaseException:
        for в in временные:
            в.unlink(missing_ok=True)
        raise
    return {"directory": str(цель), "files": [имя for имя, _ in файлы],
            "urls": sum(данные.count(b"<loc>") for _, данные in файлы
                        if not это_индекс(данные))}


def это_индекс(данные: bytes) -> bool:
    return b"<sitemapindex" in данные
