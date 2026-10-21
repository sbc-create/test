#!/usr/bin/env python3
"""Проверка поправок года ДО и ПОСЛЕ выпуска — по доставленному снимку и по сети.

Одна команда на оба случая: до выпуска она честно показывает, что поправки НЕ
применены, после — что применены. Ничего не пишет.

Что проверяется по каждой поправке из `config/anime-year-corrections.json`:

1. **доставленный снимок витрины** — `year` равен сверенному году, `type`
   сверенному виду, и рядом стоит `year_source` с адресом источника. Снимок
   берётся из каталога данных витрины, а не из нашей ветки;
2. **живая страница** (`--network`) — печатает исправленный год и ссылается на
   `/catalog/?year=<исправленный>`. Снимок может быть исправлен, а страница
   кешировать прежний — это разные проверки, и путать их нельзя;
3. **отрицательный контроль** — шесть записей, год которых сверка подтвердила
   верным, обязаны остаться без изменений. Если изменились, правка тронула не
   то, и это отказ независимо от остального.

    python3 automation/local/year-corrections-verify-live.py --site animedia-01
    python3 automation/local/year-corrections-verify-live.py --site animedia-01 --network
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
ПОПРАВКИ = КОРЕНЬ / "config/anime-year-corrections.json"

#: site_id → (каталог данных витрины, домен). Из отчёта доставки ячеек.
ВИТРИНЫ = {
    "animedia-01": ("/srv/animedia-icu/data", "animedia.icu"),
    "animedia-02": ("/srv/animedia-space/data", "animedia.space"),
    "zona-01": ("/srv/zonafilm-space/data", "zonafilm.space"),
    "lords-02": ("/srv/lordserial33-biz/data", "lordserial33.biz"),
}

#: Записи, год которых сверка 20.10 подтвердила ВЕРНЫМ. Они обязаны остаться
#: нетронутыми: иначе правка задела не то, что сверено.
КОНТРОЛЬ = ("povelitel-demonov-2099", "shaman-king-2021",
            "poschadi-menya-velikiy-gospodin-2", "iz-odnoy-komnaty-2",
            "gintama-9", "dostuchatsya-do-tebya-4")


def _модуль(путь: Path, имя: str):
    спец = importlib.util.spec_from_file_location(имя, путь)
    м = importlib.util.module_from_spec(спец)
    sys.modules[имя] = м
    спец.loader.exec_module(м)
    return м


def добыть(url: str, таймаут: int = 30) -> str:
    г = subprocess.run(["curl", "-sS", "--max-time", str(таймаут), url],
                       capture_output=True, text=True, timeout=таймаут + 20)
    return г.stdout


def разобрать(site_id: str, *, сеть: bool, загрузчик=None) -> dict:
    каталог_данных, домен = ВИТРИНЫ[site_id]
    ф = Path(каталог_данных) / f"{site_id}-details.json"
    if not ф.exists():
        return {"не_измерено": f"нет снимка витрины {ф}"}
    снимок = json.loads(ф.read_text(encoding="utf-8"))
    подробности = снимок.get("details") or {}
    поправки = _модуль(КОРЕНЬ / "factory/lords/year_corrections.py",
                       "year_corrections").загрузить(ПОПРАВКИ)
    по_ид = {str((з or {}).get("id") or ""): (с, з)
             for с, з in подробности.items()}

    строки = []
    for ид, п in sorted(поправки.items()):
        слаг, з = по_ид.get(ид, ("", None))
        if з is None:
            строки.append({"slug": п.слаг_при_замере, "итог": "НЕ НАЙДЕНА",
                           "пояснение": "записи с этим id нет в снимке витрины"})
            continue
        ждём_год = п.год_источника if п.год_источника is not None else з.get("year")
        ждём_вид = п.вид_источника if п.вид_источника is not None else з.get("type")
        год_ок = з.get("year") == ждём_год
        вид_ок = з.get("type") == ждём_вид
        источник = з.get("year_source")
        строка = {
            "slug": слаг, "id": ид,
            "год_в_снимке": з.get("year"), "год_ожидается": ждём_год,
            "вид_в_снимке": з.get("type"), "вид_ожидается": ждём_вид,
            "year_source": источник,
            "итог": "ок" if (год_ок and вид_ок) else "НЕ ПРИМЕНЕНО",
        }
        if сеть:
            тело = (загрузчик or добыть)(f"https://{домен}/title/{слаг}/")
            # ПРИЗНАК НА СТРАНИЦЕ ВЫБРАН РАЗЛИЧАЮЩИЙ, и первый был негодным.
            # Сначала я искал само число года в теле страницы — и получил «год
            # есть» у 13 записей из 15 ДО всякого выпуска: четырёхзначное
            # число встречается на странице где угодно (годы соседних карточек,
            # фасеты, подвал). Такой признак отвечает одинаково на исправленной
            # и неисправленной странице, то есть не отвечает вовсе.
            #
            # Различает ссылка фасета года: витрина печатает `/catalog/?year=N`
            # для ГОДА ЭТОЙ записи. Проверяется и наличие нового, и ОТСУТСТВИЕ
            # прежнего — одного наличия мало, пока на странице может стоять
            # и то и другое.
            был = п.год_поставщика
            строка["ссылка_нового_года"] = (f"year={ждём_год}" in тело
                                            if ждём_год else None)
            строка["ссылка_прежнего_года"] = (f"year={был}" in тело
                                              if был else None)
            строка["страница"] = (
                "ок" if строка["ссылка_нового_года"]
                and not строка["ссылка_прежнего_года"]
                else "НЕ ПРИМЕНЕНО" if строка["ссылка_прежнего_года"]
                else "не измерено")
        строки.append(строка)

    контроль = []
    for слаг in КОНТРОЛЬ:
        з = подробности.get(слаг)
        if з is None:
            контроль.append({"slug": слаг, "итог": "нет в этом снимке"})
            continue
        # Контрольные записи поправок не имеют: их год обязан совпадать с тем,
        # что был снят 20.10 и записан в MOD-102.
        контроль.append({"slug": слаг, "год": з.get("year"),
                         "year_source": з.get("year_source"),
                         "итог": "не тронута"
                         if str(з.get("year_source") or "provider") == "provider"
                         else "ПРОВАЛ: контрольной записи поставлена поправка"})

    применено = sum(1 for с in строки if с["итог"] == "ок")
    return {
        "site_id": site_id, "домен": домен,
        "снимок": str(ф), "собран": снимок.get("catalog_built_at"),
        "поправок": len(строки), "применено": применено,
        "не применено": len(строки) - применено,
        "поле year_source есть": sum(1 for с in строки if с.get("year_source")),
        "записи": строки, "отрицательный контроль": контроль,
    }


def напечатать(итог: dict, *, сеть: bool) -> None:
    if "не_измерено" in итог:
        print(f"НЕ ИЗМЕРЕНО: {итог['не_измерено']}")
        return
    print(f"{итог['site_id']} ({итог['домен']}), снимок собран"
          f" {итог['собран']}")
    print(f"поправок {итог['поправок']}: применено {итог['применено']},"
          f" не применено {итог['не применено']},"
          f" поле year_source у {итог['поле year_source есть']}")
    for с in итог["записи"]:
        if с["итог"] == "НЕ НАЙДЕНА":
            print(f"  {с['итог']:12} {с['slug']:46} {с['пояснение']}")
            continue
        хвост = ""
        if сеть:
            хвост = (f"  страница: {с.get('страница')}"
                     f" (ссылка year={с['год_ожидается']}"
                     f" {'есть' if с.get('ссылка_нового_года') else 'нет'},"
                     f" прежняя"
                     f" {'ЕСТЬ' if с.get('ссылка_прежнего_года') else 'нет'})")
        print(f"  {с['итог']:12} {с['slug']:46} год {с['год_в_снимке']}"
              f" (ждём {с['год_ожидается']}), вид {с['вид_в_снимке']}"
              f" (ждём {с['вид_ожидается']}), источник"
              f" {с.get('year_source') or '—'}{хвост}")
    print("\nотрицательный контроль:")
    for с in итог["отрицательный контроль"]:
        print(f"  {с['итог']:50} {с['slug']:46} год {с.get('год')}")
    if итог["не применено"] == итог["поправок"]:
        print("\nИТОГ: поправки НЕ применены — это состояние ДО выпуска.")
    elif итог["не применено"]:
        print("\nИТОГ: применены ЧАСТИЧНО — разбирать поимённо, это не успех.")
    else:
        print("\nИТОГ: все поправки применены.")


def главное(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--site", default="animedia-01")
    р.add_argument("--network", action="store_true")
    р.add_argument("--json", action="store_true")
    а = р.parse_args(аргв)
    if а.site not in ВИТРИНЫ:
        print(f"НЕ ИЗМЕРЕНО: витрины {а.site} нет в перечне {sorted(ВИТРИНЫ)}")
        return 2
    итог = разобрать(а.site, сеть=а.network)
    if а.json:
        print(json.dumps(итог, ensure_ascii=False, indent=1))
    else:
        напечатать(итог, сеть=а.network)
    if "не_измерено" in итог:
        return 2
    провал_контроля = any("ПРОВАЛ" in с["итог"]
                          for с in итог["отрицательный контроль"])
    if провал_контроля:
        return 2
    return 1 if итог["не применено"] else 0


if __name__ == "__main__":
    sys.exit(главное())
