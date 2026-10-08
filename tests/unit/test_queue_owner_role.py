"""Задание берёт редактор. Сторона SEO регистрирует и ищет, но не берёт.

Распределение принято в `docs/SEO_REGULAR_RUN.md` §3. Измерено 2026-10-09 по
журналу очереди за 8–9 октября: из 130 выдач 42 ушли владельцам
`seo-analysis-*`, `seo-analyst-*`, `seo-analyzer-*` — стороне, которая по
договорённости задания не берёт. Один и тот же адрес при этом брали несколько
владельцев, и ни один не знал о других.

Главное свойство заставы — соразмерность. Отвергается названная сторона SEO, а
имя БЕЗ роли не отвергается: так названы действующие редакторы
(`editor-bot-20261008`, `editor_automation`, `claude`), и остановить их ради
формы имени значило бы остановить редакционную работу. Им возвращается
заметка, а задание выдаётся.
"""

from __future__ import annotations

import pytest

from factory.qwen import queue_bridge as qb


@pytest.mark.parametrize("имя", [
    "seo-analysis-2026-10-08",
    "seo-analyst-2026-10-07-cycle2",
    "seo-analyzer-2026-10-08",
    "seo_regular_20261009",
    "seo/regular/run-7",
])
def test_сторона_seo_задания_не_берёт(имя):
    можно, причина = qb.брать_задания_вправе(имя)
    assert можно is False
    assert "SEO" in причина
    assert "SEO_REGULAR_RUN" in причина


@pytest.mark.parametrize("имя", [
    "editor/claude-auto/run-20261008T233001Z",
    "editor-bot-20261008",
    "editor_automation",
    "claude",
    "qwen-editor-manual-20261006-1505",
])
def test_редактора_застава_не_останавливает(имя):
    можно, _ = qb.брать_задания_вправе(имя)
    assert можно is True


def test_роль_читается_до_косой_черты():
    assert qb.роль_владельца("editor/claude-auto/run-1") == ("editor", True)
    assert qb.роль_владельца("editor-bot-20261008") == ("editor-bot-20261008", False)


def test_выдача_отказана_без_обращения_к_очереди(monkeypatch):
    """Отказ по роли не создаёт аренду: очередь даже не спрашивается."""
    вызовы = []
    monkeypatch.setattr(qb, "_вызвать", lambda з, **к: вызовы.append(з) or {})
    итог = qb.взять(site="animedia.icu", owner="seo-analysis-2026-10-08")
    assert итог["claimed"] == 0
    assert итог["tasks"] == []
    assert "SEO" in итог["blocked_reason"]
    assert вызовы == []


def test_имя_без_роли_получает_заметку_но_не_отказ(monkeypatch):
    monkeypatch.setattr(qb, "доставка_описаний", lambda site: (True, ""))
    monkeypatch.setattr(qb, "_вызвать",
                        lambda з, **к: {"tasks": [{"task_id": "a1"}]})
    итог = qb.взять(site="animedia.icu", owner="editor-bot-20261008")
    assert итог["claimed"] == 1
    assert "не называет роль" in итог["owner_name_note"]
    assert "работу не останавливает" in итог["owner_name_note"]


def test_согласованная_форма_имени_заметки_не_получает(monkeypatch):
    monkeypatch.setattr(qb, "доставка_описаний", lambda site: (True, ""))
    monkeypatch.setattr(qb, "_вызвать",
                        lambda з, **к: {"tasks": [{"task_id": "a1"}]})
    итог = qb.взять(site="animedia.icu",
                    owner="editor/claude-auto/run-20261009T000000Z")
    assert "owner_name_note" not in итог


def test_регистрация_стороне_seo_остаётся_разрешённой(monkeypatch):
    """§3 оставляет регистрацию за SEO: застава касается только выдачи."""
    monkeypatch.setattr(qb, "доставка_описаний", lambda site: (True, ""))
    monkeypatch.setattr(qb, "_вызвать", lambda з, **к: {"created": True})
    итог = qb.завести(site="animedia.icu",
                      canonical_url="https://animedia.icu/title/x/",
                      headline="X")
    assert итог["created"] is True
