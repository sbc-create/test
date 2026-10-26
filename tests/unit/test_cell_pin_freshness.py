"""Проекты ячеек обязаны нести ТЕКУЩИЙ рантайм, иначе запуск унесёт прежнее поведение.

Повод измерен 26.10: в каноническом рантайме исправлен общий дефект (MOD-202),
а все пять проектов новой пятёрки остались закреплены на коммите
`137a3152fb20` с рантаймом `21ae3bed93ae…` — редакцией до правки. По паспорту
этого видно не было: там «в работе», а не «закреплён старый шаблон».
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import pathlib

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_сп = importlib.util.spec_from_file_location(
    "cell_pin_freshness", КОРЕНЬ / "automation" / "local" / "cell-pin-freshness.py")
инс = importlib.util.module_from_spec(_сп)
_сп.loader.exec_module(инс)


def _дерево(tmp_path, *, сумма_рантайма: bytes, пин: str | None, копия: bytes | None):
    """Стенд: репозиторий с рантаймом, реестр и проект ячейки."""
    (tmp_path / "automation" / "host").mkdir(parents=True)
    (tmp_path / "automation" / "host" / инс.РАНТАЙМ).write_bytes(сумма_рантайма)
    проект = tmp_path / "var" / "new-sites" / "проба"
    (проект / "src").mkdir(parents=True)
    if копия is not None:
        (проект / "src" / инс.РАНТАЙМ).write_bytes(копия)
    if пин is not None:
        # `repo_path` обязателен: по нему инструмент решает, ВЕДЁТ ли рантайм
        # ячейки эта фабрика. Стенд без него описывал бы ячейку чужой линии, и
        # проверки свежести измеряли бы не тот исход.
        (проект / "pins.lock.json").write_text(json.dumps(
            {"files": {инс.РАНТАЙМ: {
                "sha256": пин,
                "repo_path": f"automation/host/{инс.РАНТАЙМ}"}}}), encoding="utf-8")
    реестр = tmp_path / "site-cells.json"
    реестр.write_text(json.dumps({"cells": [
        {"site_id": "проба", "domain": "проба.ru",
         "repo": {"path": "var/new-sites/проба"}}]}, ensure_ascii=False), encoding="utf-8")
    return реестр


def test_совпадение_сумм_это_свежий_пин(tmp_path):
    байты = b"runtime v2\n"
    сумма = hashlib.sha256(байты).hexdigest()
    реестр = _дерево(tmp_path, сумма_рантайма=байты, пин=сумма, копия=байты)
    итог = инс.свежесть(реестр, tmp_path)
    assert [з["исход"] for з in итог] == [инс.СОВПАДАЕТ]


def test_старый_пин_называется_устаревшим(tmp_path):
    """Ровно случай пятёрки: проект несёт прежнюю редакцию рантайма."""
    старые, новые = b"runtime v1\n", b"runtime v2\n"
    реестр = _дерево(tmp_path, сумма_рантайма=новые,
                     пин=hashlib.sha256(старые).hexdigest(), копия=старые)
    итог = инс.свежесть(реестр, tmp_path)
    assert итог[0]["исход"] == инс.УСТАРЕЛ
    assert "репозиторий" in итог[0]["почему"]


def test_расхождение_пина_и_копии_тоже_устарело(tmp_path):
    """Копия свежая, а пин старый — выпуск описал бы не то, что лежит."""
    старые, новые = b"runtime v1\n", b"runtime v2\n"
    реестр = _дерево(tmp_path, сумма_рантайма=новые,
                     пин=hashlib.sha256(старые).hexdigest(), копия=новые)
    assert инс.свежесть(реестр, tmp_path)[0]["исход"] == инс.УСТАРЕЛ


def test_отсутствие_проекта_это_не_устаревание(tmp_path):
    """Третий исход обязателен: ячейка объявлена, но проект не собирался."""
    байты = b"runtime v2\n"
    реестр = _дерево(tmp_path, сумма_рантайма=байты, пин=None, копия=None)
    итог = инс.свежесть(реестр, tmp_path)
    assert итог[0]["исход"] == инс.НЕТ_ПРОЕКТА


def test_выведенная_ячейка_не_проверяется(tmp_path):
    """Выведенные домены в продвижение не возвращаются — и в сверку не идут."""
    байты = b"runtime v2\n"
    реестр = _дерево(tmp_path, сумма_рантайма=байты, пин="x", копия=байты)
    данные = json.loads(реестр.read_text(encoding="utf-8"))
    данные["cells"][0]["withdrawal"] = {"withdrawn": True}
    реестр.write_text(json.dumps(данные, ensure_ascii=False), encoding="utf-8")
    assert инс.свежесть(реестр, tmp_path) == []


def test_живая_сеть_разобрана_без_ошибок():
    """Мерка работает на настоящем реестре и называет каждую ячейку."""
    записи = инс.свежесть()
    assert записи, "ни одной ячейки не разобрано"
    исходы = {з["исход"] for з in записи}
    assert исходы <= {инс.СОВПАДАЕТ, инс.УСТАРЕЛ, инс.НЕТ_ПРОЕКТА,
                      инс.ДРУГОЙ_ИСТОЧНИК}


# --- Чужой источник устаревшим не считается ----------------------------------

def test_рантайм_не_из_фабрики_это_другой_источник(tmp_path):
    """Измерено 26.10: счёт «21 потребитель шаблона» был завышен.

    У animedia-01, zona-01 и zona-03 файл `lords-frontend.py` закреплён с
    пустым `repo_path` — он приезжает отдельным выпуском своей линии, а не из
    этой фабрики. Сверять его с каноном значит объявлять устаревшим чужой
    файл: у zona-01 в нём 105 своих имён, то есть отдельная линия оформления
    целиком.
    """
    import json

    модуль = инс
    корень = tmp_path / "factory"
    (корень / "automation" / "host").mkdir(parents=True)
    (корень / "automation" / "host" / "lords-frontend.py").write_text(
        "x = 1\n", encoding="utf-8")
    проект = корень / "var" / "site-repos" / "чужой"
    (проект / "src").mkdir(parents=True)
    (проект / "src" / "lords-frontend.py").write_text("x = 2\n", encoding="utf-8")
    (проект / "pins.lock.json").write_text(json.dumps({
        "files": {"lords-frontend.py": {"sha256": "z" * 64, "repo_path": ""}}},
        ensure_ascii=False), encoding="utf-8")
    реестр = корень / "config" / "site-cells.json"
    реестр.parent.mkdir(parents=True)
    реестр.write_text(json.dumps({"cells": [
        {"site_id": "чужой-01", "domain": "proba.invalid",
         "repo": {"kind": "local", "path": "var/site-repos/чужой"}}]},
        ensure_ascii=False), encoding="utf-8")
    записи = модуль.свежесть(реестр, корень)
    assert [з["исход"] for з in записи] == [модуль.ДРУГОЙ_ИСТОЧНИК], записи


def test_рантайм_из_фабрики_по_прежнему_сверяется(tmp_path):
    """Отрицательный контроль: исход «другой источник» не должен съесть всё."""
    import hashlib
    import json

    модуль = инс
    корень = tmp_path / "factory"
    (корень / "automation" / "host").mkdir(parents=True)
    (корень / "automation" / "host" / "lords-frontend.py").write_text(
        "x = 1\n", encoding="utf-8")
    проект = корень / "var" / "new-sites" / "свой"
    (проект / "src").mkdir(parents=True)
    (проект / "src" / "lords-frontend.py").write_text("x = 2\n", encoding="utf-8")
    (проект / "pins.lock.json").write_text(json.dumps({
        "files": {"lords-frontend.py": {
            "sha256": hashlib.sha256(b"x = 2\n").hexdigest(),
            "repo_path": "automation/host/lords-frontend.py"}}},
        ensure_ascii=False), encoding="utf-8")
    реестр = корень / "config" / "site-cells.json"
    реестр.parent.mkdir(parents=True)
    реестр.write_text(json.dumps({"cells": [
        {"site_id": "свой-01", "domain": "proba.invalid",
         "repo": {"kind": "local", "path": "var/new-sites/свой"}}]},
        ensure_ascii=False), encoding="utf-8")
    записи = модуль.свежесть(реестр, корень)
    assert [з["исход"] for з in записи] == [модуль.УСТАРЕЛ], записи
