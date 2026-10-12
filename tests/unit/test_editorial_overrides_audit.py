"""Целость редакционных правок: потеря поля должна быть измеримой.

Повод. 2026-10-11 прогон редактора перезаписал файл правок витрины
zonafilm.space одними описаниями, и внесённое решением D200 название исчезло —
страница вернулась к оригиналу. Обнаружилось это СЛУЧАЙНО: я проверял выкладку
через четыре часа после потери. Пока правка «состав файла собирается из живого
файла плюс свои описания» не установлена в службу MCP, потеря может повториться
на любой витрине.

Почему нужен реестр, а не только чтение файла: по одному файлу потерю не
отличить от «такого поля тут и не было» — поля просто нет в обоих случаях.
Реестр `config/editorial-protected-fields.json` называет, что вносилось
решением, и тогда отсутствие становится фактом, а не догадкой.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
СЦЕНАРИЙ = КОРЕНЬ / "automation" / "local" / "editorial-overrides-audit.py"
РЕЕСТР = КОРЕНЬ / "config" / "editorial-protected-fields.json"


def _модуль():
    спец = importlib.util.spec_from_file_location("editorial_overrides_audit",
                                                  СЦЕНАРИЙ)
    м = importlib.util.module_from_spec(спец)
    sys.modules["editorial_overrides_audit"] = м
    спец.loader.exec_module(м)
    return м


def _файл(каталог: Path, витрина: str, правки: dict) -> Path:
    место = каталог / витрина / "data"
    место.mkdir(parents=True, exist_ok=True)
    путь = место / "editorial-overrides.json"
    путь.write_text(json.dumps({"schema_version": 1, "site_id": витрина,
                                "overrides": правки}, ensure_ascii=False),
                    encoding="utf-8")
    return путь


@pytest.fixture()
def стенд(tmp_path):
    м = _модуль()
    м.КОРНИ = tmp_path
    return м, tmp_path


def test_состав_полей_читается_из_списка_и_из_словаря(стенд):
    """Первая версия печатала «fields» вместо состава — молчала о том, что ищет."""
    м, корень = стенд
    _файл(корень, "сайт-список", {"a": {"fields": ["description", "name"],
                                        "actor": "editor/x/run-1"}})
    _файл(корень, "сайт-словарь", {"b": {"fields": {"name": "Название"},
                                         "actor": "architect/x/run-2"}})
    по_витрине = {и["витрина"]: и for и in (м.разобрать(п) for п in м.файлы())}
    assert по_витрине["сайт-список"]["поля"] == ["description", "name"]
    assert по_витрине["сайт-словарь"]["поля"] == ["name"]
    assert по_витрине["сайт-словарь"]["авторы"] == ["architect/x/run-2"]


def test_только_описания_отмечается(стенд):
    м, корень = стенд
    _файл(корень, "сайт", {"a": {"fields": ["description"]}})
    (и,) = [м.разобрать(п) for п in м.файлы()]
    assert и["только_описания"] is True
    assert и["есть_чужие_поля"] == []


def test_поле_не_редактора_видно_отдельно(стенд):
    м, корень = стенд
    _файл(корень, "сайт", {"a": {"fields": ["description", "name"]}})
    (и,) = [м.разобрать(п) for п in м.файлы()]
    assert и["только_описания"] is False
    assert и["есть_чужие_поля"] == ["name"]


def test_пропажа_защищённого_поля_это_потеря(стенд, monkeypatch):
    м, корень = стенд
    _файл(корень, "zonafilm-space", {"a": {"fields": ["description"]}})
    monkeypatch.setattr(м, "защищённые",
                        lambda: {"zonafilm.space": {"fields": ["name"],
                                                    "decision": "D200"}})
    потери = м.сверить_с_реестром([м.разобрать(п) for п in м.файлы()])
    assert len(потери) == 1
    assert потери[0]["пропали"] == ["name"]
    assert потери[0]["решение"] == "D200"


def test_защищённое_поле_на_месте_потерей_не_считается(стенд, monkeypatch):
    м, корень = стенд
    _файл(корень, "zonafilm-space",
          {"a": {"fields": ["description", "name"]}})
    monkeypatch.setattr(м, "защищённые",
                        lambda: {"zonafilm.space": {"fields": ["name"]}})
    assert м.сверить_с_реестром([м.разобрать(п) for п in м.файлы()]) == []


def test_отсутствие_файла_правок_тоже_потеря(стенд, monkeypatch):
    """Файл мог быть удалён целиком — это не «полей нет», а «нечего читать»."""
    м, корень = стенд
    _файл(корень, "другая-витрина", {"a": {"fields": ["description"]}})
    monkeypatch.setattr(м, "защищённые",
                        lambda: {"zonafilm.space": {"fields": ["name"]}})
    потери = м.сверить_с_реестром([м.разобрать(п) for п in м.файлы()])
    assert потери and "не нашлось" in потери[0]["почему"]


def test_потеря_даёт_ненулевой_код(стенд, monkeypatch, capsys):
    м, корень = стенд
    _файл(корень, "zonafilm-space", {"a": {"fields": ["description"]}})
    monkeypatch.setattr(м, "защищённые",
                        lambda: {"zonafilm.space": {"fields": ["name"],
                                                    "decision": "D200"}})
    код = м.главное([])
    вывод = capsys.readouterr().out
    assert код == 1, вывод
    assert "ПОТЕРЯ защищённых полей" in вывод
    assert "editorial-field-write.py" in вывод, "не сказано, чем восстановить"


def test_реестр_в_репозитории_читается_и_осмыслен():
    """Реестр — не пустой файл: он называет решение и причину."""
    д = json.loads(РЕЕСТР.read_text(encoding="utf-8"))
    сайты = д["sites"]
    assert "zonafilm.space" in сайты
    правило = сайты["zonafilm.space"]
    assert правило["fields"] == ["name"]
    assert правило["decision"] == "D200"
    assert правило["handoffs"] == ["114", "115", "116"]
    assert д["why"], "реестр без причины превращается в список без основания"


def test_живой_реестр_подхватывается_инструментом():
    """Проверка на настоящем файле репозитория, без подмен."""
    м = _модуль()
    реестр = м.защищённые()
    assert "zonafilm.space" in реестр
    assert реестр["zonafilm.space"]["fields"] == ["name"]
