#!/usr/bin/env python3
"""Насколько витрины и проекты сайтов отстали от шаблона фабрики.

Зачем. Общее исправление доезжает до сайта не правкой файла, а ПРОДВИЖЕНИЕМ
версии: новый сайт собирается из шаблона этого репозитория и закрепляет его
коммит в `pins.lock.json` (`factory/cell/newsite.py`). Пока закрепление не
поднято, сайт живёт на старом рантайме — и то же исправление приходится
делать второй раз руками. Инструмент отвечает числом, насколько каждый
экземпляр отстал и какие файлы у него разошлись с каноном.

Измерено 25.10 этим инструментом: восемь проектов партии K2
(`var/new-sites/lords-1x`) закреплены на коммите `96222882`, то есть 1 549
коммитов назад; живые витрины Lords и Zona — на `ac4e439e`, `a0209877`,
`63fe3415`, `efdef56e`, то есть 2 505–2 700 коммитов назад; три витрины
закреплены на коммитах, которых в этом репозитории нет вовсе, а у пяти витрин
Yummy `source_commit` равен `null` — происхождение рантайма не записано.

Чего инструмент НЕ делает. Ничего не копирует и не продвигает: обновление
действующего сайта идёт штатной процедурой выпуска с проверкой совместимости.
Здесь только измерение, пригодное для реестра дефектов и для решения владельца.

    python3 automation/local/template-lag.py [--json out.json] [--srv /srv]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
#: Канонический рантайм семейства. Берётся из генератора, а не перечисляется
#: заново: разойдясь, два перечня мерили бы разные вещи.
def канонический_рантайм() -> tuple[str, ...]:
    sys.path.insert(0, str(КОРЕНЬ))
    from factory.cell import newsite
    return tuple(newsite.РАНТАЙМ_LORDS)


ХОСТ = КОРЕНЬ / "automation" / "host"


def отпечаток(п: pathlib.Path) -> str:
    try:
        return hashlib.sha256(п.read_bytes()).hexdigest()
    except OSError:
        return ""


def _git(*аргв: str, где: pathlib.Path | None = None) -> str:
    try:
        г = subprocess.run(["git", *аргв], capture_output=True, text=True,
                           cwd=str(где or КОРЕНЬ), timeout=60)
    except (OSError, subprocess.SubprocessError):
        return ""
    return г.stdout.strip() if г.returncode == 0 else ""


def отставание(коммит: str) -> dict:
    """Сколько коммитов между закреплением и HEAD репозитория шаблона."""
    if not коммит:
        return {"коммит": None, "в_репозитории": False, "отставание": None,
                "почему": "в замке нет source_commit: происхождение рантайма не записано"}
    есть = _git("cat-file", "-t", коммит) == "commit"
    if not есть:
        return {"коммит": коммит, "в_репозитории": False, "отставание": None,
                "почему": "коммита нет в этом репозитории: собран из другого дерева"}
    счёт = _git("rev-list", "--count", f"{коммит}..HEAD")
    return {"коммит": коммит, "в_репозитории": True,
            "отставание": int(счёт) if счёт.isdigit() else None, "почему": ""}


def замок(каталог: pathlib.Path) -> dict:
    """Содержимое `pins.lock.json` экземпляра, иначе пустой словарь."""
    for путь in (каталог / "pins.lock.json", *sorted(каталог.rglob("pins.lock.json"))):
        if путь.is_file():
            try:
                return json.loads(путь.read_text(encoding="utf-8", errors="replace"))
            except ValueError:
                return {}
    return {}


def закреплённый_коммит(з: dict) -> str:
    п = з.get("pins") or {}
    for значение in (п.get("source_commit"), з.get("commit"), п.get("common_core")):
        if значение:
            return str(значение)
    return ""


def расхождения(каталог: pathlib.Path, рантайм: tuple[str, ...]) -> dict:
    """Какие файлы канонического рантайма у экземпляра разошлись."""
    итог = {"совпало": [], "разошлось": [], "нет_файла": []}
    for имя in рантайм:
        канон = ХОСТ / имя
        if not канон.is_file():
            итог["нет_файла"].append(f"{имя} (нет канона)")
            continue
        живые = [п for п in каталог.rglob(имя) if п.is_file()]
        if not живые:
            итог["нет_файла"].append(имя)
            continue
        о = отпечаток(канон)
        (итог["совпало"] if any(отпечаток(п) == о for п in живые)
         else итог["разошлось"]).append(имя)
    return итог


def экземпляры(srv: pathlib.Path) -> list[tuple[str, str, pathlib.Path]]:
    """(вид, имя, каталог) — проекты сайтов и выложенные витрины."""
    итог = []
    проекты = КОРЕНЬ / "var" / "new-sites"
    if проекты.is_dir():
        for п in sorted(проекты.iterdir()):
            if п.is_dir():
                итог.append(("проект", п.name, п))
    if srv.is_dir():
        for к in sorted(srv.iterdir()):
            if not (к / "releases").is_dir():
                continue
            тек = к / "current"
            выпуск = тек.resolve() if тек.exists() else None
            if выпуск is None:
                релизы = sorted((к / "releases").iterdir(), key=lambda p: p.stat().st_mtime)
                выпуск = релизы[-1] if релизы else None
            if выпуск is not None:
                итог.append(("витрина", к.name, выпуск))
    return итог


def свод(srv: pathlib.Path) -> dict:
    рантайм = канонический_рантайм()
    голова = _git("rev-parse", "HEAD")[:12]
    строки = []
    for вид, имя, каталог in экземпляры(srv):
        з = замок(каталог)
        о = отставание(закреплённый_коммит(з))
        р = расхождения(каталог, рантайм)
        строки.append({"вид": вид, "имя": имя, "каталог": str(каталог),
                       "семейство": з.get("family") or (з.get("pins") or {}).get("family") or "",
                       **о,
                       "совпало": len(р["совпало"]), "разошлось": р["разошлось"],
                       "нет_файла": р["нет_файла"]})
    return {"head": голова, "рантайм": list(рантайм), "строки": строки}


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--srv", type=pathlib.Path, default=pathlib.Path("/srv"))
    р.add_argument("--json", type=pathlib.Path)
    а = р.parse_args(аргв)
    с = свод(а.srv)
    print(f"канон: HEAD {с['head']}, файлов рантайма {len(с['рантайм'])}")
    print(f"\n{'вид':9} {'имя':28} {'закрепление':14} {'отставание':>11}  расхождения")
    for з in с["строки"]:
        отст = (str(з["отставание"]) if з["отставание"] is not None
                else ("—" if з["в_репозитории"] else "НЕ ИЗМЕРЕНО"))
        разн = (f"{len(з['разошлось'])} из {len(с['рантайм'])}"
                if з["разошлось"] else ("всё совпало" if з["совпало"] else "рантайма нет"))
        print(f"{з['вид']:9} {з['имя']:28} {(з['коммит'] or '—')[:14]:14} {отст:>11}  {разн}")
        if з["почему"]:
            print(f"{'':50} — {з['почему']}")
    без = [з for з in с["строки"] if not з["в_репозитории"]]
    print(f"\nэкземпляров всего {len(с['строки'])}; с непроверяемым происхождением {len(без)}")
    отстают = [з for з in с["строки"] if з["отставание"]]
    if отстают:
        м = max(з["отставание"] for з in отстают)
        print(f"максимальное отставание закрепления: {м} коммитов")
    print("продвижение версии инструмент НЕ делает: обновление идёт штатным выпуском")
    if а.json:
        а.json.parent.mkdir(parents=True, exist_ok=True)
        а.json.write_text(json.dumps(с, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"свод записан: {а.json}")
    return 0


if __name__ == "__main__":
    sys.exit(главное())
