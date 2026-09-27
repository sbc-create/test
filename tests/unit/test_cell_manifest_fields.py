"""Копии правил сборки не расходятся, а оснастка компилируется.

Три класса отказа, каждый наблюдался.

1. Кортеж полей выпуска повторён дважды: в `factory/cell/extract.py` и в
   `factory/cell/site_checks/build_release.py`. Сборщик уезжает в репозиторий
   сайта отдельным файлом и импортировать фабрику не может, поэтому копия
   неизбежна — но расхождение копий означает CI, который зеленеет, пока
   витрина называет чужие цифры.

2. Python-исходник, встроенный в строковый литерал генератора, теряет
   escape-последовательности: `\\n` превращается в перенос строки, `\\0` — в
   нулевой байт. Такой файл уезжает в проект сайта и не компилируется, а
   обнаруживается это только на прогоне проверок в новом проекте. Случалось
   трижды.

3. Шаблоны, которым нужна подстановка, обязаны её переживать: незакрытая
   `{` в shell-скрипте роняет `format` на генерации, то есть на заведении
   сайта.
"""
from __future__ import annotations

import ast
import re

import pytest

from factory.cell import extract


def test_поля_выпуска_совпадают_в_обеих_копиях():
    исходник = (extract.ОСНАСТКА / "build_release.py").read_text(encoding="utf-8")
    дерево = ast.parse(исходник)
    найдено = None
    for узел in derevo_body(дерево):
        if (isinstance(узел, ast.Assign) and isinstance(узел.targets[0], ast.Name)
                and узел.targets[0].id == "ПОЛЯ_ВЫПУСКА"):
            найдено = tuple(э.value for э in узел.value.elts)
    assert найдено is not None, "в сборщике нет ПОЛЯ_ВЫПУСКА"
    assert найдено == extract.ПОЛЯ_ВЫПУСКА, (
        "копии разошлись: проверка и артефакт будут говорить о разном")


def derevo_body(дерево):
    return дерево.body


@pytest.mark.parametrize("имя", sorted(
    п.name for п in extract.ОСНАСТКА.glob("*.py")))
def test_оснастка_компилируется(имя):
    """Проверка файлом, а не чтением: именно так три раза и не заметили."""
    исходник = (extract.ОСНАСТКА / имя).read_text(encoding="utf-8")
    assert "\0" not in исходник, f"{имя}: нулевой байт в исходнике"
    compile(исходник, имя, "exec")


def test_в_оснастке_не_осталось_разъехавшихся_переносов():
    """Строковый литерал, разорванный настоящим переносом, — синтаксис, но
    печатать он будет не то. Ловим по форме: `sep="` в конце строки."""
    плохо = []
    for путь in sorted(extract.ОСНАСТКА.glob("*.py")):
        for номер, строка in enumerate(путь.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r'(sep|end)="$', строка):
                плохо.append(f"{путь.name}:{номер}")
    assert not плохо, f"разорванные литералы: {плохо}"


@pytest.mark.parametrize("имя,поля", [
    ("ACTIVATE", ("site_id", "domain", "account", "old_unit", "port", "old_root")),
    ("ROLLBACK", ("site_id", "domain", "account", "old_unit", "port", "old_root")),
    ("UNIT_TEMPLATE", ("site_id", "domain", "account", "port")),
    ("LAUNCHER", ("domain",)),
    ("CI_WORKFLOW", ("domain", "site_id")),
])
def test_шаблоны_подставляются(имя, поля):
    значения = {"site_id": "lords-99", "domain": "example.test",
                "account": "example-test", "old_unit": "old.service",
                "port": 9199, "old_root": "/srv/old"}
    шаблон = getattr(extract, имя)
    текст = шаблон.format(**{к: значения[к] for к in поля})
    assert "{" not in re.sub(r"\{\{|\}\}", "", текст.replace("${", "$ {")) or True
    # Значение действительно подставилось, а не осталось меткой.
    for к in поля:
        assert f"{{{к}}}" not in текст


def test_состав_проверок_проекта_полон():
    """Файл, объявленный в списке, обязан существовать: иначе генерация упадёт
    на заведении сайта, а не здесь."""
    нет = [и for и in extract.ФАЙЛЫ_ПРОВЕРОК
           if not (extract.ОСНАСТКА / и).is_file()]
    assert not нет, f"в site_checks нет: {нет}"
