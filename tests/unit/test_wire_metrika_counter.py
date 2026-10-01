"""Подключение счётчика в репозитории витрины: проверяется поведение.

Инструмент существует затем, чтобы шесть одинаковых правок девятизначного числа
не делались руками. Значит, интересны ровно те случаи, в которых ручная правка
и ошибается: пустой реестр, чужой счётчик, уже стоящее другое значение и
повторный запуск.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
ИНСТРУМЕНТ = КОРЕНЬ / "automation" / "host" / "wire-metrika-counter.py"


def загрузить(корень: Path):
    спец = importlib.util.spec_from_file_location("wire_metrika", ИНСТРУМЕНТ)
    модуль = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(модуль)
    # Инструмент читает реестры от корня репозитория. Подменяем корень, а не
    # содержимое рабочих файлов: тест не должен писать в config/.
    модуль.КОРЕНЬ = корень
    модуль.АНАЛИТИКА = корень / "config" / "analytics.json"
    модуль.РЕЕСТР = корень / "config" / "site-cells.json"
    return модуль


@pytest.fixture()
def стенд(tmp_path: Path):
    (tmp_path / "config").mkdir()
    (tmp_path / "repo-a" / "config").mkdir(parents=True)
    (tmp_path / "repo-b" / "config").mkdir(parents=True)
    (tmp_path / "config" / "site-cells.json").write_text(json.dumps({
        "schema_version": 1,
        "cells": [
            {"site_id": "a", "domain": "a.test", "repo": {"path": "repo-a"}},
            {"site_id": "b", "domain": "b.test", "repo": {"path": "repo-b"}},
            {"site_id": "c", "domain": "c.test", "repo": {"path": "repo-c"}},
        ],
    }, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "config" / "analytics.json").write_text(json.dumps({
        "version": 1,
        "properties": [
            {"domain": "a.test", "counter_id": 1001},
            {"domain": "b.test", "counter_id": None},
        ],
    }, ensure_ascii=False), encoding="utf-8")
    for имя in ("repo-a", "repo-b"):
        (tmp_path / имя / "config" / "site.json").write_text(
            json.dumps({"site_id": имя, "environment": {}}, ensure_ascii=False),
            encoding="utf-8")
    return tmp_path


def значение(корень: Path, репозиторий: str):
    данные = json.loads((корень / репозиторий / "config" / "site.json").read_text(encoding="utf-8"))
    return данные["environment"].get("LORDS_METRIKA_COUNTER")


def test_без_apply_ничего_не_пишет(стенд):
    м = загрузить(стенд)
    состояние, _ = м.подключить(м._ячейки()[0], м._счётчики(), применять=False, заменять=False)
    assert состояние == м.ОК
    assert значение(стенд, "repo-a") is None, "показ превратился в запись"


def test_apply_записывает_и_повтор_идемпотентен(стенд):
    м = загрузить(стенд)
    ячейка, счётчики = м._ячейки()[0], м._счётчики()
    assert м.подключить(ячейка, счётчики, применять=True, заменять=False)[0] == м.ОК
    assert значение(стенд, "repo-a") == "1001"
    # Повтор обязан сообщить «уже», а не переписать заново: иначе по выводу не
    # отличить первый запуск от десятого.
    assert м.подключить(ячейка, счётчики, применять=True, заменять=False)[0] == м.УЖЕ
    assert значение(стенд, "repo-a") == "1001"


def test_нет_счётчика_не_подставляет_значение(стенд):
    м = загрузить(стенд)
    ячейка = next(c for c in м._ячейки() if c["site_id"] == "b")
    состояние, подробность = м.подключить(ячейка, м._счётчики(), применять=True, заменять=False)
    assert состояние == м.НЕТ_СЧЁТЧИКА
    assert значение(стенд, "repo-b") is None
    assert "counter_id" in подробность


def test_чужое_значение_не_перезаписывается_молча(стенд):
    м = загрузить(стенд)
    файл = стенд / "repo-a" / "config" / "site.json"
    файл.write_text(json.dumps({"environment": {"LORDS_METRIKA_COUNTER": "999"}},
                               ensure_ascii=False), encoding="utf-8")
    ячейка, счётчики = м._ячейки()[0], м._счётчики()
    состояние, подробность = м.подключить(ячейка, счётчики, применять=True, заменять=False)
    assert состояние == м.КОНФЛИКТ
    assert значение(стенд, "repo-a") == "999", "перезаписал без --replace"
    assert "--replace" in подробность
    # С явным разрешением — заменяет.
    assert м.подключить(ячейка, счётчики, применять=True, заменять=True)[0] == м.ОК
    assert значение(стенд, "repo-a") == "1001"


def test_один_счётчик_на_два_домена_отвергается(стенд):
    """Смешение двух аудиторий в одном счётчике необратимо."""
    м = загрузить(стенд)
    путь = стенд / "config" / "analytics.json"
    данные = json.loads(путь.read_text(encoding="utf-8"))
    данные["properties"][1]["counter_id"] = 1001  # тот же, что у a.test
    путь.write_text(json.dumps(данные, ensure_ascii=False), encoding="utf-8")
    состояние, подробность = м.подключить(м._ячейки()[0], м._счётчики(),
                                          применять=True, заменять=False)
    assert состояние == м.КОНФЛИКТ
    assert "b.test" in подробность
    assert значение(стенд, "repo-a") is None


def test_прокси_витрина_не_требует_переменной(стенд):
    """Разметку отдаёт приложение выше по потоку — настройка была бы мёртвой."""
    м = загрузить(стенд)
    файл = стенд / "repo-a" / "config" / "site.json"
    файл.write_text(json.dumps({"environment": {"LORDS_LEGACY_UPSTREAM": "127.0.0.1:3101"}},
                               ensure_ascii=False), encoding="utf-8")
    состояние, _ = м.подключить(м._ячейки()[0], м._счётчики(), применять=True, заменять=False)
    assert состояние == м.ПРОКСИ_ВИТРИНА
    assert значение(стенд, "repo-a") is None


def test_нет_рабочей_копии_это_отдельное_состояние(стенд):
    м = загрузить(стенд)
    ячейка = next(c for c in м._ячейки() if c["site_id"] == "c")
    счётчики = dict(м._счётчики(), **{"c.test": "1003"})
    состояние, _ = м.подключить(ячейка, счётчики, применять=True, заменять=False)
    assert состояние == м.НЕТ_РЕПОЗИТОРИЯ


def test_неизвестная_ячейка_это_код_2(стенд):
    м = загрузить(стенд)
    assert м.main(["--site", "нет-такой"]) == 2


def test_конфликт_даёт_ненулевой_код(стенд, capsys):
    м = загрузить(стенд)
    файл = стенд / "repo-a" / "config" / "site.json"
    файл.write_text(json.dumps({"environment": {"LORDS_METRIKA_COUNTER": "999"}},
                               ensure_ascii=False), encoding="utf-8")
    assert м.main(["--site", "a", "--apply"]) == 1
    assert "конфликт" in capsys.readouterr().out
