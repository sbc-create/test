"""Выпуск службы: опись, откат и ПОЛНОТА состава.

MOD-198. Опасность здесь не в копировании, а в неполном составе: выпуск
устанавливается, служба запускается и падает на первом же импорте — либо, что
хуже, работает иначе, чем на рабочей копии. Поэтому проверяется замыкание
состава, запись незакоммиченных файлов и обратимость.

Каждая проверка ниже закрепляет ошибку, которая была сделана на первой же
службе: пакетный `__init__.py` не входил в состав, его собственные импорты —
тоже, а интерпретатор не считался зависимостью.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import subprocess

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_сп = importlib.util.spec_from_file_location(
    "install_service_release", КОРЕНЬ / "automation" / "local" / "install-service-release.py")
инс = importlib.util.module_from_spec(_сп)
_сп.loader.exec_module(инс)


def _дерево(tmp_path: pathlib.Path) -> pathlib.Path:
    """Крошечное дерево с пакетом, чей __init__ тянет соседний модуль."""
    д = tmp_path / "wt-проба"
    (д / "pkg" / "sub").mkdir(parents=True)
    (д / "pkg" / "__init__.py").write_text("from pkg.нужный import ЧТО\n", encoding="utf-8")
    (д / "pkg" / "нужный.py").write_text("ЧТО = 1\n", encoding="utf-8")
    (д / "pkg" / "sub" / "__init__.py").write_text("", encoding="utf-8")
    (д / "pkg" / "sub" / "вход.py").write_text("import json\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=д, check=True)
    subprocess.run(["git", "add", "-A"], cwd=д, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                    "commit", "-qm", "первый"], cwd=д, check=True)
    return д


def _состав(д: pathlib.Path, грязные: list[str] | None = None) -> dict:
    return {
        "служба": "проба.service",
        "дерево": д,
        "файлы": ["pkg/__init__.py", "pkg/нужный.py", "pkg/sub/__init__.py",
                  "pkg/sub/вход.py"],
        "грязные": грязные or [],
        "разбор": {"точка_входа": "pkg/sub/вход.py",
                   "юнит": {"ExecStart": "/usr/bin/python3 -m pkg.sub.вход"},
                   "данные": ["/var/lib/проба"],
                   "состояние_дерева": {"ветка": "main", "голова": "0000000",
                                        "незакоммичено_всего": len(грязные or [])}},
    }


def test_опись_несёт_коммит_суммы_и_пути_данных(tmp_path):
    д = _дерево(tmp_path)
    корень = tmp_path / "выпуски"
    assert инс.установить(_состав(д), корень) == 0
    опись = json.loads((корень / "проба.service" / "current" / инс.ОПИСЬ)
                       .read_text(encoding="utf-8"))
    assert len(опись["файлы"]) == 4 and all(len(с) == 64 for с in опись["файлы"].values())
    assert опись["коммит"] and опись["ветка"]
    assert опись["пути_данных"] == ["/var/lib/проба"]
    assert "интерпретатор" in опись


def test_незакоммиченные_файлы_названы_в_описи(tmp_path):
    """Перенести их молча — значит зафиксировать то, чего нет в истории."""
    д = _дерево(tmp_path)
    (д / "pkg" / "нужный.py").write_text("ЧТО = 2\n", encoding="utf-8")
    корень = tmp_path / "выпуски"
    assert инс.установить(_состав(д, ["pkg/нужный.py"]), корень) == 0
    опись = json.loads((корень / "проба.service" / "current" / инс.ОПИСЬ)
                       .read_text(encoding="utf-8"))
    assert опись["файлы_вне_коммита"] == ["pkg/нужный.py"]


def test_сверка_ловит_подмену(tmp_path):
    д = _дерево(tmp_path)
    корень = tmp_path / "выпуски"
    инс.установить(_состав(д), корень)
    assert инс.сверить("проба.service", корень) == 0
    цель = (корень / "проба.service" / "current").resolve() / "pkg" / "нужный.py"
    цель.write_text("ЧТО = 999\n", encoding="utf-8")
    assert инс.сверить("проба.service", корень) == 1


def test_откат_переключает_ссылку_в_обе_стороны(tmp_path):
    д = _дерево(tmp_path)
    корень = tmp_path / "выпуски"
    инс.установить(_состав(д), корень)
    первый = (корень / "проба.service" / "current").resolve().name
    import time

    time.sleep(1.1)   # метка выпуска — по времени с точностью до секунды
    инс.установить(_состав(д), корень)
    второй = (корень / "проба.service" / "current").resolve().name
    assert первый != второй
    assert инс.откатить("проба.service", корень) == 0
    assert (корень / "проба.service" / "current").resolve().name == первый
    assert инс.откатить("проба.service", корень) == 0
    assert (корень / "проба.service" / "current").resolve().name == второй


def test_откат_без_прежнего_выпуска_отказывает(tmp_path):
    д = _дерево(tmp_path)
    корень = tmp_path / "выпуски"
    инс.установить(_состав(д), корень)
    assert инс.откатить("проба.service", корень) == 1


def test_отсутствие_файла_в_источнике_отменяет_установку(tmp_path):
    д = _дерево(tmp_path)
    св = _состав(д)
    св["файлы"].append("pkg/нет-такого.py")
    assert инс.установить(св, tmp_path / "выпуски") == 1


def test_первый_выпуск_службы_просмотра_проверен_живым_ответом():
    """Опись установленного выпуска существует и сходится.

    Проверка смотрит на РЕЗУЛЬТАТ установки, сделанной 26.10: 11 файлов,
    ни одного вне коммита. Числа измеренные; если выпуск переустановят, они
    поменяются вместе с описью, и это нормально — упасть проверка должна
    тогда, когда опись и файлы разойдутся.
    """
    корень = pathlib.Path("/srv/site-factory/services")
    if not (корень / "seo-report-viewer.service" / "current").is_symlink():
        pytest.skip("выпуск службы просмотра на этой машине не разложен")
    assert инс.сверить("seo-report-viewer.service", корень) == 0


def test_сверка_находит_недостающий_импорт(tmp_path):
    """Выпуск, целый по суммам, но неполный по коду, должен валить сверку.

    Повод измерен 26.10 на двух службах из трёх: community-ratings-monitor
    был установлен без factory/community/metrics_store.py, а
    seo-engine-topvisor-inventory — 17 файлами из 149, и оба давали
    «расхождений 0». Запуск ловил это, сверка — нет.
    """
    дерево = tmp_path / "дерево"
    (дерево / "pkg").mkdir(parents=True)
    (дерево / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (дерево / "pkg" / "store.py").write_text("ЗНАЧЕНИЕ = 1\n", encoding="utf-8")
    выпуск = tmp_path / "releases" / "20261026T000000Z-abcdef"
    (выпуск / "pkg").mkdir(parents=True)
    (выпуск / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (выпуск / "pkg" / "main.py").write_text("from pkg import store\n", encoding="utf-8")
    # Без дерева-источника случай неразрешим и молчит — это и было дырой.
    assert инс.самодостаточен(выпуск) == []
    нет = инс.самодостаточен(выпуск, дерево)
    assert нет == ["pkg/main.py → pkg.store"], нет
    (выпуск / "pkg" / "store.py").write_text("ЗНАЧЕНИЕ = 1\n", encoding="utf-8")
    assert инс.самодостаточен(выпуск, дерево) == []


def test_сторонний_пакет_не_считается_недостающим(tmp_path):
    """Сторонние зависимости живут в venv: их отсутствие — другой разговор."""
    выпуск = tmp_path / "releases" / "20261026T000000Z-abcdef"
    (выпуск / "pkg").mkdir(parents=True)
    (выпуск / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (выпуск / "pkg" / "main.py").write_text(
        "import sqlalchemy\nfrom fastapi import FastAPI\n", encoding="utf-8")
    assert инс.самодостаточен(выпуск) == []


# --- Проверка drop-in до переключения (предложение линии SEO) ----------------

def _dropin(tmp_path, текст: str):
    ф = tmp_path / "release.conf"
    ф.write_text(текст, encoding="utf-8")
    return ф


def test_корень_состояния_обязан_быть_префиксом_путей_записи(tmp_path):
    """systemd НЕ раскрывает переменные окружения в ReadWritePaths и ExecStartPre.

    Поэтому Environment=SEO_STATE_ROOT на них не влияет, и при переносе
    состояния каталог надо перечислить ещё и там. Без этой проверки
    расхождение поймается не до переключения, а первой записью: песочница
    запретит её, и служба упадёт уже после.
    """
    ф = _dropin(tmp_path, "[Service]\n"
                "Environment=SEO_STATE_ROOT=/srv/состояние\n"
                "ReadWritePaths=/home/копия/var/seo-regular\n")
    код, строки = инс.проверить_dropin(ф)
    assert код == 1
    assert any("РАСХОЖДЕНИЕ" in с and "ReadWritePaths" in с for с in строки)


def test_согласованный_dropin_проходит(tmp_path):
    ф = _dropin(tmp_path, "[Service]\n"
                "Environment=SEO_STATE_ROOT=/srv/состояние\n"
                "ReadWritePaths=/srv/состояние/var/seo-regular\n"
                "ExecStartPre=/usr/bin/install -d /srv/состояние/var/analytics\n"
                "ExecStart=/usr/bin/python3 -m служба --out /srv/состояние/var/о.json\n")
    код, _строки = инс.проверить_dropin(ф)
    assert код == 0


def test_исполняемый_файл_путём_записи_не_считается(tmp_path):
    """`/usr/bin/install -d …`: первое слово — бинарь, а не место записи."""
    ф = _dropin(tmp_path, "[Service]\n"
                "Environment=SEO_STATE_ROOT=/srv/состояние\n"
                "ExecStartPre=/usr/bin/install -d /srv/состояние/var/x\n")
    код, строки = инс.проверить_dropin(ф)
    assert код == 0, строки
    assert not any("/usr/bin/install" in с for с in строки)


def test_без_корня_состояния_проверять_нечего(tmp_path):
    """Третий исход: состояние осталось в рабочей копии — это не отказ."""
    ф = _dropin(tmp_path, "[Service]\nWorkingDirectory=/srv/выпуск\n")
    код, строки = инс.проверить_dropin(ф)
    assert код == 2
    assert any("проверять нечего" in с for с in строки)
