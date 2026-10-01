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

    def searchers(self, ид):  # noqa: ARG002
        self.вызовы.append("get/projects_2/searchers")
        raise FactoryError("Метод get/projects_2/searchers не в списке разрешённых",
                           required_input="имя метода чтения поисковых систем")

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


def test_поисковые_системы_не_добавляются_вслепую(monkeypatch, capsys, полный_манифест):
    """Читать нечем — значит не добавляем: слепой add создал бы дубли."""
    клиент = КлиентУчёта(полный_манифест)
    monkeypatch.setattr(cli, "_client", lambda *a, **k: клиент)
    cli.cmd_apply(argparse.Namespace())
    capsys.readouterr()
    assert "add/projects_2/searchers" not in клиент.вызовы
