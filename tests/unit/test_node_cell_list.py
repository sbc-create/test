"""Состав витрин узла берётся из реестра, а не перечислением в юните.

Суточная доставка каталога объявляла восемь витрин строкой в `ExecStart`, и
пять новых ячеек ТОГО ЖЕ узла не получали бы обновлений каталога вовсе.
Отсутствие имени в юните при этом выглядит точно так же, как «доставка
настроена» — это класс 47 (`docs/RECURRING_FAILURES.md`).

Проверяется и инструмент, и то, что юниты им пользуются: иначе исправленный
инструмент лежал бы рядом с прежним перечнем.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import pathlib

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_сп = importlib.util.spec_from_file_location(
    "node_cell_list", КОРЕНЬ / "automation" / "local" / "node-cell-list.py")
инс = importlib.util.module_from_spec(_сп)
_сп.loader.exec_module(инс)


def _реестр(tmp_path: pathlib.Path, ячейки: list[dict]) -> pathlib.Path:
    путь = tmp_path / "site-cells.json"
    путь.write_text(json.dumps({"schema_version": "1.0", "cells": ячейки},
                               ensure_ascii=False), encoding="utf-8")
    return путь


def _я(site_id: str, ref: str | None, выведен: bool = False) -> dict:
    з = {"site_id": site_id, "domain": f"{site_id}.test", "status": "live",
         "repo": {}, "template": {}, "deploy_target": {"ref": ref} if ref else {}}
    if выведен:
        з["withdrawal"] = {"withdrawn": True, "at": "2026-10-25",
                           "reason": "решение владельца", "authority": "владелец"}
    return з


def test_берутся_только_витрины_своего_узла(tmp_path):
    путь = _реестр(tmp_path, [_я("a-1", "узел-1"), _я("b-1", "узел-2"),
                              _я("c-1", "узел-1"), _я("d-1", None)])
    assert инс.витрины_узла("узел-1", путь) == ["a-1", "c-1"]


def test_выведенная_из_работы_ячейка_исключается_признаком(tmp_path):
    """Решение владельца о выводе не должно требовать правки ещё и здесь."""
    путь = _реестр(tmp_path, [_я("a-1", "узел-1"), _я("b-1", "узел-1", выведен=True)])
    assert инс.витрины_узла("узел-1", путь) == ["a-1"]


def test_пустой_состав_не_выдаётся_за_успех(tmp_path):
    путь = _реестр(tmp_path, [_я("a-1", "узел-2")])
    assert инс.витрины_узла("узел-1", путь) == []


def test_боевой_реестр_даёт_все_тринадцать_витрин_узла():
    """Числа измеренные: восемь партии K2 плюс пять новых lordserials."""
    имена = инс.витрины_узла("k2-zomro-01")
    assert имена == [f"lords-{n}" for n in range(10, 23)], имена


@pytest.mark.parametrize("юнит", ["k2-catalog-deliver.service",
                                  "k2-catalog-deliver.user.service"])
def test_юниты_доставки_не_перечисляют_витрины_строкой(юнит):
    т = (КОРЕНЬ / "automation" / "host" / юнит).read_text(encoding="utf-8")
    строки = [с for с in т.splitlines() if с.startswith("ExecStart=")]
    assert строки, f"{юнит}: нет ExecStart"
    команда = строки[0]
    assert "--node k2-zomro-01" in команда, команда
    assert "lords-1" not in команда, (
        f"{юнит}: витрины снова перечислены строкой — новая ячейка узла "
        "останется без обновлений каталога, и это будет незаметно")


def test_сборщик_издателя_берёт_состав_из_того_же_модуля():
    """Четвёртое место одного класса: перечень витрин в сборщике издателя.

    Он вставляет записи в таблицу публикации живого издателя. Пока перечень был
    литералом `lords-10…lords-17`, снимок для пяти новых ячеек того же узла
    никто не пересобирал бы — и ошибок при этом нет, что и делает класс
    опасным.
    """
    сп = importlib.util.spec_from_file_location(
        "make_k2_publisher", КОРЕНЬ / "automation" / "local" / "make-k2-publisher.py")
    м = importlib.util.module_from_spec(сп)
    сп.loader.exec_module(м)
    текст = (КОРЕНЬ / "automation" / "local" / "make-k2-publisher.py").read_text(encoding="utf-8")
    assert "range(10, 18)" not in текст, "перечень витрин снова задан литералом"
    assert м.витрины_узла("k2-zomro-01") == tuple(f"lords-{n}" for n in range(10, 23))


@pytest.mark.parametrize("файл,имя", [
    ("dns-cutover-plan.py", "план перевода DNS"),
    ("k2-bundle-freshness.py", "свежесть бандлов"),
    ("build-preview-gallery.py", "галерея превью"),
    ("make-k2-publisher.py", "сборщик издателя"),
    ("k2-publisher-id-check.py", "сверка номеров издателя"),
    ("k2-posterless-works.py", "работы без постеров"),
    ("eight-sites-report.py", "отчёт по витринам узла"),
    ("k2-poster-inventory.py", "опись постеров"),
    ("k2-intake-composition.py", "состав поступлений"),
])
def test_состав_узла_нигде_не_перечислен_литералом(файл, имя):
    """Признак класса 47 — перечень состава рядом с реестром, а не слово «восемь».

    Проверяется по месту, где состав ПЕРЕЧИСЛЯЕТСЯ: пока литерал совпадал с
    реестром, молчали и инструмент, и всякая проверка над ним.
    """
    путь = КОРЕНЬ / "automation" / "local" / файл
    т = путь.read_text(encoding="utf-8")
    # Разбор КОДА, а не поиск по тексту: упоминание прежнего литерала в
    # объяснении — это память о дефекте, и её терять не надо. Первая редакция
    # этой проверки искала подстроку и падала на собственных же комментариях.
    дерево = ast.parse(т)
    литералы = [у for у in ast.walk(дерево)
                if isinstance(у, ast.Call) and getattr(у.func, "id", "") == "range"
                and [getattr(а, "value", None) for а in у.args] == [10, 18]]
    assert not литералы, f"{имя}: состав снова задан литералом range(10, 18)"
    assert "node-cell-list.py" in т, (
        f"{имя}: состав берётся не из общего модуля — значит где-то ещё")
