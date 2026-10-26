"""Заполнение семантики не обращается ни к одному платному методу.

Владельцу предстоит запустить `topvisor-connect` одной командой, а баланс
аккаунта нулевой. «Проверки позиций не запускаем» — это обещание, и оно должно
быть проверяемым, а не устным: у Topvisor платные маршруты синтаксически не
отличаются от бесплатных, и цена ошибки — деньги.

Проверяется поведение всего пути `apply`: какие методы он вызывает на полном
манифесте и что делает клиент, если платный метод всё же попросить.
"""
from __future__ import annotations

import argparse

import pytest

from factory.errors import FactoryError
from factory.topvisor import cli
from factory.topvisor.client import ALLOWED, Cost


class КлиентУчёта:
    """Считает вызовы. Отвечает так, чтобы путь прошёл до конца."""

    def __init__(self, проекты: list[dict]) -> None:
        self._проекты = проекты
        self.вызовы: list[str] = []
        self.группы: dict[object, list[dict]] = {}

    def projects(self) -> list[dict]:
        self.вызовы.append("get/projects_2/projects")
        return list(self._проекты)

    def keyword_groups(self, ид):
        self.вызовы.append("get/keywords_2/groups")
        return list(self.группы.get(ид, []))

    def keywords(self, ид):  # noqa: ARG002
        self.вызовы.append("get/keywords_2/keywords")
        return []

    def projects_with_regions(self) -> list[dict]:
        self.вызовы.append("get/projects_2/projects")
        return list(self._проекты)

    def find_regions(self, *a, **k):  # noqa: ARG002
        self.вызовы.append("get/system_2/common/regions")
        return []

    def call(self, method: str, payload: dict):
        self.вызовы.append(method)
        if method == "add/keywords_2/groups":
            ид = payload["project_id"]
            номер = sum(len(v) for v in self.группы.values()) + 1
            self.группы.setdefault(ид, []).append({"id": номер, "name": payload["name"]})
        return {"result": 1}


@pytest.fixture()
def полный_манифест() -> list[dict]:
    from factory.topvisor.manifest import MANIFEST
    return [{"id": 4000 + н, "url": с.domain, "site": с.domain}
            for н, с in enumerate(MANIFEST)]


ПЛАТНЫЕ = sorted(и for и, м in ALLOWED.items() if м.cost is not Cost.FREE)


def test_есть_что_проверять() -> None:
    assert ПЛАТНЫЕ, "в списке нет ни одного платного метода — проверка бессмысленна"


def test_apply_не_вызывает_ни_одного_платного_метода(monkeypatch, capsys, полный_манифест):
    клиент = КлиентУчёта(полный_манифест)
    monkeypatch.setattr(cli, "_client", lambda *a, **k: клиент)
    assert cli.cmd_apply(argparse.Namespace()) == 0
    capsys.readouterr()
    платные = [в for в in клиент.вызовы if в in ПЛАТНЫЕ]
    assert платные == [], f"путь apply обратился к платному методу: {платные}"
    assert "add/keywords_2/groups" in клиент.вызовы, "семантика не заполнялась вовсе"


def test_клиент_отказывает_платному_методу_при_любом_флаге():
    """Даже прямой вызов не проходит: список цен — часть клиента, а не совет."""
    from factory.topvisor.client import TopvisorClient
    from factory.topvisor.credentials import TopvisorCredentials

    кред = TopvisorCredentials("1", "не-настоящий-ключ")
    for имя in ПЛАТНЫЕ:
        клиент = TopvisorClient(credentials=кред, dry_run=False,
                                opener=lambda *a, **k: (_ for _ in ()).throw(
                                    AssertionError("платный метод дошёл до сети")),
                                sleep=lambda _: None)
        with pytest.raises(FactoryError) as отказ:
            клиент.call(имя, {})
        assert "платн" in str(отказ.value).lower(), (имя, str(отказ.value))


