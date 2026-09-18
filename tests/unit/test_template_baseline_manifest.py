"""Шаблонный baseline описывает ровно тот флот, который объявлен реестром.

Манифест существует затем, что до него ответ на вопрос «какой шаблон на каком
сайте» собирался вручную из трёх мест: ветки, релизного манифеста на хосте и
памяти сессии. Совпадали они случайно.

Здесь проверяется не содержимое замеров — оно меняется с каждым релизом, — а
два свойства, которые обязаны держаться всегда: перечень сайтов берётся только
из реестра, и неизмеренное значение названо неизмеренным, а не подставлено
нулём или правдоподобной строкой.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
МАНИФЕСТ = КОРЕНЬ / "config" / "TEMPLATE-BASELINE-MANIFEST.json"
РЕЕСТР = КОРЕНЬ / "config" / "FLEET-REGISTRY.json"

ОБЯЗАТЕЛЬНЫЕ = (
    "site_id", "canonical_domain", "template_family_id", "family_engine_version",
    "template_variant_id", "template_variant_version", "blueprint_version",
    "module_bundle_version", "route_contract_digest", "collection_contract_digest",
    "source_commit", "artifact_digest", "desired_index_state", "observed_index_state",
)

#: Единственная допустимая отметка отсутствующего замера.
НЕТ_ЗАМЕРА = "NOT_MEASURED"


@pytest.fixture(scope="module")
def манифест() -> dict:
    return json.loads(МАНИФЕСТ.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def реестр() -> dict:
    return json.loads(РЕЕСТР.read_text(encoding="utf-8"))


def test_перечень_сайтов_берётся_из_реестра(манифест, реестр) -> None:
    """Список доменов нигде не зашивается — иначе появится четвёртый источник."""
    из_реестра = {s["site_id"]: s["domain"] for s in реестр["fleet"]}
    из_манифеста = {s["site_id"]: s["canonical_domain"] for s in манифест["sites"]}
    assert из_манифеста == из_реестра


def test_каждая_запись_несёт_все_поля(манифест) -> None:
    for запись in манифест["sites"]:
        нет = [п for п in ОБЯЗАТЕЛЬНЫЕ if п not in запись]
        assert not нет, f"{запись.get('site_id')}: нет полей {нет}"


def test_пустых_значений_нет(манифест) -> None:
    """Пустая строка — это утверждение «здесь ничего», а его никто не проверял."""
    for запись in манифест["sites"]:
        for поле in ОБЯЗАТЕЛЬНЫЕ:
            assert str(запись[поле]).strip(), f"{запись['site_id']}.{поле} пусто"


def test_неизмеренное_названо_неизмеренным(манифест) -> None:
    """Ноль и правдоподобная строка на месте отсутствующего замера запрещены.

    Именно подстановка «похожего» значения превращает отчёт в тот, которому
    нельзя верить: отличить измеренное от додуманного потом уже невозможно.
    """
    подозрительные = {"0", "none", "null", "unknown", "-", "n/a"}
    for запись in манифест["sites"]:
        for поле in ОБЯЗАТЕЛЬНЫЕ:
            значение = str(запись[поле]).strip().lower()
            assert значение not in подозрительные, (
                f"{запись['site_id']}.{поле}={значение!r}: "
                f"отсутствие замера обозначается {НЕТ_ЗАМЕРА}"
            )


@pytest.mark.parametrize("поле", ["desired_index_state", "observed_index_state"])
def test_состояние_индексации_из_закрытого_словаря(манифест, поле: str) -> None:
    допустимо = {"open", "closed", "MIXED", НЕТ_ЗАМЕРА}
    for запись in манифест["sites"]:
        assert запись[поле] in допустимо, f"{запись['site_id']}.{поле}={запись[поле]!r}"


def test_семейство_совпадает_с_реестром(манифест, реестр) -> None:
    семейства = {s["site_id"]: s["family"] for s in реестр["fleet"]}
    for запись in манифест["sites"]:
        assert запись["template_family_id"] == семейства[запись["site_id"]]


def test_сайты_одного_семейства_делят_движок(манифест) -> None:
    """Общее — в Family Engine. Разные отпечатки у одного семейства означают,
    что общий код снова разошёлся по копиям."""
    по_семействам: dict[str, set[str]] = {}
    for запись in манифест["sites"]:
        по_семействам.setdefault(запись["template_family_id"], set()).add(
            запись["family_engine_version"]
        )
    разошлись = {с: v for с, v in по_семействам.items() if len(v) > 1}
    assert not разошлись, f"движок семейства разошёлся по копиям: {разошлись}"
