#!/usr/bin/env python3
"""Число серий и сезонов в видимом тексте склоняется (T180, 16.10).

Доставляется в `checks/plural_counts.py` инструментом
automation/local/wire-plural-counts.py.

Живой замер 16.10 на lordfilm47.space: «Сезон 1 · 24 серий», «21 серий»,
«4 серий» — шаблон подставлял число в f-строку с жёстким «серий»/«сезона».
Проверка читает src/lords-frontend.py (или src/animedia-frontend.py) (синтаксическое дерево, без запуска) и
ищет в f-строках подстановку, за которой сразу идёт « серий» или « сезона»:
такая строка пишет одно слово при любом числе. Затем сверяет формы функции
`_серий`/`_сезонов`, если она есть.

Коды выхода: 0 — норма, 1 — дефект, 2 — не измерено (нет файла шаблона).
"""
import ast
import pathlib
import sys

ФАЙЛЫ = (pathlib.Path("src/lords-frontend.py"), pathlib.Path("src/animedia-frontend.py"))
# Своя вёрстка lordserial33.biz: «N из M серий» на карточках (16.10 20:20Z «из 201 серий»).
ДОП = (pathlib.Path("src/lords02_view.py"),)
ЖЁСТКИЕ = (" серий", " сезона", " сезонов")


def жёсткие_места(дерево: ast.AST) -> list[int]:
    места = []
    for узел in ast.walk(дерево):
        if not isinstance(узел, ast.JoinedStr):
            continue
        части = узел.values
        for a, b in zip(части, части[1:]):
            if (isinstance(a, ast.FormattedValue) and isinstance(b, ast.Constant)
                    and isinstance(b.value, str) and b.value.startswith(ЖЁСТКИЕ)):
                места.append(узел.lineno)
    return места


def главная() -> int:
    ФАЙЛ = next((ф for ф in ФАЙЛЫ if ф.is_file()), None)
    try:  # исполняемый файл — entrypoint из config/site.json (у animedia-icu лежат оба шаблона)
        import json
        вход = pathlib.Path("src") / json.loads(pathlib.Path("config/site.json").read_text(encoding="utf-8"))["entrypoint"]
        if вход in ФАЙЛЫ and вход.is_file():
            ФАЙЛ = вход
    except (OSError, ValueError, KeyError, TypeError):
        pass
    if ФАЙЛ is None:
        print(f"НЕ ИЗМЕРЕНО: нет ни одного из {[str(ф) for ф in ФАЙЛЫ]}")
        return 2
    текст = ФАЙЛ.read_text(encoding="utf-8")
    дерево = ast.parse(текст)
    провалы = [f"{ФАЙЛ}:{n}: число в f-строке перед жёстким «серий/сезона»" for n in жёсткие_места(дерево)]
    for доп in ДОП:
        if доп.is_file():
            провалы += [f"{доп}:{n}: число в f-строке перед жёстким «серий/сезона»"
                        for n in жёсткие_места(ast.parse(доп.read_text(encoding="utf-8")))]
    функции = {у.name: у for у in дерево.body if isinstance(у, ast.FunctionDef)}
    if "_серий" in функции:
        ns: dict = {}
        имена = [и for и in ("_число_мн", "_серий", "_сезонов", "_из_серий") if и in функции]
        exec(compile(ast.Module(body=[функции[и] for и in имена], type_ignores=[]), str(ФАЙЛ), "exec"), ns)
        for n, w in {1: "1 серия", 3: "3 серии", 11: "11 серий", 21: "21 серия", 24: "24 серии", 98: "98 серий"}.items():
            if ns["_серий"](n) != w:
                провалы.append(f"_серий({n}) = «{ns['_серий'](n)}», ждали «{w}»")
        if "_из_серий" in ns and (ns["_из_серий"](201), ns["_из_серий"](44), ns["_из_серий"](11)) != (
                "201 серии", "44 серий", "11 серий"):
            провалы.append("_из_серий: неверный родительный после «из»")
        if "_сезонов" in ns and ns["_сезонов"](4) != "4 сезона":
            провалы.append(f"_сезонов(4) = «{ns['_сезонов'](4)}»")
    for п in провалы:
        print("FAIL", п)
    if провалы:
        return 1
    print("OK: числа серий и сезонов склоняются")
    return 0


if __name__ == "__main__":
    sys.exit(главная())