def test_поисковые_системы_не_добавляются_без_чтения(monkeypatch, capsys, полный_манифест):
    """Чтение регионов не удалось — не добавляем ничего: слепой add создал бы дубли."""
    клиент = КлиентУчёта(полный_манифест)

    def отказ():
        raise FactoryError("Topvisor недоступен", required_input="сеть")

    клиент.projects_with_regions = отказ
    monkeypatch.setattr(cli, "_client", lambda *a, **k: клиент)
    cli.cmd_apply(argparse.Namespace())
    вывод = capsys.readouterr().out
    assert "add/positions_2/searchers" not in клиент.вызовы
    assert not any(в.startswith("add/positions_2/searchers") for в in клиент.вызовы)
    assert "перечитать регионы не удалось" in вывод


def test_регион_добавляется_с_ключом_из_ответа_сервиса(monkeypatch, capsys):
    """Ключ региона берётся из уже настроенного проекта аккаунта, недостающие
    устройства добавляются, существующие не дублируются."""
    from factory.topvisor.manifest import MANIFEST
    from factory.cell import withdrawn

    spec = next(с for с in MANIFEST if not withdrawn.выведен(с.domain))
    настроенный = {"id": 1, "url": spec.domain, "site": spec.domain, "on": 0, "searchers": [
        {"key": 0, "name": "Yandex", "regions": [
            {"index": 5, "key": 777, "name": "Россия", "lang": "ru", "device": 0, "depth": 1}]},
    ]}
    клиент = КлиентУчёта([настроенный])
    клиент.projects_with_regions = lambda: [настроенный]
    отправлено: list[tuple[str, dict]] = []
    исходный = клиент.call

    def call(method, payload):
        отправлено.append((method, payload))
        return исходный(method, payload)

    клиент.call = call
    monkeypatch.setattr(cli, "_client", lambda *a, **k: клиент)
    cli.cmd_apply(argparse.Namespace())
    capsys.readouterr()
    регионы = [п for м, п in отправлено if м == "add/positions_2/searchers/regions"]
    # Яндекс ПК уже есть; добавляется Яндекс смартфон с тем же ключом 777.
    assert {"project_id": 1, "searcher_key": 0, "region_key": 777, "region_lang": "ru",
            "region_device": 2, "region_depth": 1} in регионы
    assert not any(п["searcher_key"] == 0 and п["region_device"] == 0 for п in регионы)
    # Google в проекте нет — система добавляется, а ключ региона для неё не
    # выводится из ключа Яндекса: справочник пуст, регион не добавляется.
    assert ("add/positions_2/searchers", {"project_id": 1, "searcher_key": 1}) in отправлено
    assert not any(п["searcher_key"] == 1 for п in регионы)


def test_архивный_активный_проект_возвращается(monkeypatch, capsys):
    """Пауза опыта — пауза изменений сайта, не измерений: архивный проект
    активного сайта возвращается в обычные; выведенный — не трогается."""
    from factory.topvisor.manifest import MANIFEST
    from factory.cell import withdrawn

    активный = next(с for с in MANIFEST if not withdrawn.выведен(с.domain))
    выведенный = next(с for с in MANIFEST if withdrawn.выведен(с.domain))
    проекты = [{"id": 1, "url": активный.domain, "site": активный.domain, "on": -1},
               {"id": 2, "url": выведенный.domain, "site": выведенный.domain, "on": -1}]
    клиент = КлиентУчёта(проекты)
    отправлено: list[tuple[str, dict]] = []
    исходный = клиент.call
    клиент.call = lambda m, p: (отправлено.append((m, p)), исходный(m, p))[1]
    monkeypatch.setattr(cli, "_client", lambda *a, **k: клиент)
    cli.cmd_apply(argparse.Namespace())
    capsys.readouterr()
    вернуть = [п for м, п in отправлено if м == "edit/projects_2/projects/on"]
    assert вернуть == [{"filters": [{"name": "id", "operator": "EQUALS", "values": [1]}], "on": 0}]
