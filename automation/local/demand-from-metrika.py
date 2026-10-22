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


def поисковый_итог(запись: dict) -> tuple[int | None, str]:
    """Поисковые визиты за окно и откуда взяты. Чистая функция от записи.

    Берётся разрез `traffic_sources`, строка `organic`. Это ЕДИНСТВЕННЫЙ
    верный знаменатель для доли топовых страниц: `visits` — все визиты, и
    делить поисковые входы на них значит смешивать два разных множества.
    """
    з = замер(запись, "traffic_sources")
    if not з or not з.get("measured"):
        return None, "traffic_sources не измерен"
    for с in з.get("value") or []:
        изм = (с.get("dimensions") or [{}])[0]
        if изм.get("id") == "organic":
            м = с.get("metrics") or [None]
            return (int(м[0]) if м[0] is not None else None,
                    "traffic_sources: organic")
    return 0, "traffic_sources: строки organic нет — поискового трафика нет"


def по_поисковикам(запись: dict) -> tuple[dict[str, int], str]:
    """Визиты раздельно по поисковым системам: Яндекс и Google отдельно.

    Задание требует именно раздельно. Сложение «всех поисковиков» скрыло бы
    то, что измерено: у части витрин Google даёт единицы визитов против
    тысяч у Яндекса, и это разные задачи, а не одна.
    """
    з = замер(запись, "search_engines")
    if not з or not з.get("measured"):
        return {}, "search_engines не измерен"
    итог: dict[str, int] = {}
    for с in з.get("value") or []:
        изм = (с.get("dimensions") or [{}])[0]
        ид = str(изм.get("id") or "")
        м = с.get("metrics") or [0]
        сколько = int(м[0] or 0)
        семья = ("yandex" if ид.startswith("yandex")
                 else "google" if ид.startswith("google")
                 else "прочие")
        итог[семья] = итог.get(семья, 0) + сколько
    return итог, "search_engines"


def страницы_поиска(запись: dict) -> tuple[list[dict], str, int]:
    """Поисковые входы по страницам: (перечень, откуда/почему пусто)."""
    з = замер(запись, "search_landing_pages")
    if з is None:
        return [], "разреза search_landing_pages в снимке нет", 0
    if not з.get("measured"):
        return [], f"не измерено: {з.get('reason') or 'причина не названа'}", 0
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
    # Возвращается и ПОЛНОЕ число страниц разреза: сохраняются только верхние
    # СТРАНИЦ, и печатать длину сохранённого как «страниц с поиском» значит
    # печатать свой предел вместо измеренной величины — так отчёт показывал
    # 10 у всех домéнов подряд.
    return (итог[:СТРАНИЦ], f"источник {з.get('source') or 'метрика'};"
            f" страниц в разрезе {len(итог)}, сохранено"
            f" {min(len(итог), СТРАНИЦ)}", len(итог))


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
        страницы, откуда, всего_страниц = страницы_поиска(запись)
        поиск, откуда_поиск = поисковый_итог(запись)
        системы, откуда_систем = по_поисковикам(запись)
        верх5 = sum(с["visits"] for с in страницы[:5])
        итог["domains"].append({
            "domain": домен,
            "site_id": акт[домен],
            "counter_id": запись.get("counter_id"),
            "visits": число(запись, "visits"),
            "visitors": число(запись, "visitors"),
            "search_visits": поиск,
            "search_visits_note": откуда_поиск,
            "search_engines": системы,
            "search_engines_note": откуда_систем,
            "top5_search_entries": верх5,
            "top5_share_of_search": (
                round(100 * верх5 / поиск, 1) if поиск else None),
            "search_landing_pages": страницы,
            "search_pages_total": всего_страниц,
            # Какую долю поискового итога несут СОХРАНЁННЫЕ страницы. Без
            # этого поля разбор по ним выглядит полным, а он частичный: у
            # одного домена десять страниц дают 82 % визитов, у другого 25 %
            # при 144 страницах в разрезе. Сравнивать состав входов между
            # домéнами без охвата нельзя.
            "search_landing_covered": (
                round(100 * sum(с["visits"] for с in страницы) / поиск, 1)
                if поиск else None),
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
    print(f"{'домен':24} {'визиты':>7} {'поиск':>7} {'Яндекс':>7}"
          f" {'Google':>7} {'топ-5':>7} {'доля':>6}")
    for з in итог["domains"]:
        c = з["search_engines"] or {}
        доля = (f"{з['top5_share_of_search']}%"
                if з["top5_share_of_search"] is not None else "—")
        print(f"{з['domain']:24} {str(з['visits'] or '—'):>7}"
              f" {str(з['search_visits'] if з['search_visits'] is not None else '—'):>7}"
              f" {str(c.get('yandex', '—')):>7} {str(c.get('google', '—')):>7}"
              f" {з['top5_search_entries']:>7} {доля:>6}")
    без = [з["domain"] for з in итог["domains"]
           if not з["search_landing_pages"]]
    print(f"\nдомéнов в снимке: {len(итог['domains'])};"
          f" без поисковых страниц: {len(без)}")
    if без:
        print(f"   {', '.join(без)}")
    print("доля топ-5 считается от ПОИСКОВЫХ входов, а не от всех визитов:"
          " делить поисковые входы на все визиты значит смешивать два разных"
          " множества")
    print("запросы НЕ измерены ни по одному домену: popular_queries требует"
          " Вебмастера. Страница запросом не является.")
    if а.write:
        ВЫХОД.write_text(json.dumps(итог, ensure_ascii=False, indent=1)
                         + "\n", encoding="utf-8")
        print(f"записано: {ВЫХОД.relative_to(КОРЕНЬ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
