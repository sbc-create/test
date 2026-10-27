#!/usr/bin/env python3
"""Первый экран главной и визуальные карточки подборок — перенос по якорям.

Поручение владельца 27.10: визуальное качество выложенного не принято. Нужно:
первая и самая заметная лента — востребованные сериалы с крупными постерами и
читаемыми названиями; поступления каталога ниже; затем визуальные тематические
подборки и востребованные фильмы; текстовые плашки подборок заменить
полноценными карточками с обложкой из РЕАЛЬНОГО состава, коротким названием,
одним предложением о пользе, числом работ и понятным переходом.

Что делает инструмент:

1. `collection_contract.py` учится полю `home_rail`: подборка, помеченная им,
   становится первой лентой главной. Поле необязательное — витрина без него
   работает как прежде.
2. В рантайм добавляются `польза_подборки` (одно предложение из вступления),
   `визитка_подборки` (карточка с обложками состава) и `_полка_главной`.
3. Текстовые плашки редакционных подборок на главной, в хабе и в полосе
   раздела заменяются визитками.
4. Порядок главной: при наличии полки — полка, подборки, фильмы недели,
   поступления, входы, жанры, SEO. Герой при этом не рисуется: два крупных
   блока подряд спорят за первый экран, а полка полезнее для выбора.

Чего инструмент НЕ делает: не придумывает состав полки (он берётся из
`config/collections.json`, где у каждой работы постоянный id, пояснение и
отметка проверки), не меняет решения об индексации и не трогает плеер.

    python3 automation/host/apply-home-visual-patch.py [--check] <файл>…
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
#  Контракт подборок: необязательное поле home_rail
# ---------------------------------------------------------------------------

КОНТРАКТ_ПОЛЕ_БЫЛО = """    indexing_open: bool
    indexing_reason: str
    works: tuple = ()"""
КОНТРАКТ_ПОЛЕ_СТАЛО = """    indexing_open: bool
    indexing_reason: str
    works: tuple = ()
    #: Полка главной. Подборка, помеченная этим полем, выходит первой лентой
    #: главной — крупными постерами, а не плашкой. Поле необязательное:
    #: витрина без него собирает главную как прежде.
    home_rail: bool = False"""

КОНТРАКТ_РАЗБОР_БЫЛО = """        итог.append(РучнаяПодборка(
            key=str(с.get("key") or ""), title=str(с.get("title") or ""),
            viewer_request=str(с.get("viewer_request") or ""),
            intro=str(с.get("intro") or ""), section=str(с.get("section") or ""),
            indexing_open=bool(индексация.get("open")),
            indexing_reason=str(индексация["reason"]),
            works=tuple(sorted(работы, key=lambda р: р.order))))"""
КОНТРАКТ_РАЗБОР_СТАЛО = """        итог.append(РучнаяПодборка(
            key=str(с.get("key") or ""), title=str(с.get("title") or ""),
            viewer_request=str(с.get("viewer_request") or ""),
            intro=str(с.get("intro") or ""), section=str(с.get("section") or ""),
            indexing_open=bool(индексация.get("open")),
            indexing_reason=str(индексация["reason"]),
            home_rail=bool(с.get("home_rail")),
            works=tuple(sorted(работы, key=lambda р: р.order))))"""

КОНТРАКТ_ПАРЫ = (
    ("контракт: поле home_rail", КОНТРАКТ_ПОЛЕ_БЫЛО, КОНТРАКТ_ПОЛЕ_СТАЛО,
     "home_rail: bool = False"),
    ("контракт: разбор home_rail", КОНТРАКТ_РАЗБОР_БЫЛО, КОНТРАКТ_РАЗБОР_СТАЛО,
     'home_rail=bool(с.get("home_rail"))'),
)

# ---------------------------------------------------------------------------
#  Линия Zona: стиль
# ---------------------------------------------------------------------------

СТИЛЬ_ЯКОРЬ = ".zhub__c{display:block;padding:12px;border:1px solid @LINE@;border-radius:6px;"
СТИЛЬ_НОВОЕ = """
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
"""

# ---------------------------------------------------------------------------
#  Линия Zona: помощники и методы
# ---------------------------------------------------------------------------

ПОМОЩНИК = '''
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

'''
ПОМОЩНИК_ЯКОРЬ = "\ndef _ручные_подборки() -> dict:"

ВИЗИТКА = '''
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
                f'<div class="zr1__h"><h1 id="zr1-h">{html.escape(полка.title)}</h1>'
                f'<a href="{html.escape(полка.canonical_path)}">Вся подборка</a></div>'
                f'<p class="zr1__sub">{html.escape(польза)}</p>'
                f'<div class="zr1__track" data-scroller="rail1">'
                f'{"".join(карточки)}</div></section>'), слаги

'''
ВИЗИТКА_ЯКОРЬ = "    def _полоса_подборок_раздела(self, разд: str, стр: int = 1) -> str:"

# ---------------------------------------------------------------------------
#  Линия Zona: плашки → визитки и порядок главной
# ---------------------------------------------------------------------------

#: Полка на главной не повторяется плашкой ниже: подборка, вынесенная наверх
#: крупными постерами, в блоке подборок была бы тем же составом второй раз.
ГЛАВНАЯ_ПЛАШКА_БЫЛО = """            for подборка_ред in РУЧНЫЕ_ПОДБОРКИ.values():
                состав_ред = КОЛЛЕКЦИИ.разрешить_ручную(подборка_ред, снимок)
                if not состав_ред.get("works"):
                    continue
                кол_карточки.append(
                    f'<a class="zhub__c" href="{html.escape(подборка_ред.canonical_path)}">'
                    f'<span class="zhub__t">{html.escape(подборка_ред.title)}</span>'
                    f'<span class="zhub__m">Выбор редакции</span></a>')"""
ГЛАВНАЯ_ПЛАШКА_СТАЛО = """            for подборка_ред in РУЧНЫЕ_ПОДБОРКИ.values():
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
                             for с in работы_ред]))"""

#: Алгоритмические подборки на главной — той же визиткой: иначе рядом стоят
#: карточка с обложками и текстовая плашка, и страница выглядит собранной из
#: двух разных сайтов.
ГЛАВНАЯ_СПЕЦ_БЫЛО = """                кол_карточки.append(
                    f'<a class="zhub__c" href="{html.escape(спец.canonical_path)}">'
                    f'<span class="zhub__t">{html.escape(данные.title)}</span>'
                    f'<span class="zhub__m">{html.escape(подпись)}</span></a>')"""
ГЛАВНАЯ_СПЕЦ_СТАЛО = """                полные = КОЛЛЕКЦИИ.разрешить(спец.collection_key, снимок,
                                             СЕМЕЙСТВО, предел=3)
                кол_карточки.append(self.визитка_подборки(
                    адрес=спец.canonical_path,
                    название=данные.title,
                    польза=польза_подборки(данные.description or подпись),
                    всего=getattr(данные, "total", 0)
                    or len(getattr(полные, "items", []) or []),
                    постеры=[(getattr(к, "poster", "") or "")
                             for к in (getattr(полные, "items", []) or [])]))"""

ГЛАВНАЯ_СЕТКА_БЫЛО = """                    f'<div class="zhub zhub--home">{"".join(кол_карточки)}</div>'"""
ГЛАВНАЯ_СЕТКА_СТАЛО = """                    f'<div class="zcl zcl--home">{"".join(кол_карточки)}</div>'"""

#: Порядок главной при наличии полки. Герой не рисуется: два крупных блока
#: подряд спорят за первый экран, а полка полезнее для выбора просмотра.
ПОРЯДОК_БЫЛО = """        куски = [блоки[имя] for имя in шаблон["порядок"]
                 if имя in блоки and блоки[имя]]"""
ПОРЯДОК_СТАЛО = """        блоки["rail1"] = полка_html
        if полка_html:
            # Поручение владельца 27.10: первой и самой заметной идёт лента
            # востребованных сериалов, затем визуальные подборки, затем фильмы
            # недели, и только потом поступления каталога. Герой при наличии
            # полки не рисуется: два крупных блока подряд спорят за первый
            # экран. Порядок закреплён здесь, а не в букве шаблона, потому что
            # он включается НАЛИЧИЕМ редакционной полки, а не профилем.
            порядок = ("rail1", "collections", "weekly", "added", "kinds",
                       "genres", "fresh", "seo")
        else:
            порядок = шаблон["порядок"]
        куски = [блоки[имя] for имя in порядок
                 if имя in блоки and блоки[имя]]"""

#: Хаб `/collections/`: редакционные подборки — визитками.
ХАБ_БЫЛО = """        for подборка_ред in РУЧНЫЕ_ПОДБОРКИ.values():
            состав_ред = КОЛЛЕКЦИИ.разрешить_ручную(подборка_ред, снимок)
            if not состав_ред.get("works"):
                continue
            карточки.append(
                f'<a class="zhub__c" href="{html.escape(подборка_ред.canonical_path)}">'
                f'<span class="zhub__t">{html.escape(подборка_ред.title)}</span>'
                f'<span class="zhub__m">{html.escape(подборка_ред.viewer_request[:90])}</span>'
                f'</a>')"""
ХАБ_СТАЛО = """        for подборка_ред in РУЧНЫЕ_ПОДБОРКИ.values():
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
                срочно="eager"))"""

ХАБ_СЕТКА_БЫЛО = """        return (f'<div class="zhub" data-testid="collection-grid" '
                f'data-hub-count="{len(карточки)}">{"".join(карточки)}</div>')"""
ХАБ_СЕТКА_СТАЛО = """        return (f'<div class="zcl" data-testid="collection-grid" '
                f'data-hub-count="{len(карточки)}">{"".join(карточки)}</div>')"""

#: Полоса раздела и каталога — те же визитки.
ПОЛОСА_БЫЛО = """        карточки = []
        for подборка in свои:
            состав = КОЛЛЕКЦИИ.разрешить_ручную(подборка, снимок)
            if not состав.get("works"):
                continue
            карточки.append(
                f'<a class="zhub__c" href="{html.escape(подборка.canonical_path)}">'
                f'<span class="zhub__t">{html.escape(подборка.title)}</span>'
                f'<span class="zhub__m">{html.escape(подборка.viewer_request[:90])}</span>'
                f'</a>')"""
ПОЛОСА_СТАЛО = """        карточки = []
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
                         for с in работы]))"""

ПОЛОСА_СЕТКА_БЫЛО = """                f'<div class="zhub">{"".join(карточки)}</div></section>')"""
ПОЛОСА_СЕТКА_СТАЛО = """                f'<div class="zcl">{"".join(карточки)}</div></section>')"""

#: Полка считается ДО недельных полок, и её слаги сразу занимаются: иначе одна
#: и та же вещь встанет и в редакционную полку, и в полку недели, а вторая
#: будет выглядеть копией первой.
РАНО_БЫЛО = """        weekly = _popular_weekly_snapshot()"""
РАНО_СТАЛО = """        weekly = _popular_weekly_snapshot()
        # Редакционная полка выбирается ПЕРВОЙ, и её слаги сразу считаются
        # занятыми: иначе та же вещь встанет и в полку недели, и в
        # поступления, а вторая полка будет выглядеть копией первой.
        полка_html, полка_слаги = self._полка_главной()
        занято |= полка_слаги"""

НЕДЕЛЯ_БЫЛО = """        for з in pop_films + pop_series + pop_anim:
            занято.add(з["slug"])"""
НЕДЕЛЯ_СТАЛО = """        pop_films = [з for з in pop_films if з["slug"] not in полка_слаги]
        pop_series = [з for з in pop_series if з["slug"] not in полка_слаги]
        pop_anim = [з for з in pop_anim if з["slug"] not in полка_слаги]
        for з in pop_films + pop_series + pop_anim:
            занято.add(з["slug"])"""


# ---------------------------------------------------------------------------
#  Линия Zona: блок анонсов «Ждём премьеру»
# ---------------------------------------------------------------------------

#: Анонс — это объявленный релиз, которого в просмотре ещё нет. Поэтому у него
#: нет ни кнопки просмотра, ни постера из каталога: обещать доступный просмотр
#: до фактической доступности запрещено (поручение владельца 27.10 §2).
АНОНСЫ_ЗАГРУЗКА = '''
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


'''
АНОНСЫ_ЯКОРЬ = "\ndef _ручные_подборки() -> dict:"

АНОНСЫ_БЛОК = '''
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

'''

АНОНСЫ_ДАТА = '''
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


'''

АНОНСЫ_СТИЛЬ = """
/* «Ждём премьеру»: карточка начинается с ДАТЫ, а не с картинки. Постера у
   объявленного релиза в каталоге нет, а рисовать букву вместо обложки или
   брать чужую картинку нельзя — поэтому блок устроен иначе и не притворяется
   постерной полкой. */
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
"""

#: Блок анонсов встаёт после подборок и фильмов недели, но ВЫШЕ поступлений:
#: «далее — подборки, фильмы и ожидаемые релизы», а новые импорты ниже.
АНОНСЫ_ПОРЯДОК_БЫЛО = """            порядок = ("rail1", "collections", "weekly", "added", "kinds",
                       "genres", "fresh", "seo")"""
АНОНСЫ_ПОРЯДОК_СТАЛО = """            порядок = ("rail1", "collections", "weekly", "announce", "added",
                       "kinds", "genres", "fresh", "seo")"""

АНОНСЫ_БЛОКИ_БЫЛО = """        блоки["rail1"] = полка_html"""
АНОНСЫ_БЛОКИ_СТАЛО = """        блоки["rail1"] = полка_html
        блоки["announce"] = self._блок_анонсов()"""


ZONA_ПАРЫ = (
    ("стиль полки и визитки", СТИЛЬ_ЯКОРЬ, СТИЛЬ_НОВОЕ + СТИЛЬ_ЯКОРЬ, ".zr1__track{"),
    ("помощник пользы", ПОМОЩНИК_ЯКОРЬ, ПОМОЩНИК + ПОМОЩНИК_ЯКОРЬ,
     "def польза_подборки"),
    ("визитка и полка", ВИЗИТКА_ЯКОРЬ, ВИЗИТКА + ВИЗИТКА_ЯКОРЬ,
     "def визитка_подборки"),
    ("главная: плашка редакции → визитка", ГЛАВНАЯ_ПЛАШКА_БЫЛО,
     ГЛАВНАЯ_ПЛАШКА_СТАЛО, 'if getattr(подборка_ред, "home_rail", False):'),
    ("главная: плашка контракта → визитка", ГЛАВНАЯ_СПЕЦ_БЫЛО,
     ГЛАВНАЯ_СПЕЦ_СТАЛО, "полные = КОЛЛЕКЦИИ.разрешить(спец.collection_key"),
    ("главная: сетка визиток", ГЛАВНАЯ_СЕТКА_БЫЛО, ГЛАВНАЯ_СЕТКА_СТАЛО,
     'zcl zcl--home'),
    ("главная: полка до недельных полок", РАНО_БЫЛО, РАНО_СТАЛО,
     "полка_html, полка_слаги = self._полка_главной()"),
    ("главная: недельные полки без слагов полки", НЕДЕЛЯ_БЫЛО, НЕДЕЛЯ_СТАЛО,
     'pop_films = [з for з in pop_films if з["slug"] not in полка_слаги]'),
    ("главная: порядок с полкой", ПОРЯДОК_БЫЛО, ПОРЯДОК_СТАЛО,
     'блоки["rail1"] = полка_html'),
    ("анонсы: дата по-человечески", ПОМОЩНИК_ЯКОРЬ, АНОНСЫ_ДАТА + ПОМОЩНИК_ЯКОРЬ,
     "def _дата_анонса"),
    ("анонсы: загрузка файла", АНОНСЫ_ЯКОРЬ, АНОНСЫ_ЗАГРУЗКА + АНОНСЫ_ЯКОРЬ,
     "АНОНСЫ = _анонсы()"),
    ("анонсы: блок главной", ВИЗИТКА_ЯКОРЬ, АНОНСЫ_БЛОК + ВИЗИТКА_ЯКОРЬ,
     "def _блок_анонсов"),
    ("анонсы: стиль", СТИЛЬ_ЯКОРЬ, АНОНСЫ_СТИЛЬ + СТИЛЬ_ЯКОРЬ, ".zann__c{"),
    ("анонсы: место в порядке", АНОНСЫ_ПОРЯДОК_БЫЛО, АНОНСЫ_ПОРЯДОК_СТАЛО,
     '"weekly", "announce", "added"'),
    ("анонсы: сборка блока", АНОНСЫ_БЛОКИ_БЫЛО, АНОНСЫ_БЛОКИ_СТАЛО,
     'блоки["announce"] = self._блок_анонсов()'),
    ("хаб: плашка → визитка", ХАБ_БЫЛО, ХАБ_СТАЛО, 'срочно="eager"'),
    ("хаб: сетка визиток", ХАБ_СЕТКА_БЫЛО, ХАБ_СЕТКА_СТАЛО,
     'class="zcl" data-testid="collection-grid"'),
    ("полоса: плашка → визитка", ПОЛОСА_БЫЛО, ПОЛОСА_СТАЛО,
     "всего=len(работы),"),
    ("полоса: сетка визиток", ПОЛОСА_СЕТКА_БЫЛО, ПОЛОСА_СЕТКА_СТАЛО,
     '<div class="zcl">{"".join(карточки)}</div></section>'),
)

# ---------------------------------------------------------------------------
#  Линия Animedia: крупнее обложки, меньше превью, полка первой
# ---------------------------------------------------------------------------

#: Четыре превью по 100 px владелец прямо назвал дефектом: «вместо четырёх
#: мелких превью используй меньше, но крупнее — например, два-три постера».
AM_СБОРЩИК_БЫЛО = """                if len(постеры) >= 4:
                    break"""
AM_СБОРЩИК_СТАЛО = """                if len(постеры) >= 3:
                    break"""

AM_СЕТКА_БЫЛО = """        плитки = "".join(
            f'<a class="zhub__c" data-card-variant="collection-card" '
            f'data-collection-key="{html.escape(к["key"])}" '
            f'href="{html.escape(к["path"])}">'
            # Название стоит над коллажем — так у оригинала: сначала читаешь,
            # о чём подборка, потом смотришь, что в ней.
            f'<span class="zhub__t">{html.escape(к["title"])}</span>'
            f'<span class="zhub__g">'
            + "".join(
                f'<span class="zhub__p">'
                f'<img class="zhub__img" src="{html.escape(_адрес_постера(п) or "")}"'
                f'{_srcset_постера(_адрес_постера(п), 100)}'
                f' alt="" loading="lazy" decoding="async" width="120" height="180"></span>'
                for п in к["posters"])
            + "</span>"
            f'<span class="zhub__m">{к["total"]} {склонение_записей(к["total"])}</span>'
            f'<span class="zhub__d">{html.escape(к["description"])}</span>'
            "</a>"
            for к in карточки)
        return f'<div class="zhub" data-b13="hub">{плитки}</div>'"""
AM_СЕТКА_СТАЛО = """        плитки = "".join(
            f'<a class="zhub__c" data-card-variant="collection-card" '
            f'data-collection-key="{html.escape(к["key"])}" '
            f'href="{html.escape(к["path"])}">'
            # Обложки стоят ПЕРВЫМИ и крупно: по четырём превью шириной 100 px
            # нельзя было понять ни что внутри, ни сколько там (поручение
            # владельца 27.10). Три кадра вместо четырёх — каждый шире.
            f'<span class="zhub__g zhub__g--big">'
            + "".join(
                f'<span class="zhub__p">'
                f'<img class="zhub__img" src="{html.escape(_адрес_постера(п) or "")}"'
                f'{_srcset_постера(_адрес_постера(п), ПОКАЗ_ВИЗИТКИ)}'
                f' alt="" loading="lazy" decoding="async" width="160" height="240"></span>'
                for п in к["posters"][:3])
            + f'<span class="zhub__n">{к["total"]} '
            f'{склонение_записей(к["total"])}</span>'
            "</span>"
            f'<span class="zhub__t">{html.escape(к["title"])}</span>'
            f'<span class="zhub__d">{html.escape(польза_подборки(к["description"]))}</span>'
            f'<span class="zhub__go">Открыть подборку →</span>'
            "</a>"
            for к in карточки)
        return f'<div class="zhub zhub--big" data-b13="hub">{плитки}</div>'"""

AM_СТИЛЬ_НОВОЕ = """
/* Визитка подборки: три крупных кадра вместо четырёх мелких (поручение
   владельца 27.10). Прежние превью рисовались шириной около 100 px — по ним
   нельзя было понять ни что внутри подборки, ни сколько там работ. */
