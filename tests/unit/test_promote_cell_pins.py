"""Продвижение закреплённой версии шаблона не пересоздаёт проект.

Повод измерен 26.10. Штатный генератор `factory cell newsite` — создатель, и
при `--force` он делает `shutil.rmtree(куда)`. После такого «обновления» у пяти
проектов исчез их собственный репозиторий вместе с первым коммитом, и три
штатные проверки проекта снова ответили отказом. У живого сайта тем же
движением ушли бы `config/player.json` с publisher_id (его кладут вне Git),
локальная история и всё, что положено рядом вне состава шаблона.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import pathlib

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ИНСТРУМЕНТ = КОРЕНЬ / "automation" / "local" / "promote-cell-pins.py"


@pytest.fixture()
def модуль():
    сп = importlib.util.spec_from_file_location("promote_cell_pins", ИНСТРУМЕНТ)
    м = importlib.util.module_from_spec(сп)
    сп.loader.exec_module(м)
    return м


def _стенд(tmp_path, *, копия: str, канон: str, repo_path="automation/host/r.py"):
    """Фабрика и проект ячейки на один файл состава."""
    корень = tmp_path / "factory"
    (корень / "automation" / "host").mkdir(parents=True)
    (корень / "automation" / "host" / "r.py").write_text(канон, encoding="utf-8")
    проект = корень / "var" / "new-sites" / "c-1"
    (проект / "src").mkdir(parents=True)
    (проект / "src" / "r.py").write_text(копия, encoding="utf-8")
    (проект / "pins.lock.json").write_text(json.dumps({
        "schema_version": 1, "site_id": "c-1",
        "pins": {"source_commit": "0" * 40, "source_dirty": False,
                 "build_id": "template-000000000000", "entrypoint": "r.py"},
        # Сумма в замке — та, что была у ИСТОЧНИКА на момент закрепления, то
        # есть сумма копии проекта. Пустая строка здесь давала бы «обновить»
        # даже совпадающему файлу, и проверка проверяла бы не то.
        "files": {"r.py": {"sha256": hashlib.sha256(копия.encode()).hexdigest(),
                           "bytes": len(копия.encode()),
                           "verified_against": "git", "repo_path": repo_path}},
    }, ensure_ascii=False), encoding="utf-8")
    реестр = корень / "config" / "site-cells.json"
    реестр.parent.mkdir(parents=True)
    реестр.write_text(json.dumps({"cells": [
        {"site_id": "c-1", "domain": "proba.invalid",
         "repo": {"kind": "local", "path": "var/new-sites/c-1"}}]},
        ensure_ascii=False), encoding="utf-8")
    return корень, проект, реестр


def test_совпадающий_файл_обновлять_не_надо(модуль, tmp_path):
    текст = "def общая():\n    return 1\n"
    корень, _, реестр = _стенд(tmp_path, копия=текст, канон=текст)
    итог = модуль.разбор("c-1", корень=корень, реестр=реестр)
    assert итог["исход"] == "совпадает", итог


def test_устаревший_файл_назначается_к_обновлению(модуль, tmp_path):
    корень, _, реестр = _стенд(tmp_path, копия="def общая():\n    return 1\n",
                               канон="def общая():\n    return 2\n")
    итог = модуль.разбор("c-1", корень=корень, реестр=реестр)
    assert итог["исход"] == "обновить"
    assert итог["файлов к обновлению"] == ["r.py"]


def test_отказ_когда_копия_несёт_своё_имя(модуль, tmp_path):
    """Главное свойство: продвижение не имеет права стереть чужую работу."""
    корень, _, реестр = _стенд(
        tmp_path,
        копия="def общая():\n    return 1\n\n\ndef своя():\n    return 'адрес'\n",
        канон="def общая():\n    return 2\n")
    итог = модуль.разбор("c-1", корень=корень, реестр=реестр)
    assert итог["исход"] == "ОТКАЗ"
    assert итог["потери"] == {"r.py": ["своя"]}


def test_имя_в_комментарии_потерей_не_считается(модуль, tmp_path):
    """Иначе отказ был бы ложным на файле, который имя только упоминает."""
    корень, _, реестр = _стенд(
        tmp_path,
        копия="# своя() здесь только упомянута\ndef общая():\n    return 1\n",
        канон="def общая():\n    return 2\n")
    итог = модуль.разбор("c-1", корень=корень, реестр=реестр)
    assert итог["исход"] == "обновить", итог


def test_путь_вне_фабрики_источником_не_считается(модуль, tmp_path):
    """У yummy-07 это каталог живой площадки: правда — репозиторий, /srv её получает."""
    корень, _, реестр = _стенд(tmp_path, копия="x = 1\n", канон="x = 2\n",
                               repo_path="/srv/lords/.frontend/r.py")
    итог = модуль.разбор("c-1", корень=корень, реестр=реестр)
    assert итог["исход"] == "другой источник", итог


def test_пустой_путь_это_отдельный_выпуск(модуль, tmp_path):
    """Канонический модуль сообщества приезжает своим выпуском, а не копией."""
    корень, _, реестр = _стенд(tmp_path, копия="x = 1\n", канон="x = 2\n",
                               repo_path="")
    итог = модуль.разбор("c-1", корень=корень, реестр=реестр)
    assert итог["исход"] == "другой источник", итог


def test_продвижение_не_трогает_ничего_кроме_состава(модуль, tmp_path, monkeypatch):
    """`.git`, config и данные остаются на месте — в этом весь смысл."""
    корень, проект, реестр = _стенд(tmp_path, копия="def общая():\n    return 1\n",
                                    канон="def общая():\n    return 2\n")
    (проект / ".git").mkdir()
    (проект / ".git" / "HEAD").write_text("ref: refs/heads/claude/x\n", encoding="utf-8")
    (проект / "config").mkdir()
    (проект / "config" / "player.json").write_text('{"publisher_id": "12345"}',
                                                   encoding="utf-8")
    monkeypatch.setattr(модуль, "коммит_фабрики", lambda корень=None: ("a" * 40, False))
    итог = модуль.продвинуть("c-1", корень=корень, реестр=реестр)
    assert итог["исход"] == "продвинуто", итог
    assert (проект / "src" / "r.py").read_text(encoding="utf-8") == \
        "def общая():\n    return 2\n"
    assert (проект / ".git" / "HEAD").is_file()
    assert json.loads((проект / "config" / "player.json").read_text(
        encoding="utf-8"))["publisher_id"] == "12345"
    пины = json.loads((проект / "pins.lock.json").read_text(encoding="utf-8"))
    assert пины["pins"]["source_commit"] == "a" * 40
    assert пины["pins"]["build_id"] == "template-aaaaaaaaaaaa"
    assert пины["files"]["r.py"]["bytes"] == len("def общая():\n    return 2\n".encode())


def test_грязное_дерево_фабрики_это_отказ(модуль, tmp_path, monkeypatch):
    """Закрепление назвало бы коммит, которому содержимое не соответствует."""
    корень, _, реестр = _стенд(tmp_path, копия="def общая():\n    return 1\n",
                               канон="def общая():\n    return 2\n")
    monkeypatch.setattr(модуль, "коммит_фабрики", lambda корень=None: ("b" * 40, True))
    итог = модуль.продвинуть("c-1", корень=корень, реестр=реестр)
    assert итог["исход"] == "ОТКАЗ"
    assert "грязное" in итог["почему"]


def test_вердикт_умеет_падать():
    """Инструмент-вердикт без ненулевого выхода в воротах всегда зелёный."""
    текст = ИНСТРУМЕНТ.read_text(encoding="utf-8")
    assert "return 1" in текст
