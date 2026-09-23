"""Где исполнитель ищет рабочую копию репозитория сайта.

Этот дефект стоил первой настоящей заявки на выпуск. Корневая копия пакета
лежит в /usr/local/lib/site-factory-cell, репозитории сайтов — в рабочем
каталоге фабрики, а основание для относительного `repo.path` выводилось из
места установки. Установленный исполнитель искал `tools/build_release.py`
рядом с собой, не находил и отвергал выпуск. Снаружи это выглядело как
работающая установка: юнит стоит, таймер идёт, очередь разбирается.

Проверяется поведение в обеих раскладках сразу: репозиторий рядом (рабочий
каталог) и репозиторий в стороне (установленная копия).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(КОРЕНЬ))

from factory.cell import registry  # noqa: E402


def _ячейка(путь: str) -> registry.Cell:
    return registry.Cell(
        site_id="zona-01", domain="zonafilm.space", aliases=(),
        repo={"kind": "remote", "path": путь}, template={}, pins={},
        deploy_target={}, publisher={}, data={})


def test_относительный_путь_разрешается_от_записанного_основания(tmp_path, monkeypatch):
    репо = tmp_path / "var" / "site-repos" / "zonafilm-space"
    (репо / "tools").mkdir(parents=True)
    monkeypatch.setenv(registry.СРЕДА_РЕПОЗИТОРИЕВ, str(tmp_path))
    assert _ячейка("var/site-repos/zonafilm-space").repo_path == репо.resolve()


def test_основание_берётся_из_записи_установщика(tmp_path, monkeypatch):
    """Ровно тот случай, что отказал: пакет в одном месте, репозитории в другом."""
    установка = tmp_path / "usr-local-lib"
    установка.mkdir()
    рабочий = tmp_path / "wt"
    (рабочий / "var" / "site-repos" / "zonafilm-space").mkdir(parents=True)
    (установка / registry.ФАЙЛ_УСТАНОВКИ).write_text(
        json.dumps({"site_repos_root": str(рабочий)}), encoding="utf-8")

    monkeypatch.delenv(registry.СРЕДА_РЕПОЗИТОРИЕВ, raising=False)
    monkeypatch.setattr(registry.PATHS, "root", установка)
    assert registry.корень_репозиториев() == рабочий.resolve()
    assert _ячейка("var/site-repos/zonafilm-space").repo_path == (
        рабочий / "var" / "site-repos" / "zonafilm-space").resolve()


def test_без_записи_основание_это_корень_пакета(tmp_path, monkeypatch):
    monkeypatch.delenv(registry.СРЕДА_РЕПОЗИТОРИЕВ, raising=False)
    monkeypatch.setattr(registry.PATHS, "root", tmp_path)
    assert registry.корень_репозиториев() == tmp_path.resolve()


def test_путь_за_пределы_основания_отвергается(tmp_path, monkeypatch):
    """Реестр — файл; запись `../../etc` в нём не должна уводить наружу."""
    monkeypatch.setenv(registry.СРЕДА_РЕПОЗИТОРИЕВ, str(tmp_path / "base"))
    with pytest.raises(registry.RegistryError, match="за пределы"):
        assert _ячейка("../../etc").repo_path


def test_абсолютный_путь_остаётся_собой(tmp_path, monkeypatch):
    monkeypatch.setenv(registry.СРЕДА_РЕПОЗИТОРИЕВ, str(tmp_path))
    assert _ячейка("/srv/repos/zona").repo_path == Path("/srv/repos/zona")


@pytest.mark.parametrize("модуль,функция", [
    ("factory/cell/executor.py", "активировать"),
    ("factory/cell/trigger.py", "не_откат"),
    ("factory/cell/admin_exec.py", "план"),
    ("factory/cell/delivery.py", "_конфиг_ячейки"),
])
def test_никто_не_выводит_путь_сам(модуль, функция):
    """Четыре вызывающих выводили путь по-разному, и двое — неверно.

    Дубль такого вывода и есть дефект: он всегда расходится не там, где его
    заметят. Основание должно остаться одно.
    """
    текст = (КОРЕНЬ / модуль).read_text(encoding="utf-8")
    assert функция in текст
    assert '(cell.repo or {}).get("path")' not in текст, (
        f"{модуль}: путь репозитория выводится в обход registry.repo_path")
