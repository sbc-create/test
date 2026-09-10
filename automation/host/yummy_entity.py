"""Представление сущности Yummy: то, что шаблон готов принять от контура.

Зачем отдельный модуль
----------------------

Контентный контур (`yummy-read-model/1.x`) ведёт Архитектор, шаблон — мы. Если
шаблон читает базу напрямую в местах вывода, то любое расширение контракта
превращается в переделку разметки. Здесь объявлено ровно обратное: **набор
полей, которые витрина умеет показать**, и правила их показа. Появится поле в
контуре — оно отобразится само, без правки шаблона.

Три правила, которые здесь закреплены
-------------------------------------

1. **Отсутствующее поле скрывается поодиночке.** Не «прочерк», не ноль, не
   пустая подпись: строки просто нет. Пустая подпись «Студия: —» выглядит как
   работающая вёрстка при отсутствующих данных и потому не чинится.
2. **Ничего не достраивается.** Компонент рекомендаций читает только
   `recommendations[]`; подобрать «похожее» внутри шаблона запрещено — это
   выдуманные данные с видом настоящих.
3. **Пустой массив — это ответ.** Секция без элементов исчезает целиком, а не
   показывает заглушку в рамке: пустое место на странице читается как поломка.

Личная оценка
-------------

Компонент внутренней оценки закрыт capability-флагом. Пока у Архитектора нет
рабочего API, флаг выключен, и наружу компонент не выходит вовсе. Имитация
сохранения запрещена: кнопка, которая «запомнила» оценку в localStorage, — это
ложь пользователю о том, что его действие сохранено.
"""

from __future__ import annotations

import html
import sys
from pathlib import Path

#: Контракт представления: что умеет показать витрина.
КОНТРАКТ = "yummy-entity-view/1.0.0"

#: Контракты контура, которые представление принимает. Мажор фиксирован:
#: 1.x расширяет набор полей и не ломает уже показанные, 2.0 потребует
#: пересмотра представления и обязан быть отвергнут явно, а не молча.
ПРИНИМАЕМЫЙ_МАЖОР = 1
ИМЯ_КОНТУРА = "yummy-read-model"


def совместим(контракт: str | None) -> bool:
    """Принимаем ли мы этот контракт контура.

    Несовместимость обязана быть громкой: молча показать половину полей от
    чужого контракта хуже, чем не показать ничего.
    """
    if not контракт or "/" not in контракт:
        return False
    имя, _, версия = контракт.partition("/")
    if имя != ИМЯ_КОНТУРА:
        return False
    мажор = версия.split(".")[0]
    return мажор.isdigit() and int(мажор) == ПРИНИМАЕМЫЙ_МАЖОР


def _соседний(имя: str, модуль: str):
    import importlib.machinery
    import importlib.util
    путь = Path(__file__).resolve().parent / имя
    спец = importlib.util.spec_from_loader(
        модуль, importlib.machinery.SourceFileLoader(модуль, str(путь)))
    м = importlib.util.module_from_spec(спец)
    sys.modules.setdefault(модуль, м)
    спец.loader.exec_module(м)
    return м


# Канонический адрес — один на всю витрину. Второй реализации не заводим:
# два места, приводящих адрес к каноническому виду, однажды разойдутся.
_СТРАНИЦЫ = sys.modules.get("yummy_pages") or _соседний("yummy_pages.py", "yummy_pages")
канонический_путь = _СТРАНИЦЫ.канонический_путь


# --- вспомогательное ---------------------------------------------------------

def _э(з) -> str:
    return html.escape("" if з is None else str(з))


def есть(значение) -> bool:
    """Есть ли что показывать.

    Ноль, пустая строка, пустой список и None — нечего. Ноль отдельно: «серий
    0» и «голосов 0» — это отсутствие данных, а не факт, и печатать его нельзя.
    """
    if значение is None:
        return False
    if isinstance(значение, str):
        return значение.strip() != ""
    if isinstance(значение, (list, tuple, set, dict)):
        return len(значение) > 0
    if isinstance(значение, (int, float)):
        return значение != 0
    return True


def _список(значение, предел: int = 0) -> str:
    э = [str(з).strip() for з in значение if str(з).strip()]
    if предел and len(э) > предел:
        э = э[:предел]
    return ", ".join(_э(з) for з in э)


