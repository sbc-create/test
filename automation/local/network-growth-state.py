#!/usr/bin/env python3
"""Состояние сети по отношению к цели: одна строка на витрину. Только чтение.

ЗАЧЕМ ОТДЕЛЬНЫЙ ИНСТРУМЕНТ. Цифры про цель лежат в четырёх разных местах:
реальные визиты — в выгрузке кабинета, доля поиска — там же но в другом
разрезе, число страниц с визитами — в третьем, режим индексации — в паспорте и
на живой витрине. Собирать их руками значит каждый раз рисковать смешать
«не измерено» с нулём и «закрыто решением» с «нет трафика».

ЧТО СЧИТАЕТСЯ И КАК:

* ``реальные/сут`` — визиты без роботов Метрики И без автоматизации, по
  суточному профилю. Ряд `daily_users` для этого НЕ годится: он снимает только
  флаг робота, а автоматизация роботом не считается (класс 19);
* ``поиск %`` — доля поискового источника в реальных визитах. Отдельно нужна
  потому, что «прямой» трафик сети на 87 % автоматика;
* ``страниц с визитами`` — сколько РАЗНЫХ адресов получили поисковые визиты;
* ``режим`` — открыта витрина для поиска или закрыта решением. Закрытой
  витрине недостача до цели НЕ пишется: это отсутствие поверхности, а не
  отставание (MOD-155).

Состояние карты сайта тут не измеряется: это отдельный проход, и смешивать
сетевой запрос на 70 000 адресов с чтением выгрузки незачем.

    python3 automation/local/network-growth-state.py
    python3 automation/local/network-growth-state.py --json
"""
from __future__ import annotations

import argparse
import collections
import glob
import importlib.util
import json
import pathlib
import subprocess
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
АРТЕФАКТ = pathlib.Path("/home/claude/wt-portable-site-cell-01/var/analytics"
                        "/cabinet-latest.json")
ЦЕЛЬ = 5000


def _сегменты():
    п = КОРЕНЬ / "automation" / "local" / "traffic-segments.py"
    с = importlib.util.spec_from_file_location("traffic_segments", п)
    м = importlib.util.module_from_spec(с)
    с.loader.exec_module(м)
    return м


def режим(домен: str) -> str:
    """Открыта ли витрина для поиска. Два признака, как в проверке режима."""
    try:
        ш = subprocess.run(
            ["curl", "-sSIL", "--max-time", "15", "-A", "factory-growth-state",
             f"https://{домен}/"], capture_output=True, text=True, timeout=35
        ).stdout
    except Exception:  # noqa: BLE001
        return "НЕ ОТВЕЧАЕТ"
    if not ш.strip():
        return "НЕ ОТВЕЧАЕТ"
    xr = next((с.split(":", 1)[1].strip().lower() for с in ш.splitlines()
               if с.lower().startswith("x-robots-tag")), "")
    if "noindex" in xr:
        return "закрыта"
    try:
        r = subprocess.run(
            ["curl", "-sSL", "--max-time", "15", "-A", "factory-growth-state",
             f"https://{домен}/robots.txt"],
            capture_output=True, text=True, timeout=35).stdout
    except Exception:  # noqa: BLE001
        return "открыта?"
    if any(с.strip().lower() == "disallow: /" for с in r.splitlines()):
        return "закрыта"
    return "открыта"


def по_витрине(я: dict, сегм) -> dict:
    мера = next((м for м in я.get("measurements") or []
                 if м.get("key") == "daily_traffic_profile"
                 and м.get("measured")), None)
    строки = сегм.строки((мера or {}).get("value")) if мера else []
    реальные = [с for с in строки
                if с["робот"] != "Robots" and not сегм.автоматизация(с["браузер"])]
    дни = {с["дата"] for с in реальные}
    всего = sum(с["визиты"] for с in реальные)
    по_источнику = collections.Counter()
    for с in реальные:
        по_источнику[с["источник"]] += с["визиты"]
    поиск = по_источнику.get("Search engine traffic", 0.0)
    посадочные = next((м for м in я.get("measurements") or []
                       if м.get("key") == "daily_search_landing_pages"
                       and м.get("measured")), None)
    адреса = set()
    for с in (посадочные or {}).get("value") or []:
        for и in с.get("dimensions") or []:
            текст = str((и or {}).get("name") or "")
            if текст.startswith("/") or "://" in текст:
                адреса.add(текст.split("?", 1)[0])
                break
    return {
        "домен": я["domain"],
        "суток": len(дни),
        "реальные_в_сутки": (всего / len(дни)) if дни else None,
        "поиск_доля": (поиск * 100.0 / всего) if всего else None,
        "страниц_с_визитами": len(адреса),
    }


