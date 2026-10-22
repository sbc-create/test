"""Изоляция работы по доменам: своя копия, своя ветка, без общих веток.

Задание владельца требует изолированных рабочих каталогов и веток для задач.
Проверяется ИЗМЕРЕННОЕ поле `work` очереди, а не объявление: изоляция,
записанная руками и отсутствующая на диске, хуже отсутствующей — по ней начнут
работать.

Отдельно закреплено различение, на котором я уже ошибалась: у витрин K2
локального РАЗЛОЖЕННОГО выпуска нет (код работает на узле), но репозиторий
исходников локально ЕСТЬ. Это два разных факта, и путать их нельзя.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
СПИСОК = КОРЕНЬ / "config" / "active-domains.json"
ОЧЕРЕДИ = КОРЕНЬ / "config" / "domain-queues"

_сп = importlib.util.spec_from_file_location(
    "record_isolation", КОРЕНЬ / "automation" / "local" / "record-isolation.py")
мера = importlib.util.module_from_spec(_сп)
_сп.loader.exec_module(мера)


@pytest.fixture(scope="module")
def очереди() -> dict[str, dict]:
    return {ф.stem: json.loads(ф.read_text(encoding="utf-8"))
            for ф in sorted(ОЧЕРЕДИ.glob("*.json"))}


def test_у_каждого_домена_записана_изоляция(очереди):
    без = [и for и, о in очереди.items() if not о.get("work")]
    assert not без, без


def test_у_каждого_домена_своя_рабочая_копия(очереди):
    копии = [о["work"]["repo"] for о in очереди.values()]
    повторы = {к: [и for и, о in очереди.items() if о["work"]["repo"] == к]
               for к in set(копии) if копии.count(к) > 1}
    assert not повторы, повторы


def test_ветку_не_делят_несколько_домéнов(очереди):
    """Общая ветка означает, что две линии правят одно дерево."""
    ветки = [о["work"]["branch"] for о in очереди.values()
             if о["work"]["branch"] and о["work"]["branch"] != мера.ОТСОЕДИНЁН]
    повторы = {в: [и for и, о in очереди.items() if о["work"]["branch"] == в]
               for в in set(ветки) if ветки.count(в) > 1}
    assert not повторы, повторы


def test_каждая_изоляция_несёт_время_замера(очереди):
    """Изоляция — измеренный факт, а не объявление: у него есть дата."""
    без = [и for и, о in очереди.items()
           if len(о["work"].get("measured_at") or "") < 10]
    assert not без, без


def test_отсоединённый_HEAD_назван_в_примечании(очереди):
    """Отсоединённое состояние не прячется: по нему легко потерять работу."""
    отсоединённые = {и: о["work"] for и, о in очереди.items()
                     if о["work"]["branch"] == мера.ОТСОЕДИНЁН}
    for и, w in отсоединённые.items():
        assert "ОТСОЕДИНЁННЫЙ" in (w.get("note") or ""), и


def test_домен_без_репозитория_не_выдаётся_за_изолированный(очереди):
    пустые = {и: о["work"] for и, о in очереди.items()
              if not о["work"]["branch"]}
    for и, w in пустые.items():
        assert "не найден" in (w.get("note") or "") or "не объявлен" in (
            w.get("note") or ""), (и, w)


def test_мера_различает_отсоединённое_состояние(tmp_path, monkeypatch):
    ячейки = {"x": {"repo": {"path": "repo-x"}}}
    (tmp_path / "repo-x" / ".git").mkdir(parents=True)
    monkeypatch.setattr(мера, "БАЗЫ", (tmp_path,))
    monkeypatch.setattr(мера, "ветка_копии", lambda п: "HEAD")
    и = мера.изоляция("x", ячейки)
    assert и["branch"] == "HEAD"
    assert "ОТСОЕДИНЁННЫЙ" in и["note"]


def test_мера_различает_отсутствующий_каталог(tmp_path, monkeypatch):
    monkeypatch.setattr(мера, "БАЗЫ", (tmp_path,))
    и = мера.изоляция("x", {"x": {"repo": {"path": "нет-такого"}}})
    assert и["branch"] == ""
    assert "не найден" in и["note"]


def test_мера_различает_необъявленный_путь():
    и = мера.изоляция("x", {"x": {}})
    assert и["branch"] == ""
    assert "не объявлен" in и["note"]


def test_обычная_ветка_называется_своей(tmp_path, monkeypatch):
    """Граница с другой стороны: исправный случай не помечается тревогой."""
    ячейки = {"x": {"repo": {"path": "repo-x"}}}
    (tmp_path / "repo-x" / ".git").mkdir(parents=True)
    monkeypatch.setattr(мера, "БАЗЫ", (tmp_path,))
    monkeypatch.setattr(мера, "ветка_копии", lambda п: "claude/extract-x")
    и = мера.изоляция("x", ячейки)
    assert и["branch"] == "claude/extract-x"
    assert "своя копия и своя ветка" in и["note"]


def test_витрины_K2_имеют_локальный_репозиторий_исходников(очереди):
    """Разложенного выпуска у них локально нет, а репозиторий — есть.

    Это различение я уже путала: `network-state.py` печатает у K2 «—»,
    потому что смотрит на РАСКЛАДКУ, и из этого был сделан неверный вывод
    «у K2 нет ни ветки, ни репозитория».
    """
    k2 = [и for и, о in очереди.items() if о["family"] == "k2"]
    assert len(k2) == 8, k2
    без = [и for и in k2 if not очереди[и]["work"]["branch"]]
    assert not без, без
