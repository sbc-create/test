"""Наблюдатель за материалами без рецензии: пустой вывод — это «ждать нечего».

Свойство, ради которого инструмент отдельный: пока ожидающих нет, он печатает
НИЧЕГО. Наблюдатель тогда молчит, и «ничего не ждёт» не выглядит как событие.
Отрицательные контроли названы заранее: оба вида хранилища (список и словарь)
разбираются одинаково, а нечитаемое хранилище молчанием не считается.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ПУТЬ = (Path(__file__).resolve().parents[2] / "automation" / "local"
        / "pending-review-watch.py")


def _модуль():
    спец = importlib.util.spec_from_file_location("pending_review_watch", ПУТЬ)
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


МОД = _модуль()


def _хранилище(tmp_path, домен: str, записи, *, словарём: bool):
    д = tmp_path / "srv" / домен / "runtime" / "overlays" / домен
    д.mkdir(parents=True, exist_ok=True)
    тело = ({"items": {з["slug"]: з for з in записи}} if словарём
            else {"items": записи})
    (д / "drafts.json").write_text(json.dumps(тело, ensure_ascii=False),
                                   encoding="utf-8")
    return str(tmp_path / "srv" / "*" / "runtime" / "overlays" / "*" / "drafts.json")


def test_материал_без_рецензии_назван(tmp_path):
    шаблон = _хранилище(tmp_path, "animedia.space", [
        {"slug": "a", "prepared_at": "2026-10-25T04:05:00Z"},
    ], словарём=False)
    строки = МОД.ожидающие("2026-10-25", шаблон)
    assert len(строки) == 1
    assert "animedia.space/a" in строки[0]
    assert "2026-10-25T04:05:00Z" in строки[0]


def test_отрецензированный_не_назван(tmp_path):
    шаблон = _хранилище(tmp_path, "animedia.space", [
        {"slug": "a", "prepared_at": "2026-10-25T04:05:00Z",
         "review": {"verdict": "accepted"}},
    ], словарём=False)
    assert МОД.ожидающие("2026-10-25", шаблон) == []


def test_материал_другого_дня_не_назван(tmp_path):
    шаблон = _хранилище(tmp_path, "animedia.space", [
        {"slug": "a", "prepared_at": "2026-10-24T22:00:00Z"},
    ], словарём=False)
    assert МОД.ожидающие("2026-10-25", шаблон) == []


def test_хранилище_словарём_разбирается_так_же(tmp_path):
    шаблон = _хранилище(tmp_path, "zonafilm.cc", [
        {"slug": "b", "prepared_at": "2026-10-25T01:00:00Z"},
    ], словарём=True)
    строки = МОД.ожидающие("2026-10-25", шаблон)
    assert len(строки) == 1 and "zonafilm.cc/b" in строки[0]


def test_нечитаемое_хранилище_не_считается_молчанием(tmp_path):
    д = tmp_path / "srv" / "x" / "runtime" / "overlays" / "x"
    д.mkdir(parents=True)
    (д / "drafts.json").write_text("{не json", encoding="utf-8")
    шаблон = str(tmp_path / "srv" / "*" / "runtime" / "overlays" / "*" / "drafts.json")
    строки = МОД.ожидающие("2026-10-25", шаблон)
    assert len(строки) == 1
    assert строки[0].startswith("ХРАНИЛИЩЕ НЕ ПРОЧИТАНО")


def test_запись_без_слага_не_ломает_разбор(tmp_path):
    шаблон = _хранилище(tmp_path, "animedia.icu", [
        {"prepared_at": "2026-10-25T04:05:00Z"},
        {"slug": "c", "prepared_at": "2026-10-25T04:06:00Z"},
    ], словарём=False)
    строки = МОД.ожидающие("2026-10-25", шаблон)
    assert len(строки) == 1 and "animedia.icu/c" in строки[0]


def test_пустое_хранилище_молчит(tmp_path):
    шаблон = _хранилище(tmp_path, "animedia.icu", [], словарём=False)
    assert МОД.ожидающие("2026-10-25", шаблон) == []
