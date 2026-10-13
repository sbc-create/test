"""Исключение сайта из общего продвижения: запись, чтение, обработчики.

Задание 2026-10-13 на партию из восьми витрин требует исключить их из общей
редакционной и SEO-очереди, генерации описаний и комментариев, периодических
автоматических SEO-правок, блоков продвижения, межсайтовой перелинковки и
плана выхода на целевой трафик — и «зафиксировать исключение в конфигурации И
ОБРАБОТЧИКАХ, чтобы следующий общий прогон не подключил эти домены обратно».

Отсюда три группы проверок, и каждая падает на неисправленном состоянии:

1. Запись доживает до следующей записи. Паспорт печатается перечислением
   полей руками, и три блока в перечислении отсутствовали: `indexing` (19
   ячеек), `analytics` (15 ячеек) и новый `promotion`. Любая повторная
   регистрация снимала их молча — то есть снимала бы и исключение.
2. Запрет — проверка на пути общего прогона, а не отсутствие имени в чьём-то
   перечне. Поэтому исключённый домен не попадает в `allowed_domains()` ДАЖЕ
   если он прописан в `EDITOR_SITES`: именно так выглядит «общий прогон
   подключил домен обратно».
3. Что исключение НЕ выключает: проверки доступности, резервное копирование и
   выпуск. Сайт без продвижения — работающий сайт, а не выключенный.
"""
from __future__ import annotations

import dataclasses
import json

import pytest

from factory.cell import registry


def _реестр(tmp_path, *ячейки):
    путь = tmp_path / "site-cells.json"
    путь.write_text(json.dumps({"schema_version": registry.SCHEMA_VERSION,
                                "cells": list(ячейки)}, ensure_ascii=False),
                    encoding="utf-8")
    return путь


def _ячейка(site_id="lords-10", domain="lordfilm.group", **поля):
    запись = {
        "site_id": site_id,
        "domain": domain,
        "aliases": [],
        "status": "planned",
        "repo": {"kind": "local", "path": f"var/new-sites/{site_id}"},
        "template": {"template_id": "lords-films", "family": "lords"},
        "pins": {},
        "deploy_target": {},
        "publisher": {},
        "data": {"database": None, "media": None},
        "deployed": {},
        "content_revision": None,
        "last_update": None,
        "backup": {},
        "resources": {},
        "runtime": {"unit": f"nova-{site_id}.service", "port": 9125},
        "release": {},
    }
    запись.update(поля)
    return запись


# --- 1. запись доживает до следующей записи -------------------------------

def test_печать_паспорта_перечисляет_все_поля_модели():
    """Поле, которого нет в to_dict(), теряется при каждой записи.

    Проверка общая нарочно: она ловит не три известных блока, а любое
    следующее поле, добавленное в модель и забытое в печати.
    """
    поля = {f.name for f in dataclasses.fields(registry.Cell)}
    напечатано = set(registry.Cell(
        site_id="x", domain="x.test", aliases=(), repo={}, template={}, pins={},
        deploy_target={}, publisher={}, data={}).to_dict())
    assert поля - напечатано == set(), (
        f"эти поля паспорта не печатаются и пропадут при записи: "
        f"{sorted(поля - напечатано)}")


@pytest.mark.parametrize("блок,значение", [
    ("indexing", {"desired_state": "CLOSED", "reason": "ещё не принят"}),
    ("analytics", {"counter_id": "104058001", "state": "connected"}),
    ("promotion", {"excluded": True, "scopes": ["editorial_queue"],
                   "reason": "партия без продвижения", "authority": "владелец"}),
])
def test_повторная_запись_не_снимает_блок(tmp_path, блок, значение):
    путь = _реестр(tmp_path, _ячейка(**{блок: значение}))
    было = registry.resolve("lords-10", путь)
    assert getattr(было, блок) == значение

    registry.register(было, path=путь, replace=True)

    стало = registry.resolve("lords-10", путь)
    assert getattr(стало, блок) == значение, (
        f"блок {блок} снят повторной записью паспорта")
    сырое = json.loads(путь.read_text(encoding="utf-8"))["cells"][0]
    assert блок in сырое


# --- 2. запрет читается обработчиками ------------------------------------

def test_исключение_требует_причины_и_основания(tmp_path):
    путь = _реестр(tmp_path, _ячейка())
    with pytest.raises(registry.RegistryError, match="BLOCKED_INPUT"):
        registry.объявить_исключение("lords-10", excluded=True, reason="",
                                     authority="владелец", path=путь)
    with pytest.raises(registry.RegistryError, match="BLOCKED_INPUT"):
        registry.объявить_исключение("lords-10", excluded=True, reason="партия",
                                     authority="  ", path=путь)


def test_придуманная_область_отвергается(tmp_path):
    """Область без обработчика обещала бы запрет, которого никто не исполняет."""
    путь = _реестр(tmp_path, _ячейка())
    with pytest.raises(registry.RegistryError, match="неизвестные области"):
        registry.объявить_исключение(
            "lords-10", excluded=True, reason="партия", authority="владелец",
            scopes=("editorial_queue", "всё_остальное"), path=путь)


