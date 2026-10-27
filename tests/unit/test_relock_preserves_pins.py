"""Пересчёт замка не стирает происхождение и не идёт без причины.

Беда измеренная (27.10, zonafilm-space): прежняя редакция `tools/relock.py`
заменяла запись файла целиком — `{"sha256", "bytes"}` — и вместе с суммой
стирала `origin`, `repo_path`, `change_note` и накопленный журнал
`verified_against`. Потеря не видна ни одной проверке репозитория: замок
сходится с исходниками, а происхождение выпускаемого файла исчезло.

Инструмент один для трёх витрин, и правка его — общая: проверяется каждая копия.
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
РЕПОЗИТОРИИ = ("zonafilm-space", "zonafilm12-site", "animedia-icu")


def _копия(имя: str, кат: str) -> pathlib.Path:
    """Копия репозитория витрины: только замок, инструмент и исходники."""
    исток = КОРЕНЬ / "var" / "site-repos" / имя
    цель = pathlib.Path(кат) / имя
    (цель / "tools").mkdir(parents=True)
    shutil.copytree(исток / "src", цель / "src")
    shutil.copyfile(исток / "pins.lock.json", цель / "pins.lock.json")
    shutil.copyfile(исток / "tools" / "relock.py", цель / "tools" / "relock.py")
    return цель


@pytest.mark.parametrize("имя", РЕПОЗИТОРИИ)
def test_копии_инструмента_совпадают(имя):
    """Общий инструмент — один текст: разошедшиеся копии означают, что правка
    дошла до одной витрины и не дошла до другой."""
    образец = (КОРЕНЬ / "var" / "site-repos" / "animedia-icu" / "tools"
               / "relock.py").read_bytes()
    assert (КОРЕНЬ / "var" / "site-repos" / имя / "tools"
            / "relock.py").read_bytes() == образец


@pytest.mark.parametrize("имя", РЕПОЗИТОРИИ)
def test_пересчёт_сохраняет_поля_происхождения(имя):
    with tempfile.TemporaryDirectory() as кат:
        репо = _копия(имя, кат)
        замок = json.loads((репо / "pins.lock.json").read_text(encoding="utf-8"))
        # Правка исходника: сумма обязана измениться.
        файл = sorted(замок["files"])[0]
        цель = репо / "src" / файл
        цель.write_text(цель.read_text(encoding="utf-8") + "\n# правка для теста\n",
                        encoding="utf-8")
        и = subprocess.run(
            [sys.executable, str(репо / "tools" / "relock.py"), "--write",
             "--unpinned", "report", "--reason", "проверка сохранности полей"],
            capture_output=True, text=True, timeout=180)
        assert и.returncode == 0, и.stdout + и.stderr
        новый = json.loads((репо / "pins.lock.json").read_text(encoding="utf-8"))

    assert set(новый["files"]) == set(замок["files"]), "состав замка изменился"
    for имя_файла, было in замок["files"].items():
        стало = новый["files"][имя_файла]
        # Поле журнала у записи могло отсутствовать: его появление — то, зачем
        # причина и требуется. Исчезнуть не может ни одно поле.
        assert set(было) - set(стало) == set(), (имя_файла, set(было) - set(стало))
        assert set(стало) - set(было) <= {"verified_against"}, (
            имя_файла, set(стало) - set(было))
        for поле, значение in было.items():
            if поле in ("sha256", "bytes", "previous_sha256", "verified_against"):
                continue
            assert стало[поле] == значение, (имя_файла, поле)
    # Журнал изменённого файла дописан, а не перезаписан.
    запись = новый["files"][sorted(замок["files"])[0]]
    прежний = замок["files"][sorted(замок["files"])[0]]
    if прежний.get("verified_against"):
        assert запись["verified_against"].startswith(прежний["verified_against"])
    assert "Замок пересчитан: проверка сохранности полей." in запись["verified_against"]
    assert прежний["sha256"][:12] in запись["verified_against"]


@pytest.mark.parametrize("имя", РЕПОЗИТОРИИ)
def test_пересчёт_без_причины_отказывает(имя):
    """Замок без причины не отличить от подогнанного под проверку."""
    with tempfile.TemporaryDirectory() as кат:
        репо = _копия(имя, кат)
        файл = sorted(json.loads(
            (репо / "pins.lock.json").read_text(encoding="utf-8"))["files"])[0]
        цель = репо / "src" / файл
        цель.write_text(цель.read_text(encoding="utf-8") + "\n# правка\n",
                        encoding="utf-8")
        прежний = (репо / "pins.lock.json").read_text(encoding="utf-8")
        и = subprocess.run(
            [sys.executable, str(репо / "tools" / "relock.py"), "--write",
             "--unpinned", "report"],
            capture_output=True, text=True, timeout=180)
        assert и.returncode != 0
        assert "ОТКАЗ" in и.stdout
        assert (репо / "pins.lock.json").read_text(encoding="utf-8") == прежний


@pytest.mark.parametrize("имя", РЕПОЗИТОРИИ)
def test_незакреплённый_файл_останавливает_по_умолчанию(имя):
    """Незакреплённый файл едет в артефакт, и `verify_pins` его не видит:
    по умолчанию это стоп, а не предупреждение в поток."""
    with tempfile.TemporaryDirectory() as кат:
        репо = _копия(имя, кат)
        (репо / "src" / "новый_модуль.py").write_text("# нечем закрепить\n",
                                                      encoding="utf-8")
        и = subprocess.run(
            [sys.executable, str(репо / "tools" / "relock.py")],
            capture_output=True, text=True, timeout=180)
    assert и.returncode != 0
    assert "незакреплённые файлы" in и.stdout
    assert "новый_модуль.py" in и.stdout


@pytest.mark.parametrize("имя", РЕПОЗИТОРИИ)
def test_замок_совпадает_с_исходниками(имя):
    """Текущее состояние: пересчёт нечего делать."""
    и = subprocess.run(
        [sys.executable,
         str(КОРЕНЬ / "var" / "site-repos" / имя / "tools" / "relock.py"),
         "--unpinned", "report"],
        capture_output=True, text=True, timeout=180)
    assert "замок совпадает с исходниками" in и.stdout, и.stdout + и.stderr
