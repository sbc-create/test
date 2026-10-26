#!/usr/bin/env python3
"""Продвинуть закреплённую версию шаблона в проекте ячейки — НЕ пересоздавая его.

Зачем отдельный инструмент. Штатный генератор `factory cell newsite` — создатель,
а не обновляющий: при `--force` он делает `shutil.rmtree(куда)` и собирает проект
заново. Измерено 26.10: после такого «обновления» у пяти проектов исчез их
собственный репозиторий вместе с первым коммитом (`.git` стёрт), и три штатные
проверки проекта снова отвечали отказом. У живого сайта тем же движением ушли бы
`config/player.json` с publisher_id (его кладут вне Git), локальная история и всё,
что положено рядом вне состава шаблона. Сам сгенерированный README говорит, как
надо: «Исправления семейства приезжают сюда продвижением версии в
`pins.lock.json`, а не копированием файлов».

Что инструмент делает: обновляет файлы рантайма в `<проект>/src/` и `pins.lock.json`
(коммит, build_id, суммы и размеры по файлам). Что НЕ трогает: `.git`, `config/`,
данные, `deploy/`, `checks/`, `tools/`, `AGENTS.md` и любой файл вне состава пинов.

Отказ, а не предупреждение, в трёх случаях:

1. **Рабочее дерево фабрики грязное.** Закрепление назвало бы коммит, которому
   содержимое не соответствует — то же правило, что у генератора.
2. **Копия проекта несёт имена, которых в каноне нет.** Продвижение их СТЁРЛО
   БЫ. Измерено 26.10: у восьми витрин партии K2 это `_контакт_подвала` и
   `_метка_по_имени` (адрес обратной связи по контракту сети и знак витрины), у
   zona-01 и zona-03 — 105 и 100 своих имён, то есть отдельная линия оформления
   целиком. Отказ называет имена: их место — в каноническом слое
   (docs/COMMON_FIX_INHERITANCE.md), а не в правке одного домена.
3. **В проекте нет `pins.lock.json` или `src/`.** Это не ячейка с проектом, и
   догадываться о её раскладке нельзя.

    python3 automation/local/promote-cell-pins.py --site lords-18 [--check]
    python3 automation/local/promote-cell-pins.py --all [--check]
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import pathlib
import subprocess
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
РЕЕСТР = КОРЕНЬ / "config" / "site-cells.json"
ИСТОЧНИК = КОРЕНЬ / "automation" / "host"


def коммит_фабрики(корень: pathlib.Path = КОРЕНЬ) -> tuple[str, bool]:
    кмт = subprocess.run(["git", "-C", str(корень), "rev-parse", "HEAD"],
                         capture_output=True, text=True, check=True).stdout.strip()
    грязно = bool(subprocess.run(["git", "-C", str(корень), "status", "--porcelain"],
                                 capture_output=True, text=True,
                                 check=True).stdout.strip())
    return кмт, грязно


def имена_верхнего_уровня(текст: str) -> set:
    """Имена функций и классов файла — по РАЗБОРУ, а не поиском по тексту.

    Поиск регулярным выражением считал бы именем и строку в комментарии, и
    отказ выходил бы ложным на файле, который всего лишь упоминает функцию.
    """
    try:
        дерево = ast.parse(текст)
    except SyntaxError:
        return set()
    имена = set()
    for узел in ast.walk(дерево):
        if isinstance(узел, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            имена.add(узел.name)
    return имена


def потери(копия: pathlib.Path, канон: pathlib.Path) -> list:
    """Имена, которые продвижение стёрло бы. Пусто — значит стирать нечего."""
    if not копия.is_file() or not канон.is_file():
        return []
    своё = имена_верхнего_уровня(копия.read_text(encoding="utf-8"))
    есть = имена_верхнего_уровня(канон.read_text(encoding="utf-8"))
    return sorted(своё - есть)


def проект(site_id: str, реестр: pathlib.Path = РЕЕСТР,
           корень: pathlib.Path = КОРЕНЬ) -> pathlib.Path | None:
    данные = json.loads(реестр.read_text(encoding="utf-8"))
    for я in данные.get("cells") or []:
        if я.get("site_id") != site_id:
            continue
        путь = ((я.get("repo") or {}).get("path") or "").strip()
        if not путь:
            return None
        п = pathlib.Path(путь)
        return п if п.is_absolute() else корень / п
    return None


def разбор(site_id: str, *, корень: pathlib.Path = КОРЕНЬ,
           реестр: pathlib.Path = РЕЕСТР) -> dict:
    """Что будет сделано и что мешает. Ни одного байта не пишется."""
    путь = проект(site_id, реестр, корень)
    if путь is None or not путь.is_dir():
        return {"site_id": site_id, "исход": "нет проекта",
                "почему": f"каталога {путь or '—'} нет"}
    замок = путь / "pins.lock.json"
    if not замок.is_file() or not (путь / "src").is_dir():
        return {"site_id": site_id, "исход": "нет проекта",
                "почему": "нет pins.lock.json или src/"}
    пины = json.loads(замок.read_text(encoding="utf-8"))
    состав = пины.get("files") or {}
    if not состав:
        return {"site_id": site_id, "исход": "нет проекта",
                "почему": "в замке нет состава файлов"}
    обновить, потерять, чужие = [], {}, []
    for имя, запись in состав.items():
        путь_в_репозитории = (запись.get("repo_path") or "").strip()
        # Пустой `repo_path` — это НЕ «ищи рядом по имени». Так помечен файл,
        # который приезжает в ячейку отдельным выпуском (канонический модуль
        # сообщества), и копия отсюда завела бы вторую его реализацию. Прежняя
        # редакция подставляла `automation/host/<имя>` и получала отказ на всех
        # двадцати девяти ячейках: инструмент требовал в фабрике файл, которого
        # там не должно быть.
        if not путь_в_репозитории:
            чужие.append(f"{имя}: отдельный выпуск")
            continue
        # Путь ВНЕ фабрики источником не считается, даже если файл по нему
        # лежит. У yummy-07 это `/srv/lords/.frontend/nova_core_indexability.py`
        # — каталог живой площадки. Копировать оттуда в проект значило бы
        # развернуть поток наоборот: правда — репозиторий, /srv её получает.
        # Иначе инструмент отвечал «совпадает», сверив проект с живым хостом.
        п_в_р = pathlib.Path(путь_в_репозитории)
        откуда = п_в_р if п_в_р.is_absolute() else корень / п_в_р
        if п_в_р.is_absolute() or not откуда.resolve().is_relative_to(корень.resolve()):
            чужие.append(f"{имя}: {путь_в_репозитории} вне фабрики")
            continue
        if not откуда.is_file():
            # Файл другого производителя: у AnimeGo, Yummy и Zona свои наборы
            # модулей, и их происхождение этот инструмент не обслуживает.
            # Назвать и пройти мимо — честнее, чем отказать за всю ячейку.
            чужие.append(f"{имя}: {путь_в_репозитории} не в фабрике")
            continue
        копия = путь / "src" / имя
        своё = потери(копия, откуда)
        if своё:
            потерять[имя] = своё
        сумма = hashlib.sha256(откуда.read_bytes()).hexdigest()
        if сумма != (запись.get("sha256") or "") or \
                (копия.is_file() and hashlib.sha256(копия.read_bytes()).hexdigest() != сумма):
            обновить.append(имя)
    if потерять:
        return {"site_id": site_id, "исход": "ОТКАЗ",
                "почему": "копия проекта несёт имена, которых в каноне нет — "
                          "продвижение их стёрло бы",
                "потери": потерять}
    if not обновить and чужие and len(чужие) == len(состав):
        return {"site_id": site_id, "исход": "другой источник",
                "почему": "ни один файл состава не ведётся этой фабрикой",
                "чужие": чужие}
    return {"site_id": site_id,
            "исход": "обновить" if обновить else "совпадает",
            "проект": str(путь.relative_to(корень)) if путь.is_relative_to(корень)
                      else str(путь),
            "файлов к обновлению": обновить,
            "чужие": чужие}


def продвинуть(site_id: str, *, корень: pathlib.Path = КОРЕНЬ,
               реестр: pathlib.Path = РЕЕСТР) -> dict:
    итог = разбор(site_id, корень=корень, реестр=реестр)
    if итог["исход"] != "обновить":
        return итог
    коммит, грязно = коммит_фабрики(корень)
    if грязно:
        return {"site_id": site_id, "исход": "ОТКАЗ",
                "почему": "рабочее дерево фабрики грязное: закрепление по "
                          "коммиту было бы неправдой"}
    путь = проект(site_id, реестр, корень)
    замок = путь / "pins.lock.json"
    пины = json.loads(замок.read_text(encoding="utf-8"))
    for имя, запись in (пины.get("files") or {}).items():
        путь_в_репозитории = (запись.get("repo_path") or "").strip()
        if not путь_в_репозитории:
            continue
        п_в_р = pathlib.Path(путь_в_репозитории)
        if п_в_р.is_absolute():
            continue
        откуда = корень / п_в_р
        if not откуда.is_file() or not откуда.resolve().is_relative_to(корень.resolve()):
            continue
        байты = откуда.read_bytes()
        (путь / "src" / имя).write_bytes(байты)
        запись["sha256"] = hashlib.sha256(байты).hexdigest()
        запись["bytes"] = len(байты)
    пины["pins"]["source_commit"] = коммит
    пины["pins"]["source_dirty"] = False
    пины["pins"]["build_id"] = f"template-{коммит[:12]}"
    замок.write_text(json.dumps(пины, ensure_ascii=False, indent=1) + "\n",
                     encoding="utf-8")
    итог["исход"] = "продвинуто"
    итог["коммит"] = коммит
    return итог


def все_ячейки(реестр: pathlib.Path = РЕЕСТР) -> list:
    данные = json.loads(реестр.read_text(encoding="utf-8"))
    return [я["site_id"] for я in (данные.get("cells") or [])
            if not (я.get("withdrawal") or {}).get("withdrawn")]


def main(аргументы=None) -> int:
    р = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    р.add_argument("--site", help="site_id одной ячейки")
    р.add_argument("--all", action="store_true", help="все ячейки реестра")
    р.add_argument("--check", action="store_true", help="только разбор, без записи")
    а = р.parse_args(аргументы)
    if bool(а.site) == bool(а.all):
        print("BLOCKED_INPUT: нужен ровно один из --site и --all", file=sys.stderr)
        return 2
    цели = [а.site] if а.site else все_ячейки()
    отказов = 0
    for site_id in цели:
        итог = разбор(site_id) if а.check else продвинуть(site_id)
        исход = итог["исход"]
        строка = f"  {исход:12} {site_id:12}"
        if исход == "ОТКАЗ":
            отказов += 1
            строка += " " + итог["почему"]
            for имя, имена in (итог.get("потери") or {}).items():
                строка += f"\n      {имя}: {', '.join(имена[:8])}"
                if len(имена) > 8:
                    строка += f" … всего {len(имена)}"
        elif исход in ("обновить", "продвинуто"):
            строка += f" файлов {len(итог['файлов к обновлению'])}"
            if итог.get("чужие"):
                строка += f", не наших {len(итог['чужие'])}"
        elif исход in ("нет проекта", "другой источник"):
            строка += " " + итог["почему"]
        print(строка)
    if отказов:
        print(f"\nприговор: {отказов} ячеек продвинуть нельзя без переноса правки "
              f"в канонический слой")
        return 1
    print("\nприговор: отказов нет")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
