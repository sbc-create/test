#!/usr/bin/env python3
"""Совместимый издатель для витрин узла K2 — из ДЕЙСТВУЮЩЕГО кода.

Задача. Регулярное обновление каталога новым витринам нужно так же, как первый
снимок. Издатель в этой ветви их знает, но не запускается: ему нужны модули
`factory.lords` (`rating_gateway`, `canonical_projection` и соседние), которых
в ветви нет. Живой издатель запускается, но про восемь витрин не знает.

Решение без заглушек и без правки действующего файла: берётся ЖИВОЙ издатель
(`/srv/site-factory/repo/automation/host/nova-catalog-publish.py`) и в его
таблицу `ВИТРИНЫ` вставляются записи ВСЕХ витрин узла — из реестра ячеек
(`deploy_target.ref`), а не придуманные и не перечисленные здесь: перечень из
восьми означал бы, что новая ячейка узла не попадает в регулярное обновление
каталога и остаётся со снимком, который никто не пересобирает. Больше ничего не меняется, и это проверяется: разница с живым
файлом обязана состоять ТОЛЬКО из вставленных строк.

Куда кладётся. В `var/k2-data/publisher/automation/host/` — так, чтобы
`parents[2]` указывал на пустой каталог: собственный `sys.path.insert` издателя
тогда не перекрывает живой пакет `factory`, который подставляет запускающий
модуль. Действующий издатель и его установленные копии не трогаются.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
ЖИВОЙ = Path("/srv/site-factory/repo/automation/host/nova-catalog-publish.py")
ВЫХОД = КОРЕНЬ / "var" / "k2-data" / "publisher"
РЕЕСТР = КОРЕНЬ / "config" / "site-cells.json"
УЗЕЛ = "k2-zomro-01"


def витрины_узла(ref: str = УЗЕЛ) -> tuple[str, ...]:
    """Состав узла из реестра — тем же модулем, что и у доставки.

    Перечень `lords-10…lords-17` стоял здесь литералом, и это четвёртое место
    одного класса (см. docs/RECURRING_FAILURES.md, класс 47): пять новых ячеек
    того же узла не попали бы в таблицу публикации, снимок для них никто не
    пересобирал бы, и заметить это было нечем — ошибок при этом нет.
    """
    import importlib.util

    путь = КОРЕНЬ / "automation" / "local" / "node-cell-list.py"
    сп = importlib.util.spec_from_file_location("node_cell_list", путь)
    м = importlib.util.module_from_spec(сп)
    сп.loader.exec_module(м)
    return tuple(м.витрины_узла(ref))

ШАПКА = """    # --- витрины узла K2 ---------------------------------------------------
    # Вставлено инструментом automation/local/make-k2-publisher.py из реестра
    # ячеек. Значения не назначены здесь: unit, host и port берутся из
    # config/site-cells.json. Каталог — тот же снимок поставщика, что у
    # остальных витрин семейства; направление (фильмы или сериалы) задаёт
    # профиль витрины при отрисовке, а не отдельный снимок.
"""


def сумма(путь: Path) -> str:
    return hashlib.sha256(путь.read_bytes()).hexdigest()


def записи_реестра(нужны: tuple[str, ...]) -> dict[str, dict]:
    данные = json.loads(РЕЕСТР.read_text(encoding="utf-8"))
    итог = {}
    for c in данные.get("cells") or []:
        if c["site_id"] in нужны:
            р = c.get("runtime") or {}
            итог[c["site_id"]] = {"unit": р.get("unit"), "host": c.get("domain"),
                                  "port": р.get("port")}
    return итог


def собрать(живой: str, ячейки: dict[str, dict], нужны: tuple[str, ...]) -> str:
    """Вставить записи в конец таблицы ВИТРИНЫ, не трогая остальное."""
    начало = живой.index("ВИТРИНЫ = {")
    # Конец таблицы — первая строка «}» в начале строки после её начала.
    конец = живой.index("\n}\n", начало) + 1
    строки = [ШАПКА]
    for site_id in нужны:
        я = ячейки[site_id]
        строки.append(f'    "{site_id}": {{"unit": "{я["unit"]}", '
                      f'"host": "{я["host"]}",\n'
                      f'{" " * (len(site_id) + 8)}"port": {я["port"]}}},\n')
    return живой[:конец] + "".join(строки) + живой[конец:]


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--source", default=str(ЖИВОЙ))
    р.add_argument("--out", default=str(ВЫХОД))
    р.add_argument("--node", default=УЗЕЛ,
                   help="узел, чьи витрины вставляются (по реестру)")
    а = р.parse_args()
    нужны = витрины_узла(а.node)
    if not нужны:
        print(f"ОТКАЗ: в реестре нет витрин узла {а.node}", file=sys.stderr)
        return 2

    источник = Path(а.source)
    if not источник.is_file():
        print(f"ОТКАЗ: нет действующего издателя {источник}", file=sys.stderr)
        return 2
    ячейки = записи_реестра(нужны)
    нет = [с for с in нужны if с not in ячейки]
    if нет:
        print(f"ОТКАЗ: в реестре нет ячеек {', '.join(нет)}", file=sys.stderr)
        return 2
    пусто = [с for с, я in ячейки.items()
             if not (я["unit"] and я["host"] and я["port"])]
    if пусто:
        print(f"ОТКАЗ: в реестре не заполнены unit/host/port у {', '.join(пусто)} — "
              "это BLOCKED_INPUT, а не повод подставить значение",
              file=sys.stderr)
        return 2

    живой = источник.read_text(encoding="utf-8")
    собранный = собрать(живой, ячейки, нужны)

    выход = Path(а.out) / "automation" / "host"
    выход.mkdir(parents=True, exist_ok=True)
    цель = выход / "nova-catalog-publish.py"
    цель.write_text(собранный, encoding="utf-8")

    # Проверка: разница с живым состоит ТОЛЬКО из добавленных строк.
    добавлено = [с for с in собранный.splitlines()
                 if с not in живой.splitlines()]
    убрано = [с for с in живой.splitlines()
              if с not in собранный.splitlines()]
    ожидаемые = list(нужны)
    print(f"источник: {источник} ({сумма(источник)[:16]})")
    print(f"результат: {цель} ({сумма(цель)[:16]})")
    print(f"строк добавлено: {len(добавлено)}; строк убрано: {len(убрано)}")
    for site_id in ожидаемые:
        есть = f'"{site_id}":' in собранный
        print(f"   {site_id} в таблице публикации: {'да' if есть else 'НЕТ'}")
    if убрано:
        print("ОТКАЗ: из действующего издателя что-то пропало — это не вставка:",
              file=sys.stderr)
        for с in убрано[:5]:
            print(f"   {с}", file=sys.stderr)
        return 1
    import ast

    try:
        ast.parse(собранный)
    except SyntaxError as ош:
        print(f"ОТКАЗ: собранный издатель не разбирается: {ош}", file=sys.stderr)
        return 1
    print("разница состоит только из добавленных записей; синтаксис цел")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
