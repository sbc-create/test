#!/usr/bin/env python3
"""Витрина ANIMEDIA: собственный изолированный рантайм.

Этот файл — entrypoint контура Animedia и ничей больше. Он появился потому, что
прежний общий рантайм обслуживал шесть витрин трёх контуров одним файлом: имя
файла принадлежало соседу, вид Animedia наследовал вид соседа, а профили,
палитры и стили трёх контуров лежали рядом. Любая правка ради одной витрины
физически касалась остальных, и заметно это становилось только после
перезапуска.

Что здесь есть и чего нет:

* виды, палитры, стили и профили соседних контуров — удалены;
* общая база, от которой наследует вид Animedia, скопирована как СВОЙ код под
  нейтральным именем `ВидОснова`: это форк, а не импорт, поэтому дальше она
  расходится с соседом свободно и без согласований;
* семейство проверяется на старте: манифест, объявляющий чужое семейство, не
  поднимает витрину. Молча отдать чужой шаблон хуже, чем не подняться.

Чего этот файл НЕ делает: не читает и не пишет ничего в каталогах соседних
контуров, не импортирует их модули и не носит их имя.

Переменные окружения. Свои — `ANIMEDIA_*`. Юниты витрин принадлежат root и
задают прежние имена `LORDS_*`; они читаются как совместимость, пока владелец
не сменит `ExecStart`. Это единственное место, где прежние имена упомянуты, и
они здесь не потому, что код чужой, а потому что чужая только строка запуска.

Сборка файла воспроизводима: `automation/host/animedia_entrypoint_build.py`
собирает его из общего рантайма перечнем именованных операций, а проверка
паритета рендера сравнивает HTML всех маршрутов побайтно с прежней версией.
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
import secrets
import threading
import time
import unicodedata
from difflib import SequenceMatcher
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, parse_qsl, quote, unquote, urlencode, urlparse

def _окр(имя: str, прежнее: str, по_умолчанию: str = "") -> str:
    """Своё имя переменной впереди, прежнее — совместимость с юнитом."""
    return os.environ.get(имя) or os.environ.get(прежнее) or по_умолчанию


#: Корень рантайма. Сейчас общий и носит имя соседа по историческим
#: причинам; собственный корень требует смены ExecStart юнитов, то есть
#: действия владельца под root (`config/animedia/TENANT_SCOPE.yaml`,
#: planned_own_root). Переезд — правка этой одной строки.
_КОРЕНЬ_РАНТАЙМА = Path(os.environ.get("ANIMEDIA_RUNTIME_ROOT",
                                       "/srv/lords/.frontend"))

РЕВИЗИЯ = _окр("ANIMEDIA_TEMPLATE_REVISION", "LORDS_TEMPLATE_REVISION",
               "unknown")
МАНИФЕСТ_ФАЙЛ = _окр(
    "ANIMEDIA_TEMPLATE_MANIFEST", "LORDS_TEMPLATE_MANIFEST",
    str(_КОРЕНЬ_РАНТАЙМА / "template-manifest-animedia-01.json"))


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
if МАНИФЕСТ["template_family"] != "animedia":
    # Fail closed. Этот рантайм принадлежит одному контуру, и отдать
    # чужое семейство своим оформлением он не имеет права.
    raise SystemExit(
        "этот рантайм обслуживает только семейство animedia, "
        f"манифест объявляет {МАНИФЕСТ['template_family']!r}")
ВЕРСИЯ = МАНИФЕСТ["design_version"]
СЕМЕЙСТВО = МАНИФЕСТ["template_family"]
СБОРКА = МАНИФЕСТ["build_id"]
ПРОФИЛЬ = МАНИФЕСТ.get("profile") or "unknown"

#: Имя общего рантайма. Один артефакт обслуживает все семейства, и это честно —
#: но называть шаблоном семейства «lords-nova» на Yummy, базу и Animedia было
#: неправдой: имя ядра выдавалось за имя шаблона витрины.
ЯДРО = "site-factory-nova"
#: Имя шаблона КОНКРЕТНОГО семейства. Отсюда и из версии складывается то, что
#: домен объявляет о себе.
ШАБЛОН_СЕМЕЙСТВА = f"{СЕМЕЙСТВО}-nova"
КАТАЛОГ_ФАЙЛ = _окр("ANIMEDIA_CATALOG", "LORDS_CATALOG",
                    str(_КОРЕНЬ_РАНТАЙМА / "animedia-01-catalog.json"))
def _рядом_с_каталогом(шаблон: str) -> str:
    """Путь-спутник снимка каталога.

    Юниты витрин принадлежат root и правятся отдельной процедурой, а боковые
    файлы обязаны находиться без правки юнита. Поэтому имя выводится из уже
    заданного `LORDS_CATALOG`: `/…/соседней витрины-catalog.json` даёт
    `/…/соседней витрины-details.json` и `/…/player-соседней витрины.json`. Соглашение
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
ПОДРОБНОСТИ_ФАЙЛ = (_окр("ANIMEDIA_DETAILS", "LORDS_DETAILS")
                    or _рядом_с_каталогом("{site}-details.json"))


def _сайт_из_каталога() -> str:
    """Идентификатор витрины из имени снимка: `animedia-01-catalog.json` → `animedia-01`.

    Единственный вывод идентификатора в файле. Прежде он выводился из профиля
    строковой заменой (`animedia-icu` → `animedia-0icu`), и путь к реестру
    событий указывал на файл, которого нет: лента новых серий молча оставалась
    пустой при живом реестре рядом. Имя снимка задаётся юнитом витрины и уже
    служит источником для соседних файлов — здесь используется то же правило.
    """
    имя = Path(КАТАЛОГ_ФАЙЛ).name
    хвост = "-catalog.json"
    return имя[: -len(хвост)] if имя.endswith(хвост) else ""


#: Идентификатор витрины. Пустым не бывает: без него пути к файлам контура
#: пришлось бы угадывать, а угаданный путь — это чужие данные на своей витрине.
САЙТ_ID = _сайт_из_каталога() or "animedia-01"
СТАРЫЙ_КОРЕНЬ = Path(_окр("ANIMEDIA_LEGACY_ROOT", "LORDS_LEGACY_ROOT",
                          "/srv/animedia/animedia-01/current/site"))
ИМЯ_ВИТРИНЫ = _окр("ANIMEDIA_SITE_NAME", "LORDS_SITE_NAME", "Animedia")
# Для витрин, где страницы отдаёт приложение, а не каталог файлов: всё, чего
# нет в новом маршруте, проксируется в него. Так плеер, карточка и любые
# динамические страницы остаются рабочими — их никто не переписывает.
ВЕРХОВОЙ = _окр("ANIMEDIA_LEGACY_UPSTREAM", "LORDS_LEGACY_UPSTREAM")

# SEO-слой отдельным модулем. Он уже дважды снимался выкладкой шаблонов, и оба
# раза не по злому умыслу: вставка жила в шаблонах, а каждое новое оформление
# добавляет свой <head>. Поэтому слой вызывается из отдачи ответа — её не
# минует ни один шаблон.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import seo_layer as SEO  # noqa: E402

# Контракт коллекций. Канонический экземпляр — `factory/lords/collection_contract.py`,
# и он же единственный: второй отслеживаемый экземпляр означал бы второй
# источник правды о лентах, а разъехаться они могут незаметно.
#
# При запуске из репозитория модуль берётся пакетом. Рядом с выкаченным
# артефактом пакета нет — там deploy кладёт тот же файл спутником
# (`install … factory/lords/collection_contract.py → <frontend>/`), и работает
# второй путь. Отсутствие обоих не должно ронять витрину: без контракта главная
# собирается прежним образом.
_КОРЕНЬ_РЕПО = Path(__file__).resolve().parents[2]
if (_КОРЕНЬ_РЕПО / "factory" / "animedia" / "collection_contract.py").is_file():
    sys.path.insert(0, str(_КОРЕНЬ_РЕПО))
try:
    from factory.animedia import collection_contract as КОЛЛЕКЦИИ  # noqa: E402
except ImportError:
    try:
        import collection_contract as КОЛЛЕКЦИИ  # noqa: E402
    except ImportError:
        КОЛЛЕКЦИИ = None

# Сообщество контура: голоса, реакции и комментарии посетителей. Импорт
# двойной по той же причине — рядом с артефактом пакета нет.
try:
    from factory.animedia import community as СООБЩЕСТВО  # noqa: E402
except ImportError:
    try:
        import community as СООБЩЕСТВО  # noqa: E402
    except ImportError:
        СООБЩЕСТВО = None

# Хронология контура: один порядок «сначала новое» для лент и для реестра
# событий. Импорт двойной по той же причине — рядом с артефактом пакета нет.
try:
    from factory.animedia import chronology as ХРОНОЛОГИЯ  # noqa: E402
except ImportError:
    try:
        import chronology as ХРОНОЛОГИЯ  # noqa: E402
    except ImportError:
        ХРОНОЛОГИЯ = None

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



#: Единый контракт карточки Animedia. Варианты различаются тем, что карточка
#: обязана показать, а не тем, как её раскрасили: иначе «похожее аниме» и
#: каталог расходятся молча, и один блок остаётся голыми постерами.
#:
#: Поля:
#:   бейджи    — счётчик серий слева сверху и оценки справа сверху, как у оригинала;
#:   название  — всегда: изображение без подписи карточкой не является;
#:   мета      — тип и год строкой под названием;
#:   оценок    — сколько источников показывать бейджами (0 — не показывать).
АНИМЕДИА_ВАРИАНТЫ_КАРТОЧКИ = {
    "catalog-title": {"бейджи": True, "название": True, "мета": True, "оценок": 2},
    "catalog":       {"бейджи": True, "название": True, "мета": True, "оценок": 2},
    "related":       {"бейджи": True, "название": True, "мета": True, "оценок": 2},
    "recommendation": {"бейджи": True, "название": True, "мета": True, "оценок": 2},
    "compact":       {"бейджи": False, "название": True, "мета": False, "оценок": 0},
    "top-shelf":     {"бейджи": False, "название": True, "мета": False, "оценок": 0},
    #: Лента первого экрана: у оригинала под постером только короткое белое
    #: название. Ни бейджей, ни строки «тип · год» там нет — они спорят с
    #: красной подложкой и превращают ленту в сетку каталога.
    "hero":          {"бейджи": False, "название": True, "мета": False, "оценок": 0},
    #: Нижний блок страницы произведения у оригинала — не сетка постеров, а
    #: строка: миниатюра слева, справа название, оригинальное название и
    #: оценка с числом голосов. Состав отличается, поэтому и вариант свой.
    #: Год и тип в строчной карточке — требование владельца: карточка без них
    #: заставляет уходить на страницу, чтобы понять, что это. У эталона этой
    #: строки нет, и это единственное место, где мы даём больше.
    "related-row":   {"бейджи": False, "название": True, "мета": True, "оценок": 1,
                      "строкой": True, "оригинальное": True, "голоса": True},
}
#: Вариант по умолчанию для неизвестного ключа. Fail loud вместо тихого
#: обеднения: неизвестный вариант получает полный набор, а не пустую карточку.
АНИМЕДИА_ВАРИАНТ_ПО_УМОЛЧАНИЮ = АНИМЕДИА_ВАРИАНТЫ_КАРТОЧКИ["catalog-title"]



#: Методика сводной оценки Animedia. Записана отдельно, потому что сводить
#: несколько источников в одно число без объявленного правила — значит выдать
#: собственную арифметику за чужую оценку.
#:
#: Правило:
#:   1. каждая оценка приводится к десятибалльной шкале по своей объявленной;
#:   2. вес источника — log10(голоса + 10): источник с десятками тысяч голосов
#:      весит больше случайной единичной оценки, но не подавляет остальные;
#:      если голоса не переданы, вес равен единице;
#:   3. сводная — взвешенное среднее, округлённое до десятых;
#:   4. один источник даёт сводную, равную ему самому: усреднять нечего;
#:   5. ни одного источника — сводной нет. Ноль сюда не подставляется.
#:
#: Сводная всегда подписана как наша и всегда показывает, из чего сложилась:
#: иначе посетитель примет её за оценку конкретного сайта.
#: Хранилище сообщества. Пишется витриной, поэтому лежит не в репозитории и не
#: в корне рантайма: и то и другое принадлежит другой учётной записи, а служба
#: работает под своей и создать там файл не может — проверено на живом хосте.
#: Каталог данных витрины (`/srv/lords/<сайт>/data`) — то же место, где держат
#: своё состояние соседние витрины флота.
#:
#: Каталога для Animedia пока нет, и создать его может только владелец:
#: родитель принадлежит служебной учётной записи. Пока его нет, раздел честно
#: выключен и называет причину — это состояние, а не поломка.
#: Выводится от корня рантайма, а не набирается руками: корень задаётся одной
#: переменной, и каталог данных обязан переезжать вместе с ним.
АНИМЕДИА_ДАННЫЕ_ВИТРИНЫ = Path(os.environ.get("ANIMEDIA_SITE_DATA_DIR")
                               or str(_КОРЕНЬ_РАНТАЙМА.parent / САЙТ_ID / "data"))
АНИМЕДИА_СООБЩЕСТВО_ПУТЬ = os.environ.get(
    "ANIMEDIA_COMMUNITY_STORE",
    str(АНИМЕДИА_ДАННЫЕ_ВИТРИНЫ / "animedia-community.json"),
)
_сообщество_хранилище = None


def сообщество():
    """Хранилище сообщества или None, если модуль не подключён.

    Витрина называется явно. Семейство границей данных не является:
    animedia.icu и animedia.space — разные публичные сайты, и хранилище,
    открытое без имени сайта, показало бы записи одного на другом. Модуль 2.0
    запоминает владельца файла и чужой не обслуживает.
    """
    global _сообщество_хранилище
    if _сообщество_хранилище is None and СООБЩЕСТВО is not None:
        _сообщество_хранилище = СООБЩЕСТВО.открыть(
            АНИМЕДИА_СООБЩЕСТВО_ПУТЬ, витрина=САЙТ_ID)
    return _сообщество_хранилище


#: Счётчик реальных запусков плеера. Лежит рядом со снимком каталога и
#: обновляется витриной; обработчик обновления читает его и, когда запусков
#: набирается достаточно, переводит «Популярное» на собственную статистику.
#:
#: Открытие страницы просмотром НЕ считается. Событие присылает сам плеер,
#: когда началось воспроизведение (`timeupdate`), — то есть когда зритель
#: действительно смотрит, а не когда страница отрисовалась.
АНИМЕДИА_ПРОСМОТРЫ_ПУТЬ = os.environ.get(
    "ANIMEDIA_VIEWS", str(_КОРЕНЬ_РАНТАЙМА / f"{САЙТ_ID}-views.json"))
_ПРОСМОТРЫ_ЗАМОК = threading.Lock()


