#!/usr/bin/env python3
"""Состояние счётчиков аналитики по каждому сайту: что измеримо и что нет.

Задание владельца требует установить по каждому сайту состояние Google
Analytics по четырём признакам: настройка, установленный тег, входящие события,
доступ к отчётам. Два из четырёх измеримы снаружи, два — нет, и их нельзя
выдавать ни за исправность, ни за поломку.

  объявлен        идентификатор назван в пакете сайта или в реестре
  установлен      живая страница грузит тег и несёт идентификатор
  события идут    НЕ ИЗМЕРИМО снаружи: нужен доступ к отчётам ресурса
  доступ к отчётам НЕ ИЗМЕРИМО снаружи: нужен сервисный аккаунт

Для Метрики те же два измеримых признака снимаются рядом — не для полноты, а
потому что контраст и есть ответ: если Метрика установлена, а GA нет, то дело
не в разметке и не в выкладке, а в отсутствии идентификаторов.

Идентификаторы НЕ придумываются: отсутствие объявленного значения — это
`BLOCKED_INPUT`, и инструмент называет внешнее действие, а не подставляет
заглушку.

    python3 automation/local/analytics-tags-state.py
"""
from __future__ import annotations

import argparse
import json
import re
import socket
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
РЕЕСТР = КОРЕНЬ / "config" / "site-cells.json"

#: Идентификатор ресурса GA4 в разметке: `G-` плюс минимум восемь знаков.
#: Строгая форма нужна, чтобы не считать тегом случайное «G-» в тексте.
GA_ID = re.compile(r"\bG-[A-Z0-9]{8,}\b")
#: Загрузка самой библиотеки. Без неё идентификатор в разметке ничего не делает.
GA_БИБЛИОТЕКА = re.compile(
    r"googletagmanager\.com/gtag/js|google-analytics\.com/analytics\.js", re.I)
#: Номер счётчика Метрики: вызов `ym(<номер>` ЛИБО `ym("<номер>"` — вторая
#: форма встречается у Yummy, и без кавычек в образце она терялась.
МЕТРИКА_НОМЕР = re.compile(r"""ym\(\s*["']?(\d{6,})["']?""")
МЕТРИКА_БИБЛИОТЕКА = re.compile(r"mc\.yandex\.ru/metrika", re.I)

ДА = "да"
НЕТ = "нет"
НЕ_ИЗМЕРИМО = "не измеримо снаружи"


#: Служебные имена стендов: домена в сети у них нет и быть не должно.
СТЕНДОВЫЕ = (".localhost", ".localhost.test")


def живые(реестр: Path) -> list[dict]:
    """Записи витрин, чьё имя РАЗРЕШАЕТСЯ, а не те, чья ячейка вынута.

    Поле `status` описывает состояние ячейки. `1lordserials1.online` и
    `lordserial33.biz` стоят `not_extracted`, но домены работают, и по ним
    состояние счётчиков надо знать так же, как по остальным.
    """
    д = json.loads(реестр.read_text(encoding="utf-8"))
    ячейки = д.get("cells") or д
    берём: list[dict] = []
    for запись in ячейки:
        домен = str(запись.get("domain") or "").strip()
        if not домен or any(домен.endswith(х) for х in СТЕНДОВЫЕ):
            continue
        try:
            socket.gethostbyname(домен)
        except OSError:
            continue
        берём.append(запись)
    return sorted(берём, key=lambda з: з["domain"])


def объявленный_ga(запись: dict) -> str:
    """Идентификатор GA4, объявленный в пакете сайта или в реестре.

    Ищется в названных полях, а не по всему документу: случайное совпадение
    в комментарии не является объявлением.
    """
    for поле in ("ga4_measurement_id", "ga_measurement_id", "ga4_id"):
        значение = str(запись.get(поле) or "").strip()
        if значение:
            return значение
    аналитика = запись.get("analytics") or {}
    if isinstance(аналитика, dict):
        for поле in ("ga4_measurement_id", "ga4_id", "measurement_id"):
            значение = str(аналитика.get(поле) or "").strip()
            if значение:
                return значение
    return ""


