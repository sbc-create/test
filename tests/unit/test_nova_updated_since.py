"""Лента изменений источника: чего она НЕ делает при сбое.

Задержка обнаружения — сейчас суточная, потому что система узнаёт о новой
серии из снимка. Источник умеет отвечать «что изменилось с момента X»:
`updated_since` объявлен в замороженном контракте
`knowledge/cdnvideohub/content-api.yaml`, снятом с клиента поставщика. Здесь
закреплено поведение инструмента, который этим пользуется.

Сеть запрещена: ответ источника подставляется.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
ИНСТРУМЕНТ = КОРЕНЬ / "automation" / "host" / "nova-updated-since.py"

спец = importlib.util.spec_from_file_location("_nus", ИНСТРУМЕНТ)
nus = importlib.util.module_from_spec(спец)
sys.modules["_nus"] = nus
спец.loader.exec_module(nus)


def страницы(*ответы):
    очередь = list(ответы)
    def подмена(путь, параметры, ключ, таймаут=30.0):
        return очередь.pop(0)
    return подмена


def test_постраничный_обход_завершается_по_обоим_условиям(monkeypatch):
    """`has_more=true` с пустым курсором зациклил бы обход."""
    monkeypatch.setattr(nus, "страница", страницы(
        {"items": [{"id": "a"}], "has_more": True, "next_cursor": "c1"},
        {"items": [{"id": "b"}], "has_more": True, "next_cursor": ""},
    ))
    assert [з["id"] for з in nus.изменённые("k", "t")] == ["a", "b"]


def test_повтор_курсора_прекращает_обход(monkeypatch):
    monkeypatch.setattr(nus, "страница", страницы(
        {"items": [{"id": "a"}], "has_more": True, "next_cursor": "c1"},
        {"items": [{"id": "b"}], "has_more": True, "next_cursor": "c1"},
    ))
    assert len(nus.изменённые("k", "t")) == 2


def test_отметка_не_двигается_при_недоступном_источнике(tmp_path, monkeypatch):
    """Иначе окно изменений теряется навсегда: витрины о них не узнают."""
    monkeypatch.setattr(nus, "токен", lambda: "k")
    def падать(*а, **к):
        raise nus.ИсточникНедоступен("таймаут")
    monkeypatch.setattr(nus, "изменённые", падать)
    (tmp_path / nus.СОСТОЯНИЕ).write_text(json.dumps({"since": "2026-09-29T00:00:00Z"}),
                                          encoding="utf-8")
    код = nus.main(["--state-dir", str(tmp_path), "--apply"])
    assert код == 1
    assert json.loads((tmp_path / nus.СОСТОЯНИЕ).read_text())["since"] == "2026-09-29T00:00:00Z"


def test_без_apply_отметка_остаётся_прежней(tmp_path, monkeypatch):
    monkeypatch.setattr(nus, "токен", lambda: "k")
    monkeypatch.setattr(nus, "изменённые", lambda *а, **к: [{"id": "x", "slug": "s"}])
    (tmp_path / nus.СОСТОЯНИЕ).write_text(json.dumps({"since": "2026-09-01T00:00:00Z"}),
                                          encoding="utf-8")
    nus.main(["--state-dir", str(tmp_path)])
    assert json.loads((tmp_path / nus.СОСТОЯНИЕ).read_text())["since"] == "2026-09-01T00:00:00Z"
    лента = json.loads((tmp_path / "updates-feed.json").read_text(encoding="utf-8"))
    assert лента["count"] == 1 and лента["items"][0]["slug"] == "s"


def test_запись_без_идентификатора_в_ленту_не_идёт():
    д = nus.лента([{"slug": "s"}, {"id": "a", "slug": "b"}], "t")
    assert д["count"] == 1 and д["items"][0]["id"] == "a"


def test_токен_в_отчёт_не_попадает(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(nus, "токен", lambda: "СЕКРЕТ-НЕ-ПЕЧАТАТЬ")
    monkeypatch.setattr(nus, "изменённые", lambda *а, **к: [])
    nus.main(["--state-dir", str(tmp_path)])
    вывод = capsys.readouterr().out
    assert "СЕКРЕТ" not in вывод
