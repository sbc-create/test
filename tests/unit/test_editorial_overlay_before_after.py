"""Накладка до и после публикации: инструмент обязан УМЕТЬ упасть.

Он создан для приёмки первой публикации после установки защиты (B004), и его
единственная ценность — поймать потерю. Поэтому здесь проверяется не «работает
на хорошем случае», а три вида потери по отдельности: пропавшая запись,
пропавшее поле у сохранившейся записи и подменённое авторство.

Отдельно закреплено, что без снимка инструмент ОТКАЗЫВАЕТ, а не печатает
«потерь нет»: это утверждение о том, чего он не знает.
"""
from __future__ import annotations

import importlib.util
import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
ИСТОЧНИК = (КОРЕНЬ / "automation" / "local"
            / "editorial-overlay-before-after.py")

ДО = {
    "silsila-badalte-rishton-ka": {
        "fields": {"name": "История наших отношений"},
        "actor": "architect/claude-restore/run-1", "reason": "восстановление"},
    "drugoy-tayitl": {
        "fields": {"description": "текст"},
        "actor": "editor/claude-auto/run-2", "reason": "описание"},
}


def _модуль():
    спец = importlib.util.spec_from_file_location("overlay", ИСТОЧНИК)
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


@pytest.fixture(scope="module")
def м():
    return _модуль()


def накладка(tmp_path: Path, правки: dict) -> Path:
    путь = tmp_path / "editorial-overrides.json"
    путь.write_text(json.dumps({"site_id": "zona-01", "overrides": правки},
                               ensure_ascii=False), encoding="utf-8")
    return путь


def публикация(путь: Path) -> None:
    """Отметить накладку как записанную ПОСЛЕ снимка.

    Инструмент отказывается судить о потерях, если публикации между снимком и
    сверкой не было: иначе «потерь нет» печаталось бы там, где проверка не
    могла упасть. В стенде снимок снимается позже записи накладки, поэтому
    событие публикации надо воспроизвести, а не обойти.
    """
    import os
    будущее = путь.stat().st_mtime + 3600
    os.utime(путь, (будущее, будущее))


def прогон(м, tmp_path: Path, путь: Path, *, снимок: bool = False):
    арг = ["--repo", "проба", "--path", str(путь),
           "--snapshots", str(tmp_path / "снимки"),
           "--snapshot" if снимок else "--compare"]
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        код = м.главное(арг)
    return код, буфер.getvalue()


def test_ничего_не_пропало_это_проход(м, tmp_path):
    путь = накладка(tmp_path, ДО)
    assert прогон(м, tmp_path, путь, снимок=True)[0] == 0
    публикация(путь)
    код, вывод = прогон(м, tmp_path, путь)
    assert код == 0, вывод
    assert "ни одна запись, поле и авторство не пропали" in вывод
    assert "чужое поле на месте" in вывод


def test_пропавшая_запись_это_отказ(м, tmp_path):
    путь = накладка(tmp_path, ДО)
    прогон(м, tmp_path, путь, снимок=True)
    накладка(tmp_path, {"drugoy-tayitl": ДО["drugoy-tayitl"]})
    публикация(путь)
    код, вывод = прогон(м, tmp_path, путь)
    assert код == 1
    assert "пропали записи" in вывод
    assert "silsila-badalte-rishton-ka" in вывод


def test_пропавшее_поле_у_сохранившейся_записи_это_отказ(м, tmp_path):
    """Тот самый дефект: запись осталась, а чужое поле из неё исчезло."""
    путь = накладка(tmp_path, ДО)
    прогон(м, tmp_path, путь, снимок=True)
    испорчено = {**ДО, "silsila-badalte-rishton-ka": {
        "fields": {"description": "подставлено издателем"},
        "actor": "editor/claude-auto/run-3", "reason": "описание"}}
    накладка(tmp_path, испорчено)
    публикация(путь)
    код, вывод = прогон(м, tmp_path, путь)
    assert код == 1
    assert "пропали поля" in вывод
    assert "name" in вывод


