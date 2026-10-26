"""Отличить «поставщик не отдал» от «мы отфильтровали» — по всем снимкам хоста.

Повод: `zonafilm12.site/title/chuzhaya-zhizn/` отдала 404, и это почти всё
падение Яндекса по домену за неделю (входы на страницу 227 → 37). Нужно было
отличить четыре причины: данные поставщика, фильтрацию на нашей стороне,
сопоставление ID (переименование) и обоснованное снятие. Разницу решает один
вопрос: держит ли слаг или это название ХОТЬ ОДИН снимок. Поиск по снимку одной
витрины на него не отвечает — у поставщика одна база на все семейства.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_сп = importlib.util.spec_from_file_location(
    "catalog_slug_presence",
    КОРЕНЬ / "automation" / "local" / "catalog-slug-presence.py")
инс = importlib.util.module_from_spec(_сп)
_сп.loader.exec_module(инс)


def _снимок(путь: pathlib.Path, записи: list) -> None:
    путь.parent.mkdir(parents=True, exist_ok=True)
    путь.write_text(json.dumps({"revision": "проба", "items": записи},
                               ensure_ascii=False), encoding="utf-8")


def test_слаг_найден_в_одном_из_снимков(tmp_path, monkeypatch):
    """Находка означает: запись у поставщика есть, дело не в нём."""
    а = tmp_path / "a" / "data" / "x-catalog.json"
    б = tmp_path / "b" / "data" / "y-catalog.json"
    _снимок(а, [{"slug": "другое", "title": "Другое"}])
    _снимок(б, [{"slug": "искомое", "title": "Искомое", "year": 2020,
                 "kind": "Сериал"}])
    monkeypatch.setattr(инс, "снимки_хоста", lambda: [а, б])
    осмотрено, находки = инс.искать(слаг="искомое")
    assert осмотрено == 2
    assert [н["title"] for н in находки] == ["Искомое"]


def test_слага_нет_нигде_это_данные_поставщика(tmp_path, monkeypatch):
    а = tmp_path / "a" / "data" / "x-catalog.json"
    _снимок(а, [{"slug": "другое", "title": "Другое"}])
    monkeypatch.setattr(инс, "снимки_хоста", lambda: [а])
    осмотрено, находки = инс.искать(слаг="пропавшее")
    assert осмотрено == 1
    assert находки == []


def test_поиск_по_названию_не_зависит_от_регистра(tmp_path, monkeypatch):
    """Слаг мог измениться вместе с названием: тогда искать надо по названию."""
    а = tmp_path / "a" / "data" / "x-catalog.json"
    _снимок(а, [{"slug": "chuzhaya-zhizn-moego-serdca",
                 "title": "Чужая жизнь моего сердца"}])
    monkeypatch.setattr(инс, "снимки_хоста", lambda: [а])
    _, точное = инс.искать(название="чужая жизнь моего СЕРДЦА")
    assert len(точное) == 1
    # Частичное совпадение находкой НЕ считается: «Чужая жизнь» и «Чужая жизнь
    # моего сердца» — разные произведения, и склеить их значило бы объявить
    # переименование, которого не было.
    _, другое = инс.искать(название="Чужая жизнь")
    assert другое == []


def test_нечитаемый_снимок_не_валит_прогон(tmp_path, monkeypatch):
    """Недоступный по правам снимок — не повод не ответить про остальные."""
    а = tmp_path / "a" / "data" / "x-catalog.json"
    битый = tmp_path / "b" / "data" / "y-catalog.json"
    _снимок(а, [{"slug": "искомое", "title": "Искомое"}])
    битый.parent.mkdir(parents=True, exist_ok=True)
    битый.write_text("{не json", encoding="utf-8")
    monkeypatch.setattr(инс, "снимки_хоста", lambda: [а, битый])
    осмотрено, находки = инс.искать(слаг="искомое")
    assert осмотрено == 1, "битый снимок не должен считаться прочитанным"
    assert len(находки) == 1


def test_вердикт_умеет_падать(tmp_path, monkeypatch):
    """Отсутствие записи — ненулевой код: иначе в воротах вердикт всегда зелёный."""
    а = tmp_path / "a" / "data" / "x-catalog.json"
    _снимок(а, [{"slug": "другое", "title": "Другое"}])
    monkeypatch.setattr(инс, "снимки_хоста", lambda: [а])
    assert инс.главная(["--slug", "пропавшее"]) == 1
    assert инс.главная(["--slug", "другое"]) == 0


def test_без_цели_это_blocked_input(capsys):
    assert инс.главная([]) == 2
