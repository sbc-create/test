"""Данные ячеек обязаны попадать в бэкап, и план сбора обязан быть выводимым.

Повод. Измерено 2026-10-13: суточный архив хоста собирал `/srv/sites/`,
`/etc/site-factory/`, `/etc/nginx/sites-available/`, `var/` фабрики и хранилище
Secret Hub. Каталоги данных ячеек живут в `/srv/<учётная запись>/data` — другой
путь, — и в архив не попадала ни одна из 28 ячеек. Снаружи это неотличимо от
«всё собрано»: бэкап завершался успехом.

Что здесь закрепляется:

1. план строится по КОНТРАКТУ ДАННЫХ витрины, а не по списку имён в коде, —
   иначе следующая ячейка снова окажется без копии;
2. невосстановимое берётся, поставляемое — нет: снимок каталога весит в сотню
   раз больше и возвращается производителем;
3. витрина без объявленного контракта не пропускается молча;
4. элемент контракта, уводящий за пределы каталога данных, ОСТАНАВЛИВАЕТ план:
   содержимое `config/site.json` витрины — это вход, а не доверенное значение;
5. сам сценарий бэкапа действительно вызывает план и валит прогон при отказе.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.cell import registry

КОРЕНЬ = Path(__file__).resolve().parents[2]
СЦЕНАРИЙ = КОРЕНЬ / "automation" / "host" / "site-factory-backup.sh"


def _модуль():
    import importlib.util

    путь = КОРЕНЬ / "automation" / "host" / "backup_cell_data.py"
    spec = importlib.util.spec_from_file_location("backup_cell_data", путь)
    м = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(м)
    return м


def _ячейка(tmp_path, site_id="lords-10", *, контракт=None, data_dir=None,
            domain=None):
    """Реестр из одной ячейки плюс её репозиторий с контрактом данных."""
    репо = tmp_path / "repo" / site_id
    (репо / "config").mkdir(parents=True)
    конфиг = {"site_id": site_id, "domain": domain or f"{site_id}.example"}
    if контракт is not None:
        конфиг["data_contract"] = {"user_writable": контракт,
                                   "delivered": [f"{site_id}-catalog.json"]}
    (репо / "config" / "site.json").write_text(
        json.dumps(конфиг, ensure_ascii=False), encoding="utf-8")
    запись = {
        "site_id": site_id, "domain": конфиг["domain"], "aliases": [],
        "status": "live", "repo": {"kind": "local", "path": str(репо)},
        "template": {"template_id": "lords-films"}, "pins": {},
        "deploy_target": {}, "publisher": {}, "data": {}, "deployed": {},
        "content_revision": None, "last_update": None, "backup": {},
        "resources": {}, "release": {},
        "runtime": {"port": 9125, "unit": f"nova-{site_id}.service",
                    **({"data_dir": data_dir} if data_dir is not None else {})},
    }
    реестр = tmp_path / "site-cells.json"
    реестр.write_text(json.dumps({"schema_version": registry.SCHEMA_VERSION,
                                  "cells": [запись]}, ensure_ascii=False),
                      encoding="utf-8")
    return реестр


def test_план_берёт_объявленное_контрактом(tmp_path):
    реестр = _ячейка(tmp_path, контракт=["site-data", "{site}-community.json",
                                         "editorial-overrides.json"],
                     data_dir="/srv/lordfilm-group/data")
    строки = _модуль().план(реестр, шум=open("/dev/null", "w"))
    элементы = [э for _, _, э in строки]
    assert элементы == ["site-data", "lords-10-community.json",
                        "editorial-overrides.json"]
    assert all(к == "/srv/lordfilm-group/data" for _, к, _ in строки)


def test_поставляемое_в_план_не_попадает(tmp_path):
    """Снимок каталога восстановит производитель; в архиве он лишний.

    Измерено: данные ячеек 1,81 ГиБ, невосстановимая часть 25,74 МиБ (1,39 %).
    """
    реестр = _ячейка(tmp_path, контракт=["site-data", "editorial-overrides.json"],
                     data_dir="/srv/lordfilm-group/data")
    элементы = [э for _, _, э in _модуль().план(реестр, шум=open("/dev/null", "w"))]
    assert not [э for э in элементы if "catalog" in э or "details" in э]


def test_витрина_без_контракта_не_пропускается_молча(tmp_path, capsys):
    реестр = _ячейка(tmp_path, контракт=None, data_dir="/srv/lordfilm-group/data")
    м = _модуль()
    строки = м.план(реестр)
    assert строки == [("lords-10", "/srv/lordfilm-group/data", "*")]
    assert "УНКОНТРАКТ" in capsys.readouterr().err


def test_нет_каталога_данных_это_названная_причина(tmp_path, capsys):
    реестр = _ячейка(tmp_path, контракт=["site-data"], data_dir=None)
    assert _модуль().план(реестр) == []
    assert "ПРОПУСК" in capsys.readouterr().err


@pytest.mark.parametrize("элемент", [
    "../../etc/shadow", "/etc/shadow", "site-data/../../..", "~/secret",
])
def test_элемент_за_пределами_каталога_останавливает_план(tmp_path, элемент):
    """`config/site.json` витрины — вход, а не доверенное значение.

    Без этой проверки правка в репозитории витрины забирала бы в архив любой
    файл, доступный root, — и архив потом распаковывают.
    """
    м = _модуль()
    реестр = _ячейка(tmp_path, контракт=["site-data", элемент],
                     data_dir="/srv/lordfilm-group/data")
    with pytest.raises(м.ПланОтвергнут, match="уводит за пределы"):
        м.план(реестр, шум=open("/dev/null", "w"))


def test_сценарий_бэкапа_действительно_зовёт_план_и_валится_при_отказе():
    """Иначе проверка выше охраняла бы код, который никто не вызывает."""
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    assert "backup_cell_data.py" in текст, "сценарий не строит план сбора данных ячеек"
    # Отказ плана обязан останавливать прогон, а не печатать предупреждение.
    блок = текст.split("backup_cell_data.py", 1)[1][:600]
    assert "fail" in блок, "отказ плана не останавливает бэкап"
    assert "srv-cells/" in текст, "данные ячеек некуда складывать в архиве"


def test_запись_о_проверке_называет_покрытие_ячеек():
    """Иначе «данные ячеек в копии» пришлось бы принимать на слово.

    Архив и запись о проверке лежат под root (`0600` и `0640 root:root`), и
    заглянуть внутрь снаружи нечем. Число витрин и элементов в записи — это
    единственный проверяемый ответ, и ноль в нём отличим от «поле не пишется».
    """
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    assert '"cell_data"' in текст, "запись о проверке не называет покрытие ячеек"
    for имя in ("CELL_SITES", "CELL_ITEMS", "CELL_KB"):
        assert имя in текст, f"{имя} не считается и в запись не попадёт"
    # Значения обязаны доехать до python-блока записи, а не остаться в echo.
    блок = текст.split('python3 - "$RECORD"', 1)[1][:400]
    assert "$CELL_SITES" in блок and "$CELL_ITEMS" in блок, (
        "сводка по ячейкам не передана в запись о проверке")


def test_действующий_реестр_даёт_непустой_план():
    """На реальном реестре план обязан покрывать ячейки, а не оказаться пустым."""
    строки = _модуль().план(шум=open("/dev/null", "w"))
    витрины = {с for с, _, _ in строки}
    assert len(витрины) >= 20, f"в плане всего {len(витрины)} витрин"
    партия = {f"lords-{n}" for n in range(10, 18)}
    assert партия <= витрины, f"партия не покрыта: {sorted(партия - витрины)}"
