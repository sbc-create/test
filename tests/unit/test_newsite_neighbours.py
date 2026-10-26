"""Проверка «путь не ведёт к соседу» обязана иметь, с чем сверять.

`run.py: foreign_paths` есть у каждой витрины с самого начала, но
`neighbour_site_ids` генератор оставлял ПУСТЫМ — у всех проектов без
исключения. Пустой перечень делает проверку тождественно пустой: путь к данным
чужой витрины прошёл бы запуск молча. Это хуже отсутствия проверки, потому что
механизм выглядит защитой и ничего не измеряет, а межсайтовая утечка названа в
Definition of Done.

Проверяется и перечень, и то, что он РАБОТАЕТ: подменённый путь должен ловиться.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.cell import newsite


def _реестр(tmp_path: Path, ид: tuple[str, ...]) -> Path:
    путь = tmp_path / "site-cells.json"
    путь.write_text(json.dumps({"schema_version": "1.0", "cells": [
        {"site_id": s, "domain": f"{s}.test", "aliases": [], "status": "live",
         "repo": {"kind": "local", "path": f"var/site-repos/{s}"},
         "template": {"template_id": "lords-serials", "family": "lords"},
         "pins": {}, "deploy_target": {"ref": "k2-zomro-01"},
         "publisher": {}, "data": {}}
        for s in ид]}, ensure_ascii=False), encoding="utf-8")
    return путь


def test_соседи_берутся_из_реестра_без_самой_ячейки(tmp_path: Path):
    путь = _реестр(tmp_path, ("lords-18", "lords-19", "lords-20"))
    соседи = newsite.соседние_ячейки("lords-19", путь)
    assert соседи == ["lords-18", "lords-20"]


def test_недоступный_реестр_даёт_пустой_перечень(tmp_path: Path):
    """Генератор не вправе отказать из-за реестра и не вправе выдумывать."""
    assert newsite.соседние_ячейки("lords-19", tmp_path / "нет-такого.json") == []


def test_проверка_ловит_путь_к_данным_соседа(tmp_path: Path):
    """Главное: перечень не украшение, а то, с чем сверяет пусковая проверка."""
    import importlib.util

    путь_ран = Path("var/new-sites/lords-18/run.py")
    if not путь_ран.is_file():
        pytest.skip("проекта lords-18 нет в рабочей копии")
    spec = importlib.util.spec_from_file_location("run_lords", путь_ран)
    м = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(м)

    config = {"site_id": "lords-18", "neighbour_site_ids": ["lords-19", "lords-20"]}
    свои = {"LORDS_CATALOG": "/srv/lordserials1-cc/data/lords-18-catalog.json"}
    чужие = {"LORDS_CATALOG": "/srv/lordserials1-info/data/lords-19-catalog.json"}
    assert м.foreign_paths(свои, config) == []
    плохие = м.foreign_paths(чужие, config)
    assert плохие and "lords-19" in плохие[0]


def test_пустой_перечень_делает_проверку_тождественно_пустой(tmp_path: Path):
    """Именно это и было: доказательство того, что пустота опасна."""
    import importlib.util

    путь_ран = Path("var/new-sites/lords-18/run.py")
    if not путь_ран.is_file():
        pytest.skip("проекта lords-18 нет в рабочей копии")
    spec = importlib.util.spec_from_file_location("run_lords2", путь_ран)
    м = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(м)

    чужие = {"LORDS_CATALOG": "/srv/lordserials1-info/data/lords-19-catalog.json"}
    assert м.foreign_paths(чужие, {"site_id": "lords-18", "neighbour_site_ids": []}) == []


def test_новый_проект_получает_требование_к_подборкам():
    """Механизм подборок обязан наследоваться новыми сайтами, а не вспоминаться.

    Требование владельца 26.10: качественные подборки — постоянное требование
    ко всей активной сети, и оно закрепляется в том числе в приёмке новых
    сайтов. Проверяется источник генератора: AGENTS.md каждого нового проекта
    называет требования, команду приёмки и схему, а также честно оговаривает,
    что мобильный сценарий этой командой не измеряется.
    """
    источник = Path(newsite.__file__).read_text(encoding="utf-8")
    assert "collections-acceptance.py" in источник
    assert "schemas/site-collections.schema.json" in источник
    assert "индексации" in источник and "профилю этого домена" in источник
    assert "НЕ измеряется" in источник


# --- Путь проекта в паспорте -------------------------------------------------

def test_путь_проекта_в_паспорте_относителен_корню(tmp_path):
    """Абсолютный путь одного рабочего дерева в реестре — неверная настройка.

    Измерено 26.10 при перезакреплении пятёрки на исправленную основу:
    генератор записывал в паспорт `/home/claude/wt-nova-publish-memory-02/var/
    new-sites/lords-18`, и это попало бы в коммит. Реестр читают другие
    рабочие деревья, другие машины и проверки — для них такой путь неверен, а
    выглядит как настройка, а не как след чужой машины.
    """
    from factory.cell import newsite

    корень = tmp_path / "repo"
    (корень / "var" / "new-sites" / "lords-99").mkdir(parents=True)
    заказ = newsite.Заказ(site_id="lords-99", domain="proba.invalid",
                          profile="lords-serials", port=9199, family="lords")
    паспорт = newsite.паспорт_ячейки(
        заказ, куда=корень / "var" / "new-sites" / "lords-99",
        аккаунт="lords-99", корень_сайта="/srv/lords-99", корень=корень)
    assert паспорт.repo["path"] == "var/new-sites/lords-99"


def test_путь_снаружи_корня_остаётся_абсолютным(tmp_path):
    """Относительным его не сделать, а выдумывать другой нельзя."""
    from factory.cell import newsite

    корень = tmp_path / "repo"
    корень.mkdir()
    снаружи = tmp_path / "другое-дерево" / "lords-99"
    снаружи.mkdir(parents=True)
    заказ = newsite.Заказ(site_id="lords-99", domain="proba.invalid",
                          profile="lords-serials", port=9199, family="lords")
    паспорт = newsite.паспорт_ячейки(заказ, куда=снаружи, аккаунт="lords-99",
                                     корень_сайта="/srv/lords-99", корень=корень)
    assert паспорт.repo["path"] == str(снаружи)


def test_новый_проект_получает_правило_закрытия_задачи():
    """Правило закрытия наследуется новыми сайтами, а не живёт в одном месте.

    Поручение владельца 26.10: задача закрывается только после достижения и
    проверки заявленного результата, и это касается всех исполнителей. Правило
    стоит в CLAUDE.md и docs/LONG_RUNS.md; новый сайт получает его в своём
    AGENTS.md, иначе исполнитель этого сайта о нём не узнает.
    """
    источник = Path(newsite.__file__).read_text(encoding="utf-8")
    assert "Задача закрывается только после достижения и проверки" in источник
    assert "ПОВТОРИТЬ проверку в той же задаче" in источник
    assert "подтверждения принявшего" in источник
    корень = Path(newsite.__file__).resolve().parents[2]
    for файл in ("CLAUDE.md", "docs/LONG_RUNS.md"):
        текст = (корень / файл).read_text(encoding="utf-8")
        assert "задача закрывается только после достижения" in текст.lower(), файл
