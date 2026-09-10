#!/usr/bin/env python3
"""Frontend витрин YummyAnime. Отдельный файл — намеренно.

Почему копия, а не общий рантайм
--------------------------------

Девять витрин обслуживались одним файлом, и любая правка задевала все
семейства сразу. Задача — менять ТОЛЬКО YummyAnime, поэтому три витрины Yummy
переведены на собственную копию: править её можно, не трогая Lords, Zona и
Animedia. Общее ядро осталось тем же, разошлись только пути сопровождения.

Расхождение с общим рантаймом допустимо и ожидаемо: у аниме своя витрина —
сезоны, эпизоды, статус выхода, — и подгонять её под кинопортал незачем.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
import sys
import unicodedata
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

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
#: Заголовки ответа, которые обязаны дойти до браузера.
#:
#: Прежде наверх переносился только Content-Type, и `Location` терялся:
#: canonical-редирект «/anime/<слаг>--<uuid>» → «/anime/<слаг>» превращался в
#: 308 без адреса перехода и с типом application/octet-stream. Снаружи это
#: выглядело как «карточки строят нерабочие адреса», хотя ломал их посредник.
ПЕРЕНОСИМЫЕ = ("location", "cache-control", "content-language", "vary",
               "last-modified", "etag", "content-disposition", "link",
               "x-nextjs-cache", "x-nextjs-prerender")
#: Стиль ТОЛЬКО служебного бейджа. Ничего больше: витрина рисуется своим
#: шаблоном, и подмешивать в неё чужую типографику незачем.
БЕЙДЖ_СТИЛЬ = (".sf-vbadge{position:fixed;left:8px;bottom:8px;z-index:2147483000;"
               "background:#1b1b1fdd;color:#ffb4a2;border:1px solid #ff7f5c;"
               "border-radius:8px;padding:4px 9px;font:600 11px/1.2 ui-monospace,"
               "SFMono-Regular,Menlo,monospace;pointer-events:none}")
#: Имя шаблона КОНКРЕТНОГО семейства. Отсюда и из версии складывается то, что
#: домен объявляет о себе.
ШАБЛОН_СЕМЕЙСТВА = f"{СЕМЕЙСТВО}-nova"
КАТАЛОГ_ФАЙЛ = os.environ.get("LORDS_CATALOG", "/srv/lords/.frontend/lords-01-catalog.json")
СТАРЫЙ_КОРЕНЬ = Path(os.environ.get("LORDS_LEGACY_ROOT", "/srv/lords/lords-01/current/site"))
ИМЯ_ВИТРИНЫ = os.environ.get("LORDS_SITE_NAME", "Lords")
# Для витрин, где страницы отдаёт приложение, а не каталог файлов: всё, чего
# нет в новом маршруте, проксируется в него. Так плеер, карточка и любые
# динамические страницы остаются рабочими — их никто не переписывает.
ВЕРХОВОЙ = os.environ.get("LORDS_LEGACY_UPSTREAM", "")


def _загрузить_страницы():
    """Модуль семейных страниц лежит рядом с рантаймом.

    Отсутствие модуля — не отказ витрины: маршруты /new, /collections и
    /schedule просто уйдут наверх, как раньше. Но отсутствие называется вслух
    в /__template_version, чтобы «страниц нет» не выглядело как «страницы
    пусты».
    """
    import importlib.machinery
    import importlib.util
    путь = Path(__file__).resolve().parent / "yummy_pages.py"
    if not путь.is_file():
        return None
    спец = importlib.util.spec_from_loader(
        "yummy_pages", importlib.machinery.SourceFileLoader("yummy_pages", str(путь)))
    м = importlib.util.module_from_spec(спец)
    sys.modules.setdefault("yummy_pages", м)
    спец.loader.exec_module(м)
    return м


СТРАНИЦЫ = _загрузить_страницы()


def _рядом(имя: str, модуль: str):
    import importlib.machinery
    import importlib.util
    путь = Path(__file__).resolve().parent / имя
    if not путь.is_file():
        return None
    спец = importlib.util.spec_from_loader(
        модуль, importlib.machinery.SourceFileLoader(модуль, str(путь)))
    м = importlib.util.module_from_spec(спец)
    sys.modules.setdefault(модуль, м)
    спец.loader.exec_module(м)
    return м


ЧИТМОДЕЛЬ = _рядом("yummy_readmodel.py", "yummy_readmodel")
ВАРИАНТЫ_МОД = _рядом("yummy_variants.py", "yummy_variants")
#: Представление сущности и переходник к контуру. Компоненты знают про поля,
#: переходник — про таблицы, витрина — ни про то, ни про другое.
ВИД = _рядом("yummy_entity.py", "yummy_entity")
СВЯЗЬ = _рядом("yummy_contract.py", "yummy_contract")

#: Capability-флаги. Компонент включается наружу только когда за ним есть
#: рабочий API: неработающий орган управления учит не нажимать и на рабочий.
#: Значение читается из окружения, а не зашивается: включение — решение
#: выката, а не редактирование кода.
КАППЫ = {
    "personal_rating": os.environ.get("YUMMY_CAP_PERSONAL_RATING") == "1",
    "recommendations": os.environ.get("YUMMY_CAP_RECOMMENDATIONS", "1") == "1",
}

#: Режим карточки. `supplement` — витрина рисует карточку сама, представление
#: добавляет только недостающее; `full` — представление рисует карточку целиком
#: (проверено на фикстуре, применяется если витрина перестанет её рисовать).
РЕЖИМ_КАРТОЧКИ = os.environ.get("YUMMY_CARD_MODE", "supplement")

#: Маршруты витрины, которые обязаны быть в навигации. Адреса — только
#: существующие: пункт меню, ведущий в 404, хуже отсутствующего пункта.
НАВИГАЦИЯ = (("/new/", "Новинки"), ("/top/", "Топ-100"),
             ("/collections/", "Подборки"), ("/schedule/", "Расписание"))
БАЗА_ЧТЕНИЯ = os.environ.get("YUMMY_READMODEL",
                             "/srv/lords/.frontend/yummy-readmodel.sqlite3")
ВАРИАНТ_ДОМЕНА = os.environ.get("YUMMY_VARIANT_DOMAIN", "yummyani.site")
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


class Обработчик(BaseHTTPRequestHandler):
    server_version = "site-factory-nova"
    данные: Данные = None  # проставляется при запуске

    def log_message(self, *a):
        pass

    def _отдать(self, тело: bytes, тип="text/html; charset=utf-8", код=200, ещё=None):
        self.send_response(код)
        if тип:
            self.send_header("Content-Type", тип)
        for имя, значение in (ещё or []):
            self.send_header(имя, значение)
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
        if путь == "/__contract":
            # Не «работает ли витрина», а что именно она готова принять и что
            # контур уже отдаёт. Пустая поверхность названа пустой.
            свод = {
                "entity_view": ВИД.КОНТРАКТ if ВИД else None,
                "accepts": f"{ВИД.ИМЯ_КОНТУРА}/{ВИД.ПРИНИМАЕМЫЙ_МАЖОР}.x" if ВИД else None,
                "adapter": СВЯЗЬ.КОНТРАКТ if СВЯЗЬ else None,
                "capabilities": КАППЫ,
                "card_mode": РЕЖИМ_КАРТОЧКИ,
                "variant": (ВАРИАНТЫ_МОД.вариант(ВАРИАНТ_ДОМЕНА).get("variant_id")
                            if ВАРИАНТЫ_МОД else None),
                "navigation": [а for а, _ in НАВИГАЦИЯ],
            }
            try:
                with self._соединение() as соед:
                    свод["read_model"] = СВЯЗЬ.версия_контракта(соед)
                    свод["compatible"] = ВИД.совместим(свод["read_model"])
                    свод["surfaces"] = {к: len(v) for к, v
                                        in self._ленты_контура().items()}
            except Exception as ош:
                свод["read_model"] = None
                свод["error"] = str(ош)[:120]
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

        # Единый renderer семейства: страницы рисует приложение YummyAnime.
        #
        # Прежде nova перехватывала /, /catalog, /new, /collections, /search и
        # /schedule и рисовала их своим тёмным каркасом. Это подменяло готовый
        # продукт худшим: на главной приложения 91 настоящий постер, разделы
        # «Новые серии», «Актуальное», «Появилось видео», «Сейчас выходят»,
        # онгоинги, анонсы, расписание, ТОП и случайное — а каркас отдавал одну
        # и ту же выборку под тремя заголовками и ноль изображений.
        #
        # Поэтому маршруты списков больше не перехватываются. На одном домене
        # остаётся ОДИН renderer, а nova добавляет только объявление версии.
        # /schedule/ — это настоящая страница расписания витрины.
        #
        # У приложения она есть: /catalog/schedule отвечает 200. Собирать своё
        # расписание рядом с готовым значило бы построить второй продукт на том
        # же домене — ровно то, что уже пришлось разбирать. Поэтому маршрут
        # отдаёт её содержимое под своим адресом.
        if ВАРИАНТЫ_МОД is not None and путь.rstrip("/") == "/top":
            тело = self._страница_топ(зпр)
            if тело is not None:
                return self._отдать(self._обогатить(тело, "text/html; charset=utf-8"),
                                    "text/html; charset=utf-8")

        # /schedule/ собирается витриной, а не проксируется.
        #
        # Собственная страница приложения — «Календарь премьер» — честно
        # пуста: подтверждённых будущих дат у контура нет. Отдавать её как
        # весь раздел значило бы отдавать пустую страницу, поэтому раздел
        # собирается здесь: поверхности контракта (пустые — скрыты), ленты
        # витрины (наполненные) и ссылка на сам календарь.
        if ВЕРХОВОЙ and СТРАНИЦЫ is not None and \
                путь.rstrip("/") in ("/new", "/collections", "/schedule"):
            тело = self._семейная_страница(путь.rstrip("/"))
            if тело is not None:
                return self._отдать(self._обогатить(тело, "text/html; charset=utf-8"),
                                    "text/html; charset=utf-8")

        if ВЕРХОВОЙ:
            # Маршруты поиска идут через расширение запроса; остальное — прямо.
            if путь.rstrip("/") in ("/search", "/api/search"):
                ответ = self._поиск_наверх(разбор, зпр)
                if ответ is not None:
                    тело, тип, код = ответ
                    return self._отдать(self._обогатить(тело, тип), тип, код=код)
            return self.наверх(разбор)
        return self.старое(путь)

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

    #: Слова, обозначающие форму издания, а не название. Витрина ищет по
    #: названию, и «Season 3» в запросе — это уточнение, а не часть имени.
    ИЗДАНИЕ = ("season", "сезон", "сезона", "сезонов", "series", "серия", "серии",
               "part", "часть", "tv", "ova", "ona", "movie", "фильм", "dreaming")

    def _сузить(self, q: str) -> list[str]:
        """Последовательно укорачиваемые варианты запроса.

        Приложение ищет по полной строке: «Grand Blue Dreaming Season 3» не
        находит ничего, хотя «Grand Blue» находит «Необъятный океан». Здесь
        запрос сокращается справа — сначала отбрасываются слова издания и
        числа, затем по одному слову с конца. Это расширение поиска, а не
        подмена: если находит полный запрос, сокращения не используются.
        """
        части = [ч for ч in re.split(r"[\s,]+", q.strip()) if ч]
        варианты = []
        без_издания = [ч for ч in части
                       if ч.lower() not in self.ИЗДАНИЕ and not ч.isdigit()]
        if без_издания and без_издания != части:
            варианты.append(" ".join(без_издания))
        основа = без_издания or части
        for n in range(len(основа) - 1, 0, -1):
            в = " ".join(основа[:n])
            if в and в not in варианты:
                варианты.append(в)
        return варианты

    def _поиск_наверх(self, разбор, зпр):
        """Поиск с расширением: полный запрос, затем сокращённые варианты."""
        q = (зпр.get("q") or [""])[0]
        ответ = self._сырое_наверх(разбор.path, разбор.query)
        if q and ответ is not None and self._пусто(разбор.path, ответ[0]):
            for вариант in self._сузить(q):
                новый = self._сырое_наверх(разбор.path, f"q={quote(вариант)}")
                if новый is not None and not self._пусто(разбор.path, новый[0]):
                    return новый
        return ответ

    @staticmethod
    def _пусто(путь: str, тело: bytes) -> bool:
        if путь.startswith("/api/"):
            try:
                return not (json.loads(тело.decode("utf-8", "replace")).get("items") or [])
            except ValueError:
                return False
        return not re.search(rb'href="/anime/', тело)

    def _сырое_наверх(self, путь: str, запрос: str):
        import http.client
        безопасно = "/:@!$&'()*+,;=~-._%"
        адрес = quote(путь, safe=безопасно) + (("?" + quote(запрос, safe=безопасно + "?&=")) if запрос else "")
        хост, _, порт = ВЕРХОВОЙ.partition(":")
        try:
            соед = http.client.HTTPConnection(хост, int(порт or 80), timeout=25)
            заг = {k: v for k, v in self.headers.items()
                   if k.lower() not in ("host", "accept-encoding", "connection")}
            заг["Host"] = self.headers.get("Host", хост)
            заг["Accept-Encoding"] = "identity"
            соед.request("GET", адрес, headers=заг)
            о = соед.getresponse()
            итог = (о.read(), о.getheader("Content-Type", "application/octet-stream"), о.status)
            соед.close()
            return итог
        except OSError:
            return None

    #: Карта «адрес тайтла → постер», собранная по нескольким страницам
    #: каталога. Держится в процессе с коротким сроком жизни: строить её на
    #: каждый запрос значило бы десяток обращений наверх на одну страницу.
    _карта: list = []
    _карта_до: float = 0.0
    #: Сколько страниц каталога обходить. Десять — это 240 тайтлов: достаточно,
    #: чтобы закрыть ленты главной, и не настолько много, чтобы страница
    #: собиралась заметно дольше.
    СТРАНИЦ_КАТАЛОГА = 10

    #: Разрешённые постеры: адрес тайтла → реальный /poster/<uuid>.webp.
    _постеры: dict = {}
    _постеры_до: float = 0.0

    def _разрешить_постеры(self, элементы: list) -> list:
        """Достаёт настоящий постер со страницы тайтла — по одному разу.

        Подставлять «/poster/<слаг>.webp» нельзя: этот адрес отвечает 200 для
        ЛЮБОГО слага, включая несуществующий, и отдаёт заглушку в 532 байта
        (image/svg+xml). Такая «обложка» выглядела бы настоящей и прятала бы
        отсутствие данных — это хуже честной заглушки.

        Настоящий адрес постера есть только на самой странице тайтла, поэтому
        она читается один раз на тайтл и результат держится в процессе.
        """
        import concurrent.futures as _cf
        import time as _t
        if _t.time() > type(self)._постеры_до:
            type(self)._постеры = {}
            type(self)._постеры_до = _t.time() + 600
        карта = type(self)._постеры
        нужны = [з["href"] for з in элементы
                 if not з.get("src") and з["href"] not in карта]

        def годный(адрес: str) -> bool:
            """Настоящая обложка, а не заглушка витрины.

            «/poster/<что угодно>.webp» отвечает 200 и отдаёт SVG-заглушку в
            532 байта — включая заведомо несуществующие идентификаторы.
            Показывать её как картинку значит рисовать поддельный постер, и
            браузер такую «обложку» временами считает битой.

            Проверять приходится по ПУБЛИЧНОМУ адресу: постеры отдаёт не
            приложение (там «/poster/» — это 404), а nginx проксированием на
            CDN, и на порту 80 он отвечает редиректом на HTTPS. Две прежние
            попытки — запрос в контейнер и HEAD на порт 80 — отвергали все
            обложки подряд, и страница оставалась вовсе без постеров.
            """
            хост = self.headers.get("Host", "yummyani.biz").split(":")[0]
            try:
                готово = subprocess.run(
                    ["curl", "-sS", "-I", "-L", "--max-time", "8",
                     f"https://{хост}{адрес}"],
                    capture_output=True, text=True, timeout=12).stdout.lower()
            except (OSError, subprocess.SubprocessError):
                return False
            if "200" not in готово.split("\n")[0]:
                return False
            тип = re.search(r"content-type:\s*(\S+)", готово)
            длина = re.search(r"content-length:\s*(\d+)", готово)
            if тип and "svg" in тип.group(1):
                return False
            return not длина or int(длина.group(1)) > 2000

        def достать(href):
            ответ = self._сырое_наверх(href, "")
            if not ответ:
                return href, None
            м = re.search(rb'"(/poster/[0-9a-f-]{36}\.webp)"', ответ[0])
            if not м:
                return href, None
            адрес = м.group(1).decode()
            return href, (адрес if годный(адрес) else None)

        # Работа ограничена по объёму И по времени: страница обязана
        # отрисоваться быстро даже на холодном кэше. Что не успели разрешить —
        # останется честной заглушкой и разрешится при следующем заходе.
        if нужны:
            крайний = _t.time() + 12.0
            with _cf.ThreadPoolExecutor(max_workers=12) as ex:
                будущие = {ex.submit(достать, h): h for h in нужны[:36]}
                for ф in _cf.as_completed(будущие, timeout=None):
                    try:
                        href, постер = ф.result(timeout=0.1)
                        карта[href] = постер
                    except Exception:
                        pass
                    if _t.time() > крайний:
                        break
        for з in элементы:
            # Выведенный из адреса постер тоже проверяется: он может оказаться
            # той же заглушкой.
            if з.get("src") and з["href"] not in карта:
                карта[з["href"]] = з["src"] if годный(з["src"]) else None
            з["src"] = карта.get(з["href"]) or (з.get("src") if з["href"] in карта and карта[з["href"]] else None)
        return элементы

    def _карта_постеров(self) -> list:
        import time as _t
        if type(self)._карта and _t.time() < type(self)._карта_до:
            return type(self)._карта
        собрано, видели = [], set()
        for н in range(1, self.СТРАНИЦ_КАТАЛОГА + 1):
            кусок = self._полезная("/catalog") if н == 1 else \
                (self._сырое_наверх("/catalog", f"page={н}") or (b"",))[0].decode("utf-8", "replace")
            for з in СТРАНИЦЫ.плитки_каталога(кусок, предел=60):
                if з["href"] in видели:
                    continue
                видели.add(з["href"])
                собрано.append(з)
        type(self)._карта = собрано
        type(self)._карта_до = _t.time() + 600
        return собрано

    def _соединение(self):
        import sqlite3
        соед = sqlite3.connect(f"file:{БАЗА_ЧТЕНИЯ}?mode=ro", uri=True, timeout=5)
        соед.row_factory = sqlite3.Row
        return соед

    # --- навигация ------------------------------------------------------
    #
    # Глобальную шапку рисует приложение витрины
    # (`src/components/layout/header-nav.tsx`, константы ANIME_LINKS и
    # COMMUNITY_LINKS). Правка там требует пересборки образа приложения, и
    # передана отдельным handoff'ом — см. docs/handoff/YUMMY-HEADER-NAV.md.
    #
    # До неё пункты добавляются здесь, классами самой витрины: маршруты
    # работают, а меню о них молчало — это и есть «пункт без исправления».
    НАВ_МЕТКА = 'data-sf-nav="1"'

    def _пункты_навигации(self) -> bytes:
        """Пункты в порядке приоритета варианта домена.

        Порядок — часть профиля: у расписания свой первый пункт, у каталога
        свой. Одинаковое меню на трёх витринах — это одна витрина втроём.
        """
        в = ВАРИАНТЫ_МОД.вариант(ВАРИАНТ_ДОМЕНА) if ВАРИАНТЫ_МОД else {}
        порядок = в.get("нав_порядок") or [а for а, _ in НАВИГАЦИЯ]
        по_адресу = dict(НАВИГАЦИЯ)
        пункты = [(а, по_адресу[а]) for а in порядок if а in по_адресу]
        пункты += [(а, п) for а, п in НАВИГАЦИЯ if а not in порядок]
        текущий = self.path.split("?", 1)[0]
        куски = []
        for адрес, подпись in пункты:
            тек = ' aria-current="page"' if текущий.rstrip("/") == адрес.rstrip("/") else ""
            куски.append(
                f'<a class="portal-nav-link" {self.НАВ_МЕТКА} href="{адрес}"{тек}>'
                f'<span class="portal-nav-text">{html.escape(подпись)}</span></a>')
        return "".join(куски).encode("utf-8")

    НАВ_ОТКРЫТИЕ = re.compile(rb'<nav class="portal-nav"[^>]*>')

    def _вставить_навигацию(self, тело: bytes) -> bytes:
        if self.НАВ_МЕТКА.encode() in тело:
            return тело                      # уже есть: повтор не создаётся
        м = self.НАВ_ОТКРЫТИЕ.search(тело)
        if not м:
            return тело
        пункты = self._пункты_навигации()
        return тело[:м.end()] + пункты + тело[м.end():]

    # --- карточка тайтла ------------------------------------------------
    def _дополнение_карточки(self, путь: str) -> bytes:
        """Поля контракта, которых на странице витрины нет.

        Витрина рисует карточку сама и делает это полно: название, оригинал,
        альтернативные, оценки провайдеров, тип, год, возраст, жанры, страны,
        режиссёр, съёмочная группа, серии, премьера, длительность, озвучки,
        описание. Рисовать это же вторым блоком — удвоить карточку.

        Поэтому сюда попадает только то, чего у витрины нет: сезоны, фон,
        рекомендации контракта и внутренняя оценка. Нет ни одного такого поля
        — нет и блока.
        """
        if ВИД is None or СВЯЗЬ is None:
            return b""
        канон = ВИД.канонический_путь(путь)
        if not канон:
            return b""
        try:
            with self._соединение() as соед:
                if not ВИД.совместим(СВЯЗЬ.версия_контракта(соед)):
                    return b""               # чужой контракт не показываем молча
                с = СВЯЗЬ.сущность(соед, canonical_path=канон)
        except Exception:
            # Контур недоступен — витрина работает без дополнения, а не падает.
            return b""
        if not с:
            return b""
        пропустить = () if РЕЖИМ_КАРТОЧКИ == "full" else (
            ВИД.РИСУЕТ_ВИТРИНА + ("poster", "title", "description", "ratings"))
        if not КАППЫ.get("recommendations"):
            пропустить = пропустить + ("recommendations",)
        разметка = ВИД.карточка_тайтла(с, КАППЫ, пропустить=пропустить)
        return разметка.encode("utf-8") if разметка else b""

    # --- ленты контура --------------------------------------------------
    def _ленты_контура(self, сейчас: str | None = None, нужные=None) -> dict:
        """Шесть поверхностей контракта. Недоступный контур — пустые ленты.

        Пустая лента означает отсутствие событий и скрывает секцию. Подменять
        её общим каталогом запрещено: раздел, показывающий каталог под именем
        «Новые серии», выглядит работающим и потому не чинится.
        """
        if СВЯЗЬ is None:
            return {}
        try:
            with self._соединение() as соед:
                актуальное = None
                if ЧИТМОДЕЛЬ is not None and hasattr(ЧИТМОДЕЛЬ, "актуальное"):
                    def актуальное(с, предел):
                        return ЧИТМОДЕЛЬ.актуальное(с, предел).get("items", [])
                return СВЯЗЬ.ленты(соед, актуальное, сейчас=сейчас,
                                   нужные=нужные)
        except Exception:
            return {}

    def _страница_топ(self, зпр) -> bytes | None:
        """Топ на настоящих внешних оценках с указанием провайдера."""
        оболочка = self._оболочка()
        if оболочка is None:
            return None
        провайдер = (зпр.get("provider") or ["imdb"])[0]
        if провайдер not in ВАРИАНТЫ_МОД.ПОРЯДОК_ПРОВАЙДЕРОВ:
            провайдер = "imdb"
        try:
            with self._соединение() as соед:
                свод = ВАРИАНТЫ_МОД.топ(соед, 100, провайдер)
        except Exception as ош:
            тело = СТРАНИЦЫ.собрать(
                оболочка, "Топ",
                "Оценки сейчас недоступны.",
                f'<p class="portal-empty">Источник оценок не отвечает: '
                f'{html.escape(str(ош)[:90])}. Показывать выдуманный порядок нельзя.</p>')
            return тело
        в = ВАРИАНТЫ_МОД.вариант(ВАРИАНТ_ДОМЕНА)
        имена = {"imdb": "IMDb", "kp": "Кинопоиск"}
        ТЕК = ' aria-current="true"'
        вкладки = "".join(
            f'<a href="/top/?provider={p}"{ТЕК if p == провайдер else ""}>{имена[p]}</a>'
            for p in ВАРИАНТЫ_МОД.ПОРЯДОК_ПРОВАЙДЕРОВ)
        плитки = []
        for з in свод["items"]:
            карта = {"href": з["canonicalPath"], "name": з["title"],
                     "src": з.get("poster"), "rating": None,
                     "alt": f'Постер аниме «{з["title"]}»'}
            разметка = СТРАНИЦЫ.карточка(карта)
            подпись = ВАРИАНТЫ_МОД.подпись_рейтингов(з["ratings"])
            разметка = разметка.replace(
                '<div class="portal-catalog-info">',
                f'<div class="portal-catalog-info"><span class="sf-rank">#{з["rank"]}</span>{подпись}')
            плитки.append(разметка)
        тело = (f'<div class="portal-section-bar">{html.escape(свод["title"])}</div>'
                f'<div class="sf-tabs">{вкладки}</div>'
                f'<p class="portal-page-lead">Порядок: {html.escape(свод["order_note"])}. '
                f'Голоса: {html.escape(свод["votes_note"])}. '
                f'Доступно записей с оценкой {провайдер}: {свод["available"]}.</p>'
                f'<div class="portal-catalog-tiles">' + "".join(плитки) + '</div>')
        return СТРАНИЦЫ.собрать(оболочка, свод["title"], в["лид"], тело, вариант=в)

    def _оболочка(self):
        """Голова, шапка и подвал берутся у самой витрины."""
        ответ = self._сырое_наверх("/catalog", "")
        if ответ is None:
            return None
        return СТРАНИЦЫ.разобрать_оболочку(ответ[0].decode("utf-8", "replace"))

    def _полезная(self, путь: str) -> str:
        ответ = self._сырое_наверх(путь, "")
        return ответ[0].decode("utf-8", "replace") if ответ else ""

    #: Готовые страницы держатся недолго: собрать одну — это обращение к
    #: главной, каталогу и страницам тайтлов за постерами, то есть секунды.
    #: Пять минут достаточно, чтобы обычный заход был мгновенным, и мало,
    #: чтобы страница успевала устаревать.
    _готовые: dict = {}
    _готовые_до: dict = {}

    _обновляется: set = set()

    def _семейная_страница(self, разд: str) -> bytes | None:
        """Готовая страница отдаётся сразу; устаревшая обновляется в фоне.

        Холодная сборка — это обращения к главной, каталогу и страницам
        тайтлов: секунды. Пока она шла в запросе, посетитель ждал, и при
        нескольких проверках подряд браузер успевал отвалиться по таймауту —
        десять провалов на одном домене были именно этим, а не поломкой
        страницы.

        Поэтому просроченная страница отдаётся как есть, а обновление идёт
        отдельным потоком: устаревшая на несколько минут витрина лучше, чем
        витрина, которая думает пятнадцать секунд.
        """
        import threading
        import time as _t
        готово = type(self)._готовые.get(разд)
        свежо = _t.time() < type(self)._готовые_до.get(разд, 0)
        if готово and свежо:
            return готово

        def обновить():
            try:
                собрано = self._собрать_страницу(разд)
                if собрано is not None:
                    type(self)._готовые[разд] = собрано
                    type(self)._готовые_до[разд] = _t.time() + 300
            finally:
                type(self)._обновляется.discard(разд)

        if готово:
            # Устаревшая страница есть — отдаём её и обновляем в фоне.
            if разд not in type(self)._обновляется:
                type(self)._обновляется.add(разд)
                threading.Thread(target=обновить, daemon=True).start()
            return готово
        # Первой сборки ещё не было: приходится подождать.
        собрано = self._собрать_страницу(разд)
        if собрано is not None:
            type(self)._готовые[разд] = собрано
            type(self)._готовые_до[разд] = _t.time() + 300
        return собрано

    #: Какая поверхность контракта относится к какой странице.
    #:
    #: Каждая — ровно к одной. /new/ и /schedule/ не должны показывать один
    #: массив под разными заголовками: именно так /collections/ и /schedule/
    #: однажды совпали на 100 % и обе выглядели работающими.
    ПОВЕРХНОСТИ_СТРАНИЦ = {
        "/new": ("new_episodes", "ongoing"),
        "/collections": ("trending", "news"),
        "/schedule": ("schedule", "announcements"),
    }
    #: Поверхности, которые рисуются не плиткой, а списком материалов.
    МАТЕРИАЛЫ = ("news", "announcements")

    def _секции_контракта(self, разд: str) -> str:
        """Поверхности контракта в порядке варианта домена.

        Пустая поверхность не рисуется вовсе: ни заголовка, ни рамки. Пустое
        место на странице читается как поломка, а «пока пусто» в рамке — как
        работающий раздел без данных. Ни то, ни другое не правда: событий нет.
        """
        if ВИД is None:
            return ""
        нужные = self.ПОВЕРХНОСТИ_СТРАНИЦ.get(разд, ())
        if not нужные:
            return ""
        контур = self._ленты_контура(нужные=нужные)
        в = ВАРИАНТЫ_МОД.вариант(ВАРИАНТ_ДОМЕНА) if ВАРИАНТЫ_МОД else {}
        порядок = [п for п in (в.get("поверхности") or []) if п in нужные]
        порядок += [п for п in нужные if п not in порядок]
        # Защита от нарезки одного массива: совпавшая с соседней поверхность
        # не рисуется. Проверка живёт в коде, а не в намерении.
        отобрано, куски = {}, []
        for п in порядок:
            элементы = контур.get(п) or []
            if not элементы:
                continue
            if ВИД.совпадения({**отобрано, п: элементы}):
                continue
            отобрано[п] = элементы
            куски.append(ВИД.лента(
                п, элементы,
                плитка=(ВИД.пост if п in self.МАТЕРИАЛЫ else None),
                сеткой=п not in self.МАТЕРИАЛЫ))
        return "".join(куски)

    def _собрать_страницу(self, разд: str) -> bytes | None:
        оболочка = self._оболочка()
        if оболочка is None:
            return None
        главная = self._полезная("/")
        каталог_плиток = self._карта_постеров()
        # Поверхности контракта идут первыми: это события, а не каталог.
        контракт = self._секции_контракта(разд)

        def лента(имя, предел=24):
            э = СТРАНИЦЫ.дополнить_постерами(
                СТРАНИЦЫ.раздел_главной(главная, имя, предел), каталог_плиток)
            return self._разрешить_постеры(э)

        if разд == "/new":
            блоки = [
                ("Новые серии", "Свежие эпизоды вышедших сериалов."),
                ("Появилось видео", "Тайтлы, у которых только что появилось видео."),
                ("Сейчас выходят", "Продолжающиеся сериалы этого сезона."),
            ]
            тело = контракт + "".join(
                СТРАНИЦЫ.секция(з, "Сейчас в этом разделе пусто. Как только витрина "
                                   "получит новые события, они появятся здесь.",
                                лента(з))
                for з, _ in блоки)
            в = ВАРИАНТЫ_МОД.вариант(ВАРИАНТ_ДОМЕНА) if ВАРИАНТЫ_МОД else {}
            заг = {"episodes-schedule": "Новые серии и обновления",
                   "editorial-guide": "Что смотреть прямо сейчас",
                   "catalog-search": "Свежие поступления каталога"}.get(
                       в.get("variant_id"), "Новинки и свежие серии")
            лид = {"episodes-schedule": ("События появления серий и то, что продолжает "
                                         "выходить. Время события — настоящее, а не "
                                         "время пересборки сайта."),
                   "editorial-guide": ("Поводы посмотреть на этой неделе: что вышло, "
                                       "что обсуждают и что вот-вот продолжится."),
                   "catalog-search": ("Что недавно добавлено и обновлено в каталоге. "
                                      "Отсюда удобно уходить в поиск и фильтры.")}.get(
                       в.get("variant_id"), "Свежие серии и поступления.")
            return СТРАНИЦЫ.собрать(оболочка, заг, лид, тело, вариант=в)

        if разд == "/collections":
            каталог = каталог_плиток[:24]
            части = []
            # «Анонсы» намеренно НЕ здесь: заявленные релизы относятся к
            # расписанию, а не к редакционным подборкам. Пока они стояли в
            # обоих разделах, /collections/ и /schedule/ совпадали на 75 %.
            for имя, подпись in (("Аниме летнего сезона", "Сезонная подборка витрины."),
                                 ("Актуальное", "То, что витрина считает актуальным."),
                                 ("Новое на сайте", "Недавно добавленное в каталог.")):
                части.append(СТРАНИЦЫ.секция(
                    имя, "Редакционных материалов в этой группе пока нет.",
                    лента(имя)))
            # Группа по рейтингу собирается из каталога — это не выдуманные
            # данные, а та же витрина, отсортированная по её же оценке.
            с_оценкой = [з for з in каталог if з.get("rating")]
            с_оценкой.sort(key=lambda з: float(з["rating"] or 0), reverse=True)
            части.append(СТРАНИЦЫ.секция(
                "Высокие оценки", "В каталоге пока нет тайтлов с оценкой.",
                с_оценкой[:12]))
            части.append(
                '<div class="portal-section-bar">Редакционное</div>'
                '<p class="portal-page-lead">Статьи, обзоры и авторские материалы '
                'витрины: <a href="/posts">записи</a>, <a href="/reviews">обзоры</a>, '
                '<a href="/blogger">блогеры</a>. Разделы ведёт сама витрина.</p>')
            в = ВАРИАНТЫ_МОД.вариант(ВАРИАНТ_ДОМЕНА) if ВАРИАНТЫ_МОД else {}
            заг = {"editorial-guide": "Редакционные подборки",
                   "episodes-schedule": "Сезон и ближайшее",
                   "catalog-search": "Жанры, годы и высокие оценки"}.get(
                       в.get("variant_id"), "Подборки")
            лид = в.get("лид", "Подборки витрины.")
            # Порядок секций — часть профиля домена: у редакционного гида
            # сначала подборки, у каталожного — оценки.
            if в.get("variant_id") == "catalog-search":
                части.reverse()
            return СТРАНИЦЫ.собрать(оболочка, заг, лид, контракт + "".join(части),
                                    вариант=в)

        if разд == "/schedule":
            выходят = лента("Сейчас выходят", 40)
            анонсы = лента("Анонсы", 20)
            тело = (СТРАНИЦЫ.секция(
                "Сейчас выходят", "Продолжающихся сериалов сейчас нет.", выходят)
                + СТРАНИЦЫ.секция("Анонсы", "Анонсов пока нет.", анонсы)
                + '<div class="portal-section-bar">По дням недели</div>'
                '<p class="portal-empty">Подтверждённых дат и номеров серий контур '
                'сейчас не отдаёт, поэтому дни недели не строятся: показывать сетку '
                'с выдуманными сериями нельзя. Календарь премьер витрины — '
                '<a href="/catalog/schedule">/catalog/schedule</a>; он покажет даты '
                'в тот же момент, что и этот раздел. Выше — то, что известно '
                'сейчас: что выходит и что заявлено.</p>')
            в = ВАРИАНТЫ_МОД.вариант(ВАРИАНТ_ДОМЕНА) if ВАРИАНТЫ_МОД else {}
            заг = {"episodes-schedule": "Расписание выходов",
                   "editorial-guide": "Что выходит и что заявлено",
                   "catalog-search": "Расписание и онгоинги"}.get(
                       в.get("variant_id"), "Расписание")
            return СТРАНИЦЫ.собрать(
                оболочка, заг,
                "Что выходит сейчас и что заявлено. Дни недели появятся, когда "
                "контур начнёт отдавать подтверждённые даты серий.",
                контракт + тело, вариант=в)
        return None

    def _обогатить(self, тело: bytes, тип: str) -> bytes:
        """Объявление версии и служебный бейдж в проксируемой странице.

        Вынесено отдельным методом, потому что применяется и к обычному
        проксированию, и к поиску с расширением запроса: объявление версии
        обязано быть на ВСЕХ маршрутах, включая выдачу поиска и 404.
        """
        if "text/html" not in тип or b"</head>" not in тело:
            return тело
        # Только объявление версии и небольшой служебный бейдж. Стиль
        # приложения не трогается: подмешивать сюда чужую таблицу стилей
        # значило бы снова перекрашивать готовую витрину.
        вставка = (
            f'<meta name="site-factory-template-revision" content="{МАНИФЕСТ["source_commit"]}">'
            f'<meta name="site-factory-design-version" content="{ВЕРСИЯ}">'
            f'<meta name="site-factory-template-family" content="{СЕМЕЙСТВО}">'
            f'<meta name="site-factory-template" content="{ШАБЛОН_СЕМЕЙСТВА}">'
            f'<meta name="site-factory-core" content="{ЯДРО}">'
            f'<meta name="site-factory-profile" content="{ПРОФИЛЬ}">'
            f'<meta name="site-factory-build-id" content="{СБОРКА}">'
            f'<meta name="site-factory-artifact-sha256" content="{МАНИФЕСТ["artifact_sha256"]}">'
            f'<meta name="site-factory-entity-view" content="{ВИД.КОНТРАКТ if ВИД else ""}">'
            f'<style>{БЕЙДЖ_СТИЛЬ}{ВИД.СТИЛЬ if ВИД else ""}'
            f'{self._токены_варианта()}</style>').encode("utf-8")
        # Ссылки карточек приводятся к каноническому виду.
        #
        # Приложение отдаёт часть ссылок как «/anime/<слаг>--<uuid>». Такой
        # адрес рабочий — он отвечает постоянным редиректом, — но ведёт
        # посетителя и краулер через лишний переход и расходится с canonical
        # самой страницы. Единственный контракт адресов требует публиковать
        # канонический путь, поэтому хвост снимается прямо в разметке.
        тело = re.sub(
            rb'(/anime/[a-z0-9-]+?)--[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}'
            rb'-[0-9a-f]{4}-[0-9a-f]{12}', rb'\1', тело)

        # Существующий robots витрины ЗАМЕНЯЕТСЯ, а не дополняется:
        # приложение отдаёт «noindex, follow», и добавление второго тега
        # оставляло бы первым менее строгий. Требование — nofollow.
        тело = re.sub(rb'<meta\s+name="robots"[^>]*>',
                      b'<meta name="robots" content="noindex, nofollow">',
                      тело, flags=re.I)
        if not re.search(rb'<meta\s+name="robots"', тело, re.I):
            вставка += b'<meta name="robots" content="noindex, nofollow">'
        тело = тело.replace(b"</head>", вставка + b"</head>", 1)
        # Атрибуты версии на корневом элементе — для машинной проверки.
        тело = re.sub(rb"<html\b", (
            f'<html data-template-version="{ВЕРСИЯ}" '
            f'data-template-family="{СЕМЕЙСТВО}" '
            f'data-build-id="{СБОРКА}"').encode("utf-8"), тело, count=1)
        тело = self._вставить_навигацию(тело)
        # Дополнение карточки встаёт ПЕРЕД подвалом, а не в середину
        # содержимого: страницу тайтла витрина досылает потоком, и вставка
        # между её кусками рискует разойтись с гидратацией.
        доп = self._дополнение_карточки(unquote(urlparse(self.path).path))
        if доп:
            куда = тело.rfind(b"<footer")
            if куда > 0:
                тело = тело[:куда] + доп + тело[куда:]
            elif b"</body>" in тело:
                тело = тело.replace(b"</body>", доп + b"</body>", 1)
        if b"</body>" in тело:
            бейдж = (f'<div class="sf-vbadge">Template: {СЕМЕЙСТВО} {ВЕРСИЯ} · '
                     f'{МАНИФЕСТ["source_commit"][:8]}</div>').encode("utf-8")
            тело = тело.replace(b"</body>", бейдж + b"</body>", 1)
        return тело

    def _токены_варианта(self) -> str:
        """Акцент и плотность сетки компонентов — из профиля домена."""
        if ВАРИАНТЫ_МОД is None:
            return ""
        в = ВАРИАНТЫ_МОД.вариант(ВАРИАНТ_ДОМЕНА)
        return (":root{--sf-accent:" + в.get("акцент", "#ff5c8a")
                + ";--sf-accent-2:" + в.get("акцент2", "#ffb347")
                + ";--sf-grid:" + в.get("плотность",
                                        "repeat(auto-fill,minmax(150px,1fr))") + "}")

    def наверх(self, разбор):
        """Проксирование в прежнее приложение витрины.

        Для маршрутов поиска применяется расширение запроса: если полный
        запрос не дал результатов, пробуются сокращённые варианты.

        Разметка не переписывается: добавляется только стиль и мета-данные
        версии, и только в HTML. Всё прочее идёт байт в байт.
        """
        import http.client
        # Путь и запрос кодируются перед отправкой наверх.
        #
        # http.client пишет строку запроса в ASCII, а маршруты витрины бывают
        # кириллическими: «/search?q=океан» и любой несуществующий русский
        # адрес роняли поток обработчика UnicodeEncodeError, и наружу уходил
        # 502 вместо выдачи поиска и честной страницы 404.
        безопасно = "/:@!$&'()*+,;=~-._%"
        адрес = quote(разбор.path, safe=безопасно)
        if разбор.query:
            адрес += "?" + quote(разбор.query, safe=безопасно + "?&=")
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
            # Тип не подменяется на octet-stream: у редиректа тела нет, и
            # выдумывать ему тип значит ломать переход.
            тип = ответ.getheader("Content-Type") or ""
            перенос = [(и, ответ.getheader(и)) for и in ПЕРЕНОСИМЫЕ
                       if ответ.getheader(и)]
            код = ответ.status
            соед.close()
        except OSError as ош:
            тело = оболочка(f'<div class="empty">Витрина недоступна: {html.escape(str(ош)[:80])}</div>',
                            "503", self.данные).encode("utf-8")
            return self._отдать(тело, код=503)
        тело = self._обогатить(тело, тип)
        return self._отдать(тело, тип, код=код, ещё=перенос)

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
    сервер = ThreadingHTTPServer((args.host, args.port), Обработчик)
    print(f"[nova] {args.host}:{args.port} ревизия {РЕВИЗИЯ[:12]} "
          f"тайтлов {len(Обработчик.данные.items)}", flush=True)
    сервер.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