def test_подменённое_авторство_это_отказ(м, tmp_path):
    """Приписать себе чужую правку — потеря единственной записи о том, кто её внёс."""
    путь = накладка(tmp_path, ДО)
    прогон(м, tmp_path, путь, снимок=True)
    испорчено = {**ДО, "silsila-badalte-rishton-ka": {
        **ДО["silsila-badalte-rishton-ka"], "actor": "editor/claude-auto/run-9"}}
    накладка(tmp_path, испорчено)
    публикация(путь)
    код, вывод = прогон(м, tmp_path, путь)
    assert код == 1
    assert "подменено авторство" in вывод


def test_новые_записи_потерей_не_считаются(м, tmp_path):
    """Публикация ДОБАВЛЯЕТ описания — это норма, а не дефект."""
    путь = накладка(tmp_path, ДО)
    прогон(м, tmp_path, путь, снимок=True)
    накладка(tmp_path, {**ДО, "tretiy": {
        "fields": {"description": "новое"}, "actor": "editor", "reason": "—"}})
    публикация(путь)
    код, вывод = прогон(м, tmp_path, путь)
    assert код == 0, вывод
    assert "новых 1" in вывод


def test_без_снимка_инструмент_отказывает(м, tmp_path):
    """«Потерь нет» без снимка — утверждение о том, чего не знаем."""
    путь = накладка(tmp_path, ДО)
    публикация(путь)
    код, _вывод = прогон(м, tmp_path, путь)
    assert код == 2


def test_нет_накладки_это_исход_два(м, tmp_path):
    код = м.главное(["--repo", "проба", "--path", str(tmp_path / "нет.json"),
                     "--snapshots", str(tmp_path / "снимки"), "--snapshot"])
    assert код == 2


def test_поля_редактора_объявлены_перечнем(м):
    """Чужое поле опознаётся по перечню полей редактора, а не по догадке."""
    assert м.ПОЛЯ_РЕДАКТОРА == ("description",)


def test_без_публикации_вердикт_не_выносится(м, tmp_path):
    """«Потерь нет» без публикации между снимком и сверкой — пустое слово.

    Измерено 12.10 на живых данных: все семь накладок правлены 9–11.10, снимки
    сняты 12.10 в 18:25, и инструмент печатал «ни одна запись, поле и
    авторство не пропали» с кодом 0. Проверка физически не могла упасть —
    ровно то, что запрещает D205.
    """
    путь = накладка(tmp_path, ДО)
    код, _ = прогон(м, tmp_path, путь, снимок=True)
    assert код == 0
    # Публикации НЕ воспроизводим: накладка остаётся старше снимка.
    код, вывод = прогон(м, tmp_path, путь)
    assert код == 2, вывод
    assert "не измерено" in вывод
    assert "не менялась после снимка" in вывод
    assert "не пропали" not in вывод, вывод


def test_после_публикации_потеря_ловится(м, tmp_path):
    """Обратная сторона того же свойства: с публикацией инструмент судит.

    Без этой проверки предыдущая прошла бы и у инструмента, который
    отказывается судить ВСЕГДА — а такой бесполезен.
    """
    путь = накладка(tmp_path, ДО)
    код, _ = прогон(м, tmp_path, путь, снимок=True)
    assert код == 0

    без_чужого = {
        "silsila-badalte-rishton-ka": {
            "fields": {"description": "издатель собрал из своих описаний"},
            "actor": "editor/claude-auto/run-9", "reason": "описание"},
        "drugoy-tayitl": ДО["drugoy-tayitl"],
    }
    путь.write_text(json.dumps({"site_id": "zona-01",
                                "overrides": без_чужого},
                               ensure_ascii=False), encoding="utf-8")
    публикация(путь)
    код, вывод = прогон(м, tmp_path, путь)
    assert код != 0, вывод
    assert "name" in вывод, вывод
