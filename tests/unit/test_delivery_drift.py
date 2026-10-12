"""Доставка между ветвями: отличить «их копия устарела» от «у них своя работа».

Эта разница — весь смысл инструмента. Если копию, в которой есть чужая работа,
объявить устаревшей, следующий шаг — скопировать файл целиком и затереть эту
работу молча. Именно так я чуть не удалил строку SEO-сессии из
`validate_registries.py`, и именно поэтому различение закреплено тестами, а не
осторожностью.

Git здесь настоящий: вопрос «совпадает ли их копия с каким-нибудь МОИМ
коммитом» без истории не ответить. Репозитории одноразовые, в tmp_path.
"""
from __future__ import annotations

import importlib.util
import io
import subprocess
from contextlib import redirect_stdout
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
ИСТОЧНИК = КОРЕНЬ / "automation" / "local" / "delivery-drift.py"


def _модуль():
    спец = importlib.util.spec_from_file_location("drift", ИСТОЧНИК)
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


@pytest.fixture(scope="module")
def м():
    return _модуль()


def git(репо: Path, *арг: str) -> None:
    subprocess.run(["git", "-C", str(репо), *арг], check=True,
                   capture_output=True, text=True, timeout=120)


def моя_ветвь(tmp_path: Path, версии: list[str]) -> Path:
    """Репозиторий с историей: каждая версия файла — отдельный коммит."""
    корень = tmp_path / "моё"
    (корень / "tests" / "unit").mkdir(parents=True)
    git(корень, "init", "-q", "-b", "main")
    git(корень, "config", "user.email", "s@example.invalid")
    git(корень, "config", "user.name", "стенд")
    for текст in версии:
        (корень / "tests" / "unit" / "проба.py").write_text(текст,
                                                            encoding="utf-8")
        git(корень, "add", "-A")
        git(корень, "commit", "-q", "-m", "версия")
    return корень


def их_ветвь(tmp_path: Path, текст: str) -> Path:
    корень = tmp_path / "их"
    (корень / "tests" / "unit").mkdir(parents=True)
    (корень / "tests" / "unit" / "проба.py").write_text(текст, encoding="utf-8")
    return корень


def прогон(м, моё: Path, их: Path):
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        код = м.главное(["--mine", str(моё), "--theirs", str(их),
                         "--subdir", "tests/unit"])
    return код, буфер.getvalue()


def test_их_копия_это_мой_прежний_коммит(м, tmp_path):
    """Тогда доставлять можно целиком: своей работы у них нет."""
    моё = моя_ветвь(tmp_path, ["версия 1\n", "версия 2\n"])
    их = их_ветвь(tmp_path, "версия 1\n")
    код, вывод = прогон(м, моё, их)
    assert код == 1
    assert "их копия УСТАРЕЛА" in вывод
    assert "доставить можно целиком" in вывод
    assert "своя работа" not in вывод


def test_у_них_своя_работа_целиком_копировать_нельзя(м, tmp_path):
    """Главное различение: содержимое не из моей истории."""
    моё = моя_ветвь(tmp_path, ["версия 1\n", "версия 2\n"])
    их = их_ветвь(tmp_path, "версия 1\nих собственная строка\n")
    код, вывод = прогон(м, моё, их)
    assert код == 0, вывод
    assert "СВОЯ работа" in вывод
    assert "переносить построчно" in вывод
    assert "УСТАРЕЛА" not in вывод


def test_совпадающие_файлы_молчат(м, tmp_path):
    моё = моя_ветвь(tmp_path, ["версия 1\n"])
    их = их_ветвь(tmp_path, "версия 1\n")
    код, вывод = прогон(м, моё, их)
    assert код == 0
    assert "файлов совпало 1" in вывод
    assert "УСТАРЕЛА" not in вывод and "СВОЯ работа" not in вывод


def test_разный_состав_ветвей_расхождением_не_считается(м, tmp_path):
    моё = моя_ветвь(tmp_path, ["версия 1\n"])
    их = их_ветвь(tmp_path, "версия 1\n")
    (моё / "tests" / "unit" / "только_моё.py").write_text("x\n", encoding="utf-8")
    (их / "tests" / "unit" / "только_их.py").write_text("y\n", encoding="utf-8")
    код, вывод = прогон(м, моё, их)
    assert код == 0
    assert "только в моей ветви: 1; только у них: 1" in вывод
    assert "не расхождение" in вывод


def test_предел_глубины_ограничивает_поиск(м, tmp_path):
    """Ожидание ограничено ЧИСЛОМ коммитов, а не «пока не найдётся» (D205).

    За пределом совпадение не находится, и тогда файл честно попадает в «своя
    работа» — вывод осторожнее, чем ложное «устарела».
    """
    моё = моя_ветвь(tmp_path, [f"версия {i}\n" for i in range(1, 6)])
    их = их_ветвь(tmp_path, "версия 1\n")
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        м.главное(["--mine", str(моё), "--theirs", str(их),
                   "--subdir", "tests/unit", "--depth", "2"])
    assert "СВОЯ работа" in буфер.getvalue()


def test_нет_каталога_у_одной_стороны_это_не_измерено(м, tmp_path):
    моё = моя_ветвь(tmp_path, ["версия 1\n"])
    их = tmp_path / "пусто"
    их.mkdir()
    код, вывод = прогон(м, моё, их)
    assert код == 0
    assert "нет в одной из ветвей" in вывод