def _ссылки(значение, база: str, предел: int = 0) -> str:
    """Список с переходом в каталог. Адрес перехода — только известный маршрут."""
    э = [str(з).strip() for з in значение if str(з).strip()]
    if предел and len(э) > предел:
        э = э[:предел]
    from urllib.parse import quote
    return ", ".join(
        f'<a href="{_э(база)}{quote(з)}">{_э(з)}</a>' for з in э)


#: Человеческие подписи типов и статусов. Неизвестное значение печатается как
#: есть — переводить наугад значит выдумывать.
ТИПЫ = {"MOVIE": "Фильм", "SERIES": "Сериал", "OVA": "OVA", "ONA": "ONA",
        "SPECIAL": "Спецвыпуск", "UNKNOWN": ""}
СТАТУСЫ = {"CONFIRMED_ONGOING": "Выходит", "CONFIRMED_FINISHED": "Завершён",
           "CONFIRMED_ANNOUNCED": "Анонс", "UNCONFIRMED": ""}
ПРОВАЙДЕРЫ = {"imdb": "IMDb", "kp": "Кинопоиск", "shikimori": "Shikimori",
              "anilist": "AniList", "simkl": "Simkl", "kitsu": "Kitsu",
              "mal": "MyAnimeList", "mdl": "MyDramaList"}


def имя_провайдера(код: str) -> str:
    return ПРОВАЙДЕРЫ.get((код or "").lower(), код or "")


# --- рейтинги ----------------------------------------------------------------

def рейтинги(список: list[dict]) -> str:
    """Каждая оценка отдельно: провайдер, значение, шкала, голоса.

    Сводить оценки разных провайдеров в одно безымянное число запрещено: у них
    разные шкалы, разные аудитории и разный смысл. Голоса, которых источник не
    отдал, не заменяются нулём — строка про голоса просто не печатается.
    """
    годные = [о for о in (список or [])
              if есть(о.get("value")) and есть(о.get("scale"))
              and (о.get("status") or "OK") == "OK"]
    if not годные:
        return ""
    части = []
    for о in годные:
        имя = имя_провайдера(о.get("provider"))
        голоса = ""
        if есть(о.get("votes")):
            голоса = f'<span class="sf-rt__v">{int(о["votes"]):,}</span>'.replace(",", " ")
        части.append(
            f'<li class="sf-rt"><span class="sf-rt__p">{_э(имя)}</span>'
            f'<span class="sf-rt__n">{float(о["value"]):.1f}'
            f'<small>/{float(о["scale"]):.0f}</small></span>{голоса}</li>')
    return ('<ul class="sf-rates" aria-label="Оценки источников">'
            + "".join(части) + "</ul>")


# --- поля карточки -----------------------------------------------------------
#
# Порядок здесь — порядок на странице. Каждое поле знает, как себя показать, и
# показывается только если данные есть: строку рисует общий проход, а не
# двадцать «если» по разметке.
ПОЛЯ = (
    ("title_original", "Оригинальное название", lambda з: _э(з)),
    ("alt_titles", "Другие названия", lambda з: _список(з, 8)),
    ("kind", "Тип", lambda з: _э(ТИПЫ.get(з, з))),
    ("status", "Статус", lambda з: _э(СТАТУСЫ.get(з, з))),
    ("year", "Год", lambda з: _э(з)),
    ("aired", "Даты показа", lambda з: _э(з)),
    ("countries", "Страна", lambda з: _список(з, 4)),
    ("studios", "Студия", lambda з: _список(з, 4)),
    ("genres", "Жанры", lambda з: _ссылки(з, "/catalog?genre=", 10)),
    ("directors", "Режиссёр", lambda з: _список(з, 4)),
    ("cast", "В ролях", lambda з: _список(з, 10)),
    ("age_rating", "Возраст", lambda з: _э(з)),
    ("duration", "Длительность", lambda з: _э(з)),
    ("seasons", "Сезонов", lambda з: _э(з)),
    ("episodes", "Серий", lambda з: _э(з)),
    ("dubs", "Озвучки", lambda з: _список(з, 12)),
)


