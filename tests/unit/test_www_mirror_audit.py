"""www-зеркала: дубль отличается от лишнего хода тремя признаками вместе.

Инструмент создан не для того, чтобы считать коды 200. Он отвечает на один
вопрос: делится ли вес сайта между двумя хостами. Поэтому здесь проверяется
каждый признак дубля по отдельности и каждая подмена, на которой суждение
ломается.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
ИСТОЧНИК = КОРЕНЬ / "automation" / "local" / "www-mirror-audit.py"


def _модуль():
    спец = importlib.util.spec_from_file_location("www_mirror_audit", ИСТОЧНИК)
    м = importlib.util.module_from_spec(спец)
    sys.modules["www_mirror_audit"] = м
    спец.loader.exec_module(м)
    return м


ау = _модуль()

СВОЙ = ('<link rel="canonical" href="https://www.проба.test/">'
        '<meta name="robots" content="index, follow">')
ЧУЖОЙ = ('<link rel="canonical" href="https://проба.test/">'
         '<meta name="robots" content="index, follow">')


def test_три_признака_вместе_это_дубль():
    статус, довод = ау.судить("www.проба.test", 200, СВОЙ)
    assert статус == ау.ДУБЛЬ, (статус, довод)


def test_canonical_на_основной_хост_это_лишний_ход_а_не_дубль():
    """Вес не делится: поисковику сказано, какой адрес правильный."""
    статус, _ = ау.судить("www.проба.test", 200, ЧУЖОЙ)
    assert статус == ау.ЛИШНИЙ_ХОД, статус


def test_закрытое_от_индекса_зеркало_дублем_не_считается():
    разметка = ('<link rel="canonical" href="https://www.проба.test/">'
                '<meta name="robots" content="noindex, follow">')
    статус, _ = ау.судить("www.проба.test", 200, разметка)
    assert статус == ау.ЗАКРЫТ_ОТ_ИНДЕКСА, статус


def test_перенаправление_это_исправность():
    for код in (301, 302, 303, 307, 308):
        статус, _ = ау.судить("www.проба.test", код, "")
        assert статус == ау.ПЕРЕНАПРАВЛЯЕТ, (код, статус)


def test_canonical_сравнивается_по_хосту_а_не_подстрокой():
    """Подвох, на котором подстрочное сравнение даёт неверный ответ.

    `https://проба.test/` содержится в строке `www.проба.test` ровно наоборот:
    а вот хост `проба.test` является ПОДСТРОКОЙ хоста `www.проба.test`.
    Сравнение «канон внутри хоста» объявило бы такое зеркало своим и насчитало
    бы дубль там, где canonical указывает правильный адрес.
    """
    статус, _ = ау.судить("www.проба.test", 200, ЧУЖОЙ)
    assert статус != ау.ДУБЛЬ, (
        "canonical на основной хост принят за свой — сравнение подстрокой")

    # И обратное: адрес с путём и портом всё равно разбирается по хосту.
    с_путём = ('<link rel="canonical" href="https://www.проба.test/catalog/">'
               '<meta name="robots" content="index, follow">')
    статус, _ = ау.судить("www.проба.test", 200, с_путём)
    assert статус == ау.ДУБЛЬ, статус


def test_без_canonical_вовсе_это_лишний_ход_а_не_дубль():
    """Своим зеркало называет себя только явно.

    Отсутствие canonical — отдельная беда, но не «canonical на себя»:
    приписывать странице заявление, которого она не делала, нельзя.
    """
    статус, довод = ау.судить("www.проба.test", 200,
                              '<meta name="robots" content="index, follow">')
    assert статус == ау.ЛИШНИЙ_ХОД, статус
    assert "—" in довод


def test_домены_берутся_из_реестра_и_только_живые(tmp_path):
    реестр = tmp_path / "site-cells.json"
    реестр.write_text(json.dumps({"cells": [
        {"site_id": "a", "domain": "живой.test", "status": "live"},
        {"site_id": "b", "domain": "запланирован.test", "status": "planned"},
        {"site_id": "c", "domain": "вынут.test", "status": "not_extracted"},
    ]}, ensure_ascii=False), encoding="utf-8")
    assert ау.живые_домены(реестр) == ["живой.test"]


def test_таймаут_это_не_измерено_и_меняет_код(tmp_path, capsys, monkeypatch):
    """Самая дорогая ошибка этого инструмента уже случилась на живых данных.

    12.10 первый замер дал таймаут на перегруженной витрине и напечатал три
    дубля вместо четырёх. Поэтому неизмеренное обязано быть отдельным исходом
    с собственным кодом возврата, а не тихо выпадать из счёта.
    """
    реестр = tmp_path / "site-cells.json"
    реестр.write_text(json.dumps({"cells": [
        {"site_id": "a", "domain": "медленный.test", "status": "live"},
    ]}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(ау, "снять",
                        lambda хост, предел: (ау.НЕ_ИЗМЕРЕНО,
                                              "TimeoutError: read timed out"))
    код = ау.главное(["--registry", str(реестр)])
    вывод = capsys.readouterr().out
    assert код == 2, вывод
    assert "НЕ ИЗМЕРЕНО" in вывод
    assert "факт о замере, а не о витрине" in вывод


def test_отсутствие_зеркала_дефектом_не_считается(tmp_path, capsys, monkeypatch):
    реестр = tmp_path / "site-cells.json"
    реестр.write_text(json.dumps({"cells": [
        {"site_id": "a", "domain": "без-www.test", "status": "live"},
    ]}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(ау, "снять",
                        lambda хост, предел: (ау.ЗЕРКАЛА_НЕТ, "DNS нет"))
    код = ау.главное(["--registry", str(реестр)])
    вывод = capsys.readouterr().out
    assert код == 0, вывод
    assert "дублей (200 + canonical на себя + индексация): 0" in вывод


def test_дубль_меняет_код_возврата(tmp_path, capsys, monkeypatch):
    реестр = tmp_path / "site-cells.json"
    реестр.write_text(json.dumps({"cells": [
        {"site_id": "a", "domain": "дубль.test", "status": "live"},
    ]}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(ау, "снять",
                        lambda хост, предел: (ау.ДУБЛЬ, "canonical=себя"))
    код = ау.главное(["--registry", str(реестр)])
    вывод = capsys.readouterr().out
    assert код == 1, вывод
    assert "www.дубль.test" in вывод
