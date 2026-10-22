#!/usr/bin/env python3
"""Спрос по доменам из снимка Метрики: визиты и ПОИСКОВЫЕ входы по страницам.

Только чтение снимка. Ни одного обращения к сети: снимок собирает отдельная
служба, а здесь он лишь разбирается.

ЧТО ЭТО ДАЁТ И ЧЕГО НЕ ДАЁТ. Снимок измеряет `search_landing_pages` —
поисковые входы по страницам, то есть «какие страницы спрос УЖЕ приводит».
Самих запросов в нём нет: `popular_queries` помечен как НЕ измеренный, причина
названа («webmaster: сеть недоступна»). Поэтому пара «запрос — страница» из
этого источника получается только наполовину, и вторая половина требует
доступа к Вебмастеру. Выдавать страницу за запрос нельзя.

Окно снимка — `7daysAgo…yesterday`, то есть ПОЛНЫЕ сутки, кончая днём перед
сбором. Файл однозначно задаёт неделю, и это свойство записано здесь, чтобы
следующий не сравнил перекрывающиеся окна как разные периоды.

    python3 automation/local/demand-from-metrika.py --snapshot <файл>
    python3 automation/local/demand-from-metrika.py --snapshot <файл> --write

Коды: 0 — спрос разобран; 2 — снимок не прочитан.
"""
from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
СПИСОК = КОРЕНЬ / "config" / "active-domains.json"
ВЫХОД = КОРЕНЬ / "config" / "demand-snapshot.json"
#: Сколько страниц сохраняется на домен. Ограничение намеренное: паспорт — не
#: выгрузка, в нём нужны страницы, по которым можно действовать.
СТРАНИЦ = 10


def активные() -> dict[str, str]:
    д = json.loads(СПИСОК.read_text(encoding="utf-8"))
    return {з["domain"]: з["site_id"] for з in д["domains"]}


def замер(запись: dict, ключ: str) -> dict | None:
    for з in запись.get("measurements") or []:
        if з.get("key") == ключ:
            return з
    return None


def число(запись: dict, ключ: str) -> int | None:
    з = замер(запись, ключ)
    if not з or not з.get("measured"):
        return None
    в = з.get("value")
    if isinstance(в, int | float):
        return int(в)
    if isinstance(в, dict):
        for имя in ("value", "total", "sum"):
            if isinstance(в.get(имя), int | float):
                return int(в[имя])
    return None


def _адрес_страницы(измерения: list[dict]) -> str | None:
    """Адрес страницы из набора измерений строки. Чистая функция.

    Разрез двумерный: ПЕРВОЕ измерение — источник трафика («Search engine
    traffic», `id: organic`), ВТОРОЕ — путь страницы. Брать первое — ровно
    та ошибка, которую я уже делала: в поле «страница» попадало название
    источника, одинаковое у всех строк, и перечень страниц превращался в
    десять одинаковых записей.

    Поэтому адрес ищется по признакам пути (начинается со слеша либо несёт
    `favicon` домена), а не по порядковому номеру: порядок измерений может
    смениться, а признак пути — нет.
    """
    для_пути = [и for и in измерения
                if isinstance(и, dict)
                and (str(и.get("name") or "").startswith("/")
                     or и.get("favicon"))]
    if для_пути:
        return str(для_пути[0].get("name"))
    # Ни одно измерение не похоже на путь: возвращаем None, а не первое
    # попавшееся. Пустой перечень честнее перечня из названий источника.
    return None


def страницы_поиска(запись: dict) -> tuple[list[dict], str]:
    """Поисковые входы по страницам: (перечень, откуда/почему пусто)."""
    з = замер(запись, "search_landing_pages")
    if з is None:
        return [], "разреза search_landing_pages в снимке нет"
    if not з.get("measured"):
        return [], f"не измерено: {з.get('reason') or 'причина не названа'}"
    в = з.get("value")
    строки = в if isinstance(в, list) else (в or {}).get("data") or []
    итог = []
    for с in строки:
        if isinstance(с, dict):
            путь = _адрес_страницы(с.get("dimensions") or [])
            визиты = с.get("visits") or с.get("value") or (
                (с.get("metrics") or [None])[0])
        elif isinstance(с, list | tuple) and len(с) >= 2:
            путь, визиты = с[0], с[1]
        else:
            continue
        if путь is None:
            continue
        итог.append({"page": str(путь), "visits": int(визиты or 0)})
    итог.sort(key=lambda з_: -з_["visits"])
    return итог[:СТРАНИЦ], f"источник {з.get('source') or 'метрика'}"


def разобрать(снимок: pathlib.Path) -> dict:
    д = json.loads(снимок.read_text(encoding="utf-8"))
    акт = активные()
    собрано = д.get("collected_at")
    окно = д.get("period") or {}
    итог: dict = {
        "schema_version": 1,
        "note": ("Спрос по доменам из снимка Метрики. Поле `queries` пустое"
                 " НЕ потому, что запросов нет, а потому что `popular_queries`"
                 " в снимке не измерен: нужен доступ к Вебмастеру. Страница"
                 " запросом не является."),
        "snapshot": снимок.name,
        "collected_at": собрано,
        "window": окно,
        "window_meaning": ("полные сутки, кончая днём перед сбором"
                           " (7daysAgo…yesterday); соседние снимки"
                           " перекрываются на шесть дней из семи, и их"
                           " разность — сдвиг окна, а не изменение"),
        "domains": [],
    }
    for запись in д.get("domains") or []:
        домен = запись.get("domain")
        if домен not in акт:
            continue
        страницы, откуда = страницы_поиска(запись)
        итог["domains"].append({
            "domain": домен,
            "site_id": акт[домен],
            "counter_id": запись.get("counter_id"),
            "visits": число(запись, "visits"),
            "visitors": число(запись, "visitors"),
            "search_landing_pages": страницы,
            "search_landing_note": откуда,
            "queries": [],
            "queries_note": ("не измерено: popular_queries в снимке"
                             " отсутствует (нужен Вебмастер)"),
        })
    итог["domains"].sort(key=lambda з: -(з["visits"] or 0))
    return итог


def main(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--snapshot", required=True)
    р.add_argument("--write", action="store_true")
    а = р.parse_args(аргв)

    п = pathlib.Path(а.snapshot)
    if not п.is_file():
        print(f"снимок не прочитан: {п}", file=sys.stderr)
        return 2
    итог = разобрать(п)
    print(f"снимок {итог['snapshot']}, собран {итог['collected_at']},"
          f" окно {итог['window']}")
    print(f"{'домен':24} {'визиты':>8} {'посетители':>11}"
          f" {'страниц поиска':>15}")
    for з in итог["domains"]:
        print(f"{з['domain']:24} {str(з['visits'] or '—'):>8}"
              f" {str(з['visitors'] or '—'):>11}"
              f" {len(з['search_landing_pages']):>15}")
    без = [з["domain"] for з in итог["domains"]
           if not з["search_landing_pages"]]
    print(f"\nдомéнов в снимке: {len(итог['domains'])};"
          f" без поисковых страниц: {len(без)}")
    if без:
        print(f"   {', '.join(без)}")
    print("запросы НЕ измерены ни по одному домену: popular_queries требует"
          " Вебмастера. Страница запросом не является.")
    if а.write:
        ВЫХОД.write_text(json.dumps(итог, ensure_ascii=False, indent=1)
                         + "\n", encoding="utf-8")
        print(f"записано: {ВЫХОД.relative_to(КОРЕНЬ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
