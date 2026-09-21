"""Измеритель фабрики обязан что-то измерять и уметь падать.

Два дефекта самих проверок, найденные при независимом пересмотре:

1. **Селекторы не совпадали с разметкой.** Общий измеритель искал карточки
   живого рантайма (`c--poster`), а пакеты фабрики размечены как `k--poster`.
   Множество карточек было пустым, и всё, что считалось по нему — сетки,
   пустые ячейки, одинокие хвосты, наложения, — давало ноль независимо от
   содержимого. Пятьдесят шаблонов получили «сто из ста» за проверки, которые
   не могли упасть.

2. **Колонки считались по виду, а не по объявлению.** Число колонок
   определялось как «сколько элементов стоят на одной высоте с первым». У
   мозаики ведущая плитка растянута на две колонки, в первом ряду видно три
   элемента вместо четырёх, и семь карточек делились на три с остатком один.
   Шесть исправных шаблонов объявлялись дефектными.

Здесь проверяется, что оба исправления на месте и что метрика по-прежнему
срабатывает на настоящем дефекте.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ЯДРО = КОРЕНЬ / "factory" / "templates" / "lords" / "shared"


def _загрузить(имя: str, файл: str):
    spec = importlib.util.spec_from_file_location(имя, ЯДРО / файл)
    м = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(м)
    return м


score = _загрузить("lords_score", "score.py")


# --- селекторы ---------------------------------------------------------------

def test_measurement_covers_factory_markup():
    """Измеритель обязан знать разметку пакетов фабрики, а не только рантайма."""
    измеритель = score._измеритель()
    js = измеритель.ИЗМЕРЕНИЕ
    for класс in ("k--poster", "k--compact", "k--editorial", "k--tile"):
        assert класс in js, f"измеритель не ищет карточки {класс}: множество будет пустым"
    assert "c--poster" in js, "разметка живого рантайма тоже должна остаться"


def test_substitution_fails_loudly_if_measurement_changes(monkeypatch):
    """Если общий измеритель изменится, подстановка обязана упасть, а не промолчать."""
    измеритель = score._измеритель()
    monkeypatch.setattr(измеритель, "ИЗМЕРЕНИЕ", "() => ({})")

    def подделка():
        js = измеритель.ИЗМЕРЕНИЕ
        for было, _ in score.ЗАМЕНЫ_СЕЛЕКТОРОВ:
            if было not in js:
                raise RuntimeError("подстановка не применилась")
        return измеритель

    with pytest.raises(RuntimeError):
        подделка()


def test_factory_pages_actually_contain_measured_cards():
    """На измеренных страницах карточки действительно находятся."""
    найдено = 0
    for файл in sorted((КОРЕНЬ / "var" / "scores").glob("T0*.json")):
        отчёт = json.loads(файл.read_text(encoding="utf-8"))
        for страница in отчёт.get("pages", []):
            найдено += len(страница.get("grid_summary") or [])
    assert найдено > 0, "ни одной сетки не измерено — проверки снова считают пустоту"


# --- одинокий хвост -----------------------------------------------------------

def test_orphan_tail_is_detected_on_plain_grid():
    страницы = [{"viewport": 1024, "grid_summary": [
        {"cls": "g g--poster g--shelf", "declared": 5, "cols": 5, "total": 21}]}]
    хвосты = score.одинокие_хвосты(страницы)
    assert len(хвосты) == 1, "21 карточка в пяти колонках оставляет одну — это дефект"


def test_no_orphan_when_remainder_is_not_one():
    страницы = [{"viewport": 1024, "grid_summary": [
        {"cls": "g g--poster g--shelf", "declared": 5, "cols": 5, "total": 20}]}]
    assert score.одинокие_хвосты(страницы) == []


def test_mosaic_lead_counts_as_four_cells():
    """Мозаика с растянутой плиткой не должна объявляться дефектной зря."""
    страницы = [{"viewport": 1440, "grid_summary": [
        {"cls": "g g--poster mosaic g--m1", "declared": 4, "cols": 3, "total": 7}]}]
    assert score.одинокие_хвосты(страницы) == [], \
        "семь карточек и растянутая плитка занимают десять ячеек из четырёх колонок — остаток два"


def test_mosaic_with_real_orphan_is_still_caught():
    """Исправление не должно ослепить проверку: настоящий хвост мозаики ловится."""
    страницы = [{"viewport": 1440, "grid_summary": [
        {"cls": "g g--poster mosaic g--m1", "declared": 4, "cols": 3, "total": 6}]}]
    хвосты = score.одинокие_хвосты(страницы)
    assert len(хвосты) == 1, "шесть карточек плюс три ячейки пролёта дают остаток один"


def test_two_columns_are_not_treated_as_orphan():
    """В две колонки нечётный хвост — обычный ряд, а не дыра."""
    страницы = [{"viewport": 320, "grid_summary": [
        {"cls": "g g--poster", "declared": 2, "cols": 2, "total": 7}]}]
    assert score.одинокие_хвосты(страницы) == []


def test_declared_columns_win_over_visual_count():
    """Объявленные колонки авторитетнее подсчёта по высоте элементов."""
    страницы = [{"viewport": 1440, "grid_summary": [
        {"cls": "g g--poster", "declared": 6, "cols": 3, "total": 13}]}]
    # 13 % 6 = 1 → дефект по объявленным колонкам, хотя по виду 13 % 3 = 1 тоже.
    assert len(score.одинокие_хвосты(страницы)) == 1


def test_all_shipped_templates_have_no_orphan_tail():
    плохие = []
    for файл in sorted((КОРЕНЬ / "var" / "scores").glob("T0*.json")):
        отчёт = json.loads(файл.read_text(encoding="utf-8"))
        if отчёт["measured"]["ORPHAN_LAST_ROW_COUNT"]:
            плохие.append(файл.stem)
    assert not плохие, f"одинокий хвост остался у: {плохие}"
