#!/usr/bin/env python3
"""Карта модулей: кто кого импортирует, где циклы, кто пишет в общие файлы.

Разделение границ начинается не с перемещения файлов, а с ответа на вопрос,
что сейчас от чего зависит. Ответ считается из кода, а не из представления о
нём: импорты разбираются `ast`, а не поиском по строкам, потому что строка
«import» встречается и в комментариях, и в примерах.

Ничего не перемещает и не меняет. Только читает и считает.
"""
from __future__ import annotations

import ast
import collections
import json
import pathlib
import sys

КОРЕНЬ = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/home/claude/wt-prod-25")
ПАКЕТЫ = ("factory", "seo_engine")

#: Пути, в которые пишут во время работы. Общий изменяемый файл — это связь
#: между модулями не менее крепкая, чем импорт, и куда менее заметная.
ЗАПИСЬ = ("var/", "config/", "/srv/", "queue/", "artifacts/")


def модуль_файла(путь: pathlib.Path) -> str:
    отн = путь.relative_to(КОРЕНЬ).with_suffix("")
    части = list(отн.parts)
    if части[-1] == "__init__":
        части.pop()
    return ".".join(части)


def импорты(путь: pathlib.Path) -> set[str]:
    try:
        дерево = ast.parse(путь.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return set()
    найдено: set[str] = set()
    for узел in ast.walk(дерево):
        if isinstance(узел, ast.Import):
            найдено.update(и.name for и in узел.names)
        elif isinstance(узел, ast.ImportFrom):
            if узел.level:  # относительный импорт — внутри своего пакета
                continue
            if узел.module:
                найдено.add(узел.module)
    return {и for и in найдено if и.split(".")[0] in ПАКЕТЫ}


def верхний(модуль: str, глубина: int = 2) -> str:
    """Имя подсистемы: `factory.site_engine.api.x` → `factory.site_engine`."""
    части = модуль.split(".")
    return ".".join(части[:глубина]) if len(части) > 1 else модуль


файлы = [п for пакет in ПАКЕТЫ
         for п in (КОРЕНЬ / пакет).rglob("*.py")
         if (КОРЕНЬ / пакет).is_dir() and "__pycache__" not in п.parts]

граф: dict[str, set[str]] = collections.defaultdict(set)
подробно: dict[str, set[str]] = collections.defaultdict(set)
for путь in файлы:
    свой = модуль_файла(путь)
    for цель in импорты(путь):
        подробно[свой].add(цель)
        а, б = верхний(свой), верхний(цель)
        if а != б:
            граф[а].add(б)

print(f"файлов разобрано: {len(файлы)}")
print("\n=== связи между подсистемами")
for кто in sorted(граф):
    print(f"  {кто:34} → {', '.join(sorted(граф[кто]))}")


def циклы(рёбра: dict[str, set[str]]) -> list[list[str]]:
    """Циклы через обход в глубину. Цикл между подсистемами — это не стиль,
    а невозможность вынести одну из них, не вынеся вторую."""
    найденные: list[list[str]] = []
    цвет: dict[str, int] = {}
    стек: list[str] = []

    def обойти(узел: str) -> None:
        цвет[узел] = 1
        стек.append(узел)
        for сосед in sorted(рёбра.get(узел, ())):
            if цвет.get(сосед, 0) == 0:
                обойти(сосед)
            elif цвет.get(сосед) == 1:
                найденные.append(стек[стек.index(сосед):] + [сосед])
        стек.pop()
        цвет[узел] = 2

    for узел in sorted(рёбра):
        if цвет.get(узел, 0) == 0:
            обойти(узел)
    return найденные


сцепки = циклы(граф)
print(f"\n=== циклы между подсистемами: {len(сцепки)}")
for ц in сцепки[:10]:
    print("  " + " → ".join(ц))

# --- модульный срез внутри site_engine --------------------------------------
print("\n=== кто из factory.site_engine.* импортирует factory.lords.*")
for кто, куда in sorted(подробно.items()):
    if not кто.startswith("factory.site_engine"):
        continue
    чужие = sorted(ц for ц in куда if ц.startswith("factory.lords"))
    if чужие:
        print(f"  {кто:52} → {', '.join(чужие)}")

print("\n=== кто из factory.lords.* импортирует factory.site_engine.*")
for кто, куда in sorted(подробно.items()):
    if not кто.startswith("factory.lords"):
        continue
    чужие = sorted(ц for ц in куда if ц.startswith("factory.site_engine"))
    if чужие:
        print(f"  {кто:52} → {', '.join(чужие)}")

итог = {
    "files": len(файлы),
    "edges": {к: sorted(в) for к, в in граф.items()},
    "cycles": сцепки,
}
(КОРЕНЬ / "var").mkdir(exist_ok=True)
(КОРЕНЬ / "var" / "module-map.json").write_text(
    json.dumps(итог, ensure_ascii=False, indent=2), encoding="utf-8")
print("\nкарта записана: var/module-map.json")