def test_отсутствие_блока_это_не_исключение(tmp_path):
    """Поведение действующих сайтов не меняется от появления поля."""
    путь = _реестр(tmp_path, _ячейка(site_id="lords-01", domain="lordfilm47.space"))
    действующий = registry.resolve("lords-01", путь)
    assert registry.исключён_из_продвижения(действующий) is False
    assert registry.исключённые_домены(путь) == frozenset()


def test_исключение_по_областям(tmp_path):
    путь = _реестр(tmp_path, _ячейка())
    registry.объявить_исключение(
        "lords-10", excluded=True, reason="партия витрин без продвижения",
        authority="задание владельца 2026-10-13",
        scopes=("editorial_queue", "comment_generation"), path=путь)
    ячейка = registry.resolve("lords-10", путь)
    assert registry.исключён_из_продвижения(ячейка) is True
    assert registry.исключён_из_продвижения(ячейка, "editorial_queue") is True
    # Область, которой в записи нет, не считается исключённой: исключение,
    # записанное наполовину, не должно читаться как полное.
    assert registry.исключён_из_продвижения(ячейка, "periodic_seo_edits") is False
    assert registry.исключённые_домены(путь, "editorial_queue") == {"lordfilm.group"}
    assert registry.исключённые_домены(путь, "periodic_seo_edits") == frozenset()


def test_псевдонимы_исключаются_вместе_с_доменом(tmp_path):
    путь = _реестр(tmp_path, _ячейка(aliases=["www.lordfilm.group"]))
    registry.объявить_исключение(
        "lords-10", excluded=True, reason="партия", authority="владелец", path=путь)
    assert registry.исключённые_домены(путь) == {"lordfilm.group",
                                                 "www.lordfilm.group"}


def test_редактор_не_берёт_исключённый_домен_даже_из_своего_перечня(monkeypatch, tmp_path):
    """Главная проверка задания: общий прогон не подключает домен обратно.

    Домен нарочно прописан в `EDITOR_SITES` — так выглядит следующий общий
    прогон, который взял его из реестра и добавил себе в список. Пока запрет
    был «отсутствием имени в перечне», такая правка его отменяла.
    """
    from seo_operator import editor_run, regular

    путь = _реестр(tmp_path, _ячейка())
    registry.объявить_исключение(
        "lords-10", excluded=True, reason="партия витрин без продвижения",
        authority="задание владельца 2026-10-13", path=путь)

    monkeypatch.setattr(regular, "EDITOR_SITES",
                        {**regular.EDITOR_SITES, "lordfilm.group": "lords-10"})
    monkeypatch.setattr(editor_run, "EDITOR_DOMAINS",
                        (*editor_run.EDITOR_DOMAINS, "lordfilm.group"))
    monkeypatch.setattr(registry, "registry_path", lambda: путь)

    домены = editor_run.allowed_domains()
    assert "lordfilm.group" not in домены
    # Остальные домены не затронуты: запрет адресный, а не общий.
    assert "lordfilm47.space" in домены


# --- 3. что исключение НЕ выключает --------------------------------------

def test_проверки_доступности_продолжаются(monkeypatch, tmp_path):
    """Сайт зарегистрирован для поддержки и проверок доступности.

    `discover_domains` — вход проверки доступности и технического SEO. Если
    исключение убрало бы домен оттуда, пропали бы и они.
    """
    from seo_operator import regular

    путь = _реестр(tmp_path, _ячейка())
    registry.объявить_исключение(
        "lords-10", excluded=True, reason="партия", authority="владелец", path=путь)
    monkeypatch.setattr(registry, "registry_path", lambda: путь)

    строки = regular.discover_domains({**regular.SOURCES, "cells": путь})
    свой = [с for с in строки if с["domain"] == "lordfilm.group"]
    assert свой, "исключённый из продвижения домен пропал из проверок доступности"
    assert свой[0]["promotion_excluded"] is True


def test_перечень_операций_не_предлагает_добавление_материала():
    """Генерация описаний и новостей не предлагается исключённому сайту.

    Перечень операций читают и человек, и автоматика. Операция, которая не
    должна исполняться, но предложена, рано или поздно исполняется.
    """
    from factory.qwen import registry as qwen_registry

    сайт = qwen_registry.Сайт(site_id="lords-10", domain="lordfilm.group",
                              adapter="lords", account="lordfilm-group")
    было = set(qwen_registry.доступные_операции(сайт))
    сайт.promotion_excluded = True
    стало = set(qwen_registry.доступные_операции(сайт))

    assert было - стало, "исключение не сняло ни одной операции"
    assert (было - стало) <= qwen_registry.ОПЕРАЦИИ_ПРОДВИЖЕНИЯ
    # Читающие операции остаются: сайт под поддержкой, а не выключен.
    assert {"status", "diagnose", "indexing", "sites"} <= стало


def test_снятие_опубликованного_остаётся_доступным():
    """`unpublish` не входит в снимаемые: запирать содержимое исключение не должно."""
    from factory.qwen import registry as qwen_registry

    assert "unpublish" not in qwen_registry.ОПЕРАЦИИ_ПРОДВИЖЕНИЯ
    assert "posts-unpublish" not in qwen_registry.ОПЕРАЦИИ_ПРОДВИЖЕНИЯ