#: Поля, которые витрина YummyAnime рисует своей карточкой сама.
#:
#: Показать их вторым блоком значило бы удвоить карточку: у посетителя два
#: списка жанров, два списка озвучек и два набора оценок, причём из разных
#: источников. Поэтому по умолчанию представление работает ДОПОЛНЕНИЕМ и
#: рисует только то, чего на странице нет.
#:
#: Список объявлен явно и проверяется тестом. Если витрина перестанет рисовать
#: карточку, режим переключается на полный — и он уже проверен на фикстуре.
РИСУЕТ_ВИТРИНА = (
    "title_original", "alt_titles", "kind", "status", "year", "aired",
    "countries", "studios", "genres", "directors", "cast", "age_rating",
    "duration", "episodes", "dubs",
)


def _строки(с: dict, пропустить=()) -> str:
    строки = []
    for ключ, подпись, как in ПОЛЯ:
        if ключ in пропустить:
            continue
        значение = с.get(ключ)
        if not есть(значение):
            continue                      # поле скрывается поодиночке
        напечатано = как(значение)
        if not напечатано.strip():
            continue                      # словарь не знал значения — не печатаем пустоту
        строки.append(f'<div class="sf-f"><dt>{_э(подпись)}</dt>'
                      f'<dd>{напечатано}</dd></div>')
    return ('<dl class="sf-fields">' + "".join(строки) + "</dl>") if строки else ""


def карточка_тайтла(с: dict, каппы: dict | None = None,
                    пропустить: tuple = ()) -> str:
    """Полная карточка: показывает всё, что пришло, и молчит об остальном.

    `пропустить` — поля, которые уже нарисованы витриной. Так представление
    работает дополнением, не удваивая карточку. Пустой набор даёт полный
    режим — тот, что проверен на фикстуре.

    Плеер сюда не входит и отсюда не управляется: он остаётся тем же блоком
    приложения, а карточка встаёт рядом.
    """
    каппы = каппы or {}
    if not есть(с.get("entity_id")) and not есть(с.get("title")):
        return ""
    путь = канонический_путь(с.get("canonical_path") or "")
    шапка = []
    if есть(с.get("poster")) and "poster" not in пропустить:
        шапка.append(
            f'<div class="sf-poster"><img src="{_э(с["poster"])}" width="230" '
            f'height="322" loading="lazy" decoding="async" '
            f'alt="Постер: {_э(с.get("title") or "")}"></div>')
    заголовки = []
    if есть(с.get("title")) and "title" not in пропустить:
        заголовки.append(f'<p class="sf-t">{_э(с["title"])}</p>')
    метки = []
    for ключ, словарь in (("kind", ТИПЫ), ("status", СТАТУСЫ)):
        if ключ in пропустить:
            continue
        зн = словарь.get(с.get(ключ), с.get(ключ))
        if есть(зн):
            метки.append(f'<span class="sf-chip">{_э(зн)}</span>')
    for ключ in ("year", "age_rating", "duration"):
        if есть(с.get(ключ)) and ключ not in пропустить:
            метки.append(f'<span class="sf-chip">{_э(с[ключ])}</span>')
    метки_html = f'<p class="sf-chips">{"".join(метки)}</p>' if метки else ""
    оценки = "" if "ratings" in пропустить else рейтинги(с.get("ratings") or [])
    личная = личная_оценка(с.get("personal") or {}, каппы)
    описание = ""
    if есть(с.get("description")) and "description" not in пропустить:
        описание = f'<p class="sf-desc">{_э(с["description"])}</p>'
    поля = _строки(с, пропустить)
    реки = ("" if "recommendations" in пропустить
            else рекомендации(с.get("recommendations") or []))

    # Блок целиком не выводится, если показывать нечего: пустая рамка с одним
    # заголовком — это и есть «пустое место», запрещённое правилом.
    если_нечего = not any((шапка, заголовки, метки_html, оценки, описание,
                          поля, личная, реки))
    if если_нечего:
        return ""
    фон = ""
    if есть(с.get("backdrop")) and "backdrop" not in пропустить:
        фон = (f'<div class="sf-bd" role="presentation" '
               f'style="background-image:url({_э(с["backdrop"])})"></div>')
    сущность = f' data-entity="{_э(с.get("entity_id"))}"' if есть(с.get("entity_id")) else ""
    канон = f' data-canonical="{_э(путь)}"' if путь else ""
    return (
        f'<section class="sf-entity" data-contract="{КОНТРАКТ}"{сущность}{канон}>'
        + фон
        + '<div class="sf-entity__in">'
        + "".join(шапка)
        + '<div class="sf-entity__main">'
        + "".join(заголовки) + метки_html + оценки + личная + описание + поля
        + "</div></div>" + реки + "</section>")


