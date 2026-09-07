"""Выкат payload-сайта обязан грузить каталог, а не только конфигурацию тенанта.

Что было. План выката заканчивался шагом `apply_tenant`: `content_package_ref`
пакета не читал никто. Сайт поднимался, отвечал 200 и был визуально пустым —
дефект, который не видно ни одной проверкой статусов, потому что технически всё
живо. Здесь закреплено, что шаг загрузки каталога есть, стоит после применения
конфигурации и до старта кандидата, и что он называет пакет поимённо.
"""
from __future__ import annotations

import pytest

from factory.targets.payload_multisite import PayloadMultisiteTarget
from factory.validation import load_package

КОНФИГУРАЦИЯ = {"ref": "payload-local", "root": "var/targets/payload-local",
                "bind_host": "127.0.0.1", "port_range": [8110, 8129]}


@pytest.fixture
def цель():
    package = load_package("site-a")
    return PayloadMultisiteTarget(КОНФИГУРАЦИЯ, package), package


def test_план_содержит_шаг_загрузки_каталога(цель):
    мишень, _ = цель
    шаги = [шаг["id"] for шаг in мишень.plan(мишень.root, "b" * 16).steps]
    assert "import_catalog" in шаги, f"шага загрузки каталога нет в плане: {шаги}"


def test_каталог_грузится_после_конфигурации_и_до_старта(цель):
    мишень, _ = цель
    шаги = [шаг["id"] for шаг in мишень.plan(мишень.root, "b" * 16).steps]
    assert шаги.index("apply_tenant") < шаги.index("import_catalog"), (
        "каталог грузится раньше тенанта — публикациям некуда лечь")
    assert шаги.index("import_catalog") < шаги.index("start_candidate"), (
        "кандидат стартует раньше загрузки каталога — витрина поднимется пустой")


def test_шаг_называет_пакет_контента_поимённо(цель):
    мишень, package = цель
    шаг = next(шаг for шаг in мишень.plan(мишень.root, "b" * 16).steps
               if шаг["id"] == "import_catalog")
    assert package["content_package_ref"] in шаг["detail"], (
        f"в описании шага нет пакета контента: {шаг['detail']}")
    assert шаг["mutation"] is True, "загрузка каталога помечена как немутирующая"
