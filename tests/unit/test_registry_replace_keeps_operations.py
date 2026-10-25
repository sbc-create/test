"""Пересборка паспорта не отменяет решений эксплуатации.

Класс дефекта проверен делом трижды: 13.10 `register(replace=True)` снимал
блоки `indexing` и `promotion`, 25.10 — `withdrawal`, 25.10 же пересборка пяти
новых ячеек на другом профиле снесла `deploy_target` с измеренным размещением.
Первые два случая лечились добавлением поля в `to_dict` — это симптом: когда
поле у нового паспорта ПУСТОЕ (а у генератора оно пустое всегда), перечисление
в `to_dict` записывает пустоту поверх заполненного.

Поэтому проверяется правило, а не перечень полей: пустое поле нового паспорта
не затирает заполненное старое, а непустое — затирает, иначе паспорт стало бы
нечем исправить.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.cell import registry


def _ячейка(site_id: str, домен: str, **поля):
    основа = {
        "site_id": site_id, "domain": домен, "aliases": (),
        "repo": {"kind": "local", "path": f"var/new-sites/{site_id}"},
        "template": {"template_id": "lords-serials", "family": "lords"},
        "pins": {},
        "deploy_target": {},
        "publisher": {"provider": "cdnvideohub"},
        "data": {},
    }
    основа.update(поля)
    return registry.Cell(**основа)


@pytest.fixture()
def путь(tmp_path: Path) -> Path:
    return tmp_path / "site-cells.json"


def _запись(путь: Path, site_id: str) -> dict:
    данные = json.loads(путь.read_text(encoding="utf-8"))
    return next(я for я in данные["cells"] if я["site_id"] == site_id)


def test_пересборка_сохраняет_измеренное_размещение(путь):
    registry.register(_ячейка("lords-90", "lords90.test"), path=путь)
    registry.update("lords-90", {"deploy_target": {
        "ref": "k2-zomro-01", "server": "145.63.129.86",
        "note": "размещение выбрано измерением"}}, path=путь)

    # Пересборка проекта на другом профиле: генератор про узел не знает.
    registry.register(_ячейка("lords-90", "lords90.test",
                              template={"template_id": "lords-serials"}),
                      path=путь, replace=True)

    запись = _запись(путь, "lords-90")
    assert запись["deploy_target"]["server"] == "145.63.129.86"
    assert запись["template"]["template_id"] == "lords-serials"


def test_пересборка_сохраняет_бэкап_ресурсы_и_размещение_рантайма(путь):
    registry.register(_ячейка("lords-91", "lords91.test"), path=путь)
    registry.update("lords-91", {
        "backup": {"at": "2026-10-25T00:00:00Z", "path": "/srv/backup/lords-91"},
        "resources": {"rss_mib": 447},
        "runtime": {"unit": "nova-lords91.service", "port": 9191},
    }, path=путь)

    registry.register(_ячейка("lords-91", "lords91.test"), path=путь, replace=True)

    запись = _запись(путь, "lords-91")
    assert запись["backup"]["path"] == "/srv/backup/lords-91"
    assert запись["resources"]["rss_mib"] == 447
    assert запись["runtime"]["port"] == 9191


def test_непустое_поле_нового_паспорта_побеждает(путь):
    """Иначе паспорт нечем было бы исправить."""
    registry.register(_ячейка("lords-92", "lords92.test",
                              template={"template_id": "lords-dorama"}), path=путь)
    registry.register(_ячейка("lords-92", "lords92.test",
                              template={"template_id": "lords-serials"}),
                      path=путь, replace=True)
    assert _запись(путь, "lords-92")["template"]["template_id"] == "lords-serials"


def test_псевдонимы_не_теряются_при_пересборке(путь):
    registry.register(_ячейка("lords-93", "lords93.test"), path=путь)
    registry.update("lords-93", {"aliases": ["www.lords93.test"]}, path=путь)
    registry.register(_ячейка("lords-93", "lords93.test"), path=путь, replace=True)
    assert _запись(путь, "lords-93")["aliases"] == ["www.lords93.test"]


def test_очистка_поля_остаётся_работой_update(путь):
    """Пересборка не умеет очищать — и не должна: очистку называют явно."""
    registry.register(_ячейка("lords-94", "lords94.test"), path=путь)
    registry.update("lords-94", {"deploy_target": {"ref": "claude-control-01"}}, path=путь)
    registry.register(_ячейка("lords-94", "lords94.test"), path=путь, replace=True)
    assert _запись(путь, "lords-94")["deploy_target"]["ref"] == "claude-control-01"

    registry.update("lords-94", {"deploy_target": {}}, path=путь)
    assert _запись(путь, "lords-94")["deploy_target"] == {}


def test_пустые_значения_распознаются_по_виду(путь):
    assert registry._пусто(None) and registry._пусто({}) and registry._пусто([])
    assert registry._пусто("")
    assert not registry._пусто(0) and not registry._пусто(False)
    assert not registry._пусто({"a": 1}) and not registry._пусто("x")