.zhub--big{display:grid;gap:14px;grid-template-columns:1fr}
.zhub--big .zhub__c{display:flex;flex-direction:column;gap:8px;padding:0 0 6px;overflow:hidden}
.zhub__g--big{position:relative;display:flex;gap:2px;background:@LINE@;margin:0 0 4px}
.zhub__g--big .zhub__p{flex:1 1 0;aspect-ratio:2/3;overflow:hidden;display:block}
.zhub__g--big .zhub__img{width:100%;height:100%;object-fit:cover;display:block}
.zhub__n{position:absolute;right:10px;bottom:10px;background:rgba(14,18,24,.78);color:#fff;font-size:12px;font-weight:700;line-height:1;padding:6px 9px;border-radius:999px}
.zhub--big .zhub__t{font-size:16.5px;font-weight:700;line-height:1.28;padding:0 14px}
.zhub--big .zhub__d{font-size:13.5px;line-height:1.5;color:@DIM@;padding:0 14px}
.zhub__go{margin-top:auto;font-size:13px;font-weight:700;color:@ACC@;min-height:44px;display:inline-flex;align-items:center;padding:0 14px}
@media(min-width:640px){.zhub--big{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(min-width:1024px){.zhub--big{grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}}

/* Первая полка главной: востребованные аниме-сериалы крупными постерами. */
.zr1{margin:0 0 26px}
.zr1__h{display:flex;align-items:baseline;justify-content:space-between;gap:10px;flex-wrap:wrap;margin:0 0 2px}
.zr1__h h2{margin:0;font-size:21px;line-height:1.18;font-weight:700;letter-spacing:-.01em}
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
@media(min-width:640px){.zr1__track{grid-auto-columns:172px;gap:16px}.zr1__h h2{font-size:26px}}
@media(min-width:1024px){.zr1__track{grid-auto-columns:196px;gap:18px}.zr1__h h2{font-size:29px}.zb__t{font-size:15.5px}}
"""
AM_СТИЛЬ_ЯКОРЬ = "/* Хабы жанров и типов: одинаковые карточки-ссылки, счётчик под названием. */"

AM_ПОКАЗ = '''#: Показ обложки визитки подборки: три кадра в ряд внутри карточки сетки.
ПОКАЗ_ВИЗИТКИ = "(min-width:1024px) 150px, (min-width:640px) 160px, 120px"
'''
AM_ПОКАЗ_ЯКОРЬ = "_ПОСТЕР_КЭШ: dict[str | tuple[str, int], tuple[float, bytes, str]] = {}"

AM_ПОЛКА = '''
    def _полка_главной(self) -> tuple:
        """Первая лента главной: редакционная подборка с пометкой `home_rail`.

        Возвращает ПАРУ: разметку и множество слагов. Слаги нужны вызывающему:
        без них те же тайтлы попадут и в карусель, и в ленты ниже, то есть
        встанут на главной дважды.

        Порядок и состав выбраны человеком и записаны в файле подборок с
        постоянными id. Нет такой подборки или её состав пуст — ленты нет
        вовсе: подставлять на это место алгоритмическую выборку значило бы
        выдавать её за редакционный выбор.
        """
        if КОЛЛЕКЦИИ is None or not РУЧНЫЕ_ПОДБОРКИ:
            return ""
        полка = next((п for п in РУЧНЫЕ_ПОДБОРКИ.values()
                      if getattr(п, "home_rail", False)), None)
        if полка is None:
            return ""
        снимок = Снимок.получить(self.д, self.п)
        if снимок is None:
            return ""
        состав = КОЛЛЕКЦИИ.разрешить_ручную(полка, снимок)
        работы = состав.get("works") or []
        if not работы:
            return ""
        карточки, слаги = [], set()
        for место, с in enumerate(работы):
            запись = с.get("запись") or {}
            слаг = str(запись.get("slug") or "")
            if not слаг:
                continue
            слаги.add(слаг)
            постер = _адрес_постера(str(запись.get("poster") or ""))
            срочно = место < 3
            # Приоритет и режим загрузки считаются ДО f-строки:
            # обратная косая внутри её выражения не разбирается
            # в Python 3.10, и рантайм не поднялся бы вовсе.
            приоритет = ' fetchpriority="high"' if срочно else ""
            загрузка = "eager" if срочно else "lazy"
            картинка = (
                f'<img src="{html.escape(постер or "")}"'
                f'{_srcset_постера(постер, ПОКАЗ_ПОЛКА)}'
                f' alt="{html.escape(str(запись.get("title") or ""))}"'
                f' width="300" height="450" decoding="async"'
                f' loading="{загрузка}"{приоритет}>'
                if постер else "")
            подпись = str(запись.get("year") or "")
            карточки.append(
                f'<a class="zb" href="/title/{html.escape(слаг)}/">'
                f'<span class="zb__img">{картинка}</span>'
                f'<span class="zb__t">{html.escape(str(запись.get("title") or ""))}</span>'
                f'<span class="zb__m">{html.escape(подпись)}</span></a>')
        if not карточки:
            return "", set()
        return (f'<section class="zr1" aria-labelledby="zr1-h"'
                f' data-block-key="rail:{html.escape(полка.key)}">'
                f'<div class="zr1__h"><h2 id="zr1-h">{html.escape(полка.title)}</h2>'
                f'<a href="{html.escape(полка.canonical_path)}">Вся подборка</a></div>'
                f'<p class="zr1__sub">'
                f'{html.escape(польза_подборки(полка.intro))}</p>'
                f'<div class="zr1__track" data-scroller="rail1">'
                f'{"".join(карточки)}</div></section>')

'''
AM_ПОЛКА_ЯКОРЬ = "    def _блок_подборок_home_b06(self) -> str:"

AM_ПОКАЗ_ПОЛКИ = '''ПОКАЗ_ПОЛКА = "(min-width:1024px) 240px, (min-width:640px) 200px, 164px"
'''
AM_ПОКАЗ_ПОЛКИ_ЯКОРЬ = 'ПОКАЗ_ГЕРОЙ = "(min-width:768px) 180px, 120px"'

#: Полка встаёт ПЕРВЫМ содержательным блоком главной, сразу за H1 и полосой
#: готовности: поручение владельца 27.10 — первая и самая заметная лента.
AM_ГЛАВНАЯ_БЫЛО = """        куски = [f'<h1 class="vh">{html.escape(домен["title_home"])}</h1>',
                 self.полоса_готовности()]"""
AM_ГЛАВНАЯ_СТАЛО = """        куски = [f'<h1 class="vh">{html.escape(домен["title_home"])}</h1>',
                 self.полоса_готовности()]
        # Первая и самая заметная лента — редакционная полка востребованных
        # аниме-сериалов (поручение владельца 27.10). Дальше идут визуальные
        # подборки и новые серии; карусель недельного снимка остаётся ниже.
        полка_главной, полка_слаги = self._полка_главной()
        # Слаги полки занимаются сразу: карусель и ленты ниже их не повторяют.
        занято |= полка_слаги
        занятые_каруселью |= полка_слаги
        if полка_главной:
            куски.append(полка_главной)
            куски.append(self._блок_подборок_home_b06())"""

#: Блок подборок не рисуется дважды: при полке он уже выведен выше.
AM_ПОДБОРКИ_БЫЛО = """\n        куски.append(self._блок_подборок_home_b06())\n"""
AM_ПОДБОРКИ_СТАЛО = """\n        if not полка_главной:
            куски.append(self._блок_подборок_home_b06())\n"""

#: Второй сборщик карточек подборок этой линии (хаб спецификаций) — к тому же
#: виду: три крупных кадра, счёт значком, польза одной строкой.
AM_ХАБ_ОБЛОЖКИ_БЫЛО = """            обложки = "".join(
                f'<span class="zhub__p">'
                f'<img class="zhub__img" src="{html.escape(_адрес_постера(к.poster) or "")}"'
                f'{_srcset_постера(_адрес_постера(к.poster), 100)}'
                f' alt="" loading="lazy" decoding="async" width="120" height="180"></span>'
                for к in выбранные[:4] if к.poster)"""
AM_ХАБ_ОБЛОЖКИ_СТАЛО = """            обложки = "".join(
                f'<span class="zhub__p">'
                f'<img class="zhub__img" src="{html.escape(_адрес_постера(к.poster) or "")}"'
                f'{_srcset_постера(_адрес_постера(к.poster), ПОКАЗ_ВИЗИТКИ)}'
                f' alt="" loading="lazy" decoding="async" width="160" height="240"></span>'
                for к in выбранные[:3] if к.poster)"""
AM_ХАБ_КАРТОЧКА_БЫЛО = """            карточки.append(
                f'<a class="zhub__c" data-card-variant="collection-card" href="{html.escape(спец.canonical_path)}">'
                f'<span class="zhub__g">{обложки}</span>'
                f'<span class="zhub__t">{html.escape(коллекция.title)}</span>'
                f'<span class="zhub__m">{коллекция.total}</span>'
                f'<span class="zhub__d">{html.escape(коллекция.description)}</span>'
                f'</a>')"""
AM_ХАБ_КАРТОЧКА_СТАЛО = """            карточки.append(
                f'<a class="zhub__c" data-card-variant="collection-card" href="{html.escape(спец.canonical_path)}">'
                f'<span class="zhub__g zhub__g--big">{обложки}'
                f'<span class="zhub__n">{коллекция.total} '
                f'{склонение_записей(коллекция.total)}</span></span>'
                f'<span class="zhub__t">{html.escape(коллекция.title)}</span>'
                f'<span class="zhub__d">'
                f'{html.escape(польза_подборки(коллекция.description))}</span>'
                f'<span class="zhub__go">Открыть подборку →</span>'
                f'</a>')"""
AM_ХАБ_СЕТКА_БЫЛО = """        return f'<div class="zhub">{"".join(карточки)}</div>'

    def список(self, разд: str, зпр: dict) -> str:"""
AM_ХАБ_СЕТКА_СТАЛО = """        return f'<div class="zhub zhub--big">{"".join(карточки)}</div>'

    def список(self, разд: str, зпр: dict) -> str:"""


#: Полка не повторяется визиткой в блоке подборок главной: это тот же состав
#: второй раз. В хабе `/collections/` она остаётся.
AM_ДУБЛЬ_БЫЛО = """        карточки = self._карточки_коллекций()[:4]
        if not карточки:
            return """""
AM_ДУБЛЬ_СТАЛО = """        # Подборка, которая уже стоит первой лентой крупными постерами, в
        # блоке ниже была бы тем же составом второй раз — на живой главной
        # 27.10 это и было видно: три первых постера полки повторялись
        # обложкой первой визитки. В хабе `/collections/` она остаётся.
        ключ_полки = next((п.key for п in РУЧНЫЕ_ПОДБОРКИ.values()
                           if getattr(п, "home_rail", False)), "")
        карточки = [к for к in self._карточки_коллекций()
                    if к.get("key") != ключ_полки][:4]
        if not карточки:
            return """""


AM_ПАРЫ = (
    ("Animedia: показ визитки", AM_ПОКАЗ_ЯКОРЬ, AM_ПОКАЗ + AM_ПОКАЗ_ЯКОРЬ,
     "ПОКАЗ_ВИЗИТКИ ="),
    ("Animedia: показ полки", AM_ПОКАЗ_ПОЛКИ_ЯКОРЬ,
     AM_ПОКАЗ_ПОЛКИ + AM_ПОКАЗ_ПОЛКИ_ЯКОРЬ, "ПОКАЗ_ПОЛКА ="),
    ("Animedia: стиль визитки и полки", AM_СТИЛЬ_ЯКОРЬ,
     AM_СТИЛЬ_НОВОЕ + AM_СТИЛЬ_ЯКОРЬ, ".zhub__g--big{"),
    ("Animedia: помощник пользы", ПОМОЩНИК_ЯКОРЬ, ПОМОЩНИК + ПОМОЩНИК_ЯКОРЬ,
     "def польза_подборки"),
    ("Animedia: три превью вместо четырёх", AM_СБОРЩИК_БЫЛО, AM_СБОРЩИК_СТАЛО,
     "if len(постеры) >= 3:"),
    ("Animedia: крупная визитка", AM_СЕТКА_БЫЛО, AM_СЕТКА_СТАЛО,
     'zhub__g zhub__g--big'),
    ("Animedia: хаб — крупные обложки", AM_ХАБ_ОБЛОЖКИ_БЫЛО,
     AM_ХАБ_ОБЛОЖКИ_СТАЛО, "for к in выбранные[:3] if к.poster"),
    ("Animedia: хаб — счёт значком", AM_ХАБ_КАРТОЧКА_БЫЛО, AM_ХАБ_КАРТОЧКА_СТАЛО,
     'f\'<span class="zhub__n">{коллекция.total} \''),
    ("Animedia: хаб — сетка крупных", AM_ХАБ_СЕТКА_БЫЛО, AM_ХАБ_СЕТКА_СТАЛО,
     'class="zhub zhub--big">{"".join(карточки)}'),
    ("Animedia: полка главной", AM_ПОЛКА_ЯКОРЬ, AM_ПОЛКА + AM_ПОЛКА_ЯКОРЬ,
     "def _полка_главной"),
    # Порядок этих двух пар значим: «не дважды» правится ПЕРВОЙ, пока вызов
    # блока подборок в файле один. Иначе правка попадает в только что
    # вставленный вызов внутри `if полка_главной:`, и у `if` пустеет тело.
    ("Animedia: полка не дублируется визиткой", AM_ДУБЛЬ_БЫЛО, AM_ДУБЛЬ_СТАЛО,
     'к.get("key") != ключ_полки'),
    ("Animedia: подборки не дважды", AM_ПОДБОРКИ_БЫЛО, AM_ПОДБОРКИ_СТАЛО,
     "if not полка_главной:"),
    ("Animedia: полка первым блоком", AM_ГЛАВНАЯ_БЫЛО, AM_ГЛАВНАЯ_СТАЛО,
     "полка_главной, полка_слаги = self._полка_главной()"),
)


def линия(текст: str) -> str:
    if "def _карточки_коллекций(self)" in текст:
        return "animedia"
    if "class РучнаяПодборка:" in текст:
        return "контракт"
    if "_ld_json_scripts" in текст:
        return "zona"
    return "канон"


def остатки(текст: str) -> list:
    эта = линия(текст)
    пары = {"animedia": AM_ПАРЫ, "контракт": КОНТРАКТ_ПАРЫ}.get(эта, ZONA_ПАРЫ)
    return [f"нет: {имя}" for имя, _, _, признак in пары if признак not in текст]


def применить(текст: str) -> tuple[str, list]:
    эта = линия(текст)
    пары = {"animedia": AM_ПАРЫ, "контракт": КОНТРАКТ_ПАРЫ}.get(эта, ZONA_ПАРЫ)
    if эта == "канон":
        raise SystemExit("ОТКАЗ: это не рантайм линии Zona и не контракт "
                         "подборок — своих якорей для него у инструмента нет")
    журнал = []
    for имя, было, стало, признак in пары:
        if признак in текст:
            журнал.append(f"пропущено (уже стоит): {имя}")
            continue
        if было not in текст:
            raise SystemExit(f"ОТКАЗ: якорь «{имя}» не найден — рантайм "
                             "разошёлся с разобранным образцом")
        # Стиль объявлен в нескольких темах этого рантайма: правится КАЖДОЕ
        # вхождение якоря, иначе часть тем останется со старой плашкой.
        сколько = (текст.count(было)
                   if имя in ("стиль полки и визитки",) else 1)
        текст = текст.replace(было, стало, сколько)
        журнал.append(f"применено{'' if сколько == 1 else f' ×{сколько}'}: {имя}")
    return текст, журнал


def main(аргв=None) -> int:
    р = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    р.add_argument("файлы", nargs="+")
    р.add_argument("--check", action="store_true")
    а = р.parse_args(аргв)
    плохих = 0
    for имя in а.файлы:
        путь = Path(имя)
        исходный = путь.read_text(encoding="utf-8")
        if линия(исходный) == "канон":
            print("не этой линии (нет своих якорей) " + str(путь))
            continue
        if а.check:
            п = остатки(исходный)
            print(("ок     " if not п else "НЕ ПРИВЕДЁН ") + str(путь)
                  + ("" if not п else f"  остатки: {п}"))
            плохих += bool(п)
            continue
        новый, журнал = применить(исходный)
        print(f"== {путь}")
        for строка in журнал:
            print(f"   {строка}")
        п = остатки(новый)
        if п:
            print(f"ОТКАЗ: после правки остались признаки непривёденности: {п}",
                  file=sys.stderr)
            return 1
        if новый != исходный:
            путь.write_text(новый, encoding="utf-8")
    return 1 if плохих else 0


if __name__ == "__main__":
    raise SystemExit(main())
