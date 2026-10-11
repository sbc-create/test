"""Матрица доменов: источники раздельны, и ни один не выводится из другого.

Повод для инструмента — требование ночного цикла дать таблицу по доменам, не
переписывая цифры из сообщений. Повод для ЭТИХ проверок — дефект, который
первая редакция инструмента внесла молча.

Заголовки и тело читались из одного потока (`curl -D -`) и делились по
`\\r\\n\\r\\n`. При `text=True` переводы строк переводятся, разделитель
исчезает, и тело выходит пустым ВСЕГДА. Режим индексации при этом читался
только из заголовка `X-Robots-Tag`: у Lords и Zona он есть, и столбец выглядел
осмысленным, а у пяти Yummy заголовка нет — там стоял «—», хотя мета говорит
`index, follow`. То есть ошибка чтения выглядела как факт о витрине: «режим не
задан» у пяти production-доменов.

Отсюда свойства, которые проверяются ниже:

* мета робота читается из ТЕЛА, а не только из заголовка;
* расхождение меты и заголовка называется, а не склеивается в одно значение —
  у сети уже был такой случай (D166): приложение отдавало `index, follow`, а
  nginx `noindex`, и ответ противоречил сам себе;
* «тега нет» и «не прочитано» — разные исходы: первое факт о витрине, второе
  о измерении;
* имена из RFC 6761 не измеряются вовсе: их молчание — свойство имени.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
СЦЕНАРИЙ = КОРЕНЬ / "automation" / "local" / "domain-matrix.py"


def _модуль():
    спец = importlib.util.spec_from_file_location("domain_matrix", СЦЕНАРИЙ)
    м = importlib.util.module_from_spec(спец)
    sys.modules["domain_matrix"] = м
    спец.loader.exec_module(м)
    return м


class Ответ:
    """Подставной результат curl: заголовки пишутся в файл, тело в stdout."""

    def __init__(self, заголовки: str, тело: str, код: int = 0):
        self.заголовки = заголовки
        self.тело = тело
        self.код = код

    def __call__(self, аргв, **кв):
        # Там, где инструмент просит писать заголовки в файл, пишем туда.
        if "-D" in аргв:
            путь = Path(аргв[аргв.index("-D") + 1])
            if путь.name != "-":
                путь.write_text(self.заголовки, encoding="utf-8")

        class Итог:
            returncode = self.код
            stdout = self.тело
            stderr = ""

        return Итог()


ЗАГОЛОВКИ = ("HTTP/2 200 \r\n"
             "x-site-factory-build-id: abc123456789-zona-01\r\n")


def test_мета_робота_читается_из_тела(monkeypatch):
    """Главный случай: заголовка нет, мета есть — и она должна попасть в отчёт."""
    м = _модуль()
    monkeypatch.setattr(м.subprocess, "run", Ответ(
        ЗАГОЛОВКИ, '<meta name="robots" content="index, follow"/>'))
    build, режим, код = м.живое("yummyani.site")
    assert build == "abc123456789-zona-01"
    assert режим == "index, follow"
    assert код == "200"


def test_только_заголовок_называется_отдельно(monkeypatch):
    """Если меты нет, а заголовок есть — это другой факт, и он назван."""
    м = _модуль()
    monkeypatch.setattr(м.subprocess, "run", Ответ(
        ЗАГОЛОВКИ + "x-robots-tag: index, follow\r\n", "<html></html>"))
    _b, режим, _к = м.живое("x-proba.ru")
    assert режим == "только заголовок: index, follow"


def test_расхождение_меты_и_заголовка_называется(monkeypatch):
    """D166: ответ, противоречащий сам себе, нельзя сводить к одному значению."""
    м = _модуль()
    monkeypatch.setattr(м.subprocess, "run", Ответ(
        ЗАГОЛОВКИ + "x-robots-tag: noindex, nofollow\r\n",
        '<meta name="robots" content="index, follow">'))
    _b, режим, _к = м.живое("x-proba.ru")
    assert "≠" in режим
    assert "index, follow" in режим and "noindex" in режим


def test_совпадение_меты_и_заголовка_не_считается_расхождением(monkeypatch):
    м = _модуль()
    monkeypatch.setattr(м.subprocess, "run", Ответ(
        ЗАГОЛОВКИ + "x-robots-tag: INDEX, FOLLOW\r\n",
        '<meta name="robots" content="index, follow">'))
    _b, режим, _к = м.живое("x-proba.ru")
    assert режим == "index, follow"


def test_тега_нет_и_не_прочитано_это_разные_исходы(monkeypatch):
    """Первое — факт о витрине, второе — о измерении."""
    м = _модуль()
    monkeypatch.setattr(м.subprocess, "run", Ответ(ЗАГОЛОВКИ, "<html></html>"))
    assert м.живое("x-proba.ru")[1] == "тега нет"
    monkeypatch.setattr(м.subprocess, "run", Ответ(ЗАГОЛОВКИ, ""))
    assert м.живое("x-proba.ru")[1] == "не прочитано"


def test_отказ_curl_не_выдаётся_за_состояние_витрины(monkeypatch):
    м = _модуль()
    monkeypatch.setattr(м.subprocess, "run", Ответ("", "", код=6))
    build, режим, код = м.живое("нет-такого.test1")
    assert build == "" and режим == ""
    assert код == "curl 6"


@pytest.mark.parametrize("домен", [
    "pilot.localhost.test", "site-a.localhost", "что.invalid", "x.example"])
def test_испытательные_имена_не_измеряются(домен, monkeypatch, tmp_path):
    """RFC 6761: публично не разрешаются, и запрашивать их незачем."""
    м = _модуль()
    реестр = tmp_path / "site-cells.json"
    реестр.write_text(json.dumps({"cells": [
        {"domain": домен, "site_id": "pilot-local", "status": "not_extracted"},
    ]}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(м, "РЕЕСТР", реестр)

    def не_звать(*_а, **_к):  # pragma: no cover - вызов и есть ошибка
        raise AssertionError("испытательное имя не должно запрашиваться")

    monkeypatch.setattr(м.subprocess, "run", не_звать)
    assert м.главное([]) == 0


def test_несовпадение_build_с_журналом_даёт_ненулевой_код(monkeypatch, tmp_path):
    """Витрина отдаёт не то, что закрыл исполнитель, — это разбор."""
    м = _модуль()
    реестр = tmp_path / "site-cells.json"
    реестр.write_text(json.dumps({"cells": [
        {"domain": "x-proba.ru", "site_id": "x-01", "status": "live"},
    ]}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(м, "РЕЕСТР", реестр)
    monkeypatch.setattr(м.subprocess, "run", Ответ(
        "HTTP/2 200 \r\nx-site-factory-build-id: aaaaaaaaaaaa-x-01\r\n",
        '<meta name="robots" content="index, follow">'))
    monkeypatch.setattr(м, "последний_удачный", lambda s: ("bbbbbbbbbbbb", "t"))
    assert м.главное([]) == 1


def test_совпадение_build_даёт_ноль(monkeypatch, tmp_path):
    м = _модуль()
    реестр = tmp_path / "site-cells.json"
    реестр.write_text(json.dumps({"cells": [
        {"domain": "x-proba.ru", "site_id": "x-01", "status": "live"},
    ]}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(м, "РЕЕСТР", реестр)
    monkeypatch.setattr(м.subprocess, "run", Ответ(
        "HTTP/2 200 \r\nx-site-factory-build-id: aaaaaaaaaaaa-x-01\r\n",
        '<meta name="robots" content="index, follow">'))
    monkeypatch.setattr(м, "последний_удачный", lambda s: ("aaaaaaaaaaaa", "t"))
    assert м.главное([]) == 0


def test_реестр_не_прочитан_это_не_пустая_сеть(monkeypatch, tmp_path, capsys):
    """Отсутствие реестра не должно выглядеть как «ячеек нет»."""
    м = _модуль()
    monkeypatch.setattr(м, "РЕЕСТР", tmp_path / "нет-такого.json")
    assert м.ячейки() == []
    assert "не прочитан" in capsys.readouterr().err
