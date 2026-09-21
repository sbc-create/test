"""Контракт карточек и CSS обязаны говорить одно и то же.

Расхождение между ними уже случалось и жило незамеченным: реестр требовал для
ленты рекомендаций три колонки при 320 px и шесть при 860, а CSS давал два и
четыре. Ни одна проверка этого не видела, потому что визуальные гейты смотрят
на результат, а реестр никто не сверял с кодом (D141).

Набор сверяет лестницы колонок в обе стороны: точки перелома и число колонок.
"""

from __future__ import annotations

import json
import pathlib
import re

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
РЕЕСТР = КОРЕНЬ / "config" / "lords-card-registry.json"
ВИТРИНА = КОРЕНЬ / "automation" / "host" / "lords-frontend.py"


@pytest.fixture(scope="module")
def реестр() -> dict:
    return json.loads(РЕЕСТР.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def стили() -> str:
    return ВИТРИНА.read_text(encoding="utf-8")


def лестница_из_css(стили: str, селектор: str) -> dict[int, int]:
    """Число колонок по точкам перелома для одного селектора.

    Читается базовое правило (без media) и все `@media(min-width:N)`. Точка 0 —
    это и есть базовое правило: так его и записывает реестр.
    """
    лестница: dict[int, int] = {}

    база = re.search(
        rf"(?<!\w){re.escape(селектор)}\{{[^}}]*?grid-template-columns:\s*repeat\((\d+)",
        стили,
    )
    if база:
        лестница[0] = int(база.group(1))

    for точка, тело in re.findall(r"@media\(min-width:(\d+)px\)\{(.*?)\}\}", стили, re.S):
        правило = re.search(
            rf"(?<!\w){re.escape(селектор)}\{{[^}}]*?grid-template-columns:\s*repeat\((\d+)",
            тело,
        )
        if правило:
            лестница[int(точка)] = int(правило.group(1))
    return лестница


def test_recommendation_ladder_matches_css(реестр, стили):
    объявлено = {int(k): v for k, v in реестр["types"]["recommendation"]["columns_rel"].items()}
    измерено = лестница_из_css(стили, ".rel")
    assert измерено, "в витрине не найдено ни одного правила grid-template-columns для .rel"
    assert объявлено == измерено, (
        f"реестр объявляет {объявлено}, CSS даёт {измерено}. "
        "Расходиться им нельзя: одно из двух неверно, и молчать об этом нельзя (D141)."
    )


def test_recommendation_declares_inheritance_honestly(реестр):
    """`inherits: poster` не должно противоречить собственной лестнице."""
    рек = реестр["types"]["recommendation"]
    assert рек.get("inherits") == "poster"
    постер = {int(k): v for k, v in реестр["types"]["poster"]["columns"].items()}
    свои = {int(k): v for k, v in рек["columns_rel"].items()}
    # Наследование не обязано совпадать числом колонок — лента уже сетки, — но
    # обязано идти в ту же сторону: шире экран, не меньше колонок.
    for ширина in sorted(свои):
        соседи = [w for w in sorted(свои) if w > ширина]
        if соседи:
            assert свои[соседи[0]] >= свои[ширина], (
                f"на {соседи[0]}px колонок меньше, чем на {ширина}px — лестница идёт вспять"
            )
    assert min(свои) == 0, "нижняя ступень обязана быть базовым правилом (0)"
    assert min(постер) == 0


def test_poster_ladder_is_monotonic(реестр):
    постер = {int(k): v for k, v in реестр["types"]["poster"]["columns"].items()}
    ширины = sorted(постер)
    значения = [постер[w] for w in ширины]
    assert значения == sorted(значения), f"лестница постеров не монотонна: {постер}"


@pytest.mark.parametrize("ключ", ["max_width_px", "padding_mobile_px", "gap_mobile_px"])
def test_container_contract_present(реестр, ключ):
    assert реестр["container"].get(ключ), f"в контракте контейнера нет {ключ}"


def test_registry_carries_its_provenance(реестр):
    """Контракт обязан помнить, откуда он взялся."""
    assert "_provenance" in реестр
    assert реестр["_provenance"].get("origin")
