#!/usr/bin/env python3
"""Где расходятся три дерева кода: моё, живое и установленное. Только чтение.

Повод — три случая за один день 19.10:

* правка источников лежала в моей ветке, а редактор читает файл из ЖИВОГО
  дерева (ветка линии SEO) — пока она не перенесла коммит, правка не работала;
* файл теста аналитики в моей ветке отставал от живого на пять суток, и полный
  прогон падал не из-за моей работы;
* установленная копия исполнителя ячеек `/usr/local/lib/site-factory-cell`
  отличается от живого дерева в 13 файлах.

Каждый раз вопрос один: КАКОЙ код исполняется. Инструмент отвечает на него
сразу по трём деревьям и печатает расхождения по именам файлов.

Сравнение — по содержимому (sha256), а не по времени: время правится копированием,
содержимое — нет. Время печатается рядом, чтобы было видно, какая сторона свежее.

    python3 automation/local/tree-divergence.py
    python3 automation/local/tree-divergence.py --paths automation/local --json

Коды: 0 — расхождений нет; 1 — есть; 2 — сравнивать нечего.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import sys

МОЁ = pathlib.Path("/home/claude/wt-nova-publish-memory-02")
ЖИВОЕ = pathlib.Path("/home/claude/wt-portable-site-cell-01")
УСТАНОВЛЕННОЕ = pathlib.Path("/usr/local/lib/site-factory-cell")
#: Что сравнивать по умолчанию: код, который кто-то исполняет.
ПОДДЕРЕВЬЯ = ("factory", "seo_operator", "automation/local", "tests/unit")


def цифра(п: pathlib.Path) -> str:
    try:
        return hashlib.sha256(п.read_bytes()).hexdigest()
    except OSError:
        return ""


def собрать(корень: pathlib.Path, поддеревья: tuple[str, ...]) -> dict[str, tuple[str, float]]:
    итог: dict[str, tuple[str, float]] = {}
    for поддерево in поддеревья:
        основа = корень / поддерево
        if not основа.is_dir():
            continue
        for п in основа.rglob("*"):
            if not п.is_file() or "__pycache__" in п.parts or п.suffix in (".pyc", ".pyo"):
                continue
            ц = цифра(п)
            if ц:
                итог[str(п.relative_to(корень))] = (ц, п.stat().st_mtime)
    return итог


def _когда(метка: float) -> str:
    return dt.datetime.fromtimestamp(метка, dt.timezone.utc).strftime("%m-%d %H:%M")


def сверить(деревья: dict[str, pathlib.Path],
            поддеревья: tuple[str, ...]) -> dict:
    собранные = {имя: собрать(п, поддеревья) for имя, п in деревья.items()}
    живые = {имя: с for имя, с in собранные.items() if с}
    if len(живые) < 2:
        отсутствуют = [имя for имя, с in собранные.items() if not с]
        return {"измерено": False,
                "почему": f"нечего сравнивать: пусто у {', '.join(отсутствуют)}"}
    все_файлы = sorted(set().union(*(set(с) for с in живые.values())))
    различаются = []          # файл есть у двух и более деревьев, содержимое разное
    односторонние = {}        # файл есть только у одного дерева
    for файл in все_файлы:
        цифры = {имя: с.get(файл, ("", 0.0)) for имя, с in живые.items()}
        присутствует = [имя for имя, (ц, _) in цифры.items() if ц]
        уникальные = {ц for ц, _ in цифры.values() if ц}
        запись = {
            "файл": файл,
            "состояние": {имя: ("нет" if not ц else ц[:8]) for имя, (ц, _) in цифры.items()},
            "время": {имя: ("—" if not т else _когда(т)) for имя, (ц, т) in цифры.items()},
        }
        if len(присутствует) == 1:
            # Файл есть только в одном дереве. Это обычное дело: у каждой линии
            # свои инструменты. В отдельный счёт, чтобы не топить настоящий
            # вопрос — «какой код исполняется там, где файл есть у обоих».
            односторонние.setdefault(присутствует[0], []).append(файл)
        elif len(уникальные) > 1:
            различаются.append(запись)
    return {"измерено": True, "деревья": {имя: str(п) for имя, п in деревья.items()},
            "файлов": {имя: len(с) for имя, с in живые.items()},
            "расхождений": len(различаются), "список": различаются,
            "только_в_одном": {имя: len(сп) for имя, сп in односторонние.items()},
            "только_в_одном_файлы": {имя: сп[:10] for имя, сп in односторонние.items()}}


def main(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description="расхождения трёх деревьев кода")
    р.add_argument("--mine", default=str(МОЁ))
    р.add_argument("--live", default=str(ЖИВОЕ))
    р.add_argument("--installed", default=str(УСТАНОВЛЕННОЕ))
    р.add_argument("--paths", action="append", default=[])
    р.add_argument("--limit", type=int, default=20)
    р.add_argument("--json", action="store_true")
    дов = р.parse_args(аргв)

    поддеревья = tuple(дов.paths) or ПОДДЕРЕВЬЯ
    деревья = {"моё": pathlib.Path(дов.mine), "живое": pathlib.Path(дов.live),
               "установленное": pathlib.Path(дов.installed)}
    и = сверить(деревья, поддеревья)

    if дов.json:
        print(json.dumps(и, ensure_ascii=False, indent=2))
        return 0 if и.get("измерено") and not и["расхождений"] else (
            2 if not и.get("измерено") else 1)

    if not и["измерено"]:
        print(f"НЕ ИЗМЕРЕНО: {и['почему']}")
        return 2
    for имя, путь in и["деревья"].items():
        print(f"{имя:14} {путь}  файлов {и['файлов'].get(имя, 0)}")
    print(f"сравнивались поддеревья: {', '.join(поддеревья)}")
    только = и.get("только_в_одном") or {}
    if только:
        print("только в одном дереве (это норма, у линий свои инструменты): "
              + ", ".join(f"{имя} {сколько}" for имя, сколько in только.items()))
    print(f"РАЗЛИЧАЮТСЯ (есть у двух и более, содержимое разное): {и['расхождений']}")
    for р_ in и["список"][:дов.limit]:
        состояние = "  ".join(f"{имя}={з}" for имя, з in р_["состояние"].items())
        время = "  ".join(f"{имя}:{т}" for имя, т in р_["время"].items())
        print(f"   {р_['файл']}")
        print(f"      {состояние}")
        print(f"      {время}")
    if и["расхождений"] > дов.limit:
        print(f"   … и ещё {и['расхождений'] - дов.limit}")
    print()
    print("Расхождение само по себе не дефект: деревья принадлежат разным линиям "
          "и обязаны расходиться во время работы. Дефект — когда исполняется не "
          "то, что проверено; поэтому рядом с цифрой стоит время каждой стороны.")
    return 1 if и["расхождений"] else 0


if __name__ == "__main__":
    sys.exit(main())