# --- рекомендации ------------------------------------------------------------

МИНИМУМ_РЕКОМЕНДАЦИЙ = 6


def рекомендации(список: list[dict]) -> str:
    """Только `recommendations[]` контракта. Ничего не подбирается на месте.

    Подбор «похожего» внутри шаблона — это выдуманная связь: она выглядит как
    редакционное решение, но им не является и никем не проверена.
    """
    if not список:
        return ""                          # пустой массив скрывает секцию целиком
    карточки = []
    for р in список:
        путь = канонический_путь(р.get("canonical_path") or "")
        if not путь:
            continue                       # без канонического адреса не публикуем
        постер = (f'<img src="{_э(р["poster"])}" width="230" height="322" '
                  f'loading="lazy" decoding="async" alt="{_э(р.get("title") or "")}">'
                  ) if есть(р.get("poster")) else (
                  '<span class="sf-noposter" aria-hidden="true"></span>')
        мета = [str(з) for з in (р.get("year"), ТИПЫ.get(р.get("kind"), р.get("kind")))
                if есть(з)]
        мета_html = f'<span class="sf-rc__m">{_э(" · ".join(мета))}</span>' if мета else ""
        оценка = ""
        первая = next((о for о in (р.get("ratings") or [])
                       if есть(о.get("value")) and есть(о.get("scale"))), None)
        if первая:
            оценка = (f'<span class="sf-rc__r">{float(первая["value"]):.1f}'
                      f'<small>/{float(первая["scale"]):.0f} '
                      f'{_э(имя_провайдера(первая.get("provider")))}</small></span>')
        причина = ""
        if есть(р.get("reason")):
            источник = f' — {_э(р["source"])}' if есть(р.get("source")) else ""
            причина = f'<span class="sf-rc__w">{_э(р["reason"])}{источник}</span>'
        карточки.append(
            f'<article class="sf-rc" data-entity="{_э(р.get("entity_id") or "")}">'
            f'<a class="sf-rc__a" href="{_э(путь)}">{постер}</a>'
            f'<a class="sf-rc__t" href="{_э(путь)}">{_э(р.get("title") or "")}</a>'
            f'{мета_html}{оценка}{причина}</article>')
    if not карточки:
        return ""
    return ('<section class="sf-recs" aria-labelledby="sf-recs-h">'
            '<h2 id="sf-recs-h" class="sf-h">Похожее</h2>'
            f'<div class="sf-recs__grid">{"".join(карточки)}</div></section>')


# --- личная оценка -----------------------------------------------------------

СОСТОЯНИЯ_ОЦЕНКИ = ("нет", "оценено", "изменение", "загрузка", "ошибка", "недоступен")


