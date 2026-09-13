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

import argparse
import html
import json
import os
import re
import unicodedata
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

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
        "nav": [("/", "Главная"), ("/catalog/", "Каталог"), ("/new/", "Новинки"),
                ("/collections/", "Подборки"), ("/schedule/", "Расписание выхода")],
        "secs": [("Новые эпизоды", "/new/", None), ("Онгоинги", "/catalog/", None),
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


#: Слова, которые в запросе несут форму издания, а не название. По ним нельзя
#: отсеивать: «Бункер 1-3 сезон» обязан находить «Бункер».
СЛУЖЕБНЫЕ = {"сезон", "сезона", "сезонов", "серия", "серии", "season", "s",
             "часть", "все", "смотреть", "онлайн"}


class Данные:
    def __init__(self, путь: str):
        сырое = json.loads(Path(путь).read_text(encoding="utf-8"))
        self.items = сырое["items"]
        self.absent = сырое.get("fields_absent", [])
        for з in self.items:
            з["_n"] = нормализовать(з["title"])
            # Все известные формы названия: русское, оригинальное, синонимы
            # владельца. Пустых среди них нет — сравнивать с пустой строкой
            # значило бы совпадать со всем подряд.
            формы = [з["_n"]]
            for поле in ("original_title",):
                if з.get(поле):
                    формы.append(нормализовать(з[поле]))
            for доп in (з.get("aliases") or []):
                формы.append(нормализовать(доп))
            з["_формы"] = [ф for ф in формы if ф]
        self.years = sorted({з["year"] for з in self.items if з["year"]}, reverse=True)
        self.kinds = sorted({з["kind"] for з in self.items if з["kind"]})

    def искать(self, q: str, предел: int = 120) -> list[dict]:
        """Терпимый поиск по всем известным названиям записи.

        Ищется по русскому названию, оригинальному названию и переданным
        владельцем синонимам — по каждому в отдельности. Служебные слова
        запроса («сезон», «серия») отбрасываются: «Бункер 1-3 сезон» обязан
        находить «Бункер», а не пустую выдачу.

        Ранжирование: точное совпадение, затем начало, затем вхождение, затем
        терпимость к одной-двум опечаткам. Выдумывать совпадения нельзя, но и
        терять их из-за регистра, «ё» или дефиса — тоже.
        """
        нq = нормализовать(q)
        если_токены = [т for т in токены(q) if т not in СЛУЖЕБНЫЕ and not т.isdigit()]
        ядро = нормализовать("".join(если_токены))
        if not нq and not ядро:
            return []

        точн, начало, внутри, мягкие = [], [], [], []
        for з in self.items:
            формы = з["_формы"]
            if not формы:
                continue
            if нq and нq in формы:
                точн.append(з)
                continue
            if ядро and ядро in формы:
                точн.append(з)
                continue
            цель = ядро or нq
            if any(ф.startswith(цель) for ф in формы):
                начало.append(з)
                continue
            if any(цель in ф for ф in формы):
                внутри.append(з)
                continue
            # Терпимость к опечатке соразмерна длине запроса.
            #
            # Прежде допускались две правки при любой длине, и запрос «silo»
            # (четыре знака) выдавал 80 случайных совпадений вроде «вю» и
            # «47»: на коротких строках две правки — это уже другое слово.
            # Ниже пяти знаков нечёткое сравнение не применяется вовсе, до
            # восьми допускается одна правка, дальше две.
            if len(цель) >= 5 and len(мягкие) < предел:
                допуск = 1 if len(цель) < 8 else 2
                for ф in формы:
                    if abs(len(ф) - len(цель)) <= допуск and \
                            sum(1 for a, b in zip(ф, цель) if a != b) <= допуск:
                        мягкие.append(з)
                        break
        итог, видели = [], set()
        for группа in (точн, начало, внутри, мягкие):
            for з in группа:
                if з["url"] in видели:
                    continue
                видели.add(з["url"])
                итог.append(з)
                if len(итог) >= предел:
                    return итог
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
<style>{СТИЛЬ}</style></head><body>
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

#: Включено ли новое оформление на ЭТОЙ витрине. Решает манифест витрины, а не
#: наличие кода: один артефакт обслуживает шесть витрин, и переход делается по
#: одной. Витрина на 1.0.2 исполняет прежние ветки и отдаёт прежние байты.
ОФОРМЛЕНИЕ_НОВОЕ = (ВЕРСИЯ == ОФОРМЛЕНИЕ_1_1)

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

ЗОНА_ТОКЕНЫ = {
    "ink": "#16191d", "dim": "#59616b", "page": "#ffffff", "alt": "#f5f7fa",
    "rail": "#10161f", "railink": "#e8edf5", "line": "#e3e8ee",
    "acc": "#1a5fd0", "accdk": "#14489f", "warm": "#8a5a00",
    "mute": "#5f6874",
}

#: Общая часть: сброс, доступность и то, что обязано быть на каждой странице
#: любого семейства. Всё остальное расходится.
ОБЩЕЕ_1_1 = """
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;min-height:100vh}
img{max-width:100%;display:block}
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
/* Шапка в одну строку. */
.hd{background:@CARD@;border-bottom:1px solid @LINE@}
.hd__in{display:flex;align-items:center;gap:18px;height:62px;padding:0 18px}
.hd__logo{display:flex;align-items:center;gap:9px;font-weight:800;font-size:19px;
letter-spacing:.5px;text-transform:uppercase;color:@INK@}
.hd__mark{width:30px;height:30px;border-radius:5px;background:@ACC@;color:#fff;
display:grid;place-items:center;font-size:15px;font-weight:800}
.hd__nav{display:flex;gap:2px;flex:1;flex-wrap:wrap}
.hd__nav a{padding:8px 11px;border-radius:4px;font-size:13px;font-weight:700;
text-transform:uppercase;letter-spacing:.3px;color:#39414a}
.hd__nav a:hover{background:@SHEET@;color:@ACCDK@}
.hd__nav a[aria-current]{color:@ACCDK@;box-shadow:inset 0 -2px 0 @ACC@}
.hd__s{display:flex;border:1px solid @LINE@;border-radius:4px;overflow:hidden;background:#fff}
.hd__s input{border:0;padding:8px 11px;font-size:13px;width:190px;color:@INK@;background:#fff}
.hd__s button{border:0;background:#fff;color:#6a737d;padding:0 11px;cursor:pointer;font-size:14px}
.hd__s button:hover{color:@ACCDK@}
/* Заголовок раздела и вкладки-таблетки — прямо из эталона. */
.lead{font-size:20px;font-weight:600;color:#3a4149;margin:16px 0 12px}
/* Заголовок раздела у эталона — 24px при 14px основного текста.
   Было 17px: страница открывалась почти без заголовка. 20px — шаг к
   эталону, который остаётся в ритме этой типографики; остаточное
   расхождение названо в отчёте, а не сглажено. */
.tabs{display:flex;gap:7px;align-items:center;flex-wrap:wrap;margin:0 0 12px}
.tabs__pill{display:inline-flex;align-items:center;gap:7px;background:@ACC@;color:#fff;
font-weight:700;font-size:15px;padding:10px 18px;border-radius:4px}
.tabs a{background:@CARD@;border:1px solid @LINE@;border-radius:4px;padding:9px 15px;
font-size:13px;color:#4a535d;font-weight:600}
.tabs a:hover{color:@ACCDK@;border-color:@ACC@}
.tabs a[aria-current]{background:@BAR@;color:#fff;border-color:@BAR@}
/* Сетка в шесть колонок с тесными желобами. */
.grid{display:grid;gap:8px;grid-template-columns:repeat(2,1fr)}
@media(min-width:520px){.grid{grid-template-columns:repeat(3,1fr)}}
@media(min-width:860px){.grid{grid-template-columns:repeat(4,1fr)}}
@media(min-width:1080px){.grid{grid-template-columns:repeat(6,1fr)}}
/* Карточка: постер во всю площадь, название поверх него, оценки полосой. */
.c{position:relative;display:block;background:@BAR@;overflow:hidden;border-radius:3px}
.c:hover .c__img{transform:scale(1.04)}
.c__p{display:block;position:relative;aspect-ratio:2/3;overflow:hidden;background:#22272e}
.c__img{position:relative;z-index:1;width:100%;height:100%;object-fit:cover;
transition:transform .25s}
.c__none{position:absolute;inset:0;display:grid;place-items:center;text-align:center;
padding:10px;color:#8b95a1;font-size:12px;font-weight:600;
background:repeating-linear-gradient(135deg,#242a32 0 9px,#1e242b 9px 18px)}
.c__none b{display:block;font-size:26px;margin-bottom:4px;color:#aab4c0}
.c__badge{position:absolute;z-index:2;top:6px;left:6px;background:@ACC@;color:#fff;font-size:11px;
font-weight:700;padding:3px 7px;border-radius:3px;max-width:calc(100% - 12px);
overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.c__cap{position:absolute;z-index:2;left:0;right:0;bottom:0;padding:26px 7px 8px;text-align:center;
background:linear-gradient(180deg,#0000 0,#000000d9 58%,#000000f2 100%)}
.c__t{display:block;color:#fff;font-size:13px;font-weight:700;line-height:1.25;
display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.c__y{display:block;color:#c5ccd4;font-size:12px;margin-top:2px}
.c__r{display:flex;justify-content:space-between;align-items:center;gap:6px;
padding:6px 8px;background:@BAR@;font-size:12px;font-weight:700}
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
.eps{display:flex;flex-wrap:wrap;gap:5px}
.eps a{min-width:40px;text-align:center;padding:7px 8px;border:1px solid @LINE@;
border-radius:3px;font-size:13px;font-weight:600;background:#fff;color:#3f4750}
.eps a:hover{border-color:@ACC@;color:@ACCDK@}
.eps a[aria-current]{background:@ACC@;border-color:@ACC@;color:#fff}
.eps a[data-off]{color:@MUTE@;background:#f3f5f7}
.epnav{display:flex;justify-content:space-between;gap:10px;margin:14px 0 0;flex-wrap:wrap}
.epnav a,.epnav span{padding:9px 14px;border:1px solid @LINE@;border-radius:4px;
font-size:13px;font-weight:600;background:#fff;color:#3f4750}
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
.ft{background:@CARD@;border-top:1px solid @LINE@;margin-top:26px;padding:20px 18px 30px;
color:#5b6470;font-size:12.5px}
.ft__g{display:flex;gap:14px;flex-wrap:wrap;align-items:center;justify-content:space-between}
.vb{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11.5px;color:#4d555e;
border:1px solid @LINE@;border-radius:3px;padding:4px 8px;background:@SHEET@}

img[hidden]{display:none}
"""

ЗОНА_СТИЛЬ = """
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
.zt__p{display:block;aspect-ratio:2/3;background:@ALT@;position:relative}
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
.zeps{display:flex;flex-wrap:wrap;gap:6px;padding:14px 16px}
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
        "нав": [("/new/", "Новинки"), ("/catalog/?kind=Фильм", "Фильмы"),
                ("/catalog/?kind=Сериал", "Сериалы"),
                ("/catalog/?kind=Мультфильм", "Мультфильмы"),
                ("/catalog/", "Каталог")],
        "поиск": "Введите название",
        "полосы": [("Фильмы", "/catalog/?kind=Фильм", "Фильм"),
                   ("Сериалы", "/catalog/?kind=Сериал", "Сериал"),
                   ("Мультфильмы", "/catalog/?kind=Мультфильм", "Мультфильм")],
        "лид": "Фильмы и сериалы новинки смотреть онлайн",
        "метка": "LF",
    },
    "zona": {
        "вид": "zona",
        "токены": ЗОНА_ТОКЕНЫ,
        "стиль": lambda: _общее(ЗОНА_ТОКЕНЫ) + _подставить(ЗОНА_СТИЛЬ, ЗОНА_ТОКЕНЫ),
        "нав": [("/", "Обзор"), ("/new/", "Что нового"),
                ("/catalog/?kind=Фильм", "Кино"), ("/catalog/?kind=Сериал", "Сериалы"),
                ("/catalog/?kind=Мультфильм", "Анимация"), ("/catalog/", "Весь каталог")],
        "поиск": "Название фильма или сериала",
        "полосы": [("Кино", "/catalog/?kind=Фильм", "Фильм"),
                   ("Сериалы", "/catalog/?kind=Сериал", "Сериал")],
        "лид": "Кинопортал: что смотреть и где это найти",
        "метка": "Z",
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
#   loading     — элемент выставлен, скрипт провайдера ещё не поднял его;
#   nosource    — у записи нет ни kp, ни imdb: показывать нечего и нечем;
#   noaccess    — publisher id витрине не выдан;
#   provider    — провайдер ответил `noData` на эту запись;
#   error       — скрипт провайдера не загрузился.
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
АГРЕГАТОРЫ = ("kp", "mdl", "mali")

#: Соответствие «ключ внешнего идентификатора → агрегатор». `imdb` в контракте
#: агрегатором не значится, поэтому запись только с imdb источника не имеет.
КЛЮЧ_АГРЕГАТОРА = {"kp": "kp"}


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
    return {"publisher_id": издатель}


ПЛЕЕР = _конфиг_плеера()


def источник_плеера(деталь: dict) -> tuple[str, str]:
    """Агрегатор и идентификатор записи у него. Пусто — источника нет."""
    внешние = деталь.get("external_ids")
    if not isinstance(внешние, dict):
        return "", ""
    for ключ, агрегатор in КЛЮЧ_АГРЕГАТОРА.items():
        значение = str(внешние.get(ключ) or "").strip()
        if значение and агрегатор in АГРЕГАТОРЫ:
            return агрегатор, значение
    return "", ""


def состояние_плеера(деталь: dict) -> tuple[str, str, str]:
    """Состояние до отрисовки: (код, заголовок, объяснение)."""
    агрегатор, ид = источник_плеера(деталь)
    if not ПЛЕЕР.get("publisher_id"):
        return ("noaccess", "Просмотр на витрине не подключён",
                "Витрине не выдан идентификатор издателя, и обращаться к провайдеру "
                "ей нечем. Это настройка витрины, а не состояние записи: каталог, "
                "описание и список серий на странице доступны полностью.")
    if not (агрегатор and ид):
        return ("nosource", "Источник для этой записи не передан",
                "У записи нет идентификатора ни одного из разрешённых агрегаторов, "
                "поэтому запрашивать у провайдера нечего. Как только источник "
                "появится в каталоге, плеер включится здесь сам.")
    return ("playable", "", "")


def разметка_плеера(вид, запись: dict, деталь: dict, сезон: int, эпизод: int) -> tuple[str, str]:
    """Возвращает (код состояния, HTML внутренности рамки плеера)."""
    код, заголовок, текст = состояние_плеера(деталь)
    if код != "playable":
        return код, (f'<div class="{вид.кл_состояния}" data-player-state>'
                     f"<b>{html.escape(заголовок)}</b><p>{html.escape(текст)}</p></div>")
    агрегатор, ид = источник_плеера(деталь)
    атрибуты = {
        "ident": f"player-{запись['slug']}-s{сезон}e{эпизод}",
        "season": str(сезон), "episode": str(эпизод),
        "data-publisher-id": ПЛЕЕР["publisher_id"],
        "data-title-id": ид, "data-aggregator": агрегатор,
        "is-show-voice-only": "false", "is-show-banner": "true",
        "disable-licensed": "false",
    }
    строка = " ".join(f'{к}="{html.escape(str(з))}"' for к, з in атрибуты.items())
    return код, (
        f"<video-player {строка}></video-player>"
        f'<div class="{вид.кл_состояния}" data-player-state hidden>'
        "<b>Провайдер не отдал источник</b>"
        "<p>Для этой серии у провайдера сейчас нет дорожки. "
        "Остальные серии и описание на странице работают.</p></div>"
        '<noscript><div class="' + вид.кл_состояния + '">'
        "<b>Нужен JavaScript</b><p>Плеер подключается скриптом провайдера, "
        "и без JavaScript он не запустится. Описание, серии и каталог "
        "доступны без него.</p></div></noscript>"
    )


СКРИПТ_ПЛЕЕРА_КЛИЕНТ = """
(function(){
 var f=document.querySelector('[data-player]'); if(!f) return;
 var el=f.querySelector('video-player'), st=f.querySelector('[data-player-state]');
 if(!el){return}
 // `поднялся` означает только одно: элемент провайдера появился на экране.
 // Раньше этот же флаг ГЛУШИЛ все последующие состояния, и отказ, пришедший
 // после подъёма, до зрителя не доходил вовсе.
 //
 // А приходит он именно так. Обычная последовательность у провайдера —
 // сначала элемент поднимается, и только потом выясняется, что дорожки для
 // этой серии нет: событие `noData` прилетает ПОСЛЕ `ok`. Со старым флагом
 // зритель получал поднявшийся плеер, который молча ничего не играет, —
 // то есть ровно тот чёрный прямоугольник, ради которого состояния и заводили.
 //
 // Поэтому отказ провайдера и отказ его скрипта перебивают успех всегда, а
 // флаг гасит только запоздавший таймаут: пятнадцать секунд не повод объявлять
 // сломанным то, что уже играет.
 var поднялся=false;
 function state(k,t,p){ f.setAttribute('data-state',k);
  if(k==='ok'){ if(st)st.hidden=true; el.hidden=false; поднялся=true; return }
  el.hidden=true; if(!st)return; st.hidden=false;
  st.innerHTML='<b></b><p></p>'; st.firstChild.textContent=t;
  st.lastChild.textContent=p; }
 f.setAttribute('data-state','loading');
 el.addEventListener('noData',function(){
  state('provider','Провайдер не отдал источник',
   'Для этой серии у провайдера сейчас нет дорожки. Остальные серии и описание на странице работают.');});
 var s=document.querySelector('[data-player-script]');
 if(s){ s.addEventListener('error',function(){
  state('error','Скрипт плеера не загрузился',
   'Браузер не смог получить скрипт провайдера: его мог заблокировать расширение или сеть. Страница и список серий продолжают работать.');}); }
 var seen=setInterval(function(){
  if(el.shadowRoot||el.children.length){clearInterval(seen);state('ok');}},250);
 setTimeout(function(){ clearInterval(seen);
  if(!поднялся) state('slow','Плеер не поднялся',
   'Скрипт провайдера загрузился, но проигрыватель не запустился за пятнадцать секунд. Обновите страницу; описание и серии доступны и сейчас.');},15000);
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


def заглушка_постера(запись: dict, класс_заглушки: str, класс_картинки: str,
                     ширина: int = 300, высота: int = 450) -> str:
    """Постер с заглушкой ПОД ним, а не вместо него.

    Заглушка рисуется всегда и лежит слоем ниже изображения. Так закрываются
    сразу два случая, и по-разному:

    * постера нет в снимке — заглушка сразу видна и говорит «не передан»;
    * постер объявлен, но провайдер его не отдал — изображение снимается
      обработчиком ошибки, и из-под него открывается заглушка «не открылся».

    Разница в словах не косметическая: «не передан» — это состояние наших
    данных, «не открылся» — состояние чужого хранилища. Измерено: из 48 постеров
    страницы каталога семь адресов отвечают ошибкой у самого провайдера, и без
    заглушки на их месте оставался бы значок сломанной картинки.
    """
    первая = html.escape((запись.get("title") or "?")[:1].upper())
    постер = запись.get("poster")
    подпись = "постер не открылся" if постер else "постер не передан"
    заглушка = f'<span class="{класс_заглушки}"><b>{первая}</b>{подпись}</span>'
    if not постер:
        return заглушка
    картинка = (f'<img class="{класс_картинки}" src="{html.escape(постер)}" alt="" '
                f'loading="lazy" width="{ширина}" height="{высота}" data-poster>')
    return заглушка + картинка


#: Снятие изображения, которого нет. Слушатель стоит на фазе перехвата: событие
#: `error` у `<img>` не всплывает, и обычный делегированный обработчик его не
#: увидит. Один слушатель на документ вместо атрибута у каждой карточки: на
#: странице каталога их сорок восемь.
СКРИПТ_ПОСТЕРОВ = (
    "document.addEventListener('error',function(e){var i=e.target;"
    "if(i&&i.tagName==='IMG'&&i.hasAttribute('data-poster'))i.hidden=true;},true);"
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
    """Выборка каталога по параметрам запроса. Возвращает (набор, выбранное)."""
    набор = данные.items
    вид = (зпр.get("kind") or [None])[0]
    год = (зпр.get("year") or [None])[0]
    жанр = (зпр.get("genre") or [None])[0]
    if вид:
        набор = [з for з in набор if з.get("kind") == вид]
    if год and str(год).isdigit():
        набор = [з for з in набор if з.get("year") == int(год)]
    if жанр:
        разрешённые = индекс["genre"].get(жанр)
        if разрешённые is None:
            набор = []
        else:
            членство = set(разрешённые)
            набор = [з for з in набор if з["slug"] in членство]
    if раздел == "/new":
        # «Новинки» — это свежесть публикации, а не год производства: фильм
        # 1974 года, выложенный вчера, новинкой витрины является.
        набор = sorted(набор, key=lambda з: з.get("published_at") or "", reverse=True)
    return набор, {"kind": вид, "year": год, "genre": жанр}


def запрос_строкой(выбрано: dict, **замена) -> str:
    поля = dict(выбрано)
    поля.update(замена)
    пары = [(к, з) for к, з in поля.items() if з]
    return ("?" + "&".join(f"{к}={з}" for к, з in пары)) if пары else ""


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
            ссылки.append(f'<a href="/catalog/?genre={html.escape(код)}">{html.escape(имя)}</a>'
                          if код else html.escape(имя))
        добавить("Жанр", " · ".join(ссылки))
    добавить("Время", html.escape(_длительность(деталь.get("duration"))))
    добавить("Дата выхода", html.escape(_дата(деталь.get("premiere_date") or "")))
    сезоны = деталь.get("seasons") or []
    if сезоны:
        серий = всего_серий(деталь)
        доступно = sum(int(с.get("avail") or 0) for с in сезоны)
        хвост = "" if доступно >= серий else f", доступно {доступно}"
        добавить("Серии", html.escape(f"{len(сезоны)} сезон(ов), {серий} серий{хвост}"))
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
            f'<a href="{u}"{ТЕКУЩАЯ_СТРАНИЦА if u == актив else ""}>{html.escape(t)}</a>'
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
<style>{self.се["стиль"]()}</style><script>{СКРИПТ_ПОСТЕРОВ}</script></head>
<body><div class="backdrop"></div>
<a class="skip" href="#main">Перейти к содержимому</a>
<div class="sheet">
<header class="hd"><div class="hd__in">
<a class="hd__logo" href="/"><span class="hd__mark" aria-hidden="true">{html.escape(self.се["метка"])}</span>{html.escape(self.имя)}</a>
<nav class="hd__nav" aria-label="Разделы">{нав}</nav>
<form class="hd__s" action="/search/" method="get" role="search">
<label class="vh" for="q">Поиск по каталогу</label>
<input id="q" name="q" placeholder="{html.escape(self.се["поиск"])}">
<button type="submit" aria-label="Найти">&#9906;</button></form>
</div></header>{крошки}
<main id="main" class="pad">{тело}</main>
<footer class="ft"><div class="ft__g">
<span>{html.escape(self.имя)} · тестовая витрина, закрыта от индексации</span>
<span class="vb">Template: {СЕМЕЙСТВО} {ВЕРСИЯ} · {МАНИФЕСТ["source_commit"][:8]}</span>
</div></footer></div>{схемы}</body></html>"""

    # --- составные части ---------------------------------------------
    def карточка(self, запись: dict) -> str:
        деталь = self.деталь(запись["slug"])
        изо = заглушка_постера(запись, "c__none", "c__img")
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
        полоса = (f'<div class="c__r"><span class="c__kp">КП{f"<i>{кп}</i>" if кп else " <em>—</em>"}</span>'
                  f'<span class="c__imdb">IMDb{f"<i>{им}</i>" if им else " <em>—</em>"}</span></div>')
        год = f'<span class="c__y">{запись["year"]}</span>' if запись.get("year") else ""
        return (f'<a class="c" href="{запись["url"]}">'
                f'<span class="c__p">{изо}{значок}'
                f'<span class="c__cap"><span class="c__t">{html.escape(запись["title"])}</span>{год}</span>'
                f"</span>{полоса}</a>")

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
        свежие = sorted(self.д.items, key=lambda з: з.get("published_at") or "",
                        reverse=True)[:12]
        полосы.append(self._полоса("Новинки", "/new/", свежие))
        for титул, ссылка, вид in self.се["полосы"]:
            набор = [з for з in self.д.items if з.get("kind") == вид][:12]
            if набор:
                полосы.append(self._полоса(титул, ссылка, набор))
        тело = f'<h1 class="lead">{html.escape(self.се["лид"])}</h1>' + _склеить(полосы)
        return self.оболочка(
            тело, f"{self.имя} — фильмы и сериалы онлайн", "/", актив="/",
            описание=f"{self.имя}: каталог фильмов, сериалов и мультфильмов.")

    def _полоса(self, титул: str, ссылка: str, набор) -> str:
        return (f'<section><div class="tabs"><span class="tabs__pill">{html.escape(титул)} ›</span>'
                f'<a href="{ссылка}">Все</a></div>{self.сетка(набор)}</section>')

    def список(self, разд: str, зпр: dict) -> str:
        имена = {"/catalog": "Каталог", "/new": "Новинки", "/collections": "Подборки"}
        титул = имена.get(разд, "Каталог")
        набор, выбрано = отбор(self.д, self.индекс, зпр, разд)
        стр = max(1, int((зпр.get("page") or ["1"])[0] or 1))
        всего = max(1, (len(набор) + НА_СТРАНИЦЕ_1_1 - 1) // НА_СТРАНИЦЕ_1_1)
        стр = min(стр, всего)
        кусок = набор[(стр - 1) * НА_СТРАНИЦЕ_1_1: стр * НА_СТРАНИЦЕ_1_1]
        чипы = [f'<span class="tabs__pill">{html.escape(титул)} ›</span>']
        for к in self.д.kinds:
            текущий = ' aria-current="true"' if выбрано["kind"] == к else ""
            чипы.append(f'<a href="{разд}/{запрос_строкой(выбрано, kind=к, page=None)}"{текущий}>'
                        f"{html.escape(к)}</a>")
        if any(выбрано.values()):
            чипы.append(f'<a href="{разд}/">Сбросить</a>')
        годы = "".join(
            f'<a href="{разд}/{запрос_строкой(выбрано, year=г, page=None)}"'
            f'{ТЕКУЩИЙ_ПУНКТ if выбрано["year"] == str(г) else ""}>{г}</a>'
            for г in self.д.years[:12])
        тело = (f'<h1 class="lead">{html.escape(титул)}: {len(набор)} записей</h1>'
                f'<div class="tabs">{"".join(чипы)}</div>'
                f'<div class="tabs">{годы}</div>'
                + (self.сетка(кусок) if кусок else
                   '<div class="empty"><b>Здесь пока пусто</b>'
                   "Под выбранные условия в снимке каталога не попала ни одна запись. "
                   "Снимите фильтр или вернитесь в полный каталог.</div>")
                + self.листалка(разд, выбрано, стр, всего))
        return self.оболочка(тело, f"{титул} — {self.имя}", разд + "/", актив=разд + "/",
                             описание=f"{титул} витрины {self.имя}.")

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
        return self.оболочка(тело, f"Поиск — {self.имя}", "/search/", актив="")

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

        плитки = "".join(
            f'<div class="rate rate--{вид}">{html.escape(метка)} {html.escape(значение)}'
            f"<small>источник: CDNVideoHub</small></div>"
            for вид, метка, значение in оценки(деталь))
        плитки = f'<div class="rates">{плитки}</div>' if плитки else ""

        сезон_старт = сезоны[0]["n"] if сезоны else 1
        код, внутри = разметка_плеера(self, запись, деталь, сезон_старт, 1)
        плеер = (
            '<section class="pl" aria-labelledby="pl-h"><h2 class="vh" id="pl-h">Просмотр</h2>'
            '<div class="pl__bar"><span class="pl__tab" aria-current="true">Смотреть онлайн</span>'
            f'<span class="pl__note">{html.escape(_подпись_плеера(код))}</span></div>'
            f'<div class="pl__frame" data-player data-state="{код}">{внутри}</div>'
            f"{_скрипты_плеера(код)}</section>")

        блок_серий = self._серии(запись, сезоны) if сериал else ""
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
            f'<a href="{u}"{ТЕКУЩАЯ_СТРАНИЦА if u == актив else ""}>{html.escape(t)}</a>'
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
<span>{html.escape(self.имя)} · тестовая витрина, закрыта от индексации</span>
<span class="zvb">Template: {СЕМЕЙСТВО} {ВЕРСИЯ} · {МАНИФЕСТ["source_commit"][:8]}</span>
</footer></div></div>{схемы}</body></html>"""

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
            части.append("<span><em>оценки нет</em></span>")
        оценка = f'<span class="zt__r">{"".join(части)}</span>'
        return (f'<a class="zt" href="{запись["url"]}">'
                f'<span class="zt__p">{изо}</span>'
                f'<span class="zt__b"><span class="zt__t">{html.escape(запись["title"])}</span>'
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
        свежие = sorted(self.д.items, key=lambda з: з.get("published_at") or "",
                        reverse=True)[:8]
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

    def список(self, разд: str, зпр: dict) -> str:
        имена = {"/catalog": "Весь каталог", "/new": "Что нового", "/collections": "Подборки"}
        титул = имена.get(разд, "Каталог")
        набор, выбрано = отбор(self.д, self.индекс, зпр, разд)
        стр = max(1, int((зпр.get("page") or ["1"])[0] or 1))
        всего = max(1, (len(набор) + НА_СТРАНИЦЕ_1_1 - 1) // НА_СТРАНИЦЕ_1_1)
        стр = min(стр, всего)
        кусок = набор[(стр - 1) * НА_СТРАНИЦЕ_1_1: стр * НА_СТРАНИЦЕ_1_1]
        фильтры = "".join(
            f'<a href="{разд}/{запрос_строкой(выбрано, kind=к, page=None)}"'
            f'{ТЕКУЩАЯ_СТРАНИЦА if выбрано["kind"] == к else ""}>{html.escape(к)}</a>'
            for к in self.д.kinds)
        if any(выбрано.values()):
            фильтры += f'<a href="{разд}/">Сбросить</a>'
        тело = (f'<div class="zwrap"><h1 class="zh">{html.escape(титул)}</h1>'
                f'<p class="zsub">Найдено {len(набор)} записей · страница {стр} из {всего}</p>'
                + (self.лента(кусок) if кусок else
                   '<div class="zempty"><b>Ничего не подошло</b>'
                   "<p>Под выбранные условия в снимке каталога не попала ни одна запись.</p></div>")
                + self.листалка(разд, выбрано, стр, всего) + "</div>")
        return self.оболочка(тело, f"{титул} — {self.имя}", разд + "/", актив=разд + "/",
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
                    f'<p class="zsub">Совпадений: {len(найдено)}</p>' + self.лента(найдено))
        else:
            тело = (f'<h1 class="zh">«{html.escape(q)}»</h1>'
                    '<div class="zempty"><b>Совпадений нет</b>'
                    f"<p>По запросу «{html.escape(q)}» в снимке каталога ничего не нашлось. "
                    "Проверьте написание. "
                    '<a href="/catalog/">Открыть каталог целиком</a></p></div>')
        return self.оболочка(f'<div class="zwrap">{тело}</div>',
                             f"Поиск — {self.имя}", "/search/", актив="")

    def тайтл(self, запись: dict, деталь: dict) -> str:
        путь = f"/title/{запись['slug']}/"
        имя = запись["title"]
        сезоны = список_серий(деталь)
        сериал = bool(сезоны) or запись.get("kind") == "Сериал"
        звенья = [("/", self.имя),
                  ("/catalog/?kind=Сериал", "Сериалы") if сериал else ("/catalog/?kind=Фильм", "Кино"),
                  ("", имя)]
        постер = запись.get("poster")
        фон = (f'<div class="zban__img"><img src="{html.escape(деталь.get("backdrop_url") or постер or "")}" alt=""></div>'
               if (деталь.get("backdrop_url") or постер) else "")
        изо = заглушка_постера(запись, "zt__none", "zhead__img", 372, 558)
        ориг = (f'<p class="zhead__o">{html.escape(деталь["original_name"])}</p>'
                if деталь.get("original_name") else "")

        полоса = []
        for вид, метка, значение in оценки(деталь):
            класс = "zacc" if вид == "kp" else "zwarm"
            полоса.append(f'<div><dt>{html.escape(метка)}</dt>'
                          f'<dd class="{класс}">{html.escape(значение)}</dd></div>')
        if запись.get("year"):
            полоса.append(f'<div><dt>Год</dt><dd>{запись["year"]}</dd></div>')
        if сезоны:
            полоса.append(f'<div><dt>Серий</dt><dd>{всего_серий(деталь)}</dd></div>')
        длит = _длительность(деталь.get("duration"))
        if длит:
            полоса.append(f'<div><dt>Хронометраж</dt><dd>{html.escape(длит)}</dd></div>')
        полоса_html = (f'<dl class="zstrip">{"".join(полоса)}</dl>' if полоса else "")

        описание = деталь.get("description") or деталь.get("short_description") or ""
        сюжет = (f'<section class="zsec"><h2>О чём это</h2><p>{html.escape(описание)}</p></section>'
                 if описание else
                 '<section class="zsec"><h2>О чём это</h2>'
                 '<p class="none">Описание источник по этой записи пока не передал. '
                 "Известные факты собраны в колонке справа.</p></section>")

        пары = факты(self, запись, деталь)
        аside = ("".join(f"<div><dt>{html.escape(м)}</dt><dd>{з}</dd></div>" for м, з in пары))
        колонка = (f'<aside class="zaside"><dl>{аside}</dl></aside>' if пары else
                   '<aside class="zaside"><dl><div><dt>Сведения</dt>'
                   "<dd>Источник передал по этой записи только название, вид, год и постер.</dd>"
                   "</div></dl></aside>")

        сезон_старт = сезоны[0]["n"] if сезоны else 1
        код, внутри = разметка_плеера(self, запись, деталь, сезон_старт, 1)
        плеер = (f'<section class="zpl"><div class="zpl__h"><h2>Смотреть</h2>'
                 f"<span>{html.escape(_подпись_плеера(код))}</span></div>"
                 f'<div class="zpl__f" data-player data-state="{код}">{внутри}</div>'
                 f"{_скрипты_плеера(код)}</section>")

        блок_серий = (f'<div class="zwrap">{self._серии(запись, сезоны)}</div>'
                      if сериал else "")
        похожие = self.похожие(запись, деталь)
        блок_похожих = (f'<div class="zwrap"><h2 class="zh zh--sm">Смотрите также</h2>'
                        f"{self.плитки(похожие)}</div>" if похожие else "")

        тело = (f'<div class="zban">{фон}</div>'
                f'<div class="zhead"><div class="zhead__ps">{изо}</div>'
                f'<div class="zhead__x"><h1>{html.escape(имя)}</h1>{ориг}</div></div>'
                f"{полоса_html}"
                f'<div class="zbody"><div>{сюжет}</div>{колонка}</div>'
                f"{плеер}{блок_серий}{блок_похожих}")
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
                f'<b>Сезон {сезон["n"]}</b><span>{сезон["eps"]} серий{хвост}</span></div>'
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
    if код != "playable":
        return ""
    return (f'<script src="{СКРИПТ_ПЛЕЕРА}" async data-player-script></script>'
            f"<script>{СКРИПТ_ПЛЕЕРА_КЛИЕНТ}</script>")


def _подпись_плеера(код: str) -> str:
    return {
        "playable": "источник подключён",
        "loading": "подключение источника",
        "nosource": "источник не передан",
        "noaccess": "витрина без доступа к провайдеру",
        "provider": "провайдер не отдал дорожку",
        "error": "скрипт провайдера не загрузился",
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
    )


ВИДЫ_1_1 = {"lords": ВидЛордс, "zona": ВидЗона}


def построить_индекс(данные: "Данные", подробности: Подробности) -> dict:
    """Индексы, которые дешевле построить один раз при старте.

    По slug — чтобы страница тайтла не искала запись перебором пятидесяти двух
    тысяч; по жанру — чтобы `/genre/<код>/` не перечитывал боковой файл на
    каждый запрос.
    """
    по_slug = {з["slug"]: з for з in данные.items}
    по_жанру: dict[str, list] = {}
    имена: dict[str, str] = {}
    for slug, деталь in подробности.записи.items():
        if slug not in по_slug:
            continue
        жанры = деталь.get("genres") or []
        коды = деталь.get("genre_codes") or []
        for i, код in enumerate(коды):
            по_жанру.setdefault(код, []).append(slug)
            if i < len(жанры):
                имена.setdefault(код, жанры[i])
    порядок = sorted(имена.items(), key=lambda п: -len(по_жанру.get(п[0], ())))
    return {"slug": по_slug, "genre": по_жанру, "genre_names": порядок}


class Обработчик(BaseHTTPRequestHandler):
    server_version = "site-factory-nova"
    данные: Данные = None  # проставляется при запуске
    подробности: Подробности = None  # то же: боковой файл подробностей
    индекс: dict = None  # индексы по slug и жанру

    def log_message(self, *a):
        pass

    def _отдать(self, тело: bytes, тип="text/html; charset=utf-8", код=200):
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
            return self._отдать(json.dumps(свод, ensure_ascii=False).encode("utf-8"),
                                "application/json; charset=utf-8")
        if путь == "/healthz":
            return self._отдать(b'{"ok":true}', "application/json")
        if путь == "/assets/nova.webmanifest":
            м = json.dumps({"name": ИМЯ_ВИТРИНЫ, "template": ШАБЛОН_СЕМЕЙСТВА,
                            "core": ЯДРО, "family": СЕМЕЙСТВО, "profile": ПРОФИЛЬ,
                            "revision": РЕВИЗИЯ, "display": "standalone"}, ensure_ascii=False)
            return self._отдать(м.encode(), "application/manifest+json")
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

    #: Адреса, существовавшие до 1.1.0. Каждый уводит РОВНО одним переходом на
    #: действующий раздел: молча отдавать по ним 404 значило бы терять ссылки,
    #: которые уже кем-то сохранены.
    ПРЕЖНИЕ_АДРЕСА = {"/schedule/": "/new/"}

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
        if путь in self.ПРЕЖНИЕ_АДРЕСА:
            return self._переход(self.ПРЕЖНИЕ_АДРЕСА[путь])
        обрезанный = путь.rstrip("/") or "/"
        if обрезанный == "/":
            return self._отдать(в.главная().encode("utf-8"))
        if обрезанный in ("/catalog", "/new", "/collections"):
            return self._отдать(в.список(обрезанный, зпр).encode("utf-8"))
        if обрезанный == "/search":
            return self._отдать(в.поиск(зпр).encode("utf-8"))
        жанр = self.МАРШРУТ_ЖАНРА.match(путь)
        if жанр:
            код = жанр.group("code")
            if код not in self.индекс["genre"]:
                return self._отдать(в.не_найдено(путь).encode("utf-8"), код=404)
            # Жанр — это выборка каталога, а не отдельный документ. Один
            # переход на канонический адрес выборки, и у страницы остаётся
            # ровно один адрес вместо двух с одинаковым содержимым.
            return self._переход(f"/catalog/?genre={код}")
        совпало = self.МАРШРУТ_ТАЙТЛА.match(путь)
        if совпало:
            return self.маршрут_тайтла(в, совпало, путь)
        return self._отдать(в.не_найдено(путь).encode("utf-8"), код=404)

    def маршрут_тайтла(self, в: Вид, совпало, путь: str):
        slug = совпало.group("slug")
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
        тело = (f'<div class="hero"><div class="hero__track">{герой}</div>'
                f'<div class="hero__dots">{точки}</div></div>'
                + "".join(
                    полоса(титул, ссылка,
                           (д.items if вид is None else
                            [з for з in д.items if з.get("kind") == вид])[:12])
                    for титул, ссылка, вид in _П["secs"]))
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
            f'<a href="{разд}/?kind={к}"{ТЕК if вид == к else ""}>{к}</a>'
            for к in д.kinds)
        фгод = "".join(
            f'<a href="{разд}/?year={г}"{ТЕК if год == str(г) else ""}>{г}</a>'
            for г in д.years[:14])
        осн = "&".join(f"{k}={v}" for k, v in (("kind", вид), ("year", год)) if v)
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
                f'<style>{СТИЛЬ}</style>').encode("utf-8")
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
                f'<style>{СТИЛЬ}</style>')
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
