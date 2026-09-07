"""REQ-NO-CYCLES: между подсистемами нет взаимных зависимостей.

Цикл — не вопрос стиля. Он означает, что ни одну из двух подсистем нельзя
вынести, не вынеся вторую: разрезать нечего, пока связь идёт в обе стороны.

На начало этапа циклов было три, и каждый держался на малом:

* `site_engine ↔ lords` — один импорт `slugify`, чистой текстовой функции,
  лежавшей внутри семейства витрин;
* `lords ↔ build` — одна константа `POST_BUILD_STAGES`, словарь этапов,
  которым пользуются обе стороны;
* `lords ↔ recs` — командная строка движка рекомендаций, знавшая о витринах,
  хотя сам движок о них не знает.

Все три разорваны переносом в общую опору и выделением точек входа. Проверка
стоит здесь, чтобы четвёртый цикл не появился незамеченным: заметить его по
коду в момент возникновения нельзя, он складывается из двух правок в разных
местах и разных днях.
"""

from __future__ import annotations

import ast
import collections
import pathlib

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ПАКЕТ = "factory"


def _импорты(путь: pathlib.Path) -> set[str]:
    try:
        дерево = ast.parse(путь.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return set()
    найдено: set[str] = set()
    for узел in ast.walk(дерево):
        if isinstance(узел, ast.Import):
            найдено.update(и.name for и in узел.names)
        elif isinstance(узел, ast.ImportFrom) and узел.module and not узел.level:
            найдено.add(узел.module)
    return {и for и in найдено if и.split(".")[0] == ПАКЕТ}


def _подсистема(модуль: str) -> str:
    части = модуль.split(".")
    return ".".join(части[:2]) if len(части) > 1 else модуль


@pytest.fixture(scope="module")
def граф() -> dict[str, set[str]]:
    рёбра: dict[str, set[str]] = collections.defaultdict(set)
    for путь in (КОРЕНЬ / ПАКЕТ).rglob("*.py"):
        if "__pycache__" in путь.parts:
            continue
        свой = _подсистема(
            путь.relative_to(КОРЕНЬ).with_suffix("").as_posix().replace("/", "."))
        for цель in _импорты(путь):
            чужой = _подсистема(цель)
            if чужой != свой:
                рёбра[свой].add(чужой)
    return рёбра


def _циклы(рёбра: dict[str, set[str]]) -> list[list[str]]:
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


def test_циклов_между_подсистемами_нет(граф):
    циклы = _циклы(граф)
    описание = "\n  ".join(" → ".join(ц) for ц in циклы)
    assert not циклы, (
        f"появились взаимные зависимости между подсистемами:\n  {описание}\n"
        f"Цикл означает, что ни одну из них нельзя вынести, не вынеся вторую. "
        f"Разрывается он обычно малым: общей функцией, вынесенной в опору, или "
        f"точкой входа, вынесенной из предметного пакета.")


def test_опора_никого_не_знает(граф):
    """Модули общей опоры не зависят ни от одной подсистемы."""
    for опора in ("factory.slug", "factory.lifecycle_stages"):
        зависимости = {ц for ц in граф.get(опора, set())
                       if ц not in ("factory", "factory.errors", "factory.paths")}
        assert not зависимости, (
            f"{опора} зависит от {sorted(зависимости)}; опора, знающая "
            f"подсистему, перестаёт быть опорой")