def личная_оценка(состояние: dict, каппы: dict | None = None) -> str:
    """Внутренняя оценка за capability-флагом.

    Флаг выключен — компонента нет в разметке вообще. Не «серая кнопка», не
    «скоро»: неработающий орган управления обучает не нажимать и на рабочий.

    Сохранение не имитируется. Все переходы состояний делает API Архитектора;
    здесь только их отображение.
    """
    каппы = каппы or {}
    if not каппы.get("personal_rating"):
        return ""
    вид = состояние.get("state") or "нет"
    if вид not in СОСТОЯНИЯ_ОЦЕНКИ:
        вид = "нет"
    шкала = int(состояние.get("scale") or 10)
    своя = состояние.get("value")
    голоса = состояние.get("votes")
    среднее = состояние.get("average")

    свод = []
    if есть(среднее):
        свод.append(f'<span class="sf-pr__avg">{float(среднее):.1f}'
                    f'<small>/{шкала}</small></span>')
    if есть(голоса):
        свод.append(f'<span class="sf-pr__v">{int(голоса):,}</span>'.replace(",", " "))
    свод_html = f'<p class="sf-pr__sum">{"".join(свод)}</p>' if свод else ""

    if вид == "недоступен":
        тело = ('<p class="sf-pr__msg" role="status">Оценки временно недоступны. '
                'Сохранение не выполнялось.</p>')
    elif вид == "ошибка":
        текст = состояние.get("error") or "Оценка не сохранена"
        тело = (f'<p class="sf-pr__msg sf-pr__msg--err" role="alert">{_э(текст)}. '
                f'Попробуйте ещё раз.</p>')
    elif вид == "загрузка":
        тело = ('<p class="sf-pr__msg" role="status" aria-live="polite">'
                'Сохраняем оценку…</p>')
    else:
        кнопки = "".join(
            f'<button class="sf-pr__b" type="button" value="{n}" '
            f'aria-pressed="{"true" if есть(своя) and int(своя) == n else "false"}">'
            f'{n}</button>' for n in range(1, шкала + 1))
        подпись = {"нет": "Ваша оценка",
                   "оценено": f"Ваша оценка: {своя}",
                   "изменение": f"Меняем оценку (сейчас {своя})"}[вид]
        сброс = ('<button class="sf-pr__x" type="button">Убрать оценку</button>'
                 if вид in ("оценено", "изменение") else "")
        тело = (f'<p class="sf-pr__lbl">{_э(подпись)}</p>'
                f'<div class="sf-pr__scale" role="group" '
                f'aria-label="Оценка от 1 до {шкала}">{кнопки}</div>{сброс}')
    return (f'<div class="sf-pr" data-state="{_э(вид)}" data-scale="{шкала}">'
            f'{свод_html}{тело}</div>')


# --- ленты -------------------------------------------------------------------
#
# Шесть независимых поверхностей. У каждой свой массив и свой источник; общий
# каталог под шестью заголовками — это раздел, который выглядит работающим и
# потому никогда не чинится.
ПОВЕРХНОСТИ = {
    "new_episodes": ("Новые серии", "События появления серий."),
    "ongoing": ("Сейчас выходит", "Только подтверждённый статус показа."),
    "trending": ("Актуальное", "Свежесть, сглаженный рейтинг и статус показа."),
    "news": ("Новости", "Материалы редакции с указанием источника."),
    "announcements": ("Анонсы", "Заявленные релизы."),
    "schedule": ("Расписание", "Подтверждённые даты ближайших серий."),
}


def лента(поверхность: str, элементы: list[dict], заголовок: str | None = None,
          подпись: str | None = None, плитка=None, сеткой: bool = True) -> str:
    """Секция одной поверхности. Пустой массив — секции нет.

    Не «пусто» в рамке и не заглушка: раздел исчезает вместе с заголовком,
    иначе страница показывает пустое место, которое читается как поломка.
    """
    if not элементы:
        return ""
    имя, по_умолчанию = ПОВЕРХНОСТИ.get(поверхность, (поверхность, ""))
    имя = заголовок or имя
    подпись = подпись if подпись is not None else по_умолчанию
    рисовать = плитка or _плитка
    тела = [t for t in (рисовать(э) for э in элементы) if t]
    if not тела:
        return ""
    ид = f"sf-s-{поверхность}"
    подпись_html = f'<p class="sf-s__note">{_э(подпись)}</p>' if подпись else ""
    класс = "sf-s__grid" if сеткой else "sf-s__list"
    return (f'<section class="sf-s" data-surface="{_э(поверхность)}" '
            f'aria-labelledby="{ид}"><h2 id="{ид}" class="sf-h">{_э(имя)}</h2>'
            f'{подпись_html}<div class="{класс}">{"".join(тела)}</div></section>')


def _плитка(э: dict) -> str:
    путь = канонический_путь(э.get("canonical_path") or "")
    if not путь:
        return ""
    постер = (f'<img src="{_э(э["poster"])}" width="230" height="322" loading="lazy" '
              f'decoding="async" alt="{_э(э.get("title") or "")}">'
              ) if есть(э.get("poster")) else (
              '<span class="sf-noposter" aria-hidden="true"></span>')
    строка = ""
    if есть(э.get("caption")):
        строка = f'<span class="sf-rc__m">{_э(э["caption"])}</span>'
    return (f'<article class="sf-rc" data-entity="{_э(э.get("entity_id") or "")}">'
            f'<a class="sf-rc__a" href="{_э(путь)}">{постер}</a>'
            f'<a class="sf-rc__t" href="{_э(путь)}">{_э(э.get("title") or "")}</a>'
            f'{строка}</article>')


