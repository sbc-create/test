#!/usr/bin/env python3
"""Запись состава маршрутов в пакеты.

Каждому пакету назначается набор стратегий — каталог, подача тайтла, разведка,
применение полосы — и этот набор разворачивается в явный состав блоков внутри
`template.json`. Назначение детерминированное и обязано быть различным: два
пакета с одинаковым набором стратегий отличались бы только главной, а это ровно
то, что запрещено.

Полосу получает не всякий пакет. `rail=none` — законный выбор: шаблон, которому
полоса не нужна, использует другую полноценную композицию, а не имитирует
карусель ради галочки.
"""

from __future__ import annotations

import argparse
import itertools
import json
import pathlib
import sys

import routes as маршруты_модуль

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[1]

#: Шаг обхода набора сочетаний. Взаимно прост с размером набора, поэтому первые
#: пятьдесят значений попарно различны — это свойство проверяется, а не
#: предполагается.
ШАГ = 53


def сочетания() -> list[dict]:
    все = [
        {"catalog": к, "title": т, "discovery": р, "rail": п}
        for к, т, р, п in itertools.product(
            маршруты_модуль.СТРАТЕГИИ_КАТАЛОГА,
            маршруты_модуль.СТРАТЕГИИ_ТАЙТЛА,
            маршруты_модуль.СТРАТЕГИИ_РАЗВЕДКИ,
            маршруты_модуль.ПРИМЕНЕНИЕ_ПОЛОСЫ)
    ]
    return все


def назначить(пакеты: list[pathlib.Path]) -> dict[str, dict]:
    все = сочетания()
    размер = len(все)
    назначения = {}
    for i, пакет in enumerate(пакеты):
        назначения[пакет.name[:4]] = все[(i * ШАГ) % размер]
    уникальных = {json.dumps(м, sort_keys=True) for м in назначения.values()}
    if len(уникальных) != len(назначения):
        raise SystemExit("назначение стратегий дало повтор — шаг обхода негоден")
    return назначения


def применить(пакет: pathlib.Path, модель: dict) -> list[str]:
    манифест = json.loads((пакет / "template.json").read_text(encoding="utf-8"))
    лестницы = маршруты_модуль.лестницы_из_css(
        (пакет / "layout.css").read_text(encoding="utf-8"))
    состав = маршруты_модуль.развернуть(модель, лестницы, манифест["card_grammar"])
    беды = маршруты_модуль.проверить(состав, лестницы)
    if беды:
        return [f'{манифест["template_id"]}: {б}' for б in беды]
    манифест["route_model"] = модель
    манифест["routes"] = состав
    (пакет / "template.json").write_text(
        json.dumps(манифест, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return []


def главное() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(КОРЕНЬ))
    args = parser.parse_args()
    корень = pathlib.Path(args.root)
    пакеты = sorted(п for п in корень.iterdir()
                    if п.is_dir() and (п / "template.json").is_file())
    назначения = назначить(пакеты)

    беды = []
    for пакет in пакеты:
        беды.extend(применить(пакет, назначения[пакет.name[:4]]))
    if беды:
        for б in беды:
            print("ОТКАЗ:", б, file=sys.stderr)
        return 2
    свод: dict[str, int] = {}
    for м in назначения.values():
        свод[м["catalog"]] = свод.get(м["catalog"], 0) + 1
    print(json.dumps({"пакетов": len(пакеты), "каталоги": свод,
                      "полоса_не_используется":
                          sum(1 for м in назначения.values() if м["rail"] == "none")},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(главное())
