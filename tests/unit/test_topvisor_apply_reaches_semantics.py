"""`topvisor apply` обязан доходить до семантики, даже когда проектов создавать нечего.

Повод. План отвечает ровно на один вопрос: какие проекты создать. Когда все
объявленные манифестом проекты уже существуют, план пуст — и команда выходила
`return 0` со словами «желаемое состояние уже достигнуто», не дойдя до второй
фазы. Девять новых проектов так и стояли с нулём групп и нулём запросов, а отчёт
выглядел успешным: «0 изменений» читается как «всё на месте».

Пустой проект — не мониторинг, а запись о намерении. Поэтому проверяется
поведение команды, а не наличие строки в коде.
"""
from __future__ import annotations

import argparse
from typing import Any

import pytest

from factory.topvisor import cli


class КлиентЗаглушка:
    """Отвечает как сервис: проекты есть, семантики нет."""

    def __init__(self, проекты: list[dict]) -> None:
        self._проекты = проекты
        self.создано: list[tuple[str, dict]] = []
        self.группы: dict[Any, list[dict]] = {}

    def projects(self) -> list[dict]:
        return list(self._проекты)

    def keyword_groups(self, ид) -> list[dict]:
        return list(self.группы.get(ид, []))

    def keywords(self, ид) -> list[dict]:  # noqa: ARG002
        return []

    def projects_with_regions(self) -> list[dict]:
        # Регионов нет, справочник пуст: ключа региона нет — значит, и
        # региона не добавляется. Стенд не придумывает ответ сервиса.
        return list(self._проекты)

    def find_regions(self, *a, **k):  # noqa: ARG002
        return []

    def call(self, method: str, payload: dict):
        self.создано.append((method, payload))
        if method == "add/keywords_2/groups":
            ид = payload["project_id"]
            следующий = sum(len(v) for v in self.группы.values()) + 1
            self.группы.setdefault(ид, []).append(
                {"id": следующий, "name": payload["name"]})
        if method == "add/positions_2/searchers":
            # Как сервис: добавленная система видна при следующем чтении.
            for п in self._проекты:
                if п["id"] == payload["project_id"]:
                    п.setdefault("searchers", []).append(
                        {"key": payload["searcher_key"], "regions": []})
        return {"result": 1}


@pytest.fixture()
def все_проекты() -> tuple[list[dict], Any]:
    """Все проекты манифеста уже существуют — ровно то состояние, на котором ломалось.

    Подавать один проект нельзя: план тогда не пуст (остальные шестнадцать надо
    создать), и проверялся бы не тот случай.
    """
    from factory.topvisor.manifest import MANIFEST
    проекты = [{"id": 4000 + н, "url": с.domain, "site": с.domain}
               for н, с in enumerate(MANIFEST)]
    from factory.cell import withdrawn
    # Исключённые из продвижения сайты (решение 25.10.2026) семантику не получают.
    spec = next(с for с in MANIFEST if с.groups and not withdrawn.выведен(с.domain))
    выбранный = next(p for p in проекты if p["site"] == spec.domain)
    return проекты, (spec, выбранный["id"])


def test_пустой_план_не_прекращает_работу(monkeypatch, capsys, все_проекты):
    проекты, (spec, ид) = все_проекты
    клиент = КлиентЗаглушка(проекты)
    monkeypatch.setattr(cli, "_client", lambda *a, **k: клиент)

    код = cli.cmd_apply(argparse.Namespace())
    assert код == 0

    вывод = capsys.readouterr().out
    assert "желаемое состояние уже достигнуто" not in вывод, (
        "команда снова объявляет успех, не дойдя до семантики")
    assert not [m for m, _ in клиент.создано if m == "add/projects_2/projects"], (
        "план не был пуст — проверялся не тот случай")
    from factory.topvisor.manifest import с_ядром
    # Группы стратегии манифеста и измеренные входы ядра (config/topvisor-cores.json).
    мои = [p for m, p in клиент.создано
           if m == "add/keywords_2/groups" and p["project_id"] == ид]
    assert len(мои) == len(с_ядром(spec).groups), (
        f"группы не создавались: {клиент.создано[:3]}")
    запросы = [p for m, p in клиент.создано if m == "add/keywords_2/keywords"]
    assert запросы, "запросы не добавлялись"
    assert "Групп создано:" in вывод


def test_повторный_запуск_не_создаёт_дублей(monkeypatch, capsys, все_проекты):
    """Идемпотентность по имени: второй проход не добавляет ни группы, ни запроса."""
    from factory.topvisor.manifest import MANIFEST
    проекты, _ = все_проекты
    клиент = КлиентЗаглушка(проекты)
    monkeypatch.setattr(cli, "_client", lambda *a, **k: клиент)
    cli.cmd_apply(argparse.Namespace())
    было = len(клиент.создано)
    assert было, "первый проход ничего не создал — сравнивать не с чем"

    from factory.topvisor.manifest import с_ядром
    все_запросы = {к for с in MANIFEST for г in с_ядром(с).groups for к in г.keywords}

    class Полный(КлиентЗаглушка):
        def keywords(self, ид):  # noqa: ARG002
            return [{"name": к} for к in все_запросы]

    второй = Полный(проекты)
    второй.группы = клиент.группы
    monkeypatch.setattr(cli, "_client", lambda *a, **k: второй)
    cli.cmd_apply(argparse.Namespace())
    capsys.readouterr()
    assert not второй.создано, (
        f"повторный запуск создал дубли: {второй.создано} (первый — {было} действий)")


def test_чужой_домен_не_трогается(monkeypatch, capsys, все_проекты):
    """Проект, которого нет в манифесте, не получает ни группы, ни запроса.

    Семантика берётся из манифеста по домену. Проект, которого там нет, — чужой
    или посторонний, и трогать его фабрика права не имеет.
    """
    проекты, _ = все_проекты
    чужой = {"id": 99_999, "url": "посторонний.example", "site": "посторонний.example"}
    клиент = КлиентЗаглушка([*проекты, чужой])
    monkeypatch.setattr(cli, "_client", lambda *a, **k: клиент)
    cli.cmd_apply(argparse.Namespace())
    capsys.readouterr()
    тронут = [p for _, p in клиент.создано if p.get("project_id") == чужой["id"]]
    assert not тронут, f"посторонний проект получил действия: {тронут}"
