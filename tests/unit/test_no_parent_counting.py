"""REQ-NO-PARENT-COUNTING: модуль не считает, как глубоко он лежит.

`Path(__file__).resolve().parents[N]` — это знание о собственном месте в
дереве, которого у модуля быть не должно. Оно ломается ровно тогда, когда файл
переносят, то есть в самый неподходящий момент: перенос обязан не менять
поведение, а здесь меняет молча.

Так и случилось при сборке домена флота. `site_admin_contract` считал
`parents[2]`, переехал на уровень глубже, и путь к схемам стал указывать на
`factory/schemas` вместо `schemas`. Договор перестал читаться, и две проверки
упали — но упали они после переноса, а причина была заложена раньше.

Для корня есть `factory.paths.PATHS`. Проверка не пускает отсчёт обратно.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]

#: Файлы, которым отсчёт разрешён: сам модуль путей и точки входа, лежащие вне
#: пакета и не имеющие другого способа найти корень.
РАЗРЕШЕНО = {
    "factory/paths.py",
}


def _считает_родителей(путь: pathlib.Path) -> bool:
    try:
        дерево = ast.parse(путь.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return False
    for узел in ast.walk(дерево):
        # Ищем именно `....parents[N]`, а не любое обращение к parents.
        if (isinstance(узел, ast.Subscript)
                and isinstance(узел.value, ast.Attribute)
                and узел.value.attr == "parents"):
            return True
    return False


@pytest.mark.parametrize("подпакет", ["site_engine"])
def test_модули_движка_не_считают_свою_глубину(подпакет):
    виновные = []
    for путь in sorted((КОРЕНЬ / "factory" / подпакет).rglob("*.py")):
        if "__pycache__" in путь.parts:
            continue
        отн = путь.relative_to(КОРЕНЬ).as_posix()
        if отн in РАЗРЕШЕНО:
            continue
        if _считает_родителей(путь):
            виновные.append(отн)
    assert not виновные, (
        "модули считают собственную глубину в дереве: "
        f"{виновные}. Отсчёт ломается при переносе — так уже сломался договор "
        f"админки при сборке домена флота. Корень берут у factory.paths.PATHS.")