def засчитать_просмотр(content_id: str, ключ_посетителя: str) -> bool:
    """Один запуск плеера. Повторы того же зрителя за сутки не считаются.

    Дедупликация нужна не ради точности статистики, а против самого дешёвого
    способа её накрутить: перезагрузить страницу сто раз. Ключ дедупликации —
    отпечаток «зритель + произведение + день», и хранится только сегодняшний
    набор: вчерашние отпечатки завтра не нужны, а неограниченный набор рос бы
    вечно.
    """
    content_id = str(content_id or "").strip()
    if not content_id:
        return False
    день = datetime.now(АНИМЕДИА_TZ).strftime("%Y-%m-%d")
    отпечаток = hashlib.sha256(
        f"{ключ_посетителя}|{content_id}|{день}".encode("utf-8")).hexdigest()[:16]
    путь = Path(АНИМЕДИА_ПРОСМОТРЫ_ПУТЬ)
    with _ПРОСМОТРЫ_ЗАМОК:
        try:
            данные = json.loads(путь.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            данные = {}
        if not isinstance(данные, dict):
            данные = {}
        if данные.get("day") != день:
            данные["day"] = день
            данные["seen"] = []
        видели = set(данные.get("seen") or [])
        if отпечаток in видели:
            return False
        видели.add(отпечаток)
        счёт = данные.get("by_content_id")
        if not isinstance(счёт, dict):
            счёт = {}
        счёт[content_id] = int(счёт.get(content_id) or 0) + 1
        данные.update({
            "schema_version": 1, "site_id": САЙТ_ID,
            "timezone": "Europe/Moscow",
            "semantics": "playback_started; страница, открытая без запуска, не считается",
            "updated_at": datetime.now(АНИМЕДИА_TZ).isoformat(timespec="seconds"),
            "seen": sorted(видели), "by_content_id": счёт,
        })
        врем = путь.with_suffix(путь.suffix + ".tmp")
        try:
            врем.write_text(json.dumps(данные, ensure_ascii=False), encoding="utf-8")
            os.replace(врем, путь)
        except OSError:
            врем.unlink(missing_ok=True)
            return False
    return True


#: Разрешённые источники стартовой оценки ЭТОЙ витрины, по порядку.
#: Берётся первый годный, а не наибольший: выбор «где больше» брал бы каждый
#: раз другой источник, и происхождение числа стало бы неназываемым. Оценка
#: самой витрины (`amd`) в списке отсутствует намеренно — иначе мнение наших
#: зрителей вошло бы в главный рейтинг дважды.
АНИМЕДИА_ПРИОРИТЕТ_БАЗЫ: tuple[str, ...] = ("shikimori", "kp", "imdb", "mal")


def внешние_для_базы(деталь: dict) -> dict:
    """Внешние оценки записи в том виде, в каком их ждёт модуль рейтинга.

    Значение и шкала передаются как есть: приведение к десятке — забота
    модуля, и делать его здесь во второй раз значило бы завести вторую
    методику. Оценка витрины отбрасывается: она не может быть базой.
    """
    итог: dict = {}
    for о in оценки_по_источникам(деталь):
        if о.get("пользовательская"):
            continue
        ключ = str(о.get("ключ") or "")
        if not ключ:
            continue
        итог[ключ] = {"value": о.get("значение"), "scale": о.get("шкала")}
    return итог


def тема_сообщества(подробности, slug: str) -> str:
    """Постоянный ключ темы обсуждения: `details[<slug>].id`.

    Ключом обсуждения служит идентификатор записи, а не её адрес. Адрес
    меняется — при переименовании тайтла голоса и сообщения осиротели бы, и
    ровно этот дефект на соседней витрине показывал «посетители ещё не
    голосовали» при живых голосах.

    Запасной вариант — сам slug: он же остаётся подсказкой для переноса
    записи под постоянный ключ, поэтому уже накопленное не теряется.
    """
    slug = str(slug or "").strip()
    if not slug:
        return ""
    try:
        деталь = подробности.get(slug) or {}
    except Exception:  # noqa: BLE001 — снимок подробностей может быть не готов
        деталь = {}
    return str(деталь.get("id") or "").strip() or slug


def сводная_оценка(деталь: dict) -> dict | None:
    """Взвешенная сводная по источникам или None, если источников нет."""
    оценки = оценки_по_источникам(деталь)
    if not оценки:
        return None
    import math

    сумма_весов = 0.0
    сумма = 0.0
    компоненты = []
    for о in оценки:
        try:
            шкала = float(о["шкала"])
            значение = float(str(о["значение"]).replace(",", "."))
        except (TypeError, ValueError):
            continue
        if шкала <= 0 or значение <= 0:
            continue
        на_десять = значение if abs(шкала - 10.0) < 0.01 else значение * 10.0 / шкала
        голоса = о.get("голоса") or 0
        вес = math.log10(голоса + 10) if голоса else 1.0
        сумма += на_десять * вес
        сумма_весов += вес
        компоненты.append({
            "ключ": о["ключ"], "подпись": о["подпись"],
            "значение": о["значение"], "шкала": о["шкала"],
            "на_десять": round(на_десять, 2), "голоса": голоса or None,
            "вес": round(вес, 3),
        })
    if not компоненты or сумма_весов <= 0:
        return None
    значение = round(сумма / сумма_весов, 1)
    return {
        "значение": f"{значение:g}",
        "источников": len(компоненты),
        "компоненты": компоненты,
        "методика": "weighted-log-votes/1.0",
        "всего_голосов": sum(к["голоса"] or 0 for к in компоненты) or None,
    }


def _счётчик_серий(деталь: dict) -> tuple[int, int] | None:
    """Сколько серий доступно из скольких заявлено.

    Считается по сезонам снимка: `avail` — то, к чему есть дорожка, `eps` —
    сколько объявлено. Ни одно из двух не выдумывается: нет сезонов или нет
    чисел — нет и счётчика.
    """
    сезоны = деталь.get("seasons")
    if not isinstance(сезоны, list) or not сезоны:
        return None
    доступно = заявлено = 0
    for с in сезоны:
        if not isinstance(с, dict):
            return None
        try:
            доступно += int(с.get("avail") or 0)
            заявлено += int(с.get("eps") or 0)
        except (TypeError, ValueError):
            return None
    if заявлено <= 0:
        return None
    return доступно, заявлено


#: Что видит посетитель вместо оценки, когда её ещё нет. Не ноль и не пустое
#: место: ноль — это утверждение о качестве, которого никто не делал, а пустота
#: ломает ряд карточек, потому что у соседних знак есть.
АНИМЕДИА_ОЦЕНКА_НЕТ = "—"


def фирменный_знак_оценки(деталь: dict, *, строкой: bool = False,
                          рейтинг: dict | None = None) -> str:
    """Одна оценка на карточке вместо набора чужих плашек.

    Раньше на постере висели подписи источников — IMDb, Кинопоиск, Shikimori —
    по две-три на карточку. В ряду из шести карточек это полтора десятка
    мелких надписей поверх постеров, и ни одна не отвечает на вопрос «стоит ли
    смотреть» быстрее, чем одно число.

    Число приходит готовым из модуля рейтинга: это ровно то же значение, что
    на странице произведения и в обсуждении. Считать его здесь ещё раз значило
    бы завести вторую методику, и рано или поздно соседние экраны показали бы
    разные числа про одно кино.

    Когда модуль недоступен или у записи нет ни базы, ни голосов, знак
    остаётся на месте и показывает прочерк: пустота ломает ряд карточек, а
    ноль был бы утверждением о качестве, которого никто не делал.
    """
    класс = "zt__score" + (" zt__score--row" if строкой else "")
    состояние = str((рейтинг or {}).get("состояние") or "empty")
    значение = (рейтинг or {}).get("значение")
    if значение is None:
        return (f'<span class="{класс} zt__score--none" data-score-state="none" '
                f'data-score-kind="none" '
                f'title="Оценка появится, когда придут данные">'
                f'<b aria-hidden="true">{АНИМЕДИА_ОЦЕНКА_НЕТ}</b>'
                f'<span class="vh">Оценка пока неизвестна</span></span>')
    голосов = int((рейтинг or {}).get("голосов") or 0)
    показ = f"{float(значение):g}"
    подсказка = f"Рейтинг {показ} из 10"
    if голосов:
        подсказка += f" · {голосов} {склонение_голосов(голосов)} зрителей"
    вид = "viewers" if состояние == "votes-only" else "main"
    return (f'<span class="{класс}" data-score-state="value" '
            f'data-score-kind="{вид}" '
            f'data-score="{html.escape(показ)}" '
            f'data-score-formula="{html.escape(str((рейтинг or {}).get("формула") or ""))}" '
            + (f'data-score-votes="{голосов}" ' if голосов else "")
            + f'title="{html.escape(подсказка)}">'
              f'<b aria-hidden="true">{html.escape(показ)}</b>'
              f'<span class="vh">{html.escape(подсказка)}</span></span>')


def _оценки_для_карточки(деталь: dict, сколько: int) -> list:
    """Оценки для бейджей: приведены к десятибалльной шкале, источник назван.

    Исходное значение и исходная шкала остаются в данных карточки: приведение
    нужно глазу, а не хранилищу. Ноль, пустое и неизвестное не показываются
    вовсе — «нет оценки» и «оценка ноль» разные утверждения.
    """
    if сколько <= 0:
        return []
    готово = []
    for о in оценки_по_источникам(деталь)[:сколько]:
        try:
            шкала = float(о["шкала"])
            значение = float(str(о["значение"]).replace(",", "."))
        except (TypeError, ValueError):
            continue
        if шкала <= 0 or значение <= 0:
            continue
        на_десять = значение if abs(шкала - 10.0) < 0.01 else значение * 10.0 / шкала
        готово.append({**о, "на_десять": f"{на_десять:.1f}".rstrip("0").rstrip("."),
                       "исходное": о["значение"], "исходная_шкала": о["шкала"]})
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
# Механически переносить базу на аниме и кинопорталы нельзя: у них разные
# разделы, разный словарь и разный ритм витрины. Здесь различается палитра,
# навигация и состав секций главной; общей остаётся только механика.
ПРОФИЛИ_СЕМЕЙСТВ = {
    "animedia": {
        "acc": "#4d7cff", "acc2": "#a78bfa", "bg": "#0a0d18", "card": "#141828",
        "nav": [("/", "Главная"), ("/catalog/", "Каталог"), ("/new/", "Новое в каталоге"),
                ("/collections/", "Подборки"), ("/schedule/", "Расписание")],
        "secs": [("Новое в каталоге", "/new/", None), ("Онгоинги", "/catalog/", None),
                 ("Подборки", "/collections/", None)],
        "hero_btn": "Начать просмотр", "search_ph": "Поиск аниме и дорам",
    },
}
_П = ПРОФИЛИ_СЕМЕЙСТВ["animedia"]


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
 var k='animedia-theme',r=document.documentElement;
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


#: Значки реакций рисуются разметкой, а не знаками шрифта.
#:
#: Текстовые подписи «огонь», «сердце», «смех» посетитель читал как набор слов,
#: а замена их на emoji означала бы зависимость от системного шрифта:
#: недостающий знак браузер рисует коробкой с шестнадцатеричным кодом — ровно
#: так на этой витрине уже появлялся мусор «Подробнее ВЕ». Поэтому здесь
#: собственные контуры: они выглядят одинаково на любой машине и не зависят ни
#: от шрифта, ни от внешнего файла.
#:
#: Стиль у всех пяти один: круг-подложка своего цвета, поверх — простые черты
#: лица или фигура. Разнобой рисунков («один контурный, другой залитый»)
#: читается как случайный набор, а не как ряд одного смысла.
#:
#: Название реакции никуда не делось: оно в `title`, в скрытом тексте и в
#: `aria-label`. Значок без имени нельзя ни прочитать вслух, ни понять
#: однозначно — «грусть» и «вау» отличаются одной дугой.
ЛИЦО_ГЛАЗА = ('<circle cx="9" cy="10.4" r="1.35" fill="#2b2118"/>'
              '<circle cx="15" cy="10.4" r="1.35" fill="#2b2118"/>')
ЗНАЧКИ_РЕАКЦИЙ: dict[str, str] = {
    "огонь": (
        '<path d="M12 2.4c.5 3.1-1.1 4.4-2.6 5.8C7.7 9.8 6 11.5 6 14.3a6 6 0 0 0 12 0'
        'c0-2.4-1-4-2.3-5.4-.5 1-1.2 1.5-2 1.8.6-3.4-.8-6.5-1.7-8.3Z" fill="#ff6b1a"/>'
        '<path d="M12 21.2a3.2 3.2 0 0 1-3.2-3.2c0-1.7 1.4-2.7 2.1-3.9.5 .9 1.3 1.3 2 1.7'
        '.8-.5 1.2-1.1 1.2-2 .7 1 1.1 2.1 1.1 3.2a3.2 3.2 0 0 1-3.2 3.2Z" fill="#ffd23f"/>'),
    "сердце": (
        '<path d="M12 20.6 4.4 13a4.7 4.7 0 0 1 0-6.7 4.7 4.7 0 0 1 6.7 0l.9 .9 .9-.9'
        'a4.7 4.7 0 0 1 6.7 0 4.7 4.7 0 0 1 0 6.7Z" fill="#e8174a"/>'
        '<path d="M7.4 7.2c-1 .6-1.5 1.7-1.3 2.8.5-1 1.3-1.8 2.4-2.2.5-.2.6-.9 .1-1'
        '-.4-.1-.8 0-1.2 .4Z" fill="#ff7a9c"/>'),
    "смех": (
        '<circle cx="12" cy="12" r="9.4" fill="#ffc83d"/>'
        '<path d="M6.9 13.4h10.2a5.1 5.1 0 0 1-10.2 0Z" fill="#7a3b18"/>'
        '<path d="M8.6 18.2a5.1 5.1 0 0 0 6.8 0 4 4 0 0 0-6.8 0Z" fill="#ff5c7a"/>'
        '<path d="M6.9 9.5c.8-1.1 2.4-1.1 3.2 0M13.9 9.5c.8-1.1 2.4-1.1 3.2 0" '
        'fill="none" stroke="#2b2118" stroke-width="1.7" stroke-linecap="round"/>'),
    "грусть": (
        '<circle cx="12" cy="12" r="9.4" fill="#8fbcff"/>'
        + ЛИЦО_ГЛАЗА +
        '<path d="M8.4 16.8a4.6 4.6 0 0 1 7.2 0" fill="none" stroke="#2b2118" '
        'stroke-width="1.7" stroke-linecap="round"/>'
        '<path d="M16.6 12.2c.8 1.4 1.2 2.3 1.2 3a1.2 1.2 0 0 1-2.4 0'
        'c0-.7 .4-1.6 1.2-3Z" fill="#2f7ae5"/>'),
    "вау": (
        '<circle cx="12" cy="12" r="9.4" fill="#ffc83d"/>'
        '<circle cx="8.9" cy="9.9" r="1.45" fill="#2b2118"/>'
        '<circle cx="15.1" cy="9.9" r="1.45" fill="#2b2118"/>'
        '<ellipse cx="12" cy="15.6" rx="2.4" ry="3" fill="#7a3b18"/>'),
}


#: Смайлики формы сообщения. Хранятся кодовыми точками, а не знаками: так
#: исходник остаётся читаемым в любом редакторе и в отчётах, а на странице
#: получается обычный текст.
#:
#: Это именно ТЕКСТ сообщения, а не реакция. Реакции рисуются своими цветными
#: контурами и от шрифта не зависят; вставленный в сообщение знак — часть
#: пользовательского текста и экранируется на выводе наравне со всем остальным.
СМАЙЛИКИ: tuple[tuple[str, str], ...] = tuple(
    (chr(код), имя) for код, имя in (
        (0x1F642, "улыбка"), (0x1F600, "радость"), (0x1F602, "смех"),
        (0x1F60D, "восторг"), (0x1F609, "подмигивание"), (0x1F914, "раздумье"),
        (0x1F62E, "удивление"), (0x1F622, "грусть"), (0x1F621, "злость"),
        (0x1F44D, "палец вверх"), (0x1F44E, "палец вниз"), (0x1F525, "огонь"),
        (0x2764, "сердце"), (0x1F44F, "аплодисменты"), (0x1F389, "праздник"),
        (0x1F440, "смотрю"),
    )
)


#: Палитра аватаров. Цвет выбирается по имени автора и потому постоянен: один
#: и тот же гость в ленте всегда одного цвета, и глаз отличает собеседников,
#: не перечитывая подписи. Внешних картинок здесь нет и не будет — аватар по
#: чужому адресу означал бы, что каждый читатель ленты объявляет себя чужому
#: серверу.
ЦВЕТА_АВАТАРА = ("#e8174a", "#2f7ae5", "#1a9c5b", "#b5561f", "#7a4bd0",
                 "#0f8f9e", "#c2185b", "#5a6f8a")


def аватар(имя: str) -> str:
    """Кружок с первой буквой имени. Цвет постоянен для одного имени."""
    имя = (имя or "").strip() or "Гость"
    первая = html.escape(имя[:1].upper())
    цвет = ЦВЕТА_АВАТАРА[
        int(hashlib.sha256(имя.casefold().encode("utf-8")).hexdigest(), 16)
        % len(ЦВЕТА_АВАТАРА)]
    return (f'<span class="acomm__ava" style="background:{цвет}" aria-hidden="true">'
            f'{первая}</span>')


def значок_реакции(имя: str) -> str:
    """Контур реакции. Неизвестное имя даёт пустую строку, а не крестик."""
    путь = ЗНАЧКИ_РЕАКЦИЙ.get(имя)
    if not путь:
        return ""
    return (f'<svg class="areact__i" viewBox="0 0 24 24" width="22" height="22" '
            f'aria-hidden="true" focusable="false">{путь}</svg>')


#: Контур звезды. Одна фигура на все состояния: пустая, наведённая и
#: сохранённая различаются цветом, а не разной геометрией.
ЗВЕЗДА_ПУТЬ = ("M12 3.2l2.62 5.31 5.86.85-4.24 4.13 1 5.84L12 16.6l-5.24 2.76"
               " 1-5.84L3.52 9.36l5.86-.85Z")


def звезда_svg(класс: str = "astar__i") -> str:
    return (f'<svg class="{класс}" viewBox="0 0 24 24" width="22" height="22" '
            f'aria-hidden="true" focusable="false"><path d="{ЗВЕЗДА_ПУТЬ}"/></svg>')


def склонение_голосов(n: int) -> str:
    """«1 голос», «2 голоса», «5 голосов». Число рядом с оценкой читают вслух."""
    n = abs(int(n))
    if 11 <= n % 100 <= 14:
        return "голосов"
    остаток = n % 10
    if остаток == 1:
        return "голос"
    if 2 <= остаток <= 4:
        return "голоса"
    return "голосов"


def склонение_записей(n: int) -> str:
    """«1 запись», «2 записи», «5 записей» — подпись счётчика рядом с числом.

    Не украшение: счётчики стоят в хабах жанров и типов по несколько десятков
    на страницу, и несогласованное число там заметнее любого огреха вёрстки.
    """
    n = abs(int(n))
    если_сотня = n % 100
    if 11 <= если_сотня <= 14:
        return "записей"
    последняя = n % 10
    if последняя == 1:
        return "запись"
    if 2 <= последняя <= 4:
        return "записи"
    return "записей"


#: Четыре цифры в хвосте формы — год из названия. Выражение собрано один раз:
#: в мягком сравнении оно вызывается миллионами.
_ХВОСТ_ГОДА = re.compile(r"\d{4}$")


def _мягкое_совпадение(цель: str, форма: str) -> bool:
    """Нестрогий матч без ложных соседей вроде matrix→maori.

    Прежний критерий (длина ±допуск + Hamming по zip) принимал «matrix»≈«maori».
    Теперь: длина ≥5, общий префикс ≥4, SequenceMatcher.ratio ≥ 0.75.
    «matrix»↔«matrica» проходит; «matrix»↔«maori» — нет.

    У форм с годом в хвосте (`matrica1999` из «Матрица (1999)») дополнительно
    сравниваем обрезанный вариант без четырёх цифр на конце, иначе латиница
    не находила живые тайтлы Матрицы на боевом снимке.

    Порядок проверок — от дешёвых к дорогим, и это не вкусовщина. Функция
    вызывается больше миллиона раз на один запрос без совпадений; когда
    обрезка года и разбор регулярного выражения шли первыми, один запрос
    занимал секунды. Общий префикс отсекает почти всё и стоит одно сравнение,
    а обрезка года префикс не меняет — значит, её можно отложить.
    """
    if len(цель) < 5 or len(форма) < 5:
        return False
    if цель[:4] != форма[:4]:
        return False
    кандидаты = [форма]
    без_года = _ХВОСТ_ГОДА.sub("", форма)
    if без_года != форма and len(без_года) >= 5:
        кандидаты.append(без_года)
    for ф in кандидаты:
        if abs(len(цель) - len(ф)) > 2:
            continue
        if SequenceMatcher(None, цель, ф).ratio() >= 0.75:
            return True
    return False


def из_раскладки(с: str) -> str:
    """Строка, набранная латинскими клавишами вместо русских."""
    return (с or "").translate(_РАСКЛАДКА)


def закодировать_запрос(url: str) -> str:
    """Percent-encode query values in an already-built path (?kind=Фильм).

    Якорь отрезается до разбора и возвращается на место. Без этого
    «/?genre=boevik#catalog» разбирался как жанр «boevik#catalog» — ссылка
    фильтра вела в пустую выдачу ровно там, где к сетке добавили якорь.
    """
    url = url or ""
    url, решётка, якорь = url.partition("#")
    хвост_якоря = (решётка + якорь) if решётка else ""
    if "?" not in url:
        return url + хвост_якоря
    путь, _, хвост = url.partition("?")
    пары = parse_qsl(хвост, keep_blank_values=True)
    return путь + (("?" + urlencode(пары, quote_via=quote)) if пары else "") + хвост_якоря


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
    def сбросить(cls) -> None:
        """Забыть прежний снимок: на диске появился новый каталог."""
        cls._снимок = None

    @classmethod
    def получить(cls, данные, подробности):
        if cls._снимок is None and КОЛЛЕКЦИИ is not None:
            cls._снимок = КОЛЛЕКЦИИ.Снимок(
                данные.items, getattr(подробности, "записи", None) or {},
                revision=getattr(данные, "revision", "") or "")
        return cls._снимок


#: Слова короче этого в отдельный указатель не попадают: «на», «и», «the»
#: совпадают почти со всем и только портят выдачу.
ДЛИНА_СЛОВА_УКАЗАТЕЛЯ = 3


def _написания(запись: dict) -> list[str]:
    """Все известные написания названия одной записи, склеенными формами.

    Русское название, оригинальное, синонимы владельца, slug и транслит.
    Пустых среди них нет — сравнивать с пустой строкой значило бы совпадать
    со всем подряд. Без slug/транслита запрос «matrix» / «naruto» / точный
    slug живого `/title/{slug}/` давал пустую выдачу при живой карточке.
    """
    формы = [нормализовать(запись.get("title") or "")]
    if запись.get("slug"):
        формы.append(нормализовать(запись["slug"]))
    if запись.get("title"):
        формы.append(нормализовать(транслит(запись["title"])))
    for поле in ("original_title", "original_name"):
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
    return увидели


def _слова_записи(запись: dict) -> set[str]:
    """Отдельные слова названий — то, чего не даёт склеенная форма.

    `нормализовать` выбрасывает дефисы и пробелы, поэтому slug
    «cvetuschaya-zvezda-parizha» превращался в одно слово, и запрос
    «cvetuschaya» не совпадал с ним ни точно, ни префиксом. Слова хранятся
    отдельно от склеенных форм намеренно: фразовое совпадение остаётся
    фразовым, а совпадение одного слова не поднимается до верхнего уровня.
    """
    слова: set[str] = set()
    источники = [запись.get("title") or "", (запись.get("slug") or "").replace("-", " ")]
    for поле in ("original_title", "original_name"):
        if запись.get(поле):
            источники.append(str(запись[поле]))
    источники.extend(str(д) for д in (запись.get("aliases") or []))
    for источник in источники:
        for слово in токены(источник):
            for вариант in (нормализовать(слово), нормализовать(транслит(слово))):
                if len(вариант) >= ДЛИНА_СЛОВА_УКАЗАТЕЛЯ:
                    слова.add(вариант)
    return слова


class Данные:
    def __init__(self, путь: str):
        сырое = json.loads(Path(путь).read_text(encoding="utf-8"))
        self.items = сырое["items"]
        self.absent = сырое.get("fields_absent", [])
        self.revision = str(сырое.get("revision") or "")
        self.built_at = str(сырое.get("builtAt") or сырое.get("built_at") or "")
        self.оригинальных_названий = 0
        for з in self.items:
            з["_n"] = нормализовать(з["title"])
            з["_формы"] = _написания(з)
            з["_слова"] = _слова_записи(з)
        self.years = sorted({з["year"] for з in self.items if з["year"]}, reverse=True)
        self.kinds = sorted({з["kind"] for з in self.items if з["kind"]})

    def обогатить_подробностями(self, подробности) -> int:
        """Достроить поисковый указатель оригинальными названиями.

        Снимок каталога несёт только русское название: `original_name` лежит
        в боковом файле подробностей. Поэтому обещание формы поиска («ищем по
        русскому и оригинальному написанию») до этого было неправдой — запрос
        «naruto» не находил «Наруто», хотя оригинальное написание у записи
        есть. Здесь оно добавляется в указатель из настоящих данных; там, где
        подробностей нет, не добавляется ничего.

        Возвращает число записей, которым нашлось оригинальное написание.
        """
        записи = getattr(подробности, "записи", None) or {}
        if not записи:
            self.оригинальных_названий = 0
            return 0
        учтено = 0
        for з in self.items:
            деталь = записи.get(з.get("slug")) or {}
            # Заодно раскладываются две величины, которые иначе пришлось бы
            # считать на каждый запрос по всему каталогу: сводная оценка и
            # признак незавершённости. Сортировка «по оценке» до этого
            # обращалась к полю `_rating`, которое никто не заполнял, и
            # честно расставляла семь тысяч записей по нулю.
            свод = сводная_оценка(деталь)
            try:
                з["_rating"] = float(str(свод["значение"]).replace(",", ".")) if свод else 0.0
            except (TypeError, ValueError):
                з["_rating"] = 0.0
            з["_votes"] = int((свод or {}).get("всего_голосов") or 0)
            доступно = заявлено = 0
            for с in (деталь.get("seasons") or []):
                if isinstance(с, dict):
                    доступно += int(с.get("avail") or 0)
                    заявлено += int(с.get("eps") or 0)
            з["_avail"], з["_eps"] = доступно, заявлено
            з["_ongoing"] = 1 if (заявлено and 0 < доступно < заявлено) else 0
            # Постоянный идентификатор записи живёт в подробностях, а нужен он
            # в каталоге: по нему связываются снимок популярности, реестр
            # серий и расписание. Без этого снимок, собранный по постоянным
            # ключам, не сопоставлялся с каталогом вовсе — ноль позиций при
            # восьми найденных.
            ид = str(деталь.get("id") or "").strip()
            if ид:
                з["id"] = ид
            оригинал = str(деталь.get("original_name") or "").strip()
            if not оригинал or оригинал == (з.get("title") or ""):
                continue
            з["original_name"] = оригинал
            з["_формы"] = _написания(з)
            з["_слова"] = _слова_записи(з)
            учтено += 1
        self.оригинальных_названий = учтено
        return учтено

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

        Прочтения запроса считаются по отдельности. Раньше строка «как есть» и
        строка «прочитанная в другой раскладке» сваливались в один набор
        токенов, и правило AND требовало совпадения с обоими сразу. Для любого
        латинского слова второе прочтение — бессмысленный набор букв
        («naruto» → «тфкгещ»), поэтому ни один запрос латиницей не мог найти
        ничего: выдача была пустой не из-за данных, а из-за самого правила.
        """
        прочтения: list[tuple[str, list[str]]] = []
        for сырой in (q, из_раскладки(q)):
            нq = нормализовать(сырой)
            ткн: list[str] = []
            for т in токены(сырой):
                if т in СЛУЖЕБНЫЕ or т.isdigit():
                    continue
                нт = нормализовать(т)
                if нт and len(нт) >= 2 and нт not in ткн:
                    ткн.append(нт)
            if (нq or ткн) and (нq, ткн) not in прочтения:
                прочтения.append((нq, ткн))
        if not прочтения:
            return []
        разобранные = [(нq, ткн, [т for т in ткн if len(т) >= 3],
                        len([т for т in ткн if len(т) >= 3]) >= 2)
                       for нq, ткн in прочтения]

        def токен_в_формах(т: str, формы: list[str], слова: set) -> str | None:
            if т in формы or т in слова:
                return "exact"
            if any(ф.startswith(т) for ф in формы) or any(с.startswith(т) for с in слова):
                return "prefix"
            if any(т in ф for ф in формы):
                return "sub"
            return None

        def оценить(формы: list[str], слова: set, прочтение: tuple) -> int:
            """Вес записи для одного прочтения запроса.

            Разобранное прочтение приходит готовым: перебор идёт по тысячам
            записей, и пересобирать один и тот же список токенов на каждой из
            них — это вся стоимость запроса, потраченная впустую.
            """
            нq, токены_запроса, знач_токены, многословный = прочтение
            score = 0
            # 1) full-phrase exact
            if нq and нq in формы:
                score = 1000
            # 2) multi-token AND
            if score < 1000 and знач_токены:
                kinds = [токен_в_формах(т, формы, слова) for т in знач_токены]
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
                        k = токен_в_формах(т, формы, слова)
                        if k == "exact":
                            score = max(score, 600)
                        elif k == "prefix":
                            score = max(score, 400)
                        elif k == "sub":
                            score = max(score, 300)
            elif score < 1000 and not многословный:
                for т in токены_запроса:
                    k = токен_в_формах(т, формы, слова)
                    if k == "exact":
                        score = max(score, 600)
                    elif k == "prefix":
                        score = max(score, 400)
                    elif k == "sub":
                        score = max(score, 300)
            # 3) soft only if still unmatched and short query
            #
            # Опечатка в одном слове длинного названия не ловилась: склеенная
            # форма «цветущаязвездапарижа» отличается от «цветущаяя» длиной
            # больше допуска, и запрос давал честную, но бесполезную пустоту.
            # Поэтому опечатка сравнивается и с отдельными словами тоже.
            if score == 0 and not многословный:
                for цель in ([нq] if нq else []) + токены_запроса:
                    if any(_мягкое_совпадение(цель, ф) for ф in формы):
                        score = 100
                        break
                    if any(_мягкое_совпадение(цель, с) for с in слова):
                        score = 80
                        break
            if score == 0 and многословный:
                soft_hits = sum(
                    1 for т in знач_токены
                    if токен_в_формах(т, формы, слова)
                    or any(_мягкое_совпадение(т, ф) for ф in формы[:3])
                )
                if soft_hits == len(знач_токены):
                    score = 150
            return score

        scored: list[tuple[int, str, dict]] = []
        for з in self.items:
            формы = з["_формы"]
            if not формы:
                continue
            слова = з.get("_слова") or set()
            # Лучшее из прочтений, а не пересечение: неверная раскладка —
            # это другая версия того же запроса, а не дополнительное условие.
            score = max(оценить(формы, слова, п) for п in разобранные)
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
# 1. Снимок каталога уходит вперёд релиза. У соседней витрины в снимке 3868 записей, а
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

#: Версия оформления базу и Animedia, переработанных по измеренным эталонам
#: (TEMPLATES-ZONA-ANIMEDIA-VISUAL-PARITY-006). базу остаётся на 1.1.0 и
#: поэтому отдаёт прежние байты: его ветка кода не меняется вовсе.
ОФОРМЛЕНИЕ_1_2 = "1.2.0"
ОФОРМЛЕНИЕ_1_2_1 = "1.2.1"
ОФОРМЛЕНИЕ_1_2_2 = "1.2.2"
ОФОРМЛЕНИЕ_1_2_3 = "1.2.3"
ОФОРМЛЕНИЕ_1_2_4 = "1.2.4"

#: ANIMEDIA-TEMPLATE-FIX-01: принятые владельцем правки animedia.space,
#: перенесённые в шаблон семейства. Отдельный номер нужен потому, что версия
#: обязана называть оформление: под 1.2.4 уже выпущено ПРЕЖНЕЕ расположение
#: — двухколоночная коробка оценок под всеми блоками, реакции-таблетки в её
#: углу, вторая шкала голосования в боковой колонке. Оставить тот же номер
#: значило бы, что по манифесту витрины больше нельзя сказать, что она
#: показывает.
ОФОРМЛЕНИЕ_1_2_5 = "1.2.5"

#: ANIMEDIA-EPISODE-FRESHNESS-01: заявленная, но недоступная серия больше не
#: ссылка. Под 1.2.5 такая ссылка была достижима клавиатурой, читалкой и
#: прямым адресом, хотя мышью не нажималась.
ОФОРМЛЕНИЕ_1_2_6 = "1.2.6"

#: ANIMEDIA-EPISODE-FEED-01: в ленте «Новые серии» один тайтл — одна карточка.
#: Под 1.2.6 массовый добор серий одного сериала занимал всю первую страницу
#: его же карточками.
ОФОРМЛЕНИЕ_1_2_7 = "1.2.7"

#: Версии, несущие оформление 1.1+. Набор, а не одно значение: витрина
#: включает оформление СВОИМ манифестом, и добавление следующей версии не
#: должно переводить на неё соседей. Свойство «переход по одной витрине»
#: сохраняется — меняется только то, сколько версий код умеет исполнять.
ОФОРМЛЕНИЕ_ВЕРСИИ = {ОФОРМЛЕНИЕ_1_1, ОФОРМЛЕНИЕ_1_2, ОФОРМЛЕНИЕ_1_2_1, ОФОРМЛЕНИЕ_1_2_2, ОФОРМЛЕНИЕ_1_2_3, ОФОРМЛЕНИЕ_1_2_4, ОФОРМЛЕНИЕ_1_2_5, ОФОРМЛЕНИЕ_1_2_6, ОФОРМЛЕНИЕ_1_2_7}

#: Семейства, переработанные по измеренным эталонам, и версии, с которых
#: переработка включается. Ниже этого набора витрина исполняет прежние ветки.
#:
#: Проверка нужна потому, что артефакт ОДИН на шесть витрин. Без неё выкладка
#: артефакта ради Animedia сменила бы оформление боевой базу, которая стоит на
#: 1.1.0 и о смене не просила, — то есть ровно то, что запрещает принцип
#: «переход делается по одной витрине». Здесь оформление 1.2.x достаётся
#: только той витрине, чей манифест его объявил.
ПЕРЕРАБОТАНО_С = {
    "animedia": frozenset({ОФОРМЛЕНИЕ_1_2, ОФОРМЛЕНИЕ_1_2_1, ОФОРМЛЕНИЕ_1_2_2, ОФОРМЛЕНИЕ_1_2_3, ОФОРМЛЕНИЕ_1_2_4, ОФОРМЛЕНИЕ_1_2_5, ОФОРМЛЕНИЕ_1_2_6, ОФОРМЛЕНИЕ_1_2_7}),
}

#: Исполняет ли ЭТА витрина переработанное оформление своего семейства.
ОФОРМЛЕНИЕ_ПЕРЕРАБОТАННОЕ = ВЕРСИЯ in ПЕРЕРАБОТАНО_С.get(СЕМЕЙСТВО, ())

#: Включено ли новое оформление на ЭТОЙ витрине. Решает манифест витрины, а не
#: наличие кода: один артефакт обслуживает шесть витрин, и переход делается по
#: одной. Витрина на 1.0.2 исполняет прежние ветки и отдаёт прежние байты.
ОФОРМЛЕНИЕ_НОВОЕ = (ВЕРСИЯ in ОФОРМЛЕНИЕ_ВЕРСИИ)

#: Сколько карточек на странице каталога в новом оформлении. Кратно и шести
#: (сетка базу), и четырём (сетка базу), поэтому последний ряд не рваный.
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
#   базу — узкий светлый лист на тёмной подложке, плотная сетка в шесть
#           колонок, название поверх постера, оценки полосой под постером,
#           шапка в одну строку, страница тайтла: постер слева, сюжет справа,
#           затем таблица фактов в две колонки.
#
#   базу  — постоянная боковая колонка слева и содержимое во всю оставшуюся
#           ширину, крупная шрифтовая пара с засечками в заголовках, карточки
#           списком-строкой с постером слева, шапка в два ряда, страница
#           тайтла: широкий баннер, постер внахлёст, полоса оценок, затем
#           основной текст и колонка фактов справа.
#
# Тему пользователь больше не переключает, и это решение, а не упущение.
# Переключатель существовал, светлая ветка задавала только часть переменных, и
# именно из неё выходил нечитаемый текст. Одна объявленная палитра на
# семейство закрывает целый класс дефектов наследования.




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







АНИМЕДИА_СТИЛЬ = """
/* Animedia 1.2.4 — blockwise: shell/header/theme (BLOCK_01) + shelves. */
:root{
  /* Оболочка по оригиналу. Измерено на снимке 20.09: шапка оригинала имеет
     ширину 1420 и на 1440, и на 1920 — внешняя рамка ограничена и на широком
     экране не растягивается; ширина содержимого около 1272 при окне 1363, то
     есть боковые поля внутри рамки около 40. Прежние 1760 разворачивали сетку
     до десяти колонок там, где у оригинала их семь. */
  --a-shell-max:1420px;
  --a-content-max:1340px;
  --page-gutters:80px;
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
/* Базовый кегль оригинала — 14px при плотной типографике (наблюдение источника
   эталона, CR v2.0 §3). Прежние 16px растягивали каждую строку и вместе с
   широким контейнером давали витрину на треть «крупнее» оригинала. */
body{background:var(--a-page);color:var(--a-ink);
font:14px/1.5 ui-sans-serif,system-ui,'Segoe UI',Roboto,Arial,sans-serif}
@media(prefers-reduced-motion:reduce){
  *,*::before,*::after{animation-duration:.01ms !important;animation-iteration-count:1 !important;
  transition-duration:.01ms !important;scroll-behavior:auto !important}
}
.zs{min-height:100vh;display:block}
.zmain{min-width:0}
.zwrap,.zhd__in,.zft__inner{
  width:min(var(--a-content-max),calc(100% - var(--page-gutters)));
  margin-inline:auto;padding-inline:0;box-sizing:border-box}
/* Вложенная обёртка не применяет поля второй раз. Измерено: страница каталога
   была 1260 вместо 1340 и карточка 152 вместо 163 — ровно на двойной боковой
   отступ уже остальных страниц, потому что `.zwrap` оказывалась внутри
   `.zwrap`. */
.zwrap .zwrap{width:100%;max-width:none;margin-inline:0}
.zwrap{padding-block:0}
/* Шапка оригинала — не во всю ширину окна: это ограниченная рамка, и её нижняя
   линия обрывается вместе с ней. Высота измерена: 90 на 768 и шире, 126 на
   телефоне, где шапка складывается в две строки — поиск уходит на свою. */
.zhd{position:relative;background:var(--a-rail);border-bottom:1px solid var(--a-line);z-index:30;
width:100%;margin-inline:auto}
/* Рамка ограничена только на широком экране: у оригинала шапка занимает всю
   ширину на 390 и на 768 и ровно 1420 на 1440 и на 1920. */
@media(min-width:1024px){
  .zhd{width:min(var(--a-shell-max),calc(100% - 20px))}
}
/* 89 + 1px нижней линии = измеренные 90. Считать высоту без линии значило бы
   ошибаться на пиксель на каждом маршруте. */
.zhd__in{display:flex;align-items:center;gap:12px;flex-wrap:nowrap;height:89px;min-height:89px;
max-height:89px;padding-block:0}
@media(max-width:1023px){
  .zhd__in{height:89px;min-height:89px;max-height:89px;flex-wrap:nowrap;gap:8px;padding-block:0}
}
@media(max-width:767px){
  .zhd__in{height:auto;min-height:125px;max-height:none;flex-wrap:wrap;align-content:center;
  gap:8px;row-gap:10px;padding-block:12px}
  .zhd__s{flex:1 0 100%;order:3;max-width:none}
  .zhd__actions{order:2;margin-left:auto}
}
.zhd__logo{font-size:22px;font-weight:800;letter-spacing:-.4px;color:var(--a-ink);flex:0 0 auto;
line-height:1;min-height:44px;min-width:120px;max-width:155px;width:max-content;
display:inline-flex;align-items:center}
.zhd__logo b{color:var(--a-acc)}
/* Меню шапки. Оно одно.
   Прежде рядом с ним стояла вторая навигация — «Жанр / Тип / Списки / Ещё», —
   и обе были `nowrap` при `flex-wrap:nowrap` у строки. Строка ужимала их
   боксы, а текст внутри ужиматься не умел и вылезал наружу: на 1363 читалось
   «Жанры Типы ЖАНРЫ ТИПЫ Списки ТОП СПИСКИ ЕЩЁ», и поверх этого налезало поле
   поиска. Второй ряд кнопок убран из шапки целиком; его содержимое никуда не
   делось — оно в ящике меню, на страницах «Жанры» и «Типы» и в фильтре
   каталога, который теперь стоит над сеткой.
   Порог показа поднят до 1200: на 1100 девять пунктов, логотип, поиск и две
   кнопки в строку не помещались даже без второй навигации. Ниже порога
   работает кнопка ящика. */
.zhd__n{display:none;align-items:center;gap:2px;flex:0 1 auto;min-width:0;overflow:hidden}
@media(min-width:1200px){.zhd__n{display:flex}}
.zhd__n a{padding:8px 9px;border-radius:8px;font-size:13px;font-weight:700;color:var(--a-ink);
text-decoration:none;min-height:44px;display:inline-flex;align-items:center;white-space:nowrap}
.zhd__n a:hover{color:var(--a-acc);background:var(--a-alt)}
.zhd__n a[aria-current]{color:var(--a-acc);box-shadow:inset 0 -2px 0 var(--a-acc)}
/* Таксономия осталась только в ящике меню: в строке шапки её больше нет. */
.zhd__tax{display:none}
.zhd__drawer .zhd__tax{display:flex}
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
@media(min-width:1200px){.zhd__menu{display:none}}
.zhd__theme{display:inline-flex;align-items:center;justify-content:center;width:44px;height:44px;
min-width:44px;min-height:44px;flex:0 0 44px;border:1px solid var(--a-line);border-radius:8px;
background:var(--a-page);color:var(--a-ink);font-size:16px;cursor:pointer}
.zhd__theme:focus-visible,.zhd__menu:focus-visible,.zhd__s button:focus-visible,.zhd__drawer a:focus-visible,
.zhd__drawer-x:focus-visible,.zhd__n a:focus-visible{outline:2px solid var(--a-acc);outline-offset:2px}
/* Поиск в шапке — компактный. Он умеет сжиматься (min-width заметно меньше
   основной ширины), поэтому строка шапки ужимает поле, а не наезжает на меню. */
.zhd__s{display:flex;flex:0 1 280px;min-width:190px;max-width:320px;height:44px;border:1px solid var(--a-line);
border-radius:999px;overflow:hidden;background:var(--a-page);align-items:stretch}
@media(max-width:1199px){
  .zhd__s{flex:1 1 calc(100% - 108px);min-width:120px;max-width:none;order:0;border-radius:10px;height:44px}
  .zhd__actions{order:0}
}
.zhd__s input{flex:1;min-width:0;border:0;padding:0 12px;font-size:14px;background:transparent;color:var(--a-ink);height:100%;min-height:44px}
.zhd__s button{border:0;background:var(--a-acc);color:#fff;padding:0 14px;font-weight:700;cursor:pointer;
min-width:44px;min-height:44px;height:100%;flex:0 0 auto}
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
/* Полоса крошек: высота подчинена правилу цели нажатия. Невидимое расширение
   области пробовалось первым и не сработало — полоса обрезает содержимое, и
   расширенная область обрезалась вместе с ним. Поэтому высота настоящая: 44.
   Геометрия крошек у оригинала не измерена, так что паритету это не
   противоречит. */
.zcr{display:flex;flex-wrap:wrap;align-items:center;gap:6px;min-height:44px;
padding:0;margin:0 0 8px;font-size:13px;color:var(--a-dim);line-height:1.3}
@media(max-width:767px){.zcr{min-height:44px;height:auto}}
.zcr a{color:var(--a-acc);font-weight:600;text-decoration:none;
min-height:44px;display:inline-flex;align-items:center}
.zcr a:hover{text-decoration:underline}
.zcr [aria-current=page]{color:var(--a-ink);font-weight:600}
.ast{display:none}
.zrail,.zrail__logo,.zrail__sub,.zrail__t,.zrail__n,.zrail__g,.ztop{display:none}
.zh{font-size:clamp(22px,2vw,28px);line-height:1.25;font-weight:700;margin:16px 0 8px}
/* Заголовки секций у оригинала — прописные, по центру, с разрядкой и заметно
   мельче наших прежних: «НОВЫЕ СЕРИИ АНИМЕ», «НОВЫЕ АНИМЕ НА САЙТЕ»,
   «РЕКОМЕНДУЕМ ПОСМОТРЕТЬ:». Крупный тёмный заголовок слева — наша прежняя
   привычка, а не композиция эталона. */
.zh__n{color:var(--a-mute);font-weight:600}
.zh--sm{font-size:16px;font-weight:700;margin:24px 0 14px;text-transform:uppercase;
letter-spacing:.06em;text-align:center;color:var(--a-ink)}
.zsec__h{display:grid;grid-template-columns:1fr auto 1fr;align-items:baseline;gap:12px}
.zsec__h h2{grid-column:2;justify-self:center;font-size:16px;font-weight:700;
text-transform:uppercase;letter-spacing:.06em;text-align:center}
.zsec__h a{grid-column:3;justify-self:end}
@media(max-width:767px){
  .zsec__h{grid-template-columns:1fr auto}
  .zsec__h h2{grid-column:1;justify-self:center;margin-left:auto}
  .zsec__h a{grid-column:2}
}
.zsub{font-size:15px;color:var(--a-dim);margin:0 0 16px;max-width:72ch;line-height:1.45;
display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.zsec{margin:0 0 var(--a-section-gap);max-height:none;overflow:visible}
.zsec__h{display:flex;align-items:baseline;justify-content:space-between;gap:12px;margin:0 0 12px}
@media(max-width:519px){
  .zsec__h{flex-direction:column;align-items:flex-start;gap:4px}
  .zsec__h a{min-height:36px;display:inline-flex;align-items:center}
}
.zsec__h h2{font-size:clamp(20px,1.6vw,26px);font-weight:700;margin:0}
.zsec__h a{font-size:14px;color:var(--a-acc);font-weight:700;white-space:nowrap}
/* Лента первого экрана.
   Был одиночный герой: постер, абзац описания и кнопка — один тайтл на весь
   экран. У оригинала здесь красная полоса с рядом вертикальных постеров и
   стрелками по краям, и именно она сообщает «вот что на сайте есть».
   Красная подложка — не украшение: по ней первый экран и узнаётся. */
/* Ширина ленты — ровно ширина содержимого страницы. Была `min(100%,1180px)`:
   на широком экране красная полоса оказывалась уже всего остального, и её
   края не совпадали с краями блока «Новые серии» под ней. Совпадение краёв
   здесь не придирка — по нему глаз и читает, что это один столбец. */
.ahero{margin:0 0 18px;padding:10px 0 8px;border-radius:var(--a-radius-shell);
background:var(--a-acc);color:#fff;overflow:hidden;box-sizing:border-box;
border:0;contain:paint;position:relative;width:100%}
/* `contain:paint` здесь не украшение. Одного `overflow:hidden` не хватило:
   дорожка ленты шире окна, и страница получала горизонтальную прокрутку —
   измерено, 2214px на 390. Ширина тела при этом оставалась правильной, то
   есть прокрутку давал корень документа, а не вёрстка полосы. Ограничение
   отрисовки закрывает это: прокрутка страницы 0 на всех контрольных ширинах. */
.ahero__rl{padding:0 14px}
@media(max-width:767px){.ahero{padding:8px 0 6px}.ahero__rl{padding:0 8px}}
/* Стрелки ленты видны всегда, а не по наведению: у оригинала они стоят по
   краям полосы постоянно, и на планшете наведения попросту нет.
   Рисуются рамкой, а не знаком шрифта: «‹» и «›» есть не в каждом наборе, и
   недостающий знак браузер показывает коробкой с шестнадцатеричным кодом —
   ровно так на странице произведения и появился мусор «Подробнее ВЕ». */
.ahero .zrl__btn{display:inline-flex;top:50%;transform:translateY(-50%)}
.ahero__chev{display:block;width:10px;height:10px;border-style:solid;
border-color:var(--a-acc);border-width:2px 2px 0 0}
.ahero__chev--p{transform:rotate(-135deg);margin-left:3px}
.ahero__chev--n{transform:rotate(45deg);margin-right:3px}
@media(prefers-reduced-motion:reduce){.ahero .zrl__vp{scroll-behavior:auto}}
.ahero[hidden],.ahero--gap{display:none !important;height:0 !important;min-height:0 !important;
max-height:0 !important;margin:0 !important;padding:0 !important;border:0 !important;overflow:hidden}
.zh--home{font-size:clamp(18px,1.5vw,22px);margin:8px 0 4px;font-weight:700}
.zsub--home{margin:0 0 16px;font-size:14px;-webkit-line-clamp:2}
.ahero__inner{padding-block:12px}
.ahero .zrl__vp{padding-bottom:2px;scrollbar-width:none}
.ahero .zrl__vp::-webkit-scrollbar{display:none}
/* Ритм карусели тот же, что у сетки: у оригинала на первом экране семь
   постеров той же ширины, что и в каталоге, а не десять мелких. */
.ahero .zrl__track{gap:14px;align-items:flex-start}
/* Ширина плитки считается от окна прокрутки, а не от ленты.
   Измерено: проценты в дорожке разрешаются относительно самой дорожки, а она
   шире экрана ровно настолько, насколько лента листается, — поэтому на 768
   плитка выходила 203 вместо 118, а на 1920 растягивалась во всю ширину.
   Единицы контейнера считают от окна прокрутки и дают устойчивый размер;
   запасное значение на случай, если браузер их не знает, — эталонные 163. */
.ahero .zrl__vp{container-type:inline-size}
.ahero .zrl__track>*{flex:0 0 163px;width:163px;
min-width:0;max-width:none;scroll-snap-align:start}
.ahero .zt{max-width:none;flex:0 0 auto}
@supports (width:1cqw){
  .ahero .zrl__track>*{flex:0 0 calc((100cqw - 84px)/7);width:calc((100cqw - 84px)/7)}
  @media(max-width:1279px){
    .ahero .zrl__track>*{flex:0 0 calc((100cqw - 56px)/5);width:calc((100cqw - 56px)/5)}
  }
  @media(max-width:767px){
    .ahero .zrl__track>*{flex:0 0 112px;width:112px;min-width:112px;max-width:112px}
  }
}
@media(max-width:767px){
  .ahero{margin-bottom:16px;padding:10px}
  .ahero .zrl__track{gap:12px}
  .ahero .zrl__track>*{flex:0 0 112px;width:112px;min-width:112px;max-width:112px}
  .ahero .zt{width:112px;max-width:112px}
}
.ahero .zt{background:transparent;border:0;box-shadow:none;color:#fff;height:auto;max-height:none}
.ahero .zt:hover{opacity:.92;box-shadow:none;border:0;transform:none}
/* Плитка карусели — та же пропорция 5/7, что и в сетке: у оригинала постер
   первого экрана и постер каталога одного размера, 163x228. */
.ahero .zt__p{border-radius:10px;width:100%;aspect-ratio:5/7;height:auto;background:rgba(0,0,0,.18);flex:0 0 auto}
@media(max-width:767px){.ahero .zt__p{width:112px;height:157px;aspect-ratio:auto}}
.ahero .zt__b{padding:5px 2px 0;min-height:0;max-height:34px}
.ahero .zt__t{color:#fff;font-size:12px;-webkit-line-clamp:1;min-height:0;line-height:1.3}
/* Прятать поля стилем больше не нужно: лента рисует компактную карточку,
   в которой их нет по контракту. Прятать то, что отдано в разметке, — способ
   разойтись между обещанием и видимым. */
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
/* Ширина плитки ленты задаётся лентой, а не содержимым.
   Без этого правила карточки вне первого экрана растягивались каждая по
   своему тексту: ряд «Недавно добавленные» выходил из плиток разной ширины и
   разной высоты — измерено на 1363. Единицы контейнера считают от окна
   прокрутки, запасное значение — для браузеров, которые их не знают. */
.zrl__vp{container-type:inline-size}
.zrl__track>*{flex:0 0 150px;width:150px;min-width:0;max-width:none;scroll-snap-align:start}
@supports (width:1cqw){
  .zrl__track>*{flex:0 0 calc((100cqw - 5*12px)/6);width:calc((100cqw - 5*12px)/6)}
  @media(max-width:1199px){
    .zrl__track>*{flex:0 0 calc((100cqw - 3*12px)/4);width:calc((100cqw - 3*12px)/4)}
  }
  @media(max-width:767px){
    .zrl__track>*{flex:0 0 132px;width:132px}
  }
}
/* Карточка ленты одной высоты по всему ряду: разнобой высот и был тем, что
   владелец увидел как «незаполненный ряд». */
.zrl__track .zt{height:100%;max-height:none}
.zrl__track .zt__b{min-height:44px}
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
/* Промежуток сетки у оригинала — 33. Он выведен из двух независимых измерений,
   а не подобран: при содержимом 724 пять колонок с промежутком 33 дают карточку
   118 — ровно измеренную на 768; при содержимом 1340 семь колонок с тем же
   промежутком дают 163 — ровно измеренную на 1440 и на 1920.
   Правила на 1800 здесь нет намеренно: у оригинала постер одинаков и на 1440,
   и на 1920, потому что рамка ограничена. Колонки, растущие от ширины окна при
   ограниченном контейнере, мельчили карточку — было 121 на 1920. */
/* На телефоне у оригинала две колонки по ~180 при промежутке около 10:
   измерено на полностраничном снимке 390. Промежуток 33 сужал карточку до
   163 и оставлял пустую полосу между колонками. */
/* Колонок 2 / 4 / 6, а не 2 / 5 / 7.
   Обрывок последнего ряда владелец увидел не потому, что записей не хватило,
   а потому, что число колонок и размер выборки были несовместимы: при пяти и
   семи колонках любая выборка, кратная двенадцати, оставляет хвост, а прятать
   настоящие карточки стилем нельзя. Двойка, четвёрка и шестёрка — делители
   двенадцати, поэтому полка на 12 и страница на 24 ложатся целыми рядами на
   всех контрольных ширинах разом. Постер при этом не мельчает: при
   содержимом 1340 шесть колонок с промежутком 33 дают 196 вместо 163. */
@media(max-width:767px){.zg{gap:10px}}
@media(min-width:768px){.zg{grid-template-columns:repeat(4,minmax(0,1fr));gap:24px}}
@media(min-width:1200px){.zg{grid-template-columns:repeat(6,minmax(0,1fr));gap:28px}}
/* Каталог держит тот же ритм, что и остальные сетки витрины: у оригинала
   карточка одного размера на главной, в подборках и в рекомендациях, и делать
   её на каталоге шире незачем. Прежние шесть колонок с промежутком 14 давали
   198 вместо измеренных 163. */
.zwrap--catalog .zg,.zcat .zg{grid-template-columns:repeat(2,minmax(0,1fr))}
@media(min-width:768px){.zwrap--catalog .zg,.zcat .zg{grid-template-columns:repeat(4,minmax(0,1fr));gap:24px}}
@media(min-width:1200px){.zwrap--catalog .zg,.zcat .zg{grid-template-columns:repeat(6,minmax(0,1fr));gap:28px}}
.afilt--closed{max-height:112px}
.afilt--closed:not(.is-open):not(:has(details[open])){overflow:hidden}
.afilt--closed.is-open,.afilt--closed:has(details[open]){overflow:visible;max-height:none}
.zt{display:flex;flex-direction:column;background:var(--a-page);border:0;border-radius:var(--a-radius-card);
overflow:hidden;min-width:0;height:auto;max-height:320px;box-shadow:var(--a-shadow-soft);
transition:transform .14s,box-shadow .14s}
.zt:hover{transform:translateY(-2px);box-shadow:var(--a-shadow)}
.zt:focus-visible{outline:2px solid var(--a-acc);outline-offset:2px}
/* Кнопки ленты: цель 44x44 — меньше на телефоне в них не попасть. Точки
   показывают, сколько страниц у ленты и где мы сейчас; при одной странице
   они не рисуются вовсе, чтобы не обещать листание там, где его нет. */
.zsec .zrl__btn{width:44px;height:44px;border-radius:50%;
font-size:20px;line-height:1;display:inline-flex;align-items:center;justify-content:center;
background:rgba(16,21,26,.86);color:#fff;top:38%}
/* На красной полосе стрелка своя: белый круг с красным шевроном — тёмный
   круг на красном не читается. */
.ahero .zrl__btn{width:44px;height:44px;border-radius:50%;
background:#fff;color:var(--a-acc);border:0;box-shadow:0 2px 10px rgba(0,0,0,.22);
align-items:center;justify-content:center}
.ahero .zrl__btn:hover{background:#fff;filter:brightness(.96)}
.ahero .zrl__btn:focus-visible{outline:3px solid #fff;outline-offset:2px}
.ahero .zrl__btn--p{left:6px}
.ahero .zrl__btn--n{right:6px}
.zrl__dots{display:flex;gap:8px;justify-content:center;align-items:center;
margin:10px 0 0;padding:0;flex-wrap:wrap}
.zrl__dots[hidden]{display:none !important}
.zrl__dot{width:44px;height:44px;min-width:44px;padding:0;border:0;background:transparent;
cursor:pointer;position:relative;border-radius:50%}
.zrl__dot::after{content:"";position:absolute;left:50%;top:50%;translate:-50% -50%;
width:8px;height:8px;border-radius:50%;background:var(--a-line);transition:background .15s}
.zrl__dot[aria-current="true"]::after{background:var(--a-acc);width:10px;height:10px}
.zrl__dot:focus-visible{outline:2px solid var(--a-acc);outline-offset:2px}
/* На телефоне восемь точек по 44px не помещались в ряд и переносились —
   последняя выглядела случайной кляксой под лентой. Ширину ужимаем, высоту
   цели нажатия (44) оставляем. */
@media(max-width:520px){.zrl__dots{gap:0}.zrl__dot{width:34px;min-width:34px}}
.ahero .zrl__dot::after{background:rgba(255,255,255,.45)}
.ahero .zrl__dot[aria-current="true"]::after{background:#fff}
/* Нижний блок страницы произведения. Измерено на эталоне 1440: три колонки,
   карточка 436x120, промежуток 16, светлая подложка, скруглeние 10; слева
   миниатюра около 100, справа название, оригинальное название серым и оценка
   с числом голосов. Сетка постеров здесь была не «другим размером», а другой
   композицией. */
.zg--related-row,.zsec--rel .zg--related-row{display:grid;gap:16px;
grid-template-columns:1fr}
@media(min-width:768px){
  .zg--related-row,.zsec--rel .zg--related-row{grid-template-columns:repeat(2,minmax(0,1fr))}
}
@media(min-width:1024px){
  .zg--related-row,.zsec--rel .zg--related-row{grid-template-columns:repeat(3,minmax(0,1fr))}
}
.zt--row{display:flex;flex-direction:row;align-items:stretch;gap:0;background:var(--a-alt);
border-radius:10px;overflow:hidden;min-height:120px;text-decoration:none;color:inherit}
.zt--row:hover{background:var(--a-surf)}
.zt--row:focus-visible{outline:3px solid var(--a-acc);outline-offset:2px}
.zt--row .zt__p{flex:0 0 100px;width:100px;aspect-ratio:auto;height:auto;border-radius:0;
background:var(--a-surf)}
.zt--row .zt__p img,.zt--row .zt__p .zt__img{width:100%;height:100%;object-fit:cover}
.zt--row .zt__b{flex:1 1 auto;min-width:0;display:flex;flex-direction:column;
justify-content:center;gap:6px;padding:12px 14px}
.zt--row .zt__t{font-size:15px;font-weight:600;line-height:1.25;color:var(--a-ink);
display:-webkit-box;-webkit-line-clamp:1;-webkit-box-orient:vertical;overflow:hidden}
.zt--row .zt__m{font-size:12px;color:var(--a-dim);line-height:1.3}
.zt__orig{font-size:12px;color:var(--a-mute);line-height:1.3;
display:-webkit-box;-webkit-line-clamp:1;-webkit-box-orient:vertical;overflow:hidden}
/* Оценка в строке — просто подпись источника и число, как у оригинала.
   Подложка с тенью делала её похожей на поле ввода. Селектор с двумя классами
   нужен, чтобы перекрыть общее правило бейджа, объявленное ниже по листу. */
.zt--row .zt__rate,.zt--row .zt__rate--row{position:static;background:none;
box-shadow:none;border:0;padding:0;border-radius:0;font-size:15px;gap:6px;
align-self:flex-start}
.zt__rate--row b{font-size:16px;color:var(--a-ink);font-weight:600}
.zt__rate--row i{font-size:11px}
.zt__votes{color:var(--a-mute);font-size:11px}
@media(max-width:767px){
  .zt--row{min-height:96px}
  .zt--row .zt__p{flex:0 0 76px;width:76px}
  .zt--row .zt__t{font-size:14px}
}
/* Панель действий под плеером. Одна строка: десять звёзд и пять кнопок
   списков. Ширина та же, что у плеера, — иначе она читается как чужой блок,
   приехавший со стороны.
   На компьютере всё помещается в строку: звезда 26px даёт шкале ~270, пять
   кнопок ещё ~430 — это меньше 1200 даже с промежутками. На телефоне строка
   переносится, и цель нажатия при этом не уменьшается: высота остаётся 44. */
.apanel{display:flex;align-items:center;justify-content:space-between;gap:12px 18px;
flex-wrap:wrap;margin:14px auto 0;width:min(100%,1200px);padding:10px 14px;
border:1px solid var(--a-line);border-radius:14px;background:var(--a-alt);
box-sizing:border-box}
.apanel__stars{margin:0;display:flex;align-items:center;gap:10px;flex:0 0 auto}
.apanel__stars .astar__row{gap:1px}
.apanel__stars .astar__b{min-width:26px;min-height:44px;padding:0}
.apanel__stars .astar__i,.apanel__stars .astar__s svg{width:26px;height:26px}
.apanel__stars .astar__s{padding:0 1px}
.apanel__mine{font-size:13px;color:var(--a-ink);white-space:nowrap}
.apanel__mine b{color:var(--a-acc);font-size:15px}
.apanel__lists{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:0;
flex:1 1 auto;justify-content:flex-end}
@media(max-width:899px){
  .apanel{justify-content:center}
  .apanel__stars{flex:1 1 100%;justify-content:center}
  .apanel__lists{justify-content:center;flex:1 1 100%}
  .apanel__stars .astar__b{min-width:28px}
}
/* Реакции — полоса во всю ширину плеера: крупный значок, счётчик под ним,
   равные доли. Прежде это был ряд мелких «таблеток» в углу коробки. */
.areacts{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;
margin:16px auto 0;width:min(100%,1200px)}
.areact{display:flex;flex-direction:column;align-items:center;justify-content:center;
gap:4px;min-height:74px;padding:10px 6px;border:1px solid var(--a-line);
border-radius:14px;background:var(--a-page);color:var(--a-dim);font:inherit;
cursor:pointer;transition:border-color .12s,background .12s,transform .12s}
.areact .areact__i{width:30px;height:30px;transition:transform .12s}
.areact b{font-size:14px;font-weight:700;color:var(--a-ink);
font-variant-numeric:tabular-nums}
.areact:hover{border-color:var(--a-acc);transform:translateY(-1px)}
.areact:hover .areact__i{transform:scale(1.1)}
.areact.is-on{border-color:var(--a-acc);background:var(--a-alt);
box-shadow:inset 0 0 0 1px var(--a-acc)}
.areact.is-on b{color:var(--a-acc)}
.areact:focus-visible{outline:3px solid var(--a-acc);outline-offset:2px}
@media(max-width:519px){
  .areacts{gap:6px}
  .areact{min-height:66px;padding:8px 2px}
  .areact .areact__i{width:26px;height:26px}
}
/* Раздел сообщества: оценка зрителей, списки, реакции и обсуждение.
   Было три полосы во всю ширину подряд — оценка, списки, реакции, — каждая с
   огромным пустым полем посередине, и форма сообщения во всю ширину экрана
   под ними. Стало: слева оценка, справа списки и реакции, ниже обсуждение в
   читаемой колонке. Цели нажатия остались настоящими, 44x44: пальцем по
   цифре «7» иначе не попасть. */
.acomm{margin:28px 0 0}
.acomm__off{color:var(--a-dim);margin:0 0 6px;max-width:72ch}
/* Итог отправки формы. Молчание после сохранения — это интерфейс, по которому
   нельзя понять, применилось ли действие. */
.acomm__flash{margin:0 0 14px;padding:10px 14px;border-radius:10px;font-size:14px;
border:1px solid var(--a-line);background:var(--a-alt);color:var(--a-ink)}
.acomm__flash--ok{border-color:#1a7f37;color:#1a7f37}
.acomm__flash--warn{border-color:#9a6700;color:#9a6700}
.acomm__flash--err{border-color:var(--a-acc);color:var(--a-acc)}
.acomm__hint{flex:1 0 100%;margin:2px 0 0;font-size:12px;color:var(--a-mute);line-height:1.35}
.acomm__none{color:var(--a-mute);font-size:13px;margin:0}
/* Шкала — ровная сетка на десять клеток, а не строка кнопок вразнобой. */
/* Шкала звёзд. Один компонент на карточку произведения и на обсуждение.
   Разметка идёт от десятой звезды к первой, видимый порядок разворачивает
   `row-reverse`: тогда `:hover ~ *` — это ровно звёзды левее наведённой, и
   подсветка «до сюда» работает без единой строки скрипта. */
.astar{margin:0}
.astar__row{display:flex;flex-direction:row-reverse;justify-content:flex-end;
gap:2px;flex-wrap:nowrap;min-width:0}
.astar__b{appearance:none;border:0;background:none;padding:4px 1px;margin:0;
cursor:pointer;line-height:0;color:var(--a-line);border-radius:6px;
min-width:28px;min-height:44px;display:inline-flex;align-items:center;
justify-content:center;transition:color .1s,transform .1s}
.astar__i{display:block;fill:currentColor}
/* Наведение и фокус ТОЛЬКО показывают предполагаемый выбор. Сохраняет его
   нажатие: при правиле «один голос навсегда» оценка по наведению превратила
   бы случайное движение мыши в необратимое действие. */
.astar__row:hover .astar__b:hover,
.astar__row:hover .astar__b:hover ~ .astar__b,
.astar__row:focus-within .astar__b:focus-visible,
.astar__row:focus-within .astar__b:focus-visible ~ .astar__b{
color:var(--a-acc);transform:scale(1.06)}
.astar__b:focus-visible{outline:2px solid var(--a-acc);outline-offset:2px}
/* Сохранённая оценка: те же звёзды, но не кнопки — нажимать нечего. */
.astar--fixed .astar__row{flex-direction:row}
.astar__s{color:var(--a-line);line-height:0;padding:2px 1px;display:inline-flex}
.astar__s.is-on{color:var(--a-acc)}
.areact__i{display:block;flex:0 0 auto}
.areact__i{transition:transform .12s}
/* Обсуждение — колонка чтения, а не полотно во всю ширину: строка в 200
   знаков читается глазами по одному разу и не с первого раза. */
.acomm__talk{margin:18px 0 0;max-width:72ch}
.acomm__list-wrap{margin:14px 0 0}
.acomm__list{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:10px}
/* Сообщение: аватар слева, содержимое справа. Аватар даёт ленте ритм — без
   него подряд идущие реплики сливаются в один абзац. */
.acomm__item{display:grid;grid-template-columns:auto minmax(0,1fr);gap:12px;
padding:12px 14px;border-radius:12px;background:var(--a-alt);
border:1px solid var(--a-line)}
.acomm__ava{display:inline-flex;align-items:center;justify-content:center;
width:38px;height:38px;border-radius:50%;color:#fff;font-weight:700;font-size:16px;
line-height:1;flex:0 0 auto;user-select:none}
.acomm__body{min-width:0}
.acomm__item-h{display:flex;flex-wrap:wrap;align-items:baseline;gap:2px 10px}
.acomm__text{margin:6px 0 0;color:var(--a-ink);line-height:1.45;overflow-wrap:anywhere}
.acomm__name{font-weight:700;color:var(--a-ink)}
/* Метка «на проверке» стоит у своего же сообщения: без неё автор решит, что
   отправка не сработала, и напишет ещё раз. */
.acomm__pending{margin-left:auto;font-size:11px;font-weight:700;letter-spacing:.04em;
text-transform:uppercase;color:#9a6700;border:1px solid currentColor;border-radius:999px;
padding:2px 8px}
.acomm__item--pending{border-style:dashed}
.acomm__date{color:var(--a-mute);font-size:12px}
.acomm__form{display:flex;flex-direction:column;gap:10px;margin:0}
.acomm__field{display:flex;flex-direction:column;gap:4px}
@media(min-width:560px){.acomm__field--name{max-width:280px}}
.acomm__form label{font-size:12px;color:var(--a-mute);text-transform:uppercase;
letter-spacing:.04em}
.acomm__form input,.acomm__form textarea{font:inherit;padding:10px 12px;min-height:44px;
border:1px solid var(--a-line);border-radius:10px;background:var(--a-page);color:var(--a-ink);
width:100%;box-sizing:border-box}
.acomm__form textarea{min-height:88px;resize:vertical}
/* Панель смайликов. Свёрнута по умолчанию: шестнадцать кнопок под каждым
   полем ввода — это шум, а не помощь. */
/* Расписание: переключатели дней, две колонки на компьютере, одна на
   телефоне. Время выделено акцентом — за ним сюда и приходят. */
.asch__tabs{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 16px}
.asch__tab{appearance:none;display:inline-flex;align-items:center;gap:6px;
min-height:44px;padding:0 14px;border:1px solid var(--a-line);border-radius:999px;
background:var(--a-page);color:var(--a-ink);font:inherit;font-size:14px;
font-weight:600;cursor:pointer}
.asch__tab b{font-weight:700;font-size:12px;color:var(--a-mute);
font-variant-numeric:tabular-nums}
.asch__tab:hover{border-color:var(--a-acc);color:var(--a-acc)}
.asch__tab[aria-selected="true"]{background:var(--a-acc);border-color:var(--a-acc);color:#fff}
.asch__tab[aria-selected="true"] b{color:rgba(255,255,255,.8)}
.asch__tab:focus-visible{outline:2px solid var(--a-acc);outline-offset:2px}
.asch__tab-s{display:none}
@media(max-width:519px){
  .asch__tab-l{display:none}.asch__tab-s{display:inline}
  .asch__tab{padding:0 12px}
}
.asch__day[hidden]{display:none !important}
.asch__grid{display:grid;grid-template-columns:1fr;gap:10px}
@media(min-width:768px){.asch__grid{grid-template-columns:repeat(2,minmax(0,1fr));
column-gap:clamp(16px,2vw,28px)}}
.asch__row{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;
gap:12px;min-height:72px;padding:0 14px 0 0;background:var(--a-alt);border-radius:12px;
text-decoration:none;color:inherit;overflow:hidden}
.asch__row:hover{background:var(--a-surf)}
.asch__row:focus-visible{outline:3px solid var(--a-acc);outline-offset:2px}
.asch__thumb{position:relative;width:54px;aspect-ratio:2/3;overflow:hidden;
background:var(--a-surf);border-radius:12px 0 0 12px;flex:0 0 auto}
.asch__thumb img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.asch__none-p{display:flex;align-items:center;justify-content:center;width:100%;
height:100%;color:var(--a-mute);font-weight:700}
.asch__body{min-width:0;display:flex;flex-direction:column;gap:3px;padding:8px 0}
.asch__t{font-size:14px;font-weight:600;line-height:1.25;color:var(--a-ink);
display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.asch__ep{font-size:12px;color:var(--a-dim);display:flex;align-items:center;gap:6px}
.asch__out{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.03em;
color:#1a7f37;border:1px solid currentColor;border-radius:999px;padding:1px 6px}
.asch__time{font-size:19px;font-weight:800;color:var(--a-acc);white-space:nowrap;
font-variant-numeric:tabular-nums}
.asch__time--soon{font-size:12px;font-weight:600;color:var(--a-mute);
max-width:96px;white-space:normal;text-align:right;line-height:1.25}
.asch__time--out{font-size:13px;font-weight:700;color:var(--a-mute)}
.asch__none{margin:0;padding:28px 16px;text-align:center;color:var(--a-dim);
background:var(--a-alt);border-radius:12px}
/* «Расписание уточняется» — не то же, что «релизов нет». Первое означает, что
   мы не знаем, второе — что знаем и релизов нет. Разный текст и разный вид. */
.asch__none--wait{color:var(--a-mute);border:1px dashed var(--a-line);background:transparent}
.asch__stale{margin:0 0 14px;padding:10px 14px;border-radius:10px;font-size:13px;
border:1px solid #9a6700;color:#9a6700;background:var(--a-alt)}
/* «Моё аниме»: оглавление разделов с числом отмеченного. */
.amine__tabs{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 18px}
.amine__tab{display:inline-flex;align-items:center;gap:7px;min-height:40px;padding:0 14px;
border:1px solid var(--a-line);border-radius:999px;background:var(--a-page);
color:var(--a-ink);font-size:14px;font-weight:600;text-decoration:none}
.amine__tab b{font-size:12px;color:var(--a-mute);font-variant-numeric:tabular-nums}
.amine__tab:hover{border-color:var(--a-acc);color:var(--a-acc)}
.amine__tab.is-empty{opacity:.55;pointer-events:none}
.aemo{margin:6px 0 0}
.aemo__open{appearance:none;border:1px solid var(--a-line);background:var(--a-page);
color:var(--a-dim);font:inherit;font-size:12px;font-weight:700;cursor:pointer;
border-radius:999px;min-height:32px;padding:0 12px}
.aemo__open:hover,.aemo__open[aria-expanded="true"]{border-color:var(--a-acc);color:var(--a-acc)}
.aemo__open:focus-visible,.aemo__b:focus-visible{outline:2px solid var(--a-acc);outline-offset:2px}
.aemo__panel{display:grid;grid-template-columns:repeat(8,minmax(0,1fr));gap:4px;
margin:8px 0 0;padding:10px;border:1px solid var(--a-line);border-radius:12px;
background:var(--a-page);max-width:360px;box-shadow:var(--a-shadow-soft)}
@media(max-width:519px){.aemo__panel{grid-template-columns:repeat(6,minmax(0,1fr))}}
.aemo__panel[hidden]{display:none !important}
.aemo__b{appearance:none;border:0;background:none;cursor:pointer;font-size:20px;
line-height:1;min-width:38px;min-height:38px;border-radius:10px;padding:0}
.aemo__b:hover{background:var(--a-alt);transform:scale(1.1)}
.acomm__send{align-self:flex-start;min-height:44px;padding:0 20px;border:0;
border-radius:10px;background:var(--a-acc);color:#fff;font:inherit;font-weight:700;cursor:pointer}
/* Сводная оценка: крупное число и подпись, из чего она сложилась. Без подписи
   посетитель принял бы нашу арифметику за оценку конкретного сайта. */
/* Иерархия колонки сверху вниз: главный рейтинг, шкала, личная оценка.
   Вложенной рамки у главного рейтинга больше нет — он внутри карточки, и
   вторая рамка вокруг числа только дробила колонку на коробки. */
.ztitle__score{display:flex;flex-direction:column;align-items:center;gap:2px;
padding:0;margin:0}
.ztitle__score-val{font-size:34px;font-weight:800;line-height:1;color:var(--a-acc)}
.ztitle__score-lab{font-size:11px;color:var(--a-mute);text-transform:uppercase;
letter-spacing:.04em;text-align:center}
/* Подсказка про стартовую оценку — одна фраза мелким кеглем, а не абзац:
   посетителю нужно понять, почему первая же девятка не делает рейтинг
   девяткой, а не прочитать описание методики. */
.ztitle__hint{margin:0;font-size:12px;line-height:1.4;color:var(--a-mute)}
.ztitle__drift{margin:0;font-size:12px;line-height:1.4;color:#9a6700}
/* Внешние источники — справочная строка под главным числом. Это не участники
   расчёта по отдельности (база берётся одна), но посетителю важно видеть,
   откуда она взялась; источник базы помечен. */
.ztitle__srcs{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:4px}
.ztitle__srcs li{display:flex;align-items:baseline;justify-content:space-between;
gap:8px;font-size:12px;color:var(--a-dim)}
.ztitle__srcs .lab{font-weight:600}
.ztitle__srcs .val{font-weight:700;color:var(--a-ink);font-variant-numeric:tabular-nums}
.ztitle__srcs li[data-base="1"] .lab::after{content:" · старт";color:var(--a-mute);
font-weight:600;font-size:11px}
/* Бейджи карточки — как у оригинала: слева сверху сколько серий доступно из
   заявленных, справа сверху до двух оценок с названным источником. Подпись
   источника обязательна: цифра без источника ничего не значит, а сводить
   несводимые шкалы в одно число мы не станем. */
.zt__p{position:relative}
/* Бейджи переносятся, а не выходят за край: на узкой карточке «104 из 104»
   и подпись источника вместе шире постера, и ссылка получала прокрутку —
   измерено на 320 и 390. */
.zt__badges{position:absolute;inset:6px 6px auto 6px;display:flex;justify-content:space-between;
align-items:flex-start;gap:6px;pointer-events:none;z-index:2;flex-wrap:wrap;max-width:calc(100% - 12px)}
.zt__eps{background:#fff;color:var(--a-acc);font-size:11px;font-weight:700;line-height:1;
padding:5px 7px;border-radius:6px;box-shadow:var(--a-shadow-soft);white-space:nowrap;
max-width:100%;overflow-wrap:anywhere}
/* Списки посетителя: строка кнопок, выбранная подсвечена. Повторное нажатие
   снимает выбор — у кнопки, которая умеет только добавлять, нет обратного
   хода. Класс свой: прежде кнопка списка и список сообщений назывались одним
   именем `.acomm__list`, и правила накладывались друг на друга — лента
   комментариев получала `display:inline-flex` от кнопки. */

.acomm__list-btn{display:inline-flex;align-items:center;min-height:40px;padding:0 14px;
border:1px solid var(--a-line);border-radius:999px;background:var(--a-card);
color:var(--a-ink);font:inherit;font-size:14px;cursor:pointer}
.acomm__list-btn:hover{border-color:var(--a-acc);color:var(--a-acc)}
.acomm__list-btn.is-on{background:var(--a-acc);border-color:var(--a-acc);color:#fff}
/* Оценка зрителей рядом с внешней — отдельной строкой и с подписью: без
   подписи два числа подряд читаются как одно и то же, посчитанное дважды. */
.ztitle__ourvotes{display:flex;flex-wrap:wrap;align-items:baseline;gap:2px 8px;
margin:8px 0 10px;color:var(--a-dim);font-size:13px}
.ztitle__ourvotes-l{flex:1 0 100%;font-size:11px;letter-spacing:.04em;
text-transform:uppercase;color:var(--a-mute);font-weight:700}
.ztitle__ourvotes b{color:var(--a-ink);font-size:18px;font-weight:800}
.ztitle__ourvotes-n{font-size:12px;color:var(--a-mute)}
.ztitle__ourvotes a{color:var(--a-acc);font-weight:700;min-height:44px;
display:inline-flex;align-items:center}
.ztitle__score-val--none{color:var(--a-mute)}
/* Боковая лента новых серий на внутренних страницах. */
.awrap-side{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:28px;
align-items:start}
.aside-eps{position:sticky;top:104px;margin:0}
@media(max-width:1023px){
  .awrap-side{grid-template-columns:minmax(0,1fr)}
  .aside-eps{position:static}
}
/* Отбор над сеткой каталога. У оригинала это одна компактная полоса:
   поиск, раскрывающиеся списки и «Очистить» — а не панель в полстраницы. */
.afilt__q{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:0 0 10px}
.afilt__q input{flex:1 1 220px;min-width:0;max-width:340px;min-height:44px;padding:0 14px;
font:inherit;font-size:14px;border:1px solid var(--a-line);border-radius:10px;
background:var(--a-page);color:var(--a-ink)}
.afilt__q button{min-height:44px;padding:0 18px;border:0;border-radius:10px;
background:var(--a-acc);color:#fff;font:inherit;font-weight:700;cursor:pointer}
.afilt__q input:focus-visible,.afilt__q button:focus-visible{
outline:2px solid var(--a-acc);outline-offset:2px}
.zsec--home-catalog .afilt{margin:0 0 6px}
.zsec--home-catalog .zsub{margin:6px 0 14px}
/* Хабы жанров и типов: одинаковые карточки-ссылки, счётчик под названием. */
.ahub{display:grid;gap:12px;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));
margin:18px 0 8px}
.ahub__c{display:flex;flex-direction:column;gap:3px;min-height:74px;padding:14px 16px;
border:1px solid var(--a-line);border-radius:12px;background:var(--a-card);
color:var(--a-ink);text-decoration:none}
.ahub__c:hover,.ahub__c:focus-visible{border-color:var(--a-acc)}
.ahub__n{font-weight:600;font-size:15px}
.ahub__k{color:var(--a-dim);font-size:13px}
.ahub__p{color:var(--a-mute);font-size:12px}
/* Вкладки срезов топа. */
.atabs{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0 10px}
.atabs__t{display:inline-flex;align-items:center;min-height:40px;padding:0 16px;
border:1px solid var(--a-line);border-radius:999px;font-size:14px;color:var(--a-ink);
text-decoration:none}
.atabs__t.is-on{background:var(--a-acc);border-color:var(--a-acc);color:#fff}
.atabs__t:focus-visible{outline:2px solid var(--a-acc);outline-offset:2px}
.atop__method{margin:0 0 12px;color:var(--a-dim)}
/* Фирменный знак оценки. Один на карточку, один и тот же размер везде:
   именно постоянство размера и места делает ряд карточек читаемым — глаз
   находит число, не перечитывая каждую плитку. Красный здесь работает как
   акцент на маленькой площади, а не как заливка. */
.zt__score{position:absolute;top:0;right:0;display:inline-flex;align-items:center;
justify-content:center;width:34px;height:34px;border-radius:50%;background:var(--a-acc);
color:#fff;box-shadow:var(--a-shadow-soft);pointer-events:none}
.zt__score b{font-size:13px;font-weight:700;line-height:1;letter-spacing:-.01em}
/* Нет данных — тот же знак приглушённым, чтобы ряд не рвался пустотой. */
.zt__score--none{background:var(--a-line);color:var(--a-mute)}
.zt__score--none b{font-size:14px}
/* Строчная карточка: знак встаёт в поток, круг там неуместен. */
.zt__score--row{position:static;width:auto;height:auto;border-radius:8px;
padding:4px 9px;background:var(--a-acc)}
.zt__score--row.zt__score--none{background:var(--a-line)}
@media(max-width:767px){
  .zt__badges{inset:4px 4px auto 4px}
  .zt__eps{font-size:10px;padding:4px 6px}
  .zt__score{width:30px;height:30px}
  .zt__score b{font-size:12px}
}
/* Пропорция постера оригинала — 5/7 (0.714): измерено 163x228 на 1440 и 1920,
   118x165 на 768, и на всех ширинах одно и то же отношение. Прежние 2/3 (0.667)
   вытягивали каждую карточку витрины. */
.zt__p{display:block;aspect-ratio:5/7;background:var(--a-surf);position:relative;flex:0 0 auto;width:100%}
.zt__p img,.zt__img{position:absolute;inset:0;z-index:1;width:100%;height:100%;object-fit:cover;display:block;
max-width:none;max-height:none}
.zt__none{position:absolute;inset:0;display:grid;place-items:center;padding:10px;text-align:center;color:var(--a-mute);font-size:12px}
.zt__none b{display:block;font-size:28px;font-weight:800;color:var(--a-dim);margin-bottom:4px}
.zt__b{padding:6px 8px 8px;display:flex;flex-direction:column;gap:2px;flex:0 0 auto;min-height:52px}
.zt__t{font-size:12.5px;font-weight:700;line-height:1.25;
display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;min-height:0;
/* B15: длинное слово в узкой карточке переносится, а не срезается краем.
   Измерено на 320px: «Противостояние» выходило за рамку на 6px. */
overflow-wrap:anywhere}
.zt__m{display:block;font-size:11px;color:var(--a-dim);line-height:1.25;
display:-webkit-box;-webkit-line-clamp:1;-webkit-box-orient:vertical;overflow:hidden;min-height:0}
.zt__r{display:flex;gap:8px;font-size:12px;color:var(--a-dim);margin-top:4px;padding-top:0;
flex-wrap:nowrap;min-height:1.25em;align-items:center}
.zt__r b,.zt__r i{color:var(--a-acc);font-weight:700;font-style:normal}
.zt__r em{color:var(--a-mute);font-style:italic;visibility:hidden}
.zsec--rel{margin-bottom:28px}
.zsec--rel[hidden],.zsec--rel-gap{display:none !important;height:0 !important;min-height:0 !important;
margin:0 !important;padding:0 !important;border:0 !important;overflow:hidden !important}
.zsec--rel .zg:not(.zg--related-row),.zsec--rel .zg--recommendation{gap:var(--a-grid-gap);
grid-template-columns:repeat(2,minmax(0,1fr))}
/* Рекомендации на странице тайтла — та же карточка, что и везде: у оригинала
   на 1440 она 163x228 и в рекомендациях тоже. Шесть колонок давали 197. */
@media(min-width:768px){.zsec--rel .zg:not(.zg--related-row),.zsec--rel .zg--recommendation{
  grid-template-columns:repeat(5,minmax(0,1fr));gap:33px}}
@media(min-width:1200px){.zsec--rel .zg:not(.zg--related-row),.zsec--rel .zg--recommendation{
  grid-template-columns:repeat(7,minmax(0,1fr));gap:33px}}
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
/* Честная сноска о недостающем времени: обычный текст над лентой, не
   плашка-предупреждение. */
/* Листалка ленты: кнопки по центру, выбранная — красная. */
.aeps__pages{display:flex;gap:8px;justify-content:center;margin:16px 0 0;flex-wrap:wrap}
.aeps__pg{display:inline-flex;align-items:center;justify-content:center;
min-width:44px;min-height:44px;padding:0 12px;border-radius:10px;
border:1px solid var(--a-line);background:var(--a-page);color:var(--a-ink);
font-size:15px;font-weight:700;text-decoration:none;font-variant-numeric:tabular-nums}
.aeps__pg:hover{border-color:var(--a-acc);color:var(--a-acc)}
.aeps__pg.is-on{background:var(--a-acc);border-color:var(--a-acc);color:#fff}
/* Страница, для которой событий ещё нет, видна, но не обещает содержимого. */
.aeps__pg.is-off{opacity:.4;cursor:default;pointer-events:none}
.aeps__pg:focus-visible{outline:2px solid var(--a-acc);outline-offset:2px}
.aeps__short{margin:12px 0 0;font-size:13px;line-height:1.45;color:var(--a-dim);
text-align:center;max-width:72ch;margin-inline:auto}
.aeps[hidden]{display:none !important}
.aeps__gap{margin:0 0 12px;font-size:13px;line-height:1.45;color:var(--a-dim);max-width:78ch}
/* Страница ленты: одна колонка на телефоне, две по пять строк на компьютере.
   Порядок заполнения — по колонкам сверху вниз (`grid-auto-flow:column` с
   пятью строками), как у оригинала: иначе свежие пять оказались бы размазаны
   через строку по обеим колонкам. */
.ahome-eps .aeps,.zsec--eps.ahome-eps .zl{display:grid;gap:12px;grid-template-columns:1fr}
@media(min-width:900px){
  .ahome-eps .aeps,.zsec--eps.ahome-eps .zl{
    grid-template-columns:1fr 1fr;grid-template-rows:repeat(5,auto);
    grid-auto-flow:column;column-gap:clamp(24px,2vw,32px);row-gap:12px}
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
.ahome-eps .zpg a,.ahome-eps .zpg span{min-width:44px;min-height:44px}
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
/* Базовая строка серии. Прежде размечена была только лента главной
   (`.ahome-eps .aeps__row`), а та же строка в боковой колонке каталога
   оставалась обычной ссылкой: спаны ложились друг на друга, и номер серии
   печатался поверх названия — измерено на 390, 1363 и 1920. Раскладка теперь
   у самой строки, а лента главной лишь уточняет размеры. */
.aeps__row{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;
gap:10px;min-height:64px;padding:0 10px 0 0;background:var(--a-alt);border-radius:10px;
text-decoration:none;color:inherit;overflow:hidden}
.aeps__row:hover{background:var(--a-surf)}
.aeps__row:focus-visible{outline:3px solid var(--a-acc);outline-offset:2px}
.aeps__thumb{position:relative;flex:0 0 auto;width:52px;aspect-ratio:2/3;overflow:hidden;
background:var(--a-surf);border-radius:10px 0 0 10px}
.aeps__thumb img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.aeps__none{display:flex;align-items:center;justify-content:center;width:100%;height:100%;
color:var(--a-mute);font-weight:700}
.aeps__body{min-width:0;display:flex;flex-direction:column;gap:2px;padding:8px 0}
.aeps__title{font-size:14px;font-weight:600;line-height:1.25;color:var(--a-ink);
display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.aeps__meta{font-size:12px;color:var(--a-dim);line-height:1.3}
.aeps__ep{display:flex;flex-direction:column;align-items:center;justify-content:center;
min-width:44px;color:var(--a-acc);line-height:1}
.aeps__num{font-size:22px;font-weight:800}
.aeps__lab{font-size:11px;color:var(--a-mute);text-transform:uppercase;letter-spacing:.03em}
.zfilt,.zgenres__nav,.zstrip{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 14px;align-items:center}
.zfilt a,.zgenres__nav a,.zstrip a,.zfilt__y a{display:inline-flex;align-items:center;
min-height:44px;padding:0 12px;border-radius:var(--a-radius-chip);border:1px solid var(--a-line);
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
.afilt__chip{display:inline-flex;align-items:center;gap:6px;min-height:44px;padding:0 12px;
border-radius:999px;border:1px solid var(--a-acc);background:var(--a-alt);color:var(--a-acc);font-size:13px;font-weight:700}
.afilt__reset{min-height:36px;display:inline-flex;align-items:center;padding:0 10px;font-size:13px;font-weight:700;color:var(--a-dim)}
.afilt__rows{display:flex;flex-wrap:wrap;gap:8px;align-items:flex-start}
.afilt__dd{position:relative;min-width:0}
.afilt__dd>summary{list-style:none;cursor:pointer;min-height:44px;padding:0 12px;border-radius:var(--a-radius-chip);
border:1px solid var(--a-line);background:var(--a-page);font-size:13px;font-weight:700;color:var(--a-ink);
display:inline-flex;align-items:center;gap:6px}
.afilt__dd>summary::-webkit-details-marker{display:none}
.afilt__dd[open]>summary{border-color:var(--a-acc);color:var(--a-acc)}
.afilt__opts{position:absolute;z-index:40;top:calc(100% + 4px);left:0;min-width:220px;max-height:280px;overflow:auto;
padding:8px;border-radius:12px;border:1px solid var(--a-line);background:var(--a-page);box-shadow:var(--a-shadow-soft);
display:flex;flex-direction:column;gap:2px}
.afilt__opts a{display:flex;justify-content:space-between;gap:12px;min-height:44px;padding:8px 10px;border-radius:8px;
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
@media(min-width:900px){.ztitle{grid-template-columns:180px minmax(0,1fr) 208px;
column-gap:clamp(20px,2vw,28px)}}
@media(min-width:1200px){.ztitle{grid-template-columns:240px minmax(0,1fr) 216px;
column-gap:28px;padding:28px 32px}}
.ztitle__poster{aspect-ratio:240/351;border-radius:12px;overflow:hidden;
background:var(--a-surf);position:relative;width:100%;max-width:240px;margin:0 auto;
height:auto;min-height:0}
/* Постер страницы тайтла у оригинала — 240x351 и на телефоне, и на широком
   экране: измерено на снимке 390 и подтверждено владельческой записью для
   ~1363. У нас он был 112 на телефоне и 180 на промежуточной ширине, то есть
   страница произведения начиналась с миниатюры вместо постера. */
.ztitle__poster{width:240px;max-width:100%;aspect-ratio:240/351;margin:0}
@media(max-width:599px){.ztitle__poster{width:240px;max-width:100%;margin:0}}
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
padding:0 12px;min-height:44px;border-radius:var(--a-radius-chip);border:1px solid var(--a-line);background:var(--a-alt);
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
/* Колонка оценки видна на всех ширинах. Раньше она скрывалась до 900px, и
   на телефоне страница произведения оставалась вообще без оценки — то есть
   без ответа на вопрос, ради которого её и открывают. На узком экране
   колонка идёт строкой над содержимым, на широком — боковой колонкой. */
/* Колонка рейтинга — карточка с внутренним полем, а не текст, прижатый к
   краю. Прежде ширина была 160–170, а в неё складывали десять звёзд и абзац
   пояснения: последняя звезда и текст упирались в границу колонки, потому что
   поля не было вовсе. Теперь колонка шире, у неё есть поле, и шкала считает
   свой размер от доступного места, а не наоборот. */
.ztitle__rail{display:flex;flex-direction:column;gap:10px;min-width:0;width:100%;
max-width:none;margin:0 0 12px;padding:14px;border:1px solid var(--a-line);
border-radius:14px;background:var(--a-alt);box-sizing:border-box}
@media(min-width:900px){
  .ztitle__rail{max-width:none;margin:0}
}
/* Прежде здесь стояло `.ztitle__score{display:none}` — наследство оформления,
   в котором крупной сводной не было. Правило шло ниже объявления и гасило её
   насмерть: разметка с числом отдавалась, но не отрисовывалась ни на одной
   ширине. Проверено в браузере на боевом домене: 7.6 присутствовало в DOM и
   имело нулевой размер. */
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
/* Без `max-height`. Заголовок «Смотреть» — это h2 с полями браузера по
   умолчанию и размером 1.5em от 30px родителя; в сорокапиксельную коробку он
   не влезал и печатался поверх плеера — видно на снимке владельца. Высоту
   теперь задаёт сам заголовок, а его поля обнулены явно. */
.zpl[data-b08="player"] .zpl__h{margin:0 0 16px}
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
.zpl__h h2{margin:0;font-size:inherit;font-weight:inherit;line-height:1.2}
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
.zeps a[data-off],.zeps [data-off]{opacity:.4;pointer-events:none;cursor:default}
.zeps__off{user-select:none}
.zeps a:focus-visible{outline:2px solid var(--a-acc);outline-offset:2px}
.zsea__h{display:flex;justify-content:space-between;gap:10px;margin:0 0 10px;flex-wrap:wrap}
.zepnav{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0}
.zepnav a{background:var(--a-alt);border-radius:10px;padding:8px 12px;font-size:13px;color:var(--a-acc);font-weight:700;min-height:44px}
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
/* B14: планшет — две колонки, рабочий стол — четыре, как в паспорте блока.
   Порог рабочего стола — 1024px, а не 1100: 1024 входит в список ширин B15 как
   десктопная, и при пороге 1100 она получала планшетную раскладку, то есть
   паспортная полоса высоты 220–300 на ней формально не применялась ни к чему. */
@media(min-width:768px){.zft__cols{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(min-width:1024px){.zft__cols{grid-template-columns:repeat(4,minmax(0,1fr))}}
.zft__col{display:flex;flex-direction:column;gap:6px;min-width:0}
.zft__col b{color:var(--a-ink);font-size:13px;margin:0 0 4px}
.zft__col a{color:var(--a-acc);font-weight:500;font-size:13px;min-height:32px;
display:inline-flex;align-items:center;width:fit-content}
.zft__row{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:10px 18px}
/* B15: три строки, а не четыре. В четырёхколоночной раскладке на 1024px
   колонка узкая, текст переносился на четыре строки и подвал вырастал до
   314px при паспортных 220–300. На мобильной раскладке было три и раньше. */
.zft__about{font-size:13px;color:var(--a-dim);line-height:1.4;margin:0;max-width:62ch;
display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.zft__nav{display:flex;flex-wrap:wrap;gap:6px 14px;align-items:center}
.zft__nav a{font-size:13px;color:var(--a-dim);font-weight:600;min-height:36px;display:inline-flex;align-items:center}
.zft__nav a:hover{color:var(--a-acc)}
.zft__contact:empty,.zft__legal:empty{display:none}
@media(max-width:767px){.zft__cols{grid-template-columns:1fr 1fr}.zft__about{width:100%;-webkit-line-clamp:3}}
@media(max-width:479px){.zft__cols{grid-template-columns:1fr}}
.zft__bar{display:flex;justify-content:space-between;gap:12px;align-items:center;
padding-top:6px;border-top:1px solid var(--a-line);font-size:12px;color:var(--a-mute);flex-wrap:wrap}
/* Правило .zvb здесь не нужно: нижний бар Animedia не печатает версию и
   коммит — знак сборки в подвале был дефектом B14. */
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
    "animedia": {
        "вид": "animedia",
        "токены": АНИМЕДИА_ТОКЕНЫ,
        "стиль": lambda: _общее(АНИМЕДИА_ТОКЕНЫ) + _подставить(АНИМЕДИА_СТИЛЬ, АНИМЕДИА_ТОКЕНЫ),
        # Навигация обязательного каркаса. Каждый пункт ведёт на страницу с
        # содержимым: пункт, открывающий пустой раздел или объяснение про
        # неподключённый источник, хуже отсутствующего пункта.
        # «Типы» из меню убраны: отбор по типу живёт в фильтре каталога, где
        # он и применяется, а страница /types/ остаётся на месте и по прямой
        # ссылке открывается — пункт меню ей не нужен.
        "нав": [("/", "Главная"), ("/catalog/", "Каталог"),
                ("/new/", "Новое"),
                ("/collections/", "Подборки"),
                ("/schedule/", "Расписание"),
                ("/genres/", "Жанры"),
                ("/lists/", "Моё аниме"),
                ("/top/", "Топ")],
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


#: Навигация «Смотреть по жанрам» на главной базу. Коды — из sidecar genre_codes
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
    источник записан под `mdl` или `mali`: 5 883 на базу и 2 511 на Animedia.
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

    Измерено на соседней витрине 2026-09-18: каталог 20:45 опередил details
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


#: Маячок реального запуска воспроизведения.
#:
#: Открытие страницы просмотром не считается — и это не формальность: по
#: открытиям «популярным» становится то, на что чаще нажимают в ленте, а не
#: то, что смотрят. Поэтому событие шлёт сам плеер: он присылает `timeupdate`
#: только когда картинка пошла. Один маячок на открытие страницы; повторы того
#: же зрителя за сутки отсекает сервер.
СКРИПТ_СОБЫТИЯ_ПРОСМОТРА = (
    "(function(){"
    "var узел=document.querySelector('[data-play-beacon]');if(!узел)return;"
    "var ид=узел.getAttribute('data-play-beacon');if(!ид)return;"
    "var послано=false;"
    "function послать(){if(послано)return;послано=true;"
    "try{var т=new FormData();т.append('id',ид);"
    "if(navigator.sendBeacon){navigator.sendBeacon('/event/play',"
    "new Blob(['id='+encodeURIComponent(ид)],"
    "{type:'application/x-www-form-urlencoded'}));}"
    "else{var x=new XMLHttpRequest();x.open('POST','/event/play',true);"
    "x.setRequestHeader('Content-Type','application/x-www-form-urlencoded');"
    "x.send('id='+encodeURIComponent(ид));}}catch(e){}}"
    "window.addEventListener('message',function(e){"
    "if(!e.origin||e.origin.indexOf('cdnvideohub')<0)return;"
    "var d=e.data;try{if(typeof d==='string')d=JSON.parse(d);}catch(err){return;}"
    "if(!d||!d.eventType)return;"
    "if(d.eventType==='timeupdate'||d.eventType==='started')послать();});"
    "})();"
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
#: показало массовый отказ hotlink с cdnvideohub. базу/базу сохраняют
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
    if ключ in _ПОСТЕР_НЕГАТИВ and сейчас - _ПОСТЕР_НЕГАТИВ[ключ] < ПОСТЕР_НЕГАТИВ_СЕК:
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
        # Обрыв связи или таймаут — не ответ «такого постера нет». Раньше
        # и то и другое помнилось пять минут, и одна секунда сетевой икоты
        # гасила картинку всем посетителям на это время. Измерено на холодном
        # запуске под нагрузкой: 27 постеров из выдачи пропали именно так.
        # Временная неудача остывает быстро, отказ источника — долго.
        _ПОСТЕР_НЕГАТИВ[ключ] = сейчас - (ПОСТЕР_НЕГАТИВ_СЕК - ПОСТЕР_ОБРЫВ_СЕК)
        return 504, b"", "text/plain"


#: Сколько помнить отказ источника и сколько — обрыв связи.
ПОСТЕР_НЕГАТИВ_СЕК = 300
ПОСТЕР_ОБРЫВ_СЕК = 10

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


#: Только Animedia: на узком экране пункты меню открываются кнопкой.
#: Escape и повторный клик закрывают; focus возвращается на кнопку;
#: body scroll блокируется, пока меню открыто.
СКРИПТ_АНИМЕДИА_ТЕМА_BOOT = (
    "(function(){try{var k='animedia-theme',r=document.documentElement,s=localStorage.getItem(k);"
    "var t=(s==='light'||s==='dark')?s:((window.matchMedia&&window.matchMedia('(prefers-color-scheme: dark)').matches)?'dark':'light');"
    "r.setAttribute('data-theme',t);r.style.colorScheme=t;}catch(e){document.documentElement.setAttribute('data-theme','light');}})();"
)

#: Карусель первого экрана: точки-страницы, цикличность и уважение к
#: настройке «меньше движения». Прокрутка и свайп остаются нативными — скрипт
#: только добавляет то, чего без него нет, и при его отсутствии лента
#: по-прежнему листается пальцем, колесом и клавиатурой.
СКРИПТ_КАРУСЕЛИ = (
    "(function(){"
    "function плавно(){try{return !window.matchMedia("
    "'(prefers-reduced-motion: reduce)').matches;}catch(e){return true;}}"
    "function страниц(v){return Math.max(1,Math.ceil(v.scrollWidth/Math.max(1,v.clientWidth)));}"
    "function текущая(v){return Math.round(v.scrollLeft/Math.max(1,v.clientWidth));}"
    "function точки(рамка,v){"
    "var к=рамка.querySelector('[data-rl-dots]');if(!к)return;"
    "var n=страниц(v);if(n<2){к.hidden=true;к.innerHTML='';return;}"
    "к.hidden=false;"
    "if(к.children.length!==n){к.innerHTML='';"
    "for(var i=0;i<n;i++){var b=document.createElement('button');"
    "b.type='button';b.className='zrl__dot';b.setAttribute('data-rl-dot',String(i));"
    "b.setAttribute('aria-label','Страница '+(i+1)+' из '+n);к.appendChild(b);}}"
    "var т=текущая(v);"
    "for(var j=0;j<к.children.length;j++){"
    "к.children[j].setAttribute('aria-current',j===т?'true':'false');}}"
    "function прокрутить(v,куда){"
    "v.scrollTo({left:куда,behavior:плавно()?'smooth':'auto'});}"
    "document.addEventListener('click',function(e){"
    "var t=e.target.closest('[data-rl-dot]');"
    "if(t){var рамка=t.closest('.zrl');var v=рамка&&рамка.querySelector('.zrl__vp');"
    "if(v)прокрутить(v,parseInt(t.getAttribute('data-rl-dot'),10)*v.clientWidth);return;}"
    "var b=e.target.closest('[data-rl]');if(!b)return;"
    "var v=document.getElementById(b.getAttribute('aria-controls'));if(!v)return;"
    "var шаг=Math.max(160,Math.round(v.clientWidth*0.86));"
    "var предел=v.scrollWidth-v.clientWidth-2;"
    "var вперёд=b.getAttribute('data-rl')==='next';"
    "var цель=вперёд?v.scrollLeft+шаг:v.scrollLeft-шаг;"
    "var перескок=false;"
    "if(вперёд&&v.scrollLeft>=предел){цель=0;перескок=true;}"
    "else if(!вперёд&&v.scrollLeft<=2){цель=предел;перескок=true;}"
    # Перескок с конца в начало — мгновенный. Плавная прокрутка через всю
    # ленту спорит с обязательной привязкой (scroll-snap: mandatory) и
    # обрывается на середине: измерено, лента останавливалась где попало.
    "v.scrollTo({left:цель,behavior:(перескок||!плавно())?'auto':'smooth'});});"
    # Клавиатура. Полоса прокрутки с tabindex листается стрелками и так, но
    # шагом в несколько пикселей: попасть на соседний постер этим нельзя.
    # Здесь шаг тот же, что у кнопок, плюс Home/End на края ленты.
    "document.addEventListener('keydown',function(e){"
    "var v=e.target;if(!v||!v.classList||!v.classList.contains('zrl__vp'))return;"
    "var шаг=Math.max(160,Math.round(v.clientWidth*0.86));"
    "var предел=v.scrollWidth-v.clientWidth;var цель=null;"
    "if(e.key==='ArrowRight')цель=Math.min(предел,v.scrollLeft+шаг);"
    "else if(e.key==='ArrowLeft')цель=Math.max(0,v.scrollLeft-шаг);"
    "else if(e.key==='Home')цель=0;"
    "else if(e.key==='End')цель=предел;"
    "else return;"
    "e.preventDefault();прокрутить(v,цель);});"
    "function обновить(){var р=document.querySelectorAll('.zrl');"
    "for(var i=0;i<р.length;i++){var v=р[i].querySelector('.zrl__vp');"
    "if(v)точки(р[i],v);}}"
    "document.addEventListener('scroll',function(e){"
    "var v=e.target;if(!v||!v.classList||!v.classList.contains('zrl__vp'))return;"
    "var рамка=v.closest('.zrl');if(рамка)точки(рамка,v);},true);"
    "window.addEventListener('resize',обновить);"
    "if(document.readyState!=='loading')обновить();"
    "else document.addEventListener('DOMContentLoaded',обновить);"
    "})();"
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
    # Смайлики формы сообщения. Вставка — обычный текст в поле: ни разметки,
    # ни HTML посетитель через панель не передаёт. Знак встаёт на место
    # курсора, а не в конец, и курсор остаётся после вставленного.
    # Страницы ленты новых серий. Переключение на месте: страница не
    # перезагружается и не прыгает вверх, выбор уезжает в адрес через
    # replaceState и потому переживает обновление браузера. Без скрипта
    # кнопки остаются обычными ссылками и работают перезагрузкой.
    "var ep=e.target.closest('[data-eps-page]');"
    "if(ep){if(ep.getAttribute('aria-disabled')==='true'){e.preventDefault();return;}"
    "e.preventDefault();var н=ep.getAttribute('data-eps-page');"
    "var сек=ep.closest('.ahome-eps');if(!сек)return;"
    "сек.querySelectorAll('[data-eps-panel]').forEach(function(p){"
    "p.hidden=(p.getAttribute('data-eps-panel')!==н);});"
    "сек.querySelectorAll('[data-eps-page]').forEach(function(a){"
    "var сам=a===ep;a.classList.toggle('is-on',сам);"
    "if(сам)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});"
    "сек.setAttribute('data-eps-current',н);"
    "try{var u=new URL(window.location.href);u.searchParams.set('eps',н);"
    "u.hash='';history.replaceState(null,'',u.pathname+u.search);}catch(err){}"
    "return;}"
    # Дни расписания. Переключение без перезагрузки; при выключенном
    # JavaScript видимым остаётся текущий день — он же открыт по умолчанию.
    "var sd=e.target.closest('[data-day]');"
    "if(sd){var д=sd.getAttribute('data-day');"
    "document.querySelectorAll('[data-day]').forEach(function(t){"
    "t.setAttribute('aria-selected',t===sd?'true':'false');});"
    "document.querySelectorAll('.asch__day').forEach(function(p){"
    "p.hidden=(p.id!=='sch-day-'+д);});return;}"
    "var et=e.target.closest('[data-emoji-toggle]');"
    "if(et){var box=et.parentElement,p=box.querySelector('.aemo__panel');"
    "var on=p.hidden;p.hidden=!on;et.setAttribute('aria-expanded',on?'true':'false');"
    "return;}"
    "var eb=e.target.closest('[data-emoji]');"
    "if(eb){var f=eb.closest('form');var ta=f&&f.querySelector('textarea');"
    "if(ta){var z=eb.getAttribute('data-emoji');"
    "var a=ta.selectionStart==null?ta.value.length:ta.selectionStart;"
    "var b=ta.selectionEnd==null?a:ta.selectionEnd;"
    "ta.value=ta.value.slice(0,a)+z+ta.value.slice(b);"
    "var к=a+z.length;try{ta.setSelectionRange(к,к);}catch(err){}ta.focus();}"
    "return;}"
    "if(!e.target.closest('[data-emoji-picker]')){"
    "document.querySelectorAll('[data-emoji-picker]').forEach(function(x){"
    "var p=x.querySelector('.aemo__panel'),t=x.querySelector('[data-emoji-toggle]');"
    "if(p&&!p.hidden){p.hidden=true;if(t)t.setAttribute('aria-expanded','false');}});}"
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

    def главная(self, зпр: dict | None = None) -> str:
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
    # Исключение жанра: «фэнтези, но без ужасов» — обычный запрос, и без
    # него панель фильтров умеет только сужать в одну сторону.
    исключить = (зпр.get("exclude") or [None])[0]
    if исключить:
        ключи = [исключить, нормализовать(исключить), нормализовать(транслит(исключить))]
        запрещённые = None
        for ключ in ключи:
            if ключ and (запрещённые := индекс["genre"].get(ключ)) is not None:
                break
        if запрещённые is None:
            неизвестный_фильтр = True
            набор = []
        else:
            вне = set(запрещённые)
            набор = [з for з in набор if з["slug"] not in вне]
    # Порог оценки. Записи без оценки под порог не подставляются нулём —
    # «нет оценки» и «оценка ноль» разные утверждения, и вторым нельзя
    # отвечать на вопрос про первое: они просто не проходят порог.
    порог = (зпр.get("rating") or [None])[0]
    if порог:
        try:
            число = float(str(порог).replace(",", "."))
        except (TypeError, ValueError):
            неизвестный_фильтр = True
            набор = []
        else:
            набор = [з for з in набор if float(з.get("_rating") or 0.0) >= число]
    # Незавершённые: доступно серий меньше, чем заявлено.
    онгоинг = (зпр.get("ongoing") or [None])[0]
    if онгоинг:
        if str(онгоинг) not in ("1", "0"):
            неизвестный_фильтр = True
            набор = []
        elif str(онгоинг) == "1":
            набор = [з for з in набор if з.get("_ongoing")]
        else:
            набор = [з for з in набор if not з.get("_ongoing")]
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
               "type": тип, "sort": сорт, "exclude": исключить,
               "rating": порог, "ongoing": онгоинг}
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

    Измерено на соседней витрине: у сериала `avail=3`, `eps=9` страница
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


# ---------------------------- базу -----------------------------------


class ВидОснова(Вид):
    """Боковая колонка, шрифт с засечками, карточки-строки, баннер на тайтле.

    Совпадений с базу здесь нет ни в композиции, ни в типографике, ни в
    геометрии карточки, ни в раскладке страницы произведения. Общими остались
    только данные и механика маршрутов — то есть ровно то, что у семейств и
    обязано быть общим.
    """

    кл_состояния = "zpl__s"

    def _подвал_зона(self) -> str:
        """Footer: brand, real sections, genre links, compact базу marker."""
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
            f'<div class="zft__bar"><span class="zvb">базу {html.escape(ВЕРСИЯ)} · '
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
                f'<div class="zrl__dots" data-rl-dots aria-label="Страницы ленты"'
                f' hidden></div>'
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
    def главная(self, зпр: dict | None = None) -> str:
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
            '<section class="zsec zsec--seo"><h2 class="zh zh--sm">Каталог базу</h2>'
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

        База собирает её классами `grid`/`sec`/`card` — это оформление базу.
        У базу и Animedia таких правил нет, поэтому сетка разворачивалась в
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

    def _ключ_посетителя(self) -> str:
        """Обезличенный ключ посетителя: cookie, иначе адрес соединения.

        Учётных записей у витрины нет, и выдумывать их нельзя. Но «один голос
        от одного посетителя» без какого-то ключа не сделать, поэтому берётся
        cookie, а при её отсутствии — адрес. Ни то, ни другое не хранится: в
        файл уходит только отпечаток.
        """
        куки = getattr(self, "_куки_посетителя", "") or ""
        if not куки:
            обработчик = getattr(self, "_обработчик", None)
            куки = getattr(обработчик, "_куки_посетителя", "") or ""
        if куки:
            return куки
        адрес = ""
        заголовки = getattr(self, "_заголовки_запроса", None)
        if заголовки is not None:
            адрес = (заголовки.get("X-Forwarded-For") or "").split(",")[0].strip()
        return адрес or getattr(self, "_адрес_клиента", "") or "гость"

    def _csrf_поле(self) -> str:
        """Скрытое поле формы с токеном двойной отправки.

        Токен берётся у обработчика запроса, а не считается здесь заново:
        обработчик знает куку, которую он сам же и выдал этим ответом, а вид
        — только ту, что пришла. У первого посетителя куки во входящем
        запросе ещё нет, и вид без обработчика вернул бы пустой токен, то
        есть форму, которую сервер потом отвергнет.
        """
        обработчик = getattr(self, "_обработчик", None)
        токен = ""
        if обработчик is not None and hasattr(обработчик, "_csrf"):
            токен = обработчик._csrf()
        if not токен:
            кука = getattr(self, "_куки_посетителя", "") or ""
            if кука:
                токен = hashlib.sha256(
                    ("animedia-community-csrf/1:" + кука).encode("utf-8")
                ).hexdigest()[:32]
        return (f'<input type="hidden" name="csrf" value="{html.escape(токен)}">'
                if токен else "")

    #: Что показать после отправки формы. Ключ — значение `?community=`,
    #: которым обработчик отвечает на POST. Молчание после сохранения — это
    #: интерфейс, по которому нельзя понять, применилось действие или нет.
    СООБЩЕНИЯ_СООБЩЕСТВА = {
        "ok": ("ok", "Сохранено."),
        "vote-ok": ("ok", "Оценка сохранена. Она ставится один раз и не меняется."),
        "voted": ("warn", "Оценка уже стоит и не меняется — она ставится один раз."),
        "pending": ("ok", "Сообщение отправлено и появится в ленте после проверки. "
                          "Пока оно видно только вам."),
        "error": ("err", "Не удалось сохранить."),
        "unavailable": ("err", "Раздел сейчас недоступен: сохранить не получится."),
        # Отказ по токену. Молчаливое «ничего не произошло» посетитель читает
        # как поломку формы и повторяет отправку; здесь сказано, что делать.
        "csrf": ("err", "Форма устарела — обновите страницу и повторите."),
    }

    def _итог_сообщества(self) -> str:
        """Полоса итога последней отправки — успех, отказ или ошибка."""
        зпр = getattr(self, "_зпр", None) or {}
        код = ((зпр.get("community") or [""])[0] or "").strip()
        что = self.СООБЩЕНИЯ_СООБЩЕСТВА.get(код)
        if что is None:
            return ""
        вид, текст = что
        if код == "error":
            почему = ((зпр.get("why") or [""])[0] or "").strip()
            if почему:
                текст = f"Не удалось сохранить: {почему}"
        elif код in ("voted", "vote-ok"):
            моя = ((зпр.get("mine") or [""])[0] or "").strip()
            if моя.isdigit():
                текст = (f"Ваша оценка: {моя}. "
                         "Оценка ставится один раз и не меняется.")
        роль = "alert" if вид == "err" else "status"
        return (f'<p class="acomm__flash acomm__flash--{вид}" role="{роль}" '
                f'data-community-result="{html.escape(код)}">{html.escape(текст)}</p>')

    def _код_жанра(self, имя: str) -> str:
        """Код жанра по его русскому имени — тот же, по которому идёт отбор.

        Сначала ищем в указателе (там имя и код уже связаны снимком), затем
        считаем код тем же правилом, каким его считает построение указателя.
        Придумывать третий вид кода нельзя: ссылка ушла бы в пустую выдачу.
        """
        цель = имя.strip().casefold()
        for код, подпись in (self.индекс.get("genre_names") or []):
            if str(подпись).strip().casefold() == цель:
                return код
        return нормализовать(транслит(имя))

    def _ссылка_факта(self, текст: str, адрес: str, *, годен: bool) -> str:
        """Значение факта: ссылка, если переход осмыслен, иначе просто текст."""
        if not годен:
            return html.escape(текст)
        return (f'<a href="{html.escape(закодировать_запрос(адрес), quote=True)}">'
                f'{html.escape(текст)}</a>')

    def _маячок_просмотра(self, деталь: dict) -> str:
        """Узел и скрипт, отправляющие событие реального запуска плеера."""
        ид = str((деталь or {}).get("id") or "").strip()
        if not ид:
            return ""
        return (f'<span data-play-beacon="{html.escape(ид)}" hidden></span>'
                f'<script>{СКРИПТ_СОБЫТИЯ_ПРОСМОТРА}</script>')

    def _смайлики(self) -> str:
        """Панель смайликов формы сообщения.

        Вставка — обычный текст в поле, поэтому ничего в обработке не меняется:
        сообщение по-прежнему экранируется на выводе, проходит проверку длины,
        антиспам и премодерацию. Никакой разметки посетитель через панель не
        передаёт — кнопки подставляют ровно один знак.

        Панель раскрывается по нажатию и по умолчанию свёрнута: шестнадцать
        кнопок под каждым полем ввода — это шум, а не помощь.
        """
        кнопки = "".join(
            f'<button type="button" class="aemo__b" data-emoji="{html.escape(знак)}" '
            f'title="{html.escape(имя)}" tabindex="-1">'
            f'<span aria-hidden="true">{html.escape(знак)}</span>'
            f'<span class="vh">{html.escape(имя)}</span></button>'
            for знак, имя in СМАЙЛИКИ)
        return (
            '<div class="aemo" data-emoji-picker>'
            '<button type="button" class="aemo__open" data-emoji-toggle '
            'aria-expanded="false" aria-controls="aemo-panel">Смайлики</button>'
            f'<div class="aemo__panel" id="aemo-panel" hidden>{кнопки}</div>'
            '</div>')

    def освежить_оценки_каталога(self) -> int:
        """Подтянуть `_rating` у записей, за которые голосовали наши зрители.

        Поле `_rating` заполняется при перечитывании снимка и служит ключом
        сортировки «по оценке» и порога «оценка от N». Главный рейтинг от
        внешней базы отличается ТОЛЬКО там, где есть наши голоса: в остальных
        записях это одно и то же число. Значит, освежать весь каталог не нужно
        — достаточно тех тем, где голоса есть.

        Почему не весь: измерено, 7435 вызовов главного рейтинга занимают
        368 мс. Платить их на каждый запрос каталога ради нескольких
        изменившихся записей — плохая сделка. Проголосованных тем на порядки
        меньше, и стоимость растёт вместе с ними, а не с каталогом.

        Без этого сортировка «по оценке» расходилась бы с числами на плитках:
        порядок по одной величине, подписи по другой.
        """
        хранилище = сообщество()
        if хранилище is None or not getattr(хранилище, "доступно", False):
            return 0
        if not hasattr(хранилище, "главный_рейтинг"):
            return 0
        try:
            темы = хранилище._прочитать().get("titles") or {}
        except (OSError, AttributeError):
            return 0
        с_голосами = {ид for ид, з in темы.items()
                      if isinstance(з, dict) and (з.get("votes") or {})}
        if not с_голосами:
            return 0
        освежено = 0
        for з in self.д.items:
            ид = str(з.get("id") or "")
            if ид not in с_голосами and str(з.get("slug") or "") not in с_голосами:
                continue
            r = self.рейтинг(з.get("slug") or "")
            if r and r.get("значение") is not None:
                з["_rating"] = float(r["значение"])
                з["_votes"] = int(r.get("голосов") or 0)
                освежено += 1
        return освежено

    def рейтинг(self, slug: str, деталь: dict | None = None) -> dict | None:
        """Главный рейтинг записи. Одна точка входа на всю витрину.

        Считает модуль, а не шаблон: карточка произведения, обсуждение и
        плитки каталога обязаны показывать ОДНО число, а три независимых
        вычисления одного и того же неизбежно разойдутся. Поэтому здесь нет
        ни формулы, ни округления — только вызов и передача внешних оценок.
        """
        хранилище = сообщество()
        if not slug or хранилище is None or not getattr(хранилище, "доступно", False):
            return None
        if not hasattr(СООБЩЕСТВО, "главный_рейтинг") and not hasattr(
                хранилище, "главный_рейтинг"):
            return None
        деталь = деталь if деталь is not None else (self.деталь(slug) or {})
        try:
            return хранилище.главный_рейтинг(
                тема_сообщества(self.п, slug),
                внешние_для_базы(деталь),
                АНИМЕДИА_ПРИОРИТЕТ_БАЗЫ,
                slug=slug)
        except (OSError, AttributeError):
            return None

    def _состояние_сообщества(self, запись: dict):
        """Хранилище и состояние темы или None, если раздел выключен."""
        хранилище = сообщество()
        if хранилище is None or not getattr(хранилище, "доступно", False):
            return None, None, None
        slug = запись["slug"]
        тема = тема_сообщества(self.п, slug)
        return хранилище, тема, хранилище.состояние(
            тема, self._ключ_посетителя(), slug=slug)

    def _сообщество_выключено(self, запись: dict) -> str:
        хранилище = сообщество()
        причина = ("модуль сообщества не подключён" if хранилище is None
                   else getattr(хранилище, "причина", ""))
        return (
            f'<section class="zsec acomm acomm--off" id="community" '
            f'data-community="unavailable" '
            f'data-community-reason="{html.escape(str(причина)[:120])}">'
            f'<p class="acomm__off">Сейчас нельзя оставить оценку или '
            f'сообщение. Придуманных вместо них здесь не будет: как только '
            f'раздел заработает, тут появятся настоящие отзывы посетителей.</p>'
            f'</section>')

    def панель_действий(self, запись: dict, *, возврат: str = "") -> str:
        """Одна горизонтальная полоса сразу под плеером: оценка и списки.

        Раньше это была двухколоночная коробка с заголовком «Оценки и
        обсуждение», подзаголовками «В список» и «Реакция» и абзацем про
        однократное голосование — и стояла она под всем остальным. Посетитель,
        досмотревший серию, до неё не доходил.

        Здесь ровно то, что делают сразу после просмотра: поставить оценку и
        отметить себе. Пояснение про однократность ушло в подсказку звёзд —
        на экране оно занимало три строки ради правила, которое касается
        одного нажатия.

        Наведение и фокус только ПОКАЗЫВАЮТ предполагаемый выбор — сохраняет
        его явное нажатие. Это не придирка: шкала, ставящая оценку по
        наведению, при правиле «один голос навсегда» превращает случайное
        движение мыши в необратимое действие.

        Подсветка «до наведённой звезды» сделана порядком в разметке, а не
        скриптом: звёзды идут от десятой к первой, а видимый порядок
        разворачивает CSS (`row-reverse`). Тогда `:hover ~ *` — это ровно
        звёзды левее наведённой, и шкала работает при выключенном JavaScript.
        Отсюда и обратный range ниже: менять его местами нельзя, не поменяв
        правило подсветки.

        Проголосовавшему кнопок нет вовсе: сервер всё равно откажет, и
        предлагать нажатие значило бы обещать то, чего интерфейс не держит.
        На их месте — его собственная оценка теми же звёздами.
        """
        хранилище, тема, с = self._состояние_сообщества(запись)
        if с is None:
            return ""
        slug = запись["slug"]
        путь = возврат or f"/title/{slug}/"
        проголосовал = с.мой_голос is not None

        if проголосовал:
            шкала = "".join(
                '<span class="astar__s' + (' is-on' if n <= с.мой_голос else '') + '">'
                + звезда_svg() + '</span>'
                for n in range(СООБЩЕСТВО.ОЦЕНКА_МИН, СООБЩЕСТВО.ОЦЕНКА_МАКС + 1))
            оценка = (
                f'<div class="apanel__stars astar astar--fixed" data-stars="panel" '
                f'data-my-vote="{с.мой_голос}" data-vote-locked="1">'
                f'<div class="astar__row" role="img" '
                f'aria-label="Ваша оценка {с.мой_голос} из 10">{шкала}</div>'
                f'<span class="apanel__mine">Ваша оценка: '
                f'<b>{с.мой_голос}</b></span></div>')
        else:
            подсказка = ("Оценка ставится один раз и потом не меняется. "
                         "Наведение только показывает выбор — сохраняет нажатие.")
            кнопки = "".join(
                f'<button class="astar__b" type="submit" name="value" value="{n}" '
                f'title="Оценка {n} из 10">{звезда_svg()}'
                f'<span class="vh">Поставить оценку {n} из 10</span></button>'
                for n in range(СООБЩЕСТВО.ОЦЕНКА_МАКС, СООБЩЕСТВО.ОЦЕНКА_МИН - 1, -1))
            оценка = (
                f'<form class="apanel__stars astar" method="post" '
                f'action="/community/vote" data-stars="panel" data-vote-locked="0">'
                f'{self._csrf_поле()}'
                f'<input type="hidden" name="slug" value="{html.escape(slug)}">'
                f'<input type="hidden" name="back" value="{html.escape(путь)}">'
                f'<div class="astar__row" role="group" title="{html.escape(подсказка)}" '
                f'aria-label="Поставить оценку от 1 до 10. {html.escape(подсказка)}">'
                f'{кнопки}</div></form>')

        списки = "".join(
            f'<button class="acomm__list-btn{" is-on" if с.мой_список == ключ else ""}" '
            f'type="submit" name="list" value="{ключ if с.мой_список != ключ else ""}" '
            f'aria-pressed="{"true" if с.мой_список == ключ else "false"}">'
            f'{html.escape(подпись)}</button>'
            for ключ, подпись in СООБЩЕСТВО.СПИСКИ)
        return (
            f'<section class="apanel" data-actions="1" '
            f'data-voted="{"1" if проголосовал else "0"}">'
            f'{оценка}'
            f'<form class="apanel__lists" method="post" action="/community/list" '
            f'data-lists-widget="1" aria-label="Списки">'
            f'{self._csrf_поле()}'
                f'<input type="hidden" name="slug" value="{html.escape(slug)}">'
            f'<input type="hidden" name="back" value="{html.escape(путь)}">'
            f'{списки}</form></section>')

    def полоса_реакций(self, запись: dict, *, возврат: str = "") -> str:
        """Реакции одной полосой во всю ширину: крупный значок, счёт под ним."""
        хранилище, тема, с = self._состояние_сообщества(запись)
        if с is None:
            return ""
        slug = запись["slug"]
        путь = возврат or f"/title/{slug}/"
        кнопки = "".join(
            f'<button class="areact{" is-on" if с.моя_реакция == р else ""}" '
            f'type="submit" name="reaction" value="{html.escape(р)}" '
            f'title="{html.escape(р)}" '
            f'aria-pressed="{"true" if с.моя_реакция == р else "false"}">'
            f'{значок_реакции(р)}'
            f'<b data-reaction-count="{с.реакции.get(р, 0)}">{с.реакции.get(р, 0)}</b>'
            f'<span class="vh">{html.escape(р)}</span></button>'
            for р in СООБЩЕСТВО.РЕАКЦИИ)
        return (
            f'<form class="areacts" method="post" action="/community/reaction" '
            f'data-reactions="1" aria-label="Реакции">'
            f'{self._csrf_поле()}'
                f'<input type="hidden" name="slug" value="{html.escape(slug)}">'
            f'<input type="hidden" name="back" value="{html.escape(путь)}">'
            f'{кнопки}</form>')

    def блок_обсуждения(self, запись: dict, *, возврат: str = "") -> str:
        """Комментарии отдельным блоком: форма, панель смайликов, лента."""
        хранилище, тема, с = self._состояние_сообщества(запись)
        if с is None:
            return self._сообщество_выключено(запись)
        slug = запись["slug"]
        путь = возврат or f"/title/{slug}/"

        def строка_сообщения(к: dict) -> str:
            ждёт = str(к.get("status") or "") == СООБЩЕСТВО.СТАТУС_ОЖИДАЕТ
            метка = ('<span class="acomm__pending">на проверке</span>'
                     if ждёт else "")
            классы = "acomm__item" + (" acomm__item--pending" if ждёт else "")
            дата = str(к.get("created_at") or "")
            имя_автора = str(к.get("name") or "Гость")
            return (
                f'<li class="{классы}" data-comment-status='
                f'"{html.escape(str(к.get("status") or "approved"))}">'
                f'{аватар(имя_автора)}'
                f'<div class="acomm__body">'
                f'<div class="acomm__item-h">'
                f'<span class="acomm__name">{html.escape(имя_автора)}</span>'
                f'<time class="acomm__date" datetime="{html.escape(дата)}">'
                f'{html.escape(_аниме_формат_времени_анонса(дата, "datetime"))}'
                f'</time>{метка}</div>'
                f'<p class="acomm__text">{html.escape(str(к.get("text") or ""))}</p>'
                f'</div></li>')

        лента = "".join(строка_сообщения(к) for к in с.комментарии[:20])
        пусто = ('<p class="acomm__none">Обсуждения пока нет. '
                 'Ваше сообщение появится здесь после проверки.</p>')
        список_сообщений = (f'<ul class="acomm__list">{лента}</ul>' if лента else пусто)
        форма = (
            f'<form class="acomm__form" method="post" action="/community/comment">'
            f'{self._csrf_поле()}'
                f'<input type="hidden" name="slug" value="{html.escape(slug)}">'
            f'<input type="hidden" name="back" value="{html.escape(путь)}">'
            f'<div class="acomm__field acomm__field--name">'
            f'<label for="acomm-name">Имя</label>'
            f'<input id="acomm-name" name="name" maxlength="40" placeholder="Гость"></div>'
            f'<div class="acomm__field">'
            f'<label for="acomm-text">Сообщение</label>'
            f'<textarea id="acomm-text" name="text" rows="3" required '
            f'maxlength="{СООБЩЕСТВО.ДЛИНА_КОММЕНТАРИЯ}" '
            f'placeholder="Что скажете об этом аниме?"></textarea>'
            f'{self._смайлики()}</div>'
            f'<button class="acomm__send" type="submit">Отправить</button>'
            f'<p class="acomm__hint">Сообщения проходят проверку и появляются '
            f'в общей ленте после неё.</p></form>')
        return (
            f'<section class="zsec acomm" id="community" data-community="on" '
            f'data-community-votes="{с.голосов}" '
            f'data-community-comments="{len(с.комментарии)}" '
            f'data-community-slug="{html.escape(slug)}" '
            f'data-my-list="{html.escape(с.мой_список or "")}">'
            f'<h2 class="zh zh--sm">Обсуждение</h2>'
            f'{self._итог_сообщества()}'
            f'<div class="acomm__talk">{форма}'
            f'<div class="acomm__list-wrap">{список_сообщений}</div></div>'
            f'</section>')

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
АНИМЕДИА_ЭПИЗОД_ЗАГОЛОВОК = "Новые серии"
АНИМЕДИА_ЭПИЗОД_EMPTY_COPY = (
    "Лента новых серий пока недоступна: источник событий ещё не подключён"
)
#: Собственный реестр событий «стало больше доступных серий». Он выводится
#: сравнением соседних снимков подробностей и потому говорит ровно то, что
#: знает: не «вышла серия N», а «стало доступно N серий». Номер серии, которого
#: в данных нет, здесь не появляется.
#
#: Файл лежит рядом со снимком каталога, а не в репозитории. Путь от `__file__`
#: в боевом релизе указывает внутрь неизменяемого каталога релиза — туда, где
#: данных нет и быть не может; витрина искала реестр там и молча показывала
#: пустую ленту. Снимки же лежат в корне рантайма, читаются пользователем
#: витрины и обновляются без пересборки релиза — реестру место там же.
АНИМЕДИА_EPISODE_LEDGER_PATH = os.environ.get(
    "ANIMEDIA_EPISODE_LEDGER",
    str(_КОРЕНЬ_РАНТАЙМА / f"{САЙТ_ID}-episode-events.json"),
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
АНИМЕДИА_CATALOG_ADDED_H1 = "Недавно добавленные"
АНИМЕДИА_CATALOG_ADDED_EMPTY = (
    "Пока нечего показать — вернитесь чуть позже"
)
CATALOG_FRESHNESS_DATA_GAP = 1
АНИМЕДИА_CATALOG_ADDED_HOME_LIMIT = 18
#: Сколько записей показывает раздел «Недавно добавленные» на своей странице.
АНИМЕДИА_CATALOG_ADDED_PAGE_LIMIT = 48

#: Доля каталога, начиная с которой одинаковая отметка времени перестаёт быть
#: датой добавления конкретной записи и становится следом массовой загрузки.
#:
#: Зачем порог вообще. В живом снимке 4003 записи из 7426 несут одну и ту же
#: метку `2024-11-12T12:20:11Z` — это не день, когда добавили четыре тысячи
#: произведений, а момент первичного импорта. Ровно из-за неё раздел новинок
#: когда-то отключили целиком: сортировка по этому полю выносила наверх
#: случайную часть импорта. Но отключать пришлось не поле, а когорту: у
#: остальных 3423 записей метки различны, идут по одной-две в день и
#: описывают настоящие поступления. Их и показываем.
#:
#: Порог задан долей, а не числом: он должен работать и на каталоге в сто
#: записей, и на каталоге в сто тысяч.
АНИМЕДИА_ДОЛЯ_МАССОВОЙ_МЕТКИ = 0.01


def массовые_метки(записи, доля: float = АНИМЕДИА_ДОЛЯ_МАССОВОЙ_МЕТКИ) -> set:
    """Отметки времени, которые повторяются слишком часто, чтобы быть датой.

    Возвращается множество таких меток. Пустое множество — законный ответ:
    в каталоге без массового импорта отбрасывать нечего.
    """
    записи = list(записи)
    if not записи:
        return set()
    порог = max(2, int(len(записи) * доля))
    счёт: dict = {}
    for з in записи:
        метка = str(з.get("published_at") or "")
        if метка:
            счёт[метка] = счёт.get(метка, 0) + 1
    return {метка for метка, n in счёт.items() if n >= порог}


def недавно_добавленные(записи, предел: int = 0) -> list:
    """Записи в порядке добавления в каталог, начиная с самой свежей.

    Год выхода произведения сюда не примешивается: сортировка идёт по дате
    добавления и только по ней, а при равных датах — стабильным вторым ключом
    из модуля хронологии, иначе одна и та же карточка прыгала бы между
    страницами при листании.
    """
    массовые = массовые_метки(записи)
    отобранные = [з for з in записи
                  if з.get("published_at") and str(з["published_at"]) not in массовые]
    if ХРОНОЛОГИЯ is not None:
        отобранные = ХРОНОЛОГИЯ.по_добавлению(отобранные)
    else:  # модуль хронологии не подключён — порядок всё равно по дате
        отобранные.sort(key=lambda з: (str(з.get("published_at")), з.get("slug") or ""),
                        reverse=True)
    return отобранные[:предел] if предел else отобранные
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

#: Топ по сводной оценке. Отдельный файл и отдельное основание: популярность
#: сюда не примешивается, и подменить ею пробел «Топ‑100» нельзя даже случайно.
АНИМЕДИА_ТОП_ПО_ОЦЕНКАМ_ПУТЬ = os.environ.get(
    "ANIMEDIA_RATINGS_TOP",
    str(_КОРЕНЬ_РАНТАЙМА / "{site}-ratings-top.json"),
)


def загрузить_топ_по_оценкам(*, site_id: str = "",
                             path: str | Path | None = None) -> dict | None:
    """Готовый топ по оценкам или None, если его ещё не собирали.

    Отсутствие файла — обычное состояние, а не ошибка: топ собирается
    отдельным инструментом по снимку, и до первого запуска его просто нет.
    Витрина в этом случае не показывает блок вовсе — пустая полка под
    заголовком хуже отсутствия полки.
    """
    шаблон = str(path or АНИМЕДИА_ТОП_ПО_ОЦЕНКАМ_ПУТЬ)
    сайт = site_id or САЙТ_ID
    путь = Path(шаблон.replace("{site}", сайт))
    if not путь.is_file():
        return None
    try:
        сырое = json.loads(путь.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(сырое, dict) or not isinstance(сырое.get("places"), list):
        return None
    if сырое.get("basis") != "ratings-aggregate":
        # Файл с другим основанием под этим именем — не наш случай; молча
        # показывать его как «лучшее по оценкам» нельзя.
        return None
    return сырое
#: Сколько каталожных лент показывает главная. Было два, и страница выходила
#: втрое короче оригинала при двенадцати лентах, обеспеченных данными, —
#: это и есть «пустая витрина», которую видел владелец. Восемь набирают
#: объём оригинала настоящими записями, без выдуманных блоков; ленты
#: без данных по-прежнему не рисуются вовсе.
#: Сколько тематических полок показывает главная.
#: Было восемь: страница уходила на семь с половиной тысяч пикселей, и до
#: отбора с сеткой каталога посетитель просто не доходил. У оригинала между
#: лентой первого экрана и сеткой стоит несколько полок, а не весь каталог,
#: разложенный по жанрам.
АНИМЕДИА_HOME_MAX_CATALOG_SHELVES = 4
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
#: Снимок популярности лежит рядом с каталогом, а не внутри релиза.
#: Путь от `__file__` указывал внутрь неизменяемого каталога выпуска — туда,
#: где обновляемым данным взяться неоткуда: снимок нельзя было бы освежить, не
#: пересобрав интерфейс. Ровно та же ошибка уже была у реестра серий.
АНИМЕДИА_WEEKLY_POPULAR_PATH = os.environ.get(
    "ANIMEDIA_WEEKLY_POPULAR_SNAPSHOT",
    str(_КОРЕНЬ_РАНТАЙМА / f"{САЙТ_ID}-popular.json"),
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
    # Ключом снимка может быть и постоянный идентификатор записи, и её адрес.
    # Постоянный вернее: адрес меняется при переименовании, и тогда позиция
    # молча выпадала бы из ленты. Адрес остаётся понятным запасным вариантом.
    by_slug = {з.get("slug"): з for з in items if з.get("slug")}
    by_id: dict[str, dict] = {}
    for з in items:
        for поле in ("id", "canonical_title_id", "title_id"):
            ключ = str(з.get(поле) or "").strip()
            if ключ:
                by_id.setdefault(ключ, з)
    видели: set[str] = set()
    out = []
    for ключ in approved.get("slugs") or []:
        ключ = str(ключ or "").strip()
        з = by_id.get(ключ) or by_slug.get(ключ)
        if з is None or з.get("slug") in видели:
            continue
        видели.add(з.get("slug"))
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



class ВидАнимедиа(ВидОснова):
    """Аниме-портал: светлая основа, плотная сетка, свои разделы.

    От базу наследуется только механика страниц — маршруты, карточка
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
        # совпадают с боевым каталогом базу. То есть вид записи не отличает
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
        """Карточка по единому контракту: постер, бейджи, название, мета.

        Состав определяется вариантом, а не местом вызова, — иначе «похожее
        аниме» и каталог расходятся молча и один из блоков остаётся голыми
        постерами. Именно это владелец и увидел на живых витринах.

        Как у оригинала: слева сверху — сколько серий доступно из заявленных,
        справа сверху — до двух оценок с названным источником, под постером —
        название и строка «тип · год». Размеры постера проставляются в
        разметке, чтобы место было занято до загрузки изображения.
        """
        название = str(запись.get("title") or "").strip()
        адрес = str(запись.get("url") or "").strip()
        if not название or not адрес:
            # Карточка без имени или без адреса карточкой не является: подписать
            # её выдуманным словом значило бы соврать, а показать безымянный
            # прямоугольник — оставить посетителю нерабочую плитку. Запись
            # просто не рисуется.
            return ""
        деталь = self.деталь(запись["slug"])
        состав = АНИМЕДИА_ВАРИАНТЫ_КАРТОЧКИ.get(вариант, АНИМЕДИА_ВАРИАНТ_ПО_УМОЛЧАНИЮ)
        изо = заглушка_постера(запись, "zt__none", "zt__img", 190, 285)

        бейджи = ""
        данные = ""
        if состав["бейджи"]:
            счёт = _счётчик_серий(деталь)
            слева = ""
            if счёт:
                доступно, заявлено = счёт
                слева = (f'<span class="zt__eps" data-eps-avail="{доступно}" '
                         f'data-eps-total="{заявлено}">{доступно} из {заявлено}</span>')
            знак = фирменный_знак_оценки(
                деталь, рейтинг=self.рейтинг(запись["slug"], деталь))
            if слева or знак:
                бейджи = (f'<span class="zt__badges">{слева}{знак}</span>')
        подпись = (f'<span class="zt__t">{html.escape(запись["title"])}</span>'
                   if состав["название"] else "")
        мета = " · ".join(str(ч) for ч in (запись.get("kind"), запись.get("year")) if ч)
        строка_меты = (f'<span class="zt__m">{html.escape(мета)}</span>'
                       if состав["мета"] and мета else "")
        if состав.get("строкой"):
            return self._плитка_строкой(запись, деталь, состав, изо, вариант)
        тело = (f'<span class="zt__b">{подпись}{строка_меты}</span>'
                if (подпись or строка_меты) else "")
        return (f'<a class="zt" data-card-variant="{html.escape(вариант)}"'
                f' href="{запись["url"]}" title="{html.escape(запись["title"])}">'
                f'<span class="zt__p">{изо}{бейджи}</span>{тело}{данные}</a>')

    def _плитка_строкой(self, запись: dict, деталь: dict, состав: dict,
                        изо: str, вариант: str) -> str:
        """Строчная карточка нижнего блока: миниатюра, название, оценка.

        Оригинальное название показывается только если оно есть и отличается от
        основного: строка «то же самое серым» ничего не добавляет. Число
        голосов — рядом с оценкой и только когда источник его прислал.
        """
        оригинальное = str(деталь.get("original_name") or "").strip()
        если_надо = (состав.get("оригинальное") and оригинальное
                     and оригинальное.casefold() != str(запись["title"]).strip().casefold())
        подзаголовок = (f'<span class="zt__orig">{html.escape(оригинальное)}</span>'
                        if если_надо else "")
        мета = " · ".join(str(ч) for ч in (запись.get("kind"), запись.get("year")) if ч)
        строка_меты = (f'<span class="zt__m">{html.escape(мета)}</span>'
                       if состав.get("мета") and мета else "")
        строка_оценки = фирменный_знак_оценки(
            деталь, строкой=True,
            рейтинг=self.рейтинг(запись.get("slug") or "", деталь))
        return (f'<a class="zt zt--row" data-card-variant="{html.escape(вариант)}"'
                f' href="{запись["url"]}" title="{html.escape(запись["title"])}">'
                f'<span class="zt__p">{изо}</span>'
                f'<span class="zt__b">'
                f'<span class="zt__t">{html.escape(запись["title"])}</span>'
                f'{подзаголовок}{строка_меты}{строка_оценки}</span></a>')

    def карусель(self, ключ: str, набор) -> str:
        """Лента первого экрана — компактная карточка, остальные ленты обычные.

        У оригинала под постером ленты только название; состав карточки задаёт
        вариант контракта, а не правило стиля. Прежде лента рисовала карточку
        каталога, а CSS прятал у неё мету и оценку: разметка обещала одно,
        видно было другое.
        """
        вариант = "compact" if ключ == "hero" else "catalog-title"
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
                f'<div class="zrl__dots" data-rl-dots aria-label="Страницы ленты"'
                f' hidden></div>'
                f'</div>')

    def плитки(self, набор, *, вариант: str = "catalog-title") -> str:
        extra = " zg--recommendation" if вариант == "recommendation" else ""
        if вариант == "related-row":
            extra = " zg--related-row"
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

    def _рейтинги_колонка_b07(self, деталь: dict, slug: str = "") -> str:
        """Колонка «Рейтинг»: одно число, под ним — из чего оно сложилось.

        Считает модуль сообщества, а не шаблон. Здесь нет ни формулы, ни
        весов, ни округления: главный рейтинг обязан совпадать с тем, что
        показывают плитки каталога и обсуждение, а совпадение достигается
        одним расчётом, а не тремя одинаковыми на вид.

        Что видит посетитель сверху вниз: слово «Рейтинг» и число, под ним —
        сколько наших зрителей проголосовало, ниже — внешние источники
        справочной строкой, затем шкала и личная оценка.

        Счётчик считает ТОЛЬКО наши голоса. Вес стартовой оценки живёт в
        формуле и фиктивными голосами не изображается: написать «5 голосов»
        там, где их ноль, значило бы соврать числом, которое посетитель
        принимает за людей.
        """
        внешние = [о for о in оценки_по_источникам(деталь)
                   if not о["пользовательская"]]
        r = self.рейтинг(slug, деталь) if slug else None

        # Справочная строка источников: что именно знают о произведении
        # снаружи. Это не участники расчёта по отдельности — база берётся
        # одна, — но посетителю важно видеть, откуда она вообще взялась.
        база = (r or {}).get("база") or {}
        источник_базы = str(база.get("source") or "")
        подписи = {к: п for к, (п, _ш, _с) in ИСТОЧНИКИ_ОЦЕНОК.items()}
        строки_источников = "".join(
            f'<li data-rating-source="{html.escape(о["ключ"])}"'
            + (' data-base="1"' if о["ключ"] == источник_базы else "")
            + f'><span class="lab">{html.escape(о["подпись"])}</span>'
            f'<span class="val">{html.escape(о["значение"])}</span></li>'
            for о in внешние)
        блок_источников = (
            f'<ul class="ztitle__srcs" aria-label="Оценки внешних источников">'
            f'{строки_источников}</ul>' if строки_источников else "")

        if r is None or r.get("значение") is None:
            число = (f'<span class="ztitle__score-val ztitle__score-val--none">'
                     f'{АНИМЕДИА_ОЦЕНКА_НЕТ}</span>')
            подпись = "Оценок пока нет"
            атрибуты = ' data-rating-state="empty" data-our-votes="0"'
            пояснение = ('<p class="ztitle__hint">Оценку ставят зрители — '
                         'ваша будет первой.</p>')
        else:
            голосов = int(r.get("голосов") or 0)
            показ = f"{float(r['значение']):g}"
            число = (f'<span class="ztitle__score-val">'
                     f'{html.escape(показ)}</span>')
            подпись = "Рейтинг"
            атрибуты = (
                f' data-rating-state="{html.escape(str(r.get("состояние") or ""))}"'
                f' data-rating-formula="{html.escape(str(r.get("формула") or ""))}"'
                f' data-our-votes="{голосов}"'
                + (f' data-base-source="{html.escape(источник_базы)}"'
                   if источник_базы else "")
                + (' data-base-provisional="1"'
                   if r.get("база_предварительная") else ""))
            пояснение = self._пояснение_рейтинга(r, подписи)

        if r and int(r.get("голосов") or 0):
            голосов = int(r["голосов"])
            строка_зрителей = (
                f'<p class="ztitle__ourvotes" data-our-votes="{голосов}">'
                f'<span class="ztitle__ourvotes-n">{голосов} '
                f'{склонение_голосов(голосов)} зрителей</span></p>')
        else:
            строка_зрителей = ('<p class="ztitle__ourvotes" data-our-votes="0">'
                               '<span class="ztitle__ourvotes-n">Зрители ещё '
                               'не голосовали</span></p>')

        расхождение = ""
        if r and r.get("база_разошлась"):
            сейчас = r.get("внешняя_сейчас") or {}
            имя = подписи.get(str(сейчас.get("source") or ""),
                              str(сейчас.get("source") or ""))
            try:
                сейчас_показ = f"{float(сейчас.get('value') or 0):g}"
            except (TypeError, ValueError):
                сейчас_показ = ""
            расхождение = (
                f'<p class="ztitle__drift" data-base-drift="1">'
                f'{html.escape(имя)} сейчас показывает '
                f'{html.escape(сейчас_показ)}. '
                f'Стартовая оценка закреплена и не меняется.</p>')

        return (
            f'<aside class="ztitle__rail" data-b07="ratings">'
            f'<div class="ztitle__score"{атрибуты}>{число}'
            f'<span class="ztitle__score-lab">{html.escape(подпись)}</span></div>'
            f'{строка_зрителей}{пояснение}{расхождение}{блок_источников}</aside>'
        )

    def _пояснение_рейтинга(self, r: dict, подписи: dict) -> str:
        """Короткая подсказка: откуда взялось число и при чём тут стартовая оценка.

        Одна фраза, а не абзац про методику: посетителю нужно понять, почему
        первая же зрительская девятка не превращает рейтинг в девятку, а не
        прочитать описание алгоритма.
        """
        состояние = str(r.get("состояние") or "")
        база = r.get("база") or {}
        имя = подписи.get(str(база.get("source") or ""), str(база.get("source") or ""))
        если_предварительная = r.get("база_предварительная")
        if состояние == "base+votes":
            текст = (f"Считается от стартовой оценки {имя} и голосов зрителей: "
                     f"пока голосов немного, стартовая весит больше.")
        elif состояние == "base-only":
            если_имя = имя.strip()
            if если_предварительная:
                текст = (f"Пока это стартовая оценка {если_имя}: она закрепится "
                         f"с первым голосом зрителей." if если_имя else
                         "Пока это стартовая внешняя оценка: она закрепится "
                         "с первым голосом зрителей.")
            else:
                текст = (f"Пока это стартовая оценка {если_имя}. "
                         f"С голосами зрителей число начнёт меняться."
                         if если_имя else
                         "Пока это стартовая внешняя оценка.")
        elif состояние == "votes-only":
            текст = "Считается только по голосам зрителей: внешней оценки нет."
        else:
            return ""
        return f'<p class="ztitle__hint">{html.escape(текст)}</p>'

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
        rail = self._рейтинги_колонка_b07(деталь, запись.get("slug") or "")
        orig = html.escape(str(деталь.get("original_name") or деталь.get("original_title") or ""))
        orig_html = f'<p class="ztitle__o">{orig}</p>' if orig else ""
        # Жанры — настоящие ссылки в каталог, а не серые плашки.
        # Плашка, которая выглядит кликабельной и не ведёт никуда, хуже
        # обычного текста: посетитель жмёт по ней и получает ничего.
        pills = ""
        жанры = деталь.get("genres") or []
        коды_жанров = list(деталь.get("genre_codes") or [])
        звенья_жанров = []
        # Имя переменной здесь не `имя`: так зовут название произведения, и
        # затенение в цикле уводило его в заголовок страницы — H1 показывал
        # «Япония» вместо «Хори-сан и Миямура-кун».
        for н, г in enumerate(жанры[:10]):
            имя_жанра = str(г).strip()
            if not имя_жанра:
                continue
            код = (str(коды_жанров[н]).strip() if н < len(коды_жанров) else "")
            if not код:
                код = self._код_жанра(имя_жанра)
            if код and (self.индекс.get("genre") or {}).get(код):
                адрес = закодировать_запрос(f"/catalog/?genre={код}")
                звенья_жанров.append(
                    f'<a href="{html.escape(адрес, quote=True)}">'
                    f'{html.escape(имя_жанра)}</a>')
            else:
                # Жанра нет в указателе — ссылка вела бы в пустую выдачу.
                звенья_жанров.append(f"<span>{html.escape(имя_жанра)}</span>")
        if звенья_жанров:
            pills = ('<div class="ztitle__pills">'
                     + "".join(звенья_жанров) + "</div>")
        # Значение факта либо обычный текст, либо ссылка — и тогда переход
        # ведёт ровно туда, куда обещает подпись. Промежуточного вида
        # «похоже на ссылку, но не ссылка» здесь нет.
        факты = []
        год = запись.get("year") or деталь.get("year")
        if год:
            факты.append(("Год", self._ссылка_факта(
                str(год), f"/catalog/?year={год}",
                годен=str(год).isdigit())))
        тип = запись.get("kind") or деталь.get("type")
        if тип:
            есть_вид = any(з.get("kind") == str(тип) for з in self.д.items)
            факты.append(("Тип", self._ссылка_факта(
                str(тип), "/catalog/" + запрос_строкой({"kind": str(тип)}),
                годен=есть_вид)))
        страны = деталь.get("countries") or []
        if страны:
            звенья_стран = []
            for страна in страны[:3]:
                имя_страны = str(страна).strip()
                if not имя_страны:
                    continue
                код = нормализовать(имя_страны)
                годен = bool((self.индекс.get("country") or {}).get(код))
                звенья_стран.append(self._ссылка_факта(
                    имя_страны, f"/catalog/?country={код}", годен=годен))
            if звенья_стран:
                факты.append(("Страна", ", ".join(звенья_стран)))
        статус = деталь.get("status") or деталь.get("release_status")
        avail = sum(int(с.get("avail") or 0) for с in сезоны) if сезоны else 0
        total = sum(int(с.get("eps") or 0) for с in сезоны) if сезоны else 0
        if not статус and сезоны:
            if total and avail >= total:
                статус = "Вышел"
            elif avail:
                статус = "Онгоинг"
        if статус:
            факты.append(("Статус", html.escape(str(статус))))
        if avail > 0:
            факты.append(("Доступно серий", html.escape(str(avail))))
        if total > 0 and total != avail:
            факты.append(("Вышло серий", html.escape(str(total))))
        длит = деталь.get("duration") or деталь.get("episode_duration") or деталь.get("runtime")
        if длит:
            факты.append(("Продолжительность", html.escape(str(длит))))
        студии = деталь.get("studios") or деталь.get("studio") or деталь.get("voice_studios") or []
        if isinstance(студии, str):
            студии = [студии]
        if студии:
            факты.append(("Студия",
                          html.escape(", ".join(str(с) for с in студии[:2]))))
        meta_html = ""
        if факты:
            # Значение приходит готовой разметкой (ссылка или экранированный
            # текст): экранировать его второй раз значило бы показать теги.
            rows = "".join(
                f"<div><dt>{html.escape(k)}</dt><dd>{v}</dd></div>"
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
            f'{self._маячок_просмотра(деталь)}'
            f"{_скрипты_плеера(код)}</section>")
        текущий = (сезон_старт, эпизод_старт) if эпизод_старт is not None else None
        блок_серий = (self._серии(запись, сезоны, текущий=текущий) if сериал else "")
        блок_похожих = self._блок_похожих(запись, деталь)
        # Одно произведение не должно попасть в обе полки: посетитель
        # увидел бы одну и ту же карточку дважды на одной странице.
        уже_показаны = {з.get("slug") for з in self.похожие(запись, деталь)}
        блок_рекомендуем = self._блок_рекомендуем(запись, деталь, уже_показаны)
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
            # Порядок: плеер → действия → серии → реакции → обсуждение.
            # Оценка и списки стоят сразу под плеером, потому что именно их
            # делают, досмотрев; прежде они лежали под всеми блоками, и
            # посетитель до них не доходил.
            f'</div>{rail}</div>{ad_title}{плеер}'
            f'{self.панель_действий(запись)}{блок_серий}'
            f'{self.полоса_реакций(запись)}'
            f'{self.блок_обсуждения(запись)}{блок_похожих}'
            f'{блок_рекомендуем}</div>')
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
            f'{self._маячок_просмотра(деталь)}'
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
        # Обсуждение произведения доступно и со страницы серии.
        # Ветка одна: ключ — slug произведения, а не адрес страницы, поэтому
        # переход между сериями не создаёт вторую ветку и не теряет уже
        # написанное. Формы возвращают посетителя на страницу произведения,
        # где этот раздел — основной.
        действия = self.панель_действий(запись, возврат=путь)
        реакции = self.полоса_реакций(запись, возврат=путь)
        обсуждение = self.блок_обсуждения(запись, возврат=путь)
        тело = (
            f'<div class="zwrap aep-page" data-b09="exact">'
            f'<h1 class="zh zh--ep">{html.escape(заголовок)}</h1>'
            # «Контекст тайтла» уехал ниже действий: он отделял плеер от
            # оценки и списков, то есть стоял ровно между просмотром и тем,
            # что делают сразу после него.
            f'{плеер}{действия}{переход}'
            f'{self._серии(запись, сезоны, текущий=(сезон, эпизод))}'
            f'{реакции}{ctx}{обсуждение}{блок_похожих}</div>')
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

    def верхняя_карусель(self, набор, *, snapshot: dict | None = None,
                         подпись: str = "Популярное",
                         источник: str = "weekly-popular") -> str:
        """Первый экран — горизонтальная лента вертикальных постеров.

        Прежде здесь стоял одиночный герой: большой постер, абзац описания,
        оценка и кнопка — один тайтл на весь экран, а остальные семь прятались
        за точками. У оригинала первый экран устроен иначе: красная полоса, на
        ней ряд вертикальных постеров с короткими белыми названиями и стрелки
        по краям. Семь постерами на широком экране, меньше — на узком. Ровно
        это здесь и собирается.

        Содержимое берётся из уже утверждённых источников и подписывается тем,
        чем оно является: есть утверждённый недельный снимок — «Популярное за
        неделю»; нет — лента проверенного реестра добавлений со своим
        названием; нет и её — ленты нет вовсе. Подписывать одну выборку
        названием другой нельзя: это и была бы выдуманная популярность.

        Тайтл без постера в ленту не берётся: полоса из букв-заглушек —
        не промоблок. Из каталога такой тайтл при этом никуда не девается,
        его место в ленте занимает следующий подходящий.
        """
        if not набор:
            return ""
        отобрано = [з for з in набор
                    if з.get("slug") and з.get("title") and з.get("url")
                    and str(з.get("poster") or "").strip()][:16]
        if len(отобрано) < 4:
            # Меньше четырёх постеров — это не лента, а обрывок.
            return ""
        extra = f' data-carousel-source="{html.escape(источник)}"'
        if источник == "weekly-popular":
            extra += ' data-weekly-popular="1"'
        if snapshot:
            extra += (
                f' data-popular-window="{html.escape(str(snapshot.get("window") or "weekly"))}"'
                f' data-popular-week="{html.escape(str(snapshot.get("week_key") or snapshot.get("week_id") or ""))}"'
                f' data-popular-snapshot="{html.escape(str(snapshot.get("snapshot_version") or snapshot.get("digest") or ""))}"'
                f' data-popular-updated="{html.escape(str(snapshot.get("updated_at") or snapshot.get("generated_at") or ""))}"'
                f' data-popular-algo="{html.escape(str(snapshot.get("algorithm_version") or ""))}"'
            )
        плитки = "".join(self.плитка(з, вариант="hero") for з in отобрано)
        return (
            f'<section class="ahero" aria-roledescription="carousel" '
            f'aria-label="{html.escape(подпись)}" data-hero="1" '
            f'data-hero-count="{len(отобрано)}"{extra}>'
            f'<h2 class="vh">{html.escape(подпись)}</h2>'
            f'<div class="zrl ahero__rl">'
            f'<button class="zrl__btn zrl__btn--p" type="button" data-rl="prev" '
            f'aria-controls="hero-rail">'
            f'<span class="ahero__chev ahero__chev--p" aria-hidden="true"></span>'
            f'<span class="vh">Предыдущие</span></button>'
            f'<div class="zrl__vp" id="hero-rail" tabindex="0" role="group" '
            f'aria-label="{html.escape(подпись)}: лента постеров, листается стрелками">'
            f'<div class="zrl__track">{плитки}</div></div>'
            f'<button class="zrl__btn zrl__btn--n" type="button" data-rl="next" '
            f'aria-controls="hero-rail">'
            f'<span class="ahero__chev ahero__chev--n" aria-hidden="true"></span>'
            f'<span class="vh">Следующие</span></button>'
            f'</div></section>')

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
        """Компактные номерные кнопки 40–52px; базу сохраняет «Серия N»."""
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
                if not доступна:
                    # Заявленная, но недоступная серия — не ссылка вовсе.
                    # Стиль `pointer-events:none` закрывал только мышь:
                    # клавиатурой, читалкой и прямым адресом страница
                    # открывалась и показывала плеер, которому нечего
                    # играть. Номер остаётся видимым — список серий обязан
                    # говорить, сколько их объявлено.
                    ссылки.append(
                        f'<span class="zeps__off" data-off aria-disabled="true" '
                        f'title="Серия заявлена, дорожки ещё нет">{н}</span>')
                    continue
                атрибуты = ' aria-current="page"' if текущая else ""
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

    def seo_блок(self, *, заголовок: str, текст: str, как_h1: bool = False) -> str:
        """Нижний блок «о сайте» перед подвалом; на узком экране — details.

        На главной он несёт H1. Так у оригинала: первый экран там начинается
        каруселью, а название и описание сайта стоят внизу отдельной секцией.
        Заголовок при этом остаётся ровно один на странице.
        """
        if not текст:
            return ""
        тег = "h1" if как_h1 else "h2"
        return (
            f'<aside class="zseo" aria-label="{html.escape(заголовок)}">'
            f'<div class="zseo__full"><{тег} class="zseo__t">{html.escape(заголовок)}</{тег}>'
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
            f'{self.плитки(похожие, вариант="related-row")}</section>')

    def _блок_рекомендуем(self, запись: dict, деталь: dict,
                          исключая: set | None = None) -> str:
        """«Рекомендуем посмотреть» — другой вопрос, чем «Похожее».

        «Похожее» отвечает на «ещё такое же»: жанры, тип, студия, год слабым
        сигналом. «Рекомендуем» отвечает на «а что вообще стоит посмотреть»:
        качество и свежесть. Смешивать их в одну полку — значит не ответить
        ни на один из двух вопросов.

        Поведение пользователя сюда не входит: витрина его не собирает, и
        подписывать подборку «для вас» было бы неправдой. Одно произведение
        не попадает в обе полки, и само себе не рекомендуется.
        """
        нельзя = set(исключая or ())
        нельзя.add(запись.get("slug"))
        свежесть_порог = datetime.now(timezone.utc) - timedelta(days=365)
        кандидаты = []
        for з in self.д.items:
            if з.get("slug") in нельзя:
                continue
            оценка = float(з.get("_rating") or 0.0)
            if оценка < 7.5:
                continue
            момент = (ХРОНОЛОГИЯ.разобрать_момент(з.get("published_at"))
                      if ХРОНОЛОГИЯ is not None else None)
            свежее = 1 if (момент is not None and момент >= свежесть_порог) else 0
            кандидаты.append((свежее, оценка, int(з.get("_votes") or 0), з))
        if len(кандидаты) < АНИМЕДИА_REC_MIN_ITEMS:
            return ""
        кандидаты.sort(key=lambda к: (-к[0], -к[1], -к[2], к[3]["slug"]))
        набор = [к[3] for к in кандидаты[:АНИМЕДИА_REC_MAX_ITEMS]]
        return (
            f'<section class="zsec zsec--rec" data-b10b="suggest" '
            f'data-suggest-basis="quality-freshness" '
            f'data-suggest-count="{len(набор)}">'
            f'<h2 class="zh zh--sm">Рекомендуем посмотреть</h2>'
            f'<p class="zsub">Высокие оценки, свежее — выше.</p>'
            f'{self.плитки(набор, вариант="catalog-title")}</section>')

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
        # Списки подрезаны до пяти по измерению, а не по вкусу: на восьми
        # ссылках самый высокий столбец давал подвал 463px при паспортных
        # 220–300. Ссылки настоящие, просто их меньше; остальные жанры и годы
        # открываются из таксономии шапки и фильтров каталога.
        genres = "".join(
            f'<a href="/catalog/?genre={html.escape(код)}">{html.escape(имя)}</a>'
            for код, имя in (self.индекс.get("genre_names") or [])[:5])
        years = "".join(
            f'<a href="/catalog/?year={г}">{г}</a>'
            for г in (self.д.years or [])[:5])
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
            f'<div class="zft__col"><b>Годы</b>{years or "<span>—</span>"}</div>'
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
{СКРИПТ_КАРУСЕЛИ}
{СКРИПТ_АНИМЕДИА_ШАПКА}</script>
</head>
<body><a class="skip" href="#main">Перейти к содержимому</a>
<div class="zs">
<header class="zhd">
<div class="zhd__in">
{self.логотип()}
<nav id="zhd-nav" class="zhd__n" aria-label="Разделы">{нав}</nav>
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
    def главная(self, зпр: dict | None = None) -> str:
        зпр = dict(зпр or {})
        занято: set = set()
        #: Что уже показано каруселью первого экрана: ниже эти записи не
        #: повторяются, иначе первый экран и первая лента дублируют друг друга.
        занятые_каруселью: set = set()

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
        # Единственный H1 страницы стоит первым в содержимом и визуально скрыт:
        # у оригинала первый экран начинается каруселью, и крупного заголовка
        # там нет, но документ без H1 в начале заставляет читалку идти по H2
        # до самого низа. Композиция сохраняется, семантика становится верной.
        # Блока «Найдите аниме за секунду» здесь больше нет. Он занимал верх
        # первого экрана целиком — заголовок, абзац, поле во всю ширину и ряд
        # ссылок-подсказок — и отодвигал витрину ниже сгиба. Поиск остался
        # компактным в шапке, он есть на каждой странице; расширенный отбор
        # переехал вниз, к сетке каталога, как у оригинала.
        куски = [f'<h1 class="vh">{html.escape(домен["title_home"])}</h1>',
                 self.полоса_готовности()]

        # Первый экран оригинала — карусель, а не заголовок с лидом. Источник
        # выбирается по убыванию доказанности и подписывается собой.
        if weekly_items and weekly_meta:
            куски.append(self.верхняя_карусель(weekly_items[:24], snapshot=weekly_meta))
        else:
            запасная = None
            if снимок is not None:
                for ключ in ("recently_added", "series_with_episodes"):
                    коллекция = КОЛЛЕКЦИИ.разрешить(ключ, снимок, СЕМЕЙСТВО, предел=24)
                    if коллекция is not None and len(коллекция.items) >= 4:
                        запасная = (ключ, коллекция)
                        break
            if запасная is not None:
                ключ, коллекция = запасная
                титул, _ = ПРИЧИНЫ.get(ключ, (коллекция.title, ""))
                # Запасная лента подписывается тем, чем она является, — и
                # «Популярным» её называть нельзя: это другая выборка.
                куски.append(self.верхняя_карусель(
                    [к.raw for к in коллекция.items[:24]],
                    подпись=титул, источник=ключ.replace("_", "-")))
                занятые_каруселью |= {к.raw.get("slug") for к in коллекция.items[:24]}
            else:
                куски.append(
                    '<div class="ahero ahero--gap" data-weekly-popular="0" '
                    'data-popular-gap="1" hidden aria-hidden="true"></div>')
        куски.append(_аниме_telegram_promo_html())
        # Empty ad slots must collapse to 0px (no Telegram/premium invent).
        куски.append('<div class="zad-home" data-ad-slot="home-after-hero" data-ad-enabled="0"></div>')
        # Ряда «Недавно добавленные» на главной больше нет. Он повторял ленту
        # первого экрана: та же карточка, тот же размер, часто те же тайтлы —
        # два одинаковых ряда подряд, и второй ничего не добавлял. Раздел
        # никуда не делся: он открывается по «Новое» в меню и по /new/, а
        # свежесть каталога видна в сетке ниже, где сортировка по умолчанию —
        # именно по свежести.
        куски.append(self._блок_новых_серий_b03(зпр))
        куски.append('<div class="zad-mid" data-ad-slot="home-mid-content" data-ad-enabled="0"></div>')

        # B06.2 Top-100 — approved snapshot only.
        куски.append(self._блок_top100_b06())
        # Топ по оценкам стоит после пробела «Топ‑100», а не вместо него:
        # это соседний блок с другим основанием, и подменять им популярность
        # нельзя. Когда придёт утверждённый снимок популярности, верхний блок
        # заполнится, а этот останется тем, чем был.
        куски.append(self._блок_топа_по_оценкам())
        # Cross-shelf dedup. Weekly shelf slugs may reappear in lower grids only
        # when the lower shelf is not also the weekly popular block.
        очищенные = []
        герой_slug = {з["slug"] for з in weekly_items} | set(занятые_каруселью)
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
        # Отбор и сетка каталога — внизу, над листалкой, как у оригинала.
        # Наверху им не место: там витрина, а не форма.
        куски.append(self._блок_каталога_главной(зпр))
        # B06.5/6: news/reviews/comments absent from registry → 0 px placeholders.
        куски.append(
            '<div class="ahome-editorial" data-b06="editorial" data-editorial="0" '
            'hidden aria-hidden="true"></div>')
        куски.append(
            '<div class="ahome-comments" data-b06="comments" data-comments="0" '
            'hidden aria-hidden="true"></div>')
        # B06.7 SEO/about after functional modules, before footer.
        куски.append(self.seo_блок(заголовок=домен["title_home"],
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
        self.освежить_оценки_каталога()
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
        # Боковая лента серий: посетитель каталога не должен уходить на
        # главную, чтобы узнать, что сейчас выходит.
        сбоку = self._блок_сейчас_выходит(сбоку=True)
        основное = (
            f'<h1 class="zh">{html.escape(титул)}</h1>'
            f'<p class="zsub" data-b11-count="1">Найдено {len(набор)} · {pages_label}</p>'
            + фильтры
            + (self.плитки(кусок) if кусок else
               '<div class="zempty" data-b11-empty="1"><b>Ничего не подошло</b>'
               "<p>Под выбранные условия не попала ни одна запись. "
               f'<a href="{разд}/">Сбросить фильтры</a>.</p></div>')
            + (self.листалка(разд, выбрано, стр, всего) if всего > 1 else ""))
        тело = (f'<div class="zwrap zwrap--catalog" data-b11="catalog"{facet}>'
                + (f'<div class="awrap-side"><div>{основное}</div>'
                   f'<div class="awrap-side__a">{сбоку}</div></div>'
                   if сбоку else основное)
                + "</div>")
        канон = разд + "/" + (запрос_строкой(выбрано, page=None) if any(
            выбрано.get(k) for k in ("genre", "year", "kind", "country", "type",
                                     "sort", "exclude", "rating", "ongoing")) else "")
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

    def _фильтры_каталога(self, разд: str, выбрано: dict, total: int | None = None,
                          *, база: str | None = None, якорь: str = "") -> str:
        """Панель отбора: раскрывающиеся списки и снятие выбранного.

        `база` — адрес, на который ведут ссылки фильтра. По умолчанию это сам
        раздел; главная передаёт свой «/», чтобы один и тот же фильтр правил
        сетку там, где он стоит, а не уводил на другую страницу.
        """
        idx = self.индекс or {}
        корень = база if база is not None else (разд + "/")
        набор_для_счёта = self.д.items
        chips = []
        active_keys = ("kind", "type", "year", "genre", "country", "sort",
                       "exclude", "rating", "ongoing")

        def chip(label: str, clear_key: str) -> str:
            cleared = dict(выбрано)
            cleared[clear_key] = None
            href = корень + запрос_строкой(cleared, page=None) + якорь
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
        if выбрано.get("exclude"):
            ename = выбрано["exclude"]
            for код, имя in (idx.get("genre_names") or []):
                if код == выбрано["exclude"]:
                    ename = имя
                    break
            chips.append(chip(f"без «{ename}»", "exclude"))
        if выбрано.get("rating"):
            chips.append(chip(f"оценка от {выбрано['rating']}", "rating"))
        if выбрано.get("ongoing"):
            chips.append(chip("Онгоинг" if str(выбрано["ongoing"]) == "1"
                              else "Завершённые", "ongoing"))
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
                href = корень + запрос_строкой(выбрано, **{param: value, "page": None}) + якорь
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
            reset = f'<a class="afilt__reset" href="{корень}{якорь}">Очистить</a>'
        chips_html = (f'<div class="afilt__chips" aria-label="Активные фильтры">'
                      f'{"".join(chips)}{reset}</div>' if (chips or reset) else "")
        # Порог оценки: ступени, а не свободное число. Свободное поле здесь
        # порождает запросы вроде «от 9.7», под которые в каталоге две записи,
        # и посетитель решает, что фильтр сломан.
        rating_pairs = [
            (str(п), f"от {п}", sum(1 for з in набор_для_счёта
                                    if float(з.get("_rating") or 0.0) >= п))
            for п in (9, 8, 7, 6)]
        rating_pairs = [(v, l, c) for v, l, c in rating_pairs if c]
        онгоингов = sum(1 for з in набор_для_счёта if з.get("_ongoing"))
        ongoing_pairs = ([("1", "Онгоинг", онгоингов)] if онгоингов else []) + [
            ("0", "Завершённые", len(набор_для_счёта) - онгоингов)]
        exclude_pairs = [(код, f"без «{имя}»",
                          len((idx.get("genre") or {}).get(код) or []))
                         for код, имя in (idx.get("genre_names") or [])]
        body = (
            opts("Тип", kind_pairs, "kind")
            + opts("Формат", type_pairs, "type")
            + opts("Год", year_pairs, "year")
            + opts("Жанр", genre_pairs, "genre")
            + opts("Исключить жанр", exclude_pairs, "exclude")
            + opts("Оценка", rating_pairs, "rating")
            + opts("Статус", ongoing_pairs, "ongoing")
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

    #: Страниц в ленте новых серий и записей на странице. Пять по десять —
    #: композиция оригинала: на компьютере это две колонки по пять строк.
    ЭПИЗОДЫ_СТРАНИЦ = 5
    ЭПИЗОДЫ_НА_СТРАНИЦЕ = 10

    def _блок_новых_серий_b03(self, зпр: dict | None = None) -> str:
        """Лента «Новые серии» с листалкой на пять страниц.

        Записи — настоящие события реестра, свежие сверху. Страницы не
        добиваются повторами и выдуманными событиями: если подтверждённых
        записей меньше пятидесяти, лишние кнопки видны неактивными, а нехватка
        названа числом. Заполнить пять страниц дублями значило бы соврать о
        том, сколько на сайте вышло серий.

        Кнопки — настоящие ссылки, поэтому листалка работает и без
        JavaScript. Со скриптом переключение идёт на месте: страница не
        перезагружается и не прыгает вверх, а выбор уезжает в адрес через
        `replaceState` — и потому переживает обновление браузера.
        """
        зпр = зпр or {}
        events = self._provider_playable_events()
        self._provider_playable_count = len(events)
        источник = "provider"
        if not events:
            # Источник провайдера не подключён — берём собственный реестр
            # сравнения снимков. Пустая лента остаётся пустой: выдумывать
            # события всё так же нельзя.
            events = self._episode_ledger_events()
            источник = "snapshot-diff" if events else "none"
        self._episode_feed_source = источник
        if not events:
            # Событий выхода серий ещё не накоплено: реестр выводит их
            # сравнением соседних снимков и до второго снимка знать их не
            # может. Показывать вместо ленты объяснение про источник — значит
            # отдать посетителю внутреннюю кухню вместо продукта.
            return self._блок_сейчас_выходит()

        на = self.ЭПИЗОДЫ_НА_СТРАНИЦЕ
        всего_страниц = self.ЭПИЗОДЫ_СТРАНИЦ
        вместимость = на * всего_страниц
        # ОДИН ТАЙТЛ — ОДНА КАРТОЧКА НА ВСЮ ЛЕНТУ, включая страницы листалки.
        #
        # Прежде строки шли по событиям: один event_id — одна строка. Пока
        # серии выходили по одной, это совпадало с «одна карточка на тайтл»
        # и разницы не было видно. Но опрос поставщика по кругу доходит до
        # тайтла, у которого наш снимок отстал на десятки серий, и тогда
        # сравнение снимков честно пишет сотню событий разом, с одним и тем
        # же временем: они действительно стали доступны одновременно.
        # Измерено на боевом сайте: 146 событий у одного тайтла и 104 у
        # другого из 352 всего. Лента показывала десять карточек одного
        # сериала подряд, серии 90-99, время 20:15 у всех.
        #
        # Группировка идёт ДО ограничения и разбивки на страницы, иначе
        # первые пятьдесят событий выбираются раньше, чем становится ясно,
        # что все они об одном произведении.
        #
        # Ключ — постоянный идентификатор записи, а не название и не внешний
        # ID: у разных произведений внешний ID совпадает (у двух «Клеватесс»
        # один и тот же kp), и объединять их нельзя.
        по_тайтлу: dict[str, dict] = {}
        порядок: list[str] = []
        for р in events:
            ключ = str(р.get("content_id") or "").strip() or f"slug:{р.get('slug')}"
            прежняя = по_тайтлу.get(ключ)
            появилось = str(р.get("appeared_at") or "")
            if прежняя is None:
                по_тайтлу[ключ] = dict(р)
                порядок.append(ключ)
                continue
            # Карточка показывает ПОСЛЕДНЮЮ доступную серию и ведёт на неё.
            новее = ((int(р.get("season") or 0), int(р.get("episode_number") or 0))
                     > (int(прежняя.get("season") or 0),
                        int(прежняя.get("episode_number") or 0)))
            # Место в ленте — по самому свежему появлению у этого тайтла.
            # Время не пересчитывается и не выдумывается: берётся большее из
            # уже записанных, поэтому повторный опрос и переиздание каталога
            # его не меняют.
            свежайшее = max(str(прежняя.get("appeared_at") or ""), появилось)
            if новее:
                прежняя.update(р)
            прежняя["appeared_at"] = свежайшее
            прежняя["published_at"] = свежайшее

        # Свежие сверху. Сортировка устойчивая, поэтому у тайтлов с одинаковым
        # временем сохраняется порядок реестра, а не случайный: одновременно
        # обнаруженные обновления не получают выдуманных разных минут.
        сгруппировано = [по_тайтлу[к] for к in порядок]
        сгруппировано.sort(key=lambda р: str(р.get("appeared_at") or ""), reverse=True)
        отобрано = сгруппировано[:вместимость]
        заполнено = (len(отобрано) + на - 1) // на

        try:
            текущая = int((зпр.get("eps") or ["1"])[0] or 1)
        except (TypeError, ValueError):
            текущая = 1
        if текущая < 1 or текущая > max(заполнено, 1):
            текущая = 1

        панели = []
        for н in range(1, всего_страниц + 1):
            кусок = отобрано[(н - 1) * на: н * на]
            if not кусок:
                continue
            ряды = "".join(self._разметка_эпизод_ряда(р) for р in кусок)
            панели.append(
                f'<div class="aeps" data-eps-panel="{н}"'
                f'{"" if н == текущая else " hidden"}>{ряды}</div>')

        кнопки = "".join(
            f'<a class="aeps__pg{" is-on" if н == текущая else ""}'
            f'{"" if н <= заполнено else " is-off"}" '
            f'href="/?eps={н}#new-episodes" data-eps-page="{н}"'
            + (' aria-current="page"' if н == текущая else "")
            + (' aria-disabled="true" tabindex="-1"' if н > заполнено else "")
            + f'>{н}</a>'
            for н in range(1, всего_страниц + 1))

        нехватка = ""
        if len(отобрано) < вместимость:
            нехватка = (
                f'<p class="aeps__short" data-events-confirmed="{len(отобрано)}" '
                f'data-events-capacity="{вместимость}">'
                f'Подтверждённых событий пока {len(отобрано)} из {вместимость}: '
                f'страницы заполняются по мере выхода новых серий. '
                f'Повторами и выдуманными записями места здесь не занимаются.'
                f'</p>')

        return (
            f'<section class="zsec zsec--eps ahome-eps" id="new-episodes" '
            f'data-b03="populated" '
            f'data-provider-playable-count="{self._provider_playable_count}" '
            f'data-episode-feed-source="{html.escape(источник)}" '
            f'data-eps-pages="{заполнено}" data-eps-current="{текущая}" '
            f'data-eps-total="{len(отобрано)}">'
            f'<div class="zsec__h"><h2>{АНИМЕДИА_ЭПИЗОД_ЗАГОЛОВОК}</h2>'
            f'<a href="/new/">Весь раздел</a></div>'
            f'{"".join(панели)}'
            f'<nav class="aeps__pages" aria-label="Страницы новых серий">'
            f'{кнопки}</nav>{нехватка}</section>'
        )

    def онгоинги(self, предел: int = 0) -> list[tuple]:
        """Тайтлы, у которых доступно меньше серий, чем заявлено.

        Это настоящий факт из снимка подробностей, а не догадка о выходе
        серии: `avail` — к скольким сериям есть дорожка, `eps` — сколько
        объявлено. Ни одной даты здесь не придумывается, поэтому блок
        называется «Сейчас выходит», а не «Новые серии».

        Порядок — от самого свежего поступления в каталог: у равных данных
        должен быть один и тот же порядок на каждой странице.
        """
        готовые = []
        for з in недавно_добавленные(self.д.items):
            деталь = self.деталь(з.get("slug") or "") or {}
            сезоны = деталь.get("seasons")
            if not isinstance(сезоны, list) or not сезоны:
                continue
            доступно = заявлено = 0
            for с in сезоны:
                if not isinstance(с, dict):
                    continue
                доступно += int(с.get("avail") or 0)
                заявлено += int(с.get("eps") or 0)
            if заявлено and 0 < доступно < заявлено:
                готовые.append((з, доступно, заявлено))
            if предел and len(готовые) >= предел:
                break
        return готовые

    def _блок_сейчас_выходит(self, *, сбоку: bool = False) -> str:
        """Лента «Сейчас выходит»: сколько серий уже доступно из заявленных."""
        строки = self.онгоинги(АНИМЕДИА_ЭПИЗОД_НА_СТРАНИЦЕ)
        if not строки:
            return (
                '<section class="zsec zsec--eps ahome-eps ahome-eps--empty" '
                'data-b03="empty" data-provider-playable-count="0" '
                'data-episode-feed-source="none" hidden aria-hidden="true"></section>'
            )
        ряды = []
        for з, доступно, заявлено in строки:
            изо = заглушка_постера(з, "aeps__none", "aeps__img", 60, 90)
            # Справа — номер последней доступной серии, а не общее их число:
            # «16» здесь означает шестнадцатую серию, потому что серии
            # нумеруются подряд и доступны с первой по `avail`. Прежде тут
            # стояло то же число с подписью «серий», и общий счётчик выдавался
            # за событие выхода.
            ряды.append(
                f'<a class="aeps__row" data-card-variant="episode-row" '
                f'href="{html.escape(з["url"])}" data-event-kind="ongoing" '
                f'data-eps-avail="{доступно}" data-eps-total="{заявлено}" '
                f'data-episode-number="{доступно}" data-episode-time="">'
                f'<span class="aeps__thumb">{изо}</span>'
                f'<span class="aeps__body">'
                f'<span class="aeps__title">{html.escape(з["title"])}</span>'
                f'<span class="aeps__meta">Вышло {доступно} из {заявлено} серий</span>'
                f'</span>'
                f'<span class="aeps__ep"><span class="aeps__num">{доступно}</span>'
                f'<span class="aeps__lab">серия</span></span></a>')
        класс = "aside-eps" if сбоку else "ahome-eps"
        # Ленты событий здесь нет, и блок ею не притворяется: это перечень
        # незавершённых тайтлов из снимка. Времени появления серий в нём нет,
        # и оно не выдумывается — сказано прямо, каким полем и откуда оно
        # придёт. Реестр сравнения снимков уже заведён и ждёт второго снимка.
        # Технического абзаца про снимки и реестр здесь больше нет: это
        # внутренняя кухня, а не то, ради чего открывают главную.
        сноска = ""
        return (
            f'<section class="zsec zsec--eps {класс}" data-b03="ongoing" '
            f'data-episode-feed-source="ongoing-counters" '
            f'data-episode-time-gap="1" '
            f'data-ongoing-count="{len(строки)}">'
            f'<div class="zsec__h"><h2>Сейчас выходит</h2>'
            f'<a href="/catalog/?ongoing=1">Все незавершённые</a></div>'
            f'{сноска}'
            f'<div class="aeps">{"".join(ряды)}</div></section>'
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

    def недавно_добавленные_записи(self, предел: int = 0) -> tuple[list, str]:
        """Записи для «Недавно добавленных» и откуда они взяты.

        Порядок источников — по убыванию доказанности. Утверждённый реестр
        добавлений остаётся первым: когда он появится, ничего переписывать не
        придётся. Пока его нет, берётся дата добавления из самого снимка, из
        которой убрана когорта массового импорта.
        """
        события = self._catalog_added_events()
        if события:
            slugs = [str(с.get("title_slug") or с.get("slug") or "") for с in события]
            по_slug = {з.get("slug"): з for з in self.д.items if з.get("slug")}
            записи = [по_slug[s] for s in slugs if s in по_slug]
            if записи:
                return (записи[:предел] if предел else записи), "ledger"
        return недавно_добавленные(self.д.items, предел), "catalog-added-at"

    def _блок_нового_в_каталоге_b05(self) -> str:
        """Полка «Недавно добавленные» на главной.

        Раньше полка пряталась целиком, если не подключён утверждённый реестр
        добавлений. Снаружи это выглядело так, будто на сайт ничего не
        поступает, хотя в снимке лежат настоящие даты добавления. Реестр
        по-прежнему главнее, но его отсутствие больше не отменяет раздел.
        """
        записи, источник = self.недавно_добавленные_записи(
            АНИМЕДИА_CATALOG_ADDED_HOME_LIMIT)
        self._catalog_added_count = len(записи)
        self._catalog_freshness_gap = 0 if записи else 1
        if not записи:
            return (
                '<div class="zsec zsec--b05 zsec--b05-gap" data-b05="gap" '
                'data-catalog-freshness-gap="1" hidden aria-hidden="true"></div>'
            )
        return (
            f'<section class="zsec zsec--b05" data-b05="populated" '
            f'data-catalog-freshness-gap="0" '
            f'data-catalog-added-source="{источник}" '
            f'data-catalog-added-count="{len(записи)}">'
            f'<div class="zsec__h"><h2>{АНИМЕДИА_CATALOG_ADDED_H1}</h2>'
            f'<a href="/new/">Весь раздел</a></div>'
            # Один горизонтальный ряд, а не сетка на две-три строки. Сеткой
            # этот раздел раздувал верх главной и повторял то, что и так
            # открывается по «Весь раздел»; остальное доступно прокруткой,
            # стрелками и этой ссылкой.
            f'{self.карусель("b05-added", записи)}</section>'
        )

    #: Сколько карточек в сетке главной на страницу. Кратно и двум, и четырём,
    #: и шести — числу колонок на телефоне, планшете и широком экране, — чтобы
    #: последний ряд не обрывался ни на одной контрольной ширине.
    ГЛАВНАЯ_НА_СТРАНИЦЕ = 24

    def _блок_каталога_главной(self, зпр: dict) -> str:
        """Отбор и сетка «Новые аниме на сайте» — как у оригинала, внизу главной.

        Расширенный отбор стоял вверху шапки второй строкой кнопок и оттеснял
        витрину. У оригинала он ниже, прямо над сеткой, которой управляет.
        Здесь так же: панель, счётчик, сетка, листалка.

        Каждый показанный контрол правит именно эту выдачу. Выбор живёт в
        адресе страницы, поэтому ссылку можно послать и вернуться по ней;
        листалка выбор не сбрасывает, а «Очистить» возвращает исходное
        состояние. Нерабочих переключателей здесь нет: панель собирается из
        тех же указателей, по которым идёт отбор.
        """
        self.освежить_оценки_каталога()
        набор, выбрано = отбор(self.д, self.индекс, зпр, "/catalog")
        q = ((зпр.get("q") or [""])[0] or "").strip()
        if q:
            # Поиск сужает уже отобранное, а не заменяет его: «боевик» плюс
            # слово в названии — обычный запрос, и терять при нём жанр незачем.
            попавшие = {з.get("slug") for з in self.д.искать(q, предел=2000)}
            набор = [з for з in набор if з.get("slug") in попавшие]
        выбрано = dict(выбрано)
        выбрано["q"] = q or None
        try:
            стр = max(1, int((зпр.get("page") or ["1"])[0] or 1))
        except (TypeError, ValueError):
            стр = 1
        на_странице = self.ГЛАВНАЯ_НА_СТРАНИЦЕ
        всего_страниц = (len(набор) + на_странице - 1) // на_странице
        if всего_страниц and стр > всего_страниц:
            стр = всего_страниц
        кусок = набор[(стр - 1) * на_странице: стр * на_странице]
        фильтр = self._фильтры_каталога(
            "/catalog", выбрано, total=len(набор), база="/", якорь="#catalog")
        активен = any(выбрано.get(к) for к in
                      ("kind", "type", "year", "genre", "country", "sort",
                       "exclude", "rating", "ongoing", "q"))
        заголовок = "Новые аниме на сайте" if not активен else "Отобрано в каталоге"
        сетка = (self.плитки(кусок, вариант="catalog-title") if кусок else
                 '<div class="zempty"><b>Ничего не подошло</b>'
                 '<p>Под выбранные условия не попала ни одна запись. '
                 '<a href="/#catalog">Очистить отбор</a>.</p></div>')
        листалка = (self._листалка_главной(выбрано, стр, всего_страниц)
                    if всего_страниц > 1 else "")
        return (
            f'<section class="zsec zsec--home-catalog" id="catalog" '
            f'data-home-catalog="1" data-home-catalog-total="{len(набор)}" '
            f'data-home-catalog-page="{стр}" data-home-catalog-pages="{всего_страниц}">'
            f'<div class="zsec__h"><h2>{html.escape(заголовок)}</h2>'
            f'<a href="/catalog/">Весь каталог</a></div>'
            f'{self._поиск_в_фильтре(q, выбрано)}{фильтр}'
            f'<p class="zsub" data-home-catalog-count="{len(набор)}">'
            f'Найдено {len(набор)} · страница {стр} из {max(всего_страниц, 1)}</p>'
            f'{сетка}{листалка}</section>')

    def _поиск_в_фильтре(self, q: str, выбрано: dict) -> str:
        """Строка поиска внутри панели отбора — как у оригинала.

        Отправляется на главную же: поле сужает ту сетку, рядом с которой
        стоит, а не уводит на отдельную страницу выдачи. Остальной выбор
        уезжает скрытыми полями, иначе поиск молча снимал бы жанр и год.
        """
        скрытые = "".join(
            f'<input type="hidden" name="{html.escape(к)}" value="{html.escape(str(з))}">'
            for к, з in выбрано.items()
            if з and к not in ("q", "page") and not str(к).startswith("_"))
        очистка = ('<a class="afilt__reset" href="/#catalog">Очистить</a>'
                   if (q or скрытые) else "")
        return (
            '<form class="afilt__q" action="/" method="get" role="search">'
            f'{скрытые}'
            '<label class="vh" for="home-cat-q">Поиск по каталогу аниме</label>'
            f'<input id="home-cat-q" name="q" type="search" autocomplete="off" '
            f'value="{html.escape(q)}" placeholder="Название аниме">'
            '<button type="submit">Найти</button>'
            f'{очистка}</form>')

    def _листалка_главной(self, выбрано: dict, стр: int, всего: int) -> str:
        """Листалка сетки главной. Выбор фильтра переносится на каждую страницу."""
        def адрес(н: int) -> str:
            return закодировать_запрос(
                "/" + запрос_строкой(выбрано, page=(н if н > 1 else None)) + "#catalog")
        куски = []
        if стр > 1:
            куски.append(f'<a href="{адрес(стр - 1)}" rel="prev">Назад</a>')
        for н in страницы(стр, всего):
            if н is None:
                куски.append('<span class="zpg__gap">…</span>')
            elif н == стр:
                куски.append(f'<span aria-current="page">{н}</span>')
            else:
                куски.append(f'<a href="{адрес(н)}">{н}</a>')
        if стр < всего:
            куски.append(f'<a href="{адрес(стр + 1)}" rel="next">Вперёд</a>')
        return (f'<nav class="zpg" aria-label="Страницы каталога">'
                f'{"".join(куски)}</nav>')

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

    def _блок_топа_по_оценкам(self) -> str:
        """Полка «Лучшее по оценкам» — порядок по сводной, а не по популярности.

        Отдельный блок, а не замена «Топ‑100». Популярность и оценка — разные
        величины, и подставить вторую под заголовок первой значило бы соврать
        ровно там, где витрина обещает цифру. Поэтому пробел популярности
        остаётся объявленным, а здесь честно названо основание порядка и
        порог голосов, ниже которого записи не брались.
        """
        топ = загрузить_топ_по_оценкам()
        if not топ:
            return ""
        по_slug = {з.get("slug"): з for з in self.д.items if з.get("slug")}
        записи = []
        for место in топ.get("places") or []:
            з = по_slug.get(место.get("slug"))
            if з is not None:
                записи.append(з)
            if len(записи) >= АНИМЕДИА_TOP100_HOME_LIMIT:
                break
        if len(записи) < 4:
            # Меньше четырёх — это не полка, а обрывок. Лучше ничего.
            return ""
        порог = int(топ.get("threshold_votes") or 0)
        # Подпись говорит посетителю, что перед ним, и ничего больше. Название
        # формулы и порог голосов остались в data-атрибутах: приёмке они нужны,
        # зрителю — нет, и владелец просил убрать внутреннюю кухню с экрана.
        подпись = "Высокие оценки внешних источников. Не популярность."
        return (
            f'<section class="zsec zsec--toprated" data-top-basis="ratings-aggregate" '
            f'data-top-method="{html.escape(str(топ.get("method") or ""))}" '
            f'data-top-threshold="{порог}" '
            f'data-top-digest="{html.escape(str(топ.get("digest") or ""))}" '
            f'data-top-count="{len(записи)}">'
            f'<div class="zsec__h"><h2>Лучшее по оценкам</h2>'
            f'<a href="/catalog/">Весь каталог</a></div>'
            f'<p class="zsub">{подпись}</p>'
            f'{self.плитки(записи, вариант="top100-shelf")}</section>'
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

    def _episode_ledger_events(self) -> list[dict]:
        """События «появилась новая серия» из реестра этого сайта.

        Реестр ведёт обработчик обновления: он сравнивает соседние снимки
        подробностей по ПОСТОЯННЫМ идентификаторам записей и пишет по событию
        на каждую появившуюся серию. Здесь событие только читается и
        связывается с текущим каталогом — ничего не досчитывается.

        Отметка времени в реестре — момент, когда серия стала доступна НА
        ЭТОМ САЙТЕ. Это не эфирная дата выхода, и подписана она соответственно.
        """
        путь = Path(АНИМЕДИА_EPISODE_LEDGER_PATH)
        if not путь.is_file():
            return []
        try:
            сырое = json.loads(путь.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        события = сырое.get("events") if isinstance(сырое, dict) else сырое
        if not isinstance(события, list):
            return []
        по_slug = {з.get("slug"): з for з in self.д.items if з.get("slug")}
        по_ид: dict[str, dict] = {}
        for з in self.д.items:
            ид = str((self.деталь(з.get("slug") or "") or {}).get("id") or "").strip()
            if ид:
                по_ид.setdefault(ид, з)
        строки = []
        for с in события:
            if not isinstance(с, dict):
                continue
            slug = str(с.get("slug") or "")
            ид = str(с.get("content_id") or "")
            запись = по_ид.get(ид) or по_slug.get(slug)
            if запись is None:
                # Тайтл ушёл из каталога — строка без страницы не нужна.
                continue
            сезон = int(с.get("season") or 0)
            эпизод = int(с.get("episode") or с.get("episode_to") or 0)
            # Событие — факт прошлого: «эта серия появилась тогда-то».
            # Доступность — состояние настоящего, и она умеет уменьшаться:
            # поставщик снимает поток или отзывает права, и наш опрос честно
            # понижает `avail`. Событие при этом остаётся в реестре — стирать
            # историю нельзя, — но вести карточку на серию, которой уже нет,
            # значит обещать страницу, где нечего смотреть. Измерено на боевых
            # данных: у трёх тайтлов из первой десятки событие было выше
            # доступного, и ссылки отвечали 404.
            доступно = 0
            for сез in список_серий(self.деталь(запись.get("slug") or slug) or {}):
                if int(сез.get("n") or 0) == сезон:
                    доступно = int(сез.get("avail") or 0)
                    break
            if not доступно or эпизод > доступно:
                continue
            если_есть = с.get("first_seen_at") or с.get("episode_published_at") or ""
            строки.append({
                "slug": запись.get("slug") or slug,
                "content_id": ид,
                "title": запись.get("title") or с.get("title") or slug,
                "url": (с.get("url")
                        or self.адрес_эпизода(запись.get("slug") or slug, сезон, эпизод)),
                "poster": запись.get("poster"),
                "event_kind": "appeared_on_site",
                "event_id": str(с.get("event_id") or f"{ид}:s{сезон}:e{эпизод}"),
                "season": сезон,
                "episode_number": эпизод,
                "episodes_total": int(с.get("episodes_total") or 0),
                "appeared_at": str(если_есть),
                "published_at": str(если_есть),
                "published_at_precision": "datetime",
            })
        return строки

    def _разметка_эпизод_ряда(self, row: dict) -> str:
        """Строка ленты «Новые серии».

        Слева мини-постер, посередине название и когда серия появилась,
        справа НОМЕР КОНКРЕТНОЙ СЕРИИ. Ссылка ведёт на эту серию, а не на
        карточку произведения: посетитель, пришедший за новой серией, хочет
        открыть именно её.

        Подпись времени — «Добавлено», а не «Вышло». Реестр знает момент, когда
        серия появилась на этом сайте; эфирной даты выхода источник не
        передаёт, и назвать одно другим значило бы соврать точной цифрой.
        """
        изо = заглушка_постера(
            {"title": row["title"], "poster": row.get("poster"), "url": row["url"]},
            "aeps__none", "aeps__img", 60, 90)
        сезон = int(row.get("season") or 0)
        эпизод = int(row.get("episode_number") or 0)
        когда = _аниме_формат_времени_анонса(
            row.get("appeared_at") or row.get("published_at") or "", "datetime")
        мета = f"Добавлено: {когда}" if когда else "Добавлено на сайт"
        подпись = f"с{сезон} · серия" if сезон > 1 else "серия"
        return (
            f'<a class="aeps__row" data-card-variant="episode-row" '
            f'href="{html.escape(row["url"])}" '
            f'data-event-id="{html.escape(row.get("event_id") or "")}" '
            f'data-event-kind="{html.escape(row.get("event_kind") or "appeared_on_site")}" '
            f'data-episode-number="{эпизод}" '
            f'data-appeared-at="{html.escape(str(row.get("appeared_at") or ""))}">'
            f'<span class="aeps__thumb">{изо}</span>'
            f'<span class="aeps__body">'
            f'<span class="aeps__title">{html.escape(row["title"])}</span>'
            f'<span class="aeps__meta">{html.escape(мета)}</span></span>'
            f'<span class="aeps__ep"><span class="aeps__num">{эпизод}</span>'
            f'<span class="aeps__lab">{html.escape(подпись)}</span></span></a>')

    def _страница_новых_эпизодов(self, зпр: dict) -> str:
        """Раздел «Недавно добавленные»: полноценная страница, а не объяснение.

        Прежде здесь стояло сообщение о неподключённом внутреннем реестре.
        Посетителю нечего делать с названием внутреннего компонента: он пришёл
        смотреть, что появилось на сайте. Теперь страница строится из тех же
        данных, что и полка на главной, и пустой остаётся только если в
        каталоге действительно нет ни одной датированной записи.
        """
        записи, источник = self.недавно_добавленные_записи()
        per = АНИМЕДИА_CATALOG_ADDED_PAGE_LIMIT
        if not записи:
            if (зпр.get("page") or ["1"])[0] not in (None, "", "1"):
                self._http_status = 404
                return self.не_найдено("/new/")
            self._http_status = 200
            тело = (
                f'<div class="zwrap anew-page" data-b05-page="gap">'
                f'<h1 class="zh">{АНИМЕДИА_CATALOG_ADDED_H1}</h1>'
                f'<div class="anew-empty" data-catalog-freshness-gap="1">'
                f'<b>{html.escape(АНИМЕДИА_CATALOG_ADDED_EMPTY)}</b>'
                f'<p>Каталог открыт целиком — '
                f'<a href="/catalog/">перейти в каталог</a>.</p></div></div>'
            )
            return self.оболочка(
                тело, f"{АНИМЕДИА_CATALOG_ADDED_H1} — {self.имя}", "/new/",
                актив="/new/",
                описание=АНИМЕДИА_CATALOG_ADDED_EMPTY)
        всего = max(1, (len(записи) + per - 1) // per)
        стр, err = self._разобрать_страницу_эпизодов(зпр, всего)
        if err or стр is None:
            self._http_status = 404
            return self.не_найдено("/new/")
        self._http_status = 200
        кусок = записи[(стр - 1) * per: стр * per]
        листалка = self._листалка_эпизодов(стр, всего)
        канон = "/new/" if стр == 1 else f"/new/?page={стр}"
        тело = (
            f'<div class="zwrap anew-page" data-b05-page="populated" '
            f'data-catalog-added-source="{источник}" '
            f'data-catalog-added-total="{len(записи)}">'
            f'<h1 class="zh">{АНИМЕДИА_CATALOG_ADDED_H1}</h1>'
            f'<p class="zsub">Всего {len(записи)} · страница {стр} из {всего}. '
            f'Порядок — от самого свежего поступления.</p>'
            + self.плитки(кусок, вариант="catalog-title") + листалка + "</div>"
        )
        return self.оболочка(
            тело, f"{АНИМЕДИА_CATALOG_ADDED_H1} — {self.имя}", канон,
            актив="/new/",
            описание=f"{АНИМЕДИА_CATALOG_ADDED_H1} на витрине {self.имя}.")

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
    #: Читаются общим маршрутом коллекции; у базу и базу остаются прежние.
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
            # Название стоит над коллажем — так у оригинала: сначала читаешь,
            # о чём подборка, потом смотришь, что в ней.
            f'<span class="zhub__t">{html.escape(к["title"])}</span>'
            f'<span class="zhub__g">'
            + "".join(
                f'<span class="zhub__p">'
                f'<img class="zhub__img" src="{html.escape(_адрес_постера(п) or "")}"'
                f' alt="" loading="lazy" width="120" height="180"></span>'
                for п in к["posters"])
            + "</span>"
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
            # Счётчик в самом заголовке — как у оригинала: «Подборки аниме (N)».
            f'<div class="zwrap"><h1 class="zh">Подборки аниме '
            f'<span class="zh__n">({всего})</span></h1>'
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
    # --- хабы разделов ---------------------------------------------------

    def _плитка_раздела(self, адрес: str, имя: str, сколько: int,
                        пояснение: str = "") -> str:
        return (
            f'<a class="ahub__c" href="{html.escape(адрес, quote=True)}">'
            f'<span class="ahub__n">{html.escape(имя)}</span>'
            f'<span class="ahub__k">{сколько} {склонение_записей(сколько)}</span>'
            + (f'<span class="ahub__p">{html.escape(пояснение)}</span>' if пояснение else "")
            + '</a>')

    def хаб_жанров(self) -> str:
        """Страница «Жанры»: все жанры каталога со счётчиками.

        Прежде `/genres/` отвечал переходом на каталог. Пункт навигации,
        который никуда не ведёт, — это не навигация; здесь он ведёт к списку
        жанров, каждый из которых открывает свою выдачу.
        """
        жанры = []
        for код, имя in (self.индекс.get("genre_names") or []):
            сколько = len((self.индекс.get("genre") or {}).get(код) or [])
            if сколько:
                жанры.append((сколько, код, имя))
        жанры.sort(key=lambda т: (-т[0], т[2]))
        плитки = "".join(
            self._плитка_раздела(f"/catalog/?genre={код}", имя.capitalize(), сколько)
            for сколько, код, имя in жанры)
        тело = (
            f'<div class="zwrap"><h1 class="zh">Жанры</h1>'
            f'<p class="zsub">Жанров в каталоге: {len(жанры)}. '
            f'Счётчик показывает, сколько произведений отнесено к жанру '
            f'в утверждённом снимке.</p>'
            f'<div class="ahub" data-hub="genres" data-hub-count="{len(жанры)}">'
            f'{плитки}</div></div>')
        return self.оболочка(тело, f"Жанры — {self.имя}", "/genres/",
                             актив="/genres/",
                             описание=f"Жанры аниме на витрине {self.имя}.")

    def хаб_типов(self) -> str:
        """Страница «Типы»: форматы произведений со счётчиками."""
        подписи = {"tv": ("Сериалы", "/series/", "Многосерийные произведения."),
                   "movie": ("Фильмы", "/movies/", "Полнометражные произведения.")}
        типы = []
        for код, slugs in sorted((self.индекс.get("type") or {}).items()):
            сколько = len(slugs or [])
            if not сколько:
                continue
            имя, адрес, пояснение = подписи.get(
                код, (код.upper(), f"/catalog/?type={код}", ""))
            типы.append((сколько, адрес, имя, пояснение))
        типы.sort(key=lambda т: -т[0])
        плитки = "".join(self._плитка_раздела(адрес, имя, сколько, пояснение)
                         for сколько, адрес, имя, пояснение in типы)
        тело = (
            f'<div class="zwrap"><h1 class="zh">Типы</h1>'
            f'<p class="zsub">Формат произведения берётся из снимка '
            f'подробностей. Типов в каталоге: {len(типы)}.</p>'
            f'<div class="ahub" data-hub="types" data-hub-count="{len(типы)}">'
            f'{плитки}</div></div>')
        return self.оболочка(тело, f"Типы — {self.имя}", "/types/",
                             актив="/types/",
                             описание=f"Типы аниме на витрине {self.имя}.")

    # --- топ ---------------------------------------------------------------

    #: Срезы топа: ключ, подпись и объяснение метода. Популярность сюда не
    #: входит — её данных витрине не передали, и называть оценку популярностью
    #: нельзя. Каждый срез обязан объяснять, как он посчитан.
    СРЕЗЫ_ТОПА = (
        ("rating", "По сводной оценке",
         "Порядок по сводной оценке Animedia, собранной из подтверждённых "
         "источников. Записи с малым числом голосов не участвуют."),
        ("votes", "По голосам посетителей",
         "Порядок по средней оценке посетителей этой витрины. Внешние "
         "источники в этот срез не входят."),
        ("fresh", "Новое за месяц",
         "Записи, добавленные в каталог за последние 30 дней, от самой "
         "свежей. Это срез по дате добавления, а не по популярности."),
    )

    def _топ_по_оценке(self, предел: int) -> list:
        топ = загрузить_топ_по_оценкам()
        if not топ:
            return []
        по_slug = {з.get("slug"): з for з in self.д.items if з.get("slug")}
        записи = [по_slug[м["slug"]] for м in (топ.get("places") or [])
                  if м.get("slug") in по_slug]
        return записи[:предел]

    def _топ_по_голосам(self, предел: int) -> list:
        хранилище = сообщество()
        if хранилище is None or not getattr(хранилище, "доступно", False):
            return []
        сырое = хранилище._прочитать().get("titles") or {}
        по_slug = {з.get("slug"): з for з in self.д.items if з.get("slug")}
        собрано = []
        for slug, запись in сырое.items():
            if slug not in по_slug:
                continue
            голоса = [int(v) for v in (запись.get("votes") or {}).values()
                      if isinstance(v, (int, float))]
            if not голоса:
                continue
            собрано.append((sum(голоса) / len(голоса), len(голоса), slug))
        собрано.sort(key=lambda т: (-т[0], -т[1], т[2]))
        return [по_slug[slug] for _, _, slug in собрано[:предел]]

    def _топ_свежего(self, предел: int) -> list:
        порог = datetime.now(timezone.utc) - timedelta(days=30)
        свежие = []
        for з in недавно_добавленные(self.д.items):
            момент = (ХРОНОЛОГИЯ.разобрать_момент(з.get("published_at"))
                      if ХРОНОЛОГИЯ is not None else None)
            if момент is None or момент < порог:
                break
            свежие.append(з)
            if len(свежие) >= предел:
                break
        return свежие

    def страница_топа(self, зпр: dict) -> str:
        """Страница «Топ» с названным методом у каждого среза."""
        срез = ((зпр.get("by") or [""])[0] or "rating").strip()
        известные = {к for к, _, _ in self.СРЕЗЫ_ТОПА}
        if срез not in известные:
            self._http_status = 404
            return self.не_найдено("/top/")
        предел = 48
        if срез == "rating":
            записи = self._топ_по_оценке(предел)
        elif срез == "votes":
            записи = self._топ_по_голосам(предел)
        else:
            записи = self._топ_свежего(предел)
        подпись = next(о for к, _, о in self.СРЕЗЫ_ТОПА if к == срез)
        текущая = ' aria-current="page"'
        вкладки = "".join(
            f'<a class="atabs__t{" is-on" if к == срез else ""}" '
            f'href="/top/?by={к}"{текущая if к == срез else ""}>'
            f'{html.escape(имя)}</a>'
            for к, имя, _ in self.СРЕЗЫ_ТОПА)
        if записи:
            содержимое = self.плитки(записи, вариант="catalog-title")
            счёт = f'<p class="zsub">Мест в списке: {len(записи)}.</p>'
        else:
            содержимое = (
                '<div class="zempty" data-top-state="empty">'
                '<b>Здесь пока пусто</b>'
                '<p>В этом срезе ещё нет записей. '
                '<a href="/catalog/">Открыть каталог</a>.</p></div>')
            счёт = ""
        self._http_status = 200
        тело = (
            f'<div class="zwrap atop-page" data-top-slice="{html.escape(срез)}" '
            f'data-top-count="{len(записи)}">'
            f'<h1 class="zh">Топ</h1>'
            f'<nav class="atabs" aria-label="Срезы топа">{вкладки}</nav>'
            f'<p class="zsub atop__method">{html.escape(подпись)}</p>'
            f'{счёт}{содержимое}</div>')
        канон = "/top/" if срез == "rating" else f"/top/?by={срез}"
        return self.оболочка(тело, f"Топ — {self.имя}", канон, актив="/top/",
                             описание=f"Топ аниме на витрине {self.имя}: {подпись}")

    # --- списки посетителя -------------------------------------------------

    #: Порядок разделов «Моего аниме». Он не алфавитный и не такой, как в
    #: хранилище: сверху то, что открывают чаще, — что смотрю сейчас и что
    #: собираюсь. «Брошено» внизу: этот раздел открывают реже всего.
    ПОРЯДОК_МОЕГО = ("watching", "planned", "watched", "favorite", "dropped")

    def страница_списков(self, зпр: dict) -> str:
        """«Моё аниме»: что посетитель отметил сам.

        Это ручные отметки, а не история просмотров: витрина не считает, что
        человек посмотрел, и называть эти разделы историей было бы неправдой.
        Хранятся они в том же хранилище сообщества и привязаны к обезличенному
        отпечатку посетителя — учётных записей у витрины нет.

        Адрес раздела не меняется: /lists/ остаётся, потому что на него уже
        могли сослаться. Меняется только то, как он называется и выглядит.
        """
        хранилище = сообщество()
        self._http_status = 200
        ЗАГОЛОВОК = "Моё аниме"
        if хранилище is None or not getattr(хранилище, "доступно", False):
            причина = getattr(хранилище, "причина", "") if хранилище else "модуль не подключён"
            тело = (
                '<div class="zwrap alists-page" data-lists="unavailable" '
                f'data-lists-reason="{html.escape(причина[:120])}">'
                f'<h1 class="zh">{ЗАГОЛОВОК}</h1>'
                '<div class="zempty"><b>Раздел временно недоступен</b>'
                '<p>Сейчас отметки нельзя сохранить. '
                '<a href="/catalog/">Открыть каталог</a>.</p></div></div>')
            return self.оболочка(тело, f"{ЗАГОЛОВОК} — {self.имя}", "/lists/",
                                 актив="/lists/",
                                 описание="Личные отметки посетителя.")
        разложено = хранилище.списки_посетителя(self._ключ_посетителя())
        по_slug = {з.get("slug"): з for з in self.д.items if з.get("slug")}
        по_ид: dict[str, dict] = {}
        for з in self.д.items:
            ид = str(з.get("id") or "").strip()
            if ид:
                по_ид.setdefault(ид, з)
        подписи = dict(СООБЩЕСТВО.СПИСКИ)
        всего = 0
        оглавление, блоки = [], []
        for ключ in self.ПОРЯДОК_МОЕГО:
            подпись = подписи.get(ключ)
            if подпись is None:
                continue
            записи = []
            for ссылка in разложено.get(ключ, []):
                # Ключом списка может быть и постоянный идентификатор, и адрес:
                # записи, сделанные до перехода на постоянный ключ, никуда не
                # делись и обязаны находиться.
                з = по_ид.get(str(ссылка)) or по_slug.get(str(ссылка))
                if з is not None and з not in записи:
                    записи.append(з)
            всего += len(записи)
            якорь = f"list-{ключ}"
            оглавление.append(
                f'<a class="amine__tab{" is-empty" if not записи else ""}" '
                f'href="#{якорь}">{html.escape(подпись)}'
                f'<b>{len(записи)}</b></a>')
            if not записи:
                continue
            блоки.append(
                f'<section class="zsec" id="{якорь}" data-list="{ключ}" '
                f'data-list-count="{len(записи)}">'
                f'<div class="zsec__h"><h2>{html.escape(подпись)}</h2>'
                f'<a href="/catalog/">В каталог</a></div>'
                f'{self.плитки(записи, вариант="catalog-title")}</section>')
        if not блоки:
            содержимое = (
                '<div class="zempty" data-lists="empty"><b>Здесь пока пусто</b>'
                '<p>Откройте любое аниме и отметьте его — «Смотрю», '
                '«Буду смотреть» или «Любимое». Отметки появятся в этом '
                'разделе. <a href="/catalog/">Перейти в каталог</a>.</p></div>')
        else:
            содержимое = "".join(блоки)
        тело = (
            f'<div class="zwrap alists-page" data-lists="on" '
            f'data-lists-total="{всего}">'
            f'<h1 class="zh">{ЗАГОЛОВОК}</h1>'
            f'<p class="zsub">Ваши отметки. Они сохраняются в этом браузере и '
            f'видны только вам; историю просмотров витрина не ведёт. '
            f'Всего отмечено: {всего}.</p>'
            f'<nav class="amine__tabs" aria-label="Разделы моего аниме">'
            f'{"".join(оглавление)}</nav>'
            f'{содержимое}</div>')
        return self.оболочка(тело, f"{ЗАГОЛОВОК} — {self.имя}", "/lists/",
                             актив="/lists/",
                             описание=f"Личные отметки на витрине {self.имя}.")

    #: Путь к наблюдениям расписания. Как и реестр серий, файл лежит рядом со
    #: снимком каталога: его обновляет обработчик, а не пересборка релиза.
    #: Имя переменной задаёт `run.py`.

    ДНИ_НЕДЕЛИ = ("Понедельник", "Вторник", "Среда", "Четверг",
                  "Пятница", "Суббота", "Воскресенье")
    ДНИ_КОРОТКО = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")

    def _наблюдения_расписания(self) -> dict:
        путь = Path(os.environ.get(
            "ANIMEDIA_SCHEDULE",
            str(_КОРЕНЬ_РАНТАЙМА / f"{САЙТ_ID}-schedule.json")))
        if not путь.is_file():
            return {}
        try:
            сырое = json.loads(путь.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return сырое if isinstance(сырое, dict) else {}

    def расписание(self) -> str:
        """Недельное расписание эфира.

        Источник отдаёт окно целиком — семь суток от сегодняшнего дня по
        Москве, — поэтому неделя показывается полностью, а не копится по
        одному дню. Окно перезабирается каждым обновлением, и перенос или
        отмена показа видны: пропавшее событие исчезает, сдвинутое встаёт на
        новое место.

        Три состояния дня различаются и НЕ сливаются в ноль:

        * день попал в загруженное окно, событий нет — «В этот день релизов
          нет». Это ответ, а не пустота;
        * день в окно не попал или данных ещё нет — «Расписание уточняется»;
        * источник отказал — показывается последнее корректное расписание с
          пометкой, а не пустой экран.

        Время здесь — время ЭФИРА. Время появления серии на нашем сайте живёт
        в ленте «Новые серии» и подписано «Добавлено»: это разные события, и
        подставлять одно вместо другого нельзя.
        """
        снимок = self._наблюдения_расписания()
        события = [з for з in (снимок.get("events") or []) if isinstance(з, dict)]
        покрытые = {str(д) for д in (снимок.get("covered_days") or [])}
        устарело = bool(снимок.get("stale"))
        сегодня = datetime.now(АНИМЕДИА_TZ)
        текущий = сегодня.weekday()

        по_ид: dict[str, dict] = {}
        по_slug = {з.get("slug"): з for з in self.д.items if з.get("slug")}
        for з in self.д.items:
            ид = str(з.get("id") or "").strip()
            if ид:
                по_ид.setdefault(ид, з)

        # Каждой вкладке — конкретная дата: ближайшее наступление этого дня
        # недели внутри окна. Без даты «вторник» на переходе недели означал бы
        # то прошедший вторник, то будущий.
        даты: dict[int, str] = {}
        for н in range(7):
            д = сегодня + timedelta(days=(н - текущий) % 7)
            даты[н] = д.strftime("%Y-%m-%d")

        по_дням: dict[int, list] = {н: [] for н in range(7)}
        показано = 0
        for с in события:
            запись = по_ид.get(str(с.get("content_id") or "")) or по_slug.get(
                str(с.get("slug") or ""))
            if запись is None:
                continue
            дата = str(с.get("date") or "")
            день = None
            for н, d in даты.items():
                if d == дата:
                    день = н
                    break
            if день is None:
                continue
            деталь = self.деталь(запись["slug"]) or {}
            доступно = sum(int(к.get("avail") or 0)
                           for к in (деталь.get("seasons") or []) if isinstance(к, dict))
            эпизод = int(с.get("episode") or 0)
            по_дням[день].append({
                "запись": запись,
                "время": str(с.get("time_local") or ""),
                "эпизод": эпизод,
                "вышла": bool(эпизод and доступно >= эпизод),
                "доступно": доступно,
            })
            показано += 1

        вкладки = "".join(
            f'<button type="button" class="asch__tab" data-day="{н}" '
            f'role="tab" aria-selected="{"true" if н == текущий else "false"}" '
            f'aria-controls="sch-day-{н}" id="sch-tab-{н}">'
            f'<span class="asch__tab-l">{self.ДНИ_НЕДЕЛИ[н]}</span>'
            f'<span class="asch__tab-s" aria-hidden="true">{self.ДНИ_КОРОТКО[н]}</span>'
            f'<b>{len(по_дням[н])}</b></button>'
            for н in range(7))

        панели = []
        нет_данных = 0
        for н in range(7):
            строки = sorted(по_дням[н], key=lambda з: (з["время"] or "99:99"))
            загружен = даты[н] in покрытые
            if строки:
                тело_дня = ('<div class="asch__grid">'
                            + "".join(self._ряд_расписания(з) for з in строки)
                            + "</div>")
                состояние = "loaded"
            elif загружен:
                тело_дня = ('<p class="asch__none">В этот день релизов нет.</p>')
                состояние = "empty"
            else:
                нет_данных += 1
                тело_дня = ('<p class="asch__none asch__none--wait">'
                            'Расписание уточняется.</p>')
                состояние = "unknown"
            панели.append(
                f'<div class="asch__day" id="sch-day-{н}" role="tabpanel" '
                f'data-day-state="{состояние}" data-day-date="{даты[н]}" '
                f'aria-labelledby="sch-tab-{н}"{"" if н == текущий else " hidden"}>'
                f'{тело_дня}</div>')

        # Ни одного дня с данными — значит источник ещё не отвечал ни разу.
        # Это не «релизов нет на неделе», и говорить так нельзя.
        if not покрытые:
            тело = (
                '<div class="zwrap asch-page" data-b04="nodata">'
                '<h1 class="zh">Расписание</h1>'
                '<p class="zsub">Расписание уточняется: данные ещё не '
                'получены.</p>'
                '<div class="zempty"><b>Расписание уточняется</b>'
                '<p><a href="/catalog/?ongoing=1">Что сейчас выходит</a> · '
                '<a href="/new/">Новое в каталоге</a>.</p></div></div>')
            return self.оболочка(тело, f"Расписание — {self.имя}", "/schedule/",
                                 актив="/schedule/",
                                 описание="Расписание выхода серий.")

        предупреждение = ""
        if устарело:
            предупреждение = (
                '<p class="asch__stale" data-schedule-stale="1">'
                'Источник расписания сейчас недоступен — показано последнее '
                'полученное расписание.</p>')

        тело = (
            f'<div class="zwrap asch-page" data-b04="weekly" '
            f'data-schedule-events="{показано}" data-schedule-today="{текущий}" '
            f'data-schedule-days-known="{7 - нет_данных}" '
            f'data-schedule-stale="{"1" if устарело else "0"}" '
            f'data-schedule-tz="{html.escape(str(снимок.get("timezone") or "Europe/Moscow"))}">'
            f'<h1 class="zh">Расписание</h1>'
            f'<p class="zsub">Время выхода новых серий. '
            f'Время московское (UTC+3).</p>'
            f'{предупреждение}'
            f'<div class="asch__tabs" role="tablist" '
            f'aria-label="Дни недели">{вкладки}</div>'
            f'{"".join(панели)}</div>')
        return self.оболочка(тело, f"Расписание — {self.имя}", "/schedule/",
                             актив="/schedule/",
                             описание=f"Расписание выхода серий на витрине {self.имя}.")

    def _ряд_расписания(self, з: dict) -> str:
        """Строка дня: мини-постер, название, номер серии, время эфира."""
        запись = з["запись"]
        изо = заглушка_постера(запись, "asch__none-p", "asch__img", 54, 81)
        эпизод = int(з.get("эпизод") or 0)
        if з["вышла"]:
            адрес = self.адрес_эпизода(запись["slug"], 1, min(эпизод, з["доступно"]))
            метка = '<span class="asch__out">уже доступна</span>'
        else:
            адрес = запись["url"]
            метка = ""
        время = (f'<span class="asch__time">{html.escape(з["время"])}</span>'
                 if з["время"] else
                 '<span class="asch__time asch__time--soon">Время уточняется</span>')
        подпись_серии = f"Серия {эпизод}" if эпизод else "Новая серия"
        return (
            f'<a class="asch__row" href="{html.escape(адрес)}" '
            f'data-expected-episode="{эпизод}" '
            f'data-aired="{"1" if з["вышла"] else "0"}">'
            f'<span class="asch__thumb">{изо}</span>'
            f'<span class="asch__body">'
            f'<span class="asch__t">{html.escape(запись["title"])}</span>'
            f'<span class="asch__ep">{подпись_серии}{метка}</span></span>'
            f'{время}</a>')


#: Вид Animedia появляется только у витрины, объявившей переработанное
#: оформление. Витрина на 1.0.2/1.1.0 исполняет прежнюю ветку и отдаёт прежние
#: байты — как и было до этой задачи.
ВИДЫ_1_1 = {"animedia": ВидАнимедиа}
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
        # `_rating` здесь больше не трогается. Раньше он ставился как максимум
        # из Кинопоиска и IMDb, а индекс строится после обогащения снимка —
        # то есть это значение затирало сводную. На карточке посетитель видел
        # сводную, а каталог сортировался по максимуму из двух источников:
        # одно и то же слово «оценка» означало два разных числа, и порядок в
        # выдаче выглядел случайным. Определение теперь одно — сводная.
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
        if getattr(self, "_новая_кука", ""):
            self.send_header(
                "Set-Cookie",
                f"{self.COOKIE_ПОСЕТИТЕЛЯ}={self._новая_кука}; Path=/; Max-Age=31536000; "
                f"SameSite=Lax; HttpOnly")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(тело)

    #: Имя cookie, по которой различаются посетители. Внутри — случайная
    #: строка, никаких данных о человеке: она нужна только чтобы «один голос
    #: от одного посетителя» работал без учётных записей, которых у витрины
    #: нет.
    COOKIE_ПОСЕТИТЕЛЯ = "amd_v"

    def _прочитать_куку(self) -> str:
        сырое = self.headers.get("Cookie") or ""
        for кусок in сырое.split(";"):
            имя, _, значение = кусок.strip().partition("=")
            if имя == self.COOKIE_ПОСЕТИТЕЛЯ and значение:
                return значение[:64]
        return ""

    def _подготовить_посетителя(self) -> None:
        """Запомнить ключ посетителя для этого запроса и выдать его, если нет."""
        self._заголовки_запроса = self.headers
        self._адрес_клиента = (self.client_address or ("",))[0]
        кука = self._прочитать_куку()
        self._новая_кука = ""
        if not кука:
            кука = secrets.token_urlsafe(16)
            self._новая_кука = кука
        self._куки_посетителя = кука

    def do_HEAD(self):
        self.do_GET()

    def do_POST(self):
        """Формы сообщества. Отвечает перенаправлением: повторная отправка при
        обновлении страницы не должна ставить второй голос."""
        self._подготовить_посетителя()
        разбор = urlparse(self.path)
        путь = unquote(разбор.path).rstrip("/") or "/"
        if путь == "/event/play":
            return self._событие_просмотра()
        if not путь.startswith("/community/"):
            return self._отдать(b"", код=404, тип="text/plain; charset=utf-8")
        длина = int(self.headers.get("Content-Length") or 0)
        сырое = self.rfile.read(длина).decode("utf-8", "replace") if длина else ""
        поля = {k: (v[0] if v else "") for k, v in parse_qs(сырое, keep_blank_values=True).items()}
        slug = str(поля.get("slug") or "").strip()
        назад = str(поля.get("back") or "/").strip() or "/"
        if not назад.startswith("/"):
            назад = "/"
        хранилище = сообщество()
        if хранилище is None or not хранилище.доступно or not slug:
            return self._перенаправить(назад + "?community=unavailable")
        ключ = self._ключ_посетителя_запроса()
        # CSRF до любой записи. Токен выводится из куки посетителя, а куку
        # чужой сайт прочитать не может: значит, не может и вычислить токен.
        # `SameSite=Lax` на куке уже не пустит чужую форму, но одна защита —
        # это ноль защит, когда она отключится. Правило одного голоса делает
        # цену промаха необратимой: чужая форма поставила бы оценку, которую
        # посетитель потом не сможет изменить.
        if not self._csrf_совпал(поля.get("csrf") or ""):
            return self._перенаправить(назад + "?community=csrf")
        # Ключ темы вычисляет сервер по своему снимку подробностей, а не
        # принимает из формы: присланный клиентом идентификатор позволил бы
        # писать в чужую тему.
        тема = тема_сообщества(self.подробности, slug)
        if not тема:
            return self._перенаправить(назад + "?community=error&why=unknown-title")
        try:
            if путь == "/community/vote":
                # Первая сохранённая оценка окончательна — решает хранилище,
                # под той же блокировкой, под которой пишет. Снятия больше нет.
                значение = int(поля.get("value") or 0)
                # Внешние оценки передаются вместе с голосом: стартовая база
                # закрепляется ПЕРВЫМ голосом, и без них она не закрепится
                # вовсе — запись навсегда осталась бы считаться по другому
                # правилу, чем соседние.
                деталь = self.подробности.get(slug) or {}
                хранилище.добавить_голос(
                    тема, значение, ключ, slug=slug,
                    внешние=внешние_для_базы(деталь),
                    приоритет=АНИМЕДИА_ПРИОРИТЕТ_БАЗЫ)
                return self._перенаправить(
                    f"{назад}?community=vote-ok&mine={значение}#community")
            elif путь == "/community/reaction":
                хранилище.переключить_реакцию(
                    тема, str(поля.get("reaction") or ""), ключ, slug=slug)
            elif путь == "/community/comment":
                хранилище.добавить_комментарий(
                    тема, поля.get("name") or "", поля.get("text") or "", ключ,
                    slug=slug)
                return self._перенаправить(назад + "?community=pending#community")
            elif путь == "/community/list":
                # Пустое значение — «убрать из списков»: у кнопки, которая
                # умеет только добавлять, нет обратного хода.
                выбор = str(поля.get("list") or "").strip() or None
                хранилище.выбрать_список(тема, выбор, ключ, slug=slug)
            else:
                return self._отдать(b"", код=404, тип="text/plain; charset=utf-8")
        except СООБЩЕСТВО.ГолосЗакреплён as закреплён:
            # Не ошибка ввода: посетитель уже голосовал, и ему показывается
            # его собственная оценка, а не сообщение о сбое.
            return self._перенаправить(
                f"{назад}?community=voted&mine={закреплён.сохранённая}#community")
        except (ValueError, RuntimeError) as ош:
            return self._перенаправить(f"{назад}?community=error&why={quote(str(ош)[:80])}")
        return self._перенаправить(назад + "?community=ok#community")

    def _событие_просмотра(self):
        """Плеер сообщил, что воспроизведение началось.

        Принимается только идентификатор записи, и только существующий: без
        проверки по каталогу endpoint стал бы счётчиком произвольных строк.
        Ответ короткий и без тела — это маячок, а не запрос данных.
        """
        длина = int(self.headers.get("Content-Length") or 0)
        if длина > 512:
            return self._отдать(b"", код=413, тип="text/plain; charset=utf-8")
        сырое = self.rfile.read(длина).decode("utf-8", "replace") if длина else ""
        поля = {k: (v[0] if v else "")
                for k, v in parse_qs(сырое, keep_blank_values=True).items()}
        ид = str(поля.get("id") or "").strip()[:64]
        подр = getattr(self.подробности, "записи", None) or {}
        известен = any(str((з or {}).get("id") or "") == ид for з in подр.values())
        if not ид or not известен:
            return self._отдать(b"", код=204, тип="text/plain; charset=utf-8")
        засчитать_просмотр(ид, self._ключ_посетителя_запроса())
        return self._отдать(b"", код=204, тип="text/plain; charset=utf-8")

    def _ключ_посетителя_запроса(self) -> str:
        кука = getattr(self, "_куки_посетителя", "")
        if кука:
            return кука
        вперёд = (self.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
        return вперёд or (self.client_address or ("гость",))[0]

    def _csrf(self) -> str:
        """Токен двойной отправки, выведенный из куки посетителя.

        Куку нельзя прочитать со стороннего сайта (HttpOnly), значит нельзя и
        вычислить токен. Посетителю без куки токен не выдаётся и записи не
        разрешаются: кука ставится первым же ответом, поэтому пустой токен
        означает не «новый посетитель», а запрос мимо страницы.
        """
        кука = getattr(self, "_куки_посетителя", "") or getattr(self, "_новая_кука", "")
        if not кука:
            return ""
        return hashlib.sha256(
            ("animedia-community-csrf/1:" + кука).encode("utf-8")).hexdigest()[:32]

    def _csrf_совпал(self, присланный: str) -> bool:
        свой = self._csrf()
        if not свой or not присланный:
            return False
        return secrets.compare_digest(свой, str(присланный))

    def _перенаправить(self, куда: str) -> None:
        self.send_response(303)
        self.send_header("Location", куда)
        if getattr(self, "_новая_кука", ""):
            self.send_header(
                "Set-Cookie",
                f"{self.COOKIE_ПОСЕТИТЕЛЯ}={self._новая_кука}; Path=/; Max-Age=31536000; "
                f"SameSite=Lax; HttpOnly")
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def do_GET(self):
        self._подготовить_посетителя()
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
            # Состояние горячей перезагрузки: по нему видно, что витрина
            # подхватывает новый снимок сама, а не ждёт перезапуска.
            свод["snapshot_watch"] = СНИМОК_СОСТОЯНИЕ.get("наблюдение")
            свод["snapshot_reloads"] = СНИМОК_СОСТОЯНИЕ.get("перезагрузок", 0)
            свод["snapshot_reloaded_at"] = СНИМОК_СОСТОЯНИЕ.get("последняя")
            свод["snapshot_reload_errors"] = СНИМОК_СОСТОЯНИЕ.get("ошибок", 0)
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
            player_path = (_КОРЕНЬ_РАНТАЙМА / f"player-{site_hint}.json"
                           if site_hint else None)
            tmpl_path = (_КОРЕНЬ_РАНТАЙМА / f"template-manifest-{site_hint}.json"
                         if site_hint else None)

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
            цвет = (СЕМЕЙСТВА_1_1["animedia"])["токены"]["acc"]
            метка = (СЕМЕЙСТВА_1_1["animedia"])["метка"]
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
    #: Расписание у Animedia своё, а хаб жанров теперь настоящая страница —
    #: подменять их соседними разделами больше не нужно.
    ПРЕЖНИЕ_АДРЕСА: dict = {}

    #: Разделы по формату произведения. Ключи — значения фасета `type` из
    #: снимка подробностей, а не выдуманные подписи.
    #:
    #: Прежде эти маршруты фильтровали по `kind` значениями «Фильм», «Сериал»,
    #: «Мультфильм». В каталоге Animedia `kind` у всех 7426 записей один и тот
    #: же — «Аниме», поэтому каждый из трёх разделов честно находил ноль и
    #: показывал «Найдено 0» под панелью фильтров, где рядом было написано
    #: «MOVIE 1922, TV 5504». Значения пришли из чужого профиля вместе с
    #: механикой страниц; здесь они заменены на те, что есть в данных.
    МАРШРУТЫ_ВИДА: dict = {}
    МАРШРУТЫ_ТИПА = {
        "/movies": "movie",
        "/series": "tv",
    }
    #: Вся витрина — анимация, поэтому отдельного раздела «Анимация» у неё нет:
    #: он повторял бы каталог целиком. Ссылка ведёт в каталог, а не в пустоту.
    ПЕРЕХОДЫ_РАЗДЕЛОВ = {
        "/animation": "/catalog/",
    }

    #: Исторические slug → канонический. 301 с сохранением season/episode.
    #: Измерено: …domokhozyaykoy 404, live slug …domohozyaykoy.
    SLUG_ALIASES = {
        "sudmedekspert-stavshaya-domokhozyaykoy":
            "sudmedekspert-stavshaya-domohozyaykoy",
    }

    def вид(self) -> Вид:
        описание = СЕМЕЙСТВА_1_1["animedia"]
        класс = ВИДЫ_1_1.get("animedia", ВидАнимедиа)
        экземпляр = класс(описание, self.данные, self.подробности, self.индекс,
                          ИМЯ_ВИТРИНЫ)
        # Канонический адрес берётся из запроса, а не из настройки: витрина
        # отвечает на том имени, по которому к ней пришли, и подставлять сюда
        # другое значило бы объявлять канонической чужую страницу.
        экземпляр.хост = (self.headers.get("Host") or "").split(":")[0]
        # Вид спрашивает у обработчика ключ посетителя: он живёт в cookie
        # запроса, а не в самом виде.
        экземпляр._обработчик = self
        экземпляр._куки_посетителя = getattr(self, "_куки_посетителя", "")
        return экземпляр

    def _переход(self, цель: str):
        self.send_response(308)
        self.send_header("Location", цель)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def маршрут_1_1(self, путь: str, зпр: dict):
        в = self.вид()
        # Итог отправки формы приходит параметром адреса (303 → GET). Без него
        # страница после сохранения выглядит точно так же, как до него, и
        # посетитель не знает, применилось ли действие и не отказано ли в нём.
        в._зпр = зпр
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
            return self._отдать(в.главная(зпр).encode("utf-8"))
        # Clean kind routes (базу profile surfaces). Canonical = own path
        # (/movies/, /series/, /animation/), not a silent rewrite to /catalog/.
        if обрезанный in self.ПЕРЕХОДЫ_РАЗДЕЛОВ:
            return self._переход(self.ПЕРЕХОДЫ_РАЗДЕЛОВ[обрезанный])
        if обрезанный in self.МАРШРУТЫ_ТИПА:
            зпр = dict(зпр)
            зпр["type"] = [self.МАРШРУТЫ_ТИПА[обрезанный]]
            return self._отдать(в.список(обрезанный, зпр).encode("utf-8"))
        if обрезанный in self.МАРШРУТЫ_ВИДА:
            kind = self.МАРШРУТЫ_ВИДА[обрезанный]
            зпр = dict(зпр)
            зпр["kind"] = [kind]
            return self._отдать(в.список(обрезанный, зпр).encode("utf-8"))
        if обрезанный == "/genres":
            return self._отдать(в.хаб_жанров().encode("utf-8"))
        if обрезанный == "/types":
            return self._отдать(в.хаб_типов().encode("utf-8"))
        if обрезанный == "/top":
            return self._отдать(в.страница_топа(зпр).encode("utf-8"))
        if обрезанный == "/lists":
            return self._отдать(в.страница_списков(зпр).encode("utf-8"))
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
            # Хаб подборок соседнего контура здесь не нужен: у Animedia
            # свой хаб коллекций, и его собирает вид.
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
            # У Animedia канон жанра — query на каталоге, а не отдельный
            # путь; поэтому здесь переход, а не своя выдача.
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
        # Значения по умолчанию сохраняют прежнее поведение базу и базу.
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



# ----------------------------------------------------------------------
#  Горячая перезагрузка снимка каталога
# ----------------------------------------------------------------------
#
# Снимок каталога обновляется конвейером содержимого раз в сутки. Витрина
# читала его один раз при старте, и до перезапуска «Недавно добавленные» и
# «Новые серии» показывали вчерашний день: измерено — снимок обновился в
# 04:11, а живой процесс, поднятый накануне, держал прежний.
#
# Поэтому файл наблюдается фоновым потоком. Чтение идёт в новые объекты, и
# только когда они собраны целиком, ссылки подменяются разом: запрос,
# пришедший во время перечитывания, обслуживается прежними данными, а не
# половиной новых. Ошибка чтения оставляет прежний снимок — лучше вчерашний
# каталог, чем пустая витрина.

СНИМОК_ИНТЕРВАЛ_СЕК = float(os.environ.get("ANIMEDIA_SNAPSHOT_POLL_SECONDS", "30"))
_снимок_замок = threading.Lock()
_снимок_отпечаток: tuple = ()
СНИМОК_СОСТОЯНИЕ: dict = {"перезагрузок": 0, "последняя": None, "ошибок": 0,
                          "последняя_ошибка": None, "наблюдение": "не запущено",
                          "оригинальных_названий": 0}


def _отпечаток_снимка() -> tuple:
    метки = []
    for путь in (КАТАЛОГ_ФАЙЛ, ПОДРОБНОСТИ_ФАЙЛ):
        if not путь:
            continue
        try:
            st = os.stat(путь)
            метки.append((str(путь), st.st_mtime_ns, st.st_size))
        except OSError:
            метки.append((str(путь), 0, 0))
    return tuple(метки)


def освежить_снимок(принудительно: bool = False) -> bool:
    """Перечитать каталог, если файл на диске сменился. True — перечитали."""
    global _снимок_отпечаток
    with _снимок_замок:
        отпечаток = _отпечаток_снимка()
        if not принудительно and отпечаток == _снимок_отпечаток:
            return False
        try:
            данные = Данные(КАТАЛОГ_ФАЙЛ)
            подробности = Подробности(ПОДРОБНОСТИ_ФАЙЛ)
            # Оригинальные названия живут в подробностях, а искать по ним
            # витрина обещает на форме поиска. Указатель достраивается здесь,
            # пока снимок ещё не подменил боевой.
            данные.обогатить_подробностями(подробности)
            индекс = построить_индекс(данные, подробности)
        except (OSError, ValueError, KeyError) as ош:
            СНИМОК_СОСТОЯНИЕ["ошибок"] += 1
            СНИМОК_СОСТОЯНИЕ["последняя_ошибка"] = f"{type(ош).__name__}: {ош}"
            print(f"[nova] снимок не перечитан, остаёмся на прежнем: {ош}", flush=True)
            return False
        Обработчик.данные = данные
        Обработчик.подробности = подробности
        Обработчик.индекс = индекс
        Снимок.сбросить()
        _снимок_отпечаток = отпечаток
        СНИМОК_СОСТОЯНИЕ["перезагрузок"] += 1
        СНИМОК_СОСТОЯНИЕ["последняя"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        СНИМОК_СОСТОЯНИЕ["каталог_собран"] = getattr(данные, "built_at", "")
        СНИМОК_СОСТОЯНИЕ["ревизия"] = getattr(данные, "revision", "")
        СНИМОК_СОСТОЯНИЕ["записей"] = len(данные.items)
        СНИМОК_СОСТОЯНИЕ["оригинальных_названий"] = int(
            getattr(данные, "оригинальных_названий", 0) or 0)
        print(f"[nova] снимок перечитан: записей {len(данные.items)} "
              f"ревизия {getattr(данные, 'revision', '')[:12]}", flush=True)
        return True


def _наблюдать_за_снимком() -> None:
    while True:
        time.sleep(max(5.0, СНИМОК_ИНТЕРВАЛ_СЕК))
        try:
            освежить_снимок()
        except Exception as ош:  # поток не должен умирать молча
            СНИМОК_СОСТОЯНИЕ["ошибок"] += 1
            СНИМОК_СОСТОЯНИЕ["последняя_ошибка"] = f"{type(ош).__name__}: {ош}"
            print(f"[nova] наблюдение за снимком: {ош}", flush=True)


def запустить_наблюдение_за_снимком() -> None:
    поток = threading.Thread(target=_наблюдать_за_снимком, name="снимок",
                             daemon=True)
    поток.start()
    СНИМОК_СОСТОЯНИЕ["наблюдение"] = f"каждые {max(5.0, СНИМОК_ИНТЕРВАЛ_СЕК):.0f} с"


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--host", default="127.0.0.1")
    р.add_argument("--port", type=int, required=True)
    args = р.parse_args()
    освежить_снимок(принудительно=True)
    запустить_наблюдение_за_снимком()
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
