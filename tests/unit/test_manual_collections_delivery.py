"""Перенос ручного состава подборок на линию Zona — по якорям, с отказом.

Поручение владельца 27.10: выпустить подготовленные подборки на zonafilm.space
и zonafilm12.site, добавив ручной состав в СУЩЕСТВУЮЩИЙ механизм и сохранив
работающие фильтры. Рантайм этих витрин ведёт своя линия: продвижение шаблона
на них отказывает намеренно, поэтому механизм приезжает по якорям.

Проверяется сам инструмент: он обязан отказываться там, где файл не той линии,
и не применять правку дважды.
"""
from __future__ import annotations

import importlib.util
import pathlib
import subprocess
import sys

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ИНСТРУМЕНТ = КОРЕНЬ / "automation" / "host" / "apply-manual-collections-patch.py"


@pytest.fixture()
def модуль():
    сп = importlib.util.spec_from_file_location("apply_manual_collections", ИНСТРУМЕНТ)
    м = importlib.util.module_from_spec(сп)
    sys.modules["apply_manual_collections"] = м
    сп.loader.exec_module(м)
    return м


def test_блок_контракта_берётся_из_канона_а_не_из_копии(модуль):
    """Вторая копия общего механизма — это разный состав подборки на витринах."""
    блок = модуль.блок_ручного_состава()
    for имя in ("ручные_подборки", "разрешить_ручную", "ручная_как_коллекция",
                "ИСТОЧНИК_РУЧНОЙ"):
        assert f"def {имя}" in блок or f"{имя} = " in блок, имя
    # Блок читается из канонического файла, а не хранится в инструменте.
    assert "ручная_как_коллекция" not in ИНСТРУМЕНТ.read_text(encoding="utf-8").split(
        "def блок_ручного_состава")[0]


def test_канонический_рантайм_инструментом_не_правится(модуль):
    """У канона свой путь переноса: у его оболочки есть `индексируема`."""
    текст = (КОРЕНЬ / "automation" / "host" / "lords-frontend.py").read_text(
        encoding="utf-8")
    with pytest.raises(SystemExit) as сбой:
        модуль.применить(текст)
    assert "канонический рантайм" in str(сбой.value)


def test_чужой_файл_отвергается_с_названной_причиной(модуль):
    with pytest.raises(SystemExit) as сбой:
        модуль.применить("x = 1\n")
    assert "линии Zona" in str(сбой.value)


def test_остатки_допускают_одну_легаси_оболочку(модуль):
    """Легаси-оболочка без `путь` остаётся как была: подставить путь нечем."""
    приведённый = (
        'РУЧНЫЕ_ПОДБОРКИ = {}\nif ключ in ЗАКРЫТЫЕ_ПОДБОРКИ:\n'
        '[a-z0-9_-]{1,60}\ndef ручная_подборка\n'
        'ручная = РУЧНЫЕ_ПОДБОРКИ.get(ключ)\n'
        'for подборка_ред in РУЧНЫЕ_ПОДБОРКИ.values():\n'
        'for подборка_ред in РУЧНЫЕ_ПОДБОРКИ.values():\n'
        'self._полоса_подборок_раздела(разд, стр)\n.col__why{\n'
        # Полоса раздела знает каталог: без этого признака остаток законен —
        # на самой посещаемой странице разделов ссылок на подборки нет.
        'заголовок, метка = "Редакционные подборки", "catalog"\n'
        '<meta name="robots" content="{мета_роботов()}">\n')
    assert модуль.остатки(приведённый) == []
    # Две — уже беда: страница считает директиву мимо пути.
    assert модуль.остатки(приведённый + '<meta name="robots" content="{мета_роботов()}">')


@pytest.mark.parametrize("проект", ["zonafilm-space", "zonafilm12-site"])
def test_живые_проекты_приведены(проект):
    """Главное: обе витрины, для которых делался перенос, уже приведены."""
    пути = [str(КОРЕНЬ / "var" / "site-repos" / проект / "src" / имя)
            for имя in ("lords-frontend.py", "collection_contract.py")]
    и = subprocess.run([sys.executable, str(ИНСТРУМЕНТ), "--check", *пути],
                       capture_output=True, text=True, timeout=180)
    assert и.returncode == 0, и.stdout + и.stderr


@pytest.mark.parametrize("проект", ["zonafilm-space", "zonafilm12-site"])
def test_файл_подборок_лежит_там_где_его_ищет_рантайм(проект):
    """Файл в docs/ воротами не виден: рантайм читает config/collections.json."""
    путь = КОРЕНЬ / "var" / "site-repos" / проект / "config" / "collections.json"
    assert путь.is_file(), f"нет {путь}"


@pytest.mark.parametrize("проект", ["zonafilm-space", "zonafilm12-site"])
def test_замок_описывает_исходники(проект):
    """Иначе `checks/verify_pins.py` отказывает и CI остаётся красным."""
    и = subprocess.run(
        [sys.executable, str(КОРЕНЬ / "var" / "site-repos" / проект / "checks"
                             / "verify_pins.py")],
        capture_output=True, text=True, timeout=180)
    assert и.returncode == 0, и.stdout + и.stderr


@pytest.mark.parametrize("проект", ["zonafilm-space", "zonafilm12-site"])
def test_замок_описывает_каждый_файл_состава(проект):
    """Правка после пересчёта замка — повторяющаяся беда, и она дорогая.

    Измерено 27.10: замок был пересчитан, затем инструмент целей дописал ещё
    две ветви события, и коммит ушёл с прежним отпечатком. CI отказал
    `pins-match-sources`, и это верно: артефакт выпуска не имеет права
    описывать не те байты, которые в нём лежат. Проверка здесь сверяет КАЖДЫЙ
    файл состава, а не только точку входа.
    """
    import hashlib
    import json

    к = КОРЕНЬ / "var" / "site-repos" / проект
    замок = json.loads((к / "pins.lock.json").read_text(encoding="utf-8"))
    расхождения = []
    for имя, запись in (замок.get("files") or {}).items():
        ф = к / "src" / имя
        объявлено = str(запись.get("sha256") or "")
        if not объявлено:
            continue  # поставляется отдельным выпуском
        if not ф.is_file():
            расхождения.append(f"{имя}: файла нет")
            continue
        на_диске = hashlib.sha256(ф.read_bytes()).hexdigest()
        if на_диске != объявлено:
            расхождения.append(f"{имя}: {на_диске[:12]} вместо {объявлено[:12]}")
    assert not расхождения, расхождения
