#!/usr/bin/env python3
"""Лента изменений источника: что поменялось с прошлого раза.

Зачем
-----

Сегодня наша система узнаёт об изменении из СУТОЧНОГО снимка: конвейер собирает
его раз в день, и до этого момента новая серия невидима. Согласование в витрине
после доставки выправляет запись за полчаса (замерено: 44 записи изменили
состав между снимками b27f16f7 и e1469f33, два прохода по 40), но сама ЗАДЕРЖКА
ОБНАРУЖЕНИЯ остаётся суточной, и прятать её за «тридцатью минутами» нечестно.

Опрос плейлиста этого не решает: слой активно выходящих у одной витрины — 257
записей, круг по нему 4.2 часа, а чтобы уложиться в полчаса, пришлось бы
спрашивать по двести записей за проход с каждой витрины. Это пятикратный рост
запросов к одному поставщику ради данных, которые он готов отдать сам.

Подтверждённая возможность источника
------------------------------------

`knowledge/cdnvideohub/content-api.yaml` (замороженный контракт, снят с
клиента поставщика) объявляет у списка титулов фильтр `updated_since`. То есть
источник умеет отвечать «вот что изменилось с момента X» — ровно то, что нужно,
и это не догадка о методе, а записанный контракт.

Токен здесь СЕРВЕРНЫЙ (`browser_forbidden: true`), поэтому инструмент
принадлежит конвейеру, а не витрине: у ячейки этого токена нет и быть не
должно.

Что делает
----------

Спрашивает список титулов с `updated_since` от прошлого удачного прогона,
складывает изменившиеся записи в компактную ленту и двигает отметку времени.
Лента — вход для `nova-seasons-complete.py` и для доставки в ячейки: получив
её, витрина ставит эти записи в голову очереди согласования, и появление серии
перестаёт зависеть от суточного цикла.

Чего не делает
--------------

Не публикует каталог, не трогает снимок, оценки, разметку и витрины. Без
`--apply` не двигает отметку времени: прогон, который сдвинул курсор и упал,
потерял бы окно изменений навсегда.
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

БАЗА = "https://public-api.cdnvideohub.com/api/v1/"
#: Имя файла с отметкой последнего удачного прогона.
СОСТОЯНИЕ = "updated-since-state.json"
#: Предохранитель от зациклившейся постраничности — из того же контракта.
ПРЕДЕЛ_СТРАНИЦ = 2000


class ИсточникНедоступен(RuntimeError):
    """Запрос не состоялся. Это НЕ вывод «ничего не изменилось»."""


def токен() -> str:
    """Серверный токен из окружения службы. В отчёт и в лог не попадает."""
    имя = os.environ.get("CDNVIDEOHUB_API_TOKEN_CREDENTIAL", "cdnvideohub_api_token")
    каталог = os.environ.get("CREDENTIALS_DIRECTORY")
    if каталог:
        путь = Path(каталог) / имя
        if путь.is_file():
            return путь.read_text(encoding="utf-8").strip()
    значение = os.environ.get("CDNVIDEOHUB_API_TOKEN", "").strip()
    if not значение:
        raise SystemExit("нет серверного токена: ни LoadCredential, ни окружение "
                         "его не дали. Спрашивать источник нечем.")
    return значение


def страница(путь: str, параметры: dict, ключ: str, таймаут: float = 30.0) -> dict:
    адрес = БАЗА + путь + "?" + urllib.parse.urlencode(
        {к: в for к, в in параметры.items() if в not in (None, "")})
    запрос = urllib.request.Request(адрес, headers={
        "Authorization": f"Bearer {ключ}", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(запрос, timeout=таймаут) as ответ:
            return json.loads(ответ.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise ИсточникНедоступен(f"HTTP {e.code}") from e
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as e:
        raise ИсточникНедоступен(str(e)) from e


def изменённые(ключ: str, с_момента: str, размер: int = 100,
               предел_страниц: int = ПРЕДЕЛ_СТРАНИЦ) -> list:
    """Титулы, изменившиеся с указанного момента. Постранично, с курсором.

    Условия завершения оба, как велит контракт: `has_more=false` ЛИБО пустой
    курсор. Источник, вернувший `has_more=true` с пустым курсором, зациклил бы
    обход. Повтор курсора тоже прекращает обход.
    """
    итог, курсор, видели, страниц = [], "", set(), 0
    while страниц < предел_страниц:
        тело = страница("titles", {"updated_since": с_момента, "limit": размер,
                                   "cursor": курсор or None}, ключ)
        for з in (тело.get("items") or []):
            if isinstance(з, dict):
                итог.append(з)
        страниц += 1
        дальше = str(тело.get("next_cursor") or "")
        if not тело.get("has_more") or not дальше or дальше in видели:
            break
        видели.add(дальше)
        курсор = дальше
    return итог


def лента(записи: list, с_момента: str) -> dict:
    """Компактная лента: только опознание записи и когда её изменили."""
    строки = []
    for з in записи:
        ид = str(з.get("id") or "").strip()
        if not ид:
            continue
        строки.append({"id": ид, "slug": str(з.get("slug") or ""),
                       "updated_at": str(з.get("updated_at") or "")})
    return {
        "schema": "nova.updates-feed/1",
        "note": ("Что изменилось у поставщика с прошлого прогона. Вход для "
                 "nova-seasons-complete.py и для очереди согласования витрин: "
                 "получив ленту, витрина ставит эти записи в голову очереди, и "
                 "появление серии перестаёт зависеть от суточного цикла."),
        "since": с_момента,
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "count": len(строки),
        "items": строки,
    }


def main(argv=None) -> int:
    р = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    р.add_argument("--state-dir", required=True,
                   help="куда класть отметку времени и ленту")
    р.add_argument("--feed", default="", help="путь ленты; по умолчанию в state-dir")
    р.add_argument("--fallback-hours", type=float, default=24.0,
                   help="окно первого прогона, когда отметки ещё нет")
    р.add_argument("--apply", action="store_true",
                   help="сдвинуть отметку времени; без флага только лента")
    args = р.parse_args(argv)

    каталог = Path(args.state_dir)
    каталог.mkdir(parents=True, exist_ok=True)
    отметка_путь = каталог / СОСТОЯНИЕ
    try:
        с_момента = str(json.loads(отметка_путь.read_text(encoding="utf-8"))["since"])
    except (OSError, ValueError, KeyError):
        с_момента = time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                  time.gmtime(time.time() - args.fallback_hours * 3600))

    начало = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        записи = изменённые(токен(), с_момента)
    except ИсточникНедоступен as ош:
        # Отметка НЕ двигается: иначе окно изменений потеряно навсегда, и
        # витрины никогда не узнают о том, что произошло в этот промежуток.
        print(json.dumps({"status": "source-unavailable", "since": с_момента,
                          "reason": str(ош)[:120]}, ensure_ascii=False))
        return 1

    данные = лента(записи, с_момента)
    путь_ленты = Path(args.feed) if args.feed else каталог / "updates-feed.json"
    врем = путь_ленты.with_suffix(путь_ленты.suffix + ".tmp")
    врем.write_text(json.dumps(данные, ensure_ascii=False), encoding="utf-8")
    врем.replace(путь_ленты)
    if args.apply:
        отметка_путь.write_text(json.dumps({"since": начало}, ensure_ascii=False),
                                encoding="utf-8")
    print(json.dumps({"status": "OK", "since": с_момента, "until": начало,
                      "changed": данные["count"], "feed": str(путь_ленты),
                      "cursor_moved": bool(args.apply)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
