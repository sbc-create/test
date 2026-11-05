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
import copy
import json
from array import array
import os
import re
import sys
import threading
import time
import unicodedata
from difflib import SequenceMatcher
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import parse_qs, parse_qsl, quote, unquote, urlencode, urlparse


#: Режим индексации. Домен и разрешение выпуска приходят окружением из
#: `run.py`: разрешение едет с кодом, состояние живёт вне выпуска.
ИНДЕКС_ДОМЕН = os.environ.get("LORDS_INDEXING_SITE", "").strip()
#: Строго строка "true". Любое другое значение — «не разрешено»: разрешение
#: индексации не то место, где удобно быть снисходительным к типу.
ИНДЕКС_РАЗРЕШЕНО_ВЫПУСКОМ = (
    os.environ.get("LORDS_INDEXING_RELEASE_PERMITS_OPEN", "").strip().lower()
    == "true")


def режим_индексации() -> tuple:
    """(состояние, причина). Любая беда — ЗАКРЫТО с названной причиной.

    Отсутствие модуля — тоже закрыто: витрина, которая не умеет спросить про
    режим, не вправе считать себя открытой.
    """
    try:
        import indexing_mode
    except ImportError:
        return ("CLOSED", "модуль indexing_mode не найден: режим не вычисляется")
    try:
        return indexing_mode.режим(
            ИНДЕКС_ДОМЕН, разрешено_выпуском=ИНДЕКС_РАЗРЕШЕНО_ВЫПУСКОМ)
    except Exception:  # noqa: BLE001 — беда режима не открывает сайт
        return ("CLOSED", "ошибка вычисления режима")


def мета_роботов() -> str:
    """Значение `<meta name="robots">` и `X-Robots-Tag` обычных страниц."""
    состояние, _ = режим_индексации()
    try:
        import indexing_mode
        return indexing_mode.МЕТА[состояние]
    except Exception:  # noqa: BLE001
        return "noindex, nofollow"


def мета_роботов_пути(путь: str) -> str:
    """Значение `X-Robots-Tag` для КОНКРЕТНОГО пути: служебные закрыты всегда.

    Измерено 2026-10-04 на открытом домене: `/healthz` отдавал ДВА заголовка —
    `index, follow` от приложения и `noindex, nofollow` от nginx. Запрет
    держался только на слое nginx, а ответ противоречил сам себе. Полагаться на
    разрешение конфликта нельзя: запрет служебного пути обязан стоять там, где
    этот путь и отдаётся.

    Перечень берётся из `indexing_mode.СЛУЖЕБНЫЕ_ЗАПРЕТЫ` — того же, из
    которого собираются `robots.txt` и карта запретов nginx.
    """
    try:
        import indexing_mode
        служебные = tuple(indexing_mode.СЛУЖЕБНЫЕ_ЗАПРЕТЫ)
    except Exception:  # noqa: BLE001 — без модуля служебные всё равно закрыты
        служебные = ("/poster/", "/api/", "/healthz", "/__")
    п = (путь or "/").split("?", 1)[0]
    if any(п.startswith(с) for с in служебные):
        return "noindex, nofollow"
    # Подборка, которую редакция объявила закрытой, закрыта и здесь. Обратное
    # («open: true») правом не является: страница подборки не может быть
    # открытее витрины, иначе решение о режиме домена обходилось бы файлом.
    if п.startswith("/collection/"):
        ключ = п[len("/collection/"):].strip("/")
        if ключ in ЗАКРЫТЫЕ_ПОДБОРКИ:
            return "noindex, nofollow"
    return мета_роботов()


def _тело_robots() -> str:
    """Содержимое `/robots.txt` по текущему режиму.

    Ссылка на карту ставится ТОЛЬКО если карта действительно отдаётся:
    `Sitemap:` на адрес, отвечающий 404, — обещание, которого витрина не
    выполняет, и обходчик запоминает именно его. Условий три, и все
    обязательны: открытый режим, заданный каталог карты и существующий в нём
    `sitemap.xml`.
    """
    состояние, _ = режим_индексации()
    карта = ""
    if состояние == "OPEN" and SITEMAP_DIR and ДОМЕН_КАРТЫ:
        try:
            if (Path(SITEMAP_DIR) / "sitemap.xml").is_file():
                карта = f"https://{ДОМЕН_КАРТЫ}/sitemap.xml"
        except OSError:
            карта = ""
    try:
        import indexing_mode
        return indexing_mode.robots_txt(состояние, sitemap=карта)
    except Exception:  # noqa: BLE001 — без модуля остаёмся закрытыми
        return "User-agent: *\nDisallow: /\n"

РЕВИЗИЯ = os.environ.get("LORDS_TEMPLATE_REVISION", "unknown")


def _часы_datetime() -> datetime:
    """Injectable clock (tests) or UTC now."""
    сырьё = (os.environ.get("LORDS_CLOCK_ISO") or "").strip()
    if сырьё:
        try:
            return datetime.fromisoformat(сырьё.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def текущий_год_часов() -> int:
    """Calendar year from injectable clock (tests) or UTC now — never MAX(catalog year)."""
    return _часы_datetime().year


def текущая_дата_часов() -> str:
    """YYYY-MM-DD from injectable clock or UTC now."""
    return _часы_datetime().strftime("%Y-%m-%d")


#: kind path ↔ catalog kind (Zona/Lords clean routes).
ВИД_ПО_МАРШРУТУ = {
    "/movies": "Фильм",
    "/series": "Сериал",
    "/animation": "Мультфильм",
}
МАРШРУТ_ПО_ВИДУ = {v: k for k, v in ВИД_ПО_МАРШРУТУ.items()}

#: Разделы Zona Cinema по категории, а не по полю `kind` снимка.
#:
#: Зачем отдельная карта. Поле `kind` знает три значения, а разделов четыре:
#: аниме и дунхуа приходят из снимка как «Сериал» и «Фильм», поэтому по `kind`
#: они попадали на главную и в «Сериалы», а раздела «Дорамы» не существовало
#: вовсе. Карта не заменяет `ВИД_ПО_МАРШРУТУ`: тот остаётся фасетом `?kind=`
#: каталога и семейств, где категорий нет. Подменять его молча значило бы
#: менять и соседние семейства из правки, которая касается только Zona.
КАТЕГОРИЯ_ПО_МАРШРУТУ = {
    "/movies": "movie",
    "/series": "series",
    "/animation": "animation",
    "/doramas": "dorama",
}
МАРШРУТ_ПО_КАТЕГОРИИ = {v: k for k, v in КАТЕГОРИЯ_ПО_МАРШРУТУ.items()}

#: Категории, встречающиеся в запросе. Отбор различает их от значений `kind`
#: по принадлежности этому множеству, а не по виду строки.
ЗНАЧЕНИЯ_КАТЕГОРИЙ = frozenset(КАТЕГОРИЯ_ПО_МАРШРУТУ.values())

#: Категория → её раздел. Тот же словарь, что `МАРШРУТ_ПО_КАТЕГОРИИ`, отдельным
#: именем: в разметке чипсов читается как «куда ведёт эта категория».
КАТЕГОРИЯ_ПО_МАРШРУТУ_ОБРАТНО = dict(МАРШРУТ_ПО_КАТЕГОРИИ)

#: Подписи разделов для чипсов и вкладок — и для категорий, и для прежних
#: значений `kind`. Один словарь на оба словаря ключей: две таблицы подписей
#: для одних и тех же разделов разошлись бы.
ПОДПИСЬ_РАЗДЕЛА = {
    "movie": "Фильмы", "series": "Сериалы",
    "animation": "Анимация", "dorama": "Дорамы",
    "Фильм": "Фильмы", "Сериал": "Сериалы", "Мультфильм": "Анимация",
}

#: B13 /new/ temporal modes. Tabs without a real ledger are omitted (not filled
#: from a neighbour date). provider/episode feeds are absent in current sidecars.
NEW_MODE_PREMIERE = "premiere"
NEW_MODE_ADDED = "added"
NEW_MODE_LABELS = {
    NEW_MODE_PREMIERE: "Премьеры",
    NEW_MODE_ADDED: "Добавлено на сайт",
}
NEW_MODE_DEFS = {
    NEW_MODE_PREMIERE: "Сначала самые свежие премьеры.",
    NEW_MODE_ADDED: "Сначала то, что недавно появилось на сайте.",
}


def _формат_даты_карточки(значение: str) -> str:
    """UTC/ISO or YYYY-MM-DD → DD.MM.YYYY; empty if unusable."""
    s = (значение or "").strip()
    if not s:
        return ""
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        y, m, d = s[:10].split("-")
        if y.isdigit() and m.isdigit() and d.isdigit():
            return f"{d}.{m}.{y}"
    return ""


def _подпись_свежести(запись: dict, mode: str = NEW_MODE_PREMIERE) -> str:
    """Подпись свежести для карточек — только по переданным источником датам.

    Внутри подписи разделителя нет намеренно. Подпись встаёт последним
    элементом в строку, склеенную через « · » («драма · спорт · Добавлено
    22.09.2026»), и собственная точка сделала бы «Добавлено · 22.09.2026»
    четвёртым элементом того же уровня: читатель не может понять, дата это
    часть подписи или следующий жанр.

    Какая это дата, сказано словом, а не догадкой: «Добавлено» — дата
    попадания записи в каталог (`published_at`), «Премьера» и «Ожидается» —
    дата премьеры источника (`premiere_date`). Одно вместо другого здесь
    подставить нечем: режим передаётся явно, а у каждого режима своё поле.
    """
    if mode == NEW_MODE_ADDED:
        показан = _формат_даты_карточки(дата_поступления(запись))
        return f"Добавлено {показан}" if показан else ""
    prem = (запись.get("_premiere_date") or "").strip()
    if not prem:
        return ""
    показан = _формат_даты_карточки(prem)
    if not показан:
        return ""
    if prem[:10] > текущая_дата_часов():
        return f"Ожидается {показан}"
    return f"Премьера {показан}"


#: Во сколько раз пачка записей с ОДНОЙ И ТОЙ ЖЕ секундой `published_at` должна
#: превышать обычную, чтобы считаться первоначальным импортом, а не
#: поступлениями. Порог берётся от размера снимка, а не числом из головы:
#: снимок меняется, а доля — нет. Нижняя граница страхует маленький снимок.
ДОЛЯ_ПАКЕТА_ИМПОРТА = 0.005
МИНИМУМ_ПАКЕТА_ИМПОРТА = 200


def пакеты_импорта(items) -> frozenset:
    """Секунды `published_at`, в которые «поступило» неправдоподобно многое.

    Зачем. В снимке 53 688 записей 13 299 несут одну и ту же секунду
    `2024-11-12T12:20:11Z` — это первоначальный импорт каталога, а не 13 299
    поступлений за секунду. Следующая по величине пачка — 15 записей: обычная
    почасовая доставка. Разрыв между 15 и 13 299 не пограничный, поэтому порог
    ошибиться не может, но он всё равно считается от снимка, а не записан
    числом: после очередной доставки каталога и размер, и дата импорта будут
    другими, а доля — той же.

    Витрина не «чинит» эти даты и не придумывает им замену: она лишь перестаёт
    называть их поступлениями. Сама дата остаётся в записи и доступна.
    """
    if not items:
        return frozenset()
    порог = max(МИНИМУМ_ПАКЕТА_ИМПОРТА, int(len(items) * ДОЛЯ_ПАКЕТА_ИМПОРТА))
    счёт: dict[str, int] = {}
    for з in items:
        отметка = (з.get("published_at") or "").strip()
        if отметка:
            счёт[отметка] = счёт.get(отметка, 0) + 1
    return frozenset(о for о, н in счёт.items() if н >= порог)


def дата_поступления(запись: dict) -> str:
    """`published_at`, когда он означает поступление, иначе пусто.

    Запись из пачки первоначального импорта поступлением не считается: её дата
    говорит, когда каталог завели, а не когда произведение на витрине
    появилось. Выдавать одно за другое — это и есть «старое выдать за новое».
    """
    if запись.get("_импорт"):
        return ""
    return (запись.get("published_at") or "").strip()


#: Слова, которыми части одной франшизы отличаются друг от друга.
_ХВОСТЫ_ФРАНШИЗЫ = frozenset({"финал", "final", "часть", "сезон", "part", "season"})
#: Номер части: арабский или римский. `re.fullmatch`, а не поиск в строке.
_НОМЕР_ЧАСТИ = re.compile(r"(?:\d{1,3}|[ivxlcdm]{1,7})\Z")


def франшиза(название: str) -> str:
    """Ключ франшизы: «Братик-братик 3» и «Братик-братик: Финал» — один ключ.

    Зачем. Лента поступлений показывала «Братик-братик: Финал»,
    «Братик-братик 3» и «Братик-братик 2» подряд — три карточки из двенадцати
    на одну франшизу. Для зрителя это одна и та же вещь, занявшая четверть
    полки; остальному каталогу места не осталось.

    Почему НЕ через `нормализовать`. Та форма выбрасывает всё, кроме букв и
    цифр, вместе с пробелами: «Братик-братик 3» превращается в
    «братикбратик3», и снять номер с хвоста уже нечем — границы слова нет.
    Поэтому ключ строится по словам (`токены`), а двоеточие разбирается до
    нормализации, пока оно ещё в строке.

    Подзаголовок после двоеточия отбрасывается только когда до двоеточия не
    меньше двух слов: иначе «Любовь: …» склеила бы несвязанные произведения по
    одному общему слову.

    Ключ применяется В ЛЕНТАХ, а не в списках каталога: раздел обязан
    показывать всё, что в нём есть, и прятать там части франшизы значило бы
    терять произведения.
    """
    сырое = (название or "").strip()
    if not сырое:
        return ""
    if ":" in сырое:
        глава = сырое.split(":", 1)[0]
        if len(токены(глава)) >= 2:
            сырое = глава
    слова = токены(сырое)
    # Хвост снимается, пока он остаётся хвостом части, и никогда — до пустоты:
    # «2» как целое название franchise-ключа не имеет и остаётся собой.
    while len(слова) > 1:
        хвост = слова[-1]
        if хвост in _ХВОСТЫ_ФРАНШИЗЫ or _НОМЕР_ЧАСТИ.fullmatch(хвост):
            слова = слова[:-1]
            continue
        break
    return " ".join(слова)


def _доступные_режимы_new(данные: "Данные") -> list:
    """Modes whose ledger has ≥1 verified row in the current snapshot."""
    modes = []
    if any(з.get("_premiere_date") for з in данные.items):
        modes.append(NEW_MODE_PREMIERE)
    if any(дата_поступления(з) for з in данные.items):
        modes.append(NEW_MODE_ADDED)
    # provider_available_at / episode_released_at: no ledger in sidecars → omit.
    return modes


def _нормализовать_режим_new(сырой, доступные: list) -> str:
    """Map query mode to a ledger that exists; default = premiere if present."""
    aliases = {
        None: NEW_MODE_PREMIERE,
        "": NEW_MODE_PREMIERE,
        "premiere": NEW_MODE_PREMIERE,
        "premieres": NEW_MODE_PREMIERE,
        "added": NEW_MODE_ADDED,
        "catalog_added": NEW_MODE_ADDED,
    }
    mode = aliases.get(сырой, сырой)
    if mode in доступные:
        return mode
    if доступные:
        return доступные[0]
    return NEW_MODE_PREMIERE

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

#: Скрипт слайдера героя Zona.
#:
#: Управление появляется только отсюда: пока скрипт не выставил
#: `data-zhero-ready="1"`, кнопки и точки скрыты стилем. Мёртвая кнопка хуже
#: отсутствующей — она обещает действие, которого не произойдёт.
#:
#: Панель текста одна на слайдер, поэтому переключение переписывает её поля по
#: данным активного слайда. Проверка приёмки читает те же поля и видит смену
#: ID, названия, картинки и ссылки, а не только сдвиг картинки.
ЗОНА_СКРИПТ_ГЕРОЯ = """<script>(function(){
var s=document.currentScript&&document.currentScript.closest('[data-zhero-slider]');
if(!s)s=document.querySelector('[data-zhero-slider]');
if(!s)return;
var track=s.querySelector('[data-zhero-track]');
var slides=[].slice.call(s.querySelectorAll('[data-zhero-slide]'));
var dots=[].slice.call(s.querySelectorAll('[data-zhero-dot]'));
if(!track||slides.length<2)return;
var title=s.querySelector('[data-zhero-title]'),meta=s.querySelector('[data-zhero-meta]'),
desc=s.querySelector('[data-zhero-desc]'),cta=s.querySelector('[data-zhero-cta]');
var i=0,timer=null,held=false;
var reduce=window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches;
function apply(n){
 i=(n%slides.length+slides.length)%slides.length;
 track.style.transform='translateX('+(-100*i)+'%)';
 slides.forEach(function(el,k){
  var on=k===i;
  el.setAttribute('data-active',on?'1':'0');
  if(on){el.removeAttribute('aria-hidden');}else{el.setAttribute('aria-hidden','true');}
 });
 dots.forEach(function(d,k){d.setAttribute('aria-selected',k===i?'true':'false');});
 var el=slides[i];
 if(title)title.textContent=el.getAttribute('data-slide-title')||'';
 if(meta)meta.textContent=el.getAttribute('data-slide-meta')||'';
 if(desc){var t=el.getAttribute('data-slide-desc')||'';desc.textContent=t;
  if(t){desc.removeAttribute('hidden');}else{desc.setAttribute('hidden','');}}
 if(cta){var href=el.getAttribute('data-slide-href')||'#';
  var play=el.getAttribute('data-slide-playable')==='1';
  var a=cta.querySelector('[data-zhero-play]'),b=cta.querySelector('[data-zhero-more]');
  if(b)b.setAttribute('href',href);
  if(a){a.setAttribute('href',href);a.style.display=play?'':'none';}
  else if(play){var n2=document.createElement('a');n2.className='primary';
   n2.setAttribute('data-zhero-play','');n2.setAttribute('href',href);n2.textContent='Смотреть';
   cta.insertBefore(n2,cta.firstChild);}}
 s.setAttribute('data-active-index',String(i));
}
function go(n){apply(n);restart();}
function next(){go(i+1);}function prev(){go(i-1);}
function stop(){if(timer){clearInterval(timer);timer=null;}}
function restart(){stop();if(reduce||held)return;
 timer=setInterval(function(){apply(i+1);},7000);}
var pb=s.querySelector('[data-zhero-prev]'),nb=s.querySelector('[data-zhero-next]');
if(pb)pb.addEventListener('click',function(e){e.preventDefault();prev();});
if(nb)nb.addEventListener('click',function(e){e.preventDefault();next();});
dots.forEach(function(d){d.addEventListener('click',function(e){e.preventDefault();
 go(parseInt(d.getAttribute('data-goto'),10)||0);});});
s.addEventListener('keydown',function(e){
 if(e.key==='ArrowRight'){e.preventDefault();next();}
 else if(e.key==='ArrowLeft'){e.preventDefault();prev();}});
s.addEventListener('mouseenter',function(){held=true;stop();});
s.addEventListener('mouseleave',function(){held=false;restart();});
s.addEventListener('focusin',function(){held=true;stop();});
s.addEventListener('focusout',function(){if(!s.contains(document.activeElement)){held=false;restart();}});
var vp=s.querySelector('[data-zhero-viewport]'),x0=null,dx=0;
if(vp&&window.PointerEvent){
 vp.addEventListener('dragstart',function(e){e.preventDefault();});
 vp.addEventListener('pointerdown',function(e){
  // Захват указателя на области просмотра перенаправляет на неё pointerup, и
  // click по вложенной кнопке не доходит. Жест начинается только вне органов
  // управления — иначе свайп отнимал бы нажатия у кнопок и точек.
  if(e.target.closest&&e.target.closest('[data-zhero-prev],[data-zhero-next],[data-zhero-dot]'))return;
  x0=e.clientX;dx=0;held=true;stop();
  try{vp.setPointerCapture(e.pointerId);}catch(err){}});
 vp.addEventListener('pointermove',function(e){if(x0!==null)dx=e.clientX-x0;});
 vp.addEventListener('pointerup',function(){
  if(x0!==null&&Math.abs(dx)>40){if(dx<0)next();else prev();}
  x0=null;dx=0;held=false;restart();});
 vp.addEventListener('pointercancel',function(){x0=null;dx=0;held=false;restart();});
}
// Битая картинка не должна ломать слайдер: слайд остаётся на месте, индексы не
// съезжают, вместо изображения — ровная подложка.
slides.forEach(function(el){var im=el.querySelector('[data-zhero-img]');
 if(im)im.addEventListener('error',function(){im.setAttribute('data-broken','1');
  im.style.visibility='hidden';el.style.background='#1b2027';});});
s.setAttribute('data-zhero-ready','1');
apply(0);restart();
})();</script>"""

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

try:
    import genre_aliases as ЖАНРЫ_АЛИАСЫ  # noqa: E402
except ImportError:  # pragma: no cover
    ЖАНРЫ_АЛИАСЫ = None

#: Подключение утверждённого модуля сообщества (оценки и комментарии).
#: Отсутствие моста не роняет витрину: страницы тогда собираются без оценки
#: посетителя и без обсуждения, то есть как до подключения.
try:
    import community_bridge as СООБЩЕСТВО  # noqa: E402
except ImportError:  # pragma: no cover
    СООБЩЕСТВО = None

#: Редакторские правки поверх данных поставщика. Отсутствие модуля не роняет
#: витрину: страницы тогда показывают ровно то, что сообщил источник, — то
#: есть состояние до подключения админки, а не «как попало».
try:
    import editorial_overlay as РЕДАКЦИЯ  # noqa: E402
except ImportError:  # pragma: no cover
    РЕДАКЦИЯ = None

#: Файл опубликованных правок ЭТОГО сайта. Лежит в хранилище витрины и
#: объявлен `user_writable`: доставка каталога его не перезаписывает, а
#: подключает ссылкой. Без переменной правок нет — подставлять путь по
#: соседству нельзя, это ровно тот случай, когда чужой файл выглядел бы своим.
ФАЙЛ_ПРАВОК = os.environ.get("ZONA_EDITORIAL_OVERRIDES", "")


def _идентификатор_сайта() -> str:
    """site_id этой витрины — для сверки с файлом правок.

    Приходит переменной от пускателя, который читает `config/site.json`.
    Выводить его из `build_id` нельзя: у закреплённого манифеста репозитория
    порядок частей один (`zona-01-a0209877e1db`), у штампованного сборщиком —
    обратный (`a0209877e1db-zona-01`), и обратное чтение метки давало бы то
    верный ответ, то пустой, в зависимости от того, чей манифест прочитан.
    Пустое значение — не повод угадать: тогда правки просто не применяются, и
    причина видна в `/__editorial_status`.
    """
    return os.environ.get("SITE_ID", "")


ИДЕНТИФИКАТОР_САЙТА = _идентификатор_сайта()

#: Категории разделов (фильмы / сериалы / анимация / дорамы). Отсутствие модуля
#: не роняет витрину: разделы тогда работают по прежнему полю `kind`, то есть
#: как до появления категорий, а не как попало.
try:
    import catalog_kinds as КАТЕГОРИИ_КАТАЛОГА  # noqa: E402
except ImportError:  # pragma: no cover
    КАТЕГОРИИ_КАТАЛОГА = None

#: Правило новизны (T284, перенос с zona-03): новинка — по подтверждённой дате
#: ВЫХОДА в окне, а не по дате попадания записи в снимок. Ведущая полка главной
#: «Сейчас на Zona» открывалась фильмами 1920 и 1958 годов, доставленными вчера.
import release_novelty as НОВИЗНА  # noqa: E402


def новинка(запись: dict) -> bool:
    """Новинка ли запись сегодня — по единому правилу `release_novelty`."""
    return НОВИЗНА.статус(запись, _часы_datetime().date()) == НОВИЗНА.НОВИНКА


def правило_новинки():
    """`новинка` для прохода по всему каталогу: часы и окно — один раз.

    Итог запоминается по паре дат выхода записи — правило то же, что у
    `новинка`, без повторного чтения часов и разбора дат на каждую запись.
    """
    сегодня = _часы_datetime().date()
    окно = НОВИЗНА.окно_дней()
    память: dict = {}

    def предикат(запись: dict) -> bool:
        ключ = (запись.get("_выход"), запись.get("_выход_сезона"))
        итог = память.get(ключ)
        if итог is None:
            итог = память[ключ] = НОВИЗНА.статус(запись, сегодня, окно) == НОВИЗНА.НОВИНКА
        return итог
    return предикат

#: Country path aliases → canonical translit code used in the index.
#: Independent audit: /country/velikobritaniya/ must resolve when UK titles exist.
СТРАНЫ_АЛИАСЫ: dict[str, tuple[str, ...]] = {
    "velikobritaniya": (
        "velikobritaniya", "velikobritania", "uk", "gb",
        "united-kingdom", "united_kingdom", "great-britain", "great_britain",
        "england", "angliya",
    ),
    "ssha": ("ssha", "usa", "us", "united-states", "united_states", "amerika"),
    "rossiya": ("rossiya", "russia", "rf", "ru"),
    "franciya": ("franciya", "france", "fr"),
    "germaniya": ("germaniya", "germany", "de", "deutschland"),
    "yaponiya": ("yaponiya", "japan", "jp"),
    "kitay": ("kitay", "china", "cn", "prc"),
    "koreya": ("koreya", "south-korea", "korea", "kr", "yuzhnaya-koreya"),
}


def _канон_страны(код: str, страны: dict) -> str | None:
    """Map country path/query alias to a key that exists in the index."""
    if not код:
        return None
    if код in страны:
        return код
    for канон, aliases in СТРАНЫ_АЛИАСЫ.items():
        if код == канон or код in aliases:
            if канон in страны:
                return канон
            for a in aliases:
                if a in страны:
                    return a
    return None


try:
    import popular_weekly as ПОПУЛЯРНОЕ_НЕДЕЛЯ  # noqa: E402
except ImportError:
    ПОПУЛЯРНОЕ_НЕДЕЛЯ = None

#: Недельный снимок «популярного» (WEEKLY_SNAPSHOT). Не пересчитывается
#: на HTTP-запросе. Путь: LORDS_POPULAR_WEEKLY или рядом с каталогом.
ПОПУЛЯРНОЕ_НЕДЕЛЯ_ФАЙЛ = (
    os.environ.get("LORDS_POPULAR_WEEKLY")
    or _рядом_с_каталогом("{site}-popular-weekly.json")
)
_popular_weekly_cache: dict = {"mtime": None, "data": None}


def сбросить_popular_cache() -> None:
    _popular_weekly_cache["mtime"] = None
    _popular_weekly_cache["data"] = None


def _popular_weekly_snapshot() -> dict | None:
    """Read-only weekly Popular membership. Never builds on the request path."""
    if not ПОПУЛЯРНОЕ_НЕДЕЛЯ or not ПОПУЛЯРНОЕ_НЕДЕЛЯ_ФАЙЛ:
        return _popular_weekly_cache.get("data")
    путь = Path(ПОПУЛЯРНОЕ_НЕДЕЛЯ_ФАЙЛ)
    try:
        mtime = путь.stat().st_mtime
    except OSError:
        return _popular_weekly_cache.get("data")
    if (_popular_weekly_cache.get("data") is not None
            and _popular_weekly_cache.get("mtime") == mtime):
        return _popular_weekly_cache["data"]
    data = ПОПУЛЯРНОЕ_НЕДЕЛЯ.load_snapshot(путь)
    if data is not None:
        _popular_weekly_cache["mtime"] = mtime
        _popular_weekly_cache["data"] = data
    return _popular_weekly_cache.get("data")

#: Минимум оценок источника, при котором оценка годится для показа в полке
#: недельного снимка. Тот же порог стоит в сборщике (`popular_weekly.py`), но
#: снимок пересобирается раз в неделю расписанием владельца: без проверки при
#: чтении выложенный блок до следующей пересборки показывал бы оценку 8.5 по
#: четырнадцати голосам, то есть исправление осталось бы на бумаге.
ПОЛКА_МИН_ОЦЕНОК = int(os.environ.get("POPULAR_MIN_VOTES", "1000"))


def _оценок_у_записи(подробность: dict) -> int:
    """Число оценок источника; нет числа — ноль, и это «неизвестно»."""
    источники = (подробность or {}).get("ratings_by_source") or {}
    лучшее = 0
    for запись in источники.values():
        if not isinstance(запись, dict):
            continue
        try:
            лучшее = max(лучшее, int(запись.get("votes") or 0))
        except (TypeError, ValueError):
            continue
    return лучшее



def _из_weekly_полки(данные: "Данные", weekly: dict | None, ключ: str,
                     *, отбор=None, предел: int | None = None,
                     подробности=None) -> list:
    """Полка недельного снимка → записи каталога.

    Отбор применяется ДО ограничения количества, и именно поэтому к полке
    добавляется её резерв. Снимок нарезан по полю `kind`, а витрина показывает
    разделы по категориям: полка «Фильмы недели», собранная как `kind ==
    «Фильм»`, содержит и дорамы, и полнометражное аниме. Если сначала взять
    двенадцать, а потом отсеять чужие категории, полка выйдет короче
    двенадцати — не потому, что записей нет, а потому, что их отсеяли уже
    после нарезки.

    Резерв для этого и лежит в снимке (`reserves`, следующие 24 по тому же
    ранжированию). Порядок сохраняется: сначала полка, затем резерв, дубликаты
    не повторяются.
    """
    if not weekly:
        return []
    полки = weekly.get("shelves") or {}
    резервы = weekly.get("reserves") or {}
    slugs = list(полки.get(ключ) or [])
    slugs += [s for s in (резервы.get(ключ) or []) if s not in set(slugs)]
    by_slug = {з["slug"]: з for з in данные.items}
    набор = [by_slug[s] for s in slugs if s in by_slug]
    # Порог объёма выборки применяется и при чтении: снимок пересобирается
    # раз в неделю, а показывать мнение десятка человек как «высокую оценку»
    # нельзя ни одного дня. Работа без известного числа оценок не проходит:
    # отсутствие числа — это «неизвестно», а не «мало».
    # Подробности передаются ЯВНО: у снимка каталога их нет, они лежат
    # отдельным объектом. Прежний `getattr(данные, "подробности")` всегда
    # возвращал пусто, и порог молча не применялся.
    записи = getattr(подробности, "записи", None) or {}
    if записи:
        набор = [з for з in набор
                 if _оценок_у_записи(записи.get(з.get("slug")) or {})
                 >= ПОЛКА_МИН_ОЦЕНОК]
    if отбор is not None:
        набор = [з for з in набор if отбор(з)]
    return набор[:предел] if предел else набор

#: Каталог готовых файлов карты сайта. Пусто — карта не отдаётся.
SITEMAP_DIR = os.environ.get("LORDS_SITEMAP_DIR", "").strip()
#: Домен, которым подписываются адреса карты. Та же цепочка переменных, что у
#: сборщика (`seo_layer.запустить_карту`): расхождение имён дало бы карту с
#: адресами одного домена, объявленную на другом.
ДОМЕН_КАРТЫ = (os.environ.get("LORDS_SITE_HOST")
               or os.environ.get("LORDS_INDEXING_SITE")
               or os.environ.get("LORDS_SITE_DOMAIN") or "").strip()
#: Разделы, попадающие в карту сайта. Перечень ЯВНЫЙ и ИЗМЕРЕННЫЙ: в карту
#: идёт только то, что витрина действительно отдаёт кодом 200. У сайтов
#: семейства наборы РАЗНЫЕ — у одного есть `/anime/` и `/dorama/`, у другого
#: те же адреса отвечают 404, — поэтому раздел по аналогии не добавляется.
РАЗДЕЛЫ_КАРТЫ = ("/movies/", "/series/", "/animation/", "/doramas/", "/catalog/", "/collections/", "/new/",)
class _РазделыКарты(tuple):
    """Статические разделы плюс разделы жанров — при каждом обходе (T032).

    Замер 13.10: из 98 жанров ссылку имели 6 (только с главной), в карте сайта
    (62 986 адресов) разделов жанров не было вовсе — 200 и index, но
    обходчику недостижимы. Адрес жанра — тот же, что у ссылки и в canonical
    раздела: /catalog/?genre=<код> (запрос_строкой); только жанры, у которых в
    индексе витрины есть записи. Индекс читается при сборке карты, поэтому
    перечитанный снимок даёт актуальный набор. Литерал выше не трогается: его
    разбирают проверки (sitemap_wired, canonical_requested).
    """

    def __iter__(self):
        yield from tuple.__iter__(self)
        обработчик = globals().get("Обработчик")
        индекс = getattr(обработчик, "индекс", None) or {}
        for код, _имя, _размер in sorted(разделы_жанров(индекс)):
            yield "/catalog/" + запрос_строкой({"genre": код})


def разделы_жанров(индекс: dict) -> list:
    """Разделы жанров витрины: (код, имя, размер) — одно правило для карты
    сайта (T032) и ссылок со страницы каталога (T034).

    Коды — из genre_names (те, что у жанровых ссылок витрины), а не все
    ключи индекса; и ОДИН код на имя жанра — с наибольшим составом: у
    одного имени бывает два кода с разным составом (13.10: «криминал» —
    kriminal 7 511 и criminal 63), и два раздела с одним названием и
    canonical на себя были бы дублями. Технические жанры и пустые — вне.
    """
    по_жанру = индекс.get("genre") or {}
    технические = globals().get("_ТЕХНИЧЕСКИЕ_ЖАНРЫ") or set()
    лучший: dict = {}
    for код, имя in (индекс.get("genre_names") or []):
        ключ_имени = str(имя).strip().casefold()
        размер = len(по_жанру.get(код) or ())
        if not код or not размер or ключ_имени in технические:
            continue
        if ключ_имени not in лучший or размер > лучший[ключ_имени][0]:
            лучший[ключ_имени] = (размер, код, str(имя).strip())
    return [(код, имя, размер) for размер, код, имя in лучший.values()]


РАЗДЕЛЫ_КАРТЫ = _РазделыКарты(РАЗДЕЛЫ_КАРТЫ)


#: Счётчик Яндекс Метрики этой витрины. Публичное число, не секрет: оно и так
#: видно в исходном коде любой страницы. Значение задаёт unit витрины, потому
#: что один процесс обслуживает один домен, а счётчик привязан к домену.
#: Пустое значение означает «счётчика нет» и даёт страницу без тега — не тег,
#: который молчит. Молчащий тег неотличим от работающего до первого отчёта.
СЧЁТЧИК_МЕТРИКИ = os.environ.get("LORDS_METRIKA_COUNTER", "").strip()



#: Закрытый список целей — тот же, что в каноническом рантайме. Имя вне списка
#: не отправляется: опечатка в вызове не должна заводить в кабинете
#: цель-призрак, которой нет в реестре аналитики.
ЦЕЛИ_МЕТРИКИ = (
    "title_view",       # открыта страница произведения
    "search",           # поисковый запрос отправлен (сама фраза не передаётся)
    "filter_apply",     # применён фильтр каталога (значения не передаются)
    "season_select",    # выбран сезон
    "episode_select",   # выбрана серия
    "player_start",     # площадка запросила воспроизведение
    "player_ready",     # плеер поднялся
    "player_error",     # запуск не состоялся
    "block_view",       # рекомендательный блок показан (ключ блока не передаётся)
    "block_click",      # из рекомендательного блока перешли в карточку
)


def цели_метрики(номер: str) -> str:
    """Отправка целей. Ни одного параметра — только имя из закрытого списка.

    Почему параметров нет вовсе. Метрика позволяет передать с целью
    произвольные данные, и один такой вызов из обработчика поиска вынес бы
    поисковую фразу в отчёт. Единственная точка отправки — `window.__sfGoal`,
    и третьего аргумента у неё не существует.

    Почему тип страницы определяется по адресу, а не по разметке: маршруты
    витрины свои и стабильные, а метку в разметку пришлось бы добавить в
    четыре оболочки — четыре места, где легко разойтись.
    """
    имена = ",".join(f'"{и}"' for и in ЦЕЛИ_МЕТРИКИ)
    return (
        "<script>(function(){"
        "if(window.__sfGoal){return;}"
        f"var C={номер},L=[{имена}],S={{}};"
        "function g(n){try{"
        "if(L.indexOf(n)<0){return;}"
        "if(typeof window.ym!=='function'){return;}"
        "window.ym(C,'reachGoal',n);"
        "}catch(e){}}"
        "window.__sfGoal=g;"
        "window.__sfGoalOnce=function(n){if(S[n]){return;}S[n]=1;g(n);};"
        "var p=location.pathname||'';"
        "if(/^\\/title\\//.test(p)){window.__sfGoalOnce('title_view');}"
        "document.addEventListener('submit',function(e){"
        "var f=e&&e.target; if(!f||!f.getAttribute){return;}"
        "var a=f.getAttribute('action')||'';"
        "if(f.getAttribute('role')==='search'||/\\/search\\//.test(a)){g('search');}"
        "},true);"
        "document.addEventListener('click',function(e){"
        "var n=e&&e.target,a=null;"
        "while(n&&n!==document){if(n.tagName==='A'&&n.getAttribute('href')){a=n;break;}n=n.parentNode;}"
        "if(!a){return;}"
        "var h=a.getAttribute('href')||'';"
        "if(/\\/season-\\d+\\/episode-\\d+\\/?$/.test(h)){g('episode_select');}"
        "else if(/\\/season-\\d+\\/?$/.test(h)){g('season_select');}"
        # Переход ИЗ рекомендательного блока: ключ блока остаётся в разметке,
        # в цель он не уходит — третьего аргумента у точки отправки нет.
        "var b=a.closest&&a.closest('[data-block-key]');"
        "if(b){g('block_click');}"
        "},true);"
        # Показ блока: половина высоты в экране. Одна отправка на загрузку
        # страницы, иначе прокрутка туда-сюда накрутила бы показы.
        "function начать(){try{if(!window.IntersectionObserver){return;}"
        "var o=new IntersectionObserver(function(es){"
        "for(var i=0;i<es.length;i++){if(es[i].isIntersecting){"
        "window.__sfGoalOnce('block_view');o.disconnect();return;}}},"
        "{threshold:0.5});"
        "var бл=document.querySelectorAll('[data-block-key]');"
        "if(!бл.length){return;}"
        "for(var j=0;j<бл.length;j++){o.observe(бл[j]);}"
        "}catch(e){}}"
        # Скрипт стоит в head и исполняется ДО разбора body: в этот момент
        # блоков в документе ещё нет, и наблюдать нечего. Поэтому установка
        # откладывается до готовности разметки.
        "if(document.readyState==='loading'){"
        "document.addEventListener('DOMContentLoaded',начать);}else{начать();}"
        "})();</script>"
    )

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
        # Отправка целей идёт ЗДЕСЬ, а не в четырёх оболочках: у тега метрики
        # один вызов на каждую из них, и правка в четырёх местах разошлась бы.
        + цели_метрики(н)
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
    "amd":       ("AMD",        10.0, True),
}

#: Порядок вывода. Фиксированный, а не по величине: переставлять источники
#: местами в зависимости от значения значит каждый раз показывать зрителю
#: разную картину одних и тех же данных.
ПОРЯДОК_ОЦЕНОК = ("kp", "imdb", "shikimori", "mal", "amd")


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
        собрано.update(сырое)
    else:
        for ключ, поле in (("kp", "kinopoisk_rating"), ("imdb", "imdb_rating")):
            if деталь.get(поле) is not None:
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


def _склонение(n: int, one: str, few: str, many: str) -> str:
    """Russian plural: 1 сезон, 2 сезона, 5 сезонов."""
    n = abs(int(n))
    n100 = n % 100
    n10 = n % 10
    if 11 <= n100 <= 14:
        form = many
    elif n10 == 1:
        form = one
    elif 2 <= n10 <= 4:
        form = few
    else:
        form = many
    return f"{n} {form}"


def безопасный_заголовок(значение) -> str:
    """Значение HTTP-заголовка, которое заведомо кодируется в latin-1.

    Живой отказ, ради которого написано. `http.server` кодирует заголовки в
    latin-1 со `strict`, поэтому одна кириллическая буква в значении
    возбуждает UnicodeEncodeError ВНУТРИ отправки ответа — когда строка
    состояния уже ушла. Клиент получает оборванное соединение, и так на каждой
    странице: витрина падает целиком.

    Попасть туда значение может из доставленных данных: `X-Catalog-Revision`
    берётся из снимка. По контракту это шестнадцатеричная строка, но контракт
    соблюдает поставщик, а последствие несёт витрина. Поэтому здесь не
    проверка на «правильность», а гарантия кодируемости: всё, что не
    кодируется, заменяется на `?`, длина ограничена, управляющие символы
    (включая CR и LF — это ещё и расщепление ответа) выбрасываются.

    Заголовок с испорченным значением лучше отсутствующего: он говорит, что
    поле пришло и было негодным, а не молчит об этом.
    """
    текст = str(значение if значение is not None else "")
    текст = "".join(ч for ч in текст if 32 <= ord(ч) < 127 or 160 <= ord(ч) < 256)
    return текст[:200]


def _ld_json_scripts(разметка) -> str:
    """Emit one <script type=application/ld+json> per JSON string.

    `разметка` may be a single JSON string or a list of them (title + breadcrumb).
    """
    if not разметка:
        return ""
    items = разметка if isinstance(разметка, (list, tuple)) else [разметка]
    return "".join(
        f'<script type="application/ld+json">{р}</script>' for р in items if р)


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
                "<span>Оценок пока нет</span></p>")
    def элемент(о):
        голоса = (f'<span class="{класс}__v">{_склонение(int(о["голоса"]), "голос", "голоса", "голосов")}</span>'
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
                     f'aria-label="Оценка зрителей сайта">'
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


def _сжать_юникод(с: str) -> str:
    """NFKC + ё→е + снятие комбинирующих знаков.

    NFKD разбивал «й» на «и»+breve, и `токены("войны")` давали
    `["вои","ны"]` — из‑за этого «Вой» оказывался точным хитом
    запроса «звездные войны».
    """
    с = unicodedata.normalize("NFKC", (с or "").lower()).replace("ё", "е")
    return "".join(ch for ch in с if unicodedata.category(ch) != "Mn")


@lru_cache(maxsize=4096)
def код_жанра(жанр: str) -> str:
    """Код жанра из его названия. Чистая функция строки, потому и запоминается.

    `похожие` перебирает всех соседей того же вида и у каждого превращает
    названия жанров в коды. Профиль страницы произведения zona-01 на снимке
    53 689 записей: `похожие` — 2.801 с из 2.816 с, то есть ВСЯ страница;
    внутри 102 979 вызовов `нормализовать` и 996 445 обращений к
    `unicodedata.category`.

    Повторяемость здесь измерена ДО правки, а не предположена: у 52 135 записей
    из 53 688 нет готовых `genre_codes`, полный обход даёт 178 557 вызовов на
    94 РАЗЛИЧНЫЕ строки жанра — 1899 повторов на строку. (Ровно так и надо было
    проверять прошлый раз: память подробностей на отрисовку не дала ничего,
    потому что там повторов почти не было, и я это выяснил только замером
    после.)

    Кэш не требует сброса: отображение «название жанра → код» не зависит ни от
    снимка, ни от часов. Предел размера стоит на случай мусорных строк в
    данных, а не потому, что словарь жанров растёт.
    """
    return нормализовать(транслит(жанр))


def нормализовать(с: str) -> str:
    """Единая форма для сравнения: регистр, ё/е, дефисы, пробелы, пунктуация."""
    return re.sub(r"[^a-zа-я0-9]+", "", _сжать_юникод(с))


def токены(с: str) -> list[str]:
    """Слова запроса по отдельности: «бункер 1-3 сезон» — это четыре токена."""
    return [т for т in re.split(r"[^a-zа-я0-9]+", _сжать_юникод(с)) if т]


def нормализовать_фразу(с: str) -> str:
    """Фраза с пробелами между словами (для phrase/prefix ranking)."""
    return " ".join(токены(с))


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

#: Длина куска указателя поиска. Три — потому что двухбуквенные куски попадают
#: почти в каждую запись и отбор перестаёт отбирать, а четырёхбуквенные рвутся
#: от одной опечатки в середине короткого слова.
КУСОК = 3


def куски(с: str) -> set[str]:
    """Все подстроки длины КУСОК. Короче куска — пустое множество."""
    if len(с) < КУСОК:
        return set()
    return {с[i:i + КУСОК] for i in range(len(с) - КУСОК + 1)}


def фразы_записи(з: dict) -> list[str]:
    """Названия записи со словами через пробел: русское, оригинальные, синонимы.

    Раньше это считалось внутри `искать()` для каждой записи на каждом запросе:
    две нормализации регулярным выражением и транслитерация на запись, 53 573
    записи, два варианта раскладки — отсюда и бралась основная часть тех
    секунд. Значение зависит только от самой записи, поэтому считается один раз
    при загрузке каталога и дальше читается.
    """
    out = [нормализовать_фразу(з.get("title") or "")]
    for поле in ("original_title", "original_name", "english_name", "alt_title"):
        val = з.get(поле)
        if val:
            out.append(нормализовать_фразу(str(val)))
            out.append(нормализовать_фразу(транслит(str(val))))
    for доп in з.get("aliases") or ():
        out.append(нормализовать_фразу(str(доп)))
    out.append(нормализовать_фразу(транслит(з.get("title") or "")))
    uniq, seen = [], set()
    for p in out:
        if p and p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


class Снимок:
    """Ленивый неизменяемый снимок для контракта коллекций.

    Пересобирается при смене revision каталога. Раньше строился один раз на
    процесс и после atomic publish без restart полки коллекций застывали.
    """

    _снимок = None

    @classmethod
    def получить(cls, данные, подробности):
        if КОЛЛЕКЦИИ is None:
            return None
        ревизия = getattr(данные, "revision", "") or ""
        текущая = getattr(cls._снимок, "data_revision", None) if cls._снимок else None
        if cls._снимок is None or текущая != ревизия:
            cls._снимок = КОЛЛЕКЦИИ.Снимок(
                данные.items, getattr(подробности, "записи", None) or {},
                revision=ревизия)
        return cls._снимок

    @classmethod
    def сбросить(cls) -> None:
        cls._снимок = None


class Данные:
    def __init__(self, путь: str):
        путь_п = Path(путь)
        сырое = json.loads(путь_п.read_text(encoding="utf-8"))
        self.path = str(путь_п)
        try:
            self.mtime = путь_п.stat().st_mtime
        except OSError:
            self.mtime = 0.0
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
            for поле in ("original_title", "original_name", "english_name", "alt_title"):
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
            з["_фразы"] = фразы_записи(з)
        self.years = sorted({з["year"] for з in self.items if з["year"]}, reverse=True)
        self.kinds = sorted({з["kind"] for з in self.items if з["kind"]})
        #: Отбор можно выключить — тогда поиск идёт перебором. Нужно тесту
        #: эквивалентности и как рубильник, если отбор придётся снять на живом.
        self.указатель_включён = True
        self.статистика_поиска: dict[str, object] = {
            "всего": len(self.items), "кандидатов": 0, "полный_перебор": True}
        #: Указатель строится по первому запросу, а не при загрузке. Формы
        #: названия дополняются из sidecar уже после конструктора
        #: (`построить_индекс` → `_дополнить_формы_поиска`), и указатель,
        #: собранный раньше, не знал бы оригинальных названий: запрос
        #: «Dusty Bluffs» не нашёл бы «Пыльные утёсы».
        self._указатель: dict[str, array] | None = None
        self._части: dict[str, array] = {}
        self._префиксы: dict[str, array] = {}

    def сбросить_указатель(self) -> None:
        """Забыть указатель: формы названий изменились, отбор устарел."""
        self._указатель = None
        self._части = {}
        self._префиксы = {}

    def _построить_указатель(self) -> None:
        """Кусок названия → номера записей, у которых он встречается.

        Указатель обязан быть **шире** совпадения: запись, не попавшая в отбор,
        не получит и оценки, то есть исчезнет из выдачи молча.

        Отдельно собираются слова названий короче куска — «я», «и», «не», «о».
        По ним кусок построить нельзя, а нужны они ровно одному месту: ярус 8
        многословного запроса допускает, что слово названия короче токена и
        является его началом («Не время умирать» по запросу «нечто время»).
        Первая версия на всякий случай добавляла такие записи к кандидатам
        всегда — и держала постоянный пол в 16 111 записей из 53 573, то есть
        почти сводила отбор на нет. Поэтому они разложены по самому слову:
        для токена нужны ровно два ведра, `т[:1]` и `т[:2]`.
        """
        указатель: dict[str, array] = {}
        части: dict[str, array] = {}
        префиксы: dict[str, array] = {}

        def добавить(куда: dict[str, array], ключ: str, номер: int) -> None:
            ведро = куда.get(ключ)
            if ведро is None:
                ведро = куда[ключ] = array("i")
            ведро.append(номер)

        for i, з in enumerate(self.items):
            ключи: set[str] = set()
            короткие_слова: set[str] = set()
            начала: set[str] = set()
            for ф in з["_формы"]:
                ключи |= куски(ф)
                начала.add(ф[:1])
                if len(ф) >= 2:
                    начала.add(ф[:2])
            for фраза in з["_фразы"]:
                for слово in фраза.split():
                    if len(слово) < КУСОК:
                        короткие_слова.add(слово)
                    начала.add(слово[:1])
                    if len(слово) >= 2:
                        начала.add(слово[:2])
            for к in ключи:
                добавить(указатель, к, i)
            for слово in короткие_слова:
                добавить(части, слово, i)
            for начало in начала:
                if начало:
                    добавить(префиксы, начало, i)
        self._указатель = указатель
        self._части = части
        self._префиксы = префиксы

    def _кандидаты_короткого(self, т: str) -> set[int]:
        """Кандидаты для запроса из одного слова короче куска: «я», «up», «о».

        Кусок по такому слову не построить, и первая версия честно уходила в
        полный перебор. Перебор верен, но это ровно тот дефект, который здесь
        закрывается, — поэтому слово ищется по началам форм и по словам
        названий. Для одиночного слова этого достаточно: все ярусы, кроме
        мягкого совпадения, требуют либо совпадения формы целиком, либо начала
        формы, либо отдельного слова названия, а мягкое совпадение включается
        только с пяти символов.
        """
        начала = self._префиксы.get(т)
        слова = self._части.get(т)
        итог: set[int] = set()
        if начала:
            итог |= set(начала)
        if слова:
            итог |= set(слова)
        return итог

    def _ведро(self, к: str) -> set[int]:
        часть = self._указатель.get(к)
        return set(часть) if часть else set()

    def _ведро_слова(self, слово: str) -> set[int]:
        часть = self._части.get(слово)
        return set(часть) if часть else set()

    def _кандидаты_токена(self, т: str, один: bool) -> set[int]:
        """Записи, в которых токен вообще может совпасть.

        Для одиночного токена все ярусы, кроме мягкого совпадения, требуют,
        чтобы токен целиком входил в форму названия — значит, запись обязана
        лежать во всех его кусках сразу, и пересечение корректно. Мягкое
        совпадение требует лишь общего префикса в четыре символа, поэтому к
        пересечению добавляются записи, совпавшие по двум первым кускам.
        Ярус 8 одиночному запросу недоступен, поэтому короткие слова тут не
        нужны.

        Для многословного запроса ярус 8 допускает обратное отношение — слово
        названия короче токена и является его началом. Тогда запись лежит не во
        всех кусках токена, а только в кусках этого слова, и пересечение по
        кускам одного токена потеряло бы её. Поэтому там берётся объединение,
        плюс два ведра коротких слов; селективность даёт пересечение уже между
        токенами.
        """
        наборы = [self._ведро(к) for к in sorted(куски(т))]
        if not наборы:
            return set()
        if not один:
            общее = set().union(*наборы)
            общее |= self._ведро_слова(т[:1])
            if len(т) >= 2:
                общее |= self._ведро_слова(т[:2])
            return общее
        общее = set(наборы[0])
        for набор in наборы[1:]:
            общее &= набор
        if len(т) >= 5:
            общее |= self._ведро(т[0:3]) & self._ведро(т[1:4])
        return общее

    def _отбор(self, варианты_значимых: list[list[str]]) -> set[int] | None:
        """Номера записей-кандидатов. None — честный переход на полный перебор."""
        if not self.указатель_включён:
            return None
        if self._указатель is None:
            self._построить_указатель()
        if not self._указатель:
            return None
        отобрано: set[int] = set()
        for значимые in варианты_значимых:
            один = len(значимые) == 1
            # Сужать можно только по тем токенам, для которых отбор доказуемо
            # шире совпадения. Короткое слово внутри многословного запроса
            # сужению не поддаётся (ярус 7 ищет его подстрокой где угодно),
            # поэтому оно просто не участвует в пересечении — селективность
            # дают остальные токены.
            годные = [т for т in значимые if len(т) >= КУСОК]
            if not годные:
                if not один:
                    # Все слова короче куска и их больше одного: сузить нечем.
                    return None
                отобрано |= self._кандидаты_короткого(значимые[0])
                continue
            общее: set[int] | None = None
            for т in годные:
                ведро = self._кандидаты_токена(т, один)
                общее = ведро if общее is None else (общее & ведро)
                if not общее:
                    break
            if общее:
                отобрано |= общее
        return отобрано

    def искать(self, q: str, предел: int = 120) -> list[dict]:
        """Поиск с phrase-first ranking и AND по значимым токенам.

        «звездные войны» больше не матчит «Вой»: токены не режутся по
        combining marks, а частичный фрагмент не обгоняет полную фразу.
        Popularity/rating не поднимают нерелевантное выше tier.
        """
        сырой = (q or "").strip()
        if not сырой:
            return []
        # Keyboard layouts are alternative queries, not AND-merged token bags.
        # Merging flipped Latin→Cyrillic tokens into one AND list broke original-
        # title searches («Dusty Bluffs» required mangled «dгыен» tokens too).
        варианты_значимых: list[list[str]] = []
        for v in (сырой, из_раскладки(сырой)):
            значимые_v: list[str] = []
            for т in токены(v):
                if т in СЛУЖЕБНЫЕ or т.isdigit():
                    continue
                if т not in значимые_v:
                    значимые_v.append(т)
            if значимые_v and значимые_v not in варианты_значимых:
                варианты_значимых.append(значимые_v)
        if not варианты_значимых:
            return []

        отобрано = self._отбор(варианты_значимых)
        if отобрано is None:
            смотрим = self.items
            self.статистика_поиска = {
                "всего": len(self.items), "кандидатов": len(self.items),
                "полный_перебор": True}
        else:
            смотрим = [self.items[i] for i in отобрано]
            self.статистика_поиска = {
                "всего": len(self.items), "кандидатов": len(смотрим),
                "полный_перебор": False}

        корзины = {i: [] for i in range(1, 11)}
        видели_slug: set[str] = set()

        def primary_phrase(з: dict) -> str:
            return нормализовать_фразу(з.get("title") or "")

        def forms_compact(з: dict) -> list[str]:
            return list(з.get("_формы") or [])

        def forms_phrase(з: dict) -> list[str]:
            """Предвычисленные фразы записи; см. `фразы_записи()`."""
            фразы = з.get("_фразы")
            return list(фразы) if фразы is not None else фразы_записи(з)

        for значимые in варианты_значимых:
            фраза = " ".join(значимые)
            фраза_слитно = "".join(значимые)

            def all_tokens_ordered(phrase: str, значимые=значимые) -> bool:
                parts = phrase.split()
                if not parts:
                    return False
                i = 0
                for part in parts:
                    if i < len(значимые) and (part == значимые[i] or part.startswith(значимые[i])):
                        i += 1
                return i == len(значимые)

            def strict_prefix_all(phrase: str, значимые=значимые) -> bool:
                parts = phrase.split()
                if len(parts) < len(значимые):
                    compact = phrase.replace(" ", "")
                    pos = 0
                    for т in значимые:
                        j = compact.find(т, pos)
                        if j < 0:
                            return False
                        pos = j + len(т)
                    return True
                used = [False] * len(parts)
                for т in значимые:
                    ok = False
                    for i, p in enumerate(parts):
                        if used[i]:
                            continue
                        if p.startswith(т) or т.startswith(p):
                            used[i] = True
                            ok = True
                            break
                    if not ok:
                        return False
                return True

            for з in смотрим:
                forms = forms_compact(з)
                phrases = forms_phrase(з)
                if not forms and not phrases:
                    continue
                primary = phrases[0] if phrases else ""
                tier = None
                if primary == фраза or нормализовать(з.get("title") or "") == фраза_слитно:
                    tier = 1
                elif any(p == фраза for p in phrases[1:]) or фраза_слитно in forms:
                    tier = 2
                if tier is None and (primary.startswith(фраза + " ") or primary.startswith(фраза)
                                     or нормализовать(з.get("title") or "").startswith(фраза_слитно)):
                    if len(значимые) > 1 or primary.startswith(фраза):
                        tier = 3
                if tier is None and len(значимые) > 1 and (
                        f" {фраза} " in f" {primary} "
                        or фраза_слитно in нормализовать(з.get("title") or "")):
                    tier = 4
                if tier is None and len(значимые) > 1:
                    for p in phrases[1:]:
                        if p.startswith(фраза) or f" {фраза} " in f" {p} ":
                            tier = 5
                            break
                if tier is None and len(значимые) > 1 and all_tokens_ordered(primary):
                    tier = 6
                if tier is None and len(значимые) > 1:
                    blob = " ".join(phrases) + " " + " ".join(forms)
                    if all(т in blob for т in значимые):
                        tier = 7
                if tier is None and len(значимые) > 1 and strict_prefix_all(primary):
                    tier = 8
                if tier is None and len(значимые) == 1:
                    т = значимые[0]
                    if т in forms or primary == т:
                        tier = 1
                    elif primary.startswith(т) or any(f.startswith(т) for f in forms):
                        tier = 3
                    elif any(f" {т} " in f" {p} " for p in phrases) or any(
                            f.startswith(т) or т == f for f in forms):
                        tier = 4
                if tier is None and len(значимые) == 1 and len(значимые[0]) >= 5:
                    т = значимые[0]
                    for f in forms:
                        if _мягкое_совпадение(т, f):
                            tier = 10
                            break
                if tier is None:
                    continue
                year = з.get("year") or 0
                try:
                    year = int(year)
                except (TypeError, ValueError):
                    year = 0
                корзины[tier].append((
                    -year,
                    primary or нормализовать(з.get("title") or ""),
                    з.get("slug") or "",
                    з,
                ))

        итог, видели = [], set()
        for t in range(1, 11):
            for _y, _p, _s, з in sorted(корзины[t]):
                key = з.get("url") or з.get("slug")
                if key in видели:
                    continue
                видели.add(key)
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
<meta name="robots" content="{мета_роботов()}">
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
<footer class="ft"><div class="wrap">{html.escape(ИМЯ_ВИТРИНЫ)} · сайт закрыт от индексации
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

#: Версия оформления Zona с настоящим слайдером героя (ZONA-REAL-SLIDER-01).
#: Её объявляет манифест боевой витрины zona-01, и до этой правки артефакт её
#: не знал: незнакомая версия молча выключала новое оформление и роняла витрину
#: в прежний статический релиз, где лежит 19 страниц произведений из 53 573.
#: Версия добавлена ТОЛЬКО в набор Zona — см. `ПЕРЕРАБОТАНО_С` ниже.
ОФОРМЛЕНИЕ_1_3 = "1.3.0"

#: Версии, несущие оформление 1.1+. Набор, а не одно значение: витрина
#: включает оформление СВОИМ манифестом, и добавление следующей версии не
#: должно переводить на неё соседей. Свойство «переход по одной витрине»
#: сохраняется — меняется только то, сколько версий код умеет исполнять.
ОФОРМЛЕНИЕ_ВЕРСИИ = {ОФОРМЛЕНИЕ_1_1, ОФОРМЛЕНИЕ_1_2, ОФОРМЛЕНИЕ_1_2_1,
                     ОФОРМЛЕНИЕ_1_3}

#: Семейства, переработанные по измеренным эталонам, и версии, с которых
#: переработка включается. Ниже этого набора витрина исполняет прежние ветки.
#:
#: Проверка нужна потому, что артефакт ОДИН на шесть витрин. Без неё выкладка
#: артефакта ради Animedia сменила бы оформление боевой Zona, которая стоит на
#: 1.1.0 и о смене не просила, — то есть ровно то, что запрещает принцип
#: «переход делается по одной витрине». Здесь оформление 1.2.x достаётся
#: только той витрине, чей манифест его объявил.
ПЕРЕРАБОТАНО_С = {
    "zona": frozenset({ОФОРМЛЕНИЕ_1_2, ОФОРМЛЕНИЕ_1_3}),
    "animedia": frozenset({ОФОРМЛЕНИЕ_1_2, ОФОРМЛЕНИЕ_1_2_1}),
}

#: Исполняет ли ЭТА витрина переработанное оформление своего семейства.
ОФОРМЛЕНИЕ_ПЕРЕРАБОТАННОЕ = ВЕРСИЯ in ПЕРЕРАБОТАНО_С.get(СЕМЕЙСТВО, ())

#: Включено ли новое оформление на ЭТОЙ витрине. Решает манифест витрины, а не
#: наличие кода: один артефакт обслуживает шесть витрин, и переход делается по
#: одной. Витрина на 1.0.2 исполняет прежние ветки и отдаёт прежние байты.
ОФОРМЛЕНИЕ_НОВОЕ = (ВЕРСИЯ in ОФОРМЛЕНИЕ_ВЕРСИИ)

#: Семейства, которым провал в прежний статический релиз запрещён.
#:
#: Контракт запасного пути. До этой правки он был один на всех и молчаливый:
#: версия, которой код не знает, выключала новое оформление, и витрина
#: продолжала отвечать 200 — но уже прежним статическим релизом. Для Lords это
#: честный запасной путь: его релиз полон. Для Zona это не запасной путь, а
#: подмена: в `/srv/lords/zona-01/current/site` лежит 19 страниц произведений
#: из 53 573, то есть каждая вторая ссылка витрины ведёт в 404, а витрина при
#: этом выглядит живой и для мониторинга, и для владельца.
#:
#: Поэтому здесь два разных исхода, а не один:
#:   * витрина из этого набора с незнакомой версией НЕ поднимается вовсе —
#:     отказ виден в журнале юнита и чинится одним полем манифеста;
#:   * остальные семейства сохраняют прежнее поведение байт в байт и получают
#:     только строку диагностики.
#:
#: Набор намеренно узкий: менять способ отказа соседям без их задания нельзя.
СТРОГАЯ_ВЕРСИЯ_ОФОРМЛЕНИЯ = frozenset({"zona"})


def _сверить_версию_оформления() -> None:
    """Объявленная версия либо исполняется, либо отвергается — не молча."""
    if ОФОРМЛЕНИЕ_НОВОЕ:
        return
    известные = ", ".join(sorted(ОФОРМЛЕНИЕ_ВЕРСИИ))
    диагноз = (
        f"[{СЕМЕЙСТВО}] манифест {МАНИФЕСТ_ФАЙЛ} объявляет неизвестную версию "
        f"оформления {ВЕРСИЯ!r}; артефакт умеет только: {известные}"
    )
    print(диагноз, file=sys.stderr, flush=True)
    if СЕМЕЙСТВО in СТРОГАЯ_ВЕРСИЯ_ОФОРМЛЕНИЯ:
        raise SystemExit(
            f"{диагноз}. Витрина не поднята намеренно: запасной путь ведёт в "
            f"прежний статический релиз с неполным каталогом, и витрина "
            f"выглядела бы рабочей, отвечая 404 на большинство произведений. "
            f"Чинится одним полем design_version в манифесте.")
    print(f"[{СЕМЕЙСТВО}] исполняется прежняя ветка оформления",
          file=sys.stderr, flush=True)


_сверить_версию_оформления()

#: Шаблоны витрины Zona: объявление состава, а не пятьдесят копий кода.
#:
#: Зачем так. Пятьдесят шаблонов, отличающихся цветом, — это один шаблон и
#: сорок девять перекрасок: выбирать не из чего. Отличаться шаблоны обязаны
#: СТРУКТУРНО — составом и порядком блоков, подачей и шириной героя, ритмом
#: навигации, типом сетки. При этом функциональные и доступностные свойства у
#: всех одни: ровно один H1, живые органы управления, отсутствие переполнения,
#: честные данные. Поэтому здесь объявление, а отрисовка — общая.
#:
#: Оси различия:
#:   герой   — "slider" (дорожка из восьми), "single" (один редакционный кадр
#:             без органов управления), "compact" (лид без кадра);
#:   ширина  — "boxed" (в колонке содержимого) или "full" (во всю ширину окна);
#:   неделя  — "tabs" (вкладки) или "stacked" (три ленты подряд);
#:   новое   — "list" (строки с датой) или "rail" (горизонтальная лента);
#:   сетка   — "tile" (базовая матрица колонок), "wide" (меньше и крупнее),
#:             "dense" (больше и мельче);
#:   свежие  — сколько карточек в плотной сетке новинок (0 — блока нет);
#:   состав  — буквенный код порядка блоков главной.
#:
#: Буквы состава: h — герой, w — неделя, a — поступления, k — входы видов,
#: g — жанры, c — подборки, f — сетка новинок, s — текстовый блок.
#: Блока в составе нет — блока нет на странице; это тоже различие.
#:
#: Шаблон выбирается манифестом витрины (`template_profile`). Отсутствие поля
#: и неизвестное имя дают T001 — то, что витрина отдаёт сегодня.
ЗОНА_БЛОКИ_КОД = {"h": "hero", "w": "weekly", "a": "added", "k": "kinds",
                  "g": "genres", "c": "collections", "f": "fresh", "s": "seo"}

#: Таблица шаблонов. Строка: (id, имя, замысел, герой, ширина, неделя, новое,
#: сетка, свежие, состав). Таблицей, а не пятьюдесятью словарями: пятьдесят
#: словарей читаются хуже и расходятся быстрее, а сверить строки глазами можно
#: только в таблице.
ЗОНА_ТАБЛИЦА_ШАБЛОНОВ = (
    ("T001", "Классическая", "Слайдер, вкладки недели, поступления списком.",
     "slider", "boxed", "tabs", "list", "tile", 0, "hwakgcs"),
    ("T002", "Каталог сразу", "Один кадр, следом плотная сетка новинок.",
     "single", "boxed", "stacked", "rail", "tile", 21, "hfkwagcs"),
    ("T003", "Редакционная", "Слайдер, сразу поступления, затем ленты недели.",
     "slider", "boxed", "stacked", "list", "tile", 0, "hawgkcs"),
    ("T004", "Навигационная", "Без кадра: сверху жанры и подборки.",
     "compact", "boxed", "tabs", "list", "tile", 14, "hgcwfkas"),
    ("T005", "Ленточная", "Кадр, три ленты недели подряд, поступления лентой.",
     "single", "boxed", "stacked", "rail", "tile", 28, "hwafkgcs"),
    ("T006", "Сеточная", "Лид вместо кадра и крупная сетка первым экраном.",
     "compact", "boxed", "tabs", "list", "tile", 35, "hfwkagcs"),
    ("T007", "Широкий слайдер", "Слайдер во всю ширину окна.",
     "slider", "full", "tabs", "list", "tile", 0, "hwakgcs"),
    ("T008", "Афиша", "Кадр во всю ширину и крупные карточки.",
     "single", "full", "tabs", "list", "wide", 18, "hfwakgcs"),
    ("T009", "Плотный каталог", "Лид и самая плотная сетка.",
     "compact", "boxed", "tabs", "list", "dense", 42, "hfwkagcs"),
    ("T010", "Слайдер и ленты", "Слайдер, три ленты недели, поступления лентой.",
     "slider", "boxed", "stacked", "rail", "tile", 0, "hwakgcs"),
    ("T011", "Жанры первыми", "Жанровая навигация перед всем остальным.",
     "compact", "boxed", "tabs", "list", "tile", 24, "hgfwkacs"),
    ("T012", "Подборки первыми", "Тематические выборки во главе страницы.",
     "compact", "boxed", "stacked", "list", "tile", 21, "hcgwfkas"),
    ("T013", "Крупные карточки", "Слайдер и широкая сетка.",
     "slider", "boxed", "tabs", "list", "wide", 14, "hfwakgcs"),
    ("T014", "Мелкая сетка", "Слайдер, поступления лентой, плотная сетка.",
     "slider", "boxed", "tabs", "rail", "dense", 32, "hwfakgcs"),
    ("T015", "Кадр и сетка", "Один кадр и широкая сетка новинок.",
     "single", "boxed", "tabs", "list", "wide", 28, "hfwkagcs"),
    ("T016", "Кадр во всю ширину", "Кадр на всю ширину, три ленты недели.",
     "single", "full", "stacked", "list", "tile", 0, "hwakgcs"),
    ("T017", "Слайдер и плотность", "Широкий слайдер и плотная сетка.",
     "slider", "full", "stacked", "rail", "dense", 35, "hwafkgcs"),
    ("T018", "Разделы вперёд", "Входы видов сразу после героя.",
     "slider", "boxed", "tabs", "list", "tile", 18, "hkfwagcs"),
    ("T019", "Поступления вперёд", "Что добавилось — сразу под героем.",
     "slider", "boxed", "tabs", "rail", "tile", 0, "hawkgcs"),
    ("T020", "Поступления и жанры", "Поступления, затем жанровая навигация.",
     "compact", "boxed", "stacked", "rail", "tile", 14, "hagwfkcs"),
    ("T021", "Три ленты и сетка", "Ленты недели и плотная сетка под ними.",
     "compact", "boxed", "stacked", "list", "dense", 28, "hwfkagcs"),
    ("T022", "Афиша без недели", "Недельного блока нет вовсе.",
     "single", "boxed", "tabs", "list", "wide", 24, "hfkagcs"),
    ("T023", "Только ленты", "Без подборок: лента недели и поступления.",
     "slider", "boxed", "stacked", "rail", "tile", 0, "hwakgs"),
    ("T024", "Каталог без кадра", "Лид во всю ширину и самая большая сетка.",
     "compact", "full", "tabs", "list", "tile", 42, "hfwkagcs"),
    ("T025", "Навигация сверху", "Жанры и подборки ДО героя.",
     "compact", "boxed", "tabs", "rail", "tile", 18, "gchwfkas"),
    ("T026", "Разделы сверху", "Входы видов до героя.",
     "compact", "boxed", "stacked", "list", "tile", 21, "khwfagcs"),
    ("T027", "Крупно и во всю ширину", "Кадр на всю ширину, крупные карточки.",
     "single", "full", "tabs", "list", "wide", 0, "hwakgcs"),
    ("T028", "Плотно и во всю ширину", "Широкий слайдер, мелкая сетка.",
     "slider", "full", "tabs", "list", "dense", 35, "hfwakgcs"),
    ("T029", "Редакция и сетка", "Поступления, сетка, затем ленты недели.",
     "slider", "boxed", "stacked", "list", "wide", 21, "hafwkgcs"),
    ("T030", "Редакция плотная", "Поступления лентой и плотная сетка.",
     "slider", "boxed", "stacked", "rail", "dense", 24, "hawfkgcs"),
    ("T031", "Лаконичная", "Лид, неделя, поступления — и ничего лишнего.",
     "compact", "boxed", "tabs", "list", "tile", 0, "hwakgcs"),
    ("T032", "Лаконичная широкая", "То же, но карточки крупнее.",
     "compact", "boxed", "tabs", "list", "wide", 0, "hwakgcs"),
    ("T033", "Лаконичная плотная", "То же, но карточки мельче.",
     "compact", "boxed", "tabs", "list", "dense", 0, "hwakgcs"),
    ("T034", "Кадр и лента", "Один кадр, поступления лентой.",
     "single", "boxed", "tabs", "rail", "tile", 0, "hwakgcs"),
    ("T035", "Кадр и три ленты", "Один кадр, ленты недели, крупные карточки.",
     "single", "boxed", "stacked", "list", "wide", 0, "hwakgcs"),
    ("T036", "Сетка после недели", "Неделя, затем сетка новинок.",
     "slider", "boxed", "tabs", "list", "tile", 28, "hwfakgcs"),
    ("T037", "Сетка после поступлений", "Неделя, поступления, затем сетка.",
     "slider", "boxed", "tabs", "list", "tile", 21, "hwafkgcs"),
    ("T038", "Сетка в конце", "Сетка новинок ближе к подвалу.",
     "slider", "boxed", "tabs", "list", "tile", 18, "hwakgfcs"),
    ("T039", "Жанры после недели", "Жанровая навигация между блоками.",
     "slider", "boxed", "stacked", "list", "tile", 0, "hwgakcs"),
    ("T040", "Подборки после недели", "Подборки сразу за неделей, без сетки.",
     "slider", "boxed", "tabs", "rail", "tile", 0, "hwcakgs"),
    ("T041", "Широкая редакция", "Широкий слайдер, поступления, крупная сетка.",
     "slider", "full", "stacked", "list", "wide", 14, "hafwkgcs"),
    ("T042", "Плотная навигация", "Жанры и подборки сверху, мелкая сетка.",
     "compact", "boxed", "stacked", "rail", "dense", 32, "hgcwfkas"),
    ("T043", "Афиша с лентой", "Кадр во всю ширину, поступления лентой.",
     "single", "full", "tabs", "rail", "wide", 12, "hfwakgcs"),
    ("T044", "Афиша плотная", "Кадр во всю ширину и самая мелкая сетка.",
     "single", "full", "stacked", "rail", "dense", 42, "hwfakgcs"),
    ("T045", "Каталог и жанры", "Сетка, затем жанры, крупные карточки.",
     "compact", "boxed", "tabs", "list", "wide", 24, "hfgwkacs"),
    ("T046", "Каталог и разделы", "Сетка, затем входы видов, мелкие карточки.",
     "compact", "boxed", "tabs", "list", "dense", 24, "hfkwagcs"),
    ("T047", "Слайдер и подборки", "Подборки сразу под слайдером.",
     "slider", "boxed", "tabs", "list", "tile", 12, "hcfwakgs"),
    ("T048", "Широкий слайдер и лента", "Слайдер на всю ширину, поступления лентой.",
     "slider", "full", "tabs", "rail", "tile", 0, "hawkgcs"),
    ("T049", "Тихая витрина", "Без подборок, небольшая сетка новинок.",
     "compact", "boxed", "stacked", "list", "tile", 12, "hfwakgs"),
    ("T050", "Максимальная плотность", "Лид во всю ширину и предельно мелкая сетка.",
     "compact", "full", "stacked", "rail", "dense", 42, "hwfkagcs"),
)


def _развернуть_шаблоны(таблица) -> dict:
    """Таблица → словарь объявлений. Ни одной строки кода на шаблон."""
    собрано = {}
    for (ид, имя, описание, герой, ширина, неделя, новое, сетка, свежие,
         состав) in таблица:
        собрано[ид] = {
            "имя": имя, "описание": описание, "герой": герой,
            "ширина": ширина, "недельный": неделя, "новое": новое,
            "сетка": сетка, "свежие": свежие,
            "порядок": [ЗОНА_БЛОКИ_КОД[б] for б in состав],
            "состав": состав,
        }
    return собрано


ЗОНА_ШАБЛОНЫ = _развернуть_шаблоны(ЗОНА_ТАБЛИЦА_ШАБЛОНОВ)
ЗОНА_ШАБЛОН_ПО_УМОЛЧАНИЮ = "T001"

#: Прежние имена шаблонов остаются рабочими: манифест, написанный до перехода
#: на T-нумерацию, не должен молча превратиться в другой шаблон.
ЗОНА_ШАБЛОН_АЛИАСЫ = {
    "classic": "T001", "catalog-first": "T002", "editorial": "T003",
    "discovery": "T004", "rail-dense": "T005", "grid-lead": "T006",
}

#: Класс сетки по типу. Базовый тип не добавляет класса вовсе — иначе витрина
#: по умолчанию отдавала бы не те байты, что до появления шаблонов.
ЗОНА_КЛАСС_СЕТКИ = {"tile": "", "wide": "zg--wide", "dense": "zg--dense"}

#: Имя шаблона ЭТОЙ витрины. Объявляет манифест; неизвестное имя не подменяет
#: витрину молча — оно уходит в stderr и откатывается к умолчанию.
ЗОНА_ШАБЛОН = МАНИФЕСТ.get("template_profile") or ЗОНА_ШАБЛОН_ПО_УМОЛЧАНИЮ
ЗОНА_ШАБЛОН = ЗОНА_ШАБЛОН_АЛИАСЫ.get(ЗОНА_ШАБЛОН, ЗОНА_ШАБЛОН)
if ЗОНА_ШАБЛОН not in ЗОНА_ШАБЛОНЫ:
    if СЕМЕЙСТВО == "zona":
        print(f"[zona] манифест объявляет неизвестный шаблон {ЗОНА_ШАБЛОН!r}; "
              f"известны T001–T{len(ЗОНА_ШАБЛОНЫ):03d}. "
              f"Исполняется {ЗОНА_ШАБЛОН_ПО_УМОЛЧАНИЮ}.",
              file=sys.stderr, flush=True)
    ЗОНА_ШАБЛОН = ЗОНА_ШАБЛОН_ПО_УМОЛЧАНИЮ

#: Catalog page size (Zona 1.2 densify). 28 = four full rows of seven cards
#: on desktop; totals and facets still use the full filtered set.
НА_СТРАНИЦЕ_1_1 = 28

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
        self.path = str(путь or "")
        self.mtime = 0.0
        if not путь:
            return
        try:
            путь_п = Path(путь)
            self.mtime = путь_п.stat().st_mtime
            сырое = json.loads(путь_п.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        записи = сырое.get("details")
        if isinstance(записи, dict):
            self.записи = записи
            self.источник = str(сырое.get("source") or "")
            self.покрытие = int(сырое.get("details_total") or 0)
            self.catalog_revision = str(сырое.get("catalog_revision") or "")
            self.catalog_built_at = str(сырое.get("catalog_built_at") or "")
            # Наложение ячейки поверх снимка конвейера.
            #
            # Снимок принадлежит суточному конвейеру и приезжает доставкой
            # ЦЕЛИКОМ; перечней доступных номеров (`nums`) в нём нет вовсе —
            # измерено 2026-09-29 на снимке e1469f33: ноль сезонов с
            # перечнем. Пока согласование писало прямо в снимок, доставка
            # стирала его работу каждую ночь, и круг начинался заново.
            #
            # Поэтому проверенные номера живут в отдельном файле рядом, его
            # доставка не касается, и он накладывается здесь. Нет файла —
            # витрина ведёт себя ровно как прежде, по числу `avail`.
            self.наложено = _наложить_номера(self.записи, путь_п)

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

#: Светлая палитра Zona. Контрасты посчитаны против фона, на котором цвет
#: реально стоит, а не «на белом вообще»; порог WCAG 2.2 AA для основного
#: текста — 4.5:1, для крупного — 3:1.
#:
#:   ink   — основной текст на page (#14181d на #ffffff): 15.9:1
#:   dim   — вторичный текст на page (#5a6472 на #ffffff): 5.7:1
#:   mute  — служебный текст на page (#6b7480 на #ffffff): 4.8:1
#:   acc   — ссылки и акцентный ТЕКСТ на page (#0a5bd0 на #ffffff): 6.4:1
#:   accdk — фон под БЕЛЫМ текстом (белое на #0a5bd0): 6.4:1
#:   warm  — предупреждающий текст на page (#8a5200 на #ffffff): 5.6:1
#:
#: `rail` в тёмной теме — тёмная полоса со светлым текстом; в светлой роли
#: меняются местами, иначе на светлом листе получалась бы белая надпись на
#: почти белом фоне — ровно то нечитаемое сочетание, которое требуется убрать.
ЗОНА_ТОКЕНЫ_СВЕТ = {
    "ink": "#14181d", "dim": "#5a6472", "page": "#ffffff", "alt": "#f1f4f8",
    "rail": "#ffffff", "railink": "#14181d", "line": "#dde3ea",
    "acc": "#0a5bd0", "accdk": "#0a5bd0", "warm": "#8a5200",
    "mute": "#6b7480", "surf": "#ffffff",
}

#: Имя CSS-переменной для токена оформления.
def _перем(имя: str) -> str:
    return f"--z-{имя}"


def _тема_зона() -> str:
    """Две палитры Zona как CSS-переменные.

    Почему так, а не два листа стилей. Цвета Zona раньше подставлялись в текст
    CSS на сборке (`@INK@` → `#ffffff`), поэтому тема была вкомпилирована в
    страницу: переключать её было нечем, и светлой темы у витрины не
    существовало вовсе. Теперь каждый токен — переменная, а палитра объявлена
    один раз; все 330 мест, где цвет используется, меняются вместе с ней.

    Порядок блоков важен. Явный выбор (`data-theme`) обязан побеждать
    системную настройку, поэтому он идёт последним. Медиа-запрос нужен для
    случая без JavaScript: без него витрина осталась бы тёмной у посетителя,
    у которого система просит светлую.
    """
    тёмные = ";".join(f"{_перем(и)}:{з}" for и, з in ЗОНА_ТОКЕНЫ.items())
    светлые = ";".join(f"{_перем(и)}:{з}" for и, з in ЗОНА_ТОКЕНЫ_СВЕТ.items())
    return (f":root{{{тёмные};color-scheme:dark}}\n"
            f"@media(prefers-color-scheme:light){{"
            f":root:not([data-theme=dark]){{{светлые};color-scheme:light}}}}\n"
            f":root[data-theme=light]{{{светлые};color-scheme:light}}\n"
            f":root[data-theme=dark]{{{тёмные};color-scheme:dark}}\n")


#: Токены, подставляемые в CSS Zona ссылкой на переменную, а не значением.
ЗОНА_ТОКЕНЫ_ССЫЛКИ = {и: f"var({_перем(и)})" for и in ЗОНА_ТОКЕНЫ}

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


#: Оформление страницы редакционной подборки. Лежит ЗДЕСЬ, рядом с общим
#: листом, а не в листе семейства: разметку даёт общий построитель
#: `ручная_подборка`, и правила обязаны приезжать вместе с ним. До 27.10 они
#: лежали только в `ЛОРДС_СТИЛЬ`, и Zona с Animedia отдавали страницу без
#: оформления: одна карточка в ряду, постер во всю ширину содержимого
#: (измерено 1340×565 на ширинах 1440 и 1920).
#:
#: Общий лист конкатенируется ПЕРЕД листом семейства, поэтому эти правила
#: ничего не отнимают у семейства, где своё оформление уже есть.
СТИЛЬ_ПОДБОРКИ = """
.col__grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));
  gap:20px 14px;max-width:1340px;margin:0 auto 28px;padding:0}
@media (min-width:600px){.col__grid{
  grid-template-columns:repeat(3,minmax(0,1fr));gap:22px 16px}}
@media (min-width:900px){.col__grid{
  grid-template-columns:repeat(4,minmax(0,1fr))}}
@media (min-width:1360px){.col__grid{
  grid-template-columns:repeat(5,minmax(0,1fr))}}
.col__i{display:flex;flex-direction:column;min-width:0}
.col__i .c{display:block;text-decoration:none;color:inherit;min-width:0}
/* Рамка постера одна на все карточки: отношение 2:3 задано рамкой, а картинка
   заполняет её `cover`. Пропорции не искажаются ни при каком исходном кадре —
   нестандартный кадр обрезается, а не растягивается. */
.col__i .c__p{display:block;position:relative;width:100%;aspect-ratio:2/3;
  overflow:hidden;border-radius:10px;background:rgba(128,128,128,.16)}
.col__i .c__p img{display:block;width:100%;height:100%;
  object-fit:cover;object-position:center}
.col__i .c__b{padding:8px 2px 0;min-width:0}
/* Длинные названия аниме обрезаются по двум строкам: иначе одна карточка
   растягивает весь ряд, и сетка разъезжается по высоте. */
.col__i .c__t{font-weight:600;font-size:15px;line-height:1.25;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;
  overflow:hidden;overflow-wrap:anywhere}
.col__i .c__m{margin-top:3px;font-size:12px;opacity:.7}
.col__i .c__m span+span{margin-left:6px}
.col__i .col__why{margin:6px 2px 0;font-size:13px;line-height:1.4;opacity:.85;
  display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;
  overflow:hidden;overflow-wrap:anywhere}
/* Телефон: повтор названия в крошках убран, чтобы первый ряд постеров
   помещался в первый экран. Измерено до правки на 390×844: верх первой
   карточки 613, высота рамки 258, нижний край ряда 871 при окне 844.
   Прячется ТОЛЬКО на странице подборки и только на узком экране; в JSON-LD
   цепочка остаётся полной. Вступление не обрезается — оно объясняет, зачем
   смотреть. */
@media (max-width:599px){.zcr--coll .zcr__cur{display:none}}
/* Телефон: вертикальный ритм над сеткой поджат, чтобы первый ряд постеров
   помещался в экран. Измерено после расширения состава до девятнадцати работ:
   вступление выросло на строку, низ ряда стал 852 при окне 844. Текст при
   этом НЕ сокращается — он объясняет читателю, зачем смотреть.
   Оговорка, которую нельзя терять: это возвращает запас, а не гарантирует
   критерий при любом тексте — каждая лишняя строка вступления стоит около
   21 пикселя. */
@media (max-width:599px){
  .sec--coll .claim{margin-bottom:10px}
  .sec--coll .col__src{margin-bottom:8px}
  .sec--coll .col__upd{margin-bottom:8px}
  .col__grid{gap:16px 12px}
}
/* Вступление и служебные строки — по ширине чтения, а не во всю рамку. */
.claim{max-width:74ch;line-height:1.5}
.col__upd,.col__gone,.col__src{max-width:74ch}
.col__src{margin:0 0 14px;font-size:12px;opacity:.65;line-height:1.45}
"""


def _общее(токены: dict) -> str:
    return ОБЩЕЕ_1_1.replace("@ACC@", токены["acc"]) + СТИЛЬ_ПОДБОРКИ


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
.col__i{display:flex;flex-direction:column;gap:6px;min-width:0}
.col__why{margin:0;font-size:13px;line-height:1.45;overflow-wrap:anywhere}
.col__gone{margin:14px 0 0;font-size:13px;line-height:1.5}
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
.sf-contact{max-width:100%;min-width:0;overflow-wrap:anywhere;word-break:break-word;line-height:1.45;color:var(--a-ink,var(--z-ink,var(--ag-ink,inherit)))}.sf-contact a{color:inherit;text-decoration:underline;text-underline-offset:2px}.sf-contact a:hover{text-decoration:none}
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
/* B01 header geometry: ≤767 → 56; 768–1279 → 60–64; ≥1280 → 68–72.
   Burger drawer on narrow; no multi-row header wrap. */
padding-top:56px}
@media(min-width:768px){body{padding-top:62px}}
@media(min-width:1280px){body{padding-top:70px}}
.zs{min-height:100vh;display:block}
.zmain{min-width:0}
.zwrap{max-width:1760px;margin:0 auto;padding:0 12px;box-sizing:border-box}
@media(min-width:768px){.zwrap{padding:0 24px}}
@media(min-width:1440px){.zwrap{padding:0 32px}}
@media(min-width:1920px){.zwrap{padding:0 64px}}

/* Шапка: горизонтальная, закреплённая. Постоянной левой колонки нет ни на
   одной ширине — это и было главным расхождением с эталоном. */
.zhd{position:fixed;top:0;left:0;right:0;z-index:60;background:@RAIL@;
color:@RAILINK@;box-shadow:0 1px 0 rgba(0,0,0,.25)}
.zhd__in{max-width:1400px;margin:0 auto;padding:0 12px;display:flex;
align-items:center;gap:10px;flex-wrap:nowrap;height:56px;min-height:56px;
max-height:56px;box-sizing:border-box}
@media(min-width:768px){.zhd__in{padding:0 16px;gap:12px;height:62px;min-height:62px;max-height:62px}}
@media(min-width:1280px){.zhd__in{padding:0 20px;height:70px;min-height:70px;max-height:70px;gap:14px}}
/* Ширина логотипа — по тексту. Жёсткие 110/130px резали «Zona Cinema»
   (129/136px) на всех ширинах; ужимается не логотип, а поле поиска. */
.zhd__logo{font-size:18px;font-weight:700;letter-spacing:-.3px;color:@RAILINK@;
white-space:nowrap;flex:0 0 auto;min-height:44px;
display:inline-flex;align-items:center}
@media(max-width:359px){.zhd__logo{font-size:16px}}
@media(min-width:768px){.zhd__logo{font-size:19px}}
.zhd__logo:focus-visible{outline:2px solid @RAILINK@;outline-offset:3px;border-radius:4px}
/* Строкой меню стоит только с 1280px: восемь разделов рядом с логотипом,
   поиском и темой уже не помещаются, и прежде хвост уходил в скрытую
   прокрутку (768–1279) или под поле поиска (1280+). Ниже — ящик
   (см. блок max-width:1279). Меню не сжимается никогда; сжимается поиск. */
.zhd__n{display:flex;gap:2px;flex:0 0 auto;order:0}
.zhd__n a{padding:8px 10px;border-radius:6px;font-size:14px;font-weight:500;
color:@RAILINK@;white-space:nowrap;flex:0 0 auto;min-height:44px;min-width:44px;
display:inline-flex;align-items:center;box-sizing:border-box}
@media(min-width:1280px){.zhd__n a{padding:10px 8px;font-size:15px}}
@media(min-width:1600px){.zhd__n a{padding:10px 12px;font-size:15.6px}}
.zhd__n a:hover{background:color-mix(in srgb,@RAILINK@ 14%,transparent)}
.zhd__n a:focus-visible{outline:2px solid @RAILINK@;outline-offset:2px}
.zhd__n a[aria-current]{background:@ACCDK@;color:#fff}
.zhd__s{display:flex;flex:1 1 140px;min-width:0;max-width:100%;
border-radius:6px;overflow:hidden;background:@SURF@;min-height:44px}
@media(min-width:768px){.zhd__s{flex:1 1 280px;max-width:520px;margin-left:auto}}
@media(min-width:1280px){.zhd__s{flex:1 1 360px;min-width:180px;max-width:400px}}
.zhd__s input{flex:1;min-width:0;border:0;padding:9px 12px;font-size:14px;
color:@PAGE@;font-family:inherit;min-height:44px;box-sizing:border-box}
.zhd__s input:focus-visible{outline:2px solid @ACCDK@;outline-offset:-2px}
.zhd__s button{border:0;background:@ACCDK@;color:#fff;padding:0 16px;
font-weight:600;font-size:14px;cursor:pointer;font-family:inherit;
min-height:44px;min-width:44px}
.zhd__s button:focus-visible{outline:2px solid #fff;outline-offset:2px}
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

/* B02 Hero — editorial first screen; no request-time rotation. */
.zhero{display:grid;grid-template-columns:1fr;gap:0;margin:12px 0 28px;
min-width:0;max-width:100%;box-sizing:border-box;
border-radius:16px;overflow:hidden;background:@SURF@;border:1px solid @LINE@;
min-height:300px;max-height:none}
/* Потолок 390px снят у базового правила. Он был написан для двухколоночной
   полосы рабочего стола, а ниже 900px ряд складывается в столбец: медиа плюс
   текст. Измерено в Chromium: на 390px сумма 205+259=464px, на 768px
   404+259=663px, и при `overflow:hidden` потолок срезал текст — 74px и 273px
   соответственно. Высоту сложенного ряда задаёт содержимое; на рабочем столе
   она по-прежнему задана явно ниже. */
/* Высота ряда задаётся явно. Пока её держали min/max-height, ряд растягивался
   под ПРИРОДНУЮ пропорцию портретного постера: при колонке 632px картинка
   500×741 требовала 937px, ряд становился 937px, а max-height лишь обрезал его.
   Тело справа центрировалось по 937px и уезжало под обрез — правая половина
   выглядела пустой, а текст пропадал. */
@media(min-width:900px){.zhero{grid-template-columns:46% 54%;
height:clamp(340px,26vw,390px);min-height:0;max-height:none}}
/* Пропорция 4/5 вместо 16/9. Исходники здесь портретные — измерено на живом
   домене: 500x750 (2:3). В блоке 16/9 такая картинка при любом кадрировании
   теряет две трети высоты, то есть ровно лица и надписи. Фон — поверхность
   темы, а не жёсткий #111: при светлой теме чёрные поля выглядели провалом. */
.zhero__media{position:relative;min-height:180px;background:var(--z-alt);aspect-ratio:4/5;
max-width:100%;width:100%;min-width:0;overflow:hidden;box-sizing:border-box}
@media(min-width:900px){.zhero__media{aspect-ratio:auto;min-height:0;height:100%}}
/* `contain`, а не `cover`. Постер показывается целиком и в своей пропорции;
   свободное место занимает фон темы. `object-position` оставлен нейтральным:
   подбирать смещение — значит маскировать обрезание, а не убирать его. */
.zhero__media img{width:100%;height:100%;object-fit:contain;object-position:50% 50%;
display:block;max-width:100%}
/* --- Слайдер героя -------------------------------------------------------
   Дорожка со слайдами занимает медиа-колонку, текстовая панель — вторую.
   Раскладка 46/54, скругления и палитра прежние: менялось поведение, а не
   оформление. */
.zhero--slider{position:relative}
.zhero__viewport{position:relative;overflow:hidden;min-width:0;
grid-column:1;background:var(--z-alt);touch-action:pan-y}
/* Без этого перетаскивание постера запускает нативный drag браузера: серия
   pointer-событий обрывается pointercancel, и свайп не срабатывает. */
.zhero__slide img{-webkit-user-drag:none;user-select:none}
.zhero__track{display:flex;width:100%;height:100%;
transition:transform .45s cubic-bezier(.4,0,.2,1)}
@media(prefers-reduced-motion:reduce){.zhero__track{transition:none}}
.zhero__slide{flex:0 0 100%;min-width:0;position:relative}
.zhero__slide .zhero__media{height:100%}
/* Пропорцию по-прежнему задаёт блок, а не природа картинки: иначе портретный
   постер растягивает ряд под себя. Но вписывается картинка целиком. */
.zhero__slide .zhero__media img{width:100%;height:100%;object-fit:contain;
object-position:50% 50%;display:block}
.zhero__nav{position:absolute;top:50%;transform:translateY(-50%);z-index:4;
width:44px;height:44px;min-width:44px;min-height:44px;border:0;border-radius:50%;
background:rgba(16,21,26,.72);color:#fff;font-size:24px;line-height:1;cursor:pointer;
display:none;align-items:center;justify-content:center;padding:0}
.zhero__nav:hover{background:rgba(16,21,26,.9)}
.zhero__nav:focus-visible{outline:3px solid #fff;outline-offset:2px}
.zhero__nav--prev{left:8px}
.zhero__nav--next{right:8px}
/* Полоса точек обязана поместиться в героя на ЛЮБОЙ ширине.
   Измерено на 320px: восемь точек по 44px давали строку 394px при героe
   296px. Строка выезжала за экран на 74px, первая точка оказывалась при
   x=-37 — `elementFromPoint` в её середине не находил её вовсе, то есть
   две точки из восьми не нажимались. Документ при этом не переполнялся:
   строку обрезал родитель, и обычная проверка горизонтальной прокрутки
   дефекта не видела.
   Лечится не брейкпойнтом, а разрешением точкам сжиматься: `min-width:0`
   и `flex:0 1 44px`. На широких ширинах точка остаётся 44px, на узких
   делит доступное поровну — 35px при 320px, что выше порога 24px
   (WCAG 2.5.8 AA). Полные цели 44px остаются у «вперёд» и «назад», то есть
   эквивалентная цель того же действия никуда не делась. */
.zhero__dots{position:absolute;left:50%;bottom:10px;transform:translateX(-50%);
z-index:4;display:none;gap:6px;padding:0;margin:0;
max-width:calc(100% - 16px);flex-wrap:nowrap;justify-content:center}
.zhero__dot{width:44px;height:44px;min-width:0;min-height:44px;flex:0 1 44px;
padding:0;border:0;
background:transparent;cursor:pointer;display:flex;align-items:center;justify-content:center}
.zhero__dot .zhero__dot-i{display:block;width:9px;height:9px;border-radius:50%;
background:#ffffff66;transition:width .2s,background .2s}
.zhero__dot[aria-selected="true"] .zhero__dot-i{width:22px;border-radius:5px;background:@ACC@}
.zhero__dot:focus-visible{outline:3px solid #fff;outline-offset:-6px;border-radius:8px}
/* Управление появляется только когда скрипт им управляет: мёртвая кнопка
   хуже отсутствующей — она обещает действие, которого не будет. */
.zhero--slider[data-zhero-ready="1"] .zhero__nav,
.zhero--slider[data-zhero-ready="1"] .zhero__dots{display:flex}
.zhero__body{padding:20px 22px;display:flex;flex-direction:column;justify-content:center;gap:10px;
min-width:0;max-width:100%;box-sizing:border-box}
.zhero__t{font-size:26px;line-height:1.2;font-weight:700;margin:0;
display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
@media(min-width:900px){.zhero__t{font-size:34px;line-height:1.18;-webkit-line-clamp:2}}
@media(min-width:900px){.zhero__body{padding:28px 32px}}
.zhero__kicker{font-size:12px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:@ACC@;margin:0}
.zhero h1{font-size:26px;line-height:1.2;font-weight:700;margin:0;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
@media(min-width:900px){.zhero h1{font-size:34px;line-height:1.18;-webkit-line-clamp:2}}
.zhero__meta{font-size:13px;color:@DIM@;margin:0}
.zhero__desc{font-size:14px;line-height:1.5;color:@INK@;margin:0;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.zhero__cta{display:flex;flex-wrap:wrap;gap:10px;margin-top:6px}
.zhero__cta a{display:inline-flex;align-items:center;justify-content:center;min-height:44px;padding:0 18px;border-radius:8px;font-weight:700;font-size:14px}
.zhero__cta a.primary{background:@ACC@;color:#fff}
.zhero__cta a.secondary{background:transparent;border:1px solid @LINE@;color:@INK@}
/* Компактный герой обязан быть ростом со своё содержимое.
   Десктопное правило `.zhero` задаёт height:clamp(340px,26vw,390px) ради
   слайдера; компактный вариант его наследовал, и под лидом из двух строк
   висела мёртвая полоса около 350px — пустой первый экран. Измерено на
   шаблоне grid-lead при 1440px. Сетка 46/54 здесь тоже не нужна: кадра нет,
   и правая колонка оставалась пустой. */
.zhero--compact{min-height:0;max-height:none;height:auto;
grid-template-columns:1fr;padding:18px 0 8px;border:0;background:transparent}
@media(min-width:900px){.zhero--compact{height:auto;grid-template-columns:1fr}}
.zhero--compact h1{font-size:26px}

/* B03 Weekly popular — one tabbed block, not three full rails. */

/* Первая полка главной (поручение владельца 27.10). Крупные постеры и
   читаемое название: первый экран должен помогать выбрать, что смотреть, а не
   пересказывать каталог. Ширина карточки растёт со шириной окна, а не
   задаётся одной цифрой на все экраны. */
.zr1{margin:0 0 26px}
.zr1__h{display:flex;align-items:baseline;justify-content:space-between;gap:10px;flex-wrap:wrap;margin:0 0 2px}
.zr1__h h1,.zr1__h h2{margin:0;font-size:21px;line-height:1.18;font-weight:700;letter-spacing:-.01em}
/* Ссылка «Вся подборка» не уезжает на свою строку с пустотой вокруг: на узком
   экране она прижимается к правому краю той же строки, что и подпись. */
.zr1__h a{font-size:13px;font-weight:700;color:@ACC@;min-height:44px;display:inline-flex;align-items:center;margin-left:auto}
.zr1__sub{margin:0 0 10px;color:@DIM@;font-size:13.5px;line-height:1.5;max-width:62ch;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.zr1__track{display:grid;grid-auto-flow:column;grid-auto-columns:150px;gap:14px;overflow-x:auto;scroll-snap-type:x proximity;padding:2px 2px 10px;scrollbar-width:thin}
.zb{scroll-snap-align:start;display:flex;flex-direction:column;gap:8px;color:inherit;min-height:44px}
.zb__img{position:relative;display:block;aspect-ratio:2/3;border-radius:12px;overflow:hidden;background:@SURF@;box-shadow:0 1px 3px rgba(16,20,26,.14)}
.zb__img img{width:100%;height:100%;object-fit:cover;display:block}
.zb__t{font-size:14.5px;line-height:1.3;font-weight:650;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.zb__m{font-size:12.5px;color:@DIM@}
@media(min-width:640px){.zr1__track{grid-auto-columns:172px;gap:16px}.zr1__h h1,.zr1__h h2{font-size:26px}}
@media(min-width:1024px){.zr1__track{grid-auto-columns:196px;gap:18px}.zr1__h h1,.zr1__h h2{font-size:29px}.zb__t{font-size:15.5px}}

/* Визитка подборки: обложки из реального состава, название, одно предложение
   о пользе, число работ и переход. Текстовая плашка этого не давала: по ней
   нельзя было понять ни что внутри, ни сколько там. */
.zcl{display:grid;gap:14px;grid-template-columns:1fr;margin:0}
.zcl__c{display:flex;flex-direction:column;border:1px solid @LINE@;border-radius:14px;overflow:hidden;background:@SURF@;color:inherit}
.zcl__c:hover,.zcl__c:focus-visible{border-color:@ACC@;outline:none}
.zcl__art{position:relative;display:flex;gap:2px;background:@LINE@}
.zcl__art img{width:100%;height:100%;object-fit:cover;display:block}
.zcl__p{flex:1 1 0;aspect-ratio:2/3;overflow:hidden;display:block}
.zcl__p:nth-child(n+4){display:none}
.zcl__n{position:absolute;right:10px;bottom:10px;background:rgba(14,18,24,.78);color:#fff;font-size:12px;font-weight:700;line-height:1;padding:6px 9px;border-radius:999px}
.zcl__b{display:flex;flex-direction:column;gap:6px;padding:12px 14px 6px}
.zcl__t{font-size:16.5px;font-weight:700;line-height:1.28}
.zcl__d{margin:0;font-size:13.5px;line-height:1.5;color:@DIM@}
.zcl__go{margin-top:auto;font-size:13px;font-weight:700;color:@ACC@;min-height:44px;display:inline-flex;align-items:center;padding:0 14px 2px}
@media(min-width:640px){.zcl{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(min-width:1024px){.zcl{grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}}
.zwpop{margin:8px 0 32px}
.zwpop__h{display:flex;align-items:baseline;justify-content:space-between;gap:12px;flex-wrap:wrap;margin:0 0 12px}
.zwpop__h h2{margin:0;font-size:22px;font-weight:600}
.zwpop__h a{font-size:13px;font-weight:700;color:@ACC@;min-height:44px;display:inline-flex;align-items:center}
.zwpop__tabs{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 14px}
.zwpop__tabs a,.zwpop__tabs span{display:inline-flex;align-items:center;min-height:40px;padding:0 14px;border-radius:999px;border:1px solid @LINE@;font-size:13px;font-weight:600;color:@DIM@;background:@SURF@}
.zwpop__tabs [aria-current]{background:@ACC@;border-color:@ACC@;color:#fff}
.zwpop__panel[hidden]{display:none}
/* Один источник правды для промежутка: `gap` и расчёт основы карточки обязаны
   брать одно значение. Пока полка ставила gap:12px, а расчёт продолжал делить
   по --z-gap:14px, точная подгонка не сходилась и остаток уходил в пустоту
   справа. */
.zwpop .zrl__track{--z-gap:12px;gap:var(--z-gap)}
.zwpop .zc{width:148px;max-width:160px}
@media(min-width:1024px){.zwpop .zc{width:150px}}
@media(min-width:1440px){.zwpop .zc{width:156px}}

/* B04 поступления в каталог. Блок собирается постерной сеткой `zg`, поэтому
   собственных правил карточки у него больше нет: строки zadded__row с
   картинкой 60×90 убраны вместе со своей вёрсткой. Класс оставлен один — как
   имя блока для отступа и для машинной проверки состава главной. */
.zadded{margin:8px 0 28px}

/* B05 kind entry cards */
.zkinds{display:grid;gap:12px;grid-template-columns:1fr;margin:8px 0 28px}
@media(min-width:520px){.zkinds{grid-template-columns:repeat(2,1fr)}}
@media(min-width:1000px){.zkinds{grid-template-columns:repeat(4,1fr)}}
.zkind{display:flex;flex-direction:column;justify-content:flex-end;min-height:150px;max-height:190px;
padding:18px;border-radius:14px;background:linear-gradient(160deg,@SURF@,@RAIL@);border:1px solid @LINE@;color:#fff;text-decoration:none}
.zkind b{font-size:22px;font-weight:700}
.zkind span{font-size:13px;opacity:.85;margin-top:6px}
.zkind em{font-style:normal;font-size:12px;margin-top:10px;opacity:.75}

.zsec{margin:26px 0 30px}
.zsec__h{display:flex;align-items:baseline;justify-content:space-between;
gap:12px;margin:0 0 10px}
.zsec__h h2{font-size:22.1px;font-weight:400;margin:0;letter-spacing:0}
.zsec__h a{font-size:13px;color:@ACC@;font-weight:600;white-space:nowrap}
.zrl{position:relative}
.zrl__vp{overflow-x:auto;overflow-y:hidden;scroll-behavior:smooth;
scroll-snap-type:x mandatory;-webkit-overflow-scrolling:touch;
scrollbar-width:none;padding:2px 0 4px;container-type:inline-size;container-name:zrl}
.zrl__vp::-webkit-scrollbar{display:none;width:0;height:0}
/* На полке ширина карточки — результат деления контейнера, а не потолок.
   `.zt` несёт собственный max-width:var(--z-card-max) и по порядку каскада
   перебивал расчётную основу (на 1440: 186.3px → 180px). Потолок снимается
   здесь, а не у `.zt`: в сетках `.zg` с фиксированным числом колонок он нужен. */
.zrl__track{display:flex;gap:var(--z-gap,14px);width:max-content;align-items:stretch;
--z-card-max:none}
/* Home shelves match locked catalog density: 2 / 4 / 7 / 8.

   max-width здесь снят намеренно. Расчёт основы делит ширину контейнера ровно
   на N карточек и N-1 промежутков, а потолок --z-card-max обрезал результат
   (на 1440: основа 184.6px → 180px). Семь карточек занимали 1332px из 1376 и
   справа оставалась мёртвая полоса 44px. Потолок нужен сеткам `.zg`, где число
   колонок фиксировано, а не полке, где ширина карточки и есть результат
   деления. */
.zrl__track>*{flex:0 0 calc((100cqw - var(--z-gap,14px)) / 2);scroll-snap-align:start;
min-width:0;height:auto;max-width:none;box-sizing:border-box}
@media(min-width:768px){.zrl__track>*{flex:0 0 calc((100cqw - 3 * var(--z-gap,14px)) / 4)}}
@media(min-width:1440px){.zrl__track>*{flex:0 0 calc((100cqw - 6 * var(--z-gap,14px)) / 7)}}
@media(min-width:1920px){.zrl__track>*{flex:0 0 calc((100cqw - 7 * var(--z-gap,14px)) / 8)}}
.zrl__btn{position:absolute;top:28%;transform:translateY(-50%);z-index:5;
width:36px;height:48px;min-width:44px;min-height:44px;border:0;border-radius:5px;cursor:pointer;
background:rgba(16,21,26,.82);color:#fff;font-size:18px;line-height:1;
display:flex;align-items:center;justify-content:center;opacity:.9}
.zrl__btn:focus-visible{outline:2px solid #fff;outline-offset:2px}
.zrl__btn--p{left:-6px}
.zrl__btn--n{right:-6px}
.zrl__btn[disabled]{opacity:.32;cursor:default}

/* Верхняя лента. Плотность полок ниже закреплена (2/4/7/8) и здесь не
   меняется — у героя своя: на 1440 восемь карточек дают основу
   (1376 - 7*14)/8 = 160px, то есть ориентир 150-180px, а не 184px как при
   семи. На узких ширинах плотность та же, что у полок: две карточки на 390px
   это 172px — постер читается, а третья ужала бы подписи. */
.zsec--hero{margin:16px 0 30px}
.zsec--hero .zsec__h h1{font-size:22.1px;font-weight:400;margin:0;letter-spacing:0}
@media(min-width:1440px){.zrl--hero .zrl__track>*{
flex:0 0 calc((100cqw - 7 * var(--z-gap,14px)) / 8)}}
@media(min-width:1920px){.zrl--hero .zrl__track>*{
flex:0 0 calc((100cqw - 8 * var(--z-gap,14px)) / 9)}}
/* Стрелки ленты постеров встают по центру ПОСТЕРА, а не всей карточки:
   подписи под постером высокие, и центр карточки пришёлся бы на текст. */
.zrl--hero .zrl__btn{top:34%}
/* Постер вписывается целиком. Большинство источников здесь 2:3 и при `cover`
   выглядят так же, но запись другой пропорции им обрезалась бы ради рамки.
   Свободное место занимает поверхность темы, а не чёрное поле. Полки ниже не
   трогаются: задание про верхний блок, а их плотность закреплена. */
.zrl--hero .zt__p{background:@ALT@}
.zrl--hero .zt__img{object-fit:contain}

/* B09 densify: explicit column matrix — no auto-fit 180px blank zone. */
:root{--z-card-max:180px;--z-gap:14px;--z-poster-max-h:270px}
.zg{display:grid;gap:var(--z-gap);
grid-template-columns:repeat(2,minmax(0,1fr));
align-items:stretch;justify-content:center;width:100%}
@media(min-width:768px){.zg{grid-template-columns:repeat(4,minmax(0,1fr))}}
@media(min-width:1024px){.zg{grid-template-columns:repeat(5,minmax(0,1fr))}}
@media(min-width:1280px){.zg{grid-template-columns:repeat(6,minmax(0,1fr))}}
@media(min-width:1440px){.zg{grid-template-columns:repeat(7,minmax(0,1fr))}}
@media(min-width:1920px){.zg{grid-template-columns:repeat(8,minmax(0,1fr))}}
/* Тип сетки как структурное различие шаблонов, а не как перекраска.
   Число колонок задано матрицей по ширинам, поэтому и варианты задаются
   матрицей: «широкая» показывает меньше карточек крупнее, «плотная» —
   больше и мельче. Потолок ширины карточки снимается у широкой и
   ужимается у плотной, иначе колонки расчётные, а карточки в них
   упираются в 180px и слева-справа остаётся пустота. */
.zg--wide{--z-card-max:none;grid-template-columns:repeat(2,minmax(0,1fr))}
@media(min-width:768px){.zg--wide{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(min-width:1024px){.zg--wide{grid-template-columns:repeat(4,minmax(0,1fr))}}
@media(min-width:1280px){.zg--wide{grid-template-columns:repeat(4,minmax(0,1fr))}}
@media(min-width:1440px){.zg--wide{grid-template-columns:repeat(5,minmax(0,1fr))}}
@media(min-width:1920px){.zg--wide{grid-template-columns:repeat(6,minmax(0,1fr))}}
.zg--dense{--z-card-max:150px;--z-gap:10px;grid-template-columns:repeat(3,minmax(0,1fr))}
@media(min-width:768px){.zg--dense{grid-template-columns:repeat(5,minmax(0,1fr))}}
@media(min-width:1024px){.zg--dense{grid-template-columns:repeat(6,minmax(0,1fr))}}
@media(min-width:1280px){.zg--dense{grid-template-columns:repeat(7,minmax(0,1fr))}}
@media(min-width:1440px){.zg--dense{grid-template-columns:repeat(8,minmax(0,1fr))}}
@media(min-width:1920px){.zg--dense{grid-template-columns:repeat(10,minmax(0,1fr))}}
/* Герой во всю ширину окна. Вынос за колонку содержимого делается
   симметричными отрицательными полями; горизонтальной прокрутки он не даёт,
   потому что каркас витрины несёт overflow-x:clip. Проверяется измерением
   переполнения на всех шести ширинах, а не обещанием. */
.zhero--full{margin-left:calc(50% - 50vw);margin-right:calc(50% - 50vw);
border-radius:0;max-width:100vw}
.zg--related{display:grid;gap:var(--z-gap);
grid-template-columns:repeat(2,minmax(0,1fr));
overflow:visible;justify-content:start}
@media(min-width:600px){.zg--related{grid-template-columns:repeat(4,minmax(0,1fr))}}
@media(min-width:768px){.zg--related{grid-template-columns:repeat(6,minmax(0,1fr))}}
@media(min-width:1280px){.zg--related{grid-template-columns:repeat(8,minmax(0,1fr))}}
.zg--related.zg--related-compact{grid-template-columns:repeat(2,minmax(0,1fr))}
@media(min-width:600px){.zg--related.zg--related-compact{grid-template-columns:repeat(auto-fit,minmax(140px,1fr))}}
.zt{display:flex;flex-direction:column;height:100%;min-width:0;max-width:var(--z-card-max);
background:@SURF@;border:1px solid @LINE@;border-radius:6px;overflow:hidden;
transition:border-color .16s,transform .16s;color:inherit;text-decoration:none}
.zt:hover,.zt:focus-visible{border-color:@ACC@;transform:translateY(-1px);outline:none}
.zt__p{display:block;aspect-ratio:2/3;max-height:var(--z-poster-max-h);background:@ALT@;
position:relative;flex:0 0 auto;overflow:hidden}
.zt__p img,.zt__img{position:absolute;inset:0;z-index:1;width:100%;height:100%;
object-fit:cover;display:block}
.zt__none{position:absolute;inset:0;display:grid;place-items:center;padding:10px;
text-align:center;color:@MUTE@;font-size:11px;line-height:1.3;aspect-ratio:auto}
.zt__none b{display:block;font-size:20px;font-weight:700;color:@DIM@;margin-bottom:3px}
/* Card body: title (≤2 lines) + up to 2 compact meta lines + sourced rating.
   Plot snippets stay off cards (Pass6 Block 03). */
.zt__b{padding:7px 8px 8px;display:flex;flex-direction:column;gap:2px;flex:0 0 auto;
height:96px;min-height:96px;max-height:96px;box-sizing:border-box;overflow:hidden}
.zt__t{font-size:12.5px;font-weight:600;line-height:1.25;min-height:calc(1.25em * 2);
max-height:calc(1.25em * 2);display:-webkit-box;-webkit-line-clamp:2;
-webkit-box-orient:vertical;overflow:hidden;word-break:break-word}
.zt__m{font-size:11px;color:@DIM@;line-height:1.25;min-height:0;
max-height:1.25em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
/* Дата добавления или премьеры — своей строкой и своим цветом: в «Новом в
   каталоге» она и есть повод показать карточку. Коробка подписи выше ровно
   на эту строку и ровно у таких карточек; высота общая для всей сетки,
   поэтому ряды остаются выровненными. */
.zt__m--when{color:@ACC@;font-weight:600}
.zt--fresh .zt__b{height:112px;min-height:112px;max-height:112px}
.zt__x{display:none}
.zt__r{display:flex;gap:8px;font-size:11px;color:@DIM@;margin-top:auto;
padding-top:2px;flex-wrap:nowrap;min-height:1.25em;max-height:1.25em;align-items:center;
overflow:hidden}
.zt__r b{color:@WARM@;font-weight:700}
.zt__r i{color:@WARM@;font-style:normal;font-weight:700}
/* Оценка карточки: источник приглушён, число выделено. Ряд не переносится —
   его высота зафиксирована выше, и перенос сдвинул бы низ карточки. */
.zt__ri{display:inline-flex;gap:4px;align-items:baseline;white-space:nowrap}
.zt__rs{color:@DIM@}
.zt__rn{color:@WARM@;font-weight:700;font-variant-numeric:tabular-nums}
.zt__play{display:inline-block;font-size:10px;font-weight:700;color:@ACC@;margin-left:auto}

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
.zgenres__nav a:hover{border-color:@ACC@;color:@ACC@;background:@ALT@}
.zgenres__nav a:focus-visible{outline:2px solid @ACC@;outline-offset:2px}
.zgenres__nav a[aria-current],.zgenres__nav a.is-active{
background:@ACCDK@;border-color:@ACCDK@;color:#fff}
@media(max-width:639px){
.zgenres__nav{flex-wrap:nowrap;overflow-x:auto;-webkit-overflow-scrolling:touch;
scrollbar-width:none;padding-bottom:4px}
.zgenres__nav::-webkit-scrollbar{display:none;width:0;height:0}
.zgenres__nav a{flex:0 0 auto}
}
.zpg{display:flex;gap:7px;justify-content:center;margin:26px 0;flex-wrap:wrap}
.zpg a,.zpg span{display:inline-flex;align-items:center;justify-content:center;
min-width:44px;min-height:44px;padding:8px 13px;border-radius:6px;border:1px solid @LINE@;
background:@SURF@;font-size:13.5px;text-align:center;box-sizing:border-box}
.zpg span[aria-current]{background:@ACCDK@;color:#fff;border-color:@ACCDK@}
.zpg__gap{border:0;background:transparent;min-width:24px;pointer-events:none}
.zpg__nav{font-weight:600}
.zsort{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 14px}
.zsort a{display:inline-flex;align-items:center;min-height:36px;padding:6px 12px;
border-radius:6px;border:1px solid @LINE@;background:@SURF@;font-size:13px;color:@DIM@}
.zsort a[aria-current]{border-color:@ACC@;color:@ACC@;font-weight:600}
/* B10 compact filter bar */
.zfilt-bar{display:flex;flex-wrap:wrap;gap:8px 10px;align-items:center;margin:0 0 14px;
min-height:52px;max-height:none;padding:8px 0}
.zfilt-bar__group{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.zfilt-bar label.zfilt-lab{font-size:12px;font-weight:700;color:@DIM@;margin-right:2px}
.zfilt-bar select,.zfilt-bar .zfilt__year{min-height:40px;max-width:200px;padding:6px 10px;
border:1px solid @LINE@;border-radius:8px;background:@SURF@;color:@INK@;font:inherit;font-size:13px}
.zfilt-bar a.zfilt-chip{display:inline-flex;align-items:center;min-height:40px;padding:0 12px;
border:1px solid @LINE@;border-radius:8px;background:@SURF@;font-size:13px;font-weight:600;color:@INK@}
.zfilt-bar a.zfilt-chip[aria-current]{background:@ACCDK@;color:#fff;border-color:@ACCDK@}
.zfilt-bar a.zfilt-reset{color:@ACC@;font-weight:700;min-height:40px;display:inline-flex;align-items:center}
.zfilt-chips{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 12px}
.zfilt-chips span{display:inline-flex;align-items:center;min-height:32px;padding:0 10px;
border-radius:999px;background:@SURF@;border:1px solid @LINE@;font-size:12px}
.zfilt-chips a{margin-left:6px;color:@ACC@;font-weight:700}
.zfilt-toggle{display:none}
@media(max-width:767px){
.zfilt-toggle{display:inline-flex;min-height:44px;align-items:center;padding:0 14px;
border:1px solid @LINE@;border-radius:8px;background:@SURF@;font:inherit;font-weight:700;cursor:pointer}
.zfilt-bar{display:none;flex-direction:column;align-items:stretch;max-height:240px;overflow:auto;
border:1px solid @LINE@;border-radius:10px;padding:10px;background:@SURF@}
.zfilt-bar.is-open{display:flex}
.zfilt-bar select,.zfilt-bar .zfilt__year{max-width:none;width:100%}
.zfilt-bar__sticky{display:flex;gap:8px;position:sticky;bottom:0;padding-top:8px;background:@SURF@}
}
.zfilt-wrap{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 16px;align-items:center}
.zfilt-wrap a{display:inline-flex;align-items:center;min-height:36px;padding:6px 12px;
border-radius:6px;border:1px solid @LINE@;background:@SURF@;font-size:13px}
.zfilt-wrap a[aria-current]{background:@ACCDK@;color:#fff;border-color:@ACCDK@}
.zempty,.znf{padding:52px 18px;text-align:center;color:@DIM@}
.znf b{display:block;font-size:44px;font-weight:700;color:@ACC@;margin-bottom:6px}
.znf h1{font-size:24px;margin:0 0 8px;color:@INK@;font-weight:600}
.znf a{display:inline-block;margin-top:14px;background:@ACCDK@;color:#fff;
padding:11px 22px;border-radius:6px;font-weight:600}
.zsea__h{font-size:13px;color:@DIM@;margin:0 0 14px}
.zsea{margin:0 0 20px}

/* Страница произведения: постер + основная колонка (без правой rail). */
.zban{display:none}
.zmain{padding-top:24px;scroll-padding-top:88px}
@media(min-width:768px){.zmain{padding-top:36px}}
@media(min-width:1280px){.zmain{padding-top:40px}}
.ztitle{scroll-margin-top:88px}
#catalog-h1{scroll-margin-top:88px}
.ztitle{display:grid;grid-template-columns:1fr;gap:16px;margin:4px 0 12px;
align-items:start;max-height:none}
@media(min-width:900px){.ztitle{grid-template-columns:220px minmax(0,1fr);gap:24px}}
@media(min-width:1280px){.ztitle{grid-template-columns:240px minmax(0,1fr);gap:28px}}
.ztitle__poster{aspect-ratio:2/3;border-radius:8px;overflow:hidden;background:@ALT@;
position:relative;width:100%;max-width:240px;margin:0 auto}
@media(min-width:900px){.ztitle__poster{margin:0;max-width:none}}
.ztitle__poster img,.ztitle__poster .zhead__img{position:absolute;inset:0;z-index:1;
width:100%;height:100%;object-fit:cover;display:block}
.ztitle__main{min-width:0}
.ztitle__main h1{font-size:28px;line-height:1.18;margin:0 0 8px;letter-spacing:-.4px}
@media(min-width:1280px){.ztitle__main h1{font-size:32px}}
.ztitle__o{font-size:14px;color:@DIM@;margin:0 0 10px;font-weight:500;
overflow-wrap:anywhere}
.ztitle__desc{font-size:14.5px;line-height:1.62;color:@INK@;max-width:70ch;margin:0 0 10px}
.ztitle__desc--clamp{display:-webkit-box;-webkit-line-clamp:6;-webkit-box-orient:vertical;overflow:hidden}
.ztitle__desc.is-open{-webkit-line-clamp:unset;display:block;overflow:visible}
.ztitle__genres{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 10px}
.ztitle__genres a{display:inline-flex;align-items:center;min-height:28px;padding:4px 10px;border-radius:999px;border:1px solid @LINE@;background:@SURF@;color:@ACC@;font-size:12.5px;font-weight:600;text-decoration:none}
.ztitle__genres a:hover{border-color:@ACC@}
.ztitle__more{display:inline-block;margin:0 0 14px;color:@ACC@;font-weight:600;font-size:14px}
.ztitle__src{font-size:12px;color:@MUTE@;margin:0 0 12px;line-height:1.4}
.ztitle__cta{display:inline-flex;align-items:center;justify-content:center;
min-height:44px;padding:10px 18px;border-radius:8px;background:@ACCDK@;color:#fff;
font-weight:700;font-size:14px;text-decoration:none;margin:4px 0 0}
.ztitle__cta:hover{filter:brightness(1.05)}
.ztitle__rail{display:none}
.ztitle__dl{display:none}
.zpl{margin-top:18px}
.ztitle__facts{margin:0 0 12px;display:grid;gap:6px 16px;
grid-template-columns:1fr;max-width:70ch}
@media(min-width:600px){.ztitle__facts{grid-template-columns:1fr 1fr}}
.ztitle__facts div{display:grid;grid-template-columns:88px minmax(0,1fr);gap:4px 8px;
align-items:start}
.ztitle__facts dt{margin:0;font-size:11px;letter-spacing:.03em;text-transform:uppercase;
color:@DIM@;font-weight:700;line-height:1.35;padding-top:2px}
.ztitle__facts dd{margin:0;font-size:13.5px;color:@INK@;line-height:1.35;
overflow-wrap:anywhere;min-width:0}
.ztitle__facts a{color:@ACC@;font-weight:600}
.ztitle__chips{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 10px}
.ztitle__chip{display:inline-flex;align-items:center;min-height:28px;padding:4px 10px;
border-radius:6px;border:1px solid @LINE@;background:@ALT@;color:@DIM@;font-size:12px}
.zad{display:none}
.zad[data-ad-enabled="1"]{display:block;width:100%;max-width:300px;min-height:250px;
border:1px dashed @LINE@;border-radius:8px;background:@ALT@;margin:0 auto}
.zhead{display:contents}
.zhead__ps,.zhead__x,.zhead__o{display:contents}
.zbody{font-size:14.5px;line-height:1.62;color:@INK@;max-width:70ch;margin:18px 0 0}
.zaside{display:none}
/* Хаб подборок: карточка коллекции, а не ещё одна сетка тайтлов. */
.zhub{display:grid;gap:12px;margin:14px 0;grid-template-columns:1fr}
@media(min-width:600px){.zhub{grid-template-columns:repeat(2,1fr)}}
@media(min-width:1000px){.zhub{grid-template-columns:repeat(4,1fr)}}
@media(min-width:1440px){.zhub{grid-template-columns:repeat(4,1fr)}}
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
.zeps{display:grid;gap:8px;margin:14px 0;max-height:none;overflow:visible;
grid-template-columns:repeat(4,minmax(0,1fr))}
@media(min-width:768px){.zeps{grid-template-columns:repeat(8,minmax(0,1fr))}}
@media(min-width:1100px){.zeps{grid-template-columns:repeat(12,minmax(0,1fr))}}
.zeps a,.zeps span{display:flex;align-items:center;justify-content:center;
height:48px;padding:0;border-radius:6px;border:1px solid @LINE@;background:@SURF@;
font-size:14px;font-weight:600;box-sizing:border-box;min-width:0}
.zeps span,.zeps a[aria-disabled="true"],.zeps a[data-off]{opacity:.45;cursor:not-allowed;
pointer-events:none}
.zeps a[aria-current]{background:@ACCDK@;color:#fff;border-color:@ACCDK@;opacity:1;
pointer-events:auto}
.zsea__tabs{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 12px}
.zsea__tabs button,.zsea__tabs a{background:@SURF@;border:1px solid @LINE@;border-radius:6px;
padding:8px 14px;font-size:13.5px;font-weight:600;color:@DIM@;cursor:pointer}
.zsea__tabs button[aria-current],.zsea__tabs a[aria-current]{background:@ACCDK@;color:#fff;
border-color:@ACCDK@}
.zepnav{display:flex;gap:10px;flex-wrap:wrap;margin:16px 0;align-items:center}
.zepnav a,.zepnav span{background:@SURF@;border:1px solid @LINE@;border-radius:6px;
padding:9px 14px;font-size:13.5px;color:@ACC@;font-weight:600}
.zepnav span{color:@DIM@;border-style:dashed}

/* Плеер: единый 16:9 stage; компакт только для честных unavailable/error. */
.zpl{margin:12px auto 22px;width:100%;max-width:1200px}
.zpl__f{position:relative;width:100%;aspect-ratio:16/9;background:#0d1217;
border:1px solid @LINE@;border-radius:8px;overflow:hidden;min-height:200px}
.zpl__f[data-state="awaiting"],
.zpl__f[data-state="unavailable"],
.zpl__f[data-state="nosource"],
.zpl__f[data-state="noaccess"]{aspect-ratio:auto;min-height:120px;max-height:168px}
/* provider/error/slow keep stage size until fallback finishes — avoid 150px banner trap */
.zpl__f[data-state="provider"],
.zpl__f[data-state="error"],
.zpl__f[data-state="slow"]{aspect-ratio:16/9;max-height:none;min-height:200px}
.zpl__f[data-player-host],
.zpl__f [data-player-host]{position:absolute;inset:0;width:100%;height:100%;
display:block;min-height:100%}
.zpl__f video-player{position:absolute;inset:0;display:block;width:100%!important;
height:100%!important;max-width:none!important;max-height:none!important;border:0;
min-height:100%}
.zpl__f iframe,.zpl__f video{position:absolute;inset:0;width:100%;height:100%;
border:0;object-fit:contain}
/* Полные ряды. Сетка меняет число колонок по ширине, а число карточек у
   блока одно, поэтому на части ширин последний ряд оставался с пустыми
   ячейками: семь колонок и двенадцать карточек — это 7 + 5, и блок выглядел
   недогруженным. Здесь лишние карточки последнего неполного ряда скрываются
   для каждой ширины отдельно, так что виден только полный ряд.

   Скрывается ХВОСТ, а не выборка: карточки в разметке остаются, блок ничего
   не теряет, и на другой ширине они снова показываются. Правило применяется
   только к блокам, которые объявили себя рядами (`zg--rows`); каталог и
   поиск обязаны показывать всё до единой записи. */
/* Диапазоны ВЗАИМОИСКЛЮЧАЮЩИЕ (min-width вместе с max-width), и это не
   придирка к стилю. `min-width` накапливается: правило для 1024px продолжает
   действовать и на 1280, и на 1920. С одними `min-width` правило «скрыть с
   21-й» на пяти колонках скрывало карточки и на шести, семи, восьми, где они
   нужны, — проверено в браузере: на 1280, 1440 и 1920 было видно по 20 и ряды
   снова выходили неполными. Скрытое `display:none` не возвращается тем, что
   следующее правило скрывает меньше: оно скрывает ДОПОЛНИТЕЛЬНО. */
.zg--rows > *:nth-child(n+25){display:none}
@media(min-width:1024px) and (max-width:1279px){.zg--rows > *:nth-child(n+21){display:none}}
@media(min-width:1280px) and (max-width:1439px){.zg--rows > *:nth-child(n+25){display:none}}
@media(min-width:1440px) and (max-width:1919px){.zg--rows > *:nth-child(n+22){display:none}}
@media(min-width:1920px){.zg--rows > *:nth-child(n+25){display:none}}

/* Полоса действий под плеером. Ряд собирается только из работающих действий,
   поэтому пустых ячеек в нём не бывает по построению, а не по вёрстке. */
.zplbar{display:flex;flex-wrap:wrap;gap:8px;align-items:stretch;margin:12px 0 0}
.zplbar__b{display:inline-flex;align-items:center;justify-content:center;gap:6px;
flex:1 1 auto;min-height:44px;padding:0 14px;border-radius:10px;
border:1px solid @LINE@;background:@ALT@;color:@INK@;font-weight:600;font-size:14px;
line-height:1.2;white-space:nowrap;cursor:pointer;text-align:center;
font-family:inherit;text-decoration:none}
.zplbar__b:hover{border-color:@ACC@;color:@ACC@}
.zplbar__b[data-done]{border-color:@ACC@;color:@ACC@}
/* Телефон: перенос по две кнопки в ряд. 44px высоты сохраняются — кнопка
   остаётся удобной для нажатия, а подпись не сжимается до нечитаемой. */
@media(max-width:559px){.zplbar__b{flex:1 1 calc(50% - 4px);padding:0 10px;font-size:13.5px}}
/* Компьютер: кнопки по ширине содержимого, без растягивания на пустоту. Ряд
   получается один, потому что содержимое в него влезает (худший случай — семь
   кнопок, ~848px при доступных 992px на 1024px), а НЕ потому, что перенос
   запрещён. `flex-wrap:nowrap` здесь был бы обменом переноса на горизонтальное
   переполнение: любая восьмая кнопка или более широкий шрифт вылезли бы за
   край страницы. Перенос оставлен предохранителем: он срабатывает только
   тогда, когда ряд иначе не поместился бы. */
@media(min-width:1024px){.zplbar__b{flex:0 1 auto;padding:0 18px}}
.zpl__h{display:flex;align-items:baseline;justify-content:space-between;gap:12px;
font-size:22.1px;font-weight:400;margin:18px 0 10px}
.zpl__h span{font-size:13px;color:@DIM@;font-weight:600}
.zpl__s{position:absolute;inset:0;display:grid;place-items:center;padding:22px;
text-align:center;color:@DIM@;font-size:13.5px;line-height:1.5;z-index:2;
pointer-events:none}
/* P0: [hidden] must win over display:grid — otherwise UNAVAILABLE stays visible while PLAYING */
.zpl__s[hidden],
.zpl__f [data-player-state][hidden]{
display:none!important;visibility:hidden!important;pointer-events:none!important;
opacity:0!important;z-index:-1!important}
.zpl__f[data-state="playing"] .zpl__s,
.zpl__f[data-state="playing"] [data-player-state],
.zpl__f[data-state="ready"] .zpl__s,
.zpl__f[data-state="ready"] [data-player-state],
.zpl__f[data-state="resolving"] .zpl__s,
.zpl__f[data-state="resolving"] [data-player-state]{
display:none!important;visibility:hidden!important;pointer-events:none!important}
.zpl__f[data-state="provider"] .zpl__s,
.zpl__f[data-state="error"] .zpl__s,
.zpl__f[data-state="unavailable"] .zpl__s,
.zpl__f[data-state="nosource"] .zpl__s,
.zpl__f[data-state="noaccess"] .zpl__s{pointer-events:auto;display:grid}
.zpl__f [data-player-state]{padding:18px 16px;text-align:center;color:@DIM@;
font-size:13.5px;line-height:1.5;max-width:520px;margin:0 auto}
.zpl__f [data-player-state] b{display:block;color:@INK@;margin:0 0 6px;font-size:15px}

.zft{border-top:1px solid @LINE@;margin:48px 0 0;padding:32px 0 24px;
font-size:13px;color:@DIM@;display:block;width:100%;max-width:1760px;margin-left:auto;margin-right:auto}
.zft__cols{display:grid;gap:18px;grid-template-columns:1fr;margin:0 0 18px}
@media(min-width:700px){.zft__cols{grid-template-columns:minmax(0,1.3fr) repeat(2,minmax(0,1fr));gap:24px}}
@media(min-width:1100px){.zft__cols{grid-template-columns:minmax(0,1.4fr) repeat(3,minmax(0,1fr));gap:28px}}
.zft__cols--fallback{@media(min-width:700px){grid-template-columns:minmax(0,1.3fr) repeat(2,minmax(0,1fr))}}
/* Mobile: brand full width, then two compact link columns side-by-side. */
@media(max-width:699px){
.zft__cols,.zft__cols--fallback{grid-template-columns:1fr 1fr;gap:12px 18px}
.zft__cols > .zft__col:first-child,.zft__cols--fallback > .zft__col:first-child{grid-column:1/-1}
.zft__col--links{display:flex;flex-direction:column;gap:6px}
}
.zft__col{display:flex;flex-direction:column;gap:6px;min-width:0}
.zft__col b{color:@INK@;font-size:13px;margin:0 0 4px;font-weight:700}
.zft__col a{color:@ACC@;font-weight:500;line-height:1.35;min-height:44px;
display:inline-flex;align-items:center}
.zft__col a:hover,.zft__col a:focus-visible{text-decoration:underline}
.zft__about{font-size:13px;line-height:1.5;color:@DIM@;margin:0 0 4px;max-width:36ch}
.sf-contact{max-width:100%;min-width:0;overflow-wrap:anywhere;word-break:break-word;line-height:1.45;color:var(--a-ink,var(--z-ink,var(--ag-ink,inherit)))}.sf-contact a{color:inherit;text-decoration:underline;text-underline-offset:2px}.sf-contact a:hover{text-decoration:none}
.zft__bar{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;
gap:10px;padding-top:14px;border-top:1px solid @LINE@}
.zsec--seo{margin:32px 0 16px;max-width:860px}
.zsec--seo h2{font-size:22px;font-weight:600;margin:0 0 12px}
.zsec--seo p{font-size:16px;line-height:1.65;color:@DIM@;margin:0 0 12px}
.zsec--seo a{color:@ACC@;font-weight:600}
.zvb{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11px;
border:0;padding:0;background:transparent;color:@MUTE@}
/* Цвет берётся из токена полосы, а не из жёсткого белого: в светлой теме
   полоса светлая, и белая обводка с белым знаком на ней исчезали полностью. */
.zhd__searchbtn,.zhd__menu,.zhd__theme{display:inline-flex;align-items:center;justify-content:center;
height:44px;min-height:44px;
border:1px solid var(--z-line);border-radius:6px;
background:transparent;color:var(--z-railink);font-size:18px;cursor:pointer;flex:0 0 auto}
.zhd__menu{width:44px;min-width:44px}
/* «Поиск» — слово, а не значок: ширина по тексту, иначе оно вылезало из 44px. */
.zhd__searchbtn{min-width:44px;padding:0 10px;font-size:14px;font-weight:600;margin-left:auto}
.zhd__searchbtn:focus-visible,.zhd__menu:focus-visible,
.zhd__theme:focus-visible{outline:2px solid var(--z-railink);outline-offset:2px}
@media(min-width:768px){.zhd__searchbtn,.zhd__menu{display:none;margin-left:0}}
@media(min-width:768px) and (max-width:1279px){.zhd__menu{display:inline-flex;order:8}}
/* Переключатель тем виден на ЛЮБОЙ ширине, включая телефон: он не уезжает в
   ящик меню, потому что ящик скрыт, пока его не открыли, а тема нужна сразу.
   Ниже 768px остаётся только знак — подпись съела бы строку, где и так стоят
   логотип, поиск и меню; доступное имя кнопки при этом не теряется. */
.zhd__theme{gap:6px;padding:0 10px;min-width:44px;font-size:14px;font-weight:600;
white-space:nowrap;order:9}
.zhd__theme[aria-pressed]{line-height:1}
.zhd__themetx{display:none}
@media(min-width:768px){.zhd__themetx{display:inline}.zhd__theme{font-size:13px}}
.zhd__s--drawer{display:none}
/* Ящик выпадает ПОД полосой шапки на всю ширину. Прежде он был элементом той
   же строки высотой 56px: столбец ужимался до остатка ширины, а верхние
   пункты уходили выше края экрана, куда не прокрутить. */
@media(max-width:1279px){
.zhd__n{display:none;position:absolute;top:100%;left:0;right:0;
flex-direction:column;flex-wrap:nowrap;background:@RAIL@;padding:8px 12px 12px;
border-top:1px solid @LINE@;box-shadow:0 8px 16px rgba(0,0,0,.25);
max-height:calc(100vh - 56px);overflow-y:auto;box-sizing:border-box}
.zhd__n.is-open{display:flex}
.zhd__n a{flex:0 0 auto;justify-content:flex-start;width:100%}
body.nav-lock{overflow:hidden}
}
@media(min-width:768px) and (max-width:1279px){.zhd__n{max-height:calc(100vh - 62px);padding:8px 16px 12px}}
@media(max-width:767px){
.zhd__s--bar{display:none}
.zhd__s--drawer{display:flex;flex:0 0 auto;width:100%;max-width:none;margin:8px 0 0}
}
.zfilt__y{display:inline-flex;flex-wrap:wrap;gap:6px;max-width:100%;align-items:center}
.zfilt__year{min-height:36px;padding:6px 10px;border:1px solid @LINE@;border-radius:6px;
background:@SURF@;color:@INK@;font:inherit;font-size:13px;max-width:100%}
.zfilt__y a[data-count]::after{content:attr(data-count);margin-left:4px;color:@MUTE@;font-size:11px}
.zhub--home{display:grid;gap:10px;grid-template-columns:repeat(2,minmax(0,1fr))}
@media(min-width:768px){.zhub--home{grid-template-columns:repeat(4,minmax(0,1fr))}}

/* B06 genre chips */
.zgenres__nav{display:flex;flex-wrap:wrap;gap:8px}
.zgenres__nav a{display:inline-flex;align-items:center;min-height:36px;max-height:40px;
padding:0 12px;border-radius:8px;border:1px solid @LINE@;background:@SURF@;font-size:13px;font-weight:600}
/* B08 about collapse on mobile */
@media(max-width:767px){
.zsec--seo p:nth-of-type(n+2){display:none}
.zsec--seo.is-open p{display:block}
.zsec--seo__more{display:inline-flex;min-height:44px;align-items:center;margin-top:4px;
background:none;border:0;color:@ACC@;font:inherit;font-weight:700;cursor:pointer;padding:0}
}
@media(min-width:768px){.zsec--seo__more{display:none}}
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
/* Оформление Animedia 1.2.0. Числа измерены на эталоне (см. artifacts/evidence/
   templates-zona-animedia-visual-parity-006/reference/amd-online/):
     контейнер почти во всю ширину (поля 6 на узком, 1 дальше), шапка 90 на
     десктопе и 126 на узком и НЕ закреплённая, кегль тела 14, h2 16/700,
     ссылки 17/400, пропорция карточки 0.86, сетка 3 колонки до 1024 и 4 от
     1440 с зазором 10. Разметка и правила — свои. */
body{background:@PAGE@;color:@INK@;
font:14px/1.45 ui-sans-serif,system-ui,'Segoe UI',Roboto,Arial,sans-serif}
.zs{min-height:100vh;display:block}
.zmain{min-width:0}
.zwrap{max-width:1440px;margin:0 auto;padding:0 12px;box-sizing:border-box}
@media(min-width:768px){.zwrap{padding:0 16px}}
@media(min-width:1440px){.zwrap{padding:0 20px}}

/* Шапка: обычная, не закреплённая. На узком — кнопка меню вместо
   обрезанной горизонтальной ленты пунктов (эталон amd.online: hamburger). */
.zhd{position:relative;background:@RAIL@;color:@RAILINK@;
border-bottom:2px solid @ACC@}
.zhd__in{max-width:100%;margin:0 auto;padding:10px 6px;display:flex;
align-items:center;gap:8px;flex-wrap:wrap;min-height:0}
@media(min-width:768px){.zhd__in{padding:10px 1px;min-height:90px;flex-wrap:nowrap;gap:10px}}
.zhd__logo{font-size:22px;font-weight:800;letter-spacing:-.4px;color:@INK@;
white-space:nowrap;flex:0 0 auto}
.zhd__logo b{color:@ACC@;font-weight:800}
.zhd__menu{display:inline-flex;align-items:center;justify-content:center;
width:40px;height:40px;border:1px solid @LINE@;border-radius:4px;
background:@PAGE@;color:@INK@;font-size:20px;line-height:1;cursor:pointer;
flex:0 0 auto;margin-left:auto}
@media(min-width:768px){.zhd__menu{display:none}}
.zhd__n{display:none;gap:6px;flex:1 0 100%;order:4;min-width:0;
flex-wrap:wrap;overflow:visible;padding:6px 0 2px}
.zhd__n.is-open{display:flex}
@media(min-width:768px){.zhd__n{display:flex;flex:1 1 auto;order:0;
flex-wrap:nowrap;overflow-x:auto;scrollbar-width:none;padding:0}}
.zhd__n::-webkit-scrollbar{display:none}
.zhd__n a{padding:8px 10px;border-radius:4px;font-size:15px;font-weight:400;
color:@INK@;flex:1 1 calc(50% - 6px);text-align:center;min-width:0;
overflow-wrap:anywhere}
@media(min-width:768px){.zhd__n a{flex:0 0 auto;white-space:nowrap;font-size:17px;
text-align:left;padding:7px 9px}}
.zhd__n a:hover{background:@ALT@;color:@ACC@}
.zhd__n a[aria-current]{color:@ACC@;font-weight:700;box-shadow:inset 0 -2px 0 @ACC@}
.zhd__s{display:flex;flex:1 1 120px;min-width:0;max-width:340px;
border:1px solid @LINE@;border-radius:4px;overflow:hidden;background:@PAGE@}
.zhd__s input{flex:1;min-width:0;border:0;padding:8px 10px;font-size:14px;
color:@INK@;font-family:inherit;background:transparent}
.zhd__s button{border:0;background:@ACC@;color:#fff;padding:0 14px;
font-weight:700;font-size:13px;cursor:pointer;font-family:inherit}

/* Служебная полоса состояния данных. */
.ast{background:@ALT@;border:1px solid @LINE@;border-left:4px solid @ACC@;
border-radius:4px;padding:14px 16px;margin:14px 0;font-size:13.5px;
line-height:1.55;color:@INK@}
.ast b{display:block;font-size:15px;font-weight:700;margin-bottom:5px;color:@ACC@}
.ast code{background:@SURF@;padding:1px 5px;border-radius:3px;font-size:12.5px}

.zrail,.zrail__logo,.zrail__sub,.zrail__t,.zrail__n,.zrail__g{display:none}
.ztop{border-bottom:1px solid @LINE@;background:@PAGE@}
.ztop__a{display:flex;align-items:center;gap:14px;padding:10px 0}
.ztop__s{flex:1;display:flex;border:1px solid @LINE@;border-radius:4px;
overflow:hidden;background:@PAGE@;max-width:600px}
.ztop__s input{flex:1;border:0;padding:9px 12px;font-size:14px;
background:transparent;color:@INK@;font-family:inherit}
.ztop__s button{border:0;background:@ACC@;color:#fff;padding:0 16px;
font-weight:700;font-size:13px;cursor:pointer;font-family:inherit}
.ztop__b{display:flex;gap:14px;padding:0 0 9px;font-size:13px;color:@DIM@;
flex-wrap:wrap;max-width:100%;min-width:0}
.ztop__b a{color:@ACC@;font-weight:700;display:inline-block;padding:4px 2px;
max-width:100%;overflow-wrap:anywhere}

/* Типографика по измерению: h2 16/700, ссылки 17/400. */
.zh{font-size:15px;line-height:1.35;font-weight:500;margin:14px 0 5px;max-width:100%;
overflow-wrap:anywhere}
@media(min-width:768px){.zh{font-size:16px;line-height:1.3}}
.zh--sm{font-size:16px;font-weight:700;margin:20px 0 5px}
.zsub{font-size:13px;color:@DIM@;margin:0 0 14px}
.zsub a{color:@ACC@;font-weight:700;padding:4px 2px;display:inline-block}
.zcr{font-size:12.5px;color:@DIM@;padding:10px 0 0}
.zcr a{color:@ACC@}

.zsec{margin:18px 0 22px}
.zsec__h{display:flex;align-items:center;justify-content:space-between;
gap:10px;margin:0 0 9px;border-bottom:1px solid @LINE@;padding-bottom:6px}
.zsec__h h2{font-size:16px;font-weight:700;margin:0}
.zsec__h a{font-size:13px;color:@ACC@;font-weight:700;white-space:nowrap}
.zrl{position:relative}
.zrl__vp{overflow-x:auto;overflow-y:hidden;scroll-behavior:smooth;
scroll-snap-type:x mandatory;-webkit-overflow-scrolling:touch;padding:2px 0 8px}
.zrl__track{display:flex;gap:10px;min-width:min-content;align-items:flex-start}
.zrl__track>*{flex:0 0 148px;scroll-snap-align:start;max-width:180px}
@media(min-width:1440px){.zrl__track>*{flex-basis:160px}}
.zrl__btn{position:absolute;top:34%;transform:translateY(-50%);z-index:5;
width:36px;height:48px;min-width:44px;min-height:44px;border:1px solid @LINE@;border-radius:4px;cursor:pointer;
background:rgba(255,255,255,.96);color:@ACC@;font-size:17px;line-height:1;
display:flex;align-items:center;justify-content:center;opacity:.92;box-shadow:0 1px 4px rgba(0,0,0,.12)}
.zrl__btn:focus-visible{outline:2px solid @ACC@;outline-offset:2px}
.zrl__btn--p{left:-4px}
.zrl__btn--n{right:-4px}
.zrl__btn[disabled]{opacity:.32;cursor:default}
.zrl__vp{mask-image:linear-gradient(90deg,transparent,#000 12px,#000 calc(100% - 12px),transparent);
-webkit-mask-image:linear-gradient(90deg,transparent,#000 12px,#000 calc(100% - 12px),transparent)}
@media(max-width:430px){
.zrl__btn{width:32px;min-width:32px;height:40px;min-height:40px}
.zrl__btn--p{left:0}.zrl__btn--n{right:0}
.zrl{padding:0 2px}
}

/* Компактная сетка: 2→4→5→6→7→8; без прыжка 4→7 и без пустой зоны >1 карточки. */
.zg{display:grid;gap:12px;grid-template-columns:repeat(2,minmax(0,1fr));
align-items:stretch;justify-content:center;width:100%;box-sizing:border-box}
@media(min-width:768px){.zg{grid-template-columns:repeat(4,minmax(0,1fr))}}
@media(min-width:1024px){.zg{grid-template-columns:repeat(5,minmax(0,1fr))}}
@media(min-width:1280px){.zg{grid-template-columns:repeat(6,minmax(0,1fr))}}
@media(min-width:1440px){.zg{grid-template-columns:repeat(7,minmax(0,1fr))}}
@media(min-width:1920px){.zg{grid-template-columns:repeat(8,minmax(0,1fr))}}
.zpage{min-width:0;width:100%;box-sizing:border-box}
.zt{display:flex;flex-direction:column;background:@PAGE@;
border:1px solid @LINE@;border-radius:4px;overflow:hidden;min-width:0;
height:100%;transition:border-color .14s,box-shadow .14s}
.zt:hover{border-color:@ACC@;box-shadow:0 4px 14px rgba(0,0,0,.09)}
.zt__p{display:block;aspect-ratio:2/3;background:@SURF@;position:relative;flex:0 0 auto}
.zt__p img,.zt__img{position:absolute;inset:0;z-index:1;width:100%;height:100%;
object-fit:cover;display:block}
.zt__none{position:absolute;inset:0;display:grid;place-items:center;padding:10px;
text-align:center;color:@MUTE@;font-size:11.5px;line-height:1.3}
.zt__none b{display:block;font-size:22px;font-weight:800;color:@DIM@;margin-bottom:3px}
.zt__b{padding:7px 8px 9px;display:flex;flex-direction:column;gap:3px;flex:1}
.zt__t{font-size:14.5px;font-weight:700;line-height:1.3;
display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;
overflow-wrap:anywhere;word-break:break-word;max-height:calc(1.3em * 2)}
.zt__m{display:block;font-size:12.5px;color:@DIM@;line-height:1.3;
white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.zt__r{display:flex;gap:8px;font-size:12.5px;color:@DIM@;margin-top:auto;
padding-top:3px;flex-wrap:wrap;align-items:center}
.zt__r b,.zt__r i{color:@ACC@;font-weight:700;font-style:normal}
.zt__r em{color:@MUTE@;font-style:italic}
.zt__play{display:inline-flex;align-items:center;justify-content:center;
min-width:20px;font-size:11px;color:@ACC@;font-weight:700}

.zl{display:flex;flex-direction:column;gap:8px}
.zr{display:grid;grid-template-columns:58px 1fr;gap:10px;padding:8px;
background:@PAGE@;border:1px solid @LINE@;border-radius:4px;align-items:start}
@media(min-width:768px){.zr{grid-template-columns:74px 1fr}}
.zr:hover{border-color:@ACC@}
.zr__p{aspect-ratio:2/3;background:@SURF@;border-radius:3px;overflow:hidden;
position:relative}
.zr__p img,.zr__img{position:absolute;inset:0;width:100%;height:100%;
object-fit:cover;display:block;z-index:1}
.zr__none{position:absolute;inset:0;display:grid;place-items:center;
text-align:center;color:@MUTE@;font-size:10.5px;padding:5px}
.zr__t{display:block;font-size:14px;font-weight:700;line-height:1.3;margin-bottom:2px}
.zr__m{display:block;font-size:12px;color:@DIM@;margin-bottom:4px}
.zr__d{font-size:12px;color:@DIM@;line-height:1.42;
display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.zr__r{display:flex;gap:9px;font-size:11.5px;color:@DIM@;margin-top:5px;flex-wrap:wrap}

.zstrip{display:flex;gap:6px;flex-wrap:wrap;margin:12px 0 5px}
.zstrip a{background:@ALT@;border:1px solid @LINE@;border-radius:4px;
padding:6px 10px;font-size:12.5px;color:@INK@;font-weight:600}
.zstrip a:hover{border-color:@ACC@;color:@ACC@}
.zstrip a[aria-current]{background:@ACC@;color:#fff;border-color:@ACC@}
.zpg{display:flex;gap:5px;justify-content:center;margin:22px 0;flex-wrap:wrap}
.zpg a,.zpg span{padding:7px 12px;border-radius:4px;border:1px solid @LINE@;
background:@PAGE@;font-size:13px;min-width:36px;text-align:center}
.zpg span{background:@ACC@;color:#fff;border-color:@ACC@}
.zempty,.znf{padding:44px 16px;text-align:center;color:@DIM@}
.znf b{display:block;font-size:40px;font-weight:800;color:@ACC@;margin-bottom:5px}
.znf h1{font-size:21px;margin:0 0 7px;color:@INK@;font-weight:700}
.znf a{display:inline-block;margin-top:12px;background:@ACC@;color:#fff;
padding:10px 20px;border-radius:4px;font-weight:700}
.zsea__h{font-size:13px;color:@DIM@;margin:0 0 12px}
.zsea{margin:0 0 18px}

/* Расписание: день, время и номер серии. Пустое значение названо словами. */
.asch{display:grid;gap:10px;margin:12px 0}
@media(min-width:900px){.asch{grid-template-columns:repeat(2,1fr)}}
@media(min-width:1440px){.asch{grid-template-columns:repeat(4,1fr)}}
.asch__d{border:1px solid @LINE@;border-radius:4px;background:@PAGE@;overflow:hidden}
.asch__d h3{margin:0;padding:8px 11px;font-size:13px;font-weight:700;
background:@ALT@;border-bottom:1px solid @LINE@}
.asch__l{margin:0;padding:0;list-style:none}
.asch__l li{display:flex;gap:9px;align-items:baseline;padding:7px 11px;
border-bottom:1px solid @LINE@;font-size:12.5px}
.asch__l li:last-child{border-bottom:0}
.asch__t{color:@ACC@;font-weight:700;flex:0 0 42px;font-variant-numeric:tabular-nums}
.asch__e{color:@DIM@;margin-left:auto;flex:0 0 auto;font-size:11.5px}
.asch__n{color:@MUTE@;font-style:italic}

.zban{position:relative;border-radius:4px;overflow:hidden;background:@SURF@;
margin:14px 0 0;min-height:170px;max-height:240px}
.zban__img{position:absolute;inset:0;opacity:.5}
.zban__img img{width:100%;height:100%;object-fit:cover;display:block}

/* Верхняя карусель главной (amd.online: акцентная лента постеров). Только
   реальные карточки снимка — без выдуманных тайтлов и без чужих CTA. */
.ahero{margin:10px 0 16px;padding:14px 8px 10px;border-radius:4px;
background:@ACC@;color:#fff;overflow:hidden}
.ahero .zrl__vp{padding-bottom:4px}
.ahero .zrl__track{gap:12px}
.ahero .zrl__track>*{flex:0 0 118px}
@media(min-width:768px){.ahero{padding:18px 12px 14px}
.ahero .zrl__track>*{flex-basis:140px}}
@media(min-width:1440px){.ahero .zrl__track>*{flex-basis:156px}}
.ahero .zt{background:transparent;border:0;border-radius:0;box-shadow:none;color:#fff}
.ahero .zt:hover{border:0;box-shadow:none;opacity:.92}
.ahero .zt__p{border-radius:2px;aspect-ratio:2/3;background:rgba(0,0,0,.18)}
.ahero .zt__b{padding:6px 2px 0}
.ahero .zt__t{color:#fff;font-size:12.5px;-webkit-line-clamp:2}
.ahero .zt__m,.ahero .zt__r{display:none}
.ahero .zrl__btn{background:rgba(255,255,255,.95);color:@ACC@;border-color:transparent}
.ahero__cap{display:none}

/* «Новые серии» — компактные list-items 3–4 колонки, без растяжки. */
.zsec--eps .zl{display:grid;gap:10px;grid-template-columns:1fr;
border:0;background:transparent;overflow:visible}
@media(min-width:700px){.zsec--eps .zl{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(min-width:1100px){.zsec--eps .zl{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(min-width:1440px){.zsec--eps .zl{grid-template-columns:repeat(4,minmax(0,440px))}}
.zsec--eps .zr{border:1px solid @LINE@;border-radius:4px;border-bottom:1px solid @LINE@;
padding:8px 10px;align-items:center;grid-template-columns:72px minmax(0,1fr);
max-width:440px;width:100%;box-sizing:border-box}
.zsec--eps .zr:nth-child(odd){border-right:1px solid @LINE@}
.zsec--eps .zr__p{aspect-ratio:2/3;border-radius:3px;max-width:72px}
.zsec--eps .zr__t{font-size:13.5px;line-height:1.25;
display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;
min-height:calc(1.25em * 2)}
.zsec--eps .zr__m{font-size:12px}
.zsec--eps .zr__d{display:block;font-size:11.5px;color:@MUTE@;-webkit-line-clamp:1}

/* Title hub: poster + main + rail; player starts in first viewport. */
.zban{display:none}
.zhead{display:contents}
.zhead__ps,.zhead__x,.zhead__o{display:contents}
.ztitle{display:grid;grid-template-columns:1fr;gap:16px;margin:12px 0 8px;
align-items:start}
@media(min-width:768px){.ztitle{grid-template-columns:220px minmax(0,1fr);gap:20px}}
@media(min-width:1100px){.ztitle{grid-template-columns:240px minmax(0,1fr) 300px;gap:22px}}
@media(min-width:1280px){.ztitle{grid-template-columns:250px minmax(0,1fr) 320px;gap:24px}}
.ztitle__poster{aspect-ratio:2/3;border-radius:6px;overflow:hidden;background:@SURF@;
position:relative;width:100%;max-width:260px;margin:0 auto}
@media(min-width:768px){.ztitle__poster{margin:0;max-width:none}}
.ztitle__poster img,.ztitle__poster .zhead__img{position:absolute;inset:0;z-index:1;
width:100%;height:100%;object-fit:cover;display:block}
.ztitle__main{min-width:0}
.ztitle__main h1{font-size:24px;line-height:1.2;margin:0 0 8px;letter-spacing:-.3px}
@media(min-width:1100px){.ztitle__main h1{font-size:28px}}
.ztitle__o{font-size:13.5px;color:@DIM@;margin:0 0 8px}
.ztitle__desc{font-size:14px;line-height:1.55;color:@INK@;max-width:68ch;margin:0 0 12px;
display:-webkit-box;-webkit-line-clamp:5;-webkit-box-orient:vertical;overflow:hidden}
.ztitle__desc--empty{display:none}
.ztitle__cta{display:inline-flex;align-items:center;justify-content:center;
min-height:40px;padding:8px 16px;border-radius:4px;background:@ACC@;color:#fff;
font-weight:700;font-size:14px;text-decoration:none}
.ztitle__cta:hover{filter:brightness(1.05)}
.ztitle__rail{min-width:0;display:flex;flex-direction:column;gap:12px}
@media(max-width:1099px){.ztitle__rail{order:3}}
.ztitle__dl{margin:0;background:@ALT@;border:1px solid @LINE@;border-radius:4px;
padding:10px 12px;display:grid;gap:8px}
.ztitle__dl div{display:grid;grid-template-columns:92px minmax(0,1fr);gap:6px 10px;
align-items:baseline}
.ztitle__dl dt{font-size:11px;letter-spacing:.04em;text-transform:uppercase;
color:@DIM@;font-weight:700;margin:0}
.ztitle__dl dd{margin:0;font-size:13px;color:@INK@;line-height:1.35;
overflow-wrap:anywhere}
.ztitle__dl a{color:@ACC@;font-weight:700}
.zad{display:none}
.zad[data-ad-enabled="1"]{display:block;width:100%;max-width:300px;min-height:250px;
border:1px dashed @LINE@;border-radius:4px;background:@ALT@;margin:0 auto}
.zbody{font-size:14px;line-height:1.55;color:@INK@;max-width:70ch;margin:14px 0 0}
.zaside{display:none}
/* Хаб подборок: карточка коллекции, а не ещё одна сетка тайтлов. */
.zhub{display:grid;gap:12px;margin:14px 0;grid-template-columns:1fr}
@media(min-width:600px){.zhub{grid-template-columns:repeat(2,1fr)}}
@media(min-width:1000px){.zhub{grid-template-columns:repeat(3,1fr)}}

/* «Ждём премьеру»: карточка начинается с ДАТЫ, а не с картинки. Постера у
   объявленного релиза в каталоге нет, а рисовать букву вместо обложки или
   брать чужую картинку нельзя — поэтому блок устроен иначе и не притворяется
   постерной полкой. */
/* Дата пересмотра состава подборки: строка под вступлением. */
.col__upd{margin:0 0 14px;color:@DIM@;font-size:13px}
.zann{margin:0 0 28px}
.zann__sub{margin:0 0 14px;color:@DIM@;font-size:13.5px;line-height:1.5;max-width:62ch}
.zann__g{display:grid;gap:12px;grid-template-columns:1fr}
.zann__c{display:flex;flex-direction:column;gap:4px;padding:14px;border:1px solid @LINE@;border-radius:14px;background:@SURF@}
.zann__d{font-size:17px;font-weight:700;line-height:1.2}
.zann__k{font-size:12.5px;color:@DIM@}
.zann__more{font-size:12.5px;color:@DIM@}
.zann__t{margin-top:4px;font-size:16px;font-weight:650;line-height:1.3}
.zann__r{font-size:13.5px;line-height:1.5;color:@DIM@}
.zann__src{margin-top:6px;font-size:13px;font-weight:700;color:@ACC@;min-height:44px;display:inline-flex;align-items:center}
@media(min-width:640px){.zann__g{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(min-width:1024px){.zann__g{grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}}
.zhub__c{display:block;padding:12px;border:1px solid @LINE@;border-radius:6px;
background:@SURF@;color:inherit;text-decoration:none}
.zhub__c:hover,.zhub__c:focus-visible{border-color:@ACC@;outline:none}
.zhub__g{display:flex;gap:4px;margin-bottom:9px}
.zhub__p{flex:1 1 0;aspect-ratio:2/3;overflow:hidden;border-radius:4px;background:@ALT@}
.zhub__img{width:100%;height:100%;object-fit:cover;display:block}
.zhub__t{display:block;font-weight:700;font-size:15px}
.zhub__m{display:block;font-size:12px;color:@DIM@;font-weight:600;margin:2px 0 4px}
.zhub__d{display:block;font-size:13px;color:@DIM@;line-height:1.45}

/* Компактные номерные кнопки серий: CSS Grid auto-fill, без скрытых колонок. */
.zeps{display:grid;gap:6px;margin:12px 0;max-height:70vh;overflow-x:hidden;
overflow-y:auto;overscroll-behavior:contain;align-content:flex-start;
grid-template-columns:repeat(auto-fill,minmax(44px,1fr));width:100%;
max-width:100%;min-width:0;box-sizing:border-box}
@media(min-width:768px){.zeps{max-height:520px;
grid-template-columns:repeat(auto-fill,minmax(48px,1fr))}}
.zeps a,.zeps span{display:inline-flex;align-items:center;justify-content:center;
min-width:44px;min-height:44px;width:100%;height:44px;padding:0;
border-radius:6px;border:1px solid @LINE@;background:@PAGE@;font-size:13px;
font-weight:700;font-variant-numeric:tabular-nums;box-sizing:border-box}
@media(min-width:768px){.zeps a,.zeps span{min-height:48px;height:48px}}
.zeps span{opacity:.5}
.zeps a[aria-current]{background:@ACC@;color:#fff;border-color:@ACC@}
.zeps a[data-off]{opacity:.45;pointer-events:none}
.zsea__h{display:flex;justify-content:space-between;align-items:baseline;
gap:10px;flex-wrap:wrap;margin:0 0 10px}
.zsea__h b{font-size:15px;font-weight:700}
.zsea__h span{font-size:13px;color:@DIM@}
.zepnav{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0}
.zepnav a{background:@ALT@;border:1px solid @LINE@;border-radius:4px;
padding:8px 12px;font-size:13px;color:@ACC@;font-weight:700}

.zpl{margin:14px 0}
.zpl__f{aspect-ratio:16/9;background:#f3f3f3;border:1px solid @LINE@;
border-radius:4px;overflow:hidden;position:relative;max-height:min(56vw,420px)}
.zpl__f[data-state=playable]{background:#101010;max-height:none}
.zpl__h{font-size:16px;font-weight:700;margin:18px 0 9px;display:flex;
align-items:baseline;justify-content:space-between;gap:10px}
.zpl__h span{font-size:12.5px;font-weight:600;color:@DIM@}
.zpl__s,.zpl [data-player-state]{position:absolute;inset:0;display:grid;
place-items:center;padding:16px;text-align:center;color:@INK@;font-size:13px;
line-height:1.45;background:#f7f7f7}
.zpl [data-player-state] b{display:block;font-size:15px;margin-bottom:6px}
.zpl [data-player-state] p{margin:0;max-width:36ch;color:@DIM@}

.zft{border-top:2px solid @ACC@;margin:28px 0 0;padding:18px 0 10px;
font-size:13px;color:@DIM@}
.zft__grid{display:grid;gap:14px;grid-template-columns:1fr;
margin-bottom:14px}
@media(min-width:768px){.zft__grid{grid-template-columns:repeat(4,1fr)}}
.zft__col b{display:block;font-size:12.5px;font-weight:700;color:@INK@;
margin-bottom:6px;text-transform:uppercase;letter-spacing:.03em}
.zft__col a{display:block;padding:3px 0;color:@DIM@;font-size:13px}
.zft__col a:hover{color:@ACC@}
.zft__about{margin:0;font-size:12.5px;line-height:1.45;color:@DIM@}
.sf-contact{max-width:100%;min-width:0;overflow-wrap:anywhere;word-break:break-word;line-height:1.45;color:var(--a-ink,var(--z-ink,var(--ag-ink,inherit)))}.sf-contact a{color:inherit;text-decoration:underline;text-underline-offset:2px}.sf-contact a:hover{text-decoration:none}
.zft__bar{display:flex;justify-content:space-between;align-items:center;
gap:10px;flex-wrap:wrap;border-top:1px solid @LINE@;padding-top:10px}
.zvb{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;
color:@MUTE@;letter-spacing:0}
.zseo{margin:22px 0 8px;padding:12px 0 0;border-top:1px solid @LINE@;
color:@DIM@;font-size:13px;line-height:1.55;max-width:72ch}
.zseo h2{font-size:14px;font-weight:700;color:@INK@;margin:0 0 6px}
.zseo p{margin:0 0 8px}
@media(max-width:767px){.zseo{font-size:12.5px}
.zseo details{border:1px solid @LINE@;border-radius:4px;padding:8px 10px}
.zseo summary{cursor:pointer;font-weight:700;color:@INK@}}
.zseo .zseo__full{display:none}
@media(min-width:768px){.zseo details{display:none}
.zseo .zseo__full{display:block}}

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
.rbs__i{background:@ALT@;border:1px solid @LINE@;color:@INK@}
.rbs__s{color:@ACC@}
.rbs__n{color:@INK@}
.rbs__l--own{color:@DIM@}
.rbs--none{color:@MUTE@}

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
        # Цвета уходят в CSS ссылками на переменные, а палитры объявлены выше
        # обеими темами сразу. Тема перестала быть вкомпилированной в страницу.
        "стиль": (lambda: _тема_зона() + _общее(ЗОНА_ТОКЕНЫ_ССЫЛКИ)
                  + _подставить(ЗОНА_СТИЛЬ, ЗОНА_ТОКЕНЫ_ССЫЛКИ))
                  if ОФОРМЛЕНИЕ_ПЕРЕРАБОТАННОЕ else
                  (lambda: _общее(ЗОНА_ТОКЕНЫ_1_1) + _подставить(ЗОНА_СТИЛЬ_1_1, ЗОНА_ТОКЕНЫ_1_1)),
        # Clean kind routes — same map as Обработчик.МАРШРУТЫ_ВИДА. Query
        # `?kind=` remains valid for combinations; nav must not 404.
        # B01 nav labels: user-facing «Главная»/«Новинки»/«Фильмы»/«Каталог»
        # (not abstract «Обзор» / «Что нового» / «Кино» / «Весь каталог»).
        # «Дорамы» стоят отдельным пунктом, а не внутри «Сериалов»: 9 616
        # записей снимка — дорамы, и до этой правки они лежали в «Сериалах» и
        # на главной, где им не место.
        "нав": [("/", "Главная"), ("/new/", "Новинки"),
                ("/movies/", "Фильмы"), ("/series/", "Сериалы"),
                ("/animation/", "Анимация"), ("/doramas/", "Дорамы"),
                ("/collections/", "Подборки"),
                ("/catalog/", "Каталог")],
        "поиск": "Название фильма или сериала",
        "полосы": [("Фильмы", "/movies/", "movie"),
                   ("Сериалы", "/series/", "series"),
                   ("Анимация", "/animation/", "animation"),
                   ("Дорамы", "/doramas/", "dorama")],
        "лид": "Кинопортал: что смотреть и где это найти",
        # Заголовок первого уровня главной. Отдельным полем, а не лидом:
        # «кинопортал» — единственное содержательное слово в <title>, и H1
        # повторял бы заголовок страницы, а «что смотреть и где это найти» —
        # обещание услуги, а не название предмета. Перечислены ВСЕ три вида
        # каталога (`kind`: Фильм, Сериал, Мультфильм): «фильмы и сериалы»,
        # как на zonafilm.cc, опускало бы третий. Строку назвала линия SEO
        # 27.10 — наименование её область; механизм её только ставит.
        "h1 главной": "Фильмы, сериалы и мультфильмы онлайн",
        "метка": "Z",
    },
    "animedia": {
        "вид": "animedia",
        "токены": АНИМЕДИА_ТОКЕНЫ,
        "стиль": lambda: _общее(АНИМЕДИА_ТОКЕНЫ) + _подставить(АНИМЕДИА_СТИЛЬ, АНИМЕДИА_ТОКЕНЫ),
        "нав": [("/", "Главная"), ("/catalog/", "Каталог аниме"),
                ("/new/", "Новые эпизоды"), ("/schedule/", "Расписание"),
                ("/collections/", "Подборки")],
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
# Playback aggregators: contract allows kp/mali/mdl; cvh is provider-id UUID mode.
# IMDb is never a playback aggregator (PC-2).
АГРЕГАТОРЫ = ("cvh", "kp", "mdl", "mali")
АГРЕГАТОРЫ_ПЛЕЕРА = frozenset({"kp", "mdl", "mali", "cvh"})

#: Соответствие «ключ внешнего идентификатора → агрегатор». `imdb` в контракте
#: агрегатором не значится, поэтому запись только с imdb источника не имеет.
КЛЮЧ_АГРЕГАТОРА = {"kp": "kp"}

#: Расширенная цепочка запасных ключей. Работает только в режиме `provider-id`:
#: прежний режим обязан вести себя в точности как раньше, иначе выкладка по
#: одному домену теряет смысл — менялись бы сразу все.
ЗАПАСНЫЕ_КЛЮЧИ = (("kp", "kp"), ("mdl", "mdl"), ("mal", "mali"))

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
    ("dorama", "дорама"),
    ("drama", "драма"),
    ("comedy", "комедия"),
    ("triller", "триллер"),
    ("action", "боевик"),
    ("melodrama", "мелодрама"),
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
        if not значение or агрегатор not in АГРЕГАТОРЫ_ПЛЕЕРА:
            return
        # PC-2: IMDb never used as playback identifier.
        if агрегатор == "imdb":
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
        return ("noaccess", "Просмотр на сайте не подключён",
                "Каталог, описание и список серий доступны полностью.")
    if not (агрегатор and ид):
        if not деталь:
            return ("nosource", "Просмотр пока недоступен",
                    "Описание и список серий появятся здесь сами.")
        return ("nosource", "Просмотр пока недоступен",
                "Для этой записи видео ещё нет. Плеер включится здесь сам.")
    return ("playable", "", "")


def выбрать_доступную_серию(деталь: dict) -> tuple[int, int | None]:
    """Детерминированный выбор серии для хаба сериала.

    Приоритет: первая реально доступная (avail) → номер сезона без эпизода
    (честный unavailable/awaiting без SDK). Прямой URL недоступного эпизода
    не подменяется молча — только хаб выбирает первую playable.
    """
    сезоны = список_серий(деталь)
    if not сезоны:
        return 1, None
    доступные: list[tuple[int, int]] = []
    for с in сезоны:
        # Номера берутся из множества доступных, а не из отрезка «с первой
        # по avail»: спецвыпуск с номером 0 идёт первым и предлагается тогда,
        # когда обычной первой серии у источника нет.
        for н in sorted(с["доступные"] & set(с["номера"])):
            доступные.append((с["n"], н))
    if доступные:
        # Hub picks the first playable episode; direct episode URLs stay exact.
        return доступные[0]
    return сезоны[0]["n"], None


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
                "До выбора серии запросов за видео нет.</p></div>")
    if эпизод is not None and not серия_с_дорожкой(деталь, сезон, эпизод):
        доступно = 0
        всего = 0
        for с in список_серий(деталь):
            if с["n"] == сезон:
                доступно, всего = с["доступно"], с["eps"]
                break
        # Числа снимка — в журнал службы, а не на страницу. Посетителю «в
        # снимке серий 12, с дорожкой 11» не говорит ничего, а разбирать по
        # ним случай всё равно буду я, и удобнее это делать по журналу.
        print(f"[плеер] дорожки нет: slug={запись.get('slug')!r} "
              f"тип={деталь.get('type')!r} сезон={сезон} серия={эпизод} "
              f"eps={всего} avail={доступно} источники="
              f"{[и.get('provider') for и in (деталь.get('sources') or []) if isinstance(и, dict)]}",
              flush=True)
        return ("unavailable",
                f'<div class="{вид.кл_состояния}" data-player-state>'
                "<b>Эта серия пока недоступна</b>"
                "<p>Видео этой серии пока не опубликовано. "
                "Выберите серию из доступных в списке ниже.</p></div>")
    if ПЛЕЕР.get("source_mode") == "provider-id":
        кандидаты = кандидаты_источника(деталь)
    else:
        а, и = источник_плеера(деталь)
        кандидаты = [(а, и)] if а and и else []
    if not кандидаты:
        return ("nosource",
                f'<div class="{вид.кл_состояния}" data-player-state>'
                "<b>Видео временно недоступно</b>"
                "<p>Для этой записи пока нет воспроизведения.</p></div>")
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
        "is-show-voice-only": "false", "is-show-banner": "false",
        "disable-licensed": "false",
    }
    if эпизод is not None:
        атрибуты["episode"] = str(эпизод)
    строка = " ".join(f'{к}="{html.escape(str(з))}"' for к, з in атрибуты.items())
    # SSR: resolving — кандидат есть, playable_source ещё не подтверждён.
    return ("resolving",
        f'<div data-player-host data-src-candidates="{список_json}">'
        f"<video-player {строка}></video-player></div>"
        f'<div class="{вид.кл_состояния}" data-player-state hidden>'
        "<b>Видео временно недоступно</b>"
        "<p>Попробуйте другую озвучку или вернитесь позже.</p></div>"
        '<noscript><div class="' + вид.кл_состояния + '">'
        "<b>Нужен JavaScript</b><p>Плеер подключается скриптом, "
        "и без JavaScript он не запустится. Описание, серии и каталог "
        "доступны без него.</p></div></noscript>"
    )


СКРИПТ_ПЛЕЕРА_КЛИЕНТ = """
(function(){
 var f=document.querySelector('[data-player]'); if(!f) return;
 var host=f.querySelector('[data-player-host]');
 if(!host) return;
 var st=f.querySelector('[data-player-state]');
 var label=document.querySelector('.zpl__h span, .pl__note');
 var cands=[];
 try{ cands=JSON.parse(host.getAttribute('data-src-candidates')||'[]')||[]; }catch(e){ cands=[]; }
 var generation=0, attempt=0, idx=0, playing=false, отказ=false, seen, timers=[];
 var maxFallback=3, baseAttrs={}, lastPos=0, readyAt=0, activeSource=null;
 var requested=false, adActive=false, playTimers=[];
 /* T338: желание зрителя, записанное ПЕРВЫМ нажатием по рамке. Оно
    тратится на разрешение источника и дальше не продолжается — измерено
    27.10 на живых витринах. Здесь оно запоминается и применяется к медиа,
    как только медиа появилось. */
 var хотел_играть=false, пуск_сделан='';
 var MSG='Видео временно недоступно. Попробуйте другую озвучку или вернитесь позже.';
 var LABELS={idle:'',loading:'Подключаем видео',resolving:'Подключаем видео',
  ready:'Видео готово',playing:'Воспроизведение',try_next:'Подключаем видео',
  provider:'Видео временно недоступно',unavailable:'Видео временно недоступно',
  error:'Видео временно недоступно',
  slow:'Видео временно недоступно',nosource:'Видео временно недоступно',
  noaccess:'Видео временно недоступно'};
 var ORIGIN='https://player.cdnvideohub.com';
 function el(){ return host.querySelector('video-player'); }
 function clearPlayTimers(){ playTimers.forEach(clearTimeout); playTimers=[]; }
 function clearTimers(){ timers.forEach(clearTimeout); timers=[]; clearPlayTimers(); if(seen){clearInterval(seen);seen=null;} }
 /* Запас, если `play()` отклонён политикой автозапуска: нажать кнопку
    пуска САМОГО провайдера. Ищется по его разметке в теневом дереве; не
    найдена — ничего не делаем и ничего не обещаем. */
 function нажать_пуск(root){
  try{
   var корни=[root], i=0;
   while(i<корни.length){
    var r=корни[i++]; if(!r) continue;
    var b=r.querySelector('.playButton,[aria-label="Смотреть"],[aria-label="Play"]');
    if(b){ b.click(); return true; }
    var все=r.querySelectorAll('*');
    for(var j=0;j<все.length;j++){ if(все[j].shadowRoot) корни.push(все[j].shadowRoot); }
   }
  }catch(e){}
  return false;
 }
 function armPlayTimers(myGen, myAttempt){
  clearPlayTimers();
  playTimers.push(setTimeout(function(){
   if(myGen!==generation || myAttempt!==attempt || playing || adActive) return;
   nextOrFail('timeout-no-playing');
  },25000));
  playTimers.push(setTimeout(function(){
   if(myGen!==generation || myAttempt!==attempt || playing || adActive) return;
   if(!отказ) state('provider', MSG, '');
  },35000));
 }
 function hideOverlay(){
  if(!st) return;
  st.hidden=true;
  st.setAttribute('hidden','');
  st.setAttribute('aria-hidden','true');
  st.style.setProperty('display','none','important');
 }
 function showOverlay(t,p){
  if(!st) return;
  st.hidden=false;
  st.removeAttribute('hidden');
  st.setAttribute('aria-hidden','false');
  st.style.removeProperty('display');
  st.innerHTML='<b></b><p></p>';
  st.firstChild.textContent=t||MSG;
  st.lastChild.textContent=p||'';
 }
 function setLabel(k){ if(label) label.textContent=LABELS[k]||''; }
 function state(k,t,p){
  if(playing && (k==='provider'||k==='unavailable'||k==='error'||k==='slow'||k==='nosource')) return;
  if(отказ && (k==='ready'||k==='playing'||k==='ok'||k==='resolving'||k==='loading')) return;
  if(k==='provider'||k==='unavailable'||k==='error'||k==='slow'||k==='nosource'||k==='noaccess'){
   отказ=true; clearTimers();
  }
  f.setAttribute('data-state',k==='ok'?'playing':k);
  setLabel(k==='ok'?'playing':k);
  var node=el();
  if(k==='resolving'||k==='loading'||k==='ready'||k==='playing'||k==='ok'||k==='try_next'||k==='idle'){
   hideOverlay();
   if(node) node.hidden=false;
   if(k==='playing'||k==='ok'){
    playing=true; отказ=false;
    f.setAttribute('data-state','playing'); setLabel('playing');
    hideOverlay(); clearTimers();
   }
   return;
  }
  if(node) node.hidden=true;
  showOverlay(t||MSG, p||'');
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
  activeSource=null;
 }
 function nextOrFail(reason){
  try{ if(window.__sfGoalOnce){ window.__sfGoalOnce('player_error'); } }catch(e){}
  if(playing) return;
  if(idx+1<cands.length && (idx+1)<=maxFallback){
   state('try_next');
   mountAt(idx+1);
   return;
  }
  state('provider', MSG, '');
 }
 function mountAt(i){
  idx=i;
  var c=cands[i]; if(!c) return;
  var prev=el();
  if(prev) snapshot(prev);
  destroy();
  playing=false; отказ=false; lastPos=0; readyAt=0; requested=false; adActive=false;
  generation += 1;
  attempt = generation;
  var myGen=generation, myAttempt=attempt;
  var n=document.createElement('video-player');
  Object.keys(baseAttrs).forEach(function(a){ n.setAttribute(a, baseAttrs[a]); });
  n.setAttribute('data-title-id', c.id||'');
  n.setAttribute('data-aggregator', c.aggregator||'');
  n.setAttribute('is-show-banner', 'false');
  n.setAttribute('data-attempt', String(myAttempt));
  host.appendChild(n);
  activeSource={gen:myGen, attempt:myAttempt, id:c.id||'', agg:c.aggregator||''};
  bind(n, myGen, myAttempt);
 }
 function confirmPlaying(evName, pos, myGen, myAttempt){
  if(myGen!==generation || myAttempt!==attempt) return;
  window.__zonaPlayerPlaying={
   generation:myGen, attempt:myAttempt, event:evName||'playing',
   pos:pos||0, at:Date.now()
  };
  playing=true; отказ=false;
  clearTimers();
  state('playing');
  hideOverlay();
 }
 function frameWindow(){
  var n=el(); if(!n||!n.shadowRoot) return null;
  var fr=n.shadowRoot.querySelector('iframe');
  return fr ? fr.contentWindow : null;
 }
 function onProviderMsg(ev){
  if(!ev || ev.origin!==ORIGIN) return;
  var myGen=generation, myAttempt=attempt;
  if(!activeSource || activeSource.gen!==myGen || activeSource.attempt!==myAttempt) return;
  var win=frameWindow();
  if(win && ev.source && ev.source!==win) return;
  var payload=ev.data, type='', data=null;
  try{
   if(typeof payload==='string') payload=JSON.parse(payload);
   type=payload && payload.eventType || '';
   data=payload && payload.data;
  }catch(e){ return; }
  if(!type) return;
  if(type==='requestPlay'){
   requested=true;
   /* «Площадка запросила показ» — та же формулировка, что у канона и Yummy,
      чтобы одна цель не значила на разных витринах разное. */
   try{ if(window.__sfGoalOnce){ window.__sfGoalOnce('player_start'); } }catch(e){}
   if(!playing && !adActive) armPlayTimers(myGen, myAttempt);
   return;
  }
  if(type==='adStart' || (type==='rollState' && data && data.state==='start')){
   adActive=true; clearPlayTimers();
   return;
  }
  if(type==='adComplete' || type==='adClosed' || type==='adSkipped' || type==='adError'
     || (type==='rollState' && data && data.state && data.state!=='start')){
   if(adActive){ adActive=false; if(requested && !playing) armPlayTimers(myGen, myAttempt); }
   return;
  }
  if(type==='statechange' && data==='ready'){
   if(!playing && !отказ){ readyAt=Date.now(); state('ready');
    try{ if(window.__sfGoalOnce){ window.__sfGoalOnce('player_ready'); } }catch(e){} }
   return;
  }
  if(type==='timeupdate' && data && typeof data.position==='number'){
   lastPos=data.position;
   if(data.position>=3) confirmPlaying('pm.timeupdate3', data.position, myGen, myAttempt);
   return;
  }
  if(type==='statechange' && data==='playing'){
   if(lastPos>=3) confirmPlaying('pm.statechange.playing', lastPos, myGen, myAttempt);
   else if(!playing && !отказ){ readyAt=Date.now(); state('ready');
    try{ if(window.__sfGoalOnce){ window.__sfGoalOnce('player_ready'); } }catch(e){} }
   return;
  }
  if(type==='play'||type==='started'){
   if(lastPos>=3) confirmPlaying('pm.'+type, lastPos, myGen, myAttempt);
   else if(!playing && !отказ){ readyAt=Date.now(); state('ready');
    try{ if(window.__sfGoalOnce){ window.__sfGoalOnce('player_ready'); } }catch(e){} }
  }
 }
 window.addEventListener('message', onProviderMsg);
 function bind(node, myGen, myAttempt){
  if(!node) return;
  snapshot(node);
  state('resolving');
  hideOverlay();
  node.hidden=false;
  node.addEventListener('noData', function(){
   if(myGen!==generation || myAttempt!==attempt || playing) return;
   nextOrFail('noData');
  });
  node.addEventListener('error', function(){
   if(myGen!==generation || myAttempt!==attempt || playing) return;
   nextOrFail('error');
  });
  clearTimers();
  seen=setInterval(function(){
   if(myGen!==generation || myAttempt!==attempt || playing) return;
   var root=node.shadowRoot; if(!root) return;
   var v=root.querySelector('video');
   /* Донести желание зрителя до появившегося медиа. Условия узкие намеренно:
      только если зритель нажал, не во время рекламного ролика, только пока
      ничего не играло и только один раз на эту попытку — иначе мы боролись бы
      с тем, кто поставил на паузу сам. */
   var метка=myGen+'/'+myAttempt;
   if(v && хотел_играть && !adActive && пуск_сделан!==метка
      && v.paused && (v.currentTime||0)<0.25){
    пуск_сделан=метка;
    try{
     var обещание=v.play();
     if(обещание && обещание.catch){ обещание.catch(function(){ нажать_пуск(root); }); }
    }catch(e){ нажать_пуск(root); }
   }
   if(v && !v.__zonaBound){
    v.__zonaBound=true;
    v.addEventListener('timeupdate', function(){
     if(myGen!==generation || myAttempt!==attempt) return;
     if(v.currentTime>=3) confirmPlaying('video.timeupdate3', v.currentTime, myGen, myAttempt);
    });
   }
   if(v && !v.paused && v.currentTime>=3) confirmPlaying('video.poll', v.currentTime, myGen, myAttempt);
  },400);
  timers.push(setTimeout(function(){
   if(myGen!==generation || myAttempt!==attempt || playing || readyAt) return;
   nextOrFail('timeout-no-ready');
  },10000));
  // Таймеры «нет воспроизведения» взводятся по requestPlay (armPlayTimers),
  // а не при монтировании: см. src/player_watchdog.py витрины.
 }
 /* Нажатие по рамке плеера — это и есть «хочу смотреть». Слушатель стоит
    на рамке, а не на документе: щелчок по описанию или по меню желанием
    смотреть не является. `capture` нужен, чтобы жест был записан и когда
    его съедает разметка провайдера внутри. */
 f.addEventListener('click', function(){ хотел_играть=true; }, true);
 f.addEventListener('touchstart', function(){ хотел_играть=true; },
                    {capture:true, passive:true});
 var first=el();
 if(first){
  if(!cands.length){
   cands=[{aggregator:first.getAttribute('data-aggregator')||'', id:first.getAttribute('data-title-id')||''}];
  }
  generation=1; attempt=1;
  activeSource={gen:1, attempt:1,
   id:first.getAttribute('data-title-id')||'',
   agg:first.getAttribute('data-aggregator')||''};
  first.setAttribute('data-attempt','1');
  bind(first, 1, 1);
 }
 var s=document.querySelector('[data-player-script]');
 if(s){ s.addEventListener('error',function(){
  if(!playing) state('error', MSG, '');}); }
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
    or (_ПОСТЕР_ENV not in ("0", "false", "no")
        and СЕМЕЙСТВО in ("animedia", "zona"))
)
ВНЕШНИЙ_ПОСТЕР = "https://poster.cdnvideohub.com/"
ПОСТЕР_HOSTS = frozenset({"poster.cdnvideohub.com"})
ПОСТЕР_MAX_BYTES = 2_500_000
_ПОСТЕР_КЭШ: dict[str | tuple[str, int], tuple[float, bytes, str]] = {}
_ПОСТЕР_НЕГАТИВ: dict[str, float] = {}


#: Закрытый набор ширин /poster/<ключ>?w=N: прочие w — как без параметра,
#: чтобы память и адреса не размножались. Вариант уже предела берётся из
#: обложки предела, шире — из исходника; увеличения нет никогда.
ПОСТЕР_ШИРИНЫ = (160, 240, 320, 720)
#: Форма обложки: самое широкое окно показа — 0,83, поэтому кадр шире порога
#: обрезается по центру до цели. Срезается только то, что `object-fit:cover`
#: и так не показывает.
ПОСТЕР_ПОРОГ_ФОРМЫ = 0.94
ПОСТЕР_ЦЕЛЬ_ФОРМЫ = 0.85
#: Сколько помнить отказ источника, прежде чем спрашивать снова.
ПОСТЕР_НЕГАТИВ_СЕК = 300


def _предел_постера(значение: str | None, умолчание: int = 480) -> int:
    """Предел ширины из окружения. Мусор не меняет витрину молча."""
    текст = (значение or "").strip()
    if текст.isdigit() and 160 <= int(текст) <= 2000:
        return int(текст)
    return умолчание


ПОСТЕР_МАКС_ШИРИНА = _предел_постера(os.environ.get("LORDS_POSTER_MAX_WIDTH"))

#: `sizes` по блокам: измеренный максимум отрисовки с запасом вверх. Без него
#: браузер считает показ равным ширине окна и берёт самый крупный файл.
ПОКАЗ_ПОЛКА = "(min-width:1024px) 240px, (min-width:640px) 200px, 164px"
ПОКАЗ_СЕТКА = "(min-width:1200px) 180px, (min-width:640px) 200px, 164px"
ПОКАЗ_ОБЛОЖКА = "(min-width:1024px) 320px, (min-width:640px) 280px, 240px"

#: Настоящая ширина обложки по ключу: заполняется, когда витрина САМА
#: разбирает файл (в `_уменьшить_постер`). Нужна разметке: объявить кандидата
#: шире, чем есть на самом деле, — значит пообещать браузеру пиксели, которых
#: нет, и он растянет то, что получил.
_ПОСТЕР_ШИРИНА_ФАЙЛА: dict[str, int] = {}


def _запомнить_ширину(ключ: str, ширина: int) -> None:
    """Запомнить фактическую ширину исходника; ноль и мусор не запоминаются."""
    if ключ and isinstance(ширина, int) and ширина > 0:
        _ПОСТЕР_ШИРИНА_ФАЙЛА[ключ] = ширина
        if len(_ПОСТЕР_ШИРИНА_ФАЙЛА) > 4096:
            for лишний in list(_ПОСТЕР_ШИРИНА_ФАЙЛА)[:1024]:
                _ПОСТЕР_ШИРИНА_ФАЙЛА.pop(лишний, None)



def _уменьшить_постер(данные: bytes, тип: str,
                      ширина: int | None = None) -> tuple[bytes, str]:
    """WebP/JPEG шире предела — до предела тем же форматом; иначе как есть.

    Нет Pillow, ошибка разбора или кодирования, анимация, картинка больше
    4000×6000 или результат не меньше исходника — исходные байты без
    изменений. Витрина обязана отдать обложку и без уменьшения.
    """
    if тип not in ("image/webp", "image/jpeg"):
        return данные, тип
    предел = ширина or ПОСТЕР_МАКС_ШИРИНА
    try:
        import io
        from PIL import Image

        with Image.open(io.BytesIO(данные)) as im:
            if getattr(im, "n_frames", 1) > 1:
                return данные, тип
            w, h = im.size
            if w > 4000 or h > 6000:
                return данные, тип
            обрезать = w > h * ПОСТЕР_ПОРОГ_ФОРМЫ
            if not обрезать and w <= предел:
                return данные, тип
            icc = im.info.get("icc_profile")
            im.load()
            мал = im
            if обрезать:
                узкая = max(1, round(h * ПОСТЕР_ЦЕЛЬ_ФОРМЫ))
                слева = (w - узкая) // 2
                мал = im.crop((слева, 0, слева + узкая, h))
                w = узкая
            if w > предел:
                мал = мал.resize((предел, max(1, round(h * предел / w))),
                                 Image.LANCZOS)
        опции: dict = {"icc_profile": icc} if icc else {}
        буф = io.BytesIO()
        if тип == "image/webp":
            if мал.mode not in ("RGB", "RGBA"):
                мал = мал.convert("RGBA" if "A" in мал.getbands() else "RGB")
            мал.save(буф, "WEBP", quality=85, method=4, **опции)
        else:
            if мал.mode not in ("RGB", "L", "CMYK"):
                мал = мал.convert("RGB")
            мал.save(буф, "JPEG", quality=85, optimize=True, progressive=True,
                     **опции)
        новые = буф.getvalue()
    except Exception:  # noqa: BLE001 — любая ошибка: отдать источник как есть
        return данные, тип
    if not новые or len(новые) >= len(данные):
        return данные, тип
    return новые, тип


def _ширина_постера(запрос: str) -> int | None:
    """`w` ровно из набора и ровно одним значением; иначе None."""
    if not запрос:
        return None
    значения = parse_qs(запрос).get("w") or []
    if len(значения) != 1 or not значения[0].isdigit():
        return None
    w = int(значения[0])
    return w if w in ПОСТЕР_ШИРИНЫ else None


def _набор_постера(адрес: str | None, показ_css: int | str | None) -> str:
    """`srcset`/`sizes` для своего адреса обложки; для чужого — пусто.

    Кандидаты шире предела добавляются только когда показ больше 240 px:
    при двойной плотности ему нужен файл шире предела.
    """
    if not показ_css or not адрес or not str(адрес).startswith("/poster/"):
        return ""
    а = html.escape(str(адрес))
    условия = isinstance(показ_css, str)
    шире = условия and any(
        часть.strip().split()[-1].endswith("px")
        and int(часть.strip().split()[-1][:-2]) > 240
        for часть in показ_css.split(","))
    # Фактическая ширина файла, если витрина уже его разбирала. Объявить
    # кандидата шире, чем есть, — значит пообещать пиксели, которых нет: при
    # тройной плотности браузер выбирает «480w», получает 300 и растягивает.
    ключ = str(адрес).rsplit("/", 1)[-1].split("?")[0]
    настоящая = _ПОСТЕР_ШИРИНА_ФАЙЛА.get(ключ, 0)
    предел_базы = min(ПОСТЕР_МАКС_ШИРИНА, настоящая) if настоящая else ПОСТЕР_МАКС_ШИРИНА
    узкие = [w for w in ПОСТЕР_ШИРИНЫ
             if w < предел_базы and (not настоящая or w < настоящая)]
    широкие = [w for w in ПОСТЕР_ШИРИНЫ
               if шире and w > ПОСТЕР_МАКС_ШИРИНА
               and (not настоящая or w <= настоящая)]
    кандидаты = ", ".join(
        [f"{а}?w={w} {w}w" for w in узкие]
        + [f"{а} {предел_базы}w"]
        + [f"{а}?w={w} {w}w" for w in широкие])
    sizes = html.escape(показ_css) if условия else f"{показ_css}px"
    return f' srcset="{кандидаты}" sizes="{sizes}"'


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


def отдать_постер(хвост: str, запрос: str = "") -> tuple[int, bytes, str]:
    """First-party proxy: allowlist host, timeouts, size/MIME limits, caches."""
    import http.client
    import time

    ключ = _постер_безопасный_ключ(хвост)
    if not ключ:
        return 404, b"", "text/plain"
    сейчас = time.time()
    if ключ in _ПОСТЕР_НЕГАТИВ and сейчас - _ПОСТЕР_НЕГАТИВ[ключ] < 300:
        return 404, b"", "text/plain"
    ширина = _ширина_постера(запрос)
    if ширина:
        вариант = _ПОСТЕР_КЭШ.get((ключ, ширина))
        if вариант and сейчас - вариант[0] < 86_400:
            return 200, вариант[1], вариант[2]
    кэш = _ПОСТЕР_КЭШ.get(ключ)
    шире = bool(ширина) and ширина > ПОСТЕР_МАКС_ШИРИНА
    if кэш and сейчас - кэш[0] < 86_400 and not шире:
        if not ширина:
            return 200, кэш[1], кэш[2]
        данные, тип = _уменьшить_постер(кэш[1], кэш[2], ширина)
        _ПОСТЕР_КЭШ[(ключ, ширина)] = (кэш[0], данные, тип)
        return 200, данные, тип
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
        исходник, тип_исходника = данные, тип
        # Ширина исходника нужна разметке: без неё srcset объявляет кандидата
        # шире, чем файл, и браузер растягивает то, что получил (замер линии
        # SEO 27.10 на плотности 3: обещали 480, отдали 300).
        try:
            import io as _io

            from PIL import Image as _Image

            with _Image.open(_io.BytesIO(исходник)) as _им:
                _запомнить_ширину(ключ, int(_им.size[0]))
        except Exception:  # noqa: BLE001 — без Pillow разметка остаётся прежней
            pass
        данные, тип = _уменьшить_постер(данные, тип)
        if not (шире and кэш and сейчас - кэш[0] < 86_400):
            _ПОСТЕР_КЭШ[ключ] = (сейчас, данные, тип)
        if шире:
            данные, тип = _уменьшить_постер(исходник, тип_исходника, ширина)
            _ПОСТЕР_КЭШ[(ключ, ширина)] = (сейчас, данные, тип)
        elif ширина:
            данные, тип = _уменьшить_постер(данные, тип, ширина)
            _ПОСТЕР_КЭШ[(ключ, ширина)] = (сейчас, данные, тип)
        if len(_ПОСТЕР_КЭШ) > 512:
            # Простой LRU-суррогат: выкинуть самые старые четверть.
            устаревшие = sorted(_ПОСТЕР_КЭШ.items(), key=lambda п: п[1][0])[:128]
            for у in устаревшие:
                _ПОСТЕР_КЭШ.pop(у[0], None)
        return 200, данные, тип
    except OSError:
        _ПОСТЕР_НЕГАТИВ[ключ] = сейчас
        return 504, b"", "text/plain"


_ПОСТЕР_КЭШ: dict[str | tuple[str, int], tuple[float, bytes, str]] = {}
_ПОСТЕР_НЕГАТИВ: dict[str, float] = {}


def _адрес_постера(адрес: str | None) -> str | None:
    """Адрес постера: свой путь либо адрес источника, без третьего варианта."""
    if not адрес:
        return адрес
    if ПОСТЕРЫ_СВОИМ_АДРЕСОМ and адрес.startswith(ВНЕШНИЙ_ПОСТЕР):
        return "/poster/" + адрес[len(ВНЕШНИЙ_ПОСТЕР):]
    return адрес


def заглушка_постера(запись: dict, класс_заглушки: str, класс_картинки: str,
                     ширина: int = 300, высота: int = 450,
                     срочно: str | None = None) -> str:
    """Постер с заглушкой ПОД ним, а не вместо него.

    Заглушка рисуется всегда и лежит слоем ниже изображения. Alt у значимого
    постера — название тайтла; декоративная заглушка без изображения не
    объявляет зрителю внутреннюю диагностику («постер не открылся»).

    `срочно` — режим загрузки (T334, MOD-149; перенос T333 animedia.icu):
    "high" — сразу и с высоким приоритетом, "eager" — сразу, приоритет
    выбирает браузер, иначе лениво; с явным режимом — decoding="async".
    None — разметка до T334 байт в байт: её отдают Lords и Animedia этого
    ядра. Низкий приоритет (fetchpriority low) не ставится: на space он
    ставил превью в очередь за крупными постерами (7,9 с).
    """
    название = (запись.get("title") or "").strip() or "Без названия"
    первая = html.escape(название[:1].upper())
    постер = _адрес_постера(запись.get("poster"))
    заглушка = (f'<span class="{класс_заглушки}" aria-hidden="true">'
                f"<b>{первая}</b></span>")
    if not постер:
        return заглушка
    if срочно is None:
        картинка = (
            f'<img class="{класс_картинки}" src="{html.escape(постер)}" '
            f'alt="{html.escape(название)}" loading="lazy" width="{ширина}" '
            f'height="{высота}" data-poster>')
        return заглушка + картинка
    загрузка = {"high": 'loading="eager" fetchpriority="high"',
                "eager": 'loading="eager"'}.get(срочно, 'loading="lazy"')
    картинка = (
        f'<img class="{класс_картинки}" src="{html.escape(постер)}" '
        f'alt="{html.escape(название)}" {загрузка} decoding="async" '
        f'width="{ширина}" height="{высота}" data-poster>')
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
    # Состояние краёв. Считается от фактической прокрутки, поэтому одинаково
    # верно после кнопки, свайпа, колеса и клавиатуры: отдельный обработчик на
    # каждый способ не нужен. Кнопка, которая нажимается и ничего не делает,
    # неотличима от поломки — поэтому на краю она именно disabled.
    "(function(){function края(v){"
    "var rl=v.closest('.zrl');if(!rl)return;"
    'var p=rl.querySelector(\'[data-rl="prev"]\'),'
    'n=rl.querySelector(\'[data-rl="next"]\');'
    "var max=v.scrollWidth-v.clientWidth;"
    "if(p)p.disabled=v.scrollLeft<=1;"
    "if(n)n.disabled=max<=1||v.scrollLeft>=max-1;}"
    "function связать(){[].forEach.call(document.querySelectorAll('.zrl__vp'),"
    "function(v){края(v);"
    "v.addEventListener('scroll',function(){края(v)},{passive:true});});}"
    "if(document.readyState==='loading')"
    "document.addEventListener('DOMContentLoaded',связать);else связать();"
    "window.addEventListener('resize',function(){"
    "[].forEach.call(document.querySelectorAll('.zrl__vp'),края)});})();"
)

#: Только Animedia: на узком экране пункты меню открываются кнопкой.
#: Escape и повторный клик закрывают; focus возвращается на кнопку;
#: body scroll блокируется, пока меню открыто.
СКРИПТ_АНИМЕДИА_ШАПКА = (
    "(function(){"
    "function close(nav,btn){if(!nav||!btn)return;nav.classList.remove('is-open');"
    "btn.setAttribute('aria-expanded','false');document.body.style.overflow='';"
    "try{btn.focus()}catch(e){}}"
    "document.addEventListener('click',function(e){"
    "var b=e.target.closest('[data-nav-toggle]');"
    "var n=document.getElementById('zhd-nav');if(!n)return;"
    "if(b){var open=n.classList.toggle('is-open');"
    "b.setAttribute('aria-expanded',open?'true':'false');"
    "document.body.style.overflow=open?'hidden':'';return}"
    "if(n.classList.contains('is-open')&&!e.target.closest('.zhd')){"
    "close(n,document.querySelector('[data-nav-toggle]'));}"
    "});"
    "document.addEventListener('keydown',function(e){"
    "if(e.key!=='Escape')return;"
    "var n=document.getElementById('zhd-nav');"
    "if(n&&n.classList.contains('is-open'))"
    "close(n,document.querySelector('[data-nav-toggle]'));"
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

#: Zona B01: drawer on #zhd-nav + empty-search forbid + basic focus cycle.
#: Тема выставляется ДО первой отрисовки. Скрипт стоит в `<head>` перед
#: стилями и работает синхронно: если решать тему после загрузки, посетитель
#: успевает увидеть вспышку чужой темы — сначала тёмную страницу, потом
#: светлую. Отсюда же и системная настройка: при первом визите, когда
#: сохранённого выбора ещё нет, берётся `prefers-color-scheme`, и выбор
#: проставляется явно — дальше он уже не зависит от системы.
#:
#: Всё обёрнуто в try: в приватном режиме и при запрете хранилища сам доступ
#: к `localStorage` бросает исключение, и незащищённый скрипт оставил бы
#: страницу вовсе без темы.
СКРИПТ_ТЕМЫ = (
    "(function(){try{var k='zona-theme',r=document.documentElement,s=null;"
    "try{s=localStorage.getItem(k)}catch(e){}"
    "if(s!=='light'&&s!=='dark'){s=(window.matchMedia&&"
    "window.matchMedia('(prefers-color-scheme: light)').matches)?'light':'dark';}"
    "r.setAttribute('data-theme',s);}catch(e){"
    "document.documentElement.setAttribute('data-theme','dark');}})();"
)

#: Переключатель. Состояние держит атрибут на `<html>`, а не класс на теле:
#: тот же атрибут ставит головной скрипт, поэтому между ними нет расхождения.
#: Подпись меняется на действие, которое кнопка выполнит, — «Светлая», когда
#: включена тёмная. Нажатие сохраняется, поэтому выбор переживает переходы и
#: перезагрузку.
СКРИПТ_ПЕРЕКЛЮЧАТЕЛЯ_ТЕМЫ = (
    "(function(){var k='zona-theme';"
    "function подпись(n){var s=document.querySelectorAll('[data-theme-toggle]');"
    "[].forEach.call(s,function(b){"
    "b.setAttribute('aria-pressed',n==='light'?'true':'false');"
    "b.setAttribute('aria-label',n==='light'?'Включить тёмную тему':'Включить светлую тему');"
    "var l=b.querySelector('[data-theme-label]');"
    "if(l)l.textContent=n==='light'?'Тёмная':'Светлая';"
    "var i=b.querySelector('[data-theme-icon]');"
    "if(i)i.textContent=n==='light'?'\u263D':'\u2600';});}"
    "document.addEventListener('click',function(e){"
    "var b=e.target.closest&&e.target.closest('[data-theme-toggle]');if(!b)return;"
    "e.preventDefault();var r=document.documentElement;"
    "var n=r.getAttribute('data-theme')==='light'?'dark':'light';"
    "r.setAttribute('data-theme',n);"
    "try{localStorage.setItem(k,n)}catch(e2){}подпись(n);});"
    "подпись(document.documentElement.getAttribute('data-theme')||'dark');})();"
)

СКРИПТ_ЗОНА_ШАПКА = (
    "(function(){"
    "function allToggles(){return document.querySelectorAll('[data-nav-toggle]');}"
    "function setExpanded(open){allToggles().forEach(function(b){b.setAttribute('aria-expanded',open?'true':'false');});}"
    "function close(nav,btn){if(!nav)return;nav.classList.remove('is-open');"
    "setExpanded(false);document.body.classList.remove('nav-lock');"
    "document.body.style.overflow='';"
    "var back=btn||document.querySelector('[data-nav-toggle]');"
    "try{if(back)back.focus()}catch(e){}}"
    "function trap(e,nav){"
    "if(e.key!=='Tab'||!nav.classList.contains('is-open'))return;"
    "var f=[].slice.call(nav.querySelectorAll('a,button,input')).filter(function(el){return el.offsetParent!==null;});"
    "if(!f.length)return;"
    "var first=f[0],last=f[f.length-1];"
    "if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}"
    "else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}"
    "}"
    "document.addEventListener('click',function(e){"
    "var b=e.target.closest('[data-nav-toggle]');"
    "var n=document.getElementById('zhd-nav');if(!n)return;"
    "if(b){var open=!n.classList.contains('is-open');"
    "n.classList.toggle('is-open',open);setExpanded(open);"
    "document.body.classList.toggle('nav-lock',open);"
    "document.body.style.overflow=open?'hidden':'';"
    "if(open){var fid=b.getAttribute('data-focus-search');"
    "var focusEl=fid?document.getElementById(fid):n.querySelector('a');"
    "if(focusEl)try{focusEl.focus()}catch(err){}}return}"
    "if(n.classList.contains('is-open')&&!e.target.closest('.zhd')){"
    "close(n,document.querySelector('[data-nav-toggle]'));}"
    "});"
    "document.addEventListener('keydown',function(e){"
    "var n=document.getElementById('zhd-nav');"
    "if(!n)return;"
    "if(e.key==='Escape'&&n.classList.contains('is-open'))"
    "close(n,document.querySelector('[data-nav-toggle]'));"
    "trap(e,n);"
    "});"
    "document.addEventListener('submit',function(e){"
    "var f=e.target;if(!f||f.getAttribute('role')!=='search')return;"
    "var inp=f.querySelector('input[name=q]');if(!inp)return;"
    "var v=(inp.value||'').replace(/^\\s+|\\s+$/g,'').replace(/\\u00a0/g,' ');"
    "inp.value=v;"
    "if(!v){e.preventDefault();inp.focus();}"
    "});"
    "})();"
)


def _склеить(части) -> str:
    return "".join(ч for ч in части if ч)


def _число(значение) -> str:
    """Visual rating: one decimal. Raw precision is not shown in UI."""
    try:
        ч = float(значение)
    except (TypeError, ValueError):
        return ""
    if ч <= 0:
        return ""
    return f"{ч:.1f}"


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



def _контакт_подвала() -> str:
    """Строка обратной связи для общего подвала.

    Адрес берётся из окружения, куда его кладёт `run.py` из `config/site.json`
    (ключ `contact_email`). Пустое значение — не повод подставить умолчание:
    выдуманный адрес хуже отсутствующего, потому что письма по нему уходят в
    никуда и никто об этом не узнаёт.

    Ссылка настоящая `mailto:`, и сам адрес остаётся текстом — его копируют
    выделением куда чаще, чем нажимают. `overflow-wrap` в стиле рядом: длинный
    адрес обязан переноситься, а не раздвигать страницу на телефоне.
    """
    import os as _os
    адрес = str(_os.environ.get("SITE_CONTACT_EMAIL") or "").strip()
    if not адрес or "@" not in адрес or " " in адрес:
        return ""
    видимый = html.escape(адрес)
    return (f'<span class="sf-contact">Обратная связь: '
            f'<a href="mailto:{видимый}">{видимый}</a></span>')

class Вид:
    #: Работают ли разделы по категориям (Zona) или по полю `kind` (остальные).
    #: Объявлено на базовом виде, чтобы разметка не спрашивала про семейство.
    КАТЕГОРИЙНЫЕ_РАЗДЕЛЫ = (СЕМЕЙСТВО == "zona"
                            and КАТЕГОРИИ_КАТАЛОГА is not None)

    """Общая механика семейства: данные, адреса, разметка Schema.

    Здесь живёт всё, что от оформления не зависит: что считается сезоном,
    какой адрес у серии, что попадает в хлебные крошки и в `ld+json`. Различие
    семейств — в наследниках, и только в разметке.
    """

    кл_состояния = "pl__state"

    #: Опубликованные правки редактора. Ставится фабрикой вида на запрос;
    #: None означает «правок нет», и страница тогда показывает ровно то, что
    #: сообщил источник.
    правки = None

    def __init__(self, семейство: dict, данные: "Данные", подробности: Подробности,
                 индекс: dict, имя_витрины: str):
        self.се = семейство
        self.д = данные
        self.п = подробности
        self.индекс = индекс
        self.имя = имя_витрины
        self.хост = ""
        #: Может ли накладка сообщества что-нибудь добавить. Спрашивается один
        #: раз на отрисовку, потому что сам вопрос стоит два обращения к
        #: файловой системе, а `деталь` зовётся по разу на запись отбора.
        self._накладка_возможна = (
            СООБЩЕСТВО is not None and СООБЩЕСТВО.проекция_доступна())

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
        найдено = self.индекс["slug"].get(slug)
        if найдено is None or self.правки is None or not self.правки.есть:
            return найдено
        return self.правки.наложить_на_запись(найдено)

    def деталь(self, slug: str) -> dict:
        """Подробности записи с проекцией оценок сообщества поверх них.

        Проекция накладывается утверждённым модулем и только из своего
        хранилища сайта. Когда хранилища нет, возвращаются исходные
        подробности: накладка обязана быть дополнением, а не условием.

        МОЖЕТ ли накладка что-нибудь добавить, решено один раз при создании
        вида. Раньше это решалось внутри `дополнить_деталь`, то есть на каждом
        вызове, а вызовов здесь по одному на запись отбора полок. Измерено
        A/B на выпуске 0fb857b26f85 (деревья отличались только наличием
        `community_bridge.py`): главная 1.84 / 1.76 / 1.89 с против
        0.97 / 1.04 / 1.04 с при неизменных карточке (0.59 с) и разделе
        (0.25 с), где вызов один. Сам вызов — 22.1 мкс, из них 12.7 мкс на два
        `is_file()`.

        Сначала я попробовал запоминать подробности на отрисовку — и замер
        показал, что это не помогает вовсе: отбор спрашивает РАЗНЫЕ записи,
        повторов почти нет. Правка откачена, осталась та, что подтверждена
        измерением.

        Найдено соседней сессией на своей витрине, где отбор идёт по всему
        каталогу и та же надбавка стоила 9.3 с.
        """
        сырое = self.п.get(slug)
        if сырое and self.правки is not None and self.правки.есть:
            # Правка накладывается ДО проекции сообщества: редактор правит
            # текст поставщика, а проекция добавляет оценки посетителей.
            # Обратный порядок означал бы, что правка стирает проекцию.
            сырое = self.правки.наложить_на_деталь(сырое, slug)
        if not self._накладка_возможна or not сырое:
            return сырое
        return СООБЩЕСТВО.дополнить_деталь(сырое)

    def похожие(self, запись: dict, деталь: dict, сколько: int = 12) -> list:
        """Быстрая версия _похожие_полные (T030): тот же результат."""
        return _похожие_быстро(self, запись, деталь, сколько)

    def _похожие_полные(self, запись: dict, деталь: dict, сколько: int = 12) -> list:
        """Same kind required; then genre overlap, country, year proximity, rating.

        After score order: stable-sort so playable titles precede non-playable
        (policy playable_preferred_with_explicit_nonplayable_state_v1). Caller
        records the policy via a data attribute on the related section.
        """
        текущий = запись["slug"]
        kind = запись.get("kind")
        жанры = set(деталь.get("genre_codes") or [])
        if not жанры:
            жанры = {нормализовать(транслит(g)) for g in (деталь.get("genres") or []) if g}
        страны = set(деталь.get("countries") or [])
        year = запись.get("year") or 0
        rating = float(запись.get("_rating") or 0.0)
        scored = []
        for сосед in self.д.items:
            if сосед["slug"] == текущий:
                continue
            if сосед.get("kind") != kind:
                continue
            д = self.п.get(сосед["slug"]) or {}
            g2 = set(д.get("genre_codes") or [])
            if not g2:
                g2 = {код_жанра(g) for g in (д.get("genres") or []) if g}
            overlap = len(жанры & g2)
            c2 = set(д.get("countries") or [])
            country_hit = 1 if (страны & c2) else 0
            y2 = сосед.get("year") or 0
            year_prox = -abs(int(year) - int(y2)) if year and y2 else -9999
            r2 = float(сосед.get("_rating") or 0.0)
            scored.append((overlap, country_hit, year_prox, r2, сосед.get("_n") or "",
                           сосед["slug"], сосед))
        scored.sort(key=lambda t: (t[0], t[1], t[2], t[3], t[4], t[5]), reverse=True)
        # Stable: playable first, preserve score order within each group.
        scored.sort(key=lambda t: 0 if (self.п.get(t[6]["slug"]) or {}).get("playable") is True
                    else 1)
        out = []
        seen_names: set[str] = set()
        cur_norm = _нормализовать_для_дедупа(запись.get("title") or "")
        if cur_norm:
            seen_names.add(cur_norm)
        for t in scored:
            сосед = t[6]
            norm = _нормализовать_для_дедупа(сосед.get("title") or "")
            if norm and norm in seen_names:
                continue
            if norm:
                seen_names.add(norm)
            out.append(сосед)
            if len(out) >= сколько:
                break
        return out

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
        описание_ld = чистое_описание(деталь.get("description"))
        if описание_ld:
            узел["description"] = описание_ld
        if запись.get("year"):
            узел["datePublished"] = str(запись["year"])
        # Служебные метки поставщика — не жанр и в разметке (T113).
        жанры_разметки = [ж for ж in (деталь.get("genres") or [])
                          if str(ж).strip().casefold() not in _ТЕХНИЧЕСКИЕ_ЖАНРЫ]
        if жанры_разметки:
            узел["genre"] = жанры_разметки
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


    #: Подпись раздела-владельца для цепочки крошек подборки — по адресу
    #: раздела, а не придумывается: названия разделов объявлены семейством, и
    #: вторая их копия разошлась бы с навигацией.
    ПОДПИСИ_РАЗДЕЛОВ = {
        "/movies/": "Фильмы", "/series/": "Сериалы",
        "/animation/": "Мультфильмы", "/anime/": "Аниме",
        "/dorama/": "Дорамы", "/new/": "Недавно добавлено",
        "/catalog/": "Каталог",
    }

    def ручная_подборка(self, подборка, состав: dict) -> str:
        """Страница редакционной подборки: состав поимённо и зачем каждая работа.

        Отличие от `коллекция` не в оформлении, а в содержании: там состав
        задаёт фильтр и пояснять нечего, здесь у КАЖДОЙ работы своё пояснение
        редакции, и порядок — её решение.

        Пропавшие работы не подменяются соседними и не исчезают молча: внизу
        стоит строка о том, сколько работ каталог больше не отдаёт. Подмена
        была бы выдуманным фактом — читателю обещали конкретную работу.
        """
        карточки = "".join(
            f'<div class="col__i">{карточка(с["запись"])}'
            f'<p class="col__why">{html.escape(с["работа"].reason)}</p></div>'
            for с in состав.get("works") or [])
        пусто = состав.get("missing") or []
        сетка = (f'<div class="grid col__grid">{карточки}</div>' if карточки else
                 '<div class="empty">Состав этой подборки каталог сейчас не '
                 'отдаёт.</div>')
        потери = ""
        if пусто:
            потери = ('<p class="col__gone">Каталог больше не отдаёт '
                      f'{len(пусто)} из {len(подборка.works)} работ подборки. '
                      'Заменять их похожими мы не станем: подборка собрана '
                      'поимённо.</p>')
        звенья = [("/", self.имя)]
        if подборка.section:
            звенья.append((подборка.section,
                           self.ПОДПИСИ_РАЗДЕЛОВ.get(подборка.section,
                                                     "Каталог")))
        звенья += [("/collections/", "Подборки"), ("", подборка.title)]
        # Дата пересмотра состава — видимая строка, а не поле в файле:
        # промежуточная подборка без неё не отличается от прошлогодней.
        обновлено = ""
        если_дата = getattr(подборка, "updated", "")
        if если_дата:
            обновлено = (f'<p class="col__upd">Состав пересмотрен '
                         f'{html.escape(_дата_анонса(если_дата))}</p>')
        # Справка об источниках — отдельная мелкая строка под вступлением, а
        # не часть его. Вступление отвечает читателю, зачем смотреть; откуда
        # взяты сведения — справка (поручение владельца 27.10). Поля нет —
        # строки нет: пустая справка хуже её отсутствия.
        справка = ""
        если_справка = getattr(подборка, "sources_note", "")
        if если_справка:
            справка = (f'<p class="col__src">'
                       f'{html.escape(если_справка)}</p>')
        тело = (f'<section class="sec sec--coll"><div class="sec__h">'
                f"<h1>{html.escape(подборка.title)}</h1>"
                f'<a href="/collections/">Все подборки →</a></div>'
                f'<p class="claim">{html.escape(подборка.intro)}</p>'
                f"{справка}{обновлено}{сетка}{потери}</section>")
        return self.оболочка(
            тело, f"{подборка.title} — {self.имя}", подборка.canonical_path,
            актив=подборка.section or "/collections/",
            описание=подборка.intro[:300],
            разметка=(self.schema_крошек(звенья),),
            # Цепочка этой страницы помечена: правило прячет повтор названия
            # только здесь и только на узком экране. Крошки общие для всех
            # страниц витрины, и прятать последнее звено везде правка не
            # должна. В JSON-LD цепочка остаётся полной.
            крошки=self.крошки(звенья).replace(
                'class="zcr"', 'class="zcr zcr--coll"', 1))

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

    year = release year only. /new/ uses B13 temporal modes with distinct
    ledgers (premiere vs catalog_added). Modes without a ledger are empty,
    never filled from a neighbour date. Default kind-routes sort by release
    freshness, not title.
    """
    набор = list(данные.items)
    вид = (зпр.get("kind") or [None])[0]
    год = (зпр.get("year") or [None])[0]
    жанр = (зпр.get("genre") or [None])[0]
    страна = (зпр.get("country") or [None])[0]
    сырой_сорт = (зпр.get("sort") or [None])[0]
    # Aliases: date → newest (legacy).
    сорт = {"date": "newest", "new": "newest"}.get(сырой_сорт or "", сырой_сорт)
    неизвестный_фильтр = False
    new_mode = None
    #: Запрошенный режим ленты. Держится отдельно от действующего, потому что
    #: действующий выставляет маршрут, и различать их нужно за пределами отбора.
    сырой_mode = None

    # B13: /new/ temporal modes — ledger per mode, no neighbour-date fill.
    if раздел == "/new":
        доступные = _доступные_режимы_new(данные)
        сырой_mode = (зпр.get("mode") or [None])[0]
        # Legacy sort aliases must not silently equal premiere ledger.
        if not сырой_mode and сорт == "recently_added":
            сырой_mode = NEW_MODE_ADDED
        # Explicit unsupported mode with no ledger → honest empty (not 400),
        # so omitted tabs stay unreachable without inventing a feed.
        if сырой_mode in ("available", "episodes", "provider", "episode"):
            new_mode = сырой_mode
            набор = []
        else:
            new_mode = _нормализовать_режим_new(сырой_mode, доступные)
            if new_mode == NEW_MODE_ADDED:
                # Реестр поступлений, а не реестр дат. Запись из пачки
                # первоначального импорта сюда не попадает: её дата говорит,
                # когда завели каталог, и выдавать её за поступление — значит
                # показывать зрителю старое как новое.
                набор = [з for з in набор if дата_поступления(з)]
            else:
                набор = [з for з in набор if з.get("_premiere_date")]

    if вид:
        if вид in ЗНАЧЕНИЯ_КАТЕГОРИЙ:
            # Раздел по категории. Индекс держит готовые списки, но фильтр по
            # полю записи дешевле пересечения множеств и не зависит от того,
            # успел ли индекс перестроиться после смены снимка.
            набор = [з for з in набор if з.get("_ck") == вид]
        else:
            набор = [з for з in набор if з.get("kind") == вид]
    if год:
        if str(год).isdigit() and 1870 <= int(год) <= 2100:
            набор = [з for з in набор if з.get("year") == int(год)]
        else:
            неизвестный_фильтр = True
            набор = []
    if жанр:
        ключи = {жанр, нормализовать(жанр), нормализовать(транслит(жанр))}
        if ЖАНРЫ_АЛИАСЫ is not None:
            расширенные = set()
            for ключ in list(ключи):
                if ключ:
                    расширенные |= set(ЖАНРЫ_АЛИАСЫ.алиасы_жанра(ключ))
                    расширенные.add(ключ)
            ключи = расширенные
        членство: set = set()
        for ключ in ключи:
            if not ключ:
                continue
            часть = индекс["genre"].get(ключ)
            if часть:
                членство.update(часть)
        if not членство:
            неизвестный_фильтр = True
            набор = []
        else:
            набор = [з for з in набор if з["slug"] in членство]
    if страна:
        страны = индекс.get("country") or {}
        ключ = _канон_страны(страна, страны) or страна
        разрешённые = страны.get(ключ)
        if разрешённые is None:
            неизвестный_фильтр = True
            набор = []
        else:
            членство = set(разрешённые)
            набор = [з for з in набор if з["slug"] in членство]
            страна = ключ

    def _title_key(з: dict) -> tuple:
        return (з.get("_n") or нормализовать(з["title"]), з["slug"])

    def _activity_key(з: dict) -> tuple:
        # Confirmed premiere/activity only — never fall back to ingest date.
        prem = з.get("_premiere_date") or ""
        has = 1 if prem else 0
        return (has, prem, _title_key(з)[0], з["slug"])

    def _release_key(з: dict) -> tuple:
        prem = з.get("_premiere_date") or ""
        year = з.get("year") or 0
        has_prem = 1 if prem else 0
        has_year = 1 if year else 0
        return (has_prem, prem, has_year, int(year) if year else 0,
                _title_key(з)[0], з["slug"])

    def _rating_key(з: dict) -> tuple:
        rating = float(з.get("_rating") or 0.0)
        votes = int(з.get("_votes") or 0)
        # Min votes soft preference: 0 still allowed but sorts after voted.
        has_votes = 1 if votes > 0 else 0
        return (1 if rating > 0 else 0, has_votes, rating, votes,
                _title_key(з)[0], з["slug"])

    # Default sort by route when sort omitted.
    if not сорт:
        if раздел == "/new":
            сорт = "newest"
        elif раздел in ("/movies", "/series", "/animation", "/doramas", "/catalog"):
            сорт = "newest"
        elif раздел == "/collections":
            сорт = "title"
        else:
            сорт = "newest"

    if раздел == "/new":
        if new_mode == NEW_MODE_ADDED:
            набор = sorted(
                набор,
                key=lambda з: (1 if дата_поступления(з) else 0,
                               дата_поступления(з),
                               _title_key(з)[0], з["slug"]),
                reverse=True)
        else:
            набор = sorted(набор, key=_activity_key, reverse=True)
    elif сорт == "newest":
        набор = sorted(набор, key=_release_key, reverse=True)
    elif сорт == "recently_added":
        # Записи первоначального импорта не всплывают наверх «недавно
        # добавленных»: у них нет даты поступления, они сортируются как
        # записи без даты — в конец, а не как самые свежие.
        набор = sorted(
            набор,
            key=lambda з: (1 if дата_поступления(з) else 0,
                           дата_поступления(з),
                           _title_key(з)[0], з["slug"]),
            reverse=True)
    elif сорт == "rating":
        набор = sorted(набор, key=_rating_key, reverse=True)
    elif сорт == "title":
        набор = sorted(набор, key=_title_key)
    elif сорт == "year":
        набор = sorted(
            набор,
            key=lambda з: (1 if з.get("year") else 0, з.get("year") or 0,
                           _title_key(з)[0], з["slug"]),
            reverse=True)
    elif сорт:
        неизвестный_фильтр = True
        набор = []

    выбрано = {"kind": вид, "year": год, "genre": жанр, "country": страна,
               "sort": сорт if сорт not in (None, "") else None}
    if раздел == "/new" and new_mode:
        выбрано["mode"] = new_mode
    if неизвестный_фильтр:
        выбрано["_unknown"] = "1"
    # Какие значения выставил МАРШРУТ, а не читатель. Различие нужно за
    # пределами отбора: канонический адрес страницы складывается из
    # ЗАПРОШЕННОГО, а подразумеваемое значение отдельного адреса не образует.
    # Без этой пометки голый `/catalog/` объявлял каноническим
    # `/catalog/?sort=newest` — адрес, которого нет ни в навигации, ни в карте
    # сайта, то есть страница объявляла дублем саму себя.
    подразумеваемые = [к for к, сырое in (("sort", сырой_сорт),
                                          ("mode", сырой_mode))
                       if выбрано.get(к) and not сырое]
    if подразумеваемые:
        выбрано["_подразумеваемое"] = ",".join(подразумеваемые)
    return набор, выбрано


def запрос_строкой(выбрано: dict, **замена) -> str:
    """Собрать `?k=v` с percent-encoding значений (kind=Фильм → %D0%A4…).

    Значения, которые подставил МАРШРУТ (`_подразумеваемое`: sort, mode), в
    адрес не пишутся, если их не передали явно: 13.10 листалка /movies/
    ссылалась на ?sort=newest&page=N, а это не каноническая страница —
    canonical указывает на ?page=N, и сама каноническая прямых ссылок не
    получала. Переключатель сортировки передаёт sort явно и не меняется.
    """
    поля = dict(выбрано)
    for ключ in str(поля.get("_подразумеваемое") or "").split(","):
        if ключ and ключ not in замена:
            поля.pop(ключ, None)
    поля.update(замена)
    omit_kind = bool(поля.pop("_omit_kind", False))
    if omit_kind:
        поля.pop("kind", None)
    # Default /new/ premiere mode stays on clean /new/ (no ?mode=premiere).
    if поля.get("mode") == NEW_MODE_PREMIERE:
        поля.pop("mode", None)
    пары = [(к, з) for к, з in поля.items()
            if з and not str(к).startswith("_")]
    return ("?" + urlencode(пары, quote_via=quote)) if пары else ""


#: Метки поставщика, которые не жанр для посетителя (раздел витрины, а не тема).
#: «Азиатский контент» — та же метка поставщика, что «западный» (T077, 14.10:
#: ?genre=aziatskiykontent — 200, index и в карте). На Lords — T064.
_ТЕХНИЧЕСКИЕ_ЖАНРЫ = {"западный контент", "азиатский контент"}

_ССЫЛКА_ПОСТАВЩИКА = re.compile(r"«\[([^\[\]«»]*)\]»")
_ПУСТЫЕ_КАВЫЧКИ = re.compile(r"«\s*»")


def чистое_описание(текст: str) -> str:
    """Описание поставщика без служебной разметки (T318 — перенос T317, SEO_KNOWLEDGE_PACK §4 п.2).

    Замер 22.10: «…аниме-сериала «[91 Days]».» — маркер нерешённой ссылки,
    «…аниме-сериала «», включённые…» — имя потеряно.
    «[X]» → «X», содержимое не меняется. Остались пустые кавычки — описания нет:
    недостающее имя не придумывается, работает ветка карточки без описания.
    """
    текст = _ССЫЛКА_ПОСТАВЩИКА.sub(r"«\1»", str(текст or ""))
    if _ПУСТЫЕ_КАВЫЧКИ.search(текст):
        return ""
    return текст


#: Индекс повторяющихся названий на снимок каталога (ключ — id списка записей:
#: перечитанный снимок даёт новый список и новый индекс).
_ПОВТОРЫ_НАЗВАНИЙ: dict = {}


def различимое_название(имя: str, запись: dict, деталь: dict, записи: list) -> str:
    """Название для <title>, различимое среди одноимённых записей каталога.

    Замер 13.10: в каталоге Lords/Zona 3 952 названия повторяются (10 576
    записей) — «Мастер кунг-фу» 2004 и 2012 отдавали одинаковый <title>. Год
    добавляется только при повторе названия; совпал и год — ещё оригинальное
    название, если оно есть и отличается. Ничего сверх полей снимка.
    """
    ключ = id(записи)
    индекс = _ПОВТОРЫ_НАЗВАНИЙ.get(ключ)
    if индекс is None:
        по_имени: dict = {}
        по_имени_году: dict = {}
        for з in записи:
            н = str(з.get("title") or "").strip().lower()
            по_имени[н] = по_имени.get(н, 0) + 1
            по_имени_году[(н, з.get("year"))] = по_имени_году.get((н, з.get("year")), 0) + 1
        индекс = (по_имени, по_имени_году)
        _ПОВТОРЫ_НАЗВАНИЙ.clear()
        _ПОВТОРЫ_НАЗВАНИЙ[ключ] = индекс
    по_имени, по_имени_году = индекс
    н = str(имя or "").strip().lower()
    год = запись.get("year")
    if по_имени.get(н, 0) < 2 or not год:
        return имя
    if по_имени_году.get((н, год), 0) < 2:
        return f"{имя} ({год})"
    оригинал = str((деталь or {}).get("original_name") or "").strip()
    if оригинал and оригинал.lower() != н:
        return f"{имя} ({оригинал}, {год})"
    return f"{имя} ({год})"


def краткое_описание(имя: str, запись: dict, деталь: dict, описание: str, сайт: str) -> str:
    """<meta name="description"> страницы произведения.

    Текст описания обрезается по границе слова (прежде — на 180-м знаке посреди
    слова). Без описания — фраза из фактов каталога: оригинальное название, вид,
    год, страна, жанры. Прежде это было «Имя: Фильм 2025» — одно и то же у
    тысяч карточек без описания (SEO-аудит 2026-10-11). Ничего сверх данных
    каталога не добавляется.
    """
    описание = " ".join(str(описание or "").split())
    if описание:
        if len(описание) <= 180:
            return описание
        срез = описание[:178].rsplit(" ", 1)[0].rstrip(",;:—- ")
        return срез + "…"
    деталь = деталь or {}
    ориг = str(деталь.get("original_name") or "").strip()
    голова = f"«{имя}»" + (f" ({ориг})" if ориг and ориг.casefold() != str(имя).casefold() else "")
    вид = str(запись.get("kind") or "").strip().lower()
    год = str(запись.get("year") or "").strip()
    что = " ".join(x for x in (вид, f"{год} года" if год else "") if x)
    страны = ", ".join(str(с) for с in (деталь.get("countries") or [])[:2])
    жанры = [str(ж) for ж in (деталь.get("genres") or [])
             if str(ж).strip().casefold() not in _ТЕХНИЧЕСКИЕ_ЖАНРЫ][:3]
    части = [голова + (f" — {что}" if что else "") + (f", {страны}" if страны else "") + "."]
    if жанры:
        части.append(("Жанры: " if len(жанры) > 1 else "Жанр: ") + ", ".join(жанры) + ".")
    части.append(f"Смотреть онлайн на {сайт}.")
    return " ".join(части)


def факты(вид: Вид, запись: dict, деталь: dict) -> list:
    """Пары «что — значение» страницы. Пустого значения в списке не бывает."""
    собрано = []

    def добавить(метка, значение):
        if значение:
            собрано.append((метка, значение))

    добавить("Оригинальное название", html.escape(деталь.get("original_name") or ""))
    добавить("Год", html.escape(str(запись.get("year") or "")))
    добавить("Тип", html.escape(запись.get("kind") or ""))
    # Страна — ссылкой на раздел страны каталога (T242, перенос T240;
    # SEO_KNOWLEDGE_PACK §8 п.1, п.3): код — тот же, под которым
    # построить_индекс регистрирует страну и который ставит фильтр каталога.
    # Ссылка — только если в разделе больше одной записи: раздел с единственной
    # записью повторяет ту же карточку (FACTS F7.5). Иначе текст, как прежде.
    индекс = getattr(вид, "индекс", None) or {}
    по_стране = индекс.get("country") or {}
    по_slug = индекс.get("slug") or {}
    страны = []
    for страна in деталь.get("countries") or []:
        имя = html.escape(str(страна))
        код = нормализовать(транслит(str(страна)))
        if код and sum(1 for s in по_стране.get(код) or () if s in по_slug) > 1:
            имя = f'<a href="/catalog/{запрос_строкой({"country": код})}">{имя}</a>'
        страны.append(имя)
    добавить("Страна", ", ".join(страны))
    жанры = деталь.get("genres") or []
    коды = деталь.get("genre_codes") or []
    индекс = getattr(вид, "индекс", None) or {}
    ссылки = []
    for i, имя in enumerate(жанры):
        if str(имя).strip().casefold() in _ТЕХНИЧЕСКИЕ_ЖАНРЫ:
            continue
        код = главный_код_жанра(индекс, коды[i]) if i < len(коды) and коды[i] else ""
        ссылки.append(f'<a href="/catalog/{запрос_строкой({"genre": код})}">{html.escape(имя)}</a>'
                      if код else html.escape(имя))
    if ссылки:
        добавить("Жанр", " · ".join(ссылки))
    добавить("Время", html.escape(_длительность(деталь.get("duration"))))
    добавить("Дата выхода", html.escape(_дата(деталь.get("premiere_date") or "")))
    сезоны = деталь.get("seasons") or []
    if сезоны:
        серий = всего_серий(деталь)
        доступно = sum(len(доступные_номера(с)) for с in сезоны)
        хвост = "" if доступно >= серий else f", доступно {доступно}"
        добавить("Серии", html.escape(
            f"{_склонение(len(сезоны), 'сезон', 'сезона', 'сезонов')}, "
            f"{_склонение(серий, 'серия', 'серии', 'серий')}{хвост}"))
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


#: Номер, которым источник помечает спецвыпуск внутри сезона. Ноль — это
#: НАСТОЯЩИЙ номер серии в плейлисте провайдера, а не «значения нет» и не
#: ошибка разбора. Измерено на `/title/skotty/` («Скотты»,
#: `01a0e27f-8175-7115-8972-83cce31b15d3`, 2026-09-28, издатели 10238, 10252 и
#: 10261 отвечают одинаково): у записи ровно одна дорожка — `Pilot`, season 1,
#: episode 0, с `vkId` и `cvhId`. Пока рантайм отвергал эпизоды меньше единицы,
#: эта дорожка была недостижима со страницы вовсе.
СПЕЦВЫПУСК = 0


def подпись_серии(эпизод: int) -> str:
    """Короткая подпись серии. Ноль читателю показывается словом."""
    return "Спецвыпуск" if эпизод == СПЕЦВЫПУСК else f"Серия {эпизод}"


def подпись_сезон_серия(сезон: int, эпизод: int) -> str:
    """Длинная подпись: заголовок, крошки, соседние серии."""
    if эпизод == СПЕЦВЫПУСК:
        return f"{сезон} сезон, спецвыпуск — серия 0"
    return f"{сезон} сезон, {эпизод} серия"


def _наложить_номера(записи: dict, снимок) -> int:
    """Перенести проверенные номера серий из файла ячейки в записи снимка.

    Файл называется как снимок с суффиксом `.nums.json` и пишется фоновым
    согласованием (`episode_sync.py`). Накладывается только пересечение: слаг,
    которого в снимке больше нет, не воскрешается, сезон, которого у записи
    нет, не заводится. Это память о ПРОВЕРЕННОМ, а не второй каталог.

    Любая беда с файлом — молчаливый ноль: витрина обязана подниматься и без
    наложения, показывая ровно то же, что показывала бы по числу `avail`.
    """
    try:
        import episode_sync
    except ImportError:
        return 0
    try:
        return episode_sync.наложить(
            записи, episode_sync.прочитать_наложение(
                episode_sync.путь_наложения(Path(снимок))))
    except Exception:  # noqa: BLE001 — наложение не имеет права ронять витрину
        return 0


def доступные_номера(сезон: dict) -> set:
    """Какие НОМЕРА серий сезона играются.

    `nums` — явный перечень доступных номеров от поставщика снимка, и он
    главный: одним числом нельзя описать ни спецвыпуск с номером 0, ни
    пропуски в нумерации, ни сезон, у которого нумерация начинается со
    второй серии. Нет `nums` — остаётся прежний смысл `avail`: «серии с
    первой по avail», и снимок прежнего образца ведёт себя в точности как
    раньше.

    Пустой или неразборный `nums` НЕ превращается в `{0}`: отсутствие
    значения не номер, и подставлять на его место спецвыпуск значило бы
    обещать серию, которой никто не заявлял.
    """
    сырое = сезон.get("nums")
    if isinstance(сырое, (list, tuple, set)):
        номера = set()
        for н in сырое:
            try:
                ц = int(н)
            except (TypeError, ValueError):
                continue
            if ц >= 0:
                номера.add(ц)
        return номера
    return set(range(1, int(сезон.get("avail") or 0) + 1))


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
        доступные = доступные_номера(сезон)
        # Объединение ЗАЯВЛЕННОГО состава сезона и того, что реально играет.
        # Номера выше `eps` прятать нельзя: у `boec-baki` второй сезон объявлен
        # из 24 серий, а провайдер отдаёт 26, и обе последние были недостижимы.
        # Выдумать номер этим нельзя — сюда попадает только подтверждённое
        # дорожкой.
        номера = sorted(set(range(1, всего + 1)) | доступные)
        готово.append({"n": номер, "eps": всего, "avail": доступно,
                       "доступные": доступные,
                       "доступно": len(доступные & set(номера)),
                       "номера": номера})
    return готово


def серия_с_дорожкой(деталь: dict, сезон: int, эпизод: int) -> bool:
    """Есть ли у серии дорожка по снимку (`avail`), а не только номер в `eps`.

    Измерено на lordserial33.biz: у сериала `avail=3`, `eps=9` страница
    `/episode-7/` монтировала `<video-player episode="7">`. UI говорил «серия 7»,
    провайдер в контроле показывал «Эпизод 3» (последняя с дорожкой) и через
    15 с срабатывал таймаут «Плеер не поднялся». Список уже помечал 4–9 как
    `data-off`; страница серии обязана говорить то же самое и НЕ поднимать SDK.
    """
    if сезон < 1 or эпизод < 0:
        return False
    for с in список_серий(деталь):
        if с["n"] == сезон:
            return эпизод in с["доступные"]
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
                 описание: str = "", разметка: str | list = "", код: int = 200,
                 крошки: str = "", og: dict | None = None) -> str:
        нав = "".join(
            f'<a href="{закодировать_запрос(u)}"{ТЕКУЩАЯ_СТРАНИЦА if u == актив else ""}>{html.escape(t)}</a>'
            for u, t in self.се["нав"])
        схемы = _ld_json_scripts(разметка)
        описание_мета = (f'<meta name="description" content="{html.escape(описание)}">'
                         if описание else "")
        канон = (f'<link rel="canonical" href="{html.escape(self.канон(путь))}">'
                 if путь and код == 200 else "")
        return f"""<!doctype html><html lang="ru" data-template-version="{ВЕРСИЯ}" data-template-family="{СЕМЕЙСТВО}" data-build-id="{СБОРКА}" data-design="lords-sheet">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(титул)}</title>{описание_мета}{канон}
<meta name="robots" content="{мета_роботов_пути(путь)}">
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
                 "из каталога. Описание и оценки только из источника.")
        return (
            '<footer class="ft">'
            '<div class="ft__cols">'
            '<div class="ft__col"><b>Разделы</b>'
            '<a href="/movies/">Фильмы</a><a href="/series/">Сериалы</a>'
            '<a href="/animation/">Мультфильмы</a><a href="/new/">Новинки</a>'
            '<a href="/collections/">Подборки</a></div>'
            f'<div class="ft__col"><b>Жанры</b>{жанры or "<span>жанры появятся из sidecar</span>"}</div>'
            f'<div class="ft__col"><b>Годы</b>{годы or "<span>—</span>"}</div>'
            f'<div class="ft__col"><b>О сайте</b><p class="ft__about">{about}</p></div>'
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
            "с подборками и фильтрами по жанрам, годам и оценкам.</p>")
        bottom = (
            '<section class="sec" style="margin-top:22px"><h2>О каталоге</h2>'
            f'<p style="margin:0;line-height:1.6;color:#4d555e;font-size:14px;max-width:68ch">'
            f"Витрина {html.escape(self.имя)} собрана фабрикой поверх закрытого "
            "снимка: название, год, тип, постер и оценки приходят из источника. "
            "Разделы «Новинки», фильмы, сериалы и мультфильмы ведут в списки "
            "названий. Поиск понимает кириллицу, латиницу и транслит. "
            "Индексация поисковиками на этом стенде закрыта политикой noindex."
            "</p></section>")
        тело = intro + _склеить(полосы) + bottom
        return self.оболочка(
            тело, f"{self.имя} — фильмы и сериалы онлайн", "/", актив="/",
            описание=(f"{self.имя}: смотреть фильмы, сериалы и мультфильмы онлайн. "
                      "Каталог, новинки и подборки."),
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
                    "Сейчас здесь нет подборок. "
                    '<a href="/catalog/">Открыть каталог</a></div>')
        else:
            тело = (f'<h1 class="lead">Подборки</h1>'
                    f'<p class="zsub" style="margin:0 0 12px;color:#5b6470">'
                    f"Тематические подборки фильмов и сериалов.</p>"
                    f'<div class="hub">{"".join(карточки)}</div>')
        return self.оболочка(тело, f"Подборки — {self.имя}", "/collections/",
                             актив="/collections/",
                             описание=f"Подборки на {self.имя}.")

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
        подзаг = f'<p class="zsub" style="margin:0 0 10px;color:#5b6470">Найдено: {len(набор)}</p>'
        if выбрано.get("_unknown"):
            пусто = ('<div class="empty"><b>Неизвестный фильтр</b>'
                     "Параметр фильтра не распознан и не применён молча. "
                     "Сбросьте условия или выберите значение из списка.</div>")
        elif not кусок:
            пусто = ('<div class="empty"><b>Здесь пока пусто</b>'
                     "Под выбранные условия не попала ни одна запись. "
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
                             описание=f"{титул} на {self.имя}: подборка из каталога.")

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
                    f"По запросу «{html.escape(q)}» совпадений нет. "
                    "Проверьте написание. "
                    '<a href="/catalog/">Открыть каталог целиком</a></div>')
        return self.оболочка(
            тело, f"Поиск — {self.имя}", "/search/", актив="",
            описание=f"Поиск по каталогу {self.имя}.",
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

        описание = (чистое_описание(деталь.get("description"))
                    or чистое_описание(деталь.get("short_description")))
        сюжет = (f'<div class="plot"><p>{html.escape(описание)}</p></div>' if описание else
                 '<div class="plot"><p class="none">Описания пока нет: основные сведения '
                 "о записи собраны в таблице ниже.</p></div>")

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
        краткое = краткое_описание(имя, запись, деталь, описание, self.имя)
        return self.оболочка(
            тело, f"{различимое_название(имя, запись, деталь, self.д.items)} — смотреть онлайн — {self.имя}", путь,
            описание=краткое, разметка=разметка, крошки=self.крошки(звенья),
            og=self.карточка_графа(
                тип="video.tv_show" if сериал else "video.movie",
                титул=имя, описание=краткое, путь=путь,
                изображение=запись.get("poster") or ""))

    def _серии(self, запись: dict, сезоны: list, текущий=None) -> str:
        if not сезоны:
            return ('<section class="sec"><h2>Серии</h2>'
                    '<p class="plot"><span class="none">Список серий по этой '
                    "записи пока не опубликован. Как только серии появятся, список "
                    "встанет сюда.</span></p></section>")
        блоки = []
        for сезон in сезоны:
            ссылки = []
            for н in сезон["номера"]:
                доступна = н in сезон["доступные"]
                текущая = (текущий == (сезон["n"], н))
                атрибуты = ' aria-current="page"' if текущая else (
                    "" if доступна else ' data-off title="Серия пока недоступна"')
                ссылки.append(
                    f'<a href="{self.адрес_эпизода(запись["slug"], сезон["n"], н)}"{атрибуты}>{н}</a>')
            хвост = ("" if сезон["доступно"] == сезон["eps"]
                     else f", доступно {сезон['доступно']}")
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
            описание=f"{заголовок}: список серий на {self.имя}.",
            разметка=self.schema_крошек(звенья), крошки=self.крошки(звенья),
            og=self.карточка_графа(
                тип="video.tv_show", титул=заголовок,
                описание=f"{заголовок}: список серий на {self.имя}.",
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
            описание=f"{заголовок}: смотреть онлайн на {self.имя}.",
            разметка=разметка, крошки=self.крошки(звенья),
            og=self.карточка_графа(
                тип="video.episode", титул=заголовок,
                описание=f"{заголовок}: смотреть онлайн на {self.имя}.",
                путь=путь, изображение=запись.get("poster") or ""))

    def не_найдено(self, путь: str) -> str:
        тело = ('<div class="nf"><b>404</b><h1>Такой страницы на сайте нет</h1>'
                f"<p>Адрес <code>{html.escape(путь[:120])}</code> не соответствует ни одной "
                "странице сайта. Возможно, ссылка устарела или в ней опечатка.</p>"
                '<a href="/catalog/">Открыть каталог</a></div>')
        return self.оболочка(тело, f"Страница не найдена — {self.имя}", "", код=404)


# ----------------------------- Zona -----------------------------------


#: Поведение полосы действий. Обе кнопки — дополнение, а не замена: без
#: JavaScript полоса остаётся ссылками на серии, и ни одна ссылка не зависит
#: от скрипта. «Поделиться» пробует системный диалог, затем буфер обмена, и
#: только потом сознаётся, что не смог, — молчащая кнопка хуже отсутствующей.
_СКРИПТ_ПОЛОСЫ_ДЕЙСТВИЙ = (
    '<script>(function(){'
    'var bar=document.querySelector(".zplbar");if(!bar)return;'
    'var full=bar.querySelector("[data-zpl-full]");'
    'if(full){full.addEventListener("click",function(){'
    'var f=document.querySelector("[data-player]");if(!f)return;'
    'var el=f.querySelector("iframe,video,video-player")||f;'
    'var req=el.requestFullscreen||el.webkitRequestFullscreen||el.webkitEnterFullscreen;'
    'if(req){try{req.call(el);}catch(e){}}});}'
    'var sh=bar.querySelector("[data-zpl-share]");'
    'if(sh){sh.addEventListener("click",function(){'
    'var url=location.href,ok=function(t){var p=sh.textContent;sh.textContent=t;'
    'sh.setAttribute("data-done","1");'
    'setTimeout(function(){sh.textContent=p;sh.removeAttribute("data-done");},1600);};'
    'if(navigator.share){navigator.share({url:url,title:document.title})'
    '.then(function(){}).catch(function(){});return;}'
    'if(navigator.clipboard&&navigator.clipboard.writeText){'
    'navigator.clipboard.writeText(url).then(function(){ok("Ссылка скопирована");})'
    '.catch(function(){ok("Скопируйте из адресной строки");});return;}'
    'ok("Скопируйте из адресной строки");});}'
    '})();</script>')


class ВидЗона(Вид):
    """Боковая колонка, шрифт с засечками, карточки-строки, баннер на тайтле.

    Совпадений с Lords здесь нет ни в композиции, ни в типографике, ни в
    геометрии карточки, ни в раскладке страницы произведения. Общими остались
    только данные и механика маршрутов — то есть ровно то, что у семейств и
    обязано быть общим.
    """

    кл_состояния = "zpl__s"

    def оболочка(self, тело: str, титул: str, путь: str, *, актив: str = "",
                 описание: str = "", разметка: str | list = "", код: int = 200,
                 сверху: str = "", крошки: str = "", og: dict | None = None) -> str:
        нав = "".join(
            f'<a href="{закодировать_запрос(u)}"{ТЕКУЩАЯ_СТРАНИЦА if u == актив else ""}>{html.escape(t)}</a>'
            for u, t in self.се["нав"])
        # P0-05: rail genre links preserve active kind/year/country/sort when set.
        _ф = getattr(self, "_активные_фильтры", None) or {}
        жанры = "".join(
            f'<a href="/catalog/{html.escape(запрос_строкой(_ф, genre=код_жанра, page=None))}">'
            f'{html.escape(имя)}</a>'
            for код_жанра, имя in self.индекс["genre_names"][:14])
        схемы = _ld_json_scripts(разметка)
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
    <meta name="robots" content="{мета_роботов_пути(путь)}">
    {_открытый_граф(og or {})}
    <link rel="icon" href="/favicon.svg" type="image/svg+xml">
    {_мета_версии()}
    <style>{self.се["стиль"]()}</style><script>{СКРИПТ_ПОСТЕРОВ}</script></head>
    <body><a class="skip" href="#main">Перейти к содержимому</a>
    <div class="zs">
    <aside class="zrail">
    <a class="zrail__logo" href="/">{html.escape(self.имя)}</a>
    <p class="zrail__sub">Кинопортал</p>
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
        return f"""<!doctype html><html lang="ru" data-template-version="{ВЕРСИЯ}" data-template-family="{СЕМЕЙСТВО}" data-build-id="{СБОРКА}" data-design="zona-top" data-template-profile="{ЗОНА_ШАБЛОН}">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<script>{СКРИПТ_ТЕМЫ}</script>
<title>{html.escape(титул)}</title>{описание_мета}{канон}
<meta name="robots" content="{мета_роботов_пути(путь)}">
{_открытый_граф(og or {})}
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
{_мета_версии()}
<style>{self.се["стиль"]()}</style><script>{СКРИПТ_ПОСТЕРОВ}
{СКРИПТ_ЛЕНТ}
{СКРИПТ_ЗОНА_ШАПКА}
{СКРИПТ_ПЕРЕКЛЮЧАТЕЛЯ_ТЕМЫ}</script></head>
<body><a class="skip" href="#main">Перейти к содержимому</a>
<div class="zs">
<header class="zhd">
<div class="zhd__in">
<a class="zhd__logo" href="/" aria-label="{html.escape(self.имя)}">{html.escape(self.имя)}</a>
<button class="zhd__searchbtn" type="button" data-nav-toggle data-focus-search="q-drawer"
 aria-controls="zhd-nav" aria-expanded="false" aria-label="Открыть поиск">Поиск</button>
<button class="zhd__menu" type="button" data-nav-toggle aria-controls="zhd-nav"
 aria-expanded="false" aria-label="Меню разделов">&#9776;</button>
<nav id="zhd-nav" class="zhd__n" aria-label="Разделы">{нав}
<form class="zhd__s zhd__s--drawer" action="/search/" method="get" role="search" data-empty-submit="forbid">
<label class="vh" for="q-drawer">Поиск по каталогу</label>
<input id="q-drawer" name="q" placeholder="{html.escape(self.се["поиск"])}" autocomplete="off">
<button type="submit">Найти</button></form>
</nav>
<form class="zhd__s zhd__s--bar" action="/search/" method="get" role="search" data-empty-submit="forbid">
<label class="vh" for="q">Поиск по каталогу</label>
<input id="q" name="q" placeholder="{html.escape(self.се["поиск"])}" autocomplete="off">
<button type="submit" aria-label="Найти">Найти</button></form>
<button class="zhd__theme" type="button" data-theme-toggle aria-pressed="false"
 aria-label="Включить светлую тему"><span aria-hidden="true" data-theme-icon>&#9728;</span><span
 class="zhd__themetx" data-theme-label>Светлая</span></button>
</div>
</header>
<div class="zmain">
<div class="zwrap">{_склеить([f'<div class="ztop"><div class="ztop__b">{сверху}</div></div>' if сверху else ""])}{крошки}
<main id="main">{тело}</main>
{self._подвал_зона()}
</div></div></div>{схемы}</body></html>"""

    def _подвал_зона(self) -> str:
        """Compact four-zone footer. Dead legal routes are omitted (no fiction)."""
        source = (МАНИФЕСТ.get("source_commit") or "")[:8]
        # Contact/legal pages are published only when config provides a real URL
        # that the storefront actually serves. Missing config → gate FAIL in report.
        cfg_path = os.environ.get("ZONA_FOOTER_CONFIG") or _рядом_с_каталогом(
            "footer-zona-01.json")
        cfg = {}
        try:
            if cfg_path and Path(cfg_path).is_file():
                cfg = json.loads(Path(cfg_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            cfg = {}
        def _links(pairs):
            out = []
            for href, label in pairs:
                if not href:
                    continue
                out.append(f'<a href="{html.escape(href)}">{html.escape(label)}</a>')
            return "".join(out)
        раздел_а = _links([
            ("/", "Главная"), ("/new/", "Новинки"),
            ("/movies/", "Фильмы"), ("/series/", "Сериалы"),
        ])
        раздел_б = _links([
            ("/animation/", "Анимация"), ("/collections/", "Подборки"),
            ("/catalog/", "Каталог"), ("/search/", "Поиск"),
        ])
        помощь = _links([
            (cfg.get("about_url"), "О проекте"),
            (cfg.get("contacts_url"), "Контакты"),
            (cfg.get("feedback_url"), "Обратная связь"),
        ])
        документы = _links([
            (cfg.get("rights_url"), "Правообладателям"),
            (cfg.get("privacy_url"), "Политика конфиденциальности"),
            (cfg.get("terms_url"), "Пользовательское соглашение"),
        ])
        contact_missing = not any(
            cfg.get(k) for k in (
                "about_url", "contacts_url", "feedback_url",
                "rights_url", "privacy_url", "terms_url", "contact_email"))
        # No placeholders: omit empty help/docs. Fallback = brand + two link cols.
        help_col = (f'<div class="zft__col"><b>Помощь</b>{помощь}</div>' if помощь else "")
        docs_col = (f'<div class="zft__col"><b>Документы</b>{документы}</div>' if документы else "")
        cols_mod = ' zft__cols--fallback' if contact_missing else ""
        # B22: never show version/commit/build in public footer.
        marker = (f'<span class="zvb vh" data-contact-config-missing="{1 if contact_missing else 0}" '
                  f'data-footer-contact-gate="{0 if contact_missing else 1}" '
                  f'data-footer-technical-marker="0"></span>')
        return (
            '<footer class="zft" data-testid="site-footer">'
            f'<div class="zft__cols{cols_mod}">'
            f'<div class="zft__col"><b>{html.escape(self.имя)}</b>'
            f'<p class="zft__about">{html.escape(self.имя)} — фильмы, сериалы '
            "и анимация: каталог, поиск и подборки.</p></div>"
            f'<div class="zft__col zft__col--links"><b>Разделы</b>{раздел_а}</div>'
            f'<div class="zft__col zft__col--links"><b>Каталог</b>{раздел_б}</div>'
            f'{help_col}{docs_col}'
            "</div>"
            f'<div class="zft__bar"><span>© {html.escape(self.имя)}</span>'
            f"{_контакт_подвала()}{marker}</div></footer>")

    # --- составные части ---------------------------------------------
    #: Сколько обложек страницы грузятся сразу (T334, MOD-149; бюджет T333
    #: animedia.icu): ряд сетки на широком экране. Больше — лишняя полоса на
    #: телефоне, где видно четыре.
    СРОЧНЫХ_ПОСТЕРОВ = 6

    #: Сколько из них — с `fetchpriority="high"`: только видимые на ЛЮБОМ
    #: экране. Ширину экрана сервер не знает, и на узком иначе высокий
    #: приоритет уходил бы невидимым картинкам.
    ПРИОРИТЕТНЫХ_ПОСТЕРОВ = 2

    #: Выключатель для наследников: ВидАнимедиа берёт у Zona тайтл и ленты, а
    #: её разметка этим ядром не меняется.
    СРОЧНОСТЬ_ОБЛОЖЕК = True

    def _постер_срочно(self) -> str:
        """Режим загрузки следующей обложки первого экрана: "high", "eager", "".

        Бюджет живёт на экземпляре вида, а вид создаётся на запрос: первый
        экран считается по странице. Просят его только первый блок главной и
        сетка списка — в порядке разметки; прочие полки, поиск, подборки и
        похожее грузятся лениво и бюджет не тратят.
        """
        остаток = getattr(self, "_бюджет_постеров", None)
        if остаток is None:
            остаток = self.СРОЧНЫХ_ПОСТЕРОВ
        if остаток <= 0:
            self._бюджет_постеров = 0
            return ""
        self._бюджет_постеров = остаток - 1
        потрачено = self.СРОЧНЫХ_ПОСТЕРОВ - остаток
        return "high" if потрачено < self.ПРИОРИТЕТНЫХ_ПОСТЕРОВ else "eager"

    def _срочность(self, первый_экран: bool = False) -> dict:
        """Аргумент `срочно` для плитки; у наследника с выключенной — пусто."""
        if not self.СРОЧНОСТЬ_ОБЛОЖЕК:
            return {}
        return {"срочно": self._постер_срочно() if первый_экран else ""}

    def плитка(self, запись: dict, *, freshness: bool = False,
               fresh_mode: str = NEW_MODE_PREMIERE,
               show_play: bool | None = None,
               срочно: str | None = None) -> str:
        деталь = self.деталь(запись["slug"]) or {}
        изо = заглушка_постера(запись, "zt__none", "zt__img", срочно=срочно)
        # Line 1: year · country (source-backed only).
        страна = ""
        страны = деталь.get("countries") or []
        if страны:
            страна = str(страны[0])
        meta1_parts = [str(ч) for ч in (запись.get("year"), страна) if ч]
        # Line 2: genres only (kind is separate elsewhere — avoid «Мультфильм · мультфильм»).
        kind_l = (запись.get("kind") or "").strip().lower()
        жанры = []
        for g in (деталь.get("genres") or [])[:3]:
            gs = str(g).strip()
            if not gs:
                continue
            if gs.lower() == kind_l or нормализовать(транслит(gs)) == нормализовать(транслит(kind_l or "")):
                continue
            # Region tags are not genres.
            # Сравнение — нормализованного с нормализованным: прежде список не
            # нормализовался, совпадения не было никогда, и «западный контент»
            # печатался жанром в карточках списков (T185).
            if (gs.casefold() in _ТЕХНИЧЕСКИЕ_ЖАНРЫ
                    or нормализовать(gs) in {нормализовать(м) for м in (
                        "западный контент", "west_content", "zapadnyy-kontent")}):
                continue
            жанры.append(gs)
            if len(жанры) >= 2:
                break
        meta2_parts = list(жанры)
        # Подпись свежести идёт СВОЕЙ строкой, а не хвостом к жанрам. Хвостом
        # она не помещалась: `.zt__m` — одна строка с многоточием, и «драма ·
        # спорт · Добавлено 22.09.2026» обрезалось до «драма · спорт ·
        # Добавле…». Обрезанная подпись не короче — она бессмысленна: не
        # называет ни дату, ни то, что это за дата.
        свежесть = _подпись_свежести(запись, fresh_mode) if freshness else ""
        мета1 = " · ".join(meta1_parts)
        мета2 = " · ".join(meta2_parts)
        # Card bodies stay metadata-only: plot text belongs on the title page.
        оценки_карточки, состояние_оценки = self._оценки_плитки(деталь)
        части = list(оценки_карточки)
        playable = деталь.get("playable") is True
        if show_play is False:
            show_badge = False
        elif show_play is True:
            show_badge = playable
        else:
            show_badge = playable
        if show_badge:
            части.append('<span class="zt__play" title="Есть видео" aria-label="Есть видео">▶</span>')
        # Collapse rating row when empty — no blank NBSP reservation.
        оценка = (f'<span class="zt__r">{"".join(части)}</span>' if части else "")
        заголовок = запись["title"] or ""
        meta_html = ""
        if мета1:
            meta_html += f'<span class="zt__m">{html.escape(мета1)}</span>'
        if мета2:
            meta_html += f'<span class="zt__m">{html.escape(мета2)}</span>'
        if свежесть:
            meta_html += (f'<span class="zt__m zt__m--when">'
                          f'{html.escape(свежесть)}</span>')
        # data-clamp-allowed объявляет обрезку в две строки как замысел, а не
        # дефект. Без объявления машинный аудит не может отличить задуманный
        # clamp от съеденного вёрсткой заголовка и считает любой обрезанный
        # заголовок нарушением. Полное название рядом — в title и aria-label,
        # иначе объявлять было бы нечего: обрезка допустима только тогда,
        # когда текст целиком остаётся доступен.
        класс_плитки = "zt zt--fresh" if свежесть else "zt"
        return (f'<a class="{класс_плитки}" data-testid="title-card" '
                f'href="{запись["url"]}" '
                f'data-rating="{html.escape(состояние_оценки)}" '
                f'title="{html.escape(заголовок)}" aria-label="{html.escape(заголовок)}">'
                f'<span class="zt__p">{изо}</span>'
                f'<span class="zt__b"><span class="zt__t" data-clamp-allowed="2">'
                f'{html.escape(заголовок)}</span>'
                f'{meta_html}</span>{оценка}</a>')

    #: Сколько внешних источников показывает карточка. Два — та же плотность,
    #: что была до правки; третий источник ломал бы строку на узкой карточке.
    #: Страница произведения показывает все: там есть место.
    ОЦЕНОК_НА_КАРТОЧКЕ = 2

    def _оценки_плитки(self, деталь: dict) -> tuple[list, str]:
        """Оценки карточки из ТОГО ЖЕ разбора, что и страница произведения.

        До этой правки карточка читала `kinopoisk_rating` и `imdb_rating`
        напрямую. Из-за этого Shikimori, который витрина показывает на странице
        произведения, на карточке пропадал, а число печаталось в другом виде —
        «IMDb 7.8» против «IMDb 7.8 из 10». Второе место чтения оценок убрано:
        расхождение двух копий логики — вопрос времени, а не возможности.

        Возвращает разметку и состояние для `data-rating`:

        * ``"none"`` — оценок у витрины действительно нет. Ноль и `null`
          оценкой не считаются и сюда попадают именно как «нет».
        * ``"unavailable"`` — разбор оценок недоступен. Карточка остаётся
          рабочей, но честное «нет» и сбой различимы машиной.
        * число — значение первой показанной оценки.

        Ряд по-прежнему схлопывается, когда показывать нечего: пустая строка,
        зарезервированная под оценку, — дефект, чинённый в этой витрине ранее.
        Поэтому отсутствие объявлено атрибутом, а не пустым местом.
        """
        try:
            оценки = оценки_по_источникам(деталь)
        except Exception as ош:  # noqa: BLE001 — витрина важнее оценки
            print(f"[zona] разбор оценок недоступен: {ош!r}",
                  file=sys.stderr, flush=True)
            return [], "unavailable"
        внешние = [о for о in оценки if not о["пользовательская"]]
        if not внешние:
            return [], "none"
        части = []
        for о in внешние[:self.ОЦЕНОК_НА_КАРТОЧКЕ]:
            вслух = f'{о["подпись"]} {о["значение"]} из {о["шкала"]}'
            части.append(
                f'<span class="zt__ri" data-source="{о["ключ"]}" '
                f'title="{html.escape(вслух)}">'
                f'<span class="vh">{html.escape(вслух)}</span>'
                # Шкала на карточке не печатается видимо намеренно: «/10»
                # дважды в ряду удлиняет строку и на узкой карточке толкает её
                # в перенос. Вслух и в подсказке шкала названа полностью — тем
                # же текстом, что на странице произведения.
                f'<span class="zt__rs" aria-hidden="true">{html.escape(о["подпись"])}</span>'
                f'<span class="zt__rn" aria-hidden="true">{о["значение"]}</span></span>')
        return части, внешние[0]["значение"]

    def строка(self, запись: dict) -> str:
        деталь = self.деталь(запись["slug"])
        изо = заглушка_постера(запись, "zr__none", "zr__img", 184, 276)
        части = [запись.get("kind"), запись.get("year")]
        части += (деталь.get("countries") or [])[:1]
        части += (деталь.get("genres") or [])[:2]
        мета = " · ".join(str(ч) for ч in части if ч)
        описание = (чистое_описание(деталь.get("short_description"))
                    or чистое_описание(деталь.get("description")))
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

    def карусель(self, ключ: str, набор, *, первый_экран: bool = False) -> str:
        """Горизонтальная лента: мышь, клавиатура и свайп.

        Прокрутка нативная, поэтому свайп и колесо работают без единой строки
        скрипта, а клавиатура — потому что область получает фокус. Кнопки
        добавляют мышиный способ и ничего не заменяют: при выключенном
        JavaScript лента остаётся прокручиваемой.
        """
        плитки = "".join(self.плитка(з, **self._срочность(первый_экран))
                         for з in набор)
        ид = f"rl-{ключ}"
        return (f'<div class="zrl">'
                f'<button class="zrl__btn zrl__btn--p" type="button" data-rl="prev"'
                f' aria-controls="{ид}" aria-label="Пролистать назад">&#8249;</button>'
                # data-scroller объявляет боковую прокрутку замыслом: у ленты
                # есть кнопки, клавиатура и подпись. Аудит иначе считает её
                # непреднамеренной внутренней прокруткой наравне с вёрсткой,
                # которая поехала.
                f'<div class="zrl__vp" id="{ид}" tabindex="0" role="group"'
                f' data-scroller="rail" aria-label="Лента произведений">'
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

    def класс_сетки(self) -> str:
        """Модификатор сетки, объявленный шаблоном витрины.

        Базовый тип не добавляет класса вовсе: иначе витрина по умолчанию
        отдавала бы не те байты, что до появления шаблонов, и «шаблонов ещё
        нет» стало бы неотличимо от «шаблон сменили».
        """
        тип = ЗОНА_ШАБЛОНЫ[ЗОНА_ШАБЛОН].get("сетка", "tile")
        return ЗОНА_КЛАСС_СЕТКИ.get(тип, "")

    def плитки(self, набор, *, freshness: bool = False,
               fresh_mode: str = NEW_MODE_PREMIERE,
               полные_ряды: bool = False, первый_экран: bool = False) -> str:
        """Сетка карточек.

        `полные_ряды` объявляет блок рядами: лишний хвост последнего неполного
        ряда скрывается стилем для каждой ширины. Включается у полок главной,
        не у каталога: список раздела обязан показывать всё.
        """
        мод = self.класс_сетки()
        класс = f"zg {мод}" if мод else "zg"
        if полные_ряды:
            класс += " zg--rows"
        return (f'<div class="{класс}">'
                + "".join(self.плитка(з, freshness=freshness, fresh_mode=fresh_mode,
                                      **self._срочность(первый_экран))
                          for з in набор)
                + "</div>")

    def листалка(self, разд: str, выбрано: dict, стр: int, всего: int) -> str:
        пункты = страницы(стр, всего)
        if not пункты:
            return ""
        куски = []
        if стр > 1:
            куски.append(
                f'<a class="zpg__nav" href="{разд}/'
                f'{запрос_строкой(выбрано, page=(стр - 1 if стр - 1 > 1 else None))}"'
                f' rel="prev">Назад</a>')
        for н in пункты:
            if н is None:
                куски.append('<span class="zpg__gap" aria-hidden="true">…</span>')
            elif н == стр:
                куски.append(f'<span aria-current="page">{н}</span>')
            else:
                куски.append(
                    f'<a href="{разд}/'
                    f'{запрос_строкой(выбрано, page=(н if н > 1 else None))}">{н}</a>')
        if стр < всего:
            куски.append(
                f'<a class="zpg__nav" href="{разд}/'
                f'{запрос_строкой(выбрано, page=стр + 1)}" rel="next">Далее</a>')
        return (f'<nav class="zpg" data-testid="pagination" aria-label="Страницы">'
                f'{"".join(куски)}</nav>')

    def крошки(self, звенья) -> str:
        """Цепочка крошек. Текущая страница — отдельным узлом со своим
        разделителем.

        Прежде она была голым текстовым узлом, и убрать её с узкого экрана
        было нечем: спрятать можно элемент, а не текст, и если спрятать
        только имя, остался бы висящий слеш. Видимый текст от этой правки не
        меняется ни на знак — меняется только то, что у него появился узел.
        """
        куски = []
        for н, (адрес, имя) in enumerate(звенья):
            разделитель = " / " if н else ""
            if адрес:
                куски.append(f'{разделитель}'
                             f'<a href="{адрес}">{html.escape(имя)}</a>')
            else:
                куски.append(f'<span class="zcr__cur">{разделитель}'
                             f'{html.escape(имя)}</span>')
        return (f'<nav class="zcr" aria-label="Хлебные крошки">'
                f'{"".join(куски)}</nav>')

    # --- страницы -----------------------------------------------------
    # --- B02–B05 home building blocks ---------------------------------
    #: Сколько карточек в полке поступлений. Двадцать четыре, а не двенадцать:
    #: при 24 последний ряд полон на 2, 4, 6 и 8 колонках, а на 5 и 7 лишние
    #: карточки скрывает `zg--rows` — ряд с пустыми ячейками выглядит как
    #: недогруженный блок, а не как замысел.
    ПОСТУПЛЕНИЙ = 24

    #: Сколько карточек в недельной полке. Столько же, сколько нарезает снимок;
    #: резерв снимка добирает полку после отбора по категории, а не расширяет её.
    ПОЛКА_НЕДЕЛИ = 12
    #: Сколько карточек должно остаться во вкладке, чтобы её показывать.
    #: Четыре — ряд на телефоне и половина ряда на компьютере; меньше — это
    #: огрызок, по которому нельзя выбрать.
    ПОЛКА_МИНИМУМ = 4

    #: Сколько слайдов показывает герой, если хватает годных записей.
    ГЕРОЙ_СЛАЙДОВ = 16
    #: Меньше двух — управление прячется: листать нечего.
    ГЕРОЙ_МИНИМУМ = 2

    #: Из скольких недавних поступлений герой выбирает свои слайды. Пул, а не
    #: весь каталог: «актуальные» — это недавние, иначе на первом экране вечно
    #: стояла бы одна и та же классика с высокой оценкой.
    ГЕРОЙ_ПУЛ = 400

    def _герои_кандидаты(self, weekly, pop_films, pop_series, pop_anim,
                         занято: set | None = None) -> list:
        """Слайды героя: РАЗНЫЕ тайтлы, и не те, что стоят в полках ниже.

        Правило, по которому набор обновляется из данных: взять недавние
        поступления в области главной (фильмы и обычные сериалы), оставить те,
        у которых есть постер, работающий источник и настоящая оценка
        источника, и отсортировать по этой оценке. То есть «лучшее из недавно
        добавленного» — и оно меняется само, как только меняется снимок.
        Искусственно список не перемешивается: случайности на запрос нет, иначе
        два прогона приёмки дали бы разные слайды и доказать переключение стало
        бы нечем.

        Почему не «просто самые свежие». Раньше герой брал начало того же
        списка, из которого собирается полка поступлений, и не смотрел в набор
        занятых слагов. На публичной главной это давало восемь слайдов,
        дословно повторяющих первые восемь карточек блока под ними: один и тот
        же набор под двумя заголовками.

        Недельный снимок, когда он доставлен, идёт первым: это отобранное
        редакцией, и оно важнее оценки.

        Годность проверяется, а не предполагается: нужны slug, название и
        постер. Запись без постера дала бы пустой слайд.
        """
        отобраны: list = []
        видели: set = set(занято or ())
        франшизы: set = set()

        def взять(з) -> None:
            if len(отобраны) >= self.ГЕРОЙ_СЛАЙДОВ:
                return
            slug = (з or {}).get("slug")
            if not slug or slug in видели:
                return
            if not str(з.get("poster") or "").strip():
                return
            if not str(з.get("title") or "").strip():
                return
            # Герой — первый экран главной, и область у него та же: иначе
            # кинопортал открывался бы аниме или дорамой.
            if not self.в_области_главной(з):
                return
            # Полка «Сейчас на Zona» ведёт на «Все новинки», и правило у неё
            # то же, что у раздела: дата выхода в окне. Старое произведение
            # сюда не попадает, сколько бы раз его ни доставили заново (T284).
            if not новинка(з):
                return
            # Разные тайтлы, а не части одной франшизы подряд: восемь слайдов
            # «Рокки 1…5» — это один фильм, показанный пять раз.
            фр = франшиза(з.get("title") or "")
            if фр and фр in франшизы:
                return
            видели.add(slug)
            if фр:
                франшизы.add(фр)
            отобраны.append(з)

        for набор in (pop_films, pop_series, pop_anim):
            for з in набор or ():
                взять(з)
        # Недавние поступления области главной → с оценкой → по оценке.
        недавние = [з for з in self.д.items
                    if дата_поступления(з) and self.в_области_главной(з)]
        недавние.sort(key=дата_поступления, reverse=True)
        пул = недавние[:self.ГЕРОЙ_ПУЛ]

        def по_оценке(записи):
            с_оценкой = [з for з in записи if float(з.get("_rating") or 0) > 0]
            с_оценкой.sort(key=lambda з: (float(з.get("_rating") or 0),
                                          дата_поступления(з)), reverse=True)
            return с_оценкой

        # Фильмы и сериалы идут вперемежку, а не подряд по общей оценке. На
        # чистой оценке сериалы проигрывают фильмам почти всегда: в пуле из
        # 400 недавних у фильмов 288 оценённых против 65 у сериалов, и лучший
        # сериал (8.2) не попадал в восьмёрку вовсе — герой кинопортала
        # состоял из одних фильмов. Чередование — правило, а не подкрутка
        # списка: оно ничего не переставляет внутри вида.
        очереди = [по_оценке([з for з in пул if (з.get("_ck") or "") == к])
                   for к in ("movie", "series")]
        позиции = [0, 0]
        while len(отобраны) < self.ГЕРОЙ_СЛАЙДОВ:
            двинулись = False
            for i, очередь in enumerate(очереди):
                было = len(отобраны)
                while позиции[i] < len(очередь) and len(отобраны) == было:
                    взять(очередь[позиции[i]])
                    позиции[i] += 1
                if len(отобраны) != было:
                    двинулись = True
                if len(отобраны) >= self.ГЕРОЙ_СЛАЙДОВ:
                    break
            if not двинулись:
                break
        # Если оценённых не хватило — добираем свежими из того же пула, а не
        # из всего каталога: герой обязан оставаться про недавнее.
        for з in пул:
            взять(з)
        return отобраны

    def _герой_кандидат(self, weekly, pop_films, pop_series, pop_anim):
        """Первый слайд. Оставлен для вызовов, которым нужна одна запись."""
        набор = self._герои_кандидаты(weekly, pop_films, pop_series, pop_anim)
        return набор[0] if набор else None

    def _герой_данные(self, з) -> dict:
        """Поля одного слайда. Ничего не выдумывается: пусто — значит пусто."""
        д = self.деталь(з["slug"])
        мета = " · ".join(str(x) for x in (з.get("kind"), з.get("year")) if x)
        return {
            "slug": з["slug"],
            "title": з.get("title") or "Без названия",
            "meta": мета,
            "desc": чистое_описание(д.get("description")).strip()[:280],
            "poster": з.get("poster") or "",
            "href": f'/title/{з["slug"]}/',
            "playable": состояние_плеера(д)[0] == "playable",
        }

    def _герой_панель(self, с: dict) -> str:
        """Текстовая панель активного слайда.

        Панель одна на весь слайдер, а не по одной на слайд. Иначе шесть
        слайдов дали бы шесть H1 на странице, а требование — ровно один.
        Скрипт переписывает её содержимое по активному слайду; без скрипта
        она остаётся панелью первого слайда, и страница осмысленна.
        """
        ctas = [f'<a class="secondary" data-zhero-more href="{html.escape(с["href"])}">Подробнее</a>']
        if с["playable"]:
            ctas.insert(0, f'<a class="primary" data-zhero-play href="{html.escape(с["href"])}">Смотреть</a>')
        desc = (f'<p class="zhero__desc" data-zhero-desc>{html.escape(с["desc"])}</p>'
                if с["desc"] else '<p class="zhero__desc" data-zhero-desc hidden></p>')
        return (
            f'<div class="zhero__body">'
            f'<p class="zhero__kicker">Сейчас на Zona</p>'
            f'<h1 class="zhero__t" data-zhero-title>{html.escape(с["title"])}</h1>'
            f'<p class="zhero__meta" data-zhero-meta>{html.escape(с["meta"])}</p>'
            f'{desc}'
            f'<div class="zhero__cta" data-zhero-cta>{"".join(ctas)}</div>'
            f'</div>')

    def герой_карусель(self, слайды: list) -> str:
        """Верхний блок — компактная лента постеров, а не большая композиция.

        Почему лента, а не слайдер. Прежняя подача занимала первый экран одним
        тайтлом: постер слева, описание справа, большие кнопки и точки. За один
        взгляд посетитель видел одно произведение, а высоту блока задавала
        текстовая панель, а не карточка. Лента показывает сразу семь-восемь.

        Компонент взят готовый — тот же `карусель`/`плитка`, что у полок ниже.
        Это не копия полки: набор приходит из `_герои_кандидаты`, который
        исключает слаги, уже занятые полками, держится области главной
        (фильмы и сериалы) и требует настоящей оценки. Совпадает вид, а не
        содержимое; собственный слайдер здесь означал бы вторую реализацию
        стрелок, свайпа и клавиатуры.

        H1 страницы переезжает сюда. Прежде его давала панель слайдера, и без
        замены на главной не осталось бы ни одного заголовка первого уровня.
        """
        if not слайды:
            return (f'<section class="zhero zhero--compact" aria-label="Введение">'
                    f'<h1>{html.escape(self.се["лид"])}</h1>'
                    f'<p class="zhero__meta">Фильмы, сериалы и анимация в каталоге.</p>'
                    f'</section>')
        # Герой-лента — первый блок главной: бюджет срочных обложек её (T334).
        лента = self.карусель("hero", слайды, первый_экран=True)
        лента = лента.replace('<div class="zrl">', '<div class="zrl zrl--hero">', 1)
        лента = лента.replace('aria-label="Лента произведений"',
                              'aria-label="Сейчас на Zona"', 1)
        return (f'<section class="zsec zsec--hero" aria-labelledby="zhero-h">'
                f'<div class="zsec__h"><h1 id="zhero-h">Сейчас на Zona</h1>'
                f'<a href="/new/">Все новинки</a></div>'
                f'{лента}</section>')

    def герой(self, з) -> str:
        """Совместимость: один кандидат — слайдер из одного слайда."""
        return self.герой_слайдер([з] if з else [])

    def герой_слайдер(self, слайды: list) -> str:
        if not слайды:
            return (f'<section class="zhero zhero--compact" aria-label="Введение">'
                    f'<h1>{html.escape(self.се["лид"])}</h1>'
                    f'<p class="zhero__meta">Фильмы, сериалы и анимация в каталоге.</p>'
                    f'</section>')
        данные = [self._герой_данные(з) for з in слайды]
        много = len(данные) >= self.ГЕРОЙ_МИНИМУМ

        куски = []
        for i, с in enumerate(данные):
            активен = "1" if i == 0 else "0"
            # Постер отдаётся с явной пропорцией: без неё портретная картинка
            # растягивает ряд под себя — дефект, уже чинённый в этой витрине.
            img = (f'<img src="{html.escape(с["poster"])}" alt="{html.escape(с["title"])}" '
                   f'loading="{"eager" if i == 0 else "lazy"}" decoding="async" '
                   f'draggable="false" data-zhero-img>')
            скрыт = "" if i == 0 else 'aria-hidden="true"'
            куски.append(
                f'<article class="zhero__slide" role="group" aria-roledescription="слайд" '
                f'aria-label="{i + 1} из {len(данные)}: {html.escape(с["title"])}" '
                f'data-zhero-slide data-index="{i}" data-active="{активен}" '
                f'data-slide-id="{html.escape(с["slug"])}" '
                f'data-slide-title="{html.escape(с["title"])}" '
                f'data-slide-meta="{html.escape(с["meta"])}" '
                f'data-slide-desc="{html.escape(с["desc"])}" '
                f'data-slide-href="{html.escape(с["href"])}" '
                f'data-slide-playable="{"1" if с["playable"] else "0"}" '
                f'{скрыт}>'
                f'<div class="zhero__media">{img}</div>'
                f'</article>')

        точки = "".join(
            f'<button type="button" class="zhero__dot" data-zhero-dot data-goto="{i}" '
            f'role="tab" aria-selected="{"true" if i == 0 else "false"}" '
            f'aria-label="Слайд {i + 1}: {html.escape(с["title"])}">'
            f'<span class="zhero__dot-i" aria-hidden="true"></span></button>'
            for i, с in enumerate(данные)) if много else ""

        нав = (
            f'<button type="button" class="zhero__nav zhero__nav--prev" data-zhero-prev '
            f'aria-label="Предыдущий слайд"><span aria-hidden="true">‹</span></button>'
            f'<button type="button" class="zhero__nav zhero__nav--next" data-zhero-next '
            f'aria-label="Следующий слайд"><span aria-hidden="true">›</span></button>'
        ) if много else ""

        точки_блок = (f'<div class="zhero__dots" role="tablist" '
                      f'aria-label="Выбор слайда">{точки}</div>') if много else ""

        return (
            f'<section class="zhero zhero--slider" data-zhero-slider '
            f'data-hero-slug="{html.escape(данные[0]["slug"])}" data-hero-recompute="0" '
            f'data-slides="{len(данные)}" data-zhero-ready="0" '
            f'aria-roledescription="карусель" aria-label="Сейчас на Zona">'
            f'<div class="zhero__viewport" data-zhero-viewport>'
            f'<div class="zhero__track" data-zhero-track>{"".join(куски)}</div>'
            f'{нав}{точки_блок}'
            f'</div>'
            f'{self._герой_панель(данные[0])}'
            f'{ЗОНА_СКРИПТ_ГЕРОЯ if много else ""}'
            f'</section>')

    def недельный_блок(self, pop_films, pop_series, pop_anim, weekly) -> str:
        """B03: one weekly block with tabs; honest rating-week label."""
        week_id = (weekly or {}).get("week_id") or ""
        digest = ((weekly or {}).get("digest") or "")[:12]
        # Пустая вкладка не рисуется вовсе. Заголовок вкладки без содержимого
        # неотличим от сломанной полки — тот же дефект, который `секция` уже
        # лечит скрытием пустых блоков.
        # Вкладка короче порога не рисуется: после проверки объёма выборки в
        # полке может остаться одна-две работы, и блок из двух карточек под
        # заголовком выглядит сломанным. Добивать его случайными карточками
        # запрещено, значит остаётся не показывать.
        tabs = [т for т in (
            ("films", "Фильмы", pop_films, "/movies/"),
            ("series", "Сериалы", pop_series, "/series/"),
            ("anim", "Анимация", pop_anim, "/animation/"),
        ) if len(т[2] or ()) >= self.ПОЛКА_МИНИМУМ]
        # Prefer first non-empty tab as default
        default = next((t[0] for t in tabs if t[2]), "films")
        tab_html = []
        panels = []
        for key, label, items, cta in tabs:
            cur = ' aria-current="true"' if key == default else ""
            tab_html.append(
                f'<a href="#zwpop-{key}" data-zwpop-tab="{key}"{cur}>{html.escape(label)}</a>')
            hidden = "" if key == default else " hidden"
            body = self.карусель(f"weekly-{key}", items) if items else ""
            panels.append(
                f'<div class="zwpop__panel" id="zwpop-{key}" data-zwpop-panel="{key}"{hidden}>'
                f'{body}</div>')
        if not any(t[2] for t in tabs):
            return ""
        meta = f' data-week-id="{html.escape(week_id)}" data-weekly-digest="{html.escape(digest)}"' if week_id else ""
        return (
            f'<section class="zwpop" aria-labelledby="zwpop-h"{meta}>'
            f'<div class="zwpop__h"><h2 id="zwpop-h">Высокие оценки зрителей</h2>'
            f'<a href="/catalog/?sort=rating">Смотреть всё</a></div>'
            f'<div class="zwpop__tabs" role="tablist">{"".join(tab_html)}</div>'
            f'{"".join(panels)}</section>'
            '<script>(function(){document.querySelectorAll("[data-zwpop-tab]").forEach(function(a){'
            'a.addEventListener("click",function(e){e.preventDefault();var k=a.getAttribute("data-zwpop-tab");'
            'document.querySelectorAll("[data-zwpop-tab]").forEach(function(x){x.removeAttribute("aria-current");});'
            'a.setAttribute("aria-current","true");'
            'document.querySelectorAll("[data-zwpop-panel]").forEach(function(p){'
            'p.hidden=p.getAttribute("data-zwpop-panel")!==k;});});});})();</script>')

    def новое_в_каталоге(self, события) -> str:
        """B04: поступления в каталог — постерной сеткой.

        Почему сеткой, а не строками. До этой правки блок рисовал собственные
        строки `zadded__row` с картинкой 60×90 — единственный блок витрины со
        своей вёрсткой карточки. Из-за него главная не показывала ни одного
        постера: остальные полки собираются из недельного снимка, а его в
        доставке данных сайта нет (см. отчёт о зависимостях). Плитка `zt` уже
        есть, работает в каталоге и на страницах разделов и умеет то, чего
        строка не умела: крупный вертикальный постер, оценки источников,
        жанры, заглушку при отсутствии постера. Вторая вёрстка карточки рядом
        с первой — это два ответа на вопрос «как выглядит произведение
        в списке»; убран тот, который показывал меньше.

        Дата остаётся датой ДОБАВЛЕНИЯ и подписана именно так: «Добавлено
        DD.MM.YYYY». Премьера — другое поле (`premiere_date`) и другая подпись;
        показывать одно вместо другого здесь нечем, потому что режим передан
        явно.
        """
        if not события:
            return ""
        набор = [з for з, _, _ in события]
        return (
            '<section class="zsec zadded" aria-labelledby="zadded-h">'
            '<div class="zsec__h"><h2 id="zadded-h">Новое в каталоге</h2>'
            '<a href="/new/?mode=added">Смотреть всё</a></div>'
            f'{self.плитки(набор, freshness=True, fresh_mode=NEW_MODE_ADDED, полные_ряды=True)}'
            "</section>")

    #: Категории, попадающие на главную. Zona Cinema — фильмы и обычные
    #: сериалы; анимация и дорамы живут в своих разделах и в навигации. До этой
    #: правки полки главной брались из всего снимка, и аниме с дорамами
    #: оказывались на первом экране кинопортала: 8 610 и 9 616 записей снимка,
    #: то есть каждая третья.
    #:
    #: Входы разделов (`входы_видов`) и меню этим НЕ ограничены: они ведут в
    #: разделы, а не показывают их содержимое.
    ГЛАВНАЯ_КАТЕГОРИИ = frozenset({"movie", "series"})

    def в_области_главной(self, з: dict) -> bool:
        """Попадает ли запись в полки главной."""
        if not self.КАТЕГОРИЙНЫЕ_РАЗДЕЛЫ:
            return True
        return (з.get("_ck") or "") in self.ГЛАВНАЯ_КАТЕГОРИИ

    #: Подписи входов. Описание раздела — то же, что раздел действительно
    #: показывает: «Анимация» включает аниме и дунхуа, и умалчивать об этом в
    #: подписи значило бы описывать не тот раздел, куда ведёт ссылка.
    ОПИСАНИЕ_ВХОДА = {
        "movie": "Полный каталог фильмов",
        "series": "Сериалы без анимации и дорам",
        "animation": "Мультфильмы, аниме и дунхуа",
        "dorama": "Дорамы Кореи, Японии, Китая и Тайланда",
    }

    def входы_видов(self) -> str:
        """B05: входы разделов со счётчиками по всему снимку.

        Счётчик считается по той же категории, по которой раздел отбирает
        записи. Пока он считался по полю `kind`, «Анимация» обещала 4 142
        записи, а показывала 8 610: аниме и дунхуа приходят из снимка как
        «Сериал» и «Фильм».
        """
        if not self.КАТЕГОРИЙНЫЕ_РАЗДЕЛЫ:
            counts = {"Фильм": 0, "Сериал": 0, "Мультфильм": 0}
            for з in self.д.items:
                k = з.get("kind")
                if k in counts:
                    counts[k] += 1
            cards = [
                ("Фильмы", "/movies/", counts["Фильм"], "Полный каталог фильмов"),
                ("Сериалы", "/series/", counts["Сериал"], "Полный каталог сериалов"),
                ("Анимация", "/animation/", counts["Мультфильм"],
                 "Полный каталог анимации"),
            ]
            return self._разметка_входов(cards)
        счёт: dict[str, int] = {к: 0 for к in КАТЕГОРИИ_КАТАЛОГА.КАТЕГОРИИ}
        for з in self.д.items:
            к = з.get("_ck")
            if к in счёт:
                счёт[к] += 1
        cards = [
            (КАТЕГОРИИ_КАТАЛОГА.ярлык(к), f"{МАРШРУТ_ПО_КАТЕГОРИИ[к]}/",
             счёт[к], self.ОПИСАНИЕ_ВХОДА.get(к, ""))
            for к in КАТЕГОРИИ_КАТАЛОГА.КАТЕГОРИИ if счёт[к]
        ]
        return self._разметка_входов(cards)

    def _разметка_входов(self, cards) -> str:
        parts = []
        for title, href, count, desc in cards:
            parts.append(
                f'<a class="zkind" href="{href}"><b>{html.escape(title)}</b>'
                f'<span>{html.escape(desc)}</span>'
                f'<em>{count} в каталоге</em></a>')
        return f'<section class="zkinds" aria-label="Разделы каталога">{"".join(parts)}</section>'

    def главная(self) -> str:
        """Пять горизонтальных лент, и ни одна не повторяет выборку другой.

        Повтор одной выборки под тремя заголовками — дефект, который витрина
        показывает зрителю как три разных раздела. Поэтому здесь ведётся один
        набор занятых slug: запись, попавшая в ленту выше, ниже не повторяется.
        Ленту, для которой источник не передал данных, заменяет названная
        причина, а не молчание и не чужая выборка.
        """
        from episode_feed_integration import load_rows, render_rows
        episode_catalog = [з for з in self.д.items if з.get('_ck') == 'series'
                           and self.в_области_главной(з)]
        if not ОФОРМЛЕНИЕ_ПЕРЕРАБОТАННОЕ:
            episode_rows = load_rows(self, sys.modules[__name__], 'zona-01', episode_catalog)
            episode_html = render_rows(episode_rows, style='zona')
            свежие = новинки_с_источником(self.д, self.п, 8)
            куски = [f'<h1 class="zh">{html.escape(self.се["лид"])}</h1>'
                     f'<p class="zsub">В каталоге {len(self.д.items)} записей. '
                     f"Ниже — то, что появилось последним.</p>"
                     + self.плитки(свежие, первый_экран=True)]
            for титул, ссылка, вид in self.се["полосы"]:
                # Третий элемент полосы — категория (Zona) или значение `kind`
                # (остальные семейства). Различаются по множеству, а не по виду
                # строки: см. `ЗНАЧЕНИЯ_КАТЕГОРИЙ`.
                поле = "_ck" if вид in ЗНАЧЕНИЯ_КАТЕГОРИЙ else "kind"
                набор = [з for з in self.д.items if з.get(поле) == вид][:6]
                if набор:
                    куски.append(f'<h2 class="zh zh--sm">{html.escape(титул)}</h2>'
                                 f'<p class="zsub"><a href="{ссылка}">Открыть весь раздел</a></p>'
                                 + self.лента(набор))
            if episode_html:
                куски.append(episode_html)
            return self.оболочка(
                f'<div class="zpage">{_склеить(куски)}</div>',
                f"{self.имя} — кинопортал", "/", актив="/",
                описание=f"{self.имя}: фильмы, сериалы и анимация.",
                сверху="<span>Обзор каталога</span>")

        занято: set = set()
        занятые_имена: set = set()
        занятые_франшизы: set = set()

        def свежесть(з: dict) -> str:
            return дата_поступления(з)

        def выбрать(вид: str | None, ключ, сколько: int = 12,
                    пул: int | None = None, условие=None) -> list:
            подходящие = [з for з in self.д.items
                          if (вид is None or з.get("kind") == вид)
                          and self.в_области_главной(з)
                          and (условие is None or условие(з))]
            if пул:
                подходящие = sorted(подходящие, key=свежесть, reverse=True)[:пул]
            отобрано = []
            for з in sorted(подходящие, key=ключ, reverse=True):
                if з["slug"] in занято:
                    continue
                norm = _нормализовать_для_дедупа(з.get("title") or "")
                if norm and norm in занятые_имена:
                    continue
                # Одна карточка на франшизу. «Братик-братик: Финал»,
                # «Братик-братик 3» и «Братик-братик 2» занимали три места из
                # двенадцати — четверть полки на одну и ту же вещь. Остаётся
                # самая свежая часть: набор уже отсортирован нужным ключом.
                фр = франшиза(з.get("title") or "")
                if фр and фр in занятые_франшизы:
                    continue
                занято.add(з["slug"])
                if norm:
                    занятые_имена.add(norm)
                if фр:
                    занятые_франшизы.add(фр)
                отобрано.append(з)
                if len(отобрано) >= сколько:
                    break
            return отобрано

        def есть_серии(з: dict) -> bool:
            return bool(self.деталь(з["slug"]).get("seasons"))

        def есть_источник(з: dict) -> bool:
            return состояние_плеера(self.деталь(з["slug"]))[0] == "playable"

        def поступление(з: dict) -> bool:
            """Годно для полки поступлений: есть и дата поступления, и видео."""
            return bool(дата_поступления(з)) and есть_источник(з)

        # Popular shelves: WEEKLY_SNAPSHOT only — never request-time recompute.
        # New-films / new-eps keep their own freshness contracts (published_at).
        weekly = _popular_weekly_snapshot()
        # Редакционная полка выбирается ПЕРВОЙ, и её слаги сразу считаются
        # занятыми: иначе та же вещь встанет и в полку недели, и в
        # поступления, а вторая полка будет выглядеть копией первой.
        полка_html, полка_слаги = self._полка_главной()
        занято |= полка_слаги
        # Недельные полки тоже подчинены области главной: полка с заголовком
        # «Фильмы недели», в которой лежит аниме, — это неверная подпись, а не
        # широкая выборка. Полка анимации на главной не показывается вовсе;
        # её раздел — «/animation/», и ссылка на него есть во входах и в меню.
        # Отбор по категории передаётся В полку, а не применяется после неё:
        # иначе полка теряет карточки уже после нарезки по двенадцать.
        pop_films = _из_weekly_полки(self.д, weekly, "pop-films",
                                     отбор=self.в_области_главной,
                                     предел=self.ПОЛКА_НЕДЕЛИ,
                                     подробности=self.п)
        pop_series = _из_weekly_полки(self.д, weekly, "pop-series",
                                      отбор=self.в_области_главной,
                                      предел=self.ПОЛКА_НЕДЕЛИ,
                                      подробности=self.п)
        pop_anim = ([] if self.КАТЕГОРИЙНЫЕ_РАЗДЕЛЫ
                    else _из_weekly_полки(self.д, weekly, "pop-anim",
                                          предел=self.ПОЛКА_НЕДЕЛИ,
                                          подробности=self.п))
        pop_films = [з for з in pop_films if з["slug"] not in полка_слаги]
        pop_series = [з for з in pop_series if з["slug"] not in полка_слаги]
        pop_anim = [з for з in pop_anim if з["slug"] not in полка_слаги]
        episode_rows = load_rows(
            self, sys.modules[__name__], 'zona-01',
            [з for з in episode_catalog if з['slug'] not in полка_слаги])
        episode_html = render_rows(episode_rows, style='zona')
        episode_slugs = {row['slug'] for row in episode_rows}
        занято.update(episode_slugs)
        pop_films = [з for з in pop_films if з['slug'] not in episode_slugs]
        pop_series = [з for з in pop_series if з['slug'] not in episode_slugs]
        pop_anim = [з for з in pop_anim if з['slug'] not in episode_slugs]
        for з in pop_films + pop_series + pop_anim:
            занято.add(з["slug"])

        коллекции_html = ""
        снимок = Снимок.получить(self.д, self.п)
        if КОЛЛЕКЦИИ is not None and снимок is not None:
            кол_карточки = []
            подписи = {
                "recently_added": "Недавно добавленные",
                "recent": "Недавно добавленные",
                "recently_added_movies": "Недавно добавленные фильмы",
                "new-movies": "Новые фильмы",
                "new_movie_releases": "Премьеры фильмов",
                "new_series_releases": "Новые сериалы",
                "new_episodes": "Недавно добавленные сериалы",
                "top-rated": "С высокими оценками",
                "top_rated": "С высокими оценками",
                "current_season": "Этого года",
                "video_available": "С видео",
                "genre_comedy": "Комедии",
                "genre_drama": "Драмы",
                "genre_thriller": "Триллеры",
                "genre_animation": "Анимация",
                "popular": "С высокими оценками",
            }
            # T286: «С видео» убрана из реестра Zona — блок главной держит прежние
            # семь подборок, а не подставляет восьмую на освободившееся место.
            # Редакционные подборки идут ПЕРВЫМИ: их состав выбран человеком
            # под названную потребность читателя. Обратный порядок выдавал бы
            # алгоритмический список за редакционный выбор.
            for подборка_ред in РУЧНЫЕ_ПОДБОРКИ.values():
                if getattr(подборка_ред, "home_rail", False):
                    # Эта подборка уже стоит первой лентой главной крупными
                    # постерами: плашка ниже была бы тем же составом второй раз.
                    continue
                состав_ред = КОЛЛЕКЦИИ.разрешить_ручную(подборка_ред, снимок)
                работы_ред = состав_ред.get("works") or []
                if not работы_ред:
                    continue
                кол_карточки.append(self.визитка_подборки(
                    адрес=подборка_ред.canonical_path,
                    название=подборка_ред.title,
                    польза=польза_подборки(подборка_ред.intro),
                    всего=len(работы_ред),
                    постеры=[(с.get("запись") or {}).get("poster") or ""
                             for с in работы_ред]))
            полка = 7 if СЕМЕЙСТВО == "zona" else 8
            for спец in КОЛЛЕКЦИИ.спецификации(СЕМЕЙСТВО)[:полка]:
                if not спец.доступна:
                    continue
                данные = КОЛЛЕКЦИИ.разрешить(спец.collection_key, снимок, СЕМЕЙСТВО,
                                             предел=1)
                if данные is None or not данные.items:
                    continue
                ключ = getattr(спец, "collection_key", "") or ""
                подпись = подписи.get(ключ) or (данные.title or "Подборка")
                if подпись == данные.title:
                    подпись = "Подборка"
                полные = КОЛЛЕКЦИИ.разрешить(спец.collection_key, снимок,
                                             СЕМЕЙСТВО, предел=3)
                кол_карточки.append(self.визитка_подборки(
                    адрес=спец.canonical_path,
                    название=данные.title,
                    польза=польза_подборки(данные.description or подпись),
                    всего=getattr(данные, "total", 0)
                    or len(getattr(полные, "items", []) or []),
                    постеры=[(getattr(к, "poster", "") or "")
                             for к in (getattr(полные, "items", []) or [])]))
            if кол_карточки:
                коллекции_html = (
                    '<section class="zsec"><div class="zsec__h">'
                    "<h2>Подборки</h2>"
                    '<a href="/collections/">Весь раздел</a></div>'
                    f'<div class="zcl zcl--home">{"".join(кол_карточки)}</div>'
                    "</section>")
        жанр_навигация = "".join(
            f'<a href="/catalog/{запрос_строкой({"genre": код})}">{html.escape(имя)}</a>'
            for код, имя in ZONA_GENRE_NAV)
        блок_жанров = (
            f'<section class="zgenres" aria-labelledby="zgenres-h">'
            f'<h2 class="zgenres__h" id="zgenres-h">Жанры</h2>'
            f'<nav class="zgenres__nav" data-scroller="chips" '
            f'aria-label="Жанры">{жанр_навигация}</nav>'
            f'<p class="zsub"><a href="/catalog/">Все жанры</a></p>'
            f'</section>') if жанр_навигация else ""

        # Герой выбирается ПЕРВЫМ и занимает свои слаги: полки ниже тогда
        # берут из остатка, и одна запись не стоит дважды на одной странице.
        # Раньше порядок был обратный, герой в `занято` не смотрел, и восемь
        # слайдов дословно повторяли первые восемь карточек блока под ними.
        hero_слайды = self._герои_кандидаты(weekly, pop_films, pop_series,
                                            pop_anim, занято=занято)
        for з in hero_слайды:
            занято.add(з["slug"])
            имя_г = _нормализовать_для_дедупа(з.get("title") or "")
            if имя_г:
                занятые_имена.add(имя_г)

        added_events = []
        for з in выбрать(None, свежесть, сколько=self.ПОСТУПЛЕНИЙ,
                         условие=поступление):
            raw = дата_поступления(з)
            if not raw:
                continue
            # Формат обязан быть полным: «%H» без «%M» обрезает время до часа
            # ещё до вёрстки, и визуальная проверка такую обрезку не видит —
            # элемент не переполнен, в нём просто лежит неполный текст.
            def _дата(строка: str) -> str:
                """ISO-дата в том же точечном формате, что и дата со временем."""
                части = строка[:10].split("-")
                if len(части) == 3 and all(ч.isdigit() for ч in части):
                    год, месяц, день = части
                    return f"{день}.{месяц}.{год}"
                return строка[:10]

            if "T" in raw:
                try:
                    from datetime import datetime as _dt
                    d = _dt.fromisoformat(raw.replace("Z", "+00:00"))
                    when = d.strftime("%d.%m.%Y, %H:%M")
                    precision = "datetime"
                except ValueError:
                    when = _дата(raw)
                    precision = "date-only"
            else:
                when = _дата(raw)
                precision = "date-only"
            added_events.append((з, when, precision))

        шаблон = ЗОНА_ШАБЛОНЫ[ЗОНА_ШАБЛОН]

        # Герой: три подачи одного и того же набора кандидатов. Ни одна не
        # добавляет и не убирает H1 — он всегда ровно один и всегда осмыслен.
        режим_героя = шаблон.get("герой", "slider")
        if режим_героя == "compact":
            герой_html = self.герой_карусель([])
        else:
            # `single` больше не значит «один огромный слайд»: лента и при
            # одном кандидате остаётся лентой, просто короткой.
            герой_html = self.герой_карусель(hero_слайды)
        # Ширина героя — тоже композиция: вынос за колонку содержимого меняет
        # первый экран сильнее, чем любая перестановка блоков ниже. Класс
        # добавляется правкой уже собранной секции, а не вторым её вариантом:
        # двух отрисовок героя быть не должно.
        if шаблон.get("ширина") == "full":
            герой_html = герой_html.replace('<section class="zhero ',
                                            '<section class="zhero zhero--full ', 1)

        # Неделя: вкладки или три ленты подряд. Второе — другой ритм
        # навигации, а не другой цвет: видно все три полки сразу.
        if шаблон.get("недельный") == "stacked":
            неделя_html = "".join(
                self.секция(ключ, титул, ссылка, набор, "")
                for ключ, титул, ссылка, набор in (
                    ("wk-films", "Фильмы", "/movies/", pop_films),
                    ("wk-series", "Сериалы", "/series/", pop_series),
                    ("wk-anim", "Анимация", "/animation/", pop_anim)))
        else:
            неделя_html = self.недельный_блок(pop_films, pop_series, pop_anim, weekly)

        # Поступления: строки с датой или горизонтальная лента карточек.
        if шаблон.get("новое") == "rail" and added_events:
            новое_html = self.секция("added", "Новое в каталоге",
                                     "/new/?mode=added",
                                     [з for з, _, _ in added_events], "")
        else:
            новое_html = self.новое_в_каталоге(added_events)

        # Плотная сетка новинок. Берётся из уже занятых наборов НЕ повторно:
        # `выбрать` ведёт общий набор занятых слагов, поэтому одна запись не
        # окажется в двух блоках одной страницы.
        сколько_свежих = int(шаблон.get("свежие") or 0)
        свежая_сетка = ""
        if сколько_свежих:
            набор = выбрать(None, свежесть, сколько=сколько_свежих)
            if набор:
                свежая_сетка = (
                    '<section class="zsec" aria-labelledby="zfresh-h">'
                    '<div class="zsec__h"><h2 id="zfresh-h">Новинки каталога</h2>'
                    '<a href="/new/?mode=added">Весь раздел</a></div>'
                    f'{self.плитки(набор, полные_ряды=True)}</section>')

        блоки = {
            "episodes": episode_html,
            "hero": герой_html,
            "weekly": неделя_html,
            "added": новое_html,
            "kinds": self.входы_видов(),
            "genres": блок_жанров,
            "collections": коллекции_html,
            "fresh": свежая_сетка,
        }
        блоки["seo"] = (
            '<section class="zsec zsec--seo" aria-labelledby="zona-seo-h">'
            '<h2 id="zona-seo-h">Смотреть кино и сериалы на Zona</h2>'
            f'<p>{html.escape(self.имя)} — фильмы, сериалы и анимация. '
            "На главной — редакционный акцент, высокие оценки текущей недели, "
            "недавние поступления в каталог и входы в разделы; "
            "полный список открывается в каталоге с фильтрами по виду, жанру, году "
            "и стране.</p>"
            "<p>Разделы "
            '<a href="/movies/">Фильмы</a>, '
            '<a href="/series/">Сериалы</a>, '
            '<a href="/animation/">Анимация</a> и '
            '<a href="/doramas/">Дорамы</a> '
            "помогают сузить выбор. Жанровые кнопки ведут в каталог с уже выбранным "
            "фильтром. В "
            '<a href="/collections/">подборках</a> '
            "собраны фильмы и сериалы на одну тему, а "
            '<a href="/search/">поиск</a> '
            "находит название по русскому или оригинальному написанию.</p>"
            "<p>Страница названия показывает описание (когда оно есть), "
            "оценки, список серий и плеер. Если видео для серии ещё недоступно, "
            "это отмечено явно — без пустого плеера.</p>"
            '<button type="button" class="zsec--seo__more" data-seo-more>Читать далее</button>'
            "</section>"
            '<script>(function(){var b=document.querySelector("[data-seo-more]");if(!b)return;'
            'b.addEventListener("click",function(){var s=b.closest(".zsec--seo");if(!s)return;'
            's.classList.add("is-open");b.hidden=true;});})();</script>')
        блоки["rail1"] = полка_html
        блоки["announce"] = self._блок_анонсов()
        if полка_html:
            # Поручение владельца 27.10: первой и самой заметной идёт лента
            # востребованных сериалов, затем визуальные подборки, затем фильмы
            # недели, и только потом поступления каталога. Герой при наличии
            # полки не рисуется: два крупных блока подряд спорят за первый
            # экран. Порядок закреплён здесь, а не в букве шаблона, потому что
            # он включается НАЛИЧИЕМ редакционной полки, а не профилем.
            порядок = ("rail1", "collections", "weekly", "announce", "added",
                       "kinds", "genres", "fresh", "seo")
        else:
            порядок = шаблон["порядок"]
        порядок = list(порядок)
        порядок.insert(порядок.index('weekly') + 1 if 'weekly' in порядок else 1, 'episodes')
        куски = [блоки[имя] for имя in порядок
                 if имя in блоки and блоки[имя]]
        if полка_html:
            # H1 главной давала панель героя, а с редакционной полкой герой не
            # рисуется: заголовком первого уровня становилось название
            # подборки, и главная перестала называть предмет сайта. Текст
            # взят из поля семейства, которое назвала линия SEO, — здесь он
            # не придумывается. Заголовок скрыт визуально: первым видимым
            # блоком остаётся полка (поручение владельца 27.10), строки
            # текста над ней появиться не должно.
            куски.insert(0, f'<h1 class="vh">'
                            f'{html.escape(self.се["h1 главной"])}</h1>')
        return self.оболочка(
            _склеить(куски),
            f"{self.имя} — кинопортал", "/", актив="/",
            # Описание пересказывает видимый блок «Смотреть кино и сериалы»
            # выше, а не придумывает: 40 знаков без единого факта поисковик
            # заменял своим отрывком (META_THIN, отчёт 13.10, главная — 240
            # входов и просмотров за неделю).
            описание=(f"{self.имя}: фильмы, сериалы и анимация — высокие оценки "
                      "недели, недавние поступления и каталог с фильтрами "
                      "по виду, жанру, году и стране."),
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
        # Page size stays 60: collection_contract.разрешить defaults to 60 and
        # the shared handler does not pass НА_СТРАНИЦЕ_1_1; changing only the
        # view would desync pager UI from the sliced items.
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
        count_line = _склонение(int(данные.total or 0), "название", "названия", "названий")
        звенья = [("/", self.имя), ("/collections/", "Подборки"), ("", данные.title)]
        # Подборка — не раздел: /collection/genre_animation/ и /animation/ носили
        # один title «Анимация — …» и H1 «Анимация» при разных списках (T255).
        # Слово «Подборка» и её название из контракта различают их.
        название = str(данные.title or "")
        заголовок = (название if not название or название.startswith("Подборка")
                     else f"Подборка «{название}»")
        тело = (f'<div class="zpage"><h1 class="zh">{html.escape(заголовок)}</h1>'
                f'<p class="zsub">{html.escape(данные.description)} · '
                f'{html.escape(count_line)} · '
                f'страница {данные.page} из {всего_страниц}</p>'
                + (self.плитки([к.raw for к in данные.items]) if данные.items else
                   f'<div class="zempty"><b>{html.escape(данные.title)}: пока пусто</b>'
                   "<p>В каталоге под эту коллекцию не попала ни одна "
                   "запись.</p></div>")
                + листалка + "</div>")
        # Страница N>1 коллекции — self-canonical и номер в заголовке (п.3).
        хвост = f" — страница {данные.page}" if данные.page > 1 else ""
        return self.оболочка(тело, f"{заголовок}{хвост} — {self.имя}",
                             данные.canonical_path + (f"?page={данные.page}" if данные.page > 1 else ""),
                             актив="/collections/",
                             описание=(данные.description or "") + хвост,
                             крошки=self.крошки(звенья),
                             разметка=self.schema_крошек(звенья))

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
                    "<p>Подборки сейчас недоступны.</p></div>")
        карточки = []
        занятые_постеры: set[str] = set()
        сигнатуры: list[tuple[str, ...]] = []
        # Редакционные подборки — отдельными карточками и ПЕРВЫМИ. Плитка
        # коллажа здесь считается по постерам состава, поэтому карточка
        # добавляется своей разметкой: у ручной подборки состав короткий, и
        # требование «четыре разных постера» для неё не обязательно.
        for подборка_ред in РУЧНЫЕ_ПОДБОРКИ.values():
            состав_ред = КОЛЛЕКЦИИ.разрешить_ручную(подборка_ред, снимок)
            работы_ред = состав_ред.get("works") or []
            if not работы_ред:
                continue
            карточки.append(self.визитка_подборки(
                адрес=подборка_ред.canonical_path,
                название=подборка_ред.title,
                польза=польза_подборки(подборка_ред.intro),
                всего=len(работы_ред),
                постеры=[(с.get("запись") or {}).get("poster") or ""
                         for с in работы_ред],
                срочно="eager"))
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
            ключ_кол = getattr(спец, "collection_key", "") or ""
            подписи_хаб = {
                "recently_added": "Недавно добавленные",
                "recently_added_movies": "Недавно добавленные фильмы",
                "new_movie_releases": "Премьеры фильмов",
                "new_series_releases": "Новые сериалы",
                "new_episodes": "Сериалы, недавно добавленные в каталог",
                "top_rated": "Фильмы и сериалы с высокими оценками",
                "current_season": "Этого года",
                "video_available": "С подтверждённым видео",
                "genre_comedy": "Комедии",
                "genre_drama": "Драмы",
                "genre_thriller": "Триллеры",
                "genre_animation": "Анимация",
            }
            подпись_хаб = подписи_хаб.get(ключ_кол) or html.escape(
                (коллекция.description or "").split(".")[0][:80]
                or "Подборка")
            total = getattr(коллекция, "total", None)
            if total is None:
                total = len(коллекция.items or [])
            count_txt = _склонение(int(total), "название", "названия", "названий")
            карточки.append(
                f'<a class="zhub__c" data-testid="collection-card" '
                f'href="{html.escape(спец.canonical_path)}">'
                f'<span class="zhub__g">{обложки}</span>'
                f'<span class="zhub__t">{html.escape(коллекция.title)}</span>'
                f'<span class="zhub__m">{подпись_хаб}</span>'
                f'<span class="zhub__d">{html.escape(count_txt)}</span>'
                f'</a>')
        if not карточки:
            return ('<div class="zempty"><b>Подборок пока нет</b>'
                    "<p>Ни одна коллекция не набрала записей в каталоге. "
                    "Наполнять их похожими тайтлами нельзя: подборка без источника — "
                    "это выдумка.</p></div>")
        return (f'<div class="zcl" data-testid="collection-grid" '
                f'data-hub-count="{len(карточки)}">{"".join(карточки)}</div>')



    #: Показ обложки визитки: три кадра в ряд внутри карточки сетки.
    ПОКАЗ_ВИЗИТКИ = "(min-width:1024px) 150px, (min-width:640px) 160px, 120px"

    def визитка_подборки(self, *, адрес: str, название: str, польза: str,
                         всего: int, постеры, срочно: str = "") -> str:
        """Визуальная карточка подборки: обложки состава, название, польза, счёт.

        Обложки берутся ИЗ СОСТАВА подборки — первые три работы. Выдуманной
        картинки у карточки быть не может: нет постеров — нет и полосы обложек,
        остаётся текстовая часть, и это видно.
        """
        кадры = "".join(
            f'<span class="zcl__p"><img src="{html.escape(_адрес_постера(п) or "")}"'
            f'{_набор_постера(_адрес_постера(п), self.ПОКАЗ_ВИЗИТКИ)}'
            f' alt="" loading="{"eager" if срочно else "lazy"}" decoding="async"'
            f' width="160" height="240"></span>'
            for п in list(постеры)[:3] if п)
        счёт = _склонение(int(всего or 0), "название", "названия", "названий")
        обложка = (f'<span class="zcl__art">{кадры}'
                   f'<span class="zcl__n">{html.escape(счёт)}</span></span>'
                   if кадры else "")
        подпись = (f'<span class="zcl__d">{html.escape(польза)}</span>'
                   if польза else "")
        ключ_блока = str(адрес).strip("/").split("/")[-1]
        return (f'<a class="zcl__c" href="{html.escape(адрес)}"'
                f' data-block-key="card:{html.escape(ключ_блока)}">{обложка}'
                f'<span class="zcl__b">'
                f'<span class="zcl__t">{html.escape(название)}</span>'
                f'{подпись}</span>'
                f'<span class="zcl__go">Открыть подборку →</span></a>')

    def _полка_главной(self) -> tuple:
        """Первая лента главной: редакционная подборка с пометкой `home_rail`.

        Возвращает ПАРУ: разметку и множество слагов полки. Слаги нужны
        вызывающему: без них та же вещь попадала бы и в полку недели, и в
        поступления, то есть стояла бы на главной дважды.

        Это ответ на вопрос «что посмотреть», а не пересказ каталога: состав и
        порядок выбраны человеком и записаны в файле подборок с постоянными id.
        Нет такой подборки или её состав пуст — ленты нет вовсе, и главная
        собирается прежним порядком: подставлять на это место алгоритмическую
        выборку значило бы выдавать её за редакционный выбор.
        """
        if КОЛЛЕКЦИИ is None or not РУЧНЫЕ_ПОДБОРКИ:
            return "", set()
        полка = next((п for п in РУЧНЫЕ_ПОДБОРКИ.values()
                      if getattr(п, "home_rail", False)), None)
        if полка is None:
            return "", set()
        снимок = Снимок.получить(self.д, self.п)
        if снимок is None:
            return "", set()
        состав = КОЛЛЕКЦИИ.разрешить_ручную(полка, снимок)
        работы = состав.get("works") or []
        if not работы:
            return "", set()
        карточки, слаги = [], set()
        for место, с in enumerate(работы):
            запись = с.get("запись") or {}
            слаг = str(запись.get("slug") or "")
            if not слаг:
                continue
            слаги.add(слаг)
            постер = _адрес_постера(str(запись.get("poster") or ""))
            вид = "сериал" if (запись.get("kind") or "") == "Сериал" else ""
            подпись = " · ".join(x for x in (str(запись.get("year") or ""), вид) if x)
            срочно = "high" if место < 3 else ""
            # Приоритет и режим загрузки считаются ДО f-строки:
            # обратная косая внутри её выражения не разбирается
            # в Python 3.10, и рантайм не поднялся бы вовсе.
            приоритет = ' fetchpriority="high"' if срочно else ""
            загрузка = "eager" if срочно else "lazy"
            картинка = (
                f'<img src="{html.escape(постер or "")}"'
                f'{_набор_постера(постер, ПОКАЗ_ПОЛКА)}'
                f' alt="{html.escape(str(запись.get("title") or ""))}"'
                f' width="300" height="450" decoding="async"'
                f' loading="{загрузка}"{приоритет}>'
                if постер else "")
            карточки.append(
                f'<a class="zb" href="/title/{html.escape(слаг)}/">'
                f'<span class="zb__img">{картинка}</span>'
                f'<span class="zb__t">{html.escape(str(запись.get("title") or ""))}</span>'
                f'<span class="zb__m">{html.escape(подпись)}</span></a>')
        if not карточки:
            return "", set()
        польза = польза_подборки(полка.intro)
        return (f'<section class="zr1" aria-labelledby="zr1-h"'
                f' data-block-key="rail:{html.escape(полка.key)}">'
                f'<div class="zr1__h"><h2 id="zr1-h">{html.escape(полка.title)}</h2>'
                f'<a href="{html.escape(полка.canonical_path)}">Вся подборка</a></div>'
                f'<p class="zr1__sub">{html.escape(польза)}</p>'
                f'<div class="zr1__track" data-scroller="rail1">'
                f'{"".join(карточки)}</div></section>'), слаги


    #: Сколько анонсов показывать на главной. Остальные остаются в файле:
    #: блок главной — витрина ожидания, а не полный перечень.
    АНОНСОВ_НА_ГЛАВНОЙ = 6

    def _блок_анонсов(self) -> str:
        """«Ждём премьеру»: объявленные релизы без обещания просмотра.

        Позиция уходит из блока в двух случаях, и оба проверяются здесь, а не
        на глаз: работа уже доступна в каталоге (`catalog.playable`) — значит
        это больше не ожидание, — или все объявленные даты уже прошли. Второе
        важно отдельно: просроченный состав нельзя продолжать показывать как
        ожидаемое, а подставлять вместо него случайные карточки нельзя тем
        более. Если после отсева не осталось ничего, блока нет вовсе.
        """
        данные = АНОНСЫ
        позиции = list(данные.get("items") or [])
        if not позиции:
            return ""
        сегодня = _часы_datetime().date().isoformat()
        годные = []
        for п in sorted(позиции, key=lambda з: int(з.get("order") or 0)):
            каталог = п.get("catalog") or {}
            if каталог.get("playable"):
                continue
            выпуск = п.get("release") or {}
            даты = [str(выпуск.get("date") or "")]
            второй = выпуск.get("second") or {}
            if второй.get("date"):
                даты.append(str(второй["date"]))
            if not any(д >= сегодня for д in даты if д):
                continue
            годные.append(п)
            if len(годные) >= self.АНОНСОВ_НА_ГЛАВНОЙ:
                break
        if not годные:
            return ""
        карточки = []
        for п in годные:
            выпуск = п.get("release") or {}
            когда = _дата_анонса(str(выпуск.get("date") or ""))
            подпись = " · ".join(x for x in (str(выпуск.get("kind") or ""),
                                             str(выпуск.get("territory") or "")) if x)
            второй = выпуск.get("second") or {}
            ещё = ""
            if второй.get("date"):
                ещё = (f'<span class="zann__more">затем '
                       f'{html.escape(_дата_анонса(str(второй["date"])))} · '
                       f'{html.escape(str(второй.get("territory") or ""))}</span>')
            источник = str(п.get("source") or "")
            ссылка = ""
            if источник.startswith("https://") or источник.startswith("http://"):
                ссылка = (f'<a class="zann__src" href="{html.escape(источник)}" '
                          'rel="nofollow noopener" target="_blank">'
                          "официальный анонс →</a>")
            карточки.append(
                f'<div class="zann__c">'
                f'<span class="zann__d">{html.escape(когда)}</span>'
                f'<span class="zann__k">{html.escape(подпись)}</span>{ещё}'
                f'<span class="zann__t">{html.escape(str(п.get("name") or ""))}</span>'
                f'<span class="zann__r">{html.escape(str(п.get("reason") or ""))}</span>'
                f"{ссылка}</div>")
        заголовок = html.escape(str(данные.get("title") or "Ждём премьеру"))
        вступление = html.escape(str(данные.get("intro") or ""))
        return (f'<section class="zann" aria-labelledby="zann-h" '
                f'data-block-key="announce" '
                f'data-announcements="{len(карточки)}">'
                f'<div class="zsec__h"><h2 id="zann-h">{заголовок}</h2></div>'
                f'<p class="zann__sub">{вступление}</p>'
                f'<div class="zann__g">{"".join(карточки)}</div></section>')

    def _полоса_подборок_раздела(self, разд: str, стр: int = 1) -> str:
        """Редакционные подборки ЭТОГО раздела — ссылкой с его страницы.

        Подборка, на которую ведёт только главная, с раздела недостижима.
        Раздел — та страница, где читатель уже выбрал направление, и подборка
        его направления здесь уместнее всего.

        Показывается только на первой странице выдачи: на второй это был бы
        повтор без повода. Пустой состав не рисуется — обещать подборку,
        которой каталог не отдаёт, нельзя.
        """
        if стр > 1 or КОЛЛЕКЦИИ is None or not РУЧНЫЕ_ПОДБОРКИ:
            return ""
        ключ_раздела = (разд or "").strip("/")
        if ключ_раздела == "catalog":
            # `/catalog/` — самая посещаемая страница разделов: на animedia.icu
            # 1252 просмотра за 20–26.10 против 414 у главной (замер 27.10), а
            # ведёт она только на хаб. Каталог — родитель всех разделов,
            # поэтому «подборки этого раздела» для него означает ВСЕ подборки,
            # а не пустоту по несовпадению ключа.
            свои = list(РУЧНЫЕ_ПОДБОРКИ.values())
            заголовок, метка = "Редакционные подборки", "catalog"
        else:
            свои = [п for п in РУЧНЫЕ_ПОДБОРКИ.values()
                    if (п.section or "").strip("/") == ключ_раздела]
            заголовок, метка = "Подборки этого раздела", "section"
        if not свои:
            return ""
        снимок = Снимок.получить(self.д, self.п)
        if снимок is None:
            return ""
        карточки = []
        for подборка in свои:
            состав = КОЛЛЕКЦИИ.разрешить_ручную(подборка, снимок)
            работы = состав.get("works") or []
            if not работы:
                continue
            карточки.append(self.визитка_подборки(
                адрес=подборка.canonical_path,
                название=подборка.title,
                польза=польза_подборки(подборка.intro),
                всего=len(работы),
                постеры=[(с.get("запись") or {}).get("poster") or ""
                         for с in работы]))
        if not карточки:
            return ""
        return (f'<section class="zsec" data-collections="{метка}">'
                f'<div class="zsec__h"><h2>{заголовок}</h2>'
                '<a href="/collections/">Все подборки</a></div>'
                f'<div class="zcl">{"".join(карточки)}</div></section>')

    def _ссылки_жанров(self, разд: str, есть_условия: bool, стр: int) -> str:
        """Ссылки на разделы жанров с голого /catalog/ (T034).

        Замер 13.10: со страницы /catalog/ Zona не вело ни одной ссылки на
        раздел жанра (фильтр — выпадающий список без ссылок); вход был только
        с главной (6) и с карточек (3). Набор и адреса — те же, что в карте
        сайта (разделы_жанров: главный код имени), порядок — по составу.
        Только первая страница без условий: выборки и страницы пагинации
        ссылками не дублируются.
        """
        if разд != "/catalog" or есть_условия or стр != 1:
            return ""
        разделы = sorted(разделы_жанров(self.индекс), key=lambda р: (-р[2], р[1]))
        if not разделы:
            return ""
        # Разметка — та же, что у блока «Жанры» на главной (.zgenres): его
        # ссылка «Все жанры» ведёт сюда, и здесь жанры теперь действительно все.
        ссылки = "".join(
            f'<a href="/catalog/{html.escape(запрос_строкой({"genre": код}))}">'
            f'{html.escape(имя[:1].upper() + имя[1:])}</a>'
            for код, имя, _ in разделы)
        return (f'<section class="zgenres" data-testid="catalog-genres" '
                f'aria-labelledby="zgenres-cat-h">'
                f'<h2 class="zgenres__h" id="zgenres-cat-h">Жанры</h2>'
                f'<nav class="zgenres__nav" data-scroller="chips" '
                f'aria-label="Жанры каталога">{ссылки}</nav></section>')

    def список(self, разд: str, зпр: dict) -> str:
        имена = {
            "/catalog": "Каталог",
            "/new": "Новинки",
            "/collections": "Подборки",
            "/movies": "Фильмы",
            "/series": "Сериалы",
            "/animation": "Анимация",
            "/doramas": "Дорамы",
        }
        титул = имена.get(разд, "Каталог")
        if разд == "/collections":
            хаб = self.хаб_коллекций()
            m_count = re.search(r'data-hub-count="(\d+)"', хаб)
            hub_n = int(m_count.group(1)) if m_count else 0
            # Описание хаба несёт факт страницы — число подборок, то же, что в
            # видимой строке (T127; образец T036). Было «Подборки на Zona
            # Cinema.» без единого факта при видимых «12 подборок».
            описание_хаба = f"Подборки на {self.имя}."
            if hub_n:
                число_подборок = _склонение(hub_n, "подборка", "подборки", "подборок")
                sub = (f'<p class="zsub">Тематические подборки · '
                       f'{html.escape(число_подборок)}'
                       f'.</p>')
                описание_хаба = (f"Подборки на {self.имя}: {число_подборок} — "
                                 f"тематические подборки с числом названий в каждой.")
            else:
                sub = '<p class="zsub">Тематические подборки.</p>'
            тело = (f'<div class="zpage" data-testid="page-container">'
                    f'<h1 class="zh" data-testid="catalog-heading" id="catalog-h1">'
                    f'{html.escape(титул)}</h1>'
                    f'{sub}'
                    + хаб + "</div>")
            return self.оболочка(тело, f"{титул} — {self.имя}", "/collections/",
                                 актив="/collections/",
                                 описание=описание_хаба)
        набор, выбрано = отбор(self.д, self.индекс, зпр, разд)
        # Expose active filters to оболочка so rail genre links preserve state.
        self._активные_фильтры = {
            k: v for k, v in выбрано.items()
            if v and not str(k).startswith("_")
        }
        if выбрано.get("_unknown"):
            тело = (f'<div class="zpage" data-testid="page-container">'
                    f'<h1 class="zh" id="catalog-h1">Некорректный фильтр</h1>'
                    f'<p class="zsub">Параметр не распознан. '
                    f'<a href="{разд}/">Открыть раздел без фильтра</a></p></div>')
            # Нераспознанный фильтр — не страница (SEO_KNOWLEDGE_PACK §3 п.3–4).
            self._код_ответа = 404
            return self.оболочка(тело, f"Некорректный фильтр — {self.имя}",
                                 разд + "/", код=404)
        # B13: mode-specific H1 / definition for /new/.
        new_mode = выбрано.get("mode") if разд == "/new" else None
        mode_tabs_html = ""
        mode_def = ""
        if разд == "/new":
            доступные = _доступные_режимы_new(self.д)
            if new_mode in NEW_MODE_LABELS:
                титул = NEW_MODE_LABELS[new_mode]
            mode_def = NEW_MODE_DEFS.get(new_mode or "", "")
            if len(доступные) > 1:
                tabs = []
                for m in доступные:
                    href = "/new/" + запрос_строкой(
                        {k: v for k, v in выбрано.items() if k != "mode"},
                        mode=m, page=None)
                    cur = ' aria-current="page"' if m == new_mode else ""
                    tabs.append(
                        f'<a class="zfilt-chip" href="{href}"{cur} '
                        f'data-new-mode="{m}">{html.escape(NEW_MODE_LABELS[m])}</a>')
                mode_tabs_html = (
                    f'<nav class="zfilt-bar__group" data-testid="new-mode-tabs" '
                    f'aria-label="Режимы новинок">{"".join(tabs)}</nav>')
        # Выбор раздела в «Новинках»: Все / Фильмы / Сериалы / Анимация /
        # Дорамы. По умолчанию «Все» — то есть параметра нет вовсе, а не есть
        # со значением «все»: пустой фильтр и фильтр «всё» дали бы две разные
        # ссылки на одну выборку.
        #
        # Выбор ездит в том же `kind`, которым размечены разделы, поэтому он
        # сам собой складывается с жанром, страной, годом и сортировкой и
        # сохраняется при переходе страниц: `запрос_строкой` переносит
        # `выбрано` целиком, а листалка строится из него же.
        cat_tabs_html = ""
        if разд == "/new" and self.КАТЕГОРИЙНЫЕ_РАЗДЕЛЫ:
            выбранная = выбрано.get("kind")
            пункты = [(None, "Все")] + [
                (к, КАТЕГОРИИ_КАТАЛОГА.ярлык(к))
                for к in КАТЕГОРИИ_КАТАЛОГА.КАТЕГОРИИ]
            чипсы = []
            for значение, лейбл in пункты:
                href = "/new/" + запрос_строкой(выбрано, kind=значение, page=None)
                cur = ' aria-current="page"' if выбранная == значение else ""
                чипсы.append(
                    f'<a class="zfilt-chip" href="{href}"{cur} '
                    f'data-new-kind="{значение or "all"}">{html.escape(лейбл)}</a>')
            cat_tabs_html = (
                f'<nav class="zfilt-bar__group" data-testid="new-kind-tabs" '
                f'aria-label="Разделы новинок">{"".join(чипсы)}</nav>')
        raw_page = (зпр.get("page") or ["1"])[0]
        try:
            стр = max(1, int(raw_page or 1))
        except (TypeError, ValueError):
            стр = 1
        всего_страниц = max(1, (len(набор) + НА_СТРАНИЦЕ_1_1 - 1) // НА_СТРАНИЦЕ_1_1) if набор else 1
        if набор and стр > всего_страниц:
            # Router should 404 first; belt-and-suspenders.
            return self.не_найдено(f"{разд}/?page={стр}")
        стр = min(стр, всего_страниц)
        кусок = набор[(стр - 1) * НА_СТРАНИЦЕ_1_1: стр * НА_СТРАНИЦЕ_1_1]

        титул_выборки = титул
        год = выбрано.get("year")
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
        # H1 reflects active year / genre.
        if разд == "/series" and год:
            титул = f"Сериалы {год} года"
        elif разд == "/movies" and год:
            титул = f"Фильмы {год} года"
        elif разд == "/animation" and год:
            титул = f"Анимация {год} года"
        elif разд == "/doramas" and год:
            титул = f"Дорамы {год} года"
        elif разд == "/catalog" and год and жанр_имя:
            титул = f"{жанр_имя.capitalize()} {год} года"
        elif разд == "/catalog" and год:
            титул = f"Каталог {год} года"
        elif жанр_имя:
            титул = жанр_имя.capitalize() if жанр_имя[:1].islower() else жанр_имя
        # Страна выборки — в заголовке (apply-country-title).
        # Прежде у каждой страны были title «Каталог — …» и H1 «Каталог»: дубль
        # заголовков на разных выдачах (аудит страниц 12.10).
        страна_код = выбрано.get("country")
        if страна_код:
            страна_имя = dict(self.индекс.get("country_names") or []).get(страна_код)
            if страна_имя:
                титул = f"{титул}: {страна_имя}"
        # Вид выборки — в заголовке /new/ и /catalog/ (T255, перенос T254). Прежде
        # /new/ и /new/?kind=movie (разные списки) носили один title «Премьеры — …»
        # и H1 «Премьеры» (справка Яндекса title-description-doubles: разнообразить
        # автоматически формируемые заголовки). Подпись — та же, что у чипса;
        # только когда заголовок не заменён жанром/годом/страной.
        подпись_вида = ПОДПИСЬ_РАЗДЕЛА.get(выбрано.get("kind") or "")
        if разд in ("/new", "/catalog") and подпись_вида and титул == титул_выборки:
            титул = f"{титул}: {подпись_вида.lower()}"

        kind_route = разд in ВИД_ПО_МАРШРУТУ or разд in КАТЕГОРИЯ_ПО_МАРШРУТУ
        omit = {"_omit_kind": True} if kind_route else {}

        # B10 compact filter bar: kind chips + year/genre/country/sort selects.
        kind_chips = []
        # Чипсы повторяют разделы витрины: у Zona это четыре категории, иначе —
        # прежние три значения `kind`. Расхождение чипсов с навигацией — это
        # два разных ответа на один вопрос «какие тут разделы».
        if self.КАТЕГОРИЙНЫЕ_РАЗДЕЛЫ:
            чипсы_разделов = tuple(
                (кат, КАТЕГОРИЯ_ПО_МАРШРУТУ_ОБРАТНО[кат])
                for кат in КАТЕГОРИИ_КАТАЛОГА.КАТЕГОРИИ)
        else:
            чипсы_разделов = (("Фильм", "/movies"), ("Сериал", "/series"),
                              ("Мультфильм", "/animation"))
        for к, путь_к in чипсы_разделов:
            q = запрос_строкой({**выбрано, **omit, "kind": None},
                               year=выбрано.get("year"),
                               genre=выбрано.get("genre"),
                               country=выбрано.get("country"),
                               sort=выбрано.get("sort"),
                               page=None, _omit_kind=True)
            cur = ' aria-current="page"' if выбрано.get("kind") == к else ""
            label = ПОДПИСЬ_РАЗДЕЛА.get(к, к)
            kind_chips.append(
                f'<a class="zfilt-chip" href="{путь_к}/{q}"{cur}>{html.escape(label)}</a>')
        if разд == "/catalog":
            kind_chips = [
                f'<a class="zfilt-chip" href="/catalog/'
                f'{запрос_строкой(выбрано, kind=к, page=None, _omit_kind=False)}"'
                f'{ТЕКУЩАЯ_СТРАНИЦА if выбрано.get("kind") == к else ""}>'
                f'{html.escape({"Фильм":"Фильмы","Сериал":"Сериалы","Мультфильм":"Анимация"}.get(к, к))}</a>'
                for к in self.д.kinds
            ]

        # Year facets (full oracle, no [:24] truncate) → select only.
        facet_зпр = {k: ([None] if k == "year" else v) for k, v in зпр.items()}
        if "year" not in facet_зпр:
            facet_зпр["year"] = [None]
        facet_набор, _ = отбор(self.д, self.индекс, facet_зпр, разд)
        from collections import Counter as _Counter
        year_counts = _Counter(
            int(з["year"]) for з in facet_набор
            if isinstance(з.get("year"), int) and 1870 <= int(з["year"]) <= 2100)
        year_list = sorted(year_counts.keys(), reverse=True)
        # P0-05: keep active year visible/removable even when the combo is empty.
        active_year = выбрано.get("year")
        if active_year and str(active_year).isdigit():
            ay = int(active_year)
            if ay not in year_counts:
                year_counts[ay] = 0
                year_list = sorted(year_counts.keys(), reverse=True)
        year_html = ""
        if year_list or active_year:
            all_years_href = разд + "/" + запрос_строкой(
                {**выбрано, **omit}, year=None, page=None)
            opts = [f'<option value="{html.escape(all_years_href)}">Все годы</option>']
            for г in year_list:
                href = разд + "/" + запрос_строкой(
                    {**выбрано, **omit}, year=г, page=None)
                sel = " selected" if str(выбрано.get("year")) == str(г) else ""
                n = year_counts[г]
                opts.append(
                    f'<option value="{html.escape(href)}"{sel}>{г} ({n})</option>')
            year_html = (
                f'<div class="zfilt-bar__group">'
                f'<label class="zfilt-lab" for="zona-year-facet">Год</label>'
                f'<select class="zfilt__year" id="zona-year-facet" '
                f'onchange="if(this.value)location.href=this.value" '
                f'aria-label="Фильтр по году">{"".join(opts)}</select></div>')

        # Genre select from full registry (not button wall).
        genre_html = ""
        genres = list(self.индекс.get("genre_names") or [])
        if genres:
            all_g = разд + "/" + запрос_строкой(
                {**выбрано, **omit}, genre=None, page=None)
            gopts = [f'<option value="{html.escape(all_g)}">Все жанры</option>']
            for код, имя in genres:
                # Служебная метка поставщика — не жанр: в фильтре её нет,
                # кроме случая, когда её раздел сейчас открыт (T185).
                if str(имя).strip().casefold() in _ТЕХНИЧЕСКИЕ_ЖАНРЫ and жанр_код != код:
                    continue
                href = разд + "/" + запрос_строкой(
                    {**выбрано, **omit}, genre=код, page=None)
                sel = " selected" if жанр_код == код else ""
                gopts.append(
                    f'<option value="{html.escape(href)}"{sel}>{html.escape(имя)}</option>')
            genre_html = (
                f'<div class="zfilt-bar__group">'
                f'<label class="zfilt-lab" for="zona-genre-facet">Жанр</label>'
                f'<select id="zona-genre-facet" '
                f'onchange="if(this.value)location.href=this.value" '
                f'aria-label="Фильтр по жанру">{"".join(gopts)}</select></div>')

        # Country select (ASCII translit codes).
        country_html = ""
        countries = list(self.индекс.get("country_names") or [])
        country_код = выбрано.get("country")
        if countries:
            all_c = разд + "/" + запрос_строкой(
                {**выбрано, **omit}, country=None, page=None)
            copts = [f'<option value="{html.escape(all_c)}">Все страны</option>']
            for код, имя in countries:
                href = разд + "/" + запрос_строкой(
                    {**выбрано, **omit}, country=код, page=None)
                sel = " selected" if country_код == код else ""
                copts.append(
                    f'<option value="{html.escape(href)}"{sel}>{html.escape(имя)}</option>')
            country_html = (
                f'<div class="zfilt-bar__group">'
                f'<label class="zfilt-lab" for="zona-country-facet">Страна</label>'
                f'<select id="zona-country-facet" '
                f'onchange="if(this.value)location.href=this.value" '
                f'aria-label="Фильтр по стране">{"".join(copts)}</select></div>')

        sort_opts = (
            ("newest", "Сначала новые"),
            ("recently_added", "Недавно добавленные"),
            ("rating", "По рейтингу"),
            ("title", "По названию"),
        )
        active_sort = выбрано.get("sort") or "newest"
        sopts = []
        for ключ, лейбл in sort_opts:
            href = разд + "/" + запрос_строкой({**выбрано, **omit}, sort=ключ, page=None)
            sel = " selected" if active_sort == ключ else ""
            sopts.append(
                f'<option value="{html.escape(href)}"{sel}>{html.escape(лейбл)}</option>')
        sort_html = (
            f'<div class="zfilt-bar__group">'
            f'<label class="zfilt-lab" for="zona-sort-facet">Сортировка</label>'
            f'<select id="zona-sort-facet" data-testid="catalog-sort" '
            f'onchange="if(this.value)location.href=this.value" '
            f'aria-label="Сортировка">{"".join(sopts)}</select></div>')

        # Служебные ключи отбора («_unknown», «_подразумеваемое») — не условия
        # посетителя: голый /catalog/ говорил о результатах выборки и
        # предлагал «Сбросить» (T039).
        has_active = any(
            v for k, v in выбрано.items()
            if not k.startswith("_") and k != "sort" and v)
        reset_html = (
            f'<a class="zfilt-reset" href="{разд}/">Сбросить</a>' if has_active else "")

        n_active = sum(1 for k, v in выбрано.items()
                       if not k.startswith("_") and k != "sort" and v)
        toggle = (
            f'<button type="button" class="zfilt-toggle" data-filt-toggle '
            f'aria-controls="zona-filt-bar" aria-expanded="false">'
            f'Фильтры{f" {n_active}" if n_active else ""}</button>')

        фильтры = (
            f'{toggle}'
            f'<div class="zfilt-bar" id="zona-filt-bar" data-scroller="filters" '
            f'data-testid="catalog-filters">'
            f'<div class="zfilt-bar__group">{"".join(kind_chips)}</div>'
            f'{year_html}{genre_html}{country_html}{sort_html}'
            f'<div class="zfilt-bar__sticky">{reset_html}</div>'
            f'</div>'
            '<script>(function(){var b=document.querySelector("[data-filt-toggle]");'
            'var p=document.getElementById("zona-filt-bar");if(!b||!p)return;'
            'b.addEventListener("click",function(){var o=!p.classList.contains("is-open");'
            'p.classList.toggle("is-open",o);b.setAttribute("aria-expanded",o?"true":"false");'
            '});})();</script>')

        активные_чипы = []
        if выбрано.get("kind"):
            активные_чипы.append(
                {"label": ПОДПИСЬ_РАЗДЕЛА.get(выбрано["kind"], выбрано["kind"]),
                 "clear": разд + "/" + запрос_строкой({**выбрано, **omit}, kind=None, page=None)})
        if год:
            активные_чипы.append({
                "label": str(год),
                "clear": разд + "/" + запрос_строкой({**выбрано, **omit}, year=None, page=None)})
        if жанр_имя:
            активные_чипы.append({
                "label": жанр_имя,
                "clear": разд + "/" + запрос_строкой({**выбрано, **omit}, genre=None, page=None)})
        if country_код:
            cname = dict(countries).get(country_код, country_код)
            активные_чипы.append({
                "label": cname,
                "clear": разд + "/" + запрос_строкой(
                    {**выбрано, **omit}, country=None, page=None)})
        chips_html = ""
        if активные_чипы:
            chips_html = '<div class="zfilt-chips" aria-label="Активные фильтры">' + "".join(
                f'<span>{html.escape(c["label"])}'
                f'<a href="{html.escape(c["clear"])}" aria-label="Убрать фильтр">×</a></span>'
                for c in активные_чипы) + "</div>"

        сорт_лейбл = dict(sort_opts).get(active_sort, active_sort)
        if разд == "/new":
            scope = "в этой ленте"
        elif has_active or разд != "/catalog":
            scope = "по фильтрам" if has_active else "в разделе"
        else:
            scope = "в каталоге"
        zsub_bits = [f"Результаты {scope}: {len(набор)}"]
        if mode_def:
            zsub_bits.insert(0, mode_def)
        if разд != "/new":
            zsub_bits.append(f"Сортировка: {сорт_лейбл}")
        zsub = " · ".join(zsub_bits)

        # Канонический адрес описывает ЗАПРОШЕННУЮ страницу, а не действующую
        # выборку. Подразумеваемое маршрутом (`_подразумеваемое` из `отбор`)
        # отбрасывается, а правило «порядок списка отдельной страницы не
        # образует» применяется общим слоем (`seo_layer.канонический_путь`), а
        # не повторяется здесь: второе правило разошлось бы с первым.
        подразум = {к for к in (выбрано.get("_подразумеваемое") or "").split(",") if к}
        канон_поля = {к: з for к, з in выбрано.items() if к not in подразум}
        if канон_поля.get("genre"):
            канон_поля["genre"] = главный_код_жанра(self.индекс, канон_поля["genre"])
        канон_q = запрос_строкой({**канон_поля, **omit}, page=None)
        канон = SEO.канонический_путь(разд + "/" + канон_q)
        show_fresh = разд == "/new"
        fresh_mode = new_mode or NEW_MODE_PREMIERE
        # Пустой раздел без единого условия — это не «ничего не подошло».
        # Предлагать сбросить фильтры, которых читатель не ставил, значит
        # объяснять пустоту его действиями: он идёт снимать несуществующее
        # условие и возвращается к той же пустой странице. Пусто здесь потому,
        # что пуст снимок каталога, и сказать надо ровно это.
        # Сужает выборку только фильтр. Сортировка выставлена по умолчанию и
        # порядок меняет, а не состав: считать её условием значило бы объявить
        # «условия применены» на голом /catalog/.
        есть_условия = any(
            (выбрано or {}).get(к) for к in ("kind", "year", "genre", "country"))
        if кусок:
            сетка = self.плитки(кусок, freshness=show_fresh, fresh_mode=fresh_mode,
                                первый_экран=True)
        elif есть_условия:
            # Фильтр, под который не попала ни одна запись, — пустая выборка, а
            # не страница: 404 и без canonical (SEO_KNOWLEDGE_PACK §3 п.4).
            self._код_ответа = 404
            сетка = ('<div class="zempty"><b>Ничего не подошло</b>'
                     "<p>Под выбранные условия не попала ни одна запись. "
                     f'<a href="{разд}/">Сбросить фильтры</a></p></div>')
        else:
            сетка = ('<div class="zempty"><b>Раздел пока пуст</b>'
                     "<p>В каталоге для этого раздела нет ни одной "
                     "записи. Условия ни при чём — снимок обновится, и записи "
                     f'появятся. <a href="/">На главную</a> · '
                     f'<a href="/catalog/">Открыть каталог</a></p></div>')

        тело = (
            f'<div class="zpage" data-testid="page-container">'
            f'<h1 class="zh" data-testid="catalog-heading" id="catalog-h1">'
            f'{html.escape(титул)}</h1>'
            f'<p class="zsub">{html.escape(zsub)}</p>'
            f'{cat_tabs_html}'
            f'{mode_tabs_html}'
            f'{chips_html}'
            f'{фильтры}'
            + self._полоса_подборок_раздела(разд, стр)
            + f'<div data-testid="catalog-grid">{сетка}</div>'
            + self.листалка(разд, {**выбрано, **omit}, стр, всего_страниц)
            + self._ссылки_жанров(разд, есть_условия, стр)
            + "</div>")
        актив = разд + "/"
        # Страница выдачи N>1 — своя страница: номер в canonical и заголовке
        # (REQ-SEO-PAGINATION п.3, knowledge/SEO_KNOWLEDGE_PACK.md §2; D202).
        # Прежде все страницы объявляли канонической первую и носили её
        # заголовок; page в общем seo_layer не относится к неканоническим.
        адрес = канон or (разд + "/")
        хвост = ""
        if стр > 1:
            адрес += ("&" if "?" in адрес else "?") + f"page={стр}"
            хвост = f" — страница {стр}"
        # Описание раздела несёт факт страницы — число записей выборки (T036;
        # образец Lords). Было «Драма на Zona Cinema.» — 14–23 знака без
        # единого факта, при том что страница сама показывает «Результаты: N».
        число = len(набор)
        if число:
            # «N названий», а не «N записей каталога»: посетителю — что он
            # найдёт, без устройства данных (§4 п.2; T303, перенос T301).
            слово = ("название" if число % 10 == 1 and число % 100 != 11 else
                     "названия" if 2 <= число % 10 <= 4 and not 12 <= число % 100 <= 14
                     else "названий")
            описание_раздела = (f"{титул} на {self.имя}: {число} {слово} — "
                                f"смотреть онлайн{хвост}.")
        else:
            описание_раздела = f"{титул} на {self.имя}{хвост}."
        # Крошки раздела жанра и раздела вида — тот же компонент, что на
        # карточке, BreadcrumbList из тех же звеньев (SEO_KNOWLEDGE_PACK §4 п.4;
        # T270, перенос T269: на /catalog/?genre=drama не было ни того, ни
        # другого). Только сам раздел, без прочих условий; разделы стран
        # (?country=) не трогаются до оценки 01.11.
        # Вид, который подставил маршрут раздела (/movies/ → kind=movie), —
        # сам раздел, а не условие (T281, перенос T275: живой /movies/ шёл без крошек).
        вид_раздела = (КАТЕГОРИЯ_ПО_МАРШРУТУ.get(разд), ВИД_ПО_МАРШРУТУ.get(разд))
        явные = {к for к in ("kind", "year", "genre", "country")
                 if выбрано.get(к) and к not in подразум
                 and not (к == "kind" and выбрано.get(к) in вид_раздела)}
        раздел_крошек = ""
        if getattr(self, "_код_ответа", 200) == 200:
            if разд == "/catalog" and явные == {"genre"} and жанр_имя:
                раздел_крошек = жанр_имя[:1].upper() + жанр_имя[1:]
            elif разд != "/catalog" and разд in имена and not явные:
                раздел_крошек = имена[разд]
        звенья = ([("/", self.имя), ("/catalog/", "Каталог"), ("", раздел_крошек)]
                  if раздел_крошек else [])
        return self.оболочка(тело, f"{титул}{хвост} — {self.имя}", адрес,
                             актив=актив,
                             описание=описание_раздела,
                             сверху="", код=getattr(self, "_код_ответа", 200),
                             крошки=self.крошки(звенья) if звенья else "",
                             разметка=self.schema_крошек(звенья) if звенья else "")

    def поиск(self, зпр: dict) -> str:
        q_raw = (зпр.get("q") or [""])[0]
        q_stripped = q_raw.strip()
        truncated = len(q_stripped) > 120
        q = q_stripped[:120]
        q_attr = html.escape(q, quote=True)
        if not q_stripped:
            тело = ('<h1 class="zh">Поиск</h1><p class="zsub">Введите название — '
                    "поиск идёт по русскому и оригинальному написанию.</p>"
                    '<div class="zempty"><b>Запрос пуст</b>'
                    "<p>Наберите название в строке сверху. Слова «сезон» и «серия» "
                    "в запросе поиску не мешают. "
                    '<a href="/catalog/">Открыть каталог целиком</a></p></div>')
            html_page = self.оболочка(
                f'<div class="zpage">{тело}</div>',
                f"Поиск — {self.имя}", "/search/", актив="")
            return html_page

        найдено = self.д.искать(q)
        raw_page = (зпр.get("page") or ["1"])[0]
        try:
            стр = int(raw_page or 1)
        except (TypeError, ValueError):
            return self.не_найдено(f"/search/?q={q_attr}&page={html.escape(str(raw_page))}")
        if стр < 1:
            return self.не_найдено(f"/search/?q={q_attr}&page={стр}")

        clamp_note = ('<p class="zsub">Запрос обрезан до 120 символов.</p>'
                      if truncated else "")
        if not найдено:
            тело = (f'<h1 class="zh">Результаты поиска: «{html.escape(q)}»</h1>'
                    f'{clamp_note}'
                    '<div class="zempty"><b>Совпадений нет</b>'
                    f"<p>По запросу «{html.escape(q)}» ничего не нашлось. "
                    "Проверьте написание. "
                    '<a href="/catalog/">Открыть весь каталог</a></p></div>')
            канон = f"/search/?q={q_attr}"
        else:
            всего_страниц = max(1, (len(найдено) + НА_СТРАНИЦЕ_1_1 - 1) // НА_СТРАНИЦЕ_1_1)
            if стр > всего_страниц:
                return self.не_найдено(f"/search/?q={q_attr}&page={стр}")
            кусок = найдено[(стр - 1) * НА_СТРАНИЦЕ_1_1: стр * НА_СТРАНИЦЕ_1_1]
            листалка = self.листалка("/search", {"q": q}, стр, всего_страниц)
            тело = (f'<h1 class="zh">Результаты поиска: «{html.escape(q)}»</h1>'
                    f'{clamp_note}'
                    f'<p class="zsub">Совпадений: {len(найдено)}</p>'
                    + self.плитки(кусок) + листалка)
            канон = (f"/search/?q={q_attr}" if стр <= 1
                     else f"/search/?q={q_attr}&page={стр}")

        html_page = self.оболочка(
            f'<div class="zpage">{тело}</div>',
            f"Поиск — {self.имя}", канон, актив="")
        html_page = html_page.replace(
            'id="q" name="q" placeholder=',
            f'id="q" name="q" value="{q_attr}" placeholder=',
            1)
        return html_page

    def тайтл(self, запись: dict, деталь: dict) -> str:
        путь = f"/title/{запись['slug']}/"
        имя = запись["title"]
        сезоны = список_серий(деталь)
        сериал = bool(сезоны) or запись.get("kind") == "Сериал"
        звенья = [("/", self.имя),
                  ("/series/", "Сериалы") if сериал else ("/movies/", "Фильмы"),
                  ("", имя)]
        изо = заглушка_постера(запись, "zt__none", "zhead__img", 260, 390,
                               срочно="high" if self.СРОЧНОСТЬ_ОБЛОЖЕК else None)
        полное = чистое_описание(деталь.get("description")).strip()
        краткое_поле = чистое_описание(деталь.get("short_description")).strip()
        оригинал = (деталь.get("original_name") or деталь.get("english_name") or "").strip()
        оригинал_html = (f'<p class="ztitle__o">{html.escape(оригинал)}</p>'
                         if оригинал and оригинал != имя else "")
        # Center column: distinct short OR full with clamp+expand (once; no post-player copy).
        # Expand only when full text is long enough that clamp would overflow (~320).
        if краткое_поле and краткое_поле != полное:
            описание_html = f'<p class="ztitle__desc">{html.escape(краткое_поле)}</p>'
            if полное and len(полное) > 320:
                описание_html += (
                    f'<div class="ztitle__desc ztitle__desc--clamp" id="synopsis" hidden>'
                    f'{html.escape(полное)}</div>'
                    '<button type="button" class="ztitle__more" data-expand-plot '
                    'aria-controls="synopsis">Развернуть</button>')
            elif полное:
                описание_html += (
                    f'<div class="ztitle__desc" id="synopsis" hidden>'
                    f'{html.escape(полное)}</div>')
        elif полное:
            if len(полное) > 320:
                описание_html = (
                    f'<div class="ztitle__desc ztitle__desc--clamp" id="synopsis">'
                    f'{html.escape(полное)}</div>'
                    '<button type="button" class="ztitle__more" data-expand-plot '
                    'aria-controls="synopsis" aria-expanded="false">Развернуть</button>')
            elif len(полное) < 160:
                описание_html = (
                    f'<div class="ztitle__desc" id="synopsis">'
                    f'{html.escape(полное)}</div>')
            else:
                описание_html = (
                    f'<div class="ztitle__desc ztitle__desc--clamp" id="synopsis">'
                    f'{html.escape(полное)}</div>')
        else:
            описание_html = ""
        оценки_html = разметка_оценок(деталь, "rbs")
        # Genre chips in center (not glued into rail as uppercase soup).
        жанры = деталь.get("genres") or []
        коды = list(деталь.get("genre_codes") or [])
        # Resolve missing codes via index name→code (many titles lack genre_codes).
        имя_в_код = {имя.lower(): код
                     for код, имя in (self.индекс.get("genre_names") or [])}
        # Fixed nav codes for common labels when index translit differs.
        имя_в_код.update({
            "драма": "drama", "комедия": "comedy", "триллер": "triller",
            "дорама": "dorama", "боевик": "action",
            "западный контент": "west_content", "мелодрама": "melodrama",
            "исторический": "history", "романтика": "melodrama",
        })
        genre_chips = []
        for i, gname in enumerate(жанры[:8]):
            # Служебная метка поставщика — не жанр (T044/T077, T113).
            if str(gname or "").strip().casefold() in _ТЕХНИЧЕСКИЕ_ЖАНРЫ:
                continue
            код = коды[i] if i < len(коды) else ""
            if not код:
                код = имя_в_код.get((gname or "").lower(), "")
            if код:
                # Ссылка — сразу на главный код, тот же, что в canonical раздела (T033).
                код = главный_код_жанра(self.индекс, код)
                genre_chips.append(
                    f'<a href="/catalog/{запрос_строкой({"genre": код})}">'
                    f'{html.escape(gname)}</a>')
            else:
                genre_chips.append(f'<span>{html.escape(gname)}</span>')
        genres_html = (f'<div class="ztitle__genres">{"".join(genre_chips)}</div>'
                       if genre_chips else "")
        chips = []
        длит = _длительность(деталь.get("duration"))
        if длит:
            chips.append(f'<span class="ztitle__chip">{html.escape(длит)}</span>')
        дата = _дата(деталь.get("premiere_date") or "")
        if дата:
            chips.append(f'<span class="ztitle__chip">{html.escape(дата)}</span>')
        chips_html = (f'<div class="ztitle__chips">{"".join(chips)}</div>' if chips else "")
        # Single facts grid only — no right-hand series rail (Pass6 Block 04).
        # Genres stay as chips above; do not duplicate them as a fact row.
        keep_labels = {
            "Год", "Тип", "Страна", "Статус", "Время", "Серии", "Возраст",
            "Дата выхода",
        }
        label_map = {"Время": "Продолжительность"}
        все_пары = list(факты(self, запись, деталь))
        for метка, ключ in (("Возраст", "age_rating"), ("Статус", "status")):
            знач = деталь.get(ключ)
            if знач:
                все_пары.append((метка, html.escape(str(знач))))
        seen = set()
        fact_пары = []
        for м, з in все_пары:
            if м not in keep_labels or not з or м in seen:
                continue
            seen.add(м)
            fact_пары.append((label_map.get(м, м), з))
        core_rows = "".join(
            f"<div><dt>{html.escape(м)}</dt><dd>{з}</dd></div>" for м, з in fact_пары)
        core_dl = (f'<dl class="ztitle__facts" data-testid="title-facts">{core_rows}</dl>'
                   if core_rows else "")
        ads_on = os.environ.get("ZONA_AD_SLOTS", "") == "1"
        ad_slot = (f'<div class="zad" data-ad-slot="title-rail-300x250" '
                   f'data-ad-enabled="{1 if ads_on else 0}" '
                   f'aria-hidden="{"false" if ads_on else "true"}"></div>') if ads_on else ""
        сезон_старт, эпизод_старт = выбрать_доступную_серию(деталь) if сезоны else (1, None)
        код, внутри = разметка_плеера(self, запись, деталь, сезон_старт, эпизод_старт)
        player_contract = (os.environ.get("PLAYER_CONTRACT_ID")
                           or "cdnvideohub-player-v1")
        полоса = self.полоса_действий(
            запись, деталь, сезон=сезон_старт if сезоны else None,
            эпизод=эпизод_старт if сезоны else None, состояние=код)
        плеер = (f'<section class="zpl" id="watch" '
                 f'data-player-contract="{html.escape(player_contract)}">'
                 f'<div class="zpl__h"><h2>Смотреть</h2>'
                 f"<span>{html.escape(_подпись_плеера(код))}</span></div>"
                 f'<div class="zpl__f" data-player data-state="{код}">{внутри}</div>'
                 f"{_скрипты_плеера(код)}{полоса}</section>")
        текущий = (сезон_старт, эпизод_старт) if эпизод_старт is not None else None
        блок_серий = (f'<div class="zpage">{self._серии(запись, сезоны, текущий=текущий)}</div>'
                      if сериал else "")
        похожие = self.похожие(запись, деталь, сколько=12)
        if похожие:
            compact = " zg--related-compact" if len(похожие) < 4 else ""
            блок_похожих = (
                f'<div class="zpage"><section class="zsec" data-testid="related-grid" '
                f'data-rec-policy="playable_preferred_with_explicit_nonplayable_state_v1">'
                f'<div class="zsec__h"><h2>Смотрите также</h2></div>'
                f'<div class="zg zg--related{compact}">'
                f'{"".join(self.плитка(з, show_play=False, **self._срочность()) for з in похожие)}'
                f'</div></section></div>')
        else:
            блок_похожих = ""
        expand_js = ""
        if "data-expand-plot" in описание_html:
            expand_js = (
                "<script>(function(){var b=document.querySelector('[data-expand-plot]');"
                "var p=document.getElementById('synopsis');if(!b||!p)return;"
                "requestAnimationFrame(function(){"
                "if(p.scrollHeight<=p.clientHeight+1){b.hidden=true;b.setAttribute('aria-hidden','true');"
                "p.classList.remove('ztitle__desc--clamp');return;}"
                "b.addEventListener('click',function(){var open=p.classList.toggle('is-open');"
                "p.hidden=false;b.setAttribute('aria-expanded',open?'true':'false');"
                "b.textContent=open?'Свернуть':'Развернуть';});});})();</script>")
        тело = (
            f'<div class="zpage"><div class="ztitle">'
            f'<div class="ztitle__poster">{изо}</div>'
            f'<div class="ztitle__main"><h1>{html.escape(имя)}</h1>'
            f'{оригинал_html}{оценки_html}{genres_html}{chips_html}{core_dl}'
            f'{описание_html}'
            f'<a class="ztitle__cta" href="#watch" data-cta="to-player">К плееру</a>{ad_slot}</div>'
            f'</div></div>{плеер}{блок_серий}{блок_похожих}'
            f'{self._блок_сообщества(запись, деталь)}'
            f'{self._точка_комментариев(запись, деталь)}{expand_js}')
        разметка = [
            self.schema_тайтла(запись, деталь, путь),
            self.schema_крошек(звенья),
        ]
        meta_desc = (краткое_поле or полное or "").strip()
        краткое = краткое_описание(имя, запись, деталь, meta_desc, self.имя)
        return self.оболочка(
            тело, f"{различимое_название(имя, запись, деталь, self.д.items)} — смотреть онлайн — {self.имя}", путь,
            описание=краткое, разметка=разметка, крошки=self.крошки(звенья),
            og=self.карточка_графа(
                тип="video.tv_show" if сериал else "video.movie",
                титул=имя, описание=краткое, путь=путь,
                изображение=запись.get("poster") or ""))

    #: Полоса действий под плеером. Ровно один ряд на компьютере, аккуратный
    #: перенос на телефоне; пустых ячеек не бывает, потому что ряд собирается
    #: только из тех действий, которые на этой странице действительно работают.
    def полоса_действий(self, запись: dict, деталь: dict, *,
                        сезон: int | None = None, эпизод: int | None = None,
                        состояние: str = "") -> str:
        """Действия под плеером.

        Почему собирается, а не рисуется по шаблону. Полоса с кнопкой, которая
        на этой странице ничего не делает, — это пустая ячейка с подписью, и
        отличить её от сломанной нельзя. Поэтому каждое действие добавляется
        только вместе со своим условием: переходы по сериям — когда серии
        есть, полный экран — когда есть что разворачивать, обсуждение — когда
        модуль сообщества подключён и видим.

        Второй шкалы голосования здесь нет и не будет: «Оценить» — это переход
        к единственной шкале модуля сообщества, а не своя. Пока модуль не
        подключён, перехода тоже нет: вести к тому, чего на странице нет, —
        обещание, которого витрина не выполняет.
        """
        куски: list[str] = []
        slug = (запись or {}).get("slug") or ""
        серийная = bool(список_серий(деталь))

        if серийная and сезон is not None and эпизод is not None:
            пред, след = границы_серии(деталь, сезон, эпизод)
            if пред:
                куски.append(
                    f'<a class="zplbar__b" rel="prev" '
                    f'href="{self.адрес_эпизода(slug, *пред)}">'
                    f'<span aria-hidden="true">←</span> Предыдущая</a>')
            if след:
                куски.append(
                    f'<a class="zplbar__b" rel="next" '
                    f'href="{self.адрес_эпизода(slug, *след)}">'
                    f'Следующая <span aria-hidden="true">→</span></a>')
        if серийная:
            якорь = (self.адрес_сезона(slug, сезон) if сезон is not None
                     else f"/title/{slug}/#episodes")
            куски.append(f'<a class="zplbar__b" href="{якорь}">Все серии</a>')

        # Полный экран просит у кадра сам браузер. Кнопка добавляется ровно
        # там, где витрина монтирует плеер, — то же условие, по которому
        # подключаются его скрипты (`_скрипты_плеера`). У состояний «нет
        # источника», «не подключено» и «ожидается выбор серии» разворачивать
        # нечего, и кнопка там была бы подписанной пустотой.
        if состояние in ("playable", "resolving"):
            куски.append(
                '<button class="zplbar__b" type="button" data-zpl-full '
                'aria-label="Развернуть плеер на весь экран">Во весь экран</button>')

        куски.append(
            '<button class="zplbar__b" type="button" data-zpl-share '
            'aria-label="Скопировать ссылку на страницу">Поделиться</button>')

        обсуждение = self._действия_сообщества(запись)
        if обсуждение:
            куски.append(обсуждение)

        if not куски:
            return ""
        return (f'<nav class="zplbar" data-testid="player-actions" '
                f'aria-label="Действия">{"".join(куски)}</nav>'
                + _СКРИПТ_ПОЛОСЫ_ДЕЙСТВИЙ)

    def _действия_сообщества(self, запись: dict) -> str:
        """Переход к оценке и обсуждению — только когда им есть куда вести.

        Это переход к единственной шкале модуля, а не вторая шкала: кнопка
        просто уводит к блоку сообщества. Пока модуль не разрешает запись для
        этого домена, кнопки нет вовсе — вести к тому, чего на странице нет,
        значит обещать неработающее.
        """
        if СООБЩЕСТВО is None or not СООБЩЕСТВО.виджет_включён():
            return ""
        куски = ['<a class="zplbar__b" href="#community-rating">Оценить</a>']
        if СООБЩЕСТВО.комментарии_разрешены():
            куски.append('<a class="zplbar__b" href="#comments">Комментарии</a>')
        return "".join(куски)

    def _точка_комментариев(self, запись: dict, деталь: dict) -> str:
        """Место, куда общий модуль комментариев сможет подключиться.

        Здесь НЕТ кода комментариев и не будет: модуль общий, и копия его
        разметки в каждом шаблоне — это пятьдесят мест, которые разойдутся.
        Есть только объявленная точка: якорь подключения, предмет обсуждения
        и пространство, из которого предмет берётся.

        Почему скрыта. Пока модуль не подключён, комментариев ноль, а секция с
        заголовком и без содержимого — это обещание, которого витрина не
        выполняет. `hidden` снимает её из потока и из дерева доступности;
        модуль, подключившись, снимет атрибут сам. Соглашение об атрибутах
        взято у соседней ленты (`data-comments="0"` плюс `hidden`), чтобы
        модуль искал одно и то же во всём флоте, а не по-разному в каждом
        семействе.

        Точка ставится только витрине Zona. `ВидАнимедиа` наследует `тайтл`
        целиком, и без этой проверки объявление протекло бы соседу, у которого
        своя лента и своя точка.
        """
        if СЕМЕЙСТВО != "zona" or СООБЩЕСТВО is None:
            return ""
        # Предмет обсуждения — ПОСТОЯННЫЙ идентификатор, а не slug, и берётся
        # тем же способом, что у виджета оценки. Здесь стоял slug, и это был
        # дефект контракта, который не проявлялся только потому, что точка
        # скрыта: у витрины есть SLUG_ALIASES, то есть слаги уже менялись, и
        # обсуждения, привязанные к слагу, после переименования уехали бы не
        # туда. Вторая причина — каталог у витрин семейства общий, слаги в нём
        # совпадают, и в общем пространстве обсуждения двух сайтов слились бы
        # в одно.
        предмет = СООБЩЕСТВО.предмет(деталь)
        if not предмет:
            # Без постоянного идентификатора точку не объявляем вовсе: якорь с
            # заведомо неверным предметом хуже отсутствующего — модуль его
            # примет и привяжет обсуждение не к тому.
            return ""
        # Род ключа объявляется, а не угадывается. Модуль хранит обсуждение в
        # канонических полях `site_space` / `title_id`; `title_id` здесь —
        # схема `nova:<uuid>`, та же, что у виджета оценки. Без объявления
        # принимающей стороне пришлось бы разбирать строку и догадываться, а
        # догадка о ключе — это привязка обсуждения не к тому произведению.
        #
        # Пространство остаётся брендовым (`zona`) намеренно. Оно задано
        # контрактом модуля (`required_rating_space`), а сам модуль выводит
        # пространство на сервере из домена и телу запроса не верит
        # («Never trust body.rating_space_id»). Подставить сюда `zona-01`
        # значило бы объявить пространство, которого модуль не знает, и
        # разойтись с его моделью, где домены одного бренда делят пространство
        # по подтверждённому решению владельца. Вопрос, делят ли его
        # zonafilm.space и zonafilm.cc, решает владелец модуля, а не витрина.
        #
        # Смешать произведения или типы контента этот ключ не может: `title_id`
        # — собственный идентификатор записи, он принадлежит ровно одному
        # произведению, а значит и ровно одному типу. Тип передаётся отдельным
        # полем как справочный, потому что у модуля есть колонка `content_type`.
        вид = str((запись or {}).get("kind") or "").strip()
        slug = str((запись or {}).get("slug") or "")
        тип = f'data-comments-content-type="{html.escape(вид)}" ' if вид else ""
        return (f'<section class="zcomments" id="comments" data-comments="0" '
                f'data-comments-space="{html.escape(СООБЩЕСТВО.ПРОСТРАНСТВО)}" '
                f'data-comments-subject="{html.escape(предмет)}" '
                f'data-comments-subject-kind="nova-title-id" '
                f'{тип}'
                f'data-comments-slug="{html.escape(slug)}" '
                f'hidden aria-hidden="true"></section>')

    def _блок_сообщества(self, запись: dict, деталь: dict) -> str:
        """Оценка посетителя и обсуждение — разметкой утверждённого модуля.

        Витрина добавляет ровно два узла: место, куда виджет смонтируется, и
        тег его загрузчика. Ни шкалы, ни кнопок, ни счётчиков здесь нет: это
        разметка модуля, и копия её в шаблоне разошлась бы с ним при первом же
        его выпуске.

        Пока модуль не поддерживает пространство этого домена, не добавляется
        ничего — ни заголовка, ни пустой секции. Заголовок «Ваша оценка» над
        неработающим управлением — обещание, которого витрина не выполняет;
        сам модуль требует того же в `widget_enabled`.
        """
        if СООБЩЕСТВО is None or not СООБЩЕСТВО.виджет_включён():
            return ""
        предмет = СООБЩЕСТВО.предмет(деталь)
        if not предмет:
            return ""
        return (f'<section class="zcommunity" id="community-rating" '
                f'data-community-space="{html.escape(СООБЩЕСТВО.ПРОСТРАНСТВО)}" '
                f'data-community-subject="{html.escape(предмет)}"></section>'
                + СООБЩЕСТВО.тег_загрузчика(предмет, версия=СБОРКА[:12]))

    def _серии(self, запись: dict, сезоны: list, текущий=None) -> str:
        if not сезоны:
            return ('<h2 class="zh zh--sm">Серии</h2>'
                    '<div class="zempty"><b>Состав сезонов не передан</b>'
                    "<p>Источник по этой записи ещё не отдал список серий. "
                    "Как только отдаст, он появится здесь.</p></div>")

        def panel(сезон: dict) -> str:
            ячейки = []
            for н in сезон["номера"]:
                доступна = н in сезон["доступные"]
                текущая = (текущий == (сезон["n"], н))
                label = f"Серия {н}"
                if текущая and доступна:
                    ячейки.append(
                        f'<a href="{self.адрес_эпизода(запись["slug"], сезон["n"], н)}" '
                        f'aria-current="page" aria-label="{html.escape(label)}">{н}</a>')
                elif доступна:
                    ячейки.append(
                        f'<a href="{self.адрес_эпизода(запись["slug"], сезон["n"], н)}" '
                        f'aria-label="{html.escape(label)}">{н}</a>')
                else:
                    ячейки.append(
                        f'<span role="link" aria-disabled="true" '
                        f'title="Серия заявлена, видео пока недоступно" '
                        f'aria-label="{html.escape(label)}">{н}</span>')
            хвост = ("" if сезон["доступно"] == сезон["eps"]
                     else f", доступно {сезон['доступно']}")
            return (
                f'<section class="zsea" data-zsea-panel="{сезон["n"]}">'
                f'<div class="zsea__h">'
                f'<b>Сезон {сезон["n"]}</b><span>· '
                f'{_склонение(сезон["eps"], "серия", "серии", "серий")}{хвост}</span></div>'
                f'<div class="zeps">{"".join(ячейки)}</div></section>')

        if len(сезоны) == 1:
            return f'<h2 class="zh zh--sm">Серии</h2>{panel(сезоны[0])}'

        # Default panel: season containing current episode, else first.
        default_n = сезоны[0]["n"]
        if текущий:
            for с in сезоны:
                if с["n"] == текущий[0]:
                    default_n = с["n"]
                    break
        tabs = []
        panels = []
        for с in сезоны:
            cur = ' aria-current="true"' if с["n"] == default_n else ""
            tabs.append(
                f'<button type="button" data-zsea-tab="{с["n"]}"{cur}>'
                f'Сезон {с["n"]}</button>')
            hidden = "" if с["n"] == default_n else " hidden"
            p = panel(с).replace(
                f'data-zsea-panel="{с["n"]}"',
                f'data-zsea-panel="{с["n"]}"{hidden}', 1)
            panels.append(p)
        js = (
            '<script>(function(){document.querySelectorAll("[data-zsea-tab]").forEach(function(b){'
            'b.addEventListener("click",function(){var k=b.getAttribute("data-zsea-tab");'
            'document.querySelectorAll("[data-zsea-tab]").forEach(function(x){x.removeAttribute("aria-current");});'
            'b.setAttribute("aria-current","true");'
            'document.querySelectorAll("[data-zsea-panel]").forEach(function(p){'
            'p.hidden=p.getAttribute("data-zsea-panel")!==k;});});});})();</script>')
        return (f'<h2 class="zh zh--sm">Серии</h2>'
                f'<div class="zsea__tabs" data-testid="season-tabs" role="tablist">'
                f'{"".join(tabs)}</div>{"".join(panels)}{js}')

    def сезон(self, запись: dict, деталь: dict, номер: int) -> str:
        имя = запись["title"]
        путь = self.адрес_сезона(запись["slug"], номер)
        только = [с for с in список_серий(деталь) if с["n"] == номер]
        заголовок = f"{имя} — сезон {номер}"
        звенья = [("/", self.имя), ("/series/", "Сериалы"),
                  (f"/title/{запись['slug']}/", имя), ("", f"Сезон {номер}")]
        серий = только[0]["eps"] if только else 0
        тело = (f'<div class="zpage"><h1 class="zh">{html.escape(заголовок)}</h1>'
                f'<p class="zsub">В сезоне {серий} серий · '
                f'<a href="/title/{запись["slug"]}/">вернуться к описанию</a></p>'
                + self._серии(запись, только) + "</div>")
        return self.оболочка(
            тело, f"{заголовок} — {self.имя}", путь,
            описание=f"{заголовок}: список серий на {self.имя}.",
            разметка=self.schema_крошек(звенья), крошки=self.крошки(звенья),
            og=self.карточка_графа(
                тип="video.tv_show", титул=заголовок,
                описание=f"{заголовок}: список серий на {self.имя}.",
                путь=путь, изображение=запись.get("poster") or ""))

    def серия(self, запись: dict, деталь: dict, сезон: int, эпизод: int) -> str:
        имя = запись["title"]
        путь = self.адрес_эпизода(запись["slug"], сезон, эпизод)
        заголовок = f"{имя} — {сезон} сезон, {эпизод} серия"
        звенья = [("/", self.имя), ("/series/", "Сериалы"),
                  (f"/title/{запись['slug']}/", имя),
                  ("", f"Сезон {сезон}, серия {эпизод}")]
        player_contract = (os.environ.get("PLAYER_CONTRACT_ID")
                           or "cdnvideohub-player-v1")
        код, внутри = разметка_плеера(self, запись, деталь, сезон, эпизод)
        # Полоса действий стоит под кадром внутри секции плеера. Прежний
        # `zepnav` убран: две полосы переходов под одним плеером — это два
        # ответа на один вопрос «куда отсюда», и нижняя из них к тому же
        # печатала «Это первая серия» пустой ячейкой с подписью.
        полоса = self.полоса_действий(запись, деталь, сезон=сезон,
                                      эпизод=эпизод, состояние=код)
        плеер = (f'<section class="zpl" id="watch" '
                 f'data-player-contract="{html.escape(player_contract)}">'
                 f'<div class="zpl__h"><h2>Смотреть серию</h2>'
                 f"<span>{html.escape(_подпись_плеера(код))}</span></div>"
                 f'<div class="zpl__f" data-player data-state="{код}">{внутри}</div>'
                 f"{_скрипты_плеера(код)}{полоса}</section>")
        переход = ""
        # Episode facts: only source-backed fields on the episode object.
        facts_html = ""
        ep_obj = None
        for с in (деталь.get("seasons") or []):
            if int(с.get("n") or 0) != сезон:
                continue
            for эп in (с.get("episodes") or []):
                if not isinstance(эп, dict):
                    continue
                num = эп.get("number") if эп.get("number") is not None else эп.get("n")
                try:
                    if int(num) == эпизод:
                        ep_obj = эп
                        break
                except (TypeError, ValueError):
                    continue
            break
        if ep_obj:
            rows = []
            if ep_obj.get("title"):
                rows.append(("Название", html.escape(str(ep_obj["title"]))))
            air = ep_obj.get("air_date") or ep_obj.get("premiere_date")
            if air:
                d = _дата(str(air))
                if d:
                    rows.append(("Дата выхода", html.escape(d)))
            dur = ep_obj.get("duration")
            if dur:
                dlabel = _длительность(dur)
                if dlabel:
                    rows.append(("Длительность", html.escape(dlabel)))
            if rows:
                facts_html = (
                    '<div class="zpage"><dl class="ztitle__facts" '
                    'data-testid="episode-facts">'
                    + "".join(f"<div><dt>{html.escape(м)}</dt><dd>{з}</dd></div>"
                              for м, з in rows)
                    + "</dl></div>")
        parent = (
            f'<div class="zpage"><a class="zr" href="/title/{запись["slug"]}/">'
            f'<span class="zr__t">{html.escape(имя)}</span>'
            f'<span class="zr__m">Сезон {сезон}</span></a></div>')
        сезоны = список_серий(деталь)
        шапка = (f'<div class="zpage"><h1 class="zh zh--sm">{html.escape(заголовок)}</h1>'
                 f'<p class="zsub">Сезон {сезон}, серия {эпизод} · '
                 f'<a href="/title/{запись["slug"]}/">к описанию</a></p></div>')
        блок_серий = (f'<div class="zpage">'
                      f'{self._серии(запись, сезоны, текущий=(сезон, эпизод))}</div>')
        похожие = self.похожие(запись, деталь, сколько=12)
        if похожие:
            compact = " zg--related-compact" if len(похожие) < 4 else ""
            блок_похожих = (
                f'<div class="zpage"><section class="zsec" data-testid="related-grid" '
                f'data-rec-policy="playable_preferred_with_explicit_nonplayable_state_v1">'
                f'<div class="zsec__h"><h2>Смотрите также</h2></div>'
                f'<div class="zg zg--related{compact}">'
                f'{"".join(self.плитка(з, show_play=False, **self._срочность()) for з in похожие)}'
                f'</div></section></div>')
        else:
            блок_похожих = ""
        тело = (шапка + плеер + переход + facts_html + parent
                + блок_серий + блок_похожих)
        разметка = [
            self.schema_эпизода(запись, деталь, сезон, эпизод, путь),
            self.schema_крошек(звенья),
        ]
        return self.оболочка(
            тело, f"{заголовок} — {self.имя}", путь,
            описание=f"{заголовок}: смотреть онлайн на {self.имя}.",
            разметка=разметка, крошки=self.крошки(звенья),
            og=self.карточка_графа(
                тип="video.episode", титул=заголовок,
                описание=f"{заголовок}: смотреть онлайн на {self.имя}.",
                путь=путь, изображение=запись.get("poster") or ""))

    def не_найдено(self, путь: str) -> str:
        тело = ('<div class="znf"><b>404</b><h1>Страница не найдена</h1>'
                f"<p>Адрес <code>{html.escape(путь[:120])}</code> не соответствует ни одной "
                "странице сайта. Проверьте ссылку или начните с каталога.</p>"
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
    consumer = {
        "playable": "Подключаем видео",
        "resolving": "Подключаем видео",
        "ready": "Видео готово",
        "playing": "Воспроизведение",
        "awaiting": "Выберите серию",
        "unavailable": "Видео временно недоступно",
        "loading": "Подключаем видео",
        "nosource": "Видео временно недоступно",
        "noaccess": "Видео временно недоступно",
        "provider": "Видео временно недоступно",
        "error": "Видео временно недоступно",
        "slow": "Видео временно недоступно",
    }
    if СЕМЕЙСТВО == "animedia":
        return {
            **consumer,
            "playable": "смотреть",
            "awaiting": "выберите серию",
            "unavailable": "серия недоступна",
            "loading": "загрузка",
        }.get(код, "")
    return consumer.get(код, "")


def главный_код_жанра(индекс: dict, код: str) -> str:
    """Главный код имени жанра — с наибольшим составом (T033).

    Замер 13.10: у 29 из 98 имён жанров по два кода — «криминал»: kriminal
    (269 страниц) и criminal (3), первая страница совпадает 28 из 28, H1 один,
    каждый объявлял canonical на себя. Малый код — алиас: его canonical ведёт
    на главный. Карта строится один раз на индекс (перечитанный снимок —
    новый индекс). Режим индексации не трогается.
    """
    алиасы = индекс.get("_алиасы_жанров")
    if алиасы is None:
        по_жанру = индекс.get("genre") or {}
        лучший: dict = {}
        коды_имени: dict = {}
        for к, имя in (индекс.get("genre_names") or []):
            ключ = str(имя).strip().casefold()
            коды_имени.setdefault(ключ, []).append(к)
            размер = len(по_жанру.get(к) or ())
            if ключ not in лучший or размер > лучший[ключ][0]:
                лучший[ключ] = (размер, к)
        алиасы = {к: лучший[ключ][1] for ключ, коды in коды_имени.items()
                  for к in коды if к != лучший[ключ][1]}
        # Синоним кода вне genre_names (T267). Замер 19.10 zonafilm12.site:
        # ?genre=komediya — 18 239 записей, как comedy, canonical на себя;
        # boevik — как action. Индекс регистрирует состав под транслитом имени
        # и синонимами шаблона, и сайт такой код принимает. Форма значения
        # (нормализованная, транслит, синоним шаблона), совпавшая с формой
        # главного кода или его имени, ведёт canonical на главный код —
        # как на zonafilm.cc (genre_canonical, T114).
        def формы(с: str) -> set:
            с = str(с or "").strip()
            if not с:
                return set()
            ф = {нормализовать(с), нормализовать(транслит(с))}
            if ЖАНРЫ_АЛИАСЫ is not None:
                ф |= {нормализовать(а) for а in ЖАНРЫ_АЛИАСЫ.алиасы_жанра(с)}
            return {х for х in ф if х}
        к_главному: dict = {}
        for ключ, (_, главный) in лучший.items():
            for ф in формы(главный) | формы(ключ):
                к_главному.setdefault(ф, главный)
        известные = {к for к, _ in (индекс.get("genre_names") or [])}
        for к in по_жанру:
            if к in известные or к in алиасы:
                continue
            for ф in sorted(формы(к)):
                if ф in к_главному and к_главному[ф] != к:
                    алиасы[к] = к_главному[ф]
                    break
        индекс["_алиасы_жанров"] = алиасы
    return алиасы.get(код, код)


def _нормализовать_для_дедупа(title: str) -> str:
    """Collapse near-duplicate titles (punctuation/ё/hyphen variants)."""
    s = нормализовать(title or "")
    s = s.replace("ё", "е")
    for ch in "-–—·•_/\\|":
        s = s.replace(ch, " ")
    return " ".join(s.split())


#: «Похожие» без перебора признаков всего каталога на каждый запрос (T030).
#: Профиль 13.10: на холодной странице тайтла ~95 % времени — проход по всему
#: каталогу с построением множеств жанров и стран у каждой записи; памяти
#: страниц у этой витрины нет, поэтому так стоил КАЖДЫЙ запрос тайтла (живой
#: zonafilm.space 0,5–1 с на повтор той же страницы, zonafilm12.site 2–17 с).
#: Признаки — один раз на снимок, готовые списки — в памяти; срок обоих 30 мин
#: (подробности обновляются и на месте — согласованием серий). Порядок и отбор
#: дословно прежние: checks/similar_fast.py сравнивает с _похожие_полные.
_ПОХОЖИЕ_СРОК_С = 1800.0
_ПОХОЖИЕ_ПРИЗНАКИ: dict = {}
_ПОХОЖИЕ_ИТОГИ: dict = {}


def _отпечаток_снимка(*объекты) -> tuple:
    return tuple((id(о), getattr(о, "mtime", None), getattr(о, "revision", None))
                 for о in объекты)


def _признаки_похожих(вид) -> dict:
    ключ = _отпечаток_снимка(вид.д, вид.п)
    сейчас = time.monotonic()
    готово = _ПОХОЖИЕ_ПРИЗНАКИ.get(ключ)
    if готово is not None and сейчас - готово[0] < _ПОХОЖИЕ_СРОК_С:
        return готово[1]
    по_виду: dict = {}
    for сосед in вид.д.items:
        д = вид.п.get(сосед["slug"]) or {}
        g2 = set(д.get("genre_codes") or [])
        if not g2:
            g2 = {код_жанра(g) for g in (д.get("genres") or []) if g}
        по_виду.setdefault(сосед.get("kind"), []).append((
            сосед["slug"], frozenset(g2), frozenset(д.get("countries") or []),
            сосед.get("year") or 0, float(сосед.get("_rating") or 0.0),
            сосед.get("_n") or "", сосед, 0 if д.get("playable") is True else 1))
    _ПОХОЖИЕ_ПРИЗНАКИ.clear()
    _ПОХОЖИЕ_ИТОГИ.clear()
    _ПОХОЖИЕ_ПРИЗНАКИ[ключ] = (сейчас, по_виду)
    return по_виду


def _похожие_отбор(упорядоченные, запись: dict, сколько: int) -> list:
    out = []
    seen_names: set = set()
    cur_norm = _нормализовать_для_дедупа(запись.get("title") or "")
    if cur_norm:
        seen_names.add(cur_norm)
    for t in упорядоченные:
        сосед = t[6]
        norm = _нормализовать_для_дедупа(сосед.get("title") or "")
        if norm and norm in seen_names:
            continue
        if norm:
            seen_names.add(norm)
        out.append(сосед)
        if len(out) >= сколько:
            break
    return out


def _похожие_быстро(вид, запись: dict, деталь: dict, сколько: int) -> list:
    import heapq
    признаки = _признаки_похожих(вид)
    ключ_итога = (запись["slug"], сколько)
    итог = _ПОХОЖИЕ_ИТОГИ.get(ключ_итога)
    if итог is not None:
        return list(итог)
    текущий = запись["slug"]
    kind = запись.get("kind")
    жанры = set(деталь.get("genre_codes") or [])
    if not жанры:
        жанры = {нормализовать(транслит(g)) for g in (деталь.get("genres") or []) if g}
    страны = set(деталь.get("countries") or [])
    year = запись.get("year") or 0
    scored = []
    for slug, g2, c2, y2, r2, n, сосед, играет in признаки.get(kind, ()):
        if slug == текущий:
            continue
        year_prox = -abs(int(year) - int(y2)) if year and y2 else -9999
        scored.append((len(жанры & g2), 1 if (страны & c2) else 0, year_prox, r2, n, slug,
                       сосед, играет))
    # Прежний порядок — убывание (жанры, страна, год, оценка, имя, slug), затем
    # устойчивый подъём играющих; slug уникален, значит это ровно убывание по
    # (-играет, …). Верх с запасом под отсев повторов; не хватило — всё.
    ключ = (lambda t: (-t[7], t[0], t[1], t[2], t[3], t[4], t[5]))
    запас = max(сколько * 8, 96)
    верх = (heapq.nlargest(запас, scored, key=ключ) if len(scored) > запас
            else sorted(scored, key=ключ, reverse=True))
    out = _похожие_отбор(верх, запись, сколько)
    if len(out) < сколько and len(верх) < len(scored):
        out = _похожие_отбор(sorted(scored, key=ключ, reverse=True), запись, сколько)
    if len(_ПОХОЖИЕ_ИТОГИ) > 8192:
        _ПОХОЖИЕ_ИТОГИ.clear()
    _ПОХОЖИЕ_ИТОГИ[ключ_итога] = tuple(out)
    return out


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

АНИМЕДИА_ДОМЕНЫ = {
    "animedia.space": {
        "profile": "animedia-space",
        "og_site_name": "Animedia Space",
        "title_home": "Animedia Space — каталог аниме онлайн",
        "h1": "Каталог аниме онлайн",
        "description": (
            "Animedia Space собирает аниме из каталога: "
            "новые серии, оценки и подборки."),
        "lead": (
            "Свежие серии и тайтлы из каталога Animedia Space — только то, "
            "что в нём действительно есть."),
        "footer_about": (
            "Animedia Space — аниме-портал с каталогом, поиском и подборками "
            "из каталога. Юридические реквизиты и партнёры здесь "
            "не публикуются: их нет во входных данных."),
        "seo_home_title": "О каталоге Animedia Space",
        "seo_home": (
            "На Animedia Space главная собирается из непустых полок снимка: "
            "новые серии, недавно добавленные тайтлы, высокие оценки и записи "
            "с подтверждённой дорожкой. Пустые разделы без исходных полей "
            "скрываются, а не заполняются выдумкой. Каталог и поиск открывают "
            "весь доступный набор через серверную пагинацию."),
        "seo_catalog_title": "Как устроен каталог",
        "seo_catalog": (
            "Фильтры жанра, года и типа сужают реальный снимок Animedia Space. "
            "Адрес страницы отражает выбранные условия; пустая выдача честно "
            "сообщает об отсутствии совпадений."),
    },
    "animedia.icu": {
        "profile": "animedia-icu",
        "og_site_name": "Animedia ICU",
        "title_home": "Animedia ICU — аниме, серии и подборки",
        "h1": "Аниме, серии и подборки",
        "description": (
            "Animedia ICU показывает аниме-каталог с упором на серии, "
            "подборки и расписание: данные только из каталога."),
        "lead": (
            "Серии, подборки и расписание на Animedia ICU — по фактам каталога, "
            "без обещаний сверх источника."),
        "footer_about": (
            "Animedia ICU — аниме с акцентом на серии и тематические "
            "подборки. Контакты, лицензии и юрлицо не выдуманы и потому не "
            "указаны."),
        "seo_home_title": "Чем полезен Animedia ICU",
        "seo_home": (
            "Animedia ICU начинается с серий и подборок: если в снимке есть "
            "сериалы с датой, они выходят на первый план. Расписание дней "
            "недели остаётся каркасом без выдуманного времени выхода. "
            "Оценки и описания берутся только из sidecar подробностей."),
        "seo_catalog_title": "Навигация по каталогу ICU",
        "seo_catalog": (
            "Каталог Animedia ICU сочетает жанровые и годовые срезы с поиском "
            "по кириллице, латинице и slug. Пагинация сохраняет фильтры в URL, "
            "чтобы можно было вернуться назад без потери состояния."),
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

    #: T334: срочность обложек Zona сюда не переходит — тайтл и ленты
    #: наследуются, а разметка Animedia этого ядра остаётся прежней.
    СРОЧНОСТЬ_ОБЛОЖЕК = False

    def плитка(self, запись: dict) -> str:
        """Карточка с пропорцией постера 0.86 — измеренной на эталоне.

        Размеры проставляются в разметке, а не только в CSS: браузер обязан
        зарезервировать место до загрузки изображения, иначе сетка прыгает.
        """
        деталь = self.деталь(запись["slug"])
        изо = заглушка_постера(запись, "zt__none", "zt__img", 172, 200)
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
        полное = запись["title"] or ""
        return (f'<a class="zt" data-testid="title-card" href="{запись["url"]}" '
                f'title="{html.escape(полное)}" aria-label="{html.escape(полное)}">'
                f'<span class="zt__p">{изо}</span>'
                f'<span class="zt__b"><span class="zt__t" data-clamp-allowed="2">'
                f'{html.escape(полное)}</span>'
                f'<span class="zt__m">{html.escape(мета)}</span>{оценка}</span></a>')

    def логотип(self) -> str:
        """Логотип: хвост «dia» акцентом, как у эталона (без чужой иконки)."""
        имя = self.имя or "Animedia"
        if имя.lower().endswith("dia") and len(имя) > 3:
            база, хвост = имя[:-3], имя[-3:]
            return (f'<a class="zhd__logo" href="/">{html.escape(база)}'
                    f"<b>{html.escape(хвост)}</b></a>")
        return f'<a class="zhd__logo" href="/">{html.escape(имя)}</a>'

    def верхняя_карусель(self, набор) -> str:
        """Горизонтальная витрина постеров над сетками — ритм amd.online.

        Набор только из снимка каталога. Пустой набор не рисует полосу:
        красный пустой блок выглядел бы как сломанный герой.
        """
        if not набор:
            return ""
        return f'<div class="ahero" aria-label="Избранные тайтлы">{self.карусель("hero", набор)}</div>'

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
        if ключ in {"new_episodes", "new-episodes", "series_with_episodes",
                    "series-with-episodes"}:
            тело = self.лента(набор)
            return f'<section class="zsec zsec--eps">{шапка}{тело}</section>'
        return f'<section class="zsec">{шапка}{self.плитки(набор)}</section>'

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
                доступна = н in сезон["доступные"]
                текущая = (текущий == (сезон["n"], н))
                атрибуты = ' aria-current="page"' if текущая else (
                    "" if доступна else
                    ' data-off aria-disabled="true" title="Серия пока недоступна"')
                ссылки.append(
                    f'<a href="{self.адрес_эпизода(запись["slug"], сезон["n"], н)}"'
                    f"{атрибуты}>{н}</a>")
            хвост = ("" if сезон["доступно"] == сезон["eps"]
                     else f" · доступно {сезон['доступно']}")
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

    def подвал(self) -> str:
        домен = _аниме_домен(self.хост)
        жанры = "".join(
            f'<a href="/genre/{html.escape(код)}/">{html.escape(имя)}</a>'
            for код, имя in (self.индекс.get("genre_names") or [])[:8])
        runtime = (МАНИФЕСТ.get("runtime_commit") or МАНИФЕСТ.get("source_commit") or "")[:7]
        tip = (f"source={МАНИФЕСТ.get('source_commit', '')[:12]} "
               f"runtime={(МАНИФЕСТ.get('runtime_commit') or '')[:12]} "
               f"build={СБОРКА}")
        return (
            '<footer class="zft">'
            '<div class="zft__grid">'
            '<div class="zft__col"><b>Разделы</b>'
            '<a href="/">Главная</a><a href="/catalog/">Каталог</a>'
            '<a href="/new/">Новинки</a><a href="/collections/">Подборки</a>'
            '<a href="/schedule/">Расписание</a></div>'
            f'<div class="zft__col"><b>Жанры</b>{жанры or "<span>появятся из каталога</span>"}</div>'
            '<div class="zft__col"><b>Подборки</b>'
            '<a href="/collections/">Все подборки</a></div>'
            f'<div class="zft__col"><b>О сайте</b>'
            f'<p class="zft__about">{html.escape(домен["footer_about"])}</p></div>'
            "</div>"
            f'<div class="zft__bar"><span>© {html.escape(self.имя)}</span>'
            f'<span class="zvb" title="{html.escape(tip)}">'
            f"Animedia {html.escape(ВЕРСИЯ)} · {html.escape(runtime)}</span></div>"
            "</footer>")

    # --- честное состояние данных -------------------------------------
    def полоса_готовности(self) -> str:
        г = self.готовность
        if г["готово"]:
            return ""
        return (
            '<div class="ast" role="status">'
            '<b>Каталог аниме ещё не загружен</b>'
            f'Сейчас в каталоге {г["записей_в_снимке"]} записей, из них аниме '
            f'{г["из_них_аниме"]}. Остальные к этому сайту не относятся и здесь '
            'не показываются. Разделы, поиск и оформление работают — не хватает '
            'только самих данных аниме-каталога, и они пока не поступили.'
            '</div>')

    # --- каркас --------------------------------------------------------
    def оболочка(self, тело: str, титул: str, путь: str, *, актив: str = "",
                 описание: str = "", разметка: str | list = "", код: int = 200,
                 сверху: str = "", крошки: str = "", og: dict | None = None) -> str:
        домен = _аниме_домен(self.хост)
        нав = "".join(
            f'<a href="{закодировать_запрос(u)}"{ТЕКУЩАЯ_СТРАНИЦА if u == актив else ""}>{html.escape(t)}</a>'
            for u, t in self.се["нав"])
        схемы = _ld_json_scripts(разметка)
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
<meta name="robots" content="{мета_роботов_пути(путь)}">
{_открытый_граф(og_данные)}
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
{_мета_версии().replace(f'content="{ПРОФИЛЬ}"', f'content="{профиль_meta}"', 1)}
<style>{self.се["стиль"]()}</style><script>{СКРИПТ_ПОСТЕРОВ}
{СКРИПТ_ЛЕНТ}
{СКРИПТ_АНИМЕДИА_ШАПКА}</script></head>
<body><a class="skip" href="#main">Перейти к содержимому</a>
<div class="zs">
<header class="zhd">
<div class="zhd__in">
{self.логотип()}
<form class="zhd__s" action="/search/" method="get" role="search">
<label class="vh" for="q">Поиск по каталогу аниме</label>
<input id="q" name="q" placeholder="{html.escape(self.се["поиск"])}">
<button type="submit">Найти</button></form>
<button class="zhd__menu" type="button" data-nav-toggle aria-controls="zhd-nav"
 aria-expanded="false" aria-label="Меню разделов">&#9776;</button>
<nav id="zhd-nav" class="zhd__n" aria-label="Разделы">{нав}</nav>
</div>
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
            "ongoing": ("Онгоинги",
                        "Источник не передал признака «сейчас выходит», "
                        "поэтому определить выходящие сейчас нечем."),
            "new_episodes": ("Новые серии аниме",
                             "В снимке нет дат выхода отдельных серий."),
            "series_with_episodes": ("Сериалы с сериями",
                                     "В снимке нет сериалов с доступными сериями."),
            "today_schedule": ("Сегодня выйдет",
                               "Время выхода серий источником не передаётся ни одним "
                               "полем, поэтому сегодняшний день собрать не из чего."),
            "recently_added": ("Новые аниме на сайте",
                               "В снимке нет аниме с датой добавления."),
            "top_rated": ("Топ по оценкам", "Источник не передал оценок ни одному тайтлу."),
            "anime_movies": ("Аниме-фильмы", "В снимке нет полнометражных аниме."),
            "donghua": ("Дунхуа", "В снимке нет записей со страной Китай."),
            "video_available": ("С видео", "Ни у одной записи не подтверждена дорожка."),
        }
        ПОРЯДОК = ("series_with_episodes", "recently_added", "top_rated",
                   "anime_movies", "donghua", "video_available")
        снимок = Снимок.получить(self.д, self.п) if КОЛЛЕКЦИИ else None
        ленты = []
        занятые_полки: set[str] = set()
        if снимок is not None:
            for ключ in ПОРЯДОК:
                коллекция = КОЛЛЕКЦИИ.разрешить(ключ, снимок, СЕМЕЙСТВО, предел=48)
                if коллекция is None:
                    continue
                титул, причина = ПРИЧИНЫ.get(ключ, (коллекция.title, ""))
                набор = []
                for к in коллекция.items:
                    if к.raw.get("slug") in занятые_полки:
                        continue
                    набор.append(к.raw)
                    if len(набор) >= 24:
                        break
                for з in набор:
                    занятые_полки.add(з["slug"])
                ленты.append((ключ.replace("_", "-"), титул,
                              коллекция.view_all_path if набор else "",
                              набор, причина))
        else:
            ленты = [
                ("new-anime", "Новые аниме", "/new/", выбрать(свежесть),
                 "В снимке нет аниме с датой добавления."),
                ("top", "Топ по оценкам", "/catalog/", выбрать(оценка, пул=400),
                 "Источник не передал оценок ни одному тайтлу."),
            ]
        куски = [self.полоса_готовности(),
                 f'<h1 class="zh">{html.escape(_аниме_домен(self.хост)["h1"])}</h1>',
                 f'<p class="zsub">{html.escape(_аниме_домен(self.хост)["lead"])}</p>']
        # Верхняя карусель — первые постеры из уже собранных лент (без
        # отдельной выдуманной выборки). Источник = снимок; если лент нет —
        # полосы нет.
        герой = []
        for ключ, _титул, _ссылка, набор, _причина in ленты:
            for з in набор:
                if not з.get("poster"):
                    continue
                if з["slug"] in {г["slug"] for г in герой}:
                    continue
                герой.append(з)
                if len(герой) >= 12:
                    break
            if len(герой) >= 12:
                break
        if герой:
            куски.append(self.верхняя_карусель(герой))
        куски += [self.секция(*л) for л in ленты]
        домен = _аниме_домен(self.хост)
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
        """Каталог, новинки и подборки.

        Пустая страница без объяснения неотличима от сломанной, поэтому
        причина нехватки данных называется здесь так же, как на главной, а не
        только там, где о ней вспомнили.
        """
        готово = super().список(разд, зпр)
        полоса = self.полоса_готовности()
        if полоса and "<main id=\"main\">" in готово:
            готово = готово.replace("<main id=\"main\">", "<main id=\"main\">" + полоса, 1)
        return готово

    def поиск(self, зпр: dict) -> str:
        """Поиск. Пустая выдача объясняется тем же и теми же словами."""
        готово = super().поиск(зпр)
        полоса = self.полоса_готовности()
        if полоса and "<main id=\"main\">" in готово:
            готово = готово.replace("<main id=\"main\">", "<main id=\"main\">" + полоса, 1)
        return готово

    # --- расписание ----------------------------------------------------
    def расписание(self) -> str:
        """Расписание выхода серий.

        Дни недели объявлены всегда: раздел, исчезающий без данных,
        неотличим от нереализованного. Время и номер серии берутся только из
        источника; их отсутствие названо словами, а не заполнено правдоподобным
        значением — выдуманное расписание хуже пустого.
        """
        дни = ("Понедельник", "Вторник", "Среда", "Четверг",
               "Пятница", "Суббота", "Воскресенье")
        карточки = []
        for день in дни:
            карточки.append(
                f'<div class="asch__d"><h3>{день}</h3>'
                f'<ul class="asch__l"><li><span class="asch__n">'
                f'источник не передал времени и номера серии</span></li></ul></div>')
        тело = (self.полоса_готовности()
                + '<h1 class="zh">Расписание выхода серий</h1>'
                + '<p class="zsub">Время и номер серии берутся из источника. '
                  'Пока источник их не передаёт, дни показаны пустыми: '
                  'правдоподобное расписание опаснее пустого, потому что ему верят.</p>'
                + f'<div class="asch">{"".join(карточки)}</div>')
        return self.оболочка(тело, f"Расписание — {self.имя}", "/schedule/",
                             актив="/schedule/",
                             описание="Расписание выхода серий аниме.")


#: Вид Animedia появляется только у витрины, объявившей переработанное
#: оформление. Витрина на 1.0.2/1.1.0 исполняет прежнюю ветку и отдаёт прежние
#: байты — как и было до этой задачи.
ВИДЫ_1_1 = {"lords": ВидЛордс, "zona": ВидЗона}
if ОФОРМЛЕНИЕ_ПЕРЕРАБОТАННОЕ:
    ВИДЫ_1_1["animedia"] = ВидАнимедиа


def _дополнить_формы_поиска(запись: dict) -> None:
    """Rebuild `_формы` and `_фразы` after sidecar fields land on the item.

    Фразы пересобираются здесь же не для симметрии: указатель поиска строится
    по формам и фразам, и если оригинальное название доехало из sidecar, а
    фразы остались прежними, запрос по оригинальному названию не отберёт
    запись в кандидаты и выдача молча опустеет.
    """
    формы = [запись.get("_n") or нормализовать(запись.get("title") or "")]
    if запись.get("slug"):
        формы.append(нормализовать(запись["slug"]))
    if запись.get("title"):
        формы.append(нормализовать(транслит(запись["title"])))
    for поле in ("original_title", "original_name", "english_name", "alt_title"):
        if запись.get(поле):
            формы.append(нормализовать(запись[поле]))
            формы.append(нормализовать(транслит(запись[поле])))
    for доп in (запись.get("aliases") or []):
        формы.append(нормализовать(доп))
        формы.append(нормализовать(транслит(доп)))
    увидели: list[str] = []
    for ф in формы:
        if ф and ф not in увидели:
            увидели.append(ф)
    запись["_формы"] = увидели
    запись["_фразы"] = фразы_записи(запись)


#: Обратная карта алиасов стран. Считается один раз на процесс, а не заново на
#: каждую страну каждой карточки: прежний вложенный обход СТРАНЫ_АЛИАСЫ внутри
#: цикла по 53 688 записям был чистой повторной работой.
_ОБРАТНЫЕ_СТРАНЫ: dict[str, frozenset] = {}


def _ключи_страны(код: str) -> frozenset:
    """Все ключи, под которыми регистрируется страна."""
    if not _ОБРАТНЫЕ_СТРАНЫ:
        собранное: dict[str, set] = {}
        for канон_с, aliases in СТРАНЫ_АЛИАСЫ.items():
            семья = {канон_с, *aliases}
            for имя in семья:
                собранное.setdefault(имя, set()).update(семья)
        _ОБРАТНЫЕ_СТРАНЫ.update({к: frozenset(v) for к, v in собранное.items()})
    return _ОБРАТНЫЕ_СТРАНЫ.get(код) or frozenset({код})


#: Файл редакционных подборок ВИТРИНЫ. Состав принадлежит домену, а не
#: семейству: одинаковые подборки по сети запрещены. Путь переопределяется
#: переменной, как у плеера и манифеста, иначе стенд не подставит свой файл.
ПОДБОРКИ_ФАЙЛ = os.environ.get(
    "LORDS_COLLECTIONS",
    str(Path(МАНИФЕСТ_ФАЙЛ).parent / "collections.json"))


def польза_подборки(вступление: str, предел: int = 125) -> str:
    """Одно предложение о пользе подборки — из её вступления, без обрыва слова.

    На превью длинное вступление читать никто не будет: владелец 27.10 прямо
    потребовал убрать длинные описания с превью. Берётся первое предложение;
    если оно длиннее предела — обрезается по последнему пробелу и закрывается
    многоточием, чтобы не оборвать слово посередине.
    """
    текст = " ".join(str(вступление or "").split())
    if not текст:
        return ""
    for знак in (". ", "! ", "? "):
        место = текст.find(знак)
        if 0 < место <= предел:
            return текст[:место + 1].strip()
    if len(текст) <= предел:
        return текст
    край = текст.rfind(" ", 0, предел)
    return текст[:край if край > 40 else предел].rstrip(" ,;:—-") + "…"


#: Месяцы в родительном падеже: «20 ноября», а не «20 ноябрь». Отдельной
#: таблицей, потому что `strftime` на этой системе даёт именительный.
МЕСЯЦЫ_РОД = ("января", "февраля", "марта", "апреля", "мая", "июня", "июля",
              "августа", "сентября", "октября", "ноября", "декабря")


def _дата_анонса(iso: str) -> str:
    """ISO-дата человеческой строкой. Непонятную дату возвращаем как есть."""
    части = (iso or "").split("-")
    if len(части) != 3 or not all(ч.isdigit() for ч in части):
        return iso or ""
    год, месяц, день = int(части[0]), int(части[1]), int(части[2])
    if not 1 <= месяц <= 12:
        return iso
    return f"{день} {МЕСЯЦЫ_РОД[месяц - 1]} {год}"



#: Файл анонсов витрины. Отсутствие файла — рабочее состояние: блока просто
#: нет. Битый файл тоже не валит витрину и не выдумывает состав.
АНОНСЫ_ФАЙЛ = os.environ.get(
    "LORDS_ANNOUNCEMENTS",
    str(Path(МАНИФЕСТ_ФАЙЛ).parent / "announcements.json"))


def _анонсы() -> dict:
    """Объявленные релизы витрины или пустой словарь."""
    путь = Path(АНОНСЫ_ФАЙЛ)
    if not путь.is_file():
        return {}
    try:
        данные = json.loads(путь.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if str(данные.get("schema") or "") != "site-announcements/1":
        return {}
    return данные


АНОНСЫ = _анонсы()



def _ручные_подборки() -> dict:
    """{ключ: РучнаяПодборка} витрины. Пусто — значит витрина их не объявляет.

    Отсутствие файла — рабочее состояние, а не поломка: подборки появляются
    поставкой редакции. Битый файл тоже не валит витрину и не выдумывает
    состав: подборок просто нет, и это видно по пустому хабу.
    """
    if КОЛЛЕКЦИИ is None or not hasattr(КОЛЛЕКЦИИ, "ручные_подборки"):
        return {}
    путь = Path(ПОДБОРКИ_ФАЙЛ)
    if not путь.is_file():
        return {}
    try:
        данные = json.loads(путь.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {п.key: п for п in КОЛЛЕКЦИИ.ручные_подборки(данные) if п.key}


РУЧНЫЕ_ПОДБОРКИ = _ручные_подборки()
#: Ключи подборок, которые редакция объявила закрытыми. Решение исполняется
#: там, где отдаётся путь, — иначе оно держалось бы только на слое nginx.
ЗАКРЫТЫЕ_ПОДБОРКИ = frozenset(
    к for к, п in РУЧНЫЕ_ПОДБОРКИ.items() if not п.indexing_open)


def построить_индекс(данные: "Данные", подробности: Подробности,
                     уступать: bool = False) -> dict:
    """Индексы, которые дешевле построить один раз при старте.

    По slug — чтобы страница тайтла не искала запись перебором; по жанру и
    стране — чтобы filter query не перечитывал sidecar на каждый запрос.

    Also copies sidecar original/english names onto catalog items and rebuilds
    search forms so original-title queries resolve (P0-02).
    """
    по_slug = {з["slug"]: з for з in данные.items}
    # Пачки первоначального импорта помечаются ДО всего остального: их дата не
    # поступление, и ленты поступлений обязаны это знать. Считается по снимку,
    # поэтому переживает очередную доставку каталога.
    импортные = пакеты_импорта(данные.items)
    for з in данные.items:
        з["_импорт"] = bool(импортные) and (з.get("published_at") or "") in импортные
        # Дата выхода размечается при каждом построении индекса, то есть после
        # каждой доставки каталога. `published_at` в неё не входит, поэтому
        # повторный импорт и смена озвучки новизну не меняют (T284).
        НОВИЗНА.разметить(з, подробности.записи.get(з["slug"]))
    # Бакеты — словари, а не списки. Раньше принадлежность проверялась
    # перебором списка (`if slug not in бакет`), и на 53 688 карточках это
    # квадратично: популярный жанр с 30 000 участников стоил 30 000 сравнений
    # на каждую вставку. Измерено: 218.5 с из 224.5 с всей загрузки снимка.
    # Словарь сохраняет порядок вставки, поэтому выдача не меняется.
    по_жанру: dict[str, dict] = {}
    по_стране: dict[str, dict] = {}
    имена: dict[str, str] = {}
    имена_стран: dict[str, str] = {}
    # Категория раздела (фильм / сериал / анимация / дорама). Считается здесь
    # потому, что этот проход по подробностям уже есть: отдельный обход тех же
    # 53 688 записей стоил бы второй загрузки снимка.
    по_категории: dict[str, dict] = {}
    # Уступка процессора. Перестроение считает 11.6 с подряд и держит GIL:
    # обработчики запросов в это время ждут, и поиск отвечал 8.8 с вместо
    # обычных десятков миллисекунд. Короткий sleep раз в несколько тысяч
    # записей отдаёт GIL и стоит доли секунды на всю сборку.
    шаг_уступки = 2000 if уступать else 0
    for номер, (slug, деталь) in enumerate(подробности.записи.items()):
        if шаг_уступки and номер % шаг_уступки == 0:
            time.sleep(0.001)
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
        # Votes from ratings_by_source when present (for rating sort soft floor).
        голоса = 0
        by_src = деталь.get("ratings_by_source") or {}
        if isinstance(by_src, dict):
            for блок in by_src.values():
                if isinstance(блок, dict):
                    try:
                        голоса = max(голоса, int(блок.get("votes") or 0))
                    except (TypeError, ValueError):
                        pass
        if голоса:
            запись["_votes"] = голоса
        prem = (деталь.get("premiere_date") or "").strip()
        if prem:
            запись["_premiere_date"] = prem[:10]
        if КАТЕГОРИИ_КАТАЛОГА is not None:
            кат = КАТЕГОРИИ_КАТАЛОГА.категория(запись, деталь)
            запись["_ck"] = кат
            по_категории.setdefault(кат, {})[slug] = None
        # P0-02: join sidecar original names into search forms.
        names_changed = False
        for поле in ("original_name", "english_name", "original_title"):
            знач = (деталь.get(поле) or "").strip()
            if знач and not запись.get(поле):
                запись[поле] = знач
                names_changed = True
        if names_changed or not запись.get("_формы"):
            _дополнить_формы_поиска(запись)
        жанры = деталь.get("genres") or []
        коды = list(деталь.get("genre_codes") or [])
        # Animedia sidecar часто отдаёт только русские имена без genre_codes.
        # Без кодов индекс жанров пуст, и любой ?genre= даёт «Найдено 0».
        # Код — латиница (как /genre/<code>/), имя остаётся русским для UI.
        if not коды and жанры:
            коды = [нормализовать(транслит(г)) for г in жанры]
            коды = [к for к in коды if к]
        # P0-01: register every alias of each genre under one membership set.
        ключи_регистрации: set[str] = set()
        for i, код in enumerate(коды):
            if not код:
                continue
            ключи_регистрации.add(код)
            if ЖАНРЫ_АЛИАСЫ is not None:
                ключи_регистрации |= set(ЖАНРЫ_АЛИАСЫ.алиасы_жанра(код))
            if i < len(жанры) and жанры[i]:
                ключи_регистрации.add(нормализовать(жанры[i]))
                ключи_регистрации.add(нормализовать(транслит(жанры[i])))
                if ЖАНРЫ_АЛИАСЫ is not None:
                    ключи_регистрации |= set(ЖАНРЫ_АЛИАСЫ.алиасы_жанра(жанры[i]))
            # Prefer Russian label for UI when available.
            канон = (ЖАНРЫ_АЛИАСЫ.канон_жанра(код) if ЖАНРЫ_АЛИАСЫ else None) or код
            if i < len(жанры) and жанры[i]:
                имена.setdefault(канон, жанры[i])
            else:
                имена.setdefault(канон, код)
        for ключ in ключи_регистрации:
            if not ключ:
                continue
            по_жанру.setdefault(ключ, {})[slug] = None
        for страна in (деталь.get("countries") or []):
            # ASCII slug for /country/<code>/ (regex is [a-z0-9_-]); Cyrillic
            # labels stay in country_names for UI.
            код = нормализовать(транслит(страна))
            if not код:
                continue
            # Register common aliases onto the same membership bucket.
            ключи_страны = _ключи_страны(код)
            for ключ_с in ключи_страны:
                if not ключ_с:
                    continue
                по_стране.setdefault(ключ_с, {})[slug] = None
            имена_стран.setdefault(код, страна)
    # Prefer canonical codes in genre_names ordering when aliases collapsed.
    порядок = sorted(имена.items(), key=lambda п: -len(по_жанру.get(п[0], ())))
    порядок_стран = sorted(имена_стран.items(),
                           key=lambda п: -len(по_стране.get(п[0], ())))
    # Формы названий только что дополнены оригинальными именами из sidecar —
    # указатель поиска, если он уже был собран, устарел на эту разницу.
    данные.сбросить_указатель()
    # Записи без подробностей категорию по снимку всё равно получают: раздел,
    # в котором запись не показывается вовсе, — та же потеря, что и неверный.
    if КАТЕГОРИИ_КАТАЛОГА is not None:
        for slug, запись in по_slug.items():
            if запись.get("_ck"):
                continue
            кат = КАТЕГОРИИ_КАТАЛОГА.категория(запись, None)
            запись["_ck"] = кат
            по_категории.setdefault(кат, {})[slug] = None
    return {"slug": по_slug,
            "import_batches": sorted(импортные),
            "catalog_kind": {к: list(v) for к, v in по_категории.items()},
            "genre": {к: list(v) for к, v in по_жанру.items()},
            "genre_names": порядок,
            "country": {к: list(v) for к, v in по_стране.items()},
            "country_names": порядок_стран,
            "country_aliases": dict(СТРАНЫ_АЛИАСЫ)}



#: Ключи запроса, которые витрина читает (собрано из кода; apply-unknown-keys-noindex).
_ИЗВЕСТНЫЕ_КЛЮЧИ_ЗАПРОСА = frozenset(['community', 'country', 'from', 'genre', 'kind', 'mode', 'page', 'q', 'sort', 'why', 'year'])


def _лишние_ключи_запроса(путь: str) -> list[str]:
    """Ключи вне перечня витрины и повторённые ключи — причина noindex."""
    from urllib.parse import parse_qsl as _пары, urlsplit as _адрес
    ключи = [к for к, _ in _пары(_адрес(путь).query, keep_blank_values=True)]
    лишние = sorted({к for к in ключи if к not in _ИЗВЕСТНЫЕ_КЛЮЧИ_ЗАПРОСА})
    повторы = sorted({к for к in ключи if ключи.count(к) > 1})
    return лишние + [f"{к} (повтор)" for к in повторы]



def _поиск_по_сайту(путь: str) -> bool:
    """Внутренний поиск не индексируется (§3 п.2; apply-search-noindex)."""
    from urllib.parse import urlsplit as _адрес
    return _адрес(путь).path.rstrip("/") == "/search"

def _служебный_раздел_жанра(путь: str) -> bool:
    """Раздел служебной метки поставщика — не индексируется (T044).

    Замер 13.10: «западный контент» стоит у 40 947 из 62 978 записей, ссылкой
    в жанрах карточки ведёт на /catalog/?genre=west_content — 200, index,
    canonical на себя, H1 «Западный контент». Это раздел витрины поставщика,
    а не тема: страница остаётся (ссылки не ломаются), но в индекс не просится.
    Метки — _ТЕХНИЧЕСКИЕ_ЖАНРЫ, та же, что исключает их из карты (T032).
    """
    from urllib.parse import parse_qs as _разбор, urlsplit as _адрес
    адрес = _адрес(путь)
    if адрес.path.rstrip("/") not in ("/catalog", "/movies", "/series", "/animation", "/doramas", "/new"):
        return False
    жанры = _разбор(адрес.query).get("genre") or []
    if len(жанры) != 1:
        return False
    индекс = getattr(globals().get("Обработчик"), "индекс", None) or {}
    значение = жанры[0].strip()
    имя = dict(индекс.get("genre_names") or []).get(значение, "")
    # Те же формы метки, что отсекает строка жанров карточки: у одной метки
    # бывает два кода (west_content и zapadnyykontent — по 40 947 записей).
    метки = {нормализовать(м) for м in (*(globals().get("_ТЕХНИЧЕСКИЕ_ЖАНРЫ") or ()),
                                        "west_content", "zapadnyy-kontent")}
    return нормализовать(str(имя)) in метки or нормализовать(значение) in метки


def _закрытые_роботы(значение: str) -> str:
    return "noindex, nofollow" if "nofollow" in значение.lower() else "noindex, follow"


def _закрыть_индекс_в_теле(тело: bytes) -> bytes:
    import re as _re
    try:
        текст = тело.decode("utf-8")
    except UnicodeDecodeError:
        return тело
    найдено = _re.search(r'<meta name="robots" content="([^"]*)"\s*/?>', текст)
    if найдено:
        if "noindex" in найдено.group(1).lower():
            return тело
        новое = f'<meta name="robots" content="{_закрытые_роботы(найдено.group(1))}">'
        return (текст[:найдено.start()] + новое + текст[найдено.end():]).encode("utf-8")
    if "</head>" in текст:
        return текст.replace("</head>", '<meta name="robots" content="noindex, follow"></head>', 1).encode("utf-8")
    return тело

class Обработчик(BaseHTTPRequestHandler):
    server_version = "site-factory-nova"
    данные: Данные = None  # проставляется при запуске
    подробности: Подробности = None  # то же: боковой файл подробностей
    индекс: dict = None  # индексы по slug и жанру
    правки = None  # редакторские правки: см. editorial_overlay
    _snapshot_lock = threading.Lock()
    #: Идёт ли перестроение снимка. Второй поток не нужен: он читал бы те же
    #: файлы и строил тот же индекс, отнимая процессор у ответов.
    _rebuild_in_progress = False

    def log_message(self, *a):
        pass

    @classmethod
    def _ensure_fresh_snapshots(cls) -> bool:
        """Reload catalog/details when authorized snapshot files change.

        Atomic publish updates zona-01-*.json without a frontend deploy. Without
        this check the process kept last-good membership until restart, so a
        successful daily publish that skipped restart would leave shelves stale.
        Empty/unreadable updates keep the previous in-memory snapshot.

        Always mutates the base ``Обработчик`` class attributes: test stubs
        subclass the handler, and assigning on the subclass would shadow the
        process-wide snapshot the next request still reads from the base.
        """
        target = Обработчик
        cat_path = Path(КАТАЛОГ_ФАЙЛ)
        det_path = Path(ПОДРОБНОСТИ_ФАЙЛ) if ПОДРОБНОСТИ_ФАЙЛ else None
        try:
            cat_mtime = cat_path.stat().st_mtime
        except OSError:
            return False
        det_mtime = 0.0
        if det_path is not None:
            try:
                det_mtime = det_path.stat().st_mtime
            except OSError:
                det_mtime = getattr(target.подробности, "mtime", 0.0) or 0.0
        cur_cat = getattr(target.данные, "mtime", 0.0) or 0.0
        cur_det = getattr(target.подробности, "mtime", 0.0) or 0.0
        if cat_mtime <= cur_cat and det_mtime <= cur_det:
            return False
        with target._snapshot_lock:
            cur_cat = getattr(target.данные, "mtime", 0.0) or 0.0
            cur_det = getattr(target.подробности, "mtime", 0.0) or 0.0
            if cat_mtime <= cur_cat and det_mtime <= cur_det:
                return False
            # Перестроение идёт в фоне: запрос, первым заметивший новый
            # снимок, раньше ждал всю сборку сам. Даже после ускорения индекса
            # (218 с -> 12 с) это означало бы один очень долгий ответ на каждое
            # обновление каталога. Остальные запросы и до, и во время сборки
            # обслуживаются ПРЕЖНИМ снимком: он остаётся в памяти нетронутым,
            # пока новый не готов целиком.
            if target._rebuild_in_progress:
                return False
            target._rebuild_in_progress = True
            поток = threading.Thread(target=cls._перестроить, daemon=True,
                                     name="snapshot-rebuild")
            поток.start()
            return False

    @classmethod
    def _перестроить(cls) -> None:
        """Собрать новый снимок целиком и подменить его под замком.

        Подмена — три присваивания, а не одно: согласованность запроса даёт не
        она, а `_закрепить_снимок`, снимающее тройку под тем же замком.

        При любой ошибке рабочий снимок остаётся прежним: половина каталога
        хуже вчерашнего целого, потому что выглядит как настоящий ответ.
        """
        target = Обработчик
        try:
            новые_данные = Данные(КАТАЛОГ_ФАЙЛ)
            if not новые_данные.items:
                return
            try:
                новые_подробности = Подробности(ПОДРОБНОСТИ_ФАЙЛ)
            except (OSError, ValueError, KeyError, json.JSONDecodeError):
                новые_подробности = target.подробности
            # В фоне уступаем процессор: иначе сборка съедает GIL и живые
            # запросы ждут её целиком.
            новый_индекс = построить_индекс(новые_данные, новые_подробности,
                                            уступать=True)
            # Указатель поиска строится ЗДЕСЬ, до подмены. Он ленивый: без
            # этой строки его собирал первый же поисковый запрос после
            # подмены — синхронно, в своём потоке, и посетитель ждал 7-8 с
            # вместо десятков миллисекунд. Фоновая сборка обязана отдавать
            # снимок готовым целиком, а не почти готовым.
            try:
                новые_данные._построить_указатель()
            except Exception:  # noqa: BLE001 — указатель не обязателен для показа
                pass
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            # Флаг обязателен к сбросу: иначе одна неудачная сборка заморозила
            # бы обновления навсегда, и витрина осталась бы на старом каталоге
            # без единой жалобы.
            target._rebuild_in_progress = False
            return
        with target._snapshot_lock:
            target.данные = новые_данные
            target.подробности = новые_подробности
            target.индекс = новый_индекс
            Снимок.сбросить()
        target._rebuild_in_progress = False

    def send_header(self, keyword, value):
        # Ужесточение X-Robots-Tag для адресов с лишними ключами (см. _отдать).
        if (str(keyword).lower() == "x-robots-tag" and getattr(self, "_закрыть_индекс", False)
                and "noindex" not in str(value).lower()):
            value = _закрытые_роботы(str(value))
        return super().send_header(keyword, value)

    def _отдать(self, тело: bytes, тип="text/html; charset=utf-8", код=200, *, без_индекса: bool = False):
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
        # Неизвестный или повторённый ключ запроса — noindex (SEO_KNOWLEDGE_PACK
        # §3 п.2–3; apply-unknown-keys-noindex). Только ужесточение.
        self._закрыть_индекс = bool(
            код == 200 and "text/html" in тип and (_лишние_ключи_запроса(self.path or "/") or _поиск_по_сайту(self.path or "/")
                                                   or _служебный_раздел_жанра(self.path or "/")))
        # Серия без дорожки и сезон без единой доступной серии (T055 Lords,
        # перенесено T202): страница 200, но смотреть на ней нечего. Живой
        # замер 18.10 на zonafilm.space: index, follow и canonical на себя,
        # ссылки из списка серий тайтла. Ссылки остаются, страница не
        # просится в индекс, пока источник не отдаст серию.
        if без_индекса and "text/html" in тип:
            self._закрыть_индекс = True
        if self._закрыть_индекс:
            тело = _закрыть_индекс_в_теле(тело)
        self.send_response(код)
        self.send_header("Content-Type", тип)
        self.send_header("Content-Length", str(len(тело)))
        # В ОБОИХ режимах и явным значением: по отсутствию заголовка нельзя
        # отличить открытый сайт от витрины, которая про режим не знает.
        self.send_header("X-Robots-Tag",
                         мета_роботов_пути(self.path or "/"))
        self.send_header("X-Site-Factory-Template-Revision", МАНИФЕСТ["source_commit"])
        self.send_header("X-Site-Factory-Template", ШАБЛОН_СЕМЕЙСТВА)
        self.send_header("X-Site-Factory-Core", ЯДРО)
        self.send_header("X-Site-Factory-Profile", ПРОФИЛЬ)
        self.send_header("X-Site-Factory-Template-Family", СЕМЕЙСТВО)
        self.send_header("X-Site-Factory-Template-Version", ВЕРСИЯ)
        self.send_header("X-Site-Factory-Build-Id", СБОРКА)
        self.send_header("X-Site-Factory-Artifact-Sha256", МАНИФЕСТ["artifact_sha256"])
        # Значения ниже приходят из доставленных данных, а не из кода, и
        # потому пропускаются через `безопасный_заголовок`: одна некодируемая
        # буква в них роняла ответ целиком, на каждой странице.
        рев = безопасный_заголовок(getattr(self.данные, "revision", ""))
        built = безопасный_заголовок(getattr(self.данные, "built_at", ""))
        if рев:
            self.send_header("X-Catalog-Revision", рев)
        if built:
            self.send_header("X-Catalog-Built-At", built)
        weekly = _popular_weekly_snapshot()
        week_id = безопасный_заголовок((weekly or {}).get("week_id") or "")
        week_digest = безопасный_заголовок((weekly or {}).get("digest") or "")
        if week_id:
            self.send_header("X-Popular-Week-Id", week_id)
        if week_digest:
            self.send_header("X-Popular-Weekly-Digest", week_digest[:32])
        # Digest participates in cache identity for any intermediary that
        # ignores no-store; browser/CDN must not reuse across revisions.
        etag_parts = []
        if рев:
            etag_parts.append(f"cat-{рев}")
        if week_id and week_digest:
            etag_parts.append(f"pop-{week_id}-{week_digest[:16]}")
        if etag_parts:
            self.send_header("ETag", f'W/"{"|".join(etag_parts)}"')
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(тело)

    def do_HEAD(self):
        self.do_GET()

    # --- переходник к модулю сообщества -----------------------------------
    # Запись голоса приходит на витрину только затем, чтобы уйти к модулю с
    # того же происхождения, что и страница. Витрина не проверяет голос и не
    # хранит его: проверки Origin, пары CSRF, идентичности и идемпотентности —
    # в модуле, и работают они ровно потому, что запрос выглядит для браузера
    # как обращение к своему сайту. Собственная проверка здесь означала бы
    # вторую реализацию защиты записи рядом с утверждённой.
    def do_POST(self):
        return self._переходник_сообщества("POST")

    def do_PUT(self):
        return self._переходник_сообщества("PUT")

    def do_DELETE(self):
        return self._переходник_сообщества("DELETE")

    def do_OPTIONS(self):
        return self._переходник_сообщества("OPTIONS")

    def _переходник_сообщества(self, метод: str):
        """`/api/community/ratings/*` → шлюз модуля на петле."""
        путь = unquote(urlparse(self.path).path)
        if СООБЩЕСТВО is None or not СООБЩЕСТВО.это_api(путь):
            # Ни одного другого метода, кроме GET и HEAD, витрина не
            # обслуживает. Отказ назван, а не выдан пустым соединением.
            return self._отдать(
                json.dumps({"status": 405, "error": "method not allowed"},
                           ensure_ascii=False).encode("utf-8"),
                "application/json; charset=utf-8", код=405)
        try:
            длина = int(self.headers.get("Content-Length") or 0)
        except (TypeError, ValueError):
            длина = 0
        if длина > СООБЩЕСТВО.ПРЕДЕЛ_ТЕЛА:
            return self._отдать(
                json.dumps({"status": 413, "error": "body too large"},
                           ensure_ascii=False).encode("utf-8"),
                "application/json; charset=utf-8", код=413)
        тело = self.rfile.read(длина) if длина > 0 else b""
        заголовки = {и: self.headers.get(и) for и in СООБЩЕСТВО.ЗАПРОС_ЗАГОЛОВКИ
                     if self.headers.get(и)}
        клиент = self.client_address[0] if self.client_address else ""
        # Настоящий адрес посетителя за nginx приходит в X-Real-IP; принимать
        # его от кого угодно нельзя, поэтому он берётся только когда сосед по
        # соединению — петля, и передаётся дальше как есть. Модуль сам
        # оговаривает, что идентичностью этот адрес не считает.
        if клиент in ("127.0.0.1", "::1"):
            прямой = (self.headers.get("X-Real-IP") or "").strip()
            if прямой and "," not in прямой:
                клиент = прямой
        with_query = urlparse(self.path)
        полный = путь + (f"?{with_query.query}" if with_query.query else "")
        код, исходящие, данные = СООБЩЕСТВО.передать(
            метод, полный, тело, заголовки, peer_ip=клиент)
        self.send_response(код)
        отдан_тип = False
        for имя, значение in исходящие.items():
            if имя == "Set-Cookie" and isinstance(значение, list):
                for одна in значение:
                    self.send_header("Set-Cookie", одна)
                continue
            if имя == "Content-Type":
                отдан_тип = True
            self.send_header(имя, значение)
        if not отдан_тип:
            self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(данные)))
        # Ответ модуля не кэшируется и не индексируется: это состояние голоса
        # конкретного посетителя.
        self.send_header("X-Robots-Tag", "noindex, nofollow")
        self.end_headers()
        if метод != "HEAD":
            self.wfile.write(данные)
        return None

    def _закрепить_снимок(self) -> None:
        """Закрепить за запросом ОДИН снимок: данные, подробности и индекс.

        Подмена в `_перестроить` — три присваивания. Каждое атомарно само по
        себе, но запрос читает `self.данные` в начале, а `self.индекс` — позже,
        при разборе маршрута, и между этими чтениями проходит время отрисовки.
        Попав на подмену, запрос видел половину старого снимка и половину
        нового: новая карточка уже в списках, а маршрут её ещё не знает —
        `/title/<новый slug>/` отвечал 404 на ссылку, которую витрина сама же
        только что показала. Обратный порядок чтений даёт обратный перекос:
        индекс указывает на запись, которой в данных ещё нет.

        Замок `_snapshot_lock` этого не закрывал: он сериализует перестроение,
        а читающие запросы его не берут вовсе. Здесь тройка снимается под тем
        же замком, под которым подменяется, и кладётся в атрибуты экземпляра —
        они закрывают классовые, и все дальнейшие чтения запроса идут по
        закреплённому снимку. Читаем через `type(self)`, а не через
        `Обработчик`, чтобы подкласс-заглушка в тестах по-прежнему закрывал
        снимок процесса.

        Закрепление повторяется на каждом запросе: при keep-alive один
        экземпляр обслуживает их несколько, и снятое однажды значение
        заморозило бы соединение на прежнем каталоге до его разрыва.
        """
        к = type(self)
        with Обработчик._snapshot_lock:
            д, п, и = к.данные, к.подробности, к.индекс
            пр = к.правки
        self.данные, self.подробности, self.индекс = д, п, и
        # Правки перечитываются по mtime — тем же способом, что снимок, и той
        # же ценой в один stat. Перечитывание ДО закрепления: иначе правка,
        # опубликованная секунду назад, ждала бы следующего запроса.
        if пр is not None:
            try:
                пр.перечитать()
            except Exception:  # noqa: BLE001 — витрина важнее правок
                pass
        self.правки = пр

    def do_GET(self):
        self._ensure_fresh_snapshots()
        self._закрепить_снимок()
        д = self.данные
        разбор = urlparse(self.path)
        путь = unquote(разбор.path)
        зпр = parse_qs(разбор.query)

        if путь == "/__editorial_status":
            # Машинный ответ на вопрос «почему правок не видно». Без него
            # отсутствие правки на странице неотличимо от отсутствия правки в
            # файле, от чужого site_id и от испорченного файла.
            свод = (self.правки.состояние() if self.правки is not None
                    else {"status": "модуль правок не подключён",
                          "entries": 0, "site_id": ИДЕНТИФИКАТОР_САЙТА})
            свод["runtime_site_id"] = ИДЕНТИФИКАТОР_САЙТА
            return self._отдать(
                json.dumps(свод, ensure_ascii=False).encode("utf-8"),
                "application/json; charset=utf-8")

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
        # --- модуль сообщества --------------------------------------------
        # Состояние интеграции объявлено отдельной точкой: «голосования нет»
        # без названной причины неотличимо от «сломалось».
        if путь == "/__community_status" and СООБЩЕСТВО is not None:
            return self._отдать(
                json.dumps(СООБЩЕСТВО.состояние(), ensure_ascii=False).encode("utf-8"),
                "application/json; charset=utf-8")
        if СООБЩЕСТВО is not None:
            имя = СООБЩЕСТВО.имя_ассета(путь)
            if имя:
                прочитано = СООБЩЕСТВО.прочитать_ассет(имя)
                if прочитано is None:
                    return self._отдать(b"", "text/plain; charset=utf-8", код=404)
                данные, тип = прочитано
                return self._отдать(данные, тип)
            if СООБЩЕСТВО.это_api(путь):
                return self._переходник_сообщества("GET")
        if путь == "/healthz":
            return self._отдать(b'{"ok":true}', "application/json")
        if путь == "/assets/nova.webmanifest":
            м = json.dumps({"name": ИМЯ_ВИТРИНЫ, "template": ШАБЛОН_СЕМЕЙСТВА,
                            "core": ЯДРО, "family": СЕМЕЙСТВО, "profile": ПРОФИЛЬ,
                            "revision": РЕВИЗИЯ, "display": "standalone"}, ensure_ascii=False)
            return self._отдать(м.encode(), "application/manifest+json")
        if путь == "/sitemap.xml" or re.fullmatch(r"/sitemap-\d+\.xml", путь):
            # Закрытая витрина карту не отдаёт даже при готовых файлах: карта —
            # приглашение к обходу, и на закрытом домене она противоречила бы
            # и заголовку, и robots.txt. Это ВТОРОЙ, независимый рубеж: сами
            # файлы снимает сборщик (`seo_layer.снять_карту`), потому что у
            # витрин на общем ядре этой проверки в маршруте нет, а править
            # ядро в репозитории сайта запрещено его же правилами.
            if режим_индексации()[0] != "OPEN":
                return self._отдать(b"", "text/plain; charset=utf-8", код=404)
            if not SITEMAP_DIR:
                return self._отдать(b"", "text/plain; charset=utf-8", код=404)
            try:
                данные = (Path(SITEMAP_DIR) / путь.lstrip("/")).read_bytes()
            except OSError:
                return self._отдать(b"", "text/plain; charset=utf-8", код=404)
            return self._отдать(данные, "application/xml; charset=utf-8")
        if путь.startswith("/poster/"):
            код, тело, тип = отдать_постер(путь[len("/poster/"):],
                                            разбор.query)
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
            return self._отдать(_тело_robots().encode("utf-8"),
                                "text/plain; charset=utf-8")
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
    #: Полная страница коллекции. Тот же ключ, что и у ленты на главной, —
    #: именно поэтому первые карточки страницы совпадают с лентой.
    #: Дефис в ключе разрешён: ключи редакционных подборок пишутся
    #: словами через дефис (`trillery-na-vecher-2026`), и прежний
    #: образец их не принимал — выпущенная подборка отдавала бы 404
    #: по своему же адресу.
    МАРШРУТ_КОЛЛЕКЦИИ = re.compile(r"^/collection/(?P<key>[a-z0-9_-]{1,60})/$")

    #: Адреса, существовавшие до 1.1.0. Каждый уводит РОВНО одним переходом на
    #: действующий раздел: молча отдавать по ним 404 значило бы терять ссылки,
    #: которые уже кем-то сохранены.
    ПРЕЖНИЕ_АДРЕСА = {"/schedule/": "/new/", "/genres/": "/catalog/"}

    #: Чистые маршруты разделов. Query kind must redirect — never silently
    #: ignore. У Zona это категории (появляется «/doramas», «/animation»
    #: включает аниме и дунхуа); у остальных семейств — прежние значения `kind`,
    #: потому что категорий у них нет и подменять им разделы эта правка не
    #: должна.
    МАРШРУТЫ_ВИДА = (dict(КАТЕГОРИЯ_ПО_МАРШРУТУ)
                     if (СЕМЕЙСТВО == "zona" and КАТЕГОРИИ_КАТАЛОГА is not None)
                     else dict(ВИД_ПО_МАРШРУТУ))

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
        экземпляр.правки = self.правки
        return экземпляр

    def _отдать_вид(self, в, тело: str):
        """Отдать страницу вида с кодом, который вид назначил сам (404 пустого фильтра).

        Код снимается с вида после отдачи: вид, переживший запрос, не должен
        отдать следующую страницу с чужим кодом.
        """
        код = getattr(в, "_код_ответа", 200)
        в.__dict__.pop("_код_ответа", None)
        return self._отдать(тело.encode("utf-8"), код=код)

    def _переход(self, цель: str):
        self.send_response(308)
        self.send_header("Location", цель)
        self.send_header("Content-Length", "0")
        self.end_headers()
        return True

    def _page_gate(self, в: "Вид", путь: str, разд: str, зпр: dict,
                   path_kind: str | None):
        """Validate ?page= before render. Returns truthy if response already sent."""
        raw = (зпр.get("page") or [None])[0]
        if raw is None:
            return None
        if not str(raw).isdigit() or int(raw) < 1:
            # Страница ошибки без выхода — тупик: читатель понял, что ввёл
            # ерунду, и не понял, куда деваться. Раздел, из которого он пришёл,
            # известен — на него и уводим.
            назад = f"{разд}/" if разд else "/catalog/"
            тело = ('<!doctype html><html lang="ru"><meta charset="utf-8">'
                    "<title>400</title>"
                    "<h1>Некорректный номер страницы</h1>"
                    "<p>Номер страницы должен быть целым числом больше нуля.</p>"
                    f'<p><a href="{html.escape(назад)}">Вернуться в раздел</a> '
                    '· <a href="/catalog/">Открыть каталог</a></p></html>')
            self._отдать(тело.encode("utf-8"), код=400)
            return True
        page = int(raw)
        # Strip ?page=1 → canonical without page.
        if page == 1:
            keep = {к: (зпр.get(к) or [None])[0]
                    for к in ("kind", "year", "genre", "country", "sort")
                    if (зпр.get(к) or [None])[0]}
            if path_kind:
                keep.pop("kind", None)
            qs = запрос_строкой(keep)
            return self._переход(f"{разд}/{qs}")
        зпр2 = dict(зпр)
        if path_kind:
            зпр2["kind"] = [path_kind]
        набор, _ = отбор(self.данные, self.индекс, зпр2, разд)
        всего = max(1, (len(набор) + НА_СТРАНИЦЕ_1_1 - 1) // НА_СТРАНИЦЕ_1_1) if набор else 1
        if not набор:
            всего = 1
        if page > всего:
            self._отдать(в.не_найдено(путь).encode("utf-8"), код=404)
            return True
        return None

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
            return self._отдать(self._главная_из_памяти(в).encode("utf-8"))
        # Clean kind routes. Conflicting/redundant ?kind= → one 308 redirect.
        if обрезанный in self.МАРШРУТЫ_ВИДА:
            path_kind = self.МАРШРУТЫ_ВИДА[обрезанный]
            q_kind = (зпр.get("kind") or [None])[0]
            # Preserve non-kind params; drop kind from canonical query.
            keep = {к: (зпр.get(к) or [None])[0]
                    for к in ("year", "genre", "country", "sort", "page")
                    if (зпр.get(к) or [None])[0]}
            if q_kind and q_kind != path_kind:
                цель_путь = (МАРШРУТ_ПО_КАТЕГОРИИ.get(q_kind)
                             or МАРШРУТ_ПО_ВИДУ.get(q_kind))
                if not цель_путь:
                    return self._отдать(в.не_найдено(путь).encode("utf-8"), код=404)
                # Reset page on kind change.
                keep.pop("page", None)
                qs = запрос_строкой(keep)
                return self._переход(f"{цель_путь}/{qs}")
            if q_kind == path_kind:
                qs = запрос_строкой(keep)
                return self._переход(f"{обрезанный}/{qs}")
            # page gates before render
            gated = self._page_gate(в, путь, обрезанный, зпр, path_kind)
            if gated is not None:
                return gated
            зпр = dict(зпр)
            зпр["kind"] = [path_kind]
            return self._отдать_вид(в, в.список(обрезанный, зпр))
        if обрезанный in ("/catalog", "/new"):
            gated = self._page_gate(в, путь, обрезанный, зпр, None)
            if gated is not None:
                return gated
            return self._отдать_вид(в, в.список(обрезанный, зпр))
        if обрезанный == "/collections":
            if СЕМЕЙСТВО == "lords" and hasattr(в, "хаб_подборок"):
                return self._отдать(в.хаб_подборок().encode("utf-8"))
            return self._отдать_вид(в, в.список(обрезанный, зпр))
        if обрезанный == "/search":
            тело = в.поиск(зпр)
            код = 404 if 'class="znf"' in тело else 200
            return self._отдать(тело.encode("utf-8"), код=код)
        коллекция = self.МАРШРУТ_КОЛЛЕКЦИИ.match(путь)
        if коллекция is not None:
            return self.маршрут_коллекции(в, коллекция.group("key"), путь, зпр)

        год = self.МАРШРУТ_ГОДА.match(путь)
        if год:
            зпр = dict(зпр)
            зпр["year"] = [год.group("year")]
            # Номер страницы путевого фасета разбирается тем же _page_gate, что
            # и в каталоге: 0/abc → 400, за пределом → 404, ?page=1 → 308.
            # Прежде ?page=0/abc отдавали первую страницу, ?page=9999 — пустой
            # шаблон с 200 (soft 404, REQ-SEO-PAGINATION п.8; приёмка 11.10).
            if self._page_gate(в, путь, "/catalog", зпр, None):
                return None
            return self._отдать_вид(в, в.список("/catalog", зпр))
        страна = self.МАРШРУТ_СТРАНЫ.match(путь)
        if страна:
            код = страна.group("code")
            страны = self.индекс.get("country") or {}
            if код not in страны:
                resolved = _канон_страны(код, страны)
                if resolved is None:
                    return self._отдать(в.не_найдено(путь).encode("utf-8"), код=404)
                keep = {к: (зпр.get(к) or [None])[0]
                        for к in ("kind", "year", "genre", "sort", "page")
                        if (зпр.get(к) or [None])[0]}
                keep["country"] = resolved
                return self._переход("/catalog/" + запрос_строкой(keep))
            зпр = dict(зпр)
            зпр["country"] = [код]
            if self._page_gate(в, путь, "/catalog", зпр, None):
                return None
            return self._отдать_вид(в, в.список("/catalog", зпр))

        жанр = self.МАРШРУТ_ЖАНРА.match(путь)
        if жанр:
            код = жанр.group("code")
            if код not in self.индекс["genre"]:
                return self._отдать(в.не_найдено(путь).encode("utf-8"), код=404)
            # Канон жанра для Lords — path /genre/<code>/; комбинации остаются query.
            if СЕМЕЙСТВО == "lords":
                зпр = dict(зпр)
                зпр["genre"] = [код]
                return self._отдать_вид(в, в.список("/catalog", зпр))
            # Zona: redirect to catalog query, preserving other active filters.
            keep = {к: (зпр.get(к) or [None])[0]
                    for к in ("kind", "year", "country", "sort", "page")
                    if (зпр.get(к) or [None])[0]}
            keep["genre"] = код
            return self._переход("/catalog/" + запрос_строкой(keep))
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
        # Убранная подборка (T286): все её страницы — один 301 на цель, без ?page.
        объединена = getattr(КОЛЛЕКЦИИ, "объединена", None)
        цель = объединена(СЕМЕЙСТВО, ключ) if объединена else None
        if цель:
            self.send_response(301)
            self.send_header("Location", цель)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return True
        снимок = Снимок.получить(в.д, self.подробности)
        # Редакционная подборка решается ПЕРВОЙ: её состав задан поимённо, и
        # спецификация фильтра с тем же ключом его не подменяет. Фильтры при
        # этом работают как раньше — ветвь ниже не изменилась.
        ручная = РУЧНЫЕ_ПОДБОРКИ.get(ключ)
        if ручная is not None and снимок is not None:
            состав = КОЛЛЕКЦИИ.разрешить_ручную(ручная, снимок)
            return self._отдать(в.ручная_подборка(ручная, состав).encode("utf-8"))
        спец = КОЛЛЕКЦИИ.спецификация(СЕМЕЙСТВО, ключ)
        if спец is None or снимок is None:
            return self._отдать(в.не_найдено(путь).encode("utf-8"), код=404)
        # Номер страницы коллекции разбирается, а не зажимается (REQ-SEO-PAGINATION
        # п.2, п.8; приёмка Архитектора 11.10): ?page=1 → 308 без номера,
        # 0/abc → 400 (как в каталоге Zona), за пределом → 404. Прежде abc/0
        # отдавали копию первой страницы, 9999 — пустой шаблон с 200.
        сырой = str((зпр.get("page") or [""])[0] or "").strip()
        if сырой == "1":
            пары = {к: (зн or [""])[0] for к, зн in зпр.items()
                    if к != "page" and not к.startswith("_")}
            return self._переход(путь + (запрос_строкой(пары) if пары else ""))
        if сырой and (not сырой.isdigit() or int(сырой) < 1):
            return self._отдать(в.не_найдено(путь).encode("utf-8"), код=400)
        страница = int(сырой) if сырой else 1
        данные = КОЛЛЕКЦИИ.разрешить(ключ, снимок, СЕМЕЙСТВО, страница=страница)
        if данные is None or (страница > 1 and not данные.items):
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
            return self._отдать(в.сезон(запись, деталь, номер).encode("utf-8"),
                                без_индекса=not any(с["доступные"] for с in список_серий(деталь)
                                                    if с["n"] == номер))
        серия = int(н_серии)
        # Границы проверяются по объявленному числу серий сезона. Двести
        # одиннадцатая у сериала с двумястами десятью — это 404, а не пустая
        # страница с плеером, которому нечего показать.
        # Границы проверяются по НОМЕРАМ, которые у сезона существуют.
        # Спецвыпуск с номером 0 адресуется ровно тогда, когда он у сезона
        # ЗАЯВЛЕН: иначе `episode-0` был бы вечной страницей-обещанием у
        # каждого сериала подряд.
        существующие: set = set()
        for с in список_серий(деталь):
            if с["n"] == номер:
                существующие = set(с["номера"])
                break
        if серия not in существующие:
            return self._отдать(в.не_найдено(путь).encode("utf-8"), код=404)
        return self._отдать(в.серия(запись, деталь, номер, серия).encode("utf-8"),
                            без_индекса=not серия_с_дорожкой(деталь, номер, серия))

    #: Память главной (T040). Замер 13.10: главная стоила 0,6–0,7 с на КАЖДЫЙ
    #: запрос — новинка() по всему каталогу (76 362 вызова), — а под нагрузкой
    #: стояла в очереди под GIL до 21,6 с. Ответ зависит от снимка, вида, хоста и
    #: суток; правки на месте (согласование серий, накладки редактора, оценки)
    #: снимок не меняют — их ограничивает срок. Тело — то же, что отдал бы
    #: прямой вызов: памяти нечего «додумать», она только повторяет.
    _ПАМЯТЬ_ГЛАВНОЙ: dict = {}
    СРОК_ГЛАВНОЙ_С = float(os.environ.get("ZONA_HOME_TTL", "60"))

    def _главная_из_памяти(self, в) -> str:
        д = self.данные
        ключ = (type(в).__name__, getattr(в, "хост", ""), id(д), getattr(д, "mtime", None),
                getattr(д, "revision", None), len(getattr(д, "items", ()) or ()),
                _часы_datetime().date())
        запись = Обработчик._ПАМЯТЬ_ГЛАВНОЙ.get("главная")
        сейчас = time.monotonic()
        if запись and запись[0] == ключ and сейчас - запись[1] < Обработчик.СРОК_ГЛАВНОЙ_С:
            return запись[2]
        тело = в.главная()
        Обработчик._ПАМЯТЬ_ГЛАВНОЙ["главная"] = (ключ, сейчас, тело)
        return тело

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
                '<p class="empty">Расписание построено по доступному каталогу: '
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



def прогреть_ширины_обложек(ограничение: int = 24) -> int:
    """Узнать ширины обложек первого экрана заранее. Возвращает число ключей.

    Берутся обложки редакционной полки и первых визиток подборок: именно их
    видит первый посетитель. Запросы идут по одному и ТОЛЬКО через собственный
    прокси, то есть тем же путём, что и обычная отдача. Любая ошибка молча
    пропускается: прогрев — удобство, а не условие работы витрины.
    """
    if not ПОСТЕРЫ_СВОИМ_АДРЕСОМ or КОЛЛЕКЦИИ is None or not РУЧНЫЕ_ПОДБОРКИ:
        return 0
    данные = Обработчик.данные
    подробности = Обработчик.подробности
    if данные is None:
        return 0
    try:
        снимок = Снимок.получить(данные, подробности)
    except Exception:  # noqa: BLE001
        return 0
    if снимок is None:
        return 0
    ключи: list[str] = []
    for подборка in РУЧНЫЕ_ПОДБОРКИ.values():
        try:
            состав = КОЛЛЕКЦИИ.разрешить_ручную(подборка, снимок)
        except Exception:  # noqa: BLE001
            continue
        for с in (состав.get("works") or []):
            адрес = str((с.get("запись") or {}).get("poster") or "")
            if адрес.startswith(ВНЕШНИЙ_ПОСТЕР):
                ключ = адрес[len(ВНЕШНИЙ_ПОСТЕР):]
                if ключ not in ключи:
                    ключи.append(ключ)
            if len(ключи) >= ограничение:
                break
        if len(ключи) >= ограничение:
            break
    согрето = 0
    for ключ in ключи:
        try:
            код, _, _ = отдать_постер(ключ)
        except Exception:  # noqa: BLE001
            continue
        if код == 200:
            согрето += 1
    return согрето


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--host", default="127.0.0.1")
    р.add_argument("--port", type=int, required=True)
    args = р.parse_args()
    if РЕДАКЦИЯ is not None and ФАЙЛ_ПРАВОК:
        Обработчик.правки = РЕДАКЦИЯ.Правки(ФАЙЛ_ПРАВОК, ИДЕНТИФИКАТОР_САЙТА)
    Обработчик.данные = Данные(КАТАЛОГ_ФАЙЛ)
    Обработчик.подробности = Подробности(ПОДРОБНОСТИ_ФАЙЛ)
    Обработчик.индекс = построить_индекс(Обработчик.данные, Обработчик.подробности)
    # Указатель поиска — до приёма запросов (apply-search-index-prebuild).
    # Ленивый указатель собирал первый поисковый запрос после запуска, синхронно:
    # 504 через 30 с у первых посетителей после выкладки (замер 12.10). Фоновая
    # пересборка строит его до подмены — запуск теперь тоже.
    try:
        Обработчик.данные._построить_указатель()
    except Exception:  # noqa: BLE001 — указатель не обязателен для показа: ленивый путь остаётся
        pass
    # Ширины обложек первого экрана узнаются ДО первого посетителя: иначе
    # ему достаётся прежний srcset, и честным он станет только для следующих.
    # Фоном и без спешки: прогрев — удобство, а не условие работы витрины.
    def _прогрев() -> None:
        try:
            сколько = прогреть_ширины_обложек()
        except Exception:  # noqa: BLE001
            return
        if сколько:
            print(f"[nova] ширины обложек первого экрана: {сколько}", flush=True)

    threading.Thread(target=_прогрев, name="poster-widths", daemon=True).start()
    сервер = ThreadingHTTPServer((args.host, args.port), Обработчик)
    # Согласование доступности серий идёт ФОНОМ и никогда не в пути запроса
    # страницы: синхронный вызов провайдера при отрисовке означал бы, что
    # страница ждёт чужую службу — соседняя витрина ровно на этом и легла.
    #
    # Модуль лежит рядом с рантаймом. Его отсутствие витрину не роняет: она
    # просто остаётся на суточном снимке, как была.
    try:
        import episode_sync as _согласование
    except ImportError:
        _согласование = None
    if _согласование is not None and _согласование.запустить(sys.modules[__name__]):
        print("[nova] согласование доступности серий: запущено", flush=True)
    # Карта сайта собирается ФОНОМ и никогда в пути запроса: сборка идёт по
    # всему снимку каталога, и делать её при отдаче страницы значило бы
    # заставить посетителя ждать.
    #
    # Сборщик живёт в общем `seo_layer`: файл у семейства один, и выпуск
    # доставляет его всем сайтам сразу. Молчаливый пропуск запрещён — причина
    # называется в журнале.
    try:
        import seo_layer as _карта
    except ImportError:
        _карта = None
    if _карта is None:
        print("[nova] карта сайта не заводится: модуля seo_layer нет", flush=True)
    elif not hasattr(_карта, "запустить_карту"):
        print("[nova] карта сайта не заводится: в seo_layer нет запустить_карту "
              "(выпуск несёт прежнюю версию модуля)", flush=True)
    else:
        _карта.запустить_карту(sys.modules[__name__])

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
