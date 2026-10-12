"""Три места `publisher_id` по D177: когда учёт можно заполнить, а когда нельзя.

Инструмент пишет в паспорт сайта, поэтому главное здесь — не «умеет
заполнять», а границы: заполняется ТОЛЬКО учёт и ТОЛЬКО там, где объявление в
пакете и живая страница согласны между собой. Два независимых источника против
одного — это разница между записью по знанию и записью по догадке, и она
закреплена тестами, а не намерением.

Значение `publisher_id` публично (витрина отдаёт его атрибутом
`data-publisher-id`), но в вывод оно всё равно не попадает: отчёт о сверке не
место для значений.

Сеть не нужна: живое значение подставляется вместо `живое`.
"""
from __future__ import annotations

import importlib.util
import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
ИСТОЧНИК = КОРЕНЬ / "automation" / "local" / "publisher-id-reconcile.py"


def _модуль():
    спец = importlib.util.spec_from_file_location("publisher", ИСТОЧНИК)
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


@pytest.fixture(scope="module")
def м():
    return _модуль()


def стенд(tmp_path: Path, ячейки: list[dict], пакеты: dict[str, str]) -> Path:
    """Реестр и пакеты сайтов. Ячейка: site_id, domain, учёт. Пакет: объявление."""
    реестр = tmp_path / "реестр.json"
    реестр.write_text(json.dumps({"schema_version": 1, "cells": [
        {"site_id": я["site_id"], "domain": я["domain"],
         "repo": {"path": f"var/site-repos/repo-{я['site_id']}"},
         "publisher": ({"publisher_id": я["учёт"]} if я.get("учёт") else {})}
        for я in ячейки]}, ensure_ascii=False), encoding="utf-8")
    for site_id, объявлено in пакеты.items():
        каталог = tmp_path / "cells" / f"repo-{site_id}" / "config"
        каталог.mkdir(parents=True, exist_ok=True)
        (каталог / "site.json").write_text(
            json.dumps({"site_id": site_id,
                        "publisher_id_expected": объявлено} if объявлено
                       else {"site_id": site_id}, ensure_ascii=False),
            encoding="utf-8")
    return реестр


def прогон(м, monkeypatch, tmp_path: Path, реестр: Path, живые: dict[str, str],
           *, писать: bool = False):
    monkeypatch.setattr(м, "КОРЕНЬ_ЯЧЕЕК", tmp_path / "cells")
    monkeypatch.setattr(м, "живое", lambda домен: живые.get(домен, ""))
    арг = ["--registry", str(реестр)]
    if писать:
        арг.append("--confirm-writes")
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        код = м.главное(арг)
    return код, буфер.getvalue()


def учёт(реестр: Path) -> dict[str, str | None]:
    данные = json.loads(реестр.read_text(encoding="utf-8"))
    return {я["site_id"]: (я.get("publisher") or {}).get("publisher_id")
            for я in данные["cells"]}


def test_учёт_заполняется_по_двум_согласным_источникам(м, monkeypatch, tmp_path):
    реестр = стенд(tmp_path,
                   [{"site_id": "a", "domain": "a.invalid", "учёт": ""}],
                   {"a": "48217"})
    код, вывод = прогон(м, monkeypatch, tmp_path, реестр, {"a.invalid": "48217"},
                        писать=True)
    assert код == 0, вывод
    assert учёт(реестр) == {"a": "48217"}


def test_без_объявления_учёт_не_выдумывается(м, monkeypatch, tmp_path):
    """Одного источника мало: пустое объявление — вопрос к D177, не опечатка."""
    реестр = стенд(tmp_path,
                   [{"site_id": "a", "domain": "a.invalid", "учёт": ""}],
                   {"a": ""})
    код, вывод = прогон(м, monkeypatch, tmp_path, реестр, {"a.invalid": "48217"},
                        писать=True)
    assert учёт(реестр) == {"a": None}
    assert "вопрос о D177" in вывод
    assert "НЕ выдумывается" in вывод
    assert код == 1


def test_расхождение_живого_с_объявлением_это_отказ_без_записи(м, monkeypatch,
                                                               tmp_path):
    реестр = стенд(tmp_path,
                   [{"site_id": "a", "domain": "a.invalid", "учёт": ""}],
                   {"a": "11111"})
    код, вывод = прогон(м, monkeypatch, tmp_path, реестр, {"a.invalid": "48217"},
                        писать=True)
    assert код == 1
    assert "расходится с объявлением" in вывод
    assert учёт(реестр) == {"a": None}, "записал при расхождении источников"