def main(аргв=None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--json", action="store_true")
    р.add_argument("--artifact", default=str(АРТЕФАКТ))
    а = р.parse_args(аргв)
    путь = pathlib.Path(а.artifact)
    if not путь.is_file():
        print(f"НЕ ИЗМЕРЕНО: выгрузки нет: {путь}", file=sys.stderr)
        return 2
    д = json.loads(путь.read_text("utf-8"))
    сегм = _сегменты()
    из_очередей = {pathlib.Path(п).stem
                   for п in glob.glob(str(КОРЕНЬ / "config/domain-queues/*.json"))}
    строки = []
    for я in д.get("domains") or []:
        if я.get("domain") not in из_очередей:
            continue
        запись = по_витрине(я, сегм)
        запись["режим"] = режим(запись["домен"])
        строки.append(запись)
    # домены очереди, которых в выгрузке нет вовсе
    для_отчёта = {с["домен"] for с in строки}
    for домен in sorted(из_очередей - для_отчёта):
        строки.append({"домен": домен, "суток": 0, "реальные_в_сутки": None,
                       "поиск_доля": None, "страниц_с_визитами": 0,
                       "режим": режим(домен)})
    строки.sort(key=lambda с: -(с["реальные_в_сутки"] or -1))
    if а.json:
        print(json.dumps(строки, ensure_ascii=False, indent=1))
    else:
        print(f"выгрузка собрана {д.get('collected_at')}; цель {ЦЕЛЬ}"
              " реальных визитов в сутки")
        print("%-22s %-10s %11s %7s %11s %10s"
              % ("домен", "режим", "реальн/сут", "поиск%", "стр. с виз.",
                 "до цели"))
        for с in строки:
            реальные = с["реальные_в_сутки"]
            доля = с["поиск_доля"]
            если_закрыта = с["режим"] == "закрыта"
            if если_закрыта:
                до_цели = "— закрыта"
            elif реальные is None:
                до_цели = "не измерено"
            else:
                до_цели = f"{max(0.0, ЦЕЛЬ - реальные):.0f}"
            столбец_визитов = ("не изм." if реальные is None
                               else f"{реальные:.1f}")
            столбец_доли = "—" if доля is None else f"{доля:.0f}%"
            print(f'{с["домен"]:<22} {с["режим"]:<10} {столбец_визитов:>11}'
                  f' {столбец_доли:>7} {с["страниц_с_визитами"]:>11}'
                  f' {до_цели:>10}')
        открытые = [с for с in строки if с["режим"] == "открыта"]
        измеренные = [с for с in открытые if с["реальные_в_сутки"] is not None]
        сумма = sum(с["реальные_в_сутки"] for с in измеренные)
        достигли = [с["домен"] for с in измеренные
                    if с["реальные_в_сутки"] >= ЦЕЛЬ]
        print()
        закрытых = sum(1 for с in строки if с["режим"] == "закрыта")
        молчащих = sum(1 for с in строки if с["режим"] == "НЕ ОТВЕЧАЕТ")
        print(f"открытых витрин {len(открытые)}, из них измерено"
              f" {len(измеренные)}; закрыто решением {закрытых};"
              f" не отвечают {молчащих}")
        print(f"сумма реальных визитов по открытым: {сумма:.0f} в сутки")
        print("достигают цели: "
              + (", ".join(достигли) or "ни одна"))
        print("Закрытым витринам недостача не пишется: это отсутствие"
              " поверхности, а не отставание (MOD-155).")
    print(f"ЗАВЕРШЕНО: витрин в отчёте {len(строки)}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
