"""REQ-TREE-DIVERGENCE: расхождения трёх деревьев кода видны по именам файлов.

Три случая за 19.10, и каждый стоил времени: правка в моей ветке при чтении из
живого дерева; файл теста в моей ветке отставал от живого на пять суток;
установленная копия исполнителя отличалась от живого дерева в 13 файлах.

Закрепляется:

* сравнение по СОДЕРЖИМОМУ, а не по времени (время правится копированием);
* файл, который есть только в одном дереве, считается ОТДЕЛЬНО: у линий свои
  инструменты, и это не расхождение исполняемого кода;
* кэш питона не сравнивается;
* меньше двух непустых деревьев — «не измерено», а не «совпадает».
"""
from __future__ import annotations

import importlib.util
import pathlib

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_путь = КОРЕНЬ / "automation/local/tree-divergence.py"
_спец = importlib.util.spec_from_file_location("tree_divergence", _путь)
ИНСТР = importlib.util.module_from_spec(_спец)
_спец.loader.exec_module(ИНСТР)

ПОДДЕРЕВЬЯ = ("factory",)


def _дерево(корень: pathlib.Path, файлы: dict[str, str]) -> pathlib.Path:
    for путь, тело in файлы.items():
        п = корень / путь
        п.parent.mkdir(parents=True, exist_ok=True)
        п.write_text(тело, encoding="utf-8")
    return корень


def test_совпадающие_деревья(tmp_path):
    a = _дерево(tmp_path / "a", {"factory/x.py": "код\n"})
    b = _дерево(tmp_path / "b", {"factory/x.py": "код\n"})
    и = ИНСТР.сверить({"моё": a, "живое": b}, ПОДДЕРЕВЬЯ)
    assert и["измерено"] is True and и["расхождений"] == 0
    assert и["только_в_одном"] == {}


def test_разное_содержимое_называется(tmp_path):
    a = _дерево(tmp_path / "a", {"factory/x.py": "код 1\n"})
    b = _дерево(tmp_path / "b", {"factory/x.py": "код 2\n"})
    и = ИНСТР.сверить({"моё": a, "живое": b}, ПОДДЕРЕВЬЯ)
    assert и["расхождений"] == 1
    assert и["список"][0]["файл"] == "factory/x.py"
    assert и["список"][0]["состояние"]["моё"] != и["список"][0]["состояние"]["живое"]


def test_односторонний_файл_не_расхождение(tmp_path):
    a = _дерево(tmp_path / "a", {"factory/x.py": "код\n", "factory/мой.py": "я\n"})
    b = _дерево(tmp_path / "b", {"factory/x.py": "код\n"})
    и = ИНСТР.сверить({"моё": a, "живое": b}, ПОДДЕРЕВЬЯ)
    assert и["расхождений"] == 0
    assert и["только_в_одном"] == {"моё": 1}
    assert и["только_в_одном_файлы"]["моё"] == ["factory/мой.py"]


def test_одинаковое_время_не_скрывает_разное_содержимое(tmp_path):
    """Сравнение по содержимому: копирование сохраняет время, но не смысл."""
    a = _дерево(tmp_path / "a", {"factory/x.py": "код 1\n"})
    b = _дерево(tmp_path / "b", {"factory/x.py": "код 2\n"})
    метка = (a / "factory/x.py").stat().st_mtime
    import os
    os.utime(b / "factory/x.py", (метка, метка))
    и = ИНСТР.сверить({"моё": a, "живое": b}, ПОДДЕРЕВЬЯ)
    assert и["расхождений"] == 1


def test_кэш_питона_не_сравнивается(tmp_path):
    a = _дерево(tmp_path / "a", {"factory/x.py": "код\n",
                                 "factory/__pycache__/x.cpython-310.pyc": "м"})
    b = _дерево(tmp_path / "b", {"factory/x.py": "код\n", "factory/x.pyc": "м"})
    и = ИНСТР.сверить({"моё": a, "живое": b}, ПОДДЕРЕВЬЯ)
    assert и["расхождений"] == 0 and и["только_в_одном"] == {}


def test_три_дерева_сравниваются_разом(tmp_path):
    a = _дерево(tmp_path / "a", {"factory/x.py": "код 1\n"})
    b = _дерево(tmp_path / "b", {"factory/x.py": "код 2\n"})
    c = _дерево(tmp_path / "c", {"factory/x.py": "код 3\n"})
    и = ИНСТР.сверить({"моё": a, "живое": b, "установленное": c}, ПОДДЕРЕВЬЯ)
    assert и["расхождений"] == 1
    состояние = и["список"][0]["состояние"]
    assert len({состояние["моё"], состояние["живое"], состояние["установленное"]}) == 3


def test_одно_непустое_дерево_не_измерено(tmp_path):
    a = _дерево(tmp_path / "a", {"factory/x.py": "код\n"})
    пусто = tmp_path / "b"
    пусто.mkdir()
    и = ИНСТР.сверить({"моё": a, "живое": пусто}, ПОДДЕРЕВЬЯ)
    assert и["измерено"] is False and "нечего сравнивать" in и["почему"]


def test_коды_возврата(tmp_path, capsys):
    a = _дерево(tmp_path / "a", {"factory/x.py": "код\n"})
    b = _дерево(tmp_path / "b", {"factory/x.py": "код\n"})
    c = tmp_path / "c"
    c.mkdir()
    assert ИНСТР.main(["--mine", str(a), "--live", str(b), "--installed", str(c),
                       "--paths", "factory"]) == 0
    (b / "factory/x.py").write_text("другое\n", encoding="utf-8")
    assert ИНСТР.main(["--mine", str(a), "--live", str(b), "--installed", str(c),
                       "--paths", "factory"]) == 1
    вывод = capsys.readouterr().out
    assert "РАЗЛИЧАЮТСЯ" in вывод


def test_живые_деревья_сравниваются(capsys):
    """Отрицательный контроль: на этом хосте инструмент что-то измеряет."""
    код = ИНСТР.main(["--paths", "factory/cell"])
    вывод = capsys.readouterr().out
    assert код in (0, 1), вывод
    assert "сравнивались поддеревья" in вывод