def test_учёт_расходящийся_с_живым_называется(м, monkeypatch, tmp_path):
    реестр = стенд(tmp_path, [
        {"site_id": "a", "domain": "a.invalid", "учёт": "11111"},
        {"site_id": "b", "domain": "b.invalid", "учёт": "48217"}], {"a": ""})
    код, вывод = прогон(м, monkeypatch, tmp_path, реестр,
                        {"a.invalid": "48217", "b.invalid": "48217"})
    assert код == 1
    assert "учёт в реестре расходится с живым" in вывод
    assert "b" in вывод, "не назван владелец значения из учёта"


def test_по_умолчанию_не_пишет(м, monkeypatch, tmp_path):
    реестр = стенд(tmp_path,
                   [{"site_id": "a", "domain": "a.invalid", "учёт": ""}],
                   {"a": "48217"})
    код, вывод = прогон(м, monkeypatch, tmp_path, реестр, {"a.invalid": "48217"})
    assert код == 1
    assert "нужен --confirm-writes" in вывод
    assert учёт(реестр) == {"a": None}


def test_один_идентификатор_на_две_ячейки_это_замечание(м, monkeypatch, tmp_path):
    """`publisher_id` принадлежит КОНКРЕТНОМУ домену (D177) — повод спросить."""
    реестр = стенд(tmp_path, [
        {"site_id": "a", "domain": "a.invalid", "учёт": "48217"},
        {"site_id": "b", "domain": "b.invalid", "учёт": "48217"}],
        {"a": "48217", "b": "48217"})
    код, вывод = прогон(м, monkeypatch, tmp_path, реестр,
                        {"a.invalid": "48217", "b.invalid": "48217"})
    assert код == 0, вывод
    assert "тот же идентификатор в учёте у 2 ячеек" in вывод


def test_все_три_места_согласны_это_проход(м, monkeypatch, tmp_path):
    реестр = стенд(tmp_path,
                   [{"site_id": "a", "domain": "a.invalid", "учёт": "48217"}],
                   {"a": "48217"})
    код, вывод = прогон(м, monkeypatch, tmp_path, реестр, {"a.invalid": "48217"})
    assert код == 0
    assert "все три места согласны" in вывод


def test_карточка_не_ответила_это_не_измерено(м, monkeypatch, tmp_path):
    реестр = стенд(tmp_path,
                   [{"site_id": "a", "domain": "a.invalid", "учёт": ""}],
                   {"a": "48217"})
    код, вывод = прогон(м, monkeypatch, tmp_path, реестр, {}, писать=True)
    assert "не измерено: 1" in вывод
    assert учёт(реестр) == {"a": None}, "записал, ничего не измерив"
    assert код == 0


def test_значения_не_печатаются(м, monkeypatch, tmp_path):
    """Отчёт о сверке — не место для значений, даже публичных."""
    реестр = стенд(tmp_path,
                   [{"site_id": "a", "domain": "a.invalid", "учёт": ""}],
                   {"a": "48217"})
    _код, вывод = прогон(м, monkeypatch, tmp_path, реестр,
                         {"a.invalid": "48217"}, писать=True)
    assert "48217" not in вывод, вывод


def test_в_сеть_не_ходит_с_offline(м, monkeypatch, tmp_path):
    реестр = стенд(tmp_path,
                   [{"site_id": "a", "domain": "a.invalid", "учёт": ""}],
                   {"a": "48217"})
    monkeypatch.setattr(м, "КОРЕНЬ_ЯЧЕЕК", tmp_path / "cells")
    monkeypatch.setattr(м, "живое", lambda домен: pytest.fail(
        "с --offline живое значение не запрашивается"))
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        код = м.главное(["--registry", str(реестр), "--offline"])
    assert код == 0
    assert "не измерено: 1" in буфер.getvalue()


def test_нет_таких_ячеек_это_исход_два(м, monkeypatch, tmp_path):
    реестр = стенд(tmp_path,
                   [{"site_id": "a", "domain": "a.invalid", "учёт": ""}],
                   {"a": "48217"})
    monkeypatch.setattr(м, "КОРЕНЬ_ЯЧЕЕК", tmp_path / "cells")
    assert м.главное(["--registry", str(реестр), "--site", "нет-такой"]) == 2
