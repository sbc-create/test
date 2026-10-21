"""Unit-файлы регулярных проходов запустили бы ровно то, что мы думаем.

«Файл существует» тестом не считается, поэтому проверяется исполнимость строки
`ExecStart`: тот ли это скрипт, принимает ли он НАЗВАННЫЙ в unit-е флаг и
запускается ли из объявленного `WorkingDirectory`. Повод измеренный: сверка
карт один раз уже падала на том, что в unit-е стоял вызов без обязательного
аргумента — `sitemap-reconcile.py` без `--all-indexable` завершается кодом 2 с
«не названо ни одной витрины», и таймер отмечал бы запуск неуспешным каждые
сутки, не измеряя ничего.

Отдельно — специфер новее целевого systemd: Ubuntu 22.04 везёт 249, и `%d`
(введён в 250) остался бы literal-ом. Это тот же класс, что закреплён в
`test_systemd_unit_compatibility.py` для каталога `automation/host/systemd`, но
регулярные проходы лежат на уровень выше и той проверкой не охвачены.
"""
from __future__ import annotations

import importlib.util
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
ХОСТ = КОРЕНЬ / "automation" / "host"

#: Регулярные проходы: unit → (скрипт, флаг, который unit ему даёт).
ПРОХОДЫ = {
    "sitemap-reconcile": ("automation/local/sitemap-reconcile.py",
                          "--all-indexable"),
    "selection-indexability": ("automation/local/catalog-selection-indexability.py",
                               "--all"),
}

#: Минимальная версия systemd на целевом хосте (Ubuntu 22.04 LTS везёт 249).
СПЕЦИФЕРЫ_НОВЕЕ_ЦЕЛИ = {"%d": 250, "%D": 250}


def _значение(текст: str, ключ: str) -> str | None:
    м = re.search(rf"^{ключ}=(.*)$", текст, re.M)
    return м.group(1).strip() if м else None


@pytest.mark.parametrize("имя", sorted(ПРОХОДЫ))
def test_execstart_запускает_названный_скрипт(имя):
    текст = (ХОСТ / f"{имя}.service").read_text(encoding="utf-8")
    скрипт, флаг = ПРОХОДЫ[имя]
    строка = _значение(текст, "ExecStart")
    assert строка, f"{имя}.service без ExecStart"
    части = shlex.split(строка)
    assert части[0] == "/usr/bin/python3", части[0]
    assert части[1] == скрипт, части[1]
    assert флаг in части[2:], f"unit не передаёт {флаг}: {части}"
    assert (КОРЕНЬ / скрипт).is_file(), f"нет файла {скрипт}"


@pytest.mark.parametrize("имя", sorted(ПРОХОДЫ))
def test_скрипт_принимает_флаг_из_unit_а(имя):
    """Флаг разбирается самим скриптом, а не предполагается похожим."""
    скрипт, флаг = ПРОХОДЫ[имя]
    спец = importlib.util.spec_from_file_location(f"проход_{имя}",
                                                  КОРЕНЬ / скрипт)
    модуль = importlib.util.module_from_spec(спец)
    sys.modules[спец.name] = модуль
    спец.loader.exec_module(модуль)
    main = getattr(модуль, "main", None) or getattr(модуль, "главное", None)
    assert main is not None, f"{скрипт} без точки входа"
    # Разбор аргументов без выхода в сеть: просьба о справке печатает флаги.
    г = subprocess.run([sys.executable, str(КОРЕНЬ / скрипт), "--help"],
                       capture_output=True, text=True, cwd=КОРЕНЬ, timeout=120)
    assert г.returncode == 0, г.stderr[:400]
    assert флаг in г.stdout, f"{скрипт} не знает флага {флаг}"


@pytest.mark.parametrize("имя", sorted(ПРОХОДЫ))
def test_рабочий_каталог_и_учётная_запись(имя):
    текст = (ХОСТ / f"{имя}.service").read_text(encoding="utf-8")
    каталог = _значение(текст, "WorkingDirectory")
    assert каталог and Path(каталог).is_dir(), каталог
    # Проход только читает публичные страницы, поэтому прав root ему не нужно.
    assert _значение(текст, "User") == "claude"
    assert _значение(текст, "Type") == "oneshot"


@pytest.mark.parametrize("имя", sorted(ПРОХОДЫ))
def test_нет_специферов_новее_целевого_systemd(имя):
    for файл in (ХОСТ / f"{имя}.service", ХОСТ / f"{имя}.timer"):
        текст = файл.read_text(encoding="utf-8")
        for строка in текст.splitlines():
            голая = строка.strip()
            if голая.startswith("#") or "=" not in голая:
                continue
            for специфер, версия in СПЕЦИФЕРЫ_НОВЕЕ_ЦЕЛИ.items():
                assert специфер not in голая, (
                    f"{файл.name}: {специфер} введён в systemd {версия},"
                    f" на целевом хосте 249 он останется literal-ом")


@pytest.mark.parametrize("имя", sorted(ПРОХОДЫ))
def test_таймер_переживает_выключенный_узел(имя):
    текст = (ХОСТ / f"{имя}.timer").read_text(encoding="utf-8")
    assert _значение(текст, "OnCalendar"), "у таймера нет расписания"
    # Без Persistent пропущенный запуск теряется молча, и «мониторинг» снова
    # становится «по случаю» — ровно то, против чего эти проходы написаны.
    assert _значение(текст, "Persistent") == "true"


def test_расписания_проходов_не_совпадают():
    """Два прохода опрашивают одни витрины; одновременный запуск их замедлит."""
    времена = {}
    for имя in ПРОХОДЫ:
        текст = (ХОСТ / f"{имя}.timer").read_text(encoding="utf-8")
        времена[имя] = _значение(текст, "OnCalendar")
    assert len(set(времена.values())) == len(времена), времена