def пост(п: dict) -> str:
    """Новость или анонс. Без канонического адреса материал не публикуется."""
    путь = п.get("canonical_path") or ""
    if not путь.startswith("/"):
        return ""
    дата = ""
    if есть(п.get("published_at")):
        дата = (f'<time class="sf-p__d" datetime="{_э(п["published_at"])}">'
                f'{_э(str(п["published_at"])[:10])}</time>')
    свод = f'<p class="sf-p__s">{_э(п["summary"])}</p>' if есть(п.get("summary")) else ""
    источник = f'<span class="sf-p__src">{_э(п["source"])}</span>' if есть(п.get("source")) else ""
    картинка = (f'<img class="sf-p__i" src="{_э(п["image"])}" loading="lazy" '
                f'decoding="async" alt="">') if есть(п.get("image")) else ""
    return (f'<article class="sf-p"><a class="sf-p__t" href="{_э(путь)}">'
            f'{картинка}<span>{_э(п.get("title") or "")}</span></a>'
            f'{свод}<p class="sf-p__m">{дата}{источник}</p></article>')


def _множество(элементы) -> set:
    return {str(э.get("entity_id") or э.get("canonical_path") or "")
            for э in (элементы or [])} - {""}


def пересечения(секции: dict[str, list[dict]]) -> dict[str, list[str]]:
    """Какие сущности видны больше чем в одном разделе страницы.

    Диагностика, а не запрет: тайтл законно бывает и в «Сейчас выходит», и в
    «Расписании» — это разные вопросы об одной сущности. Значение имеет доля
    совпадения, и её считает `совпадения()`.
    """
    где: dict[str, list[str]] = {}
    for имя, элементы in секции.items():
        for э in элементы or []:
            ид = э.get("entity_id") or э.get("canonical_path")
            if ид:
                где.setdefault(str(ид), []).append(имя)
    return {ид: разделы for ид, разделы in где.items() if len(set(разделы)) > 1}


#: Доля совпадения, выше которой два раздела — это один массив под двумя
#: заголовками. Порог не «на глаз»: /collections/ и /schedule/ однажды
#: совпадали на 100 %, и обе страницы выглядели работающими.
ПОРОГ_СОВПАДЕНИЯ = 0.8


def совпадения(секции: dict[str, list[dict]],
               порог: float = ПОРОГ_СОВПАДЕНИЯ) -> list[tuple[str, str, float]]:
    """Пары разделов, которые показывают по сути один и тот же массив.

    Главный запрет владельца: нарезать общий каталог под разными заголовками.
    Раздел, совпадающий с соседним, выглядит наполненным и потому никогда не
    чинится — поэтому совпадение обязано падать в тесте, а не читаться глазами.
    """
    имена = [и for и in секции if _множество(секции[и])]
    итог = []
    for i, а in enumerate(имена):
        for б in имена[i + 1:]:
            А, Б = _множество(секции[а]), _множество(секции[б])
            доля = len(А & Б) / len(А | Б)
            if доля >= порог:
                итог.append((а, б, round(доля, 3)))
    return итог


