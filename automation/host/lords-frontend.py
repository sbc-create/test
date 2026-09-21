#!/usr/bin/env python3
"""Новый frontend витрины Lords поверх существующего снимка содержимого.

Зачем отдельный рантайм
-----------------------

Полный рендер каталога занимает около трёх часов, а новый интерфейс нужен на
публичном адресе сразу. Содержимое при этом уже отрисовано и лежит в текущем
релизе. Здесь страницы собираются на лету из готового каталога, поэтому смена
интерфейса не ждёт обновления содержимого.

Что не трогается
----------------

Страницы тайтлов отдаются из существующего релиза как есть — в них живёт
плеер, и переписывать их значило бы его сломать. К ним подмешивается только
новая таблица стилей и шапка, чтобы вид был общим. Всё, чего нет в новом
маршруте, отдаётся из старого релиза без изменений.

Честность данных
----------------

Жанры, страны, возраст, КП и IMDb в текущем снимке отсутствуют: `ld+json`
отдаёт `genre: []` и пустую страну. Поэтому карточка показывает то, что
измерено — название, год, вид, постер, — и не выдумывает остального. Фильтры
построены по годам и виду, которые есть, а не по жанрам, которых нет.

Индексация закрыта: `noindex, nofollow` и заголовком, и в `robots.txt`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import argparse
import hashlib
import html
import copy
import json
import os
import re
import sys
import unicodedata
from difflib import SequenceMatcher
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, parse_qsl, quote, unquote, urlencode, urlparse

РЕВИЗИЯ = os.environ.get("LORDS_TEMPLATE_REVISION", "unknown")
МАНИФЕСТ_ФАЙЛ = os.environ.get("LORDS_TEMPLATE_MANIFEST",
                               "/srv/lords/.frontend/template-manifest.json")


def _манифест() -> dict:
    """Версия объявляется манифестом. Без него витрина не поднимается.

    Правило владельца 2026-09-10: определять версию по классу, размеру файла,
    ссылке, имени тега или коду 200 запрещено. Нет манифеста — нет заявленной
    версии, а значит выкладывать нечего.
    """
    try:
        м = json.loads(Path(МАНИФЕСТ_ФАЙЛ).read_text(encoding="utf-8"))
    except (OSError, ValueError) as ош:
        raise SystemExit(f"нет манифеста шаблона {МАНИФЕСТ_ФАЙЛ}: {ош}")
    нет = [п for п in ("schema_version", "template_family", "design_version",
                       "source_commit", "build_id", "artifact_sha256", "profile",
                       "built_at") if п not in м]
    if нет:
        raise SystemExit(f"манифест неполон, нет полей: {нет}")
    return м


МАНИФЕСТ = _манифест()
ВЕРСИЯ = МАНИФЕСТ["design_version"]
СЕМЕЙСТВО = МАНИФЕСТ["template_family"]
СБОРКА = МАНИФЕСТ["build_id"]
ПРОФИЛЬ = МАНИФЕСТ.get("profile") or "unknown"

#: Имя общего рантайма. Один артефакт обслуживает все семейства, и это честно —
#: но называть шаблоном семейства «lords-nova» на Yummy, Zona и Animedia было
#: неправдой: имя ядра выдавалось за имя шаблона витрины.
ЯДРО = "site-factory-nova"
#: Имя шаблона КОНКРЕТНОГО семейства. Отсюда и из версии складывается то, что
#: домен объявляет о себе.
ШАБЛОН_СЕМЕЙСТВА = f"{СЕМЕЙСТВО}-nova"
КАТАЛОГ_ФАЙЛ = os.environ.get("LORDS_CATALOG", "/srv/lords/.frontend/lords-01-catalog.json")
def _рядом_с_каталогом(шаблон: str) -> str:
    """Путь-спутник снимка каталога.

    Юниты витрин принадлежат root и правятся отдельной процедурой, а боковые
    файлы обязаны находиться без правки юнита. Поэтому имя выводится из уже
    заданного `LORDS_CATALOG`: `/…/lords-01-catalog.json` даёт
    `/…/lords-01-details.json` и `/…/player-lords-01.json`. Соглашение
    перекрывается переменной окружения, если она задана.
    """
    путь = Path(КАТАЛОГ_ФАЙЛ)
    имя = путь.name
    if not имя.endswith("-catalog.json"):
        return ""
    витрина = имя[: -len("-catalog.json")]
    return str(путь.with_name(шаблон.format(site=витрина)))


#: Боковой файл подробностей (`build-detail-sidecar.py`). Отсутствие файла —
#: законное состояние: страницы тайтлов тогда строятся на полях снимка.
ПОДРОБНОСТИ_ФАЙЛ = os.environ.get("LORDS_DETAILS") or _рядом_с_каталогом("{site}-details.json")
СТАРЫЙ_КОРЕНЬ = Path(os.environ.get("LORDS_LEGACY_ROOT", "/srv/lords/lords-01/current/site"))
ИМЯ_ВИТРИНЫ = os.environ.get("LORDS_SITE_NAME", "Lords")
# Для витрин, где страницы отдаёт приложение, а не каталог файлов: всё, чего
# нет в новом маршруте, проксируется в него. Так плеер, карточка и любые
# динамические страницы остаются рабочими — их никто не переписывает.
ВЕРХОВОЙ = os.environ.get("LORDS_LEGACY_UPSTREAM", "")

# SEO-слой отдельным модулем. Он уже дважды снимался выкладкой шаблонов, и оба
# раза не по злому умыслу: вставка жила в шаблонах, а каждое новое оформление
# добавляет свой <head>. Поэтому слой вызывается из отдачи ответа — её не
# минует ни один шаблон.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import seo_layer as SEO  # noqa: E402

# Контракт коллекций. Канонический экземпляр живёт в `factory/lords/`, рядом с
# артефактом лежит его копия — тем же способом, что и SEO-слой. Отсутствие
# файла не должно ронять витрину: без него главная собирается прежним образом.
try:
    import collection_contract as КОЛЛЕКЦИИ  # noqa: E402
except ImportError:
    КОЛЛЕКЦИИ = None

#: Каталог готовых файлов карты сайта. Пусто — карта не отдаётся.
SITEMAP_DIR = os.environ.get("LORDS_SITEMAP_DIR", "").strip()
#: Счётчик Яндекс Метрики этой витрины. Публичное число, не секрет: оно и так
#: видно в исходном коде любой страницы. Значение задаёт unit витрины, потому
#: что один процесс обслуживает один домен, а счётчик привязан к домену.
#: Пустое значение означает «счётчика нет» и даёт страницу без тега — не тег,
#: который молчит. Молчащий тег неотличим от работающего до первого отчёта.
СЧЁТЧИК_МЕТРИКИ = os.environ.get("LORDS_METRIKA_COUNTER", "").strip()


def тег_метрики() -> str:
    """Официальный тег Метрики или пустая строка.

    Про единственность инициализации. Тег вставляется в четырёх местах —
    в две оболочки собственных страниц и в два места, где размечается чужой
    HTML (проксируемый и взятый из прежнего релиза). Пересечься они не должны,
    но «не должны» — это не «не могут»: достаточно одной страницы, которая
    пройдёт обоими путями, и счётчик получит два просмотра одного визита.
    Поэтому защёлка стоит в самом теге, а не в рассуждении о том, где он
    окажется.

    Загрузка асинхронная: аналитика не имеет права задерживать отрисовку.
    Вебвизор выключен намеренно — он включается отдельным решением владельца,
    и реестр аналитики требует от него `false`.
    """
    if not СЧЁТЧИК_МЕТРИКИ.isdigit():
        return ""
    н = СЧЁТЧИК_МЕТРИКИ
    return (
        f'<script data-metrika-counter="{н}">'
        "(function(){"
        "if(window.__sfMetrikaReady){return;}window.__sfMetrikaReady=1;"
        "(function(m,e,t,r,i,k,a){"
        "m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};"
        "m[i].l=1*new Date();"
        "for(var j=0;j<e.scripts.length;j++){if(e.scripts[j].src===r){return;}}"
        "k=e.createElement(t),a=e.getElementsByTagName(t)[0],"
        "k.async=1,k.src=r,a.parentNode.insertBefore(k,a)"
        '})(window,document,"script","https://mc.yandex.ru/metrika/tag.js","ym");'
        f'ym({н},"init",{{trackLinks:true,accurateTrackBounce:true,webvisor:false}});'
        "})();"
        "</script>"
        f'<noscript><div><img src="https://mc.yandex.ru/watch/{н}" '
        'style="position:absolute;left:-9999px" alt=""></div></noscript>'
    )

#: Контракт многоисточниковых оценок. Единственное место, где объявлено,
#: какие источники бывают и как каждый подписывается. Подпись привязана к
#: ключу жёстко: показать Shikimori под подписью «КП» значило бы соврать о
#: происхождении числа, а оценка без верного источника — это не оценка.
#:
#: Ключ → (подпись, шкала по умолчанию, это ли оценка пользователей витрины).
ИСТОЧНИКИ_ОЦЕНОК = {
    "kp":        ("КП",         10.0, False),
    "imdb":      ("IMDb",       10.0, False),
    "shikimori": ("Shikimori",  10.0, False),
    "mal":       ("MyAnimeList", 10.0, False),
    "amd":       ("AnimeMedia", 10.0, True),
}

#: Порядок вывода. Фиксированный, а не по величине: переставлять источники
#: местами в зависимости от значения значит каждый раз показывать зрителю
#: разную картину одних и тех же данных.
ПОРЯДОК_ОЦЕНОК = ("shikimori", "kp", "imdb", "mal", "amd")


def _число_оценки(значение) -> str:
    """Оценка как число или пусто. Ноль и null оценкой не являются."""
    if значение is None or isinstance(значение, bool):
        return ""
    try:
        ч = float(значение)
    except (TypeError, ValueError):
        return ""
    if ч <= 0:
        return ""
    return f"{ч:.1f}".rstrip("0").rstrip(".") if ч % 1 else f"{int(ч)}"


def оценки_по_источникам(деталь: dict) -> list:
    """Разбор `ratings_by_source` в список готовых к выводу оценок.

    Принимаются две формы записи источника: число и объект
    ``{"value": …, "scale": …, "votes": …}``. Вторая нужна затем, чтобы шкала
    и число голосов приходили вместе со значением, а не додумывались витриной.

    Чего здесь не происходит: не выдумывается шкала, если источник её не
    прислал, — берётся объявленная контрактом; не показывается ноль, пустое и
    null; не подставляется чужая подпись. Источник, которого в данных нет,
    просто отсутствует — «нет оценки» и «оценка 0» это разные утверждения.

    Совместимость: пока `ratings_by_source` не пришёл, читаются прежние поля
    `kinopoisk_rating` и `imdb_rating`. Это не догадка о данных, а те же два
    источника под своими подписями.
    """
    сырое = деталь.get("ratings_by_source")
    собрано = {}
    if isinstance(сырое, dict):
        # Normalize provider aliases into ИСТОЧНИКИ_ОЦЕНОК keys.
        for ключ, запись in сырое.items():
            к = str(ключ or "").strip().lower()
            if к in ("kinopoisk", "kino", "kp"):
                к = "kp"
            elif к in ("myanimelist", "my_anime_list"):
                к = "mal"
            собрано[к] = запись
    for ключ, поле in (("kp", "kinopoisk_rating"), ("imdb", "imdb_rating"),
                       ("shikimori", "shikimori_score"), ("shikimori", "shikimori_rating")):
        if ключ not in собрано and деталь.get(поле) is not None:
            собрано[ключ] = деталь[поле]
    готово = []
    for ключ in ПОРЯДОК_ОЦЕНОК:
        if ключ not in собрано:
            continue
        подпись, шкала_по_умолчанию, пользовательская = ИСТОЧНИКИ_ОЦЕНОК[ключ]
        запись = собрано[ключ]
        if isinstance(запись, dict):
            значение = _число_оценки(запись.get("value"))
            шкала = запись.get("scale") or шкала_по_умолчанию
            голоса = запись.get("votes")
        else:
            значение = _число_оценки(запись)
            шкала = шкала_по_умолчанию
            голоса = None
        if not значение:
            continue
        try:
            голосов = int(голоса) if голоса is not None else None
        except (TypeError, ValueError):
            голосов = None
        готово.append({
            "ключ": ключ, "подпись": подпись, "значение": значение,
            "шкала": f"{float(шкала):g}", "голоса": голосов if (голосов or 0) > 0 else None,
            "пользовательская": пользовательская,
        })
    return готово


def разметка_оценок(деталь: dict, класс: str = "rbs", пусто: bool = True) -> str:
    """Компонент оценок. Один на все семейства, вид задаёт CSS семейства.

    Оценка витрины (AMD) отделена от внешних явной группой: смешать их в один
    ряд значило бы выдать мнение зрителей одной витрины за оценку агрегатора.

    Доступность: список размечен как список, каждая оценка читается целиком —
    «КП 7.4 из 10, 1234 голоса», — потому что вслух «7.4» без источника и
    шкалы не значит ничего.
    """
    оценки = оценки_по_источникам(деталь)
    if not оценки:
        if not пусто:
            return ""
        return (f'<p class="{класс} {класс}--none">'
                "<span>Оценок пока нет: источник их не передал</span></p>")
    def элемент(о):
        голоса = (f'<span class="{класс}__v">{о["голоса"]} голос.</span>'
                  if о["голоса"] else "")
        вслух = (f'{о["подпись"]} {о["значение"]} из {о["шкала"]}'
                 + (f', {о["голоса"]} голосов' if о["голоса"] else ""))
        return (f'<li class="{класс}__i" data-source="{о["ключ"]}">'
                f'<span class="vh">{html.escape(вслух)}</span>'
                f'<span class="{класс}__s" aria-hidden="true">{html.escape(о["подпись"])}</span>'
                f'<span class="{класс}__n" aria-hidden="true">{о["значение"]}'
                f'<small>/{о["шкала"]}</small></span>{голоса}</li>')
    внешние = [о for о in оценки if not о["пользовательская"]]
    свои = [о for о in оценки if о["пользовательская"]]
    части = []
    if внешние:
        части.append(f'<ul class="{класс}__l">' + "".join(элемент(о) for о in внешние) + "</ul>")
    if свои:
        части.append(f'<ul class="{класс}__l {класс}__l--own" '
                     f'aria-label="Оценка зрителей витрины">'
                     + "".join(элемент(о) for о in свои) + "</ul>")
    return f'<div class="{класс}" role="group" aria-label="Оценки">' + "".join(части) + "</div>"


НА_СТРАНИЦЕ = 60

# Оформление и разделы — свои у каждого семейства.
#
# Механически переносить Lords на аниме и кинопорталы нельзя: у них разные
# разделы, разный словарь и разный ритм витрины. Здесь различается палитра,
# навигация и состав секций главной; общей остаётся только механика.
ПРОФИЛИ_СЕМЕЙСТВ = {
    "lords": {
        "acc": "#6d5cff", "acc2": "#00d4ff", "bg": "#0b0d12", "card": "#161a24",
        "nav": [("/", "Главная"), ("/catalog/", "Каталог"), ("/new/", "Новинки"),
                ("/collections/", "Подборки"), ("/schedule/", "Расписание")],
        "secs": [("Новинки", "/new/", None), ("Фильмы", "/catalog/?kind=Фильм", "Фильм"),
                 ("Сериалы", "/catalog/?kind=Сериал", "Сериал")],
        "hero_btn": "Смотреть", "search_ph": "Поиск фильмов и сериалов",
    },
    "yummy": {
        "acc": "#ff5c8a", "acc2": "#ffb347", "bg": "#100a14", "card": "#1c1320",
        "nav": [("/", "Главная"), ("/catalog/", "Каталог"), ("/new/", "Новинки"),
                ("/collections/", "Подборки"), ("/schedule/", "Расписание выхода")],
        "secs": [("Свежие серии", "/new/", None), ("Онгоинги", "/catalog/", None),
                 ("Полюбившееся", "/collections/", None)],
        "hero_btn": "Смотреть аниме", "search_ph": "Поиск аниме",
    },
    "zona": {
        "acc": "#2fd07a", "acc2": "#7de08d", "bg": "#08120d", "card": "#11201a",
        "nav": [("/", "Главная"), ("/catalog/", "Каталог"), ("/new/", "Новинки"),
                ("/collections/", "Подборки"), ("/schedule/", "Расписание")],
        "secs": [("Новинки кино", "/new/", None), ("Фильмы", "/catalog/?kind=Фильм", "Фильм"),
                 ("Сериалы", "/catalog/?kind=Сериал", "Сериал")],
        "hero_btn": "Смотреть", "search_ph": "Поиск по кинопорталу",
    },
    "animedia": {
        "acc": "#4d7cff", "acc2": "#a78bfa", "bg": "#0a0d18", "card": "#141828",
        "nav": [("/", "Главная"), ("/catalog/", "Каталог"), ("/new/", "Новое в каталоге"),
                ("/collections/", "Подборки"), ("/schedule/", "Расписание")],
        "secs": [("Новое в каталоге", "/new/", None), ("Онгоинги", "/catalog/", None),
                 ("Подборки", "/collections/", None)],
        "hero_btn": "Начать просмотр", "search_ph": "Поиск аниме и дорам",
    },
}
_П = ПРОФИЛИ_СЕМЕЙСТВ.get(МАНИФЕСТ["template_family"], ПРОФИЛИ_СЕМЕЙСТВ["lords"])


СТИЛЬ = """
:root{--bg:@BG@;--bg2:#12151d;--card:@CARD@;--line:#232838;--tx:#e8ecf5;--dim:#9aa4bd;
--acc:@ACC@;--acc2:@ACC2@;--warm:#ffb347;--r:14px}
:root[data-theme=light]{--bg:#f5f6fa;--bg2:#fff;--card:#fff;--line:#e2e6f0;--tx:#12151d;
--dim:#5a6478;--acc:#5b4bff;--acc2:#0091c2}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tx);font:16px/1.5 ui-sans-serif,system-ui,'Segoe UI',Roboto,sans-serif;
-webkit-font-smoothing:antialiased}
a{color:inherit;text-decoration:none}
.wrap{max-width:1440px;margin:0 auto;padding:0 24px}
.hdr{position:sticky;top:0;z-index:50;background:color-mix(in srgb,var(--bg) 86%,transparent);
backdrop-filter:blur(14px);border-bottom:1px solid var(--line)}
.hdr__in{display:flex;align-items:center;gap:20px;height:68px}
.logo{font-weight:800;font-size:20px;letter-spacing:-.5px;
background:linear-gradient(92deg,var(--acc),var(--acc2));-webkit-background-clip:text;background-clip:text;color:transparent}
.nav{display:flex;gap:6px;flex:1;flex-wrap:wrap}
.nav a{padding:9px 14px;border-radius:10px;color:var(--dim);font-weight:600;font-size:14px}
.nav a:hover,.nav a[aria-current]{background:var(--card);color:var(--tx)}
.srch{display:flex;align-items:center;gap:8px;background:var(--card);border:1px solid var(--line);
border-radius:12px;padding:8px 12px;min-width:200px}
.srch input{background:0;border:0;color:var(--tx);outline:0;width:100%;font-size:14px}
.tsw{background:var(--card);border:1px solid var(--line);border-radius:12px;color:var(--tx);
cursor:pointer;height:40px;width:44px;font-size:17px;display:inline-flex;align-items:center;justify-content:center}
.hero{position:relative;margin:24px 0 10px;border-radius:20px;overflow:hidden;border:1px solid var(--line);
background:var(--bg2);min-height:340px}
.hero__track{display:flex;transition:transform .45s cubic-bezier(.4,0,.2,1)}
.hero__it{min-width:100%;display:grid;grid-template-columns:224px 1fr;gap:26px;padding:28px;align-items:center}
.hero__ps{aspect-ratio:2/3;border-radius:14px;overflow:hidden;background:var(--card);box-shadow:0 18px 48px #0007}
.hero__ps img{width:100%;height:100%;object-fit:cover;display:block}
.hero__t{font-size:clamp(24px,3.4vw,42px);font-weight:800;margin:0 0 10px;letter-spacing:-1px;line-height:1.1}
.hero__m{color:var(--dim);display:flex;gap:10px;flex-wrap:wrap;font-size:14px;margin-bottom:16px}
.chip{background:var(--card);border:1px solid var(--line);border-radius:999px;padding:5px 12px;font-size:13px;color:var(--dim)}
.btn{display:inline-flex;align-items:center;gap:8px;background:linear-gradient(92deg,var(--acc),var(--acc2));
color:#fff;border:0;border-radius:12px;padding:12px 22px;font-weight:700;cursor:pointer;font-size:15px}
.hero__dots{position:absolute;bottom:14px;left:50%;transform:translateX(-50%);display:flex;gap:7px}
.hero__dots b{width:8px;height:8px;border-radius:50%;background:#fff4;cursor:pointer;display:block;border:0;padding:0}
.hero__dots b[data-on]{background:var(--acc2);width:22px;border-radius:4px}
.sec{margin:34px 0}
.sec__h{display:flex;align-items:baseline;justify-content:space-between;margin-bottom:14px;gap:12px}
.sec__h h2{font-size:21px;margin:0;font-weight:750;letter-spacing:-.4px}
.sec__h a{color:var(--dim);font-size:14px;font-weight:600}
.grid{display:grid;gap:18px;grid-template-columns:repeat(2,1fr)}
@media(min-width:768px){.grid{grid-template-columns:repeat(4,1fr)}}
@media(min-width:1280px){.grid{grid-template-columns:repeat(6,1fr)}}
.c{display:block;border-radius:var(--r);overflow:hidden;background:var(--card);border:1px solid var(--line);
transition:transform .18s,border-color .18s}
.c:hover{transform:translateY(-4px);border-color:var(--acc)}
.c__p{aspect-ratio:2/3;position:relative;background:linear-gradient(160deg,#1b2030,#0f121a);overflow:hidden}
.c__p img{width:100%;height:100%;object-fit:cover;display:block}
.c__ph{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
font-size:38px;font-weight:800;color:#2f3750}
.c__b{padding:10px 12px 13px}
.c__t{font-weight:650;font-size:14px;line-height:1.3;margin-bottom:5px;
display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.c__m{color:var(--dim);font-size:12.5px;display:flex;gap:7px;flex-wrap:wrap}
.flt{display:flex;gap:9px;flex-wrap:wrap;margin:18px 0 6px}
.flt a{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:8px 14px;
font-size:13.5px;color:var(--dim);font-weight:600}
.flt a[aria-current]{background:var(--acc);color:#fff;border-color:var(--acc)}
.pg{display:flex;gap:8px;justify-content:center;margin:30px 0;flex-wrap:wrap}
.pg a,.pg span{padding:9px 15px;border-radius:10px;border:1px solid var(--line);background:var(--card);font-size:14px}
.pg span{background:var(--acc);color:#fff;border-color:var(--acc)}
.ft{border-top:1px solid var(--line);margin-top:50px;padding:26px 0 40px;color:var(--dim);font-size:13.5px}
.empty{padding:60px 20px;text-align:center;color:var(--dim)}
.sched{display:grid;gap:12px}
.sched__d{background:var(--card);border:1px solid var(--line);border-radius:var(--r);padding:16px 18px}
.sched__d h3{margin:0 0 10px;font-size:15px;color:var(--acc2)}
.sched__d ul{margin:0;padding-left:18px;color:var(--dim);font-size:14px;line-height:1.9}
.vbadge{display:inline-block;margin-left:10px;padding:4px 10px;border-radius:8px;
background:var(--card);border:1px solid var(--acc);color:var(--acc2);font-size:12px;
font-weight:700;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
""".replace("@BG@", _П["bg"]).replace("@CARD@", _П["card"]) \
    .replace("@ACC@", _П["acc"]).replace("@ACC2@", _П["acc2"])

СКРИПТ = """
(function(){
 var k='lords-theme',r=document.documentElement;
 var s=localStorage.getItem(k); if(s) r.setAttribute('data-theme',s);
 document.addEventListener('click',function(e){
  var b=e.target.closest('.tsw'); if(!b) return;
  var n=r.getAttribute('data-theme')==='light'?'dark':'light';
  r.setAttribute('data-theme',n); localStorage.setItem(k,n);
  b.textContent = n==='light'?'\\u2600':'\\u263D';
 });
 var t=document.querySelector('.hero__track'); if(!t) return;
 var n=t.children.length,i=0,dots=document.querySelectorAll('.hero__dots b');
 function go(x){i=(x+n)%n;t.style.transform='translateX('+(-i*100)+'%)';
  dots.forEach(function(d,j){j===i?d.setAttribute('data-on',''):d.removeAttribute('data-on')});}
 dots.forEach(function(d,j){d.addEventListener('click',function(){go(j)})});
 setInterval(function(){go(i+1)},6000);
})();
"""


def нормализовать(с: str) -> str:
    """Единая форма для сравнения: регистр, ё/е, дефисы, пробелы, пунктуация."""
    с = unicodedata.normalize("NFKD", (с or "").lower()).replace("ё", "е")
    return re.sub(r"[^a-zа-я0-9]+", "", с)


def токены(с: str) -> list[str]:
    """Слова запроса по отдельности: «бункер 1-3 сезон» — это четыре токена."""
    с = unicodedata.normalize("NFKD", (с or "").lower()).replace("ё", "е")
    return [т for т in re.split(r"[^a-zа-я0-9]+", с) if т]


#: Русская раскладка под латинскими клавишами: «vfnhbwf» → «матрица».
_РАСКЛАДКА = str.maketrans(
    "qwertyuiop[]asdfghjkl;'zxcvbnm,.`",
    "йцукенгшщзхъфывапролджэячсмитьбюё",
)

#: Транслитерация кириллицы → латиница теми же правилами, что у slug витрины.
_ТРАНСЛИТ = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n",
    "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f",
    "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y",
    "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def транслит(с: str) -> str:
    """Кириллица латиницей. Латинские символы остаются как есть."""
    return "".join(_ТРАНСЛИТ.get(ch, ch) for ch in (с or "").lower().replace("ё", "е"))


def _мягкое_совпадение(цель: str, форма: str) -> bool:
    """Нестрогий матч без ложных соседей вроде matrix→maori.

    Прежний критерий (длина ±допуск + Hamming по zip) принимал «matrix»≈«maori».
    Теперь: длина ≥5, общий префикс ≥4, SequenceMatcher.ratio ≥ 0.75.
    «matrix»↔«matrica» проходит; «matrix»↔«maori» — нет.

    У форм с годом в хвосте (`matrica1999` из «Матрица (1999)») дополнительно
    сравниваем обрезанный вариант без четырёх цифр на конце, иначе латиница
    не находила живые тайтлы Матрицы на боевом снимке.
    """
    if len(цель) < 5:
        return False
    кандидаты = [форма]
    без_года = re.sub(r"\d{4}$", "", форма)
    if без_года and без_года != форма:
        кандидаты.append(без_года)
    for ф in кандидаты:
        if len(ф) < 5:
            continue
        if abs(len(цель) - len(ф)) > 2:
            continue
        if цель[:4] != ф[:4]:
            continue
        if SequenceMatcher(None, цель, ф).ratio() >= 0.75:
            return True
    return False


def из_раскладки(с: str) -> str:
    """Строка, набранная латинскими клавишами вместо русских."""
    return (с or "").translate(_РАСКЛАДКА)


def закодировать_запрос(url: str) -> str:
    """Percent-encode query values in an already-built path (?kind=Фильм)."""
    if "?" not in (url or ""):
        return url
    путь, _, хвост = url.partition("?")
    пары = parse_qsl(хвост, keep_blank_values=True)
    return путь + (("?" + urlencode(пары, quote_via=quote)) if пары else "")


#: Слова, которые в запросе несут форму издания, а не название. По ним нельзя
#: отсеивать: «Бункер 1-3 сезон» обязан находить «Бункер».
СЛУЖЕБНЫЕ = {"сезон", "сезона", "сезонов", "серия", "серии", "season", "s",
             "часть", "все", "смотреть", "онлайн"}


class Снимок:
    """Ленивый неизменяемый снимок для контракта коллекций.

    Строится один раз на процесс. Раньше каждый блок главной отдельно обходил
    весь каталог на каждом запросе; теперь порядок и разрезы считаются однажды.
    """

    _снимок = None

    @classmethod
    def получить(cls, данные, подробности):
        if cls._снимок is None and КОЛЛЕКЦИИ is not None:
            cls._снимок = КОЛЛЕКЦИИ.Снимок(
                данные.items, getattr(подробности, "записи", None) or {},
                revision=getattr(данные, "revision", "") or "")
        return cls._снимок


class Данные:
    def __init__(self, путь: str):
        сырое = json.loads(Path(путь).read_text(encoding="utf-8"))
        self.items = сырое["items"]
        self.absent = сырое.get("fields_absent", [])
        self.revision = str(сырое.get("revision") or "")
        self.built_at = str(сырое.get("builtAt") or сырое.get("built_at") or "")
        for з in self.items:
            з["_n"] = нормализовать(з["title"])
            # Все известные формы названия: русское, оригинальное, синонимы
            # владельца, slug и транслит. Пустых среди них нет — сравнивать
            # с пустой строкой значило бы совпадать со всем подряд.
            #
            # Без slug/транслита запрос «matrix» / «naruto» / точный slug
            # живого `/title/{slug}/` давал пустую выдачу при живой карточке.
            формы = [з["_n"]]
            if з.get("slug"):
                формы.append(нормализовать(з["slug"]))
            if з.get("title"):
                формы.append(нормализовать(транслит(з["title"])))
            for поле in ("original_title", "original_name"):
                if з.get(поле):
                    формы.append(нормализовать(з[поле]))
                    формы.append(нормализовать(транслит(з[поле])))
            for доп in (з.get("aliases") or []):
                формы.append(нормализовать(доп))
                формы.append(нормализовать(транслит(доп)))
            # Уникальный порядок без пустых.
            увидели: list[str] = []
            for ф in формы:
                if ф and ф not in увидели:
                    увидели.append(ф)
            з["_формы"] = увидели
        self.years = sorted({з["year"] for з in self.items if з["year"]}, reverse=True)
        self.kinds = sorted({з["kind"] for з in self.items if з["kind"]})

    def искать(self, q: str, предел: int = 120) -> list[dict]:
        """Терпимый поиск по всем известным названиям записи.

        Ищется по русскому названию, оригинальному названию, синонимам,
        slug и транслиту. Запрос дополнительно читается как набранный в
        чужой раскладке. Служебные слова («сезон», «серия») отбрасываются.

        Ранжирование (выше — раньше):
        1) полная фраза точно совпала с формой;
        2) все значимые токены присутствуют (AND) — точные / prefix / substring;
        3) одиночный токен (OR) — только если токенов мало;
        4) мягкое совпадение опечаток.

        Для «Звёздные войны» точное/полное название обязано быть выше
        однотокенных prefix-совпадений вроде «Воин…».
        """
        сырые = [q, из_раскладки(q)]
        фразы: list[str] = []
        токены_запроса: list[str] = []
        for сырой in сырые:
            нq = нормализовать(сырой)
            если_токены = [т for т in токены(сырой)
                           if т not in СЛУЖЕБНЫЕ and not т.isdigit()]
            if нq and нq not in фразы:
                фразы.append(нq)
            for т in если_токены:
                нт = нормализовать(т)
                if нт and нт not in токены_запроса and len(нт) >= 2:
                    токены_запроса.append(нт)
        if not фразы and not токены_запроса:
            return []

        знач_токены = [т for т in токены_запроса if len(т) >= 3]
        многословный = len(знач_токены) >= 2

        def токен_в_формах(т: str, формы: list[str]) -> str | None:
            if т in формы:
                return "exact"
            if any(ф.startswith(т) for ф in формы):
                return "prefix"
            if any(т in ф for ф in формы):
                return "sub"
            return None

        scored: list[tuple[int, str, dict]] = []
        for з in self.items:
            формы = з["_формы"]
            if not формы:
                continue
            score = 0
            # 1) full-phrase exact
            for фраза in фразы:
                if фраза and фраза in формы:
                    score = max(score, 1000)
                    break
            # 2) multi-token AND
            if score < 1000 and знач_токены:
                kinds = [токен_в_формах(т, формы) for т in знач_токены]
                if all(kinds):
                    if all(k == "exact" for k in kinds):
                        score = max(score, 900)
                    elif all(k in {"exact", "prefix"} for k in kinds):
                        score = max(score, 800)
                    else:
                        score = max(score, 700)
                elif not многословный:
                    # single meaningful token — OR tiers
                    for т in знач_токены:
                        k = токен_в_формах(т, формы)
                        if k == "exact":
                            score = max(score, 600)
                        elif k == "prefix":
                            score = max(score, 400)
                        elif k == "sub":
                            score = max(score, 300)
            elif score < 1000 and not многословный:
                for т in токены_запроса:
                    k = токен_в_формах(т, формы)
                    if k == "exact":
                        score = max(score, 600)
                    elif k == "prefix":
                        score = max(score, 400)
                    elif k == "sub":
                        score = max(score, 300)
            # 3) soft only if still unmatched and short query
            if score == 0 and not многословный:
                for цель in (фразы + токены_запроса):
                    if any(_мягкое_совпадение(цель, ф) for ф in формы):
                        score = 100
                        break
            if score == 0 and многословный:
                soft_hits = sum(
                    1 for т in знач_токены
                    if токен_в_формах(т, формы) or any(_мягкое_совпадение(т, ф) for ф in формы[:3])
                )
                if soft_hits == len(знач_токены):
                    score = 150
            if score > 0:
                scored.append((score, з.get("title") or "", з))

        scored.sort(key=lambda x: (-x[0], x[1]))
        итог, видели = [], set()
        for _, _, з in scored:
            if з["url"] in видели:
                continue
            видели.add(з["url"])
            итог.append(з)
            if len(итог) >= предел:
                break
        return итог


def карточка(з: dict) -> str:
    п = з.get("poster")
    изо = (f'<img src="{html.escape(п)}" alt="" loading="lazy" width="400" height="600">'
           if п else f'<span class="c__ph">{html.escape(з["title"][:1])}</span>')
    мета = " ".join(f"<span>{html.escape(str(x))}</span>"
                    for x in (з.get("kind"), з.get("year")) if x)
    return (f'<a class="c" href="{з["url"]}"><div class="c__p">{изо}</div>'
            f'<div class="c__b"><div class="c__t">{html.escape(з["title"])}</div>'
            f'<div class="c__m">{мета}</div></div></a>')


def оболочка(тело: str, титул: str, д: Данные, актив: str = "") -> str:
    нав = _П["nav"]
    ТЕК = ' aria-current="page"'
    пункты = "".join(
        f'<a href="{u}"{ТЕК if u == актив else ""}>{html.escape(t)}</a>'
        for u, t in нав)
    return f"""<!doctype html><html lang="ru" data-theme="dark" data-template-version="{ВЕРСИЯ}" data-template-family="{СЕМЕЙСТВО}" data-build-id="{СБОРКА}"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(титул)} — {html.escape(ИМЯ_ВИТРИНЫ)}</title>
<meta name="robots" content="noindex, nofollow">
<meta name="site-factory-template-revision" content="{МАНИФЕСТ["source_commit"]}">
<meta name="site-factory-design-version" content="{ВЕРСИЯ}">
<meta name="site-factory-template-family" content="{СЕМЕЙСТВО}">
<meta name="site-factory-build-id" content="{СБОРКА}">
<meta name="site-factory-artifact-sha256" content="{МАНИФЕСТ["artifact_sha256"]}">
<meta name="site-factory-template" content="{ШАБЛОН_СЕМЕЙСТВА}">
<meta name="site-factory-core" content="{ЯДРО}">
<meta name="site-factory-profile" content="{ПРОФИЛЬ}">
<link rel="manifest" href="/assets/nova.webmanifest">
{тег_метрики()}<style>{СТИЛЬ}</style></head><body>
<header class="hdr"><div class="wrap hdr__in">
<a class="logo" href="/">{html.escape(ИМЯ_ВИТРИНЫ)}</a>
<nav class="nav">{пункты}</nav>
<form class="srch" action="/search/" method="get" role="search">
<input name="q" placeholder="{_П["search_ph"]}" aria-label="Поиск">
</form>
<button class="tsw" type="button" aria-label="Переключить тему">&#9789;</button>
</div></header>
<main class="wrap">{тело}</main>
<footer class="ft"><div class="wrap">{html.escape(ИМЯ_ВИТРИНЫ)} · тестовая витрина, закрыта от индексации
<span class="vbadge">Template: {СЕМЕЙСТВО} {ВЕРСИЯ} · {МАНИФЕСТ["source_commit"][:8]}</span>
</div></footer>
<script>{СКРИПТ}</script></body></html>"""


# ======================================================================
#  Оформление 1.1.0 — два самостоятельных семейства и свои страницы тайтлов
# ======================================================================
#
# Почему всё, что ниже, вообще появилось
# --------------------------------------
#
# До 1.1.0 витрина отдавала своими силами только списки, а страницу
# произведения брала из старого статического релиза (`старое()`). Отсюда три
# дефекта, которые видел любой посетитель и не видел ни один локальный тест:
#
# 1. Снимок каталога уходит вперёд релиза. У zona-01 в снимке 3868 записей, а
#    в релизе 19 страниц: КАЖДАЯ карточка главной вела на 404. Проверено
#    выборкой из тридцати карточек — двести ни одна не вернула.
# 2. В чужую страницу подмешивался наш `<style>` (`старое()`), и он
#    переопределял `body{color}` поверх чужой темы. При светлой теме системы
#    старый CSS красил поверхности в белый, наш — текст в почти белый:
#    получался светлый текст на светлом фоне. Это и есть тот самый нечитаемый
#    `/title/sinora-volpe/`.
# 3. Серии, состояния плеера, хлебные крошки и разметка Schema принадлежали
#    чужому релизу, и починить их отсюда было нельзя.
#
# Поэтому 1.1.0 рисует страницу произведения сам, из снимка каталога и
# бокового файла подробностей, и в чужую разметку больше не вмешивается.
#
# Почему версия выбирается манифестом
# -----------------------------------
#
# Один и тот же файл обслуживает шесть витрин. Подменить его — значит сменить
# оформление всем сразу, чего никто не просил. Версия оформления объявляется
# манифестом КАЖДОЙ витрины отдельно: витрина, чей манифест остался на 1.0.2,
# исполняет прежний код и отдаёт прежние байты. Переход делается по одной
# витрине, и откат — это возврат одного поля манифеста.

ОФОРМЛЕНИЕ_1_1 = "1.1.0"

#: Версия оформления Zona и Animedia, переработанных по измеренным эталонам
#: (TEMPLATES-ZONA-ANIMEDIA-VISUAL-PARITY-006). Lords остаётся на 1.1.0 и
#: поэтому отдаёт прежние байты: его ветка кода не меняется вовсе.
ОФОРМЛЕНИЕ_1_2 = "1.2.0"
ОФОРМЛЕНИЕ_1_2_1 = "1.2.1"
ОФОРМЛЕНИЕ_1_2_2 = "1.2.2"
ОФОРМЛЕНИЕ_1_2_3 = "1.2.3"
ОФОРМЛЕНИЕ_1_2_4 = "1.2.4"

#: Версии, несущие оформление 1.1+. Набор, а не одно значение: витрина
#: включает оформление СВОИМ манифестом, и добавление следующей версии не
#: должно переводить на неё соседей. Свойство «переход по одной витрине»
#: сохраняется — меняется только то, сколько версий код умеет исполнять.
ОФОРМЛЕНИЕ_ВЕРСИИ = {ОФОРМЛЕНИЕ_1_1, ОФОРМЛЕНИЕ_1_2, ОФОРМЛЕНИЕ_1_2_1, ОФОРМЛЕНИЕ_1_2_2, ОФОРМЛЕНИЕ_1_2_3, ОФОРМЛЕНИЕ_1_2_4}

#: Семейства, переработанные по измеренным эталонам, и версии, с которых
#: переработка включается. Ниже этого набора витрина исполняет прежние ветки.
#:
#: Проверка нужна потому, что артефакт ОДИН на шесть витрин. Без неё выкладка
#: артефакта ради Animedia сменила бы оформление боевой Zona, которая стоит на
#: 1.1.0 и о смене не просила, — то есть ровно то, что запрещает принцип
#: «переход делается по одной витрине». Здесь оформление 1.2.x достаётся
#: только той витрине, чей манифест его объявил.
ПЕРЕРАБОТАНО_С = {
    "zona": frozenset({ОФОРМЛЕНИЕ_1_2}),
    "animedia": frozenset({ОФОРМЛЕНИЕ_1_2, ОФОРМЛЕНИЕ_1_2_1, ОФОРМЛЕНИЕ_1_2_2, ОФОРМЛЕНИЕ_1_2_3, ОФОРМЛЕНИЕ_1_2_4}),
}

#: Исполняет ли ЭТА витрина переработанное оформление своего семейства.
ОФОРМЛЕНИЕ_ПЕРЕРАБОТАННОЕ = ВЕРСИЯ in ПЕРЕРАБОТАНО_С.get(СЕМЕЙСТВО, ())

#: Включено ли новое оформление на ЭТОЙ витрине. Решает манифест витрины, а не
#: наличие кода: один артефакт обслуживает шесть витрин, и переход делается по
#: одной. Витрина на 1.0.2 исполняет прежние ветки и отдаёт прежние байты.
ОФОРМЛЕНИЕ_НОВОЕ = (ВЕРСИЯ in ОФОРМЛЕНИЕ_ВЕРСИИ)

#: Сколько карточек на странице каталога в новом оформлении. Кратно и шести
#: (сетка Lords), и четырём (сетка Zona), поэтому последний ряд не рваный.
НА_СТРАНИЦЕ_1_1 = 48

#: Сколько серий показывается в одном блоке списка серий. Ограничения на общее
#: число серий нет: список из двухсот десяти обязан содержать все двести
#: десять. Разбиение здесь — только визуальное, по десяткам.
СЕРИЙ_В_РЯДУ = 10


class Подробности:
    """Боковой файл подробностей. Отсутствие файла — это пустой словарь.

    Витрина обязана подниматься и без подробностей: страница тайтла тогда
    строится на полях снимка. Падать из-за отсутствия дополнения значило бы
    менять «меньше данных» на «нет сайта».
    """

    def __init__(self, путь: str):
        self.записи: dict = {}
        self.источник = ""
        self.покрытие = 0
        self.catalog_revision = ""
        self.catalog_built_at = ""
        if not путь:
            return
        try:
            сырое = json.loads(Path(путь).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        записи = сырое.get("details")
        if isinstance(записи, dict):
            self.записи = записи
            self.источник = str(сырое.get("source") or "")
            self.покрытие = int(сырое.get("details_total") or 0)
            self.catalog_revision = str(сырое.get("catalog_revision") or "")
            self.catalog_built_at = str(сырое.get("catalog_built_at") or "")

    def get(self, slug: str) -> dict:
        значение = self.записи.get(slug)
        return значение if isinstance(значение, dict) else {}


def всего_серий(деталь: dict) -> int:
    return sum(int(с.get("eps") or 0) for с in (деталь.get("seasons") or []))


def сезон_по_номеру(деталь: dict, номер: int) -> dict | None:
    for с in (деталь.get("seasons") or []):
        if int(с.get("n") or 0) == номер:
            return с
    return None


# ----------------------------------------------------------------------
#  Оформление: токены и разметка у каждого семейства свои
# ----------------------------------------------------------------------
#
# Различие здесь не «другой акцентный цвет». Отличаются композиция страницы,
# типографическая система, геометрия карточки и раскладка страницы тайтла —
# то есть ровно то, по чему семейство узнают без логотипа.
#
#   Lords — узкий светлый лист на тёмной подложке, плотная сетка в шесть
#           колонок, название поверх постера, оценки полосой под постером,
#           шапка в одну строку, страница тайтла: постер слева, сюжет справа,
#           затем таблица фактов в две колонки.
#
#   Zona  — постоянная боковая колонка слева и содержимое во всю оставшуюся
#           ширину, крупная шрифтовая пара с засечками в заголовках, карточки
#           списком-строкой с постером слева, шапка в два ряда, страница
#           тайтла: широкий баннер, постер внахлёст, полоса оценок, затем
#           основной текст и колонка фактов справа.
#
# Тему пользователь больше не переключает, и это решение, а не упущение.
# Переключатель существовал, светлая ветка задавала только часть переменных, и
# именно из неё выходил нечитаемый текст. Одна объявленная палитра на
# семейство закрывает целый класс дефектов наследования.

# Зелёный здесь темнее, чем на эталоне, и это осознанный выбор, а не промах
# по цвету. Белый текст на зелёном эталона даёт контраст около 2.2 — вдвое
# ниже требуемых 4.5. Оттенок семейства сохранён, светлота опущена до той, при
# которой надпись на кнопке читается: измерено, а не оценено на глаз
# (`scripts/lords_zona_visual_audit.cjs`, проба контраста).
#
#   acc   — фон под БЕЛЫМ текстом (кнопки, таблетки, значки): 5.03:1
#   accdk — зелёный ТЕКСТ на светлом (ссылки, крошки): 6.17:1 на фоне крошек
ЛОРДС_ТОКЕНЫ = {
    "ink": "#1f2329", "dim": "#5b6470", "page": "#111111", "sheet": "#eef1f4",
    "card": "#ffffff", "line": "#d7dde3", "acc": "#3f7d26", "accdk": "#2f5e1c",
    "kp": "#b34700", "imdb": "#f5c518", "bar": "#171a1e",
    "mute": "#5f6874", "onbar": "#8a939e",
}

# Палитра Zona 1.2.0 измерена на эталоне (`tests/tools/measure_reference_palette.js`,
# 2026-09-14): подложка rgb(30,37,43), текст белый, поверхность шапки
# rgb(84,103,120). Взяты ИЗМЕРЕНИЯ, а не разметка эталона: оформление ниже
# написано своё.
#
# Акцент разведён на две роли по той же причине, что и у Lords. Синий эталона
# rgb(0,119,255) как ТЕКСТ на подложке даёт 3.6:1 — ниже требуемых 4.5.
# Поэтому:
#   acc   — синий ТЕКСТ на тёмном (ссылки, пункты): 6.3:1
#   accdk — фон под БЕЛЫМ текстом (кнопки, активный пункт): 6.2:1
#: Палитра прежнего оформления Zona 1.1.0 — светлый лист с засечками.
ЗОНА_ТОКЕНЫ_1_1 = {
    "ink": "#16191d", "dim": "#59616b", "page": "#ffffff", "alt": "#f5f7fa",
    "rail": "#10161f", "railink": "#e8edf5", "line": "#e3e8ee",
    "acc": "#1a5fd0", "accdk": "#14489f", "warm": "#8a5a00",
    "mute": "#5f6874",
}

ЗОНА_ТОКЕНЫ = {
    "ink": "#ffffff", "dim": "#aeb9c5", "page": "#1e252b", "alt": "#28303a",
    "rail": "#546778", "railink": "#ffffff", "line": "#3a4450",
    "acc": "#4d9bff", "accdk": "#0a5bd0", "warm": "#ffb454",
    "mute": "#8d9aa8", "surf": "#232b34",
}

# Палитра Animedia 1.2.0 измерена на эталоне (`tests/tools/measure_reference_palette.js`,
# 2026-09-14): основа rgb(255,255,255), текст rgb(22,22,22), акцент rgb(197,7,37),
# служебные поверхности rgb(249,249,249) и rgb(240,240,240). Это измерения;
# оформление ниже написано своё.
#
#   acc   — красный ТЕКСТ на белом: 7.4:1
#   accdk — фон под БЕЛЫМ текстом: тот же красный, белое на нём 7.4:1
АНИМЕДИА_ТОКЕНЫ = {
    "ink": "#161616", "dim": "#5c6370", "page": "#ffffff", "alt": "#f9f9f9",
    "rail": "#ffffff", "railink": "#161616", "line": "#e4e4e4",
    "acc": "#c50725", "accdk": "#c50725", "warm": "#b26a00",
    "mute": "#757b85", "surf": "#f0f0f0",
}

#: Общая часть: сброс, доступность и то, что обязано быть на каждой странице
#: любого семейства. Всё остальное расходится.
ОБЩЕЕ_1_1 = """
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;overflow-x:clip;max-width:100%}
body{margin:0;min-height:100vh;overflow-x:clip;max-width:100%}
img,video,iframe,svg{max-width:100%;height:auto;display:block}
a{text-decoration:none;color:inherit}
.vh{position:absolute;width:1px;height:1px;margin:-1px;padding:0;overflow:hidden;
clip:rect(0 0 0 0);white-space:nowrap;border:0}
:focus-visible{outline:3px solid @ACC@;outline-offset:2px;border-radius:3px}
.skip{position:absolute;left:-9999px;top:0;z-index:200;padding:10px 16px;background:@ACC@;color:#fff}
.skip:focus{left:8px;top:8px}
"""


def _общее(токены: dict) -> str:
    return ОБЩЕЕ_1_1.replace("@ACC@", токены["acc"])


ЛОРДС_СТИЛЬ = """
body{background:@PAGE@;color:@INK@;
font:14px/1.5 'Open Sans','Segoe UI',system-ui,-apple-system,sans-serif}
/* Лист. Узкая светлая полоса на тёмной подложке — первое, по чему семейство
   узнают; ширина взята из измерения эталона на 1440 (контейнер 1100). */
.sheet{max-width:1100px;margin:0 auto;background:@SHEET@;min-height:100vh;
box-shadow:0 0 60px #0009}
@media(min-width:1000px){.sheet{margin-top:118px;min-height:calc(100vh - 118px)}}
.pad{padding:0 18px}
.backdrop{position:fixed;inset:0 0 auto 0;height:330px;z-index:-1;
background:radial-gradient(120% 140% at 50% 0,#243043 0,#0e1013 68%)}
/* Шапка в одну строку на десктопе; на узком — burger + drawer. */
.hd{background:@CARD@;border-bottom:1px solid @LINE@;position:sticky;top:0;z-index:40}
.hd__in{display:flex;align-items:center;gap:12px;min-height:56px;padding:0 12px}
@media(min-width:768px){.hd__in{height:62px;padding:0 18px;gap:18px}}
.hd__logo{display:flex;align-items:center;gap:9px;font-weight:800;font-size:17px;
letter-spacing:.5px;text-transform:uppercase;color:@INK@;flex:0 0 auto}
@media(min-width:768px){.hd__logo{font-size:19px}}
.hd__mark{width:30px;height:30px;border-radius:5px;background:@ACC@;color:#fff;
display:grid;place-items:center;font-size:15px;font-weight:800}
.hd__menu{display:inline-flex;align-items:center;justify-content:center;
width:44px;height:44px;border:1px solid @LINE@;border-radius:4px;background:#fff;
color:@INK@;font-size:20px;cursor:pointer;margin-left:auto;flex:0 0 auto}
@media(min-width:768px){.hd__menu{display:none}}
.hd__nav{display:none;flex-direction:column;gap:4px;flex:1 0 100%;order:5;
padding:8px 0 12px;border-top:1px solid @LINE@}
.hd__nav.is-open{display:flex}
@media(min-width:768px){.hd__nav{display:flex;flex-direction:row;flex:1;order:0;
flex-wrap:wrap;padding:0;border:0;gap:2px}}
.hd__nav a{padding:12px 14px;border-radius:4px;font-size:14px;font-weight:700;
text-transform:uppercase;letter-spacing:.3px;color:#39414a;min-height:44px;
display:flex;align-items:center}
@media(min-width:768px){.hd__nav a{padding:8px 11px;font-size:13px;min-height:0}}
.hd__nav a:hover{background:@SHEET@;color:@ACCDK@}
.hd__nav a[aria-current]{color:@ACCDK@;box-shadow:inset 0 -2px 0 @ACC@}
.hd__s{display:flex;border:1px solid @LINE@;border-radius:4px;overflow:hidden;background:#fff;
flex:1 1 auto;min-width:0;max-width:100%}
@media(min-width:768px){.hd__s{flex:0 1 220px}}
.hd__s input{border:0;padding:10px 11px;font-size:13px;width:100%;min-width:0;color:@INK@;background:#fff}
.hd__s button{border:0;background:#fff;color:#6a737d;padding:0 12px;cursor:pointer;font-size:14px;
min-width:44px;min-height:44px}
.hd__s button:hover{color:@ACCDK@}
body.nav-lock{overflow:hidden}
/* Заголовок раздела: настоящий H2 + «Весь раздел». */
.lead{font-size:20px;font-weight:600;color:#3a4149;margin:16px 0 12px}
.sec-rail{margin:0 0 18px}
.sec-rail__h{display:flex;align-items:baseline;justify-content:space-between;gap:12px;
margin:0 0 12px;flex-wrap:wrap}
.sec-rail__h h2{margin:0;font-size:18px;font-weight:700;color:@INK@}
.sec-rail__h h2 a{color:inherit;text-decoration:none}
.sec-rail__h h2 a:hover{color:@ACCDK@}
.sec-rail__h .sec-rail__all{font-size:13px;font-weight:700;color:@ACCDK@;padding:8px 4px;
min-height:44px;display:inline-flex;align-items:center}
.tabs{display:flex;gap:7px;align-items:center;flex-wrap:wrap;margin:0 0 12px}
.tabs__pill{display:inline-flex;align-items:center;gap:7px;background:@ACC@;color:#fff;
font-weight:700;font-size:15px;padding:10px 18px;border-radius:4px}
.tabs a{background:@CARD@;border:1px solid @LINE@;border-radius:4px;padding:9px 15px;
font-size:13px;color:#4a535d;font-weight:600;min-height:44px;display:inline-flex;align-items:center}
.tabs a:hover{color:@ACCDK@;border-color:@ACC@}
.tabs a[aria-current]{background:@BAR@;color:#fff;border-color:@BAR@}
/* Сетка в шесть колонок с тесными желобами. */
.grid{display:grid;gap:8px;grid-template-columns:repeat(2,1fr)}
@media(min-width:520px){.grid{grid-template-columns:repeat(3,1fr)}}
@media(min-width:860px){.grid{grid-template-columns:repeat(4,1fr)}}
@media(min-width:1080px){.grid{grid-template-columns:repeat(6,1fr)}}
/* Карточка: постер 2:3, подпись фиксированной высоты, весь блок кликабелен. */
.c{position:relative;display:flex;flex-direction:column;background:@BAR@;overflow:hidden;border-radius:3px;
color:inherit;text-decoration:none;height:100%}
.c:focus-visible{outline:2px solid @ACC@;outline-offset:2px}
.c:hover .c__img{transform:scale(1.04)}
.c__p{display:block;position:relative;aspect-ratio:2/3;overflow:hidden;background:#22272e;flex:0 0 auto}
.c__img{position:relative;z-index:1;width:100%;height:100%;object-fit:cover;
transition:transform .25s}
.c__none{position:absolute;inset:0;display:grid;place-items:center;text-align:center;
padding:10px;color:#8b95a1;font-size:12px;font-weight:600;
background:repeating-linear-gradient(135deg,#242a32 0 9px,#1e242b 9px 18px)}
.c__none b{display:block;font-size:26px;margin-bottom:4px;color:#aab4c0}
.c__badge{position:absolute;z-index:2;top:6px;left:6px;background:@ACC@;color:#fff;font-size:11px;
font-weight:700;padding:3px 7px;border-radius:3px;max-width:calc(100% - 12px);
overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.c__cap{display:flex;flex-direction:column;justify-content:flex-end;gap:2px;
height:66px;padding:8px 7px;text-align:center;background:#11161c;flex:0 0 66px;
box-sizing:border-box}
.c__t{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;
color:#fff;font-size:13.5px;font-weight:700;line-height:1.25;margin:0}
.c__y{display:block;color:#c5ccd4;font-size:12px}
.c__r{display:flex;justify-content:space-between;align-items:center;gap:6px;
padding:6px 8px;background:@BAR@;font-size:12px;font-weight:700;min-height:30px;
box-sizing:border-box;flex:0 0 auto}
.c__kp{color:#ff8b3d}.c__imdb{color:@IMDB@}
.c__r span i{font-style:normal;color:#fff;margin-left:4px}
.c__r em{font-style:normal;color:@ONBAR@;font-weight:600}
/* Листалка. */
.pg{display:flex;gap:6px;justify-content:center;flex-wrap:wrap;margin:22px 0 8px}
.pg a,.pg span{min-width:36px;text-align:center;padding:8px 10px;border-radius:4px;
border:1px solid @LINE@;background:@CARD@;font-size:13px;font-weight:600;color:#4a535d}
.pg span[aria-current]{background:@ACC@;border-color:@ACC@;color:#fff}
.pg em{border:0;background:0;font-style:normal;color:@DIM@;align-self:center}
/* Крошки, страница тайтла. */
.crumbs{background:#e3e7eb;border-bottom:1px solid @LINE@;font-size:12px;color:#5b6470;
padding:9px 18px}
.crumbs a{color:@ACCDK@;font-weight:600;display:inline-block;padding:5px 2px}
.crumbs b{font-weight:600;color:@INK@}
.tw{display:grid;grid-template-columns:1fr;gap:18px;background:@CARD@;padding:18px;
margin:14px 0;border:1px solid @LINE@;border-radius:4px}
@media(min-width:720px){.tw{grid-template-columns:180px 1fr}}
.tw__ps{position:relative;border-radius:4px;overflow:hidden;background:#22272e;aspect-ratio:2/3}
.tw__ps img,.tw__img{position:relative;z-index:1;width:100%;height:100%;
object-fit:cover;display:block}
.tw__ps .c__none{font-size:13px}
.tw h1{font-size:20px;line-height:1.3;font-weight:600;margin:0 0 12px;color:@INK@}
.plot p{margin:0 0 10px;font-size:13.5px;line-height:1.62;color:#333a42}
.plot .none{color:@DIM@;font-style:italic}
.plot a{display:inline-block;padding:5px 2px;color:@ACCDK@;font-weight:600}
.facts{display:grid;grid-template-columns:1fr;gap:4px 26px;margin:14px 0 0;font-size:13px}
@media(min-width:720px){.facts{grid-template-columns:1fr 1fr}}
.facts div{display:flex;gap:6px;padding:3px 0;border-bottom:1px dotted #dfe4e9}
.facts dt{font-weight:700;color:#39414a;flex:0 0 auto}
.facts dd{margin:0;color:#4d555e}
.facts a{color:@ACCDK@;font-weight:600;display:inline-block;padding:5px 2px}
/* Высота ссылки жанра — 14 px по строке, и пальцем в неё не попасть.
   Измерено пробой целей касания: 238 попаданий ниже 24 px, и все —
   эти ссылки. Отступ поднимает цель до 24 px, не меняя типографики. */
.rates{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0 0}
.rate{border:2px solid;border-radius:4px;padding:8px 14px;font-size:13px;font-weight:700;
background:#fff}
.rate--kp{border-color:@KP@;color:@KP@}
.rate--imdb{border-color:#9a7b00;color:#6f5900}
.rate small{display:block;font-weight:600;font-size:11px;color:@DIM@;margin-top:2px}
.claim{text-align:center;font-weight:700;font-size:15px;color:#3a4149;margin:18px 0 0}
/* Плеер: полоса вкладок и поле 16:9. */
.pl{margin:14px 0}
.pl__bar{display:flex;align-items:center;gap:4px;background:@BAR@;padding:0 8px;
flex-wrap:wrap;border-radius:4px 4px 0 0}
.pl__tab{padding:12px 18px;font-size:13px;font-weight:700;color:#b9c2cc}
.pl__tab[aria-current]{background:@ACC@;color:#fff;border-radius:3px 3px 0 0}
.pl__note{margin-left:auto;color:#8d97a2;font-size:12px;padding:12px 4px}
.pl__frame{position:relative;aspect-ratio:16/9;background:#05070a;display:grid;
place-items:center;border-radius:0 0 4px 4px;overflow:hidden}
.pl__frame[data-state="awaiting"],
.pl__frame[data-state="unavailable"],
.pl__frame[data-state="nosource"],
.pl__frame[data-state="idle"]{aspect-ratio:auto;min-height:140px;max-height:180px}
.pl__frame video-player{display:block;width:100%;height:100%}
.pl__state{max-width:520px;text-align:center;padding:26px 20px;color:#d6dde5}
.pl__state b{display:block;font-size:16px;margin-bottom:8px;color:#fff}
.pl__state p{margin:0;font-size:13.5px;line-height:1.6;color:#aeb8c3}
.pl__state code{background:#151a20;padding:2px 6px;border-radius:3px;font-size:12px;color:#cfd8e2}
/* Сезоны и серии. */
.sec{background:@CARD@;border:1px solid @LINE@;border-radius:4px;padding:16px 18px;margin:14px 0}
.sec h2{font-size:16px;margin:0 0 12px;font-weight:700;color:@INK@}
.sea{margin:0 0 16px}
.sea__h{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin:0 0 9px}
.sea__h h3{margin:0;font-size:14px;font-weight:700}
.sea__h span{font-size:12px;color:@DIM@}
.eps{display:flex;flex-wrap:wrap;gap:8px}
.eps a{min-width:44px;min-height:44px;text-align:center;padding:10px 8px;border:1px solid @LINE@;
border-radius:3px;font-size:13px;font-weight:600;background:#fff;color:#3f4750;
display:inline-flex;align-items:center;justify-content:center;box-sizing:border-box}
.eps a:hover{border-color:@ACC@;color:@ACCDK@}
.eps a[aria-current]{background:@ACC@;border-color:@ACC@;color:#fff}
.eps a[data-off]{color:@MUTE@;background:#f3f5f7;pointer-events:none}
.epnav{display:flex;justify-content:space-between;gap:10px;margin:14px 0 0;flex-wrap:wrap}
.epnav a,.epnav span{padding:12px 14px;border:1px solid @LINE@;border-radius:4px;
font-size:13px;font-weight:600;background:#fff;color:#3f4750;min-height:44px;
display:inline-flex;align-items:center;box-sizing:border-box}
.epnav span{color:@MUTE@;background:#f3f5f7}
/* Похожее и подвал. */
.rel{display:grid;gap:8px;grid-template-columns:repeat(3,1fr)}
@media(min-width:860px){.rel{grid-template-columns:repeat(6,1fr)}}
.empty{background:@CARD@;border:1px solid @LINE@;border-radius:4px;padding:44px 22px;
text-align:center;color:#4d555e;margin:14px 0}
.empty b{display:block;font-size:17px;color:@INK@;margin-bottom:8px}
.empty a{display:inline-block;padding:6px 2px;color:@ACCDK@;font-weight:600}
.nf{text-align:center;padding:56px 20px}
.nf b{display:block;font-size:64px;font-weight:800;color:@ACC@;line-height:1}
.nf h1{font-size:20px;font-weight:600;margin:10px 0 8px}
.nf p{color:#4d555e;margin:0 auto 18px;max-width:460px}
.nf a{display:inline-block;background:@ACC@;color:#fff;font-weight:700;padding:11px 22px;
border-radius:4px}
.ft{background:@CARD@;border-top:1px solid @LINE@;margin-top:26px;padding:22px 18px 16px;
color:#5b6470;font-size:13px}
.ft__cols{display:grid;gap:18px;grid-template-columns:1fr;margin-bottom:16px}
@media(min-width:720px){.ft__cols{grid-template-columns:repeat(4,1fr)}}
.ft__col b{display:block;font-size:12px;text-transform:uppercase;letter-spacing:.4px;
color:@INK@;margin-bottom:8px}
.ft__col a{display:block;padding:6px 0;color:#4a535d;font-weight:600;min-height:44px}
.ft__col a:hover{color:@ACCDK@}
.ft__about{font-size:12.5px;line-height:1.5;color:#5b6470;max-width:52ch;margin:0 0 12px}
.ft__bar{display:flex;justify-content:flex-end;align-items:center;gap:10px;
border-top:1px solid @LINE@;padding-top:10px}
.vb{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11.5px;color:#4d555e;
padding:4px 8px;background:transparent;border:0;cursor:help}
.hub{display:grid;gap:12px;grid-template-columns:1fr;margin:14px 0}
@media(min-width:600px){.hub{grid-template-columns:repeat(2,1fr)}}
@media(min-width:1000px){.hub{grid-template-columns:repeat(3,1fr)}}
.hub__c{display:block;padding:14px;border:1px solid @LINE@;border-radius:6px;background:@CARD@;
color:inherit;text-decoration:none;min-height:120px}
.hub__c:hover{border-color:@ACC@}
.hub__c b{display:block;font-size:15px;margin-bottom:6px;color:@INK@}
.hub__c p{margin:0;font-size:12.5px;color:#5b6470;line-height:1.45}
.hub__c span{display:block;margin-top:10px;font-size:12px;color:@ACCDK@;font-weight:700}

img[hidden]{display:none}

/* Оценки по источникам. Разметка общая, вид свой у каждого семейства. */
.rbs{margin:14px 0;display:flex;flex-direction:column;gap:8px}
.rbs__l{display:flex;flex-wrap:wrap;gap:8px;margin:0;padding:0;list-style:none}
.rbs__i{display:flex;align-items:baseline;gap:6px;padding:6px 11px;border-radius:6px;
white-space:nowrap}
.rbs__s{font-size:11.5px;font-weight:700;letter-spacing:.04em;text-transform:uppercase}
.rbs__n{font-size:15px;font-weight:700;font-variant-numeric:tabular-nums}
.rbs__n small{font-size:11px;font-weight:400;opacity:.72}
.rbs__v{font-size:11px;opacity:.75;font-variant-numeric:tabular-nums}
.rbs__l--own{border-top:1px dashed currentColor;padding-top:8px;margin-top:2px;opacity:.95}
.rbs--none{margin:14px 0;font-size:13px;font-style:italic}
@media(max-width:400px){.rbs__i{padding:5px 8px}.rbs__n{font-size:14px}}
.rbs__i{background:@CARD@;border:1px solid @LINE@;color:@INK@}
.rbs__s{color:@ACCDK@}
.rbs__i[data-source=imdb] .rbs__n{color:@KP@}
.rbs__l--own{color:@DIM@}
.rbs--none{color:@MUTE@}

"""

#: Прежнее оформление Zona 1.1.0. Оставлено намеренно: артефакт один на
#: шесть витрин, и витрина, чей манифест остался на 1.1.0, обязана отдавать
#: ПРЕЖНИЕ байты даже после выкладки этого файла ради соседа.
ЗОНА_СТИЛЬ_1_1 = """
body{background:@PAGE@;color:@INK@;
font:16px/1.62 'PT Serif',Georgia,'Times New Roman',serif}
/* Композиция: постоянная боковая колонка слева, содержимое во всю ширину. */
.zs{display:grid;grid-template-columns:1fr;max-width:1440px;margin:0 auto;min-height:100vh}
@media(min-width:1000px){.zs{grid-template-columns:246px 1fr}}
.zrail{background:@RAIL@;color:@RAILINK@;padding:20px 18px 30px}
@media(min-width:1000px){.zrail{position:sticky;top:0;height:100vh;overflow:auto}}
.zrail__logo{font-size:22px;font-weight:700;letter-spacing:-.3px;color:#fff;
display:block;margin:0 0 4px}
.zrail__sub{font-size:12.5px;color:#8e9bad;font-family:system-ui,sans-serif;margin:0 0 22px}
.zrail__t{font-size:11px;letter-spacing:1.4px;text-transform:uppercase;color:#79879b;
font-family:system-ui,sans-serif;font-weight:700;margin:20px 0 8px}
.zrail__n{display:flex;flex-direction:column;gap:1px}
.zrail__n a{padding:9px 12px;border-radius:6px;font-size:15px;color:#d3dbe6;
font-family:system-ui,sans-serif}
.zrail__n a:hover{background:#1c2532;color:#fff}
.zrail__n a[aria-current]{background:@ACC@;color:#fff;font-weight:600}
.zrail__g{display:flex;flex-wrap:wrap;gap:5px}
.zrail__g a{font-size:12.5px;font-family:system-ui,sans-serif;padding:5px 9px;
border:1px solid #2a3341;border-radius:999px;color:#b9c4d2}
.zrail__g a:hover{border-color:@ACC@;color:#fff}
.zmain{min-width:0;padding:0 0 40px}
/* Шапка содержимого в два ряда: поиск, затем состояние выборки. */
.ztop{border-bottom:1px solid @LINE@;background:@PAGE@;position:sticky;top:0;z-index:40}
.ztop__a{display:flex;align-items:center;gap:16px;padding:14px 26px}
.ztop__s{flex:1;display:flex;border:2px solid @LINE@;border-radius:8px;overflow:hidden;
background:#fff;max-width:640px}
.ztop__s input{flex:1;border:0;padding:11px 14px;font-size:15px;
font-family:system-ui,sans-serif;color:@INK@}
.ztop__s button{border:0;background:@ACC@;color:#fff;padding:0 20px;font-weight:600;
font-family:system-ui,sans-serif;font-size:14px;cursor:pointer}
.ztop__b{display:flex;gap:18px;padding:0 26px 12px;font-size:13.5px;
font-family:system-ui,sans-serif;color:@DIM@;flex-wrap:wrap}
.ztop__b a{color:@ACC@;font-weight:600;display:inline-block;padding:5px 2px}
.ztop__b a[aria-current]{color:@INK@;box-shadow:inset 0 -2px 0 @ACC@}
.zwrap{padding:0 26px}
/* Крупная шрифтовая пара: заголовки с засечками, служебный текст без. */
.zh{font-size:30px;line-height:1.2;font-weight:700;margin:26px 0 6px;letter-spacing:-.4px}
.zh--sm{font-size:22px;margin:30px 0 6px}
.zsub{font-family:system-ui,sans-serif;font-size:14px;color:@DIM@;margin:0 0 20px}
.zsub a{display:inline-block;padding:5px 2px;color:@ACC@;font-weight:600}
/* Главная: карточки-плитки, постер сверху, текст снизу, полоса оценок внизу. */
.zg{display:grid;gap:22px;grid-template-columns:repeat(2,1fr)}
@media(min-width:700px){.zg{grid-template-columns:repeat(3,1fr)}}
@media(min-width:1180px){.zg{grid-template-columns:repeat(4,1fr)}}
.zt{display:flex;flex-direction:column;background:#fff;border:1px solid @LINE@;
border-radius:10px;overflow:hidden;transition:box-shadow .18s,transform .18s}
.zt:hover{box-shadow:0 10px 30px #16191d1f;transform:translateY(-3px)}
.zt__p{display:block;aspect-ratio:2/3;background:@ALT@;position:relative;flex:0 0 auto}
.zt__p img,.zt__img{position:relative;z-index:1;width:100%;height:100%;
object-fit:cover;display:block}
.zt__none{position:absolute;inset:0;display:grid;place-items:center;padding:14px;
text-align:center;color:@MUTE@;font-family:system-ui,sans-serif;font-size:13px;
background:linear-gradient(160deg,#eef1f6,#dfe5ed)}
.zt__b{display:block;padding:13px 14px 10px;flex:1}
.zt__t{display:block;font-size:17px;line-height:1.3;font-weight:700;margin:0 0 5px}
.zt__m{display:block;font-family:system-ui,sans-serif;font-size:13px;color:@DIM@}
.zt__r{display:flex;gap:12px;padding:9px 14px;border-top:1px solid @LINE@;
background:@ALT@;font-family:system-ui,sans-serif;font-size:13px;font-weight:600}
.zt__r b{color:@ACC@}.zt__r i{font-style:normal;color:@WARM@}
.zt__r em{font-style:normal;color:@MUTE@;font-weight:500}
/* Каталог и поиск: строки-списки, постер слева. Это не сетка главной. */
.zl{display:flex;flex-direction:column;gap:2px}
.zr{display:grid;grid-template-columns:74px 1fr;gap:16px;padding:14px 12px;
border-radius:10px;align-items:start}
@media(min-width:700px){.zr{grid-template-columns:92px 1fr}}
.zr:hover{background:@ALT@}
.zr+.zr{border-top:1px solid @LINE@}
.zr__p{display:block;aspect-ratio:2/3;border-radius:6px;overflow:hidden;background:@ALT@;position:relative}
.zr__p img,.zr__img{position:relative;z-index:1;width:100%;height:100%;
object-fit:cover;display:block}
.zr__none{position:absolute;inset:0;display:grid;place-items:center;font-size:11px;
text-align:center;color:@MUTE@;font-family:system-ui,sans-serif;padding:6px;
background:linear-gradient(160deg,#eef1f6,#dfe5ed)}
.zr__t{display:block;font-size:19px;font-weight:700;margin:0 0 4px;line-height:1.28}
.zr__m{display:block;font-family:system-ui,sans-serif;font-size:13.5px;color:@DIM@;margin:0 0 6px}
.zr__d{display:block;font-size:14.5px;color:#39414a;margin:0;
display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.zr__r{display:flex;gap:12px;margin-top:7px;font-family:system-ui,sans-serif;
font-size:13px;font-weight:600}
.zr__r b{color:@ACC@}.zr__r i{font-style:normal;color:@WARM@}
/* Листалка — крупная, текстовая, не плитками. */
.zpg{display:flex;gap:10px;align-items:center;justify-content:center;flex-wrap:wrap;
margin:32px 0;font-family:system-ui,sans-serif;font-size:14px}
.zpg a{padding:9px 15px;border:1px solid @LINE@;border-radius:8px;font-weight:600;color:@ACC@}
.zpg a:hover{border-color:@ACC@;background:@ALT@}
.zpg span[aria-current]{padding:9px 15px;border-radius:8px;background:@ACC@;color:#fff;font-weight:600}
.zpg em{font-style:normal;color:@DIM@}
/* Страница произведения: широкий баннер, постер внахлёст, полоса оценок. */
.zcr{font-family:system-ui,sans-serif;font-size:13px;color:@DIM@;padding:14px 26px 0}
.zcr a{color:@ACC@;font-weight:600;display:inline-block;padding:5px 2px}
.zban{position:relative;margin:12px 26px 0;border-radius:14px;min-height:186px;
background:linear-gradient(120deg,#1a2433,#0f1620 60%,#16233a);overflow:hidden}
.zban__img{position:absolute;inset:0;opacity:.42}
.zban__img img{width:100%;height:100%;object-fit:cover}
.zhead{display:grid;grid-template-columns:1fr;gap:20px;padding:0 26px;margin:-92px 0 0;
position:relative;z-index:2}
@media(min-width:760px){.zhead{grid-template-columns:186px 1fr;align-items:end}}
.zhead__ps{border-radius:12px;overflow:hidden;aspect-ratio:2/3;background:@ALT@;
box-shadow:0 14px 40px #0000004d;border:4px solid #fff;position:relative}
.zhead__ps img,.zhead__img{position:relative;z-index:1;width:100%;height:100%;
object-fit:cover;display:block}
.zhead__x{padding:0 0 10px}
.zhead h1{font-size:32px;line-height:1.18;margin:0 0 6px;letter-spacing:-.5px}
@media(max-width:759px){.zhead h1{font-size:25px}}
.zhead__o{font-family:system-ui,sans-serif;font-size:14px;color:@DIM@;margin:0 0 10px}
.zstrip{display:flex;flex-wrap:wrap;gap:10px;margin:18px 26px 0;padding:14px 16px;
background:@ALT@;border:1px solid @LINE@;border-radius:12px;
font-family:system-ui,sans-serif;font-size:14px}
.zstrip div{display:flex;flex-direction:column;gap:2px;padding-right:18px}
.zstrip div+div{border-left:1px solid @LINE@;padding-left:18px}
.zstrip dt{font-size:11.5px;letter-spacing:.9px;text-transform:uppercase;color:@DIM@;font-weight:700}
.zstrip dd{margin:0;font-size:17px;font-weight:700;color:@INK@}
.zstrip .zacc{color:@ACC@}.zstrip .zwarm{color:@WARM@}
/* Тело: основной текст слева, факты колонкой справа. */
.zbody{display:grid;grid-template-columns:1fr;gap:28px;padding:0 26px;margin:26px 0 0}
@media(min-width:980px){.zbody{grid-template-columns:minmax(0,1fr) 316px}}
.zsec{margin:0 0 28px}
.zsec h2{font-size:22px;margin:0 0 10px;font-weight:700}
.zsec p{margin:0 0 12px;font-size:16px;line-height:1.7}
.zsec .none{color:@DIM@;font-style:italic;font-size:15px}
.zaside{font-family:system-ui,sans-serif;font-size:14px}
.zaside dl{margin:0;background:@ALT@;border:1px solid @LINE@;border-radius:12px;padding:16px 18px}
.zaside div{padding:7px 0}
.zaside div+div{border-top:1px solid @LINE@}
.zaside dt{font-size:11.5px;letter-spacing:.9px;text-transform:uppercase;color:@DIM@;
font-weight:700;margin-bottom:3px}
.zaside dd{margin:0;color:@INK@;line-height:1.5}
.zaside a{color:@ACC@;font-weight:600;display:inline-block;padding:5px 2px}
/* Ссылки жанров в колонке фактов Zona были 16px по высоте — та же
   болезнь, что раньше вылечили у Lords в `.facts a`, и ровно так же
   её нашла проба целей касания, а не чтение. */
/* Плеер Zona: без вкладок, рамка со скруглением и подпись сверху. */
.zpl{margin:0 26px}
.zpl__h{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;margin:0 0 10px}
.zpl__h h2{font-size:22px;margin:0;font-weight:700}
.zpl__h span{font-family:system-ui,sans-serif;font-size:13.5px;color:@DIM@}
.zpl__f{position:relative;aspect-ratio:16/9;background:#0c1017;border-radius:14px;
overflow:hidden;display:grid;place-items:center;border:1px solid @LINE@}
.zpl__f video-player{display:block;width:100%;height:100%}
.zpl__s{max-width:540px;text-align:center;padding:26px 22px;
font-family:system-ui,sans-serif;color:#cfd8e2}
.zpl__s b{display:block;font-size:17px;color:#fff;margin-bottom:8px;font-weight:600}
.zpl__s p{margin:0;font-size:14px;line-height:1.6;color:#a9b4c1}
.zpl__s code{background:#141a22;padding:2px 6px;border-radius:4px;font-size:12.5px;color:#cfd8e2}
/* Сезоны Zona: списком с подписями, а не плитками-номерами. */
.zsea{border:1px solid @LINE@;border-radius:12px;overflow:hidden;margin:0 0 16px}
.zsea__h{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;
background:@ALT@;padding:12px 16px;font-family:system-ui,sans-serif}
.zsea__h b{font-size:15px}
.zsea__h span{font-size:13px;color:@DIM@}
/* Хаб подборок: карточка коллекции, а не ещё одна сетка тайтлов. */
.zhub{display:grid;gap:12px;margin:14px 0;grid-template-columns:1fr}
@media(min-width:600px){.zhub{grid-template-columns:repeat(2,1fr)}}
@media(min-width:1000px){.zhub{grid-template-columns:repeat(3,1fr)}}
.zhub__c{display:block;padding:12px;border:1px solid @LINE@;border-radius:8px;
background:@SURF@;color:inherit;text-decoration:none}
.zhub__c:hover{border-color:@ACC@}
.zhub__g{display:flex;gap:4px;margin-bottom:9px}
.zhub__p{flex:1 1 0;aspect-ratio:2/3;overflow:hidden;border-radius:5px;background:@ALT@}
.zhub__img{width:100%;height:100%;object-fit:cover;display:block}
.zhub__t{display:block;font-weight:700;font-size:15.5px}
.zhub__m{display:block;font-size:12.5px;color:@ACC@;font-weight:600;margin:2px 0 4px}
.zhub__d{display:block;font-size:13px;color:@DIM@;line-height:1.45}

/* Окно просмотра списка серий ограничено; сам список не обрезается. */
.zeps{display:flex;flex-wrap:wrap;gap:6px;padding:14px 16px;max-height:70vh;
overflow-y:auto;overscroll-behavior:contain}
@media(min-width:768px){.zeps{max-height:520px}}
.zeps a{font-family:system-ui,sans-serif;font-size:13.5px;font-weight:600;padding:7px 12px;
border:1px solid @LINE@;border-radius:8px;color:@ACC@}
.zeps a:hover{background:@ALT@;border-color:@ACC@}
.zeps a[aria-current]{background:@ACC@;color:#fff;border-color:@ACC@}
.zeps a[data-off]{color:@MUTE@}
.zepnav{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;margin:18px 0 0;
font-family:system-ui,sans-serif;font-size:14px}
.zepnav a{padding:10px 16px;border:1px solid @LINE@;border-radius:8px;font-weight:600;color:@ACC@}
.zepnav span{padding:10px 16px;border:1px solid @LINE@;border-radius:8px;color:@MUTE@}
.zempty{padding:56px 24px;text-align:center;border:1px solid @LINE@;border-radius:14px;
background:@ALT@;margin:20px 0}
.zempty b{display:block;font-size:22px;margin-bottom:8px}
.zempty p{margin:0;font-family:system-ui,sans-serif;font-size:14.5px;color:@DIM@}
.zempty a{display:inline-block;padding:6px 2px;color:@ACC@;font-weight:600}
.znf{padding:70px 26px;text-align:center}
.znf b{display:block;font-size:78px;line-height:1;color:@ACC@;font-weight:700}
.znf h1{font-size:26px;margin:12px 0 10px}
.znf p{font-family:system-ui,sans-serif;font-size:15px;color:@DIM@;max-width:470px;
margin:0 auto 20px}
.znf a{display:inline-block;background:@ACC@;color:#fff;font-family:system-ui,sans-serif;
font-weight:600;padding:12px 24px;border-radius:8px}
.zft{border-top:1px solid @LINE@;margin:40px 26px 0;padding:22px 0 10px;
font-family:system-ui,sans-serif;font-size:13px;color:@DIM@;
display:flex;gap:14px;flex-wrap:wrap;justify-content:space-between;align-items:center}
.zvb{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11.5px;
border:1px solid @LINE@;border-radius:6px;padding:5px 9px;background:@ALT@;color:#4d555e}

img[hidden]{display:none}

/* Оценки по источникам. Разметка общая, вид свой у каждого семейства. */
.rbs{margin:14px 0;display:flex;flex-direction:column;gap:8px}
.rbs__l{display:flex;flex-wrap:wrap;gap:8px;margin:0;padding:0;list-style:none}
.rbs__i{display:flex;align-items:baseline;gap:6px;padding:6px 11px;border-radius:6px;
white-space:nowrap}
.rbs__s{font-size:11.5px;font-weight:700;letter-spacing:.04em;text-transform:uppercase}
.rbs__n{font-size:15px;font-weight:700;font-variant-numeric:tabular-nums}
.rbs__n small{font-size:11px;font-weight:400;opacity:.72}
.rbs__v{font-size:11px;opacity:.75;font-variant-numeric:tabular-nums}
.rbs__l--own{border-top:1px dashed currentColor;padding-top:8px;margin-top:2px;opacity:.95}
.rbs--none{margin:14px 0;font-size:13px;font-style:italic}
@media(max-width:400px){.rbs__i{padding:5px 8px}.rbs__n{font-size:14px}}
.rbs__i{background:#fff;border:1px solid @LINE@;color:@INK@}
.rbs__s{color:@ACC@}
.rbs__l--own{color:@DIM@}
.rbs--none{color:@MUTE@}

"""


ЗОНА_СТИЛЬ = """
/* Оформление Zona 1.2.0. Числа — измеренные на эталоне; разметка и правила
   написаны свои. Ключевые цели измерения (см. artifacts/evidence/
   templates-zona-animedia-visual-parity-006/reference/zona-w140/):
     контейнер 1400 max, поля 20 (16 на узком), шапка горизонтальная и
     закреплённая высотой 69 на десктопе, кегль тела 13/17.9,
     h2 22.1 нормального начертания, ссылки 15.6 полужирные. */
body{background:@PAGE@;color:@INK@;
font:13px/1.375 ui-sans-serif,system-ui,'Segoe UI',Roboto,Arial,sans-serif;
padding-top:117px}
@media(min-width:768px){body{padding-top:138px}}
@media(min-width:1280px){body{padding-top:69px}}
.zs{min-height:100vh;display:block}
.zmain{min-width:0}
.zwrap{max-width:1400px;margin:0 auto;padding:0 16px}
@media(min-width:1280px){.zwrap{padding:0 20px}}

/* Шапка: горизонтальная, закреплённая. Постоянной левой колонки нет ни на
   одной ширине — это и было главным расхождением с эталоном. */
.zhd{position:fixed;top:0;left:0;right:0;z-index:60;background:@RAIL@;
color:@RAILINK@;box-shadow:0 1px 0 rgba(0,0,0,.25)}
.zhd__in{max-width:1400px;margin:0 auto;padding:14px 16px;display:flex;
align-items:center;gap:12px;flex-wrap:wrap}
@media(min-width:768px){.zhd__in{padding:25px 16px;gap:14px}}
@media(min-width:1280px){.zhd__in{padding:0 20px;height:69px;flex-wrap:nowrap;gap:14px}}
.zhd__logo{font-size:19px;font-weight:700;letter-spacing:-.3px;color:#fff;
white-space:nowrap;flex:0 0 auto}
/* Пункты в одну строку с горизонтальной прокруткой: перенос на узком экране
   поднимал шапку до 185 px против измеренных на эталоне 117. */
.zhd__n{display:flex;gap:2px;flex:1 0 100%;order:3;min-width:0;
overflow-x:auto;scrollbar-width:none;-webkit-overflow-scrolling:touch}
.zhd__n::-webkit-scrollbar{display:none}
@media(min-width:1280px){.zhd__n{flex:1 1 auto;order:0;overflow:visible}}
.zhd__n a{padding:9px 10px;border-radius:6px;font-size:15.6px;font-weight:500;
color:#eef3f8;white-space:nowrap;flex:0 0 auto}
.zhd__n a:hover{background:rgba(255,255,255,.14)}
.zhd__n a[aria-current]{background:@ACCDK@;color:#fff}
.zhd__s{display:flex;flex:1 1 140px;min-width:0;max-width:420px;
border-radius:6px;overflow:hidden;background:#fff}
.zhd__s input{flex:1;min-width:0;border:0;padding:9px 12px;font-size:14px;
color:@PAGE@;font-family:inherit}
.zhd__s button{border:0;background:@ACCDK@;color:#fff;padding:0 16px;
font-weight:600;font-size:14px;cursor:pointer;font-family:inherit}
/* Жанры вынесены из шапки в тело главной: третий ряд поднимал шапку до
   170 px против измеренных на эталоне 137.8. */

/* Прежние узлы каркаса остаются объявленными: на них ссылаются страницы
   каталога, поиска и произведения. Боковая колонка больше не раскладывается. */
.zrail,.zrail__logo,.zrail__sub,.zrail__t,.zrail__n,.zrail__g{display:none}
.ztop{border-bottom:1px solid @LINE@;background:@PAGE@}
.ztop__a{display:flex;align-items:center;gap:16px;padding:12px 0}
.ztop__s{flex:1;display:flex;border:1px solid @LINE@;border-radius:6px;
overflow:hidden;background:@ALT@;max-width:640px}
.ztop__s input{flex:1;border:0;padding:10px 13px;font-size:14px;
background:transparent;color:@INK@;font-family:inherit}
.ztop__s button{border:0;background:@ACCDK@;color:#fff;padding:0 18px;
font-weight:600;font-size:14px;cursor:pointer;font-family:inherit}
.ztop__b{display:flex;gap:16px;padding:0 0 10px;font-size:13px;color:@DIM@;
flex-wrap:wrap;max-width:100%;min-width:0}
.ztop__b a{color:@ACC@;font-weight:600;display:inline-block;padding:5px 2px;
max-width:100%;overflow-wrap:anywhere}
.ztop__b a[aria-current]{color:@INK@;box-shadow:inset 0 -2px 0 @ACC@}

/* Типографика по измерению: h2 22.1 нормального начертания. */
.zh{font-size:26px;line-height:1.22;font-weight:600;margin:22px 0 6px;
letter-spacing:-.3px}
@media(min-width:1280px){.zh{font-size:30px}}
.zh--sm{font-size:22.1px;font-weight:400;margin:26px 0 6px;letter-spacing:0}
.zsub{font-size:13px;color:@DIM@;margin:0 0 18px}
.zsub a{display:inline-block;padding:5px 2px;color:@ACC@;font-weight:600}
.zcr{font-size:12.5px;color:@DIM@;padding:12px 0 0}
.zcr a{color:@ACC@}

/* Пять горизонтальных лент. Управление мышью, клавиатурой и свайпом. */
.zsec{margin:26px 0 30px}
.zsec__h{display:flex;align-items:baseline;justify-content:space-between;
gap:12px;margin:0 0 10px}
.zsec__h h2{font-size:22.1px;font-weight:400;margin:0;letter-spacing:0}
.zsec__h a{font-size:13px;color:@ACC@;font-weight:600;white-space:nowrap}
.zrl{position:relative}
.zrl__vp{overflow-x:auto;overflow-y:hidden;scroll-behavior:smooth;
scroll-snap-type:x mandatory;-webkit-overflow-scrolling:touch;
scrollbar-width:thin;padding:2px 0 10px}
/* align-items:flex-start обязателен: по умолчанию флекс растягивает все
   карточки до высоты самой высокой, и постер с заданной пропорцией
   перерастает её — измерено 0.56 вместо 0.67 в лентах с длинными названиями. */
.zrl__track{display:flex;gap:12px;min-width:min-content;align-items:stretch}
.zrl__track>*{flex:0 0 148px;scroll-snap-align:start;min-width:0;height:auto}
@media(min-width:768px){.zrl__track>*{flex-basis:180px}}
@media(min-width:1280px){.zrl__track>*{flex-basis:216px}}
.zrl__btn{position:absolute;top:28%;transform:translateY(-50%);z-index:5;
width:34px;height:52px;border:0;border-radius:5px;cursor:pointer;
background:rgba(16,21,26,.82);color:#fff;font-size:18px;line-height:1;
display:none;align-items:center;justify-content:center}
@media(min-width:1024px){.zrl:hover .zrl__btn,.zrl__btn:focus-visible{display:flex}}
.zrl__btn--p{left:-6px}
.zrl__btn--n{right:-6px}
.zrl__btn[disabled]{opacity:.32;cursor:default}

/* Сетка каталога и карточка. Пропорция постера 2:3, высота ряда ровная. */
.zg{display:grid;gap:14px;grid-template-columns:repeat(2,minmax(0,1fr));
align-items:stretch}
@media(min-width:640px){.zg{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(min-width:900px){.zg{grid-template-columns:repeat(5,minmax(0,1fr))}}
@media(min-width:1200px){.zg{grid-template-columns:repeat(6,minmax(0,1fr))}}
@media(min-width:1440px){.zg{grid-template-columns:repeat(7,minmax(0,1fr))}}
.zt{display:flex;flex-direction:column;height:100%;min-width:0;background:@SURF@;
border:1px solid @LINE@;border-radius:8px;overflow:hidden;
transition:border-color .16s,transform .16s;color:inherit;text-decoration:none}
.zt:hover{border-color:@ACC@;transform:translateY(-2px)}
.zt__p{display:block;aspect-ratio:2/3;background:@ALT@;position:relative;flex:0 0 auto;
overflow:hidden}
.zt__p img,.zt__img{position:absolute;inset:0;z-index:1;width:100%;height:100%;
object-fit:cover;display:block}
.zt__none{position:absolute;inset:0;display:grid;place-items:center;padding:12px;
text-align:center;color:@MUTE@;font-size:12px;line-height:1.3;aspect-ratio:auto}
.zt__none b{display:block;font-size:24px;font-weight:700;color:@DIM@;margin-bottom:4px}
.zt__b{padding:8px 9px 10px;display:flex;flex-direction:column;gap:4px;flex:1 1 auto;
min-height:108px;box-sizing:border-box}
.zt__t{font-size:13.5px;font-weight:600;line-height:1.28;min-height:calc(1.28em * 2);
max-height:calc(1.28em * 2);display:-webkit-box;-webkit-line-clamp:2;
-webkit-box-orient:vertical;overflow:hidden;word-break:break-word}
.zt__m{display:block;font-size:12px;color:@DIM@;line-height:1.3;min-height:1.3em;
white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.zt__r{display:flex;gap:9px;font-size:12px;color:@DIM@;margin-top:auto;
padding-top:4px;flex-wrap:nowrap;min-height:1.3em;align-items:center}
.zt__r b{color:@WARM@;font-weight:700}
.zt__r i{color:@WARM@;font-style:normal;font-weight:700}
.zt__r em{color:@MUTE@;font-style:italic}

/* Строка списка: постер слева. Это не сетка главной. */
.zl{display:flex;flex-direction:column;gap:10px}
.zr{display:grid;grid-template-columns:64px 1fr;gap:12px;padding:10px;
background:@SURF@;border:1px solid @LINE@;border-radius:8px;align-items:start}
@media(min-width:768px){.zr{grid-template-columns:82px 1fr}}
.zr:hover{border-color:@ACC@}
.zr__p{aspect-ratio:2/3;background:@ALT@;border-radius:5px;overflow:hidden;
position:relative}
.zr__p img,.zr__img{position:absolute;inset:0;width:100%;height:100%;
object-fit:cover;display:block;z-index:1}
.zr__none{position:absolute;inset:0;display:grid;place-items:center;
text-align:center;color:@MUTE@;font-size:11px;padding:6px}
.zr__t{display:block;font-size:15px;font-weight:600;line-height:1.3;margin-bottom:3px}
.zr__m{display:block;font-size:12.5px;color:@DIM@;margin-bottom:5px}
.zr__d{font-size:12.5px;color:@DIM@;line-height:1.45;
display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.zr__r{display:flex;gap:10px;font-size:12px;color:@DIM@;margin-top:6px;flex-wrap:wrap}

/* Фильтры каталога (служебные) и жанровая навигация главной. */
.zstrip{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0 6px;max-width:100%;min-width:0}
.zstrip a{background:@SURF@;border:1px solid @LINE@;border-radius:6px;
padding:7px 12px;font-size:13px;color:@DIM@;font-weight:600;
max-width:100%;overflow-wrap:anywhere}
.zstrip a:hover{border-color:@ACC@;color:@INK@}
.zstrip a[aria-current]{background:@ACCDK@;color:#fff;border-color:@ACCDK@}
.zgenres{margin:8px 0 28px;max-width:100%;min-width:0}
.zgenres__h{font-size:22.1px;font-weight:400;margin:0 0 12px;letter-spacing:0}
.zgenres__nav{display:flex;flex-wrap:wrap;gap:10px;max-width:100%}
.zgenres__nav a{display:inline-flex;align-items:center;justify-content:center;
min-height:42px;padding:10px 16px;border-radius:9px;border:1px solid @LINE@;
background:@SURF@;color:@INK@;font-size:14px;font-weight:600;line-height:1.2;
text-decoration:none;box-sizing:border-box}
.zgenres__nav a:hover{border-color:@ACC@;color:@ACC@;background:#f3f7fc}
.zgenres__nav a:focus-visible{outline:2px solid @ACC@;outline-offset:2px}
.zgenres__nav a[aria-current],.zgenres__nav a.is-active{
background:@ACCDK@;border-color:@ACCDK@;color:#fff}
@media(max-width:639px){
.zgenres__nav{flex-wrap:nowrap;overflow-x:auto;-webkit-overflow-scrolling:touch;
scrollbar-width:thin;padding-bottom:4px}
.zgenres__nav a{flex:0 0 auto}
}
.zpg{display:flex;gap:7px;justify-content:center;margin:26px 0;flex-wrap:wrap}
.zpg a,.zpg span{padding:8px 13px;border-radius:6px;border:1px solid @LINE@;
background:@SURF@;font-size:13.5px;min-width:40px;text-align:center}
.zpg span{background:@ACCDK@;color:#fff;border-color:@ACCDK@}
.zempty,.znf{padding:52px 18px;text-align:center;color:@DIM@}
.znf b{display:block;font-size:44px;font-weight:700;color:@ACC@;margin-bottom:6px}
.znf h1{font-size:24px;margin:0 0 8px;color:@INK@;font-weight:600}
.znf a{display:inline-block;margin-top:14px;background:@ACCDK@;color:#fff;
padding:11px 22px;border-radius:6px;font-weight:600}
.zsea__h{font-size:13px;color:@DIM@;margin:0 0 14px}
.zsea{margin:0 0 20px}

/* Страница произведения: компактная трёхзональная шапка. */
.zban{display:none}
.ztitle{display:grid;grid-template-columns:1fr;gap:20px;margin:16px 0 8px;
align-items:start}
@media(min-width:900px){.ztitle{grid-template-columns:220px minmax(0,1fr);gap:22px}}
@media(min-width:1280px){.ztitle{grid-template-columns:260px minmax(0,1fr) 300px;gap:24px}}
.ztitle__poster{aspect-ratio:2/3;border-radius:8px;overflow:hidden;background:@ALT@;
position:relative;width:100%;max-width:280px;margin:0 auto}
@media(min-width:900px){.ztitle__poster{margin:0;max-width:none}}
.ztitle__poster img,.ztitle__poster .zhead__img{position:absolute;inset:0;z-index:1;
width:100%;height:100%;object-fit:cover;display:block}
.ztitle__main{min-width:0}
.ztitle__main h1{font-size:28px;line-height:1.18;margin:0 0 8px;letter-spacing:-.4px}
@media(min-width:1280px){.ztitle__main h1{font-size:32px}}
.ztitle__o{font-size:14px;color:@DIM@;margin:0 0 10px}
.ztitle__desc{font-size:14.5px;line-height:1.62;color:@INK@;max-width:70ch;margin:0 0 14px;
display:-webkit-box;-webkit-line-clamp:6;-webkit-box-orient:vertical;overflow:hidden}
.ztitle__cta{display:inline-flex;align-items:center;justify-content:center;
min-height:42px;padding:10px 18px;border-radius:8px;background:@ACCDK@;color:#fff;
font-weight:700;font-size:14px;text-decoration:none}
.ztitle__cta:hover{filter:brightness(1.05)}
.ztitle__rail{min-width:0;display:flex;flex-direction:column;gap:16px}
@media(max-width:899px){.ztitle__rail{order:3}}
.ztitle__dl{margin:0;background:@SURF@;border:1px solid @LINE@;border-radius:8px;
padding:12px 14px;display:grid;gap:10px}
.ztitle__dl div{display:grid;grid-template-columns:96px minmax(0,1fr);gap:8px 12px;
align-items:baseline}
.ztitle__dl dt{font-size:11.5px;letter-spacing:.06em;text-transform:uppercase;
color:@DIM@;font-weight:700;margin:0}
.ztitle__dl dd{margin:0;font-size:13.5px;color:@INK@;line-height:1.4;
overflow-wrap:anywhere}
.ztitle__dl a{color:@ACC@;font-weight:600}
.zad{display:none}
.zad[data-ad-enabled="1"]{display:block;width:100%;max-width:300px;min-height:250px;
border:1px dashed @LINE@;border-radius:8px;background:@ALT@;margin:0 auto}
/* legacy hooks kept for older markup paths */
.zhead{display:contents}
.zhead__ps,.zhead__x,.zhead__o{display:contents}
.zbody{font-size:14.5px;line-height:1.62;color:@INK@;max-width:70ch;margin:18px 0 0}
.zaside{display:none}
/* Хаб подборок: карточка коллекции, а не ещё одна сетка тайтлов. */
.zhub{display:grid;gap:12px;margin:14px 0;grid-template-columns:1fr}
@media(min-width:600px){.zhub{grid-template-columns:repeat(2,1fr)}}
@media(min-width:1000px){.zhub{grid-template-columns:repeat(3,1fr)}}
.zhub__c{display:block;padding:12px;border:1px solid @LINE@;border-radius:8px;
background:@SURF@;color:inherit;text-decoration:none}
.zhub__c:hover{border-color:@ACC@}
.zhub__g{display:flex;gap:4px;margin-bottom:9px}
.zhub__p{flex:1 1 0;aspect-ratio:2/3;overflow:hidden;border-radius:5px;background:@ALT@}
.zhub__img{width:100%;height:100%;object-fit:cover;display:block}
.zhub__t{display:block;font-weight:700;font-size:15.5px}
.zhub__m{display:block;font-size:12.5px;color:@ACC@;font-weight:600;margin:2px 0 4px}
.zhub__d{display:block;font-size:13px;color:@DIM@;line-height:1.45}

/* Окно просмотра списка серий ограничено; сам список не обрезается. */
.zeps{display:grid;gap:7px;margin:14px 0;max-height:70vh;overflow-y:auto;
overscroll-behavior:contain}
@media(min-width:768px){.zeps{max-height:520px}}
.zeps a,.zeps span{display:block;padding:9px 12px;border-radius:6px;
border:1px solid @LINE@;background:@SURF@;font-size:13.5px}
.zeps span{opacity:.55}
.zeps a[aria-current]{background:@ACCDK@;color:#fff;border-color:@ACCDK@}
.zepnav{display:flex;gap:10px;flex-wrap:wrap;margin:16px 0}
.zepnav a{background:@SURF@;border:1px solid @LINE@;border-radius:6px;
padding:9px 14px;font-size:13.5px;color:@ACC@;font-weight:600}

/* Плеер: кадр 16:9 только при resolving/ok; честные состояния — компактны. */
.zpl{margin:18px 0}
.zpl__f{aspect-ratio:16/9;background:#0d1217;border:1px solid @LINE@;
border-radius:8px;overflow:hidden;position:relative}
.zpl__f[data-state="awaiting"],
.zpl__f[data-state="unavailable"],
.zpl__f[data-state="nosource"],
.zpl__f[data-state="noaccess"],
.zpl__f[data-state="provider"],
.zpl__f[data-state="error"],
.zpl__f[data-state="slow"]{aspect-ratio:auto;min-height:120px;max-height:180px}
.zpl__f video-player{display:block;width:100%;height:100%}
.zpl__h{display:flex;align-items:baseline;justify-content:space-between;gap:12px;
font-size:22.1px;font-weight:400;margin:22px 0 10px}
.zpl__h span{font-size:13px;color:@DIM@;font-weight:600}
.zpl__s{position:absolute;inset:0;display:grid;place-items:center;padding:22px;
text-align:center;color:@DIM@;font-size:13.5px;line-height:1.5}
.zpl__f [data-player-state]{padding:18px 16px;text-align:center;color:@DIM@;
font-size:13.5px;line-height:1.5;max-width:520px;margin:0 auto}
.zpl__f [data-player-state] b{display:block;color:@INK@;margin:0 0 6px;font-size:15px}

.zft{border-top:1px solid @LINE@;margin:36px 0 0;padding:20px 0 30px;
font-size:12.5px;color:@DIM@;display:block}
.zft__cols{display:grid;gap:18px;grid-template-columns:1fr;
margin:0 0 16px}
@media(min-width:768px){.zft__cols{grid-template-columns:repeat(3,minmax(0,1fr))}}
.zft__col{display:flex;flex-direction:column;gap:6px;min-width:0}
.zft__col b{color:@INK@;font-size:13px;margin:0 0 4px}
.zft__col a{color:@ACC@;font-weight:500}
.zft__bar{display:flex;justify-content:flex-end;align-items:center}
.zvb{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11px;
border:0;padding:0;background:transparent;color:@MUTE@}
.zhd__menu{display:inline-flex;align-items:center;justify-content:center;
width:40px;height:40px;border:1px solid rgba(255,255,255,.28);border-radius:6px;
background:transparent;color:#fff;font-size:20px;cursor:pointer;flex:0 0 auto}
@media(min-width:768px){.zhd__menu{display:none}}
@media(max-width:767px){
.zhd__n{display:none;flex:1 0 100%;order:4;flex-wrap:wrap;overflow:visible}
.zhd__n.is-open{display:flex}
body.nav-lock{overflow:hidden}
}
.zfilt__y{display:inline-flex;flex-wrap:wrap;gap:6px;max-width:100%}
.zhub--home{display:grid;gap:10px;grid-template-columns:repeat(2,minmax(0,1fr))}
@media(min-width:768px){.zhub--home{grid-template-columns:repeat(4,minmax(0,1fr))}}
.zsec--seo{margin:28px 0 8px}
.ztop__b{max-width:100%;overflow-wrap:anywhere}

img[hidden]{display:none}

/* Оценки по источникам. Разметка общая, вид свой у каждого семейства. */
.rbs{margin:14px 0;display:flex;flex-direction:column;gap:8px}
.rbs__l{display:flex;flex-wrap:wrap;gap:8px;margin:0;padding:0;list-style:none}
.rbs__i{display:flex;align-items:baseline;gap:6px;padding:6px 11px;border-radius:6px;
white-space:nowrap}
.rbs__s{font-size:11.5px;font-weight:700;letter-spacing:.04em;text-transform:uppercase}
.rbs__n{font-size:15px;font-weight:700;font-variant-numeric:tabular-nums}
.rbs__n small{font-size:11px;font-weight:400;opacity:.72}
.rbs__v{font-size:11px;opacity:.75;font-variant-numeric:tabular-nums}
.rbs__l--own{border-top:1px dashed currentColor;padding-top:8px;margin-top:2px;opacity:.95}
.rbs--none{margin:14px 0;font-size:13px;font-style:italic}
@media(max-width:400px){.rbs__i{padding:5px 8px}.rbs__n{font-size:14px}}
.rbs__i{background:@SURF@;border:1px solid @LINE@;color:@INK@}
.rbs__s{color:@ACC@}
.rbs__n{color:@WARM@}
.rbs__l--own{color:@DIM@}
.rbs--none{color:@MUTE@}

"""


АНИМЕДИА_СТИЛЬ = """
/* Animedia 1.2.4 — blockwise: shell/header/theme (BLOCK_01) + shelves. */
:root{
  --a-content-max:1760px;
  --page-gutters:96px;
  --a-gutter-desktop:48px;
  --a-gutter-tablet:22px;
  --a-gutter-mobile:14px;
  --a-section-gap:40px;
  --a-grid-gap:16px;
  --a-space-1:8px;--a-space-2:12px;--a-space-3:16px;--a-space-4:24px;
  --a-space-5:32px;--a-space-6:40px;--a-space-7:48px;--a-space-8:64px;
  --a-radius-shell:clamp(18px,1.4vw,24px);--a-radius-card:12px;--a-radius-chip:999px;
  --a-shadow:0 10px 28px rgba(15,23,42,.08);--a-shadow-soft:0 4px 14px rgba(15,23,42,.06);
  --a-page:@PAGE@;--a-ink:@INK@;--a-dim:@DIM@;--a-alt:@ALT@;--a-line:@LINE@;
  --a-acc:@ACC@;--a-mute:@MUTE@;--a-surf:@SURF@;--a-rail:@RAIL@;--a-warm:@WARM@;
}
@media(max-width:1023px){:root{--page-gutters:44px}}
@media(max-width:767px){:root{--page-gutters:28px}}
@media(max-width:390px){:root{--page-gutters:24px}}
html{color-scheme:light}
html[data-theme=dark]{color-scheme:dark;
  --a-page:#12141a;--a-ink:#eef0f4;--a-dim:#a7adb8;--a-alt:#1c202b;--a-line:#2e3545;
  --a-mute:#8b92a0;--a-surf:#222633;--a-rail:#161922;--a-warm:#e0a24a;
  --a-shadow:0 10px 28px rgba(0,0,0,.45);--a-shadow-soft:0 4px 14px rgba(0,0,0,.35);
}
/* Theme must never recolor media */
.zt__p img,.zt__img,.ahero img,.ztitle__poster img,.zpl__f iframe,.zpl__f video,.zhub__img{
  filter:none !important;-webkit-filter:none !important;
}
*{box-sizing:border-box}
html,body{max-width:100%;overflow-x:hidden}
body{background:var(--a-page);color:var(--a-ink);
font:16px/1.45 ui-sans-serif,system-ui,'Segoe UI',Roboto,Arial,sans-serif}
@media(prefers-reduced-motion:reduce){
  *,*::before,*::after{animation-duration:.01ms !important;animation-iteration-count:1 !important;
  transition-duration:.01ms !important;scroll-behavior:auto !important}
}
.zs{min-height:100vh;display:block}
.zmain{min-width:0}
.zwrap,.zhd__in,.zft__inner{
  width:min(var(--a-content-max),calc(100% - var(--page-gutters)));
  margin-inline:auto;padding-inline:0;box-sizing:border-box}
.zwrap{padding-block:0}
.zhd{position:relative;background:var(--a-rail);border-bottom:1px solid var(--a-line);z-index:30}
.zhd__in{display:flex;align-items:center;gap:12px;flex-wrap:nowrap;height:68px;min-height:64px;
max-height:72px;padding-block:0}
@media(max-width:1023px){
  .zhd__in{height:60px;min-height:56px;max-height:64px;flex-wrap:nowrap;gap:8px;padding-block:0}
}
@media(max-width:767px){
  .zhd__in{height:56px;min-height:56px;max-height:64px;gap:8px}
}
.zhd__logo{font-size:22px;font-weight:800;letter-spacing:-.4px;color:var(--a-ink);flex:0 0 auto;
line-height:1;min-height:44px;min-width:120px;max-width:155px;width:max-content;
display:inline-flex;align-items:center}
.zhd__logo b{color:var(--a-acc)}
.zhd__n{display:none;align-items:center;gap:2px;flex:0 1 auto;min-width:0}
@media(min-width:1100px){.zhd__n{display:flex}}
.zhd__n a{padding:8px 10px;border-radius:8px;font-size:13px;font-weight:700;color:var(--a-ink);
text-decoration:none;min-height:44px;display:inline-flex;align-items:center;white-space:nowrap}
.zhd__n a:hover{color:var(--a-acc);background:var(--a-alt)}
.zhd__n a[aria-current]{color:var(--a-acc);box-shadow:inset 0 -2px 0 var(--a-acc)}
.zhd__tax{display:none;align-items:center;gap:2px;flex:1 1 auto;min-width:0}
@media(min-width:1100px){.zhd__tax{display:flex}}
.zhd__dd{position:relative}
.zhd__dd-btn{appearance:none;border:0;background:transparent;color:var(--a-ink);font:inherit;
font-size:13px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;padding:8px 10px;
min-height:44px;cursor:pointer;border-radius:8px}
.zhd__dd-btn:hover,.zhd__dd-btn[aria-expanded=true]{color:var(--a-acc);background:var(--a-alt)}
.zhd__dd-btn:focus-visible{outline:2px solid var(--a-acc);outline-offset:2px}
.zhd__dd-panel{position:absolute;top:calc(100% + 6px);left:0;width:min(920px,calc(100vw - 48px));
min-width:min(720px,calc(100vw - 48px));max-width:960px;max-height:70vh;overflow:auto;
display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;padding:14px;background:var(--a-page);
border:1px solid var(--a-line);border-radius:12px;box-shadow:var(--a-shadow);z-index:50}
@media(min-width:1280px){.zhd__dd-panel{grid-template-columns:repeat(5,minmax(0,1fr))}}
.zhd__dd-panel[hidden]{display:none !important}
.zhd__dd-panel a{display:inline-flex;align-items:center;justify-content:space-between;gap:8px;
padding:8px 10px;border-radius:8px;border:1px solid var(--a-line);color:var(--a-ink);font-size:13px;
text-decoration:none;min-height:44px}
.zhd__dd-panel a:hover{border-color:var(--a-acc);color:var(--a-acc)}
.zhd__dd-panel a .zhd__cnt{color:var(--a-mute);font-size:12px;font-weight:600}
.zhd__actions{display:inline-flex;align-items:center;gap:8px;flex:0 0 auto;margin-left:auto}
.zhd__menu{display:inline-flex;align-items:center;justify-content:center;width:44px;height:44px;
min-width:44px;min-height:44px;flex:0 0 44px;border:1px solid var(--a-line);border-radius:8px;
background:var(--a-page);color:var(--a-ink);font-size:20px;cursor:pointer;margin-left:0}
@media(min-width:1100px){.zhd__menu{display:none}}
.zhd__theme{display:inline-flex;align-items:center;justify-content:center;width:44px;height:44px;
min-width:44px;min-height:44px;flex:0 0 44px;border:1px solid var(--a-line);border-radius:8px;
background:var(--a-page);color:var(--a-ink);font-size:16px;cursor:pointer}
.zhd__theme:focus-visible,.zhd__menu:focus-visible,.zhd__s button:focus-visible,.zhd__drawer a:focus-visible,
.zhd__drawer-x:focus-visible,.zhd__n a:focus-visible{outline:2px solid var(--a-acc);outline-offset:2px}
.zhd__s{display:flex;flex:0 1 320px;min-width:280px;max-width:360px;height:48px;border:1px solid var(--a-line);
border-radius:999px;overflow:hidden;background:var(--a-page);align-items:stretch}
@media(max-width:1099px){
  .zhd__s{flex:1 1 calc(100% - 108px);min-width:120px;max-width:none;order:0;border-radius:10px;height:48px}
  .zhd__actions{order:0}
}
.zhd__s input{flex:1;min-width:0;border:0;padding:0 12px;font-size:14px;background:transparent;color:var(--a-ink);height:100%;min-height:48px}
.zhd__s button{border:0;background:var(--a-acc);color:#fff;padding:0 14px;font-weight:700;cursor:pointer;
min-width:48px;min-height:48px;height:100%;flex:0 0 auto}
/* B12 on-page search block */
.asearch{margin:0 0 18px;padding:14px 16px;border:1px solid var(--a-line);border-radius:12px;
background:var(--a-alt);min-height:130px;max-height:160px;box-sizing:border-box;
display:flex;flex-direction:column;justify-content:center;gap:10px}
.asearch__form{display:flex;gap:8px;align-items:stretch;flex-wrap:wrap}
.asearch__form input{flex:1 1 220px;min-height:48px;max-height:52px;height:50px;padding:0 14px;
border:1px solid var(--a-line);border-radius:10px;background:var(--a-page);color:var(--a-ink);font-size:15px}
.asearch__form button{min-height:48px;max-height:52px;padding:0 18px;border:0;border-radius:10px;
background:var(--a-acc);color:#fff;font-weight:700;cursor:pointer}
.asearch__clear{display:inline-flex;align-items:center;min-height:48px;padding:0 12px;
font-size:13px;font-weight:700;color:var(--a-dim);text-decoration:underline}
.asearch__hint{margin:0;font-size:13px;color:var(--a-dim);line-height:1.35;
overflow:hidden;text-overflow:clip}
.asearch__clear:focus-visible,.asearch__form input:focus-visible,
.asearch__form button:focus-visible{outline:2px solid var(--a-acc);outline-offset:2px}
.zhd__backdrop{position:fixed;inset:0;background:rgba(15,23,42,.45);z-index:60}
.zhd__backdrop[hidden]{display:none !important;pointer-events:none !important}
.zhd__drawer{position:fixed;top:0;left:0;bottom:0;width:min(360px,calc(100vw - 24px));z-index:70;background:var(--a-page);
border-right:1px solid var(--a-line);box-shadow:var(--a-shadow);padding:12px 14px 24px;overflow:auto;
flex-direction:column;gap:12px}
.zhd__drawer:not([hidden]){display:flex}
.zhd__drawer[hidden]{display:none !important;pointer-events:none !important}
.zhd__drawer-h{display:flex;align-items:center;justify-content:space-between;font-weight:700}
.zhd__drawer-x{width:44px;height:44px;border:1px solid var(--a-line);border-radius:8px;background:var(--a-rail);
font-size:22px;cursor:pointer;color:var(--a-ink)}
.zhd__drawer-nav{display:flex;flex-direction:column;gap:4px}
.zhd__drawer-nav a{padding:12px 10px;border-radius:8px;color:var(--a-ink);min-height:44px;
display:flex;align-items:center;text-decoration:none}
.zhd__drawer-nav a[aria-current]{color:var(--a-acc);font-weight:700;background:var(--a-alt)}
.zhd__drawer .zhd__tax{display:flex;flex-direction:column;align-items:stretch;gap:8px}
.zhd__drawer .zhd__n{display:none}
.zhd__drawer .zhd__dd-panel{position:static;width:auto;min-width:0;max-width:none;box-shadow:none;margin-top:6px;
grid-template-columns:1fr}
body.zhd-lock{overflow:hidden}
/* B01.2 breadcrumb */
.zcr{display:flex;flex-wrap:wrap;align-items:center;gap:6px;min-height:32px;max-height:40px;
padding:6px 0;margin:0 0 8px;font-size:13px;color:var(--a-dim);line-height:1.3;overflow:hidden}
@media(max-width:767px){.zcr{max-height:none;min-height:0;height:auto;max-height:2.8em}}
.zcr a{color:var(--a-acc);font-weight:600;text-decoration:none;padding:2px 0}
.zcr a:hover{text-decoration:underline}
.zcr [aria-current=page]{color:var(--a-ink);font-weight:600}
.ast{display:none}
.zrail,.zrail__logo,.zrail__sub,.zrail__t,.zrail__n,.zrail__g,.ztop{display:none}
.zh{font-size:clamp(22px,2vw,28px);line-height:1.25;font-weight:700;margin:16px 0 8px}
.zh--sm{font-size:clamp(20px,1.8vw,26px);font-weight:700;margin:24px 0 10px}
.zsub{font-size:15px;color:var(--a-dim);margin:0 0 16px;max-width:72ch;line-height:1.45;
display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.zsec{margin:0 0 var(--a-section-gap);max-height:none;overflow:visible}
.zsec__h{display:flex;align-items:baseline;justify-content:space-between;gap:12px;margin:0 0 12px}
.zsec__h h2{font-size:clamp(20px,1.6vw,26px);font-weight:700;margin:0}
.zsec__h a{font-size:14px;color:var(--a-acc);font-weight:700;white-space:nowrap}
.ahero{margin:8px 0 14px;padding:12px;border-radius:var(--a-radius-shell);
background:var(--a-acc);color:#fff;overflow:hidden;box-sizing:border-box;
min-height:0;height:auto;max-height:none}
.ahero[hidden],.ahero--gap{display:none !important;height:0 !important;min-height:0 !important;
max-height:0 !important;margin:0 !important;padding:0 !important;border:0 !important;overflow:hidden}
.zh--home{font-size:clamp(18px,1.5vw,22px);margin:8px 0 4px;font-weight:700}
.zsub--home{margin:0 0 16px;font-size:14px;-webkit-line-clamp:2}
.ahero__inner{padding-block:12px}
.ahero .zrl__vp{padding-bottom:2px;scrollbar-width:none}
.ahero .zrl__vp::-webkit-scrollbar{display:none}
.ahero .zrl__track{gap:16px;align-items:flex-start}
/* B02 exact poster grid (desktop/tablet); mobile = rail 112px */
.ahero .zrl__track>*{flex:0 0 calc((100% - 144px)/10);width:calc((100% - 144px)/10);
min-width:0;max-width:none;scroll-snap-align:start}
.ahero .zt{width:100%;max-width:none;flex:0 0 auto}
@media(max-width:1599px){
  .ahero .zrl__track{gap:16px}
  .ahero .zrl__track>*{flex:0 0 calc((100% - 112px)/8);width:calc((100% - 112px)/8)}
}
@media(max-width:1279px){
  .ahero .zrl__track>*{flex:0 0 calc((100% - 80px)/6);width:calc((100% - 80px)/6)}
}
@media(max-width:1023px){
  .ahero .zrl__track>*{flex:0 0 calc((100% - 48px)/4);width:calc((100% - 48px)/4)}
}
@media(max-width:767px){
  .ahero{margin-bottom:16px;padding:10px}
  .ahero .zrl__track{gap:12px}
  .ahero .zrl__track>*{flex:0 0 112px;width:112px;min-width:112px;max-width:112px}
  .ahero .zt{width:112px;max-width:112px}
}
.ahero .zt{background:transparent;border:0;box-shadow:none;color:#fff;height:auto;max-height:none}
.ahero .zt:hover{opacity:.92;box-shadow:none;border:0;transform:none}
.ahero .zt__p{border-radius:10px;width:100%;aspect-ratio:2/3;height:auto;background:rgba(0,0,0,.18);flex:0 0 auto}
@media(max-width:767px){.ahero .zt__p{width:112px;height:168px;aspect-ratio:auto}}
.ahero .zt__b{padding:6px 2px 0;min-height:44px;max-height:52px}
.ahero .zt__t{color:#fff;font-size:13px;-webkit-line-clamp:2;min-height:0;line-height:1.25}
.ahero .zt__m,.ahero .zt__r{display:none}
.ahero .zrl__btn{background:rgba(255,255,255,.96);color:var(--a-acc);border:0;border-radius:10px}
.ahero__cap{display:none}
.atg{display:flex;align-items:center;min-height:46px;max-height:56px;margin:0 0 12px;padding:0 14px;
border-radius:10px;background:var(--a-alt);border:1px solid var(--a-line)}
.atg a{font-weight:700;color:var(--a-acc);text-decoration:none;min-height:44px;display:inline-flex;align-items:center}
.atg:empty{display:none;height:0;margin:0;padding:0;border:0}
.zad,.zad-home,.zad-mid,.zad-title{display:none;height:0;min-height:0;max-height:0;margin:0;padding:0;border:0;overflow:hidden}
.zad[data-ad-enabled="1"],.zad-home[data-ad-enabled="1"],.zad-mid[data-ad-enabled="1"],
.zad-title[data-ad-enabled="1"]{display:block;height:auto;max-height:120px;max-width:100%;margin:12px 0;
overflow:hidden;border-radius:8px}
.zrl{position:relative}
.zrl__vp{overflow-x:auto;overflow-y:hidden;scroll-behavior:smooth;scroll-snap-type:x mandatory;
-webkit-overflow-scrolling:touch;padding:2px 0 6px;scrollbar-width:none}
.zrl__vp::-webkit-scrollbar{display:none}
.zrl__track{display:flex;gap:12px;min-width:min-content;align-items:flex-start}
.zrl__btn{position:absolute;top:36%;transform:translateY(-50%);z-index:5;width:36px;height:48px;
border:0;border-radius:10px;cursor:pointer;background:rgba(255,255,255,.96);color:var(--a-acc);
font-size:18px;display:none;align-items:center;justify-content:center;box-shadow:var(--a-shadow-soft)}
@media(min-width:1024px){.zrl:hover .zrl__btn,.zrl__btn:focus-visible{display:flex}}
.zrl__btn--p{left:2px}.zrl__btn--n{right:2px}
.zrl__btn:disabled{opacity:.35;cursor:default}
.zg{display:grid;gap:var(--a-grid-gap);grid-template-columns:repeat(2,minmax(0,1fr));align-items:start;
justify-items:stretch}
.zg .zt{align-self:start;width:100%;max-width:100%;height:auto}
/* CARD_VARIANT_REGISTRY: last incomplete row must not stretch cards */
.zrl__track{align-items:flex-start}
@media(min-width:640px){.zg{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(min-width:768px){.zg{grid-template-columns:repeat(4,minmax(0,1fr))}}
@media(min-width:1024px){.zg{grid-template-columns:repeat(5,minmax(0,1fr));gap:14px}}
@media(min-width:1200px){.zg{grid-template-columns:repeat(7,minmax(0,1fr));gap:14px}}
@media(min-width:1800px){.zg{grid-template-columns:repeat(10,minmax(0,1fr));gap:14px}}
@media(min-width:768px) and (max-width:1199px){
  .zcat .zg,.zwrap--catalog .zg{grid-template-columns:repeat(4,minmax(0,1fr))}
}
/* B11 catalog grid: 2 / 4 / 6 — never inherit home 7/10 density */
.zwrap--catalog .zg,.zcat .zg{grid-template-columns:repeat(2,minmax(0,1fr))}
@media(min-width:768px){.zwrap--catalog .zg,.zcat .zg{grid-template-columns:repeat(4,minmax(0,1fr))}}
@media(min-width:1200px){.zwrap--catalog .zg,.zcat .zg{grid-template-columns:repeat(6,minmax(0,1fr));gap:14px}}
@media(min-width:1800px){.zwrap--catalog .zg,.zcat .zg{grid-template-columns:repeat(6,minmax(0,1fr));gap:14px}}
.afilt--closed{max-height:112px}
.afilt--closed:not(.is-open):not(:has(details[open])){overflow:hidden}
.afilt--closed.is-open,.afilt--closed:has(details[open]){overflow:visible;max-height:none}
.zt{display:flex;flex-direction:column;background:var(--a-page);border:0;border-radius:var(--a-radius-card);
overflow:hidden;min-width:0;height:auto;max-height:320px;box-shadow:var(--a-shadow-soft);
transition:transform .14s,box-shadow .14s}
.zt:hover{transform:translateY(-2px);box-shadow:var(--a-shadow)}
.zt:focus-visible{outline:2px solid var(--a-acc);outline-offset:2px}
.zt__p{display:block;aspect-ratio:2/3;background:var(--a-surf);position:relative;flex:0 0 auto;width:100%}
.zt__p img,.zt__img{position:absolute;inset:0;z-index:1;width:100%;height:100%;object-fit:cover;display:block;
max-width:none;max-height:none}
.zt__none{position:absolute;inset:0;display:grid;place-items:center;padding:10px;text-align:center;color:var(--a-mute);font-size:12px}
.zt__none b{display:block;font-size:28px;font-weight:800;color:var(--a-dim);margin-bottom:4px}
.zt__b{padding:6px 8px 8px;display:flex;flex-direction:column;gap:2px;flex:0 0 auto;min-height:52px}
.zt__t{font-size:12.5px;font-weight:700;line-height:1.25;
display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;min-height:0}
.zt__m{display:block;font-size:11px;color:var(--a-dim);line-height:1.25;
display:-webkit-box;-webkit-line-clamp:1;-webkit-box-orient:vertical;overflow:hidden;min-height:0}
.zt__r{display:flex;gap:8px;font-size:12px;color:var(--a-dim);margin-top:4px;padding-top:0;
flex-wrap:nowrap;min-height:1.25em;align-items:center}
.zt__r b,.zt__r i{color:var(--a-acc);font-weight:700;font-style:normal}
.zt__r em{color:var(--a-mute);font-style:italic;visibility:hidden}
.zsec--rel{margin-bottom:28px}
.zsec--rel[hidden],.zsec--rel-gap{display:none !important;height:0 !important;min-height:0 !important;
margin:0 !important;padding:0 !important;border:0 !important;overflow:hidden !important}
.zsec--rel .zg,.zsec--rel .zg--recommendation{gap:var(--a-grid-gap);
grid-template-columns:repeat(2,minmax(0,1fr))}
@media(min-width:768px){.zsec--rel .zg,.zsec--rel .zg--recommendation{grid-template-columns:repeat(4,minmax(0,1fr))}}
@media(min-width:1200px){.zsec--rel .zg,.zsec--rel .zg--recommendation{grid-template-columns:repeat(6,minmax(0,1fr))}}
.ahome-eps{max-width:min(1760px,100%);margin-inline:auto}
.ahome-eps--empty{margin:0 0 16px;max-height:96px;overflow:hidden}
.ahome-eps--empty .zsec__h{margin:0 0 6px}
.ahome-eps--empty .zsec__h h2{font-size:18px;line-height:1.2;margin:0}
/* B05 catalog-added poster grid: 8/6/5/4/2 — never episode-number chrome */
.zsec--b05[hidden],.zsec--b05-gap{display:none !important;height:0 !important;min-height:0 !important;
margin:0 !important;padding:0 !important;border:0 !important;overflow:hidden !important}
.zsec--b05 .zg--catalog-added{gap:var(--a-grid-gap);
grid-template-columns:repeat(2,minmax(0,1fr))}
@media(min-width:768px){.zsec--b05 .zg--catalog-added{grid-template-columns:repeat(4,minmax(0,1fr))}}
@media(min-width:1024px){.zsec--b05 .zg--catalog-added{grid-template-columns:repeat(5,minmax(0,1fr))}}
@media(min-width:1280px){.zsec--b05 .zg--catalog-added{grid-template-columns:repeat(6,minmax(0,1fr))}}
@media(min-width:1600px){.zsec--b05 .zg--catalog-added{grid-template-columns:repeat(8,minmax(0,1fr))}}
.zt--catalog-added .zt__r{display:none}
.zt--catalog-added .zt__added,.zt--catalog-added .zt__avail{display:block;font-size:11px;
color:var(--a-dim);line-height:1.25;margin-top:2px}
.anew-empty{max-width:min(720px,100%);margin:12px 0 24px;padding:12px 14px;
border-radius:8px;background:var(--a-alt);border:1px solid var(--a-line);
color:var(--a-dim);font-size:14px;line-height:1.4;max-height:120px;overflow:hidden}
.anew-page .zg--catalog-added{gap:var(--a-grid-gap);
grid-template-columns:repeat(2,minmax(0,1fr))}
@media(min-width:768px){.anew-page .zg--catalog-added{grid-template-columns:repeat(4,minmax(0,1fr))}}
@media(min-width:1024px){.anew-page .zg--catalog-added{grid-template-columns:repeat(5,minmax(0,1fr))}}
@media(min-width:1280px){.anew-page .zg--catalog-added{grid-template-columns:repeat(6,minmax(0,1fr))}}
@media(min-width:1600px){.anew-page .zg--catalog-added{grid-template-columns:repeat(8,minmax(0,1fr))}}
/* B06 compact home filters + top100 gap + catalog shelf cap */
.ahome-filt{margin:0 0 14px;max-height:56px;overflow:hidden}
.ahome-filt .zstrip{margin:0;max-height:56px;overflow:hidden}
@media(max-width:767px){.ahome-filt{max-height:48px}}
.zsec--top100[hidden],.zsec--top100-gap{display:none !important;height:0 !important;min-height:0 !important;
margin:0 !important;padding:0 !important;border:0 !important;overflow:hidden !important}
.zsec--home-cols .zhub--home{display:grid;gap:12px;grid-template-columns:repeat(2,minmax(0,1fr))}
@media(min-width:900px){.zsec--home-cols .zhub--home{grid-template-columns:repeat(4,minmax(0,1fr))}}
.zseo{margin:28px 0 8px;max-width:1000px}
.zseo h2{font-size:18px;margin:0 0 8px}
.zseo p{font-size:14px;line-height:1.5;color:var(--a-dim);margin:0}
.ahome-editorial,.ahome-comments{display:none;height:0;margin:0;padding:0;overflow:hidden}.ahome-eps__empty{margin:0;padding:10px 12px;border-radius:8px;background:var(--a-alt);
border:1px solid var(--a-line);color:var(--a-dim);font-size:13px;line-height:1.35;
max-height:56px;overflow:hidden}
.ahome-eps .aeps,.zsec--eps.ahome-eps .zl{display:grid;gap:14px;grid-template-columns:1fr}
@media(min-width:900px){
  .ahome-eps .aeps,.zsec--eps.ahome-eps .zl{
    grid-template-columns:1fr 1fr;column-gap:clamp(24px,2vw,32px);row-gap:14px}
  .ahome-eps .aeps__row{height:76px;gap:10px;padding:0 12px 0 0;border-radius:10px}
  .ahome-eps .aeps__thumb{width:60px;border-radius:8px 0 0 8px}
  .ahome-eps .aeps__body{padding:8px 0}
  .ahome-eps .aeps__title{font-size:15px;font-weight:600;line-height:1.25}
  .ahome-eps .aeps__meta{font-size:12px}
  .ahome-eps .aeps__num{font-size:28px}
  .ahome-eps .aeps__lab{font-size:11px}
  .ahome-eps .aeps__ep{min-width:44px;padding-right:2px}
}
.ahome-eps .aeps__row{display:grid;grid-template-columns:auto minmax(0,1fr) auto;
align-items:center;gap:10px;height:76px;padding:0 12px 0 0;
background:var(--a-alt);border:0;border-radius:10px;text-decoration:none;color:inherit;
box-shadow:none;max-height:none;min-height:0;width:100%;box-sizing:border-box}
.ahome-eps .aeps__row:hover{background:var(--a-page);box-shadow:var(--a-shadow-soft);filter:none}
.ahome-eps .aeps__row:focus-visible{outline:2px solid var(--a-acc);outline-offset:2px}
.ahome-eps .aeps__thumb{width:60px;height:100%;max-width:none;aspect-ratio:auto;
border-radius:8px 0 0 8px;overflow:hidden;position:relative;background:var(--a-surf)}
.ahome-eps .aeps__thumb img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;max-width:none}
.ahome-eps .aeps__body{min-width:0;display:flex;flex-direction:column;gap:2px;padding:8px 0}
.ahome-eps .aeps__title{font-size:15px;font-weight:600;line-height:1.25;
display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.ahome-eps .aeps__meta{font-size:12px;color:var(--a-dim)}
.ahome-eps .aeps__ep{display:flex;flex-direction:column;align-items:flex-end;
justify-content:center;padding-right:2px;min-width:44px}
.ahome-eps .aeps__num{font-size:28px;font-weight:800;color:var(--a-acc);line-height:1;
font-variant-numeric:tabular-nums}
.ahome-eps .aeps__lab{font-size:11px;color:var(--a-dim)}
.ahome-eps .zpg{margin-top:12px;margin-bottom:4px}
.ahome-eps .zpg a,.ahome-eps .zpg span{min-width:40px;min-height:40px}
@media(max-width:899px){
  .ahome-eps .aeps{gap:12px}
  .ahome-eps .aeps__row{height:72px;gap:8px;
    grid-template-columns:56px minmax(0,1fr) 44px;padding:0 8px 0 0}
  .ahome-eps .aeps__thumb{width:56px;border-radius:8px 0 0 8px}
  .ahome-eps .aeps__title{font-size:14px}
  .ahome-eps .aeps__meta{font-size:11px}
  .ahome-eps .aeps__num{font-size:24px}
  .ahome-eps .aeps__lab{font-size:10px}
  .ahome-eps .aeps__body{padding:6px 0}
}
@media(max-width:389px){.ahome-eps .aeps__row{height:70px}}
.aeps:not(.ahome-eps .aeps){display:grid;gap:12px;grid-template-columns:1fr}
.zfilt,.zgenres__nav,.zstrip{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 14px;align-items:center}
.zfilt a,.zgenres__nav a,.zstrip a,.zfilt__y a{display:inline-flex;align-items:center;
min-height:40px;padding:0 12px;border-radius:var(--a-radius-chip);border:1px solid var(--a-line);
background:var(--a-page);font-size:13px;font-weight:600;color:var(--a-ink);white-space:nowrap}
.zfilt a:hover,.zgenres__nav a:hover,.zstrip a:hover{border-color:var(--a-acc);color:var(--a-acc)}
.zfilt a[aria-current],.zgenres__nav a[aria-current],.zgenres__nav a[aria-current=true],
.zstrip a[aria-current],.zfilt__y a[aria-current]{background:var(--a-acc);color:#fff;border-color:var(--a-acc)}
.zfilt__y{display:inline-flex;flex-wrap:wrap;gap:8px}
.afilt{margin:0 0 16px}
.afilt__open{display:none;min-height:44px;padding:0 14px;border-radius:10px;border:1px solid var(--a-line);
background:var(--a-page);font-weight:700;font-size:14px;color:var(--a-ink);cursor:pointer}
.afilt__panel{display:block}
.afilt__chips{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 10px;align-items:center}
.afilt__chip{display:inline-flex;align-items:center;gap:6px;min-height:36px;padding:0 12px;
border-radius:999px;border:1px solid var(--a-acc);background:var(--a-alt);color:var(--a-acc);font-size:13px;font-weight:700}
.afilt__reset{min-height:36px;display:inline-flex;align-items:center;padding:0 10px;font-size:13px;font-weight:700;color:var(--a-dim)}
.afilt__rows{display:flex;flex-wrap:wrap;gap:8px;align-items:flex-start}
.afilt__dd{position:relative;min-width:0}
.afilt__dd>summary{list-style:none;cursor:pointer;min-height:40px;padding:0 12px;border-radius:var(--a-radius-chip);
border:1px solid var(--a-line);background:var(--a-page);font-size:13px;font-weight:700;color:var(--a-ink);
display:inline-flex;align-items:center;gap:6px}
.afilt__dd>summary::-webkit-details-marker{display:none}
.afilt__dd[open]>summary{border-color:var(--a-acc);color:var(--a-acc)}
.afilt__opts{position:absolute;z-index:40;top:calc(100% + 4px);left:0;min-width:220px;max-height:280px;overflow:auto;
padding:8px;border-radius:12px;border:1px solid var(--a-line);background:var(--a-page);box-shadow:var(--a-shadow-soft);
display:flex;flex-direction:column;gap:2px}
.afilt__opts a{display:flex;justify-content:space-between;gap:12px;min-height:40px;padding:8px 10px;border-radius:8px;
color:var(--a-ink);font-size:13px;text-decoration:none}
.afilt__opts a:hover,.afilt__opts a[aria-current]{background:var(--a-alt);color:var(--a-acc)}
.afilt__opts small{color:var(--a-dim);font-variant-numeric:tabular-nums}
@media(max-width:767px){
  .afilt__open{display:inline-flex;align-items:center;margin-bottom:8px}
  .afilt__panel{display:none;padding:12px;border:1px solid var(--a-line);border-radius:12px;background:var(--a-page)}
  .afilt.is-open .afilt__panel{display:block}
  .afilt__opts{position:static;max-height:none;box-shadow:none;border:0;padding:6px 0 0}
  .afilt__dd{width:100%}
  .afilt__dd>summary{width:100%;justify-content:space-between}
}
.zpg{display:flex;gap:8px;justify-content:center;margin:24px 0;flex-wrap:wrap}
.zpg a,.zpg span{min-width:44px;min-height:44px;display:inline-flex;align-items:center;
justify-content:center;border-radius:10px;border:1px solid var(--a-line);background:var(--a-page);font-size:14px}
.zpg span{background:var(--a-acc);color:#fff;border-color:var(--a-acc)}
.zempty,.znf{padding:40px 16px;text-align:center;color:var(--a-dim)}
.znf b,.zempty b{display:block;font-size:22px;font-weight:800;color:var(--a-ink);margin-bottom:8px}
.asch{display:none}
.asch-empty{padding:12px 14px;border-radius:var(--a-radius-card);background:var(--a-alt);color:var(--a-dim);
line-height:1.4;font-size:14px}
.asch-empty p{margin:6px 0 0}
.asch-route{max-height:260px;overflow:hidden;margin:0 0 16px}
.asch-route .zh{margin:12px 0 8px;font-size:22px;line-height:1.2}
.ahome-sched{display:none;height:0;margin:0;padding:0;overflow:hidden}
.zban,.zhead,.zhead__ps,.zhead__x,.zhead__o{display:contents}
.ztitle{display:grid;grid-template-columns:1fr;gap:16px;margin:12px 0 8px;
padding:clamp(16px,2vw,32px);background:var(--a-page);border-radius:var(--a-radius-shell);
box-shadow:var(--a-shadow-soft);align-items:start;max-height:none;min-height:0}
@media(min-width:900px){.ztitle{grid-template-columns:180px minmax(0,1fr) 160px;
column-gap:clamp(20px,2vw,32px)}}
@media(min-width:1200px){.ztitle{grid-template-columns:240px minmax(0,1fr) 170px;
column-gap:28px;padding:28px 32px}}
.ztitle__poster{aspect-ratio:2/3;border-radius:12px;overflow:hidden;
background:var(--a-surf);position:relative;width:100%;max-width:240px;margin:0 auto;
height:auto;min-height:0}
@media(min-width:900px){.ztitle__poster{margin:0;max-width:none;width:180px}}
@media(min-width:1200px){.ztitle__poster{width:240px}}
@media(max-width:599px){.ztitle__poster{max-width:112px;margin:0}}
.ztitle__poster img,.ztitle__poster .zhead__img{position:absolute;inset:0;z-index:1;width:100%;height:100%;object-fit:cover;max-width:none}
.ztitle__main{min-width:0;display:flex;flex-direction:column;gap:10px}
.ztitle__head{display:flex;gap:14px;align-items:flex-start;justify-content:space-between}
.ztitle__head-text{min-width:0;flex:1}
.ztitle__main h1{font-size:clamp(24px,2.2vw,32px);line-height:1.2;margin:0;
display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.ztitle__o{font-size:clamp(13px,1.1vw,16px);color:var(--a-dim);margin:0}
.ztitle__meta{display:none}
.ztitle__facts{display:grid;grid-template-columns:repeat(auto-fill,minmax(132px,1fr));
gap:10px 14px;margin:0;padding:0;list-style:none}
.ztitle__facts > div{min-width:0}
.ztitle__facts dt{margin:0;font-size:11px;letter-spacing:.04em;text-transform:uppercase;
color:var(--a-dim);font-weight:700}
.ztitle__facts dd{margin:3px 0 0;font-size:14px;color:var(--a-ink);line-height:1.35;
overflow-wrap:anywhere;word-break:normal}
@media(max-width:599px){.ztitle__facts{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px 12px}}
.ztitle__pills{display:flex;flex-wrap:wrap;gap:8px;margin:0}
.ztitle__pills a,.ztitle__pills span{display:inline-flex;align-items:center;min-height:30px;
padding:0 12px;border-radius:var(--a-radius-chip);border:1px solid var(--a-line);background:var(--a-alt);
font-size:13px;color:var(--a-ink)}
.ztitle__desc-panel{background:transparent;border-radius:0;padding:0;margin:2px 0 0}
.ztitle__desc{font-size:clamp(15px,1.15vw,17px);line-height:1.5;color:var(--a-ink);margin:0;
max-width:70ch;display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden}
.ztitle__desc--gap{display:block;-webkit-line-clamp:unset;color:var(--a-dim);font-size:14px;line-height:1.35;
max-height:1.5em;overflow:hidden}
@media(max-width:767px){.ztitle__desc:not(.ztitle__desc--gap){-webkit-line-clamp:6}}
.ztitle__desc.is-open{-webkit-line-clamp:unset;display:block}
.ztitle__more{border:0;background:transparent;color:var(--a-acc);font-weight:700;font-size:14px;
cursor:pointer;padding:0;margin-top:8px;min-height:44px}
.ztitle__cta{display:inline-flex;align-items:center;justify-content:center;min-height:44px;
padding:0 16px;border-radius:10px;background:var(--a-acc);color:#fff;font-weight:700;font-size:15px;
text-decoration:none;width:fit-content}
.ztitle__cta:hover{filter:brightness(1.05)}
.ztitle__actions{display:flex;flex-direction:column;gap:10px;margin-top:4px}
@media(max-width:599px){.ztitle__cta,.ztitle__actions .ztitle__cta{width:100%}}
.ztitle__rail{display:none;min-width:0}
@media(min-width:900px){
  .ztitle__rail{display:flex;flex-direction:column;gap:12px;width:100%;max-width:180px}
}
.ztitle__rail-ratings{margin:0;padding:0;list-style:none;display:flex;flex-direction:column;gap:10px}
.ztitle__rail-ratings li{display:flex;flex-direction:column;gap:2px;min-height:0}
.ztitle__rail-ratings .lab{font-size:11px;letter-spacing:.04em;text-transform:uppercase;
color:var(--a-dim);font-weight:700}
.ztitle__rail-ratings .val{font-size:20px;font-weight:800;color:var(--a-ink);line-height:1.1}
.ztitle__rail-ratings .val[data-missing="1"]{color:var(--a-mute);font-weight:600;font-size:16px}
.ztitle__score{display:none}
.ztitle__dl{display:none}
.ztitle__rels{display:flex;flex-wrap:wrap;gap:8px;margin:4px 0 0}
.ztitle__rels a{display:inline-flex;align-items:center;min-height:36px;padding:0 12px;
border-radius:10px;border:1px solid var(--a-line);background:var(--a-alt);font-size:13px;color:var(--a-acc);font-weight:600}
.zad{display:none}
.zbody{display:none}
.zaside{display:none}
.ztitle-gap{height:16px;max-height:24px;min-height:16px;margin:0;padding:0}
@media(min-width:900px){.ztitle-gap{height:20px}}
/* B08 player shell: status beside heading; 16:9 media only; no fixed 640×360 */
.zpl[data-b08="player"]{margin:0 auto;width:min(100%,1200px);max-width:1200px}
.zpl[data-b08="player"] .zpl__h{margin:0 0 16px;max-height:40px}
@media(min-width:900px){.zpl[data-b08="player"] .zpl__h{margin:0 0 20px}}
.zpl[data-b08="player"] .zpl__f{aspect-ratio:16/9;width:100%;max-width:100%;
min-height:0;height:auto}
.zpl[data-b08="player"] .zpl__f video-player,
.zpl[data-b08="player"] .zpl__f iframe,
.zpl[data-b08="player"] .zpl__f video{width:100% !important;height:100% !important;
max-width:none !important;min-width:0 !important}
.zpl__h{display:flex;align-items:baseline;justify-content:flex-start;gap:12px;flex-wrap:wrap;
margin:0 0 16px;font-size:clamp(22px,2vw,30px);font-weight:700}
.zpl__h span{font-size:13px;font-weight:600;color:var(--a-dim)}
.aep-ctx{display:grid;grid-template-columns:96px minmax(0,1fr);gap:14px 16px;margin:8px 0 12px;
padding:12px;border-radius:var(--a-radius-shell);background:var(--a-page);box-shadow:var(--a-shadow-soft);
align-items:start;max-width:100%}
@media(min-width:900px){.aep-ctx{grid-template-columns:120px minmax(0,1fr);gap:16px 20px;padding:14px 16px}}
.aep-ctx__poster{aspect-ratio:2/3;border-radius:10px;overflow:hidden;background:var(--a-surf);position:relative;width:100%}
.aep-ctx__poster img,.aep-ctx__poster .zhead__img{position:absolute;inset:0;z-index:1;width:100%;height:100%;object-fit:cover}
.aep-ctx__main{min-width:0;display:flex;flex-direction:column;gap:8px}
.aep-ctx__main h1{font-size:clamp(20px,1.8vw,26px);line-height:1.25;margin:0}
.aep-ctx__ep{font-size:14px;font-weight:700;color:var(--a-acc);margin:0}
.aep-ctx__o{font-size:13px;color:var(--a-dim);margin:0}
.aep-ctx__meta{font-size:13px;color:var(--a-dim);margin:0;line-height:1.4}
.aep-ctx__desc{font-size:14px;line-height:1.45;color:var(--a-ink);margin:0;max-width:70ch;
display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.aep-ctx__back{font-size:13px;font-weight:700;color:var(--a-acc);width:fit-content}
.aep-ctx .rbs{margin:2px 0 0}
.aep-ctx + .zpl{margin-top:8px}
.aep-page .zh--ep{font-size:clamp(20px,1.8vw,28px);line-height:1.25;margin:8px 0 12px;font-weight:800}
.aep-page .zpl{margin-top:0}
.aep-page .zepnav{margin:12px 0 16px}
.aep-page .aep-ctx{margin-top:20px}
@media(max-width:599px){.aep-ctx{grid-template-columns:72px minmax(0,1fr);gap:10px 12px;padding:10px}}
.zpl{margin:0 auto;width:min(100%,1200px);max-width:1200px}
.zpl__h{font-size:clamp(22px,2vw,30px);font-weight:700;margin:0 0 16px;
display:flex;align-items:baseline;justify-content:flex-start;gap:12px;flex-wrap:wrap}
.zpl__h span{font-size:13px;font-weight:600;color:var(--a-dim)}
.zpl__f{position:relative;width:100%;aspect-ratio:16/9;background:#101010;border:0;
border-radius:14px;overflow:hidden;max-height:none}
.zpl__f[data-player-host],.zpl__f [data-player-host]{position:absolute;inset:0;width:100%;height:100%;display:block}
.zpl__f video-player{position:absolute;inset:0;display:block;width:100% !important;height:100% !important;min-height:100%}
.zpl__f iframe,.zpl__f video{position:absolute !important;inset:0 !important;width:100% !important;height:100% !important;
max-width:none !important;max-height:none !important;border:0 !important;display:block !important;
object-fit:contain;background:#000}
/* Neutralize global iframe{height:auto} that shrinks the 16:9 shell. */
.zs .zpl__f iframe{height:100% !important;max-width:none !important}
.zpl__f[data-state=active],.zpl__f[data-state=ok],.zpl__f[data-state=resolving],
.zpl__f[data-state=playable]{background:#101010}
.zpl__s,.zpl [data-player-state]{position:absolute;inset:0;display:grid;place-items:center;
padding:16px;text-align:center;color:var(--a-ink);font-size:13px;line-height:1.45;background:var(--a-alt);z-index:2}
.zpl [data-player-state][hidden],.zpl__s[hidden]{display:none !important}
.zpl [data-player-state] b{display:block;font-size:15px;margin-bottom:6px}
.zpl [data-player-state] p{margin:0;max-width:36ch;color:var(--a-dim)}
.zeps{display:grid;gap:8px;margin:12px 0;max-height:70vh;overflow:auto;
grid-template-columns:repeat(auto-fill,minmax(40px,1fr));width:100%}
.zeps a,.zeps span{display:inline-flex;align-items:center;justify-content:center;
min-width:36px;min-height:36px;width:100%;height:clamp(36px,4vw,48px);border-radius:10px;
border:1px solid var(--a-line);background:var(--a-page);font-size:13px;font-weight:700}
.zeps a[aria-current]{background:var(--a-acc);color:#fff;border-color:var(--a-acc)}
.zeps a[data-off]{opacity:.4;pointer-events:none}
.zeps a:focus-visible{outline:2px solid var(--a-acc);outline-offset:2px}
.zsea__h{display:flex;justify-content:space-between;gap:10px;margin:0 0 10px;flex-wrap:wrap}
.zepnav{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0}
.zepnav a{background:var(--a-alt);border-radius:10px;padding:8px 12px;font-size:13px;color:var(--a-acc);font-weight:700}
.zhub{display:grid;gap:14px;margin:14px 0;grid-template-columns:1fr}
@media(min-width:600px){.zhub{grid-template-columns:repeat(2,1fr)}}
@media(min-width:1000px){.zhub{grid-template-columns:repeat(3,1fr)}}
.zhub__c{display:block;padding:14px;border-radius:var(--a-radius-card);background:var(--a-page);
box-shadow:var(--a-shadow-soft);color:inherit;text-decoration:none}
.zhub__c:hover,.zhub__c:focus-visible{box-shadow:var(--a-shadow);outline:none}
.zhub__g{display:flex;gap:4px;margin-bottom:10px}
.zhub__p{flex:1 1 0;aspect-ratio:2/3;overflow:hidden;border-radius:8px;background:var(--a-alt)}
.zhub__img{width:100%;height:100%;object-fit:cover;display:block}
.zhub__t{display:block;font-weight:700;font-size:16px}
.zhub__m{display:block;font-size:12px;color:var(--a-dim);font-weight:600;margin:2px 0 4px}
.zhub__d{display:block;font-size:13px;color:var(--a-dim);line-height:1.45}
/* B13 collections hub: order switch. Touch targets 44px, no clipped labels. */
.ahub__sorts{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 12px}
.ahub__s{display:inline-flex;align-items:center;min-height:44px;padding:0 14px;
border:1px solid var(--a-line);border-radius:999px;background:var(--a-page);
color:var(--a-ink);font-size:13px;font-weight:600;text-decoration:none;white-space:nowrap}
.ahub__s.is-on{background:var(--a-acc);border-color:var(--a-acc);color:#fff}
.ahub__s:focus-visible{outline:2px solid var(--a-acc);outline-offset:2px}
.zseo{margin:20px 0 4px;padding:14px 0;border-top:1px solid var(--a-line);color:var(--a-dim);font-size:14px;line-height:1.5}
.zseo h2{font-size:17px;color:var(--a-ink);margin:0 0 6px}
.zseo details{display:none}
@media(max-width:767px){.zseo__full{display:none}.zseo details{display:block}}
@media(min-width:768px){.zseo details{display:none}}
.zft{border-top:2px solid var(--a-acc);margin:20px 0 0;padding:12px 0 10px}
.zft__inner{display:flex;flex-direction:column;gap:12px}
.zft__cols{display:grid;gap:18px;grid-template-columns:1fr;
align-items:start}
/* B14: планшет — две колонки, рабочий стол — четыре, как в паспорте блока. */
@media(min-width:768px){.zft__cols{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(min-width:1100px){.zft__cols{grid-template-columns:repeat(4,minmax(0,1fr))}}
.zft__col{display:flex;flex-direction:column;gap:6px;min-width:0}
.zft__col b{color:var(--a-ink);font-size:13px;margin:0 0 4px}
.zft__col a{color:var(--a-acc);font-weight:500;font-size:13px;min-height:32px;
display:inline-flex;align-items:center;width:fit-content}
.zft__row{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:10px 18px}
.zft__about{font-size:13px;color:var(--a-dim);line-height:1.4;margin:0;max-width:62ch;
display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden}
.zft__nav{display:flex;flex-wrap:wrap;gap:6px 14px;align-items:center}
.zft__nav a{font-size:13px;color:var(--a-dim);font-weight:600;min-height:36px;display:inline-flex;align-items:center}
.zft__nav a:hover{color:var(--a-acc)}
.zft__contact:empty,.zft__legal:empty{display:none}
@media(max-width:767px){.zft__cols{grid-template-columns:1fr 1fr}.zft__about{width:100%;-webkit-line-clamp:3}}
@media(max-width:479px){.zft__cols{grid-template-columns:1fr}}
.zft__bar{display:flex;justify-content:space-between;gap:12px;align-items:center;
padding-top:6px;border-top:1px solid var(--a-line);font-size:12px;color:var(--a-mute);flex-wrap:wrap}
/* Правило .zvb здесь больше не нужно: нижний бар Animedia не печатает версию
   и коммит. У Zona свой бар и своё правило — оно не затронуто. */
@media(max-width:767px){.zft{padding:12px 0 8px}.zft__about{-webkit-line-clamp:3}}
.rbs{margin:6px 0 0}.rbs__l{display:flex;flex-wrap:wrap;gap:8px;list-style:none;margin:0;padding:0}
.rbs__i{display:inline-flex;align-items:center;gap:6px;padding:6px 10px;border-radius:10px;
background:var(--a-alt);border:1px solid var(--a-line);font-size:12px}
.rbs__s{color:var(--a-acc);font-weight:700}.rbs__n{color:var(--a-ink);font-weight:700}
.rbs--none{display:none}
.vh{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
"""



def _подставить(шаблон: str, токены: dict) -> str:
    готово = шаблон
    for имя, значение in токены.items():
        готово = готово.replace(f"@{имя.upper()}@", значение)
    return готово


#: Описание семейства в оформлении 1.1.0. Здесь навигация, словарь разделов и
#: то, какой рисовальщик страниц применяется. Разные значения — разные сайты,
#: и это единственное место, где различие объявлено.
СЕМЕЙСТВА_1_1 = {
    "lords": {
        "вид": "lords",
        "токены": ЛОРДС_ТОКЕНЫ,
        "стиль": lambda: _общее(ЛОРДС_ТОКЕНЫ) + _подставить(ЛОРДС_СТИЛЬ, ЛОРДС_ТОКЕНЫ),
        "нав": [("/new/", "Новинки"), ("/movies/", "Фильмы"),
                ("/series/", "Сериалы"),
                ("/animation/", "Мультфильмы"),
                ("/collections/", "Подборки"),
                ("/catalog/", "Каталог")],
        "поиск": "Введите название",
        "полосы": [("Фильмы", "/movies/", "Фильм"),
                   ("Сериалы", "/series/", "Сериал"),
                   ("Мультфильмы", "/animation/", "Мультфильм")],
        "лид": "Фильмы и сериалы онлайн",
        "метка": "LF",
    },
    "zona": {
        "вид": "zona",
        "токены": ЗОНА_ТОКЕНЫ,
        "стиль": (lambda: _общее(ЗОНА_ТОКЕНЫ) + _подставить(ЗОНА_СТИЛЬ, ЗОНА_ТОКЕНЫ))
                  if ОФОРМЛЕНИЕ_ПЕРЕРАБОТАННОЕ else
                  (lambda: _общее(ЗОНА_ТОКЕНЫ_1_1) + _подставить(ЗОНА_СТИЛЬ_1_1, ЗОНА_ТОКЕНЫ_1_1)),
        # Clean kind routes — same map as Обработчик.МАРШРУТЫ_ВИДА. Query
        # `?kind=` remains valid for combinations; nav must not 404.
        "нав": [("/", "Обзор"), ("/new/", "Что нового"),
                ("/movies/", "Кино"), ("/series/", "Сериалы"),
                ("/animation/", "Анимация"), ("/collections/", "Подборки"),
                ("/catalog/", "Весь каталог")],
        "поиск": "Название фильма или сериала",
        "полосы": [("Кино", "/movies/", "Фильм"),
                   ("Сериалы", "/series/", "Сериал"),
                   ("Анимация", "/animation/", "Мультфильм")],
        "лид": "Кинопортал: что смотреть и где это найти",
        "метка": "Z",
    },
    "animedia": {
        "вид": "animedia",
        "токены": АНИМЕДИА_ТОКЕНЫ,
        "стиль": lambda: _общее(АНИМЕДИА_ТОКЕНЫ) + _подставить(АНИМЕДИА_СТИЛЬ, АНИМЕДИА_ТОКЕНЫ),
        # B01: registry routes only. Top-100 omitted until standalone route exists.
        # /new/ = catalog additions (not episode events). /schedule/ exists → shown.
        "нав": [("/", "Главная"), ("/catalog/", "Каталог"),
                ("/new/", "Новое в каталоге"),
                ("/collections/", "Подборки"),
                ("/schedule/", "Расписание")],
        "поиск": "Поиск аниме",
        "полосы": [],
        "лид": "Аниме онлайн",
        "метка": "A",
    },
}


# ----------------------------------------------------------------------
#  Плеер: контракт провайдера и честные состояния
# ----------------------------------------------------------------------
#
# Пустая чёрная область плеером не является. Поэтому состояний здесь шесть, и
# каждое либо показывает изображение, либо объясняет словами, чего не хватает:
#
#   playable    — есть publisher id и внешний идентификатор, элемент выставлен;
#   awaiting    — источник есть, но серия ещё не выбрана: 16:9-shell без
#                 <video-player> и без тяжёлого iframe/stream (контракт:
#                 до выбора серии iframe = 0, stream не запрашивается);
#   unavailable — номер серии есть в eps, но avail его не покрывает: SDK
#                 не монтируется (иначе provider UI врёт «Эпизод N» / timeout);
#   loading     — элемент выставлен, скрипт провайдера ещё не поднял его;
#   nosource    — у записи нет ни kp, ни imdb: показывать нечего и нечем;
#   noaccess    — publisher id витрине не выдан;
#   provider    — провайдер ответил `noData` на эту запись;
#   error       — скрипт провайдера не загрузился;
#   slow        — клиентский timeout: скрипт есть, проигрыватель не поднялся.
#
# Кнопки «Смотреть», которая ничего не делает, среди них нет. Обещание
# воспроизведения даётся только в состоянии playable, и там оно обеспечено
# настоящим элементом провайдера.

#: Адрес скрипта плеера. Значение контрактное (`knowledge/cdnvideohub/
#: PLAYER_CONTRACT.yaml`), а не подобранное: оборачивать элемент в свой iframe
#: контракт прямо запрещает (PC-4).
СКРИПТ_ПЛЕЕРА = "https://player.cdnvideohub.com/s2/stable/video-player.umd.js"

#: Агрегаторы, разрешённые контрактом. Расширять перечень здесь нельзя: чужое
#: значение провайдер отвергает, а мы бы выдали отказ за состояние записи.
АГРЕГАТОРЫ = ("cvh", "kp", "mdl", "mali", "imdb")

#: Соответствие «ключ внешнего идентификатора → агрегатор». `imdb` в контракте
#: агрегатором не значится, поэтому запись только с imdb источника не имеет.
КЛЮЧ_АГРЕГАТОРА = {"kp": "kp"}

#: Расширенная цепочка запасных ключей. Работает только в режиме `provider-id`:
#: прежний режим обязан вести себя в точности как раньше, иначе выкладка по
#: одному домену теряет смысл — менялись бы сразу все.
ЗАПАСНЫЕ_КЛЮЧИ = (("kp", "kp"), ("mdl", "mdl"), ("mal", "mali"), ("imdb", "imdb"))

#: Собственный идентификатор записи в каталоге провайдера.
ИДЕНТИФИКАТОР_ПРОВАЙДЕРА = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def _конфиг_плеера() -> dict:
    """Publisher ID витрины. Только ссылка на файл, значение не в коде.

    Значение живёт вне репозитория (правило секретов фабрики) и приезжает
    файлом, путь к которому задаёт юнит. Нет файла — нет плеера, и страница
    скажет об этом прямо, а не покажет чёрный прямоугольник.
    """
    путь = os.environ.get("LORDS_PLAYER_CONFIG") or _рядом_с_каталогом("player-{site}.json")
    if not путь:
        return {}
    try:
        значение = json.loads(Path(путь).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    издатель = str(значение.get("publisher_id") or "").strip()
    # Плеер вызывает Number(publisherId): нечисловое значение превращается в
    # NaN, и провайдер отвечает 400. Проверка здесь дешевле, чем на странице.
    if not издатель.isdigit() or издатель.startswith("0"):
        return {}
    # Режим выбора источника. Артефакт рендерера один на все витрины, поэтому
    # переключатель живёт здесь, в боковом файле витрины: только так выкладку
    # можно вести по одному домену и откатывать её тоже по одному.
    режим = str(значение.get("source_mode") or "external-ids").strip()
    if режим not in ("external-ids", "provider-id"):
        режим = "external-ids"
    return {"publisher_id": издатель, "source_mode": режим}


ПЛЕЕР = _конфиг_плеера()


#: Навигация «Смотреть по жанрам» на главной Zona. Коды — из sidecar genre_codes
#: (`triller` — фактический код снимка, не `thriller`). дорама ≠ драма.
ZONA_GENRE_NAV = (
    ("west_content", "западный контент"),
    ("dorama", "дорама"),
    ("drama", "драма"),
    ("comedy", "комедия"),
    ("triller", "триллер"),
)



def кандидаты_источника(деталь: dict) -> list[tuple[str, str]]:
    """Упорядоченные кандидаты (агрегатор, id) для режима provider-id.

    Live на /title/aida-vozvraschaetsya/: UUID→cvh давал noData при наличии
    available kp; UI показывал Play + «нет дорожки». Available sources раньше UUID.
    """
    увидели: set[tuple[str, str]] = set()
    итог: list[tuple[str, str]] = []

    def добавить(агрегатор: str, значение: str) -> None:
        агрегатор = (агрегатор or "").strip()
        значение = (значение or "").strip()
        if not значение or агрегатор not in АГРЕГАТОРЫ:
            return
        ключ = (агрегатор, значение)
        if ключ in увидели:
            return
        увидели.add(ключ)
        итог.append(ключ)

    источники = [с for с in (деталь.get("sources") or ()) if isinstance(с, dict)]
    for с in источники:
        if str(с.get("availability_status") or "").strip().lower() == "available":
            добавить(str(с.get("provider") or ""), str(с.get("source_id") or ""))
    свой = str(деталь.get("id") or "").strip().lower()
    if ИДЕНТИФИКАТОР_ПРОВАЙДЕРА.match(свой):
        добавить("cvh", свой)
    for с in источники:
        статус = str(с.get("availability_status") or "").strip().lower()
        if статус in {"unavailable", "missing", "none"}:
            continue
        добавить(str(с.get("provider") or ""), str(с.get("source_id") or ""))
    внешние = деталь.get("external_ids")
    if isinstance(внешние, dict):
        for ключ, агрегатор in ЗАПАСНЫЕ_КЛЮЧИ:
            добавить(агрегатор, str(внешние.get(ключ) or ""))
    return итог


def источник_по_провайдеру(деталь: dict) -> tuple[str, str]:
    """Первый кандидат; пусто — источника нет."""
    кандидаты = кандидаты_источника(деталь)
    return кандидаты[0] if кандидаты else ("", "")


def источник_плеера(деталь: dict) -> tuple[str, str]:
    """Агрегатор и идентификатор записи у него. Пусто — источника нет.

    Прежний порядок знал единственный ключ `kp` и терял записи, у которых
    источник записан под `mdl` или `mali`: 5 883 на Lords и 2 511 на Animedia.
    Страница честно сообщала «источник не передан», хотя дорожки у провайдера
    были. Новый порядок включается витриной поимённо, через её боковой файл.
    """
    if ПЛЕЕР.get("source_mode") == "provider-id":
        return источник_по_провайдеру(деталь)
    внешние = деталь.get("external_ids")
    if not isinstance(внешние, dict):
        return "", ""
    for ключ, агрегатор in КЛЮЧ_АГРЕГАТОРА.items():
        значение = str(внешние.get(ключ) or "").strip()
        if значение and агрегатор in АГРЕГАТОРЫ:
            return агрегатор, значение
    return "", ""


def состояние_плеера(деталь: dict) -> tuple[str, str, str]:
    """Серверное состояние: provider_configured ≠ playable_source.

    `playable` = publisher + кандидат источника; SDK ещё подтверждает дорожку.
    """
    агрегатор, ид = источник_плеера(деталь)
    if not ПЛЕЕР.get("publisher_id"):
        return ("noaccess", "Просмотр на витрине не подключён",
                "Витрине не выдан идентификатор издателя, и обращаться к провайдеру "
                "ей нечем. Это настройка витрины, а не состояние записи: каталог, "
                "описание и список серий на странице доступны полностью.")
    if not (агрегатор and ид):
        if not деталь:
            return ("nosource", "Подробности записи ещё не в снимке",
                    "Карточка уже есть в каталоге, но боковой файл подробностей "
                    "её ещё не содержит. Без идентификатора источника плеер "
                    "запрашивать нечего; после обновления sidecar он появится здесь.")
        return ("nosource", "Источник для этой записи не передан",
                "У записи нет идентификатора ни одного из разрешённых агрегаторов, "
                "поэтому запрашивать у провайдера нечего. Как только источник "
                "появится в каталоге, плеер включится здесь сам.")
    return ("playable", "", "")


def выбрать_доступную_серию(деталь: dict) -> tuple[int, int | None]:
    """Owner policy FIRST_PLAYABLE_DETERMINISTIC (ANIMEDIA-B10-B16-20260920-01).

    Generic title hubs bind the first confirmed playable episode after sorting
    ``(season_number ASC, episode_number ASC)``. Exact episode routes never
    call this helper for identity — they keep the requested S/E.
    """
    сезоны = список_серий(деталь)
    if not сезоны:
        return 1, None
    доступные: list[tuple[int, int]] = []
    for с in sorted(сезоны, key=lambda x: int(x.get("n") or 0)):
        season_n = int(с.get("n") or 0)
        if season_n < 1:
            continue
        avail = int(с.get("avail") or 0)
        for н in range(1, avail + 1):
            доступные.append((season_n, н))
    if доступные:
        # First playable after ASC sort — never silently pick a random/latest.
        return доступные[0]
    # No playable episode: season known, episode unknown → honest empty shell.
    return int(сезоны[0].get("n") or 1), None


def ждёт_выбора_серии(запись: dict, деталь: dict, эпизод: int | None) -> bool:
    """Сериал с известным составом сезонов: на хабе тайтла тяжёлый плеер рано.

    Пока серия не выбрана, `<video-player>` и stream-запрос запрещены: SDK
    иначе поднимает iframe и тянет плейлист «за зрителя». Фильмы и записи без
    списка сезонов монтируются сразу — выбирать нечего.
    """
    if эпизод is not None:
        return False
    return bool(список_серий(деталь))


def новинки_с_источником(данные: "Данные", подробности: "Подробности",
                         сколько: int = 12) -> list:
    """Свежие записи, у которых sidecar уже даёт playable-источник.

    Измерено на lordserial33.biz 2026-09-18: каталог 20:45 опередил details
    04:06 на 35 slug, и 24 из 36 карточек главной открывали nosource. Главная
    обязана вести на то, что уже можно смотреть, а не на рассинхрон снимков.
    """
    собрано = []
    for запись in sorted(данные.items,
                         key=lambda з: з.get("published_at") or "",
                         reverse=True):
        if состояние_плеера(подробности.get(запись["slug"]))[0] != "playable":
            continue
        собрано.append(запись)
        if len(собрано) >= сколько:
            break
    return собрано


def разметка_плеера(вид, запись: dict, деталь: dict, сезон: int,
                    эпизод: int | None) -> tuple[str, str]:
    """Возвращает (код состояния, HTML внутренности рамки плеера).

    Серверный `playable`/`resolving` = publisher + кандидат. Подпись
    «источник подключён» и READY выставляет только клиент после подтверждения.
    """
    код, заголовок, текст = состояние_плеера(деталь)
    if код != "playable":
        return код, (f'<div class="{вид.кл_состояния}" data-player-state>'
                     f"<b>{html.escape(заголовок)}</b><p>{html.escape(текст)}</p></div>")
    if ждёт_выбора_серии(запись, деталь, эпизод):
        return ("awaiting",
                f'<div class="{вид.кл_состояния}" data-player-state>'
                "<b>Выберите серию</b>"
                "<p>Откройте серию в списке ниже — тогда загрузится плеер. "
                "До выбора серии запросов к провайдеру нет.</p></div>")
    if эпизод is not None and not серия_с_дорожкой(деталь, сезон, эпизод):
        доступно = 0
        всего = 0
        for с in список_серий(деталь):
            if с["n"] == сезон:
                доступно, всего = с["avail"], с["eps"]
                break
        return ("unavailable",
                f'<div class="{вид.кл_состояния}" data-player-state>'
                "<b>Дорожки этой серии ещё нет</b>"
                f"<p>Серия {html.escape(str(эпизод))} заявлена в сезоне "
                f"{html.escape(str(сезон))} "
                f"(в снимке серий {html.escape(str(всего))}, с дорожкой "
                f"{html.escape(str(доступно))}), но источник ещё не отдал "
                "плейлист на этот номер. Плеер не подключается: иначе "
                "провайдер показал бы чужой эпизод или завис бы в таймауте. "
                "Откройте серию из доступных в списке ниже.</p></div>")
    if ПЛЕЕР.get("source_mode") == "provider-id":
        кандидаты = кандидаты_источника(деталь)
    else:
        а, и = источник_плеера(деталь)
        кандидаты = [(а, и)] if а and и else []
    if not кандидаты:
        return ("nosource",
                f'<div class="{вид.кл_состояния}" data-player-state>'
                "<b>Источник для этой записи не передан</b>"
                "<p>Запрашивать у провайдера нечего.</p></div>")
    агрегатор, ид = кандидаты[0]
    список_json = html.escape(json.dumps(
        [{"aggregator": а, "id": i} for а, i in кандидаты],
        ensure_ascii=False, separators=(",", ":")))
    атрибуты = {
        "ident": f"player-{запись['slug']}-s{сезон}"
                 + (f"e{эпизод}" if эпизод is not None else ""),
        "season": str(сезон),
        "data-publisher-id": ПЛЕЕР["publisher_id"],
        "data-title-id": ид, "data-aggregator": агрегатор,
        "is-show-voice-only": "false", "is-show-banner": "true",
        "disable-licensed": "false",
        "autoplay": "0",
    }
    if эпизод is not None:
        атрибуты["episode"] = str(эпизод)
    строка = " ".join(f'{к}="{html.escape(str(з))}"' for к, з in атрибуты.items())
    # SSR: resolving — кандидат есть, playable_source ещё не подтверждён.
    return ("resolving",
        f'<div data-player-host data-src-candidates="{список_json}">'
        f"<video-player {строка}></video-player></div>"
        f'<div class="{вид.кл_состояния}" data-player-state hidden></div>'
        '<noscript><div class="' + вид.кл_состояния + '">'
        "<b>Нужен JavaScript</b><p>Плеер подключается скриптом провайдера, "
        "и без JavaScript он не запустится. Описание, серии и каталог "
        "доступны без него.</p></div></noscript>"
    )


СКРИПТ_ПЛЕЕРА_КЛИЕНТ = """
(function(){
 var f=document.querySelector('[data-player]'); if(!f) return;
 var host=f.querySelector('[data-player-host]');
 if(!host) return;
 var st=f.querySelector('[data-player-state]');
 var cands=[];
 try{ cands=JSON.parse(host.getAttribute('data-src-candidates')||'[]')||[]; }catch(e){ cands=[]; }
 var idx=0, token=0, поднялся=false, отказ=false, seen, timers=[], maxFallback=3;
 var baseAttrs={}, progress={t0:0, c0:0, ok:false};
 function el(){ return host.querySelector('video-player'); }
 function clearTimers(){ timers.forEach(clearTimeout); timers=[]; if(seen){clearInterval(seen);seen=null;} }
 function providerShell(node){
  if(!node) return null;
  var root=node.shadowRoot;
  if(!root) return null;
  return root.querySelector('iframe,video');
 }
 function nestedVideo(node){
  var root=node && node.shadowRoot; if(!root) return null;
  return root.querySelector('video');
 }
 function hideOverlay(){
  if(!st) return;
  st.hidden=true;
  st.setAttribute('hidden','');
  st.style.display='none';
  st.innerHTML='';
 }
 function showOverlay(t,p){
  if(!st) return;
  st.hidden=false;
  st.removeAttribute('hidden');
  st.style.display='';
  st.innerHTML='<b></b><p></p>';
  st.firstChild.textContent=t;
  st.lastChild.textContent=p;
 }
 function state(k,t,p){
  if(отказ&&k==='ok') return;
  /* Hard failures hide the component. Soft/active states never cover a live iframe. */
  var hard=(k==='provider'||k==='error'||k==='nosource'||k==='noaccess'||k==='unavailable');
  if(hard){ отказ=true; clearTimers(); }
  f.setAttribute('data-state',k);
  var node=el();
  if(k==='ok'||k==='resolving'||k==='active'){
   hideOverlay();
   if(node) node.hidden=false;
   if(k==='ok') поднялся=true;
   return;
  }
  if(k==='slow'){
   /* False-negative guard: provider chrome already mounted → keep it visible. */
   if(providerShell(node)){
    f.setAttribute('data-state','active');
    hideOverlay();
    if(node) node.hidden=false;
    return;
   }
   if(node) node.hidden=true;
   showOverlay(t,p);
   return;
  }
  if(node) node.hidden=true;
  showOverlay(t,p);
 }
 function snapshot(node){
  baseAttrs={};
  if(!node) return;
  ['ident','season','episode','is-show-voice-only','is-show-banner','disable-licensed','data-publisher-id'].forEach(function(a){
   var v=node.getAttribute(a); if(v!=null) baseAttrs[a]=v;
  });
 }
 function destroy(){
  clearTimers();
  var node=el();
  if(!node) return;
  try{ node.remove(); }catch(e){}
 }
 function mountAt(i){
  idx=i;
  var c=cands[i]; if(!c) return;
  var prev=el();
  if(prev) snapshot(prev);
  destroy();
  поднялся=false; отказ=false; progress={t0:0,c0:0,ok:false};
  var n=document.createElement('video-player');
  Object.keys(baseAttrs).forEach(function(a){ n.setAttribute(a, baseAttrs[a]); });
  n.setAttribute('data-title-id', c.id||'');
  n.setAttribute('data-aggregator', c.aggregator||'');
  host.appendChild(n);
  bind(n, ++token);
 }
 function markPlaying(evName, ct){
  if(отказ) return;
  поднялся=true;
  window.__animediaPlayback={
   token:token, event:evName||'playing', at:Date.now(),
   currentTime: ct||0, confirmed:!!progress.ok
  };
  window.__zonaPlayerReady=window.__animediaPlayback;
  state('ok');
 }
 function observeProgress(v, my){
  if(!v || v.__animediaBound) return;
  v.__animediaBound=true;
  var onTick=function(){
   if(my!==token || отказ) return;
   if(v.paused) return;
   var ct=v.currentTime||0;
   if(!progress.t0){ progress.t0=Date.now(); progress.c0=ct; return; }
   var dt=(Date.now()-progress.t0)/1000;
   var dc=ct-progress.c0;
   if(dt>=5 && dc>=3){
    progress.ok=true;
    markPlaying('progress+3s', ct);
   } else if(ct>0.05){
    /* Shell is alive; never cover it while media advances. */
    state('active');
   }
  };
  ['playing','play','timeupdate'].forEach(function(ev){
   v.addEventListener(ev, onTick);
  });
 }
 function bind(node, my){
  if(!node) return;
  snapshot(node);
  state('resolving');
  /* Contract documents only noData as a provider failure signal. */
  node.addEventListener('noData', function(){
   if(my!==token) return;
   if(idx+1<cands.length && (idx+1)<=maxFallback){
    state('resolving');
    mountAt(idx+1);
    return;
   }
   state('provider','Провайдер не отдал источник',
    'Для этой серии у провайдера сейчас нет дорожки. Остальные серии и описание на странице работают.');
  });
  clearTimers();
  seen=setInterval(function(){
   if(my!==token || отказ) return;
   var shell=providerShell(node);
   var v=nestedVideo(node);
   if(v) observeProgress(v, my);
   if(shell && !поднялся){
    /* Provider chrome mounted — keep resolving/active, never false-fail over it. */
    state('active');
   }
   if(v && !v.paused && (v.currentTime||0)>0.05) observeProgress(v, my);
  },400);
  timers.push(setTimeout(function(){
   if(my!==token || отказ || поднялся) return;
   if(seen){clearInterval(seen);seen=null;}
   if(providerShell(node)){
    state('active');
    return;
   }
   state('slow','Плеер не поднялся',
    'Скрипт провайдера загрузился, но окно воспроизведения не появилось. Обновите страницу; описание и серии доступны и сейчас.');
  },15000));
 }
 var first=el();
 if(first){
  if(!cands.length){
   cands=[{aggregator:first.getAttribute('data-aggregator')||'', id:first.getAttribute('data-title-id')||''}];
  }
  bind(first, ++token);
 }
 var s=document.querySelector('[data-player-script]');
 if(s){ s.addEventListener('error',function(){
  state('error','Скрипт плеера не загрузился',
   'Браузер не смог получить скрипт провайдера: его мог заблокировать расширение или сеть. Страница и список серий продолжают работать.');}); }
})();
"""


# ----------------------------------------------------------------------
#  Рисовальщики страниц
# ----------------------------------------------------------------------


#: Атрибут текущего пункта. Вынесен в константу не ради краткости: f-строка в
#: Python 3.10 не принимает обратный слэш в выражении, и вставленная по месту
#: кавычка ломает разбор всего файла.
ТЕКУЩАЯ_СТРАНИЦА = ' aria-current="page"'
ТЕКУЩИЙ_ПУНКТ = ' aria-current="true"'


#: Отдавать ли постеры своим адресом вместо прямой ссылки на внешний CDN.
#: Animedia включает first-party `/poster/` по умолчанию: live измерение
#: показало массовый отказ hotlink с cdnvideohub. Lords/Zona сохраняют
#: прежний default (прямая ссылка), пока явно не зададут env=1.
_ПОСТЕР_ENV = os.environ.get("LORDS_POSTER_SAME_ORIGIN", "").strip().lower()
ПОСТЕРЫ_СВОИМ_АДРЕСОМ = (
    _ПОСТЕР_ENV in ("1", "true", "yes")
    or (_ПОСТЕР_ENV not in ("0", "false", "no") and СЕМЕЙСТВО == "animedia")
)
ВНЕШНИЙ_ПОСТЕР = "https://poster.cdnvideohub.com/"
ПОСТЕР_HOSTS = frozenset({"poster.cdnvideohub.com"})
ПОСТЕР_MAX_BYTES = 2_500_000
_ПОСТЕР_КЭШ: dict[str, tuple[float, bytes, str]] = {}
_ПОСТЕР_НЕГАТИВ: dict[str, float] = {}


def _адрес_постера(адрес: str | None) -> str | None:
    """Адрес постера: свой путь либо адрес источника, без третьего варианта."""
    if not адрес:
        return адрес
    if ПОСТЕРЫ_СВОИМ_АДРЕСОМ and адрес.startswith(ВНЕШНИЙ_ПОСТЕР):
        return "/poster/" + адрес[len(ВНЕШНИЙ_ПОСТЕР):]
    return адрес


def _постер_безопасный_ключ(хвост: str) -> str | None:
    """Только uuid-like имя файла у allowlist host — без path traversal."""
    хвост = (хвост or "").lstrip("/")
    if not хвост or ".." in хвост or "/" in хвост or "\\" in хвост:
        return None
    if not re.fullmatch(r"[0-9a-fA-F-]{8,64}\.(?:webp|jpg|jpeg|png|gif)", хвост):
        return None
    return хвост


def отдать_постер(хвост: str) -> tuple[int, bytes, str]:
    """First-party proxy: allowlist host, timeouts, size/MIME limits, caches."""
    import http.client
    import time

    ключ = _постер_безопасный_ключ(хвост)
    if not ключ:
        return 404, b"", "text/plain"
    сейчас = time.time()
    if ключ in _ПОСТЕР_НЕГАТИВ and сейчас - _ПОСТЕР_НЕГАТИВ[ключ] < 300:
        return 404, b"", "text/plain"
    кэш = _ПОСТЕР_КЭШ.get(ключ)
    if кэш and сейчас - кэш[0] < 86_400:
        return 200, кэш[1], кэш[2]
    try:
        соед = http.client.HTTPSConnection("poster.cdnvideohub.com", timeout=4)
        соед.request("GET", "/" + ключ, headers={
            "User-Agent": "site-factory-nova-poster/1.2",
            "Accept": "image/webp,image/*,*/*;q=0.8",
        })
        отв = соед.getresponse()
        if отв.status != 200:
            _ПОСТЕР_НЕГАТИВ[ключ] = сейчас
            соед.close()
            return 404, b"", "text/plain"
        тип = (отв.getheader("Content-Type") or "").split(";")[0].strip().lower()
        if not тип.startswith("image/"):
            _ПОСТЕР_НЕГАТИВ[ключ] = сейчас
            соед.close()
            return 415, b"", "text/plain"
        данные = отв.read(ПОСТЕР_MAX_BYTES + 1)
        соед.close()
        if len(данные) > ПОСТЕР_MAX_BYTES:
            _ПОСТЕР_НЕГАТИВ[ключ] = сейчас
            return 413, b"", "text/plain"
        _ПОСТЕР_КЭШ[ключ] = (сейчас, данные, тип)
        if len(_ПОСТЕР_КЭШ) > 512:
            # Простой LRU-суррогат: выкинуть самые старые четверть.
            устаревшие = sorted(_ПОСТЕР_КЭШ.items(), key=lambda п: п[1][0])[:128]
            for у in устаревшие:
                _ПОСТЕР_КЭШ.pop(у[0], None)
        return 200, данные, тип
    except OSError:
        _ПОСТЕР_НЕГАТИВ[ключ] = сейчас
        return 504, b"", "text/plain"


_ПОСТЕР_КЭШ: dict[str, tuple[float, bytes, str]] = {}
_ПОСТЕР_НЕГАТИВ: dict[str, float] = {}


def _адрес_постера(адрес: str | None) -> str | None:
    """Адрес постера: свой путь либо адрес источника, без третьего варианта."""
    if not адрес:
        return адрес
    if ПОСТЕРЫ_СВОИМ_АДРЕСОМ and адрес.startswith(ВНЕШНИЙ_ПОСТЕР):
        return "/poster/" + адрес[len(ВНЕШНИЙ_ПОСТЕР):]
    return адрес


def заглушка_постера(запись: dict, класс_заглушки: str, класс_картинки: str,
                     ширина: int = 300, высота: int = 450) -> str:
    """Постер с заглушкой ПОД ним, а не вместо него.

    Заглушка рисуется всегда и лежит слоем ниже изображения. Alt у значимого
    постера — название тайтла; декоративная заглушка без изображения не
    объявляет зрителю внутреннюю диагностику («постер не открылся»).
    """
    название = (запись.get("title") or "").strip() or "Без названия"
    первая = html.escape(название[:1].upper())
    постер = _адрес_постера(запись.get("poster"))
    заглушка = (f'<span class="{класс_заглушки}" aria-hidden="true">'
                f"<b>{первая}</b></span>")
    if not постер:
        return заглушка
    картинка = (
        f'<img class="{класс_картинки}" src="{html.escape(постер)}" '
        f'alt="{html.escape(название)}" loading="lazy" width="{ширина}" '
        f'height="{высота}" data-poster>')
    return заглушка + картинка


#: Снятие изображения, которого нет. Слушатель стоит на фазе перехвата: событие
#: `error` у `<img>` не всплывает, и обычный делегированный обработчик его не
#: увидит. Один слушатель на документ вместо атрибута у каждой карточки: на
#: странице каталога их сорок восемь.
СКРИПТ_ПОСТЕРОВ = (
    "document.addEventListener('error',function(e){var i=e.target;"
    "if(i&&i.tagName==='IMG'&&i.hasAttribute('data-poster'))i.hidden=true;},true);"
)

#: Скрипт горизонтальных лент. Отдельная константа, а не дополнение к
#: СКРИПТ_ПОСТЕРОВ: тот подключают обе витрины, и дописывание в него изменило
#: бы байты, которые отдаёт Lords. Здесь ровно кнопочная прокрутка; свайп,
#: колесо и клавиатура работают нативно и без скрипта.
СКРИПТ_ЛЕНТ = (
    "document.addEventListener('click',function(e){"
    "var b=e.target.closest('[data-rl]');if(!b)return;"
    "var v=document.getElementById(b.getAttribute('aria-controls'));if(!v)return;"
    "var d=Math.max(160,Math.round(v.clientWidth*0.86));"
    "v.scrollBy({left:b.getAttribute('data-rl')==='next'?d:-d,behavior:'smooth'});"
    "});"
)

#: Только Animedia: на узком экране пункты меню открываются кнопкой.
#: Escape и повторный клик закрывают; focus возвращается на кнопку;
#: body scroll блокируется, пока меню открыто.
СКРИПТ_АНИМЕДИА_ТЕМА_BOOT = (
    "(function(){try{var k='animedia-theme',r=document.documentElement,s=localStorage.getItem(k);"
    "var t=(s==='light'||s==='dark')?s:((window.matchMedia&&window.matchMedia('(prefers-color-scheme: dark)').matches)?'dark':'light');"
    "r.setAttribute('data-theme',t);r.style.colorScheme=t;}catch(e){document.documentElement.setAttribute('data-theme','light');}})();"
)

СКРИПТ_АНИМЕДИА_ШАПКА = (
    "(function(){"
    "var TK='animedia-theme';"
    "function applyTheme(t){var r=document.documentElement;"
    "if(t!=='dark'&&t!=='light'){"
    "t=(window.matchMedia&&window.matchMedia('(prefers-color-scheme: dark)').matches)?'dark':'light';}"
    "r.setAttribute('data-theme',t);r.style.colorScheme=t;"
    "var b=document.querySelector('[data-theme-toggle]');"
    "if(b)b.setAttribute('aria-pressed',t==='dark'?'true':'false');}"
    "function sync(){try{var stored=localStorage.getItem(TK);applyTheme(stored||'');}catch(e){applyTheme('');}}"
    "if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',sync);else sync();"
    "try{var mq=window.matchMedia('(prefers-color-scheme: dark)');"
    "mq.addEventListener('change',function(){try{if(!localStorage.getItem(TK))sync();}catch(err){}});}catch(e){}"
    "var lastFocus=null;"
    "function drawerEls(){return{"
    "d:document.getElementById('zhd-drawer'),"
    "b:document.querySelector('[data-drawer-toggle]'),"
    "bd:document.querySelector('[data-drawer-backdrop]')};}"
    "function closeTax(){document.querySelectorAll('[data-tax-toggle]').forEach(function(btn){"
    "btn.setAttribute('aria-expanded','false');"
    "var p=document.getElementById(btn.getAttribute('aria-controls')||'');"
    "if(p)p.hidden=true;});}"
    "function closeDrawer(){var e=drawerEls();if(!e.d||!e.b)return;"
    "e.d.hidden=true;e.d.setAttribute('aria-hidden','true');"
    "e.b.setAttribute('aria-expanded','false');"
    "if(e.bd)e.bd.hidden=true;document.body.classList.remove('zhd-lock');"
    "if(lastFocus){try{lastFocus.focus()}catch(err){}}}"
    "function openDrawer(btn){var e=drawerEls();if(!e.d||!e.b)return;"
    "lastFocus=btn||e.b;closeTax();e.d.hidden=false;e.d.setAttribute('aria-hidden','false');"
    "e.b.setAttribute('aria-expanded','true');if(e.bd)e.bd.hidden=false;"
    "document.body.classList.add('zhd-lock');"
    "var f=e.d.querySelector('a,button,[tabindex]:not([tabindex=\"-1\"])');"
    "try{if(f)f.focus()}catch(err){}}"
    "document.addEventListener('click',function(e){"
    "var th=e.target.closest('[data-theme-toggle]');"
    "if(th){var cur=document.documentElement.getAttribute('data-theme')==='dark'?'dark':'light';"
    "var next=cur==='dark'?'light':'dark';try{localStorage.setItem(TK,next);}catch(err){}"
    "applyTheme(next);return;}"
    "var more=e.target.closest('[data-desc-toggle]');"
    "if(more){var p=document.getElementById(more.getAttribute('aria-controls')||'title-desc');"
    "if(p){var open=p.classList.toggle('is-open');more.setAttribute('aria-expanded',open?'true':'false');"
    "more.textContent=open?'Свернуть':'Развернуть';}return;}"
    "var tax=e.target.closest('[data-tax-toggle]');"
    "if(tax){var id=tax.getAttribute('aria-controls');var panel=document.getElementById(id||'');"
    "var open=tax.getAttribute('aria-expanded')!=='true';"
    "closeTax();if(open&&panel){tax.setAttribute('aria-expanded','true');panel.hidden=false;}return;}"
    "var db=e.target.closest('[data-drawer-toggle]');"
    "if(db){var e2=drawerEls();if(e2.d&&!e2.d.hidden)closeDrawer();else openDrawer(db);return;}"
    "if(e.target.closest('[data-drawer-close]')||e.target.closest('[data-drawer-backdrop]')){"
    "closeDrawer();return;}"
    "var af=e.target.closest('[data-afilt-open]');"
    "if(af){var box=af.closest('[data-afilt]');if(box){"
    "var on=!box.classList.contains('is-open');box.classList.toggle('is-open',on);"
    "af.setAttribute('aria-expanded',on?'true':'false');}return;}"
    "if(!e.target.closest('.zhd__dd'))closeTax();"
    "});"
    "document.addEventListener('keydown',function(e){"
    "if(e.key!=='Escape')return;closeTax();"
    "var dr=document.getElementById('zhd-drawer');"
    "if(dr&&!dr.hidden)closeDrawer();"
    "});"
    "})();"
)

#: Lords mobile drawer: focus return + Escape + body scroll lock.
СКРИПТ_ЛОРДС_ШАПКА = (
    "(function(){"
    "function close(nav,btn){if(!nav||!btn)return;nav.classList.remove('is-open');"
    "btn.setAttribute('aria-expanded','false');document.body.classList.remove('nav-lock');"
    "try{btn.focus()}catch(e){}}"
    "document.addEventListener('click',function(e){"
    "var b=e.target.closest('[data-nav-toggle]');if(!b)return;"
    "var n=document.getElementById('hd-nav');if(!n)return;"
    "var open=n.classList.toggle('is-open');"
    "b.setAttribute('aria-expanded',open?'true':'false');"
    "document.body.classList.toggle('nav-lock',open);"
    "if(open){var a=n.querySelector('a');if(a)try{a.focus()}catch(err){}}"
    "});"
    "document.addEventListener('keydown',function(e){"
    "if(e.key!=='Escape')return;"
    "var n=document.getElementById('hd-nav');var b=document.querySelector('[data-nav-toggle]');"
    "if(n&&n.classList.contains('is-open'))close(n,b);"
    "});"
    "})();"
)


def _склеить(части) -> str:
    return "".join(ч for ч in части if ч)


def _число(значение) -> str:
    """Оценка печатается как пришла, без округления и без выдумки."""
    try:
        ч = float(значение)
    except (TypeError, ValueError):
        return ""
    return (f"{ч:.3f}".rstrip("0").rstrip(".")) if ч else ""


def _длительность(минут) -> str:
    try:
        м = int(минут)
    except (TypeError, ValueError):
        return ""
    if м <= 0:
        return ""
    часы, остаток = divmod(м, 60)
    return f"{часы} ч {остаток} мин" if часы else f"{остаток} мин"


МЕСЯЦЫ = ("января", "февраля", "марта", "апреля", "мая", "июня",
          "июля", "августа", "сентября", "октября", "ноября", "декабря")


def _дата(значение: str) -> str:
    совпало = re.match(r"^(\d{4})-(\d{2})-(\d{2})", str(значение or ""))
    if not совпало:
        return ""
    год, месяц, день = (int(ч) for ч in совпало.groups())
    if not 1 <= месяц <= 12:
        return ""
    return f"{день} {МЕСЯЦЫ[месяц - 1]} {год}"


class Вид:
    """Общая механика семейства: данные, адреса, разметка Schema.

    Здесь живёт всё, что от оформления не зависит: что считается сезоном,
    какой адрес у серии, что попадает в хлебные крошки и в `ld+json`. Различие
    семейств — в наследниках, и только в разметке.
    """

    кл_состояния = "pl__state"

    def __init__(self, семейство: dict, данные: "Данные", подробности: Подробности,
                 индекс: dict, имя_витрины: str):
        self.се = семейство
        self.д = данные
        self.п = подробности
        self.индекс = индекс
        self.имя = имя_витрины
        self.хост = ""

    # --- адреса ------------------------------------------------------
    def адрес_сезона(self, slug: str, сезон: int) -> str:
        return f"/title/{slug}/season-{сезон}/"

    def адрес_эпизода(self, slug: str, сезон: int, эпизод: int) -> str:
        return f"/title/{slug}/season-{сезон}/episode-{эпизод}/"

    def канон(self, путь: str) -> str:
        хост = self.хост or ""
        return f"https://{хост}{путь}" if хост else путь

    # --- данные ------------------------------------------------------
    def запись(self, slug: str) -> dict | None:
        return self.индекс["slug"].get(slug)

    def деталь(self, slug: str) -> dict:
        return self.п.get(slug)

    def похожие(self, запись: dict, деталь: dict, сколько: int = 6) -> list:
        """Похожее выбирается по жанру, затем по виду и году. Порядок
        детерминирован: одна и та же запись всегда даёт один и тот же ряд."""
        текущий = запись["slug"]
        собрано, видели = [], {текущий}
        for код in (деталь.get("genre_codes") or [])[:3]:
            for slug in self.индекс["genre"].get(код, ()):
                if slug in видели:
                    continue
                сосед = self.индекс["slug"].get(slug)
                if not сосед:
                    continue
                видели.add(slug)
                собрано.append(сосед)
                if len(собрано) >= сколько:
                    return собрано
        for сосед in self.д.items:
            if len(собрано) >= сколько:
                break
            if сосед["slug"] in видели or сосед.get("kind") != запись.get("kind"):
                continue
            видели.add(сосед["slug"])
            собрано.append(сосед)
        return собрано

    # --- разметка ----------------------------------------------------
    def schema_тайтла(self, запись: dict, деталь: dict, путь: str) -> str:
        сериал = bool(деталь.get("seasons")) or запись.get("kind") == "Сериал"
        узел = {
            "@context": "https://schema.org",
            "@type": "TVSeries" if сериал else "Movie",
            "name": запись["title"],
            "url": self.канон(путь),
        }
        if запись.get("poster"):
            узел["image"] = запись["poster"]
        if деталь.get("description"):
            узел["description"] = деталь["description"]
        if запись.get("year"):
            узел["datePublished"] = str(запись["year"])
        if деталь.get("genres"):
            узел["genre"] = деталь["genres"]
        if деталь.get("countries"):
            узел["countryOfOrigin"] = деталь["countries"]
        if деталь.get("original_name"):
            узел["alternateName"] = деталь["original_name"]
        if сериал and деталь.get("seasons"):
            узел["numberOfSeasons"] = len(деталь["seasons"])
            узел["numberOfEpisodes"] = всего_серий(деталь)
        # `aggregateRating` не выставляется намеренно: schema.org требует при
        # нём ratingCount или reviewCount, а числа голосов источник не даёт.
        # Поставить единицу или опустить обязательное поле значило бы
        # подделать показатель, который поисковик покажет как наш.
        return json.dumps(узел, ensure_ascii=False)

    def schema_эпизода(self, запись: dict, деталь: dict, сезон: int,
                       эпизод: int, путь: str) -> str:
        узел = {
            "@context": "https://schema.org", "@type": "TVEpisode",
            "episodeNumber": эпизод,
            "name": f"{запись['title']} — {сезон} сезон, {эпизод} серия",
            "url": self.канон(путь),
            "partOfSeason": {"@type": "TVSeason", "seasonNumber": сезон},
            "partOfSeries": {"@type": "TVSeries", "name": запись["title"],
                             "url": self.канон(f"/title/{запись['slug']}/")},
        }
        if запись.get("poster"):
            узел["image"] = запись["poster"]
        return json.dumps(узел, ensure_ascii=False)

    def schema_крошек(self, крошки) -> str:
        элементы = [
            {"@type": "ListItem", "position": i + 1, "name": имя,
             **({"item": self.канон(адрес)} if адрес else {})}
            for i, (адрес, имя) in enumerate(крошки)
        ]
        return json.dumps({"@context": "https://schema.org",
                           "@type": "BreadcrumbList", "itemListElement": элементы},
                          ensure_ascii=False)

    def карточка_графа(self, *, тип: str, титул: str, описание: str,
                       путь: str, изображение: str = "") -> dict:
        """Open Graph страницы. Значения — те же, что ушли в разметку и Schema."""
        return {
            "type": тип, "title": титул, "description": описание,
            "url": self.канон(путь), "image": изображение,
            "site_name": self.имя, "locale": "ru_RU",
        }

    # --- то, что обязаны дать наследники -----------------------------
    def оболочка(self, **кв) -> str:
        raise NotImplementedError

    def главная(self) -> str:
        raise NotImplementedError

    def коллекция(self, данные) -> str:
        """Полная страница коллекции. Разметка — та же, что у разделов.

        Оформление здесь намеренно не изобретается: коллекция — это тот же
        раздел каталога, только его состав задаёт контракт, а не шаблон.
        """
        на_странице = 60
        всего_страниц = max(1, (данные.total + на_странице - 1) // на_странице)
        листалка = "".join(
            (f"<span>{n}</span>" if n == данные.page else
             f'<a href="{данные.canonical_path}?page={n}">{n}</a>')
            for n in range(max(1, данные.page - 3),
                           min(всего_страниц, данные.page + 3) + 1))
        если_пусто = (
            f'<div class="empty">{html.escape(данные.title)}: пока пусто.</div>')
        сетка = ('<div class="grid">'
                 + "".join(карточка(к.raw) for к in данные.items)
                 + "</div>") if данные.items else если_пусто
        # H1 обязателен контрактом SEO-снимка (Meta/page-metadata): коллекция —
        # самостоятельная страница, а не секция без заголовка первого уровня.
        тело = (f'<section class="sec"><div class="sec__h">'
                f"<h1>{html.escape(данные.title)}</h1>"
                f'<a href="/catalog/">В каталог →</a></div>'
                f'<p class="claim">{html.escape(данные.description)}</p>'
                f"{сетка}"
                + (f'<div class="pg">{листалка}</div>' if данные.total > на_странице
                   else "")
                + "</section>")
        return self.оболочка(
            тело, данные.title, данные.canonical_path,
            описание=данные.description or f"Подборка «{данные.title}».",
        )

    def список(self, разд, зпр) -> str:
        raise NotImplementedError

    def поиск(self, зпр) -> str:
        raise NotImplementedError

    def тайтл(self, запись, деталь) -> str:
        raise NotImplementedError

    def серия(self, запись, деталь, сезон, эпизод) -> str:
        raise NotImplementedError

    def не_найдено(self, путь: str) -> str:
        raise NotImplementedError


def страницы(текущая: int, всего: int, окно: int = 2) -> list:
    """Номера листалки: первая, окно вокруг текущей, последняя, многоточия."""
    if всего <= 1:
        return []
    нужные = {1, всего}
    нужные.update(range(max(1, текущая - окно), min(всего, текущая + окно) + 1))
    итог, прежний = [], 0
    for н in sorted(нужные):
        if прежний and н - прежний > 1:
            итог.append(None)
        итог.append(н)
        прежний = н
    return итог


def отбор(данные: "Данные", индекс: dict, зпр: dict, раздел: str) -> tuple[list, dict]:
    """Выборка каталога по параметрам запроса. Возвращает (набор, выбранное).

    Неизвестные country/genre/sort не игнорируются молча: пустая выдача или
    явная сортировка по умолчанию. `/new` ограничен свежим хвостом снимка —
    весь каталог в другом порядке «новинками» не выдаём.
    """
    набор = list(данные.items)
    вид = (зпр.get("kind") or [None])[0]
    год = (зпр.get("year") or [None])[0]
    жанр = (зпр.get("genre") or [None])[0]
    страна = (зпр.get("country") or [None])[0]
    тип = (зпр.get("type") or [None])[0]
    сорт = (зпр.get("sort") or [None])[0]
    неизвестный_фильтр = False
    if вид:
        набор = [з for з in набор if з.get("kind") == вид]
    if тип:
        разрешённые = (индекс.get("type") or {}).get(str(тип).lower())
        if разрешённые is None:
            неизвестный_фильтр = True
            набор = []
        else:
            членство = set(разрешённые)
            набор = [з for з in набор if з["slug"] in членство]
    if год:
        if str(год).isdigit():
            набор = [з for з in набор if з.get("year") == int(год)]
        else:
            неизвестный_фильтр = True
            набор = []
    if жанр:
        ключи = [жанр, нормализовать(жанр), нормализовать(транслит(жанр))]
        разрешённые = None
        for ключ in ключи:
            if not ключ:
                continue
            разрешённые = индекс["genre"].get(ключ)
            if разрешённые is not None:
                break
        if разрешённые is None:
            неизвестный_фильтр = True
            набор = []
        else:
            членство = set(разрешённые)
            набор = [з for з in набор if з["slug"] in членство]
    if страна:
        разрешённые = (индекс.get("country") or {}).get(страна)
        if разрешённые is None:
            неизвестный_фильтр = True
            набор = []
        else:
            членство = set(разрешённые)
            набор = [з for з in набор if з["slug"] in членство]
    # «Новинки» / недавно добавленное: только хвост по published_at, не весь каталог.
    НОВИНКИ_ПРЕДЕЛ = 240
    if раздел == "/new":
        набор = sorted(набор, key=lambda з: з.get("published_at") or "", reverse=True)
        набор = [з for з in набор if з.get("published_at")][:НОВИНКИ_ПРЕДЕЛ]
    elif сорт == "rating":
        def _рейтинг(з):
            return float(з.get("_rating") or 0.0)
        набор = sorted(набор, key=lambda з: (_рейтинг(з), з.get("_n") or "", з["slug"]),
                       reverse=True)
    elif сорт == "year":
        набор = sorted(набор, key=lambda з: (з.get("year") or 0, з["slug"]), reverse=True)
    elif сорт == "title":
        набор = sorted(набор, key=lambda з: (з.get("_n") or нормализовать(з["title"]),
                                             з["slug"]))
    elif сорт == "date" or (
            not сорт and раздел in ("/catalog", "/movies", "/series", "/animation")):
        # Default catalog freshness: published_at DESC, slug DESC (deterministic).
        набор = sorted(
            набор,
            key=lambda з: (з.get("published_at") or "", з["slug"]),
            reverse=True)
    elif сорт:
        неизвестный_фильтр = True
        набор = []
    elif раздел == "/collections":
        # Hub handled separately; keep stable title order if ever reused.
        набор = sorted(набор, key=lambda з: (з.get("_n") or нормализовать(з["title"]),
                                             з["slug"]))
    # B11: dedupe by canonical_title_id (slug fallback) — preserve first occurrence.
    seen_ids: set[str] = set()
    deduped: list = []
    for з in набор:
        tid = str(з.get("canonical_title_id") or з.get("title_id") or з.get("slug") or "")
        if not tid or tid in seen_ids:
            continue
        seen_ids.add(tid)
        deduped.append(з)
    набор = deduped
    выбрано = {"kind": вид, "year": год, "genre": жанр, "country": страна,
               "type": тип, "sort": сорт}
    if неизвестный_фильтр:
        выбрано["_unknown"] = "1"
    return набор, выбрано


def запрос_строкой(выбрано: dict, **замена) -> str:
    """Собрать `?k=v` с percent-encoding значений (kind=Фильм → %D0%A4…)."""
    поля = dict(выбрано)
    поля.update(замена)
    пары = [(к, з) for к, з in поля.items()
            if з and not str(к).startswith("_")]
    return ("?" + urlencode(пары, quote_via=quote)) if пары else ""


def факты(вид: Вид, запись: dict, деталь: dict) -> list:
    """Пары «что — значение» страницы. Пустого значения в списке не бывает."""
    собрано = []

    def добавить(метка, значение):
        if значение:
            собрано.append((метка, значение))

    добавить("Оригинальное название", html.escape(деталь.get("original_name") or ""))
    добавить("Год", html.escape(str(запись.get("year") or "")))
    добавить("Тип", html.escape(запись.get("kind") or ""))
    страны = деталь.get("countries") or []
    добавить("Страна", html.escape(", ".join(страны)))
    жанры = деталь.get("genres") or []
    коды = деталь.get("genre_codes") or []
    if жанры:
        ссылки = []
        for i, имя in enumerate(жанры):
            код = коды[i] if i < len(коды) else ""
            ссылки.append(f'<a href="/catalog/{запрос_строкой({"genre": код})}">{html.escape(имя)}</a>'
                          if код else html.escape(имя))
        добавить("Жанр", " · ".join(ссылки))
    добавить("Время", html.escape(_длительность(деталь.get("duration"))))
    добавить("Дата выхода", html.escape(_дата(деталь.get("premiere_date") or "")))
    сезоны = деталь.get("seasons") or []
    if сезоны:
        серий = всего_серий(деталь)
        доступно = sum(int(с.get("avail") or 0) for с in сезоны)
        хвост = "" if доступно >= серий else f", доступно {доступно}"
        добавить("Серии", html.escape(
            f"Сезон {сезоны[-1].get('n') or len(сезоны)} · {серий} серий{хвост}"
            if len(сезоны) == 1 else
            f"{len(сезоны)} сезона, {серий} серий{хвост}"))
    студии = деталь.get("voice_studios") or []
    добавить("Озвучка", html.escape(", ".join(студии[:4])))
    команда = деталь.get("crew") or []
    режиссёры = [ч["name"] for ч in команда if ч.get("role") == "director"]
    актёры = [ч["name"] for ч in команда if ч.get("role") == "actor"]
    добавить("Режиссёр", html.escape(", ".join(режиссёры[:3])))
    добавить("В ролях", html.escape(", ".join(актёры[:8])))
    return собрано


def оценки(деталь: dict) -> list:
    """Оценки с источником. Числа голосов источник не передаёт, и его тут нет:
    выдуманное «1 голос» хуже отсутствия строки."""
    собрано = []
    кп = _число(деталь.get("kinopoisk_rating"))
    им = _число(деталь.get("imdb_rating"))
    if кп:
        собрано.append(("kp", "Кинопоиск", кп))
    if им:
        собрано.append(("imdb", "IMDb", им))
    return собрано


def список_серий(деталь: dict) -> list:
    """Сезоны с полными списками номеров серий.

    Здесь нет ни обрезания, ни «первых ста»: сериал с двумястами десятью
    сериями обязан показывать все двести десять, иначе двести десятая
    недостижима с его собственной страницы. Номер серии — порядковый номер
    внутри сезона, он же номер в адресе, он же номер на экране. Одно число,
    один смысл; смешение внутреннего идентификатора с номером показа — ровно
    та ошибка, из-за которой список обрывался на сотне.
    """
    готово = []
    for сезон in (деталь.get("seasons") or []):
        номер = int(сезон.get("n") or 0)
        всего = int(сезон.get("eps") or 0)
        доступно = int(сезон.get("avail") or 0)
        if номер < 1 or всего < 1:
            continue
        готово.append({"n": номер, "eps": всего, "avail": доступно,
                       "номера": list(range(1, всего + 1))})
    return готово


def серия_с_дорожкой(деталь: dict, сезон: int, эпизод: int) -> bool:
    """Есть ли у серии дорожка по снимку (`avail`), а не только номер в `eps`.

    Измерено на lordserial33.biz: у сериала `avail=3`, `eps=9` страница
    `/episode-7/` монтировала `<video-player episode="7">`. UI говорил «серия 7»,
    провайдер в контроле показывал «Эпизод 3» (последняя с дорожкой) и через
    15 с срабатывал таймаут «Плеер не поднялся». Список уже помечал 4–9 как
    `data-off`; страница серии обязана говорить то же самое и НЕ поднимать SDK.
    """
    if сезон < 1 or эпизод < 1:
        return False
    for с in список_серий(деталь):
        if с["n"] == сезон:
            return эпизод <= с["avail"]
    return False


def границы_серии(деталь: dict, сезон: int, эпизод: int) -> tuple:
    """Предыдущая и следующая серия по всему произведению, через границы сезонов."""
    плоско = []
    for с in список_серий(деталь):
        for н in с["номера"]:
            плоско.append((с["n"], н))
    if not плоско:
        return None, None
    try:
        место = плоско.index((сезон, эпизод))
    except ValueError:
        return None, None
    предыдущая = плоско[место - 1] if место > 0 else None
    следующая = плоско[место + 1] if место + 1 < len(плоско) else None
    return предыдущая, следующая


# ---------------------------- Lords -----------------------------------


class ВидЛордс(Вид):
    """Узкий светлый лист на тёмной подложке, плотная сетка, оценки под постером."""

    кл_состояния = "pl__state"

    def оболочка(self, тело: str, титул: str, путь: str, *, актив: str = "",
                 описание: str = "", разметка: str = "", код: int = 200,
                 крошки: str = "", og: dict | None = None) -> str:
        нав = "".join(
            f'<a href="{закодировать_запрос(u)}"{ТЕКУЩАЯ_СТРАНИЦА if u == актив else ""}>{html.escape(t)}</a>'
            for u, t in self.се["нав"])
        схемы = "".join(f'<script type="application/ld+json">{р}</script>'
                        for р in ([разметка] if разметка else []))
        описание_мета = (f'<meta name="description" content="{html.escape(описание)}">'
                         if описание else "")
        канон = (f'<link rel="canonical" href="{html.escape(self.канон(путь))}">'
                 if путь and код == 200 else "")
        return f"""<!doctype html><html lang="ru" data-template-version="{ВЕРСИЯ}" data-template-family="{СЕМЕЙСТВО}" data-build-id="{СБОРКА}" data-design="lords-sheet">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(титул)}</title>{описание_мета}{канон}
<meta name="robots" content="noindex, nofollow">
{_открытый_граф(og or {})}
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
{_мета_версии()}
<style>{self.се["стиль"]()}</style><script>{СКРИПТ_ПОСТЕРОВ}
{СКРИПТ_ЛОРДС_ШАПКА}</script></head>
<body><div class="backdrop"></div>
<a class="skip" href="#main">Перейти к содержимому</a>
<div class="sheet">
<header class="hd"><div class="hd__in">
<a class="hd__logo" href="/"><span class="hd__mark" aria-hidden="true">{html.escape(self.се["метка"])}</span>{html.escape(self.имя)}</a>
<form class="hd__s" action="/search/" method="get" role="search">
<label class="vh" for="q">Поиск по каталогу</label>
<input id="q" name="q" placeholder="{html.escape(self.се["поиск"])}">
<button type="submit" aria-label="Найти">&#9906;</button></form>
<button class="hd__menu" type="button" data-nav-toggle aria-controls="hd-nav"
 aria-expanded="false" aria-label="Меню разделов">&#9776;</button>
<nav id="hd-nav" class="hd__nav" aria-label="Разделы">{нав}</nav>
</div></header>{крошки}
<main id="main" class="pad">{тело}</main>
{self._подвал()}
</div>{схемы}</body></html>"""

    def _подвал(self) -> str:
        """Footer: working section links + compact build badge (no test slogans)."""
        жанры = "".join(
            f'<a href="/genre/{html.escape(код)}/">{html.escape(имя)}</a>'
            for код, имя in (self.индекс.get("genre_names") or [])[:8])
        годы = "".join(
            f'<a href="/year/{г}/">{г}</a>' for г in (self.д.years or [])[:6])
        runtime = (МАНИФЕСТ.get("runtime_commit") or МАНИФЕСТ.get("source_commit") or "")[:8]
        tip = (f"source={МАНИФЕСТ.get('source_commit', '')[:12]} "
               f"runtime={(МАНИФЕСТ.get('runtime_commit') or МАНИФЕСТ.get('source_commit') or '')[:12]} "
               f"build={СБОРКА}")
        about = (f"{html.escape(self.имя)} — каталог фильмов, сериалов и мультфильмов "
                 "из утверждённого снимка витрины. Описание и оценки только из источника.")
        return (
            '<footer class="ft">'
            '<div class="ft__cols">'
            '<div class="ft__col"><b>Разделы</b>'
            '<a href="/movies/">Фильмы</a><a href="/series/">Сериалы</a>'
            '<a href="/animation/">Мультфильмы</a><a href="/new/">Новинки</a>'
            '<a href="/collections/">Подборки</a></div>'
            f'<div class="ft__col"><b>Жанры</b>{жанры or "<span>жанры появятся из sidecar</span>"}</div>'
            f'<div class="ft__col"><b>Годы</b>{годы or "<span>—</span>"}</div>'
            f'<div class="ft__col"><b>О витрине</b><p class="ft__about">{about}</p></div>'
            "</div>"
            f'<div class="ft__bar"><span class="vb" title="{html.escape(tip)}">'
            f"Lords · {html.escape(ВЕРСИЯ)} · {html.escape(runtime)}</span></div>"
            "</footer>")

    # --- составные части ---------------------------------------------
    def карточка(self, запись: dict) -> str:
        деталь = self.деталь(запись["slug"])
        изо = заглушка_постера(запись, "c__none", "c__img")
        if 'class="c__none"' in изо:
            изо = изо.replace('class="c__none"', 'class="c__none" aria-hidden="true"', 1)
        значок = ""
        сезоны = деталь.get("seasons") or []
        if сезоны:
            последний = сезоны[-1]
            значок = (f'<span class="c__badge">{последний["n"]} сезон, '
                      f'{последний["eps"]} сер.</span>')
        elif запись.get("kind"):
            значок = f'<span class="c__badge">{html.escape(запись["kind"])}</span>'
        кп = _число(деталь.get("kinopoisk_rating"))
        им = _число(деталь.get("imdb_rating"))
        if кп or им:
            полоса = ('<div class="c__r">'
                      + (f'<span class="c__kp">КП<i>{кп}</i></span>' if кп else "")
                      + (f'<span class="c__imdb">IMDb<i>{им}</i></span>' if им else "")
                      + "</div>")
        else:
            полоса = '<div class="c__r" aria-hidden="true"></div>'
        год = f'<span class="c__y">{запись["year"]}</span>' if запись.get("year") else ""
        return (f'<a class="c" href="{запись["url"]}" '
                f'aria-label="{html.escape(запись["title"])}">'
                f'<span class="c__p">{изо}{значок}</span>'
                f'<span class="c__cap"><span class="c__t">{html.escape(запись["title"])}</span>{год}</span>'
                f"{полоса}</a>")

    def сетка(self, набор, класс="grid") -> str:
        return f'<div class="{класс}">' + "".join(self.карточка(з) for з in набор) + "</div>"

    def листалка(self, разд: str, выбрано: dict, стр: int, всего: int) -> str:
        пункты = страницы(стр, всего)
        if not пункты:
            return ""
        куски = []
        for н in пункты:
            if н is None:
                куски.append("<em>…</em>")
            elif н == стр:
                куски.append(f'<span aria-current="page">{н}</span>')
            else:
                хвост = запрос_строкой(выбрано, page=(н if н > 1 else None))
                куски.append(f'<a href="{разд}/{хвост}">{н}</a>')
        return f'<nav class="pg" aria-label="Страницы">{"".join(куски)}</nav>'

    def крошки(self, звенья) -> str:
        куски = []
        for адрес, имя in звенья:
            куски.append(f'<a href="{адрес}">{html.escape(имя)}</a>' if адрес
                         else f"<b>{html.escape(имя)}</b>")
        return f'<nav class="crumbs" aria-label="Хлебные крошки">{" » ".join(куски)}</nav>'

    # --- страницы -----------------------------------------------------
    def главная(self) -> str:
        полосы = []
        занято: set = set()
        готовые = новинки_с_источником(self.д, self.п, 10_000)

        def взять(набор, сколько=12):
            out = []
            for з in набор:
                if з["slug"] in занято:
                    continue
                занято.add(з["slug"])
                out.append(з)
                if len(out) >= сколько:
                    break
            return out

        # 1) Популярное сейчас — только если есть реальный рейтинг в sidecar.
        топ = sorted(
            (з for з in готовые if (з.get("_rating") or 0) > 0),
            key=lambda з: з.get("_rating") or 0, reverse=True)
        топ12 = взять(топ, 12)
        if топ12:
            полосы.append(self._полоса("Популярное сейчас", "/catalog/?sort=rating", топ12))
        # 2) Новинки / недавно добавленное
        нов = взять(готовые, 12)
        if нов:
            полосы.append(self._полоса("Новинки", "/new/", нов))
        # 3–5) kind shelves
        for титул, ссылка, вид in self.се["полосы"]:
            набор = взять([з for з in готовые if з.get("kind") == вид], 12)
            if набор:
                полосы.append(self._полоса(титул, ссылка, набор))
        # 6) Подборки — ссылки на контракт, не дубль каталога
        if КОЛЛЕКЦИИ is not None:
            полосы.append(self._полоса_подборок())
        # 7) По жанрам
        жанр_блок = self._полоса_жанров()
        if жанр_блок:
            полосы.append(жанр_блок)
        # 8) Высокий рейтинг (остаток после топа)
        высокий = взять(топ, 12)
        if высокий:
            полосы.append(self._полоса("Высокий рейтинг", "/catalog/?sort=rating", высокий))

        intro = (
            f'<h1 class="lead">{html.escape(self.се["лид"])}</h1>'
            f'<p class="zsub" style="margin:0 0 14px;color:#5b6470;font-size:13.5px;line-height:1.55">'
            f"{html.escape(self.имя)} показывает фильмы, сериалы и мультфильмы "
            "из утверждённого снимка каталога. Подборки и фильтры опираются на "
            "переданные жанры, годы и оценки — без выдуманных фактов.</p>")
        bottom = (
            '<section class="sec" style="margin-top:22px"><h2>О каталоге</h2>'
            f'<p style="margin:0;line-height:1.6;color:#4d555e;font-size:14px;max-width:68ch">'
            f"Витрина {html.escape(self.имя)} собрана фабрикой поверх закрытого "
            "снимка: название, год, тип, постер и оценки приходят из источника. "
            "Разделы «Новинки», фильмы, сериалы и мультфильмы ведут в рабочие "
            "выборки. Поиск понимает кириллицу, латиницу и транслит. "
            "Индексация поисковиками на этом стенде закрыта политикой noindex."
            "</p></section>")
        тело = intro + _склеить(полосы) + bottom
        return self.оболочка(
            тело, f"{self.имя} — фильмы и сериалы онлайн", "/", актив="/",
            описание=(f"{self.имя}: смотреть фильмы, сериалы и мультфильмы онлайн. "
                      "Каталог, новинки и подборки из утверждённого снимка."),
            og=self.карточка_графа(
                тип="website",
                титул=f"{self.имя} — фильмы и сериалы онлайн",
                описание=f"Каталог {self.имя}",
                путь="/"))

    def _полоса(self, титул: str, ссылка: str, набор) -> str:
        if not набор:
            return ""
        return (
            f'<section class="sec-rail"><div class="sec-rail__h">'
            f'<h2><a href="{закодировать_запрос(ссылка)}">{html.escape(титул)}</a></h2>'
            f'<a class="sec-rail__all" href="{закодировать_запрос(ссылка)}">Весь раздел</a>'
            f"</div>{self.сетка(набор)}</section>")

    def _полоса_подборок(self) -> str:
        снимок = Снимок.получить(self.д, self.п) if КОЛЛЕКЦИИ else None
        if снимок is None:
            return ""
        карточки = []
        for спец in КОЛЛЕКЦИИ.спецификации(СЕМЕЙСТВО)[:6]:
            данные = КОЛЛЕКЦИИ.разрешить(спец.collection_key, снимок, СЕМЕЙСТВО, предел=1)
            if данные is None or not данные.items:
                continue
            карточки.append(
                f'<a class="hub__c" href="{html.escape(данные.canonical_path)}">'
                f"<b>{html.escape(данные.title)}</b>"
                f"<p>{html.escape((данные.description or '')[:160])}</p>"
                f"<span>Открыть подборку →</span></a>")
        if not карточки:
            return ""
        return (
            '<section class="sec-rail"><div class="sec-rail__h">'
            '<h2><a href="/collections/">Подборки</a></h2>'
            '<a class="sec-rail__all" href="/collections/">Весь раздел</a></div>'
            f'<div class="hub">{"".join(карточки)}</div></section>')

    def _полоса_жанров(self) -> str:
        имена = self.индекс.get("genre_names") or []
        if not имена:
            return ""
        ссылки = "".join(
            f'<a href="/genre/{html.escape(код)}/">{html.escape(имя)}</a>'
            for код, имя in имена[:10])
        return (
            '<section class="sec-rail"><div class="sec-rail__h">'
            '<h2>По жанрам</h2></div>'
            f'<div class="tabs">{ссылки}</div></section>')

    def хаб_подборок(self) -> str:
        """`/collections/` — список контрактных подборок, не копия каталога."""
        снимок = Снимок.получить(self.д, self.п) if КОЛЛЕКЦИИ else None
        карточки = []
        if снимок is not None and КОЛЛЕКЦИИ is not None:
            for спец in КОЛЛЕКЦИИ.спецификации(СЕМЕЙСТВО):
                данные = КОЛЛЕКЦИИ.разрешить(спец.collection_key, снимок, СЕМЕЙСТВО, предел=1)
                if данные is None or not данные.items:
                    continue
                n = данные.total
                хвост = f"{n} записей" if n else ""
                карточки.append(
                    f'<a class="hub__c" href="{html.escape(данные.canonical_path)}">'
                    f"<b>{html.escape(данные.title)}</b>"
                    f"<p>{html.escape(данные.description or '')}</p>"
                    f"<span>{html.escape(хвост)} →</span></a>")
        if not карточки:
            тело = ('<h1 class="lead">Подборки</h1>'
                    '<div class="empty"><b>Подборки пока пусты</b>'
                    "Контракт коллекций не вернул ни одной непустой выборки. "
                    '<a href="/catalog/">Открыть каталог</a></div>')
        else:
            тело = (f'<h1 class="lead">Подборки</h1>'
                    f'<p class="zsub" style="margin:0 0 12px;color:#5b6470">'
                    f"Тематические выборки витрины — не полный каталог.</p>"
                    f'<div class="hub">{"".join(карточки)}</div>')
        return self.оболочка(тело, f"Подборки — {self.имя}", "/collections/",
                             актив="/collections/",
                             описание=f"Подборки витрины {self.имя}.")

    def список(self, разд: str, зпр: dict) -> str:
        имена = {"/catalog": "Каталог", "/new": "Недавно добавлено",
                 "/collections": "Подборки"}
        титул = имена.get(разд, "Каталог")
        if выбрано_kind := (зпр.get("kind") or [None])[0]:
            титул = {"Фильм": "Фильмы", "Сериал": "Сериалы",
                     "Мультфильм": "Мультфильмы"}.get(выбрано_kind, титул)
        набор, выбрано = отбор(self.д, self.индекс, зпр, разд)
        стр = max(1, int((зпр.get("page") or ["1"])[0] or 1))
        всего = max(1, (len(набор) + НА_СТРАНИЦЕ_1_1 - 1) // НА_СТРАНИЦЕ_1_1) if набор else 1
        стр = min(стр, всего)
        кусок = набор[(стр - 1) * НА_СТРАНИЦЕ_1_1: стр * НА_СТРАНИЦЕ_1_1]
        чипы = [f'<span class="tabs__pill">{html.escape(титул)} ›</span>']
        for к in self.д.kinds:
            текущий = ' aria-current="true"' if выбрано.get("kind") == к else ""
            чипы.append(f'<a href="{разд}/{запрос_строкой(выбрано, kind=к, page=None)}"{текущий}>'
                        f"{html.escape(к)}</a>")
        активные = {к: в for к, в in выбрано.items() if в and к != "_unknown"}
        if активные:
            чипы.append(f'<a href="{разд}/">Сбросить</a>')
        годы = "".join(
            f'<a href="{разд}/{запрос_строкой(выбрано, year=г, page=None)}"'
            f'{ТЕКУЩИЙ_ПУНКТ if выбрано.get("year") == str(г) else ""}>{г}</a>'
            for г in self.д.years[:12])
        сорт_чипы = "".join(
            f'<a href="{разд}/{запрос_строкой(выбрано, sort=с, page=None)}"'
            f'{ТЕКУЩИЙ_ПУНКТ if выбрано.get("sort") == с else ""}>{html.escape(имя)}</a>'
            for с, имя in (("title", "По названию"), ("date", "По дате"),
                           ("year", "По году"), ("rating", "По рейтингу")))
        жанры = "".join(
            f'<a href="/genre/{html.escape(код)}/"'
            f'{ТЕКУЩИЙ_ПУНКТ if выбрано.get("genre") == код else ""}>{html.escape(имя)}</a>'
            for код, имя in (self.индекс.get("genre_names") or [])[:12])
        страны = "".join(
            f'<a href="/country/{html.escape(код)}/"'
            f'{ТЕКУЩИЙ_ПУНКТ if выбрано.get("country") == код else ""}>{html.escape(имя)}</a>'
            for код, имя in (self.индекс.get("country_names") or [])[:8])
        h1 = html.escape(титул)
        подзаг = f'<p class="zsub" style="margin:0 0 10px;color:#5b6470">{len(набор)} записей в выборке</p>'
        if выбрано.get("_unknown"):
            пусто = ('<div class="empty"><b>Неизвестный фильтр</b>'
                     "Параметр фильтра не распознан и не применён молча. "
                     "Сбросьте условия или выберите значение из списка.</div>")
        elif not кусок:
            пусто = ('<div class="empty"><b>Здесь пока пусто</b>'
                     "Под выбранные условия в снимке каталога не попала ни одна запись. "
                     "Снимите фильтр или вернитесь в полный каталог.</div>")
        else:
            пусто = ""
        тело = (f'<h1 class="lead">{h1}</h1>{подзаг}'
                f'<div class="tabs">{"".join(чипы)}</div>'
                f'<div class="tabs">{годы}</div>'
                f'<div class="tabs">{сорт_чипы}</div>'
                + (f'<div class="tabs">{жанры}</div>' if жанры else "")
                + (f'<div class="tabs">{страны}</div>' if страны else "")
                + (self.сетка(кусок) if кусок else пусто)
                + self.листалка(разд, выбрано, стр, всего))
        # Search/sort/arbitrary filter combos stay noindex via global meta.
        return self.оболочка(тело, f"{титул} — {self.имя}", разд + "/", актив=разд + "/",
                             описание=f"{титул} витрины {self.имя}: выборка из утверждённого снимка.")

    def поиск(self, зпр: dict) -> str:
        q = (зпр.get("q") or [""])[0]
        найдено = self.д.искать(q) if q.strip() else []
        if not q.strip():
            тело = ('<h1 class="lead">Поиск по каталогу</h1>'
                    '<div class="empty"><b>Введите название</b>'
                    "Поиск идёт по русскому и оригинальному названию. "
                    "Форма издания в запросе не мешает: «Бункер 1-3 сезон» найдёт «Бункер». "
                    '<a href="/catalog/">Открыть каталог целиком</a></div>')
        elif найдено:
            тело = (f'<h1 class="lead">Поиск: {html.escape(q)} — {len(найдено)} совпадений</h1>'
                    + self.сетка(найдено))
        else:
            тело = (f'<h1 class="lead">Поиск: {html.escape(q)}</h1>'
                    '<div class="empty"><b>Ничего не найдено</b>'
                    f"По запросу «{html.escape(q)}» в снимке каталога совпадений нет. "
                    "Проверьте написание. "
                    '<a href="/catalog/">Открыть каталог целиком</a></div>')
        return self.оболочка(
            тело, f"Поиск — {self.имя}", "/search/", актив="",
            описание=f"Поиск по каталогу витрины {self.имя}.",
        )

    def тайтл(self, запись: dict, деталь: dict) -> str:
        путь = f"/title/{запись['slug']}/"
        имя = запись["title"]
        сезоны = список_серий(деталь)
        сериал = bool(сезоны) or запись.get("kind") == "Сериал"
        раздел_вида = ("/catalog/?kind=Сериал", "Сериалы") if сериал else \
                      ("/catalog/?kind=Фильм", "Фильмы")
        звенья = [("/", self.имя), раздел_вида, ("", имя)]

        изо = заглушка_постера(запись, "c__none", "tw__img", 360, 540)

        описание = деталь.get("description") or деталь.get("short_description") or ""
        сюжет = (f'<div class="plot"><p>{html.escape(описание)}</p></div>' if описание else
                 '<div class="plot"><p class="none">Описание для этой записи источник пока '
                 "не передал. Всё, что о ней известно, собрано в таблице ниже.</p></div>")

        пары = факты(self, запись, деталь)
        таблица = ("".join(f"<div><dt>{html.escape(м)}</dt><dd>{з}</dd></div>" for м, з in пары))
        таблица = f'<dl class="facts">{таблица}</dl>' if пары else ""

        # Единый компонент оценок: подпись источника принадлежит источнику,
        # а не витрине. Прежняя строка подписывала любую оценку как
        # «источник: CDNVideoHub», хотя это поставщик каталога, а не тот, кто
        # выставил оценку.
        плитки = разметка_оценок(деталь, "rbs")

        сезон_старт, эпизод_старт = выбрать_доступную_серию(деталь) if сезоны else (1, None)
        код, внутри = разметка_плеера(self, запись, деталь, сезон_старт, эпизод_старт)
        плеер = (
            '<section class="pl" aria-labelledby="pl-h"><h2 class="vh" id="pl-h">Просмотр</h2>'
            '<div class="pl__bar"><span class="pl__tab" aria-current="true">Смотреть онлайн</span>'
            f'<span class="pl__note">{html.escape(_подпись_плеера(код))}</span></div>'
            f'<div class="pl__frame" data-player data-state="{код}">{внутри}</div>'
            f"{_скрипты_плеера(код)}</section>")

        текущий = (сезон_старт, эпизод_старт) if эпизод_старт is not None else None
        блок_серий = self._серии(запись, сезоны, текущий=текущий) if сериал else ""
        похожие = self.похожие(запись, деталь)
        блок_похожих = (f'<section class="sec"><h2>Похожее</h2>'
                        f'{self.сетка(похожие, "rel")}</section>' if похожие else "")

        заявка = (f'<p class="claim">Смотреть {html.escape(имя)} онлайн'
                  f'{" — все серии" if сериал else ""}</p>')

        тело = (f'<div class="tw"><div class="tw__ps">{изо}</div><div>'
                f"<h1>{html.escape(имя)}</h1>{сюжет}{таблица}{плитки}</div></div>"
                f"{заявка}{плеер}{блок_серий}{блок_похожих}")
        разметка = self.schema_тайтла(запись, деталь, путь)
        краткое = (описание[:180] if описание else
                   f"{имя}: {запись.get('kind') or ''} {запись.get('year') or ''}".strip())
        return self.оболочка(
            тело, f"{имя} — смотреть онлайн — {self.имя}", путь,
            описание=краткое, разметка=разметка, крошки=self.крошки(звенья),
            og=self.карточка_графа(
                тип="video.tv_show" if сериал else "video.movie",
                титул=имя, описание=краткое, путь=путь,
                изображение=запись.get("poster") or ""))

    def _серии(self, запись: dict, сезоны: list, текущий=None) -> str:
        if not сезоны:
            return ('<section class="sec"><h2>Серии</h2>'
                    '<p class="plot"><span class="none">Состав сезонов источник по этой '
                    "записи пока не передал. Как только он появится, список серий "
                    "встанет сюда.</span></p></section>")
        блоки = []
        for сезон in сезоны:
            ссылки = []
            for н in сезон["номера"]:
                доступна = н <= сезон["avail"]
                текущая = (текущий == (сезон["n"], н))
                атрибуты = ' aria-current="page"' if текущая else (
                    "" if доступна else ' data-off title="Серия заявлена, дорожки ещё нет"')
                ссылки.append(
                    f'<a href="{self.адрес_эпизода(запись["slug"], сезон["n"], н)}"{атрибуты}>{н}</a>')
            хвост = ("" if сезон["avail"] >= сезон["eps"]
                     else f", доступно {сезон['avail']}")
            блоки.append(
                f'<div class="sea"><div class="sea__h">'
                f'<h3>{сезон["n"]} сезон</h3><span>{сезон["eps"]} серий{хвост}</span></div>'
                f'<div class="eps">{"".join(ссылки)}</div></div>')
        return f'<section class="sec"><h2>Серии</h2>{_склеить(блоки)}</section>'

    def сезон(self, запись: dict, деталь: dict, номер: int) -> str:
        имя = запись["title"]
        путь = self.адрес_сезона(запись["slug"], номер)
        только = [с for с in список_серий(деталь) if с["n"] == номер]
        заголовок = f"{имя} — {номер} сезон"
        звенья = [("/", self.имя), ("/catalog/?kind=Сериал", "Сериалы"),
                  (f"/title/{запись['slug']}/", имя), ("", f"{номер} сезон")]
        серий = только[0]["eps"] if только else 0
        тело = ('<div class="tw" style="grid-template-columns:1fr"><div>'
                f"<h1>{html.escape(заголовок)}</h1>"
                f'<div class="plot"><p>В сезоне {серий} серий. Любая из них открывается '
                f'отдельным адресом. <a href="/title/{запись["slug"]}/">Вернуться к '
                "описанию</a>.</p></div></div></div>" + self._серии(запись, только))
        return self.оболочка(
            тело, f"{заголовок} — {self.имя}", путь,
            описание=f"{заголовок}: список серий на витрине {self.имя}.",
            разметка=self.schema_крошек(звенья), крошки=self.крошки(звенья),
            og=self.карточка_графа(
                тип="video.tv_show", титул=заголовок,
                описание=f"{заголовок}: список серий на витрине {self.имя}.",
                путь=путь, изображение=запись.get("poster") or ""))

    def серия(self, запись: dict, деталь: dict, сезон: int, эпизод: int) -> str:
        имя = запись["title"]
        путь = self.адрес_эпизода(запись["slug"], сезон, эпизод)
        заголовок = f"{имя} — {сезон} сезон, {эпизод} серия"
        звенья = [("/", self.имя), ("/catalog/?kind=Сериал", "Сериалы"),
                  (f"/title/{запись['slug']}/", имя), ("", f"{сезон} сезон, {эпизод} серия")]
        код, внутри = разметка_плеера(self, запись, деталь, сезон, эпизод)
        плеер = (
            '<section class="pl" aria-labelledby="pl-h"><h2 class="vh" id="pl-h">Просмотр серии</h2>'
            '<div class="pl__bar"><span class="pl__tab" aria-current="true">Смотреть онлайн</span>'
            f'<span class="pl__note">{html.escape(_подпись_плеера(код))}</span></div>'
            f'<div class="pl__frame" data-player data-state="{код}">{внутри}</div>'
            f"{_скрипты_плеера(код)}</section>")
        пред, след = границы_серии(деталь, сезон, эпизод)
        переход = (
            '<nav class="epnav" aria-label="Соседние серии">'
            + (f'<a href="{self.адрес_эпизода(запись["slug"], *пред)}" rel="prev">← '
               f"{пред[0]} сезон, {пред[1]} серия</a>" if пред else
               "<span>Это первая серия</span>")
            + (f'<a href="{self.адрес_эпизода(запись["slug"], *след)}" rel="next">'
               f"{след[0]} сезон, {след[1]} серия →</a>" if след else
               "<span>Это последняя серия</span>")
            + "</nav>")
        сезоны = список_серий(деталь)
        тело = (f'<div class="tw" style="grid-template-columns:1fr"><div>'
                f"<h1>{html.escape(заголовок)}</h1>"
                f'<div class="plot"><p>Серия {эпизод} из {sum(с["eps"] for с in сезоны) or "?"} '
                f'по произведению «{html.escape(имя)}». '
                f'<a href="/title/{запись["slug"]}/">Вернуться к описанию</a>.</p></div>'
                f"</div></div>{плеер}{переход}"
                + self._серии(запись, сезоны, текущий=(сезон, эпизод)))
        разметка = self.schema_эпизода(запись, деталь, сезон, эпизод, путь)
        return self.оболочка(
            тело, f"{заголовок} — {self.имя}", путь,
            описание=f"{заголовок}: смотреть онлайн на витрине {self.имя}.",
            разметка=разметка, крошки=self.крошки(звенья),
            og=self.карточка_графа(
                тип="video.episode", титул=заголовок,
                описание=f"{заголовок}: смотреть онлайн на витрине {self.имя}.",
                путь=путь, изображение=запись.get("poster") or ""))

    def не_найдено(self, путь: str) -> str:
        тело = ('<div class="nf"><b>404</b><h1>Такой страницы на витрине нет</h1>'
                f"<p>Адрес <code>{html.escape(путь[:120])}</code> не соответствует ни одной "
                "записи каталога. Возможно, ссылка устарела или в ней опечатка.</p>"
                '<a href="/catalog/">Открыть каталог</a></div>')
        return self.оболочка(тело, f"Страница не найдена — {self.имя}", "", код=404)


# ----------------------------- Zona -----------------------------------


class ВидЗона(Вид):
    """Боковая колонка, шрифт с засечками, карточки-строки, баннер на тайтле.

    Совпадений с Lords здесь нет ни в композиции, ни в типографике, ни в
    геометрии карточки, ни в раскладке страницы произведения. Общими остались
    только данные и механика маршрутов — то есть ровно то, что у семейств и
    обязано быть общим.
    """

    кл_состояния = "zpl__s"

    def оболочка(self, тело: str, титул: str, путь: str, *, актив: str = "",
                 описание: str = "", разметка: str = "", код: int = 200,
                 сверху: str = "", крошки: str = "", og: dict | None = None) -> str:
        нав = "".join(
            f'<a href="{закодировать_запрос(u)}"{ТЕКУЩАЯ_СТРАНИЦА if u == актив else ""}>{html.escape(t)}</a>'
            for u, t in self.се["нав"])
        жанры = "".join(
            f'<a href="/catalog/?genre={html.escape(код_жанра)}">{html.escape(имя)}</a>'
            for код_жанра, имя in self.индекс["genre_names"][:14])
        схемы = "".join(f'<script type="application/ld+json">{р}</script>'
                        for р in ([разметка] if разметка else []))
        описание_мета = (f'<meta name="description" content="{html.escape(описание)}">'
                         if описание else "")
        канон = (f'<link rel="canonical" href="{html.escape(self.канон(путь))}">'
                 if путь and код == 200 else "")
        # Витрина на 1.1.0 отдаёт ПРЕЖНИЙ каркас: артефакт общий, и выкладка
        # ради соседнего семейства не имеет права сменить ей оформление.
        if not ОФОРМЛЕНИЕ_ПЕРЕРАБОТАННОЕ:
            return f"""<!doctype html><html lang="ru" data-template-version="{ВЕРСИЯ}" data-template-family="{СЕМЕЙСТВО}" data-build-id="{СБОРКА}" data-design="zona-rail">
    <head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>{html.escape(титул)}</title>{описание_мета}{канон}
    <meta name="robots" content="noindex, nofollow">
    {_открытый_граф(og or {})}
    <link rel="icon" href="/favicon.svg" type="image/svg+xml">
    {_мета_версии()}
    <style>{self.се["стиль"]()}</style><script>{СКРИПТ_ПОСТЕРОВ}</script></head>
    <body><a class="skip" href="#main">Перейти к содержимому</a>
    <div class="zs">
    <aside class="zrail">
    <a class="zrail__logo" href="/">{html.escape(self.имя)}</a>
    <p class="zrail__sub">Кинопортал · тестовая витрина</p>
    <p class="zrail__t">Разделы</p>
    <nav class="zrail__n" aria-label="Разделы">{нав}</nav>
    <p class="zrail__t">Жанры</p>
    <div class="zrail__g">{жанры}</div>
    </aside>
    <div class="zmain">
    <div class="ztop"><div class="ztop__a">
    <form class="ztop__s" action="/search/" method="get" role="search">
    <label class="vh" for="q">Поиск по каталогу</label>
    <input id="q" name="q" placeholder="{html.escape(self.се["поиск"])}">
    <button type="submit">Найти</button></form>
    </div><div class="ztop__b">{_склеить([сверху])}</div></div>{крошки}
    <main id="main">{тело}</main>
    <footer class="zft">
    <span class="zvb">Zona {ВЕРСИЯ} · {МАНИФЕСТ["source_commit"][:8]}</span>
    </footer></div></div>{схемы}</body></html>"""
        return f"""<!doctype html><html lang="ru" data-template-version="{ВЕРСИЯ}" data-template-family="{СЕМЕЙСТВО}" data-build-id="{СБОРКА}" data-design="zona-top">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(титул)}</title>{описание_мета}{канон}
<meta name="robots" content="noindex, nofollow">
{_открытый_граф(og or {})}
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
{_мета_версии()}
<style>{self.се["стиль"]()}</style><script>{СКРИПТ_ПОСТЕРОВ}
{СКРИПТ_ЛЕНТ}
{СКРИПТ_ЛОРДС_ШАПКА}</script></head>
<body><a class="skip" href="#main">Перейти к содержимому</a>
<div class="zs">
<header class="zhd">
<div class="zhd__in">
<a class="zhd__logo" href="/">{html.escape(self.имя)}</a>
<button class="zhd__menu" type="button" data-nav-toggle aria-controls="zhd-nav"
 aria-expanded="false" aria-label="Меню разделов">&#9776;</button>
<nav id="zhd-nav" class="zhd__n" aria-label="Разделы">{нав}</nav>
<form class="zhd__s" action="/search/" method="get" role="search">
<label class="vh" for="q">Поиск по каталогу</label>
<input id="q" name="q" placeholder="{html.escape(self.се["поиск"])}">
<button type="submit">Найти</button></form>
</div>
</header>
<div class="zmain">
<div class="zwrap">{_склеить([f'<div class="ztop"><div class="ztop__b">{сверху}</div></div>' if сверху else ""])}{крошки}
<main id="main">{тело}</main>
{self._подвал_зона()}
</div></div></div>{схемы}</body></html>"""

    def _подвал_зона(self) -> str:
        """Footer: brand, real sections, genre links, compact Zona marker."""
        жанры = "".join(
            f'<a href="/catalog/?genre={html.escape(код)}">{html.escape(имя)}</a>'
            for код, имя in (self.индекс.get("genre_names") or [])[:8])
        source = (МАНИФЕСТ.get("source_commit") or "")[:8]
        return (
            '<footer class="zft">'
            '<div class="zft__cols">'
            f'<div class="zft__col"><b>{html.escape(self.имя)}</b>'
            '<a href="/">Обзор</a><a href="/movies/">Кино</a>'
            '<a href="/series/">Сериалы</a><a href="/animation/">Анимация</a>'
            '<a href="/new/">Что нового</a><a href="/collections/">Подборки</a>'
            '<a href="/catalog/">Весь каталог</a></div>'
            f'<div class="zft__col"><b>Жанры</b>{жанры or "<span>—</span>"}</div>'
            '<div class="zft__col"><b>Каталог</b>'
            '<a href="/search/">Поиск</a></div></div>'
            f'<div class="zft__bar"><span class="zvb">Zona {html.escape(ВЕРСИЯ)} · '
            f"{html.escape(source)}</span></div>"
            "</footer>")

    # --- составные части ---------------------------------------------
    def плитка(self, запись: dict) -> str:
        деталь = self.деталь(запись["slug"])
        изо = заглушка_постера(запись, "zt__none", "zt__img")
        мета = " · ".join(str(ч) for ч in (запись.get("kind"), запись.get("year")) if ч)
        кп = _число(деталь.get("kinopoisk_rating"))
        им = _число(деталь.get("imdb_rating"))
        части = []
        if кп:
            части.append(f"<span>КП <b>{кп}</b></span>")
        if им:
            части.append(f"<span>IMDb <i>{им}</i></span>")
        if not части:
            части.append("<span><em>нет оценки</em></span>")
        оценка = f'<span class="zt__r">{"".join(части)}</span>'
        заголовок = запись["title"] or ""
        return (f'<a class="zt" href="{запись["url"]}" title="{html.escape(заголовок)}">'
                f'<span class="zt__p">{изо}</span>'
                f'<span class="zt__b"><span class="zt__t">{html.escape(заголовок)}</span>'
                f'<span class="zt__m">{html.escape(мета)}</span></span>{оценка}</a>')

    def строка(self, запись: dict) -> str:
        деталь = self.деталь(запись["slug"])
        изо = заглушка_постера(запись, "zr__none", "zr__img", 184, 276)
        части = [запись.get("kind"), запись.get("year")]
        части += (деталь.get("countries") or [])[:1]
        части += (деталь.get("genres") or [])[:2]
        мета = " · ".join(str(ч) for ч in части if ч)
        описание = (деталь.get("short_description") or деталь.get("description") or "")
        кп = _число(деталь.get("kinopoisk_rating"))
        им = _число(деталь.get("imdb_rating"))
        оценки_html = ""
        if кп or им:
            оценки_html = ('<span class="zr__r">'
                           + (f"<span>Кинопоиск <b>{кп}</b></span>" if кп else "")
                           + (f"<span>IMDb <i>{им}</i></span>" if им else "")
                           + "</span>")
        текст = (f'<span class="zr__d">{html.escape(описание)}</span>' if описание else "")
        return (f'<a class="zr" href="{запись["url"]}">'
                f'<span class="zr__p">{изо}</span><span>'
                f'<span class="zr__t">{html.escape(запись["title"])}</span>'
                f'<span class="zr__m">{html.escape(мета)}</span>{текст}{оценки_html}'
                "</span></a>")

    def лента(self, набор) -> str:
        return '<div class="zl">' + "".join(self.строка(з) for з in набор) + "</div>"

    def карусель(self, ключ: str, набор) -> str:
        """Горизонтальная лента: мышь, клавиатура и свайп.

        Прокрутка нативная, поэтому свайп и колесо работают без единой строки
        скрипта, а клавиатура — потому что область получает фокус. Кнопки
        добавляют мышиный способ и ничего не заменяют: при выключенном
        JavaScript лента остаётся прокручиваемой.
        """
        плитки = "".join(self.плитка(з) for з in набор)
        ид = f"rl-{ключ}"
        return (f'<div class="zrl">'
                f'<button class="zrl__btn zrl__btn--p" type="button" data-rl="prev"'
                f' aria-controls="{ид}" aria-label="Пролистать назад">&#8249;</button>'
                f'<div class="zrl__vp" id="{ид}" tabindex="0" role="group"'
                f' aria-label="Лента произведений">'
                f'<div class="zrl__track">{плитки}</div></div>'
                f'<button class="zrl__btn zrl__btn--n" type="button" data-rl="next"'
                f' aria-controls="{ид}" aria-label="Пролистать вперёд">&#8250;</button>'
                f'</div>')

    def секция(self, ключ: str, титул: str, ссылка: str, набор, пусто: str) -> str:
        """Секция главной. Пустой набор полностью скрывается.

        Эталон w140 прячет отсутствующие блоки. Пустой контейнер или текст
        «в снимке нет…» на главной неотличимы от сломанной полки и запрещены.
        """
        if not набор:
            return ""
        ссылка_html = (f'<a href="{закодировать_запрос(ссылка)}">Весь раздел</a>'
                       if ссылка else "")
        шапка = (f'<div class="zsec__h"><h2>{html.escape(титул)}</h2>{ссылка_html}</div>')
        return f'<section class="zsec">{шапка}{self.карусель(ключ, набор)}</section>'

    def плитки(self, набор) -> str:
        return '<div class="zg">' + "".join(self.плитка(з) for з in набор) + "</div>"

    def листалка(self, разд: str, выбрано: dict, стр: int, всего: int) -> str:
        пункты = страницы(стр, всего)
        if not пункты:
            return ""
        куски = []
        for н in пункты:
            if н is None:
                куски.append("<em>…</em>")
            elif н == стр:
                куски.append(f'<span aria-current="page">{н}</span>')
            else:
                куски.append(f'<a href="{разд}/{запрос_строкой(выбрано, page=(н if н > 1 else None))}">{н}</a>')
        return f'<nav class="zpg" aria-label="Страницы">{"".join(куски)}</nav>'

    def крошки(self, звенья) -> str:
        куски = []
        for адрес, имя in звенья:
            куски.append(f'<a href="{адрес}">{html.escape(имя)}</a>' if адрес
                         else html.escape(имя))
        return f'<nav class="zcr" aria-label="Хлебные крошки">{" / ".join(куски)}</nav>'

    # --- страницы -----------------------------------------------------
    def главная(self) -> str:
        """Пять горизонтальных лент, и ни одна не повторяет выборку другой.

        Повтор одной выборки под тремя заголовками — дефект, который витрина
        показывает зрителю как три разных раздела. Поэтому здесь ведётся один
        набор занятых slug: запись, попавшая в ленту выше, ниже не повторяется.
        Ленту, для которой источник не передал данных, заменяет названная
        причина, а не молчание и не чужая выборка.
        """
        if not ОФОРМЛЕНИЕ_ПЕРЕРАБОТАННОЕ:
            свежие = новинки_с_источником(self.д, self.п, 8)
            куски = [f'<h1 class="zh">{html.escape(self.се["лид"])}</h1>'
                     f'<p class="zsub">В снимке каталога {len(self.д.items)} записей. '
                     f"Ниже — то, что появилось последним.</p>"
                     + self.плитки(свежие)]
            for титул, ссылка, вид in self.се["полосы"]:
                набор = [з for з in self.д.items if з.get("kind") == вид][:6]
                if набор:
                    куски.append(f'<h2 class="zh zh--sm">{html.escape(титул)}</h2>'
                                 f'<p class="zsub"><a href="{ссылка}">Открыть весь раздел</a></p>'
                                 + self.лента(набор))
            return self.оболочка(
                f'<div class="zwrap">{_склеить(куски)}</div>',
                f"{self.имя} — кинопортал", "/", актив="/",
                описание=f"{self.имя}: фильмы, сериалы и анимация.",
                сверху="<span>Обзор каталога</span>")

        занято: set = set()

        def оценка(з: dict) -> float:
            д = self.деталь(з["slug"])
            значения = [д.get("kinopoisk_rating"), д.get("imdb_rating")]
            числа = [float(v) for v in значения
                     if isinstance(v, (int, float)) or
                     (isinstance(v, str) and v.replace(".", "", 1).isdigit())]
            return max(числа) if числа else 0.0

        def свежесть(з: dict) -> str:
            return з.get("published_at") or ""

        #: Пул для «популярного» ограничен намеренно: сортировать 50 тысяч
        #: записей по оценке на каждый запрос незачем, а «популярное среди
        #: недавнего» — честная формулировка того, что здесь считается.
        ПУЛ = 400

        def выбрать(вид: str | None, ключ, сколько: int = 12,
                    пул: int | None = None, условие=None) -> list:
            подходящие = [з for з in self.д.items
                          if (вид is None or з.get("kind") == вид)
                          and (условие is None or условие(з))]
            if пул:
                подходящие = sorted(подходящие, key=свежесть, reverse=True)[:пул]
            отобрано = []
            for з in sorted(подходящие, key=ключ, reverse=True):
                if з["slug"] in занято:
                    continue
                занято.add(з["slug"])
                отобрано.append(з)
                if len(отобрано) >= сколько:
                    break
            return отобрано

        def есть_серии(з: dict) -> bool:
            return bool(self.деталь(з["slug"]).get("seasons"))

        def есть_источник(з: dict) -> bool:
            return состояние_плеера(self.деталь(з["slug"]))[0] == "playable"

        ленты = [
            ("pop-films", "Популярные новинки фильмов", "/movies/",
             выбрать("Фильм", оценка, пул=ПУЛ),
             ""),
            ("pop-series", "Популярные сериалы", "/series/",
             выбрать("Сериал", оценка, пул=ПУЛ),
             ""),
            ("new-films", "Добавленные недавно фильмы", "/movies/",
             выбрать("Фильм", свежесть, условие=есть_источник),
             ""),
            ("new-eps", "Новые серии", "/series/",
             выбрать("Сериал", свежесть,
                     условие=lambda з: есть_серии(з) and есть_источник(з)),
             ""),
            ("trailers", "Новые трейлеры", "",
             [],
             ""),
            ("pop-anim", "Популярная анимация", "/animation/",
             выбрать("Мультфильм", оценка, пул=ПУЛ),
             ""),
            ("new-all", "Недавно в каталоге", "/new/",
             выбрать(None, свежесть, условие=есть_источник, сколько=18),
             ""),
        ]
        жанры_лента = []
        for код, имя in self.индекс["genre_names"][:6]:
            члена = set(self.индекс["genre"].get(код) or [])
            карточки = [з for з in self.д.items
                        if з["slug"] in члена and з["slug"] not in занято][:12]
            for з in карточки:
                занято.add(з["slug"])
            if карточки:
                жанры_лента.append(
                    (f"genre-{код}", имя, f"/catalog/?genre={код}", карточки, ""))
        коллекции_html = ""
        снимок = Снимок.получить(self.д, self.п)
        if КОЛЛЕКЦИИ is not None and снимок is not None:
            кол_карточки = []
            for спец in КОЛЛЕКЦИИ.спецификации(СЕМЕЙСТВО)[:4]:
                if not спец.доступна:
                    continue
                данные = КОЛЛЕКЦИИ.разрешить(спец.collection_key, снимок, СЕМЕЙСТВО,
                                             предел=1)
                if данные is None or not данные.items:
                    continue
                кол_карточки.append(
                    f'<a class="zhub__c" data-card-variant="collection-card" href="{html.escape(спец.canonical_path)}">'
                    f'<span class="zhub__t">{html.escape(данные.title)}</span>'
                    f'<span class="zhub__m">{данные.total} записей</span></a>')
            if кол_карточки:
                коллекции_html = (
                    '<section class="zsec"><div class="zsec__h">'
                    "<h2>Подборки</h2>"
                    '<a href="/collections/">Весь раздел</a></div>'
                    f'<div class="zhub zhub--home">{"".join(кол_карточки)}</div>'
                    "</section>")
        жанр_навигация = "".join(
            f'<a href="/catalog/{запрос_строкой({"genre": код})}">{html.escape(имя)}</a>'
            for код, имя in ZONA_GENRE_NAV)
        блок_жанров = (
            f'<section class="zgenres" aria-labelledby="zgenres-h">'
            f'<h2 class="zgenres__h" id="zgenres-h">Смотреть по жанрам</h2>'
            f'<nav class="zgenres__nav" aria-label="Смотреть по жанрам">{жанр_навигация}</nav>'
            f'</section>') if жанр_навигация else ""
        куски = [f'<h1 class="zh">{html.escape(self.се["лид"])}</h1>'
                 '<p class="zsub">Фильмы, сериалы и анимация из каталога витрины. '
                 '<a href="/catalog/">Открыть весь каталог</a> · '
                 '<a href="/movies/">Кино</a> · '
                 '<a href="/series/">Сериалы</a> · '
                 '<a href="/new/">Что нового</a></p>']
        остальные = list(ленты)
        первая = остальные.pop(0) if остальные else None
        if первая:
            куски.append(self.секция(*первая))
        if блок_жанров:
            куски.append(блок_жанров)
        куски += [self.секция(*л) for л in остальные]
        куски += [self.секция(*л) for л in жанры_лента]
        if коллекции_html:
            куски.append(коллекции_html)
        куски.append(
            '<section class="zsec zsec--seo"><h2 class="zh zh--sm">Каталог Zona</h2>'
            f'<p class="zsub">{html.escape(self.имя)} собирает кино и сериалы '
            "с фильтрами по виду, жанру, году и стране. Состав страниц берётся "
            "только из утверждённого снимка каталога — без выдуманных карточек "
            "и рейтингов.</p></section>")
        return self.оболочка(
            _склеить(куски),
            f"{self.имя} — кинопортал", "/", актив="/",
            описание=f"{self.имя}: фильмы, сериалы и анимация.",
            сверху="")

    def коллекция(self, данные) -> str:
        """Полная страница коллекции в разметке своего семейства.

        База собирает её классами `grid`/`sec`/`card` — это оформление Lords.
        У Zona и Animedia таких правил нет, поэтому сетка разворачивалась в
        одну колонку на любой ширине: шестьдесят карточек давали страницу под
        сорок тысяч пикселей. Состав и порядок при этом брались из контракта и
        были верны — ломалась только раскладка. Поэтому здесь меняется разметка
        и ничего больше: те же данные, тот же порядок, та же пагинация.
        """
        на_странице = 60
        всего_страниц = max(1, (данные.total + на_странице - 1) // на_странице)
        листалка = ""
        if всего_страниц > 1:
            пункты = "".join(
                (f'<span aria-current="page">{n}</span>' if n == данные.page else
                 f'<a href="{html.escape(данные.canonical_path)}'
                 f'{"" if n == 1 else f"?page={n}"}">{n}</a>')
                for n in range(max(1, данные.page - 3),
                               min(всего_страниц, данные.page + 3) + 1))
            листалка = f'<nav class="zpg" aria-label="Страницы">{пункты}</nav>'
        тело = (f'<div class="zwrap"><h1 class="zh">{html.escape(данные.title)}</h1>'
                f'<p class="zsub">{html.escape(данные.description)} · '
                f'{данные.total} записей · страница {данные.page} из {всего_страниц}</p>'
                + (self.плитки([к.raw for к in данные.items]) if данные.items else
                   f'<div class="zempty"><b>{html.escape(данные.title)}: пока пусто</b>'
                   "<p>В текущем снимке под эту коллекцию не попала ни одна "
                   "запись.</p></div>")
                + листалка + "</div>")
        return self.оболочка(тело, f"{данные.title} — {self.имя}",
                             данные.canonical_path, актив="/collections/",
                             описание=данные.description)

    def хаб_коллекций(self) -> str:
        """Перечень коллекций со ссылками на их собственные страницы.

        До этого `/collections/` отдавал тот же каталог, что и `/catalog/`, —
        то есть обещал подборки, а показывал общий список. Здесь страница
        собирается из тех же спецификаций, что и ленты главной: заголовок,
        описание, размер и адрес берутся из контракта, второго перечня нет.

        Недоступные коллекции не показываются: контракт объявляет их с
        политикой «скрыть», и рисовать пустую карточку значило бы обещать
        раздел, которого нет.
        """
        снимок = Снимок.получить(self.д, self.п)
        if КОЛЛЕКЦИИ is None or снимок is None:
            return ('<div class="zempty"><b>Подборки недоступны</b>'
                    "<p>Контракт коллекций витрине не передан.</p></div>")
        карточки = []
        занятые_постеры: set[str] = set()
        сигнатуры: list[tuple[str, ...]] = []
        for спец in КОЛЛЕКЦИИ.спецификации(СЕМЕЙСТВО):
            if not спец.доступна:
                continue
            коллекция = КОЛЛЕКЦИИ.разрешить(спец.collection_key, снимок, СЕМЕЙСТВО,
                                            предел=48)
            if коллекция is None or not коллекция.items:
                continue
            выбранные = []
            for к in коллекция.items:
                постер = к.poster or ""
                if not постер:
                    continue
                if постер in занятые_постеры and len(выбранные) < 4:
                    # Prefer unique collage posters across hub tiles.
                    continue
                выбранные.append(к)
                if len(выбранные) >= 4:
                    break
            if len(выбранные) < 4:
                for к in коллекция.items:
                    if к in выбранные or not к.poster:
                        continue
                    выбранные.append(к)
                    if len(выбранные) >= 4:
                        break
            sig = tuple(к.poster for к in выбранные[:4])
            if sig and sig in сигнатуры:
                # Exact duplicate collage — skip tile; full page still exists.
                continue
            if sig:
                сигнатуры.append(sig)
            for к in выбранные[:4]:
                if к.poster:
                    занятые_постеры.add(к.poster)
            обложки = "".join(
                f'<span class="zhub__p">'
                f'<img class="zhub__img" src="{html.escape(_адрес_постера(к.poster) or "")}"'
                f' alt="" loading="lazy" width="120" height="180"></span>'
                for к in выбранные[:4] if к.poster)
            карточки.append(
                f'<a class="zhub__c" data-card-variant="collection-card" href="{html.escape(спец.canonical_path)}">'
                f'<span class="zhub__g">{обложки}</span>'
                f'<span class="zhub__t">{html.escape(коллекция.title)}</span>'
                f'<span class="zhub__m">{коллекция.total}</span>'
                f'<span class="zhub__d">{html.escape(коллекция.description)}</span>'
                f'</a>')
        if not карточки:
            return ('<div class="zempty"><b>Подборок пока нет</b>'
                    "<p>Ни одна коллекция контура не набрала записей в текущем снимке. "
                    "Наполнять их похожими тайтлами нельзя: подборка без источника — "
                    "это выдумка.</p></div>")
        return f'<div class="zhub">{"".join(карточки)}</div>'

    def список(self, разд: str, зпр: dict) -> str:
        имена = {
            "/catalog": "Весь каталог",
            "/new": "Что нового",
            "/collections": "Подборки",
            "/movies": "Кино",
            "/series": "Сериалы",
            "/animation": "Анимация",
        }
        титул = имена.get(разд, "Каталог")
        if разд == "/collections":
            тело = (f'<div class="zwrap"><h1 class="zh">{html.escape(титул)}</h1>'
                    f'<p class="zsub">Тематические подборки по данным текущего снимка.</p>'
                    + self.хаб_коллекций() + "</div>")
            return self.оболочка(тело, f"{титул} — {self.имя}", "/collections/",
                                 актив="/collections/",
                                 описание=f"Подборки витрины {self.имя}.")
        набор, выбрано = отбор(self.д, self.индекс, зпр, разд)
        стр = max(1, int((зпр.get("page") or ["1"])[0] or 1))
        всего = max(1, (len(набор) + НА_СТРАНИЦЕ_1_1 - 1) // НА_СТРАНИЦЕ_1_1)
        стр = min(стр, всего)
        кусок = набор[(стр - 1) * НА_СТРАНИЦЕ_1_1: стр * НА_СТРАНИЦЕ_1_1]
        жанр_код = выбрано.get("genre")
        жанр_имя = None
        if жанр_код:
            for код, имя in (self.индекс.get("genre_names") or []):
                if код == жанр_код:
                    жанр_имя = имя
                    break
            if not жанр_имя:
                for код, имя in ZONA_GENRE_NAV:
                    if код == жанр_код:
                        жанр_имя = имя
                        break
            if жанр_имя:
                титул = жанр_имя
        фильтры = "".join(
            f'<a href="{разд}/{запрос_строкой(выбрано, kind=к, page=None)}"'
            f'{ТЕКУЩАЯ_СТРАНИЦА if выбрано["kind"] == к else ""}>{html.escape(к)}</a>'
            for к in self.д.kinds)
        if any(v for k, v in выбрано.items() if k != "_unknown" and v):
            фильтры += f'<a href="{разд}/">Сбросить</a>'
        годы = "".join(
            f'<a href="{разд}/{запрос_строкой(выбрано, year=г, page=None)}"'
            f'{ТЕКУЩАЯ_СТРАНИЦА if str(выбрано.get("year")) == str(г) else ""}>{г}</a>'
            for г in (self.д.years or [])[:12])
        if годы:
            фильтры += f'<span class="zfilt__y">{годы}</span>'
        жанр_навигация = "".join(
            f'<a href="/catalog/{запрос_строкой({"genre": код})}"'
            f'{ТЕКУЩИЙ_ПУНКТ if жанр_код == код else ""}>{html.escape(имя)}</a>'
            for код, имя in ZONA_GENRE_NAV)
        блок_жанров = (
            f'<nav class="zgenres__nav" aria-label="Смотреть по жанрам">'
            f"{жанр_навигация}</nav>") if разд == "/catalog" else ""
        канон = разд + "/" + (запрос_строкой(выбрано, page=None) if жанр_код else "")
        тело = (f'<div class="zwrap"><h1 class="zh">{html.escape(титул)}</h1>'
                f'<p class="zsub">Найдено {len(набор)} · страница {стр} из {всего}</p>'
                + блок_жанров
                + (self.плитки(кусок) if кусок else
                   '<div class="zempty"><b>Ничего не подошло</b>'
                   "<p>Под выбранные условия не попала ни одна запись.</p></div>")
                + self.листалка(разд, выбрано, стр, всего) + "</div>")
        актив = разд + "/"
        if разд == "/catalog" and выбрано.get("kind") == "Фильм":
            актив = "/movies/"
        elif разд == "/catalog" and выбрано.get("kind") == "Сериал":
            актив = "/series/"
        elif разд == "/catalog" and выбрано.get("kind") == "Мультфильм":
            актив = "/animation/"
        return self.оболочка(тело, f"{титул} — {self.имя}", канон or (разд + "/"),
                             актив=актив,
                             описание=f"{титул} на витрине {self.имя}.",
                             сверху=фильтры)

    def поиск(self, зпр: dict) -> str:
        q = (зпр.get("q") or [""])[0]
        найдено = self.д.искать(q) if q.strip() else []
        if not q.strip():
            тело = ('<h1 class="zh">Поиск</h1><p class="zsub">Введите название — '
                    "поиск идёт по русскому и оригинальному написанию.</p>"
                    '<div class="zempty"><b>Запрос пуст</b>'
                    "<p>Наберите название в строке сверху. Слова «сезон» и «серия» "
                    "в запросе поиску не мешают. "
                    '<a href="/catalog/">Открыть каталог целиком</a></p></div>')
        elif найдено:
            тело = (f'<h1 class="zh">«{html.escape(q)}»</h1>'
                    f'<p class="zsub">Совпадений: {len(найдено)}</p>' + self.плитки(найдено))
        else:
            тело = (f'<h1 class="zh">«{html.escape(q)}»</h1>'
                    '<div class="zempty"><b>Совпадений нет</b>'
                    f"<p>По запросу «{html.escape(q)}» ничего не нашлось. "
                    "Проверьте написание. "
                    '<a href="/catalog/">Открыть весь каталог</a></p></div>')
        return self.оболочка(f'<div class="zwrap">{тело}</div>',
                             f"Поиск — {self.имя}", "/search/", актив="")

    def тайтл(self, запись: dict, деталь: dict) -> str:
        путь = f"/title/{запись['slug']}/"
        имя = запись["title"]
        сезоны = список_серий(деталь)
        сериал = bool(сезоны) or запись.get("kind") == "Сериал"
        звенья = [("/", self.имя),
                  ("/series/", "Сериалы") if сериал else ("/movies/", "Кино"),
                  ("", имя)]
        изо = заглушка_постера(запись, "zt__none", "zhead__img", 372, 558)
        описание = деталь.get("description") or деталь.get("short_description") or ""
        краткий = описание.strip()
        if len(краткий) > 420:
            краткий = краткий[:417].rstrip() + "…"
        описание_html = (f'<p class="ztitle__desc" id="title-desc">{html.escape(краткий)}</p>'
                         + ('<button type="button" class="ztitle__more" '
                            'onclick="this.previousElementSibling.classList.add(\'is-open\');'
                            'this.hidden=true">Развернуть</button>'
                            if len(описание.strip()) > 280 else "")
                         if краткий else "")
        оценки = оценки_по_источникам(деталь)
        primary = оценки[0] if оценки else None
        score_html = ""
        if primary:
            score_html = (
                f'<div class="ztitle__score"><b>{html.escape(primary["значение"])}</b>'
                f'<span>{html.escape(primary["подпись"])}'
                + (f' · {primary["голоса"]} оценок' if primary.get("голоса") else "")
                + "</span></div>")
        оценки_html = разметка_оценок(деталь, "rbs", пусто=False)
        orig = html.escape(str(деталь.get("original_name") or деталь.get("original_title") or ""))
        orig_html = f'<p class="ztitle__o">{orig}</p>' if orig else ""
        pills = ""
        жанры = деталь.get("genres") or []
        if жанры:
            pills = ('<div class="ztitle__pills">' + "".join(
                f"<span>{html.escape(str(г))}</span>" for г in жанры[:8]) + "</div>")
        meta_bits = [str(x) for x in (
            запись.get("year"), запись.get("kind") or деталь.get("type"),
            ", ".join(деталь.get("countries") or [])[:40] or None,
        ) if x]
        meta_html = (f'<p class="ztitle__meta">{html.escape(" · ".join(meta_bits))}</p>'
                     if meta_bits else "")
        # Rail metadata only — no year/type repeat in the hero strip.
        rail_keys = {
            "Оригинальное название", "Год", "Тип", "Страна", "Жанр",
            "Время", "Дата выхода", "Серии",
        }
        пары = [(м, з) for м, з in факты(self, запись, деталь) if м in rail_keys]
        for метка, ключ in (("Возраст", "age_rating"), ("Статус", "status")):
            знач = деталь.get(ключ)
            if знач:
                пары.append((метка, html.escape(str(знач))))
        rail_rows = "".join(
            f"<div><dt>{html.escape(м)}</dt><dd>{з}</dd></div>" for м, з in пары)
        rail_dl = (f'<dl class="ztitle__dl">{rail_rows}</dl>' if rail_rows else "")
        ads_on = os.environ.get("ZONA_AD_SLOTS", "") == "1"
        ad_slot = (f'<div class="zad" data-ad-slot="title-rail-300x250" '
                   f'data-ad-enabled="{1 if ads_on else 0}" '
                   f'aria-hidden="{"false" if ads_on else "true"}"></div>')
        сезон_старт, эпизод_старт = выбрать_доступную_серию(деталь) if сезоны else (1, None)
        код, внутри = разметка_плеера(self, запись, деталь, сезон_старт, эпизод_старт)
        плеер = (f'<section class="zpl" id="watch"><div class="zpl__h"><h2>Смотреть</h2>'
                 f"<span>{html.escape(_подпись_плеера(код))}</span></div>"
                 f'<div class="zpl__f" data-player data-state="{код}">{внутри}</div>'
                 f"{_скрипты_плеера(код)}</section>")
        текущий = (сезон_старт, эпизод_старт) if эпизод_старт is not None else None
        блок_серий = (f'<div class="zwrap zwrap--title">{self._серии(запись, сезоны, текущий=текущий)}</div>'
                      if сериал else "")
        похожие = self.похожие(запись, деталь)
        блок_похожих = (f'<div class="zwrap"><h2 class="zh zh--sm">Смотрите также</h2>'
                        f"{self.плитки(похожие)}</div>" if похожие else "")
        # Description once only — never duplicate as "О чём это".
        тело = (
            f'<div class="zwrap zwrap--title"><div class="ztitle">'
            f'<div class="ztitle__poster">{изо}</div>'
            f'<div class="ztitle__main"><h1>{html.escape(имя)}</h1>'
            f'{orig_html}{pills}{meta_html}{описание_html}'
            f'<a class="ztitle__cta" href="#watch">Смотреть</a></div>'
            f'<aside class="ztitle__rail">{score_html}{оценки_html}{rail_dl}{ad_slot}</aside>'
            f'</div>{плеер}{блок_серий}{блок_похожих}</div>')
        разметка = self.schema_тайтла(запись, деталь, путь)
        краткое = (описание[:180] if описание else
                   f"{имя}: {запись.get('kind') or ''} {запись.get('year') or ''}".strip())
        return self.оболочка(
            тело, f"{имя} — смотреть онлайн — {self.имя}", путь,
            описание=краткое, разметка=разметка, крошки=self.крошки(звенья),
            og=self.карточка_графа(
                тип="video.tv_show" if сериал else "video.movie",
                титул=имя, описание=краткое, путь=путь,
                изображение=запись.get("poster") or ""))

    def _серии(self, запись: dict, сезоны: list, текущий=None) -> str:
        if not сезоны:
            return ('<h2 class="zh zh--sm">Серии</h2>'
                    '<div class="zempty"><b>Состав сезонов не передан</b>'
                    "<p>Источник по этой записи ещё не отдал список серий. "
                    "Как только отдаст, он появится здесь.</p></div>")
        блоки = []
        for сезон in сезоны:
            ссылки = []
            for н in сезон["номера"]:
                доступна = н <= сезон["avail"]
                текущая = (текущий == (сезон["n"], н))
                атрибуты = ' aria-current="page"' if текущая else (
                    "" if доступна else ' data-off title="Серия заявлена, дорожки ещё нет"')
                ссылки.append(
                    f'<a href="{self.адрес_эпизода(запись["slug"], сезон["n"], н)}"{атрибуты}>'
                    f"Серия {н}</a>")
            хвост = ("" if сезон["avail"] >= сезон["eps"]
                     else f" · доступно {сезон['avail']}")
            блоки.append(
                f'<section class="zsea"><div class="zsea__h">'
                f'<b>Сезон {сезон["n"]}</b><span>· {сезон["eps"]} серий{хвост}</span></div>'
                f'<div class="zeps">{"".join(ссылки)}</div></section>')
        return f'<h2 class="zh zh--sm">Серии</h2>{_склеить(блоки)}'

    def сезон(self, запись: dict, деталь: dict, номер: int) -> str:
        имя = запись["title"]
        путь = self.адрес_сезона(запись["slug"], номер)
        только = [с for с in список_серий(деталь) if с["n"] == номер]
        заголовок = f"{имя} — сезон {номер}"
        звенья = [("/", self.имя), ("/catalog/?kind=Сериал", "Сериалы"),
                  (f"/title/{запись['slug']}/", имя), ("", f"Сезон {номер}")]
        серий = только[0]["eps"] if только else 0
        тело = (f'<div class="zwrap"><h1 class="zh">{html.escape(заголовок)}</h1>'
                f'<p class="zsub">В сезоне {серий} серий · '
                f'<a href="/title/{запись["slug"]}/">вернуться к описанию</a></p>'
                + self._серии(запись, только) + "</div>")
        return self.оболочка(
            тело, f"{заголовок} — {self.имя}", путь,
            описание=f"{заголовок}: список серий на витрине {self.имя}.",
            разметка=self.schema_крошек(звенья), крошки=self.крошки(звенья),
            og=self.карточка_графа(
                тип="video.tv_show", титул=заголовок,
                описание=f"{заголовок}: список серий на витрине {self.имя}.",
                путь=путь, изображение=запись.get("poster") or ""))

    def серия(self, запись: dict, деталь: dict, сезон: int, эпизод: int) -> str:
        имя = запись["title"]
        путь = self.адрес_эпизода(запись["slug"], сезон, эпизод)
        заголовок = f"{имя} — {сезон} сезон, {эпизод} серия"
        звенья = [("/", self.имя), ("/catalog/?kind=Сериал", "Сериалы"),
                  (f"/title/{запись['slug']}/", имя), ("", f"Сезон {сезон}, серия {эпизод}")]
        код, внутри = разметка_плеера(self, запись, деталь, сезон, эпизод)
        плеер = (f'<section class="zpl"><div class="zpl__h"><h2>Смотреть серию</h2>'
                 f"<span>{html.escape(_подпись_плеера(код))}</span></div>"
                 f'<div class="zpl__f" data-player data-state="{код}">{внутри}</div>'
                 f"{_скрипты_плеера(код)}</section>")
        пред, след = границы_серии(деталь, сезон, эпизод)
        переход = ('<div class="zwrap"><nav class="zepnav" aria-label="Соседние серии">'
                   + (f'<a href="{self.адрес_эпизода(запись["slug"], *пред)}" rel="prev">← Сезон '
                      f"{пред[0]}, серия {пред[1]}</a>" if пред else
                      "<span>Это первая серия</span>")
                   + (f'<a href="{self.адрес_эпизода(запись["slug"], *след)}" rel="next">Сезон '
                      f"{след[0]}, серия {след[1]} →</a>" if след else
                      "<span>Это последняя серия</span>")
                   + "</nav></div>")
        сезоны = список_серий(деталь)
        шапка = (f'<div class="zwrap"><h1 class="zh">{html.escape(заголовок)}</h1>'
                 f'<p class="zsub">Всего в произведении {sum(с["eps"] for с in сезоны) or "?"} '
                 f'серий · <a href="/title/{запись["slug"]}/">вернуться к описанию</a></p></div>')
        тело = (шапка + плеер + переход
                + f'<div class="zwrap">{self._серии(запись, сезоны, текущий=(сезон, эпизод))}</div>')
        разметка = self.schema_эпизода(запись, деталь, сезон, эпизод, путь)
        return self.оболочка(
            тело, f"{заголовок} — {self.имя}", путь,
            описание=f"{заголовок}: смотреть онлайн на витрине {self.имя}.",
            разметка=разметка, крошки=self.крошки(звенья),
            og=self.карточка_графа(
                тип="video.episode", титул=заголовок,
                описание=f"{заголовок}: смотреть онлайн на витрине {self.имя}.",
                путь=путь, изображение=запись.get("poster") or ""))

    def не_найдено(self, путь: str) -> str:
        тело = ('<div class="znf"><b>404</b><h1>Страница не найдена</h1>'
                f"<p>Адрес <code>{html.escape(путь[:120])}</code> не соответствует ни одной "
                "записи каталога. Проверьте ссылку или начните с каталога.</p>"
                '<a href="/catalog/">Открыть каталог</a></div>')
        return self.оболочка(тело, f"Страница не найдена — {self.имя}", "", код=404)


def _скрипты_плеера(код: str) -> str:
    """Скрипт провайдера подключается только там, где он может сработать.

    На странице без источника его нет вовсе: грузить внешний скрипт, чтобы он
    ничего не нашёл, — это лишний запрос и лишняя точка отказа на странице,
    которая и так честно объяснила, чего не хватает.
    """
    if код not in {"playable", "resolving"}:
        return ""
    return (f'<script src="{СКРИПТ_ПЛЕЕРА}" async data-player-script></script>'
            f"<script>{СКРИПТ_ПЛЕЕРА_КЛИЕНТ}</script>")


def _подпись_плеера(код: str) -> str:
    if СЕМЕЙСТВО == "animedia":
        return {
            "playable": "смотреть",
            "awaiting": "выберите серию",
            "unavailable": "серия недоступна",
            "loading": "загрузка",
            "resolving": "подключение",
            "active": "",
            "ok": "",
            "nosource": "видео пока недоступно",
            "noaccess": "видео пока недоступно",
            "provider": "видео временно недоступно",
            "error": "видео временно недоступно",
            "slow": "",
        }.get(код, "")
    return {
        "playable": "источник подключён",
        "awaiting": "выберите серию",
        "unavailable": "серия без дорожки",
        "loading": "подключение источника",
        "nosource": "источник не передан",
        "noaccess": "витрина без доступа к провайдеру",
        "provider": "провайдер не отдал дорожку",
        "error": "скрипт провайдера не загрузился",
        "slow": "таймаут поднятия плеера",
    }.get(код, "состояние неизвестно")


def _открытый_граф(данные: dict) -> str:
    """Карточка Open Graph. Сущность у неё та же, что у страницы.

    Поля берутся из тех же значений, что уже ушли в `H1`, `<title>`,
    `description`, canonical и Schema. Отдельного «сеошного» набора здесь нет
    намеренно: страница, которая рассказывает о себе роботу одно, а зрителю
    другое, — это подмена, и она запрещена правилами направления.

    Пустое поле не печатается: `og:image` без адреса хуже отсутствующего
    `og:image`, потому что он обещает картинку.
    """
    if not данные:
        return ""
    порядок = ("type", "title", "description", "url", "image", "site_name", "locale")
    куски = []
    for ключ in порядок:
        значение = (данные.get(ключ) or "").strip()
        if значение:
            куски.append(f'<meta property="og:{ключ}" content="{html.escape(значение)}">')
    if данные.get("image"):
        куски.append('<meta name="twitter:card" content="summary_large_image">')
    return "".join(куски)


def _мета_версии() -> str:
    return (
        f'<meta name="site-factory-template-revision" content="{МАНИФЕСТ["source_commit"]}">'
        f'<meta name="site-factory-design-version" content="{ВЕРСИЯ}">'
        f'<meta name="site-factory-template-family" content="{СЕМЕЙСТВО}">'
        f'<meta name="site-factory-build-id" content="{СБОРКА}">'
        f'<meta name="site-factory-artifact-sha256" content="{МАНИФЕСТ["artifact_sha256"]}">'
        f'<meta name="site-factory-template" content="{ШАБЛОН_СЕМЕЙСТВА}">'
        f'<meta name="site-factory-core" content="{ЯДРО}">'
        f'<meta name="site-factory-profile" content="{ПРОФИЛЬ}">'
        + тег_метрики()
    )


#: Виды записей, которые семейство Animedia считает своими. Перечень закрытый:
#: витрина аниме, показывающая обычные фильмы, — это не «широкий каталог», а
#: подмешанный чужой профиль.
АНИМЕ_ВИДЫ = ("Аниме", "ТВ", "OVA", "ONA", "Аниме-фильм", "Онгоинг", "Донхуа")


#: Europe/Moscow — documented site timezone for Animedia human timestamps.
АНИМЕДИА_TZ = timezone(timedelta(hours=3))
АНИМЕДИА_ЭПИЗОД_НА_СТРАНИЦЕ = 10
# B03: provider_became_playable ledger absent → compact empty, no catalog fallback.
АНИМЕДИА_EPISODE_EVENT_DATA_GAP = 1
TRUE_PROVIDER_PLAYABLE_EVENT_COUNT = 0
АНИМЕДИА_ЭПИЗОД_ЗАГОЛОВОК = "Новые серии аниме"
АНИМЕДИА_ЭПИЗОД_EMPTY_COPY = (
    "Лента новых серий пока недоступна: источник событий ещё не подключён"
)
АНИМЕДИА_PROVIDER_PLAYABLE_PATH = os.environ.get(
    "ANIMEDIA_PROVIDER_PLAYABLE_EVENTS",
    str(Path(__file__).resolve().parents[2] / "config" / "animedia-provider-playable-events.json"),
)
# Legacy alias — catalog-publish rows must not feed B03.
АНИМЕДИА_ЭПИЗОД_ПОДПИСЬ = АНИМЕДИА_ЭПИЗОД_EMPTY_COPY

# B05: catalog_added ledger — ambiguous published_at is NOT catalog_added_at.
АНИМЕДИА_CATALOG_ADDED_PATH = os.environ.get(
    "ANIMEDIA_CATALOG_ADDED_LEDGER",
    str(Path(__file__).resolve().parents[2] / "config" / "animedia-catalog-added.json"),
)
АНИМЕДИА_CATALOG_ADDED_PAGE_SIZE = 10
АНИМЕДИА_CATALOG_ADDED_H1 = "Новое в каталоге"
АНИМЕДИА_CATALOG_ADDED_EMPTY = (
    "Список новинок каталога пока недоступен: ledger добавлений ещё не подключён"
)
# Ambiguous catalog.items[].published_at is NOT catalog_added_at (§5.5 / B05).
CATALOG_FRESHNESS_DATA_GAP = 1
АНИМЕДИА_CATALOG_ADDED_HOME_LIMIT = 16
АНИМЕДИА_SEARCH_PAGE_SIZE = 24
АНИМЕДИА_SEARCH_EMPTY = "Запрос пуст"
АНИМЕДИА_SEARCH_ZERO = "Совпадений нет"
АНИМЕДИА_SEARCH_ERROR = "Поиск временно недоступен"

# B13: collections hub and detail.
АНИМЕДИА_COLLECTIONS_PAGE_SIZE = 12
АНИМЕДИА_COLLECTION_DETAIL_PAGE_SIZE = 24
#: Сортировки хаба идут только по полям, которые в контракте уже есть.
АНИМЕДИА_COLLECTIONS_SORTS = ("contract", "size", "name")
#: `section_id` в контракте коллекций взаимно однозначен с `collection_key`,
#: то есть измерения «категория» у данных нет. Рисовать категории поверх
#: такого поля значило бы выдумать таксономию, поэтому переключателя нет, а
#: пробел объявлен.
COLLECTION_CATEGORY_DATA_GAP = 1
#: У коллекции есть `data_revision` — отпечаток состава, а не дата публикации
#: ревизии. Показать отпечаток как дату нельзя, поэтому у карточек и страниц
#: коллекций видимой даты нет вовсе.
COLLECTION_REVISION_TIMESTAMP_DATA_GAP = 1

# B06: Top-100 home shelf — approved TopSnapshot only (no frontend ranking).
АНИМЕДИА_TOP100_PATH = os.environ.get(
    "ANIMEDIA_TOP100_SNAPSHOT",
    str(Path(__file__).resolve().parents[2] / "config" / "animedia-top100.json"),
)
TOP100_DATA_GAP = 1
АНИМЕДИА_HOME_MAX_CATALOG_SHELVES = 2
АНИМЕДИА_TOP100_HOME_LIMIT = 12
АНИМЕДИА_TOP100_REQUIRED_FIELDS = (
    "schema_version", "site_id", "ordered_title_ids", "snapshot_revision",
    "digest", "generated_at",
)
# B08: owner-approved default-episode policy (ANIMEDIA-B10-B16-20260920-01).
АНИМЕДИА_DEFAULT_EPISODE_POLICY_PATH = os.environ.get(
    "ANIMEDIA_DEFAULT_EPISODE_POLICY",
    str(Path(__file__).resolve().parents[2] / "config" / "animedia-default-episode-policy.json"),
)
АНИМЕДИА_DEFAULT_EPISODE_POLICY = "FIRST_PLAYABLE_DETERMINISTIC"
DEFAULT_EPISODE_POLICY_DATA_GAP = 0
АНИМЕДИА_DEFAULT_EPISODE_OWNER_DECISION = "ANIMEDIA-B10-B16-20260920-01"
# B10: recommendations — approved RecommendationSnapshot, else deterministic metadata fallback.
АНИМЕДИА_RECOMMENDATIONS_PATH = os.environ.get(
    "ANIMEDIA_RECOMMENDATIONS_SNAPSHOT",
    str(Path(__file__).resolve().parents[2] / "config" / "animedia-recommendations.json"),
)
АНИМЕДИА_REC_TITLE = "Похожее аниме"
АНИМЕДИА_REC_MIN_ITEMS = 4
АНИМЕДИА_REC_MAX_ITEMS = 12
АНИМЕДИА_REC_FALLBACK_ALGORITHM = "DETERMINISTIC_METADATA_RELATED_V1"
АНИМЕДИА_REC_REQUIRED_FIELDS = (
    "ordered_title_ids", "algorithm_version", "digest",
)
# Declared P2 until an approved RecommendationSnapshot is present on disk.
RECOMMENDATIONS_DATA_GAP = int(not Path(АНИМЕДИА_RECOMMENDATIONS_PATH).is_file())
# Popular shelf: ONLY an owner/Core-approved WeeklyPopularSnapshot (§5.6).
# Template must not rank catalog ratings into a public «Популярное за неделю».
АНИМЕДИА_POPULAR_WINDOW = "weekly"
АНИМЕДИА_POPULAR_REFRESH_ON_EVERY_REQUEST = 0
АНИМЕДИА_WEEKLY_POPULAR_PATH = os.environ.get(
    "ANIMEDIA_WEEKLY_POPULAR_SNAPSHOT",
    str(Path(__file__).resolve().parents[2] / "config" / "animedia-weekly-popular.json"),
)
_АНИМЕДИА_POPULAR_CACHE: dict[str, dict] = {}
АНИМЕДИА_WEEKLY_REQUIRED_FIELDS = (
    "schema_version", "site_id", "week_id", "timezone",
    "window_start", "window_end", "valid_from", "valid_to",
    "algorithm_version", "algorithm_parameters_digest", "input_revision",
    "cutoff_at", "ordered_title_ids", "eligibility_policy", "playable_policy",
    "tie_breaker", "snapshot_revision", "generated_at", "digest",
)


def _аниме_popular_week_key(now: datetime | None = None) -> str:
    dt = now or datetime.now(timezone.utc)
    y, w, _ = dt.isocalendar()
    return f"{y}-W{w:02d}"


def _аниме_popular_score(деталь: dict) -> float:
    числа = []
    for ключ in ("kinopoisk_rating", "imdb_rating", "shikimori_score"):
        try:
            числа.append(float(деталь.get(ключ)))
        except (TypeError, ValueError):
            pass
    return max(числа) if числа else 0.0


def аниме_popular_snapshot(
    items: list,
    detail_fn,
    *,
    revision: str = "",
    limit: int = 48,
    now: datetime | None = None,
) -> dict:
    """Legacy deterministic score order — NOT an approved display snapshot.

    Kept for unit immutability checks only. Home B02 must not render from this.
    """
    week = _аниме_popular_week_key(now)
    rev = str(revision or "")
    cache_key = f"{rev}|{week}"
    hit = _АНИМЕДИА_POPULAR_CACHE.get(cache_key)
    if hit is not None:
        return hit
    scored: list[tuple[float, str, str]] = []
    for з in items:
        slug = str(з.get("slug") or "")
        if not slug:
            continue
        score = _аниме_popular_score(detail_fn(slug) or {})
        if score <= 0:
            continue
        scored.append((score, str(з.get("published_at") or ""), slug))
    scored.sort(key=lambda t: (t[0], t[1], t[2]), reverse=True)
    slugs = [t[2] for t in scored[:limit]]
    updated = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    version = hashlib.sha256(
        f"{cache_key}|{'|'.join(slugs)}".encode("utf-8")).hexdigest()[:16]
    snap = {
        "window": АНИМЕДИА_POPULAR_WINDOW,
        "week_key": week,
        "catalog_revision": rev,
        "updated_at": updated,
        "snapshot_version": version,
        "slugs": slugs,
        "refresh_on_every_request": АНИМЕДИА_POPULAR_REFRESH_ON_EVERY_REQUEST,
        "display_approved": False,
    }
    _АНИМЕДИА_POPULAR_CACHE[cache_key] = snap
    stale = [k for k in _АНИМЕДИА_POPULAR_CACHE
             if k.startswith(f"{rev}|") and k != cache_key]
    for k in stale[1:]:
        _АНИМЕДИА_POPULAR_CACHE.pop(k, None)
    return snap


def аниме_popular_apply(набор: list, snapshot: dict) -> list:
    """Reorder/filter a candidate shelf by weekly popular snapshot slugs."""
    by_slug = {з.get("slug"): з for з in набор if з.get("slug")}
    out = []
    for slug in snapshot.get("slugs") or snapshot.get("ordered_title_ids") or []:
        з = by_slug.get(slug)
        if з is not None:
            out.append(з)
    return out


def аниме_load_approved_weekly_popular(
    *,
    site_id: str = "",
    path: str | Path | None = None,
) -> dict | None:
    """Load schema-shaped WeeklyPopularSnapshot or return None (POPULAR_DATA_GAP)."""
    путь = Path(path or АНИМЕДИА_WEEKLY_POPULAR_PATH)
    if not путь.is_file():
        return None
    try:
        raw = json.loads(путь.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    for key in АНИМЕДИА_WEEKLY_REQUIRED_FIELDS:
        if key not in raw or raw[key] in (None, "", []):
            return None
    ids = raw.get("ordered_title_ids")
    if not isinstance(ids, list) or len(ids) < 4:
        return None
    if site_id and str(raw.get("site_id") or "") not in {"", site_id, "animedia", "*"}:
        # Allow shared animedia snapshot across .icu/.space when site_id matches family.
        sid = str(raw.get("site_id") or "")
        if site_id not in sid and sid not in site_id and not sid.startswith("animedia"):
            return None
    out = dict(raw)
    out["slugs"] = [str(x) for x in ids if x]
    out["display_approved"] = True
    out["window"] = out.get("window") or АНИМЕДИА_POPULAR_WINDOW
    out["week_key"] = out.get("week_id") or out.get("week_key")
    out["snapshot_version"] = out.get("digest") or out.get("snapshot_revision")
    out["updated_at"] = out.get("generated_at") or out.get("updated_at") or ""
    return out


def аниме_weekly_shelf_from_approved(
    items: list,
    approved: dict | None,
    *,
    min_items: int = 4,
    limit: int = 48,
) -> tuple[list, dict | None]:
    """Resolve approved ordered IDs against catalog; enforce ≥ min_items."""
    if not approved or not approved.get("display_approved"):
        return [], None
    by_slug = {з.get("slug"): з for з in items if з.get("slug")}
    out = []
    for slug in approved.get("slugs") or []:
        з = by_slug.get(slug)
        if з is None:
            continue
        out.append(з)
        if len(out) >= limit:
            break
    if len(out) < min_items:
        return [], None
    return out, approved


def аниме_load_approved_top100(
    *,
    site_id: str = "",
    path: str | Path | None = None,
) -> dict | None:
    """Load approved TopSnapshot or return None (TOP100_DATA_GAP)."""
    путь = Path(path or АНИМЕДИА_TOP100_PATH)
    if not путь.is_file():
        return None
    try:
        raw = json.loads(путь.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    for key in АНИМЕДИА_TOP100_REQUIRED_FIELDS:
        if key not in raw or raw[key] in (None, "", []):
            return None
    ids = raw.get("ordered_title_ids")
    if not isinstance(ids, list) or len(ids) < 4:
        return None
    # Dedup while preserving order — ranks must stay dense when rendered.
    seen = set()
    slugs = []
    for x in ids:
        s = str(x or "")
        if not s or s in seen:
            continue
        seen.add(s)
        slugs.append(s)
    if len(slugs) < 4:
        return None
    if site_id and str(raw.get("site_id") or "") not in {"", site_id, "animedia", "*"}:
        sid = str(raw.get("site_id") or "")
        if site_id not in sid and sid not in site_id and not sid.startswith("animedia"):
            return None
    out = dict(raw)
    out["slugs"] = slugs
    out["display_approved"] = True
    return out


def аниме_top100_shelf_from_approved(
    items: list,
    approved: dict | None,
    *,
    min_items: int = 4,
    limit: int = 12,
) -> tuple[list, dict | None]:
    if not approved or not approved.get("display_approved"):
        return [], None
    by_slug = {з.get("slug"): з for з in items if з.get("slug")}
    out = []
    for slug in approved.get("slugs") or []:
        з = by_slug.get(slug)
        if з is None:
            continue
        out.append(з)
        if len(out) >= limit:
            break
    if len(out) < min_items:
        return [], None
    return out, approved


def _аниме_genre_codes(деталь: dict) -> list[str]:
    """Verified genre codes only — never invent genres."""
    коды = [str(к).strip() for к in (деталь.get("genre_codes") or []) if к]
    if not коды:
        for г in (деталь.get("genres") or []):
            к = нормализовать(транслит(str(г)))
            if к:
                коды.append(к)
    seen, out = set(), []
    for к in коды:
        if к and к not in seen:
            seen.add(к)
            out.append(к)
    return out


def _аниме_rec_digest(parts: list[str]) -> str:
    import hashlib
    payload = "\n".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:32]


def аниме_load_approved_recommendations(
    seed_title_id: str,
    *,
    site_id: str = "",
    path: str | Path | None = None,
) -> dict | None:
    """Load per-title RecommendationSnapshot or return None (RECOMMENDATIONS_DATA_GAP)."""
    путь = Path(path or АНИМЕДИА_RECOMMENDATIONS_PATH)
    if not путь.is_file():
        return None
    try:
        raw = json.loads(путь.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    entry = None
    by_title = raw.get("by_title") or raw.get("by_title_id") or {}
    if isinstance(by_title, dict) and seed_title_id in by_title:
        entry = by_title[seed_title_id]
    elif str(raw.get("seed_title_id") or raw.get("title_id") or "") == seed_title_id:
        entry = raw
    if not isinstance(entry, dict):
        return None
    for key in АНИМЕДИА_REC_REQUIRED_FIELDS:
        if key not in entry or entry[key] in (None, "", []):
            return None
    ids = entry.get("ordered_title_ids")
    if not isinstance(ids, list) or len(ids) < АНИМЕДИА_REC_MIN_ITEMS:
        return None
    seen, slugs = set(), []
    for x in ids:
        s = str(x or "").strip()
        if not s or s == seed_title_id or s in seen:
            continue
        seen.add(s)
        slugs.append(s)
    if len(slugs) < АНИМЕДИА_REC_MIN_ITEMS:
        return None
    if site_id and str(raw.get("site_id") or entry.get("site_id") or "") not in {
            "", site_id, "animedia", "*"}:
        sid = str(raw.get("site_id") or entry.get("site_id") or "")
        if site_id not in sid and sid not in site_id and not sid.startswith("animedia"):
            return None
    out = dict(entry)
    out["slugs"] = slugs
    out["seed_title_id"] = seed_title_id
    out["display_approved"] = True
    out["source"] = "RecommendationSnapshot"
    out["algorithm_version"] = str(entry.get("algorithm_version") or "")
    out["digest"] = str(entry.get("digest") or "")
    out["membership_digest"] = str(
        entry.get("membership_digest") or _аниме_rec_digest(slugs))
    out["generated_at"] = str(entry.get("generated_at") or "")
    return out


def аниме_recommendations_from_approved(
    items: list,
    approved: dict | None,
    *,
    min_items: int = АНИМЕДИА_REC_MIN_ITEMS,
    limit: int = АНИМЕДИА_REC_MAX_ITEMS,
) -> tuple[list, dict | None]:
    if not approved or not approved.get("display_approved"):
        return [], None
    by_slug = {з.get("slug"): з for з in items if з.get("slug")}
    out = []
    for slug in approved.get("slugs") or []:
        з = by_slug.get(slug)
        if з is None:
            continue
        # Broken / missing canonical route → skip.
        url = str(з.get("url") or f"/title/{slug}/")
        if not url.startswith("/title/"):
            continue
        out.append(з)
        if len(out) >= limit:
            break
    if len(out) < min_items:
        return [], None
    return out, approved


def аниме_build_deterministic_related(
    seed_item: dict,
    seed_detail: dict,
    items: list,
    detail_fn,
    *,
    min_items: int = АНИМЕДИА_REC_MIN_ITEMS,
    limit: int = АНИМЕДИА_REC_MAX_ITEMS,
) -> tuple[list, dict | None]:
    """DETERMINISTIC_METADATA_RELATED_V1 from verified fields only.

    Eligibility: active title, not seed, same content type (when known), ≥1
    shared genre, working canonical route. Prefer playable. Sort:
    playable DESC, shared_genre_count DESC, year_distance ASC, slug ASC.
    """
    seed_slug = str(seed_item.get("slug") or "")
    if not seed_slug:
        return [], None
    seed_genres = set(_аниме_genre_codes(seed_detail))
    if not seed_genres:
        return [], None
    seed_type = str(seed_detail.get("type") or "").strip().lower() or None
    try:
        seed_year = int(seed_item.get("year"))
    except (TypeError, ValueError):
        seed_year = None

    scored = []
    seen = {seed_slug}
    for з in items:
        slug = str(з.get("slug") or "")
        if not slug or slug in seen:
            continue
        det = detail_fn(slug) if callable(detail_fn) else {}
        if not isinstance(det, dict):
            det = {}
        genres = set(_аниме_genre_codes(det))
        shared = len(seed_genres & genres)
        if shared < 1:
            continue
        ctype = str(det.get("type") or "").strip().lower() or None
        if seed_type and ctype and seed_type != ctype:
            continue
        url = str(з.get("url") or f"/title/{slug}/")
        if not url.startswith("/title/"):
            continue
        playable = bool(det.get("playable"))
        if not playable:
            try:
                playable = состояние_плеера(det)[0] == "playable"
            except Exception:
                playable = False
        try:
            year = int(з.get("year"))
        except (TypeError, ValueError):
            year = None
        if seed_year is not None and year is not None:
            year_distance = abs(seed_year - year)
        else:
            year_distance = 10_000  # unknown year not used as a preference signal
        seen.add(slug)
        scored.append((
            0 if playable else 1,
            -shared,
            year_distance,
            slug,
            з,
        ))
    scored.sort(key=lambda t: (t[0], t[1], t[2], t[3]))
    out = [t[4] for t in scored[:limit]]
    if len(out) < min_items:
        return [], None
    slugs = [з["slug"] for з in out]
    digest = _аниме_rec_digest(
        [АНИМЕДИА_REC_FALLBACK_ALGORITHM, seed_slug, *slugs])
    meta = {
        "source": АНИМЕДИА_REC_FALLBACK_ALGORITHM,
        "algorithm_version": АНИМЕДИА_REC_FALLBACK_ALGORITHM,
        "digest": digest,
        "membership_digest": _аниме_rec_digest(slugs),
        "generated_at": str(МАНИФЕСТ.get("built_at") or МАНИФЕСТ.get("source_commit") or ""),
        "seed_title_id": seed_slug,
        "display_approved": False,
        "fallback": True,
        "slugs": slugs,
    }
    return out, meta


def _аниме_формат_времени_анонса(published_at: str, precision: str) -> str:
    """Human-readable catalog publish time. Never invents missing clocks.

    precision=datetime → may use Сегодня/Вчера with HH:MM in АНИМЕДИА_TZ.
    precision=date → localized date only (no 00:00, no «Сегодня»).
    precision=none/empty → empty string.
    """
    raw = (published_at or "").strip()
    if not raw or precision in {"", "none", None}:
        return ""
    try:
        if raw.endswith("Z"):
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return raw[:10] if len(raw) >= 10 else raw
    local = dt.astimezone(АНИМЕДИА_TZ)
    if precision == "date" or ("T" not in raw and " " not in raw):
        return local.strftime("%d.%m.%Y")
    today = datetime.now(АНИМЕДИА_TZ).date()
    if local.date() == today:
        return f"Сегодня, {local.strftime('%H:%M')}"
    if local.date() == today - timedelta(days=1):
        return f"Вчера, {local.strftime('%H:%M')}"
    return local.strftime("%d.%m.%Y, %H:%M")



#: Контракт контактов/legal Animedia. Значения только из файла владельца.
#: Пустой/отсутствующий файл → CONTACT_DATA_GAP, UI скрывает блоки.
АНИМЕДИА_OWNER_CONFIG_PATH = os.environ.get(
    "ANIMEDIA_OWNER_CONFIG",
    str(Path(__file__).resolve().parents[2] / "config" / "animedia-owner.json"),
)


def _аниме_owner_config() -> dict:
    путь = Path(АНИМЕДИА_OWNER_CONFIG_PATH)
    if not путь.is_file():
        return {}
    try:
        сырое = json.loads(путь.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return сырое if isinstance(сырое, dict) else {}


def _аниме_контакты_html() -> str:
    conf = _аниме_owner_config()
    parts = []
    email = str(conf.get("contact_email") or "").strip()
    tg = str(conf.get("telegram_url") or "").strip()
    if email and "@" in email and " " not in email:
        parts.append(f'<a href="mailto:{html.escape(email)}">{html.escape(email)}</a>')
    if tg.startswith("https://t.me/") or tg.startswith("https://telegram.me/"):
        parts.append(f'<a href="{html.escape(tg)}" rel="noopener noreferrer">Telegram</a>')
    return "".join(parts)


def _аниме_legal_html() -> str:
    conf = _аниме_owner_config()
    parts = []
    for key, label in (("privacy_url", "Конфиденциальность"), ("terms_url", "Условия")):
        url = str(conf.get(key) or "").strip()
        if url.startswith("/") or url.startswith("https://"):
            parts.append(f'<a href="{html.escape(url)}">{label}</a>')
    return "".join(parts)


def _аниме_telegram_promo_html() -> str:
    """B02.1: compact Telegram strip only when owner provides a real URL."""
    conf = _аниме_owner_config()
    tg = str(conf.get("telegram_url") or "").strip()
    if not (tg.startswith("https://t.me/") or tg.startswith("https://telegram.me/")):
        return ""
    return (
        f'<aside class="atg" data-telegram-promo="1">'
        f'<a href="{html.escape(tg)}" rel="noopener noreferrer">'
        f'Telegram-канал Animedia</a></aside>'
    )


АНИМЕДИА_ДОМЕНЫ = {
    "animedia.space": {
        "profile": "animedia-space",
        "og_site_name": "Animedia Space",
        "title_home": "Animedia Space — новое в каталоге и популярное аниме",
        "h1": "Новое в каталоге и популярное аниме",
        "description": (
            "Animedia Space — витрина недавно добавленных тайтлов и популярных "
            "записей с быстрым переходом к просмотру."),
        "lead": (
            "Недавно добавленные тайтлы и популярные записи — короткий путь "
            "к просмотру без лишнего шума."),
        "footer_about": (
            "Animedia Space помогает искать аниме по оценкам, жанрам и типу: "
            "фильмы, дунхуа и классика из утверждённого каталога."),
        "seo_home_title": "Зачем Animedia Space",
        "seo_home": (
            "Animedia Space собирает недавно добавленные тайтлы и популярные "
            "записи в одном месте: сначала лента каталога, затем топ и "
            "тематические подборки. Пустые полки скрываются. Поиск понимает "
            "кириллицу, латиницу и slug."),
        "seo_catalog_title": "Как устроен каталог Space",
        "seo_catalog": (
            "Фильтры жанра, года и типа сужают каталог Animedia Space. "
            "Пагинация сохраняет условия в адресе, а пустая выдача честно "
            "говорит об отсутствии совпадений."),
        "home_shelves": (
            "recently_added", "top_rated", "action",
            "classic", "anime_movies", "donghua",
        ),
    },
    "animedia.icu": {
        "profile": "animedia-icu",
        "og_site_name": "Animedia ICU",
        "title_home": "Animedia ICU — сериалы, фильмы и дунхуа",
        "h1": "Сериалы, фильмы и дунхуа",
        "description": (
            "Animedia ICU — каталог сериалов с сериями, аниме-фильмов, дунхуа "
            "и тематических подборок."),
        "lead": (
            "Сериалы с доступными сериями, полнометражные фильмы и дунхуа — "
            "спокойный вход в большой каталог."),
        "footer_about": (
            "Animedia ICU — сериалы с сериями, аниме-фильмы, дунхуа и "
            "тематические подборки из утверждённого каталога."),
        "seo_home_title": "Чем полезен Animedia ICU",
        "seo_home": (
            "Animedia ICU делает упор на сериалы с сериями, аниме-фильмы и "
            "дунхуа. Дальше — короткие сериалы и жанровые подборки. Даты "
            "выхода без источника не выдумываются. Каталог и поиск помогают "
            "найти нужный тайтл по названию или жанру."),
        "seo_catalog_title": "Навигация по каталогу ICU",
        "seo_catalog": (
            "Каталог Animedia ICU сочетает жанровые срезы с поиском по "
            "кириллице, латинице и slug. Фильтры остаются в URL, чтобы "
            "вернуться к той же выдаче."),
        "home_shelves": (
            "series_with_episodes", "anime_movies", "donghua",
            "short_series", "top_rated", "classic", "romance",
        ),
    },
}


def _аниме_домен(хост: str) -> dict:
    хост = (хост or "").split(":")[0].lower().removeprefix("www.")
    return АНИМЕДИА_ДОМЕНЫ.get(хост) or АНИМЕДИА_ДОМЕНЫ["animedia.space"]



class ВидАнимедиа(ВидЗона):
    """Аниме-портал: светлая основа, плотная сетка, свои разделы.

    От Zona наследуется только механика страниц — маршруты, карточка
    произведения, сезоны и серии. Оформление, состав главной и словарь
    разделов свои: механически переносить кинопортал на аниме нельзя, и
    именно это расхождение было главным дефектом витрины.

    Отдельная забота этого вида — НЕ показать чужой каталог. Если снимок
    пришёл не аниме-каталогом, витрина говорит об этом прямо и не рисует
    ни одной чужой карточки. Подменять отсутствующие данные соседним
    каталогом нельзя: зритель получил бы витрину аниме, целиком состоящую
    из обычных фильмов, — ровно то, что здесь измерено на живых доменах.
    """

    def __init__(self, *а, **кв):
        super().__init__(*а, **кв)
        всего = len(self.д.items)
        свои = [з for з in self.д.items if з.get("kind") in АНИМЕ_ВИДЫ]
        self.готовность = {
            "записей_в_снимке": всего,
            "из_них_аниме": len(свои),
            "доля": round(len(свои) / всего, 4) if всего else 0.0,
            "готово": bool(свои) and (len(свои) / всего if всего else 0) >= 0.5,
        }
        # Чужие записи снимаются НА УРОВНЕ ДАННЫХ вида, а не на каждой странице:
        # иначе каталог, поиск, маршрут тайтла и рекомендации пришлось бы
        # чинить по отдельности, и любой забытый путь снова показал бы чужое.
        #
        # Отбор по ВИДУ записи недостаточен, и это измерено: в снимке
        # animedia-01 из 3999 записей 131 помечена «Аниме», но 3995 slug
        # совпадают с боевым каталогом Zona. То есть вид записи не отличает
        # своё от чужого — чужой каталог может прийти с любой пометкой.
        #
        # Поэтому решает ГОТОВНОСТЬ снимка целиком: пока он не признан
        # аниме-каталогом, витрина не показывает ни одной карточки. Показать
        # «те, что похожи на аниме» значило бы выдать чужой каталог за свой,
        # только в меньшем объёме.
        if not self.готовность["готово"]:
            свои = []
        if len(свои) != всего:
            свой_срез = copy.copy(self.д)
            свой_срез.items = свои
            свой_срез.years = sorted({з["year"] for з in свои if з.get("year")},
                                     reverse=True)
            свой_срез.kinds = sorted({з["kind"] for з in свои if з.get("kind")})
            self.д = свой_срез

    def плитка(self, запись: dict, *, вариант: str = "catalog-title") -> str:
        """Карточка с пропорцией постера 0.86 — измеренной на эталоне.

        Размеры проставляются в разметке, а не только в CSS: браузер обязан
        зарезервировать место до загрузки изображения, иначе сетка прыгает.
        `вариант` — ключ CARD_VARIANT_REGISTRY (parity-02 BLOCK_03).
        """
        деталь = self.деталь(запись["slug"])
        изо = заглушка_постера(запись, "zt__none", "zt__img", 190, 285)
        мета = " · ".join(str(ч) for ч in (запись.get("kind"), запись.get("year")) if ч)
        оценки = оценки_по_источникам(деталь)
        if оценки:
            о = оценки[0]
            оценка = (f'<span class="zt__r"><span>{html.escape(о["подпись"])} '
                      f'<b>{html.escape(о["значение"])}</b></span></span>')
        else:
            оценка = '<span class="zt__r"><em aria-hidden="true">·</em></span>'
        return (f'<a class="zt" data-card-variant="{html.escape(вариант)}" href="{запись["url"]}">'
                f'<span class="zt__p">{изо}</span>'
                f'<span class="zt__b"><span class="zt__t">{html.escape(запись["title"])}</span>'
                f'<span class="zt__m">{html.escape(мета)}</span>{оценка}</span></a>')

    def карусель(self, ключ: str, набор) -> str:
        """Hero uses top-shelf card variant; other rails stay catalog-title."""
        вариант = "top-shelf" if ключ == "hero" else "catalog-title"
        плитки = "".join(self.плитка(з, вариант=вариант) for з in набор)
        ид = f"rl-{ключ}"
        return (f'<div class="zrl">'
                f'<button class="zrl__btn zrl__btn--p" type="button" data-rl="prev"'
                f' aria-controls="{ид}" aria-label="Пролистать назад">&#8249;</button>'
                f'<div class="zrl__vp" id="{ид}" tabindex="0" role="group"'
                f' aria-label="Лента произведений">'
                f'<div class="zrl__track">{плитки}</div></div>'
                f'<button class="zrl__btn zrl__btn--n" type="button" data-rl="next"'
                f' aria-controls="{ид}" aria-label="Пролистать вперёд">&#8250;</button>'
                f'</div>')

    def плитки(self, набор, *, вариант: str = "catalog-title") -> str:
        extra = " zg--recommendation" if вариант == "recommendation" else ""
        return (f'<div class="zg{extra}" data-card-grid="' + html.escape(вариант) + '">'
                + "".join(self.плитка(з, вариант=вариант) for з in набор) + "</div>")

    def логотип(self) -> str:
        """Логотип: «Ani» акцентом + «media», без чужой иконки/Premium."""
        имя = self.имя or "Animedia"
        low = имя.lower()
        if low.startswith("ani") and len(имя) > 3:
            return (f'<a class="zhd__logo" href="/"><b>{html.escape(имя[:3])}</b>'
                    f"{html.escape(имя[3:])}</a>")
        if low.endswith("dia") and len(имя) > 3:
            база, хвост = имя[:-3], имя[-3:]
            return (f'<a class="zhd__logo" href="/">{html.escape(база)}'
                    f"<b>{html.escape(хвост)}</b></a>")
        return f'<a class="zhd__logo" href="/">{html.escape(имя)}</a>'

    def крошки(self, звенья) -> str:
        """B01.2 breadcrumb: registry-safe intermediates, 32–40 px band."""
        куски = []
        for адрес, имя in звенья:
            if адрес:
                куски.append(f'<a href="{адрес}">{html.escape(имя)}</a>')
            else:
                куски.append(f'<span aria-current="page">{html.escape(имя)}</span>')
        return f'<nav class="zcr" aria-label="Хлебные крошки">{" / ".join(куски)}</nav>'

    def таксономия(self, *, префикс: str = "") -> str:
        """Жанр / Тип / Списки / Ещё — только из реального индекса и маршрутов.

        Counts from catalog oracle; empty facets omitted. Status absent in
        snapshot → panel not invented. Premium / Telegram / account omitted
        without owner URL. `префикс` disambiguates header vs drawer panel ids.
        """
        p = префикс
        индекс = getattr(self, "индекс", None) or {}
        genre_idx = индекс.get("genre") or {}
        жанры = []
        for код, имя in list(индекс.get("genre_names") or [])[:14]:
            n = len(genre_idx.get(код) or [])
            if n <= 0:
                continue
            жанры.append(
                f'<a href="/catalog/?genre={html.escape(код)}">'
                f'<span>{html.escape(имя)}</span>'
                f'<span class="zhd__cnt">{n}</span></a>')
        жанр_ссылки = "".join(жанры)
        типы = []
        for код, имя in (("tv", "Сериалы"), ("movie", "Фильмы")):
            slugs = индекс.get("type", {}).get(код) or []
            n = len(slugs)
            if n <= 0:
                continue
            типы.append(
                f'<a href="/catalog/?type={код}">'
                f'<span>{html.escape(имя)}</span>'
                f'<span class="zhd__cnt">{n}</span></a>')
        тип_блок = "".join(типы)
        years_idx = {str(г): 0 for г in (getattr(self.д, "years", []) or [])}
        for з in getattr(self.д, "items", []) or []:
            y = з.get("year")
            if y is not None and str(y) in years_idx:
                years_idx[str(y)] += 1
        годы = "".join(
            f'<a href="/catalog/?year={г}"><span>{г}</span>'
            f'<span class="zhd__cnt">{years_idx[str(г)]}</span></a>'
            for г in list(getattr(self.д, "years", []) or [])[:10]
            if years_idx.get(str(г), 0) > 0)
        панели = []
        if жанр_ссылки:
            панели.append(
                f'<div class="zhd__dd" data-tax-panel="genre">'
                f'<button type="button" class="zhd__dd-btn" data-tax-toggle="genre" '
                f'aria-expanded="false" aria-controls="{p}tax-genre">Жанр</button>'
                f'<div id="{p}tax-genre" class="zhd__dd-panel" hidden>{жанр_ссылки}</div></div>')
        if тип_блок:
            панели.append(
                f'<div class="zhd__dd" data-tax-panel="type">'
                f'<button type="button" class="zhd__dd-btn" data-tax-toggle="type" '
                f'aria-expanded="false" aria-controls="{p}tax-type">Тип</button>'
                f'<div id="{p}tax-type" class="zhd__dd-panel" hidden>{тип_блок}</div></div>')
        панели.append(
            f'<div class="zhd__dd" data-tax-panel="lists">'
            f'<button type="button" class="zhd__dd-btn" data-tax-toggle="lists" '
            f'aria-expanded="false" aria-controls="{p}tax-lists">Списки</button>'
            f'<div id="{p}tax-lists" class="zhd__dd-panel" hidden>'
            f'<a href="/collections/">Подборки</a>'
            f'<a href="/new/">Новое в каталоге</a>'
            f'</div></div>')
        ещё = '<a href="/catalog/">Весь каталог</a><a href="/search/">Поиск</a>'
        if годы:
            ещё += годы
        панели.append(
            f'<div class="zhd__dd" data-tax-panel="more">'
            f'<button type="button" class="zhd__dd-btn" data-tax-toggle="more" '
            f'aria-expanded="false" aria-controls="{p}tax-more">Ещё</button>'
            f'<div id="{p}tax-more" class="zhd__dd-panel" hidden>{ещё}</div></div>')
        return '<nav class="zhd__tax" aria-label="Таксономия каталога">' + "".join(панели) + "</nav>"

    def строка(self, запись: dict) -> str:
        """Компактная строка для «Новых серий»: без полного описания."""
        деталь = self.деталь(запись["slug"])
        изо = заглушка_постера(запись, "zr__none", "zr__img", 52, 76)
        части = [запись.get("kind"), запись.get("year")]
        мета = " · ".join(str(ч) for ч in части if ч)
        # Episode badge from last declared-available season when present.
        badge = ""
        seasons = деталь.get("seasons") or []
        if seasons:
            last = seasons[-1]
            avail = int(last.get("avail") or 0)
            n = int(last.get("n") or 0)
            if avail and n:
                badge = f'<span class="zr__badge">s{n}e{avail}</span>'
        return (f'<a class="zr" href="{запись["url"]}">'
                f'<span class="zr__p">{изо}</span>'
                f'<span class="zr__body"><span class="zr__t">{html.escape(запись["title"])}</span>'
                f'<span class="zr__m">{html.escape(мета)}</span></span>'
                f'{badge}</a>')

    def _рейтинги_колонка_b07(self, деталь: dict) -> str:
        """Independent source ratings: label always visible; missing ≠ 0."""
        by_key = {о["ключ"]: о for о in оценки_по_источникам(деталь)}
        # Fixed order; never invent a primary mega-score without policy.
        order = (
            ("shikimori", "Shikimori"),
            ("kp", "Кинопоиск"),
            ("imdb", "IMDb"),
        )
        items = []
        for key, label in order:
            о = by_key.get(key)
            if о:
                items.append(
                    f'<li data-rating-source="{html.escape(key)}">'
                    f'<span class="lab">{html.escape(label)}</span>'
                    f'<span class="val">{html.escape(о["значение"])}</span></li>'
                )
            else:
                items.append(
                    f'<li data-rating-source="{html.escape(key)}" data-rating-missing="1">'
                    f'<span class="lab">{html.escape(label)}</span>'
                    f'<span class="val" data-missing="1">—</span></li>'
                )
        return (
            f'<aside class="ztitle__rail" data-b07="ratings">'
            f'<ul class="ztitle__rail-ratings">{"".join(items)}</ul></aside>'
        )

    def тайтл(self, запись: dict, деталь: dict) -> str:
        """B07 passport: poster | text | ratings; verified description or true gap."""
        путь = f"/title/{запись['slug']}/"
        имя = запись["title"]
        # Exact join check: detail id/slug must match catalog item when present.
        det_slug = str(деталь.get("slug") or "").strip()
        det_id = str(деталь.get("id") or "").strip()
        item_id = str(запись.get("id") or "").strip()
        join_ok = (not det_slug or det_slug == запись["slug"]) and (
            not det_id or not item_id or det_id == item_id)
        сезоны = список_серий(деталь)
        сериал = bool(сезоны) or запись.get("kind") == "Сериал"
        звенья = [("/", self.имя), ("/catalog/", "Каталог"), ("", имя)]
        изо = заглушка_постера(запись, "zt__none", "zhead__img", 240, 360)
        описание = ""
        if join_ok:
            описание = (деталь.get("description") or деталь.get("short_description") or "").strip()
        if описание:
            описание_html = (
                f'<div class="ztitle__desc-panel" data-b07-desc="present">'
                f'<p class="ztitle__desc" id="title-desc">{html.escape(описание)}</p>'
                + ('<button type="button" class="ztitle__more" data-desc-toggle '
                   'aria-controls="title-desc" aria-expanded="false">'
                   'Развернуть</button>' if len(описание) > 220 else "")
                + "</div>")
        else:
            описание_html = (
                '<div class="ztitle__desc-panel" data-b07-desc="gap">'
                '<p class="ztitle__desc ztitle__desc--gap">'
                'Описание пока не передано источником</p></div>')
        rail = self._рейтинги_колонка_b07(деталь)
        orig = html.escape(str(деталь.get("original_name") or деталь.get("original_title") or ""))
        orig_html = f'<p class="ztitle__o">{orig}</p>' if orig else ""
        pills = ""
        жанры = деталь.get("genres") or []
        if жанры:
            pills = ('<div class="ztitle__pills">' + "".join(
                f"<span>{html.escape(str(г))}</span>" for г in жанры[:10]) + "</div>")
        факты = []
        год = запись.get("year") or деталь.get("year")
        if год:
            факты.append(("Год", str(год)))
        тип = запись.get("kind") or деталь.get("type")
        if тип:
            факты.append(("Тип", str(тип)))
        страны = деталь.get("countries") or []
        if страны:
            факты.append(("Страна", ", ".join(str(с) for с in страны[:3])))
        статус = деталь.get("status") or деталь.get("release_status")
        avail = sum(int(с.get("avail") or 0) for с in сезоны) if сезоны else 0
        total = sum(int(с.get("eps") or 0) for с in сезоны) if сезоны else 0
        if not статус and сезоны:
            if total and avail >= total:
                статус = "Вышел"
            elif avail:
                статус = "Онгоинг"
        if статус:
            факты.append(("Статус", str(статус)))
        if avail > 0:
            факты.append(("Доступно серий", str(avail)))
        if total > 0 and total != avail:
            факты.append(("Вышло серий", str(total)))
        длит = деталь.get("duration") or деталь.get("episode_duration") or деталь.get("runtime")
        if длит:
            факты.append(("Продолжительность", str(длит)))
        студии = деталь.get("studios") or деталь.get("studio") or деталь.get("voice_studios") or []
        if isinstance(студии, str):
            студии = [студии]
        if студии:
            факты.append(("Студия", ", ".join(str(с) for с in студии[:2])))
        meta_html = ""
        if факты:
            rows = "".join(
                f"<div><dt>{html.escape(k)}</dt><dd>{html.escape(v)}</dd></div>"
                for k, v in факты)
            meta_html = f'<dl class="ztitle__facts">{rows}</dl>'
        сезон_старт, эпизод_старт = выбрать_доступную_серию(деталь) if сезоны else (1, None)
        код, внутри = разметка_плеера(self, запись, деталь, сезон_старт, эпизод_старт)
        # Status lives in the player heading — never a detached right column.
        плеер = (
            f'<div class="ztitle-gap" aria-hidden="true"></div>'
            f'<section class="zpl" id="watch" data-b07-player="1" data-b08="player" '
            f'data-default-episode-policy="{html.escape(АНИМЕДИА_DEFAULT_EPISODE_POLICY)}" '
            f'data-default-episode-decision="{html.escape(АНИМЕДИА_DEFAULT_EPISODE_OWNER_DECISION)}" '
            f'data-default-s="{int(сезон_старт)}" '
            f'data-default-e="{"" if эпизод_старт is None else int(эпизод_старт)}">'
            f'<div class="zpl__h"><h2>Смотреть</h2>'
            f'<span data-player-status="{html.escape(код)}">'
            f'{html.escape(_подпись_плеера(код))}</span></div>'
            f'<div class="zpl__f" data-player data-state="{код}">{внутри}</div>'
            f"{_скрипты_плеера(код)}</section>")
        текущий = (сезон_старт, эпизод_старт) if эпизод_старт is not None else None
        блок_серий = (self._серии(запись, сезоны, текущий=текущий) if сериал else "")
        блок_похожих = self._блок_похожих(запись, деталь)
        блок_связей = self._франшиза(деталь)
        ad_title = ('<div class="zad-title" data-ad-slot="title-before-player" '
                    'data-ad-enabled="0"></div>')
        тело = (
            f'<div class="zwrap"><div class="ztitle" data-b07="passport" '
            f'data-title-join="{"ok" if join_ok else "mismatch"}">'
            f'<div class="ztitle__poster">{изо}</div>'
            f'<div class="ztitle__main"><div class="ztitle__head">'
            f'<div class="ztitle__head-text"><h1>{html.escape(имя)}</h1>{orig_html}</div>'
            f'</div>{pills}{meta_html}{описание_html}{блок_связей}'
            f'<div class="ztitle__actions"><a class="ztitle__cta" href="#watch">Смотреть</a></div>'
            f'</div>{rail}</div>{ad_title}{плеер}{блок_серий}{блок_похожих}</div>')
        разметка = self.schema_тайтла(запись, деталь, путь)
        # Gap copy must never become meta description.
        краткое = (описание[:180] if описание else
                   f"{имя}: {запись.get('kind') or ''} {запись.get('year') or ''}".strip())
        return self.оболочка(
            тело, f"{имя} — смотреть онлайн — {self.имя}", путь,
            описание=краткое, разметка=разметка, крошки=self.крошки(звенья),
            og=self.карточка_графа(
                тип="video.tv_show" if сериал else "video.movie",
                титул=имя, описание=краткое, путь=путь,
                изображение=запись.get("poster") or ""))

    def серия(self, запись: dict, деталь: dict, сезон: int, эпизод: int) -> str:
        """B09 exact episode page: compact H1 → player → nav → seasons → parent."""
        имя = запись["title"]
        путь = self.адрес_эпизода(запись["slug"], сезон, эпизод)
        title_path = f"/title/{запись['slug']}/"
        заголовок = f"{имя} — {сезон} сезон, {эпизод} серия"
        звенья = [("/", self.имя), ("/catalog/", "Каталог"),
                  (title_path, имя), ("", f"S{сезон}E{эпизод}")]
        изо = заглушка_постера(запись, "zt__none", "zhead__img", 96, 144)
        orig = str(деталь.get("original_name") or деталь.get("original_title") or "").strip()
        orig_html = f'<p class="aep-ctx__o">{html.escape(orig)}</p>' if orig else ""
        описание = (деталь.get("description") or деталь.get("short_description") or "").strip()
        desc_html = ""
        if описание:
            short = описание if len(описание) <= 220 else описание[:217].rstrip() + "…"
            desc_html = f'<p class="aep-ctx__desc">{html.escape(short)}</p>'
        код, внутри = разметка_плеера(self, запись, деталь, сезон, эпизод)
        плеер = (
            f'<section class="zpl" id="watch" data-b08="player" data-b09="player">'
            f'<div class="zpl__h"><h2>Смотреть</h2>'
            f'<span data-player-status="{html.escape(код)}">'
            f'{html.escape(_подпись_плеера(код))}</span></div>'
            f'<div class="zpl__f" data-player data-state="{код}" '
            f'data-season="{int(сезон)}" data-episode="{int(эпизод)}">{внутри}</div>'
            f"{_скрипты_плеера(код)}</section>")
        пред, след = границы_серии(деталь, сезон, эпизод)
        переход = ('<nav class="zepnav" aria-label="Соседние серии">'
                   + (f'<a href="{self.адрес_эпизода(запись["slug"], *пред)}" rel="prev">'
                      f'← S{пред[0]}E{пред[1]}</a>' if пред else "<span></span>")
                   + (f'<a href="{self.адрес_эпизода(запись["slug"], *след)}" rel="next">'
                      f'S{след[0]}E{след[1]} →</a>' if след else "<span></span>")
                   + "</nav>")
        сезоны = список_серий(деталь)
        avail = sum(int(с.get("avail") or 0) for с in сезоны) if сезоны else 0
        total = sum(int(с.get("eps") or 0) for с in сезоны) if сезоны else 0
        counts = []
        if avail > 0:
            counts.append(f"Доступно {avail} серий")
        if total > 0:
            counts.append(f"Вышло {total} серий")
        counts_html = (f'<p class="aep-ctx__meta">{html.escape(" · ".join(counts))}</p>'
                       if counts else "")
        # Compact parent context AFTER player/nav/seasons — not a second hero.
        ctx = (
            f'<aside class="aep-ctx" data-episode-context="1" data-b09="parent">'
            f'<div class="aep-ctx__poster">{изо}</div>'
            f'<div class="aep-ctx__main">'
            f'<p class="aep-ctx__ep">Контекст тайтла</p>'
            f'<a class="aep-ctx__back" href="{title_path}">{html.escape(имя)}</a>'
            f'{orig_html}{counts_html}{desc_html}'
            f'</div></aside>')
        блок_похожих = self._блок_похожих(запись, деталь, extra_attrs=' data-b09="recs"')
        тело = (
            f'<div class="zwrap aep-page" data-b09="exact">'
            f'<h1 class="zh zh--ep">{html.escape(заголовок)}</h1>'
            f'{плеер}{переход}'
            f'{self._серии(запись, сезоны, текущий=(сезон, эпизод))}'
            f'{ctx}{блок_похожих}</div>')
        разметка = self.schema_эпизода(запись, деталь, сезон, эпизод, путь)
        return self.оболочка(
            тело, f"{заголовок} — {self.имя}", путь,
            описание=(описание[:180] if описание else
                      f"{заголовок}: смотреть онлайн на витрине {self.имя}."),
            разметка=разметка, крошки=self.крошки(звенья),
            og=self.карточка_графа(
                тип="video.episode", титул=заголовок,
                описание=f"{заголовок}: смотреть онлайн на витрине {self.имя}.",
                путь=путь, изображение=запись.get("poster") or ""))

    def _франшиза(self, деталь: dict) -> str:
        """Prequel/sequel only from real relation IDs with working title routes."""
        сырое = деталь.get("relations") or деталь.get("related") or []
        if not isinstance(сырое, list) or not сырое:
            return ""
        ссылки = []
        for узел in сырое[:8]:
            if not isinstance(узел, dict):
                continue
            slug = str(узел.get("slug") or "").strip()
            kind = str(узел.get("relation") or узел.get("type") or "").strip()
            title = str(узел.get("title") or узел.get("name") or "").strip()
            if not slug or slug not in self.индекс.get("slug", {}):
                continue
            label = (f"{kind}: {title}" if kind and title else (title or slug))
            ссылки.append(f'<a href="/title/{html.escape(slug)}/">{html.escape(label)}</a>')
        if not ссылки:
            return ""
        return ('<nav class="ztitle__rels" aria-label="Связанные тайтлы">'
                + "".join(ссылки) + "</nav>")

    def верхняя_карусель(self, набор, *, snapshot: dict | None = None) -> str:
        """B02 weekly popular poster shelf — approved snapshot only.

        Empty / missing / <4 valid → 0 px (caller must omit). When rendered,
        exposes weekly digest attrs for oracle stability checks.
        """
        if not набор:
            return ""
        extra = ' data-weekly-popular="1"'
        if snapshot:
            extra += (
                f' data-popular-window="{html.escape(str(snapshot.get("window") or "weekly"))}"'
                f' data-popular-week="{html.escape(str(snapshot.get("week_key") or snapshot.get("week_id") or ""))}"'
                f' data-popular-snapshot="{html.escape(str(snapshot.get("snapshot_version") or snapshot.get("digest") or ""))}"'
                f' data-popular-updated="{html.escape(str(snapshot.get("updated_at") or snapshot.get("generated_at") or ""))}"'
                f' data-popular-algo="{html.escape(str(snapshot.get("algorithm_version") or ""))}"'
            )
        return (f'<section class="ahero" aria-label="Популярное за неделю"{extra}>'
                f'<div class="ahero__inner">{self.карусель("hero", набор)}</div></section>')

    def секция(self, ключ: str, титул: str, ссылка: str, набор, пусто: str) -> str:
        """Секция аниме-портала — плотная сетка, а не горизонтальная лента.

        Пустые полки скрываются целиком: эталон показывает только наполненные
        секции. При появлении данных в снимке секция вернётся сама.
        """
        if not набор:
            return ""
        ссылка_html = (f'<a href="{закодировать_запрос(ссылка)}">Весь раздел</a>'
                       if ссылка else "")
        шапка = f'<div class="zsec__h"><h2>{html.escape(титул)}</h2>{ссылка_html}</div>'
        if ключ in {"new_episodes", "new-episodes"}:
            тело = self.лента(набор)
            return f'<section class="zsec zsec--eps">{шапка}{тело}</section>'
        extra = ""
        if ключ in {"top-rated", "top", "top_rated"} and getattr(
                self, "_popular_snapshot", None):
            ps = self._popular_snapshot
            extra = (
                f' data-popular-window="{html.escape(str(ps.get("window") or ""))}"'
                f' data-popular-week="{html.escape(str(ps.get("week_key") or ""))}"'
                f' data-popular-snapshot="{html.escape(str(ps.get("snapshot_version") or ""))}"'
                f' data-popular-updated="{html.escape(str(ps.get("updated_at") or ""))}"'
            )
        return f'<section class="zsec"{extra}>{шапка}{self.плитки(набор)}</section>'

    def _серии(self, запись: dict, сезоны: list, текущий=None) -> str:
        """Компактные номерные кнопки 40–52px; Zona сохраняет «Серия N»."""
        if not сезоны:
            return ('<h2 class="zh zh--sm">Серии</h2>'
                    '<div class="zempty"><b>Состав сезонов не передан</b>'
                    "<p>Источник по этой записи ещё не отдал список серий. "
                    "Как только отдаст, он появится здесь.</p></div>")
        блоки = []
        for сезон in сезоны:
            ссылки = []
            for н in сезон["номера"]:
                доступна = н <= сезон["avail"]
                текущая = (текущий == (сезон["n"], н))
                атрибуты = ' aria-current="page"' if текущая else (
                    "" if доступна else
                    ' data-off aria-disabled="true" title="Серия пока недоступна"')
                ссылки.append(
                    f'<a href="{self.адрес_эпизода(запись["slug"], сезон["n"], н)}"'
                    f"{атрибуты}>{н}</a>")
            хвост = ("" if сезон["avail"] >= сезон["eps"]
                     else f" · доступно {сезон['avail']}")
            блоки.append(
                f'<section class="zsea"><div class="zsea__h">'
                f'<b>Сезон {сезон["n"]}</b>'
                f'<span>· {сезон["eps"]} серий{хвост}</span></div>'
                f'<div class="zeps">{"".join(ссылки)}</div></section>')
        return f'<h2 class="zh zh--sm">Серии</h2>{_склеить(блоки)}'

    def seo_блок(self, *, заголовок: str, текст: str) -> str:
        """Нижний SEO-текст перед footer: на mobile — details."""
        if not текст:
            return ""
        return (
            f'<aside class="zseo" aria-label="{html.escape(заголовок)}">'
            f'<div class="zseo__full"><h2>{html.escape(заголовок)}</h2>'
            f"<p>{html.escape(текст)}</p></div>"
            f"<details><summary>{html.escape(заголовок)}</summary>"
            f"<p>{html.escape(текст)}</p></details></aside>")

    def _блок_похожих(self, запись: dict, деталь: dict, *, extra_attrs: str = "") -> str:
        """B10 shelf: ≥4 valid candidates or 0 px (no invented recommendations)."""
        похожие = self.похожие(запись, деталь)
        meta = getattr(self, "_rec_meta", None) or {}
        if not похожие:
            return (
                f'<section class="zsec zsec--rel zsec--rel-gap" hidden '
                f'data-b10="recs" data-rec-state="empty" '
                f'data-rec-gap="{int(bool(RECOMMENDATIONS_DATA_GAP))}"'
                f'{extra_attrs}></section>')
        src = html.escape(str(meta.get("source") or ""))
        algo = html.escape(str(meta.get("algorithm_version") or ""))
        digest = html.escape(str(meta.get("digest") or ""))
        mdigest = html.escape(str(meta.get("membership_digest") or ""))
        gen = html.escape(str(meta.get("generated_at") or ""))
        fb = "1" if meta.get("fallback") else "0"
        return (
            f'<section class="zsec zsec--rel" data-b10="recs" data-rec-state="populated" '
            f'data-rec-source="{src}" data-rec-algorithm="{algo}" '
            f'data-rec-digest="{digest}" data-rec-membership="{mdigest}" '
            f'data-rec-generated="{gen}" data-rec-fallback="{fb}"'
            f'{extra_attrs}>'
            f'<h2 class="zh zh--sm">{html.escape(АНИМЕДИА_REC_TITLE)}</h2>'
            f'{self.плитки(похожие, вариант="recommendation")}</section>')

    def похожие(self, запись: dict, деталь: dict, сколько: int = АНИМЕДИА_REC_MAX_ITEMS) -> list:
        """B10 recommendations: approved snapshot → DETERMINISTIC_METADATA_RELATED_V1 → [].

        Never invent ratings, random order, personalization labels, or Top-100.
        Shelf hidden when fewer than АНИМЕДИА_REC_MIN_ITEMS valid candidates.
        """
        self._rec_meta = None
        seed = str(запись.get("slug") or "")
        if not seed:
            return []
        limit = max(АНИМЕДИА_REC_MIN_ITEMS, min(int(сколько or АНИМЕДИА_REC_MAX_ITEMS),
                                                 АНИМЕДИА_REC_MAX_ITEMS))
        approved = аниме_load_approved_recommendations(seed)
        items, meta = аниме_recommendations_from_approved(
            self.д.items, approved, min_items=АНИМЕДИА_REC_MIN_ITEMS, limit=limit)
        if items and meta:
            self._rec_meta = meta
            return items
        items, meta = аниме_build_deterministic_related(
            запись, деталь, self.д.items, self.деталь,
            min_items=АНИМЕДИА_REC_MIN_ITEMS, limit=limit)
        if items and meta:
            self._rec_meta = meta
            return items
        self._rec_meta = {
            "source": "none",
            "algorithm_version": "",
            "digest": "",
            "membership_digest": "",
            "generated_at": "",
            "fallback": False,
            "empty": True,
        }
        return []

    def подвал(self) -> str:
        """B14 footer: real inventory only, no invented contacts, no build marks.

        Прежний нижний бар печатал `source=…`, `runtime=…`, `build=…` в
        атрибуте и укороченный коммит на виду. Это внутренние опознавательные
        знаки: зрителю они ничего не говорят, а обходу сайта выдают версию
        сборки. Провенанс живёт в заголовках ответа и в манифесте релиза, и
        там он проверяется приёмкой — в разметке ему места нет.
        """
        домен = _аниме_домен(self.хост)
        contact = _аниме_контакты_html()
        legal = _аниме_legal_html()
        genres = "".join(
            f'<a href="/catalog/?genre={html.escape(код)}">{html.escape(имя)}</a>'
            for код, имя in (self.индекс.get("genre_names") or [])[:8])
        years = "".join(
            f'<a href="/catalog/?year={г}">{г}</a>'
            for г in (self.д.years or [])[:8])
        types = "".join(
            f'<a href="/catalog/?type={html.escape(t)}">{html.escape(t.upper())}</a>'
            for t in sorted((self.индекс.get("type") or {}).keys())[:6])
        contact_col = ""
        if contact or legal:
            contact_col = (
                f'<div class="zft__col"><b>Контакты и правовое</b>'
                f'{contact}{legal}</div>')
        # Отсутствие владельческого столбца — объявленный факт, а не тишина:
        # выдумать email, Telegram и правовые адреса нельзя, а скрыть пробел
        # молча значит потерять его из приёмки.
        пробел = "" if contact_col else ' data-b14-owner-gap="1"'
        столбцов = 4 if contact_col else 3
        return (
            f'<footer class="zft" data-b14="footer"{пробел} '
            f'data-b14-cols="{столбцов}"><div class="zft__inner">'
            '<div class="zft__cols">'
            f'<div class="zft__col"><b>{html.escape(self.имя)}</b>'
            f'<p class="zft__about">{html.escape(домен["footer_about"])}</p>'
            '<a href="/">Главная</a><a href="/catalog/">Каталог</a>'
            '<a href="/new/">Новое в каталоге</a>'
            '<a href="/collections/">Подборки</a></div>'
            f'<div class="zft__col"><b>Жанры</b>{genres or "<span>—</span>"}</div>'
            f'<div class="zft__col"><b>Годы и тип</b>{years}{types}</div>'
            f'{contact_col}'
            '</div>'
            f'<div class="zft__bar"><span>© {html.escape(self.имя)}</span></div>'
            "</div></footer>")

    # --- честное состояние данных -------------------------------------
    def полоса_готовности(self) -> str:
        г = self.готовность
        if г["готово"]:
            return ""
        return (
            '<div class="ast" role="status">'
            '<b>Каталог аниме источником не передан</b>'
            f'В снимке {г["записей_в_снимке"]} записей, и записей аниме среди них '
            f'{г["из_них_аниме"]}. Остальное — каталог другой витрины, и показывать '
            'его здесь нельзя: это была бы витрина аниме, собранная из обычных '
            'фильмов. Оформление, сетка и все разделы ниже работают — им не хватает '
            'только своих данных. Требуется действие владельца контентного '
            'конвейера: передать витрине аниме-каталог '
            '(<code>ANIMEDIA_DATA_READINESS=FAIL</code>).'
            '</div>')

    # --- каркас --------------------------------------------------------
    def оболочка(self, тело: str, титул: str, путь: str, *, актив: str = "",
                 описание: str = "", разметка: str = "", код: int = 200,
                 сверху: str = "", крошки: str = "", og: dict | None = None) -> str:
        домен = _аниме_домен(self.хост)
        нав = "".join(
            f'<a href="{закодировать_запрос(u)}"{ТЕКУЩАЯ_СТРАНИЦА if u == актив else ""}>{html.escape(t)}</a>'
            for u, t in self.се["нав"])
        схемы = "".join(f'<script type="application/ld+json">{р}</script>'
                        for р in ([разметка] if разметка else []))
        описание_мета = (f'<meta name="description" content="{html.escape(описание)}">'
                         if описание else "")
        канон = (f'<link rel="canonical" href="{html.escape(self.канон(путь))}">'
                 if путь and код == 200 else "")
        og_данные = dict(og or {})
        og_данные.setdefault("site_name", домен["og_site_name"])
        if путь and код == 200 and self.хост:
            og_данные.setdefault("url", self.канон(путь))
        # Profile в meta отражает доменный SEO-профиль, а не общий animedia-general.
        профиль_meta = домен["profile"]
        return f"""<!doctype html><html lang="ru" data-template-version="{ВЕРСИЯ}" data-template-family="{СЕМЕЙСТВО}" data-build-id="{СБОРКА}" data-design="animedia-portal" data-seo-profile="{профиль_meta}">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(титул)}</title>{описание_мета}{канон}
<meta name="robots" content="noindex, nofollow">
{_открытый_граф(og_данные)}
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
{_мета_версии().replace(f'content="{ПРОФИЛЬ}"', f'content="{профиль_meta}"', 1)}
<script>{СКРИПТ_АНИМЕДИА_ТЕМА_BOOT}</script>
<style>{self.се["стиль"]()}</style><script>{СКРИПТ_ПОСТЕРОВ}
{СКРИПТ_ЛЕНТ}
{СКРИПТ_АНИМЕДИА_ШАПКА}</script></head>
<body><a class="skip" href="#main">Перейти к содержимому</a>
<div class="zs">
<header class="zhd">
<div class="zhd__in">
{self.логотип()}
<nav id="zhd-nav" class="zhd__n" aria-label="Разделы">{нав}</nav>
{self.таксономия()}
<form class="zhd__s" action="/search/" method="get" role="search">
<label class="vh" for="q">Поиск по каталогу аниме</label>
<input id="q" name="q" placeholder="{html.escape(self.се["поиск"])}" autocomplete="off">
<button type="submit" aria-label="Найти">Найти</button></form>
<div class="zhd__actions">
<button class="zhd__theme" type="button" data-theme-toggle aria-pressed="false"
 aria-label="Переключить тему" title="Тема">◐</button>
<button class="zhd__menu" type="button" data-drawer-toggle aria-controls="zhd-drawer"
 aria-expanded="false" aria-label="Открыть меню">&#9776;</button>
</div>
</div>
<div class="zhd__backdrop" data-drawer-backdrop hidden></div>
<aside id="zhd-drawer" class="zhd__drawer" hidden aria-hidden="true" aria-label="Меню сайта">
<div class="zhd__drawer-h">
<span>Меню</span>
<button type="button" class="zhd__drawer-x" data-drawer-close aria-label="Закрыть меню">×</button>
</div>
<nav class="zhd__drawer-nav" aria-label="Разделы">{нав}</nav>
<div class="zhd__drawer-tax">{self.таксономия(префикс="d-")}</div>
</aside>
</header>
<div class="zmain">
<div class="zwrap">{_склеить([f'<div class="ztop"><div class="ztop__b">{сверху}</div></div>' if сверху else ""])}{крошки}
<main id="main">{тело}</main>
{self.подвал()}
</div></div></div>{схемы}</body></html>"""

    # --- главная -------------------------------------------------------
    def главная(self) -> str:
        занято: set = set()

        def оценка(з: dict) -> float:
            д = self.деталь(з["slug"])
            числа = []
            for v in (д.get("kinopoisk_rating"), д.get("imdb_rating")):
                try:
                    числа.append(float(v))
                except (TypeError, ValueError):
                    pass
            return max(числа) if числа else 0.0

        def свежесть(з: dict) -> str:
            return з.get("published_at") or ""

        def есть_серии(з: dict) -> bool:
            return bool(self.деталь(з["slug"]).get("seasons"))

        def выбрать(ключ, сколько: int = 24, условие=None, пул: int | None = None) -> list:
            подходящие = [з for з in self.д.items if условие is None or условие(з)]
            if пул:
                подходящие = sorted(подходящие, key=свежесть, reverse=True)[:пул]
            отобрано = []
            for з in sorted(подходящие, key=ключ, reverse=True):
                if з["slug"] in занято:
                    continue
                занято.add(з["slug"])
                отобрано.append(з)
                if len(отобрано) >= сколько:
                    break
            return отобрано

        # Ленты собираются контрактом коллекций.
        #
        # Прежний отбор имел два порока. Во-первых, «Онгоинги» и «Новые
        # эпизоды» пользовались одним и тем же правилом, а различались лишь
        # тем, что второй брал следующие двадцать четыре записи после первого:
        # из «Новых эпизодов» выпадали как раз самые новые. Во-вторых, ссылки
        # «Все →» вели в общий каталог и на `/new/`, то есть в выборки, не
        # совпадающие с лентой.
        #
        # Теперь у каждой ленты своя спецификация: фильтр, порядок и
        # собственный адрес полной страницы. Тот же ключ разрешает и ленту, и
        # страницу, поэтому их первые карточки совпадают.
        ПРИЧИНЫ = {
            "ongoing": ("Онгоинги", ""),
            "new_episodes": ("Недавно в каталоге", ""),
            "series_with_episodes": ("Сериалы с сериями", ""),
            "today_schedule": ("Расписание (нет дат выхода)", ""),
            "recently_added": ("Новые аниме на сайте", ""),
            "top_rated": ("Популярное за неделю", ""),
            "anime_movies": ("Аниме-фильмы", ""),
            "donghua": ("Дунхуа", ""),
            "classic": ("Классика", ""),
            "action": ("Экшен", ""),
            "short_series": ("Короткие сериалы", ""),
            "video_available": ("С видео", ""),
            "romance": ("Романтика", ""),
        }
        домен = _аниме_домен(self.хост)
        ПОРЯДОК = tuple(домен.get("home_shelves") or (
            "series_with_episodes", "recently_added", "top_rated",
            "anime_movies", "donghua"))
        снимок = Снимок.получить(self.д, self.п) if КОЛЛЕКЦИИ else None
        approved_weekly = аниме_load_approved_weekly_popular(
            site_id=str(self.хост or "animedia"))
        weekly_items, weekly_meta = аниме_weekly_shelf_from_approved(
            self.д.items, approved_weekly, min_items=4, limit=48)
        self._popular_snapshot = weekly_meta
        self._popular_data_gap = 0 if weekly_meta else 1
        ленты = []
        if снимок is not None:
            for ключ in ПОРЯДОК:
                if ключ == "top_rated" and not weekly_meta:
                    # B02: no approved weekly → do not invent «Популярное за неделю».
                    continue
                коллекция = КОЛЛЕКЦИИ.разрешить(ключ, снимок, СЕМЕЙСТВО, предел=48)
                if коллекция is None or not коллекция.items:
                    continue
                титул, причина = ПРИЧИНЫ.get(ключ, (коллекция.title, ""))
                набор = [к.raw for к in коллекция.items[:48]]
                if ключ == "top_rated" and weekly_meta:
                    набор = аниме_popular_apply(набор, weekly_meta) or аниме_popular_apply(
                        self.д.items, weekly_meta)
                ленты.append((ключ.replace("_", "-"), титул,
                              коллекция.view_all_path,
                              набор, причина))
        else:
            if weekly_meta:
                ленты = [
                    ("top", "Популярное за неделю", "/catalog/", weekly_items[:48], ""),
                ]
            # Catalog-addition shelves are B05 — not invented here without collections.
        куски = [self.полоса_готовности()]

        # B02: upper poster shelf = approved weekly only (≥4). Else 0 px + gap flag.
        if weekly_items and weekly_meta:
            куски.append(self.верхняя_карусель(weekly_items[:24], snapshot=weekly_meta))
        else:
            куски.append(
                '<div class="ahero ahero--gap" data-weekly-popular="0" '
                'data-popular-gap="1" hidden aria-hidden="true"></div>')
        куски.append(_аниме_telegram_promo_html())
        куски.append(f'<h1 class="zh zh--home">{html.escape(домен["h1"])}</h1>')
        куски.append(f'<p class="zsub zsub--home">{html.escape(домен["lead"])}</p>')
        # Empty ad slots must collapse to 0px (no Telegram/premium invent).
        куски.append('<div class="zad-home" data-ad-slot="home-after-hero" data-ad-enabled="0"></div>')
        # B03: provider_became_playable only — never catalog fallback.
        куски.append(self._блок_новых_серий_b03())
        # B05: verified catalog_added ledger only — never published_at shelf.
        куски.append(self._блок_нового_в_каталоге_b05())
        куски.append('<div class="zad-mid" data-ad-slot="home-mid-content" data-ad-enabled="0"></div>')
        # B06.1 compact filters (before remaining shelves).
        куски.append(self._блок_компактных_фильтров_b06())
        # B06.2 Top-100 — approved snapshot only.
        куски.append(self._блок_top100_b06())
        # Cross-shelf dedup. Weekly shelf slugs may reappear in lower grids only
        # when the lower shelf is not also the weekly popular block.
        очищенные = []
        герой_slug = {з["slug"] for з in weekly_items}
        занятые: set[str] = set(герой_slug)
        # B05 owns catalog freshness; B02 owns weekly; top_rated must not
        # reappear as a second ranked shelf without TopSnapshot.
        skip_keys = {
            "recently-added", "recently_added", "new-episodes", "new_episodes",
            "top-rated", "top_rated", "top",
        }
        for ключ, титул, ссылка, кандидаты, причина in ленты:
            norm = ключ.replace("_", "-")
            if ключ in skip_keys or norm in skip_keys:
                continue
            набор = []
            for з in кандидаты:
                slug = з.get("slug") or ""
                if not slug or slug in занятые:
                    continue
                набор.append(з)
                if len(набор) >= 12:
                    break
            for з in набор:
                занятые.add(з["slug"])
            if набор:
                очищенные.append((ключ, титул, ссылка, набор, причина))
            if len(очищенные) >= АНИМЕДИА_HOME_MAX_CATALOG_SHELVES:
                break
        куски += [self.секция(*л) for л in очищенные]
        # B06.4 collections home shelf (real specs only).
        куски.append(self._блок_подборок_home_b06())
        # B06.5/6: news/reviews/comments absent from registry → 0 px placeholders.
        куски.append(
            '<div class="ahome-editorial" data-b06="editorial" data-editorial="0" '
            'hidden aria-hidden="true"></div>')
        куски.append(
            '<div class="ahome-comments" data-b06="comments" data-comments="0" '
            'hidden aria-hidden="true"></div>')
        # B06.7 SEO/about after functional modules, before footer.
        куски.append(self.seo_блок(заголовок=домен["seo_home_title"],
                                   текст=домен["seo_home"]))
        return self.оболочка(
            _склеить(куски),
            домен["title_home"], "/", актив="/",
            описание=домен["description"],
            сверху="",
            og={"type": "website", "title": домен["title_home"],
                "description": домен["description"],
                "site_name": домен["og_site_name"]})

    # --- списки и поиск: причина пустоты называется на КАЖДОЙ странице ---
    def список(self, разд: str, зпр: dict) -> str:
        """Catalog / new episodes / collections with human H1 and episode rows."""
        if разд == "/new":
            return self._страница_новых_эпизодов(зпр)
        if разд == "/collections":
            return self.страница_коллекций(зпр)
        набор, выбрано = отбор(self.д, self.индекс, зпр, разд)
        raw_page = (зпр.get("page") or ["1"])[0]
        try:
            стр = int(raw_page or 1)
        except (TypeError, ValueError):
            стр = 0
        per = НА_СТРАНИЦЕ_1_1
        всего = (len(набор) + per - 1) // per if набор else 0
        if стр < 1 or (всего == 0 and стр > 1) or (всего > 0 and стр > всего):
            self._http_status = 404
            return self.не_найдено(разд + "/")
        self._http_status = 200
        кусок = набор[(стр - 1) * per: стр * per] if набор else []
        титул = self._заголовок_раздела(разд, выбрано)
        фильтры = self._фильтры_каталога(разд, выбрано, total=len(набор))
        pages_label = f"страница {стр} из {max(всего, 1)}" if всего else "совпадений нет"
        facet = ""
        if выбрано.get("genre"):
            facet = f' data-catalog-facet="genre:{html.escape(str(выбрано["genre"]))}"'
        elif выбрано.get("year"):
            facet = f' data-catalog-facet="year:{html.escape(str(выбрано["year"]))}"'
        elif выбрано.get("type"):
            facet = f' data-catalog-facet="type:{html.escape(str(выбрано["type"]))}"'
        тело = (f'<div class="zwrap zwrap--catalog" data-b11="catalog"{facet}>'
                f'<h1 class="zh">{html.escape(титул)}</h1>'
                f'<p class="zsub" data-b11-count="1">Найдено {len(набор)} · {pages_label}</p>'
                + фильтры
                + (self.плитки(кусок) if кусок else
                   '<div class="zempty" data-b11-empty="1"><b>Ничего не подошло</b>'
                   "<p>Под выбранные условия не попала ни одна запись.</p></div>")
                + (self.листалка(разд, выбрано, стр, всего) if всего > 1 else "")
                + "</div>")
        канон = разд + "/" + (запрос_строкой(выбрано, page=None) if any(
            выбрано.get(k) for k in ("genre", "year", "kind", "country", "type", "sort")) else "")
        return self.оболочка(тело, f"{титул} — {self.имя}", канон or (разд + "/"),
                             актив=разд + "/",
                             описание=f"{титул} на витрине {self.имя}.",
                             сверху="")

    def _заголовок_раздела(self, разд: str, выбрано: dict) -> str:
        год = выбрано.get("year")
        вид = выбрано.get("kind")
        жанр_код = выбрано.get("genre")
        жанр_имя = None
        if жанр_код:
            for код, имя in (self.индекс.get("genre_names") or []):
                if код == жанр_код:
                    жанр_имя = имя
                    break
        if разд == "/catalog":
            if вид and год:
                return f"{вид} {год} года"
            if год:
                return f"Аниме {год} года"
            if жанр_имя:
                return f"{жанр_имя[0].upper() + жанр_имя[1:]} аниме" if жанр_имя else "Каталог"
            if вид:
                return str(вид)
            return "Весь каталог"
        if разд == "/movies":
            return f"Аниме-фильмы{(' ' + str(год) + ' года') if год else ''}"
        if разд == "/series":
            return f"Сериалы{(' ' + str(год) + ' года') if год else ''}"
        return "Каталог"

    def _фильтры_каталога(self, разд: str, выбрано: dict, total: int | None = None) -> str:
        """Compact disclosure filters + chips (no year/genre button wall)."""
        idx = self.индекс or {}
        chips = []
        active_keys = ("kind", "type", "year", "genre", "country", "sort")

        def chip(label: str, clear_key: str) -> str:
            cleared = dict(выбрано)
            cleared[clear_key] = None
            href = разд + "/" + запрос_строкой(cleared, page=None)
            return (f'<a class="afilt__chip" href="{закодировать_запрос(href)}">'
                    f'{html.escape(label)} <span aria-hidden="true">×</span></a>')

        if выбрано.get("kind"):
            chips.append(chip(str(выбрано["kind"]), "kind"))
        if выбрано.get("type"):
            chips.append(chip(f"type:{выбрано['type']}", "type"))
        if выбрано.get("year"):
            chips.append(chip(str(выбрано["year"]), "year"))
        if выбрано.get("genre"):
            gname = выбрано["genre"]
            for код, имя in (idx.get("genre_names") or []):
                if код == выбрано["genre"]:
                    gname = имя
                    break
            chips.append(chip(str(gname), "genre"))
        if выбрано.get("country"):
            cname = выбрано["country"]
            for код, имя in (idx.get("country_names") or []):
                if код == выбрано["country"]:
                    cname = имя
                    break
            chips.append(chip(str(cname), "country"))
        if выбрано.get("sort"):
            sort_labels = {"title": "По названию", "rating": "По оценке",
                           "year": "По году", "date": "По свежести"}
            chips.append(chip(sort_labels.get(выбрано["sort"], str(выбрано["sort"])),
                              "sort"))

        def opts(title: str, pairs: list[tuple[str, str, int]], param: str) -> str:
            if not pairs:
                return ""
            links = []
            for value, label, count in pairs:
                href = разд + "/" + запрос_строкой(выбрано, **{param: value, "page": None})
                cur = ТЕКУЩАЯ_СТРАНИЦА if str(выбрано.get(param) or "") == str(value) else ""
                links.append(
                    f'<a href="{закодировать_запрос(href)}"{cur}>{html.escape(label)}'
                    f' <small>{count}</small></a>')
            return (f'<details class="afilt__dd"><summary>{html.escape(title)}</summary>'
                    f'<div class="afilt__opts">{"".join(links)}</div></details>')

        kind_pairs = [(к, к, sum(1 for з in self.д.items if з.get("kind") == к))
                      for к in (self.д.kinds or [])]
        type_pairs = []
        for tcode, slugs in sorted((idx.get("type") or {}).items()):
            type_pairs.append((tcode, tcode.upper(), len(slugs)))
        year_pairs = [(str(г), str(г),
                       sum(1 for з in self.д.items if з.get("year") == г))
                      for г in (self.д.years or [])]  # no hard cap
        genre_pairs = [(код, имя, len((idx.get("genre") or {}).get(код) or []))
                       for код, имя in (idx.get("genre_names") or [])]
        country_pairs = [(код, имя, len((idx.get("country") or {}).get(код) or []))
                         for код, имя in (idx.get("country_names") or [])]
        sort_pairs = [
            ("", "По свежести", total if total is not None else len(self.д.items)),
            ("title", "По названию", total if total is not None else len(self.д.items)),
            ("rating", "По оценке", total if total is not None else len(self.д.items)),
            ("year", "По году", total if total is not None else len(self.д.items)),
        ]

        reset = ""
        if any(выбрано.get(k) for k in active_keys):
            reset = f'<a class="afilt__reset" href="{разд}/">Сбросить фильтры</a>'
        chips_html = (f'<div class="afilt__chips" aria-label="Активные фильтры">'
                      f'{"".join(chips)}{reset}</div>' if (chips or reset) else "")
        body = (
            opts("Тип", kind_pairs, "kind")
            + opts("Формат", type_pairs, "type")
            + opts("Год", year_pairs, "year")
            + opts("Жанр", genre_pairs, "genre")
            + opts("Страна", country_pairs, "country")
            + opts("Сортировка", sort_pairs, "sort")
        )
        return (
            '<div class="afilt afilt--closed" data-afilt>'
            '<button type="button" class="afilt__open" data-afilt-open '
            'aria-expanded="false" aria-controls="afilt-panel">Фильтры</button>'
            f'<div class="afilt__panel" id="afilt-panel">{chips_html}'
            f'<div class="afilt__rows">{body}</div></div></div>'
        )

    def _provider_playable_events(self) -> list[dict]:
        """B03 feed: only provider_became_playable ledger rows with provenance.

        Without an approved ledger file the feed is empty
        (TRUE_PROVIDER_PLAYABLE_EVENT_COUNT=0). Catalog publish must never
        populate this list.
        """
        путь = Path(АНИМЕДИА_PROVIDER_PLAYABLE_PATH)
        if not путь.is_file():
            return []
        try:
            raw = json.loads(путь.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        events = raw.get("events") if isinstance(raw, dict) else raw
        if not isinstance(events, list):
            return []
        out = []
        seen = set()
        by_slug = {з.get("slug"): з for з in self.д.items if з.get("slug")}
        for ev in events:
            if not isinstance(ev, dict):
                continue
            if ev.get("event_type") not in {"provider_became_playable", None}:
                # Explicit non-playable types skipped; missing type allowed only
                # when provider_available_at is present (legacy fixture).
                if ev.get("event_type") and ev.get("event_type") != "provider_became_playable":
                    continue
            if not ev.get("provider_available_at"):
                continue
            slug = str(ev.get("title_slug") or ev.get("slug") or "")
            if not slug or slug not in by_slug:
                continue
            season = int(ev.get("season") or ev.get("season_number") or 0)
            episode = int(ev.get("episode") or ev.get("episode_number") or 0)
            if season < 1 or episode < 1:
                continue
            event_id = str(ev.get("event_id") or f"{slug}:s{season}e{episode}")
            dedupe = (slug, season, episode)
            if dedupe in seen:
                continue
            seen.add(dedupe)
            з = by_slug[slug]
            out.append({
                "event_id": event_id,
                "event_type": "provider_became_playable",
                "title_id": str(ev.get("title_id") or slug),
                "title_slug": slug,
                "slug": slug,
                "title": з.get("title") or slug,
                "season_number": season,
                "episode_number": episode,
                "season": season,
                "episode": episode,
                "provider_available_at": str(ev["provider_available_at"]),
                "published_at": str(ev["provider_available_at"]),
                "published_at_precision": "datetime",
                "event_kind": "provider_became_playable",
                "timestamp_semantics": "provider_available_at",
                "poster": з.get("poster") or "",
                "url": self.адрес_эпизода(slug, season, episode),
                "provenance": ev.get("provenance") or "ledger",
                "current_availability_revision": str(
                    ev.get("current_availability_revision") or ""),
            })
        out.sort(
            key=lambda e: (e.get("provider_available_at") or "", e.get("event_id") or ""),
            reverse=True,
        )
        return out

    def _блок_новых_серий_b03(self) -> str:
        """Home B03: populated provider feed or compact empty ≤96px."""
        events = self._provider_playable_events()
        self._provider_playable_count = len(events)
        if not events:
            return (
                f'<section class="zsec zsec--eps ahome-eps ahome-eps--empty" '
                f'data-b03="empty" data-provider-playable-count="0">'
                f'<div class="zsec__h"><h2>{АНИМЕДИА_ЭПИЗОД_ЗАГОЛОВОК}</h2></div>'
                f'<p class="ahome-eps__empty">{html.escape(АНИМЕДИА_ЭПИЗОД_EMPTY_COPY)}</p>'
                f'</section>'
            )
        per = АНИМЕДИА_ЭПИЗОД_НА_СТРАНИЦЕ
        rows = events[:per]
        feed = '<div class="aeps">' + "".join(
            self._разметка_эпизод_ряда(r) for r in rows) + "</div>"
        return (
            f'<section class="zsec zsec--eps ahome-eps" data-b03="populated" '
            f'data-provider-playable-count="{len(events)}">'
            f'<div class="zsec__h"><h2>{АНИМЕДИА_ЭПИЗОД_ЗАГОЛОВОК}</h2></div>'
            f'{feed}</section>'
        )

    def _available_episode_count(self, slug: str) -> int | None:
        """Sum of seasons[].avail — labeled «Доступно N серий», never «N серия»."""
        det = self.деталь(slug) or {}
        seasons = список_серий(det)
        if not seasons:
            return None
        total = sum(int(s.get("avail") or 0) for s in seasons)
        return total if total > 0 else None

    def _catalog_added_events(self) -> list[dict]:
        """B05 feed: verified catalog_added_at ledger only.

        Ambiguous catalog.items[].published_at must never populate this list.
        """
        путь = Path(АНИМЕДИА_CATALOG_ADDED_PATH)
        if not путь.is_file():
            return []
        try:
            raw = json.loads(путь.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        events = raw.get("events") if isinstance(raw, dict) else raw
        if not isinstance(events, list):
            return []
        out = []
        seen_ids: set[str] = set()
        seen_slugs: set[str] = set()
        by_slug = {з.get("slug"): з for з in self.д.items if з.get("slug")}
        for ev in events:
            if not isinstance(ev, dict):
                continue
            added = str(ev.get("catalog_added_at") or "").strip()
            if not added:
                continue
            slug = str(ev.get("title_slug") or ev.get("slug") or "")
            if not slug or slug not in by_slug:
                continue
            if slug in seen_slugs:
                continue
            event_id = str(ev.get("event_id") or f"catalog-added:{slug}:{added}")
            if event_id in seen_ids:
                continue
            seen_ids.add(event_id)
            seen_slugs.add(slug)
            з = by_slug[slug]
            if "T" in added:
                precision = "datetime"
            else:
                precision = "date"
            avail = self._available_episode_count(slug)
            out.append({
                "event_id": event_id,
                "event_kind": "catalog_added",
                "title_id": str(ev.get("title_id") or з.get("id") or slug),
                "title_slug": slug,
                "slug": slug,
                "title": з.get("title") or slug,
                "kind": з.get("kind"),
                "year": з.get("year"),
                "catalog_added_at": added,
                "catalog_added_at_precision": precision,
                "available_episode_count": avail,
                "poster": з.get("poster") or "",
                "url": з.get("url") or f"/title/{slug}/",
                "provenance": ev.get("provenance") or "catalog_added_ledger",
                "timestamp_semantics": "catalog_added_at (domain ledger; not published_at)",
            })
        out.sort(
            key=lambda e: (
                e.get("catalog_added_at") or "",
                e.get("event_id") or "",
            ),
            reverse=True,
        )
        return out

    def _плитка_catalog_added(self, row: dict) -> str:
        """Poster card for B05 — no episode-number chrome, no «N серия»."""
        запись = {
            "title": row["title"],
            "poster": row.get("poster"),
            "url": row["url"],
            "slug": row.get("slug") or "",
            "kind": row.get("kind"),
            "year": row.get("year"),
        }
        изо = заглушка_постера(запись, "zt__none", "zt__img", 190, 285)
        мета = " · ".join(
            str(ч) for ч in (row.get("kind"), row.get("year")) if ч)
        ts = _аниме_формат_времени_анонса(
            row.get("catalog_added_at") or "",
            row.get("catalog_added_at_precision") or "none")
        added = f'<span class="zt__added">Добавлено · {html.escape(ts)}</span>' if ts else ""
        avail_n = row.get("available_episode_count")
        avail = ""
        if isinstance(avail_n, int) and avail_n > 0:
            avail = f'<span class="zt__avail">Доступно {avail_n} серий</span>'
        return (
            f'<a class="zt zt--catalog-added" data-card-variant="catalog-added" '
            f'href="{html.escape(row["url"])}" '
            f'data-event-id="{html.escape(row.get("event_id") or "")}" '
            f'data-event-kind="catalog_added">'
            f'<span class="zt__p">{изо}</span>'
            f'<span class="zt__b"><span class="zt__t">{html.escape(row["title"])}</span>'
            f'<span class="zt__m">{html.escape(мета)}</span>'
            f'{added}{avail}</span></a>'
        )

    def _блок_нового_в_каталоге_b05(self) -> str:
        """Home B05: verified ledger shelf or 0 px + CATALOG_FRESHNESS_DATA_GAP."""
        events = self._catalog_added_events()
        self._catalog_added_count = len(events)
        self._catalog_freshness_gap = 0 if events else 1
        if not events:
            return (
                '<div class="zsec zsec--b05 zsec--b05-gap" data-b05="gap" '
                'data-catalog-freshness-gap="1" hidden aria-hidden="true"></div>'
            )
        rows = events[:АНИМЕДИА_CATALOG_ADDED_HOME_LIMIT]
        grid = (
            '<div class="zg zg--catalog-added" data-card-grid="catalog-added">'
            + "".join(self._плитка_catalog_added(r) for r in rows)
            + "</div>"
        )
        return (
            f'<section class="zsec zsec--b05" data-b05="populated" '
            f'data-catalog-freshness-gap="0" '
            f'data-catalog-added-count="{len(events)}">'
            f'<div class="zsec__h"><h2>{АНИМЕДИА_CATALOG_ADDED_H1}</h2>'
            f'<a href="/new/">Весь раздел</a></div>'
            f'{grid}</section>'
        )

    def _блок_компактных_фильтров_b06(self) -> str:
        """Home compact facet strip → catalog routes (no invented facets)."""
        links = [
            ('/catalog/', 'Весь каталог'),
            ('/catalog/?kind=Аниме', 'Сериалы'),
            ('/catalog/?kind=Аниме-фильм', 'Фильмы'),
        ]
        years = list(self.д.years or [])[:4]
        for г in years:
            links.append((f'/catalog/?year={г}', str(г)))
        genres = list(self.индекс.get("genre_names") or [])[:4]
        for код, имя in genres:
            links.append((f'/catalog/?genre={код}', имя))
        chips = "".join(
            f'<a href="{html.escape(href, quote=True)}">{html.escape(label)}</a>'
            for href, label in links)
        return (
            f'<nav class="ahome-filt" data-b06="filters" aria-label="Быстрые фильтры">'
            f'<div class="zstrip">{chips}</div></nav>'
        )

    def _блок_top100_b06(self) -> str:
        """Home Top-100 shelf from approved TopSnapshot only."""
        approved = аниме_load_approved_top100(site_id=str(self.хост or "animedia"))
        items, meta = аниме_top100_shelf_from_approved(
            self.д.items, approved, min_items=4, limit=АНИМЕДИА_TOP100_HOME_LIMIT)
        self._top100_data_gap = 0 if meta else 1
        if not items or not meta:
            return (
                '<div class="zsec zsec--top100 zsec--top100-gap" data-b06-top100="gap" '
                'data-top100-gap="1" hidden aria-hidden="true"></div>'
            )
        grid = self.плитки(items, вариант="top100-shelf")
        digest = html.escape(str(meta.get("digest") or ""))
        rev = html.escape(str(meta.get("snapshot_revision") or ""))
        return (
            f'<section class="zsec zsec--top100" data-b06-top100="populated" '
            f'data-top100-gap="0" data-top100-digest="{digest}" '
            f'data-top100-revision="{rev}">'
            f'<div class="zsec__h"><h2>Топ‑100</h2></div>'
            f'{grid}</section>'
        )

    def _блок_подборок_home_b06(self) -> str:
        """Home collections shelf — real collection specs only."""
        if КОЛЛЕКЦИИ is None:
            return ""
        снимок = Снимок.получить(self.д, self.п)
        if снимок is None:
            return ""
        карточки = []
        for спец in КОЛЛЕКЦИИ.спецификации(СЕМЕЙСТВО)[:4]:
            if not спец.доступна:
                continue
            данные = КОЛЛЕКЦИИ.разрешить(спец.collection_key, снимок, СЕМЕЙСТВО,
                                         предел=1)
            if данные is None or not данные.items:
                continue
            карточки.append(
                f'<a class="zhub__c" data-card-variant="collection-card" '
                f'href="{html.escape(спец.canonical_path)}">'
                f'<span class="zhub__t">{html.escape(данные.title)}</span>'
                f'<span class="zhub__m">{данные.total} записей</span></a>')
        if not карточки:
            return ""
        return (
            '<section class="zsec zsec--home-cols" data-b06="collections">'
            '<div class="zsec__h"><h2>Подборки</h2>'
            '<a href="/collections/">Весь раздел</a></div>'
            f'<div class="zhub zhub--home">{"".join(карточки)}</div></section>'
        )

    def _эпизод_события(self) -> list[dict]:
        """Deprecated catalog-publish helper — must NOT feed B03 or B05.

        Kept only for legacy unit assertions that document why published_at
        cannot be treated as catalog_added_at / episode air.
        """
        events = []
        seen = set()
        for з in self.д.items:
            slug = з.get("slug") or ""
            if not slug:
                continue
            det = self.деталь(slug)
            seasons = список_серий(det)
            if not seasons:
                continue
            last = None
            for s in seasons:
                if int(s.get("avail") or 0) >= 1:
                    last = s
            if last is None:
                continue
            season_n = int(last.get("n") or 1)
            episode_n = int(last.get("avail") or 0)
            if episode_n < 1:
                continue
            title_id = str(з.get("id") or det.get("id") or slug)
            source_episode_id = f"{title_id}:s{season_n}e{episode_n}"
            dedupe = (title_id, season_n, episode_n, source_episode_id)
            if dedupe in seen:
                continue
            seen.add(dedupe)
            published = str(з.get("published_at") or "").strip()
            if published and "T" in published:
                precision = "datetime"
            elif published:
                precision = "date"
            else:
                precision = "none"
            url = self.адрес_эпизода(slug, season_n, episode_n)
            events.append({
                "event_id": source_episode_id,
                "title_id": title_id,
                "title_slug": slug,
                "slug": slug,
                "title": з.get("title") or slug,
                "season_number": season_n,
                "episode_number": episode_n,
                "episode": episode_n,
                "season": season_n,
                "source_episode_id": source_episode_id,
                "published_at": published,
                "published_at_precision": precision,
                "event_kind": "catalog_publish",
                "timestamp_semantics": "catalog.items[].published_at (title add/update; not episode air; NOT provider_became_playable; NOT catalog_added_at)",
                "source_updated_at": str(з.get("updated_at") or ""),
                "poster": з.get("poster") or "",
                "playable_state": "playable" if det.get("playable") is True else "unknown",
                "source_provenance": "catalog.published_at+details.seasons.avail",
                "url": url,
                "kind": з.get("kind"),
                "year": з.get("year"),
            })
        events.sort(
            key=lambda e: (
                e.get("published_at") or "",
                e.get("source_episode_id") or "",
                e.get("event_id") or "",
            ),
            reverse=True,
        )
        return events

    def _эпизод_ряды(self, предел: int | None = None) -> list[dict]:
        """Backward-compatible alias over ``_эпизод_события``."""
        rows = self._эпизод_события()
        if предел is None:
            return rows
        return rows[: max(0, int(предел))]

    def _разобрать_страницу_эпизодов(self, зпр: dict, всего_страниц: int):
        """Return (page, error). error set → caller must 404 (no silent clamp)."""
        raw = (зпр.get("page") or ["1"])[0]
        if raw is None or str(raw).strip() == "":
            return 1, None
        try:
            стр = int(str(raw).strip())
        except (TypeError, ValueError):
            return None, "invalid"
        if стр < 1 or (всего_страниц >= 1 and стр > всего_страниц):
            return None, "out_of_range"
        return стр, None

    def _листалка_эпизодов(self, стр: int, всего: int) -> str:
        """Pagination for /new/ catalog-added archive."""
        if всего <= 1:
            return ""
        пункты = страницы(стр, всего)
        куски = []
        if стр <= 1:
            куски.append('<span aria-disabled="true">←</span>')
        else:
            prev = "/new/" if стр - 1 <= 1 else f"/new/?page={стр - 1}"
            куски.append(f'<a href="{prev}" rel="prev">←</a>')
        for н in пункты:
            if н is None:
                куски.append("<em>…</em>")
            elif н == стр:
                куски.append(f'<span aria-current="page">{н}</span>')
            else:
                href = "/new/" if н <= 1 else f"/new/?page={н}"
                куски.append(f'<a href="{href}">{н}</a>')
        if стр >= всего:
            куски.append('<span aria-disabled="true">→</span>')
        else:
            куски.append(f'<a href="/new/?page={стр + 1}" rel="next">→</a>')
        return f'<nav class="zpg" aria-label="Страницы новинок">{"".join(куски)}</nav>'

    def _разметка_эпизод_ряда(self, row: dict) -> str:
        """Provider-playable row only — episode number is a real episode, not avail total."""
        изо = заглушка_постера(
            {"title": row["title"], "poster": row.get("poster"), "url": row["url"]},
            "zr__none", "zr__img", 64, 80)
        kind = row.get("event_kind") or ""
        if kind == "provider_became_playable":
            ts = _аниме_формат_времени_анонса(
                row.get("provider_available_at") or row.get("published_at") or "",
                row.get("published_at_precision") or "datetime")
            meta = f"Доступно · {ts}" if ts else "Доступно у провайдера"
            season = int(row.get("season_number") or row.get("season") or 0)
            episode = int(row.get("episode_number") or row.get("episode") or 0)
            ep_lab = f"с{season} · серия" if season else "серия"
        else:
            # Must not surface catalog_publish as an episode air event.
            ts = _аниме_формат_времени_анонса(
                row.get("published_at") or "",
                row.get("published_at_precision") or "none")
            meta = f"Каталог · {ts}" if ts else "Каталог"
            episode = int(row.get("episode_number") or 0)
            ep_lab = "серия"
        return (
            f'<a class="aeps__row" data-card-variant="episode-row" href="{html.escape(row["url"])}" '
            f'data-event-id="{html.escape(row.get("event_id") or "")}" '
            f'data-event-kind="{html.escape(kind or "catalog_publish")}">'
            f'<span class="aeps__thumb">{изо}</span>'
            f'<span class="aeps__body"><span class="aeps__title">{html.escape(row["title"])}</span>'
            f'<span class="aeps__meta">{html.escape(meta)}</span></span>'
            f'<span class="aeps__ep"><span class="aeps__num">{episode}</span>'
            f'<span class="aeps__lab">{html.escape(ep_lab)}</span></span></a>')

    def _страница_новых_эпизодов(self, зпр: dict) -> str:
        """B05/B12 /new/: catalog_added ledger only — never published_at episode rows."""
        events = self._catalog_added_events()
        per = АНИМЕДИА_CATALOG_ADDED_PAGE_SIZE
        if not events:
            стр, err = self._разобрать_страницу_эпизодов(зпр, 1)
            if err or стр is None or стр != 1:
                # Only canonical /new/ exists while the ledger is absent.
                if (зпр.get("page") or ["1"])[0] not in (None, "", "1"):
                    self._http_status = 404
                    return self.не_найдено("/new/")
            self._http_status = 200
            тело = (
                f'<div class="zwrap anew-page" data-b05-page="gap">'
                f'<h1 class="zh">{АНИМЕДИА_CATALOG_ADDED_H1}</h1>'
                f'<div class="anew-empty" data-catalog-freshness-gap="1">'
                f'<b>Новинки каталога недоступны</b>'
                f'<p>{html.escape(АНИМЕДИА_CATALOG_ADDED_EMPTY)}</p></div></div>'
            )
            return self.оболочка(
                тело, f"{АНИМЕДИА_CATALOG_ADDED_H1} — {self.имя}", "/new/",
                актив="/new/",
                описание=АНИМЕДИА_CATALOG_ADDED_EMPTY)
        всего = max(1, (len(events) + per - 1) // per)
        стр, err = self._разобрать_страницу_эпизодов(зпр, всего)
        if err or стр is None:
            self._http_status = 404
            return self.не_найдено("/new/")
        self._http_status = 200
        кусок = events[(стр - 1) * per: стр * per]
        сетка = (
            '<div class="zg zg--catalog-added" data-card-grid="catalog-added">'
            + "".join(self._плитка_catalog_added(r) for r in кусок)
            + "</div>"
        )
        листалка = self._листалка_эпизодов(стр, всего)
        канон = "/new/" if стр == 1 else f"/new/?page={стр}"
        тело = (
            f'<div class="zwrap anew-page" data-b05-page="populated">'
            f'<h1 class="zh">{АНИМЕДИА_CATALOG_ADDED_H1}</h1>'
            f'<p class="zsub">Страница {стр} из {всего} · всего {len(events)}.</p>'
            + сетка + листалка + "</div>"
        )
        return self.оболочка(
            тело, f"{АНИМЕДИА_CATALOG_ADDED_H1} — {self.имя}", канон,
            актив="/new/",
            описание=АНИМЕДИА_CATALOG_ADDED_H1)

    # --- B12.2/B12.3: поиск --------------------------------------------
    @staticmethod
    def _адрес_поиска(q: str, стр: int = 1, *, для_html: bool = True) -> str:
        """Порядок параметров — q, затем page, как в паспорте B12.

        В атрибут href строка уходит экранированной: «&» между параметрами
        сам по себе ссылкой на сущность не является, и браузер разберёт его
        одинаково, но валидную разметку это возвращает без побочных эффектов.
        """
        база = f"/search/?q={q}"
        адрес = закодировать_запрос(база if стр <= 1 else f"{база}&page={стр}")
        return html.escape(адрес, quote=True) if для_html else адрес

    def _листалка_поиска(self, q: str, стр: int, всего: int) -> str:
        if всего <= 1:
            return ""
        куски = []
        if стр <= 1:
            куски.append('<span aria-disabled="true">←</span>')
        else:
            куски.append(f'<a href="{self._адрес_поиска(q, стр - 1)}" rel="prev">←</a>')
        for н in страницы(стр, всего):
            if н is None:
                куски.append("<em>…</em>")
            elif н == стр:
                куски.append(f'<span aria-current="page">{н}</span>')
            else:
                куски.append(f'<a href="{self._адрес_поиска(q, н)}">{н}</a>')
        if стр >= всего:
            куски.append('<span aria-disabled="true">→</span>')
        else:
            куски.append(f'<a href="{self._адрес_поиска(q, стр + 1)}" rel="next">→</a>')
        return f'<nav class="zpg" aria-label="Страницы поиска">{"".join(куски)}</nav>'

    def _блок_поиска(self, q: str) -> str:
        """Форма на самой странице: отправка и сброс без ухода в шапку."""
        сброс = ('<a class="asearch__clear" href="/search/" data-b12-clear="1">'
                 "Очистить</a>" if q else "")
        return (
            '<div class="asearch" data-b12="search-form">'
            '<form class="asearch__form" action="/search/" method="get" role="search">'
            f'<input id="asearch-q" name="q" type="search" value="{html.escape(q)}" '
            'aria-label="Поиск по каталогу" '
            'placeholder="Название на русском или в оригинале" autocomplete="off">'
            f'<button type="submit">Найти</button>{сброс}</form>'
            '<p class="asearch__hint">Ищем по русскому и оригинальному написанию, '
            "по синонимам и транслиту.</p></div>")

    def _страница_поиска(self, тело: str, титул: str, путь: str,
                         описание: str) -> str:
        # Полоса готовности каталога остаётся и на поиске: причина пустоты
        # должна называться на той же странице, где её видно.
        return self.оболочка(
            self.полоса_готовности() + f'<div class="zwrap asearch-page">{тело}</div>',
            титул, путь, актив="", описание=описание)

    def поиск(self, зпр: dict) -> str:
        """B12.2/B12.3 /search/: форма, выдача Search API, честная пустота.

        Шаблон не ранжирует: порядок приходит из Search API и сохраняется.
        Дедупликация — только по canonical_title_id, чтобы одна запись не
        занимала две карточки.
        """
        q = ((зпр.get("q") or [""])[0] or "").strip()
        форма = self._блок_поиска(q)
        заголовок_пусто = "Поиск"

        if not q:
            self._http_status = 200
            тело = (f'<h1 class="zh">{заголовок_пусто}</h1>{форма}'
                    '<div class="zempty" data-b12-state="empty">'
                    f"<b>{html.escape(АНИМЕДИА_SEARCH_EMPTY)}</b>"
                    "<p>Наберите название в строке выше. "
                    '<a href="/catalog/">Открыть каталог целиком</a></p></div>')
            return self._страница_поиска(
                тело, f"Поиск — {self.имя}", "/search/",
                "Поиск аниме, сериалов и фильмов по каталогу.")

        try:
            найдено = self.д.искать(q)
        except Exception:  # noqa: BLE001 — источник выдачи недоступен
            self._http_status = 200
            тело = (f'<h1 class="zh">«{html.escape(q)}»</h1>{форма}'
                    '<div class="zempty" data-b12-state="error">'
                    f"<b>{html.escape(АНИМЕДИА_SEARCH_ERROR)}</b>"
                    "<p>Попробуйте повторить запрос позже или "
                    '<a href="/catalog/">откройте каталог</a>.</p></div>')
            return self._страница_поиска(
                тело, f"Поиск — {self.имя}", self._адрес_поиска(q, для_html=False),
                "Поиск временно недоступен.")

        видели: set[str] = set()
        набор = []
        for з in найдено:
            ключ = str(з.get("canonical_title_id") or з.get("slug") or "")
            if ключ and ключ in видели:
                continue
            видели.add(ключ)
            набор.append(з)

        if not набор:
            self._http_status = 200
            тело = (f'<h1 class="zh">«{html.escape(q)}»</h1>{форма}'
                    '<div class="zempty" data-b12-state="zero" data-b12-count="0">'
                    f"<b>{html.escape(АНИМЕДИА_SEARCH_ZERO)}</b>"
                    f"<p>По запросу «{html.escape(q)}» ничего не нашлось. "
                    "Проверьте написание. "
                    '<a href="/catalog/">Открыть весь каталог</a></p></div>')
            return self._страница_поиска(
                тело, f"«{q}» — поиск — {self.имя}", self._адрес_поиска(q, для_html=False),
                f"По запросу «{q}» совпадений нет.")

        на_странице = АНИМЕДИА_SEARCH_PAGE_SIZE
        всего_страниц = max(1, (len(набор) + на_странице - 1) // на_странице)
        стр, ошибка = self._разобрать_страницу_эпизодов(зпр, всего_страниц)
        if ошибка or стр is None:
            self._http_status = 404
            return self.не_найдено("/search/")
        self._http_status = 200
        кусок = набор[(стр - 1) * на_странице: стр * на_странице]
        тело = (
            f'<h1 class="zh">«{html.escape(q)}»</h1>{форма}'
            f'<div data-b12-state="populated" data-b12-count="{len(набор)}" '
            f'data-b12-page="{стр}" data-b12-pages="{всего_страниц}">'
            f'<p class="zsub">Совпадений: {len(набор)}'
            + (f" · страница {стр} из {всего_страниц}" if всего_страниц > 1 else "")
            + "</p>"
            + self.плитки(кусок)
            + self._листалка_поиска(q, стр, всего_страниц)
            + "</div>")
        return self._страница_поиска(
            тело, f"«{q}» — поиск — {self.имя}", self._адрес_поиска(q, стр, для_html=False),
            f"Результаты поиска по запросу «{q}».")

    # --- B13: коллекции -------------------------------------------------
    #: Читаются общим маршрутом коллекции; у Lords и Zona остаются прежние.
    COLLECTION_PAGE_SIZE = АНИМЕДИА_COLLECTION_DETAIL_PAGE_SIZE
    COLLECTION_STRICT_PAGING = True

    def _карточки_коллекций(self) -> list[dict]:
        """Доступные коллекции контракта — по одной карточке на коллекцию.

        Коллекция, у которой в снимке нет записей, не показывается: так велит
        её `empty_policy`, и обещать раздел без содержимого нельзя. А вот
        прятать существующую коллекцию из-за совпадения коллажа нельзя тоже —
        тогда до неё не доведёт ни одна ссылка. Поэтому коллаж по возможности
        собирается из ещё не занятых постеров, а сама плитка остаётся.
        """
        снимок = Снимок.получить(self.д, self.п)
        if КОЛЛЕКЦИИ is None or снимок is None:
            return []
        занятые: set[str] = set()
        карточки: list[dict] = []
        видели: set[str] = set()
        for порядок, спец in enumerate(КОЛЛЕКЦИИ.спецификации(СЕМЕЙСТВО)):
            if not спец.доступна or спец.collection_key in видели:
                continue
            коллекция = КОЛЛЕКЦИИ.разрешить(спец.collection_key, снимок, СЕМЕЙСТВО,
                                            предел=48)
            if коллекция is None or not коллекция.items:
                continue
            видели.add(спец.collection_key)
            свежие = [к for к in коллекция.items
                      if к.poster and к.poster not in занятые][:4]
            if len(свежие) < 4:
                for к in коллекция.items:
                    if к in свежие or not к.poster:
                        continue
                    свежие.append(к)
                    if len(свежие) >= 4:
                        break
            for к in свежие:
                занятые.add(к.poster)
            карточки.append({
                "key": спец.collection_key,
                "order": порядок,
                "title": коллекция.title,
                "description": коллекция.description,
                "total": коллекция.total,
                "path": спец.canonical_path,
                "posters": [к.poster for к in свежие[:4] if к.poster],
            })
        return карточки

    @staticmethod
    def _сортировать_коллекции(карточки: list[dict], режим: str) -> list[dict]:
        """Порядок детерминирован при любом режиме: ключ добивает связи."""
        if режим == "size":
            return sorted(карточки, key=lambda к: (-к["total"], к["key"]))
        if режим == "name":
            return sorted(карточки, key=lambda к: (к["title"].casefold(), к["key"]))
        return sorted(карточки, key=lambda к: (к["order"], к["key"]))

    @staticmethod
    def _адрес_хаба(режим: str, стр: int = 1, *, для_html: bool = True) -> str:
        пары = []
        if режим != "contract":
            пары.append(f"sort={режим}")
        if стр > 1:
            пары.append(f"page={стр}")
        адрес = "/collections/" + (("?" + "&".join(пары)) if пары else "")
        return html.escape(адрес, quote=True) if для_html else адрес

    def _листалка_хаба(self, режим: str, стр: int, всего: int) -> str:
        if всего <= 1:
            return ""
        куски = []
        if стр <= 1:
            куски.append('<span aria-disabled="true">←</span>')
        else:
            куски.append(f'<a href="{self._адрес_хаба(режим, стр - 1)}" rel="prev">←</a>')
        for н in страницы(стр, всего):
            if н is None:
                куски.append("<em>…</em>")
            elif н == стр:
                куски.append(f'<span aria-current="page">{н}</span>')
            else:
                куски.append(f'<a href="{self._адрес_хаба(режим, н)}">{н}</a>')
        if стр >= всего:
            куски.append('<span aria-disabled="true">→</span>')
        else:
            куски.append(f'<a href="{self._адрес_хаба(режим, стр + 1)}" rel="next">→</a>')
        return f'<nav class="zpg" aria-label="Страницы подборок">{"".join(куски)}</nav>'

    def _переключатель_сортировки(self, режим: str) -> str:
        подписи = (("contract", "По контуру"), ("size", "По размеру"),
                   ("name", "По названию"))
        кнопки = "".join(
            (f'<span class="ahub__s is-on" aria-current="true">{html.escape(t)}</span>'
             if k == режим else
             f'<a class="ahub__s" href="{self._адрес_хаба(k)}">{html.escape(t)}</a>')
            for k, t in подписи)
        return ('<div class="ahub__sorts" data-b13="sort" role="group" '
                f'aria-label="Порядок подборок">{кнопки}</div>')

    @staticmethod
    def _сетка_коллекций(карточки: list[dict]) -> str:
        """Сетка из уже отобранных карточек. Пустых ячеек в ней не бывает."""
        плитки = "".join(
            f'<a class="zhub__c" data-card-variant="collection-card" '
            f'data-collection-key="{html.escape(к["key"])}" '
            f'href="{html.escape(к["path"])}">'
            f'<span class="zhub__g">'
            + "".join(
                f'<span class="zhub__p">'
                f'<img class="zhub__img" src="{html.escape(_адрес_постера(п) or "")}"'
                f' alt="" loading="lazy" width="120" height="180"></span>'
                for п in к["posters"])
            + "</span>"
            f'<span class="zhub__t">{html.escape(к["title"])}</span>'
            f'<span class="zhub__m">{к["total"]} записей</span>'
            f'<span class="zhub__d">{html.escape(к["description"])}</span>'
            "</a>"
            for к in карточки)
        return f'<div class="zhub" data-b13="hub">{плитки}</div>'

    def хаб_коллекций(self, зпр: dict | None = None) -> str:
        """B13.1 хаб: сетка 3/2/1, объявленный порядок, честная пустота."""
        if КОЛЛЕКЦИИ is None:
            return ('<div class="zempty" data-b13-state="blocked">'
                    '<b>Подборки недоступны</b>'
                    "<p>Контракт коллекций витрине не передан.</p></div>")
        карточки = self._карточки_коллекций()
        if not карточки:
            return ('<div class="zempty" data-b13-state="empty">'
                    '<b>Подборок пока нет</b>'
                    "<p>Ни одна коллекция контура не набрала записей в текущем "
                    "снимке. Наполнять их похожими тайтлами нельзя: подборка "
                    "без источника — это выдумка.</p></div>")
        зпр = зпр or {}
        режим = (зпр.get("sort") or ["contract"])[0] or "contract"
        if режим not in АНИМЕДИА_COLLECTIONS_SORTS:
            режим = "contract"
        return self._сетка_коллекций(self._сортировать_коллекции(карточки, режим))

    def страница_коллекций(self, зпр: dict) -> str:
        """B13.1 `/collections/`: H1, счётчик, порядок, страницы по 12."""
        карточки = self._карточки_коллекций()
        зпр = зпр or {}
        режим = (зпр.get("sort") or ["contract"])[0] or "contract"
        if режим not in АНИМЕДИА_COLLECTIONS_SORTS:
            режим = "contract"
        if not карточки:
            self._http_status = 200
            тело = ('<div class="zwrap"><h1 class="zh">Подборки аниме</h1>'
                    '<p class="zsub" data-b13-count="0">Доступно подборок: 0.</p>'
                    + self.хаб_коллекций(зпр) + "</div>")
            return self.оболочка(тело, f"Подборки — {self.имя}", "/collections/",
                                 актив="/collections/",
                                 описание=f"Подборки витрины {self.имя}.")
        на_странице = АНИМЕДИА_COLLECTIONS_PAGE_SIZE
        всего = len(карточки)
        всего_страниц = max(1, (всего + на_странице - 1) // на_странице)
        стр, ошибка = self._разобрать_страницу_эпизодов(зпр, всего_страниц)
        if ошибка or стр is None:
            self._http_status = 404
            return self.не_найдено("/collections/")
        self._http_status = 200
        упорядоченные = self._сортировать_коллекции(карточки, режим)
        кусок = упорядоченные[(стр - 1) * на_странице: стр * на_странице]
        плитки = self._сетка_коллекций(кусок)
        тело = (
            '<div class="zwrap"><h1 class="zh">Подборки аниме</h1>'
            f'<p class="zsub" data-b13-count="{всего}" data-b13-page="{стр}" '
            f'data-b13-pages="{всего_страниц}">Доступно подборок: {всего}'
            + (f' · страница {стр} из {всего_страниц}' if всего_страниц > 1 else "")
            + '. Карточки собраны из собственных постеров каталога.</p>'
            + self._переключатель_сортировки(режим)
            + плитки
            + self._листалка_хаба(режим, стр, всего_страниц)
            + "</div>")
        return self.оболочка(тело, f"Подборки — {self.имя}",
                             self._адрес_хаба(режим, стр, для_html=False),
                             актив="/collections/",
                             описание=f"Подборки витрины {self.имя}.")

    def коллекция(self, данные) -> str:
        """B13.2 страница коллекции: H1, счётчик, 24 на страницу, дедупликация."""
        на_странице = АНИМЕДИА_COLLECTION_DETAIL_PAGE_SIZE
        всего_страниц = max(1, (данные.total + на_странице - 1) // на_странице)
        видели: set[str] = set()
        записи = []
        for к in данные.items:
            сырое = к.raw if hasattr(к, "raw") else {}
            ключ = str(сырое.get("canonical_title_id") or сырое.get("slug")
                       or к.entity_id or "")
            if ключ and ключ in видели:
                continue
            видели.add(ключ)
            записи.append(сырое)
        листалка = ""
        if всего_страниц > 1:
            куски = []
            for н in страницы(данные.page, всего_страниц):
                if н is None:
                    куски.append("<em>…</em>")
                elif н == данные.page:
                    куски.append(f'<span aria-current="page">{н}</span>')
                else:
                    адрес = данные.canonical_path + ("" if н == 1 else f"?page={н}")
                    куски.append(f'<a href="{html.escape(адрес)}">{н}</a>')
            листалка = ('<nav class="zpg" aria-label="Страницы подборки">'
                        f'{"".join(куски)}</nav>')
        канон = данные.canonical_path + ("" if данные.page == 1
                                         else f"?page={данные.page}")
        тело = (
            f'<div class="zwrap acol-page" data-b13="detail" '
            f'data-collection-key="{html.escape(данные.collection_key)}">'
            f'<h1 class="zh">{html.escape(данные.title)}</h1>'
            f'<p class="zsub" data-b13-count="{данные.total}" '
            f'data-b13-page="{данные.page}" data-b13-pages="{всего_страниц}">'
            f'{html.escape(данные.description)} · {данные.total} записей'
            + (f' · страница {данные.page} из {всего_страниц}'
               if всего_страниц > 1 else "")
            + "</p>"
            + (self.плитки(записи) if записи else
               f'<div class="zempty" data-b13-state="empty">'
               f'<b>{html.escape(данные.title)}: пока пусто</b>'
               "<p>В текущем снимке под эту коллекцию не попала ни одна "
               "запись.</p></div>")
            + листалка + "</div>")
        return self.оболочка(тело, f"{данные.title} — {self.имя}", канон,
                             актив="/collections/",
                             описание=данные.description)

    # --- расписание ----------------------------------------------------
    def расписание(self) -> str:
        """B04/B13.3 honest empty: no fabricated times; route panel ≤260px."""
        тело = (
            '<div class="zwrap"><div class="asch-route" data-b04="empty">'
            '<h1 class="zh">Расписание</h1>'
            '<div class="asch-empty"><b>Расписание пока недоступно</b>'
            '<p>Источник плановых выходов ещё не подключен. '
            'Смотрите <a href="/new/">новое в каталоге</a> и '
            '<a href="/catalog/">каталог</a>.</p></div></div></div>')
        return self.оболочка(тело, f"Расписание — {self.имя}", "/schedule/",
                             актив="/schedule/",
                             описание="Расписание выхода серий аниме "
                             "(даты выхода пока не переданы источником).")


#: Вид Animedia появляется только у витрины, объявившей переработанное
#: оформление. Витрина на 1.0.2/1.1.0 исполняет прежнюю ветку и отдаёт прежние
#: байты — как и было до этой задачи.
ВИДЫ_1_1 = {"lords": ВидЛордс, "zona": ВидЗона}
if ОФОРМЛЕНИЕ_ПЕРЕРАБОТАННОЕ:
    ВИДЫ_1_1["animedia"] = ВидАнимедиа


def построить_индекс(данные: "Данные", подробности: Подробности) -> dict:
    """Индексы, которые дешевле построить один раз при старте.

    По slug — чтобы страница тайтла не искала запись перебором; по жанру и
    стране — чтобы filter query не перечитывал sidecar на каждый запрос.
    """
    по_slug = {з["slug"]: з for з in данные.items}
    по_жанру: dict[str, list] = {}
    по_стране: dict[str, list] = {}
    по_типу: dict[str, list] = {}
    имена: dict[str, str] = {}
    имена_стран: dict[str, str] = {}
    for slug, деталь in подробности.записи.items():
        if slug not in по_slug:
            continue
        запись = по_slug[slug]
        # Лучшая доступная оценка для sort=rating (без выдумки нулей).
        рейтинги = []
        for ключ in ("kinopoisk_rating", "imdb_rating"):
            try:
                рейтинги.append(float(деталь.get(ключ)))
            except (TypeError, ValueError):
                pass
        if рейтинги:
            запись["_rating"] = max(рейтинги)
        тип = str(деталь.get("type") or "").strip().lower()
        if тип in ("tv", "movie", "ova", "ona", "special"):
            по_типу.setdefault(тип, []).append(slug)
        жанры = деталь.get("genres") or []
        коды = list(деталь.get("genre_codes") or [])
        # Animedia sidecar часто отдаёт только русские имена без genre_codes.
        # Без кодов индекс жанров пуст, и любой ?genre= даёт «Найдено 0».
        # Код — латиница (как /genre/<code>/), имя остаётся русским для UI.
        if not коды and жанры:
            коды = [нормализовать(транслит(г)) for г in жанры]
            коды = [к for к in коды if к]
        for i, код in enumerate(коды):
            if not код:
                continue
            по_жанру.setdefault(код, []).append(slug)
            if i < len(жанры):
                имена.setdefault(код, жанры[i])
            else:
                имена.setdefault(код, код)
        for страна in (деталь.get("countries") or []):
            код = нормализовать(страна)
            if not код:
                continue
            по_стране.setdefault(код, []).append(slug)
            имена_стран.setdefault(код, страна)
        # Enrich search forms with sidecar original titles (catalog row may omit them).
        формы = list(запись.get("_формы") or [])
        for поле in ("original_title", "original_name"):
            сырье = деталь.get(поле)
            if not сырье:
                continue
            for кандидат in (нормализовать(сырье), нормализовать(транслит(сырье))):
                if кандидат and кандидат not in формы:
                    формы.append(кандидат)
        if формы:
            запись["_формы"] = формы
    порядок = sorted(имена.items(), key=lambda п: -len(по_жанру.get(п[0], ())))
    порядок_стран = sorted(имена_стран.items(),
                           key=lambda п: -len(по_стране.get(п[0], ())))
    return {"slug": по_slug, "genre": по_жанру, "genre_names": порядок,
            "country": по_стране, "country_names": порядок_стран,
            "type": по_типу}


class Обработчик(BaseHTTPRequestHandler):
    server_version = "site-factory-nova"
    данные: Данные = None  # проставляется при запуске
    подробности: Подробности = None  # то же: боковой файл подробностей
    индекс: dict = None  # индексы по slug и жанру

    def log_message(self, *a):
        pass

    def _отдать(self, тело: bytes, тип="text/html; charset=utf-8", код=200):
        # SEO-слой применяется здесь и только здесь: через эту точку уходит
        # каждый ответ витрины.
        try:
            тело = SEO.обогатить(
                тело, тип, хост=(self.headers.get("Host") or "").split(":")[0],
                путь=(self.path or "/"), counter=os.environ.get("LORDS_METRIKA_COUNTER", ""),
                имя_сайта=ИМЯ_ВИТРИНЫ,
                поиск="/search/?q={search_term_string}", код=код)
        except Exception:
            pass
        self.send_response(код)
        self.send_header("Content-Type", тип)
        self.send_header("Content-Length", str(len(тело)))
        self.send_header("X-Robots-Tag", "noindex, nofollow")
        self.send_header("X-Site-Factory-Template-Revision", МАНИФЕСТ["source_commit"])
        self.send_header("X-Site-Factory-Template", ШАБЛОН_СЕМЕЙСТВА)
        self.send_header("X-Site-Factory-Core", ЯДРО)
        self.send_header("X-Site-Factory-Profile", ПРОФИЛЬ)
        self.send_header("X-Site-Factory-Template-Family", СЕМЕЙСТВО)
        self.send_header("X-Site-Factory-Template-Version", ВЕРСИЯ)
        self.send_header("X-Site-Factory-Build-Id", СБОРКА)
        self.send_header("X-Site-Factory-Artifact-Sha256", МАНИФЕСТ["artifact_sha256"])
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(тело)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        д = self.данные
        разбор = urlparse(self.path)
        путь = unquote(разбор.path)
        зпр = parse_qs(разбор.query)

        if путь == "/__template_version":
            # Ядро, семейство, профиль и версия называются по отдельности:
            # один артефакт на все семейства допустим, но выдавать имя ядра за
            # имя шаблона витрины — нет.
            свод = dict(МАНИФЕСТ)
            свод["core_runtime"] = ЯДРО
            свод["family_template"] = ШАБЛОН_СЕМЕЙСТВА
            # Рассинхрон каталога и sidecar подробностей — частая причина
            # «плеера нет» на новинках главной. Поля читаются, значения секретов нет.
            свод["catalog_revision"] = getattr(self.данные, "revision", "") or ""
            свод["catalog_built_at"] = getattr(self.данные, "built_at", "") or ""
            свод["details_catalog_revision"] = getattr(
                self.подробности, "catalog_revision", "") or ""
            свод["details_catalog_built_at"] = getattr(
                self.подробности, "catalog_built_at", "") or ""
            свод["details_coverage"] = int(getattr(self.подробности, "покрытие", 0) or 0)
            свод["catalog_details_skew"] = bool(
                свод["catalog_revision"]
                and свод["details_catalog_revision"]
                and свод["catalog_revision"] != свод["details_catalog_revision"])
            return self._отдать(json.dumps(свод, ensure_ascii=False).encode("utf-8"),
                                "application/json; charset=utf-8")
        if путь == "/healthz":
            import hashlib
            import os as _os
            runtime_path = Path(__file__).resolve()
            try:
                runtime_sha = hashlib.sha256(runtime_path.read_bytes()).hexdigest()
            except OSError:
                runtime_sha = ""
            cat_path = Path(КАТАЛОГ_ФАЙЛ)
            det_path = Path(ПОДРОБНОСТИ_ФАЙЛ) if ПОДРОБНОСТИ_ФАЙЛ else None
            assets_path = runtime_path  # CSS/JS embedded in runtime for nova
            profile_blob = json.dumps({
                "profile": ПРОФИЛЬ, "family": СЕМЕЙСТВО, "template": ШАБЛОН_СЕМЕЙСТВА,
                "host_profiles": sorted(АНИМЕДИА_ДОМЕНЫ.keys()) if СЕМЕЙСТВО == "animedia" else [],
            }, ensure_ascii=False, sort_keys=True).encode("utf-8")
            # Provider projection + ratings digests from the actually opened details file.
            provider_h = hashlib.sha256()
            ratings_h = hashlib.sha256()
            try:
                if det_path and det_path.is_file():
                    det_obj = json.loads(det_path.read_text(encoding="utf-8"))
                    for slug, row in sorted((det_obj.get("details") or {}).items()):
                        for src in (row.get("sources") or []):
                            if isinstance(src, dict):
                                provider_h.update(
                                    f"{slug}|{src.get('provider')}|{src.get('source_id')}|"
                                    f"{src.get('availability_status')}\n".encode())
                        rbs = row.get("ratings_by_source") or {}
                        if isinstance(rbs, dict):
                            for sk in sorted(rbs.keys()):
                                ratings_h.update(
                                    f"{slug}|{sk}|{json.dumps(rbs[sk], ensure_ascii=False, sort_keys=True, default=str)}\n".encode()
                                )
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                pass
            player_cfg = None  # reserved; site player json resolved below
            # Prefer site player json next to catalog naming convention.
            site_hint = ""
            try:
                # e.g. /srv/lords/.frontend/animedia-01-catalog.json → animedia-01
                name = cat_path.name
                if name.endswith("-catalog.json"):
                    site_hint = name[: -len("-catalog.json")]
            except Exception:
                site_hint = ""
            player_path = Path(f"/srv/lords/.frontend/player-{site_hint}.json") if site_hint else None
            tmpl_path = Path(f"/srv/lords/.frontend/template-manifest-{site_hint}.json") if site_hint else None

            def _dig(p):
                try:
                    return hashlib.sha256(Path(p).read_bytes()).hexdigest() if p and Path(p).is_file() else ""
                except OSError:
                    return ""

            тело = {
                "ok": True,
                "pid": _os.getpid(),
                "process_start_time": getattr(self.server, "started_at", ""),
                "runtime_path": str(runtime_path),
                "runtime_sha256": runtime_sha,
                "assets_sha256": runtime_sha,
                "build_id": СБОРКА,
                "release_id": СБОРКА,
                "source_commit": МАНИФЕСТ.get("source_commit", ""),
                "runtime_commit": МАНИФЕСТ.get("runtime_commit", ""),
                "profile": ПРОФИЛЬ,
                "profile_digest": hashlib.sha256(profile_blob).hexdigest(),
                "catalog_path": str(cat_path),
                "catalog_digest": _dig(cat_path),
                "details_path": str(det_path) if det_path else "",
                "details_digest": _dig(det_path) if det_path else "",
                "provider_projection_digest": provider_h.hexdigest(),
                "ratings_snapshot_digest": ratings_h.hexdigest(),
                "player_config_digest": _dig(player_path) if player_path else "",
                "template_manifest_digest": _dig(tmpl_path) if tmpl_path else "",
                "catalog_revision": getattr(self.данные, "revision", "") or "",
                "details_revision": getattr(self.подробности, "catalog_revision", "") or "",
                "artifact_sha256": МАНИФЕСТ.get("artifact_sha256", ""),
                "runtime_digest_match": bool(
                    МАНИФЕСТ.get("artifact_sha256")
                    and runtime_sha
                    and МАНИФЕСТ.get("artifact_sha256") == runtime_sha
                ),
            }
            return self._отдать(json.dumps(тело, ensure_ascii=False).encode("utf-8"),
                                "application/json; charset=utf-8")
        if путь == "/assets/nova.webmanifest":
            м = json.dumps({"name": ИМЯ_ВИТРИНЫ, "template": ШАБЛОН_СЕМЕЙСТВА,
                            "core": ЯДРО, "family": СЕМЕЙСТВО, "profile": ПРОФИЛЬ,
                            "revision": РЕВИЗИЯ, "display": "standalone"}, ensure_ascii=False)
            return self._отдать(м.encode(), "application/manifest+json")
        if путь == "/sitemap.xml" or re.fullmatch(r"/sitemap-\d+\.xml", путь):
            if not SITEMAP_DIR:
                return self._отдать(b"", "text/plain; charset=utf-8", код=404)
            try:
                данные = (Path(SITEMAP_DIR) / путь.lstrip("/")).read_bytes()
            except OSError:
                return self._отдать(b"", "text/plain; charset=utf-8", код=404)
            return self._отдать(данные, "application/xml; charset=utf-8")
        if путь.startswith("/poster/"):
            код, тело, тип = отдать_постер(путь[len("/poster/"):])
            if код != 200:
                return self._отдать(тело or b"", тип or "text/plain", код=код)
            self.send_response(200)
            self.send_header("Content-Type", тип)
            self.send_header("Content-Length", str(len(тело)))
            self.send_header("Cache-Control", "public, max-age=86400")
            self.send_header("X-Robots-Tag", "noindex, nofollow")
            self.end_headers()
            self.wfile.write(тело)
            return
        if путь == "/robots.txt":
            return self._отдать(b"User-agent: *\nDisallow: /\n", "text/plain; charset=utf-8")
        if путь in ("/favicon.svg", "/favicon.ico"):
            # Значок рисуется здесь, а не лежит файлом: браузер запрашивает его
            # на каждой витрине, и без ответа в консоли посетителя стоит 404 на
            # каждой странице. Цвет берётся у семейства — значок и есть первое,
            # по чему вкладки различают.
            цвет = (СЕМЕЙСТВА_1_1.get(СЕМЕЙСТВО) or СЕМЕЙСТВА_1_1["lords"])["токены"]["acc"]
            метка = (СЕМЕЙСТВА_1_1.get(СЕМЕЙСТВО) or СЕМЕЙСТВА_1_1["lords"])["метка"]
            значок = (
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
                f'<rect width="32" height="32" rx="6" fill="{цвет}"/>'
                '<text x="16" y="22" font-family="system-ui,sans-serif" font-size="16" '
                f'font-weight="700" fill="#fff" text-anchor="middle">{html.escape(метка)}</text>'
                "</svg>")
            return self._отдать(значок.encode("utf-8"), "image/svg+xml")

        # Оформление 1.1.0 обслуживает свои маршруты целиком, включая страницы
        # произведений. Провала в старый статический релиз здесь нет: именно он
        # и отвечал 404 на каждую карточку витрины, чей снимок ушёл вперёд.
        if ОФОРМЛЕНИЕ_НОВОЕ:
            if len(путь) > 1 and not путь.endswith("/"):
                # Один документ — один адрес, и исправляется он РОВНО одним
                # переходом. 308, а не 301: метод запроса обязан сохраниться.
                цель = путь + "/" + (("?" + разбор.query) if разбор.query else "")
                self.send_response(308)
                self.send_header("Location", цель)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            return self.маршрут_1_1(путь, зпр)

        if путь == "/":
            return self._отдать(self.главная().encode("utf-8"))
        if путь.rstrip("/") in ("/catalog", "/new", "/collections"):
            return self._отдать(self.список(путь, зпр).encode("utf-8"))
        if путь.rstrip("/") == "/search":
            return self._отдать(self.поиск(зпр).encode("utf-8"))
        if путь.rstrip("/") == "/schedule":
            return self._отдать(self.расписание().encode("utf-8"))

        # Всё остальное — из прежней витрины без изменений: там плеер.
        if ВЕРХОВОЙ:
            return self.наверх(разбор)
        return self.старое(путь)

    # --- маршруты оформления 1.1.0 ---------------------------------------
    #
    # Адрес строится только из канонической карты: `/title/<slug>/`,
    # `/title/<slug>/season-<n>/`, `/title/<slug>/season-<n>/episode-<m>/`.
    # Ни позиция записи в выгрузке, ни порядок обхода в него не входят —
    # именно поэтому один и тот же slug всегда даёт один и тот же адрес, а
    # пересборка каталога адресов не переставляет.
    МАРШРУТ_ТАЙТЛА = re.compile(
        r"^/title/(?P<slug>[^/]{1,200}?)"
        r"(?:/season-(?P<s>\d{1,3})(?:/episode-(?P<e>\d{1,5}))?)?/$")
    МАРШРУТ_ЖАНРА = re.compile(r"^/genre/(?P<code>[a-z0-9_-]{1,40})/$")
    МАРШРУТ_ГОДА = re.compile(r"^/year/(?P<year>\d{4})/$")
    МАРШРУТ_СТРАНЫ = re.compile(r"^/country/(?P<code>[a-z0-9_-]{1,40})/$")
    # B11: /catalog/{facet}/ — year | type | genre code (query form remains canonical combo).
    МАРШРУТ_КАТАЛОГ_ФАСЕТ = re.compile(
        r"^/catalog/(?P<facet>[a-z0-9_-]{1,40})/$")
    #: Полная страница коллекции. Тот же ключ, что и у ленты на главной, —
    #: именно поэтому первые карточки страницы совпадают с лентой.
    МАРШРУТ_КОЛЛЕКЦИИ = re.compile(r"^/collection/(?P<key>[a-z0-9_]{1,40})/$")

    #: Адреса, существовавшие до 1.1.0. Каждый уводит РОВНО одним переходом на
    #: действующий раздел: молча отдавать по ним 404 значило бы терять ссылки,
    #: которые уже кем-то сохранены.
    ПРЕЖНИЕ_АДРЕСА = {"/schedule/": "/new/", "/genres/": "/catalog/"}

    #: Чистые kind-маршруты (Lords). Query остаётся каноном для комбинаций.
    МАРШРУТЫ_ВИДА = {
        "/movies": "Фильм",
        "/series": "Сериал",
        "/animation": "Мультфильм",
    }

    #: Исторические slug → канонический. 301 с сохранением season/episode.
    #: Измерено: …domokhozyaykoy 404, live slug …domohozyaykoy.
    SLUG_ALIASES = {
        "sudmedekspert-stavshaya-domokhozyaykoy":
            "sudmedekspert-stavshaya-domohozyaykoy",
    }

    def вид(self) -> Вид:
        описание = СЕМЕЙСТВА_1_1.get(СЕМЕЙСТВО) or СЕМЕЙСТВА_1_1["lords"]
        класс = ВИДЫ_1_1.get(описание["вид"], ВидЛордс)
        экземпляр = класс(описание, self.данные, self.подробности, self.индекс,
                          ИМЯ_ВИТРИНЫ)
        # Канонический адрес берётся из запроса, а не из настройки: витрина
        # отвечает на том имени, по которому к ней пришли, и подставлять сюда
        # другое значило бы объявлять канонической чужую страницу.
        экземпляр.хост = (self.headers.get("Host") or "").split(":")[0]
        return экземпляр

    def _переход(self, цель: str):
        self.send_response(308)
        self.send_header("Location", цель)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def маршрут_1_1(self, путь: str, зпр: dict):
        в = self.вид()
        # Расписание — собственный раздел семейства, а не синоним новинок.
        # Переход на /new/ остаётся для тех семейств, у которых своего
        # расписания нет: подменять раздел соседним честнее, чем отдавать 404,
        # но только там, где раздела действительно не существует.
        if путь.rstrip("/") == "/schedule" and hasattr(в, "расписание"):
            return self._отдать(в.расписание().encode("utf-8"))
        if путь in self.ПРЕЖНИЕ_АДРЕСА:
            return self._переход(self.ПРЕЖНИЕ_АДРЕСА[путь])
        обрезанный = путь.rstrip("/") or "/"
        if обрезанный == "/":
            return self._отдать(в.главная().encode("utf-8"))
        # Clean kind routes (Lords profile surfaces). Canonical = own path
        # (/movies/, /series/, /animation/), not a silent rewrite to /catalog/.
        if обрезанный in self.МАРШРУТЫ_ВИДА:
            kind = self.МАРШРУТЫ_ВИДА[обрезанный]
            зпр = dict(зпр)
            зпр["kind"] = [kind]
            return self._отдать(в.список(обрезанный, зпр).encode("utf-8"))
        if обрезанный in ("/catalog", "/new"):
            тело = в.список(обрезанный, зпр)
            код = int(getattr(в, "_http_status", 200) or 200)
            return self._отдать(тело.encode("utf-8"), код=код)
        фасет = self.МАРШРУТ_КАТАЛОГ_ФАСЕТ.match(путь)
        if фасет:
            token = фасет.group("facet")
            зпр = dict(зпр)
            resolved = False
            if token.isdigit() and len(token) == 4:
                зпр["year"] = [token]
                resolved = True
            elif token in (self.индекс.get("type") or {}):
                зпр["type"] = [token]
                resolved = True
            elif token in (self.индекс.get("genre") or {}):
                зпр["genre"] = [token]
                resolved = True
            else:
                # Try translit-normalized genre match against index keys.
                for ключ in (token, нормализовать(token), нормализовать(транслит(token))):
                    if ключ and ключ in (self.индекс.get("genre") or {}):
                        зпр["genre"] = [ключ]
                        resolved = True
                        break
            if not resolved:
                return self._отдать(в.не_найдено(путь).encode("utf-8"), код=404)
            тело = в.список("/catalog", зпр)
            код = int(getattr(в, "_http_status", 200) or 200)
            return self._отдать(тело.encode("utf-8"), код=код)
        if обрезанный == "/collections":
            if СЕМЕЙСТВО == "lords" and hasattr(в, "хаб_подборок"):
                return self._отдать(в.хаб_подборок().encode("utf-8"))
            return self._отдать(в.список(обрезанный, зпр).encode("utf-8"))
        if обрезанный == "/search":
            return self._отдать(в.поиск(зпр).encode("utf-8"))
        коллекция = self.МАРШРУТ_КОЛЛЕКЦИИ.match(путь)
        if коллекция is not None:
            return self.маршрут_коллекции(в, коллекция.group("key"), путь, зпр)

        год = self.МАРШРУТ_ГОДА.match(путь)
        if год:
            зпр = dict(зпр)
            зпр["year"] = [год.group("year")]
            return self._отдать(в.список("/catalog", зпр).encode("utf-8"))
        страна = self.МАРШРУТ_СТРАНЫ.match(путь)
        if страна:
            код = страна.group("code")
            if код not in (self.индекс.get("country") or {}):
                return self._отдать(в.не_найдено(путь).encode("utf-8"), код=404)
            зпр = dict(зпр)
            зпр["country"] = [код]
            return self._отдать(в.список("/catalog", зпр).encode("utf-8"))

        жанр = self.МАРШРУТ_ЖАНРА.match(путь)
        if жанр:
            код = жанр.group("code")
            if код not in self.индекс["genre"]:
                return self._отдать(в.не_найдено(путь).encode("utf-8"), код=404)
            # Канон жанра для Lords — path /genre/<code>/; комбинации остаются query.
            if СЕМЕЙСТВО == "lords":
                зпр = dict(зпр)
                зпр["genre"] = [код]
                return self._отдать(в.список("/catalog", зпр).encode("utf-8"))
            return self._переход(f"/catalog/?genre={код}")
        совпало = self.МАРШРУТ_ТАЙТЛА.match(путь)
        if совпало:
            return self.маршрут_тайтла(в, совпало, путь)
        return self._отдать(в.не_найдено(путь).encode("utf-8"), код=404)

    def маршрут_коллекции(self, в: Вид, ключ: str, путь: str, зпр: dict):
        """Полная страница коллекции — из той же спецификации, что и лента.

        Никакой второй реализации фильтра здесь нет: вызывается та же функция
        `разрешить`, только без предела и со страницей. Поэтому первые карточки
        страницы совпадают с лентой по составу и порядку, а `data_revision` у
        них один.
        """
        if КОЛЛЕКЦИИ is None:
            return self._отдать(в.не_найдено(путь).encode("utf-8"), код=404)
        снимок = Снимок.получить(в.д, self.подробности)
        спец = КОЛЛЕКЦИИ.спецификация(СЕМЕЙСТВО, ключ)
        if спец is None or снимок is None:
            return self._отдать(в.не_найдено(путь).encode("utf-8"), код=404)
        # Размер страницы и строгость разбора спрашиваются у вида: у семейств
        # они разные, а общий маршрут не должен знать про конкретное семейство.
        # Значения по умолчанию сохраняют прежнее поведение Lords и Zona.
        на_странице = getattr(в, "COLLECTION_PAGE_SIZE", 60)
        строго = getattr(в, "COLLECTION_STRICT_PAGING", False)
        сырая = (зпр.get("page") or ["1"])[0]
        try:
            номер = int(str(сырая).strip() or 1)
        except (TypeError, ValueError):
            if строго:
                return self._отдать(в.не_найдено(путь).encode("utf-8"), код=404)
            номер = 1
        if номер < 1:
            if строго:
                return self._отдать(в.не_найдено(путь).encode("utf-8"), код=404)
            номер = 1
        данные = КОЛЛЕКЦИИ.разрешить(ключ, снимок, СЕМЕЙСТВО, страница=номер,
                                     на_странице=на_странице)
        if данные is None:
            return self._отдать(в.не_найдено(путь).encode("utf-8"), код=404)
        if строго and номер > 1 and not данные.items:
            # Страница за концом коллекции — настоящая 404, а не пустая полка.
            return self._отдать(в.не_найдено(путь).encode("utf-8"), код=404)
        тело = в.коллекция(данные)
        return self._отдать(тело.encode("utf-8"))

    def маршрут_тайтла(self, в: Вид, совпало, путь: str):
        slug = совпало.group("slug")
        канон = self.SLUG_ALIASES.get(slug)
        if канон and канон != slug:
            хвост = путь[len(f"/title/{slug}"):]  # includes leading /
            return self._переход(f"/title/{канон}{хвост}")
        запись = в.запись(slug)
        if not запись:
            # Настоящая 404, а не общая оболочка с кодом 200. Мягкая
            # двухсотка на несуществующем адресе — это обещание страницы,
            # которой нет, и она же ломает любой обход ссылок.
            return self._отдать(в.не_найдено(путь).encode("utf-8"), код=404)
        деталь = в.деталь(slug)
        н_сезона, н_серии = совпало.group("s"), совпало.group("e")
        if н_сезона is None:
            return self._отдать(в.тайтл(запись, деталь).encode("utf-8"))
        номер = int(н_сезона)
        сезон = сезон_по_номеру(деталь, номер)
        if not сезон:
            return self._отдать(в.не_найдено(путь).encode("utf-8"), код=404)
        if н_серии is None:
            return self._отдать(в.сезон(запись, деталь, номер).encode("utf-8"))
        серия = int(н_серии)
        # Границы проверяются по объявленному числу серий сезона. Двести
        # одиннадцатая у сериала с двумястами десятью — это 404, а не пустая
        # страница с плеером, которому нечего показать.
        if not 1 <= серия <= int(сезон.get("eps") or 0):
            return self._отдать(в.не_найдено(путь).encode("utf-8"), код=404)
        return self._отдать(в.серия(запись, деталь, номер, серия).encode("utf-8"))

    # --- страницы -------------------------------------------------------
    def главная(self) -> str:
        д = self.данные
        новые = [з for з in д.items if з.get("poster")][:12]
        герой = "".join(
            f'<div class="hero__it"><div class="hero__ps">'
            f'<img src="{html.escape(з["poster"])}" alt=""></div><div>'
            f'<h2 class="hero__t">{html.escape(з["title"])}</h2>'
            f'<div class="hero__m">'
            + "".join(f'<span class="chip">{html.escape(str(x))}</span>'
                      for x in (з.get("kind"), з.get("year")) if x)
            + f'</div><a class="btn" href="{з["url"]}">{_П["hero_btn"]}</a></div></div>'
            for з in новые[:6])
        точки = "".join(f'<b{" data-on" if i == 0 else ""}></b>' for i in range(len(новые[:6])))
        def полоса(титул, ссылка, набор):
            return (f'<section class="sec"><div class="sec__h"><h2>{титул}</h2>'
                    f'<a href="{ссылка}">Все →</a></div><div class="grid">'
                    + "".join(карточка(з) for з in набор) + '</div></section>')
        # Блоки собираются контрактом коллекций: заголовок, выборка и адрес
        # «Все →» приходят из одной спецификации. Раньше заголовок и ссылка
        # жили в шаблоне порознь, и на Animedia три блока с фильтром `None`
        # показывали одни и те же записи под разными названиями, а ссылки вели
        # в общий каталог. Пустая коллекция не рисуется вовсе — большого
        # пустого места на главной быть не должно.
        снимок = Снимок.получить(д, self.подробности) if КОЛЛЕКЦИИ else None
        if снимок is not None:
            ленты = []
            for спец in КОЛЛЕКЦИИ.спецификации(СЕМЕЙСТВО):
                коллекция = КОЛЛЕКЦИИ.разрешить(
                    спец.collection_key, снимок, СЕМЕЙСТВО, предел=спец.card_limit)
                if коллекция is None or not коллекция.items:
                    continue
                ленты.append(полоса(коллекция.title, коллекция.view_all_path,
                                    [к.raw for к in коллекция.items]))
            блоки = "".join(ленты)
        else:
            блоки = "".join(
                полоса(титул, ссылка,
                       (д.items if вид is None else
                        [з for з in д.items if з.get("kind") == вид])[:12])
                for титул, ссылка, вид in _П["secs"])
        тело = (f'<div class="hero"><div class="hero__track">{герой}</div>'
                f'<div class="hero__dots">{точки}</div></div>' + блоки)
        return оболочка(тело, "Главная", д, "/")

    def список(self, путь: str, зпр: dict) -> str:
        д = self.данные
        разд = путь.rstrip("/")
        набор = д.items
        вид = (зпр.get("kind") or [None])[0]
        год = (зпр.get("year") or [None])[0]
        if вид:
            набор = [з for з in набор if з.get("kind") == вид]
        if год and год.isdigit():
            набор = [з for з in набор if з.get("year") == int(год)]
        стр = max(1, int((зпр.get("page") or ["1"])[0] or 1))
        всего = (len(набор) + НА_СТРАНИЦЕ - 1) // НА_СТРАНИЦЕ
        кусок = набор[(стр - 1) * НА_СТРАНИЦЕ: стр * НА_СТРАНИЦЕ]

        ТЕК = ' aria-current="true"'
        фвид = "".join(
            f'<a href="{разд}/{запрос_строкой({"kind": к})}"{ТЕК if вид == к else ""}>{к}</a>'
            for к in д.kinds)
        фгод = "".join(
            f'<a href="{разд}/{запрос_строкой({"year": г})}"{ТЕК if год == str(г) else ""}>{г}</a>'
            for г in д.years[:14])
        осн = urlencode([(k, v) for k, v in (("kind", вид), ("year", год)) if v],
                        quote_via=quote)
        листалка = "".join(
            (f'<span>{p}</span>' if p == стр else
             f'<a href="{разд}/?{осн}&page={p}">{p}</a>')
            for p in range(max(1, стр - 3), min(всего, стр + 3) + 1))
        титулы = {"/catalog": "Каталог", "/new": "Новинки", "/collections": "Подборки"}
        тело = (f'<section class="sec"><div class="sec__h"><h2>{титулы[разд]}</h2>'
                f'<a href="{разд}/">Сбросить</a></div>'
                f'<div class="flt">{фвид}</div><div class="flt">{фгод}</div>'
                f'<div class="grid">' + "".join(карточка(з) for з in кусок) + '</div>'
                f'<div class="pg">{листалка}</div></section>')
        return оболочка(тело, титулы[разд], д, разд + "/")

    def поиск(self, зпр: dict) -> str:
        д = self.данные
        q = (зпр.get("q") or [""])[0]
        найдено = д.искать(q)
        подпись = (": " + html.escape(q)) if q else ""
        пусто_хвост = (" по запросу «" + html.escape(q) + "»") if q else ""
        тело = (f'<section class="sec"><div class="sec__h">'
                f'<h2>Поиск{": " + html.escape(q) if q else ""}</h2>'
                f'<a href="/catalog/">В каталог →</a></div>'
                + (f'<div class="grid">' + "".join(карточка(з) for з in найдено) + '</div>'
                   if найдено else
                   f'<div class="empty">Ничего не найдено{пусто_хвост}.</div>')
                + '</section>')
        return оболочка(тело, "Поиск", д, "/search/")

    def расписание(self) -> str:
        д = self.данные
        дни = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        по_годам = [з for з in д.items if з.get("kind") == "Сериал"][:70]
        блоки = ""
        for i, день in enumerate(дни):
            куски = по_годам[i * 10:(i + 1) * 10]
            пункты = "".join(f'<li><a href="{з["url"]}">{html.escape(з["title"])}</a></li>'
                             for з in куски)
            блоки += f'<div class="sched__d"><h3>{день}</h3><ul>{пункты}</ul></div>'
        тело = ('<section class="sec"><div class="sec__h"><h2>Расписание</h2></div>'
                f'<div class="sched">{блоки}</div>'
                '<p class="empty">Сетка построена по доступному снимку каталога: '
                'дат выхода серий в нём нет, и выдумывать их нельзя.</p></section>')
        return оболочка(тело, "Расписание", д, "/schedule/")

    def наверх(self, разбор):
        """Проксирование в прежнее приложение витрины.

        Разметка не переписывается: добавляется только стиль и мета-данные
        версии, и только в HTML. Всё прочее идёт байт в байт.
        """
        import http.client
        адрес = разбор.path + (("?" + разбор.query) if разбор.query else "")
        хост, _, порт = ВЕРХОВОЙ.partition(":")
        try:
            соед = http.client.HTTPConnection(хост, int(порт or 80), timeout=25)
            заг = {k: v for k, v in self.headers.items()
                   if k.lower() not in ("host", "accept-encoding", "connection")}
            заг["Host"] = self.headers.get("Host", хост)
            заг["Accept-Encoding"] = "identity"
            соед.request("GET", адрес, headers=заг)
            ответ = соед.getresponse()
            тело = ответ.read()
            тип = ответ.getheader("Content-Type", "application/octet-stream")
            код = ответ.status
            соед.close()
        except OSError as ош:
            тело = оболочка(f'<div class="empty">Витрина недоступна: {html.escape(str(ош)[:80])}</div>',
                            "503", self.данные).encode("utf-8")
            return self._отдать(тело, код=503)
        if "text/html" in тип and b"</head>" in тело:
            вставка = (
                f'<meta name="site-factory-template-revision" content="{МАНИФЕСТ["source_commit"]}">'
                f'<meta name="site-factory-design-version" content="{ВЕРСИЯ}">'
                f'<meta name="site-factory-template-family" content="{СЕМЕЙСТВО}">'
                f'<meta name="site-factory-build-id" content="{СБОРКА}">'
                + тег_метрики()
                + f'<style>{СТИЛЬ}</style>').encode("utf-8")
            тело = тело.replace(b"</head>", вставка + b"</head>", 1)
        return self._отдать(тело, тип, код=код)

    def старое(self, путь: str):
        """Страницы тайтлов и активы — из существующего релиза, с новой оболочкой."""
        отн = путь.lstrip("/")
        корень = СТАРЫЙ_КОРЕНЬ.resolve()
        цель = (корень / отн)
        # Права каталога релиза принадлежат пользователю витрины; из-под другой
        # учётной записи `is_dir()` бросает PermissionError и рушит поток
        # обработчика. Отказ должен быть страницей, а не пустым ответом.
        try:
            if цель.is_dir():
                цель = цель / "index.html"
        except OSError:
            тело = оболочка('<div class="empty">Страница недоступна.</div>', "503",
                            self.данные).encode("utf-8")
            return self._отдать(тело, код=503)
        # Сравнение ведётся по разрешённым путям с обеих сторон: СТАРЫЙ_КОРЕНЬ
        # приходит через ссылку current, и без resolve() он никогда не окажется
        # среди parents — любая страница тайтла отдавала бы 404.
        try:
            разрешённый = цель.resolve()
            внутри = разрешённый == корень or корень in разрешённый.parents
            это_файл = цель.is_file()
        except OSError:
            внутри, это_файл = False, False
        if not это_файл or not внутри:
            тело = оболочка('<div class="empty">Страница не найдена.</div>', "404",
                            self.данные).encode("utf-8")
            return self._отдать(тело, код=404)
        данные = цель.read_bytes()
        if цель.suffix == ".html":
            текст = данные.decode("utf-8", errors="replace")
            # Плеер и разметка не трогаются: добавляется только стиль, шапка и
            # доказательство ревизии.
            вставка = (
                f'<meta name="site-factory-template-revision" content="{МАНИФЕСТ["source_commit"]}">'
                f'<meta name="site-factory-design-version" content="{ВЕРСИЯ}">'
                f'<meta name="site-factory-template-family" content="{СЕМЕЙСТВО}">'
                f'<meta name="site-factory-build-id" content="{СБОРКА}">'
                f'<meta name="site-factory-template" content="{ШАБЛОН_СЕМЕЙСТВА}">'
                f'<meta name="site-factory-core" content="{ЯДРО}">'
                f'<meta name="site-factory-profile" content="{ПРОФИЛЬ}">'
                + тег_метрики()
                + f'<style>{СТИЛЬ}</style>')
            текст = текст.replace("</head>", вставка + "</head>", 1)
            данные = текст.encode("utf-8")
        типы = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
                ".js": "application/javascript; charset=utf-8", ".json": "application/json",
                ".webmanifest": "application/manifest+json", ".svg": "image/svg+xml",
                ".png": "image/png", ".ico": "image/x-icon", ".txt": "text/plain; charset=utf-8"}
        return self._отдать(данные, типы.get(цель.suffix, "application/octet-stream"))


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--host", default="127.0.0.1")
    р.add_argument("--port", type=int, required=True)
    args = р.parse_args()
    Обработчик.данные = Данные(КАТАЛОГ_ФАЙЛ)
    Обработчик.подробности = Подробности(ПОДРОБНОСТИ_ФАЙЛ)
    Обработчик.индекс = построить_индекс(Обработчик.данные, Обработчик.подробности)
    сервер = ThreadingHTTPServer((args.host, args.port), Обработчик)
    import time as _time
    сервер.started_at = _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime())
    print(f"[nova] {args.host}:{args.port} ревизия {РЕВИЗИЯ[:12]} "
          f"оформление {ВЕРСИЯ} тайтлов {len(Обработчик.данные.items)} "
          f"подробностей {Обработчик.подробности.покрытие} "
          f"жанров {len(Обработчик.индекс['genre'])} "
          f"плеер {'подключён' if ПЛЕЕР.get('publisher_id') else 'без доступа'}",
          flush=True)
    сервер.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