def снять(домен: str, предел: float) -> dict:
    контекст = ssl.create_default_context()
    контекст.check_hostname = False
    контекст.verify_mode = ssl.CERT_NONE
    открыть = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=контекст))
    запрос = urllib.request.Request(
        f"https://{домен}/", headers={"User-Agent": "factory-tags-state"})
    try:
        ответ = открыть.open(запрос, timeout=предел)
        разметка = ответ.read(400_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as сбой:
        return {"ошибка": f"HTTP {сбой.code}"}
    except Exception as сбой:
        return {"ошибка": f"{type(сбой).__name__}: {str(сбой)[:60]}"}
    ga = GA_ID.search(разметка)
    метрика = МЕТРИКА_НОМЕР.search(разметка)
    return {
        "ga_id": ga.group(0) if ga else "",
        "ga_библиотека": bool(GA_БИБЛИОТЕКА.search(разметка)),
        "метрика_номер": метрика.group(1) if метрика else "",
        "метрика_библиотека": bool(МЕТРИКА_БИБЛИОТЕКА.search(разметка)),
    }


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--registry", type=Path, default=РЕЕСТР)
    р.add_argument("--timeout", type=float, default=60.0)
    опции = р.parse_args(аргв)

    записи = живые(опции.registry)
    без_ga: list[str] = []
    неснятые: list[str] = []
    метрика_есть = 0
    номера: dict[str, list[str]] = {}

    print(f"{'домен':26s} {'GA объявлен':12s} {'GA установлен':14s} "
          f"{'Метрика':10s} номер")
    for запись in записи:
        домен = запись["domain"]
        снято = снять(домен, опции.timeout)
        if "ошибка" in снято:
            неснятые.append(домен)
            print(f"{домен:26s} {'—':12s} {'НЕ ИЗМЕРЕНО':14s} "
                  f"{'—':10s} {снято['ошибка']}")
            continue
        объявлен = объявленный_ga(запись)
        установлен = снято["ga_id"] and снято["ga_библиотека"]
        метрика = снято["метрика_номер"] and снято["метрика_библиотека"]
        метрика_есть += bool(метрика)
        if метрика:
            номера.setdefault(снято["метрика_номер"], []).append(домен)
        if not установлен:
            без_ga.append(домен)
        print(f"{домен:26s} {(объявлен or НЕТ):12s} "
              f"{(снято['ga_id'] if установлен else НЕТ):14s} "
              f"{(ДА if метрика else НЕТ):10s} {снято['метрика_номер'] or '—'}")

    print(f"\nживых доменов: {len(записи)}")
    print(f"   GA4 установлен:    {len(записи) - len(без_ga) - len(неснятые)}")
    print(f"   GA4 не установлен: {len(без_ga)}")
    print(f"   Метрика работает:  {метрика_есть}")
    if неснятые:
        print(f"   НЕ ИЗМЕРЕНО: {len(неснятые)} — {', '.join(неснятые)}")

    повторы = {н: д for н, д in номера.items() if len(д) > 1}
    if повторы:
        print("\nодин номер Метрики на нескольких доменах — данные смешаются:")
        for номер, домены in sorted(повторы.items()):
            print(f"   {номер}: {', '.join(домены)}")

    print("\nдва признака из четырёх снаружи НЕ ИЗМЕРИМЫ и исправностью "
          "не считаются:")
    print("   события идут     — нужен доступ к отчётам ресурса GA4")
    print("   доступ к отчётам — нужен сервисный аккаунт с правом чтения")

    if без_ga:
        print(f"\nВНЕШНЕЕ ДЕЙСТВИЕ (GA4 не установлен на {len(без_ga)} "
              "доменах). Нужны от владельца:")
        print("   1. ресурс GA4 на каждый домен и его measurement ID (G-…);")
        print("   2. сервисный аккаунт с правом чтения отчётов и его ключ "
              "через secret_ref;")
        print("   3. разрешение сети на googletagmanager.com, если выкладка "
              "идёт в закрытом контуре.")
        print("   Идентификаторы НЕ придумываются: пустое поле — это "
              "BLOCKED_INPUT, а не повод подставить значение.")

    if неснятые:
        return 2
    return 1 if без_ga else 0


if __name__ == "__main__":
    raise SystemExit(главное())
