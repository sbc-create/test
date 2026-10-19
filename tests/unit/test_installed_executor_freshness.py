"""REQ-CELL-INSTALLED-FRESHNESS: исполнитель ячеек исполняет код из копии.

Операции над ячейками исполняет не рабочее дерево, а установленная копия
`/usr/local/lib/site-factory-cell`. Проверка процессов (`service-code-freshness`)
этого не видит: там сравнивается запуск процесса с датой файла, а здесь — два
дерева между собой.

Повод, измеренный 19.10: правка прогрева лежала в ветке, установленная копия
была от 12.10, и повтор активации пошёл бы по старому коду. Тот же прогон нашёл
13 различающихся файлов и 2 отсутствующие схемы.

Третий исход обязателен: нет копии или нет дерева — «не измерено» с причиной, а
не «всё совпадает».
"""
from __future__ import annotations

import importlib.util
import json
import pathlib

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_путь = КОРЕНЬ / "automation/local/installed-executor-freshness.py"
_спец = importlib.util.spec_from_file_location("installed_executor_freshness", _путь)
ИНСТР = importlib.util.module_from_spec(_спец)
_спец.loader.exec_module(ИНСТР)


def _дерево(корень: pathlib.Path, файлы: dict[str, str]) -> pathlib.Path:
    for путь, тело in файлы.items():
        п = корень / путь
        п.parent.mkdir(parents=True, exist_ok=True)
        п.write_text(тело, encoding="utf-8")
    return корень


БАЗА = {
    "factory/cell/privileged.py": "код = 1\n",
    "factory/cell/executor.py": "код = 2\n",
    "schemas/site.schema.json": "{}\n",
}


def test_совпадающие_деревья(tmp_path):
    у = _дерево(tmp_path / "installed", БАЗА)
    д = _дерево(tmp_path / "tree", БАЗА)
    и = ИНСТР.сверить(у, д)
    assert и["измерено"] is True
    assert и["различается"] == [] and и["только_в_дереве"] == []
    assert и["совпадает"] == 3


def test_различие_называется_по_имени(tmp_path):
    у = _дерево(tmp_path / "installed", БАЗА)
    д = _дерево(tmp_path / "tree", {**БАЗА, "factory/cell/privileged.py": "код = 99\n"})
    и = ИНСТР.сверить(у, д)
    assert и["различается"] == ["factory/cell/privileged.py"]


def test_файл_только_в_дереве(tmp_path):
    """Не установленная новая проверка — расхождение, а не мелочь."""
    у = _дерево(tmp_path / "installed", БАЗА)
    д = _дерево(tmp_path / "tree", {**БАЗА, "schemas/новая.schema.json": "{}\n"})
    и = ИНСТР.сверить(у, д)
    assert и["только_в_дереве"] == ["schemas/новая.schema.json"]


def test_файл_только_у_исполнителя(tmp_path):
    у = _дерево(tmp_path / "installed", {**БАЗА, "factory/cell/старый.py": "x\n"})
    д = _дерево(tmp_path / "tree", БАЗА)
    и = ИНСТР.сверить(у, д)
    assert и["только_установлено"] == ["factory/cell/старый.py"]


def test_кэш_питона_не_сравнивается(tmp_path):
    у = _дерево(tmp_path / "installed", {**БАЗА,
                                         "factory/cell/__pycache__/x.cpython-310.pyc": "м"})
    д = _дерево(tmp_path / "tree", {**БАЗА, "factory/cell/x.pyc": "м"})
    и = ИНСТР.сверить(у, д)
    assert и["различается"] == [] and и["только_установлено"] == []
    assert и["только_в_дереве"] == []


def test_данные_исполнителя_не_сравниваются(tmp_path):
    """var/ и artifacts/ принадлежат исполнителю, в дереве их нет."""
    у = _дерево(tmp_path / "installed", {**БАЗА, "var/заявки/1.json": "{}"})
    д = _дерево(tmp_path / "tree", БАЗА)
    assert ИНСТР.сверить(у, д)["только_установлено"] == []


def test_нет_копии_не_измерено(tmp_path):
    д = _дерево(tmp_path / "tree", БАЗА)
    и = ИНСТР.сверить(tmp_path / "нет", д)
    assert и["измерено"] is False and "нет установленной копии" in и["почему"]


def test_нет_дерева_не_измерено(tmp_path):
    у = _дерево(tmp_path / "installed", БАЗА)
    и = ИНСТР.сверить(у, tmp_path / "нет")
    assert и["измерено"] is False and "нет дерева источника" in и["почему"]


def test_пустая_копия_не_измерено(tmp_path):
    у = (tmp_path / "installed")
    у.mkdir()
    д = _дерево(tmp_path / "tree", БАЗА)
    и = ИНСТР.сверить(у, д)
    assert и["измерено"] is False and "нет файлов" in и["почему"]


def test_происхождение_читается(tmp_path):
    у = _дерево(tmp_path / "installed", БАЗА)
    (у / "cell-install.json").write_text(json.dumps(
        {"code_source": "/x", "installed_at": "2026-10-12T17:34:02Z"}), encoding="utf-8")
    д = _дерево(tmp_path / "tree", БАЗА)
    и = ИНСТР.сверить(у, д)
    assert и["установлена_из"] == "/x"
    assert и["установлена_когда"] == "2026-10-12T17:34:02Z"
    assert "без пакета" in и["пакет"]


def test_коды_возврата(tmp_path, capsys):
    у = _дерево(tmp_path / "installed", БАЗА)
    д = _дерево(tmp_path / "tree", БАЗА)
    assert ИНСТР.main(["--installed", str(у), "--tree", str(д)]) == 0
    assert "расхождений нет" in capsys.readouterr().out
    (д / "factory/cell/privileged.py").write_text("код = 99\n", encoding="utf-8")
    assert ИНСТР.main(["--installed", str(у), "--tree", str(д)]) == 1
    assert "по ДРУГОМУ коду" in capsys.readouterr().out
    assert ИНСТР.main(["--installed", str(tmp_path / "нет"), "--tree", str(д)]) == 2


def test_живой_хост_измеряется(capsys):
    """Отрицательный контроль: на этом хосте проверка что-то измеряет."""
    код = ИНСТР.main([])
    вывод = capsys.readouterr().out
    assert код in (0, 1), вывод
    assert "установленная копия" in вывод
