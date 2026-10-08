"""Публикация, названная заданием, оставляет след в журнале очереди.

Публикация идёт инструментом моста, а очередь о ней не узнавала. Измерено
2026-10-08: описание `animedia.space/title/detektivnoe-agentstvo-li/`
опубликовано 2026-10-07T09:32:13Z по журналу хранилища накладок, задание на
этот адрес зарегистрировано минутой раньше, а последний `published_at` в
реестре очереди относился к 2026-09-21. Связи между работой и её публичным
результатом не было ни в одну сторону.

Ключевое свойство: отметка — это СЛЕД, а не разрешение. Она не меняет статус
задания (его выводят ворота из текста, источников и адреса) и не подтверждает
публичную видимость. И её отказ не отменяет публикацию: текст на странице уже
стоит, и терять сделанную работу из-за журнала нельзя.
"""

from __future__ import annotations

from factory.qwen import mcp


ИТОГ = {
    "site": "animedia.icu", "slug": "пример", "state": "confirmed",
    "generation_id": "qwen-пример-1", "canonical_url": "https://animedia.icu/title/пример/",
}


def test_без_task_id_журнал_не_трогается(monkeypatch):
    вызовы = []
    monkeypatch.setattr(mcp.editorial, "публиковать",
                        lambda *а, **к: dict(ИТОГ))
    from factory.qwen import queue_bridge as мост
    monkeypatch.setattr(мост, "отметить_публикацию",
                        lambda **к: вызовы.append(к) or {"noted": True})
    ответ = mcp.инструмент_публикации({"site": "animedia.icu", "slug": "пример",
                                       "body": "текст"})
    assert ответ["confirmed"] is True
    assert "queue_note" not in ответ
    assert вызовы == []


def test_с_task_id_событие_уходит_в_журнал(monkeypatch):
    вызовы = []
    monkeypatch.setattr(mcp.editorial, "публиковать",
                        lambda *а, **к: dict(ИТОГ))
    from factory.qwen import queue_bridge as мост
    monkeypatch.setattr(мост, "отметить_публикацию",
                        lambda **к: вызовы.append(к) or {"noted": True, **к})
    ответ = mcp.инструмент_публикации({"site": "animedia.icu", "slug": "пример",
                                       "body": "текст", "task_id": "abc123",
                                       "author": "editor/ночь/run-1"})
    assert ответ["queue_note"]["noted"] is True
    assert вызовы and вызовы[0]["task_id"] == "abc123"
    assert вызовы[0]["generation_id"] == "qwen-пример-1"
    assert вызовы[0]["author"] == "editor/ночь/run-1"


def test_отказ_журнала_публикацию_не_отменяет(monkeypatch):
    """Самое важное свойство: журнал не становится условием успеха."""
    monkeypatch.setattr(mcp.editorial, "публиковать",
                        lambda *а, **к: dict(ИТОГ))
    from factory.qwen import queue_bridge as мост

    def падать(**к):
        raise RuntimeError("очередь не ответила")

    monkeypatch.setattr(мост, "отметить_публикацию", падать)
    ответ = mcp.инструмент_публикации({"site": "animedia.icu", "slug": "пример",
                                       "body": "текст", "task_id": "abc123"})
    assert ответ["confirmed"] is True, ответ
    assert ответ["queue_note"]["noted"] is False
    assert "очередь не ответила" in ответ["queue_note"]["error"]


def test_схема_объявляет_task_id_необязательным():
    схема = mcp.ИНСТРУМЕНТЫ["publish_material"]["схема"]
    assert "task_id" in схема["properties"]
    assert "task_id" not in схема["required"]


def test_отметка_не_несёт_ни_статуса_ни_исхода(monkeypatch):
    """Отметка — след, а не разрешение: статус выводят ворота, не вызывающий."""
    from factory.qwen import queue_bridge as мост

    отправлено = {}
    monkeypatch.setattr(мост, "_вызвать",
                        lambda з, **к: отправлено.update(з) or {"noted": True})
    мост.отметить_публикацию(task_id="abc123", generation_id="g1",
                             canonical_url="https://пример.test/title/x/",
                             author="editor/ночь/run-1")
    assert отправлено["op"] == "published"
    # Ни статуса, ни исхода, ни тела: журнал не способ повысить запись.
    assert not {"status", "outcome", "body", "facts"} & set(отправлено)
