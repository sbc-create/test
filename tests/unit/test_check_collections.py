"""Приёмка подборок вызывается ВЫПУСКОМ, а не памятью исполнителя.

Повод назван владельцем прямо: «проверь, что приёмка подборок действительно
вызывается штатным выпуском; наличие команды в AGENTS.md само по себе этого не
подтверждает». Измерено 26.10: `checks/run.sh` проекта о подборках не знал, и
`factory verify` тоже — то есть требование существовало только как текст.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ПРОВЕРКА = КОРЕНЬ / "automation" / "host" / "check_collections.py"
СХЕМА = КОРЕНЬ / "schemas" / "site-collections.schema.json"


def _модуль(корень: pathlib.Path):
    """Проверка живёт В ПРОЕКТЕ и пути считает от своего каталога."""
    (корень / "checks").mkdir(parents=True, exist_ok=True)
    копия = корень / "checks" / "check_collections.py"
    копия.write_text(ПРОВЕРКА.read_text(encoding="utf-8"), encoding="utf-8")
    (корень / "config").mkdir(exist_ok=True)
    (корень / "config" / "site-collections.schema.json").write_text(
        СХЕМА.read_text(encoding="utf-8"), encoding="utf-8")
    сп = importlib.util.spec_from_file_location(
        f"check_collections_{abs(hash(str(корень)))}", копия)
    м = importlib.util.module_from_spec(сп)
    сп.loader.exec_module(м)
    return м


def _подборка(ключ: str = "trillery-na-vecher") -> dict:
    return {
        "key": ключ,
        "title": "Триллеры на вечер",
        "viewer_request": "посмотреть напряжённое кино на один вечер",
        "intro": "Семь фильмов с закрытой историей: каждый заканчивается в тот "
                 "же вечер, продолжения искать не нужно.",
        "section": "/movies/",
        "indexing": {"open": True,
                     "reason": "семь работ с пояснениями, страница несёт "
                               "собственную пользу, а не повтор каталога"},
        # Схема требует не меньше трёх работ, постоянный id не короче восьми
        # знаков и АБСОЛЮТНЫЙ адрес: подборка из двух строк и подборка со
        # слагом вместо id — это ровно то, что требование и запрещает.
        "items": [{"order": н, "id": f"catalog-{н:04d}", "slug": f"proba-{н}",
                   "url": f"https://proba.invalid/title/proba-{н}/",
                   "name": f"Проба {н}", "year": 2024,
                   "reason": "закрытая история на один вечер",
                   "checked": "2026-10-26"} for н in (1, 2, 3)],
    }


def _файл(корень: pathlib.Path, подборки: list) -> None:
    (корень / "config" / "collections.json").write_text(json.dumps({
        "schema": "proba.invalid.collections/1", "site": "proba.invalid",
        "site_id": "proba-01", "prepared_at": "2026-10-26T00:00:00Z",
        "status": "PREPARED_NOT_RELEASED", "key": "proba-01-20261026",
        "direction_rule": "подборки по направлению витрины и разделу-владельцу",
        "collections": подборки,
    }, ensure_ascii=False), encoding="utf-8")


def test_годный_файл_проходит(tmp_path):
    м = _модуль(tmp_path)
    _файл(tmp_path, [_подборка()])
    assert м.главная([]) == 0


def test_нарушение_схемы_это_отказ(tmp_path, capsys):
    """Решение об индексации без причины — не решение."""
    м = _модуль(tmp_path)
    п = _подборка()
    п["indexing"] = {"open": True}
    _файл(tmp_path, [п])
    assert м.главная([]) == 1
    вывод = capsys.readouterr()
    assert "нарушений схемы" in вывод.err


def test_нет_файла_подборок_это_пропуск_с_причиной(tmp_path, capsys):
    """Новая витрина подборок ещё не объявляет — это не провал выпуска."""
    м = _модуль(tmp_path)
    assert м.главная([]) == 0
    вывод = capsys.readouterr().out
    assert "ПРОПУЩЕНО" in вывод and "НЕ ИЗМЕРЕНО" in вывод


def test_битый_json_это_отказ(tmp_path, capsys):
    м = _модуль(tmp_path)
    (tmp_path / "config" / "collections.json").write_text("{не json",
                                                          encoding="utf-8")
    assert м.главная([]) == 1
    assert "не разбирается" in capsys.readouterr().err


def test_отчёт_называет_границу_своей_проверки(tmp_path, capsys):
    """Молчать о том, чего проверка не измеряет, нельзя: «проверено» и «не
    измерено» сольются."""
    м = _модуль(tmp_path)
    _файл(tmp_path, [_подборка()])
    м.главная([])
    вывод = capsys.readouterr().out
    assert "живые факты" in вывод
    assert "collections-acceptance.py" in вывод


def test_без_схемы_в_проекте_проверка_честно_молчит(tmp_path, capsys):
    м = _модуль(tmp_path)
    _файл(tmp_path, [_подборка()])
    (tmp_path / "config" / "site-collections.schema.json").unlink()
    assert м.главная([]) == 0
    assert "НЕ ИЗМЕРЕНО" in capsys.readouterr().out