# --- оформление --------------------------------------------------------------
#
# Только собственные компоненты. Типографика и цвета витрины не трогаются:
# акцент берётся из переменной варианта домена, а если её нет — из currentColor.
СТИЛЬ = (
    ".sf-entity{position:relative;margin:24px 0;padding:18px;border-radius:16px;"
    "border:1px solid color-mix(in srgb,currentColor 14%,transparent);overflow:hidden}"
    ".sf-bd{position:absolute;inset:0;background-size:cover;background-position:50% 30%;"
    "opacity:.13;filter:saturate(1.1)}"
    ".sf-entity__in{position:relative;display:flex;gap:18px;flex-wrap:wrap}"
    ".sf-entity__main{flex:1 1 320px;min-width:0}"
    ".sf-poster img{width:172px;height:auto;border-radius:12px;display:block}"
    ".sf-t{margin:0 0 6px;font-size:15px;opacity:.75}"
    ".sf-chips{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 10px}"
    ".sf-chip{font-size:12px;padding:3px 9px;border-radius:999px;"
    "border:1px solid color-mix(in srgb,var(--sf-accent,currentColor) 45%,transparent)}"
    ".sf-rates{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 10px;padding:0;list-style:none}"
    ".sf-rt{display:flex;align-items:baseline;gap:5px;padding:4px 9px;border-radius:9px;"
    "background:color-mix(in srgb,currentColor 8%,transparent);font-size:13px}"
    ".sf-rt__p{opacity:.7}.sf-rt__n{font-weight:700}.sf-rt__n small{font-weight:400;opacity:.6}"
    ".sf-rt__v{opacity:.55;font-size:11px}"
    ".sf-desc{margin:10px 0;line-height:1.55;max-width:72ch}"
    ".sf-fields{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));"
    "gap:6px 18px;margin:12px 0 0}"
    ".sf-f{display:flex;gap:8px;font-size:14px;line-height:1.5;min-width:0}"
    ".sf-f dt{flex:0 0 auto;opacity:.6}.sf-f dd{margin:0;min-width:0;overflow-wrap:anywhere}"
    ".sf-h{font-size:18px;margin:22px 0 4px}"
    ".sf-s__note{margin:0 0 12px;opacity:.65;font-size:13px}"
    ".sf-recs__grid,.sf-s__grid{display:grid;gap:14px;"
    "grid-template-columns:var(--sf-grid,repeat(auto-fill,minmax(150px,1fr)))}"
    ".sf-rc{min-width:0;display:flex;flex-direction:column;gap:4px}"
    ".sf-rc__a{display:block;aspect-ratio:2/3;border-radius:10px;overflow:hidden}"
    ".sf-rc__a img{width:100%;height:100%;object-fit:cover;display:block}"
    ".sf-noposter{display:block;width:100%;height:100%;"
    "background:color-mix(in srgb,currentColor 10%,transparent)}"
    ".sf-rc__t{font-size:13px;line-height:1.35;overflow-wrap:anywhere}"
    ".sf-rc__m{font-size:12px;opacity:.6}"
    ".sf-rc__r{font-size:12px;font-weight:700}.sf-rc__r small{font-weight:400;opacity:.6}"
    ".sf-rc__w{font-size:12px;opacity:.7;font-style:italic}"
    ".sf-s__list{display:block}"
    ".sf-p{padding:12px 0;border-top:1px solid color-mix(in srgb,currentColor 12%,transparent)}"
    ".sf-p__t{display:flex;gap:12px;align-items:flex-start;font-weight:600;line-height:1.4}"
    ".sf-p__i{width:96px;height:64px;object-fit:cover;border-radius:8px;flex:0 0 auto}"
    ".sf-p__s{margin:6px 0 0;opacity:.8;font-size:14px;line-height:1.5;max-width:72ch}"
    ".sf-p__m{margin:6px 0 0;font-size:12px;opacity:.55;display:flex;gap:10px}"
    ".sf-pr{margin:0 0 12px}"
    ".sf-pr__sum{margin:0 0 4px;display:flex;gap:8px;align-items:baseline}"
    ".sf-pr__avg{font-weight:700}.sf-pr__avg small{font-weight:400;opacity:.6}"
    ".sf-pr__v{font-size:12px;opacity:.55}"
    ".sf-pr__lbl{margin:0 0 4px;font-size:13px;opacity:.7}"
    ".sf-pr__scale{display:flex;flex-wrap:wrap;gap:4px}"
    ".sf-pr__b{min-width:30px;min-height:30px;border-radius:8px;cursor:pointer;"
    "border:1px solid color-mix(in srgb,currentColor 25%,transparent);background:none;"
    "color:inherit;font:inherit}"
    ".sf-pr__b[aria-pressed=true]{background:var(--sf-accent,currentColor);color:#111}"
    ".sf-pr__b:focus-visible,.sf-pr__x:focus-visible{outline:2px solid var(--sf-accent,"
    "currentColor);outline-offset:2px}"
    ".sf-pr__x{margin-top:6px;background:none;border:0;color:inherit;opacity:.6;"
    "cursor:pointer;font:inherit;text-decoration:underline}"
    ".sf-pr__msg{margin:0;font-size:13px;opacity:.75}"
    ".sf-pr__msg--err{opacity:1;color:#ff8080}"
    "@media(max-width:520px){.sf-poster img{width:118px}"
    ".sf-fields{grid-template-columns:1fr}}"
)
