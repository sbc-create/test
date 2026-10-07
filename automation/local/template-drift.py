#!/usr/bin/env python3
"""Насколько закреплённый у ячейки рантайм отстал от общего шаблона. Только чтение.

    python3 automation/local/template-drift.py
    python3 automation/local/template-drift.py --feature СКРИПТ_ЛЕНТ --feature РЯД_ПОЛКИ

Зачем. Исправления общего кода живут в `automation/host/lords-frontend.py`, а
витрина исполняет СВОЮ закреплённую копию (`template/<build>/lords-frontend.py`
у ячеек на общем ядре, либо собственный рантайм у монолитов). Совпадение
`template-manifest.json` ни о чём не говорит: он описывает закреплённую копию, а
не шаблон. Поэтому «исправление перенесено» проверяется наличием КОНКРЕТНОГО
признака в той копии, которую витрина действительно исполняет.

Признак — не номер версии: номер можно переставить, не внеся правку. Признаком
служит имя, введённое исправлением (`РЯД_ПОЛКИ`, `СКРИПТ_ЛЕНТ`, …): оно либо
есть в исполняемом файле, либо нет.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ШАБЛОН = КОРЕНЬ / "automation" / "host" / "lords-frontend.py"
РЕПОЗИТОРИИ = КОРЕНЬ / "var" / "site-repos"

#: Признаки известных исправлений: имя → что оно означает в отчёте.
#: Берутся из `docs/LORDS_TEMPLATE_FIXES.md`; добавлять только то, что введено
#: исправлением и не может появиться в файле иначе.
ПРИЗНАКИ: dict[str, str] = {
    "РЯД_ПОЛКИ": "полка набирает полный ряд, а не константу 12",
    "СКРИПТ_ЛЕНТ": "карусель: шаг по карточке, края, клавиатура, перетаскивание",
    "СРОЧНЫХ_ПОСТЕРОВ": "первый экран грузится сразу, нижние блоки — нет",
    "МАРШРУТЫ_ВИДА": "разделы /anime/ и /dorama/ отдаются рантаймом",
    "data-shelf-size": "полка называет фактическое число при нехватке записей",
    "СКРИПТ_ТЕМЫ": "переключатель темы",
    "построить_sitemap": "карта сайта собирается рантаймом",
    "эпизоды_доступны": "доступность серий по дорожкам, а не по счётчику",
}


def сумма(п: pathlib.Path) -> str:
    return hashlib.sha256(п.read_bytes()).hexdigest()


def исполняемые(репо: pathlib.Path) -> list[pathlib.Path]:
    """Файлы, которые витрина действительно исполняет как рантайм витрины."""
    найдено: list[pathlib.Path] = []
    for подкаталог in ("template", "src", "."):
        к = репо / подкаталог
        if not к.is_dir():
            continue
        for ф in sorted(к.rglob("*frontend*.py")) + sorted(к.rglob("serve.py")):
            if "__pycache__" not in str(ф):
                найдено.append(ф)
        if найдено:
            break
    return найдено


def разбор(репо: pathlib.Path, признаки: dict[str, str]) -> dict:
    итог: dict = {"репозиторий": репо.name, "файлы": [], "нет": [], "есть": []}
    манифест = репо / "template-manifest.json"
    if манифест.is_file():
        try:
            м = json.loads(манифест.read_text(encoding="utf-8"))
            итог["build_id"] = м.get("build_id", "")
            итог["семейство"] = м.get("template_family", "")
            итог["профиль"] = м.get("profile", "")
        except ValueError:
            pass
    файлы = исполняемые(репо)
    if not файлы:
        итог["нет"] = ["рантайм витрины не найден"]
        return итог
    текст = ""
    for ф in файлы:
        итог["файлы"].append(str(ф.relative_to(репо)))
        итог["совпал_с_шаблоном"] = итог.get("совпал_с_шаблоном") or (
            сумма(ф) == сумма(ШАБЛОН))
        текст += ф.read_text(encoding="utf-8", errors="replace")
    for имя, смысл in признаки.items():
        (итог["есть"] if имя in текст else итог["нет"]).append(имя)
    итог["строк"] = текст.count("\n")
    return итог


def главная(argv: list[str]) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--feature", action="append", default=[],
                   help="проверять только эти признаки")
    р.add_argument("--json", action="store_true")
    о = р.parse_args(argv[1:])
    признаки = ({и: ПРИЗНАКИ.get(и, "") for и in о.feature} if о.feature
                else ПРИЗНАКИ)

    шаблонные = [и for и in признаки if и in ШАБЛОН.read_text(encoding="utf-8")]
    строки = [разбор(п, признаки) for п in sorted(РЕПОЗИТОРИИ.iterdir())
              if (п / ".git").is_dir()]
    if о.json:
        print(json.dumps({"шаблон": шаблонные, "ячейки": строки},
                         ensure_ascii=False, indent=2))
        return 0
    print(f"общий шаблон {ШАБЛОН.relative_to(КОРЕНЬ)}: признаков из списка "
          f"{len(шаблонные)} из {len(признаки)}")
    отсутствуют = [и for и in признаки if и not in шаблонные]
    if отсутствуют:
        print(f"   в шаблоне НЕТ: {', '.join(отсутствуют)} "
              "— сравнивать по ним нечего")
    print()
    for с in строки:
        нет = [и for и in с["нет"] if и in шаблонные]
        метка = "всё" if not нет else f"НЕТ: {', '.join(нет)}"
        print(f"{с['репозиторий']:24} {с.get('семейство',''):9} "
              f"{с.get('build_id','')[:26]:26} строк {с.get('строк',0):6}  {метка}")
    print()
    сводка: dict[str, list[str]] = {}
    for с in строки:
        for и in с["нет"]:
            if и in шаблонные:
                сводка.setdefault(и, []).append(с["репозиторий"])
    if not сводка:
        print("признаков, отсутствующих хотя бы у одной ячейки, нет")
    for и, где in сводка.items():
        print(f"{и}: отсутствует у {len(где)} — {', '.join(где)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(главная(sys.argv))
